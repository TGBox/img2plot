"""
Delaunay / Low-Poly Art generation module for img2plot.
Generates geometric wireframe artwork by sampling feature points along edges
and dark regions, performing Delaunay Triangulation, and extracting polygon edges.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, Set, TYPE_CHECKING
import numpy as np
from scipy.spatial import Delaunay

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_delaunay_art(
    gray_image: np.ndarray,
    grad_magnitude: Optional[np.ndarray] = None,
    num_points: int = 800,
    edge_weight: float = 0.6,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate Delaunay low-poly wireframe paths from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        grad_magnitude: Optional Sobel gradient magnitude array, same shape.
        num_points: Total number of interior vertices.
        edge_weight: Weight given to gradient edges (0.0=pure darkness, 1.0=pure edges).
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing triangle edges.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_points < 10:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)

    if grad_magnitude is None:
        gy, gx = np.gradient(gray_image)
        grad_mag = np.hypot(gx, gy)
    else:
        grad_mag = grad_magnitude.copy()

    g_max = float(grad_mag.max())
    if g_max > 0:
        grad_mag /= g_max

    # Combined feature importance map
    weight_map = (1.0 - edge_weight) * darkness + edge_weight * grad_mag
    w_sum = float(np.sum(weight_map))
    if w_sum <= 1e-4:
        weight_map = np.ones_like(weight_map)

    # 1. Sample perimeter border points to anchor the boundary
    border_pts: List[Point2D] = []
    # Corners
    border_pts.extend([(0.0, 0.0), (float(w - 1), 0.0), (float(w - 1), float(h - 1)), (0.0, float(h - 1))])

    # Equispaced border points
    num_border = max(4, int(math.sqrt(num_points)))
    for bx in np.linspace(0, w - 1, num_border):
        border_pts.append((float(bx), 0.0))
        border_pts.append((float(bx), float(h - 1)))
    for by in np.linspace(0, h - 1, num_border):
        border_pts.append((0.0, float(by)))
        border_pts.append((float(w - 1), float(by)))

    # 2. Sample interior feature points based on weight map
    rng = random.Random(1337)
    interior_pts: List[Point2D] = []
    attempts = 0
    max_attempts = num_points * 30

    while len(interior_pts) < num_points and attempts < max_attempts:
        if attempts % 1000 == 0 and is_cancelled and is_cancelled():
            return []

        attempts += 1
        rx = rng.uniform(2.0, w - 3.0)
        ry = rng.uniform(2.0, h - 3.0)
        ix = int(rx)
        iy = int(ry)

        val = float(weight_map[iy, ix])
        if rng.random() < val:
            interior_pts.append((rx, ry))

    all_pts = np.array(border_pts + interior_pts, dtype=np.float32)

    if len(all_pts) < 4:
        return []

    if is_cancelled and is_cancelled():
        return []

    # 3. Compute Delaunay Triangulation
    tri = Delaunay(all_pts)

    # 4. Extract unique edges
    edges: Set[Tuple[int, int]] = set()
    for simplex in tri.simplices:
        for i in range(3):
            u, v = simplex[i], simplex[(i + 1) % 3]
            if u > v:
                u, v = v, u
            edges.add((u, v))

    paths: List[StrokePath] = []
    for u, v in edges:
        p1 = (float(all_pts[u, 0]), float(all_pts[u, 1]))
        p2 = (float(all_pts[v, 0]), float(all_pts[v, 1]))
        svg_d = f"M {p1[0]:.2f},{p1[1]:.2f} L {p2[0]:.2f},{p2[1]:.2f}"
        paths.append(StrokePath(points=[p1, p2], svg_d=svg_d))

    return paths
