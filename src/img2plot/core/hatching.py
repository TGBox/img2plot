"""
Hatching and cross-hatching generator for shaded and shadow regions.
Supports straight lines as well as organic, form-following Bezier curves that adapt
to the underlying surface contours and luminance gradients.
"""

from __future__ import annotations
import math
import time
from typing import List, Tuple, Optional, Callable
import numpy as np
import scipy.ndimage

from .bezier import Point, CubicSegment, fit_cubic_spline, segments_to_svg_path


class HatchStroke:
    """
    Represents a single hatching stroke.
    Maintains compatibility with tuple unpacking (p_start, p_end) while providing
    full vector stroke properties (points, bezier segments, svg_d).
    """

    def __init__(
        self,
        points: List[Point],
        is_bezier: bool = False,
        cubic_segments: Optional[List[CubicSegment]] = None,
        svg_d: str = "",
    ):
        self.points = points
        self.is_bezier = is_bezier
        self.cubic_segments = cubic_segments or []
        self.svg_d = svg_d
        self.is_hatch = True

    def length(self) -> float:
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(len(self.points) - 1):
            total += math.hypot(
                self.points[i + 1][0] - self.points[i][0],
                self.points[i + 1][1] - self.points[i][1],
            )
        return total

    def __iter__(self):
        """Allows unpacking as (start_point, end_point) for backward compatibility."""
        if len(self.points) >= 2:
            return iter((self.points[0], self.points[-1]))
        elif len(self.points) == 1:
            return iter((self.points[0], self.points[0]))
        return iter(())

    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int) -> Point:
        if index == 0:
            return self.points[0]
        elif index == 1:
            return self.points[-1]
        raise IndexError("HatchStroke only supports index 0 (start) and 1 (end)")


def compute_contour_flow_field(
    gray_image: np.ndarray,
    guide_angle_deg: float,
    curve_strength: float = 0.65,
    is_cross_hatch: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute a 2D unit vector field (vx, vy) that smoothly blends the global guide angle
    with local surface contour directions (isophotes) extracted from image gradients.
    """
    h, w = gray_image.shape

    # Smooth the luminance to produce stable, noise-free contour flow
    sigma = max(2.0, min(h, w) / 150.0)
    smoothed = scipy.ndimage.gaussian_filter(gray_image, sigma=sigma)

    # Compute spatial image gradients
    gy, gx = np.gradient(smoothed)
    grad_mag = np.hypot(gx, gy)

    # Base guide direction vector
    angle_rad = math.radians(guide_angle_deg)
    if is_cross_hatch:
        angle_rad += math.pi / 2.0

    guide_x = math.cos(angle_rad)
    guide_y = math.sin(angle_rad)

    # Normalise gradients
    eps = 1e-6
    norm_gx = gx / (grad_mag + eps)
    norm_gy = gy / (grad_mag + eps)

    # Contour tangent (perpendicular to gradient: along constant brightness curves)
    if not is_cross_hatch:
        tangent_x = -norm_gy
        tangent_y = norm_gx
    else:
        # Cross pass flows along the gradient direction (slope)
        tangent_x = norm_gx
        tangent_y = norm_gy

    # Orient tangent into the same hemisphere as the guide vector
    dot = tangent_x * guide_x + tangent_y * guide_y
    flip_mask = dot < 0
    tangent_x[flip_mask] = -tangent_x[flip_mask]
    tangent_y[flip_mask] = -tangent_y[flip_mask]

    # Contrast-dependent blend weight: flat areas keep the guide angle,
    # contrasted/curved areas follow the surface contour
    ref_mag = float(np.percentile(grad_mag, 75)) if np.any(grad_mag > 1e-4) else 1.0
    ref_mag = max(1e-4, ref_mag)
    weight = np.clip(grad_mag / ref_mag, 0.0, 1.0) * np.clip(curve_strength, 0.0, 1.0)

    # Blend vectors
    flow_x = (1.0 - weight) * guide_x + weight * tangent_x
    flow_y = (1.0 - weight) * guide_y + weight * tangent_y

    # Normalize flow field
    flow_len = np.hypot(flow_x, flow_y) + eps
    flow_x /= flow_len
    flow_y /= flow_len

    return flow_x, flow_y


def generate_hatching(
    gray_image: np.ndarray,
    threshold: float = 0.35,
    spacing: int = 10,
    angle_deg: float = 45.0,
    cross_hatch: bool = False,
    min_length: int = 6,
    mode: str = "bezier",
    curve_strength: float = 0.65,
    wobble: float = 0.0,
    bezier_smoothness: float = 0.35,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[HatchStroke]:
    """
    Generate hatching strokes across regions darker than the given threshold.
    Supports straight lines as well as organic, form-following Bezier curves.
    
    Args:
        gray_image: 2D numpy array with values in [0.0, 1.0].
        threshold: Gray value below which hatching is applied (0=black, 1=white).
        spacing: Pixel distance between parallel hatching lines.
        angle_deg: Primary orientation angle in degrees.
        cross_hatch: If True, adds perpendicular hatching for deep shadows.
        min_length: Minimum stroke length in pixels to keep.
        mode: "bezier" for form-following curved strokes, "straight" for classic lines.
        curve_strength: Influence of underlying surface curvature (0.0=straight, 1.0=full contour flow).
        wobble: Subtle organic hand-drawn wobble amplitude in pixels.
        bezier_smoothness: Tangent smoothness factor for cubic Bezier fitting.
        
    Returns:
        List of HatchStroke objects (iterable as (start_pt, end_pt) for backward compatibility).
    """
    h, w = gray_image.shape
    if h == 0 or w == 0:
        return []

    dark_mask = gray_image < threshold
    if not np.any(dark_mask):
        return []

    use_bezier = mode.lower() == "bezier"
    strokes: List[HatchStroke] = []

    # --- First Pass ---
    flow_x, flow_y = compute_contour_flow_field(
        gray_image=gray_image,
        guide_angle_deg=angle_deg,
        curve_strength=curve_strength if use_bezier else 0.0,
        is_cross_hatch=False,
    )

    strokes.extend(
        _trace_streamlines(
            mask=dark_mask,
            flow_x=flow_x,
            flow_y=flow_y,
            spacing=spacing,
            base_angle_deg=angle_deg,
            min_length=min_length,
            use_bezier=use_bezier,
            bezier_smoothness=bezier_smoothness,
            wobble=wobble,
            is_cancelled=is_cancelled,
        )
    )

    if is_cancelled and is_cancelled():
        return strokes

    # --- Second Pass for Cross-Hatching ---
    if cross_hatch:
        deep_dark_mask = gray_image < (threshold * 0.8)
        if np.any(deep_dark_mask):
            cross_flow_x, cross_flow_y = compute_contour_flow_field(
                gray_image=gray_image,
                guide_angle_deg=angle_deg,
                curve_strength=curve_strength if use_bezier else 0.0,
                is_cross_hatch=True,
            )

            strokes.extend(
                _trace_streamlines(
                    mask=deep_dark_mask,
                    flow_x=cross_flow_x,
                    flow_y=cross_flow_y,
                    spacing=spacing,
                    base_angle_deg=angle_deg + 90.0,
                    min_length=min_length,
                    use_bezier=use_bezier,
                    bezier_smoothness=bezier_smoothness,
                    wobble=wobble,
                    is_cancelled=is_cancelled,
                )
            )

    return strokes


def _trace_streamlines(
    mask: np.ndarray,
    flow_x: np.ndarray,
    flow_y: np.ndarray,
    spacing: int,
    base_angle_deg: float,
    min_length: int,
    use_bezier: bool,
    bezier_smoothness: float,
    wobble: float = 0.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[HatchStroke]:
    """
    Trace curved or straight streamlines through the mask guided by the flow field.
    """
    h, w = mask.shape
    rad = math.radians(base_angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Perpendicular vector to step between parallel scanlines
    perp_x = -sin_a
    perp_y = cos_a

    diag = math.hypot(w, h)
    cx, cy = w / 2.0, h / 2.0

    num_lines = int(diag / max(1, spacing)) + 1
    half_lines = num_lines // 2

    step_size = 2.0
    max_steps = int(diag / step_size)

    strokes: List[HatchStroke] = []
    # Grid to prevent overlapping parallel tracks from colliding
    visited_mask = np.zeros((h, w), dtype=bool)

    for i in range(-half_lines, half_lines + 1):
        if is_cancelled and is_cancelled():
            break
        if i % 15 == 0:
            time.sleep(0.0001)
        offset = i * spacing
        bx = cx + offset * perp_x
        by = cy + offset * perp_y

        s = -max_steps // 2
        while s < max_steps // 2:
            # Check along guide line for start of dark region
            px = bx + s * step_size * cos_a
            py = by + s * step_size * sin_a
            s += 1

            ix = int(round(px))
            iy = int(round(py))

            if not (0 <= ix < w and 0 <= iy < h):
                continue
            if not mask[iy, ix] or visited_mask[iy, ix]:
                continue

            # Start tracing streamline from this seed
            stroke_pts: List[Point] = [(px, py)]
            curr_x, curr_y = px, py
            total_len = 0.0
            step_count = 0

            # Trace forward following the vector field
            while total_len < diag:
                step_count += 1
                c_ix = max(0, min(w - 1, int(round(curr_x))))
                c_iy = max(0, min(h - 1, int(round(curr_y))))

                if not mask[c_iy, c_ix]:
                    break

                # Mark visited in small neighborhood to maintain breathing room between strokes
                visited_mask[c_iy, c_ix] = True

                if use_bezier:
                    # Sample vector field
                    vx = float(flow_x[c_iy, c_ix])
                    vy = float(flow_y[c_iy, c_ix])
                else:
                    vx, vy = cos_a, sin_a

                # Add subtle hand-drawn wobble if requested
                if wobble > 0.0:
                    wobble_offset = math.sin(step_count * 0.35) * wobble
                    w_perp_x = -vy * wobble_offset
                    w_perp_y = vx * wobble_offset
                else:
                    w_perp_x = 0.0
                    w_perp_y = 0.0

                next_x = curr_x + vx * step_size + w_perp_x
                next_y = curr_y + vy * step_size + w_perp_y

                n_ix = int(round(next_x))
                n_iy = int(round(next_y))

                if not (0 <= n_ix < w and 0 <= n_iy < h):
                    break
                if not mask[n_iy, n_ix]:
                    break

                dist = math.hypot(next_x - curr_x, next_y - curr_y)
                total_len += dist
                stroke_pts.append((next_x, next_y))
                curr_x, curr_y = next_x, next_y

            # Check if stroke meets minimum length criteria
            if total_len >= min_length and len(stroke_pts) >= 2:
                if use_bezier and len(stroke_pts) >= 3:
                    cubic_segs = fit_cubic_spline(
                        stroke_pts,
                        tension=bezier_smoothness,
                        sample_step=2,
                    )
                    svg_d = segments_to_svg_path(cubic_segs)
                    stroke = HatchStroke(
                        points=stroke_pts,
                        is_bezier=True,
                        cubic_segments=cubic_segs,
                        svg_d=svg_d,
                    )
                else:
                    start_pt = stroke_pts[0]
                    end_pt = stroke_pts[-1]
                    svg_d = f"M {start_pt[0]:.2f},{start_pt[1]:.2f} L {end_pt[0]:.2f},{end_pt[1]:.2f}"
                    stroke = HatchStroke(
                        points=[start_pt, end_pt],
                        is_bezier=False,
                        svg_d=svg_d,
                    )
                strokes.append(stroke)

    return strokes
