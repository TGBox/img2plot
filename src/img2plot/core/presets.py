"""
Predefined and user-customizable presets for img2plot.
"""

from __future__ import annotations
import os
import json
from typing import Dict
from .parameters import PlotParameters


DEFAULT_PRESETS: Dict[str, PlotParameters] = {
    "Standard": PlotParameters(
        termination_ratio=0.2857,
        line_continue_thresh=0.01,
        min_line_length=21,
        max_curve_angle_deg=20.0,
        lpf_atk=0.05,
        use_clahe=True,
        clahe_kernel_size=32,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        line_mode="straight",
        use_hatching=False,
    ),
    "Feine Details": PlotParameters(
        termination_ratio=0.18,
        line_continue_thresh=0.008,
        min_line_length=12,
        max_curve_angle_deg=25.0,
        lpf_atk=0.08,
        use_clahe=True,
        clahe_kernel_size=24,
        use_gaussian_blur=True,
        gaussian_kernel_size=0.6,
        line_mode="bezier",
        bezier_smoothness=0.25,
        use_hatching=False,
    ),
    "Künstlerische Skizze": PlotParameters(
        termination_ratio=0.24,
        line_continue_thresh=0.015,
        min_line_length=26,
        max_curve_angle_deg=35.0,
        lpf_atk=0.07,
        use_clahe=True,
        clahe_kernel_size=32,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.2,
        line_mode="bezier",
        bezier_smoothness=0.45,
        use_hatching=False,
    ),
    "Starke Konturen": PlotParameters(
        termination_ratio=0.38,
        line_continue_thresh=0.02,
        min_line_length=28,
        max_curve_angle_deg=18.0,
        lpf_atk=0.04,
        use_clahe=False,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.5,
        line_mode="straight",
        use_hatching=False,
    ),
    "Klassische Gravur (Schraffur)": PlotParameters(
        termination_ratio=0.25,
        line_continue_thresh=0.01,
        min_line_length=18,
        max_curve_angle_deg=22.0,
        lpf_atk=0.05,
        use_clahe=True,
        clahe_kernel_size=32,
        use_gaussian_blur=True,
        gaussian_kernel_size=0.8,
        line_mode="straight",
        use_hatching=True,
        hatching_threshold=0.36,
        hatching_spacing=8,
        hatching_angle_deg=45.0,
        cross_hatch=True,
    ),
    "Schnell-Entwurf": PlotParameters(
        termination_ratio=0.45,
        line_continue_thresh=0.02,
        min_line_length=32,
        max_curve_angle_deg=20.0,
        lpf_atk=0.05,
        use_clahe=True,
        clahe_kernel_size=32,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        line_mode="straight",
        use_hatching=False,
    ),
}


def load_preset_file(file_path: str) -> PlotParameters:
    """Load parameter configuration from a JSON preset file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PlotParameters.from_dict(data)


def save_preset_file(params: PlotParameters, file_path: str) -> None:
    """Save parameter configuration to a JSON preset file."""
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(params.to_dict(), f, indent=2, ensure_ascii=False)
