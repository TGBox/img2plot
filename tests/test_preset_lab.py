"""
Tests for Preset Laboratory and Randomizer components.
"""

import os
import pytest
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyleOptionViewItem, QWidget

from img2plot.core.parameters import PlotParameters
from img2plot.core.engine import EngineResult, StrokePath
from img2plot.core.randomizer import (
    ARTISTIC_MODES,
    generate_random_parameters,
    suggest_preset_name,
)
from img2plot.core.presets import get_all_presets, delete_user_preset
from img2plot.gui.preset_lab import (
    FAVORITE_ROLE,
    GalleryItem,
    PresetCardDelegate,
    PresetGalleryModel,
    PresetLabWindow,
    PresetSaveDialog,
    render_result_to_image,
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


def test_generate_random_parameters_artistic_only_and_classic_only():
    """Verify artistic_only never selects 'none', and classic_only always selects 'none'."""
    for _ in range(40):
        p_art = generate_random_parameters(mode="artistic_only")
        assert p_art.artistic_mode != "none"
        assert p_art.artistic_mode in ARTISTIC_MODES

    for _ in range(40):
        p_classic = generate_random_parameters(mode="classic_only")
        assert p_classic.artistic_mode == "none"


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

    # Worker-thread variant must return a QImage (QPixmap is GUI-thread only)
    image = render_result_to_image(result, stroke_color="#1e3a8a", target_size=200)
    assert isinstance(image, QImage)
    assert image.size().width() == 200


def test_gallery_model_favorites():
    """Test PresetGalleryModel favorite toggling and bulk selection."""
    dummy_pixmap = QPixmap(100, 100)
    dummy_pixmap.fill(Qt.GlobalColor.white)
    model = PresetGalleryModel()
    for i in range(3):
        model.append_item(GalleryItem(i, PlotParameters(artistic_mode="voronoi"), dummy_pixmap, f"Test {i}"))

    assert model.rowCount() == 3
    assert model.favorite_count() == 0

    changes = []
    model.dataChanged.connect(lambda tl, br, roles: changes.append((tl.row(), br.row())))

    idx = model.index(1)
    assert model.setData(idx, True, FAVORITE_ROLE)
    assert idx.data(FAVORITE_ROLE) is True
    assert model.favorite_count() == 1
    assert [it.suggested_name for it in model.favorite_items()] == ["Test 1"]
    assert changes == [(1, 1)]

    model.set_all_favorites(True)
    assert model.favorite_count() == 3
    assert changes[-1] == (0, 2)  # one signal for the whole range

    model.set_all_favorites(False)
    assert model.favorite_count() == 0

    model.clear()
    assert model.rowCount() == 0


def test_preset_lab_window_and_selection(qapp):
    """Test PresetLabWindow gallery selection helpers and fullscreen toggle."""
    win = PresetLabWindow()
    assert win.windowTitle() == "img2plot - Preset-Labor & Stil-Entdecker"

    # Count range up to 1000
    assert win.slider_count.minimum() == 1
    assert win.slider_count.maximum() == 1000
    assert win.spin_count.maximum() == 1000

    # Focus options
    focus_data_items = [win.combo_focus.itemData(i) for i in range(win.combo_focus.count())]
    assert "all" in focus_data_items
    assert "artistic_only" in focus_data_items
    assert "classic_only" in focus_data_items

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
    assert win.model.rowCount() == 2

    # Select all / Unselect all
    win.select_all_cards()
    assert win.model.favorite_count() == 2
    assert win.btn_save_favs.isEnabled()
    assert "2 von 2" in win.lbl_fav_counter.text()

    win.unselect_all_cards()
    assert win.model.favorite_count() == 0
    assert not win.btn_save_favs.isEnabled()

    # Filter toggles
    win.model.setData(win.model.index(0), True, FAVORITE_ROLE)
    win._filter_favs_clicked()
    assert win.proxy.rowCount() == 1
    assert win.proxy.index(0, 0).data(FAVORITE_ROLE) is True

    # Un-favoriting while filtered hides the card immediately
    win.model.setData(win.model.index(0), False, FAVORITE_ROLE)
    assert win.proxy.rowCount() == 0

    win._filter_all_clicked()
    assert win.proxy.rowCount() == 2

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


def test_preset_lab_dynamic_grid_and_card_scaling(qapp):
    """Test dynamic column layout, card size slider and delegate painting."""
    win = PresetLabWindow()
    win.resize(1600, 900)
    win.show()
    qapp.processEvents()

    dummy_pixmap = QPixmap(300, 300)
    dummy_pixmap.fill(Qt.GlobalColor.white)
    for i in range(6):
        win._on_item_ready(i, PlotParameters(artistic_mode="spiral"), dummy_pixmap)
    assert win.model.rowCount() == 6

    view = win.gallery_view
    assert win.slider_card_size.minimum() == 200
    assert win.slider_card_size.maximum() == 520

    win.slider_card_size.setValue(280)
    cols_small = view.columns
    win.slider_card_size.setValue(450)
    assert win.card_target_width == 450
    assert "450 px" in win.lbl_card_size_val.text()
    cols_large = view.columns
    assert 1 <= cols_large < cols_small

    # Cards fill the row without wrapping early: the last column sits in the first row
    win.slider_card_size.setValue(200)
    first = view.visualRect(win.proxy.index(0, 0))
    last_in_row = view.visualRect(win.proxy.index(min(view.columns, 6) - 1, 0))
    assert last_in_row.top() == first.top()
    assert last_in_row.right() <= view.viewport().width()
    card = view.card_delegate.card_size
    assert card.height() == PresetCardDelegate.card_height_for_width(card.width())

    # Painting a card must not raise
    img = QImage(card.width(), card.height(), QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(img)
    opt = QStyleOptionViewItem()
    opt.rect = QRect(0, 0, card.width(), card.height())
    opt.font = view.font()
    view.card_delegate.paint(painter, opt, win.proxy.index(0, 0))
    painter.end()

    win.close()


def test_preset_lab_click_favorite_on_card(qapp):
    """Clicking the 'Merken' area of a painted card toggles the favorite."""
    win = PresetLabWindow()
    win.resize(1280, 840)
    win.show()
    qapp.processEvents()

    dummy_pixmap = QPixmap(100, 100)
    dummy_pixmap.fill(Qt.GlobalColor.white)
    win._on_item_ready(0, PlotParameters(artistic_mode="spiral"), dummy_pixmap)
    qapp.processEvents()

    view = win.gallery_view
    idx = win.proxy.index(0, 0)
    fav_rect = PresetCardDelegate.card_rects(view.visualRect(idx)).fav
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=fav_rect.center())
    assert win.model.favorite_count() == 1
    assert win.btn_save_favs.isEnabled()

    win.close()


def test_preset_lab_gallery_scales_to_1000_variants(qapp):
    """Regression: 1000 variants must not create per-card widgets and must stay reachable."""
    win = PresetLabWindow()
    win.resize(1280, 840)
    win.show()
    qapp.processEvents()

    widgets_before = len(win.findChildren(QWidget))

    image = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)  # small: keeps the test light
    image.fill(Qt.GlobalColor.white)
    for i in range(1000):
        win._on_item_ready(i, PlotParameters(artistic_mode="spiral"), image)
    win._on_worker_finished()
    qapp.processEvents()

    assert win.model.rowCount() == 1000
    assert "1000 Varianten" in win.lbl_status.text()
    assert len(win.findChildren(QWidget)) == widgets_before

    view = win.gallery_view
    view.scrollToBottom()
    qapp.processEvents()
    last_rect = view.visualRect(win.proxy.index(999, 0))
    assert last_rect.isValid()
    assert view.viewport().rect().intersects(last_rect)

    win.close()
