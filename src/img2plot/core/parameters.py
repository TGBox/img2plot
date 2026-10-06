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
    use_kuwahara: bool = False
    kuwahara_radius: int = 3  # Radius for painterly oil-painting smoothing (1 to 10)
    kuwahara_mode: str = "standard"  # "standard" (4 quadrants) or "anisotropic" (structure tensor)
    kuwahara_anisotropy: float = 1.0  # Directional anisotropy strength for anisotropic Kuwahara

    # Preprocessing Filters: Quadtree & Pixel Sorting
    use_quadtree: bool = False
    quadtree_threshold: float = 0.06  # Variance threshold for splitting (0.01 to 0.25)
    quadtree_min_size: int = 8  # Minimum block size in pixels (2 to 64)
    quadtree_max_depth: int = 7  # Maximum recursion depth (2 to 10)
    quadtree_render_boxes: bool = False  # Render quadtree block borders as vector strokes

    use_pixel_sort: bool = False
    pixel_sort_direction: str = "horizontal"  # "horizontal" or "vertical"
    pixel_sort_lower_thresh: float = 0.25  # Minimum brightness threshold (0.0 to 1.0)
    pixel_sort_upper_thresh: float = 0.80  # Maximum brightness threshold (0.0 to 1.0)
    pixel_sort_reverse: bool = False  # Reverse sort order (descending instead of ascending)

    # Preprocessing Filter: 2D-FFT Frequenzraum-Manipulation
    use_fft: bool = False
    fft_mode: str = "moiré"  # "moiré", "bandpass", "interference", "highpass"
    fft_frequency: float = 12.0
    fft_bandwidth: float = 6.0
    fft_strength: float = 0.75

    # Preprocessing Filter: Cyclic Cellular Automata
    use_ca: bool = False
    ca_states: int = 8
    ca_iterations: int = 20
    ca_threshold: int = 1
    ca_strength: float = 0.85

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

    # Künstlerische Stile (Artistic Modes)
    artistic_mode: str = "none"  # "none", "waveform", "spiral", "tsp", "delaunay", "flowfield", "voronoi", "reaction_diffusion", "stippling", "sbr"
    artistic_overlay_contours: bool = False  # If True, overlays detected edge contours over the artistic style

    # Waveform / Joy Division Parameters
    waveform_lines: int = 60
    waveform_amplitude: float = 20.0
    waveform_resolution: int = 250
    waveform_occlusion: bool = True

    # Spiral Art Parameters
    spiral_loops: int = 75
    spiral_resolution: int = 400
    spiral_amplitude: float = 6.0
    spiral_frequency: float = 30.0

    # TSP Single-Line Art Parameters
    tsp_points: int = 2400
    tsp_2opt_passes: int = 15

    # Delaunay / Low-Poly Art Parameters
    delaunay_points: int = 1400
    delaunay_edge_weight: float = 0.65

    # Flow Field / Streamlines Parameters
    flowfield_lines: int = 1000
    flowfield_step_len: float = 2.5
    flowfield_max_steps: int = 50
    flowfield_direction: str = "tangent"  # "tangent" (contour flow) or "gradient"

    # Voronoi Cellular Mosaic Parameters
    voronoi_points: int = 1200
    voronoi_edge_weight: float = 0.60

    # Reaction-Diffusion (Turing Pattern) Parameters
    rd_sim_resolution: int = 180
    rd_iterations: int = 240
    rd_feed_rate: float = 0.037
    rd_kill_rate: float = 0.060
    rd_contour_level: float = 0.28

    # Voronoi Stippling (Lloyd's Relaxation) Parameters
    stippling_points: int = 1500
    stippling_lloyd_passes: int = 6
    stippling_min_radius: float = 0.8
    stippling_max_radius: float = 3.0
    stippling_size_by_darkness: bool = True

    # Stroke-Based Rendering (SBR) Parameters
    sbr_strokes: int = 1500
    sbr_length: float = 16.0
    sbr_curvature: float = 0.65
    sbr_align_mode: str = "tangent"  # "tangent" or "cross"

    # Isocontour / Marching Squares Topographic Parameters
    iso_levels: int = 16
    iso_min_level: float = 0.08
    iso_max_level: float = 0.92
    iso_smoothing: float = 1.5

    # Physarum Slime Mold Parameters
    physarum_agents: int = 1500
    physarum_iterations: int = 40
    physarum_sim_res: int = 160
    physarum_decay: float = 0.90
    physarum_sensor_angle: float = 30.0

    # String Art Parameters
    string_pins: int = 240
    string_max_lines: int = 1500
    string_weight: float = 0.18
    string_shape: str = "circle"  # "circle" or "rectangle"

    # Differential Growth Parameters
    diffgrowth_iterations: int = 50
    diffgrowth_max_nodes: int = 1400
    diffgrowth_collision_r: float = 6.0
    diffgrowth_split_dist: float = 5.0

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