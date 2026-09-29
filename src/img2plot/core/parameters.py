"""
Configuration parameters for the img2plot vectorizer and line generator.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from typing import Any, Dict


@dataclass
class PlotParameters:
    """Dataclass holding all customizable parameters for image vectorization."""

    # File paths
    input_path: str = ""
    output_path: str = ""

    # Preview and processing optimization
    preview_max_dim: int = 800  # Downsample max dimension for fast live preview (0 = full resolution)

    # Preprocessing
    use_clahe: bool = True
    clahe_kernel_size: int = 32
    clahe_clip_limit: float = 0.01
    use_gaussian_blur: bool = True
    gaussian_kernel_size: float = 1.0

    # Line tracing & edge detection
    termination_ratio: float = 0.2857  # ~ 1.0 / 3.5
    line_continue_thresh: float = 0.01
    min_line_length: int = 21
    max_curve_angle_deg: float = 20.0
    lpf_atk: float = 0.05
    max_iterations: int = 20000

    # Line style & curve fitting
    line_mode: str = "straight"  # "straight" or "bezier"
    bezier_smoothness: float = 0.35  # Tangent smoothing strength for organic Bezier curves
    curve_sample_step: int = 2  # Step size for picking points along tracked edges

    # Hatching (Schraffur für dunkle Flächen)
    use_hatching: bool = False
    hatch_mode: str = "bezier"  # "bezier" (form-following curved lines) or "straight"
    hatch_curve_strength: float = 0.65  # How strongly hatching curves follow underlying image contours (0.0 to 1.0)
    hatch_wobble: float = 0.0  # Subtle organic hand-drawn wobble amplitude (0.0 to 2.0 px)
    hatching_threshold: float = 0.35  # Grayscale brightness threshold (0.0=black, 1.0=white)
    hatching_spacing: int = 10  # Pixel spacing between hatching lines
    hatching_angle_deg: float = 45.0  # Angle of hatching lines
    cross_hatch: bool = False  # Add a second orthogonal pass for deep shadows
    hatching_min_length: int = 6  # Minimum length of hatching strokes

    # Formen-Modus (Shapes)
    use_shapes: bool = False
    shape_type: str = "dots"           # dots|circles|rects|triangles|lines|stars|diamonds|hexagons|spirals|hearts|ascii
    shape_placement: str = "grid"      # "grid" | "random"
    shape_min_size: float = 2.0        # Minimale Formgröße in Pixel (für helle Bereiche)
    shape_max_size: float = 20.0       # Maximale Formgröße in Pixel (für dunkle Bereiche)
    shape_density: float = 0.6         # Dichte 0.0–2.0 (skaliert Rastergröße/Anzahl)
    shape_rotation_mode: str = "random"  # "none" | "random" | "gradient" | "mixed"
    shape_gradient_align: float = 0.5   # Blend: 0=rein zufällig, 1=rein gradientenausgerichtet
    shape_size_by_brightness: bool = True    # Helligkeit → Größe (dunkel = groß)
    shape_density_by_brightness: bool = True  # Helligkeit → Dichte (dunkel = mehr Formen)
    shape_ascii_charset: str = "@#S%?*+;:,. "  # Zeichensatz für ASCII-Modus (dunkel → hell)

    # Export & physical page setup
    stroke_color: str = "#1a1a1a"
    stroke_width_mm: float = 0.35
    page_format: str = "Original"  # "Original", "A4", "A3", "Letter", "Custom"
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    margin_mm: float = 10.0
    sort_paths: bool = False  # TSP/Nearest-neighbor sort to minimize pen-up movements (disabled by default for fast preview)
    two_opt: bool = False  # Additional 2-opt refinement pass after sort_paths (slower, further reduces pen-up travel)

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlotParameters:
        """Create PlotParameters instance from a dictionary, ignoring unknown keys."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_json(self, indent: int = 2) -> str:
        """Serialize parameters to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> PlotParameters:
        """Deserialize parameters from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)