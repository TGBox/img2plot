"""
Reaction-Diffusion (Turing Pattern) art generation module for img2plot.
Simulates an anisotropic Gray-Scott chemical reaction-diffusion model where
diffusion tensors align along image gradient tangents (contour flow), feed/kill
rates are modulated by local image darkness, and clean isolines are extracted
for pen plotters.
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
    Generate Turing pattern reaction-diffusion contour paths faithfully representing an image.

    Uses anisotropic diffusion oriented along image gradient tangents so that
    Turing stripes and labyrinth ridges follow the curves, contours, and tonal values
    of the input subject instead of random isotropic noise.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        sim_resolution: Max dimension of the downsampled simulation grid.
        iterations: Number of integration steps.
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
    sim_h = max(24, int(round(orig_h * scale)))
    sim_w = max(24, int(round(orig_w * scale)))

    scaled_gray = skimage.transform.resize(
        gray_image, (sim_h, sim_w), mode="reflect", anti_aliasing=True
    ).astype(np.float32)

    darkness = np.clip(1.0 - scaled_gray, 0.0, 1.0)

    # 1. Compute image gradient and anisotropic diffusion tensor
    # Sobel kernels for gradient estimation
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32) / 8.0
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32) / 8.0

    gx = scipy.ndimage.convolve(scaled_gray, sobel_x, mode="reflect")
    gy = scipy.ndimage.convolve(scaled_gray, sobel_y, mode="reflect")
    grad_mag = np.sqrt(gx * gx + gy * gy)
    max_gm = float(grad_mag.max())
    norm_gm = grad_mag / max(1e-5, max_gm)

    # Tangent vector: perpendicular to gradient (-gy, gx)
    # Along edges, diffusion is strong along the tangent (parallel)
    # and suppressed across the gradient (perpendicular)
    safe_mag = np.maximum(grad_mag, 1e-6)
    nx = gx / safe_mag  # normal x
    ny = gy / safe_mag  # normal y
    tx = -ny            # tangent x
    ty = nx             # tangent y

    # Anisotropic weights: in high gradient areas, lambda_perp drops to 0.15
    # In flat areas, lambda_perp blends to 0.70 (isotropic diffusion)
    lambda_par = 1.0
    lambda_perp = np.clip(0.70 - 0.55 * norm_gm, 0.15, 0.70)

    # 2D diffusion tensor components
    D_xx = lambda_par * (tx * tx) + lambda_perp * (nx * nx)
    D_yy = lambda_par * (ty * ty) + lambda_perp * (ny * ny)
    D_xy = (lambda_par - lambda_perp) * (tx * ty)

    # 2. Modulate Gray-Scott Feed and Kill parameters by darkness
    # Highlights (darkness near 0): higher kill, lower feed -> V dies out (clean paper)
    # Shadows (darkness > 0.3): parameters in stable labyrinth/spots regime
    f_grid = np.clip(feed_rate + (darkness - 0.4) * 0.020, 0.018, 0.058)
    k_grid = np.clip(kill_rate - (darkness - 0.4) * 0.012, 0.048, 0.068)
    # Force complete extinction in pure white/bright areas (< 0.12 darkness)
    light_mask = darkness < 0.12
    k_grid[light_mask] = 0.072
    f_grid[light_mask] = 0.014

    # 3. Initial concentrations
    u = np.ones((sim_h, sim_w), dtype=np.float32)
    v = np.zeros((sim_h, sim_w), dtype=np.float32)

    # Seed chemical V strictly where there is image content (darkness > 0.18 or edges)
    rng = np.random.RandomState(42)
    seed_mask = (darkness > 0.18) | (norm_gm > 0.25)
    v[seed_mask] = 0.40 + 0.30 * rng.rand(int(np.sum(seed_mask)))
    u[seed_mask] = 0.60

    # Diffusion constants
    du_base = 0.18
    dv_base = 0.09
    dt = 1.0

    # Simulation loop using anisotropic finite-difference operator
    for step in range(iterations):
        if is_cancelled and step % 20 == 0 and is_cancelled():
            return []

        # Central finite differences for 2nd derivatives
        # d2/dx2
        d2u_dx2 = np.pad(u[:, 2:] - 2.0 * u[:, 1:-1] + u[:, :-2], ((0, 0), (1, 1)), mode="edge")
        d2v_dx2 = np.pad(v[:, 2:] - 2.0 * v[:, 1:-1] + v[:, :-2], ((0, 0), (1, 1)), mode="edge")

        # d2/dy2
        d2u_dy2 = np.pad(u[2:, :] - 2.0 * u[1:-1, :] + u[:-2, :], ((1, 1), (0, 0)), mode="edge")
        d2v_dy2 = np.pad(v[2:, :] - 2.0 * v[1:-1, :] + v[:-2, :], ((1, 1), (0, 0)), mode="edge")

        # d2/dxdy
        # 4-point cross derivative
        u_yp1 = np.roll(u, -1, axis=0)
        u_ym1 = np.roll(u, 1, axis=0)
        d2u_dxdy = (np.roll(u_yp1, -1, axis=1) - np.roll(u_yp1, 1, axis=1) -
                    np.roll(u_ym1, -1, axis=1) + np.roll(u_ym1, 1, axis=1)) * 0.25

        v_yp1 = np.roll(v, -1, axis=0)
        v_ym1 = np.roll(v, 1, axis=0)
        d2v_dxdy = (np.roll(v_yp1, -1, axis=1) - np.roll(v_yp1, 1, axis=1) -
                    np.roll(v_ym1, -1, axis=1) + np.roll(v_ym1, 1, axis=1)) * 0.25

        # Tensor Laplacians
        lap_u = D_xx * d2u_dx2 + D_yy * d2u_dy2 + 2.0 * D_xy * d2u_dxdy
        lap_v = D_xx * d2v_dx2 + D_yy * d2v_dy2 + 2.0 * D_xy * d2v_dxdy

        # Gray-Scott reaction terms
        uvv = u * v * v
        du_dt = du_base * lap_u - uvv + f_grid * (1.0 - u)
        dv_dt = dv_base * lap_v + uvv - (f_grid + k_grid) * v

        u = np.clip(u + dt * du_dt, 0.0, 1.0)
        v = np.clip(v + dt * dv_dt, 0.0, 1.0)

    if is_cancelled and is_cancelled():
        return []

    # 4. Extract isolines with tone-based density
    # In darker areas, V is stronger and patterns are denser
    # Extract primary contour at contour_level
    primary_contours = skimage.measure.find_contours(v, level=contour_level)

    # In deep shadows (darkness > 0.5), extract secondary sub-contours for higher ink density
    shadow_mask = darkness > 0.50
    secondary_level = min(0.60, contour_level + 0.15)
    v_shadows = np.where(shadow_mask, v, 0.0)
    secondary_contours = skimage.measure.find_contours(v_shadows, level=secondary_level)

    all_raw_contours = primary_contours + secondary_contours

    paths: List[StrokePath] = []
    scale_x = float(orig_w) / float(sim_w)
    scale_y = float(orig_h) / float(sim_h)
    content_mask = scipy.ndimage.binary_dilation(darkness > 0.08, iterations=3)

    for contour in all_raw_contours:
        if len(contour) < 4:
            continue

        sample_rows = np.clip(np.round(contour[:, 0]).astype(int), 0, sim_h - 1)
        sample_cols = np.clip(np.round(contour[:, 1]).astype(int), 0, sim_w - 1)
        if not np.any(content_mask[sample_rows, sample_cols]):
            continue

        pts: List[Point2D] = [
            (
                float(np.clip(pt[1] * scale_x, 0.0, float(orig_w - 1))),
                float(np.clip(pt[0] * scale_y, 0.0, float(orig_h - 1))),
            )
            for pt in contour
        ]
        paths.append(StrokePath(points=pts, is_artistic=True))

    # Graceful fallback: if strict filter rejected all contours but raw contours exist, retain longest
    if not paths and all_raw_contours:
        longest = max(all_raw_contours, key=len)
        if len(longest) >= 4:
            pts = [
                (
                    float(np.clip(pt[1] * scale_x, 0.0, float(orig_w - 1))),
                    float(np.clip(pt[0] * scale_y, 0.0, float(orig_h - 1))),
                )
                for pt in longest
            ]
            paths.append(StrokePath(points=pts, is_artistic=True))

    return paths

