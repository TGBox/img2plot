"""
Weighted Voronoi Stippling module for img2plot.
Implements Adrian Secord's Centroidal Voronoi Tessellation via Lloyd's Relaxation,
distributing stipple points according to image density for pointillist illustrations.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
from scipy.spatial import cKDTree

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_voronoi_stippling(
    gray_image: np.ndarray,
    num_points: int = 1500,
    lloyd_iterations: int = 6,
    min_radius: float = 0.8,
    max_radius: float = 3.0,
    size_by_darkness: bool = True,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate weighted Voronoi stipple points using Lloyd's relaxation.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_points: Target number of stipple points.
        lloyd_iterations: Number of Lloyd relaxation passes (higher = more uniform).
        min_radius: Minimum stipple dot radius in pixels.
        max_radius: Maximum stipple dot radius in pixels.
        size_by_darkness: If True, stipple radius scales with darkness.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing stipple dots.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_points < 4:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)
    # Enhance contrast of density map
    density = np.power(darkness, 1.5)
    d_sum = float(np.sum(density))
    if d_sum <= 1e-5:
        density = np.ones_like(density)
        d_sum = float(np.sum(density))

    prob = (density / d_sum).flatten()
    n_seeds = min(num_points, int(np.count_nonzero(prob > 0)))
    if n_seeds < 4:
        return []

    # 1. Initial importance sampling of seed points
    rng = np.random.RandomState(42)
    sampled_indices = rng.choice(len(prob), size=n_seeds, replace=False, p=prob)
    pts_y = (sampled_indices // w).astype(np.float32) + rng.uniform(-0.4, 0.4, size=n_seeds)
    pts_x = (sampled_indices % w).astype(np.float32) + rng.uniform(-0.4, 0.4, size=n_seeds)
    centroids = np.column_stack((pts_x, pts_y))

    # 2. Monte-Carlo weighted sample grid for Lloyd relaxation
    n_samples = min(w * h, max(n_seeds * 8, 20_000))
    sample_indices = rng.choice(len(prob), size=n_samples, replace=True, p=prob)
    sample_y = (sample_indices // w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_samples)
    sample_x = (sample_indices % w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_samples)
    samples = np.column_stack((sample_x, sample_y))

    # 3. Lloyd's Relaxation iterations
    for it in range(lloyd_iterations):
        if is_cancelled and is_cancelled():
            return []

        tree = cKDTree(centroids)
        _, nearest_idx = tree.query(samples, k=1)

        # Compute new centroid for each cell as mean of assigned samples
        new_centroids = centroids.copy()
        counts = np.bincount(nearest_idx, minlength=n_seeds)
        sum_x = np.bincount(nearest_idx, weights=samples[:, 0], minlength=n_seeds)
        sum_y = np.bincount(nearest_idx, weights=samples[:, 1], minlength=n_seeds)

        valid_mask = counts > 0
        new_centroids[valid_mask, 0] = sum_x[valid_mask] / counts[valid_mask]
        new_centroids[valid_mask, 1] = sum_y[valid_mask] / counts[valid_mask]

        # Clamp inside image bounds
        new_centroids[:, 0] = np.clip(new_centroids[:, 0], 0.0, float(w - 1))
        new_centroids[:, 1] = np.clip(new_centroids[:, 1], 0.0, float(h - 1))
        centroids = new_centroids

    # 4. Generate StrokePath for each relaxed stipple
    paths: List[StrokePath] = []
    num_poly_steps = 8

    for px, py in centroids:
        ix = int(np.clip(round(px), 0, w - 1))
        iy = int(np.clip(round(py), 0, h - 1))
        local_darkness = float(darkness[iy, ix])

        # Skip points that ended up in completely blank paper areas
        if local_darkness < 0.02:
            continue

        if size_by_darkness:
            radius = min_radius + (max_radius - min_radius) * local_darkness
        else:
            radius = (min_radius + max_radius) * 0.5

        # Build circular polygon points for plotter polyline
        poly_pts: List[Point2D] = []
        for a_idx in range(num_poly_steps + 1):
            theta = (float(a_idx) / float(num_poly_steps)) * math.tau
            poly_pts.append((px + radius * math.cos(theta), py + radius * math.sin(theta)))

        sp = StrokePath(
            points=poly_pts,
            svg_d=f"__circle__ cx={px:.2f} cy={py:.2f} r={radius:.2f} fill=1",
            is_artistic=True,
        )
        paths.append(sp)

    return paths
