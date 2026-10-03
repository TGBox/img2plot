"""
Archimedean Spiral Art generation module for img2plot.
Generates a single continuous spiral winding from center to corners,
with high-frequency sinusoidal amplitude modulation based on image darkness.
Produces 100% single-stroke continuous plotter art with zero pen lifts.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_spiral(
    gray_image: np.ndarray,
    num_loops: int = 60,
    resolution: int = 350,
    amplitude: float = 4.0,
    frequency: float = 30.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate an Archimedean spiral modulated by image darkness.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_loops: Total number of 360-degree spiral revolutions.
        resolution: Points sampled per single revolution.
        amplitude: Max oscillation amplitude in dark areas (pixels).
        frequency: Modulation cycles per radian or revolution.
        is_cancelled: Optional cancellation callback.

    Returns:
        List containing a single continuous StrokePath (or empty if cancelled/invalid).
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 2 or w < 2 or num_loops < 1 or resolution < 4:
        return []

    cx = w / 2.0
    cy = h / 2.0
    # Spiral covers the canvas out to the corners
    max_radius = math.hypot(cx, cy) * 0.98

    total_steps = int(num_loops * resolution)
    theta_max = 2.0 * math.pi * num_loops

    darkness = 1.0 - gray_image

    points: List[Point2D] = []

    # Yield GIL occasionally
    yield_step = max(500, total_steps // 20)

    for i in range(total_steps):
        if i % yield_step == 0 and is_cancelled and is_cancelled():
            return []

        theta = (i / float(total_steps)) * theta_max
        # Base Archimedean radius
        r_base = (theta / theta_max) * max_radius

        # Base coordinate on smooth spiral
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        base_x = cx + r_base * cos_t
        base_y = cy + r_base * sin_t

        # If base point is inside image, sample darkness
        ix = int(round(base_x))
        iy = int(round(base_y))

        if 0 <= ix < w and 0 <= iy < h:
            d = float(darkness[iy, ix])
        else:
            d = 0.0

        # Oscillation wave perpendicular to spiral arm
        wave = math.sin(theta * frequency)
        disp = d * amplitude * wave

        # Normal vector perpendicular to radial direction is (-sin_t, cos_t)
        px = base_x - disp * sin_t
        py = base_y + disp * cos_t

        # Only include points inside canvas with slight boundary margin
        if -10 <= px <= w + 10 and -10 <= py <= h + 10:
            points.append((float(px), float(py)))

    if len(points) < 2:
        return []

    # Construct single continuous SVG path
    svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in points)
    return [StrokePath(points=points, svg_d=svg_d)]
