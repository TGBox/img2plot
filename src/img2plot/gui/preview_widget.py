"""
Interactive preview canvas for img2plot.
Supports panning, zooming, vector path rendering, Sobel edge maps, and image overlay with opacity.
"""

from __future__ import annotations
import math
from typing import Optional, List
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QPixmap,
    QImage,
    QPainterPath,
    QWheelEvent,
    QMouseEvent,
    QBrush,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QSlider,
    QPushButton,
    QComboBox,
    QFrame,
)

from ..core.engine import EngineResult, StrokePath


class CanvasView(QWidget):
    """Interactive canvas widget handling mouse pan, zoom, and multi-layer rendering."""

    sig_zoom_changed = Signal(float)
    sig_hover_info = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Transformation state
        self.zoom: float = 1.0
        self.pan_offset: QPointF = QPointF(0.0, 0.0)
        self.is_panning: bool = False
        self.last_mouse_pos: QPointF = QPointF(0.0, 0.0)

        # Data to render
        self.result: Optional[EngineResult] = None
        self.display_mode: str = "vector"  # "vector", "preprocess", "sobel", "overlay"
        self.overlay_opacity: float = 0.7
        self.paper_style: str = "white"  # "white", "paper", "dark"

        # Cached raster images for performance
        self.pixmap_preprocess: Optional[QPixmap] = None
        self.pixmap_sobel: Optional[QPixmap] = None
        self.cached_vector_path: Optional[QPainterPath] = None
        self.cached_hatch_path: Optional[QPainterPath] = None

    def set_result(self, result: EngineResult) -> None:
        """Update canvas with a new vectorization result."""
        self.result = result

        # Convert preprocessed numpy array to QPixmap
        if result.preprocessed_gray is not None:
            gray_u8 = (result.preprocessed_gray * 255.0).astype(np.uint8)
            h, w = gray_u8.shape
            qimg = QImage(gray_u8.data, w, h, w, QImage.Format.Format_Grayscale8)
            self.pixmap_preprocess = QPixmap.fromImage(qimg.copy())

        # Convert Sobel magnitude to QPixmap
        if result.sobel_magnitude is not None:
            sobel_u8 = (result.sobel_magnitude * 255.0).astype(np.uint8)
            h, w = sobel_u8.shape
            qimg_sobel = QImage(sobel_u8.data, w, h, w, QImage.Format.Format_Grayscale8)
            self.pixmap_sobel = QPixmap.fromImage(qimg_sobel.copy())

        # Build QPainterPath for vector lines
        v_path = QPainterPath()
        h_path = QPainterPath()

        for stroke in result.paths:
            target_path = h_path if stroke.is_hatch else v_path
            if stroke.is_bezier and stroke.cubic_segments:
                p1 = stroke.cubic_segments[0][0]
                target_path.moveTo(p1[0], p1[1])
                for _, c1, c2, p2 in stroke.cubic_segments:
                    target_path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
            else:
                pts = stroke.points
                if len(pts) >= 2:
                    target_path.moveTo(pts[0][0], pts[0][1])
                    for pt in pts[1:]:
                        target_path.lineTo(pt[0], pt[1])

        self.cached_vector_path = v_path
        self.cached_hatch_path = h_path
        self.update()

    def fit_to_view(self) -> None:
        """Scale and center image within current widget bounds."""
        if not self.result:
            return
        w, h = float(self.result.width), float(self.result.height)
        if w <= 0 or h <= 0:
            return

        avail_w = float(self.width() - 40)
        avail_h = float(self.height() - 40)

        scale = min(avail_w / w, avail_h / h)
        self.zoom = max(0.05, min(scale, 10.0))

        # Center on widget
        self.pan_offset = QPointF(
            (self.width() - w * self.zoom) / 2.0,
            (self.height() - h * self.zoom) / 2.0,
        )
        self.sig_zoom_changed.emit(self.zoom)
        self.update()

    def reset_zoom(self) -> None:
        """Reset to 100% 1:1 zoom."""
        self.zoom = 1.0
        if self.result:
            self.pan_offset = QPointF(
                (self.width() - self.result.width) / 2.0,
                (self.height() - self.result.height) / 2.0,
            )
        else:
            self.pan_offset = QPointF(0.0, 0.0)
        self.sig_zoom_changed.emit(self.zoom)
        self.update()

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode
        self.update()

    def set_paper_style(self, style: str) -> None:
        self.paper_style = style
        self.update()

    def set_overlay_opacity(self, opacity: float) -> None:
        self.overlay_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Smooth zooming anchored at mouse cursor."""
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            return

        factor = 1.15 if angle_delta > 0 else (1.0 / 1.15)
        old_zoom = self.zoom
        new_zoom = max(0.05, min(self.zoom * factor, 30.0))

        # Zoom centered at cursor pos
        mouse_pos = event.position()
        self.pan_offset = mouse_pos - (mouse_pos - self.pan_offset) * (new_zoom / old_zoom)
        self.zoom = new_zoom
        self.sig_zoom_changed.emit(self.zoom)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self.is_panning = True
            self.last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        curr_pos = event.position()
        if self.is_panning:
            delta = curr_pos - self.last_mouse_pos
            self.pan_offset += delta
            self.last_mouse_pos = curr_pos
            self.update()

        # Emit coordinate info
        if self.result and self.zoom > 0:
            img_x = (curr_pos.x() - self.pan_offset.x()) / self.zoom
            img_y = (curr_pos.y() - self.pan_offset.y()) / self.zoom
            if 0 <= img_x < self.result.width and 0 <= img_y < self.result.height:
                self.sig_hover_info.emit(f"X: {int(img_x)} px | Y: {int(img_y)} px")
            else:
                self.sig_hover_info.emit("")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Draw dark canvas background with subtle grid
        self._draw_canvas_background(painter)

        if not self.result:
            # Draw placeholder message
            painter.setPen(QColor("#71717a"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Kein Bild geladen.\nZiehe ein Bild per Drag & Drop hierher\noder wähle ein Bild in der Seitenleiste.",
            )
            return

        w, h = float(self.result.width), float(self.result.height)

        # Apply Zoom & Pan transform
        painter.save()
        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        img_rect = QRectF(0.0, 0.0, w, h)

        # 1. Background of the artwork
        bg_col = QColor("#ffffff")
        if self.paper_style == "paper":
            bg_col = QColor("#faf5eb")  # Warm cream sketchbook
        elif self.paper_style == "dark":
            bg_col = QColor("#18181b")  # Dark charcoal

        painter.fillRect(img_rect, bg_col)

        # 2. Render depending on selected display mode
        if self.display_mode == "preprocess" and self.pixmap_preprocess:
            painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)

        elif self.display_mode == "sobel" and self.pixmap_sobel:
            painter.drawPixmap(img_rect.toRect(), self.pixmap_sobel)

        elif self.display_mode == "overlay":
            # Draw image first
            if self.pixmap_preprocess:
                painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)
            # Overlay vector lines with opacity
            painter.setOpacity(self.overlay_opacity)
            self._render_vector_paths(painter)
            painter.setOpacity(1.0)

        else:  # "vector"
            self._render_vector_paths(painter)

        # Draw neat border around the artwork sheet
        border_pen = QPen(QColor("#3f3f46"), 1.0 / self.zoom)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(img_rect)

        painter.restore()

    def _render_vector_paths(self, painter: QPainter) -> None:
        """Render contours and hatching paths with appropriate pen colors and widths."""
        stroke_color = QColor("#111111")
        if self.paper_style == "dark" and self.display_mode == "vector":
            stroke_color = QColor("#38bdf8")

        # 1. Render hatching (slightly thinner stroke)
        if self.cached_hatch_path:
            hatch_pen = QPen(stroke_color)
            hatch_pen.setWidthF(max(0.6, 0.8 / math.sqrt(self.zoom)))
            hatch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            hatch_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(hatch_pen)
            painter.drawPath(self.cached_hatch_path)

        # 2. Render contours
        if self.cached_vector_path:
            vector_pen = QPen(stroke_color)
            vector_pen.setWidthF(max(0.8, 1.1 / math.sqrt(self.zoom)))
            vector_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            vector_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(vector_pen)
            painter.drawPath(self.cached_vector_path)

    def _draw_canvas_background(self, painter: QPainter) -> None:
        """Draw viewport backdrop with subtle dots or grid pattern."""
        painter.fillRect(self.rect(), QColor("#09090b"))


class PreviewWidget(QWidget):
    """Compound preview widget with view tabs, zoom controls, and canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header toolbar with view mode buttons and zoom controls
        header_bar = QFrame()
        header_bar.setStyleSheet("background-color: #18181b; border-bottom: 1px solid #27272a; padding: 4px;")
        h_layout = QHBoxLayout(header_bar)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(10)

        # View mode selector
        h_layout.addWidget(QLabel("Ansicht:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Plot-Ergebnis (Vektor)",
            "Original / Vorverarbeitung",
            "Kanten / Sobel-Karte",
            "Überlagerung (Overlay)",
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        h_layout.addWidget(self.combo_mode)

        # Overlay opacity slider (only shown when in overlay mode)
        self.label_opacity = QLabel("Deckkraft:")
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(70)
        self.slider_opacity.setFixedWidth(100)
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        self.label_opacity.setVisible(False)
        self.slider_opacity.setVisible(False)
        h_layout.addWidget(self.label_opacity)
        h_layout.addWidget(self.slider_opacity)

        # Paper color selector
        h_layout.addWidget(QLabel("Papier:"))
        self.combo_paper = QComboBox()
        self.combo_paper.addItems(["Weiß", "Pergament / Creme", "Dunkel"])
        self.combo_paper.currentIndexChanged.connect(self._on_paper_changed)
        h_layout.addWidget(self.combo_paper)

        h_layout.addStretch()

        # Zoom buttons & label
        self.btn_fit = QPushButton("An Fenster anpassen")
        self.btn_fit.clicked.connect(self._on_fit_clicked)
        h_layout.addWidget(self.btn_fit)

        self.btn_100 = QPushButton("100 %")
        self.btn_100.clicked.connect(self._on_100_clicked)
        h_layout.addWidget(self.btn_100)

        self.label_zoom = QLabel("100%")
        self.label_zoom.setStyleSheet("color: #38bdf8; font-weight: bold; min-width: 48px;")
        h_layout.addWidget(self.label_zoom)

        layout.addWidget(header_bar)

        # Interactive canvas
        self.canvas = CanvasView()
        self.canvas.sig_zoom_changed.connect(self._update_zoom_label)
        layout.addWidget(self.canvas, 1)

        # Footer info bar
        footer_bar = QFrame()
        footer_bar.setStyleSheet("background-color: #18181b; border-top: 1px solid #27272a; padding: 2px 8px;")
        f_layout = QHBoxLayout(footer_bar)
        f_layout.setContentsMargins(8, 2, 8, 2)

        self.label_coords = QLabel("")
        self.label_coords.setStyleSheet("color: #71717a;")
        self.canvas.sig_hover_info.connect(self.label_coords.setText)
        f_layout.addWidget(self.label_coords)

        f_layout.addStretch()
        layout.addWidget(footer_bar)

    def set_result(self, result: EngineResult) -> None:
        """Forward vectorization result to canvas."""
        self.canvas.set_result(result)
        self.canvas.fit_to_view()

    def _on_mode_changed(self, index: int) -> None:
        modes = ["vector", "preprocess", "sobel", "overlay"]
        selected = modes[index]
        self.canvas.set_display_mode(selected)
        is_overlay = (selected == "overlay")
        self.label_opacity.setVisible(is_overlay)
        self.slider_opacity.setVisible(is_overlay)

    def _on_paper_changed(self, index: int) -> None:
        styles = ["white", "paper", "dark"]
        self.canvas.set_paper_style(styles[index])

    def _on_opacity_changed(self, val: int) -> None:
        self.canvas.set_overlay_opacity(val / 100.0)

    def _on_fit_clicked(self) -> None:
        self.canvas.fit_to_view()

    def _on_100_clicked(self) -> None:
        self.canvas.reset_zoom()

    def _update_zoom_label(self, zoom: float) -> None:
        self.label_zoom.setText(f"{int(round(zoom * 100))}%")
