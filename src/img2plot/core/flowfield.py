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
import scipy.ndimage

if TYPE_CHECKING:
    from .engine import StrokePath

from .bezier import fit_cubic_spline, segments_to_svg_path

Point2D = Tuple[float, float]


def generate_flowfield(
    gray_image: np.ndarray,
    num_lines: int = 1000,
    step_len: float = 2.5,
    max_steps: int = 50,
    direction: str = "tangent",
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate flow field streamlines along image contours and gradients.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_lines: Target number of streamlines.
        step_len: Integration step size in pixels.
        max_steps: Max steps per streamline in each direction.
        direction: "tangent" (flows along edges) or "gradient" (flows across edges).
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing flow field strokes.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_lines < 1:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)

    # 1. Pre-smooth image slightly so gradient vectors produce coherent curves
    smooth_img = scipy.ndimage.gaussian_filter(gray_image, sigma=1.8)
    gy, gx = np.gradient(smooth_img)
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

    # Smooth the vector field so subtle regions inherit coherent flow from nearby edges
    smooth_vx = scipy.ndimage.gaussian_filter(vx, sigma=2.5)
    smooth_vy = scipy.ndimage.gaussian_filter(vy, sigma=2.5)
    flow_len = np.hypot(smooth_vx, smooth_vy)
    flow_len = np.maximum(1e-6, flow_len)
    flow_x = smooth_vx / flow_len
    flow_y = smooth_vy / flow_len

    # Seeding weight: focus strictly on shadows and edges
    seed_weight = 0.65 * np.power(darkness, 1.4) + 0.35 * np.power(norm_mag, 1.2)
    has_contrast = bool(np.max(seed_weight) > 0.12)
    if has_contrast:
        # Mask out flat, empty white background
        seed_weight[seed_weight < 0.06] = 0.0

    total_weight = float(np.sum(seed_weight))
    if total_weight <= 1e-4:
        seed_weight = np.ones_like(seed_weight)
        total_weight = float(np.sum(seed_weight))

    # 2. Importance sampling of seed points
    flat_weights = seed_weight.flatten()
    prob = flat_weights / total_weight
    non_zero = int(np.count_nonzero(prob > 0))
    sample_size = min(num_lines, non_zero)
    if sample_size < 1:
        return []

    sampled_indices = np.random.RandomState(2026).choice(
        len(prob), size=sample_size, replace=False, p=prob
    )

    rng = random.Random(2026)
    seeds: List[Point2D] = []
    for idx in sampled_indices:
        y = idx // w
        x = idx % w
        seeds.append((float(x) + rng.uniform(-0.4, 0.4), float(y) + rng.uniform(-0.4, 0.4)))

    # 3. Spatial occupancy grid to avoid overlapping strokes
    cell_size = max(2.5, step_len * 1.3)
    grid_w = max(1, int(w / cell_size) + 1)
    grid_h = max(1, int(h / cell_size) + 1)
    visited_grid = np.zeros((grid_h, grid_w), dtype=np.int32)

    paths: List[StrokePath] = []
    yield_step = max(50, len(seeds) // 20)

    for s_idx, (sx, sy) in enumerate(seeds):
        if s_idx % yield_step == 0 and is_cancelled and is_cancelled():
            break

        gcx = int(sx / cell_size)
        gcy = int(sy / cell_size)
        if 0 <= gcx < grid_w and 0 <= gcy < grid_h:
            if visited_grid[gcy, gcx] >= 2:
                continue

        # Forward integration
        fwd_pts: List[Point2D] = []
        curr_x, curr_y = sx, sy
        for _ in range(max_steps):
            ix = int(round(curr_x))
            iy = int(round(curr_y))
            if not (0 <= ix < w and 0 <= iy < h):
                break
            if has_contrast and darkness[iy, ix] < 0.04 and norm_mag[iy, ix] < 0.04:
                break
            gcx = int(curr_x / cell_size)
            gcy = int(curr_y / cell_size)
            if 0 <= gcx < grid_w and 0 <= gcy < grid_h:
                if visited_grid[gcy, gcx] >= 3:
                    break
                visited_grid[gcy, gcx] += 1

            dx = float(flow_x[iy, ix])
            dy = float(flow_y[iy, ix])
            next_x = curr_x + dx * step_len
            next_y = curr_y + dy * step_len
            if not (1.0 <= next_x < w - 2.0 and 1.0 <= next_y < h - 2.0):
                break
            fwd_pts.append((next_x, next_y))
            curr_x, curr_y = next_x, next_y

        # Backward integration
        bwd_pts: List[Point2D] = []
        curr_x, curr_y = sx, sy
        for _ in range(max_steps):
            ix = int(round(curr_x))
            iy = int(round(curr_y))
            if not (0 <= ix < w and 0 <= iy < h):
                break
            if has_contrast and darkness[iy, ix] < 0.04 and norm_mag[iy, ix] < 0.04:
                break
            gcx = int(curr_x / cell_size)
            gcy = int(curr_y / cell_size)
            if 0 <= gcx < grid_w and 0 <= gcy < grid_h:
                if visited_grid[gcy, gcx] >= 3:
                    break
                visited_grid[gcy, gcx] += 1

            dx = -float(flow_x[iy, ix])
            dy = -float(flow_y[iy, ix])
            next_x = curr_x + dx * step_len
            next_y = curr_y + dy * step_len
            if not (1.0 <= next_x < w - 2.0 and 1.0 <= next_y < h - 2.0):
                break
            bwd_pts.append((next_x, next_y))
            curr_x, curr_y = next_x, next_y

        full_line = list(reversed(bwd_pts)) + [(sx, sy)] + fwd_pts
        if len(full_line) >= 4:
            cubic_segs = fit_cubic_spline(full_line, tension=0.35, sample_step=2)
            svg_d = segments_to_svg_path(cubic_segs)
            paths.append(StrokePath(points=full_line, is_bezier=True, cubic_segments=cubic_segs, svg_d=svg_d))
        elif len(full_line) >= 2:
            svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in full_line)
            paths.append(StrokePath(points=full_line, svg_d=svg_d))

    return paths
