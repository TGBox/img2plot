"""
Preset Laboratory / Style Discovery tool for img2plot.
Allows users to batch-generate random parameter variations on a source image,
browse results in an interactive visual gallery, bookmark favorites,
and save chosen configurations as named presets for the main application.
"""

from __future__ import annotations
import math
import os
import sys
from typing import List, Optional, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal, QRectF, QSize, QPoint
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.engine import PlotEngine, EngineResult, StrokePath
from ..core.parameters import PlotParameters
from ..core.presets import save_user_preset
from ..core.randomizer import (
    ARTISTIC_MODES,
    NON_CLASSIC_ARTISTIC_MODES,
    generate_random_parameters,
    suggest_preset_name,
)
from .theme import DARK_STYLESHEET


def render_result_to_pixmap(
    result: EngineResult,
    stroke_color: str = "#18181b",
    target_size: int = 320,
    bg_color: str = "#ffffff",
) -> QPixmap:
    """Render EngineResult vector paths into a crisp anti-aliased thumbnail pixmap."""
    w, h = result.width, result.height
    if w <= 0 or h <= 0:
        empty = QImage(target_size, target_size, QImage.Format.Format_ARGB32_Premultiplied)
        empty.fill(QColor(bg_color))
        return QPixmap.fromImage(empty)

    scale = min((target_size - 16) / float(w), (target_size - 16) / float(h))
    pix_w = max(1, int(round(w * scale)))
    pix_h = max(1, int(round(h * scale)))

    img = QImage(target_size, target_size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(bg_color))

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    offset_x = (target_size - pix_w) / 2.0
    offset_y = (target_size - pix_h) / 2.0

    painter.translate(offset_x, offset_y)
    painter.scale(scale, scale)

    # Build QPainterPath
    v_path = QPainterPath()
    for stroke in result.paths:
        if stroke.is_bezier and stroke.cubic_segments:
            p1 = stroke.cubic_segments[0][0]
            v_path.moveTo(p1[0], p1[1])
            for _, c1, c2, p2 in stroke.cubic_segments:
                v_path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
        else:
            pts = stroke.points
            if len(pts) >= 2:
                v_path.moveTo(pts[0][0], pts[0][1])
                for pt in pts[1:]:
                    v_path.lineTo(pt[0], pt[1])
            elif len(pts) == 1:
                md = stroke.shape_metadata
                if md.get("type") == "circle":
                    r = float(md.get("r", 2.0))
                    v_path.addEllipse(pts[0][0] - r, pts[0][1] - r, r * 2, r * 2)
                else:
                    v_path.moveTo(pts[0][0] - 1, pts[0][1])
                    v_path.lineTo(pts[0][0] + 1, pts[0][1])

    pen = QPen(QColor(stroke_color))
    pen.setWidthF(max(0.7, 1.0 / math.sqrt(max(0.1, scale))))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(v_path)
    painter.end()

    return QPixmap.fromImage(img)


# -----------------------------------------------------------------------------
# Background Worker
# -----------------------------------------------------------------------------

class PresetLabWorker(QThread):
    """Background worker for batch-rendering randomized preset variations."""

    sig_progress = Signal(int, int, str)  # current, total, status_message
    sig_item_ready = Signal(int, object, object)  # index, PlotParameters, QPixmap
    sig_finished = Signal()
    sig_error = Signal(int, str)  # index, error_msg

    def __init__(
        self,
        image_path: str,
        param_list: List[PlotParameters],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.image_path = image_path
        self.param_list = param_list
        self._is_cancelled = False

    def cancel(self) -> None:
        """Request immediate thread cancellation."""
        self._is_cancelled = True

    def run(self) -> None:
        total = len(self.param_list)
        for idx, params in enumerate(self.param_list):
            if self._is_cancelled:
                break

            style_label = params.artistic_mode if params.artistic_mode != "none" else "Konturzeichnung"
            self.sig_progress.emit(
                idx + 1,
                total,
                f"Generiere Variante {idx + 1} von {total}: {style_label}...",
            )

            try:
                engine = PlotEngine(params)
                result = engine.process_image(
                    self.image_path,
                    is_cancelled=lambda: self._is_cancelled,
                    is_preview=True,
                )

                if self._is_cancelled:
                    break

                color = params.stroke_color if params.stroke_color else "#18181b"
                pixmap = render_result_to_pixmap(result, stroke_color=color, target_size=320)
                self.sig_item_ready.emit(idx, params, pixmap)

            except Exception as e:
                self.sig_error.emit(idx, str(e))

        self.sig_finished.emit()


# -----------------------------------------------------------------------------
# Zoom Dialog / Lightbox Modal
# -----------------------------------------------------------------------------

class ZoomModalDialog(QDialog):
    """High-resolution lightbox zoom modal for inspecting a rendered preset card."""

    def __init__(
        self,
        pixmap: QPixmap,
        params: PlotParameters,
        title: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Detailansicht - {title}")
        self.resize(780, 780)
        self.setStyleSheet(DARK_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Large image view in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 8px;")

        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img.setPixmap(pixmap.scaled(720, 720, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        scroll.setWidget(lbl_img)
        layout.addWidget(scroll, 1)

        # Info bar
        info_box = QFrame()
        info_box.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 6px;")
        info_layout = QHBoxLayout(info_box)
        info_layout.setContentsMargins(8, 4, 8, 4)

        mode_str = params.artistic_mode if params.artistic_mode != "none" else "Klassische Kontur"
        info_txt = f"<b>Stil:</b> {mode_str} | <b>Farbe:</b> {params.stroke_color} | <b>Strichstärke:</b> {params.stroke_width_mm} mm"
        if params.use_hatching:
            info_txt += " | <i>Schraffur aktiv</i>"
        if params.use_pixel_sort:
            info_txt += " | <i>Pixel-Sort aktiv</i>"
        if params.use_quadtree:
            info_txt += " | <i>Quadtree aktiv</i>"

        lbl_info = QLabel(info_txt)
        lbl_info.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        info_layout.addWidget(lbl_info)

        btn_close = QPushButton("Schließen")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        info_layout.addWidget(btn_close)

        layout.addWidget(info_box)


# -----------------------------------------------------------------------------
# Card Widget
# -----------------------------------------------------------------------------

class PresetCardWidget(QFrame):
    """Gallery card displaying a single randomized result with favorite toggle and zoom."""

    sig_favorite_toggled = Signal(int, bool)  # index, is_favorite

    def __init__(
        self,
        index: int,
        params: PlotParameters,
        pixmap: QPixmap,
        suggested_name: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.index = index
        self.params = params
        self.pixmap = pixmap
        self.suggested_name = suggested_name
        self.is_favorite = False

        self.setFixedSize(290, 360)
        self._setup_ui()
        self._update_appearance()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Image container with subtle dark paper border
        self.lbl_image = QLabel()
        self.lbl_image.setFixedSize(270, 260)
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: #ffffff; border-radius: 6px;")
        self.lbl_image.setPixmap(
            self.pixmap.scaled(260, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        self.lbl_image.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_image.mousePressEvent = lambda e: self._on_zoom_clicked()
        layout.addWidget(self.lbl_image)

        # Meta row: Style badge & zoom button
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        style_title = self.params.artistic_mode.upper() if self.params.artistic_mode != "none" else "KONTUR"
        self.lbl_badge = QLabel(f"  {style_title}  ")
        self.lbl_badge.setStyleSheet(
            "background-color: #27272a; color: #38bdf8; font-size: 11px; font-weight: bold; border-radius: 4px; padding: 2px;"
        )
        meta_row.addWidget(self.lbl_badge)

        meta_row.addStretch()

        self.btn_zoom = QPushButton("🔍")
        self.btn_zoom.setFixedSize(28, 24)
        self.btn_zoom.setToolTip("Großansicht anzeigen")
        self.btn_zoom.clicked.connect(self._on_zoom_clicked)
        meta_row.addWidget(self.btn_zoom)

        layout.addLayout(meta_row)

        # Title / Suggested Name
        self.lbl_name = QLabel(self.suggested_name)
        self.lbl_name.setStyleSheet("font-weight: bold; color: #f4f4f5; font-size: 13px;")
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setFixedHeight(20)
        layout.addWidget(self.lbl_name)

        # Bottom row: Favorite Button
        btn_row = QHBoxLayout()
        self.btn_fav = QPushButton("🤍  Merken")
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fav.clicked.connect(self._toggle_favorite)
        btn_row.addWidget(self.btn_fav)
        layout.addLayout(btn_row)

    def _toggle_favorite(self) -> None:
        self.set_favorite(not self.is_favorite)
        self.sig_favorite_toggled.emit(self.index, self.is_favorite)

    def set_favorite(self, fav: bool) -> None:
        self.is_favorite = fav
        self._update_appearance()

    def _update_appearance(self) -> None:
        if self.is_favorite:
            self.setStyleSheet(
                """
                PresetCardWidget {
                    background-color: #1e293b;
                    border: 2px solid #38bdf8;
                    border-radius: 10px;
                }
                """
            )
            self.btn_fav.setText("❤️  Gemerkt")
            self.btn_fav.setStyleSheet(
                """
                QPushButton {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                PresetCardWidget {
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    border-radius: 10px;
                }
                PresetCardWidget:hover {
                    border: 1px solid #52525b;
                }
                """
            )
            self.btn_fav.setText("🤍  Merken")
            self.btn_fav.setStyleSheet(
                """
                QPushButton {
                    background-color: #27272a;
                    color: #e4e4e7;
                    border: 1px solid #3f3f46;
                    border-radius: 6px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #3f3f46;
                    color: #ffffff;
                }
                """
            )

    def _on_zoom_clicked(self) -> None:
        dlg = ZoomModalDialog(self.pixmap, self.params, self.suggested_name, parent=self)
        dlg.exec()


# -----------------------------------------------------------------------------
# Save Presets Review Dialog
# -----------------------------------------------------------------------------

class PresetSaveDialog(QDialog):
    """Dialog allowing the user to review selected favorites, edit their names, and save as presets."""

    def __init__(
        self,
        favorites: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Favoriten als Presets speichern")
        self.resize(720, 520)
        self.setStyleSheet(DARK_STYLESHEET)
        self.favorites = favorites
        self.saved_names: List[str] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header_lbl = QLabel("Favoriten als dauerhafte Presets übernehmen")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(header_lbl)

        desc_lbl = QLabel(
            "Vergib für jede ausgewählte Konfiguration einen passenden Namen.\n"
            "Nach dem Speichern stehen die neuen Vorlagen sofort im Hauptprogramm zur Verfügung."
        )
        desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        layout.addWidget(desc_lbl)

        # Table with selected cards
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Vorschau", "Preset-Name", "Stil / Eigenschaften", "Speichern"])
        self.table.setRowCount(len(self.favorites))
        self.table.verticalHeader().setVisible(False)
        self.table.setRowHeight(0, 72)
        self.table.horizontalHeader().setStretchLastSection(False)

        self.edit_fields: List[QLineEdit] = []
        self.save_checks: List[QCheckBox] = []

        for row, item in enumerate(self.favorites):
            self.table.setRowHeight(row, 72)

            # 1. Thumbnail preview
            lbl_thumb = QLabel()
            lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_thumb.setPixmap(
                item["pixmap"].scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            self.table.setCellWidget(row, 0, lbl_thumb)

            # 2. Name input
            edit = QLineEdit(item["suggested_name"])
            edit.setStyleSheet("padding: 6px; font-size: 13px; font-weight: bold;")
            self.edit_fields.append(edit)
            self.table.setCellWidget(row, 1, edit)

            # 3. Details description
            params: PlotParameters = item["params"]
            style_str = params.artistic_mode if params.artistic_mode != "none" else "Kontur"
            info_txt = f"{style_str}\nFarbe: {params.stroke_color}"
            lbl_detail = QLabel(info_txt)
            lbl_detail.setStyleSheet("color: #a1a1aa; font-size: 12px;")
            self.table.setCellWidget(row, 2, lbl_detail)

            # 4. Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk_container = QWidget()
            chk_lay = QHBoxLayout(chk_container)
            chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            chk_lay.addWidget(chk)
            self.save_checks.append(chk)
            self.table.setCellWidget(row, 3, chk_container)

        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 320)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 80)

        layout.addWidget(self.table, 1)

        # Buttons bottom
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()

        self.btn_save_all = QPushButton("💾  Ausgewählte Presets speichern")
        self.btn_save_all.setStyleSheet(
            """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            """
        )
        self.btn_save_all.clicked.connect(self._save_presets)
        btn_layout.addWidget(self.btn_save_all)

        layout.addLayout(btn_layout)

    def _save_presets(self) -> None:
        saved_count = 0
        self.saved_names = []

        for row, item in enumerate(self.favorites):
            if not self.save_checks[row].isChecked():
                continue

            name = self.edit_fields[row].text().strip()
            if not name:
                name = item["suggested_name"]

            params: PlotParameters = item["params"]
            safe_name = save_user_preset(name, params)
            self.saved_names.append(safe_name)
            saved_count += 1

        if saved_count > 0:
            QMessageBox.information(
                self,
                "Presets erfolgreich gespeichert",
                f"{saved_count} Preset(s) wurden erfolgreich gespeichert!\n"
                "Sie sind nun sofort im Hauptfenster auswählbar.",
            )
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Keine Presets ausgewählt",
                "Es wurde kein Preset zum Speichern markiert.",
            )


# -----------------------------------------------------------------------------
# Main Preset Laboratory Window
# -----------------------------------------------------------------------------

class PresetLabWindow(QMainWindow):
    """
    Standalone and dockable Preset Discovery Application.
    Supports fullscreen (F11) and windowed modes.
    """

    sig_presets_saved = Signal()  # Emitted when new presets have been saved to refresh main window

    def __init__(
        self,
        initial_image_path: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("img2plot - Preset-Labor & Stil-Entdecker")
        self.resize(1280, 840)

        self.current_image_path: str = initial_image_path or ""
        self.card_widgets: List[PresetCardWidget] = []
        self.generated_data: List[Dict[str, Any]] = []
        self.worker: Optional[PresetLabWorker] = None
        self.is_fullscreen: bool = False

        self._setup_ui()
        self._build_menus()
        self.setStyleSheet(DARK_STYLESHEET)

        if self.current_image_path and os.path.isfile(self.current_image_path):
            self.lbl_image_path.setText(os.path.basename(self.current_image_path))
            self.lbl_image_path.setToolTip(self.current_image_path)

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Top Control Bar
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 4px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 8, 12, 8)
        top_layout.setSpacing(12)

        # Image picker
        top_layout.addWidget(QLabel("<b>Quellbild:</b>"))
        self.btn_pick_image = QPushButton("Bild wählen...")
        self.btn_pick_image.clicked.connect(self._select_image)
        top_layout.addWidget(self.btn_pick_image)

        self.lbl_image_path = QLabel("Kein Bild gewählt")
        self.lbl_image_path.setStyleSheet("color: #a1a1aa; font-style: italic;")
        self.lbl_image_path.setMaximumWidth(240)
        top_layout.addWidget(self.lbl_image_path)

        top_layout.addSpacing(16)

        # Count slider (1 to 1000)
        top_layout.addWidget(QLabel("<b>Anzahl Varianten:</b>"))
        self.slider_count = QSlider(Qt.Orientation.Horizontal)
        self.slider_count.setRange(1, 1000)
        self.slider_count.setValue(12)
        self.slider_count.setFixedWidth(140)

        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 1000)
        self.spin_count.setValue(12)
        self.spin_count.setFixedWidth(65)

        self.slider_count.valueChanged.connect(self.spin_count.setValue)
        self.spin_count.valueChanged.connect(self.slider_count.setValue)

        top_layout.addWidget(self.slider_count)
        top_layout.addWidget(self.spin_count)

        top_layout.addSpacing(16)

        # Style focus filter
        top_layout.addWidget(QLabel("<b>Stil-Fokus:</b>"))
        self.combo_focus = QComboBox()
        self.combo_focus.addItem("Alle Stile (Bunter Zufallsmix)", "all")
        self.combo_focus.addItem("Ausschließlich künstlerische Stile (ohne Kontur)", "artistic_only")
        self.combo_focus.addItem("Künstlerische Stile gar nicht (nur klassische Kontur & Schraffur)", "classic_only")
        self.combo_focus.insertSeparator(3)

        mode_display_names = {
            "waveform": "Wellenform / 3D-Relief",
            "spiral": "Archimedische Spirale",
            "tsp": "TSP Single-Line",
            "delaunay": "Low-Poly (Delaunay)",
            "flowfield": "Flussfeld (Streamlines)",
            "voronoi": "Voronoi-Mosaik",
            "reaction_diffusion": "Reaktions-Diffusion (Turing)",
            "stippling": "Voronoi Stippling",
            "sbr": "Stroke-Based Rendering (Pinselstriche)",
            "isocontours": "Marching Squares (Iso-Höhenlinien)",
            "physarum": "Physarum (Schleimpilz-Netzwerk)",
            "string_art": "String-Art (Fadenbild)",
            "diffgrowth": "Differenzielles Wachstum",
        }
        for mode in NON_CLASSIC_ARTISTIC_MODES:
            label = f"Nur: {mode_display_names.get(mode, mode.title())}"
            self.combo_focus.addItem(label, mode)
        top_layout.addWidget(self.combo_focus)

        top_layout.addStretch()

        # Primary Generate Button
        self.btn_generate = QPushButton("🎲  Varianten generieren")
        self.btn_generate.setStyleSheet(
            """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            """
        )
        self.btn_generate.clicked.connect(self.start_generation)
        top_layout.addWidget(self.btn_generate)

        # Stop Button
        self.btn_stop = QPushButton("⏹  Abbrechen")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_generation)
        top_layout.addWidget(self.btn_stop)

        root_layout.addWidget(top_bar)

        # 2. Progress Indicator Bar
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px;")
        prog_layout = QHBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(12, 6, 12, 6)
        prog_layout.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        prog_layout.addWidget(self.progress_bar, 1)

        self.lbl_status = QLabel("Bereit. Wähle ein Bild und klicke auf 'Varianten generieren'.")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        prog_layout.addWidget(self.lbl_status)

        root_layout.addWidget(self.progress_frame)

        # 3. Filter and Selection Sub-header
        sub_bar = QHBoxLayout()
        sub_bar.setContentsMargins(4, 0, 4, 0)

        self.btn_filter_all = QPushButton("Alle Varianten anzeigen")
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setChecked(True)
        self.btn_filter_all.clicked.connect(self._filter_all_clicked)
        sub_bar.addWidget(self.btn_filter_all)

        self.btn_filter_favs = QPushButton("Nur Gemerkte (0)")
        self.btn_filter_favs.setCheckable(True)
        self.btn_filter_favs.setChecked(False)
        self.btn_filter_favs.clicked.connect(self._filter_favs_clicked)
        sub_bar.addWidget(self.btn_filter_favs)

        sub_bar.addSpacing(16)

        btn_select_all = QPushButton("Alle merken")
        btn_select_all.clicked.connect(self.select_all_cards)
        sub_bar.addWidget(btn_select_all)

        btn_unselect_all = QPushButton("Auswahl aufheben")
        btn_unselect_all.clicked.connect(self.unselect_all_cards)
        sub_bar.addWidget(btn_unselect_all)

        sub_bar.addStretch()

        self.lbl_fav_counter = QLabel("0 von 0 gemerkt")
        self.lbl_fav_counter.setStyleSheet("font-weight: bold; color: #38bdf8;")
        sub_bar.addWidget(self.lbl_fav_counter)

        root_layout.addLayout(sub_bar)

        # 4. Scrollable Gallery Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #09090b; border: 1px solid #27272a; border-radius: 8px;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(14, 14, 14, 14)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        root_layout.addWidget(self.scroll_area, 1)

        # 5. Bottom Action Bar
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 4px;")
        bot_layout = QHBoxLayout(bottom_bar)
        bot_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_summary = QLabel("Tipp: Klicke auf 'Merken' bei den Varianten, die dir gefallen.")
        self.lbl_summary.setStyleSheet("color: #a1a1aa;")
        bot_layout.addWidget(self.lbl_summary)

        bot_layout.addStretch()

        self.btn_save_favs = QPushButton("💾  Gemerkte als Presets speichern (0)...")
        self.btn_save_favs.setEnabled(False)
        self.btn_save_favs.setStyleSheet(
            """
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #27272a;
                color: #71717a;
            }
            """
        )
        self.btn_save_favs.clicked.connect(self._open_save_dialog)
        bot_layout.addWidget(self.btn_save_favs)

        root_layout.addWidget(bottom_bar)

    # -------------------------------------------------------------------------
    # Menubar & Fullscreen
    # -------------------------------------------------------------------------

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        menu_file = menubar.addMenu("Datei")
        act_open = QAction("Quellbild wählen...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._select_image)
        menu_file.addAction(act_open)

        menu_file.addSeparator()

        act_close = QAction("Schließen", self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self.close)
        menu_file.addAction(act_close)

        menu_view = menubar.addMenu("Ansicht")
        self.act_fullscreen = QAction("Vollbildmodus (F11)", self)
        self.act_fullscreen.setShortcut(QKeySequence("F11"))
        self.act_fullscreen.setCheckable(True)
        self.act_fullscreen.triggered.connect(self.toggle_fullscreen)
        menu_view.addAction(self.act_fullscreen)

    def toggle_fullscreen(self) -> None:
        """Toggle between windowed and fullscreen display mode."""
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
            self.act_fullscreen.setChecked(True)
        else:
            self.showNormal()
            self.act_fullscreen.setChecked(False)

    # -------------------------------------------------------------------------
    # Image Selection & Generation Flow
    # -------------------------------------------------------------------------

    def _select_image(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Quellbild für Preset-Labor wählen",
            "",
            "Bilder (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;Alle Dateien (*.*)",
        )
        if fpath:
            self.set_source_image(fpath)

    def set_source_image(self, image_path: str) -> None:
        """Set the active source image for batch testing."""
        self.current_image_path = image_path
        self.lbl_image_path.setText(os.path.basename(image_path))
        self.lbl_image_path.setToolTip(image_path)
        self.lbl_status.setText(f"Bild geladen: {os.path.basename(image_path)}")

    def start_generation(self) -> None:
        """Start batch generation of randomized configurations."""
        if not self.current_image_path or not os.path.isfile(self.current_image_path):
            QMessageBox.warning(
                self,
                "Kein Bild gewählt",
                "Bitte wähle zuerst ein Quellbild aus.",
            )
            return

        # Clear existing cards
        self._clear_cards()

        count = self.slider_count.value()
        focus_mode = self.combo_focus.currentData()

        param_list = [generate_random_parameters(focus_mode) for _ in range(count)]

        self.btn_generate.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(count)
        self.lbl_status.setText(f"Starte Generierung von {count} Varianten...")

        self.worker = PresetLabWorker(self.current_image_path, param_list, parent=self)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_item_ready.connect(self._on_item_ready)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.sig_error.connect(self._on_worker_error)
        self.worker.start()

    def stop_generation(self) -> None:
        """Cancel the ongoing worker calculation."""
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Breche Berechnung ab...")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def _on_worker_progress(self, current: int, total: int, msg: str) -> None:
        self.progress_bar.setValue(current)
        self.lbl_status.setText(msg)

    def _on_item_ready(self, index: int, params: PlotParameters, pixmap: QPixmap) -> None:
        suggested_name = suggest_preset_name(params)

        item_data = {
            "index": index,
            "params": params,
            "pixmap": pixmap,
            "suggested_name": suggested_name,
        }
        self.generated_data.append(item_data)

        card = PresetCardWidget(
            index=index,
            params=params,
            pixmap=pixmap,
            suggested_name=suggested_name,
            parent=self.grid_container,
        )
        card.sig_favorite_toggled.connect(self._on_card_favorite_toggled)
        self.card_widgets.append(card)

        # Place into responsive grid (4 cards per row)
        row = (len(self.card_widgets) - 1) // 4
        col = (len(self.card_widgets) - 1) % 4
        self.grid_layout.addWidget(card, row, col)

        self._update_counter()

    def _on_worker_finished(self) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText(f"Fertig! {len(self.card_widgets)} Varianten wurden generiert.")
        self._update_counter()

    def _on_worker_error(self, index: int, error_msg: str) -> None:
        self.lbl_status.setText(f"Fehler bei Variante {index + 1}: {error_msg}")

    # -------------------------------------------------------------------------
    # Card Management & Selection
    # -------------------------------------------------------------------------

    def _clear_cards(self) -> None:
        self.grid_container.setUpdatesEnabled(False)
        try:
            for card in self.card_widgets:
                self.grid_layout.removeWidget(card)
                card.deleteLater()
            self.card_widgets.clear()
            self.generated_data.clear()
        finally:
            self.grid_container.setUpdatesEnabled(True)
        self._update_counter()

    def _on_card_favorite_toggled(self, index: int, is_fav: bool) -> None:
        self._update_counter()
        if self.btn_filter_favs.isChecked() and not is_fav:
            for card in self.card_widgets:
                if card.index == index:
                    card.setVisible(False)

    def select_all_cards(self) -> None:
        self.grid_container.setUpdatesEnabled(False)
        try:
            for card in self.card_widgets:
                card.set_favorite(True)
        finally:
            self.grid_container.setUpdatesEnabled(True)
        self._update_counter()

    def unselect_all_cards(self) -> None:
        self.grid_container.setUpdatesEnabled(False)
        try:
            for card in self.card_widgets:
                card.set_favorite(False)
        finally:
            self.grid_container.setUpdatesEnabled(True)
        self._update_counter()

    def _filter_all_clicked(self) -> None:
        self.btn_filter_all.setChecked(True)
        self.btn_filter_favs.setChecked(False)
        self.grid_container.setUpdatesEnabled(False)
        try:
            for card in self.card_widgets:
                card.setVisible(True)
        finally:
            self.grid_container.setUpdatesEnabled(True)

    def _filter_favs_clicked(self) -> None:
        self.btn_filter_all.setChecked(False)
        self.btn_filter_favs.setChecked(True)
        self.grid_container.setUpdatesEnabled(False)
        try:
            for card in self.card_widgets:
                card.setVisible(card.is_favorite)
        finally:
            self.grid_container.setUpdatesEnabled(True)

    def _update_counter(self) -> None:
        fav_count = sum(1 for c in self.card_widgets if c.is_favorite)
        total = len(self.card_widgets)
        self.lbl_fav_counter.setText(f"{fav_count} von {total} gemerkt")
        self.btn_filter_favs.setText(f"Nur Gemerkte ({fav_count})")
        self.btn_save_favs.setText(f"💾  Gemerkte als Presets speichern ({fav_count})...")
        self.btn_save_favs.setEnabled(fav_count > 0)

    # -------------------------------------------------------------------------
    # Save Presets Action
    # -------------------------------------------------------------------------

    def _open_save_dialog(self) -> None:
        fav_items = []
        for card in self.card_widgets:
            if card.is_favorite:
                fav_items.append({
                    "index": card.index,
                    "params": card.params,
                    "pixmap": card.pixmap,
                    "suggested_name": card.suggested_name,
                })

        if not fav_items:
            return

        dlg = PresetSaveDialog(fav_items, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.sig_presets_saved.emit()


def main() -> None:
    """Standalone entry point for the Preset Laboratory."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    initial_img = sys.argv[1] if len(sys.argv) > 1 else None
    window = PresetLabWindow(initial_image_path=initial_img)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
