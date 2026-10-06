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
    QTabWidget,
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


class AccessibleCheckBox(QCheckBox):
    """QCheckBox with independent visibility query for container testing."""
    def isVisibleTo(self, ancestor) -> bool:
        return not self.isHidden()


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


class AccordionSection(QWidget):
    """
    Collapsible section with an accessible header button, chevron toggle indicator (▾/▸),
    section title, and dynamic status badge.
    """

    sig_toggled = Signal(bool)

    def __init__(self, title: str, parent=None, expanded: bool = True):
        super().__init__(parent)
        self._title = title
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(0)

        # Header Button
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("accordionHeader")
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle)

        header_layout = QHBoxLayout(self.header_btn)
        header_layout.setContentsMargins(10, 7, 10, 7)
        header_layout.setSpacing(8)

        # Chevron arrow label
        self.lbl_chevron = QLabel("▾" if expanded else "▸")
        self.lbl_chevron.setObjectName("accordionChevron")
        self.lbl_chevron.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        header_layout.addWidget(self.lbl_chevron)

        # Title label
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("accordionTitle")
        self.lbl_title.setStyleSheet("color: #f4f4f5; font-weight: 600; font-size: 12px;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        # Status badge label
        self.lbl_badge = QLabel("")
        self.lbl_badge.setObjectName("accordionBadge")
        header_layout.addWidget(self.lbl_badge)

        layout.addWidget(self.header_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_widget.setObjectName("accordionContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 6, 6, 8)
        self.content_layout.setSpacing(6)
        layout.addWidget(self.content_widget)

        self.set_expanded(expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.content_widget.setVisible(expanded)
        self.lbl_chevron.setText("▾" if expanded else "▸")
        self.header_btn.setProperty("expanded", "true" if expanded else "false")
        self.header_btn.style().unpolish(self.header_btn)
        self.header_btn.style().polish(self.header_btn)
        self.sig_toggled.emit(expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_badge(self, text: str, active: bool = False) -> None:
        if not text:
            self.lbl_badge.setVisible(False)
            return
        self.lbl_badge.setText(text)
        self.lbl_badge.setVisible(True)
        if active:
            self.lbl_badge.setStyleSheet(
                "color: #38bdf8; font-weight: 600; font-size: 11px; padding: 2px 7px; "
                "border-radius: 4px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35);"
            )
        else:
            self.lbl_badge.setStyleSheet(
                "color: #71717a; font-size: 11px; padding: 2px 6px; "
                "border-radius: 4px; background: #27272a; border: 1px solid #3f3f46;"
            )


class SidebarWidget(QWidget):
    """Sidebar containing all input sliders, buttons, file explorers, presets, and stats."""

    sig_parameters_changed = Signal()
    sig_recalculate_requested = Signal()
    sig_cancel_requested = Signal()
    sig_export_svg_requested = Signal()
    sig_export_png_requested = Signal()
    sig_input_file_selected = Signal(str)
    sig_open_preset_lab = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.setMaximumWidth(460)

        # Internal current parameters
        self.params = PlotParameters()
        self._block_signals = True

        # Main layout for SidebarWidget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Fixed Header (Dateien & Presets & Toolbar)
        header_container = QWidget()
        header_container.setObjectName("sidebarHeader")
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(8, 8, 8, 4)
        header_layout.setSpacing(6)

        self._build_file_input_section(header_layout)
        self._build_preset_section(header_layout)
        self._build_sections_toolbar(header_layout)
        main_layout.addWidget(header_container, stretch=0)

        # 2. Central Scroll Area with unified 4 Accordions
        scroll_area = QScrollArea()
        scroll_area.setObjectName("sidebarScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_content.setObjectName("sidebarContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 6, 8, 6)
        scroll_layout.setSpacing(8)

        # Accordion 1: 🧪 Bild-Filter & Vorschau (eingeklappt standardmäßig)
        self.acc_filter = AccordionSection("🧪 Bild-Filter & Vorschau", expanded=False)
        self._build_preprocessing_section(self.acc_filter.content_layout)
        self._build_preview_control_section(self.acc_filter.content_layout)
        scroll_layout.addWidget(self.acc_filter)

        # Accordion 2: 🎨 Künstlerische Stile (ausgeklappt standardmäßig)
        self.acc_artistic = AccordionSection("🎨 Künstlerische Stile", expanded=True)
        self._build_artistic_modes_section(self.acc_artistic.content_layout)
        scroll_layout.addWidget(self.acc_artistic)

        # Accordion 3: ✏️ Konturen & Schraffur (ausgeklappt standardmäßig)
        self.acc_contours = AccordionSection("✏️ Konturen & Schraffur", expanded=True)
        self._build_line_detection_section(self.acc_contours.content_layout)
        self._build_style_section(self.acc_contours.content_layout)
        self._build_hatching_section(self.acc_contours.content_layout)
        self._build_shapes_section(self.acc_contours.content_layout)
        scroll_layout.addWidget(self.acc_contours)

        # Accordion 4: 📐 Plotter, Export & Statistiken (eingeklappt standardmäßig)
        self.acc_plotter = AccordionSection("📐 Plotter, Export & Statistiken", expanded=False)
        self._build_export_files_section(self.acc_plotter.content_layout)
        self._build_page_export_section(self.acc_plotter.content_layout)
        self._build_stats_section(self.acc_plotter.content_layout)
        scroll_layout.addWidget(self.acc_plotter)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, stretch=1)

        # 3. Fixed Bottom Sticky Footer (Status, Progress, Calculate & Cancel)
        self._build_sticky_footer(main_layout)

        # Compatibility alias
        self.layout_content = scroll_layout

        self._refresh_presets_dropdown()
        self._block_signals = False
        self._update_accordion_badges()

    def _build_sections_toolbar(self, parent_layout: QVBoxLayout) -> None:
        """Toolbar with quick Expand All / Collapse All buttons."""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.setSpacing(6)

        lbl = QLabel("Abschnitte:")
        lbl.setStyleSheet("color: #71717a; font-size: 11px; font-weight: 500;")
        toolbar_layout.addWidget(lbl)
        toolbar_layout.addStretch()

        self.btn_expand_all = QPushButton("▾ Alle öffnen")
        self.btn_expand_all.setObjectName("toolbarSmallBtn")
        self.btn_expand_all.setToolTip("Alle 4 Einstellungs-Abschnitte aufklappen.")
        self.btn_expand_all.clicked.connect(self._expand_all_sections)
        toolbar_layout.addWidget(self.btn_expand_all)

        self.btn_collapse_all = QPushButton("▸ Alle schließen")
        self.btn_collapse_all.setObjectName("toolbarSmallBtn")
        self.btn_collapse_all.setToolTip("Alle Einstellungs-Abschnitte einklappen.")
        self.btn_collapse_all.clicked.connect(self._collapse_all_sections)
        toolbar_layout.addWidget(self.btn_collapse_all)

        parent_layout.addWidget(toolbar)

    def _expand_all_sections(self) -> None:
        for acc in [self.acc_filter, self.acc_artistic, self.acc_contours, self.acc_plotter]:
            acc.set_expanded(True)

    def _collapse_all_sections(self) -> None:
        for acc in [self.acc_filter, self.acc_artistic, self.acc_contours, self.acc_plotter]:
            acc.set_expanded(False)

    def _build_sticky_footer(self, parent_layout: QVBoxLayout) -> None:
        """Build sticky bottom footer containing progress bar, status, and recalculate/cancel buttons."""
        footer = QWidget()
        footer.setObjectName("stickyFooter")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        # Status text + percentage
        h_status = QHBoxLayout()
        self.lbl_status = QLabel("Bereit")
        self.lbl_status.setObjectName("statusLabel")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 500;")

        self.lbl_percent = QLabel("0%")
        self.lbl_percent.setObjectName("percentLabel")
        self.lbl_percent.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        h_status.addWidget(self.lbl_status, stretch=1)
        h_status.addWidget(self.lbl_percent, stretch=0)
        layout.addLayout(h_status)

        # Thin sleek progress bar (always visible regardless of scroll position)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("stickyProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Recalculate + Cancel buttons
        h_calc = QHBoxLayout()
        h_calc.setSpacing(6)
        self.btn_calc = QPushButton("⚡  Vorschau berechnen")
        self.btn_calc.setObjectName("primaryButton")
        self.btn_calc.setToolTip("Berechnung der Vektor-Vorschau manuell anstoßen.")
        self.btn_calc.clicked.connect(self.sig_recalculate_requested.emit)

        self.btn_cancel = QPushButton("✕  Abbrechen")
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setToolTip("Laufende Vektorisierungsberechnung abbrechen.")
        self.btn_cancel.clicked.connect(self.sig_cancel_requested.emit)

        h_calc.addWidget(self.btn_calc, stretch=2)
        h_calc.addWidget(self.btn_cancel, stretch=1)
        layout.addLayout(h_calc)

        # Randomize button
        self.btn_randomize_top = QPushButton("🎲  Einstellungen würfeln")
        self.btn_randomize_top.setObjectName("randomizeButton")
        self.btn_randomize_top.setToolTip(
            "Würfelt ALLE Einstellungen (Filter, Linienerkennung, Zeichenstil, Schraffur, Formen und Strich) zufällig mit sinnvollen Werten."
        )
        self.btn_randomize_top.clicked.connect(self._randomize_all_params)
        layout.addWidget(self.btn_randomize_top)

        parent_layout.addWidget(footer, stretch=0)

    def _update_accordion_badges(self) -> None:
        """Update status badges on accordion headers to reflect active features."""
        if (
            not hasattr(self, "acc_filter")
            or not hasattr(self, "acc_artistic")
            or not hasattr(self, "acc_contours")
            or not hasattr(self, "acc_plotter")
        ):
            return

        # 1. Filter badge
        has_kuwahara = hasattr(self, "chk_kuwahara") and self.chk_kuwahara.isChecked()
        has_quadtree = hasattr(self, "chk_quadtree") and self.chk_quadtree.isChecked()
        has_pixel_sort = hasattr(self, "chk_pixel_sort") and self.chk_pixel_sort.isChecked()
        has_fft = hasattr(self, "chk_fft") and self.chk_fft.isChecked()
        has_ca = hasattr(self, "chk_ca") and self.chk_ca.isChecked()
        if has_fft:
            self.acc_filter.set_badge("• 2D-FFT aktiv", active=True)
        elif has_ca:
            self.acc_filter.set_badge("• Automaten (CCA)", active=True)
        elif has_quadtree and has_pixel_sort:
            self.acc_filter.set_badge("• Quadtree + Glitch", active=True)
        elif has_quadtree:
            self.acc_filter.set_badge("• Quadtree aktiv", active=True)
        elif has_pixel_sort:
            self.acc_filter.set_badge("• Pixel-Sort aktiv", active=True)
        elif has_kuwahara:
            r = int(self.slider_kuwahara_r.get_value()) if hasattr(self, "slider_kuwahara_r") else 3
            is_aniso = hasattr(self, "combo_kuwahara_mode") and self.combo_kuwahara_mode.currentIndex() == 1
            mode_lbl = "Aniso" if is_aniso else "Kuwahara"
            self.acc_filter.set_badge(f"• {mode_lbl} (R={r})", active=True)
        else:
            self.acc_filter.set_badge("Standard", active=False)

        # 2. Artistic badge
        if hasattr(self, "combo_artistic_mode"):
            idx = self.combo_artistic_mode.currentIndex()
            mode_names = [
                "Keiner",
                "• Wellenform",
                "• Spirale",
                "• TSP-Linie",
                "• Low-Poly",
                "• Flussfeld",
                "• Voronoi",
                "• Turing-Muster",
                "• Stippling",
                "• SBR-Pinsel",
                "• Iso-Konturen",
                "• Physarum",
                "• String-Art",
                "• Diff-Growth",
            ]
            if 0 < idx < len(mode_names):
                self.acc_artistic.set_badge(mode_names[idx], active=True)
            else:
                self.acc_artistic.set_badge("Keiner", active=False)

        # 3. Contours & Hatching & Shapes badge
        has_hatch = hasattr(self, "chk_hatching") and self.chk_hatching.isChecked()
        has_shape = hasattr(self, "chk_shapes") and self.chk_shapes.isChecked()
        if has_hatch and has_shape:
            self.acc_contours.set_badge("• Schraffur + Formen", active=True)
        elif has_hatch:
            self.acc_contours.set_badge("• Schraffur aktiv", active=True)
        elif has_shape:
            st = self.combo_shape_type.currentText().split()[0] if hasattr(self, "combo_shape_type") else "Formen"
            self.acc_contours.set_badge(f"• {st}", active=True)
        else:
            self.acc_contours.set_badge("Konturen aktiv", active=False)

        # 4. Plotter badge
        has_tsp = hasattr(self, "chk_tsp") and self.chk_tsp.isChecked()
        has_two_opt = hasattr(self, "chk_two_opt") and self.chk_two_opt.isChecked()
        if has_tsp and has_two_opt:
            self.acc_plotter.set_badge("• TSP + 2-Opt", active=True)
        elif has_tsp:
            self.acc_plotter.set_badge("• TSP aktiv", active=True)
        else:
            page_sz = self.combo_page.currentText().split()[0] if hasattr(self, "combo_page") else "A4"
            self.acc_plotter.set_badge(page_sz, active=False)

    def _update_tab_badges(self) -> None:
        """Backwards compatibility alias for _update_accordion_badges."""
        self._update_accordion_badges()

    # -------------------------------------------------------------------------
    # UI Sections
    # -------------------------------------------------------------------------

    def _build_file_input_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        box = QGroupBox("Bildquelle")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Eingabebild:"))
        h_in = QHBoxLayout()
        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Pfad zu PNG, JPG, BMP, WebP...")
        self.edit_input.textChanged.connect(self._on_input_text_changed)
        self.btn_browse_in = QPushButton("Durchsuchen...")
        self.btn_browse_in.clicked.connect(self._browse_input_file)
        h_in.addWidget(self.edit_input)
        h_in.addWidget(self.btn_browse_in)
        layout.addLayout(h_in)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_export_files_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        box = QGroupBox("Datei-Export")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Ausgabedatei:"))
        h_out = QHBoxLayout()
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Pfad für SVG / PNG...")
        self.btn_browse_out = QPushButton("Speichern unter...")
        self.btn_browse_out.clicked.connect(self._browse_output_file)
        h_out.addWidget(self.edit_output)
        h_out.addWidget(self.btn_browse_out)
        layout.addLayout(h_out)

        h_btn = QHBoxLayout()
        self.btn_export_svg = QPushButton("SVG Exportieren")
        self.btn_export_svg.setObjectName("primaryButton")
        self.btn_export_svg.clicked.connect(self.sig_export_svg_requested.emit)
        self.btn_export_png = QPushButton("PNG Exportieren")
        self.btn_export_png.clicked.connect(self.sig_export_png_requested.emit)
        h_btn.addWidget(self.btn_export_svg)
        h_btn.addWidget(self.btn_export_png)
        layout.addLayout(h_btn)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_file_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        """Backward compatibility helper."""
        self._build_file_input_section(parent_layout)
        self._build_export_files_section(parent_layout)

    def _build_preset_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
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

        self.btn_open_preset_lab = QPushButton("🔬  Preset-Labor / Stil-Entdecker...")
        self.btn_open_preset_lab.setToolTip("Öffnet das Preset-Labor, um Zufallsvarianten auf dem Quellbild auszuprobieren und als Presets zu speichern.")
        self.btn_open_preset_lab.clicked.connect(self.sig_open_preset_lab.emit)
        layout.addWidget(self.btn_open_preset_lab)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_preview_control_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        box = QGroupBox("Live-Vorschau & Performance")
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

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_preprocessing_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        box = QGroupBox("Vorverarbeitung (Filter)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.chk_clahe = QCheckBox("CLAHE Kontrast-Angleichung")
        self.chk_clahe.setChecked(True)
        self.chk_clahe.stateChanged.connect(self._on_filter_toggled)
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
        self.chk_blur.stateChanged.connect(self._on_filter_toggled)
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

        # Kuwahara filter for oil painting look
        self.chk_kuwahara = QCheckBox("Kuwahara Ölgemälde-Filter")
        self.chk_kuwahara.setChecked(False)
        self.chk_kuwahara.setToolTip("Glättet Farbflächen flächig wie Ölgemälde, erhält Hauptkanten aber messerscharf.")
        self.chk_kuwahara.stateChanged.connect(self._on_filter_toggled)
        layout.addWidget(self.chk_kuwahara)

        self.combo_kuwahara_mode = QComboBox()
        self.combo_kuwahara_mode.addItems(["Klassisch (4 Sektoren)", "Anisotrop (Strukturtensor)"])
        self.combo_kuwahara_mode.currentIndexChanged.connect(self._on_filter_toggled)
        self.combo_kuwahara_mode.setVisible(False)
        layout.addWidget(self.combo_kuwahara_mode)

        self.slider_kuwahara_r = SliderRow(
            title="Ölgemälde-Pinselgröße (Radius):",
            min_val=1,
            max_val=8,
            default_val=3,
            step=1,
            suffix="px",
            tooltip="Radius der Kuwahara-Pinselstriche.",
        )
        self.slider_kuwahara_r.sig_value_changed.connect(self._emit_param_change)
        self.slider_kuwahara_r.setVisible(False)
        layout.addWidget(self.slider_kuwahara_r)

        self.slider_kuwahara_anisotropy = SliderRow(
            title="Anisotropie-Stärke:",
            min_val=0.1,
            max_val=3.0,
            default_val=1.0,
            step=0.1,
            decimals=1,
            tooltip="Stärke der Kantenfluss-Dehnung bei anisotropem Kuwahara.",
        )
        self.slider_kuwahara_anisotropy.sig_value_changed.connect(self._emit_param_change)
        self.slider_kuwahara_anisotropy.setVisible(False)
        layout.addWidget(self.slider_kuwahara_anisotropy)

        # Quadtree decomposition filter
        self.chk_quadtree = QCheckBox("Quadtree-Dekomposition (Block-Abstraktion)")
        self.chk_quadtree.setChecked(False)
        self.chk_quadtree.setToolTip("Zerlegt das Bild rekursiv in 4 Quadranten nach Helligkeitsvarianz.")
        self.chk_quadtree.stateChanged.connect(self._on_filter_toggled)
        layout.addWidget(self.chk_quadtree)

        self.slider_quadtree_thresh = SliderRow(
            title="Quadtree Varianz-Schwelle:",
            min_val=0.01,
            max_val=0.25,
            default_val=0.06,
            step=0.01,
            decimals=2,
            tooltip="Schwellenwert zur Blockunterteilung (höher = gröbere Blöcke).",
        )
        self.slider_quadtree_thresh.sig_value_changed.connect(self._emit_param_change)
        self.slider_quadtree_thresh.setVisible(False)
        layout.addWidget(self.slider_quadtree_thresh)

        self.slider_quadtree_min_size = SliderRow(
            title="Min. Blockgröße:",
            min_val=2,
            max_val=48,
            default_val=8,
            step=2,
            suffix="px",
            tooltip="Minimale Kantenlänge der Blöcke in Pixeln.",
        )
        self.slider_quadtree_min_size.sig_value_changed.connect(self._emit_param_change)
        self.slider_quadtree_min_size.setVisible(False)
        layout.addWidget(self.slider_quadtree_min_size)

        self.chk_quadtree_render_boxes = QCheckBox("Quadtree-Gitterboxen als Vektorlinien plotten")
        self.chk_quadtree_render_boxes.setChecked(False)
        self.chk_quadtree_render_boxes.setToolTip("Zeichnet die Rechteck-Gitterlinien der Quadtree-Blöcke direkt als Striche.")
        self.chk_quadtree_render_boxes.stateChanged.connect(self._emit_param_change)
        self.chk_quadtree_render_boxes.setVisible(False)
        layout.addWidget(self.chk_quadtree_render_boxes)

        # Pixel Sorting filter
        self.chk_pixel_sort = QCheckBox("Pixel-Sorting (Glitch-Art)")
        self.chk_pixel_sort.setChecked(False)
        self.chk_pixel_sort.setToolTip("Sortiert Bildzeilen oder -spalten in Helligkeitsintervallen für Glitch-Art-Streifen.")
        self.chk_pixel_sort.stateChanged.connect(self._on_filter_toggled)
        layout.addWidget(self.chk_pixel_sort)

        self.widget_pixel_sort_opts = QWidget()
        ps_layout = QVBoxLayout(self.widget_pixel_sort_opts)
        ps_layout.setContentsMargins(0, 0, 0, 0)
        ps_layout.setSpacing(4)

        ps_layout.addWidget(QLabel("Sortierrichtung:"))
        self.combo_pixel_sort_dir = QComboBox()
        self.combo_pixel_sort_dir.addItems(["Horizontal (Zeilen)", "Vertikal (Spalten)"])
        self.combo_pixel_sort_dir.currentIndexChanged.connect(self._emit_param_change)
        ps_layout.addWidget(self.combo_pixel_sort_dir)

        self.slider_pixel_sort_lower = SliderRow(
            title="Untere Helligkeitsschwelle:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.25,
            step=0.05,
            decimals=2,
            tooltip="Minimale Helligkeit für sortierbare Intervalle.",
        )
        self.slider_pixel_sort_lower.sig_value_changed.connect(self._emit_param_change)
        ps_layout.addWidget(self.slider_pixel_sort_lower)

        self.slider_pixel_sort_upper = SliderRow(
            title="Obere Helligkeitsschwelle:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.80,
            step=0.05,
            decimals=2,
            tooltip="Maximale Helligkeit für sortierbare Intervalle.",
        )
        self.slider_pixel_sort_upper.sig_value_changed.connect(self._emit_param_change)
        ps_layout.addWidget(self.slider_pixel_sort_upper)

        self.chk_pixel_sort_rev = QCheckBox("Sortierung umkehren (absteigend)")
        self.chk_pixel_sort_rev.setChecked(False)
        self.chk_pixel_sort_rev.stateChanged.connect(self._emit_param_change)
        ps_layout.addWidget(self.chk_pixel_sort_rev)

        self.widget_pixel_sort_opts.setVisible(False)
        layout.addWidget(self.widget_pixel_sort_opts)

        # 2D-FFT frequency domain filter
        self.chk_fft = QCheckBox("2D-FFT Frequenzraum-Filter (Moiré / Wellen)")
        self.chk_fft.setChecked(False)
        self.chk_fft.setToolTip("Filtert Amplitude oder Phase im Frequenzraum für Moiré-Effekte und Welleninterferenzen.")
        self.chk_fft.stateChanged.connect(self._on_filter_toggled)
        layout.addWidget(self.chk_fft)

        self.widget_fft_opts = QWidget()
        fft_layout = QVBoxLayout(self.widget_fft_opts)
        fft_layout.setContentsMargins(0, 0, 0, 0)
        fft_layout.setSpacing(4)

        fft_layout.addWidget(QLabel("FFT Filtertyp:"))
        self.combo_fft_type = QComboBox()
        self.combo_fft_type.addItems([
            "Moiré-Interferenz (Ringe)",
            "Bandpass (Frequenzband)",
            "Richtungs-Interferenz (Wellen)",
            "Hochpass (Kantenfrequenzen)",
        ])
        self.combo_fft_type.currentIndexChanged.connect(self._emit_param_change)
        fft_layout.addWidget(self.combo_fft_type)

        self.slider_fft_freq = SliderRow(
            title="Frequenz-Radius / Gitter:",
            min_val=2.0,
            max_val=80.0,
            default_val=25.0,
            step=1.0,
            decimals=1,
            tooltip="Ziel-Frequenzradius für Bandpass oder Moiré-Muster.",
        )
        self.slider_fft_freq.sig_value_changed.connect(self._emit_param_change)
        fft_layout.addWidget(self.slider_fft_freq)

        self.slider_fft_amount = SliderRow(
            title="Misch-Intensität:",
            min_val=0.05,
            max_val=1.0,
            default_val=0.6,
            step=0.05,
            decimals=2,
            tooltip="Mischungsverhältnis zwischen Original und FFT-Muster.",
        )
        self.slider_fft_amount.sig_value_changed.connect(self._emit_param_change)
        fft_layout.addWidget(self.slider_fft_amount)

        self.widget_fft_opts.setVisible(False)
        layout.addWidget(self.widget_fft_opts)

        # Cyclic Cellular Automata filter
        self.chk_ca = QCheckBox("Zelluläre Automaten (CCA Kristallisation)")
        self.chk_ca.setChecked(False)
        self.chk_ca.setToolTip("Transformiert Bildpixel durch zyklische Nachbarschaftsregeln in kristalline Muster.")
        self.chk_ca.stateChanged.connect(self._on_filter_toggled)
        layout.addWidget(self.chk_ca)

        self.widget_ca_opts = QWidget()
        ca_layout = QVBoxLayout(self.widget_ca_opts)
        ca_layout.setContentsMargins(0, 0, 0, 0)
        ca_layout.setSpacing(4)

        self.slider_ca_steps = SliderRow(
            title="Simulations-Schritte:",
            min_val=1,
            max_val=25,
            default_val=6,
            step=1,
            tooltip="Anzahl Zyklen des zellulären Automaten.",
        )
        self.slider_ca_steps.sig_value_changed.connect(self._emit_param_change)
        ca_layout.addWidget(self.slider_ca_steps)

        self.slider_ca_states = SliderRow(
            title="Zustände (Farbstufen):",
            min_val=3,
            max_val=16,
            default_val=8,
            step=1,
            tooltip="Anzahl der diskreten Zustände im Automaten.",
        )
        self.slider_ca_states.sig_value_changed.connect(self._emit_param_change)
        ca_layout.addWidget(self.slider_ca_states)

        self.slider_ca_threshold = SliderRow(
            title="Nachbarschafts-Schwelle:",
            min_val=1,
            max_val=5,
            default_val=1,
            step=1,
            tooltip="Mindestanzahl an Nachbarn für einen Zustandsübergang.",
        )
        self.slider_ca_threshold.sig_value_changed.connect(self._emit_param_change)
        ca_layout.addWidget(self.slider_ca_threshold)

        self.widget_ca_opts.setVisible(False)
        layout.addWidget(self.widget_ca_opts)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _on_filter_toggled(self, *args) -> None:
        """Progressive disclosure for filter sliders."""
        if hasattr(self, "slider_clahe_kernel"):
            self.slider_clahe_kernel.setVisible(self.chk_clahe.isChecked())
        if hasattr(self, "slider_blur_sigma"):
            self.slider_blur_sigma.setVisible(self.chk_blur.isChecked())
        if hasattr(self, "chk_kuwahara"):
            is_kuw = self.chk_kuwahara.isChecked()
            if hasattr(self, "slider_kuwahara_r"):
                self.slider_kuwahara_r.setVisible(is_kuw)
            if hasattr(self, "combo_kuwahara_mode"):
                self.combo_kuwahara_mode.setVisible(is_kuw)
            if hasattr(self, "slider_kuwahara_anisotropy"):
                is_aniso = hasattr(self, "combo_kuwahara_mode") and self.combo_kuwahara_mode.currentIndex() == 1
                self.slider_kuwahara_anisotropy.setVisible(is_kuw and is_aniso)
        if hasattr(self, "chk_quadtree"):
            is_qt = self.chk_quadtree.isChecked()
            self.slider_quadtree_thresh.setVisible(is_qt)
            self.slider_quadtree_min_size.setVisible(is_qt)
            self.chk_quadtree_render_boxes.setVisible(is_qt)
        if hasattr(self, "chk_pixel_sort"):
            self.widget_pixel_sort_opts.setVisible(self.chk_pixel_sort.isChecked())
        if hasattr(self, "chk_fft"):
            self.widget_fft_opts.setVisible(self.chk_fft.isChecked())
        if hasattr(self, "chk_ca"):
            self.widget_ca_opts.setVisible(self.chk_ca.isChecked())
        self._emit_param_change()

    def _build_line_detection_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
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

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_style_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
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

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    _ARTISTIC_MODE_VALUES = [
        "none",
        "waveform",
        "spiral",
        "tsp",
        "delaunay",
        "flowfield",
        "voronoi",
        "reaction_diffusion",
        "stippling",
        "sbr",
        "isocontours",
        "physarum",
        "string_art",
        "diffgrowth",
    ]

    def _build_artistic_modes_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        """Build the non-AI artistic styles control section."""
        box = QGroupBox("🎨 Künstlerische Stile (Artistic Modes)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Kunststil auswählen:"))
        self.combo_artistic_mode = QComboBox()
        self.combo_artistic_mode.addItems([
            "Keiner (Klassische Konturzeichnung)",
            "Wellenform / Joy Division (3D-Relief)",
            "Archimedische Spirale (1 durchgehende Linie)",
            "TSP Single-Line (Handlungsreisender)",
            "Low-Poly (Delaunay-Mosaik)",
            "Flussfeld (Van-Gogh-Streamlines)",
            "Voronoi-Mosaik (Zell-Polygone)",
            "Reaktions-Diffusion (Turing-Muster)",
            "Voronoi Stippling (Lloyd-Relaxation)",
            "Stroke-Based Rendering (Bézier-Pinselstriche)",
            "Marching Squares (Iso-Höhenlinien)",
            "Physarum-Simulation (Schleimpilz-Netzwerk)",
            "String-Art (Radon/Bresenham Fadenbild)",
            "Differenzielles Wachstum (Differential Growth)",
        ])
        self.combo_artistic_mode.currentIndexChanged.connect(self._on_artistic_mode_changed)
        layout.addWidget(self.combo_artistic_mode)

        self.chk_artistic_overlay = QCheckBox("Hauptkonturen zusätzlich überlagern")
        self.chk_artistic_overlay.setChecked(False)
        self.chk_artistic_overlay.setToolTip("Zeichnet zusätzlich zum Kunststil die erkannten Hauptkanten.")
        self.chk_artistic_overlay.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_artistic_overlay)

        # --- Waveform controls ---
        self.widget_waveform_opts = QWidget()
        w_layout = QVBoxLayout(self.widget_waveform_opts)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.setSpacing(4)

        self.slider_wave_lines = SliderRow(
            title="Wellenlinien-Anzahl:",
            min_val=20,
            max_val=120,
            default_val=60,
            step=5,
            tooltip="Anzahl der horizontalen Scanlinien über das Bild.",
        )
        self.slider_wave_lines.sig_value_changed.connect(self._emit_param_change)
        w_layout.addWidget(self.slider_wave_lines)

        self.slider_wave_amp = SliderRow(
            title="Wellen-Ausschlag (Amplitude):",
            min_val=5.0,
            max_val=50.0,
            default_val=20.0,
            step=1.0,
            decimals=1,
            suffix="px",
            tooltip="Maximale Auslenkung der Wellen in dunklen Bildbereichen.",
        )
        self.slider_wave_amp.sig_value_changed.connect(self._emit_param_change)
        w_layout.addWidget(self.slider_wave_amp)

        self.chk_wave_occlusion = QCheckBox("3D-Verdeckung (Hintergrundlinien verbergen)")
        self.chk_wave_occlusion.setChecked(True)
        self.chk_wave_occlusion.setToolTip("Klassischer Joy-Division-Effekt: Vordergrundberge verdecken dahinterliegende Linien.")
        self.chk_wave_occlusion.stateChanged.connect(self._emit_param_change)
        w_layout.addWidget(self.chk_wave_occlusion)
        layout.addWidget(self.widget_waveform_opts)

        # --- Spiral controls ---
        self.widget_spiral_opts = QWidget()
        s_layout = QVBoxLayout(self.widget_spiral_opts)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(4)

        self.slider_spiral_loops = SliderRow(
            title="Spiral-Windungen (Umdrehungen):",
            min_val=20,
            max_val=150,
            default_val=75,
            step=5,
            tooltip="Gesamtzahl der Spiralwindungen von innen nach außen.",
        )
        self.slider_spiral_loops.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_spiral_loops)

        self.slider_spiral_amp = SliderRow(
            title="Schwingungs-Amplitude:",
            min_val=1.0,
            max_val=25.0,
            default_val=6.0,
            step=0.5,
            decimals=1,
            suffix="px",
            tooltip="Stärke der Zickzack-/Wellenmodulation in dunklen Bereichen.",
        )
        self.slider_spiral_amp.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_spiral_amp)

        self.slider_spiral_freq = SliderRow(
            title="Schwingungs-Frequenz:",
            min_val=5.0,
            max_val=60.0,
            default_val=30.0,
            step=2.0,
            decimals=0,
            tooltip="Wellenfrequenz entlang des Spiralarms.",
        )
        self.slider_spiral_freq.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_spiral_freq)
        layout.addWidget(self.widget_spiral_opts)

        # --- TSP controls ---
        self.widget_tsp_opts = QWidget()
        t_layout = QVBoxLayout(self.widget_tsp_opts)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(4)

        self.slider_tsp_points = SliderRow(
            title="Punktanzahl (Dichte):",
            min_val=300,
            max_val=4000,
            default_val=2400,
            step=50,
            tooltip="Anzahl der Stipple-Punkte, die zu einer einzigen Linie verbunden werden.",
        )
        self.slider_tsp_points.sig_value_changed.connect(self._emit_param_change)
        t_layout.addWidget(self.slider_tsp_points)

        self.slider_tsp_passes = SliderRow(
            title="2-Opt Entflechtung (Durchläufe):",
            min_val=3,
            max_val=30,
            default_val=15,
            step=1,
            tooltip="Anzahl der Optimierungsdurchläufe zur Beseitigung von Linienkreuzungen.",
        )
        self.slider_tsp_passes.sig_value_changed.connect(self._emit_param_change)
        t_layout.addWidget(self.slider_tsp_passes)
        layout.addWidget(self.widget_tsp_opts)

        # --- Delaunay controls ---
        self.widget_delaunay_opts = QWidget()
        d_layout = QVBoxLayout(self.widget_delaunay_opts)
        d_layout.setContentsMargins(0, 0, 0, 0)
        d_layout.setSpacing(4)

        self.slider_delaunay_points = SliderRow(
            title="Polygonanzahl / Knoten:",
            min_val=200,
            max_val=3000,
            default_val=1400,
            step=50,
            tooltip="Anzahl der Dreiecksknoten für das Low-Poly-Mosaik.",
        )
        self.slider_delaunay_points.sig_value_changed.connect(self._emit_param_change)
        d_layout.addWidget(self.slider_delaunay_points)

        self.slider_delaunay_weight = SliderRow(
            title="Kanten- vs. Schattenfokus:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.65,
            step=0.05,
            decimals=2,
            tooltip="0.0 = Punkte nach Helligkeit, 1.0 = Punkte dicht an Objektkanten.",
        )
        self.slider_delaunay_weight.sig_value_changed.connect(self._emit_param_change)
        d_layout.addWidget(self.slider_delaunay_weight)
        layout.addWidget(self.widget_delaunay_opts)

        # --- Flowfield controls ---
        self.widget_flow_opts = QWidget()
        f_layout = QVBoxLayout(self.widget_flow_opts)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(4)

        self.slider_flow_lines = SliderRow(
            title="Linienanzahl (Streamlines):",
            min_val=200,
            max_val=2500,
            default_val=1000,
            step=50,
            tooltip="Anzahl der virtuellen Pinselstriche.",
        )
        self.slider_flow_lines.sig_value_changed.connect(self._emit_param_change)
        f_layout.addWidget(self.slider_flow_lines)

        self.slider_flow_steps = SliderRow(
            title="Maximale Strichlänge:",
            min_val=10,
            max_val=100,
            default_val=50,
            step=5,
            tooltip="Maximale Schrittweite je Flusslinie.",
        )
        self.slider_flow_steps.sig_value_changed.connect(self._emit_param_change)
        f_layout.addWidget(self.slider_flow_steps)

        f_layout.addWidget(QLabel("Flussrichtung:"))
        self.combo_flow_dir = QComboBox()
        self.combo_flow_dir.addItems([
            "Entlang von Objektkanten (Tangential)",
            "Quer zu Kanten (Gradient)",
        ])
        self.combo_flow_dir.currentIndexChanged.connect(self._emit_param_change)
        f_layout.addWidget(self.combo_flow_dir)
        layout.addWidget(self.widget_flow_opts)

        # --- Voronoi Mosaic controls ---
        self.widget_voronoi_opts = QWidget()
        vo_layout = QVBoxLayout(self.widget_voronoi_opts)
        vo_layout.setContentsMargins(0, 0, 0, 0)
        vo_layout.setSpacing(4)

        self.slider_voronoi_points = SliderRow(
            title="Voronoi-Zellenanzahl:",
            min_val=100,
            max_val=4000,
            default_val=1200,
            step=50,
            tooltip="Anzahl der Voronoi-Zellkeime.",
        )
        self.slider_voronoi_points.sig_value_changed.connect(self._emit_param_change)
        vo_layout.addWidget(self.slider_voronoi_points)

        self.slider_voronoi_weight = SliderRow(
            title="Kanten-Gewichtung:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.60,
            step=0.05,
            decimals=2,
            tooltip="0.0 = Reine Schattenbetonung, 1.0 = Reine Kantenbetonung.",
        )
        self.slider_voronoi_weight.sig_value_changed.connect(self._emit_param_change)
        vo_layout.addWidget(self.slider_voronoi_weight)
        layout.addWidget(self.widget_voronoi_opts)

        # --- Reaction-Diffusion (Turing) controls ---
        self.widget_rd_opts = QWidget()
        rd_layout = QVBoxLayout(self.widget_rd_opts)
        rd_layout.setContentsMargins(0, 0, 0, 0)
        rd_layout.setSpacing(4)

        self.slider_rd_res = SliderRow(
            title="Simulations-Auflösung:",
            min_val=80,
            max_val=320,
            default_val=180,
            step=10,
            tooltip="Gittergröße für die Diffusionssimulation (höher = feinere Muster).",
        )
        self.slider_rd_res.sig_value_changed.connect(self._emit_param_change)
        rd_layout.addWidget(self.slider_rd_res)

        self.slider_rd_iter = SliderRow(
            title="Simulations-Schritte:",
            min_val=50,
            max_val=500,
            default_val=240,
            step=10,
            tooltip="Anzahl der Zeitschritte für das Gray-Scott-Modell.",
        )
        self.slider_rd_iter.sig_value_changed.connect(self._emit_param_change)
        rd_layout.addWidget(self.slider_rd_iter)

        self.slider_rd_feed = SliderRow(
            title="Feed-Rate (F):",
            min_val=0.015,
            max_val=0.065,
            default_val=0.037,
            step=0.002,
            decimals=3,
            tooltip="Chemische Zufuhrrate (steuert Flecken vs. Streifen).",
        )
        self.slider_rd_feed.sig_value_changed.connect(self._emit_param_change)
        rd_layout.addWidget(self.slider_rd_feed)

        self.slider_rd_kill = SliderRow(
            title="Kill-Rate (k):",
            min_val=0.045,
            max_val=0.070,
            default_val=0.060,
            step=0.001,
            decimals=3,
            tooltip="Chemische Abbaurate.",
        )
        self.slider_rd_kill.sig_value_changed.connect(self._emit_param_change)
        rd_layout.addWidget(self.slider_rd_kill)

        self.slider_rd_level = SliderRow(
            title="Isolinien-Schwelle:",
            min_val=0.10,
            max_val=0.50,
            default_val=0.28,
            step=0.02,
            decimals=2,
            tooltip="Schwellenwert zur Konturextraktion der chemischen Wellen.",
        )
        self.slider_rd_level.sig_value_changed.connect(self._emit_param_change)
        rd_layout.addWidget(self.slider_rd_level)
        layout.addWidget(self.widget_rd_opts)

        # --- Voronoi Stippling controls ---
        self.widget_stippling_opts = QWidget()
        st_layout = QVBoxLayout(self.widget_stippling_opts)
        st_layout.setContentsMargins(0, 0, 0, 0)
        st_layout.setSpacing(4)

        self.slider_stippling_points = SliderRow(
            title="Stipple-Punkte:",
            min_val=200,
            max_val=5000,
            default_val=1500,
            step=50,
            tooltip="Gesamtzahl der Punkte im Stippling.",
        )
        self.slider_stippling_points.sig_value_changed.connect(self._emit_param_change)
        st_layout.addWidget(self.slider_stippling_points)

        self.slider_stippling_passes = SliderRow(
            title="Lloyd-Relaxationsrunden:",
            min_val=1,
            max_val=15,
            default_val=6,
            step=1,
            tooltip="Iterationen zur harmonischen Punktverteilung (Centroidal Voronoi).",
        )
        self.slider_stippling_passes.sig_value_changed.connect(self._emit_param_change)
        st_layout.addWidget(self.slider_stippling_passes)

        self.slider_stippling_min_r = SliderRow(
            title="Min. Punktradius:",
            min_val=0.2,
            max_val=3.0,
            default_val=0.8,
            step=0.1,
            decimals=1,
            suffix="px",
            tooltip="Radius in hellen Bereichen.",
        )
        self.slider_stippling_min_r.sig_value_changed.connect(self._emit_param_change)
        st_layout.addWidget(self.slider_stippling_min_r)

        self.slider_stippling_max_r = SliderRow(
            title="Max. Punktradius:",
            min_val=1.0,
            max_val=6.0,
            default_val=3.0,
            step=0.2,
            decimals=1,
            suffix="px",
            tooltip="Radius in dunklen Schattenbereichen.",
        )
        self.slider_stippling_max_r.sig_value_changed.connect(self._emit_param_change)
        st_layout.addWidget(self.slider_stippling_max_r)

        self.chk_stippling_size_dark = QCheckBox("Punktgröße an Bildhelligkeit anpassen")
        self.chk_stippling_size_dark.setChecked(True)
        self.chk_stippling_size_dark.stateChanged.connect(self._emit_param_change)
        st_layout.addWidget(self.chk_stippling_size_dark)
        layout.addWidget(self.widget_stippling_opts)

        # --- Stroke-Based Rendering (SBR) controls ---
        self.widget_sbr_opts = QWidget()
        sbr_layout = QVBoxLayout(self.widget_sbr_opts)
        sbr_layout.setContentsMargins(0, 0, 0, 0)
        sbr_layout.setSpacing(4)

        self.slider_sbr_strokes = SliderRow(
            title="Pinselstrich-Anzahl:",
            min_val=200,
            max_val=6000,
            default_val=1500,
            step=50,
            tooltip="Anzahl parametrischer Bézier-Pinselstriche.",
        )
        self.slider_sbr_strokes.sig_value_changed.connect(self._emit_param_change)
        sbr_layout.addWidget(self.slider_sbr_strokes)

        self.slider_sbr_length = SliderRow(
            title="Strichlänge (Basis):",
            min_val=5.0,
            max_val=40.0,
            default_val=16.0,
            step=1.0,
            decimals=1,
            suffix="px",
            tooltip="Durchschnittliche Länge der Pinselstriche.",
        )
        self.slider_sbr_length.sig_value_changed.connect(self._emit_param_change)
        sbr_layout.addWidget(self.slider_sbr_length)

        self.slider_sbr_curv = SliderRow(
            title="Biegung / Kantenfluss:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.65,
            step=0.05,
            decimals=2,
            tooltip="Wie stark Striche dem Richtungsfeld der Konturen folgen.",
        )
        self.slider_sbr_curv.sig_value_changed.connect(self._emit_param_change)
        sbr_layout.addWidget(self.slider_sbr_curv)

        sbr_layout.addWidget(QLabel("Strich-Ausrichtung:"))
        self.combo_sbr_align = QComboBox()
        self.combo_sbr_align.addItems([
            "Tangente (Kantenfluss / Gravur)",
            "Kreuzend (Schraffur / Querfluss)",
        ])
        self.combo_sbr_align.currentIndexChanged.connect(self._emit_param_change)
        sbr_layout.addWidget(self.combo_sbr_align)
        layout.addWidget(self.widget_sbr_opts)

        # --- Marching Squares / Isocontour controls ---
        self.widget_iso_opts = QWidget()
        iso_layout = QVBoxLayout(self.widget_iso_opts)
        iso_layout.setContentsMargins(0, 0, 0, 0)
        iso_layout.setSpacing(4)

        self.slider_iso_levels = SliderRow(
            title="Höhenschichten (Isolinien):",
            min_val=3,
            max_val=40,
            default_val=12,
            step=1,
            tooltip="Anzahl der Helligkeitsstufen für Iso-Höhenlinien.",
        )
        self.slider_iso_levels.sig_value_changed.connect(self._emit_param_change)
        iso_layout.addWidget(self.slider_iso_levels)

        self.slider_iso_min_length = SliderRow(
            title="Minimale Linienlänge:",
            min_val=2,
            max_val=50,
            default_val=8,
            step=1,
            suffix="px",
            tooltip="Filtert winzige Iso-Kreise und Fragmente heraus.",
        )
        self.slider_iso_min_length.sig_value_changed.connect(self._emit_param_change)
        iso_layout.addWidget(self.slider_iso_min_length)

        self.chk_iso_smooth = QCheckBox("Bézier-Glättung der Isolinien")
        self.chk_iso_smooth.setChecked(True)
        self.chk_iso_smooth.stateChanged.connect(self._emit_param_change)
        iso_layout.addWidget(self.chk_iso_smooth)
        layout.addWidget(self.widget_iso_opts)

        # --- Physarum (Slime Mold) controls ---
        self.widget_physarum_opts = QWidget()
        phy_layout = QVBoxLayout(self.widget_physarum_opts)
        phy_layout.setContentsMargins(0, 0, 0, 0)
        phy_layout.setSpacing(4)

        self.slider_physarum_agents = SliderRow(
            title="Partikel-Anzahl (Agenten):",
            min_val=200,
            max_val=3000,
            default_val=1000,
            step=50,
            tooltip="Anzahl autonomer Schleimpilz-Agenten.",
        )
        self.slider_physarum_agents.sig_value_changed.connect(self._emit_param_change)
        phy_layout.addWidget(self.slider_physarum_agents)

        self.slider_physarum_steps = SliderRow(
            title="Simulations-Schritte:",
            min_val=10,
            max_val=120,
            default_val=40,
            step=5,
            tooltip="Dauer des Schleimpilz-Wachstums.",
        )
        self.slider_physarum_steps.sig_value_changed.connect(self._emit_param_change)
        phy_layout.addWidget(self.slider_physarum_steps)

        self.slider_physarum_decay = SliderRow(
            title="Spur-Verblassung (Decay):",
            min_val=0.50,
            max_val=0.99,
            default_val=0.90,
            step=0.01,
            decimals=2,
            tooltip="Verdunstungsrate der Pheromon-Spurkarte je Schritt.",
        )
        self.slider_physarum_decay.sig_value_changed.connect(self._emit_param_change)
        phy_layout.addWidget(self.slider_physarum_decay)

        self.slider_physarum_sensor_angle = SliderRow(
            title="Sensor-Winkel:",
            min_val=10.0,
            max_val=60.0,
            default_val=22.5,
            step=2.5,
            decimals=1,
            suffix="°",
            tooltip="Erkennungswinkel der Agentensensoren.",
        )
        self.slider_physarum_sensor_angle.sig_value_changed.connect(self._emit_param_change)
        phy_layout.addWidget(self.slider_physarum_sensor_angle)
        layout.addWidget(self.widget_physarum_opts)

        # --- String-Art controls ---
        self.widget_string_opts = QWidget()
        str_layout = QVBoxLayout(self.widget_string_opts)
        str_layout.setContentsMargins(0, 0, 0, 0)
        str_layout.setSpacing(4)

        self.slider_string_pins = SliderRow(
            title="Rand-Pins (Nägel):",
            min_val=60,
            max_val=360,
            default_val=180,
            step=10,
            tooltip="Anzahl Nägel entlang des Randes.",
        )
        self.slider_string_pins.sig_value_changed.connect(self._emit_param_change)
        str_layout.addWidget(self.slider_string_pins)

        self.slider_string_lines = SliderRow(
            title="Faden-Iterationen (Sehnen):",
            min_val=200,
            max_val=3500,
            default_val=1200,
            step=50,
            tooltip="Gesamtzahl gespannter Fadensegmente.",
        )
        self.slider_string_lines.sig_value_changed.connect(self._emit_param_change)
        str_layout.addWidget(self.slider_string_lines)

        self.slider_string_opacity = SliderRow(
            title="Fadendichte / Abzug:",
            min_val=0.05,
            max_val=0.50,
            default_val=0.18,
            step=0.01,
            decimals=2,
            tooltip="Subtraktionsgewicht je gespannter Fadenlinie.",
        )
        self.slider_string_opacity.sig_value_changed.connect(self._emit_param_change)
        str_layout.addWidget(self.slider_string_opacity)

        str_layout.addWidget(QLabel("Rahmenform:"))
        self.combo_string_shape = QComboBox()
        self.combo_string_shape.addItems(["Kreis", "Quadrat"])
        self.combo_string_shape.currentIndexChanged.connect(self._emit_param_change)
        str_layout.addWidget(self.combo_string_shape)
        layout.addWidget(self.widget_string_opts)

        # --- Differential Growth controls ---
        self.widget_diffgrowth_opts = QWidget()
        diff_layout = QVBoxLayout(self.widget_diffgrowth_opts)
        diff_layout.setContentsMargins(0, 0, 0, 0)
        diff_layout.setSpacing(4)

        self.slider_diffgrowth_iter = SliderRow(
            title="Wachstums-Iterationen:",
            min_val=10,
            max_val=150,
            default_val=50,
            step=5,
            tooltip="Anzahl Schritte differentieller Knotenteilung.",
        )
        self.slider_diffgrowth_iter.sig_value_changed.connect(self._emit_param_change)
        diff_layout.addWidget(self.slider_diffgrowth_iter)

        self.slider_diffgrowth_nodes = SliderRow(
            title="Max. Knotenanzahl:",
            min_val=100,
            max_val=2000,
            default_val=600,
            step=50,
            tooltip="Maximale Anzahl Linienknoten bevor das Wachstum stoppt.",
        )
        self.slider_diffgrowth_nodes.sig_value_changed.connect(self._emit_param_change)
        diff_layout.addWidget(self.slider_diffgrowth_nodes)

        self.slider_diffgrowth_feed = SliderRow(
            title="Kanten-Teilung (Wachstumsdrang):",
            min_val=3.0,
            max_val=25.0,
            default_val=10.0,
            step=1.0,
            decimals=1,
            suffix="px",
            tooltip="Abstand, ab dem Kanten geteilt werden.",
        )
        self.slider_diffgrowth_feed.sig_value_changed.connect(self._emit_param_change)
        diff_layout.addWidget(self.slider_diffgrowth_feed)

        self.slider_diffgrowth_repulsion = SliderRow(
            title="Abstoßungs-Radius (Kollision):",
            min_val=4.0,
            max_val=30.0,
            default_val=12.0,
            step=1.0,
            decimals=1,
            suffix="px",
            tooltip="Mindestabstand zwischen Knoten zur Vermeidung von Selbstüberschneidungen.",
        )
        self.slider_diffgrowth_repulsion.sig_value_changed.connect(self._emit_param_change)
        diff_layout.addWidget(self.slider_diffgrowth_repulsion)
        layout.addWidget(self.widget_diffgrowth_opts)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)
        self._on_artistic_mode_changed(0)

    def _on_artistic_mode_changed(self, idx: int) -> None:
        """Update visibility of sub-controls according to selected artistic mode."""
        self.widget_waveform_opts.setVisible(idx == 1)
        self.widget_spiral_opts.setVisible(idx == 2)
        self.widget_tsp_opts.setVisible(idx == 3)
        self.widget_delaunay_opts.setVisible(idx == 4)
        self.widget_flow_opts.setVisible(idx == 5)
        self.widget_voronoi_opts.setVisible(idx == 6)
        self.widget_rd_opts.setVisible(idx == 7)
        self.widget_stippling_opts.setVisible(idx == 8)
        self.widget_sbr_opts.setVisible(idx == 9)
        if hasattr(self, "widget_iso_opts"):
            self.widget_iso_opts.setVisible(idx == 10)
        if hasattr(self, "widget_physarum_opts"):
            self.widget_physarum_opts.setVisible(idx == 11)
        if hasattr(self, "widget_string_opts"):
            self.widget_string_opts.setVisible(idx == 12)
        if hasattr(self, "widget_diffgrowth_opts"):
            self.widget_diffgrowth_opts.setVisible(idx == 13)
        self.chk_artistic_overlay.setVisible(idx > 0)
        self._emit_param_change()

    def _build_hatching_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        box = QGroupBox("Schraffur (Hatching) für Schatten")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.chk_hatching = QCheckBox("Schraffur für dunkle Flächen aktivieren")
        self.chk_hatching.setChecked(False)
        self.chk_hatching.stateChanged.connect(self._on_hatching_toggled)
        layout.addWidget(self.chk_hatching)

        self.widget_hatching_opts = QWidget()
        h_layout = QVBoxLayout(self.widget_hatching_opts)
        h_layout.setContentsMargins(0, 2, 0, 0)
        h_layout.setSpacing(6)

        h_layout.addWidget(QLabel("Schraffurstil:"))
        self.combo_hatch_mode = QComboBox()
        self.combo_hatch_mode.addItems([
            "Glatte Bézier-Kurven (Formfolgend)",
            "Gerade Striche (Klassisch)",
        ])
        self.combo_hatch_mode.currentIndexChanged.connect(self._emit_param_change)
        h_layout.addWidget(self.combo_hatch_mode)

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
        h_layout.addWidget(self.slider_hatch_curve)

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
        h_layout.addWidget(self.slider_hatch_wobble)

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
        h_layout.addWidget(self.slider_hatch_thresh)

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
        h_layout.addWidget(self.slider_hatch_spacing)

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
        h_layout.addWidget(self.slider_hatch_angle)

        self.chk_cross_hatch = QCheckBox("Kreuzschraffur für tiefe Schatten")
        self.chk_cross_hatch.setChecked(False)
        self.chk_cross_hatch.stateChanged.connect(self._emit_param_change)
        h_layout.addWidget(self.chk_cross_hatch)

        layout.addWidget(self.widget_hatching_opts)
        self.widget_hatching_opts.setVisible(False)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    # Mapping lists for shape type and rotation mode combo boxes
    _SHAPE_TYPE_VALUES = [
        "dots", "circles", "rects", "triangles", "lines",
        "stars", "diamonds", "hexagons", "spirals", "hearts", "ascii",
    ]
    _ROTATION_MODE_VALUES = ["none", "random", "gradient", "mixed"]

    def _build_shapes_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
        """Build the Shapes mode control section."""
        box = QGroupBox("✨ Formen-Modus (Shapes)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Enable toggle
        self.chk_shapes = QCheckBox("Formen-Modus aktivieren")
        self.chk_shapes.setChecked(False)
        self.chk_shapes.stateChanged.connect(self._on_shapes_toggled)
        layout.addWidget(self.chk_shapes)

        self.widget_shapes_opts = QWidget()
        s_layout = QVBoxLayout(self.widget_shapes_opts)
        s_layout.setContentsMargins(0, 2, 0, 0)
        s_layout.setSpacing(6)

        # Shape type
        s_layout.addWidget(QLabel("Formtyp:"))
        self.combo_shape_type = QComboBox()
        self.combo_shape_type.addItems([
            "Punkte (Dots)", "Kreise (Kontur)", "Rechtecke",
            "Dreiecke", "Linien-Segmente", "Sterne", "Rauten",
            "Hexagons", "Spiralen", "Herzen", "ASCII-Zeichen",
        ])
        self.combo_shape_type.currentIndexChanged.connect(self._on_shape_type_changed)
        s_layout.addWidget(self.combo_shape_type)

        # ASCII charset (only visible for ASCII mode)
        self.lbl_ascii_charset = QLabel("Zeichensatz (dunkel → hell):")
        self.edit_ascii_charset = QLineEdit("@#S%?*+;:,. ")
        self.edit_ascii_charset.textChanged.connect(self._emit_param_change)
        s_layout.addWidget(self.lbl_ascii_charset)
        s_layout.addWidget(self.edit_ascii_charset)
        self.lbl_ascii_charset.setVisible(False)
        self.edit_ascii_charset.setVisible(False)

        # Placement
        s_layout.addWidget(QLabel("Platzierung:"))
        self.combo_shape_placement = QComboBox()
        self.combo_shape_placement.addItems(["Raster (Grid)", "Zufällig (Random)"])
        self.combo_shape_placement.currentIndexChanged.connect(self._emit_param_change)
        s_layout.addWidget(self.combo_shape_placement)

        # Size sliders
        self.slider_shape_min_size = SliderRow(
            title="Min. Größe (helle Bereiche):",
            min_val=1.0,
            max_val=30.0,
            default_val=2.0,
            step=0.5,
            decimals=1,
            suffix="px",
            tooltip="Minimale Formgröße in hellen Bildbereichen.",
        )
        self.slider_shape_min_size.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_shape_min_size)

        self.slider_shape_max_size = SliderRow(
            title="Max. Größe (dunkle Bereiche):",
            min_val=2.0,
            max_val=60.0,
            default_val=20.0,
            step=1.0,
            decimals=0,
            suffix="px",
            tooltip="Maximale Formgröße in dunklen Bildbereichen.",
        )
        self.slider_shape_max_size.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_shape_max_size)

        # Density
        self.slider_shape_density = SliderRow(
            title="Dichte:",
            min_val=0.1,
            max_val=2.0,
            default_val=0.6,
            step=0.05,
            decimals=2,
            tooltip="Anzahl der Formen pro Fläche. Höherer Wert = dichter.",
        )
        self.slider_shape_density.sig_value_changed.connect(self._emit_param_change)
        s_layout.addWidget(self.slider_shape_density)

        # Brightness-driven size and density
        self.chk_shape_size_by_bright = QCheckBox("Größe nach Helligkeit (dunkel = groß)")
        self.chk_shape_size_by_bright.setChecked(True)
        self.chk_shape_size_by_bright.stateChanged.connect(self._emit_param_change)
        s_layout.addWidget(self.chk_shape_size_by_bright)

        self.chk_shape_density_by_bright = QCheckBox("Dichte nach Helligkeit (dunkel = mehr)")
        self.chk_shape_density_by_bright.setChecked(True)
        self.chk_shape_density_by_bright.stateChanged.connect(self._emit_param_change)
        s_layout.addWidget(self.chk_shape_density_by_bright)

        # Rotation mode
        s_layout.addWidget(QLabel("Rotationsmodus:"))
        self.combo_shape_rotation = QComboBox()
        self.combo_shape_rotation.addItems([
            "Keine Rotation", "Zufällig", "Gradientenausgerichtet", "Gemischt",
        ])
        self.combo_shape_rotation.setCurrentIndex(1)  # default: random
        self.combo_shape_rotation.currentIndexChanged.connect(self._on_shape_rotation_changed)
        s_layout.addWidget(self.combo_shape_rotation)

        self.slider_shape_gradient_align = SliderRow(
            title="Gradient-Einfluss:",
            min_val=0.0,
            max_val=1.0,
            default_val=0.5,
            step=0.05,
            decimals=2,
            tooltip="0 = rein zufällig, 1 = vollständig gradientenausgerichtet (nur im Gemischt-Modus).",
        )
        self.slider_shape_gradient_align.sig_value_changed.connect(self._emit_param_change)
        self.slider_shape_gradient_align.setVisible(False)
        s_layout.addWidget(self.slider_shape_gradient_align)

        # Randomize button inside shapes
        self.btn_randomize = QPushButton("🎲  Alle Einstellungen zufällig würfeln")
        self.btn_randomize.setObjectName("randomizeButton")
        self.btn_randomize.setToolTip(
            "Setzt ALLE Parameter (Vorverarbeitung, Linien, Zeichenstil, Schraffur, Formen und Strichstärke) auf zufällige, erlaubte Werte und berechnet die Vorschau neu."
        )
        self.btn_randomize.clicked.connect(self._randomize_all_params)
        s_layout.addWidget(self.btn_randomize)

        layout.addWidget(self.widget_shapes_opts)
        self.widget_shapes_opts.setVisible(False)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _on_shapes_toggled(self, state: int) -> None:
        """Progressive disclosure for shapes options."""
        if hasattr(self, "widget_shapes_opts"):
            self.widget_shapes_opts.setVisible(self.chk_shapes.isChecked())
        self._emit_param_change()

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
        from ..core.randomizer import generate_random_parameters
        new_params = generate_random_parameters()
        # Preserve current image file paths and preview resolution
        new_params.input_path = self.params.input_path
        new_params.output_path = self.params.output_path
        new_params.preview_max_dim = self.params.preview_max_dim
        self.apply_parameters(new_params)
        self._emit_param_change()

    def _randomize_shape_params(self) -> None:
        """Alias for _randomize_all_params."""
        self._randomize_all_params()

    def _build_page_export_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
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
        self.chk_tsp.stateChanged.connect(self._on_tsp_toggled)
        layout.addWidget(self.chk_tsp)

        # 2-opt Verfeinerung: nur sinnvoll und sichtbar, wenn die
        # Wegoptimierung selbst aktiv ist. Deutlich langsamer, daher
        # standardmäßig deaktiviert und nur für den finalen Export gedacht.
        self.chk_two_opt = AccessibleCheckBox("2-opt Feinoptimierung (langsamer, kürzere Leerwege)")
        self.chk_two_opt.setChecked(False)
        self.chk_two_opt.setEnabled(False)
        self.chk_two_opt.setVisible(False)
        self.chk_two_opt.setToolTip(
            "Verfeinert die sortierten Pfade zusätzlich per 2-opt.\n"
            "Reduziert Leerfahrten weiter, kann bei vielen Linien aber\n"
            "spürbar länger dauern. Für die Live-Vorschau nicht empfohlen."
        )
        self.chk_two_opt.stateChanged.connect(self._emit_param_change)
        layout.addWidget(self.chk_two_opt)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
            self.layout_content.addWidget(box)

    def _build_stats_section(self, parent_layout: Optional[QVBoxLayout] = None) -> None:
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

        layout.addWidget(QLabel("Kunststil-Pfade:"), 3, 0)
        self.lbl_stat_artistic = QLabel("0")
        self.lbl_stat_artistic.setStyleSheet("color: #ec4899; font-weight: bold;")
        layout.addWidget(self.lbl_stat_artistic, 3, 1)

        layout.addWidget(QLabel("Zeichenlänge gesamt:"), 4, 0)
        self.lbl_stat_len = QLabel("0.0 m")
        self.lbl_stat_len.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_len, 4, 1)

        layout.addWidget(QLabel("Leerweg (Pen-Up):"), 5, 0)
        self.lbl_stat_penup = QLabel("0.0 m")
        self.lbl_stat_penup.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_penup, 5, 1)

        layout.addWidget(QLabel("Berechnungsdauer:"), 6, 0)
        self.lbl_stat_time = QLabel("0.0 s")
        self.lbl_stat_time.setStyleSheet("color: #38bdf8; font-weight: bold;")
        layout.addWidget(self.lbl_stat_time, 6, 1)

        if parent_layout is not None:
            parent_layout.addWidget(box)
        elif hasattr(self, "layout_content"):
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
        p.use_kuwahara = self.chk_kuwahara.isChecked()
        p.kuwahara_radius = int(self.slider_kuwahara_r.get_value())
        if hasattr(self, "combo_kuwahara_mode"):
            p.kuwahara_mode = "anisotropic" if self.combo_kuwahara_mode.currentIndex() == 1 else "classic"
            p.kuwahara_anisotropy = self.slider_kuwahara_anisotropy.get_value()

        # Preprocessing filter: Quadtree & Pixel Sorting & FFT & CA
        if hasattr(self, "chk_quadtree"):
            p.use_quadtree = self.chk_quadtree.isChecked()
            p.quadtree_threshold = self.slider_quadtree_thresh.get_value()
            p.quadtree_min_size = int(self.slider_quadtree_min_size.get_value())
            p.quadtree_render_boxes = self.chk_quadtree_render_boxes.isChecked()

        if hasattr(self, "chk_pixel_sort"):
            p.use_pixel_sort = self.chk_pixel_sort.isChecked()
            p.pixel_sort_direction = "horizontal" if self.combo_pixel_sort_dir.currentIndex() == 0 else "vertical"
            p.pixel_sort_lower_thresh = self.slider_pixel_sort_lower.get_value()
            p.pixel_sort_upper_thresh = self.slider_pixel_sort_upper.get_value()
            p.pixel_sort_reverse = self.chk_pixel_sort_rev.isChecked()

        if hasattr(self, "chk_fft"):
            p.use_fft = self.chk_fft.isChecked()
            fft_types = ["moiré", "bandpass", "interference", "highpass"]
            f_idx = self.combo_fft_type.currentIndex()
            p.fft_mode = fft_types[f_idx] if 0 <= f_idx < len(fft_types) else "moiré"
            p.fft_frequency = self.slider_fft_freq.get_value()
            p.fft_strength = self.slider_fft_amount.get_value()

        if hasattr(self, "chk_ca"):
            p.use_ca = self.chk_ca.isChecked()
            p.ca_iterations = int(self.slider_ca_steps.get_value())
            p.ca_states = int(self.slider_ca_states.get_value())
            p.ca_threshold = int(self.slider_ca_threshold.get_value())

        # Artistic mode
        a_idx = self.combo_artistic_mode.currentIndex()
        p.artistic_mode = self._ARTISTIC_MODE_VALUES[a_idx] if 0 <= a_idx < len(self._ARTISTIC_MODE_VALUES) else "none"
        p.artistic_overlay_contours = self.chk_artistic_overlay.isChecked()
        p.waveform_lines = int(self.slider_wave_lines.get_value())
        p.waveform_amplitude = self.slider_wave_amp.get_value()
        p.waveform_occlusion = self.chk_wave_occlusion.isChecked()
        p.spiral_loops = int(self.slider_spiral_loops.get_value())
        p.spiral_amplitude = self.slider_spiral_amp.get_value()
        p.spiral_frequency = self.slider_spiral_freq.get_value()
        p.tsp_points = int(self.slider_tsp_points.get_value())
        p.tsp_2opt_passes = int(self.slider_tsp_passes.get_value())
        p.delaunay_points = int(self.slider_delaunay_points.get_value())
        p.delaunay_edge_weight = self.slider_delaunay_weight.get_value()
        p.flowfield_lines = int(self.slider_flow_lines.get_value())
        p.flowfield_max_steps = int(self.slider_flow_steps.get_value())
        p.flowfield_direction = "tangent" if self.combo_flow_dir.currentIndex() == 0 else "gradient"

        if hasattr(self, "slider_voronoi_points"):
            p.voronoi_points = int(self.slider_voronoi_points.get_value())
            p.voronoi_edge_weight = self.slider_voronoi_weight.get_value()

        if hasattr(self, "slider_rd_res"):
            p.rd_sim_resolution = int(self.slider_rd_res.get_value())
            p.rd_iterations = int(self.slider_rd_iter.get_value())
            p.rd_feed_rate = self.slider_rd_feed.get_value()
            p.rd_kill_rate = self.slider_rd_kill.get_value()
            p.rd_contour_level = self.slider_rd_level.get_value()

        if hasattr(self, "slider_stippling_points"):
            p.stippling_points = int(self.slider_stippling_points.get_value())
            p.stippling_lloyd_passes = int(self.slider_stippling_passes.get_value())
            p.stippling_min_radius = self.slider_stippling_min_r.get_value()
            p.stippling_max_radius = self.slider_stippling_max_r.get_value()
            p.stippling_size_by_darkness = self.chk_stippling_size_dark.isChecked()

        if hasattr(self, "slider_sbr_strokes"):
            p.sbr_strokes = int(self.slider_sbr_strokes.get_value())
            p.sbr_length = self.slider_sbr_length.get_value()
            p.sbr_curvature = self.slider_sbr_curv.get_value()
            p.sbr_align_mode = "tangent" if self.combo_sbr_align.currentIndex() == 0 else "cross"

        if hasattr(self, "slider_iso_levels"):
            p.iso_levels = int(self.slider_iso_levels.get_value())

        if hasattr(self, "slider_physarum_agents"):
            p.physarum_agents = int(self.slider_physarum_agents.get_value())
            p.physarum_iterations = int(self.slider_physarum_steps.get_value())
            p.physarum_decay = self.slider_physarum_decay.get_value()
            p.physarum_sensor_angle = self.slider_physarum_sensor_angle.get_value()

        if hasattr(self, "slider_string_pins"):
            p.string_pins = int(self.slider_string_pins.get_value())
            p.string_max_lines = int(self.slider_string_lines.get_value())
            p.string_weight = self.slider_string_opacity.get_value()
            p.string_shape = "circle" if self.combo_string_shape.currentIndex() == 0 else "rectangle"

        if hasattr(self, "slider_diffgrowth_iter"):
            p.diffgrowth_iterations = int(self.slider_diffgrowth_iter.get_value())
            p.diffgrowth_max_nodes = int(self.slider_diffgrowth_nodes.get_value())
            p.diffgrowth_split_dist = self.slider_diffgrowth_feed.get_value()
            p.diffgrowth_collision_r = self.slider_diffgrowth_repulsion.get_value()

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
        p.two_opt = self.chk_two_opt.isChecked() and p.sort_paths

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
        self.chk_kuwahara.setChecked(p.use_kuwahara)
        self.slider_kuwahara_r.set_value(p.kuwahara_radius)
        if hasattr(self, "combo_kuwahara_mode"):
            self.combo_kuwahara_mode.setCurrentIndex(1 if p.kuwahara_mode == "anisotropic" else 0)
            self.slider_kuwahara_anisotropy.set_value(p.kuwahara_anisotropy)

        if hasattr(self, "chk_quadtree"):
            self.chk_quadtree.setChecked(p.use_quadtree)
            self.slider_quadtree_thresh.set_value(p.quadtree_threshold)
            self.slider_quadtree_min_size.set_value(p.quadtree_min_size)
            self.chk_quadtree_render_boxes.setChecked(p.quadtree_render_boxes)

        if hasattr(self, "chk_pixel_sort"):
            self.chk_pixel_sort.setChecked(p.use_pixel_sort)
            self.combo_pixel_sort_dir.setCurrentIndex(0 if p.pixel_sort_direction == "horizontal" else 1)
            self.slider_pixel_sort_lower.set_value(p.pixel_sort_lower_thresh)
            self.slider_pixel_sort_upper.set_value(p.pixel_sort_upper_thresh)
            self.chk_pixel_sort_rev.setChecked(p.pixel_sort_reverse)

        if hasattr(self, "chk_fft"):
            self.chk_fft.setChecked(getattr(p, "use_fft", False))
            fft_types = ["moiré", "bandpass", "interference", "highpass"]
            cur_mode = getattr(p, "fft_mode", "moiré")
            try:
                f_idx = fft_types.index(cur_mode)
            except ValueError:
                f_idx = 0
            self.combo_fft_type.setCurrentIndex(f_idx)
            self.slider_fft_freq.set_value(getattr(p, "fft_frequency", 12.0))
            self.slider_fft_amount.set_value(getattr(p, "fft_strength", 0.75))

        if hasattr(self, "chk_ca"):
            self.chk_ca.setChecked(getattr(p, "use_ca", False))
            self.slider_ca_steps.set_value(getattr(p, "ca_iterations", 20))
            self.slider_ca_states.set_value(getattr(p, "ca_states", 8))
            self.slider_ca_threshold.set_value(getattr(p, "ca_threshold", 1))

        # Artistic mode
        try:
            art_idx = self._ARTISTIC_MODE_VALUES.index(p.artistic_mode.lower())
        except ValueError:
            art_idx = 0
        self.combo_artistic_mode.setCurrentIndex(art_idx)
        self.chk_artistic_overlay.setChecked(p.artistic_overlay_contours)
        self.slider_wave_lines.set_value(p.waveform_lines)
        self.slider_wave_amp.set_value(p.waveform_amplitude)
        self.chk_wave_occlusion.setChecked(p.waveform_occlusion)
        self.slider_spiral_loops.set_value(p.spiral_loops)
        self.slider_spiral_amp.set_value(p.spiral_amplitude)
        self.slider_spiral_freq.set_value(p.spiral_frequency)
        self.slider_tsp_points.set_value(p.tsp_points)
        self.slider_tsp_passes.set_value(p.tsp_2opt_passes)
        self.slider_delaunay_points.set_value(p.delaunay_points)
        self.slider_delaunay_weight.set_value(p.delaunay_edge_weight)
        self.slider_flow_lines.set_value(p.flowfield_lines)
        self.slider_flow_steps.set_value(p.flowfield_max_steps)
        self.combo_flow_dir.setCurrentIndex(0 if p.flowfield_direction == "tangent" else 1)

        if hasattr(self, "slider_voronoi_points"):
            self.slider_voronoi_points.set_value(p.voronoi_points)
            self.slider_voronoi_weight.set_value(p.voronoi_edge_weight)

        if hasattr(self, "slider_rd_res"):
            self.slider_rd_res.set_value(p.rd_sim_resolution)
            self.slider_rd_iter.set_value(p.rd_iterations)
            self.slider_rd_feed.set_value(p.rd_feed_rate)
            self.slider_rd_kill.set_value(p.rd_kill_rate)
            self.slider_rd_level.set_value(p.rd_contour_level)

        if hasattr(self, "slider_stippling_points"):
            self.slider_stippling_points.set_value(p.stippling_points)
            self.slider_stippling_passes.set_value(p.stippling_lloyd_passes)
            self.slider_stippling_min_r.set_value(p.stippling_min_radius)
            self.slider_stippling_max_r.set_value(p.stippling_max_radius)
            self.chk_stippling_size_dark.setChecked(p.stippling_size_by_darkness)

        if hasattr(self, "slider_sbr_strokes"):
            self.slider_sbr_strokes.set_value(p.sbr_strokes)
            self.slider_sbr_length.set_value(p.sbr_length)
            self.slider_sbr_curv.set_value(p.sbr_curvature)
            self.combo_sbr_align.setCurrentIndex(0 if p.sbr_align_mode == "tangent" else 1)

        if hasattr(self, "slider_iso_levels"):
            self.slider_iso_levels.set_value(getattr(p, "iso_levels", 16))

        if hasattr(self, "slider_physarum_agents"):
            self.slider_physarum_agents.set_value(getattr(p, "physarum_agents", 1500))
            self.slider_physarum_steps.set_value(getattr(p, "physarum_iterations", 40))
            self.slider_physarum_decay.set_value(getattr(p, "physarum_decay", 0.90))
            self.slider_physarum_sensor_angle.set_value(getattr(p, "physarum_sensor_angle", 30.0))

        if hasattr(self, "slider_string_pins"):
            self.slider_string_pins.set_value(getattr(p, "string_pins", 240))
            self.slider_string_lines.set_value(getattr(p, "string_max_lines", 1500))
            self.slider_string_opacity.set_value(getattr(p, "string_weight", 0.18))
            self.combo_string_shape.setCurrentIndex(0 if getattr(p, "string_shape", "circle") == "circle" else 1)

        if hasattr(self, "slider_diffgrowth_iter"):
            self.slider_diffgrowth_iter.set_value(getattr(p, "diffgrowth_iterations", 50))
            self.slider_diffgrowth_nodes.set_value(getattr(p, "diffgrowth_max_nodes", 1400))
            self.slider_diffgrowth_feed.set_value(getattr(p, "diffgrowth_split_dist", 5.0))
            self.slider_diffgrowth_repulsion.set_value(getattr(p, "diffgrowth_collision_r", 6.0))

        self._on_artistic_mode_changed(art_idx)

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
        self.chk_two_opt.setEnabled(p.sort_paths)
        self.chk_two_opt.setVisible(p.sort_paths)
        self.chk_two_opt.setChecked(p.two_opt)

        # Progressive disclosure visibility updates
        self._on_filter_toggled()
        if hasattr(self, "widget_hatching_opts"):
            self.widget_hatching_opts.setVisible(p.use_hatching)
        if hasattr(self, "widget_shapes_opts"):
            self.widget_shapes_opts.setVisible(p.use_shapes)

        self._block_signals = False
        self._update_accordion_badges()

    def update_statistics(self, stats: PlotStats) -> None:
        """Display computation statistics in the statistics panel."""
        self.lbl_stat_lines.setText(f"{stats.contour_strokes}")
        self.lbl_stat_hatch.setText(f"{stats.hatch_strokes}")
        self.lbl_stat_shapes.setText(f"{stats.shape_strokes}")
        self.lbl_stat_artistic.setText(f"{stats.artistic_strokes}")

        mm_per_px = 0.264583
        draw_m = (stats.total_length_px * mm_per_px) / 1000.0
        penup_m = (stats.pen_up_distance_px * mm_per_px) / 1000.0

        self.lbl_stat_len.setText(f"{draw_m:.2f} m ({int(stats.total_length_px)} px)")
        self.lbl_stat_penup.setText(f"{penup_m:.2f} m")
        self.lbl_stat_time.setText(f"{stats.elapsed_time_sec:.2f} s")

    def set_progress(self, fraction: float, msg: str) -> None:
        percent = max(0, min(100, int(round(fraction * 100))))
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(msg)
        if hasattr(self, "lbl_percent"):
            self.lbl_percent.setText(f"{percent}%")

    def set_computing_state(self, computing: bool) -> None:
        self.btn_calc.setEnabled(not computing)
        self.btn_cancel.setEnabled(computing)
        if not computing:
            self.progress_bar.setValue(100)
            if hasattr(self, "lbl_percent"):
                self.lbl_percent.setText("100%")

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
            self._update_accordion_badges()

            # Context-sensitive accordion expansion based on preset mode
            if hasattr(self, "acc_artistic"):
                if p.artistic_mode and p.artistic_mode != "none":
                    self.acc_artistic.set_expanded(True)
                elif p.use_shapes or p.use_hatching:
                    self.acc_contours.set_expanded(True)
                elif p.use_kuwahara:
                    self.acc_filter.set_expanded(True)
                elif p.sort_paths:
                    self.acc_plotter.set_expanded(True)

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
            self._update_tab_badges()
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
        if hasattr(self, "widget_hatching_opts"):
            self.widget_hatching_opts.setVisible(self.chk_hatching.isChecked())
        self._emit_param_change()

    def _on_tsp_toggled(self, state: int) -> None:
        """2-opt only makes sense on top of an already sorted path set."""
        enabled = self.chk_tsp.isChecked()
        self.chk_two_opt.setEnabled(enabled)
        self.chk_two_opt.setVisible(enabled)
        if not enabled:
            self.chk_two_opt.setChecked(False)
        self._update_tab_badges()