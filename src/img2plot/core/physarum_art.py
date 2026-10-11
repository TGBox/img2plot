"""
Physarum (Slime Mold transport network) simulation module for img2plot.
Simulates autonomous agents that navigate trail maps and image darkness attractors,
leaving behind organic biological branching networks and veins.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
import scipy.ndimage
import skimage.transform
import skimage.measure
import skimage.morphology
import skimage.filters

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def _trace_skeleton_paths(skel: np.ndarray) -> List[List[Tuple[float, float]]]:
    """
    Trace an 8-connected single-pixel skeleton mask into continuous polylines.
    Starts walks from leaf endpoints and junctions to extract clean branch curves.
    """
    h, w = skel.shape
    visited = np.zeros_like(skel, dtype=bool)
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    # Compute degree (number of 8-neighbors)
    coords = np.argwhere(skel)
    deg = np.zeros((h, w), dtype=int)
    for r, c in coords:
        cnt = 0
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and skel[nr, nc]:
                cnt += 1
        deg[r, c] = cnt

    # Prioritize starting from endpoints (deg == 1), then branch points (deg >= 3), then loops
    starts = [tuple(p) for p in coords if deg[p[0], p[1]] == 1]
    starts += [tuple(p) for p in coords if deg[p[0], p[1]] >= 3]
    starts += [tuple(p) for p in coords]

    paths: List[List[Tuple[float, float]]] = []

    for sr, sc in starts:
        if visited[sr, sc] or not skel[sr, sc]:
            continue

        path: List[Tuple[float, float]] = [(float(sc), float(sr))]
        visited[sr, sc] = True
        curr_r, curr_c = sr, sc

        while True:
            next_pt = None
            for dr, dc in neighbors:
                nr, nc = curr_r + dr, curr_c + dc
                if 0 <= nr < h and 0 <= nc < w and skel[nr, nc] and not visited[nr, nc]:
                    next_pt = (nr, nc)
                    break

            if next_pt is None:
                break

            visited[next_pt[0], next_pt[1]] = True
            curr_r, curr_c = next_pt
            path.append((float(curr_c), float(curr_r)))

        if len(path) >= 3:
            paths.append(path)

    return paths


def generate_physarum_art(
    gray_image: np.ndarray,
    num_agents: int = 1500,
    iterations: int = 40,
    sim_resolution: int = 160,
    decay_factor: float = 0.90,
    sensor_angle_deg: float = 30.0,
    sensor_dist: float = 3.5,
    contour_level: float = 0.35,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate Physarum polycephalum slime mold vein networks from an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_agents: Number of particle agents.
        iterations: Number of simulation steps.
        sim_resolution: Max dimension for the downsampled simulation grid.
        decay_factor: Trail evaporation factor per step (0.80 to 0.98).
        sensor_angle_deg: Angle between center sensor and left/right sensors.
        sensor_dist: Distance in pixels from agent to sensor positions.
        contour_level: Threshold sensitivity for vein extraction.
        is_cancelled: Optional cancellation callback.

    Returns:
        List of StrokePath objects representing organic vein structures.
    """
    from .engine import StrokePath

    orig_h, orig_w = gray_image.shape
    if orig_h < 4 or orig_w < 4 or num_agents < 10:
        return []

    # Downsample for responsive simulation
    scale = min(1.0, float(sim_resolution) / max(orig_h, orig_w))
    sim_h = max(24, int(round(orig_h * scale)))
    sim_w = max(24, int(round(orig_w * scale)))

    scaled_gray = skimage.transform.resize(
        gray_image, (sim_h, sim_w), mode="reflect", anti_aliasing=True
    ).astype(np.float32)

    darkness = np.clip(1.0 - scaled_gray, 0.0, 1.0)

    # Detect edge magnitude and orientation for biological guided chemotaxis
    gx = scipy.ndimage.sobel(scaled_gray, axis=1)
    gy = scipy.ndimage.sobel(scaled_gray, axis=0)
    edge_mag = np.hypot(gx, gy)
    edge_max = float(edge_mag.max())
    edge_norm = (edge_mag / (edge_max + 1e-6)).astype(np.float32)

    # Image features serve as nutrient food sources
    food = np.clip(0.65 * np.power(darkness, 1.3) + 0.35 * edge_norm, 0.0, 1.0)
    # Extinction / zero nutrients in pure highlights so background remains clean
    food[darkness < 0.08] = 0.0

    # Initialize agents seeded strictly within content areas
    rng = np.random.RandomState(42)
    prob = food.flatten()
    prob_sum = float(np.sum(prob))
    if prob_sum <= 1e-5:
        prob = np.ones_like(prob)
        prob_sum = float(np.sum(prob))
    prob /= prob_sum

    n_act = min(num_agents, sim_w * sim_h * 2)
    seed_indices = rng.choice(len(prob), size=n_act, replace=True, p=prob)
    pos_x = (seed_indices % sim_w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_act)
    pos_y = (seed_indices // sim_w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_act)

    # Initial orientations aligned along image gradient tangents with minor jitter
    tangent_angle = np.arctan2(gx, -gy).astype(np.float32)
    sy = np.clip(np.round(pos_y).astype(int), 0, sim_h - 1)
    sx = np.clip(np.round(pos_x).astype(int), 0, sim_w - 1)
    angles = tangent_angle[sy, sx] + rng.uniform(-0.4, 0.4, size=n_act).astype(np.float32)

    sensor_rad = math.radians(sensor_angle_deg)
    turn_angle = sensor_rad * 0.75
    trail_map = np.zeros((sim_h, sim_w), dtype=np.float32)

    # Simulation loop
    for step in range(iterations):
        if is_cancelled and step % 6 == 0 and is_cancelled():
            return []

        # Sensory stage: combined chemoattractant of existing trails and image nutrients
        env_map = trail_map * 0.60 + food * 0.40

        # Sensor sample coordinates
        c_x = np.clip(np.round(pos_x + sensor_dist * np.cos(angles)).astype(int), 0, sim_w - 1)
        c_y = np.clip(np.round(pos_y + sensor_dist * np.sin(angles)).astype(int), 0, sim_h - 1)

        l_x = np.clip(np.round(pos_x + sensor_dist * np.cos(angles - sensor_rad)).astype(int), 0, sim_w - 1)
        l_y = np.clip(np.round(pos_y + sensor_dist * np.sin(angles - sensor_rad)).astype(int), 0, sim_h - 1)

        r_x = np.clip(np.round(pos_x + sensor_dist * np.cos(angles + sensor_rad)).astype(int), 0, sim_w - 1)
        r_y = np.clip(np.round(pos_y + sensor_dist * np.sin(angles + sensor_rad)).astype(int), 0, sim_h - 1)

        val_c = env_map[c_y, c_x]
        val_l = env_map[l_y, l_x]
        val_r = env_map[r_y, r_x]

        # Steering decision
        turn = np.zeros(n_act, dtype=np.float32)
        steer_left = (val_l > val_c) & (val_l > val_r)
        steer_right = (val_r > val_c) & (val_r > val_l)
        steer_rand = (val_l == val_r) & (val_l > val_c)

        turn[steer_left] = -turn_angle
        turn[steer_right] = turn_angle
        if np.any(steer_rand):
            turn[steer_rand] = rng.choice([-turn_angle, turn_angle], size=int(np.sum(steer_rand)))

        angles += turn

        # Motor stage: step forward
        pos_x += np.cos(angles) * 1.2
        pos_y += np.sin(angles) * 1.2

        # Boundary clamping
        pos_x = np.clip(pos_x, 0.0, float(sim_w - 1))
        pos_y = np.clip(pos_y, 0.0, float(sim_h - 1))

        # Deposit stage: trail deposition is weighted by local darkness
        ix = np.clip(np.round(pos_x).astype(int), 0, sim_w - 1)
        iy = np.clip(np.round(pos_y).astype(int), 0, sim_h - 1)
        deposit = np.clip(darkness[iy, ix] * 1.5, 0.0, 1.0)
        np.add.at(trail_map, (iy, ix), deposit)

        # Diffuse & evaporate trail
        trail_map = scipy.ndimage.gaussian_filter(trail_map, sigma=0.7) * decay_factor

    if is_cancelled and is_cancelled():
        return []

    # Combine normalized trails with image guidance
    veins = trail_map * (darkness > 0.08)
    vmax = float(veins.max())
    if vmax > 0:
        veins /= vmax

    # Extract vein centerlines using multi-scale ridge filtering (Meijering neurite / vessel filter)
    try:
        ridges = skimage.filters.meijering(veins, sigmas=[1.0, 1.5, 2.0], black_ridges=False)
    except Exception:
        # Fallback to white tophat if filter encounters unexpected state
        ridges = scipy.ndimage.white_tophat(veins, size=5)
        rmax = float(ridges.max())
        if rmax > 0:
            ridges /= rmax

    # Multi-tier network extraction
    thresh_primary = max(0.12, contour_level * 0.50)
    thresh_shadows = max(0.08, contour_level * 0.30)
    mask_primary = (ridges > thresh_primary) & (darkness > 0.12)
    mask_shadows = (ridges > thresh_shadows) & (darkness > 0.38)
    combined_mask = mask_primary | mask_shadows

    skel = skimage.morphology.skeletonize(combined_mask)
    raw_paths = _trace_skeleton_paths(skel)

    paths: List[StrokePath] = []
    scale_x = float(orig_w) / float(sim_w)
    scale_y = float(orig_h) / float(sim_h)

    for p in raw_paths:
        if len(p) < 3:
            continue
        # Check minimum path length
        pts: List[Point2D] = [
            (
                float(np.clip(pt[0] * scale_x, 0.0, float(orig_w - 1))),
                float(np.clip(pt[1] * scale_y, 0.0, float(orig_h - 1))),
            )
            for pt in p
        ]
        # Calculate length
        total_len = sum(
            math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            for i in range(len(pts) - 1)
        )
        if total_len >= 8.0:
            paths.append(StrokePath(points=pts, is_artistic=True))

    # Also extract major transport boundary contours in deep shadow clusters to enrich dense hubs
    if np.any(darkness > 0.45):
        shadow_vein_level = max(0.20, contour_level * 0.8)
        shadow_contours = skimage.measure.find_contours(veins * (darkness > 0.35), level=shadow_vein_level)
        for c in shadow_contours:
            if len(c) < 5:
                continue
            c_pts: List[Point2D] = [
                (
                    float(np.clip(pt[1] * scale_x, 0.0, float(orig_w - 1))),
                    float(np.clip(pt[0] * scale_y, 0.0, float(orig_h - 1))),
                )
                for pt in c
            ]
            c_len = sum(
                math.hypot(c_pts[i + 1][0] - c_pts[i][0], c_pts[i + 1][1] - c_pts[i][1])
                for i in range(len(c_pts) - 1)
            )
            if c_len >= 12.0:
                paths.append(StrokePath(points=c_pts, is_artistic=True))

    return paths

