"""
Reaction-Diffusion (Turing Pattern) art generation module for img2plot.
Simulates a Gray-Scott chemical reaction-diffusion model where local reaction
rates (feed and kill) are modulated by image darkness, and extracts organic
labyrinthine/fingerprint contour lines for pen plotters.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage
import skimage.transform
import skimage.measure

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_reaction_diffusion(
    gray_image: np.ndarray,
    sim_resolution: int = 180,
    iterations: int = 240,
    feed_rate: float = 0.037,
    kill_rate: float = 0.060,
    contour_level: float = 0.28,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate Turing pattern reaction-diffusion contour paths from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        sim_resolution: Max dimension of the downsampled simulation grid.
        iterations: Number of Euler integration steps.
        feed_rate: Base Gray-Scott feed rate (F).
        kill_rate: Base Gray-Scott kill rate (k).
        contour_level: Isoline threshold on chemical V for contour extraction.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing organic Turing isolines.
    """
    from .engine import StrokePath

    orig_h, orig_w = gray_image.shape
    if orig_h < 4 or orig_w < 4 or iterations < 10:
        return []

    # Downsample image to simulation grid for real-time responsiveness
    scale = min(1.0, float(sim_resolution) / max(orig_h, orig_w))
    sim_h = max(20, int(round(orig_h * scale)))
    sim_w = max(20, int(round(orig_w * scale)))

    scaled_gray = skimage.transform.resize(
        gray_image, (sim_h, sim_w), mode="reflect", anti_aliasing=True
    ).astype(np.float32)

    darkness = np.clip(1.0 - scaled_gray, 0.0, 1.0)

    # Modulate feed and kill parameters by local image darkness
    # F in [feed_rate - 0.015, feed_rate + 0.015], k in [kill_rate - 0.005, kill_rate + 0.005]
    f_grid = np.clip(feed_rate + (darkness - 0.5) * 0.024, 0.012, 0.065)
    k_grid = np.clip(kill_rate + (darkness - 0.5) * 0.008, 0.045, 0.070)

    # Initial concentrations
    u = np.ones((sim_h, sim_w), dtype=np.float32)
    v = np.zeros((sim_h, sim_w), dtype=np.float32)

    # Seed chemical V in high-darkness regions and random noise
    rng = np.random.RandomState(42)
    seed_mask = (darkness > 0.25) | (rng.rand(sim_h, sim_w) < 0.08)
    v[seed_mask] = 0.5 + 0.2 * rng.rand(int(np.sum(seed_mask)))
    u[seed_mask] = 0.5

    # Diffusion rates
    du = 0.20
    dv = 0.10
    dt = 1.0

    # 3x3 Laplacian kernel with diagonal weighting
    laplace_kernel = np.array(
        [[0.05, 0.20, 0.05], [0.20, -1.00, 0.20], [0.05, 0.20, 0.05]], dtype=np.float32
    )

    # Simulation loop
    for step in range(iterations):
        if is_cancelled and step % 20 == 0 and is_cancelled():
            return []

        lap_u = scipy.ndimage.convolve(u, laplace_kernel, mode="reflect")
        lap_v = scipy.ndimage.convolve(v, laplace_kernel, mode="reflect")

        uvv = u * v * v
        du_dt = du * lap_u - uvv + f_grid * (1.0 - u)
        dv_dt = dv * lap_v + uvv - (f_grid + k_grid) * v

        u = np.clip(u + dt * du_dt, 0.0, 1.0)
        v = np.clip(v + dt * dv_dt, 0.0, 1.0)

    if is_cancelled and is_cancelled():
        return []

    # Extract isolines from chemical V
    raw_contours = skimage.measure.find_contours(v, level=contour_level)

    paths: List[StrokePath] = []
    scale_x = float(orig_w) / float(sim_w)
    scale_y = float(orig_h) / float(sim_h)

    for contour in raw_contours:
        if len(contour) < 3:
            continue

        # contour coordinates are (row, col) = (y, x)
        pts: List[Point2D] = [
            (
                float(np.clip(pt[1] * scale_x, 0.0, float(orig_w - 1))),
                float(np.clip(pt[0] * scale_y, 0.0, float(orig_h - 1))),
            )
            for pt in contour
        ]
        paths.append(StrokePath(points=pts, is_artistic=True))

    return paths
