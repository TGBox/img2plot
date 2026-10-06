"""
Tests for Preset Laboratory and Randomizer components.
"""

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from img2plot.core.parameters import PlotParameters
from img2plot.core.engine import EngineResult, StrokePath
from img2plot.core.randomizer import (
    ARTISTIC_MODES,
    generate_random_parameters,
    suggest_preset_name,
)
from img2plot.core.presets import get_all_presets, delete_user_preset
from img2plot.gui.preset_lab import (
    PresetLabWindow,
    PresetCardWidget,
    PresetSaveDialog,
    render_result_to_pixmap,
)


def test_generate_random_parameters_coverage():
    """Verify random parameter generation produces valid parameters within boundaries."""
    modes_seen = set()
    for _ in range(60):
        params = generate_random_parameters()
        assert isinstance(params, PlotParameters)
        assert params.artistic_mode in ARTISTIC_MODES
        modes_seen.add(params.artistic_mode)
        assert 0.0 <= params.termination_ratio <= 1.0
        assert params.min_line_length >= 5
        assert params.preview_max_dim > 0
        assert params.stroke_color.startswith("#")

    # Over 60 draws, several artistic modes should be observed
    assert len(modes_seen) >= 6


def test_generate_random_parameters_forced_mode():
    """Verify passing a specific mode forces that artistic style."""
    for mode in ["spiral", "waveform", "flowfield", "voronoi", "physarum", "string_art"]:
        p = generate_random_parameters(mode=mode)
        assert p.artistic_mode == mode


def test_suggest_preset_name():
    """Verify intelligent German naming suggestions for various modes."""
    p_spiral = PlotParameters(artistic_mode="spiral")
    name_spiral = suggest_preset_name(p_spiral)
    assert isinstance(name_spiral, str) and len(name_spiral) > 3

    p_wave = PlotParameters(artistic_mode="waveform")
    name_wave = suggest_preset_name(p_wave)
    assert isinstance(name_wave, str) and len(name_wave) > 3

    p_filtered = PlotParameters(artistic_mode="spiral", use_pixel_sort=True)
    name_filtered = suggest_preset_name(p_filtered)
    assert "(Pixel-Sort)" in name_filtered

    p_quad = PlotParameters(artistic_mode="flowfield", use_quadtree=True)
    name_quad = suggest_preset_name(p_quad)
    assert "(Quadtree)" in name_quad


def test_render_result_to_pixmap():
    """Verify thumbnail rendering of EngineResult into QPixmap."""
    path1 = StrokePath(points=[(10.0, 10.0), (50.0, 50.0), (90.0, 30.0)])
    path2 = StrokePath(
        points=[],
        is_bezier=True,
        cubic_segments=[((10.0, 10.0), (20.0, 30.0), (40.0, 60.0), (70.0, 70.0))],
    )
    import numpy as np
    from img2plot.core.engine import PlotStats

    result = EngineResult(
        paths=[path1, path2],
        width=100,
        height=100,
        preprocessed_gray=np.zeros((100, 100), dtype=float),
        sobel_magnitude=np.zeros((100, 100), dtype=float),
        stats=PlotStats(),
    )

    pixmap = render_result_to_pixmap(result, stroke_color="#1e3a8a", target_size=200)
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 200
    assert pixmap.height() == 200


def test_preset_card_widget(qapp):
    """Test PresetCardWidget favorite toggling and appearance."""
    dummy_pixmap = QPixmap(100, 100)
    dummy_pixmap.fill(Qt.GlobalColor.white)
    params = PlotParameters(artistic_mode="voronoi")

    card = PresetCardWidget(
        index=0,
        params=params,
        pixmap=dummy_pixmap,
        suggested_name="Test Voronoi",
    )

    assert not card.is_favorite
    assert "🤍" in card.btn_fav.text()

    # Toggle favorite
    events_received = []
    card.sig_favorite_toggled.connect(lambda idx, fav: events_received.append((idx, fav)))

    card._toggle_favorite()
    assert card.is_favorite
    assert "❤️" in card.btn_fav.text()
    assert len(events_received) == 1
    assert events_received[0] == (0, True)

    # Untoggle
    card._toggle_favorite()
    assert not card.is_favorite
    assert len(events_received) == 2
    assert events_received[1] == (0, False)


def test_preset_lab_window_and_selection(qapp):
    """Test PresetLabWindow gallery selection helpers and fullscreen toggle."""
    win = PresetLabWindow()
    assert win.windowTitle() == "img2plot - Preset-Labor & Stil-Entdecker"

    # Fullscreen toggle
    assert not win.is_fullscreen
    win.toggle_fullscreen()
    assert win.is_fullscreen
    win.toggle_fullscreen()
    assert not win.is_fullscreen

    # Simulate cards added
    dummy_pixmap = QPixmap(100, 100)
    dummy_pixmap.fill(Qt.GlobalColor.white)

    win._on_item_ready(0, PlotParameters(artistic_mode="spiral"), dummy_pixmap)
    win._on_item_ready(1, PlotParameters(artistic_mode="waveform"), dummy_pixmap)
    assert len(win.card_widgets) == 2

    # Select all / Unselect all
    win.select_all_cards()
    assert all(c.is_favorite for c in win.card_widgets)
    assert win.btn_save_favs.isEnabled()

    win.unselect_all_cards()
    assert not any(c.is_favorite for c in win.card_widgets)
    assert not win.btn_save_favs.isEnabled()

    # Filter toggles
    win.card_widgets[0].set_favorite(True)
    win._filter_favs_clicked()
    assert win.card_widgets[0].isVisible()
    assert not win.card_widgets[1].isVisible()

    win._filter_all_clicked()
    assert win.card_widgets[0].isVisible()
    assert win.card_widgets[1].isVisible()

    win.close()


def test_preset_save_dialog_and_persistence(qapp, tmp_path, monkeypatch):
    """Test PresetSaveDialog saving user presets to disk."""
    dummy_pixmap = QPixmap(64, 64)
    dummy_pixmap.fill(Qt.GlobalColor.white)

    # Mock user preset directory to a temp path
    test_preset_dir = str(tmp_path / "presets")
    monkeypatch.setattr("img2plot.core.presets.get_user_presets_dir", lambda: test_preset_dir)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)

    favorites = [
        {
            "index": 0,
            "params": PlotParameters(artistic_mode="spiral", spiral_loops=88),
            "pixmap": dummy_pixmap,
            "suggested_name": "Test Spirale Labor",
        }
    ]

    dlg = PresetSaveDialog(favorites)
    assert dlg.table.rowCount() == 1
    assert dlg.edit_fields[0].text() == "Test Spirale Labor"

    # Change name in input field
    dlg.edit_fields[0].setText("Mein Super Spiral Preset")

    # Save
    dlg._save_presets()

    # Verify saved file exists
    saved_file = os.path.join(test_preset_dir, "Mein Super Spiral Preset.json")
    assert os.path.isfile(saved_file)

    # Verify loaded preset matches parameters
    all_presets = get_all_presets()
    assert "Mein Super Spiral Preset" in all_presets
    assert all_presets["Mein Super Spiral Preset"].spiral_loops == 88

    dlg.close()
