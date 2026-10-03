"""
TSP (Travelling Salesperson Problem) Art generation module for img2plot.
Converts an image into stipple points proportional to local darkness, then solves
a continuous single-line TSP tour using KD-tree nearest-neighbor initialization
and fast k-nearest 2-opt edge-swap optimization.
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
    num_points: int = 1200,
    two_opt_passes: int = 15,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate a single-line TSP drawing from a grayscale image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_points: Target number of stipple points (approx 500..3000).
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
    # Apply a slight gamma to boost contrast between highlights and shadows
    darkness = np.power(darkness, 1.3)

    # 1. Stipple Sampling via Jittered Grid & Importance Sampling
    points = _sample_stipple_points(darkness, w, h, num_points)
    if len(points) < 4:
        return []

    if is_cancelled and is_cancelled():
        return []

    # 2. Fast Nearest-Neighbor Tour Initialization
    tour = _build_nearest_neighbor_tour(points)

    if is_cancelled and is_cancelled():
        return []

    # 3. Fast Spatial 2-Opt Optimization
    tour = _optimize_tour_2opt(tour, passes=two_opt_passes, is_cancelled=is_cancelled)

    # Close the tour by returning to starting point
    tour.append(tour[0])

    svg_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in tour)
    return [StrokePath(points=tour, svg_d=svg_d)]


def _sample_stipple_points(
    darkness: np.ndarray, w: int, h: int, target_count: int
) -> List[Point2D]:
    """Sample points with spatial distribution proportional to darkness."""
    rng = random.Random(42)  # Deterministic seed for reproducible art

    # Use a grid with cell size scaled to yield approximately target_count points
    total_darkness = float(np.sum(darkness))
    if total_darkness <= 1e-4:
        return []

    # Estimate average cell dimension
    area = w * h
    grid_res = max(10, int(math.sqrt(target_count * 3)))
    cell_w = w / float(grid_res)
    cell_h = h / float(grid_res)

    candidates: List[Point2D] = []

    for gy in range(grid_res):
        y0 = int(gy * cell_h)
        y1 = min(h, int((gy + 1) * cell_h))
        if y1 <= y0:
            continue

        for gx in range(grid_res):
            x0 = int(gx * cell_w)
            x1 = min(w, int((gx + 1) * cell_w))
            if x1 <= x0:
                continue

            cell_val = float(np.mean(darkness[y0:y1, x0:x1]))
            # Probability of placing point in this cell
            # Scale so total expected points ~ target_count
            prob = cell_val * (target_count / (total_darkness / (w * h) * grid_res * grid_res + 1e-6))

            if rng.random() < prob:
                # Add jittered point within cell
                px = gx * cell_w + rng.uniform(0.1, 0.9) * cell_w
                py = gy * cell_h + rng.uniform(0.1, 0.9) * cell_h
                candidates.append((float(px), float(py)))

    # Adjust to target_count
    if len(candidates) > target_count:
        rng.shuffle(candidates)
        candidates = candidates[:target_count]

    return candidates


def _build_nearest_neighbor_tour(points: List[Point2D]) -> List[Point2D]:
    """Build an initial tour connecting points using nearest-neighbor greedy search."""
    n = len(points)
    pts_arr = np.array(points, dtype=np.float32)
    visited = np.zeros(n, dtype=bool)

    tree = KDTree(pts_arr)
    tour_indices = [0]
    visited[0] = True
    current_idx = 0

    k_search = min(n, 32)
    for _ in range(1, n):
        # Query nearest neighbors
        dists, indices = tree.query(pts_arr[current_idx], k=k_search)
        next_idx = -1
        for idx in indices:
            if not visited[idx]:
                next_idx = idx
                break

        if next_idx == -1:
            # Fallback to linear scan of unvisited
            unvisited = np.where(~visited)[0]
            if len(unvisited) > 0:
                d = np.sum((pts_arr[unvisited] - pts_arr[current_idx]) ** 2, axis=1)
                next_idx = unvisited[np.argmin(d)]
            else:
                break

        visited[next_idx] = True
        tour_indices.append(next_idx)
        current_idx = next_idx

    return [points[i] for i in tour_indices]


def _optimize_tour_2opt(
    tour: List[Point2D], passes: int = 15, is_cancelled: Optional[Callable[[], bool]] = None
) -> List[Point2D]:
    """Untangle tour using fast spatial 2-opt edge swaps."""
    n = len(tour)
    if n < 4 or passes < 1:
        return tour

    pts = np.array(tour, dtype=np.float32)

    # Use KDTree on tour points to quickly find candidate edge intersections
    for pass_idx in range(passes):
        if is_cancelled and is_cancelled():
            break

        improved = False
        tree = KDTree(pts)

        # Check candidate swaps
        step = 1 if n < 1500 else 2
        for i in range(0, n - 2, step):
            p1 = pts[i]
            p2 = pts[i + 1]
            d12 = math.hypot(p1[0] - p2[0], p1[1] - p2[1])

            # Find nearest spatial neighbors to p1 to test as potential j
            _, neighbor_indices = tree.query(p1, k=min(16, n))

            best_gain = 0.0
            best_j = -1

            for j in neighbor_indices:
                if j <= i + 1 or j >= n - 1:
                    continue

                p3 = pts[j]
                p4 = pts[(j + 1) % n]

                # Current distance
                d_curr = d12 + math.hypot(p3[0] - p4[0], p3[1] - p4[1])
                # New distance if edge (i, i+1) and (j, j+1) are swapped
                d_swap = math.hypot(p1[0] - p3[0], p1[1] - p3[1]) + math.hypot(p2[0] - p4[0], p2[1] - p4[1])

                gain = d_curr - d_swap
                if gain > best_gain:
                    best_gain = gain
                    best_j = j

            if best_j != -1 and best_gain > 1e-4:
                # Reverse segment from i+1 to best_j
                pts[i + 1 : best_j + 1] = pts[i + 1 : best_j + 1][::-1]
                improved = True

        if not improved:
            break

    return [(float(p[0]), float(p[1])) for p in pts]
