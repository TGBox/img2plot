"""
Waveform / Joy Division art generation module for img2plot.
Generates stacked topographic scanlines modulated by image darkness,
with optional 3D hidden-line occlusion (front-to-back horizon masking).
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage

if TYPE_CHECKING:
    from .engine import StrokePath

from .bezier import fit_cubic_spline, segments_to_svg_path

Point2D = Tuple[float, float]


def generate_waveform(
    gray_image: np.ndarray,
    num_lines: int = 60,
    amplitude: float = 20.0,
    resolution: int = 250,
    occlusion: bool = True,
    smoothness: float = 1.5,
    margin_ratio: float = 0.05,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate topographic waveform lines across a grayscale image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_lines: Number of horizontal scanlines.
        amplitude: Max peak height displacement in pixels.
        resolution: Number of sample points per scanline.
        occlusion: If True, occluded lines behind peaks are hidden (Joy Division style).
        smoothness: Gaussian sigma applied along scanline brightness profile.
        margin_ratio: Margin fraction on each side of the image.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing the waveform artwork.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 2 or w < 2 or num_lines < 1 or resolution < 2:
        return []

    x_start = w * margin_ratio
    x_end = w * (1.0 - margin_ratio)
    y_start = h * margin_ratio + amplitude  # Room for top peaks
    y_end = h * (1.0 - margin_ratio)

    y_bases = np.linspace(y_start, y_end, num_lines)
    x_coords = np.linspace(x_start, x_end, resolution)

    # Invert grayscale so dark areas produce high peaks (darkness in [0, 1])
    darkness = 1.0 - gray_image

    paths: List[StrokePath] = []

    # If occlusion is enabled, we track the horizon line.
    # Lines are ordered from bottom (front) to top (back).
    # Peaks displace upward (negative delta Y).
    # A point is visible if its Y is smaller (higher up) than the lowest horizon seen in front of it.
    horizon = np.full(resolution, np.inf, dtype=np.float32)

    # Process from bottom (foreground) to top (background)
    for y_idx in reversed(range(num_lines)):
        if is_cancelled and is_cancelled():
            break

        y_base = y_bases[y_idx]

        # Sample darkness along the horizontal line
        y_int = int(round(np.clip(y_base, 0, h - 1)))
        # Bilinear or nearest sampling along x
        xs_int = np.clip(np.round(x_coords).astype(int), 0, w - 1)
        row_darkness = darkness[y_int, xs_int].astype(np.float32)

        # Smooth the profile along the line for organic curves
        if smoothness > 0.0:
            row_darkness = scipy.ndimage.gaussian_filter1d(row_darkness, sigma=smoothness, mode="nearest")

        # Displace Y coordinates upward (toward 0) based on darkness
        y_pts = y_base - (row_darkness * amplitude)

        if not occlusion:
            # Complete uninterrupted line across the image
            pts: List[Point2D] = [(float(x), float(y)) for x, y in zip(x_coords, y_pts)]
            if len(pts) >= 2:
                svg_d = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in pts)
                paths.append(StrokePath(points=pts, svg_d=svg_d))
        else:
            # Hidden-line occlusion: break into visible segments
            current_segment: List[Point2D] = []
            new_horizon = horizon.copy()

            for i in range(resolution):
                px = float(x_coords[i])
                py = float(y_pts[i])

                # Visible if it rises above (y < horizon) or near the horizon
                if py <= horizon[i] + 0.1:
                    current_segment.append((px, py))
                    if py < new_horizon[i]:
                        new_horizon[i] = py
                else:
                    # Line fell behind the foreground horizon
                    if len(current_segment) >= 2:
                        svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in current_segment)
                        paths.append(StrokePath(points=current_segment, svg_d=svg_d))
                    current_segment = []

            if len(current_segment) >= 2:
                svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in current_segment)
                paths.append(StrokePath(points=current_segment, svg_d=svg_d))

            horizon = new_horizon

    # Reverse paths so they are ordered top-to-bottom for natural plotter execution
    paths.reverse()
    return paths
