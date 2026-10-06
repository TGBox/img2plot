"""
Pixel Sorting filter module for img2plot.
Segments rows or columns based on luminance thresholds and sorts pixels
within those intervals, producing characteristic linear glitch-art streaks.
"""

from __future__ import annotations
from typing import Optional, Callable
import numpy as np


def apply_pixel_sort(
    gray_image: np.ndarray,
    direction: str = "horizontal",
    lower_threshold: float = 0.25,
    upper_threshold: float = 0.80,
    reverse: bool = False,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Apply interval-based pixel sorting to a grayscale image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        direction: "horizontal" (sort along rows) or "vertical" (sort along columns).
        lower_threshold: Min luminance to consider a pixel part of a sortable segment.
        upper_threshold: Max luminance to consider a pixel part of a sortable segment.
        reverse: If True, sort intervals in descending order instead of ascending.
        is_cancelled: Optional cancellation callback.

    Returns:
        Sorted 2D float array with same shape and type.
    """
    img = gray_image.copy()
    if direction == "vertical":
        img = img.T

    h, w = img.shape

    for row_idx in range(h):
        if is_cancelled and row_idx % 16 == 0 and is_cancelled():
            return gray_image.copy()

        row = img[row_idx]
        mask = (row >= lower_threshold) & (row <= upper_threshold)

        # Find contiguous segments of True in mask
        diff = np.diff(np.pad(mask.astype(np.int8), (1, 1), mode="constant"))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        for s, e in zip(starts, ends):
            if e - s > 1:
                segment = row[s:e]
                if reverse:
                    row[s:e] = np.sort(segment)[::-1]
                else:
                    row[s:e] = np.sort(segment)

    if direction == "vertical":
        img = img.T

    return img
