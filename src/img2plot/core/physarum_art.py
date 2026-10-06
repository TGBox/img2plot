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

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


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
        contour_level: Isoline extraction threshold for network veins.
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

    # Darkness acts as an organic attractant
    attractor = np.power(np.clip(1.0 - scaled_gray, 0.0, 1.0), 1.4)
    trail_map = np.zeros((sim_h, sim_w), dtype=np.float32)

    # Initialize agents seeded in darker regions and noise
    rng = np.random.RandomState(42)
    prob = attractor.flatten()
    prob_sum = float(np.sum(prob))
    if prob_sum <= 1e-5:
        prob = np.ones_like(prob)
        prob_sum = float(np.sum(prob))
    prob /= prob_sum

    n_act = min(num_agents, sim_w * sim_h)
    seed_indices = rng.choice(len(prob), size=n_act, replace=True, p=prob)
    pos_x = (seed_indices % sim_w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_act)
    pos_y = (seed_indices // sim_w).astype(np.float32) + rng.uniform(-0.5, 0.5, size=n_act)
    angles = rng.uniform(0.0, math.tau, size=n_act).astype(np.float32)

    sensor_rad = math.radians(sensor_angle_deg)
    turn_angle = sensor_rad * 0.75

    # Simulation loop
    for step in range(iterations):
        if is_cancelled and step % 8 == 0 and is_cancelled():
            return []

        # Sensory stage: compute combined map of trails and image attraction
        env_map = trail_map * 0.6 + attractor * 0.4

        # Sensor positions
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
        turn[steer_rand] = rng.choice([-turn_angle, turn_angle], size=int(np.sum(steer_rand)))

        angles += turn

        # Motor stage: step forward
        pos_x += np.cos(angles) * 1.2
        pos_y += np.sin(angles) * 1.2

        # Boundary bounce / wrap
        pos_x = np.clip(pos_x, 0.0, float(sim_w - 1))
        pos_y = np.clip(pos_y, 0.0, float(sim_h - 1))

        # Deposit stage
        ix = np.clip(np.round(pos_x).astype(int), 0, sim_w - 1)
        iy = np.clip(np.round(pos_y).astype(int), 0, sim_h - 1)
        np.add.at(trail_map, (iy, ix), 1.0)

        # Diffuse & evaporate trail
        trail_map = scipy.ndimage.gaussian_filter(trail_map, sigma=0.8) * decay_factor

    if is_cancelled and is_cancelled():
        return []

    # Normalize trail map
    t_max = float(trail_map.max())
    if t_max > 0:
        norm_trails = trail_map / t_max
    else:
        norm_trails = trail_map

    # Extract vein contours
    raw_contours = skimage.measure.find_contours(norm_trails, level=contour_level)

    paths: List[StrokePath] = []
    scale_x = float(orig_w) / float(sim_w)
    scale_y = float(orig_h) / float(sim_h)

    for contour in raw_contours:
        if len(contour) < 3:
            continue

        pts: List[Point2D] = [
            (
                float(np.clip(pt[1] * scale_x, 0.0, float(orig_w - 1))),
                float(np.clip(pt[0] * scale_y, 0.0, float(orig_h - 1))),
            )
            for pt in contour
        ]
        paths.append(StrokePath(points=pts, is_artistic=True))

    return paths
