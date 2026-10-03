"""
Predefined and user-customizable presets for img2plot.
Provides persistence for custom user presets in ~/.img2plot/presets.
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
        sort_paths=False,
        two_opt=False,
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
        sort_paths=False,
        two_opt=False,
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
        sort_paths=False,
        two_opt=False,
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
        sort_paths=False,
        two_opt=False,
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
        line_mode="bezier",
        bezier_smoothness=0.35,
        use_hatching=True,
        hatch_mode="bezier",
        hatch_curve_strength=0.75,
        hatching_threshold=0.36,
        hatching_spacing=9,
        hatching_angle_deg=45.0,
        cross_hatch=True,
        hatch_wobble=0.15,
        sort_paths=False,
        two_opt=False,
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
        sort_paths=False,
        two_opt=False,
    ),
    "Wellenform (Joy Division)": PlotParameters(
        artistic_mode="waveform",
        waveform_lines=65,
        waveform_amplitude=22.0,
        waveform_resolution=280,
        waveform_occlusion=True,
        use_clahe=True,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.2,
        sort_paths=False,
    ),
    "Archimedische Spirale (1-Linie)": PlotParameters(
        artistic_mode="spiral",
        spiral_loops=80,
        spiral_resolution=420,
        spiral_amplitude=7.0,
        spiral_frequency=30.0,
        use_clahe=True,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        sort_paths=False,
    ),
    "TSP Single-Line (Handlungsreisender)": PlotParameters(
        artistic_mode="tsp",
        tsp_points=2500,
        tsp_2opt_passes=18,
        use_clahe=True,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        sort_paths=False,
    ),
    "Low-Poly (Delaunay-Mosaik)": PlotParameters(
        artistic_mode="delaunay",
        delaunay_points=1500,
        delaunay_edge_weight=0.65,
        use_clahe=True,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        sort_paths=False,
    ),
    "Flussfeld (Van-Gogh-Linien)": PlotParameters(
        artistic_mode="flowfield",
        flowfield_lines=1100,
        flowfield_step_len=2.5,
        flowfield_max_steps=55,
        flowfield_direction="tangent",
        use_clahe=True,
        use_gaussian_blur=True,
        gaussian_kernel_size=1.0,
        sort_paths=False,
    ),
    "Malerisches Ölgemälde (Kuwahara)": PlotParameters(
        use_kuwahara=True,
        kuwahara_radius=4,
        termination_ratio=0.22,
        line_continue_thresh=0.012,
        min_line_length=16,
        max_curve_angle_deg=28.0,
        line_mode="bezier",
        bezier_smoothness=0.45,
        use_clahe=True,
        use_gaussian_blur=False,
        sort_paths=False,
    ),
}


def get_user_presets_dir() -> str:
    """Return the directory path where user presets are stored."""
    base_dir = os.path.join(os.path.expanduser("~"), ".img2plot", "presets")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def list_user_presets() -> Dict[str, PlotParameters]:
    """Scan and load all custom presets saved by the user."""
    presets_dir = get_user_presets_dir()
    user_presets: Dict[str, PlotParameters] = {}

    if not os.path.isdir(presets_dir):
        return user_presets

    for fname in sorted(os.listdir(presets_dir)):
        if fname.endswith(".json"):
            name = os.path.splitext(fname)[0]
            fpath = os.path.join(presets_dir, fname)
            try:
                user_presets[name] = load_preset_file(fpath)
            except Exception:
                pass

    return user_presets


def get_all_presets() -> Dict[str, PlotParameters]:
    """Return a dictionary of all available presets (default + user saved)."""
    merged = dict(DEFAULT_PRESETS)
    merged.update(list_user_presets())
    return merged


def save_user_preset(name: str, params: PlotParameters) -> str:
    """Save parameters as a user preset with the specified name."""
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    if not safe_name:
        safe_name = "Benutzerdefiniert"

    presets_dir = get_user_presets_dir()
    fpath = os.path.join(presets_dir, f"{safe_name}.json")
    save_preset_file(params, fpath)
    return safe_name


def delete_user_preset(name: str) -> bool:
    """Delete a user preset if it exists."""
    presets_dir = get_user_presets_dir()
    fpath = os.path.join(presets_dir, f"{name}.json")
    if os.path.isfile(fpath):
        try:
            os.remove(fpath)
            return True
        except Exception:
            return False
    return False


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