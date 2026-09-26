"""
Main application window for img2plot.
Integrates the menubar, toolbar, sidebar, and interactive vector preview canvas.
Supports windowed and fullscreen modes, drag-and-drop, and background debounced live updates.
"""

from __future__ import annotations
import os
import sys
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QApplication,
)

from ..core.parameters import PlotParameters
from ..core.engine import EngineResult, PlotStats, PlotEngine
from ..core.exporter import export_svg, export_png
from .theme import DARK_STYLESHEET
from .sidebar import SidebarWidget
from .preview_widget import PreviewWidget
from .worker import VectorizationWorker, PreviewRenderData


class MainWindow(QMainWindow):
    """Main application window for img2plot with fullscreen/windowed toggle and live preview."""

    def __init__(self, initial_image: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("img2plot - Vektor-Zeichenvorlagen Generator für Stiftplotter")
        self.resize(1340, 860)
        self.setAcceptDrops(True)

        # State tracking
        self.current_image_path: str = ""
        self.current_result: Optional[EngineResult] = None
        self.is_fullscreen: bool = False
        self._force_fit_next: bool = True
        self._current_req_id: int = 0

        # Persistent background worker thread for non-blocking preview vectorization
        self.worker = VectorizationWorker(parent=self)
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.sig_error.connect(self._on_worker_error)
        self.worker.start()

        # Debounce timer for smooth slider live-preview updates
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(300)
        self.debounce_timer.timeout.connect(self._start_preview_calculation)

        # Central layout with QSplitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # 1. Left Sidebar
        self.sidebar = SidebarWidget()
        self.splitter.addWidget(self.sidebar)

        # 2. Right Canvas / Preview area
        self.preview = PreviewWidget()
        self.splitter.addWidget(self.preview)

        # Set splitter proportions (approx 380px left, remainder right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([380, 960])

        # Connect signals
        self._connect_signals()

        # Build Menubar, Toolbar, and Statusbar
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()

        # Apply dark styling
        self.setStyleSheet(DARK_STYLESHEET)

        # Load initial image if provided or check default samples
        if initial_image and os.path.isfile(initial_image):
            self.load_image(initial_image)
        else:
            self._load_default_sample_if_available()

    # -------------------------------------------------------------------------
    # Setup & Construction
    # -------------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.sidebar.sig_parameters_changed.connect(self._on_parameters_changed)
        self.sidebar.sig_recalculate_requested.connect(self._on_manual_recalculate)
        self.sidebar.sig_cancel_requested.connect(self._on_cancel_requested)
        self.sidebar.sig_export_svg_requested.connect(self.export_svg_file)
        self.sidebar.sig_export_png_requested.connect(self.export_png_file)
        self.sidebar.sig_input_file_selected.connect(self.load_image)

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # Menu: Datei
        menu_file = menubar.addMenu("Datei")

        act_open = QAction("Bild öffnen...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._action_open_image)
        menu_file.addAction(act_open)

        menu_file.addSeparator()

        act_export_svg = QAction("SVG exportieren...", self)
        act_export_svg.setShortcut(QKeySequence("Ctrl+S"))
        act_export_svg.triggered.connect(self.export_svg_file)
        menu_file.addAction(act_export_svg)

        act_export_png = QAction("PNG exportieren...", self)
        act_export_png.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_export_png.triggered.connect(self.export_png_file)
        menu_file.addAction(act_export_png)

        menu_file.addSeparator()

        act_exit = QAction("Beenden", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Menu: Ansicht
        menu_view = menubar.addMenu("Ansicht")

        self.act_fullscreen = QAction("Vollbildmodus (F11)", self)
        self.act_fullscreen.setShortcut(QKeySequence("F11"))
        self.act_fullscreen.setCheckable(True)
        self.act_fullscreen.triggered.connect(self.toggle_fullscreen)
        menu_view.addAction(self.act_fullscreen)

        menu_view.addSeparator()

        act_fit = QAction("An Fenster anpassen", self)
        act_fit.setShortcut(QKeySequence("Ctrl+0"))
        act_fit.triggered.connect(self.preview.canvas.fit_to_view)
        menu_view.addAction(act_fit)

        act_100 = QAction("Tatsächliche Größe (100 %)", self)
        act_100.setShortcut(QKeySequence("Ctrl+1"))
        act_100.triggered.connect(self.preview.canvas.reset_zoom)
        menu_view.addAction(act_100)

        menu_view.addSeparator()

        self.act_keep_zoom = QAction("Zoomstufe bei Neuberechnung beibehalten", self)
        self.act_keep_zoom.setCheckable(True)
        self.act_keep_zoom.setChecked(self.preview.chk_keep_zoom.isChecked())
        self.act_keep_zoom.toggled.connect(self.preview.chk_keep_zoom.setChecked)
        self.preview.chk_keep_zoom.toggled.connect(self.act_keep_zoom.setChecked)
        menu_view.addAction(self.act_keep_zoom)

        # Menu: Hilfe
        menu_help = menubar.addMenu("Hilfe")
        act_about = QAction("Über img2plot", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Hauptleiste")
        toolbar.setMovable(False)

        act_open = QAction("Bild öffnen", self)
        act_open.setToolTip("Ein neues Bild zum Plotten laden (Strg+O)")
        act_open.triggered.connect(self._action_open_image)
        toolbar.addAction(act_open)

        act_calc = QAction("Berechnen", self)
        act_calc.setToolTip("Vorschau sofort neu berechnen")
        act_calc.triggered.connect(self._on_manual_recalculate)
        toolbar.addAction(act_calc)

        toolbar.addSeparator()

        act_export_svg = QAction("SVG Export", self)
        act_export_svg.setToolTip("Vektorzeichnung als SVG für Stiftplotter speichern")
        act_export_svg.triggered.connect(self.export_svg_file)
        toolbar.addAction(act_export_svg)

        act_export_png = QAction("PNG Export", self)
        act_export_png.setToolTip("Zeichnung als hochauflösendes PNG-Bild exportieren")
        act_export_png.triggered.connect(self.export_png_file)
        toolbar.addAction(act_export_png)

        toolbar.addSeparator()

        # Dedicated Fullscreen / Windowed toggle action on toolbar
        self.act_tb_fullscreen = QAction("Vollbild (F11)", self)
        self.act_tb_fullscreen.setToolTip("Zwischen Vollbild- und Fenstermodus wechseln (F11)")
        self.act_tb_fullscreen.triggered.connect(self.toggle_fullscreen)
        toolbar.addAction(self.act_tb_fullscreen)

    def _build_statusbar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_label = status_bar
        self.status_label.showMessage("Bereit. Wähle ein Bild oder ziehe es per Drag & Drop in das Fenster.")

    def _load_default_sample_if_available(self) -> None:
        """Auto-load a sample image from readme-imgs if present."""
        sample_candidates = [
            os.path.join("readme-imgs", "betta.jpg"),
            os.path.join("readme-imgs", "revali.jpg"),
            os.path.join("readme-imgs", "dunwall.jpg"),
        ]
        for candidate in sample_candidates:
            if os.path.isfile(candidate):
                self.load_image(os.path.abspath(candidate))
                break

    # -------------------------------------------------------------------------
    # Fullscreen & Windowed Mode (User Rule 4)
    # -------------------------------------------------------------------------

    def toggle_fullscreen(self) -> None:
        """Toggle between Fullscreen mode and Windowed mode."""
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False
            self.act_fullscreen.setChecked(False)
            self.act_fullscreen.setText("Vollbildmodus (F11)")
            self.act_tb_fullscreen.setText("Vollbild (F11)")
            self.statusBar().showMessage("Fenstermodus aktiviert.", 2500)
        else:
            self.showFullScreen()
            self.is_fullscreen = True
            self.act_fullscreen.setChecked(True)
            self.act_fullscreen.setText("Fenstermodus verlassen (F11)")
            self.act_tb_fullscreen.setText("Fenster (F11)")
            self.statusBar().showMessage("Vollbildmodus aktiviert (Drücke F11 oder Escape zum Beenden).", 3500)

    def keyPressEvent(self, event) -> None:
        """Handle global keyboard shortcuts."""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Cleanly stop persistent worker thread and timers on application exit."""
        self.debounce_timer.stop()
        if self.worker:
            self.worker.stop()
        super().closeEvent(event)

    # -------------------------------------------------------------------------
    # Drag and Drop Support
    # -------------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.isLocalFile() for url in urls):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                ext = os.path.splitext(file_path)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"):
                    self.load_image(file_path)
                    event.acceptProposedAction()
                    break

    # -------------------------------------------------------------------------
    # Image Loading & Processing
    # -------------------------------------------------------------------------

    def _action_open_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Bilddatei öffnen",
            "",
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;Alle Dateien (*.*)",
        )
        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path: str) -> None:
        """Load an image and trigger initial vectorization."""
        if not os.path.isfile(file_path):
            QMessageBox.warning(self, "Datei nicht gefunden", f"Die Datei '{file_path}' existiert nicht.")
            return

        self.current_image_path = file_path
        self.sidebar.edit_input.setText(file_path)

        # Set suggested output path
        base, _ = os.path.splitext(file_path)
        out_svg = base + "_plot.svg"
        self.sidebar.edit_output.setText(out_svg)

        self.statusBar().showMessage(f"Bild geladen: {os.path.basename(file_path)}")
        self._force_fit_next = True
        self._start_preview_calculation()

    def _on_parameters_changed(self) -> None:
        """Handle parameter changes from sidebar with debouncing."""
        if not self.current_image_path:
            return

        if self.sidebar.chk_auto_preview.isChecked():
            # Reset debounce timer
            self.debounce_timer.start()

    def _on_manual_recalculate(self) -> None:
        self.debounce_timer.stop()
        self._start_preview_calculation()

    def _on_cancel_requested(self) -> None:
        if self.worker:
            self.worker.cancel()
        self.sidebar.set_progress(0.0, "Berechnung abgebrochen.")
        self.sidebar.set_computing_state(False)
        self.statusBar().showMessage("Berechnung abgebrochen.")

    def _start_preview_calculation(self) -> None:
        """Submit vectorization task to background worker without blocking the GUI."""
        if not self.current_image_path or not os.path.isfile(self.current_image_path):
            return

        params = self.sidebar.get_current_parameters()
        params.input_path = self.current_image_path

        self._current_req_id += 1
        req_id = self._current_req_id

        self.sidebar.set_computing_state(True)
        self.sidebar.set_progress(0.05, "Vorbereitung...")
        self.statusBar().showMessage("Vektorisierung läuft im Hintergrund...")

        self.worker.submit_task(
            params=params,
            image_input=self.current_image_path,
            req_id=req_id,
            is_preview=True,
            paper_style=self.preview.canvas.paper_style,
            display_mode=self.preview.canvas.display_mode,
            overlay_opacity=self.preview.canvas.overlay_opacity,
        )

    def _on_worker_progress(self, fraction: float, msg: str) -> None:
        self.sidebar.set_progress(fraction, msg)

    def _on_worker_finished(self, data: PreviewRenderData, req_id: int) -> None:
        if req_id != self._current_req_id:
            # Stale result from an older calculation that was cancelled
            return

        self.current_result = data.result
        self.sidebar.set_computing_state(False)
        self.sidebar.update_statistics(data.result.stats)
        force_fit = getattr(self, "_force_fit_next", False)
        self.preview.set_preview_data(data, force_fit=force_fit)
        self._force_fit_next = False
        self.statusBar().showMessage(
            f"Fertig: {data.result.stats.total_strokes} Pfade in {data.result.stats.elapsed_time_sec:.2f}s generiert."
        )

    def _on_worker_error(self, err_msg: str, req_id: int) -> None:
        if req_id != self._current_req_id:
            return
        self.sidebar.set_computing_state(False)
        self.sidebar.set_progress(0.0, "Fehler bei der Berechnung")
        self.statusBar().showMessage("Fehler bei der Vektorisierung.")
        QMessageBox.critical(self, "Berechnungsfehler", f"Ein Fehler ist aufgetreten:\n{err_msg}")

    # -------------------------------------------------------------------------
    # Export Functions
    # -------------------------------------------------------------------------

    def export_svg_file(self) -> None:
        """Export current or full-resolution vector drawing to SVG."""
        if not self.current_image_path:
            QMessageBox.information(self, "Kein Bild", "Bitte zuerst ein Bild laden.")
            return

        out_path = self.sidebar.edit_output.text().strip()
        if not out_path or not out_path.lower().endswith(".svg"):
            out_path, _ = QFileDialog.getSaveFileName(
                self, "SVG-Datei speichern", out_path or "plot.svg", "SVG (*.svg)"
            )
            if not out_path:
                return
            self.sidebar.edit_output.setText(out_path)

        params = self.sidebar.get_current_parameters()
        params.input_path = self.current_image_path
        params.output_path = out_path

        # If user has an existing result, ask if they want to export current preview or full resolution
        reply = QMessageBox.question(
            self,
            "SVG Export",
            "Möchtest du das Bild in voller Originalauflösung für den Plotter berechnen und exportieren?\n\n"
            "(Ja = Volle Auflösung für maximale Details, Nein = Schneller Export der aktuellen Vorschau)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        try:
            self.statusBar().showMessage("Exportiere SVG...")
            if reply == QMessageBox.StandardButton.Yes:
                # Compute at full resolution
                full_params = self.sidebar.get_current_parameters()
                full_params.preview_max_dim = 0  # No downscaling
                engine = PlotEngine(full_params)
                result = engine.process_image(self.current_image_path, is_preview=False)
            else:
                if self.current_result:
                    result = self.current_result
                else:
                    engine = PlotEngine(params)
                    result = engine.process_image(self.current_image_path, is_preview=True)

            export_svg(result, params, out_path)
            self.statusBar().showMessage(f"SVG erfolgreich gespeichert: {out_path}", 4000)
            QMessageBox.information(
                self,
                "SVG Export erfolgreich",
                f"Die Datei wurde erfolgreich gespeichert:\n{out_path}\n\n"
                f"Pfade: {result.stats.total_strokes}\n"
                f"Zeichenlänge: {result.stats.total_length_px:.1f} px",
            )
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Exportieren", f"Konnte SVG nicht exportieren:\n{e}")

    def export_png_file(self) -> None:
        """Export vector drawing as high-resolution PNG image."""
        if not self.current_result:
            QMessageBox.information(self, "Keine Vorschau", "Bitte zuerst ein Bild berechnen lassen.")
            return

        out_path = self.sidebar.edit_output.text().strip()
        base, _ = os.path.splitext(out_path)
        default_png = (base or "plot") + ".png"

        png_path, _ = QFileDialog.getSaveFileName(
            self, "PNG-Bild speichern", default_png, "PNG (*.png)"
        )
        if not png_path:
            return

        try:
            params = self.sidebar.get_current_parameters()
            export_png(self.current_result, params, png_path, scale_factor=2.0)
            self.statusBar().showMessage(f"PNG erfolgreich gespeichert: {png_path}", 4000)
            QMessageBox.information(
                self, "PNG Export erfolgreich", f"Die Bilddatei wurde gespeichert:\n{png_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Exportieren", f"Konnte PNG nicht exportieren:\n{e}")

    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            "Über img2plot",
            "<h3>img2plot</h3>"
            "<p>Ein modernes Werkzeug zur Erstellung künstlerischer Strich- und Vektorzeichnungen für Stiftplotter (z. B. Silhouette Cameo, AxiDraw).</p>"
            "<p><b>Funktionen:</b></p>"
            "<ul>"
            "<li>Live-Vorschau mit Zoom, Verschieben und Bildüberlagerung</li>"
            "<li>Glatte Bézier-Kurven für einen organischen Handzeichnungs-Look</li>"
            "<li>Schraffur-Modus (Hatching) für Schattenbereiche</li>"
            "<li>Plotter-Wegoptimierung (Nearest Neighbor) zur Minimierung von Leerwegen</li>"
            "<li>Vollbild- (F11) und Fenstermodus</li>"
            "<li>Vordefinierte und benutzerdefinierte Presets (JSON)</li>"
            "<li>SVG- und PNG-Export mit Maßstabs- und Randoptionen</li>"
            "</ul>",
        )
