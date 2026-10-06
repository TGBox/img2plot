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

    # 5. Preprocessing filter with Quadtree vector boxes
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

    # Verify new artistic mode items exist in combo box
    assert sidebar.combo_artistic_mode.count() == 10
    assert "Voronoi" in sidebar.combo_artistic_mode.itemText(6)
    assert "Reaktions-Diffusion" in sidebar.combo_artistic_mode.itemText(7)
    assert "Stippling" in sidebar.combo_artistic_mode.itemText(8)
    assert "Stroke-Based" in sidebar.combo_artistic_mode.itemText(9)

    # Check subpanels switching
    sidebar.combo_artistic_mode.setCurrentIndex(6)
    assert sidebar.widget_voronoi_opts.isHidden() is False
    assert sidebar.widget_rd_opts.isHidden() is True
    assert "Voronoi" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(7)
    assert sidebar.widget_rd_opts.isHidden() is False
    assert "Turing" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(8)
    assert sidebar.widget_stippling_opts.isHidden() is False
    assert "Stippling" in sidebar.acc_artistic.lbl_badge.text()

    sidebar.combo_artistic_mode.setCurrentIndex(9)
    assert sidebar.widget_sbr_opts.isHidden() is False
    assert "SBR" in sidebar.acc_artistic.lbl_badge.text()

    # Check filter controls
    sidebar.chk_quadtree.setChecked(True)
    assert sidebar.slider_quadtree_thresh.isHidden() is False
    assert "Quadtree" in sidebar.acc_filter.lbl_badge.text()

    sidebar.chk_pixel_sort.setChecked(True)
    assert sidebar.widget_pixel_sort_opts.isHidden() is False

    # Parameter sync
    params = sidebar.get_current_parameters()
    assert params.artistic_mode == "sbr"
    assert params.use_quadtree is True
    assert params.use_pixel_sort is True


def test_svg_export_new_styles(test_image, tmp_path):
    from PIL import Image
    from img2plot.core.exporter import export_svg

    pil_img = Image.fromarray((test_image * 255).astype(np.uint8))

    for mode in ["voronoi", "reaction_diffusion", "stippling", "sbr"]:
        params = PlotParameters(artistic_mode=mode)
        if mode == "reaction_diffusion":
            params.rd_sim_resolution = 50
            params.rd_iterations = 25
        engine = PlotEngine(params)
        res = engine.process_image(pil_img, is_preview=True)

        svg_out = str(tmp_path / f"export_{mode}.svg")
        export_svg(res, params, svg_out)
        with open(svg_out, "r", encoding="utf-8") as f:
            svg_content = f.read()
            assert "<svg" in svg_content
            assert "</svg>" in svg_content

