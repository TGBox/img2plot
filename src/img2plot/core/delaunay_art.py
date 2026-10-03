"""
Delaunay / Low-Poly Art generation module for img2plot.
Generates geometric wireframe artwork by placing feature-aware vertices
along image contours, edges, and shadow forms, performing Delaunay Triangulation,
and culling background edges to tightly sculpt the subject's 3D silhouette.
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
    num_points: int = 1200,
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

    # Combined feature importance map: edges and shadows
    weight_map = (1.0 - edge_weight) * np.power(darkness, 1.4) + edge_weight * np.power(grad_mag, 1.2)
    
    # Check if image has identifiable content
    w_sum = float(np.sum(weight_map))
    if w_sum <= 1e-4:
        weight_map = np.ones_like(weight_map)
        w_sum = float(np.sum(weight_map))

    # Mask out flat, low-contrast background unless entire image is uniform
    has_contrast = bool(np.max(weight_map) > 0.15)
    if has_contrast:
        weight_map[weight_map < 0.06] = 0.0
        w_sum = float(np.sum(weight_map))
        if w_sum <= 1e-4:
            weight_map = np.clip(1.0 - gray_image, 0.01, 1.0)
            w_sum = float(np.sum(weight_map))

    # Importance sampling of vertices
    rng = random.Random(1337)
    flat_weights = weight_map.flatten()
    prob = flat_weights / w_sum
    non_zero = int(np.count_nonzero(prob > 0))
    sample_size = min(num_points, non_zero)
    if sample_size < 4:
        return []

    sampled_indices = np.random.RandomState(1337).choice(
        len(prob), size=sample_size, replace=False, p=prob
    )

    vertices: List[Point2D] = []
    for idx in sampled_indices:
        y = idx // w
        x = idx % w
        jx = float(x) + rng.uniform(-0.3, 0.3)
        jy = float(y) + rng.uniform(-0.3, 0.3)
        vertices.append((max(0.0, min(float(w - 1), jx)), max(0.0, min(float(h - 1), jy))))

    all_pts = np.array(vertices, dtype=np.float32)
    if len(all_pts) < 4:
        return []

    if is_cancelled and is_cancelled():
        return []

    # Compute Delaunay Triangulation
    tri = Delaunay(all_pts)

    # Extract unique undirected edges
    edges: Set[Tuple[int, int]] = set()
    for simplex in tri.simplices:
        for i in range(3):
            u, v = simplex[i], simplex[(i + 1) % 3]
            if u > v:
                u, v = v, u
            edges.add((u, v))

    max_span = max(w, h) * 0.25
    paths: List[StrokePath] = []

    for u, v in edges:
        p1 = all_pts[u]
        p2 = all_pts[v]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dist = math.hypot(dx, dy)

        # Cull excessive long-distance bridge spans across empty regions
        if dist > max_span:
            continue

        # If contrast exists, check if this edge spans purely empty white background
        if has_contrast:
            num_samples = 5
            ts = np.linspace(0.1, 0.9, num_samples)
            xs = np.clip(np.round(p1[0] + ts * dx).astype(int), 0, w - 1)
            ys = np.clip(np.round(p1[1] + ts * dy).astype(int), 0, h - 1)

            sample_dark = darkness[ys, xs]
            sample_grad = grad_mag[ys, xs]

            mid_idx = num_samples // 2
            if (sample_dark[mid_idx] < 0.05 and sample_grad[mid_idx] < 0.05) and (
                np.mean(sample_dark) < 0.07 and np.mean(sample_grad) < 0.07
            ):
                continue

            if np.max(sample_dark) < 0.06 and np.max(sample_grad) < 0.06:
                continue

        pt1 = (float(p1[0]), float(p1[1]))
        pt2 = (float(p2[0]), float(p2[1]))
        svg_d = f"M {pt1[0]:.2f},{pt1[1]:.2f} L {pt2[0]:.2f},{pt2[1]:.2f}"
        paths.append(StrokePath(points=[pt1, pt2], svg_d=svg_d))

    # If edge culling was too aggressive, fallback to original edges
    if len(paths) < 10:
        paths.clear()
        for u, v in edges:
            p1 = all_pts[u]
            p2 = all_pts[v]
            pt1 = (float(p1[0]), float(p1[1]))
            pt2 = (float(p2[0]), float(p2[1]))
            svg_d = f"M {pt1[0]:.2f},{pt1[1]:.2f} L {pt2[0]:.2f},{pt2[1]:.2f}"
            paths.append(StrokePath(points=[pt1, pt2], svg_d=svg_d))

    return paths
