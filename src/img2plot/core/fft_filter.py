"""
2D-FFT frequency domain manipulation module for img2plot.
Transforms images to the Fourier frequency space to apply spectral filters,
moiré interference masks, and phase shifts before reconstructing via inverse FFT.
"""

from __future__ import annotations
import math
from typing import Optional, Callable
import numpy as np


def apply_fft_filter(
    gray_image: np.ndarray,
    mode: str = "moiré",  # "moiré", "bandpass", "interference", "highpass"
    frequency: float = 12.0,
    bandwidth: float = 6.0,
    strength: float = 0.75,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> np.ndarray:
    """
    Apply 2D Fourier transform frequency domain manipulation.

    Args:
        gray_image: 2D float array in [0.0, 1.0], shape (H, W).
        mode: Filtering mode ("moiré", "bandpass", "interference", "highpass").
        frequency: Center frequency / grating spatial frequency.
        bandwidth: Width of the spectral pass-band or ring thickness.
        strength: Blend factor between original and filtered image (0.0 to 1.0).
        is_cancelled: Optional cancellation callback.

    Returns:
        Transformed 2D float array in [0.0, 1.0].
    """
    h, w = gray_image.shape
    if h < 4 or w < 4:
        return gray_image.copy()

    # 1. 2D FFT
    f_shift = np.fft.fftshift(np.fft.fft2(gray_image))

    cy, cx = h / 2.0, w / 2.0
    y, x = np.ogrid[:h, :w]
    radius = np.hypot(x - cx, y - cy)

    # 2. Build spectral mask
    mask = np.ones((h, w), dtype=np.complex64)

    if mode == "moiré":
        # Multi-ring concentric grating in Fourier domain
        rings = np.cos((radius / max(1.0, bandwidth)) * math.tau)
        mask = 0.5 + 0.5 * rings

    elif mode == "bandpass":
        # Annular bandpass filter
        r_min = max(1.0, frequency - bandwidth * 0.5)
        r_max = frequency + bandwidth * 0.5
        pass_band = (radius >= r_min) & (radius <= r_max)
        # Smooth edges
        mask = np.exp(-((radius - frequency) ** 2) / (2.0 * max(1.0, bandwidth) ** 2))
        mask[0, 0] = 1.0  # Preserve DC component slightly

    elif mode == "interference":
        # Dual-frequency directional wave interference
        angle_rad = math.radians(45.0)
        u = (x - cx) * math.cos(angle_rad) + (y - cy) * math.sin(angle_rad)
        interf = 0.5 + 0.5 * np.cos((u / max(1.0, frequency)) * math.tau)
        mask = interf

    elif mode == "highpass":
        # Highpass filter suppressing low DC frequencies
        mask = 1.0 - np.exp(-(radius**2) / (2.0 * max(1.0, frequency) ** 2))

    if is_cancelled and is_cancelled():
        return gray_image.copy()

    # Apply mask with DC component preservation
    f_filtered = f_shift * (1.0 - strength + strength * mask)
    # Ensure DC center energy is not completely obliterated
    f_filtered[int(cy), int(cx)] = f_shift[int(cy), int(cx)]

    # 3. Inverse FFT
    f_ishift = np.fft.ifftshift(f_filtered)
    img_back = np.fft.ifft2(f_ishift)
    img_real = np.real(img_back).astype(np.float32)

    # Normalize back to [0.0, 1.0]
    min_v, max_v = float(img_real.min()), float(img_real.max())
    if max_v - min_v > 1e-6:
        result = (img_real - min_v) / (max_v - min_v)
    else:
        result = np.clip(img_real, 0.0, 1.0)

    # Blend with original according to strength
    return np.clip((1.0 - strength) * gray_image + strength * result, 0.0, 1.0)
