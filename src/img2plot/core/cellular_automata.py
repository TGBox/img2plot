"""
Cyclic Cellular Automata (CCA) simulation module for img2plot.
Transforms image pixel levels into self-organizing cellular states that evolve
over discrete cycles to generate spiral waves, crystalline patterns, and Belousov-Zhabotinsky textures.
"""

from __future__ import annotations
from typing import Optional, Callable
import numpy as np


def apply_cyclic_ca(
    gray_image: np.ndarray,
    num_states: int = 8,
    iterations: int = 20,
    threshold: int = 1,
    strength: float = 0.85,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Apply Cyclic Cellular Automata transformation to an image.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        num_states: Number of discrete cyclic state levels (e.g. 6 to 16).
        iterations: Number of evolution clock cycles.
        threshold: Required count of advancing neighbors in Moore neighborhood.
        strength: Blend factor with the original image (0.0 to 1.0).
        is_cancelled: Optional cancellation callback.

    Returns:
        Transformed 2D float array in [0.0, 1.0].
    """
    h, w = gray_image.shape
    if h < 4 or w < 4 or iterations < 1:
        return gray_image.copy()

    # Initial state grid quantizing grayscale values
    states = np.clip(np.floor(gray_image * float(num_states)).astype(np.int32), 0, num_states - 1)

    # 8-neighbor offsets
    neighbor_offsets = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    for step in range(iterations):
        if is_cancelled and step % 4 == 0 and is_cancelled():
            return gray_image.copy()

        target_state = (states + 1) % num_states
        neighbor_match_count = np.zeros_like(states)

        for dy, dx in neighbor_offsets:
            rolled = np.roll(np.roll(states, dy, axis=0), dx, axis=1)
            neighbor_match_count += (rolled == target_state)

        # Advance cells that meet threshold
        advance_mask = neighbor_match_count >= threshold
        states[advance_mask] = target_state[advance_mask]

    # Map states back to float [0.0, 1.0]
    ca_image = states.astype(np.float32) / float(max(1, num_states - 1))

    # Blend with original image
    return np.clip((1.0 - strength) * gray_image + strength * ca_image, 0.0, 1.0)
