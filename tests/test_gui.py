"""
Tests for img2plot GUI components, sidebar synchronization, preview widget, and fullscreen/windowed toggling.
"""

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_sidebar_parameter_sync(qapp):
    from img2plot.gui.sidebar import SidebarWidget
    from img2plot.core.parameters import PlotParameters

    sidebar = SidebarWidget()
    p = PlotParameters(
        min_line_length=37,
        line_mode="bezier",
        bezier_smoothness=0.52,
        use_hatching=True,
        hatch_mode="bezier",
        hatch_curve_strength=0.75,
        hatch_wobble=0.3,
        hatching_threshold=0.42,
    )
    sidebar.apply_parameters(p)

    read_p = sidebar.get_current_parameters()
    assert read_p.min_line_length == 37
    assert read_p.line_mode == "bezier"
    assert abs(read_p.bezier_smoothness - 0.52) < 0.05
    assert read_p.use_hatching is True
    assert read_p.hatch_mode == "bezier"
    assert abs(read_p.hatch_curve_strength - 0.75) < 0.05
    assert abs(read_p.hatch_wobble - 0.3) < 0.05
    assert abs(read_p.hatching_threshold - 0.42) < 0.05


def test_main_window_fullscreen_toggle(qapp):
    from img2plot.gui.main_window import MainWindow

    window = MainWindow()
    assert window.is_fullscreen is False

    # Toggle to fullscreen
    window.toggle_fullscreen()
    assert window.is_fullscreen is True
    assert window.act_fullscreen.isChecked() is True

    # Toggle back to windowed mode
    window.toggle_fullscreen()
    assert window.is_fullscreen is False
    assert window.act_fullscreen.isChecked() is False

    window.close()


def test_preview_widget_modes(qapp):
    from img2plot.gui.preview_widget import PreviewWidget
    from img2plot.core.engine import EngineResult, PlotStats, StrokePath
    import numpy as np

    preview = PreviewWidget()

    # Create dummy EngineResult
    gray = np.full((100, 100), 0.5, dtype=np.float32)
    mag = np.full((100, 100), 0.2, dtype=np.float32)
    stroke = StrokePath(points=[(10.0, 10.0), (80.0, 80.0)], is_bezier=False)
    stats = PlotStats(total_strokes=1, contour_strokes=1, total_length_px=98.9)
    result = EngineResult(
        paths=[stroke],
        width=100,
        height=100,
        preprocessed_gray=gray,
        sobel_magnitude=mag,
        stats=stats,
    )

    preview.set_result(result)
    assert preview.canvas.result is not None

    # Test mode change
    preview.combo_mode.setCurrentIndex(1)  # Preprocessing
    assert preview.canvas.display_mode == "preprocess"
    assert preview.label_opacity.isHidden() is True

    preview.combo_mode.setCurrentIndex(3)  # Overlay
    assert preview.canvas.display_mode == "overlay"
    assert preview.label_opacity.isHidden() is False

    preview.slider_opacity.setValue(50)
    assert preview.canvas.overlay_opacity == 0.5

    # Test paper styles
    preview.combo_paper.setCurrentIndex(1)  # Paper / Cream
    assert preview.canvas.paper_style == "paper"

    preview.combo_paper.setCurrentIndex(2)  # Dark
    assert preview.canvas.paper_style == "dark"

    # Test zoom fit and 100%
    preview.btn_100.click()
    assert preview.canvas.zoom == 1.0

    preview.btn_fit.click()
    assert preview.canvas.zoom > 0
