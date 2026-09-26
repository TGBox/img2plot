"""
Sidebar widget containing all parameter controls, file explorers, presets, and statistics.
"""

from __future__ import annotations
import os
from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
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
    QFrame,
)

from ..core.parameters import PlotParameters
from ..core.presets import DEFAULT_PRESETS, load_preset_file, save_preset_file
from ..core.engine import PlotStats


class SliderRow(QWidget):
    """Reusable widget combining a label, a slider, and a formatted numeric value readout."""

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
        self.lbl_val.setStyleSheet("color: #38bdf8; font-weight: bold; min-width: 45px; text-align: right;")
        self.lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        h_layout.addWidget(self.lbl_title)
        h_layout.addWidget(self.lbl_val)
        layout.addLayout(h_layout)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider_steps = int(round((max_val - min_val) / step))
        self.slider.setRange(0, self.slider_steps)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        if tooltip:
            self.setToolTip(tooltip)

        self.set_value(default_val)

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
        self.setMaximumWidth(440)

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
        self._build_page_export_section()
        self._build_stats_section()

        self.layout_content.addStretch()
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)

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

        self.combo_presets = QComboBox()
        self.combo_presets.addItems(list(DEFAULT_PRESETS.keys()))
        self.combo_presets.currentTextChanged.connect(self._on_preset_selected)
        layout.addWidget(self.combo_presets)

        h_btn = QHBoxLayout()
        self.btn_load_preset = QPushButton("Laden...")
        self.btn_load_preset.clicked.connect(self._load_preset_dialog)
        self.btn_save_preset = QPushButton("Speichern...")
        self.btn_save_preset.clicked.connect(self._save_preset_dialog)
        self.btn_reset_preset = QPushButton("Zurücksetzen")
        self.btn_reset_preset.clicked.connect(self._reset_to_default)
        h_btn.addWidget(self.btn_load_preset)
        h_btn.addWidget(self.btn_save_preset)
        h_btn.addWidget(self.btn_reset_preset)
        layout.addLayout(h_btn)

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
            tooltip="Winkel der Schraffurlinien.",
        )
        self.slider_hatch_angle.sig_value_changed.connect(self._emit_param_change)
        layout.addWidget(self.slider_hatch_angle)

        self.chk_cross_hatch = QCheckBox("Kreuzschraffur für tiefe Schatten")
        self.chk_cross_hatch.setChecked(False)
        self.chk_cross_hatch.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_cross_hatch)

        self.layout_content.addWidget(box)

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

        self.chk_tsp = QCheckBox("Plotter-Wegoptimierung (Leerwege minimieren)")
        self.chk_tsp.setChecked(True)
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

        layout.addWidget(QLabel("Zeichenlänge gesamt:"), 2, 0)
        self.lbl_stat_len = QLabel("0.0 m")
        self.lbl_stat_len.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_len, 2, 1)

        layout.addWidget(QLabel("Leerweg (Pen-Up):"), 3, 0)
        self.lbl_stat_penup = QLabel("0.0 m")
        self.lbl_stat_penup.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_penup, 3, 1)

        layout.addWidget(QLabel("Berechnungsdauer:"), 4, 0)
        self.lbl_stat_time = QLabel("0.0 s")
        self.lbl_stat_time.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_time, 4, 1)

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
        p.hatching_threshold = self.slider_hatch_thresh.get_value()
        p.hatching_spacing = int(self.slider_hatch_spacing.get_value())
        p.hatching_angle_deg = self.slider_hatch_angle.get_value()
        p.cross_hatch = self.chk_cross_hatch.isChecked()

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
        self.slider_hatch_thresh.set_value(p.hatching_threshold)
        self.slider_hatch_spacing.set_value(p.hatching_spacing)
        self.slider_hatch_angle.set_value(p.hatching_angle_deg)
        self.chk_cross_hatch.setChecked(p.cross_hatch)

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

        # Convert px to approximate meters assuming 96 DPI (~0.264583 mm / px)
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
            # Suggest default output path
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

    def _on_preset_selected(self, preset_name: str) -> None:
        if preset_name in DEFAULT_PRESETS:
            p = DEFAULT_PRESETS[preset_name]
            # Preserve current paths
            p.input_path = self.edit_input.text().strip()
            p.output_path = self.edit_output.text().strip()
            self.apply_parameters(p)
            self._emit_param_change()

    def _load_preset_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Preset-Datei laden", "", "JSON (*.json)")
        if path:
            try:
                p = load_preset_file(path)
                p.input_path = self.edit_input.text().strip()
                p.output_path = self.edit_output.text().strip()
                self.apply_parameters(p)
                self._emit_param_change()
                QMessageBox.information(self, "Preset geladen", f"Voreinstellung erfolgreich aus '{os.path.basename(path)}' geladen.")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Laden des Presets:\n{e}")

    def _save_preset_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Preset speichern", "mein_preset.json", "JSON (*.json)")
        if path:
            try:
                curr_p = self.get_current_parameters()
                save_preset_file(curr_p, path)
                QMessageBox.information(self, "Preset gespeichert", f"Voreinstellung erfolgreich in '{os.path.basename(path)}' gespeichert.")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Fehler beim Speichern des Presets:\n{e}")

    def _reset_to_default(self) -> None:
        self.combo_presets.setCurrentText("Standard")
        self._on_preset_selected("Standard")
