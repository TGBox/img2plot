"""
Unit tests for the img2plot vectorization engine, bezier curves, presets, and exporters.
"""

import os
import tempfile
import numpy as np
import pytest
from PIL import Image

from img2plot.core.parameters import PlotParameters
from img2plot.core.presets import DEFAULT_PRESETS, load_preset_file, save_preset_file
from img2plot.core.bezier import fit_cubic_spline, segments_to_svg_path, discretize_segments
from img2plot.core.hatching import generate_hatching
from img2plot.core.engine import PlotEngine, StrokePath
from img2plot.core.exporter import export_svg, export_png


def test_parameters_serialization():
    p = PlotParameters(min_line_length=15, line_mode="bezier", use_hatching=True)
    d = p.to_dict()
    assert d["min_line_length"] == 15
    assert d["line_mode"] == "bezier"
    assert d["use_hatching"] is True

    json_str = p.to_json()
    p2 = PlotParameters.from_json(json_str)
    assert p2.min_line_length == 15
    assert p2.line_mode == "bezier"
    assert p2.use_hatching is True


def test_presets_io():
    with tempfile.TemporaryDirectory() as tmpdir:
        preset_file = os.path.join(tmpdir, "custom_preset.json")
        p = DEFAULT_PRESETS["Künstlerische Skizze"]
        save_preset_file(p, preset_file)
        assert os.path.isfile(preset_file)

        loaded = load_preset_file(preset_file)
        assert loaded.line_mode == "bezier"
        assert loaded.bezier_smoothness == p.bezier_smoothness


def test_user_presets_persistence(monkeypatch, tmp_path):
    from img2plot.core import presets
    monkeypatch.setattr(presets, "get_user_presets_dir", lambda: str(tmp_path))

    p = PlotParameters(min_line_length=42, line_mode="bezier")
    saved_name = presets.save_user_preset("Mein Test Profil", p)
    assert saved_name == "Mein Test Profil"

    user_list = presets.list_user_presets()
    assert "Mein Test Profil" in user_list
    assert user_list["Mein Test Profil"].min_line_length == 42

    all_presets = presets.get_all_presets()
    assert "Mein Test Profil" in all_presets
    assert "Standard" in all_presets

    deleted = presets.delete_user_preset("Mein Test Profil")
    assert deleted is True
    assert "Mein Test Profil" not in presets.list_user_presets()



def test_bezier_fitting():
    # Test with colinear points
    points = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    segments = fit_cubic_spline(points, tension=0.35, sample_step=1)
    assert len(segments) == 3

    svg_d = segments_to_svg_path(segments)
    assert svg_d.startswith("M 0.00,0.00 C")

    pts = discretize_segments(segments, steps_per_segment=4)
    assert len(pts) > len(points)


def test_hatching_generation():
    # Create image with a dark circular spot in center to test contour curvature
    y, x = np.ogrid[:100, :100]
    dist_from_center = np.hypot(x - 50, y - 50)
    # Circular gradient: dark at center, bright at edge
    img = np.clip(dist_from_center / 50.0, 0.0, 1.0).astype(np.float32)

    # 1. Test Bezier form-following hatching
    bezier_strokes = generate_hatching(
        img,
        threshold=0.50,
        spacing=8,
        angle_deg=45.0,
        cross_hatch=True,
        min_length=5,
        mode="bezier",
        curve_strength=0.8,
        wobble=0.2,
    )
    assert len(bezier_strokes) > 0
    # Check that bezier strokes have cubic segments and valid SVG path strings
    has_bezier = any(s.is_bezier for s in bezier_strokes)
    assert has_bezier is True
    for s in bezier_strokes:
        if s.is_bezier:
            assert len(s.cubic_segments) > 0
            assert "C" in s.svg_d
        # Backward compatibility unpacking
        p1, p2 = s
        assert len(p1) == 2
        assert len(p2) == 2

    # 2. Test classic straight hatching
    straight_strokes = generate_hatching(
        img,
        threshold=0.50,
        spacing=8,
        angle_deg=45.0,
        cross_hatch=False,
        min_length=5,
        mode="straight",
    )
    assert len(straight_strokes) > 0
    for s in straight_strokes:
        assert s.is_bezier is False
        assert "L" in s.svg_d


def test_engine_processing_and_exports():
    # Synthetic test image with sharp contrast edges
    arr = np.zeros((80, 80, 3), dtype=np.uint8)
    arr[20:60, 20:60] = 255  # White square on black background
    test_img = Image.fromarray(arr)

    params = PlotParameters(
        termination_ratio=0.3,
        min_line_length=10,
        line_mode="bezier",
        use_hatching=True,
        hatching_threshold=0.5,
        hatching_spacing=10,
    )

    engine = PlotEngine(params)
    progress_records = []

    def on_progress(p, msg):
        progress_records.append((p, msg))

    result = engine.process_image(test_img, is_preview=True, progress_callback=on_progress)
    assert len(result.paths) > 0
    assert result.stats.total_strokes == len(result.paths)
    assert result.width == 80
    assert result.height == 80
    assert len(progress_records) > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        svg_file = os.path.join(tmpdir, "test.svg")
        export_svg(result, params, svg_file)
        assert os.path.isfile(svg_file)
        with open(svg_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "<svg" in content
            assert "layer_contours" in content

        png_file = os.path.join(tmpdir, "test.png")
        export_png(result, params, png_file)
        assert os.path.isfile(png_file)
        assert os.path.getsize(png_file) > 100


def test_engine_preprocess_cache():
    from img2plot.core.engine import _PREPROCESS_CACHE
    arr = np.zeros((60, 60, 3), dtype=np.uint8)
    arr[15:45, 15:45] = 255
    test_img = Image.fromarray(arr)

    p1 = PlotParameters(min_line_length=15, termination_ratio=0.5)
    e1 = PlotEngine(p1)
    res1 = e1.process_image(test_img, is_preview=True)
    assert len(_PREPROCESS_CACHE) == 1

    # Second run with different line parameters re-uses cache
    p2 = PlotParameters(min_line_length=20, termination_ratio=0.7)
    e2 = PlotEngine(p2)
    res2 = e2.process_image(test_img, is_preview=True)
    assert res1.preprocessed_gray is res2.preprocessed_gray or np.array_equal(res1.preprocessed_gray, res2.preprocessed_gray)

