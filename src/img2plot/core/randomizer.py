"""
Preset randomizer and creative parameter generator for img2plot.
Generates balanced, diverse, and visually striking parameter sets across all 14 artistic modes and filters,
and provides smart German naming suggestions for discovered presets.
"""

from __future__ import annotations
import random
from typing import Optional, List
from .parameters import PlotParameters


ARTISTIC_MODES: List[str] = [
    "none",
    "waveform",
    "spiral",
    "tsp",
    "delaunay",
    "flowfield",
    "voronoi",
    "reaction_diffusion",
    "stippling",
    "sbr",
    "isocontours",
    "physarum",
    "string_art",
    "diffgrowth",
]

NON_CLASSIC_ARTISTIC_MODES: List[str] = [m for m in ARTISTIC_MODES if m != "none"]

INK_PALETTE: List[str] = [
    "#1a1a1a",  # Tiefschwarz / Deep Charcoal
    "#1e3a8a",  # Blueprint Marineblau
    "#0f766e",  # Tiefes Petrolgrün
    "#b91c1c",  # Rubinrot / Vermilion
    "#7e22ce",  # Purpurviolett
    "#c2410c",  # Terrakotta / Rostorange
    "#374151",  # Schiefergrau
    "#047857",  # Smaragdgrün
    "#4338ca",  # Königliches Indigo
    "#78350f",  # Warmes Sepiabraun
]


def generate_random_parameters(mode: Optional[str] = None) -> PlotParameters:
    """
    Generate a balanced, random, aesthetically viable PlotParameters instance.
    - If mode == "classic_only" or "none": forces artistic_mode="none" (no artistic mode, only classic contours/hatching/shapes).
    - If mode == "artistic_only": samples exclusively from artistic modes (waveform, spiral, tsp, etc.), never "none".
    - If mode is in ARTISTIC_MODES: uses that exact artistic mode.
    - Otherwise (mode is None or "all"): picks randomly across all modes.
    """
    if mode in ("none", "classic_only"):
        chosen_mode = "none"
    elif mode == "artistic_only":
        chosen_mode = random.choice(NON_CLASSIC_ARTISTIC_MODES)
    elif mode and mode in ARTISTIC_MODES:
        chosen_mode = mode
    else:
        chosen_mode = random.choice(ARTISTIC_MODES)

    p = PlotParameters()
    p.artistic_mode = chosen_mode
    p.preview_max_dim = 600  # Fast batch preview resolution

    # 1. Preprocessing filters
    p.use_clahe = random.random() < 0.70
    p.clahe_kernel_size = random.choice([16, 24, 32, 40, 48])
    p.clahe_clip_limit = round(random.uniform(0.005, 0.025), 3)

    p.use_gaussian_blur = random.random() < 0.65
    p.gaussian_kernel_size = round(random.uniform(0.4, 2.0), 1)

    # Optional artistic pre-filters (low probability so they don't overpower everything)
    p.use_kuwahara = random.random() < 0.20
    p.kuwahara_radius = random.randint(2, 5)
    p.kuwahara_mode = random.choice(["standard", "anisotropic"])
    p.kuwahara_anisotropy = round(random.uniform(0.6, 1.8), 1)

    p.use_quadtree = random.random() < 0.15
    p.quadtree_threshold = round(random.uniform(0.03, 0.12), 2)
    p.quadtree_min_size = random.choice([4, 8, 12, 16])
    p.quadtree_max_depth = random.randint(5, 8)
    p.quadtree_render_boxes = random.random() < 0.35

    p.use_pixel_sort = random.random() < 0.15
    p.pixel_sort_direction = random.choice(["horizontal", "vertical"])
    p.pixel_sort_lower_thresh = round(random.uniform(0.15, 0.40), 2)
    p.pixel_sort_upper_thresh = round(random.uniform(0.65, 0.90), 2)
    p.pixel_sort_reverse = random.choice([True, False])

    p.use_fft = random.random() < 0.12
    p.fft_mode = random.choice(["moiré", "bandpass", "interference", "highpass"])
    p.fft_frequency = round(random.uniform(6.0, 22.0), 1)
    p.fft_bandwidth = round(random.uniform(3.0, 8.0), 1)
    p.fft_strength = round(random.uniform(0.4, 0.85), 2)

    p.use_ca = random.random() < 0.12
    p.ca_states = random.choice([6, 8, 10, 12])
    p.ca_iterations = random.randint(12, 28)
    p.ca_threshold = random.choice([1, 2])
    p.ca_strength = round(random.uniform(0.60, 0.90), 2)

    # 2. Contour & Line parameters
    p.line_mode = random.choice(["straight", "bezier"])
    p.bezier_smoothness = round(random.uniform(0.20, 0.55), 2)
    p.curve_sample_step = random.randint(1, 3)
    p.termination_ratio = round(random.uniform(0.16, 0.42), 2)
    p.line_continue_thresh = round(random.uniform(0.006, 0.024), 3)
    p.min_line_length = random.randint(12, 36)
    p.max_curve_angle_deg = round(random.uniform(15.0, 40.0), 0)
    p.lpf_atk = round(random.uniform(0.03, 0.10), 2)

    # 3. Hatching (active primarily for classic mode or subtle overlays)
    if chosen_mode == "none":
        p.use_hatching = random.random() < 0.45
        p.hatch_mode = random.choice(["straight", "bezier"])
        p.hatch_curve_strength = round(random.uniform(0.4, 0.9), 2)
        p.hatch_wobble = random.choice([0.0, 0.0, 0.15, 0.35, 0.6])
        p.hatching_threshold = round(random.uniform(0.20, 0.45), 2)
        p.hatching_spacing = random.randint(7, 18)
        p.hatching_angle_deg = random.choice([0.0, 30.0, 45.0, 60.0, 90.0, 135.0])
        p.cross_hatch = random.random() < 0.35

        p.use_shapes = random.random() < 0.30
        if p.use_shapes:
            shape_types = [
                "dots", "circles", "rects", "triangles", "lines",
                "stars", "diamonds", "hexagons", "spirals", "hearts", "ascii"
            ]
            p.shape_type = random.choice(shape_types)
            p.shape_placement = random.choice(["grid", "random"])
            p.shape_min_size = round(random.uniform(1.5, 4.0), 1)
            p.shape_max_size = round(random.uniform(10.0, 26.0), 1)
            p.shape_density = round(random.uniform(0.4, 1.2), 2)
            p.shape_rotation_mode = random.choice(["none", "random", "gradient", "mixed"])
    else:
        p.use_hatching = False
        p.use_shapes = False
        p.artistic_overlay_contours = random.random() < 0.25

    # 4. Mode-specific artistic parameters
    if chosen_mode == "waveform":
        p.waveform_lines = random.choice([45, 55, 65, 75, 90])
        p.waveform_amplitude = round(random.uniform(14.0, 32.0), 1)
        p.waveform_resolution = random.choice([200, 250, 300])
        p.waveform_occlusion = random.random() < 0.85

    elif chosen_mode == "spiral":
        p.spiral_loops = random.choice([55, 70, 85, 100])
        p.spiral_resolution = random.choice([320, 400, 480])
        p.spiral_amplitude = round(random.uniform(4.0, 9.0), 1)
        p.spiral_frequency = round(random.uniform(22.0, 42.0), 1)

    elif chosen_mode == "tsp":
        p.tsp_points = random.choice([1400, 1800, 2200, 2600])
        p.tsp_2opt_passes = random.choice([8, 12, 16])

    elif chosen_mode == "delaunay":
        p.delaunay_points = random.choice([900, 1200, 1600, 2000])
        p.delaunay_edge_weight = round(random.uniform(0.45, 0.85), 2)

    elif chosen_mode == "flowfield":
        p.flowfield_lines = random.choice([700, 950, 1200, 1500])
        p.flowfield_step_len = round(random.uniform(1.8, 3.2), 1)
        p.flowfield_max_steps = random.randint(35, 65)
        p.flowfield_direction = random.choice(["tangent", "gradient"])

    elif chosen_mode == "voronoi":
        p.voronoi_points = random.choice([800, 1100, 1400, 1800])
        p.voronoi_edge_weight = round(random.uniform(0.45, 0.80), 2)

    elif chosen_mode == "reaction_diffusion":
        p.rd_sim_resolution = random.choice([140, 160, 180])
        p.rd_iterations = random.choice([180, 220, 260])
        feed_rates = [0.034, 0.037, 0.040, 0.042]
        kill_rates = [0.058, 0.060, 0.062, 0.064]
        p.rd_feed_rate = random.choice(feed_rates)
        p.rd_kill_rate = random.choice(kill_rates)
        p.rd_contour_level = round(random.uniform(0.22, 0.35), 2)

    elif chosen_mode == "stippling":
        p.stippling_points = random.choice([1000, 1400, 1800, 2200])
        p.stippling_lloyd_passes = random.choice([4, 6, 8])
        p.stippling_min_radius = round(random.uniform(0.6, 1.2), 1)
        p.stippling_max_radius = round(random.uniform(2.4, 4.0), 1)
        p.stippling_size_by_darkness = random.random() < 0.90

    elif chosen_mode == "sbr":
        p.sbr_strokes = random.choice([1000, 1400, 1800, 2400])
        p.sbr_length = round(random.uniform(11.0, 20.0), 1)
        p.sbr_curvature = round(random.uniform(0.45, 0.80), 2)
        p.sbr_align_mode = random.choice(["tangent", "cross"])

    elif chosen_mode == "isocontours":
        p.iso_levels = random.choice([10, 14, 18, 22])
        p.iso_min_level = round(random.uniform(0.06, 0.16), 2)
        p.iso_max_level = round(random.uniform(0.82, 0.95), 2)
        p.iso_smoothing = round(random.uniform(1.0, 2.2), 1)

    elif chosen_mode == "physarum":
        p.physarum_agents = random.choice([900, 1300, 1700])
        p.physarum_iterations = random.choice([30, 40, 50])
        p.physarum_sim_res = random.choice([130, 150, 170])
        p.physarum_decay = round(random.uniform(0.86, 0.94), 2)
        p.physarum_sensor_angle = round(random.uniform(25.0, 40.0), 1)

    elif chosen_mode == "string_art":
        p.string_pins = random.choice([160, 200, 240])
        p.string_max_lines = random.choice([1000, 1400, 1800])
        p.string_weight = round(random.uniform(0.14, 0.24), 2)
        p.string_shape = random.choice(["circle", "rectangle"])

    elif chosen_mode == "diffgrowth":
        p.diffgrowth_iterations = random.choice([35, 45, 55])
        p.diffgrowth_max_nodes = random.choice([900, 1300, 1600])
        p.diffgrowth_collision_r = round(random.uniform(4.5, 7.5), 1)
        p.diffgrowth_split_dist = round(random.uniform(4.0, 6.5), 1)

    # 5. Ink & Pen styling
    p.stroke_color = random.choice(INK_PALETTE)
    p.stroke_width_mm = random.choice([0.25, 0.30, 0.35, 0.40, 0.50])

    return p


_STYLE_NAME_POOLS = {
    "spiral": [
        "Hypnotische Spirale",
        "Galaktischer Wirbel",
        "Eindimensionale Schlinge",
        "Zyklische Spirallinie",
        "Kosmische Windung",
        "Zentrierte Spirale",
    ],
    "waveform": [
        "Pulsierende Topografie",
        "Wellenberg-Relief",
        "Joy-Division-Horizont",
        "Schallwellen-Profil",
        "Seismische Höhenschichten",
        "Oszillogramm-Skizze",
    ],
    "tsp": [
        "Kontinuierlicher Faden",
        "Einfaden-Wanderschaft",
        "Minimalistischer TSP-Pfad",
        "Ununterbrochene Tour",
        "Euler-Schleifenzeichnung",
    ],
    "delaunay": [
        "Kristallines Poly-Netz",
        "Geometrisches Facettenwerk",
        "Prismatische Zerlegung",
        "Low-Poly Struktur",
        "Triangulierte Abstraktion",
    ],
    "flowfield": [
        "Fließende Strömungslinien",
        "Organisches Flussfeld",
        "Topografische Vektoren",
        "Dynamische Wirbelpfade",
        "Van-Gogh-Streamlines",
    ],
    "voronoi": [
        "Biologische Zellstruktur",
        "Mosaik-Facetten",
        "Bienenwaben-Netzwerk",
        "Zellulare Dekomposition",
        "Polygonaler Mikrokosmos",
    ],
    "reaction_diffusion": [
        "Organische Turing-Muster",
        "Bio-Diffusionsgeflecht",
        "Korallenstruktur",
        "Turing-Streifentextur",
        "Morphogenetisches Gewebe",
    ],
    "stippling": [
        "Punktierte Schattierung",
        "Stippling-Punktraster",
        "Lloyd-Punktgrau",
        "Feinstaub-Rasterung",
        "Voronoi-Stippling Art",
    ],
    "sbr": [
        "Impressionistischer Duktus",
        "Bézier-Pinselstriche",
        "Dynamische Schraffurzüge",
        "Expressiver Pinselduktus",
        "Malerische Strichführung",
    ],
    "isocontours": [
        "Geodätische Höhenlinien",
        "Höhenschichten-Relief",
        "Topografische Isolinien",
        "Kartografische Höhenstufe",
        "Marching-Squares Map",
    ],
    "physarum": [
        "Schleimpilz-Adernetz",
        "Biomorphe Transportpfade",
        "Organisches Myzel",
        "Physarum-Leitbahnen",
        "Autonome Spurnetzwerke",
    ],
    "string_art": [
        "Fadenbild-Radialspannung",
        "String-Art Polyeder",
        "Sehnen-Transparenz",
        "Geometrische Fadengeometrie",
        "Radon-Sehnenspannung",
    ],
    "diffgrowth": [
        "Differenzielles Korallenwachstum",
        "Verzweigte Wachstumskette",
        "Mäanderndes Band",
        "Organische Wachstumsfalten",
        "Expansionierende Zellkette",
    ],
    "hatching": [
        "Klassische Kupferstich-Gravur",
        "Feine Kreuzschraffur",
        "Bézier-Schraffierte Skizze",
        "Architektonische Schraffur",
        "Organische Konturschraffur",
    ],
    "shapes": [
        "Geometrisches Formraster",
        "Typografische Rasterung",
        "Halbton-Formenmuster",
        "Pixelart-Formgewebe",
    ],
    "classic": [
        "Feine Vektorkonturen",
        "Expressive Kontursilhouette",
        "Klare Umrisszeichnung",
        "Minimalistische Linienführung",
        "Organische Bézier-Kontur",
    ],
}


def suggest_preset_name(params: PlotParameters) -> str:
    """Generate an appealing, descriptive German preset name based on parameter characteristics."""
    mode = params.artistic_mode.lower() if params.artistic_mode else "none"

    if mode in _STYLE_NAME_POOLS:
        candidates = _STYLE_NAME_POOLS[mode]
    elif params.use_hatching:
        candidates = _STYLE_NAME_POOLS["hatching"]
    elif params.use_shapes:
        candidates = _STYLE_NAME_POOLS["shapes"]
    else:
        candidates = _STYLE_NAME_POOLS["classic"]

    base = random.choice(candidates)

    # Add filter qualifiers if strong pre-filters are active
    if params.use_pixel_sort:
        return f"{base} (Pixel-Sort)"
    if params.use_quadtree:
        return f"{base} (Quadtree)"
    if params.use_kuwahara:
        return f"{base} (Kuwahara)"
    if params.use_fft:
        return f"{base} (FFT-Moiré)"
    if params.use_ca:
        return f"{base} (Zellular-Automat)"

    return base
