"""
Anisotropic Kuwahara filter module for img2plot.
Determines local structure tensors to detect edge orientation and curvature,
performing directional smoothing along edge contours for a flowing, painterly
oil/gouache aesthetic with crisp boundaries.
"""

from __future__ import annotations
import math
from typing import Optional, Callable
import numpy as np
import scipy.ndimage


def apply_anisotropic_kuwahara(
    image: np.ndarray,
    radius: int = 3,
    num_sectors: int = 8,
    sharpness: float = 4.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Apply Anisotropic Kuwahara filter to an image using structure tensor orientation.

    Args:
        image: 2D float array in [0.0, 1.0], shape (H, W).
        radius: Kernel smoothing radius in pixels (1 to 8).
        num_sectors: Number of directional angular sectors (e.g. 4 or 8).
        sharpness: Exponent for inverse-variance weighting (higher = sharper transitions).
        is_cancelled: Optional cancellation callback.

    Returns:
        Filtered 2D float array with same shape as input.
    """
    if radius < 1:
        return image.copy()

    img = np.asarray(image, dtype=np.float32)
    h, w = img.shape
    r = max(1, radius)

    # 1. Compute gradients
    gy, gx = np.gradient(img)

    # 2. Structure tensor components
    j_xx = gx * gx
    j_yy = gy * gy
    j_xy = gx * gy

    # Smooth structure tensor components
    sigma_tensor = max(1.0, float(r) * 0.6)
    j_xx = scipy.ndimage.gaussian_filter(j_xx, sigma=sigma_tensor)
    j_yy = scipy.ndimage.gaussian_filter(j_yy, sigma=sigma_tensor)
    j_xy = scipy.ndimage.gaussian_filter(j_xy, sigma=sigma_tensor)

    # Eigenstructure: local orientation theta (tangent to edges) and anisotropy
    diff = j_xx - j_yy
    trace = j_xx + j_yy
    disc = np.hypot(diff, 2.0 * j_xy)
    anisotropy = np.clip(disc / (trace + 1e-6), 0.0, 1.0)
    theta = 0.5 * np.arctan2(2.0 * j_xy, diff) + (math.pi / 2.0)

    # 3. Sample directional sectors
    # Pre-generate sector kernels with Gaussian falloff along orientation
    k = num_sectors
    angles = np.linspace(0.0, math.tau, k, endpoint=False)
    offset_dist = float(r) * 0.7

    sector_means = []
    sector_vars = []

    sq_img = img * img

    for ang in angles:
        if is_cancelled and is_cancelled():
            return image.copy()

        # Sector offset
        ox = offset_dist * math.cos(ang)
        oy = offset_dist * math.sin(ang)

        # Shifted Gaussian kernel centered at (ox, oy)
        k_size = 2 * r + 1
        ky, kx = np.mgrid[-r : r + 1, -r : r + 1]
        dist_sq = (kx - ox) ** 2 + (ky - oy) ** 2
        kernel = np.exp(-dist_sq / (2.0 * (max(0.8, float(r) * 0.5) ** 2))).astype(np.float32)
        kernel /= float(np.sum(kernel))

        m = scipy.ndimage.convolve(img, kernel, mode="reflect")
        sq_m = scipy.ndimage.convolve(sq_img, kernel, mode="reflect")
        v = np.maximum(0.0, sq_m - m * m)

        sector_means.append(m)
        sector_vars.append(v)

    # 4. Compute sector weights combining local variance and tensor alignment
    weights = []
    for idx, ang in enumerate(angles):
        v = sector_vars[idx]
        # Inverse-variance weight
        inv_v = 1.0 / (np.power(v, sharpness * 0.5) + 1e-5)

        # Tensor alignment factor: reward sectors aligned with tangent theta
        d_theta = np.cos(2.0 * (ang - theta))  # in [-1, 1]
        align_weight = np.exp(2.0 * anisotropy * d_theta)

        w_sector = inv_v * align_weight
        weights.append(w_sector)

    # 5. Composite output
    w_sum = np.sum(weights, axis=0) + 1e-6
    weighted_mean = np.zeros_like(img)
    for idx in range(k):
        weighted_mean += weights[idx] * sector_means[idx]

    output = np.clip(weighted_mean / w_sum, 0.0, 1.0).astype(np.float32)
    return output
