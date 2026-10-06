"""
Differential Growth art module for img2plot.
Simulates organic node expansion, edge splitting, and spatial collision repulsion,
yielding brain-coral, meandering river, and folded tissue line patterns.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np
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

    h, w = gray_image.shape
    if h < 4 or w < 4 or iterations < 2:
        return []

    darkness = np.clip(1.0 - gray_image, 0.0, 1.0)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    init_radius = min(w, h) * 0.12

    # Start with a small circular loop of 20 nodes
    num_init = 24
    nodes: List[Point2D] = []
    for i in range(num_init):
        th = (float(i) / float(num_init)) * math.tau
        nodes.append((cx + init_radius * math.cos(th), cy + init_radius * math.sin(th)))

    for step in range(iterations):
        if is_cancelled and step % 5 == 0 and is_cancelled():
            return []

        n = len(nodes)
        pts = np.array(nodes, dtype=np.float32)

        # 1. Edge split (growth)
        if n < max_nodes:
            new_nodes: List[Point2D] = []
            for i in range(n):
                p0 = nodes[i]
                p1 = nodes[(i + 1) % n]
                new_nodes.append(p0)

                dx = p1[0] - p0[0]
                dy = p1[1] - p0[1]
                edge_len = math.hypot(dx, dy)

                # Query local darkness: dark regions grow faster (lower split threshold)
                mx = int(np.clip(round((p0[0] + p1[0]) * 0.5), 0, w - 1))
                my = int(np.clip(round((p0[1] + p1[1]) * 0.5), 0, h - 1))
                local_dark = float(darkness[my, mx])

                local_split_thresh = split_dist * (1.2 - 0.6 * local_dark)

                if edge_len > local_split_thresh and len(new_nodes) < max_nodes:
                    mid_pt = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
                    new_nodes.append(mid_pt)

            nodes = new_nodes
            n = len(nodes)
            pts = np.array(nodes, dtype=np.float32)

        # 2. Collision repulsion via KDTree
        tree = cKDTree(pts)
        pairs = tree.query_pairs(r=collision_radius)
        displacements = np.zeros_like(pts)

        for i, j in pairs:
            # Skip direct connected chain neighbors
            if abs(i - j) == 1 or abs(i - j) == (n - 1):
                continue
            d = pts[j] - pts[i]
            dist = float(np.hypot(d[0], d[1]))
            if dist < 1e-4:
                # Random nudge
                displacements[i] += np.random.uniform(-0.5, 0.5, size=2)
                displacements[j] -= np.random.uniform(-0.5, 0.5, size=2)
            else:
                push = (collision_radius - dist) * repulsion_force * (d / dist)
                displacements[i] -= push
                displacements[j] += push

        # 3. Spring smoothing towards immediate neighbors
        smooth_shifts = np.zeros_like(pts)
        for i in range(n):
            p_prev = pts[(i - 1) % n]
            p_next = pts[(i + 1) % n]
            target_mid = (p_prev + p_next) * 0.5
            smooth_shifts[i] = (target_mid - pts[i]) * spring_force

        # Apply displacements and clamp
        pts += displacements + smooth_shifts
        pts[:, 0] = np.clip(pts[:, 0], 2.0, float(w - 3))
        pts[:, 1] = np.clip(pts[:, 1], 2.0, float(h - 3))

        nodes = [(float(p[0]), float(p[1])) for p in pts]

    if len(nodes) < 3:
        return []

    # Close loop
    closed_pts = nodes + [nodes[0]]
    segs = fit_cubic_spline(closed_pts, tension=0.35, sample_step=2)
    svg_d = segments_to_svg_path(segs) if segs else ""

    return [StrokePath(points=closed_pts, svg_d=svg_d, is_artistic=True)]
