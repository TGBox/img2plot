"""
Unit and integration tests for preset navigation, zoom stability,
PresetLab favorite inspection/collision-handling, and multi-preset batch export.
"""

import os
import tempfile
import pytest
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication

from img2plot.core.parameters import PlotParameters
from img2plot.core.presets import (
    DEFAULT_PRESETS,
    get_all_presets,
    get_unique_preset_name,
)
from img2plot.gui.sidebar import SidebarWidget
from img2plot.gui.preview_widget import PreviewWidget
from img2plot.gui.preset_lab import PresetSaveDialog
from img2plot.gui.batch_export_dialog import (
    BatchExportDialog,
    BatchExportWorker,
    BatchExportTask,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_image_file():
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img = Image.fromarray(np.full((120, 120, 3), 180, dtype=np.uint8))
    img.save(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_unique_preset_naming():
    """Verify sequential numbering prevents duplicate preset names."""
    known = {"Standard", "Mein Preset", "Mein Preset 1"}
    # New unique name
    res1 = get_unique_preset_name("Neues Preset", existing_names=known)
    assert res1 == "Neues Preset"

    # Collision triggers numbering
    res2 = get_unique_preset_name("Standard", existing_names=known)
    assert res2 == "Standard 1"

    # Multiple collisions increment counter
    res3 = get_unique_preset_name("Mein Preset", existing_names=known)
    assert res3 == "Mein Preset 2"


def test_sidebar_preset_prev_next_cycling(qapp):
    """Verify prev/next buttons cycle through presets in sidebar."""
    sidebar = SidebarWidget()
    assert hasattr(sidebar, "btn_preset_prev")
    assert hasattr(sidebar, "btn_preset_next")

    count = sidebar.combo_presets.count()
    assert count > 1

    sidebar.combo_presets.setCurrentIndex(0)
    initial_text = sidebar.combo_presets.currentText()

    # Next button moves forward
    sidebar.btn_preset_next.click()
    assert sidebar.combo_presets.currentIndex() == 1
    assert sidebar.combo_presets.currentText() != initial_text

    # Prev button moves back to 0
    sidebar.btn_preset_prev.click()
    assert sidebar.combo_presets.currentIndex() == 0
    assert sidebar.combo_presets.currentText() == initial_text

    # Prev wraps to the end
    sidebar.btn_preset_prev.click()
    assert sidebar.combo_presets.currentIndex() == count - 1


def test_sidebar_preset_selection_preserves_preview_resolution(qapp):
    """Verify switching presets maintains the user's preview resolution setting."""
    sidebar = SidebarWidget()
    # User customizes preview resolution
    sidebar.slider_preview_res.set_value(1200)
    assert sidebar.slider_preview_res.get_value() == 1200

    # Switch preset
    sidebar._select_next_preset()
    # Preview resolution should remain 1200, not reset to default 800
    assert sidebar.slider_preview_res.get_value() == 1200


def test_preview_widget_keep_zoom_relative_stabilization(qapp):
    """Verify PreviewWidget keeps zoom and centers properly across result updates."""
    from img2plot.core.engine import EngineResult, PlotStats
    from img2plot.gui.worker import PreviewRenderData

    preview = PreviewWidget()
    preview.chk_keep_zoom.setChecked(True)

    dummy_arr = np.zeros((600, 800), dtype=np.float32)

    # Initial dummy result
    res1 = EngineResult(
        paths=[],
        width=800,
        height=600,
        preprocessed_gray=dummy_arr,
        sobel_magnitude=dummy_arr,
        stats=PlotStats(),
    )
    data1 = PreviewRenderData(
        result=res1,
        cached_vector_path=None,
        cached_hatch_path=None,
        pixmap_preprocess_img=None,
        pixmap_sobel_img=None,
        cached_rendered_img=None,
    )
    preview.set_preview_data(data1, force_fit=True)
    initial_zoom = preview.canvas.zoom
    assert initial_zoom > 0

    # User manually zooms in
    preview.canvas.zoom = 2.0
    preview.canvas.pan_offset = QPointF(50.0, 50.0)

    # Now update with a second result of same dimensions (standard preset switch)
    res2 = EngineResult(
        paths=[],
        width=800,
        height=600,
        preprocessed_gray=dummy_arr,
        sobel_magnitude=dummy_arr,
        stats=PlotStats(),
    )
    data2 = PreviewRenderData(
        result=res2,
        cached_vector_path=None,
        cached_hatch_path=None,
        pixmap_preprocess_img=None,
        pixmap_sobel_img=None,
        cached_rendered_img=None,
    )
    preview.set_preview_data(data2, force_fit=False)
    # Zoom should remain 2.0 exactly
    assert preview.canvas.zoom == 2.0
    assert preview.canvas.pan_offset == QPointF(50.0, 50.0)


def test_preset_save_dialog_thumbnails_and_naming(qapp):
    """Verify PresetSaveDialog has enlarged rows, unique naming, and zoom trigger."""
    # Create dummy favorites
    qimg = QImage(120, 120, QImage.Format.Format_RGB32)
    qimg.fill(Qt.GlobalColor.white)
    pix = QPixmap.fromImage(qimg)

    favorites = [
        {
            "index": 0,
            "params": PlotParameters(artistic_mode="waveform"),
            "pixmap": pix,
            "suggested_name": "Wellenform Variante",
        },
        {
            "index": 1,
            "params": PlotParameters(artistic_mode="waveform"),
            "pixmap": pix,
            "suggested_name": "Wellenform Variante",
        },
    ]

    dlg = PresetSaveDialog(favorites)
    assert dlg.table.rowCount() == 2
    # Verify row height is enlarged (>100px)
    assert dlg.table.rowHeight(0) >= 120

    # Names should be automatically unique (Variant 1 != Variant 2)
    name0 = dlg.edit_fields[0].text()
    name1 = dlg.edit_fields[1].text()
    assert name0 != name1
    assert "Wellenform" in name0
    assert "Wellenform" in name1


def test_batch_export_dialog_and_worker(qapp, sample_image_file):
    """Verify BatchExportDialog can be initialized and BatchExportWorker exports SVG and PNG."""
    with tempfile.TemporaryDirectory() as out_dir:
        tasks = [
            BatchExportTask("Standard", DEFAULT_PRESETS["Standard"]),
            BatchExportTask("Feine Details", DEFAULT_PRESETS["Feine Details"]),
        ]

        worker = BatchExportWorker(
            image_path=sample_image_file,
            tasks=tasks,
            output_dir=out_dir,
            export_svg_flag=True,
            export_png_flag=True,
            full_resolution=False,
        )

        # Run synchronously for test verification
        worker.run()

        files = os.listdir(out_dir)
        # 2 presets * 2 formats (svg + png) = 4 files
        assert len(files) == 4
        svg_files = [f for f in files if f.endswith(".svg")]
        png_files = [f for f in files if f.endswith(".png")]
        assert len(svg_files) == 2
        assert len(png_files) == 2

        # Verify dialog initializes properly
        dlg = BatchExportDialog(image_path=sample_image_file)
        assert dlg.list_presets.count() > 0
        assert dlg.chk_svg.isChecked()
