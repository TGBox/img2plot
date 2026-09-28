"""
Background processing worker thread for non-blocking vectorization and preview generation.
A persistent worker thread processes tasks from a queue and yields the Python GIL regularly.
"""

from __future__ import annotations
import math
import time
import traceback
from dataclasses import dataclass
from typing import Optional, Any
import numpy as np
from PySide6.QtCore import QThread, Signal, QRectF, QMutex, QWaitCondition, Qt
from PySide6.QtGui import (
    QPainterPath,
    QImage,
    QPainter,
    QColor,
    QPen,
)

from ..core.parameters import PlotParameters
from ..core.engine import PlotEngine, EngineResult


@dataclass
class PreviewRenderData:
    """Pre-computed preview assets generated asynchronously on background thread."""
    result: EngineResult
    cached_vector_path: QPainterPath
    cached_hatch_path: QPainterPath
    cached_shape_path: QPainterPath = None  # type: ignore[assignment]
    pixmap_preprocess_img: Optional[QImage] = None
    pixmap_sobel_img: Optional[QImage] = None
    cached_rendered_img: Optional[QImage] = None

    def __post_init__(self):
        if self.cached_shape_path is None:
            self.cached_shape_path = QPainterPath()


@dataclass
class WorkerTask:
    params: PlotParameters
    image_input: Any
    req_id: int
    is_preview: bool = True
    paper_style: str = "white"
    display_mode: str = "vector"
    overlay_opacity: float = 0.7


class VectorizationWorker(QThread):
    """
    Persistent background worker thread that processes preview vectorization tasks.
    Stays alive throughout the application lifecycle to avoid thread creation/destruction overhead
    and completely eliminate QThread destruction crashes.
    """

    sig_progress = Signal(float, str)
    sig_finished = Signal(object, int)  # (PreviewRenderData, req_id)
    sig_error = Signal(str, int)        # (err_msg, req_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._pending_task: Optional[WorkerTask] = None
        self._current_cancelled: bool = False
        self._is_alive: bool = True
        self._is_busy: bool = False

    def submit_task(
        self,
        params: PlotParameters,
        image_input: Any,
        req_id: int,
        is_preview: bool = True,
        paper_style: str = "white",
        display_mode: str = "vector",
        overlay_opacity: float = 0.7,
    ) -> None:
        """Submit a new task. Cancels any in-progress calculation and replaces pending task."""
        self._mutex.lock()
        self._pending_task = WorkerTask(
            params=params,
            image_input=image_input,
            req_id=req_id,
            is_preview=is_preview,
            paper_style=paper_style,
            display_mode=display_mode,
            overlay_opacity=overlay_opacity,
        )
        self._current_cancelled = True
        self._cond.wakeOne()
        self._mutex.unlock()

    def cancel(self) -> None:
        """Cancel current in-progress task and clear pending tasks."""
        self._mutex.lock()
        self._pending_task = None
        self._current_cancelled = True
        self._mutex.unlock()

    def stop(self) -> None:
        """Stop worker thread cleanly upon application exit."""
        self._mutex.lock()
        self._is_alive = False
        self._pending_task = None
        self._current_cancelled = True
        self._cond.wakeOne()
        self._mutex.unlock()
        self.wait(1500)

    def is_busy(self) -> bool:
        self._mutex.lock()
        busy = self._is_busy or (self._pending_task is not None)
        self._mutex.unlock()
        return busy

    def _is_task_cancelled(self) -> bool:
        self._mutex.lock()
        cancelled = self._current_cancelled
        self._mutex.unlock()
        return cancelled

    def run(self) -> None:
        """Worker loop waiting for tasks and executing them with cancellation and GIL yielding."""
        while True:
            self._mutex.lock()
            while self._is_alive and self._pending_task is None:
                self._is_busy = False
                self._cond.wait(self._mutex)

            if not self._is_alive:
                self._mutex.unlock()
                break

            task = self._pending_task
            self._pending_task = None
            self._current_cancelled = False
            self._is_busy = True
            self._mutex.unlock()

            if task is None:
                continue

            try:
                self._execute_task(task)
            except Exception as e:
                if not self._is_task_cancelled():
                    err_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                    self.sig_error.emit(err_msg, task.req_id)

    def run_once(self, task: WorkerTask) -> None:
        """Synchronously execute a single task (used primarily for automated tests)."""
        self._current_cancelled = False
        self._execute_task(task)

    def _execute_task(self, task: WorkerTask) -> None:
        engine = PlotEngine(task.params)

        def progress_hook(fraction: float, msg: str):
            if not self._is_task_cancelled():
                self.sig_progress.emit(fraction, msg)

        result = engine.process_image(
            image_input=task.image_input,
            is_preview=task.is_preview,
            progress_callback=progress_hook,
            is_cancelled=self._is_task_cancelled,
        )

        if self._is_task_cancelled():
            return

        if not task.is_preview:
            data = PreviewRenderData(
                result=result,
                cached_vector_path=QPainterPath(),
                cached_hatch_path=QPainterPath(),
            )
            self.sig_finished.emit(data, task.req_id)
            return

        progress_hook(0.90, "Vorschau wird vorbereitet...")

        # 1. Prepare QImages for preview layers
        qimg_prep: Optional[QImage] = None
        if result.preprocessed_gray is not None:
            gray_u8 = (result.preprocessed_gray * 255.0).astype(np.uint8)
            gh, gw = gray_u8.shape
            qimg_prep = QImage(gray_u8.data, gw, gh, gw, QImage.Format.Format_Grayscale8).copy()

        qimg_sobel: Optional[QImage] = None
        if result.sobel_magnitude is not None:
            sobel_u8 = (result.sobel_magnitude * 255.0).astype(np.uint8)
            sh, sw = sobel_u8.shape
            qimg_sobel = QImage(sobel_u8.data, sw, sh, sw, QImage.Format.Format_Grayscale8).copy()

        if self._is_task_cancelled():
            return

        # 2. Build QPainterPaths in background
        v_path = QPainterPath()
        h_path = QPainterPath()
        s_path = QPainterPath()  # Shape strokes

        for idx, stroke in enumerate(result.paths):
            if idx % 100 == 0:
                time.sleep(0.0001)  # Yield GIL to GUI thread
                if self._is_task_cancelled():
                    return

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
            else:
                pts = stroke.points
                if len(pts) >= 2:
                    target_path.moveTo(pts[0][0], pts[0][1])
                    for pt in pts[1:]:
                        target_path.lineTo(pt[0], pt[1])
                elif len(pts) == 1:
                    # Single-point shapes (circles, rects, text) - draw a tiny mark for preview
                    md = stroke.shape_metadata
                    if md.get("type") == "circle":
                        r = float(md.get("r", 2.0))
                        target_path.addEllipse(pts[0][0] - r, pts[0][1] - r, r * 2, r * 2)
                    else:
                        target_path.moveTo(pts[0][0] - 1, pts[0][1])
                        target_path.lineTo(pts[0][0] + 1, pts[0][1])

        if self._is_task_cancelled():
            return

        # 3. Pre-render 2x raster cache
        w, h = result.width, result.height
        cached_rendered_img: Optional[QImage] = None
        if w > 0 and h > 0:
            scale_factor = min(2.0, 2400.0 / max(w, h))
            cache_w = max(1, int(round(w * scale_factor)))
            cache_h = max(1, int(round(h * scale_factor)))
            cache_img = QImage(cache_w, cache_h, QImage.Format.Format_ARGB32_Premultiplied)

            bg_col = QColor("#ffffff")
            if task.paper_style == "paper":
                bg_col = QColor("#faf5eb")
            elif task.paper_style == "dark":
                bg_col = QColor("#18181b")
            cache_img.fill(bg_col)

            painter = QPainter(cache_img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.scale(scale_factor, scale_factor)

            img_rect = QRectF(0.0, 0.0, float(w), float(h))
            if task.display_mode == "preprocess" and qimg_prep:
                painter.drawImage(img_rect, qimg_prep)
            elif task.display_mode == "sobel" and qimg_sobel:
                painter.drawImage(img_rect, qimg_sobel)
            elif task.display_mode == "overlay":
                if qimg_prep:
                    painter.drawImage(img_rect, qimg_prep)
                painter.setOpacity(task.overlay_opacity)
                self._draw_paths(painter, v_path, h_path, task.paper_style, task.display_mode, zoom=scale_factor, s_path=s_path)
                painter.setOpacity(1.0)
            else:
                self._draw_paths(painter, v_path, h_path, task.paper_style, task.display_mode, zoom=scale_factor, s_path=s_path)

            painter.end()
            cached_rendered_img = cache_img

        if self._is_task_cancelled():
            return

        preview_data = PreviewRenderData(
            result=result,
            cached_vector_path=v_path,
            cached_hatch_path=h_path,
            cached_shape_path=s_path,
            pixmap_preprocess_img=qimg_prep,
            pixmap_sobel_img=qimg_sobel,
            cached_rendered_img=cached_rendered_img,
        )

        progress_hook(1.0, "Bereit")
        self.sig_finished.emit(preview_data, task.req_id)

    def _draw_paths(
        self,
        painter: QPainter,
        v_path: QPainterPath,
        h_path: QPainterPath,
        paper_style: str,
        display_mode: str,
        zoom: float = 1.0,
        s_path: Optional[QPainterPath] = None,
    ) -> None:
        stroke_color = QColor("#111111")
        if paper_style == "dark" and display_mode == "vector":
            stroke_color = QColor("#38bdf8")

        if not h_path.isEmpty():
            hatch_pen = QPen(stroke_color)
            hatch_pen.setWidthF(max(0.6, 0.8 / math.sqrt(max(0.1, zoom))))
            hatch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            hatch_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(hatch_pen)
            painter.drawPath(h_path)

        if s_path is not None and not s_path.isEmpty():
            shape_pen = QPen(stroke_color)
            shape_pen.setWidthF(max(0.7, 1.0 / math.sqrt(max(0.1, zoom))))
            shape_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            shape_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(shape_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(s_path)

        if not v_path.isEmpty():
            vector_pen = QPen(stroke_color)
            vector_pen.setWidthF(max(0.8, 1.1 / math.sqrt(max(0.1, zoom))))
            vector_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            vector_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(vector_pen)
            painter.drawPath(v_path)
