"""
Flow Field / Van Gogh Streamlines module for img2plot.
Generates organic, fluid brushstrokes that flow along image contours,
isoclines, and gradient fields, inspired by impressionist line drawings.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .engine import StrokePath

from .bezier import fit_cubic_spline, segments_to_svg_path

Point2D = Tuple[float, float]


def generate_flowfield(
    gray_image: np.ndarray,
    num_lines: int = 800,
    step_len: float = 3.0,
    max_steps: int = 40,
    direction: str = "tangent",
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate flow field streamlines along image contours and gradients.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_lines: Target number of streamlines.
        step_len: Integration step size in pixels.
        max_steps: Max steps per streamline.
        direction: "tangent" (flows along edges) or "gradient" (flows across edges).
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing flow field strokes.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_lines < 1:
        return []

    # 1. Compute gradients and normalized flow field
    gy, gx = np.gradient(gray_image)
    mag = np.hypot(gx, gy)
    max_mag = float(mag.max())
    if max_mag > 0:
        norm_mag = mag / max_mag
    else:
        norm_mag = np.zeros_like(mag)

    # Tangent field flows along contours (orthogonal to gradient)
    if direction == "tangent":
        vx = -gy
        vy = gx
    else:
        vx = gx
        vy = gy

    # Base noise angle for flat areas so streamlines have an organic swirl
    yy, xx = np.mgrid[0:h, 0:w]
    ambient_angle = np.sin(xx / 35.0) * np.cos(yy / 35.0) * math.pi
    amb_x = np.cos(ambient_angle)
    amb_y = np.sin(ambient_angle)

    # Blend between image contour direction and ambient flow
    flow_x = norm_mag * vx + (1.0 - norm_mag) * amb_x
    flow_y = norm_mag * vy + (1.0 - norm_mag) * amb_y

    flow_len = np.hypot(flow_x, flow_y)
    flow_len = np.maximum(1e-6, flow_len)
    flow_x /= flow_len
    flow_y /= flow_len

    # Darkness map for seeding
    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)
    seed_weight = 0.6 * darkness + 0.4 * norm_mag

    # 2. Seed streamlines
    rng = random.Random(2026)
    seeds: List[Point2D] = []
    attempts = 0
    max_attempts = num_lines * 15

    while len(seeds) < num_lines and attempts < max_attempts:
        attempts += 1
        rx = rng.uniform(4.0, w - 5.0)
        ry = rng.uniform(4.0, h - 5.0)
        ix = int(rx)
        iy = int(ry)

        prob = float(seed_weight[iy, ix])
        if rng.random() < max(0.15, prob):
            seeds.append((rx, ry))

    # 3. Integrate streamlines with spatial spacing grid
    cell_size = max(4.0, step_len * 1.5)
    grid_w = max(1, int(w / cell_size) + 1)
    grid_h = max(1, int(h / cell_size) + 1)
    visited_grid = np.zeros((grid_h, grid_w), dtype=np.int32)

    paths: List[StrokePath] = []

    for s_idx, (sx, sy) in enumerate(seeds):
        if s_idx % 100 == 0 and is_cancelled and is_cancelled():
            break

        pts: List[Point2D] = [(sx, sy)]
        curr_x, curr_y = sx, sy

        for _ in range(max_steps):
            ix = int(round(curr_x))
            iy = int(round(curr_y))

            if not (0 <= ix < w and 0 <= iy < h):
                break

            # Grid cell collision check
            gcx = int(curr_x / cell_size)
            gcy = int(curr_y / cell_size)
            if 0 <= gcx < grid_w and 0 <= gcy < grid_h:
                if visited_grid[gcy, gcx] >= 2:
                    break
                visited_grid[gcy, gcx] += 1

            dx = float(flow_x[iy, ix])
            dy = float(flow_y[iy, ix])

            next_x = curr_x + dx * step_len
            next_y = curr_y + dy * step_len

            if not (1.0 <= next_x < w - 2.0 and 1.0 <= next_y < h - 2.0):
                break

            pts.append((next_x, next_y))
            curr_x, curr_y = next_x, next_y

        if len(pts) >= 4:
            cubic_segs = fit_cubic_spline(pts, tension=0.35, sample_step=2)
            svg_d = segments_to_svg_path(cubic_segs)
            paths.append(StrokePath(points=pts, is_bezier=True, cubic_segments=cubic_segs, svg_d=svg_d))
        elif len(pts) >= 2:
            svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
            paths.append(StrokePath(points=pts, svg_d=svg_d))

    return paths
