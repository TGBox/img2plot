"""
Background processing worker thread for non-blocking vectorization.
"""

from __future__ import annotations
import traceback
from typing import Optional
import numpy as np
from PySide6.QtCore import QThread, Signal

from ..core.parameters import PlotParameters
from ..core.engine import PlotEngine, EngineResult


class VectorizationWorker(QThread):
    """Worker thread that executes vectorization without freezing the GUI."""

    sig_progress = Signal(float, str)
    sig_finished = Signal(object)
    sig_error = Signal(str)

    def __init__(
        self,
        params: PlotParameters,
        image_input: str | np.ndarray,
        is_preview: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.params = params
        self.image_input = image_input
        self.is_preview = is_preview
        self._cancelled = False

    def cancel(self) -> None:
        """Request immediate thread cancellation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    def run(self) -> None:
        """Execute processing in background thread."""
        try:
            engine = PlotEngine(self.params)

            def progress_hook(fraction: float, msg: str):
                if not self._cancelled:
                    self.sig_progress.emit(fraction, msg)

            result = engine.process_image(
                image_input=self.image_input,
                is_preview=self.is_preview,
                progress_callback=progress_hook,
                is_cancelled=self.is_cancelled,
            )

            if not self._cancelled:
                self.sig_finished.emit(result)

        except Exception as e:
            if not self._cancelled:
                err_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                self.sig_error.emit(err_msg)
