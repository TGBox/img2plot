"""
Archimedean Spiral Art generation module for img2plot.
Generates a continuous spiral winding from center to edges,
with metric arc-length sinusoidal amplitude modulation based on image darkness and edges.
Produces single-stroke continuous plotter art with zero cross-canvas artifacts.
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
    num_loops: int = 70,
    resolution: int = 400,
    amplitude: float = 6.0,
    frequency: float = 30.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate an Archimedean spiral modulated by image darkness and edges.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_loops: Total number of 360-degree spiral revolutions.
        resolution: Points sampled per single revolution.
        amplitude: Max oscillation amplitude in dark areas (pixels).
        frequency: Oscillation frequency parameter (higher = tighter wave frequency).
        is_cancelled: Optional cancellation callback.

    Returns:
        List containing a single continuous StrokePath (or empty if cancelled/invalid).
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 2 or w < 2 or num_loops < 1 or resolution < 4:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)

    # Edge gradient to sharpen fine contours (eyes, beaks, silhouettes)
    gy, gx = np.gradient(gray_image)
    grad_mag = np.hypot(gx, gy)
    g_max = float(grad_mag.max())
    if g_max > 0:
        grad_mag /= g_max

    # Combined feature response: strong shadows + sharp edges
    feature_map = 0.75 * np.power(darkness, 1.4) + 0.25 * np.power(grad_mag, 1.2)
    feature_map = np.clip(feature_map, 0.0, 1.0)
    # Highlights remain clean and smooth
    feature_map[feature_map < 0.06] = 0.0

    cx = w / 2.0
    cy = h / 2.0

    # Scale spiral to cover corners of the canvas
    corner_scale = math.hypot(cx, cy) / max(cx, cy)
    rx_max = cx * corner_scale
    ry_max = cy * corner_scale
    pitch = min(cx, cy) / float(num_loops)

    total_steps = int(num_loops * resolution)
    theta_max = 2.0 * math.pi * num_loops

    # Metric wavelength: constant spatial distance per wave cycle
    # frequency 30 -> ~4.0px wavelength; frequency 15 -> ~8.0px wavelength
    wavelength = max(2.5, 120.0 / max(1.0, frequency))
    max_amp = min(amplitude, pitch * 0.92)

    points: List[Point2D] = []
    s = 0.0
    prev_bx, prev_by = cx, cy

    yield_step = max(500, total_steps // 20)

    for i in range(total_steps):
        if i % yield_step == 0 and is_cancelled and is_cancelled():
            return []

        theta = (i / float(total_steps)) * theta_max
        frac = theta / theta_max

        # Elliptical radius along aspect ratio
        rx = frac * rx_max
        ry = frac * ry_max

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        bx = cx + rx * cos_t
        by = cy + ry * sin_t

        ds = math.hypot(bx - prev_bx, by - prev_by)
        s += ds
        prev_bx, prev_by = bx, by

        # Sample feature map
        ix = int(round(bx))
        iy = int(round(by))
        if 0 <= ix < w and 0 <= iy < h:
            d = float(feature_map[iy, ix])
        else:
            d = 0.0

        # Normal vector to elliptical spiral arm
        tx = -rx * sin_t
        ty = ry * cos_t
        t_len = math.hypot(tx, ty)
        if t_len > 1e-6:
            nx = -ty / t_len
            ny = tx / t_len
        else:
            nx, ny = 0.0, 1.0

        wave = math.sin(2.0 * math.pi * s / wavelength)
        disp = d * max_amp * wave

        px = bx + disp * nx
        py = by + disp * ny

        # Clamp cleanly to canvas boundaries
        px = max(0.0, min(float(w - 1), px))
        py = max(0.0, min(float(h - 1), py))
        points.append((px, py))

    if len(points) < 2:
        return []

    svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in points)
    return [StrokePath(points=points, svg_d=svg_d)]
