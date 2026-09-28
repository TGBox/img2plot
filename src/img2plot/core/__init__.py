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
    "PlotEngine",
    "StrokePath",
    "PlotStats",
    "EngineResult",
    "export_svg",
    "export_png",
]
