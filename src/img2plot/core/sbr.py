"""
Stroke-Based Rendering (SBR) module for img2plot.
Generates parametric curved brush strokes (cubic Bézier paths) that follow
local edge orientation and gradient fields, creating woodcut, engraving,
or painterly hatching illustrations.
"""

from __future__ import annotations
import math
import random
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage

if TYPE_CHECKING:
    from .engine import StrokePath

from .bezier import fit_cubic_spline, segments_to_svg_path

Point2D = Tuple[float, float]


def generate_sbr_art(
    gray_image: np.ndarray,
    num_strokes: int = 1500,
    stroke_length: float = 16.0,
    curvature: float = 0.65,
    step_size: float = 2.0,
    align_mode: str = "tangent",
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate stroke-based rendering (SBR) Bézier strokes from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_strokes: Target count of strokes.
        stroke_length: Base stroke length in pixels.
        curvature: How strongly strokes bend along the direction field (0.0 to 1.0).
        step_size: Step distance per integration step.
        align_mode: "tangent" (contour-following engraving) or "cross" (cross-hatching).
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing parametric brush strokes.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_strokes < 1:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)

    # 1. Compute smooth gradient direction field
    smooth_img = scipy.ndimage.gaussian_filter(gray_image, sigma=1.5)
    gy, gx = np.gradient(smooth_img)
    mag = np.hypot(gx, gy)
    max_mag = float(mag.max())
    if max_mag > 0:
        norm_mag = mag / max_mag
    else:
        norm_mag = np.zeros_like(mag)

    # Tangent vector: (-gy, gx) or gradient: (gx, gy)
    if align_mode == "cross":
        vx = gx
        vy = gy
    else:  # "tangent"
        vx = -gy
        vy = gx

    v_len = np.hypot(vx, vy)
    non_zero = v_len > 1e-6
    vx[non_zero] /= v_len[non_zero]
    vy[non_zero] /= v_len[non_zero]

    # Fill flat regions with gentle diagonal default flow
    diag_inv = 1.0 / math.sqrt(2.0)
    vx[~non_zero] = diag_inv
    vy[~non_zero] = diag_inv

    # 2. Probability map for stroke seeding
    prob_map = (np.power(darkness, 1.3) * 0.7 + np.power(norm_mag, 1.1) * 0.3).flatten()
    prob_sum = float(np.sum(prob_map))
    if prob_sum <= 1e-5:
        prob_map = np.ones_like(prob_map)
        prob_sum = float(np.sum(prob_map))

    prob_dist = prob_map / prob_sum
    n_seeds = min(num_strokes, int(np.count_nonzero(prob_dist > 0)))
    if n_seeds < 1:
        return []

    rng = np.random.RandomState(42)
    seed_indices = rng.choice(len(prob_dist), size=n_seeds, replace=False, p=prob_dist)

    paths: List[StrokePath] = []
    base_steps = max(2, int(round((stroke_length * 0.5) / max(0.5, step_size))))

    for count, idx in enumerate(seed_indices):
        if is_cancelled and count % 100 == 0 and is_cancelled():
            return []

        sy = float(idx // w)
        sx = float(idx % w)

        ix = int(np.clip(round(sx), 0, w - 1))
        iy = int(np.clip(round(sy), 0, h - 1))
        local_dark = float(darkness[iy, ix])

        # Darker areas get longer strokes; lighter areas get shorter strokes
        n_steps = max(1, int(round(base_steps * (0.4 + 0.9 * local_dark))))

        # Integrate forward and backward from seed point
        stroke_pts: List[Point2D] = [(sx, sy)]

        # Forward
        cx, cy = sx, sy
        for _ in range(n_steps):
            bx = int(np.clip(round(cx), 0, w - 1))
            by = int(np.clip(round(cy), 0, h - 1))
            dx = vx[by, bx]
            dy = vy[by, bx]
            # Blend with initial tangent by curvature factor
            cx += dx * step_size * curvature + dx * step_size * (1.0 - curvature)
            cy += dy * step_size * curvature + dy * step_size * (1.0 - curvature)
            if cx < 0 or cx >= w or cy < 0 or cy >= h:
                break
            stroke_pts.append((cx, cy))

        # Backward
        cx, cy = sx, sy
        bwd_pts: List[Point2D] = []
        for _ in range(n_steps):
            bx = int(np.clip(round(cx), 0, w - 1))
            by = int(np.clip(round(cy), 0, h - 1))
            dx = vx[by, bx]
            dy = vy[by, bx]
            cx -= dx * step_size * curvature + dx * step_size * (1.0 - curvature)
            cy -= dy * step_size * curvature + dy * step_size * (1.0 - curvature)
            if cx < 0 or cx >= w or cy < 0 or cy >= h:
                break
            bwd_pts.append((cx, cy))

        full_pts = list(reversed(bwd_pts)) + stroke_pts
        if len(full_pts) < 2:
            continue

        # Fit cubic Bezier segments
        segments = fit_cubic_spline(full_pts, tension=0.35, sample_step=2)
        svg_d = segments_to_svg_path(segments) if segments else ""

        paths.append(StrokePath(points=full_pts, svg_d=svg_d, is_artistic=True))

    return paths
