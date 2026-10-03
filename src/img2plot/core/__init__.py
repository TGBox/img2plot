"""
Core engine package for img2plot.
"""

from .parameters import PlotParameters
from .presets import (
    DEFAULT_PRESETS,
    load_preset_file,
    save_preset_file,
    list_user_presets,
    get_all_presets,
    save_user_preset,
    delete_user_preset,
)
from .bezier import fit_cubic_spline, segments_to_svg_path
from .hatching import generate_hatching
from .shapes import generate_shapes
from .kuwahara import apply_kuwahara
from .waveform import generate_waveform
from .spiral import generate_spiral
from .tsp_art import generate_tsp_art
from .delaunay_art import generate_delaunay_art
from .flowfield import generate_flowfield
from .engine import PlotEngine, StrokePath, PlotStats, EngineResult
from .exporter import export_svg, export_png

__all__ = [
    "PlotParameters",
    "DEFAULT_PRESETS",
    "load_preset_file",
    "save_preset_file",
    "list_user_presets",
    "get_all_presets",
    "save_user_preset",
    "delete_user_preset",
    "fit_cubic_spline",
    "segments_to_svg_path",
    "generate_hatching",
    "generate_shapes",
    "apply_kuwahara",
    "generate_waveform",
    "generate_spiral",
    "generate_tsp_art",
    "generate_delaunay_art",
    "generate_flowfield",
    "PlotEngine",
    "StrokePath",
    "PlotStats",
    "EngineResult",
    "export_svg",
    "export_png",
]
