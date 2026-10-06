"""
String Art (Radon / Bresenham pin optimization) module for img2plot.
Generates a single continuous threaded string woven between border pins,
iteratively covering the darkest pixel chords in the image.
"""

from __future__ import annotations
import math
from typing import List, Optional, Callable, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .engine import StrokePath

Point2D = Tuple[float, float]


def generate_string_art(
    gray_image: np.ndarray,
    num_pins: int = 240,
    max_strings: int = 1500,
    string_weight: float = 0.18,
    pin_shape: str = "circle",
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[StrokePath]:
    """
    Generate a single continuous thread weaving between border pins.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_pins: Number of physical pins placed around perimeter (e.g. 150 to 360).
        max_strings: Total number of threaded chord passes (e.g. 500 to 3000).
        string_weight: Darkness subtracted from the image per drawn string (0.05 to 0.40).
        pin_shape: "circle" or "rectangle".
        is_cancelled: Optional cancellation callback.

    Returns:
        List containing a single continuous StrokePath representing the woven thread.
    """
    from .engine import StrokePath

    h, w = gray_image.shape
    if h < 4 or w < 4 or num_pins < 12 or max_strings < 1:
        return []

    # 1. Compute pin coordinates around border
    pins: List[Point2D] = []
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    rx = cx * 0.98
    ry = cy * 0.98

    if pin_shape == "circle":
        r = min(rx, ry)
        for i in range(num_pins):
            theta = (float(i) / float(num_pins)) * math.tau
            px = cx + r * math.cos(theta)
            py = cy + r * math.sin(theta)
            pins.append((px, py))
    else:  # rectangle border
        perimeter = 2.0 * (w + h)
        step = perimeter / float(num_pins)
        for i in range(num_pins):
            d = i * step
            if d < w:
                pins.append((d, 0.0))
            elif d < w + h:
                pins.append((w - 1.0, d - w))
            elif d < 2 * w + h:
                pins.append((w - 1.0 - (d - (w + h)), h - 1.0))
            else:
                pins.append((0.0, h - 1.0 - (d - (2 * w + h))))

    # 2. Residual darkness image to be covered by thread
    residual = np.clip(1.0 - gray_image, 0.0, 1.0)

    # 3. Weaving loop
    current_pin = 0
    string_coords: List[Point2D] = [pins[current_pin]]
    min_pin_distance = max(4, num_pins // 20)  # avoid trivial neighboring chords

    # Pre-subsample candidates to keep step time fast
    candidate_step = 1 if num_pins <= 180 else 2

    for str_idx in range(max_strings):
        if is_cancelled and str_idx % 50 == 0 and is_cancelled():
            return []

        best_pin = -1
        best_darkness = -1.0
        best_samples = None

        p0 = pins[current_pin]

        # Search best target pin
        for target_pin in range(0, num_pins, candidate_step):
            pin_diff = abs(target_pin - current_pin)
            if pin_diff < min_pin_distance or (num_pins - pin_diff) < min_pin_distance:
                continue

            p1 = pins[target_pin]
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dist = math.hypot(dx, dy)
            if dist < 2.0:
                continue

            n_samples = max(4, int(dist))
            ts = np.linspace(0.0, 1.0, n_samples)
            xs = np.clip(np.round(p0[0] + ts * dx).astype(int), 0, w - 1)
            ys = np.clip(np.round(p0[1] + ts * dy).astype(int), 0, h - 1)

            # Score is sum of darkness along this line
            line_score = float(np.sum(residual[ys, xs])) / float(n_samples)
            if line_score > best_darkness:
                best_darkness = line_score
                best_pin = target_pin
                best_samples = (ys, xs)

        if best_pin < 0 or best_darkness <= 0.001:
            break

        # Subtract drawn thread density from residual image
        ys, xs = best_samples
        residual[ys, xs] = np.clip(residual[ys, xs] - string_weight, 0.0, 1.0)

        current_pin = best_pin
        string_coords.append(pins[current_pin])

    if len(string_coords) < 2:
        return []

    return [StrokePath(points=string_coords, is_artistic=True)]
