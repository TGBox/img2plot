"""
Differential Growth art module for img2plot.
Simulates organic node expansion, edge splitting, and spatial collision repulsion,
yielding brain-coral, meandering river, and folded tissue line patterns.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage
import skimage.measure
from scipy.spatial import cKDTree

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_diffgrowth_art(
    gray_image: np.ndarray,
    iterations: int = 50,
    max_nodes: int = 1400,
    collision_radius: float = 6.0,
    split_dist: float = 5.0,
    repulsion_force: float = 0.45,
    spring_force: float = 0.35,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate differential growth meandering curves modulated by image darkness.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        iterations: Number of growth and relaxation steps.
        max_nodes: Cap on total node count for responsiveness.
        collision_radius: Neighbor repulsion distance.
        split_dist: Edge length above which a new node is inserted.
        repulsion_force: Strength of collision push.
        spring_force: Strength of neighbor curve smoothing.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing differential growth contours.
    """
    from .engine import StrokePath
    from .bezier import fit_cubic_spline, segments_to_svg_path

    orig_h, orig_w = gray_image.shape
    if orig_h < 4 or orig_w < 4 or iterations < 2:
        return []

    # Downsample slightly if image is exceptionally large to keep simulation snappy
    max_dim = 400
    scale = min(1.0, float(max_dim) / max(orig_h, orig_w))
    sim_h = max(24, int(round(orig_h * scale)))
    sim_w = max(24, int(round(orig_w * scale)))

    if scale < 1.0:
        scaled_gray = scipy.ndimage.zoom(
            gray_image, (sim_h / orig_h, sim_w / orig_w), order=1
        ).astype(np.float32)
    else:
        scaled_gray = gray_image.astype(np.float32)

    darkness = np.clip(1.0 - scaled_gray, 0.0, 1.0)
    smooth_dark = scipy.ndimage.gaussian_filter(darkness, sigma=1.8)

    # 1. Multi-level feature seeding across the subject
    seed_curves: List[Tuple[List[Point2D], bool]] = []  # (points, is_closed)
    sample_stride = max(5, int(round(split_dist * 1.5)))

    # Sample contour isolines at multiple tonal depths
    contour_levels = [0.18, 0.35, 0.52, 0.70]
    for lvl in contour_levels:
        if is_cancelled and is_cancelled():
            return []
        raw_contours = skimage.measure.find_contours(smooth_dark, level=lvl)
        for c in raw_contours:
            if len(c) < 14:
                continue
            is_closed = math.hypot(c[0][1] - c[-1][1], c[0][0] - c[-1][0]) < (sample_stride * 1.5)
            pts: List[Point2D] = [
                (float(p[1]), float(p[0])) for p in c[::sample_stride]
            ]
            if len(pts) >= 5:
                seed_curves.append((pts, is_closed))

    # Fallback if no contours found (e.g. uniform or faint image): seed organic loops
    if not seed_curves:
        cx, cy = (sim_w - 1) / 2.0, (sim_h - 1) / 2.0
        init_radius = min(sim_w, sim_h) * 0.16
        fallback_pts = [
            (cx + init_radius * math.cos(th), cy + init_radius * math.sin(th))
            for th in np.linspace(0.0, math.tau, 18, endpoint=False)
        ]
        seed_curves.append((fallback_pts, True))

    # Precompute gradient tangent field for directional flow guidance
    gx = scipy.ndimage.sobel(smooth_dark, axis=1)
    gy = scipy.ndimage.sobel(smooth_dark, axis=0)

    curves: List[List[Point2D]] = [list(pts) for pts, _ in seed_curves]
    curves_closed: List[bool] = [is_closed for _, is_closed in seed_curves]

    # Simulation loop
    for step in range(iterations):
        if is_cancelled and step % 5 == 0 and is_cancelled():
            return []

        # 1. Edge split (growth driven by local darkness)
        total_nodes = sum(len(c) for c in curves)
        if total_nodes < max_nodes:
            new_curves: List[List[Point2D]] = []
            for c_idx, c in enumerate(curves):
                n = len(c)
                is_closed = curves_closed[c_idx]
                nc: List[Point2D] = []
                edges_count = n if is_closed else (n - 1)

                for i in range(edges_count):
                    p0 = c[i]
                    p1 = c[(i + 1) % n]
                    nc.append(p0)

                    dx = p1[0] - p0[0]
                    dy = p1[1] - p0[1]
                    edge_len = math.hypot(dx, dy)

                    mx = int(np.clip(round((p0[0] + p1[0]) * 0.5), 0, sim_w - 1))
                    my = int(np.clip(round((p0[1] + p1[1]) * 0.5), 0, sim_h - 1))
                    d_val = float(darkness[my, mx])

                    # In dark areas: lower split threshold -> dense convolutions
                    # In light areas: higher split threshold -> slow/no growth
                    local_thresh = split_dist * (1.35 - 0.75 * d_val)

                    if edge_len > local_thresh and d_val > 0.10 and total_nodes < max_nodes:
                        mid_pt = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
                        nc.append(mid_pt)
                        total_nodes += 1

                if not is_closed:
                    nc.append(c[-1])

                new_curves.append(nc)
            curves = new_curves

        # 2. Collision repulsion across all nodes via cKDTree
        flat_pts: List[Point2D] = []
        curve_meta: List[Tuple[int, int, int]] = []  # (curve_idx, start_idx, length)
        for c_idx, c in enumerate(curves):
            start = len(flat_pts)
            flat_pts.extend(c)
            curve_meta.append((c_idx, start, len(c)))

        n_total = len(flat_pts)
        if n_total < 3:
            break

        pts_arr = np.array(flat_pts, dtype=np.float32)
        tree = cKDTree(pts_arr)
        pairs = tree.query_pairs(r=collision_radius)

        node_to_c = np.zeros(n_total, dtype=int)
        node_to_idx = np.zeros(n_total, dtype=int)
        for c_idx, start, length in curve_meta:
            node_to_c[start : start + length] = c_idx
            node_to_idx[start : start + length] = np.arange(length)

        displacements = np.zeros_like(pts_arr)
        for i, j in pairs:
            c_i = node_to_c[i]
            c_j = node_to_c[j]
            idx_i = node_to_idx[i]
            idx_j = node_to_idx[j]
            if c_i == c_j:
                length = curve_meta[c_i][2]
                is_closed = curves_closed[c_i]
                if abs(idx_i - idx_j) <= 1 or (is_closed and abs(idx_i - idx_j) == (length - 1)):
                    continue

            d = pts_arr[j] - pts_arr[i]
            dist = float(np.hypot(d[0], d[1]))
            if dist < 1e-4:
                displacements[i] += np.random.uniform(-0.3, 0.3, size=2)
                displacements[j] -= np.random.uniform(-0.3, 0.3, size=2)
            else:
                push = (collision_radius - dist) * repulsion_force * (d / dist)
                displacements[i] -= push
                displacements[j] += push

        # 3. Spring smoothing and morphogenetic tangent flow per curve
        updated_curves: List[List[Point2D]] = []
        for c_idx, start, length in curve_meta:
            if length < 3:
                updated_curves.append(curves[c_idx])
                continue

            c_pts = pts_arr[start : start + length] + displacements[start : start + length]
            smoothed = np.zeros_like(c_pts)
            is_closed = curves_closed[c_idx]

            for i in range(length):
                if is_closed:
                    p_prev = c_pts[(i - 1) % length]
                    p_next = c_pts[(i + 1) % length]
                else:
                    p_prev = c_pts[max(0, i - 1)]
                    p_next = c_pts[min(length - 1, i + 1)]

                target_mid = (p_prev + p_next) * 0.5
                spring = (target_mid - c_pts[i]) * spring_force

                # Tangent guidance
                ix = int(np.clip(round(c_pts[i, 0]), 0, sim_w - 1))
                iy = int(np.clip(round(c_pts[i, 1]), 0, sim_h - 1))
                t_gx, t_gy = gx[iy, ix], gy[iy, ix]
                t_mag = math.hypot(t_gx, t_gy)
                flow = np.zeros(2, dtype=np.float32)
                if t_mag > 0.05:
                    tx, ty = -t_gy / t_mag, t_gx / t_mag
                    cdx = p_next[0] - p_prev[0]
                    cdy = p_next[1] - p_prev[1]
                    if (tx * cdx + ty * cdy) < 0:
                        tx, ty = -tx, -ty
                    flow = np.array([tx, ty], dtype=np.float32) * (0.35 * darkness[iy, ix])

                smoothed[i] = c_pts[i] + spring + flow

            smoothed[:, 0] = np.clip(smoothed[:, 0], 2.0, float(sim_w - 3))
            smoothed[:, 1] = np.clip(smoothed[:, 1], 2.0, float(sim_h - 3))
            updated_curves.append([(float(p[0]), float(p[1])) for p in smoothed])

        curves = updated_curves

    if is_cancelled and is_cancelled():
        return []

    # Map back to original image dimensions and construct StrokePaths
    scale_x = float(orig_w) / float(sim_w)
    scale_y = float(orig_h) / float(sim_h)
    paths: List[StrokePath] = []

    for c_idx, c in enumerate(curves):
        if len(c) < 4:
            continue

        is_closed = curves_closed[c_idx]
        pts_scaled: List[Point2D] = [
            (
                float(np.clip(p[0] * scale_x, 0.0, float(orig_w - 1))),
                float(np.clip(p[1] * scale_y, 0.0, float(orig_h - 1))),
            )
            for p in c
        ]

        if is_closed:
            pts_scaled.append(pts_scaled[0])

        # Filter out tiny insignificant loops
        total_len = sum(
            math.hypot(pts_scaled[i + 1][0] - pts_scaled[i][0], pts_scaled[i + 1][1] - pts_scaled[i][1])
            for i in range(len(pts_scaled) - 1)
        )
        if total_len < 12.0:
            continue

        segs = fit_cubic_spline(pts_scaled, tension=0.35, sample_step=2)
        svg_d = segments_to_svg_path(segs) if segs else ""
        paths.append(StrokePath(points=pts_scaled, svg_d=svg_d, is_artistic=True))

    return paths

