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


def test_clickable_slider_and_slider_row_hit_area(qapp):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent
    from img2plot.gui.sidebar import ClickableSlider, SliderRow

    slider = ClickableSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(10)
    slider.resize(200, 34)

    # Click on the right side of the slider
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(160, 17),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    slider.mousePressEvent(press_ev)
    assert slider.value() > 60
    assert slider.isSliderDown() is True

    # Drag to the left side
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(40, 17),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    slider.mouseMoveEvent(move_ev)
    assert slider.value() < 30

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(40, 17),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    slider.mouseReleaseEvent(release_ev)
    assert slider.isSliderDown() is False

    # Test SliderRow click forwarding (clicking above/below track)
    row = SliderRow("Test Regler", min_val=0, max_val=100, default_val=10)
    row.resize(250, 60)
    row.show()

    # Click at y=2 (above the slider groove in the row header)
    row_click_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(190, 2),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    row.mousePressEvent(row_click_ev)
    assert row.get_value() > 60


def test_zoom_retention_toggle(qapp):
    from img2plot.gui.preview_widget import PreviewWidget
    from img2plot.core.engine import EngineResult, PlotStats, StrokePath
    import numpy as np

    preview = PreviewWidget()
    preview.resize(800, 600)
    preview.show()
    stroke = StrokePath(points=[(0.0, 0.0), (100.0, 100.0)])
    gray = np.full((200, 200), 0.5, dtype=np.float32)
    mag = np.full((200, 200), 0.2, dtype=np.float32)
    res1 = EngineResult(
        paths=[stroke],
        width=200,
        height=200,
        preprocessed_gray=gray,
        sobel_magnitude=mag,
        stats=PlotStats(total_strokes=1),
    )
    res2 = EngineResult(
        paths=[stroke],
        width=200,
        height=200,
        preprocessed_gray=gray,
        sobel_magnitude=mag,
        stats=PlotStats(total_strokes=1),
    )

    # First load: initial fit
    preview.set_result(res1)
    # Manually set a custom zoom and pan
    preview.canvas.zoom = 3.5
    preview.canvas.pan_offset.setX(123.0)
    preview.canvas.pan_offset.setY(456.0)

    # 1. With chk_keep_zoom checked: zoom and pan are preserved across updates
    preview.chk_keep_zoom.setChecked(True)
    preview.set_result(res2)
    assert preview.canvas.zoom == 3.5
    assert preview.canvas.pan_offset.x() == 123.0
    assert preview.canvas.pan_offset.y() == 456.0

    # 2. With force_fit=True: resets to fit view even if chk_keep_zoom is True
    preview.set_result(res2, force_fit=True)
    assert preview.canvas.zoom != 3.5

    # 3. With chk_keep_zoom unchecked: resets to fit view on every update
    preview.canvas.zoom = 2.8
    preview.chk_keep_zoom.setChecked(False)
    preview.set_result(res2)
    assert preview.canvas.zoom != 2.8


def test_default_sort_paths_is_false(qapp):
    from img2plot.core.parameters import PlotParameters
    from img2plot.core.presets import DEFAULT_PRESETS
    from img2plot.gui.sidebar import SidebarWidget

    # Default PlotParameters
    p = PlotParameters()
    assert p.sort_paths is False

    # Default presets
    for name, preset_params in DEFAULT_PRESETS.items():
        assert preset_params.sort_paths is False, f"Preset {name} has sort_paths=True"

    # Sidebar checkbox
    sidebar = SidebarWidget()
    assert sidebar.chk_tsp.isChecked() is False


def test_worker_async_preview_generation(qapp):
    import numpy as np
    from img2plot.core.parameters import PlotParameters
    from img2plot.gui.worker import VectorizationWorker, WorkerTask, PreviewRenderData

    img_data = np.full((120, 120, 3), 180, dtype=np.uint8)
    img_data[30:90, 30:90] = 20  # dark square in center to trigger lines and hatching

    params = PlotParameters(min_line_length=10, use_hatching=True, sort_paths=False)
    worker = VectorizationWorker()
    task = WorkerTask(
        params=params,
        image_input=img_data,
        req_id=42,
        is_preview=True,
        paper_style="dark",
        display_mode="vector",
        overlay_opacity=0.7,
    )

    received_data = []

    def on_finished(data, req_id):
        received_data.append((data, req_id))

    worker.sig_finished.connect(on_finished)
    worker.run_once(task)

    assert len(received_data) == 1
    data, req_id = received_data[0]
    assert req_id == 42
    assert isinstance(data, PreviewRenderData)
    assert data.result is not None
    assert data.cached_rendered_img is not None
    assert not data.cached_rendered_img.isNull()
    assert not data.cached_vector_path.isEmpty() or not data.cached_hatch_path.isEmpty()


def test_preview_widget_blit_rendering(qapp):
    from img2plot.gui.preview_widget import PreviewWidget
    from img2plot.core.engine import EngineResult, StrokePath, PlotStats
    import numpy as np

    widget = PreviewWidget()
    gray = np.zeros((100, 100), dtype=np.float32)
    mag = np.zeros((100, 100), dtype=np.float32)
    stroke = StrokePath(points=[(10.0, 10.0), (90.0, 90.0)])
    result = EngineResult(
        paths=[stroke],
        width=100,
        height=100,
        preprocessed_gray=gray,
        sobel_magnitude=mag,
        stats=PlotStats(total_strokes=1),
    )

    widget.set_result(result)
    assert widget.canvas.cached_rendered_pixmap is not None
    assert not widget.canvas.cached_rendered_pixmap.isNull()

    # Trigger a paintEvent to ensure blit renders without errors
    widget.canvas.repaint()



