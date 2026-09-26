"""
Hatching / Cross-hatching generator for shaded and shadow regions.
"""

from __future__ import annotations
import math
import numpy as np
from typing import List, Tuple

Point = Tuple[float, float]
LineSegment = Tuple[Point, Point]


def generate_hatching(
    gray_image: np.ndarray,
    threshold: float = 0.35,
    spacing: int = 10,
    angle_deg: float = 45.0,
    cross_hatch: bool = False,
    min_length: int = 6,
) -> List[LineSegment]:
    """
    Generate hatching lines across regions darker than the given threshold.
    
    Args:
        gray_image: 2D numpy array with values in [0.0, 1.0].
        threshold: Gray value below which hatching is applied (0=black, 1=white).
        spacing: Pixel distance between parallel hatching lines.
        angle_deg: Orientation angle in degrees.
        cross_hatch: If True, adds perpendicular hatching for deep shadows.
        min_length: Minimum stroke length in pixels to keep.
        
    Returns:
        List of line segments ((x1, y1), (x2, y2)).
    """
    h, w = gray_image.shape
    if h == 0 or w == 0:
        return []

    dark_mask = gray_image < threshold
    if not np.any(dark_mask):
        return []

    strokes: List[LineSegment] = []

    # First pass
    strokes.extend(
        _trace_hatch_lines(dark_mask, spacing=spacing, angle_deg=angle_deg, min_length=min_length)
    )

    # Second pass for cross-hatching in deeper shadows
    if cross_hatch:
        deep_dark_mask = gray_image < (threshold * 0.8)
        strokes.extend(
            _trace_hatch_lines(
                deep_dark_mask,
                spacing=spacing,
                angle_deg=angle_deg + 90.0,
                min_length=min_length,
            )
        )

    return strokes


def _trace_hatch_lines(
    mask: np.ndarray,
    spacing: int,
    angle_deg: float,
    min_length: int
) -> List[LineSegment]:
    """Internal helper to trace parallel lines across a binary mask."""
    h, w = mask.shape
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Perpendicular vector to step between lines
    perp_x = -sin_a
    perp_y = cos_a

    # Bounding box diagonal and center
    diag = math.hypot(w, h)
    cx, cy = w / 2.0, h / 2.0

    strokes: List[LineSegment] = []
    num_lines = int(diag / max(1, spacing)) + 1
    half_lines = num_lines // 2

    # Step along the line direction in 1-pixel increments
    line_step = 1.0
    max_steps = int(diag)

    for i in range(-half_lines, half_lines + 1):
        offset = i * spacing
        # Base point on the line passing through center + offset * perpendicular
        bx = cx + offset * perp_x
        by = cy + offset * perp_y

        in_stroke = False
        start_pt: Point | None = None
        current_len = 0

        for s in range(-max_steps // 2, max_steps // 2 + 1):
            px = bx + s * line_step * cos_a
            py = by + s * line_step * sin_a

            ix = int(round(px))
            iy = int(round(py))

            is_inside = (0 <= ix < w) and (0 <= iy < h) and mask[iy, ix]

            if is_inside:
                if not in_stroke:
                    in_stroke = True
                    start_pt = (px, py)
                    current_len = 0
                else:
                    current_len += line_step
            else:
                if in_stroke:
                    if current_len >= min_length and start_pt is not None:
                        strokes.append((start_pt, (px, py)))
                    in_stroke = False
                    start_pt = None
                    current_len = 0

        if in_stroke and current_len >= min_length and start_pt is not None:
            # End of line reached
            px = bx + (max_steps // 2) * line_step * cos_a
            py = by + (max_steps // 2) * line_step * sin_a
            strokes.append((start_pt, (px, py)))

    return strokes
