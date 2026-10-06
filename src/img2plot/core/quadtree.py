"""
Quadtree decomposition module for img2plot.
Recursively decomposes an image into quadrants based on local variance,
producing a structured block-abstraction image filter and optional
vectorized bounding-box stroke paths for pen plotting.
"""

from __future__ import annotations
from typing import List, Tuple, Optional, Callable, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def apply_quadtree_decomposition(
    gray_image: np.ndarray,
    variance_threshold: float = 0.06,
    min_size: int = 8,
    max_depth: int = 8,
    render_boxes: bool = False,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, List[StrokePath]]:
    """
    Decompose an image using quadtree partitioning.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        variance_threshold: Threshold on standard deviation / variance to split a quadrant.
        min_size: Minimum block size (width/height in pixels) below which splitting stops.
        max_depth: Maximum recursion depth.
        render_boxes: If True, generates rectangular vector stroke paths for all leaf blocks.
        is_cancelled: Optional cancellation callback.

    Returns:
        Tuple of (abstracted_image, box_stroke_paths).
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 2 or w < 2:
        return gray_image.copy(), []

    result_img = np.zeros_like(gray_image)
    paths: List[StrokePath] = []

    # Stack-based quadtree traversal: (x, y, block_w, block_h, depth)
    stack = [(0, 0, w, h, 0)]

    while stack:
        if is_cancelled and is_cancelled():
            return gray_image.copy(), []

        x, y, bw, bh, depth = stack.pop()
        sub = gray_image[y : y + bh, x : x + bw]

        std_dev = float(np.std(sub))
        mean_val = float(np.mean(sub))

        can_split = (
            depth < max_depth
            and bw >= 2 * min_size
            and bh >= 2 * min_size
            and std_dev > variance_threshold
        )

        if can_split:
            half_w = bw // 2
            half_h = bh // 2
            # 4 quadrants: top-left, top-right, bottom-left, bottom-right
            stack.append((x, y, half_w, half_h, depth + 1))
            stack.append((x + half_w, y, bw - half_w, half_h, depth + 1))
            stack.append((x, y + half_h, half_w, bh - half_h, depth + 1))
            stack.append((x + half_w, y + half_h, bw - half_w, bh - half_h, depth + 1))
        else:
            # Leaf block: fill with mean value
            result_img[y : y + bh, x : x + bw] = mean_val

            if render_boxes:
                # Add rectangle contour
                x0, y0 = float(x), float(y)
                x1, y1 = float(x + bw), float(y + bh)
                rect_pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
                paths.append(StrokePath(points=rect_pts, is_artistic=True))

    return result_img, paths
