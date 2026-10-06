"""
Voronoi Mosaic / Cellular Tessellation art module for img2plot.
Generates geometric Voronoi cell boundary artwork by placing feature-aware vertices
along image contours and shadows, computing the Voronoi diagram, and extracting
cell boundary ridges clipped to the image frame.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, Set, TYPE_CHECKING
import numpy as np
from scipy.spatial import Voronoi

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def _clip_segment_to_rect(
    p1: Point2D, p2: Point2D, w: float, h: float
) -> Optional[Tuple[Point2D, Point2D]]:
    """Clip a 2D line segment to the rectangle [0, w] x [0, h] using Liang-Barsky."""
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1

    p = [-dx, dx, -dy, dy]
    q = [x1, w - x1, y1, h - y1]

    u1 = 0.0
    u2 = 1.0

    for pi, qi in zip(p, q):
        if pi == 0.0:
            if qi < 0.0:
                return None
        else:
            t = qi / pi
            if pi < 0.0:
                if t > u2:
                    return None
                if t > u1:
                    u1 = t
            else:
                if t < u1:
                    return None
                if t < u2:
                    u2 = t

    cx1 = x1 + u1 * dx
    cy1 = y1 + u1 * dy
    cx2 = x1 + u2 * dx
    cy2 = y1 + u2 * dy
    return (cx1, cy1), (cx2, cy2)


def generate_voronoi_art(
    gray_image: np.ndarray,
    grad_magnitude: Optional[np.ndarray] = None,
    num_points: int = 1200,
    edge_weight: float = 0.6,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate Voronoi cellular mosaic paths from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        grad_magnitude: Optional Sobel gradient magnitude array, same shape.
        num_points: Target number of seed points.
        edge_weight: Weight given to gradient edges vs darkness (0.0 to 1.0).
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing Voronoi cell boundaries.
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

    weight_map = (1.0 - edge_weight) * np.power(darkness, 1.4) + edge_weight * np.power(grad_mag, 1.2)
    w_sum = float(np.sum(weight_map))
    if w_sum <= 1e-4:
        weight_map = np.ones_like(weight_map)
        w_sum = float(np.sum(weight_map))

    has_contrast = bool(np.max(weight_map) > 0.15)
    if has_contrast:
        weight_map[weight_map < 0.05] = 0.0
        w_sum = float(np.sum(weight_map))
        if w_sum <= 1e-4:
            weight_map = np.clip(1.0 - gray_image, 0.01, 1.0)
            w_sum = float(np.sum(weight_map))

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

    # Add exterior bounding ring of points to close boundary Voronoi cells cleanly
    margin_w = float(w) * 0.4
    margin_h = float(h) * 0.4
    exterior_pts = [
        (-margin_w, -margin_h),
        (w / 2.0, -margin_h),
        (w + margin_w, -margin_h),
        (w + margin_w, h / 2.0),
        (w + margin_w, h + margin_h),
        (w / 2.0, h + margin_h),
        (-margin_w, h + margin_h),
        (-margin_w, h / 2.0),
    ]
    all_pts = np.array(vertices + exterior_pts, dtype=np.float32)

    if is_cancelled and is_cancelled():
        return []

    vor = Voronoi(all_pts)

    paths: List[StrokePath] = []
    max_span = max(w, h) * 0.3

    for p1_idx, p2_idx in vor.ridge_vertices:
        if p1_idx < 0 or p2_idx < 0:
            continue

        v1 = vor.vertices[p1_idx]
        v2 = vor.vertices[p2_idx]

        clipped = _clip_segment_to_rect((v1[0], v1[1]), (v2[0], v2[1]), float(w - 1), float(h - 1))
        if clipped is None:
            continue

        (cx1, cy1), (cx2, cy2) = clipped
        dist = math.hypot(cx2 - cx1, cy2 - cy1)
        if dist < 1.0 or dist > max_span:
            continue

        # Check background culling
        if has_contrast:
            mx = int(np.clip(round((cx1 + cx2) * 0.5), 0, w - 1))
            my = int(np.clip(round((cy1 + cy2) * 0.5), 0, h - 1))
            if darkness[my, mx] < 0.05 and grad_mag[my, mx] < 0.08:
                continue

        paths.append(StrokePath(points=[(cx1, cy1), (cx2, cy2)], is_artistic=True))

    return paths
