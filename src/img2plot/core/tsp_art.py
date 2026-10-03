"""
TSP (Travelling Salesperson Problem) Art generation module for img2plot.
Converts an image into stipple points proportional to local darkness and edge gradients,
then solves a continuous single-line TSP tour using 2D Hilbert space-filling curve
ordering and fast cyclic windowed + spatial KD-tree 2-opt edge-swap optimization.
The entire artwork is rendered as a single continuous line with zero pen lifts.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
from scipy.spatial import KDTree

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_tsp_art(
    gray_image: np.ndarray,
    num_points: int = 2200,
    two_opt_passes: int = 15,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate a high-fidelity single-line TSP drawing from a grayscale image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_points: Target number of stipple points (approx 800..4000).
        two_opt_passes: Number of 2-opt untangling passes (approx 5..30).
        is_cancelled: Optional cancellation callback.

    Returns:
        List containing a single continuous StrokePath representing the TSP tour.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_points < 10:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)

    # Edge gradient magnitude to accentuate fine contours and silhouettes
    gy, gx = np.gradient(gray_image)
    grad_mag = np.hypot(gx, gy)
    g_max = float(grad_mag.max())
    if g_max > 0:
        grad_mag /= g_max

    # Combined visual importance map: deep shadows + sharp edges
    weight_map = 0.65 * np.power(darkness, 1.5) + 0.35 * np.power(grad_mag, 1.2)
    # Highlight suppression: leave clean white paper with zero ink
    weight_map[weight_map < 0.07] = 0.0

    total_weight = float(np.sum(weight_map))
    if total_weight <= 1e-4:
        return []

    if is_cancelled and is_cancelled():
        return []

    # 1. Feature-weighted Importance Sampling with subpixel jitter
    points = _sample_stipple_points(weight_map, w, h, num_points)
    if len(points) < 4:
        return []

    if is_cancelled and is_cancelled():
        return []

    # 2. Continuous 2D Hilbert Space-Filling Curve Tour Initialization
    tour = _build_hilbert_tour(points, w, h)

    if is_cancelled and is_cancelled():
        return []

    # 3. Fast Cyclic Windowed and Spatial 2-Opt Optimization
    tour = _optimize_tour_2opt(tour, passes=two_opt_passes, is_cancelled=is_cancelled)

    # Close the tour by returning to starting point
    tour.append(tour[0])

    svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in tour)
    return [StrokePath(points=tour, svg_d=svg_d)]


def _sample_stipple_points(
    weight_map: np.ndarray, w: int, h: int, target_count: int
) -> List[Point2D]:
    """Sample points with spatial distribution strictly proportional to feature weight."""
    rng = random.Random(42)  # Deterministic seed for reproducible art
    flat_weights = weight_map.flatten()
    total = float(np.sum(flat_weights))
    if total <= 1e-6:
        return []

    prob = flat_weights / total
    non_zero_count = int(np.count_nonzero(prob > 0))
    sample_size = min(target_count, non_zero_count)
    if sample_size < 4:
        return []

    # Rejection / choice sampling without replacement
    sampled_indices = np.random.RandomState(42).choice(
        len(prob), size=sample_size, replace=False, p=prob
    )

    points: List[Point2D] = []
    for idx in sampled_indices:
        y = idx // w
        x = idx % w
        # Subpixel jitter
        jx = float(x) + rng.uniform(-0.35, 0.35)
        jy = float(y) + rng.uniform(-0.35, 0.35)
        points.append((max(0.0, min(float(w - 1), jx)), max(0.0, min(float(h - 1), jy))))

    return points


def _xy_to_hilbert(n: int, x: int, y: int) -> int:
    """Map 2D grid coordinates to 1D distance along a Hilbert curve of size n (n power of 2)."""
    d = 0
    s = n // 2
    curr_x, curr_y = x, y
    while s > 0:
        rx = 1 if (curr_x & s) > 0 else 0
        ry = 1 if (curr_y & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                curr_x = (s - 1) - curr_x
                curr_y = (s - 1) - curr_y
            curr_x, curr_y = curr_y, curr_x
        s //= 2
    return d


def _build_hilbert_tour(points: List[Point2D], w: int, h: int) -> List[Point2D]:
    """Build an initial tour sorted by a continuous 2D Hilbert space-filling curve."""
    grid_size = 1024
    norm_pts = []
    for px, py in points:
        ix = int(max(0, min(grid_size - 1, (px / float(w)) * grid_size)))
        iy = int(max(0, min(grid_size - 1, (py / float(h)) * grid_size)))
        h_idx = _xy_to_hilbert(grid_size, ix, iy)
        norm_pts.append((h_idx, px, py))

    norm_pts.sort(key=lambda t: t[0])
    return [(p[1], p[2]) for p in norm_pts]


def _optimize_tour_2opt(
    tour: List[Point2D], passes: int = 15, is_cancelled: Optional[Callable[[], bool]] = None
) -> List[Point2D]:
    """Untangle tour using fast windowed cyclic 2-opt and KD-tree edge swaps."""
    n = len(tour)
    if n < 4 or passes < 1:
        return tour

    pts = np.array(tour, dtype=np.float32)

    # 1. Windowed cyclic 2-opt (resolves 95% of adjacent crossings)
    window = min(40, max(15, n // 50))
    for pass_idx in range(passes):
        if is_cancelled and is_cancelled():
            break

        improved = False
        step = 1 if n < 2000 else 2
        for i in range(0, n, step):
            i_next = (i + 1) % n
            p1 = pts[i]
            p2 = pts[i_next]
            d12 = math.hypot(p1[0] - p2[0], p1[1] - p2[1])

            for offset in range(2, window):
                j = (i + offset) % n
                j_next = (j + 1) % n
                if j == i or j_next == i or j == i_next:
                    continue

                p3 = pts[j]
                p4 = pts[j_next]

                d_curr = d12 + math.hypot(p3[0] - p4[0], p3[1] - p4[1])
                d_swap = math.hypot(p1[0] - p3[0], p1[1] - p3[1]) + math.hypot(p2[0] - p4[0], p2[1] - p4[1])

                if d_curr - d_swap > 1e-2:
                    if i < j:
                        pts[i + 1 : j + 1] = pts[i + 1 : j + 1][::-1]
                    improved = True
                    break

        if not improved:
            break

    # 2. Spatial KDTree pass for remaining spatial edge overlaps
    tree = KDTree(pts)
    for _ in range(min(5, max(2, passes // 3))):
        if is_cancelled and is_cancelled():
            break
        improved = False
        for i in range(0, n, 2):
            i_next = (i + 1) % n
            p1 = pts[i]
            p2 = pts[i_next]
            d12 = math.hypot(p1[0] - p2[0], p1[1] - p2[1])

            _, nbrs = tree.query(p1, k=min(16, n))
            for j in nbrs:
                if j == i or j == i_next or abs(j - i) <= 1:
                    continue
                j_next = (j + 1) % n
                p3 = pts[j]
                p4 = pts[j_next]
                d_curr = d12 + math.hypot(p3[0] - p4[0], p3[1] - p4[1])
                d_swap = math.hypot(p1[0] - p3[0], p1[1] - p3[1]) + math.hypot(p2[0] - p4[0], p2[1] - p4[1])

                if d_curr - d_swap > 1e-2:
                    if i < j:
                        pts[i + 1 : j + 1] = pts[i + 1 : j + 1][::-1]
                    improved = True
                    break
        if not improved:
            break

    return [(float(p[0]), float(p[1])) for p in pts]
