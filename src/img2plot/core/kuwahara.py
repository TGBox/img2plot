"""
Kuwahara filter module for painterly image preprocessing in img2plot.
Performs non-linear edge-preserving smoothing that creates an oil-painting /
cel-shaded artistic effect without external AI models or dependencies.
Uses integral images (summed-area tables) for fast O(1) performance.
"""

from __future__ import annotations
import numpy as np


def apply_kuwahara(image: np.ndarray, radius: int = 3) -> np.ndarray:
    """
    Apply Kuwahara filter to a 2D float array in [0.0, 1.0].

    Divides the (2r+1) x (2r+1) window around each pixel into 4 overlapping quadrants,
    computes mean and variance for each quadrant, and sets the pixel to the mean of
    the quadrant with minimal variance.

    Uses integral images (summed-area tables) for constant O(1) execution time per pixel.

    Args:
        image: 2D numpy float32/float64 array in range [0.0, 1.0].
        radius: Radius of quadrants (window size = 2*radius + 1). Min 1, recommended 2..6.

    Returns:
        Filtered 2D float array with same shape as input.
    """
    if radius < 1:
        return image.copy()

    img = np.asarray(image, dtype=np.float32)
    h, w = img.shape
    r = radius

    pad_img = np.pad(img, r, mode="reflect")
    pad_sq = pad_img * pad_img

    sat = np.zeros((h + 2 * r + 1, w + 2 * r + 1), dtype=np.float32)
    sat_sq = np.zeros_like(sat)
    sat[1:, 1:] = pad_img.cumsum(0).cumsum(1)
    sat_sq[1:, 1:] = pad_sq.cumsum(0).cumsum(1)

    area = float((r + 1) * (r + 1))

    # Top-Left: y in [y, y + r + 1], x in [x, x + r + 1]
    s0 = sat[r + 1 : h + r + 1, r + 1 : w + r + 1] - sat[0:h, r + 1 : w + r + 1] - sat[r + 1 : h + r + 1, 0:w] + sat[0:h, 0:w]
    sq0 = sat_sq[r + 1 : h + r + 1, r + 1 : w + r + 1] - sat_sq[0:h, r + 1 : w + r + 1] - sat_sq[r + 1 : h + r + 1, 0:w] + sat_sq[0:h, 0:w]
    m0 = s0 / area
    v0 = np.maximum(0.0, sq0 / area - m0 * m0)

    # Top-Right: y in [y, y + r + 1], x in [x + r, x + 2r + 1]
    s1 = sat[r + 1 : h + r + 1, 2 * r + 1 : w + 2 * r + 1] - sat[0:h, 2 * r + 1 : w + 2 * r + 1] - sat[r + 1 : h + r + 1, r : w + r] + sat[0:h, r : w + r]
    sq1 = sat_sq[r + 1 : h + r + 1, 2 * r + 1 : w + 2 * r + 1] - sat_sq[0:h, 2 * r + 1 : w + 2 * r + 1] - sat_sq[r + 1 : h + r + 1, r : w + r] + sat_sq[0:h, r : w + r]
    m1 = s1 / area
    v1 = np.maximum(0.0, sq1 / area - m1 * m1)

    # Bottom-Left: y in [y + r, y + 2r + 1], x in [x, x + r + 1]
    s2 = sat[2 * r + 1 : h + 2 * r + 1, r + 1 : w + r + 1] - sat[r : h + r, r + 1 : w + r + 1] - sat[2 * r + 1 : h + 2 * r + 1, 0:w] + sat[r : h + r, 0:w]
    sq2 = sat_sq[2 * r + 1 : h + 2 * r + 1, r + 1 : w + r + 1] - sat_sq[r : h + r, r + 1 : w + r + 1] - sat_sq[2 * r + 1 : h + 2 * r + 1, 0:w] + sat_sq[r : h + r, 0:w]
    m2 = s2 / area
    v2 = np.maximum(0.0, sq2 / area - m2 * m2)

    # Bottom-Right: y in [y + r, y + 2r + 1], x in [x + r, x + 2r + 1]
    s3 = sat[2 * r + 1 : h + 2 * r + 1, 2 * r + 1 : w + 2 * r + 1] - sat[r : h + r, 2 * r + 1 : w + 2 * r + 1] - sat[2 * r + 1 : h + 2 * r + 1, r : w + r] + sat[r : h + r, r : w + r]
    sq3 = sat_sq[2 * r + 1 : h + 2 * r + 1, 2 * r + 1 : w + 2 * r + 1] - sat_sq[r : h + r, 2 * r + 1 : w + 2 * r + 1] - sat_sq[2 * r + 1 : h + 2 * r + 1, r : w + r] + sat_sq[r : h + r, r : w + r]
    m3 = s3 / area
    v3 = np.maximum(0.0, sq3 / area - m3 * m3)

    vars_stack = np.stack([v0, v1, v2, v3], axis=0)
    means_stack = np.stack([m0, m1, m2, m3], axis=0)

    min_idx = np.argmin(vars_stack, axis=0)
    chosen_mean = np.take_along_axis(means_stack, min_idx[np.newaxis, :, :], axis=0)[0]

    return np.clip(chosen_mean, 0.0, 1.0)
