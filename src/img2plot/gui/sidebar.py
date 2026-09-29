"""
Sidebar widget containing all parameter controls, file explorers, presets, and statistics.
Includes ClickableSlider for generous mouse hit areas and full custom preset management.
"""

from __future__ import annotations
import os
from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QSlider,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QFileDialog,
    QColorDialog,
    QMessageBox,
    QInputDialog,
    QStyle,
    QStyleOptionSlider,
)

from ..core.parameters import PlotParameters
from ..core.presets import (
    DEFAULT_PRESETS,
    get_all_presets,
    list_user_presets,
    save_user_preset,
    delete_user_preset,
    load_preset_file,
    save_preset_file,
)
from ..core.engine import PlotStats


class ClickableSlider(QSlider):
    """
    QSlider with direct click-to-value snapping across the entire widget height,
    eliminating accidental misses when clicking slightly above or below the groove.
    """

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            val = self._pixel_to_val(event.position().x())
            self.setValue(val)
            self.setSliderDown(True)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            val = self._pixel_to_val(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _pixel_to_val(self, x: float) -> int:
        handle_w = 24
        slider_len = max(1.0, float(self.width() - handle_w))
        pos = max(0.0, min(slider_len, x - handle_w / 2.0))
        fraction = pos / slider_len
        if self.invertedAppearance():
            fraction = 1.0 - fraction
        return int(round(self.minimum() + fraction * (self.maximum() - self.minimum())))


class SliderRow(QWidget):
    """Reusable widget combining a label, an accessible slider, and a formatted numeric value readout."""

    sig_value_changed = Signal(float)

    def __init__(
        self,
        title: str,
        min_val: float,
        max_val: float,
        default_val: float,
        step: float = 1.0,
        decimals: int = 0,
        suffix: str = "",
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.decimals = decimals
        self.suffix = suffix

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # Header with title and current value
        h_layout = QHBoxLayout()
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #d4d4d8; font-weight: 500;")
        self.lbl_val = QLabel()
        self.lbl_val.setStyleSheet("color: #38bdf8; font-weight: bold; min-width: 50px;")
        self.lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        h_layout.addWidget(self.lbl_title)
        h_layout.addWidget(self.lbl_val)
        layout.addLayout(h_layout)

        # Large Clickable Slider
        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider_steps = int(round((max_val - min_val) / step))
        self.slider.setRange(0, self.slider_steps)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        if tooltip:
            self.setToolTip(tooltip)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_value(default_val)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            slider_x = self.slider.mapFrom(self, event.position().toPoint()).x()
            val = self.slider._pixel_to_val(slider_x)
            self.slider.setValue(val)
            self.slider.setSliderDown(True)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            slider_x = self.slider.mapFrom(self, event.position().toPoint()).x()
            val = self.slider._pixel_to_val(slider_x)
            self.slider.setValue(val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.slider.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _on_slider_changed(self, step_idx: int) -> None:
        val = self.min_val + step_idx * self.step
        self._update_label(val)
        self.sig_value_changed.emit(val)

    def _update_label(self, val: float) -> None:
        if self.decimals == 0:
            formatted = f"{int(round(val))}"
        else:
            formatted = f"{val:.{self.decimals}f}"
        if self.suffix:
            formatted += f" {self.suffix}"
        self.lbl_val.setText(formatted)

    def get_value(self) -> float:
        step_idx = self.slider.value()
        return self.min_val + step_idx * self.step

    def set_value(self, val: float) -> None:
        val = max(self.min_val, min(self.max_val, val))
        step_idx = int(round((val - self.min_val) / self.step))
        self.slider.blockSignals(True)
        self.slider.setValue(step_idx)
        self.slider.blockSignals(False)
        self._update_label(val)


class SidebarWidget(QWidget):
    """Sidebar containing all input sliders, buttons, file explorers, presets, and stats."""

    sig_parameters_changed = Signal()
    sig_recalculate_requested = Signal()
    sig_cancel_requested = Signal()
    sig_export_svg_requested = Signal()
    sig_export_png_requested = Signal()
    sig_input_file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.setMaximumWidth(450)

        # Internal current parameters
        self.params = PlotParameters()
        self._block_signals = False

        # Main scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.layout_content = QVBoxLayout(content)
        self.layout_content.setContentsMargins(10, 10, 10, 10)
        self.layout_content.setSpacing(12)

        self._build_file_section()
        self._build_preset_section()
        self._build_preview_control_section()
        self._build_preprocessing_section()
        self._build_line_detection_section()
        self._build_style_section()
        self._build_hatching_section()
        self._build_shapes_section()
        self._build_page_export_section()
        self._build_stats_section()

        self.layout_content.addStretch()
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)

        self._refresh_presets_dropdown()

    # -------------------------------------------------------------------------
    # UI Sections
    # -------------------------------------------------------------------------

    def _build_file_section(self) -> None:
        box = QGroupBox("Dateien & Pfade")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        # Input image
        layout.addWidget(QLabel("Eingabebild:"))
        h_in = QHBoxLayout()
        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Pfad zu PNG, JPG, BMP...")
        self.edit_input.textChanged.connect(self._on_input_text_changed)
        self.btn_browse_in = QPushButton("Durchsuchen...")
        self.btn_browse_in.clicked.connect(self._browse_input_file)
        h_in.addWidget(self.edit_input)
        h_in.addWidget(self.btn_browse_in)
        layout.addLayout(h_in)

        # Output file
        layout.addWidget(QLabel("Ausgabedatei:"))
        h_out = QHBoxLayout()
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Pfad für SVG / PNG...")
        self.btn_browse_out = QPushButton("Speichern unter...")
        self.btn_browse_out.clicked.connect(self._browse_output_file)
        h_out.addWidget(self.edit_output)
        h_out.addWidget(self.btn_browse_out)
        layout.addLayout(h_out)

        # Quick Export Buttons
        h_btn = QHBoxLayout()
        self.btn_export_svg = QPushButton("SVG Exportieren")
        self.btn_export_svg.setObjectName("primaryButton")
        self.btn_export_svg.clicked.connect(self.sig_export_svg_requested.emit)
        self.btn_export_png = QPushButton("PNG Exportieren")
        self.btn_export_png.clicked.connect(self.sig_export_png_requested.emit)
        h_btn.addWidget(self.btn_export_svg)
        h_btn.addWidget(self.btn_export_png)
        layout.addLayout(h_btn)

        self.layout_content.addWidget(box)

    def _build_preset_section(self) -> None:
        box = QGroupBox("Voreinstellungen (Presets)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Gespeicherte Profile:"))
        self.combo_presets = QComboBox()
        self.combo_presets.currentTextChanged.connect(self._on_preset_selected)
        layout.addWidget(self.combo_presets)

        h_btn = QHBoxLayout()
        self.btn_save_user_preset = QPushButton("Preset speichern...")
        self.btn_save_user_preset.setToolTip("Aktuelle Reglerwerte als eigenes Preset speichern.")
        self.btn_save_user_preset.clicked.connect(self._save_user_preset_dialog)

        self.btn_delete_preset = QPushButton("Löschen")
        self.btn_delete_preset.setToolTip("Aktuell ausgewähltes eigenes Preset löschen.")
        self.btn_delete_preset.clicked.connect(self._delete_current_preset)

        self.btn_reset_preset = QPushButton("Zurücksetzen")
        self.btn_reset_preset.setToolTip("Alle Regler auf den Standard zurücksetzen.")
        self.btn_reset_preset.clicked.connect(self._reset_to_default)

        h_btn.addWidget(self.btn_save_user_preset)
        h_btn.addWidget(self.btn_delete_preset)
        h_btn.addWidget(self.btn_reset_preset)
        layout.addLayout(h_btn)

        # Secondary row: file import/export
        h_files = QHBoxLayout()
        self.btn_import_json = QPushButton("JSON importieren...")
        self.btn_import_json.clicked.connect(self._load_preset_dialog)
        self.btn_export_json = QPushButton("JSON exportieren...")
        self.btn_export_json.clicked.connect(self._save_preset_dialog)
        h_files.addWidget(self.btn_import_json)
        h_files.addWidget(self.btn_export_json)
        layout.addLayout(h_files)

        self.layout_content.addWidget(box)

    def _build_preview_control_section(self) -> None:
        box = QGroupBox("Live-Vorschau & Berechnung")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        self.chk_auto_preview = QCheckBox("Automatische Live-Vorschau (Debounced)")
        self.chk_auto_preview.setChecked(True)
        layout.addWidget(self.chk_auto_preview)

        self.slider_preview_res = SliderRow(
            title="Vorschau-Auflösung (max px):",
            min_val=400,
            max_val=1600,
            default_val=800,
            step=50,
            suffix="px",
            tooltip="Begrenzt die Bilddimension bei der interaktiven Live-Vorschau für flüssiges Arbeiten.",
        )
        self.slider_preview_res.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_preview_res)

        h_calc = QHBoxLayout()
        self.btn_calc = QPushButton("Vorschau neu berechnen")
        self.btn_calc.setObjectName("primaryButton")
        self.btn_calc.clicked.connect(self.sig_recalculate_requested.emit)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.sig_cancel_requested.emit)
        h_calc.addWidget(self.btn_calc)
        h_calc.addWidget(self.btn_cancel)
        layout.addLayout(h_calc)

        # Progress bar & label
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_status = QLabel("Bereit")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_status)

        # Randomize button (prominent near calculation controls)
        self.btn_randomize_top = QPushButton("🎲  Alle Einstellungen zufällig würfeln")
        self.btn_randomize_top.setObjectName("randomizeButton")
        self.btn_randomize_top.setToolTip(
            "Würfelt ALLE Einstellungen (Filter, Linienerkennung, Zeichenstil, Schraffur, Formen und Strich) zufällig mit sinnvollen Werten."
        )
        self.btn_randomize_top.clicked.connect(self._randomize_all_params)
        layout.addWidget(self.btn_randomize_top)

        self.layout_content.addWidget(box)

    def _build_preprocessing_section(self) -> None:
        box = QGroupBox("Vorverarbeitung (Filter)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.chk_clahe = QCheckBox("CLAHE Kontrast-Angleichung")
        self.chk_clahe.setChecked(True)
        self.chk_clahe.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_clahe)

        self.slider_clahe_kernel = SliderRow(
            title="CLAHE Kachelgröße:",
            min_val=8,
            max_val=64,
            default_val=32,
            step=2,
            suffix="px",
            tooltip="Größe der lokalen Kontrastkacheln.",
        )
        self.slider_clahe_kernel.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_clahe_kernel)

        self.chk_blur = QCheckBox("Gaußscher Weichzeichner")
        self.chk_blur.setChecked(True)
        self.chk_blur.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_blur)

        self.slider_blur_sigma = SliderRow(
            title="Weichzeichnung (Sigma):",
            min_val=0.2,
            max_val=4.0,
            default_val=1.0,
            step=0.1,
            decimals=1,
            tooltip="Entfernt Rauschen und hochfrequente Texturen.",
        )
        self.slider_blur_sigma.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_blur_sigma)

        self.layout_content.addWidget(box)

    def _build_line_detection_section(self) -> None:
        box = QGroupBox("Linienerkennung & Dichte")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.slider_term_ratio = SliderRow(
            title="Abbruch-Schwelle (Termination):",
            min_val=0.08,
            max_val=0.60,
            default_val=0.28,
            step=0.01,
            decimals=2,
            tooltip="Kleinerer Wert erzeugt mehr Linien in schwächeren Kanten.",
        )
        self.slider_term_ratio.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_term_ratio)

        self.slider_continue_thresh = SliderRow(
            title="Fortführ-Schwelle:",
            min_val=0.002,
            max_val=0.05,
            default_val=0.01,
            step=0.002,
            decimals=3,
            tooltip="Kleinerer Wert lässt Linien weiter über schwache Kanten laufen.",
        )
        self.slider_continue_thresh.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_continue_thresh)

        self.slider_min_length = SliderRow(
            title="Minimale Linienlänge:",
            min_val=6,
            max_val=70,
            default_val=21,
            step=1,
            suffix="px",
            tooltip="Kürzere Linien werden verworfen.",
        )
        self.slider_min_length.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_min_length)

        self.slider_max_angle = SliderRow(
            title="Max. Biegungswinkel:",
            min_val=5.0,
            max_val=60.0,
            default_val=20.0,
            step=1.0,
            suffix="°",
            tooltip="Maximaler Richtungswinkel vor Linienabbruch.",
        )
        self.slider_max_angle.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_max_angle)

        self.slider_lpf = SliderRow(
            title="Filter-Trägheit (LPF Attack):",
            min_val=0.01,
            max_val=0.20,
            default_val=0.05,
            step=0.01,
            decimals=2,
            tooltip="Wie schnell Linien Kurven und Ecken folgen können.",
        )
        self.slider_lpf.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_lpf)

        self.layout_content.addWidget(box)

    def _build_style_section(self) -> None:
        box = QGroupBox("Zeichenstil & Bézier-Kurven")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Linienstil:"))
        self.combo_line_mode = QComboBox()
        self.combo_line_mode.addItems(["Gerade Striche (Klassisch)", "Glatte Bézier-Kurven (Organisch)"])
        self.combo_line_mode.currentIndexChanged.connect(self._on_style_mode_changed)
        layout.addWidget(self.combo_line_mode)

        self.slider_bezier_smooth = SliderRow(
            title="Bézier-Glättungsgrad:",
            min_val=0.10,
            max_val=0.75,
            default_val=0.35,
            step=0.05,
            decimals=2,
            tooltip="Stärke der Kurvenbiegung entlang der Kanten.",
        )
        self.slider_bezier_smooth.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_bezier_smooth)

        self.slider_sample_step = SliderRow(
            title="Kurven-Abtastrate:",
            min_val=1,
            max_val=5,
            default_val=2,
            step=1,
            tooltip="Schrittweite für Kontrollpunkte.",
        )
        self.slider_sample_step.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_sample_step)

        self.layout_content.addWidget(box)

    def _build_hatching_section(self) -> None:
        box = QGroupBox("Schraffur (Hatching) für Schatten")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.chk_hatching = QCheckBox("Schraffur für dunkle Flächen aktivieren")
        self.chk_hatching.setChecked(False)
        self.chk_hatching.stateChanged.connect(self._on_hatching_toggled)
        layout.addWidget(self.chk_hatching)

        layout.addWidget(QLabel("Schraffurstil:"))
        self.combo_hatch_mode = QComboBox()
        self.combo_hatch_mode.addItems([
            "Glatte Bézier-Kurven (Formfolgend)",
            "Gerade Striche (Klassisch)",
        ])
        self.combo_hatch_mode.currentIndexChanged.connect(self._emit_param_change)
        layout.addWidget(self.combo_hatch_mode)

        self.slider_hatch_curve = SliderRow(
            title="Form-Anpassung / Krümmung:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.65,
            step=0.05,
            decimals=2,
            tooltip="Wie stark sich die Schraffurkurven an die darunterliegenden Kanten und Formverläufe anpassen (0 = gerade, 1 = vollständig formfolgend).",
        )
        self.slider_hatch_curve.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_curve)

        self.slider_hatch_wobble = SliderRow(
            title="Organische Wellung (Wobble):",
            min_val=0.0,
            max_val=2.0,
            default_val=0.0,
            step=0.1,
            decimals=1,
            suffix="px",
            tooltip="Fügt eine subtile, handgezeichnete Vibration hinzu.",
        )
        self.slider_hatch_wobble.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_wobble)

        self.slider_hatch_thresh = SliderRow(
            title="Dunkelheits-Schwelle:",
            min_val=0.10,
            max_val=0.60,
            default_val=0.35,
            step=0.02,
            decimals=2,
            tooltip="Bereiche dunkler als dieser Wert werden schraffiert.",
        )
        self.slider_hatch_thresh.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_thresh)

        self.slider_hatch_spacing = SliderRow(
            title="Linienabstand (Dichte):",
            min_val=4,
            max_val=30,
            default_val=10,
            step=1,
            suffix="px",
            tooltip="Abstand paralleler Schraffurlinien.",
        )
        self.slider_hatch_spacing.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_spacing)

        self.slider_hatch_angle = SliderRow(
            title="Schraffur-Winkel:",
            min_val=0.0,
            max_val=180.0,
            default_val=45.0,
            step=5.0,
            suffix="°",
            tooltip="Grundrichtung der Schraffurlinien.",
        )
        self.slider_hatch_angle.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_angle)

        self.chk_cross_hatch = QCheckBox("Kreuzschraffur für tiefe Schatten")
        self.chk_cross_hatch.setChecked(False)
        self.chk_cross_hatch.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_cross_hatch)

        self.layout_content.addWidget(box)

    # Mapping lists for shape type and rotation mode combo boxes
    _SHAPE_TYPE_VALUES = [
        "dots", "circles", "rects", "triangles", "lines",
        "stars", "diamonds", "hexagons", "spirals", "hearts", "ascii",
    ]
    _ROTATION_MODE_VALUES = ["none", "random", "gradient", "mixed"]

    def _build_shapes_section(self) -> None:
        """Build the Shapes mode control section."""
        box = QGroupBox("\u2728 Formen-Modus (Shapes)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Enable toggle
        self.chk_shapes = QCheckBox("Formen-Modus aktivieren")
        self.chk_shapes.setChecked(False)
        self.chk_shapes.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_shapes)

        # Shape type
        layout.addWidget(QLabel("Formtyp:"))
        self.combo_shape_type = QComboBox()
        self.combo_shape_type.addItems([
            "Punkte (Dots)", "Kreise (Kontur)", "Rechtecke",
            "Dreiecke", "Linien-Segmente", "Sterne", "Rauten",
            "Hexagons", "Spiralen", "Herzen", "ASCII-Zeichen",
        ])
        self.combo_shape_type.currentIndexChanged.connect(self._on_shape_type_changed)
        layout.addWidget(self.combo_shape_type)

        # ASCII charset (only visible for ASCII mode)
        self.lbl_ascii_charset = QLabel("Zeichensatz (dunkel \u2192 hell):")
        self.edit_ascii_charset = QLineEdit("@#S%?*+;:,. ")
        self.edit_ascii_charset.textChanged.connect(self._emit_param_change)
        layout.addWidget(self.lbl_ascii_charset)
        layout.addWidget(self.edit_ascii_charset)
        self.lbl_ascii_charset.setVisible(False)
        self.edit_ascii_charset.setVisible(False)

        # Placement
        layout.addWidget(QLabel("Platzierung:"))
        self.combo_shape_placement = QComboBox()
        self.combo_shape_placement.addItems(["Raster (Grid)", "Zuf\u00e4llig (Random)"])
        self.combo_shape_placement.currentIndexChanged.connect(self._emit_param_change)
        layout.addWidget(self.combo_shape_placement)

        # Size sliders
        self.slider_shape_min_size = SliderRow(
            title="Min. Gr\u00f6\u00dfe (helle Bereiche):",
            min_val=1.0,
            max_val=30.0,
            default_val=2.0,
            step=0.5,
            decimals=1,
            suffix="px",
            tooltip="Minimale Formgr\u00f6\u00dfe in hellen Bildbereichen.",
        )
        self.slider_shape_min_size.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_shape_min_size)

        self.slider_shape_max_size = SliderRow(
            title="Max. Gr\u00f6\u00dfe (dunkle Bereiche):",
            min_val=2.0,
            max_val=60.0,
            default_val=20.0,
            step=1.0,
            decimals=0,
            suffix="px",
            tooltip="Maximale Formgr\u00f6\u00dfe in dunklen Bildbereichen.",
        )
        self.slider_shape_max_size.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_shape_max_size)

        # Density
        self.slider_shape_density = SliderRow(
            title="Dichte:",
            min_val=0.1,
            max_val=2.0,
            default_val=0.6,
            step=0.05,
            decimals=2,
            tooltip="Anzahl der Formen pro Fl\u00e4che. H\u00f6herer Wert = dichter.",
        )
        self.slider_shape_density.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_shape_density)

        # Brightness-driven size and density
        self.chk_shape_size_by_bright = QCheckBox("Gr\u00f6\u00dfe nach Helligkeit (dunkel = gro\u00df)")
        self.chk_shape_size_by_bright.setChecked(True)
        self.chk_shape_size_by_bright.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_shape_size_by_bright)

        self.chk_shape_density_by_bright = QCheckBox("Dichte nach Helligkeit (dunkel = mehr)")
        self.chk_shape_density_by_bright.setChecked(True)
        self.chk_shape_density_by_bright.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_shape_density_by_bright)

        # Rotation mode
        layout.addWidget(QLabel("Rotationsmodus:"))
        self.combo_shape_rotation = QComboBox()
        self.combo_shape_rotation.addItems([
            "Keine Rotation", "Zuf\u00e4llig", "Gradientenausgerichtet", "Gemischt",
        ])
        self.combo_shape_rotation.setCurrentIndex(1)  # default: random
        self.combo_shape_rotation.currentIndexChanged.connect(self._on_shape_rotation_changed)
        layout.addWidget(self.combo_shape_rotation)

        self.slider_shape_gradient_align = SliderRow(
            title="Gradient-Einfluss:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.5,
            step=0.05,
            decimals=2,
            tooltip="0 = rein zuf\u00e4llig, 1 = vollst\u00e4ndig gradientenausgerichtet (nur im Gemischt-Modus).",
        )
        self.slider_shape_gradient_align.sig_value_changed.connect(self._emit_param_change)
        self.slider_shape_gradient_align.setVisible(False)
        layout.addWidget(self.slider_shape_gradient_align)

        # Randomize button
        self.btn_randomize = QPushButton("🎲  Alle Einstellungen zufällig würfeln")
        self.btn_randomize.setObjectName("randomizeButton")
        self.btn_randomize.setToolTip(
            "Setzt ALLE Parameter (Vorverarbeitung, Linien, Zeichenstil, Schraffur, Formen und Strichstärke) auf zufällige, erlaubte Werte und berechnet die Vorschau neu."
        )
        self.btn_randomize.clicked.connect(self._randomize_all_params)
        layout.addWidget(self.btn_randomize)

        self.layout_content.addWidget(box)

    def _on_shape_type_changed(self, idx: int) -> None:
        """Show/hide ASCII charset field depending on selected shape type."""
        is_ascii = (idx == len(self._SHAPE_TYPE_VALUES) - 1)  # ASCII is last
        self.lbl_ascii_charset.setVisible(is_ascii)
        self.edit_ascii_charset.setVisible(is_ascii)
        self._emit_param_change()

    def _on_shape_rotation_changed(self, idx: int) -> None:
        """Show/hide gradient align slider for 'mixed' mode."""
        self.slider_shape_gradient_align.setVisible(idx == 3)  # 3 = Gemischt
        self._emit_param_change()

    def _randomize_all_params(self) -> None:
        """Randomize ALL parameters across preprocessing, lines, style, hatching, shapes, and plotter options."""
        import random
        self._block_signals = True

        # --- 1. Vorverarbeitung (Filter) ---
        self.chk_clahe.setChecked(random.random() < 0.75)
        self.slider_clahe_kernel.set_value(random.choice([16, 24, 32, 40, 48, 56]))
        self.chk_blur.setChecked(random.random() < 0.70)
        self.slider_blur_sigma.set_value(round(random.uniform(0.4, 2.5), 1))

        # --- 2. Linienerkennung & Dichte ---
        self.slider_term_ratio.set_value(round(random.uniform(0.12, 0.45), 2))
        self.slider_continue_thresh.set_value(round(random.uniform(0.004, 0.030) / 0.002) * 0.002)
        self.slider_min_length.set_value(random.randint(10, 45))
        self.slider_max_angle.set_value(round(random.uniform(12.0, 45.0), 0))
        self.slider_lpf.set_value(round(random.uniform(0.02, 0.12), 2))

        # --- 3. Zeichenstil & Bézier-Kurven ---
        self.combo_line_mode.setCurrentIndex(random.choice([0, 1]))
        self.slider_bezier_smooth.set_value(round(random.uniform(0.15, 0.65) / 0.05) * 0.05)
        self.slider_sample_step.set_value(random.randint(1, 4))

        # --- 4. Schraffur (Hatching) ---
        self.chk_hatching.setChecked(random.random() < 0.50)
        self.combo_hatch_mode.setCurrentIndex(random.choice([0, 1]))
        self.slider_hatch_curve.set_value(round(random.uniform(0.2, 0.95), 2))
        self.slider_hatch_wobble.set_value(random.choice([0.0, 0.0, 0.2, 0.5, 0.8, 1.2]))
        self.slider_hatch_thresh.set_value(round(random.uniform(0.18, 0.50), 2))
        self.slider_hatch_spacing.set_value(random.randint(6, 22))
        self.slider_hatch_angle.set_value(random.choice([0.0, 25.0, 45.0, 60.0, 75.0, 90.0, 120.0, 135.0, 150.0]))
        self.chk_cross_hatch.setChecked(random.random() < 0.35)

        # --- 5. Formen-Modus (Shapes) ---
        self.chk_shapes.setChecked(random.random() < 0.55)
        n_types = len(self._SHAPE_TYPE_VALUES)
        type_idx = random.randint(0, n_types - 1)
        self.combo_shape_type.setCurrentIndex(type_idx)

        self.combo_shape_placement.setCurrentIndex(random.choice([0, 1]))

        min_s = round(random.uniform(1.0, 10.0), 1)
        max_s = round(random.uniform(min_s + 3.0, 45.0), 0)
        self.slider_shape_min_size.set_value(min_s)
        self.slider_shape_max_size.set_value(max_s)

        self.slider_shape_density.set_value(round(random.uniform(0.25, 1.6), 2))

        self.chk_shape_size_by_bright.setChecked(random.random() < 0.80)
        self.chk_shape_density_by_bright.setChecked(random.random() < 0.80)

        rot_idx = random.randint(0, 3)
        self.combo_shape_rotation.setCurrentIndex(rot_idx)
        self.slider_shape_gradient_align.set_value(round(random.uniform(0.2, 0.9), 2))
        self.slider_shape_gradient_align.setVisible(rot_idx == 3)

        is_ascii = (type_idx == len(self._SHAPE_TYPE_VALUES) - 1)
        self.lbl_ascii_charset.setVisible(is_ascii)
        self.edit_ascii_charset.setVisible(is_ascii)
        if is_ascii:
            ascii_options = [
                "@#S%?*+;:,. ",
                "@%#*+=-:. ",
                "01 ",
                "█▓▒░ ",
                "+-· ",
                "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ",
            ]
            self.edit_ascii_charset.setText(random.choice(ascii_options))

        # --- 6. Stift- und Plotter-Optionen ---
        self.slider_stroke_w.set_value(random.choice([0.25, 0.3, 0.35, 0.4, 0.5]))
        ink_colors = [
            "#1a1a1a",  # Deep Charcoal
            "#1e3a8a",  # Blueprint Navy
            "#0f766e",  # Deep Teal
            "#b91c1c",  # Crimson Vermilion
            "#7e22ce",  # Royal Violet
            "#c2410c",  # Burnt Orange
            "#374151",  # Slate Graphite
            "#047857",  # Emerald Green
            "#4338ca",  # Indigo
        ]
        chosen_color = random.choice(ink_colors)
        self.params.stroke_color = chosen_color
        self.btn_color.setStyleSheet(f"background-color: {chosen_color}; color: #ffffff;")

        self._block_signals = False
        self._emit_param_change()

    def _randomize_shape_params(self) -> None:
        """Alias for _randomize_all_params."""
        self._randomize_all_params()

    def _build_page_export_section(self) -> None:
        box = QGroupBox("Papier & Plotter-Optionen")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Papierformat:"))
        self.combo_page = QComboBox()
        self.combo_page.addItems(["Original", "A4", "A3", "A5", "Letter", "Custom"])
        self.combo_page.currentIndexChanged.connect(self._emit_param_change)
        layout.addWidget(self.combo_page)

        self.slider_margin = SliderRow(
            title="Rand:",
            min_val=0.0,
            max_val=40.0,
            default_val=10.0,
            step=1.0,
            suffix="mm",
            tooltip="Sicherheitsrand für den Stiftplotter.",
        )
        self.slider_margin.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_margin)

        self.slider_stroke_w = SliderRow(
            title="Strichstärke:",
            min_val=0.1,
            max_val=1.5,
            default_val=0.35,
            step=0.05,
            decimals=2,
            suffix="mm",
            tooltip="Physische Strichbreite des Stifts.",
        )
        self.slider_stroke_w.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_stroke_w)

        # Stroke color picker
        h_col = QHBoxLayout()
        h_col.addWidget(QLabel("Strichfarbe:"))
        self.btn_color = QPushButton("Farbe wählen...")
        self.btn_color.setStyleSheet("background-color: #1a1a1a; color: #ffffff;")
        self.btn_color.clicked.connect(self._pick_stroke_color)
        h_col.addWidget(self.btn_color)
        layout.addLayout(h_col)

        # Wegoptimierung: standardmäßig deaktiviert für schnellste Vorschau!
        self.chk_tsp = QCheckBox("Plotter-Wegoptimierung (Leerwege minimieren)")
        self.chk_tsp.setChecked(False)
        self.chk_tsp.setToolTip(
            "Sortiert Striche zur Reduktion von Leerfahrten beim physischen Plotten.\n"
            "Standardmäßig für schnelle Live-Vorschau deaktiviert."
        )
        self.chk_tsp.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_tsp)

        self.layout_content.addWidget(box)

    def _build_stats_section(self) -> None:
        box = QGroupBox("Plotter-Statistiken")
        layout = QGridLayout(box)
        layout.setSpacing(4)

        layout.addWidget(QLabel("Linien / Konturen:"), 0, 0)
        self.lbl_stat_lines = QLabel("0")
        self.lbl_stat_lines.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_lines, 0, 1)

        layout.addWidget(QLabel("Schraffurstriche:"), 1, 0)
        self.lbl_stat_hatch = QLabel("0")
        self.lbl_stat_hatch.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_hatch, 1, 1)

        layout.addWidget(QLabel("Formstriche:"), 2, 0)
        self.lbl_stat_shapes = QLabel("0")
        self.lbl_stat_shapes.setStyleSheet("color: #a78bfa; font-weight: bold;")
        layout.addWidget(self.lbl_stat_shapes, 2, 1)

        layout.addWidget(QLabel("Zeichenlänge gesamt:"), 3, 0)
        self.lbl_stat_len = QLabel("0.0 m")
        self.lbl_stat_len.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_len, 3, 1)

        layout.addWidget(QLabel("Leerweg (Pen-Up):"), 4, 0)
        self.lbl_stat_penup = QLabel("0.0 m")
        self.lbl_stat_penup.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_penup, 4, 1)

        layout.addWidget(QLabel("Berechnungsdauer:"), 5, 0)
        self.lbl_stat_time = QLabel("0.0 s")
        self.lbl_stat_time.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_time, 5, 1)

        self.layout_content.addWidget(box)

    # -------------------------------------------------------------------------
    # Value Synchronization
    # -------------------------------------------------------------------------

    def get_current_parameters(self) -> PlotParameters:
        """Read all widget states into a fresh PlotParameters instance."""
        p = PlotParameters()
        p.input_path = self.edit_input.text().strip()
        p.output_path = self.edit_output.text().strip()
        p.preview_max_dim = int(self.slider_preview_res.get_value())

        p.use_clahe = self.chk_clahe.isChecked()
        p.clahe_kernel_size = int(self.slider_clahe_kernel.get_value())
        p.use_gaussian_blur = self.chk_blur.isChecked()
        p.gaussian_kernel_size = self.slider_blur_sigma.get_value()

        p.termination_ratio = self.slider_term_ratio.get_value()
        p.line_continue_thresh = self.slider_continue_thresh.get_value()
        p.min_line_length = int(self.slider_min_length.get_value())
        p.max_curve_angle_deg = self.slider_max_angle.get_value()
        p.lpf_atk = self.slider_lpf.get_value()

        p.line_mode = "bezier" if self.combo_line_mode.currentIndex() == 1 else "straight"
        p.bezier_smoothness = self.slider_bezier_smooth.get_value()
        p.curve_sample_step = int(self.slider_sample_step.get_value())

        p.use_hatching = self.chk_hatching.isChecked()
        p.hatch_mode = "bezier" if self.combo_hatch_mode.currentIndex() == 0 else "straight"
        p.hatch_curve_strength = self.slider_hatch_curve.get_value()
        p.hatch_wobble = self.slider_hatch_wobble.get_value()
        p.hatching_threshold = self.slider_hatch_thresh.get_value()
        p.hatching_spacing = int(self.slider_hatch_spacing.get_value())
        p.hatching_angle_deg = self.slider_hatch_angle.get_value()
        p.cross_hatch = self.chk_cross_hatch.isChecked()

        p.use_shapes = self.chk_shapes.isChecked()
        idx = self.combo_shape_type.currentIndex()
        p.shape_type = self._SHAPE_TYPE_VALUES[idx] if 0 <= idx < len(self._SHAPE_TYPE_VALUES) else "dots"
        p.shape_placement = "grid" if self.combo_shape_placement.currentIndex() == 0 else "random"
        p.shape_min_size = self.slider_shape_min_size.get_value()
        p.shape_max_size = self.slider_shape_max_size.get_value()
        p.shape_density = self.slider_shape_density.get_value()
        p.shape_size_by_brightness = self.chk_shape_size_by_bright.isChecked()
        p.shape_density_by_brightness = self.chk_shape_density_by_bright.isChecked()
        ridx = self.combo_shape_rotation.currentIndex()
        p.shape_rotation_mode = self._ROTATION_MODE_VALUES[ridx] if 0 <= ridx < len(self._ROTATION_MODE_VALUES) else "random"
        p.shape_gradient_align = self.slider_shape_gradient_align.get_value()
        p.shape_ascii_charset = self.edit_ascii_charset.text() or "@#S%?*+;:,. "

        p.page_format = self.combo_page.currentText()
        p.margin_mm = self.slider_margin.get_value()
        p.stroke_width_mm = self.slider_stroke_w.get_value()
        p.stroke_color = self.params.stroke_color
        p.sort_paths = self.chk_tsp.isChecked()

        return p

    def apply_parameters(self, p: PlotParameters) -> None:
        """Populate sidebar widgets from a PlotParameters object."""
        self._block_signals = True

        if p.input_path:
            self.edit_input.setText(p.input_path)
        if p.output_path:
            self.edit_output.setText(p.output_path)

        self.slider_preview_res.set_value(p.preview_max_dim)

        self.chk_clahe.setChecked(p.use_clahe)
        self.slider_clahe_kernel.set_value(p.clahe_kernel_size)
        self.chk_blur.setChecked(p.use_gaussian_blur)
        self.slider_blur_sigma.set_value(p.gaussian_kernel_size)

        self.slider_term_ratio.set_value(p.termination_ratio)
        self.slider_continue_thresh.set_value(p.line_continue_thresh)
        self.slider_min_length.set_value(p.min_line_length)
        self.slider_max_angle.set_value(p.max_curve_angle_deg)
        self.slider_lpf.set_value(p.lpf_atk)

        self.combo_line_mode.setCurrentIndex(1 if p.line_mode.lower() == "bezier" else 0)
        self.slider_bezier_smooth.set_value(p.bezier_smoothness)
        self.slider_sample_step.set_value(p.curve_sample_step)

        self.chk_hatching.setChecked(p.use_hatching)
        self.combo_hatch_mode.setCurrentIndex(0 if p.hatch_mode.lower() == "bezier" else 1)
        self.slider_hatch_curve.set_value(p.hatch_curve_strength)
        self.slider_hatch_wobble.set_value(p.hatch_wobble)
        self.slider_hatch_thresh.set_value(p.hatching_threshold)
        self.slider_hatch_spacing.set_value(p.hatching_spacing)
        self.slider_hatch_angle.set_value(p.hatching_angle_deg)
        self.chk_cross_hatch.setChecked(p.cross_hatch)

        self.chk_shapes.setChecked(p.use_shapes)
        try:
            type_idx = self._SHAPE_TYPE_VALUES.index(p.shape_type)
        except ValueError:
            type_idx = 0
        self.combo_shape_type.setCurrentIndex(type_idx)
        self.lbl_ascii_charset.setVisible(type_idx == len(self._SHAPE_TYPE_VALUES) - 1)
        self.edit_ascii_charset.setVisible(type_idx == len(self._SHAPE_TYPE_VALUES) - 1)
        self.combo_shape_placement.setCurrentIndex(0 if p.shape_placement == "grid" else 1)
        self.slider_shape_min_size.set_value(p.shape_min_size)
        self.slider_shape_max_size.set_value(p.shape_max_size)
        self.slider_shape_density.set_value(p.shape_density)
        self.chk_shape_size_by_bright.setChecked(p.shape_size_by_brightness)
        self.chk_shape_density_by_bright.setChecked(p.shape_density_by_brightness)
        try:
            rot_idx = self._ROTATION_MODE_VALUES.index(p.shape_rotation_mode)
        except ValueError:
            rot_idx = 1
        self.combo_shape_rotation.setCurrentIndex(rot_idx)
        self.slider_shape_gradient_align.set_value(p.shape_gradient_align)
        self.slider_shape_gradient_align.setVisible(rot_idx == 3)
        self.edit_ascii_charset.setText(p.shape_ascii_charset or "@#S%?*+;:,. ")

        idx = self.combo_page.findText(p.page_format)
        if idx >= 0:
            self.combo_page.setCurrentIndex(idx)
        self.slider_margin.set_value(p.margin_mm)
        self.slider_stroke_w.set_value(p.stroke_width_mm)
        self.params.stroke_color = p.stroke_color
        self.btn_color.setStyleSheet(f"background-color: {p.stroke_color}; color: #ffffff;")
        self.chk_tsp.setChecked(p.sort_paths)

        self._block_signals = False

    def update_statistics(self, stats: PlotStats) -> None:
        """Display computation statistics in the statistics panel."""
        self.lbl_stat_lines.setText(f"{stats.contour_strokes}")
        self.lbl_stat_hatch.setText(f"{stats.hatch_strokes}")
        self.lbl_stat_shapes.setText(f"{stats.shape_strokes}")

        mm_per_px = 0.264583
        draw_m = (stats.total_length_px * mm_per_px) / 1000.0
        penup_m = (stats.pen_up_distance_px * mm_per_px) / 1000.0

        self.lbl_stat_len.setText(f"{draw_m:.2f} m ({int(stats.total_length_px)} px)")
        self.lbl_stat_penup.setText(f"{penup_m:.2f} m")
        self.lbl_stat_time.setText(f"{stats.elapsed_time_sec:.2f} s")

    def set_progress(self, fraction: float, msg: str) -> None:
        self.progress_bar.setValue(int(round(fraction * 100)))
        self.lbl_status.setText(msg)

    def set_computing_state(self, computing: bool) -> None:
        self.btn_calc.setEnabled(not computing)
        self.btn_cancel.setEnabled(computing)
        if not computing:
            self.progress_bar.setValue(100)

    # -------------------------------------------------------------------------
    # Preset Management
    # -------------------------------------------------------------------------

    def _refresh_presets_dropdown(self, select_name: Optional[str] = None) -> None:
        """Reload all presets into combo box."""
        self.combo_presets.blockSignals(True)
        current = select_name or self.combo_presets.currentText()
        self.combo_presets.clear()

        all_presets = get_all_presets()
        for name in all_presets.keys():
            self.combo_presets.addItem(name)

        idx = self.combo_presets.findText(current)
        if idx >= 0:
            self.combo_presets.setCurrentIndex(idx)
        else:
            self.combo_presets.setCurrentIndex(0)

        self._update_preset_delete_button_state()
        self.combo_presets.blockSignals(False)

    def _update_preset_delete_button_state(self) -> None:
        """Enable delete button only for custom user presets."""
        curr = self.combo_presets.currentText()
        is_user_preset = curr not in DEFAULT_PRESETS
        self.btn_delete_preset.setEnabled(is_user_preset)

    def _on_preset_selected(self, preset_name: str) -> None:
        all_presets = get_all_presets()
        if preset_name in all_presets:
            p = all_presets[preset_name]
            p.input_path = self.edit_input.text().strip()
            p.output_path = self.edit_output.text().strip()
            self.apply_parameters(p)
            self._update_preset_delete_button_state()
            self._emit_param_change()

    def _save_user_preset_dialog(self) -> None:
        """Prompt user for a preset name and save parameters to disk."""
        curr_text = self.combo_presets.currentText()
        default_name = curr_text if curr_text not in DEFAULT_PRESETS else "Mein Preset"

        name, ok = QInputDialog.getText(
            self,
            "Preset speichern",
            "Name für die neue Voreinstellung:",
            QLineEdit.EchoMode.Normal,
            default_name,
        )
        if ok and name.strip():
            preset_name = name.strip()
            params = self.get_current_parameters()
            saved_name = save_user_preset(preset_name, params)
            self._refresh_presets_dropdown(select_name=saved_name)
            QMessageBox.information(
                self,
                "Preset gespeichert",
                f"Die Voreinstellung '{saved_name}' wurde dauerhaft gespeichert.",
            )

    def _delete_current_preset(self) -> None:
        """Delete currently selected user preset."""
        curr = self.combo_presets.currentText()
        if curr in DEFAULT_PRESETS:
            QMessageBox.warning(self, "Hinweis", "Standard-Presets können nicht gelöscht werden.")
            return

        reply = QMessageBox.question(
            self,
            "Preset löschen",
            f"Möchtest du das Preset '{curr}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_user_preset(curr)
            self._refresh_presets_dropdown(select_name="Standard")
            self._on_preset_selected("Standard")

    def _load_preset_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "JSON-Preset importieren", "", "JSON (*.json)")
        if path:
            try:
                p = load_preset_file(path)
                p.input_path = self.edit_input.text().strip()
                p.output_path = self.edit_output.text().strip()
                self.apply_parameters(p)
                # Also save to user presets so it's readily accessible
                base_name = os.path.splitext(os.path.basename(path))[0]
                save_user_preset(base_name, p)
                self._refresh_presets_dropdown(select_name=base_name)
                self._emit_param_change()
                QMessageBox.information(self, "Import erfolgreich", f"Preset '{base_name}' importiert.")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Laden des Presets:\n{e}")

    def _save_preset_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Preset als JSON exportieren", "mein_preset.json", "JSON (*.json)")
        if path:
            try:
                curr_p = self.get_current_parameters()
                save_preset_file(curr_p, path)
                QMessageBox.information(self, "Export erfolgreich", f"Preset in '{os.path.basename(path)}' exportiert.")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern des Presets:\n{e}")

    def _reset_to_default(self) -> None:
        self.combo_presets.setCurrentText("Standard")
        self._on_preset_selected("Standard")

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _emit_param_change(self) -> None:
        if not self._block_signals:
            self.sig_parameters_changed.emit()

    def _on_input_text_changed(self, text: str) -> None:
        clean_text = text.strip()
        if os.path.isfile(clean_text) and not self._block_signals:
            self.sig_input_file_selected.emit(clean_text)

    def _browse_input_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Eingabebild auswählen",
            "",
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;Alle Dateien (*.*)",
        )
        if file_path:
            self.edit_input.setText(file_path)
            base, _ = os.path.splitext(file_path)
            self.edit_output.setText(base + "_plot.svg")
            self.sig_input_file_selected.emit(file_path)

    def _browse_output_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Ausgabedatei speichern unter",
            self.edit_output.text().strip(),
            "Vektordatei (*.svg);;Rasterbild (*.png);;Alle Dateien (*.*)",
        )
        if file_path:
            self.edit_output.setText(file_path)

    def _pick_stroke_color(self) -> None:
        initial = QColor(self.params.stroke_color)
        col = QColorDialog.getColor(initial, self, "Strichfarbe für Plotter wählen")
        if col.isValid():
            hex_col = col.name()
            self.params.stroke_color = hex_col
            self.btn_color.setStyleSheet(f"background-color: {hex_col}; color: #ffffff;")
            self._emit_param_change()

    def _on_style_mode_changed(self, idx: int) -> None:
        self._emit_param_change()

    def _on_hatching_toggled(self, state: int) -> None:
        self._emit_param_change()
