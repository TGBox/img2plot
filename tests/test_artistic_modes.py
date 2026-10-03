"""
Unit tests for non-AI artistic modes and Kuwahara filter in img2plot.
"""

import numpy as np
import pytest

from img2plot.core.parameters import PlotParameters
from img2plot.core.engine import PlotEngine, StrokePath
from img2plot.core.kuwahara import apply_kuwahara
from img2plot.core.waveform import generate_waveform
from img2plot.core.spiral import generate_spiral
from img2plot.core.tsp_art import generate_tsp_art
from img2plot.core.delaunay_art import generate_delaunay_art
from img2plot.core.flowfield import generate_flowfield
from img2plot.core.presets import DEFAULT_PRESETS
from img2plot.core.exporter import export_svg


@pytest.fixture
def synthetic_image():
    """Create a 120x120 synthetic test image with a dark circle on light background."""
    img = np.ones((120, 120), dtype=np.float32)
    yy, xx = np.mgrid[0:120, 0:120]
    dist = np.hypot(xx - 60, yy - 60)
    img[dist < 35] = 0.1  # Dark circular region
    return img


def test_kuwahara_filter(synthetic_image):
    """Test Kuwahara painterly filter on synthetic image."""
    filtered = apply_kuwahara(synthetic_image, radius=3)
    assert filtered.shape == synthetic_image.shape
    assert filtered.dtype == np.float32
    assert 0.0 <= filtered.min() <= filtered.max() <= 1.0
    # Center should remain dark and corners light
    assert filtered[60, 60] < 0.2
    assert filtered[5, 5] > 0.8


def test_waveform_generation(synthetic_image):
    """Test Waveform / Joy Division art generation with and without occlusion."""
    # With occlusion
    paths_occ = generate_waveform(
        synthetic_image,
        num_lines=25,
        amplitude=15.0,
        resolution=100,
        occlusion=True,
    )
    assert len(paths_occ) > 0
    assert all(len(p.points) >= 2 for p in paths_occ)

    # Without occlusion
    paths_no_occ = generate_waveform(
        synthetic_image,
        num_lines=20,
        amplitude=12.0,
        resolution=80,
        occlusion=False,
    )
    assert len(paths_no_occ) == 20
    assert all(len(p.points) == 80 for p in paths_no_occ)


def test_spiral_generation(synthetic_image):
    """Test Archimedean Spiral single-stroke art generation."""
    paths = generate_spiral(
        synthetic_image,
        num_loops=25,
        resolution=150,
        amplitude=3.0,
        frequency=15.0,
    )
    assert len(paths) == 1
    spiral = paths[0]
    assert len(spiral.points) > 500
    assert spiral.svg_d.startswith("M ")
    assert spiral.length() > 500.0


def test_tsp_art_generation(synthetic_image):
    """Test TSP Single-Line tour generation."""
    paths = generate_tsp_art(
        synthetic_image,
        num_points=180,
        two_opt_passes=5,
    )
    assert len(paths) == 1
    tsp_tour = paths[0]
    assert len(tsp_tour.points) >= 50
    # Closed tour: start point equals end point
    assert tsp_tour.points[0] == tsp_tour.points[-1]
    assert tsp_tour.length() > 100.0


def test_delaunay_art_generation(synthetic_image):
    """Test Delaunay Low-Poly wireframe generation."""
    paths = generate_delaunay_art(
        synthetic_image,
        num_points=120,
        edge_weight=0.5,
    )
    assert len(paths) > 20
    for p in paths:
        assert len(p.points) == 2
        assert p.svg_d.startswith("M ")


def test_flowfield_generation(synthetic_image):
    """Test Flow Field / Streamlines generation."""
    paths = generate_flowfield(
        synthetic_image,
        num_lines=100,
        step_len=3.0,
        max_steps=25,
        direction="tangent",
    )
    assert len(paths) > 10
    assert all(len(p.points) >= 2 for p in paths)


def test_engine_integration_artistic_modes(synthetic_image, tmp_path):
    """Test PlotEngine execution across all artistic modes and export to SVG."""
    modes = ["waveform", "spiral", "tsp", "delaunay", "flowfield"]

    for mode in modes:
        params = PlotParameters(
            artistic_mode=mode,
            waveform_lines=20,
            spiral_loops=20,
            tsp_points=150,
            tsp_2opt_passes=3,
            delaunay_points=80,
            flowfield_lines=80,
            use_kuwahara=True,
            kuwahara_radius=2,
            preview_max_dim=120,
        )
        engine = PlotEngine(params)
        res = engine.process_image(synthetic_image, is_preview=True)

        assert len(res.paths) > 0
        assert res.stats.total_strokes > 0
        assert res.stats.artistic_strokes > 0

        # Verify SVG export
        svg_file = tmp_path / f"test_{mode}.svg"
        export_svg(res, params, str(svg_file))
        assert svg_file.exists()
        assert svg_file.stat().st_size > 100


def test_artistic_presets_exist():
    """Verify that all new artistic presets are registered in DEFAULT_PRESETS."""
    expected_presets = [
        "Wellenform (Joy Division)",
        "Archimedische Spirale (1-Linie)",
        "TSP Single-Line (Handlungsreisender)",
        "Low-Poly (Delaunay-Mosaik)",
        "Flussfeld (Van-Gogh-Linien)",
        "Malerisches Ölgemälde (Kuwahara)",
    ]
    for name in expected_presets:
        assert name in DEFAULT_PRESETS
        p = DEFAULT_PRESETS[name]
        assert isinstance(p, PlotParameters)
