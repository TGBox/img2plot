"""
Unit tests for the new artistic styles and image filters:
- Quadtree decomposition (Block abstraction & vector box plotting)
- Pixel Sorting (Glitch art)
- Voronoi Mosaic (Cellular tessellation)
- Reaction-Diffusion (Turing patterns / Gray-Scott)
- Weighted Voronoi Stippling (Lloyd relaxation)
- Stroke-Based Rendering (SBR parametric Bézier strokes)
"""

import numpy as np
import pytest

from img2plot.core.parameters import PlotParameters
from img2plot.core.engine import PlotEngine, StrokePath
from img2plot.core.quadtree import apply_quadtree_decomposition
from img2plot.core.pixel_sort import apply_pixel_sort
from img2plot.core.voronoi_art import generate_voronoi_art
from img2plot.core.reaction_diffusion import generate_reaction_diffusion
from img2plot.core.voronoi_stippling import generate_voronoi_stippling
from img2plot.core.sbr import generate_sbr_art
from img2plot.core.anisotropic_kuwahara import apply_anisotropic_kuwahara
from img2plot.core.fft_filter import apply_fft_filter
from img2plot.core.cellular_automata import apply_cyclic_ca
from img2plot.core.isocontour_art import generate_isocontours
from img2plot.core.physarum_art import generate_physarum_art
from img2plot.core.string_art import generate_string_art
from img2plot.core.diffgrowth_art import generate_diffgrowth_art
from img2plot.gui.sidebar import SidebarWidget


@pytest.fixture
def test_image():
    """Create a 120x120 synthetic test image with a dark circle on light background."""
    img = np.ones((120, 120), dtype=np.float32)
    yy, xx = np.mgrid[0:120, 0:120]
    dist = np.hypot(xx - 60, yy - 60)
    img[dist < 35] = 0.1  # Dark circular region
    return img


def test_quadtree_decomposition(test_image):
    # Test filter abstraction and vector boxes
    abs_img, boxes = apply_quadtree_decomposition(
        test_image,
        variance_threshold=0.05,
        min_size=8,
        max_depth=5,
        render_boxes=True,
    )
    assert abs_img.shape == test_image.shape
    assert 0.0 <= abs_img.min() <= abs_img.max() <= 1.0
    assert len(boxes) > 0
    assert all(len(b.points) == 5 for b in boxes)  # closed rectangle: 5 points

    # Test cancellation
    _, empty_boxes = apply_quadtree_decomposition(
        test_image,
        render_boxes=True,
        is_cancelled=lambda: True,
    )
    assert len(empty_boxes) == 0


def test_pixel_sort(test_image):
    # Test horizontal sort
    sorted_h = apply_pixel_sort(
        test_image,
        direction="horizontal",
        lower_threshold=0.05,
        upper_threshold=0.50,
        reverse=False,
    )
    assert sorted_h.shape == test_image.shape
    assert sorted_h.dtype == test_image.dtype

    # Test vertical sort with reverse
    sorted_v = apply_pixel_sort(
        test_image,
        direction="vertical",
        lower_threshold=0.05,
        upper_threshold=0.50,
        reverse=True,
    )
    assert sorted_v.shape == test_image.shape


def test_voronoi_mosaic(test_image):
    paths = generate_voronoi_art(
        test_image,
        num_points=150,
        edge_weight=0.5,
    )
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) == 2
        p1, p2 = p.points
        # Inside image boundary
        assert 0.0 <= p1[0] <= 120.0 and 0.0 <= p1[1] <= 120.0
        assert 0.0 <= p2[0] <= 120.0 and 0.0 <= p2[1] <= 120.0


def test_reaction_diffusion(test_image):
    paths = generate_reaction_diffusion(
        test_image,
        sim_resolution=60,
        iterations=40,
        feed_rate=0.037,
        kill_rate=0.060,
        contour_level=0.25,
    )
    assert isinstance(paths, list)
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) >= 3


def test_voronoi_stippling(test_image):
    paths = generate_voronoi_stippling(
        test_image,
        num_points=120,
        lloyd_iterations=3,
        min_radius=0.5,
        max_radius=2.5,
        size_by_darkness=True,
    )
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) >= 8
        assert p.svg_d.startswith("__circle__")
        assert "fill=1" in p.svg_d


def test_stroke_based_rendering(test_image):
    paths = generate_sbr_art(
        test_image,
        num_strokes=100,
        stroke_length=14.0,
        curvature=0.6,
        step_size=2.0,
        align_mode="tangent",
    )
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) >= 2
        assert p.is_artistic is True


def test_anisotropic_kuwahara(test_image):
    filtered = apply_anisotropic_kuwahara(test_image, radius=3, sharpness=4.0)
    assert filtered.shape == test_image.shape
    assert filtered.dtype == np.float32
    assert 0.0 <= filtered.min() <= filtered.max() <= 1.0


def test_fft_filter(test_image):
    for f_type in ["moiré", "bandpass", "interference", "highpass"]:
        filtered = apply_fft_filter(test_image, mode=f_type, frequency=20.0, strength=0.5)
        assert filtered.shape == test_image.shape
        assert filtered.dtype == np.float32
        assert 0.0 <= filtered.min() <= filtered.max() <= 1.0


def test_cyclic_ca(test_image):
    ca_img = apply_cyclic_ca(test_image, num_states=6, iterations=3, threshold=1)
    assert ca_img.shape == test_image.shape
    assert ca_img.dtype == np.float32
    assert 0.0 <= ca_img.min() <= ca_img.max() <= 1.0


def test_isocontours(test_image):
    paths = generate_isocontours(test_image, num_levels=6, min_length=5)
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) >= 2
        assert p.is_artistic is True


def test_physarum_art(test_image):
    paths = generate_physarum_art(test_image, num_agents=80, iterations=15, decay_factor=0.85)
    assert isinstance(paths, list)
    for p in paths:
        assert len(p.points) >= 2
        assert p.is_artistic is True


def test_string_art(test_image):
    # Circle
    paths_c = generate_string_art(test_image, num_pins=48, max_strings=120, pin_shape="circle")
    assert len(paths_c) == 1
    assert len(paths_c[0].points) > 10
    # Rectangle
    paths_s = generate_string_art(test_image, num_pins=48, max_strings=120, pin_shape="rectangle")
    assert len(paths_s) == 1
    assert len(paths_s[0].points) > 10


def test_diffgrowth_art(test_image):
    paths = generate_diffgrowth_art(test_image, iterations=15, max_nodes=80, split_dist=8.0)
    assert len(paths) > 0
    for p in paths:
        assert len(p.points) >= 2
        assert p.is_artistic is True


def test_engine_integration_with_new_modes(test_image):
    from PIL import Image

    pil_img = Image.fromarray((test_image * 255).astype(np.uint8))

    # 1. Voronoi mode
    params_voronoi = PlotParameters(artistic_mode="voronoi", voronoi_points=80)
    engine_voronoi = PlotEngine(params_voronoi)
    res_voronoi = engine_voronoi.process_image(pil_img, is_preview=True)
    assert len(res_voronoi.paths) > 0

    # 2. Reaction-Diffusion mode
    params_rd = PlotParameters(
        artistic_mode="reaction_diffusion",
        rd_sim_resolution=50,
        rd_iterations=30,
    )
    engine_rd = PlotEngine(params_rd)
    res_rd = engine_rd.process_image(pil_img, is_preview=True)
    assert len(res_rd.paths) > 0

    # 3. Stippling mode
    params_stip = PlotParameters(
        artistic_mode="stippling",
        stippling_points=80,
        stippling_lloyd_passes=2,
    )
    engine_stip = PlotEngine(params_stip)
    res_stip = engine_stip.process_image(pil_img, is_preview=True)
    assert len(res_stip.paths) > 0

    # 4. SBR mode
    params_sbr = PlotParameters(
        artistic_mode="sbr",
        sbr_strokes=80,
        sbr_length=12.0,
    )
    engine_sbr = PlotEngine(params_sbr)
    res_sbr = engine_sbr.process_image(pil_img, is_preview=True)
    assert len(res_sbr.paths) > 0

    # 5. Isocontours mode
    params_iso = PlotParameters(
        artistic_mode="isocontours",
        iso_levels=8,
    )
    engine_iso = PlotEngine(params_iso)
    res_iso = engine_iso.process_image(pil_img, is_preview=True)
    assert len(res_iso.paths) > 0

    # 6. Physarum mode
    params_phy = PlotParameters(
        artistic_mode="physarum",
        physarum_agents=80,
        physarum_iterations=15,
    )
    engine_phy = PlotEngine(params_phy)
    res_phy = engine_phy.process_image(pil_img, is_preview=True)
    assert isinstance(res_phy.paths, list)

    # 7. String art mode
    params_str = PlotParameters(
        artistic_mode="string_art",
        string_pins=48,
        string_max_lines=100,
    )
    engine_str = PlotEngine(params_str)
    res_str = engine_str.process_image(pil_img, is_preview=True)
    assert len(res_str.paths) > 0

    # 8. Diffgrowth mode
    params_dg = PlotParameters(
        artistic_mode="diffgrowth",
        diffgrowth_iterations=15,
        diffgrowth_max_nodes=60,
    )
    engine_dg = PlotEngine(params_dg)
    res_dg = engine_dg.process_image(pil_img, is_preview=True)
    assert len(res_dg.paths) > 0

    # 9. Preprocessing filter with Anisotropic Kuwahara + FFT
    params_filters = PlotParameters(
        use_kuwahara=True,
        kuwahara_mode="anisotropic",
        kuwahara_radius=2,
        use_fft=True,
        fft_mode="moiré",
        artistic_mode="none",
    )
    engine_filters = PlotEngine(params_filters)
    res_filters = engine_filters.process_image(pil_img, is_preview=True)
    assert len(res_filters.paths) > 0

    # 10. Preprocessing filter with Quadtree vector boxes
    params_qt = PlotParameters(
        use_quadtree=True,
        quadtree_threshold=0.05,
        quadtree_min_size=10,
        quadtree_render_boxes=True,
        artistic_mode="none",
    )
    engine_qt = PlotEngine(params_qt)
    res_qt = engine_qt.process_image(pil_img, is_preview=True)
    assert len(res_qt.paths) > 0


def test_sidebar_ui_new_styles_and_badges(app):
    sidebar = SidebarWidget()

    # Verify all 14 artistic modes exist in combo box
    assert sidebar.combo_artistic_mode.count() == 14
    assert "Voronoi" in sidebar.combo_artistic_mode.itemText(6)
    assert "Reaktions-Diffusion" in sidebar.combo_artistic_mode.itemText(7)
    assert "Stippling" in sidebar.combo_artistic_mode.itemText(8)
    assert "Stroke-Based" in sidebar.combo_artistic_mode.itemText(9)
    assert "Marching Squares" in sidebar.combo_artistic_mode.itemText(10)
    assert "Physarum" in sidebar.combo_artistic_mode.itemText(11)
    assert "String-Art" in sidebar.combo_artistic_mode.itemText(12)
    assert "Differenzielles" in sidebar.combo_artistic_mode.itemText(13)

    # Check subpanels switching
    sidebar.combo_artistic_mode.setCurrentIndex(10)
    assert sidebar.widget_iso_opts.isHidden() is False
    assert "Iso" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(11)
    assert sidebar.widget_physarum_opts.isHidden() is False
    assert "Physarum" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(12)
    assert sidebar.widget_string_opts.isHidden() is False
    assert "String-Art" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(13)
    assert sidebar.widget_diffgrowth_opts.isHidden() is False
    assert "Diff-Growth" in sidebar.acc_artistic.lbl_badge.text()

    # Check filter controls
    sidebar.chk_fft.setChecked(True)
    assert sidebar.widget_fft_opts.isHidden() is False
    assert "FFT" in sidebar.acc_filter.lbl_badge.text()

    sidebar.chk_fft.setChecked(False)
    sidebar.chk_ca.setChecked(True)
    assert sidebar.widget_ca_opts.isHidden() is False
    assert "CCA" in sidebar.acc_filter.lbl_badge.text()

    # Parameter sync
    params = sidebar.get_current_parameters()
    assert params.artistic_mode == "diffgrowth"
    assert params.use_ca is True


def test_svg_export_new_styles(test_image, tmp_path):
    from PIL import Image
    from img2plot.core.exporter import export_svg

    pil_img = Image.fromarray((test_image * 255).astype(np.uint8))

    modes_to_test = [
        "voronoi",
        "reaction_diffusion",
        "stippling",
        "sbr",
        "isocontours",
        "physarum",
        "string_art",
        "diffgrowth",
    ]
    for mode in modes_to_test:
        params = PlotParameters(artistic_mode=mode)
        if mode == "reaction_diffusion":
            params.rd_sim_resolution = 50
            params.rd_iterations = 25
        elif mode == "physarum":
            params.physarum_agents = 80
            params.physarum_iterations = 15
        elif mode == "string_art":
            params.string_pins = 48
            params.string_max_lines = 100
        elif mode == "diffgrowth":
            params.diffgrowth_iterations = 15
            params.diffgrowth_max_nodes = 50
        engine = PlotEngine(params)
        res = engine.process_image(pil_img, is_preview=True)

        svg_out = str(tmp_path / f"export_{mode}.svg")
        export_svg(res, params, svg_out)
        with open(svg_out, "r", encoding="utf-8") as f:
            svg_content = f.read()
            assert "<svg" in svg_content
            assert "</svg>" in svg_content

