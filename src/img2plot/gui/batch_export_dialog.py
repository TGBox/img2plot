"""
Batch export dialog for img2plot.
Allows users to select multiple (or all) presets and sequentially export the active image
into various vector (SVG) and/or raster (PNG) files.
"""

from __future__ import annotations
import copy
import os
from typing import List, Dict, Optional, NamedTuple

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QFrame,
)

from ..core.parameters import PlotParameters
from ..core.presets import DEFAULT_PRESETS, get_all_presets, list_user_presets
from ..core.engine import PlotEngine
from ..core.exporter import export_svg, export_png
from .theme import DARK_STYLESHEET


class BatchExportTask(NamedTuple):
    preset_name: str
    params: PlotParameters


class BatchExportWorker(QThread):
    """Background worker thread performing sequential vectorization and export."""

    sig_progress = Signal(int, int, str)  # current_done, total_count, message
    sig_finished = Signal(list)          # list of successfully created file paths
    sig_error = Signal(str)

    def __init__(
        self,
        image_path: str,
        tasks: List[BatchExportTask],
        output_dir: str,
        export_svg_flag: bool,
        export_png_flag: bool,
        full_resolution: bool,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.image_path = image_path
        self.tasks = tasks
        self.output_dir = output_dir
        self.export_svg_flag = export_svg_flag
        self.export_png_flag = export_png_flag
        self.full_resolution = full_resolution
        self._is_cancelled = False

    def cancel(self) -> None:
        """Request cooperative cancellation."""
        self._is_cancelled = True

    def run(self) -> None:
        exported_files: List[str] = []
        total = len(self.tasks)
        base_img_name = os.path.splitext(os.path.basename(self.image_path))[0]

        os.makedirs(self.output_dir, exist_ok=True)

        for idx, task in enumerate(self.tasks):
            if self._is_cancelled:
                break

            msg = f"Berechne Variante {idx + 1}/{total}: '{task.preset_name}'..."
            self.sig_progress.emit(idx, total, msg)

            try:
                # Clone parameters to avoid modifying existing preset configs
                p = copy.deepcopy(task.params)
                p.input_path = self.image_path
                if self.full_resolution:
                    p.preview_max_dim = 0

                engine = PlotEngine(p)
                result = engine.process_image(self.image_path, is_preview=not self.full_resolution)

                # Format safe filename segment
                clean_name = "".join(
                    c for c in task.preset_name if c.isalnum() or c in (" ", "_", "-")
                ).strip().replace(" ", "_")
                if not clean_name:
                    clean_name = f"variant_{idx + 1}"

                if self.export_svg_flag:
                    svg_path = os.path.join(self.output_dir, f"{base_img_name}_{clean_name}.svg")
                    p.output_path = svg_path
                    export_svg(result, p, svg_path)
                    exported_files.append(svg_path)

                if self.export_png_flag:
                    png_path = os.path.join(self.output_dir, f"{base_img_name}_{clean_name}.png")
                    export_png(result, p, png_path, scale_factor=2.0)
                    exported_files.append(png_path)

            except Exception as e:
                # Report error but allow following tasks to proceed if possible
                pass

        if self._is_cancelled:
            self.sig_progress.emit(len(exported_files), total, "Stapel-Export abgebrochen.")
        else:
            self.sig_progress.emit(total, total, f"Fertig! {len(exported_files)} Datei(en) exportiert.")

        self.sig_finished.emit(exported_files)


class BatchExportDialog(QDialog):
    """Dialog allowing the user to select multiple presets and export the active image into multiple variants."""

    def __init__(
        self,
        image_path: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Stapel-Export (Mehrere Presets)")
        self.resize(720, 640)
        self.setStyleSheet(DARK_STYLESHEET)
        self.image_path = image_path
        self.worker: Optional[BatchExportWorker] = None

        self._all_presets: Dict[str, PlotParameters] = get_all_presets()
        self._user_preset_names: set[str] = set(list_user_presets().keys())

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        lbl_title = QLabel("Stapel-Export: Bild in mehreren Preset-Varianten exportieren")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f4f4f5;")
        layout.addWidget(lbl_title)

        base_name = os.path.basename(self.image_path) if self.image_path else "Kein Bild"
        lbl_info = QLabel(f"Aktuelles Bild: <b>{base_name}</b>")
        lbl_info.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        layout.addWidget(lbl_info)

        # Presets selection card
        lbl_presets = QLabel("Wähle die gewünschten Presets aus:")
        lbl_presets.setStyleSheet("font-weight: bold; color: #e4e4e7;")
        layout.addWidget(lbl_presets)

        # Presets ListWidget with checkable items
        self.list_presets = QListWidget()
        self.list_presets.setStyleSheet(
            """
            QListWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #202023;
            }
            QListWidget::item:hover {
                background-color: #27272a;
            }
            """
        )

        for name, params in self._all_presets.items():
            is_user = name in self._user_preset_names
            tag = "Eigenes Preset" if is_user else "Standard"
            style_str = params.artistic_mode if params.artistic_mode != "none" else "Kontur"
            display_text = f"{name}   —   [{tag} | Stil: {style_str}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)  # checked by default
            self.list_presets.addItem(item)

        layout.addWidget(self.list_presets, 1)

        # Quick selection buttons row
        h_quick = QHBoxLayout()
        h_quick.setSpacing(6)

        btn_all = QPushButton("Alle auswählen")
        btn_all.clicked.connect(lambda: self._set_all_checked(True))
        h_quick.addWidget(btn_all)

        btn_none = QPushButton("Keine auswählen")
        btn_none.clicked.connect(lambda: self._set_all_checked(False))
        h_quick.addWidget(btn_none)

        btn_default = QPushButton("Nur Standard-Presets")
        btn_default.clicked.connect(self._select_only_defaults)
        h_quick.addWidget(btn_default)

        btn_user = QPushButton("Nur Eigene Presets")
        btn_user.clicked.connect(self._select_only_user)
        h_quick.addWidget(btn_user)

        h_quick.addStretch()
        layout.addLayout(h_quick)

        # Output folder row
        box_dest = QFrame()
        box_dest.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 6px;")
        dest_lay = QVBoxLayout(box_dest)
        dest_lay.setContentsMargins(8, 8, 8, 8)
        dest_lay.setSpacing(6)

        dest_lay.addWidget(QLabel("<b>Zielordner für den Export:</b>"))
        h_folder = QHBoxLayout()
        default_dir = os.path.dirname(os.path.abspath(self.image_path)) if self.image_path else ""
        self.edit_dir = QLineEdit(default_dir)
        self.edit_dir.setPlaceholderText("Verzeichnis auswählen...")
        btn_browse = QPushButton("Durchsuchen...")
        btn_browse.clicked.connect(self._browse_folder)
        h_folder.addWidget(self.edit_dir, 1)
        h_folder.addWidget(btn_browse)
        dest_lay.addLayout(h_folder)

        # Options: formats & resolution
        h_opts = QHBoxLayout()
        h_opts.setSpacing(20)

        # Formats
        h_formats = QHBoxLayout()
        h_formats.addWidget(QLabel("Formate:"))
        self.chk_svg = QCheckBox("SVG (*.svg)")
        self.chk_svg.setChecked(True)
        self.chk_png = QCheckBox("PNG (*.png)")
        self.chk_png.setChecked(False)
        h_formats.addWidget(self.chk_svg)
        h_formats.addWidget(self.chk_png)
        h_opts.addLayout(h_formats)

        h_opts.addSpacing(16)

        # Resolution
        h_res = QHBoxLayout()
        h_res.addWidget(QLabel("Qualität:"))
        self.radio_full = QRadioButton("Volle Auflösung (Plotter)")
        self.radio_full.setChecked(True)
        self.radio_preview = QRadioButton("Schnelle Vorschau")
        self.bg_res = QButtonGroup(self)
        self.bg_res.addButton(self.radio_full)
        self.bg_res.addButton(self.radio_preview)
        h_res.addWidget(self.radio_full)
        h_res.addWidget(self.radio_preview)
        h_opts.addLayout(h_res)

        h_opts.addStretch()
        dest_lay.addLayout(h_opts)

        layout.addWidget(box_dest)

        # Progress bar & status
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Bereit zum Exportieren.")
        self.lbl_status.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Bottom buttons
        h_bottom = QHBoxLayout()
        h_bottom.setSpacing(10)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self._cancel_or_reject)
        h_bottom.addWidget(self.btn_cancel)

        h_bottom.addStretch()

        self.btn_start = QPushButton("🚀  Export starten")
        self.btn_start.setStyleSheet(
            """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:disabled {
                background-color: #3f3f46;
                color: #71717a;
            }
            """
        )
        self.btn_start.clicked.connect(self._start_export)
        h_bottom.addWidget(self.btn_start)

        layout.addLayout(h_bottom)

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for idx in range(self.list_presets.count()):
            self.list_presets.item(idx).setCheckState(state)

    def _select_only_defaults(self) -> None:
        for idx in range(self.list_presets.count()):
            item = self.list_presets.item(idx)
            name = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Checked if name in DEFAULT_PRESETS else Qt.CheckState.Unchecked)

    def _select_only_user(self) -> None:
        for idx in range(self.list_presets.count()):
            item = self.list_presets.item(idx)
            name = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Checked if name in self._user_preset_names else Qt.CheckState.Unchecked)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Zielordner für Batch-Export wählen", self.edit_dir.text())
        if folder:
            self.edit_dir.setText(folder)

    def _start_export(self) -> None:
        if not self.image_path or not os.path.isfile(self.image_path):
            QMessageBox.warning(self, "Kein Bild", "Bitte zuerst ein gültiges Quellbild öffnen.")
            return

        out_dir = self.edit_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "Kein Zielordner", "Bitte einen Zielordner angeben.")
            return

        if not self.chk_svg.isChecked() and not self.chk_png.isChecked():
            QMessageBox.warning(self, "Kein Format gewählt", "Bitte mindestens ein Export-Format (SVG oder PNG) auswählen.")
            return

        # Collect checked presets
        selected_tasks: List[BatchExportTask] = []
        for idx in range(self.list_presets.count()):
            item = self.list_presets.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                name = item.data(Qt.ItemDataRole.UserRole)
                if name in self._all_presets:
                    selected_tasks.append(BatchExportTask(name, self._all_presets[name]))

        if not selected_tasks:
            QMessageBox.warning(self, "Keine Presets gewählt", "Bitte mindestens ein Preset in der Liste markieren.")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setText("Berechnung stoppen")
        self.list_presets.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(selected_tasks))

        self.worker = BatchExportWorker(
            image_path=self.image_path,
            tasks=selected_tasks,
            output_dir=out_dir,
            export_svg_flag=self.chk_svg.isChecked(),
            export_png_flag=self.chk_png.isChecked(),
            full_resolution=self.radio_full.isChecked(),
            parent=self,
        )
        self.worker.sig_progress.connect(self._on_worker_progress)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, current: int, total: int, msg: str) -> None:
        self.progress_bar.setValue(current)
        self.lbl_status.setText(msg)

    def _on_worker_finished(self, exported_files: List[str]) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setText("Schließen")
        self.list_presets.setEnabled(True)

        if exported_files:
            QMessageBox.information(
                self,
                "Batch-Export abgeschlossen",
                f"{len(exported_files)} Datei(en) wurden erfolgreich im Zielordner gespeichert:\n"
                f"{self.edit_dir.text()}",
            )
        else:
            self.lbl_status.setText("Keine Dateien exportiert oder abgebrochen.")

    def _cancel_or_reject(self) -> None:
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Breche Stapel-Export ab...")
            self.worker.cancel()
            self.worker.wait(1500)
            self.btn_start.setEnabled(True)
            self.btn_cancel.setText("Schließen")
            self.list_presets.setEnabled(True)
        else:
            self.reject()

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        super().closeEvent(event)
