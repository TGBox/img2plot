"""
Isocontour / Marching Squares topographic relief module for img2plot.
Interprets image luminance as a digital elevation model (DEM) and extracts
contour isolines at discrete elevation thresholds, imitating topographic maps
and laser-cut / CNC relief layers.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage
import skimage.measure

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_isocontours(
    gray_image: np.ndarray,
    num_levels: int = 16,
    min_level: float = 0.08,
    max_level: float = 0.92,
    smoothing_sigma: float = 1.5,
    min_length: float = 8.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate topographic elevation isolines from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_levels: Number of discrete height/contour slices.
        min_level: Lowest elevation contour threshold.
        max_level: Highest elevation contour threshold.
        smoothing_sigma: Gaussian pre-smoothing to avoid jittery pixel steps.
        min_length: Minimum path length in pixels to filter out tiny dust spots.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing topographic contour lines.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_levels < 1:
        return []

    # Invert so darkness = peak elevation or vice versa (darkness as topography)
    elevation = np.clip(1.0 - gray_image, 0.0, 1.0)
    if smoothing_sigma > 0:
        elevation = scipy.ndimage.gaussian_filter(elevation, sigma=smoothing_sigma)

    levels = np.linspace(min_level, max_level, max(1, num_levels))
    paths: List[StrokePath] = []

    for idx, lvl in enumerate(levels):
        if is_cancelled and is_cancelled():
            return []

        raw_contours = skimage.measure.find_contours(elevation, level=float(lvl))
        for contour in raw_contours:
            if len(contour) < 3:
                continue

            # contour points are (row, col) = (y, x)
            pts: List[Point2D] = [
                (float(np.clip(p[1], 0.0, float(w - 1))), float(np.clip(p[0], 0.0, float(h - 1))))
                for p in contour
            ]

            # Calculate total length
            total_len = 0.0
            for i in range(len(pts) - 1):
                dx = pts[i + 1][0] - pts[i][0]
                dy = pts[i + 1][1] - pts[i][1]
                total_len += (dx * dx + dy * dy) ** 0.5

            if total_len >= min_length:
                paths.append(StrokePath(points=pts, is_artistic=True))

    return paths
