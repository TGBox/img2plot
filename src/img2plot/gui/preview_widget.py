"""
Interactive preview canvas for img2plot.
Supports panning, zooming, vector path rendering, Sobel edge maps, and image overlay with opacity.
Includes dual-mode hardware-like raster caching during continuous zoom/pan interaction for ultra-smooth 60 FPS performance.
"""

from __future__ import annotations
import math
from typing import Optional, List
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QTimer
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
    QLabel,
    QSlider,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
)

from ..core.engine import EngineResult, StrokePath
from .worker import PreviewRenderData


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
        self.cached_shape_path: Optional[QPainterPath] = None
        self.cached_rendered_pixmap: Optional[QPixmap] = None

    def set_preview_data(self, data: PreviewRenderData) -> None:
        """Instantly apply pre-computed background worker assets without any GUI lag."""
        self.result = data.result
        self.cached_vector_path = data.cached_vector_path
        self.cached_hatch_path = data.cached_hatch_path
        self.cached_shape_path = getattr(data, "cached_shape_path", None)
        self.pixmap_preprocess = QPixmap.fromImage(data.pixmap_preprocess_img) if data.pixmap_preprocess_img else None
        self.pixmap_sobel = QPixmap.fromImage(data.pixmap_sobel_img) if data.pixmap_sobel_img else None
        self.cached_rendered_pixmap = QPixmap.fromImage(data.cached_rendered_img) if data.cached_rendered_img else None
        self.update()

    def set_result(self, result: EngineResult | PreviewRenderData) -> None:
        """Update canvas with a new vectorization result (with synchronous fallback)."""
        if isinstance(result, PreviewRenderData):
            self.set_preview_data(result)
            return

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
        s_path = QPainterPath()

        for stroke in result.paths:
            if stroke.is_shape:
                target_path = s_path
            elif stroke.is_hatch:
                target_path = h_path
            else:
                target_path = v_path

            if stroke.is_bezier and stroke.cubic_segments:
                p1 = stroke.cubic_segments[0][0]
                target_path.moveTo(p1[0], p1[1])
                for _, c1, c2, p2 in stroke.cubic_segments:
                    target_path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
                if stroke.svg_d.strip().endswith("Z") or (stroke.cubic_segments and stroke.cubic_segments[0][0] == stroke.cubic_segments[-1][-1]):
                    target_path.closeSubpath()
            else:
                pts = stroke.points
                if len(pts) >= 2:
                    target_path.moveTo(pts[0][0], pts[0][1])
                    for pt in pts[1:]:
                        target_path.lineTo(pt[0], pt[1])
                elif len(pts) == 1:
                    md = stroke.shape_metadata
                    if md.get("type") == "circle":
                        r = float(md.get("r", 2.0))
                        target_path.addEllipse(pts[0][0] - r, pts[0][1] - r, r * 2, r * 2)
                    else:
                        target_path.moveTo(pts[0][0] - 1, pts[0][1])
                        target_path.lineTo(pts[0][0] + 1, pts[0][1])

        self.cached_vector_path = v_path
        self.cached_hatch_path = h_path
        self.cached_shape_path = s_path

        # Update high-performance raster cache
        self._update_rendered_cache()
        self.update()

    def _update_rendered_cache(self) -> None:
        """Pre-render the current artwork onto a high-res raster cache for fast zoom/pan blitting."""
        if not self.result or self.result.width <= 0 or self.result.height <= 0:
            self.cached_rendered_pixmap = None
            return

        w, h = self.result.width, self.result.height
        scale_factor = min(2.0, 2400.0 / max(w, h))
        cache_w = max(1, int(round(w * scale_factor)))
        cache_h = max(1, int(round(h * scale_factor)))
        pix = QPixmap(cache_w, cache_h)

        # Background color
        bg_col = QColor("#ffffff")
        if self.paper_style == "paper":
            bg_col = QColor("#faf5eb")
        elif self.paper_style == "dark":
            bg_col = QColor("#18181b")

        pix.fill(bg_col)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.scale(scale_factor, scale_factor)

        img_rect = QRectF(0.0, 0.0, float(w), float(h))

        if self.display_mode == "preprocess" and self.pixmap_preprocess:
            painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)
        elif self.display_mode == "sobel" and self.pixmap_sobel:
            painter.drawPixmap(img_rect.toRect(), self.pixmap_sobel)
        elif self.display_mode == "overlay":
            if self.pixmap_preprocess:
                painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)
            painter.setOpacity(self.overlay_opacity)
            self._render_vector_paths(painter, zoom=scale_factor)
            painter.setOpacity(1.0)
        else:  # "vector"
            self._render_vector_paths(painter, zoom=scale_factor)

        painter.end()
        self.cached_rendered_pixmap = pix

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
        self._update_rendered_cache()
        self.update()

    def set_paper_style(self, style: str) -> None:
        self.paper_style = style
        self._update_rendered_cache()
        self.update()

    def set_overlay_opacity(self, opacity: float) -> None:
        self.overlay_opacity = max(0.0, min(1.0, opacity))
        self._update_rendered_cache()
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
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Draw dark canvas background
        self._draw_canvas_background(painter)

        if not self.result:
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

        # FAST INTERACTION & NON-BLOCKING DISPLAY:
        # Blit pre-rendered cache if available for instant 60+ FPS performance!
        if self.cached_rendered_pixmap is not None:
            painter.drawPixmap(img_rect.toRect(), self.cached_rendered_pixmap)
        else:
            bg_col = QColor("#ffffff")
            if self.paper_style == "paper":
                bg_col = QColor("#faf5eb")
            elif self.paper_style == "dark":
                bg_col = QColor("#18181b")

            painter.fillRect(img_rect, bg_col)

            if self.display_mode == "preprocess" and self.pixmap_preprocess:
                painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)
            elif self.display_mode == "sobel" and self.pixmap_sobel:
                painter.drawPixmap(img_rect.toRect(), self.pixmap_sobel)
            elif self.display_mode == "overlay":
                if self.pixmap_preprocess:
                    painter.drawPixmap(img_rect.toRect(), self.pixmap_preprocess)
                painter.setOpacity(self.overlay_opacity)
                self._render_vector_paths(painter, zoom=self.zoom)
                painter.setOpacity(1.0)
            else:  # "vector"
                self._render_vector_paths(painter, zoom=self.zoom)

        # Draw neat border around the artwork sheet
        border_pen = QPen(QColor("#3f3f46"), 1.0 / self.zoom)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(img_rect)

        painter.restore()

    def _render_vector_paths(self, painter: QPainter, zoom: float = 1.0) -> None:
        """Render contours and hatching paths with appropriate pen colors and widths."""
        stroke_color = QColor("#111111")
        if self.paper_style == "dark" and self.display_mode == "vector":
            stroke_color = QColor("#38bdf8")

        # 1. Render hatching (slightly thinner stroke)
        if self.cached_hatch_path:
            hatch_pen = QPen(stroke_color)
            hatch_pen.setWidthF(max(0.6, 0.8 / math.sqrt(max(0.1, zoom))))
            hatch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            hatch_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(hatch_pen)
            painter.drawPath(self.cached_hatch_path)

        # 2. Render shapes
        if self.cached_shape_path and not self.cached_shape_path.isEmpty():
            shape_pen = QPen(stroke_color)
            shape_pen.setWidthF(max(0.7, 1.0 / math.sqrt(max(0.1, zoom))))
            shape_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            shape_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(shape_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.cached_shape_path)

        # 3. Render contours
        if self.cached_vector_path:
            vector_pen = QPen(stroke_color)
            vector_pen.setWidthF(max(0.8, 1.1 / math.sqrt(max(0.1, zoom))))
            vector_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            vector_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(vector_pen)
            painter.drawPath(self.cached_vector_path)

    def _draw_canvas_background(self, painter: QPainter) -> None:
        """Draw viewport backdrop."""
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

        # Checkbox: Zoomstufe beibehalten
        self.chk_keep_zoom = QCheckBox("Zoom beibehalten")
        self.chk_keep_zoom.setChecked(True)
        self.chk_keep_zoom.setToolTip(
            "Behält die aktuelle Zoomstufe und den Bildausschnitt bei Neuberechnungen bei."
        )
        h_layout.addWidget(self.chk_keep_zoom)

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

    def set_preview_data(self, data: PreviewRenderData, force_fit: bool = False) -> None:
        """Forward background-computed preview data to canvas, preserving zoom if requested."""
        is_first_load = self.canvas.result is None
        self.canvas.set_preview_data(data)

        if force_fit or is_first_load or (not self.chk_keep_zoom.isChecked()):
            self.canvas.fit_to_view()

    def set_result(self, result: EngineResult | PreviewRenderData, force_fit: bool = False) -> None:
        """Forward vectorization result to canvas, preserving zoom if requested."""
        if isinstance(result, PreviewRenderData):
            self.set_preview_data(result, force_fit=force_fit)
            return

        is_first_load = self.canvas.result is None
        self.canvas.set_result(result)

        if force_fit or is_first_load or (not self.chk_keep_zoom.isChecked()):
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
