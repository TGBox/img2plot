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
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, NamedTuple

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QRect,
    QRectF,
    QSize,
    QEvent,
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPixmapCache,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.engine import PlotEngine, EngineResult
from ..core.parameters import PlotParameters
from ..core.presets import save_user_preset
from ..core.randomizer import (
    NON_CLASSIC_ARTISTIC_MODES,
    generate_random_parameters,
    suggest_preset_name,
)
from .theme import DARK_STYLESHEET


def render_result_to_image(
    result: EngineResult,
    stroke_color: str = "#18181b",
    target_size: int = 480,
    bg_color: str = "#ffffff",
) -> QImage:
    """Render EngineResult vector paths into a crisp anti-aliased thumbnail image.

    Returns a QImage (not a QPixmap) so it can safely be produced in a worker thread.
    """
    w, h = result.width, result.height
    if w <= 0 or h <= 0:
        empty = QImage(target_size, target_size, QImage.Format.Format_ARGB32_Premultiplied)
        empty.fill(QColor(bg_color))
        return empty

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

    return img


def render_result_to_pixmap(
    result: EngineResult,
    stroke_color: str = "#18181b",
    target_size: int = 480,
    bg_color: str = "#ffffff",
) -> QPixmap:
    """GUI-thread convenience wrapper around render_result_to_image()."""
    return QPixmap.fromImage(render_result_to_image(result, stroke_color, target_size, bg_color))


# -----------------------------------------------------------------------------
# Background Worker
# -----------------------------------------------------------------------------

class PresetLabWorker(QThread):
    """Background worker for batch-rendering randomized preset variations."""

    sig_progress = Signal(int, int, str)  # current, total, status_message
    sig_item_ready = Signal(int, object, object)  # index, PlotParameters, QImage
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
                # QImage only: QPixmap must not be created outside the GUI thread.
                image = render_result_to_image(result, stroke_color=color, target_size=480)
                self.sig_item_ready.emit(idx, params, image)

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
# Virtualized Gallery (Model / Delegate / View)
#
# The gallery used to create one QFrame card with six child widgets and their own
# style sheets per variant. With 1000 variants that meant ~6000 widgets in a
# QGridLayout that was completely re-filled on every resize. The model/view
# version below keeps the data in a list model and only paints the cards that are
# currently visible, so the cost of a repaint no longer depends on the batch size.
# -----------------------------------------------------------------------------

FAVORITE_ROLE = Qt.ItemDataRole.UserRole + 1
PARAMS_ROLE = Qt.ItemDataRole.UserRole + 2
NAME_ROLE = Qt.ItemDataRole.UserRole + 3
INDEX_ROLE = Qt.ItemDataRole.UserRole + 4


@dataclass
class GalleryItem:
    """One generated variant shown in the gallery."""

    index: int
    params: PlotParameters
    pixmap: QPixmap
    suggested_name: str
    is_favorite: bool = False


def _style_label(params: PlotParameters) -> str:
    return params.artistic_mode.upper() if params.artistic_mode != "none" else "KONTUR"


class PresetGalleryModel(QAbstractListModel):
    """List model holding all generated variants of the current batch."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[GalleryItem] = []

    # --- Qt model API ---------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, NAME_ROLE):
            return item.suggested_name
        if role == Qt.ItemDataRole.DecorationRole:
            return item.pixmap
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{item.suggested_name}\nStil: {_style_label(item.params)}\nKlick aufs Bild: Großansicht"
        if role == FAVORITE_ROLE:
            return item.is_favorite
        if role == PARAMS_ROLE:
            return item.params
        if role == INDEX_ROLE:
            return item.index
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != FAVORITE_ROLE or not index.isValid():
            return False
        item = self._items[index.row()]
        fav = bool(value)
        if item.is_favorite == fav:
            return True
        item.is_favorite = fav
        self.dataChanged.emit(index, index, [FAVORITE_ROLE])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # --- Convenience API ------------------------------------------------------

    def append_item(self, item: GalleryItem) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def item_at(self, row: int) -> GalleryItem:
        return self._items[row]

    def set_all_favorites(self, fav: bool) -> None:
        if not self._items:
            return
        for item in self._items:
            item.is_favorite = fav
        # One signal for the whole range instead of one repaint per card.
        self.dataChanged.emit(self.index(0), self.index(len(self._items) - 1), [FAVORITE_ROLE])

    def favorite_items(self) -> List[GalleryItem]:
        return [it for it in self._items if it.is_favorite]

    def favorite_count(self) -> int:
        return sum(1 for it in self._items if it.is_favorite)


class FavoritesFilterProxy(QSortFilterProxyModel):
    """Optionally hides all variants that are not marked as favorite."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._favorites_only = False
        self.setDynamicSortFilter(True)  # re-filter automatically when a favorite flips

    @property
    def favorites_only(self) -> bool:
        return self._favorites_only

    def set_favorites_only(self, enabled: bool) -> None:
        if enabled == self._favorites_only:
            return
        self._favorites_only = enabled
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._favorites_only:
            return True
        src = self.sourceModel().index(source_row, 0, source_parent)
        return bool(src.data(FAVORITE_ROLE))


class _CardRects(NamedTuple):
    card: QRect
    image: QRect
    meta: QRect
    zoom: QRect
    name: QRect
    fav: QRect


class PresetCardDelegate(QStyledItemDelegate):
    """Paints a gallery card and handles clicks on its favorite / zoom areas."""

    sig_zoom_requested = Signal(object)  # QPersistentModelIndex

    TOP_GAP = 7  # half the grid spacing, so the first row doesn't touch the frame
    PAD = 10
    GAP = 6
    META_H = 22
    NAME_H = 20
    BTN_H = 28
    ZOOM_W = 28
    # Height of everything below the square image area.
    CHROME_H = META_H + NAME_H + BTN_H + 3 * GAP

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.card_size = QSize(280, 280 + self.CHROME_H)

    @classmethod
    def card_height_for_width(cls, width: int) -> int:
        # Image area is square: (width - 2*PAD) wide, (height - TOP_GAP - 2*PAD - CHROME_H) high.
        return width + cls.CHROME_H + cls.TOP_GAP

    @classmethod
    def card_rects(cls, rect: QRect) -> _CardRects:
        rect = rect.adjusted(0, cls.TOP_GAP, 0, 0)
        inner = rect.adjusted(cls.PAD, cls.PAD, -cls.PAD, -cls.PAD)
        img_h = max(40, inner.height() - cls.CHROME_H)
        image = QRect(inner.left(), inner.top(), inner.width(), img_h)
        meta_top = image.bottom() + 1 + cls.GAP
        meta = QRect(inner.left(), meta_top, inner.width() - cls.ZOOM_W - cls.GAP, cls.META_H)
        zoom = QRect(inner.right() - cls.ZOOM_W + 1, meta_top, cls.ZOOM_W, cls.META_H)
        name = QRect(inner.left(), meta_top + cls.META_H + cls.GAP, inner.width(), cls.NAME_H)
        fav = QRect(inner.left(), name.bottom() + 1 + cls.GAP, inner.width(), cls.BTN_H)
        return _CardRects(rect, image, meta, zoom, name, fav)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(self.card_size)

    @staticmethod
    def _scaled_pixmap(pixmap: QPixmap, size: QSize) -> QPixmap:
        """Smoothly scaled thumbnail, cached so scrolling doesn't rescale every frame."""
        key = f"img2plot-lab:{pixmap.cacheKey()}:{size.width()}x{size.height()}"
        cached = QPixmapCache.find(key)
        if cached is not None and not cached.isNull():
            return cached
        scaled = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        QPixmapCache.insert(key, scaled)
        return scaled

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        r = self.card_rects(option.rect)
        is_fav = bool(index.data(FAVORITE_ROLE))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        has_focus = bool(option.state & QStyle.StateFlag.State_HasFocus)
        params: PlotParameters = index.data(PARAMS_ROLE)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Card background + border
        if is_fav:
            bg, border, border_w = QColor("#1e293b"), QColor("#38bdf8"), 2.0
        else:
            bg = QColor("#18181b")
            border = QColor("#52525b") if hovered else QColor("#27272a")
            border_w = 1.0
        if has_focus:
            border, border_w = QColor("#7dd3fc"), 2.0
        painter.setPen(QPen(border, border_w))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(r.card).adjusted(1, 1, -1, -1), 10, 10)

        # Image area (white plotter paper) + thumbnail
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(QRectF(r.image), 6, 6)
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            target = r.image.adjusted(4, 4, -4, -4)
            scaled = self._scaled_pixmap(pixmap, target.size())
            x = target.left() + (target.width() - scaled.width()) // 2
            y = target.top() + (target.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        # Style badge
        base_font = QFont(option.font)
        badge_font = QFont(base_font)
        badge_font.setPixelSize(11)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_text = _style_label(params) if params is not None else ""
        fm = QFontMetrics(badge_font)
        badge_text = fm.elidedText(badge_text, Qt.TextElideMode.ElideRight, r.meta.width() - 12)
        badge_rect = QRect(r.meta.left(), r.meta.top(), fm.horizontalAdvance(badge_text) + 12, r.meta.height())
        painter.setBrush(QColor("#27272a"))
        painter.drawRoundedRect(QRectF(badge_rect), 4, 4)
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Zoom button
        painter.setPen(QPen(QColor("#3f3f46"), 1.0))
        painter.setBrush(QColor("#27272a"))
        painter.drawRoundedRect(QRectF(r.zoom), 4, 4)
        painter.setFont(base_font)
        painter.setPen(QColor("#e4e4e7"))
        painter.drawText(r.zoom, Qt.AlignmentFlag.AlignCenter, "🔍")

        # Suggested name
        name_font = QFont(base_font)
        name_font.setPixelSize(13)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#f4f4f5"))
        name = QFontMetrics(name_font).elidedText(
            str(index.data(NAME_ROLE) or ""), Qt.TextElideMode.ElideRight, r.name.width()
        )
        painter.drawText(r.name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # Favorite button
        if is_fav:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#0284c7"))
            fav_text, fav_color = "❤️  Gemerkt", QColor("#ffffff")
        else:
            painter.setPen(QPen(QColor("#3f3f46"), 1.0))
            painter.setBrush(QColor("#3f3f46") if hovered else QColor("#27272a"))
            fav_text, fav_color = "🤍  Merken", QColor("#e4e4e7")
        painter.drawRoundedRect(QRectF(r.fav), 6, 6)
        btn_font = QFont(base_font)
        btn_font.setBold(is_fav)
        painter.setFont(btn_font)
        painter.setPen(fav_color)
        painter.drawText(r.fav, Qt.AlignmentFlag.AlignCenter, fav_text)

        painter.restore()

    def editorEvent(self, event, model, option: QStyleOptionViewItem, index: QModelIndex) -> bool:
        if (
            event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            r = self.card_rects(option.rect)
            pos = event.position().toPoint()
            if r.fav.contains(pos):
                # A fast 2nd click arrives as DblClick instead of a release: toggle on both.
                model.setData(index, not bool(index.data(FAVORITE_ROLE)), FAVORITE_ROLE)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and (
                r.zoom.contains(pos) or r.image.contains(pos)
            ):
                self.sig_zoom_requested.emit(QPersistentModelIndex(index))
                return True
        return super().editorEvent(event, model, option, index)


class PresetGalleryView(QListView):
    """Icon-mode list view that sizes its grid so cards fill the full row width."""

    SPACING = 14

    sig_zoom_requested = Signal(object)  # QPersistentModelIndex

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.card_target_width = 280
        self.columns = 1

        self.card_delegate = PresetCardDelegate(self)
        self.card_delegate.sig_zoom_requested.connect(self.sig_zoom_requested)
        self.setItemDelegate(self.card_delegate)

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSpacing(0)  # spacing is part of the grid cell, see _update_grid()
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(32)
        # Always-on scrollbar: avoids grid-width <-> scrollbar visibility oscillation.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAccessibleName("Varianten-Galerie")
        self.setStyleSheet(
            "QListView { background-color: #09090b; border: 1px solid #27272a; border-radius: 8px; }"
        )

    def set_card_target_width(self, width: int) -> None:
        self.card_target_width = max(120, int(width))
        self._update_grid()

    def viewportEvent(self, event) -> bool:
        # React to the viewport's own size (window resize, fullscreen, scrollbar).
        if event.type() == QEvent.Type.Resize:
            self._update_grid()
        return super().viewportEvent(event)

    def _update_grid(self) -> None:
        if not hasattr(self, "card_delegate"):  # resize during construction
            return
        avail = self.viewport().width() - 2  # small safety margin against early wrapping
        if avail <= 0:
            return
        cell_target = self.card_target_width + self.SPACING
        cols = max(1, avail // cell_target)
        cell_w = avail // cols
        card_w = max(120, cell_w - self.SPACING)
        card_h = PresetCardDelegate.card_height_for_width(card_w)
        new_card = QSize(card_w, card_h)
        new_grid = QSize(card_w + self.SPACING, card_h + self.SPACING)
        self.columns = cols
        if self.card_delegate.card_size != new_card or self.gridSize() != new_grid:
            self.card_delegate.card_size = new_card
            self.setGridSize(new_grid)  # triggers a (cheap, delayed) items layout

    def keyPressEvent(self, event) -> None:
        idx = self.currentIndex()
        if idx.isValid():
            if event.key() == Qt.Key.Key_Space:
                self.model().setData(idx, not bool(idx.data(FAVORITE_ROLE)), FAVORITE_ROLE)
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.sig_zoom_requested.emit(QPersistentModelIndex(idx))
                return
        super().keyPressEvent(event)


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
        self.worker: Optional[PresetLabWorker] = None
        self.is_fullscreen: bool = False
        self.card_target_width: int = 280

        # App-wide cache; room for the scaled thumbnails of a few screens of cards (KB).
        QPixmapCache.setCacheLimit(max(QPixmapCache.cacheLimit(), 64 * 1024))
        self.model = PresetGalleryModel(self)
        self.proxy = FavoritesFilterProxy(self)
        self.proxy.setSourceModel(self.model)

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

        sub_bar.addSpacing(16)

        # Card size zoom slider
        sub_bar.addWidget(QLabel("<b>Vorschau-Größe:</b>"))
        self.slider_card_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_card_size.setRange(200, 520)
        self.slider_card_size.setValue(280)
        self.slider_card_size.setFixedWidth(120)
        self.slider_card_size.setToolTip("Größe der Vorschaubilder im Raster stufenlos anpassen (200px – 520px)")
        self.slider_card_size.valueChanged.connect(self._on_card_size_changed)
        sub_bar.addWidget(self.slider_card_size)

        self.lbl_card_size_val = QLabel("280 px")
        self.lbl_card_size_val.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        sub_bar.addWidget(self.lbl_card_size_val)

        sub_bar.addStretch()

        self.lbl_fav_counter = QLabel("0 von 0 gemerkt")
        self.lbl_fav_counter.setStyleSheet("font-weight: bold; color: #38bdf8;")
        sub_bar.addWidget(self.lbl_fav_counter)

        root_layout.addLayout(sub_bar)

        # 4. Virtualized gallery (only visible cards are painted)
        self.gallery_view = PresetGalleryView()
        self.gallery_view.setModel(self.proxy)
        self.gallery_view.set_card_target_width(self.card_target_width)
        # Queued: open the modal dialog after the view has finished its mouse handling.
        self.gallery_view.sig_zoom_requested.connect(
            self._open_zoom, Qt.ConnectionType.QueuedConnection
        )
        root_layout.addWidget(self.gallery_view, 1)

        self.model.dataChanged.connect(self._update_counter)
        self.model.rowsInserted.connect(self._update_counter)
        self.model.modelReset.connect(self._update_counter)

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

    def _on_card_size_changed(self, value: int) -> None:
        self.card_target_width = value
        self.lbl_card_size_val.setText(f"{value} px")
        self.gallery_view.set_card_target_width(value)

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

        # Clear existing variants
        self.model.clear()

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

    def _on_item_ready(self, index: int, params: PlotParameters, image: QImage | QPixmap) -> None:
        # The worker delivers QImage; QPixmap is created here in the GUI thread.
        pixmap = QPixmap.fromImage(image) if isinstance(image, QImage) else image
        self.model.append_item(
            GalleryItem(
                index=index,
                params=params,
                pixmap=pixmap,
                suggested_name=suggest_preset_name(params),
            )
        )

    def _on_worker_finished(self) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText(f"Fertig! {self.model.rowCount()} Varianten wurden generiert.")
        self._update_counter()

    def _on_worker_error(self, index: int, error_msg: str) -> None:
        self.lbl_status.setText(f"Fehler bei Variante {index + 1}: {error_msg}")

    # -------------------------------------------------------------------------
    # Card Management & Selection
    # -------------------------------------------------------------------------

    def _open_zoom(self, index: QPersistentModelIndex) -> None:
        if not index.isValid():
            return
        dlg = ZoomModalDialog(
            index.data(Qt.ItemDataRole.DecorationRole),
            index.data(PARAMS_ROLE),
            index.data(NAME_ROLE),
            parent=self,
        )
        dlg.exec()

    def select_all_cards(self) -> None:
        self.model.set_all_favorites(True)

    def unselect_all_cards(self) -> None:
        self.model.set_all_favorites(False)

    def _filter_all_clicked(self) -> None:
        self.btn_filter_all.setChecked(True)
        self.btn_filter_favs.setChecked(False)
        self.proxy.set_favorites_only(False)

    def _filter_favs_clicked(self) -> None:
        self.btn_filter_all.setChecked(False)
        self.btn_filter_favs.setChecked(True)
        self.proxy.set_favorites_only(True)

    def _update_counter(self, *_args) -> None:
        fav_count = self.model.favorite_count()
        total = self.model.rowCount()
        self.lbl_fav_counter.setText(f"{fav_count} von {total} gemerkt")
        self.btn_filter_favs.setText(f"Nur Gemerkte ({fav_count})")
        self.btn_save_favs.setText(f"💾  Gemerkte als Presets speichern ({fav_count})...")
        self.btn_save_favs.setEnabled(fav_count > 0)

    # -------------------------------------------------------------------------
    # Save Presets Action
    # -------------------------------------------------------------------------

    def _open_save_dialog(self) -> None:
        fav_items = [
            {
                "index": it.index,
                "params": it.params,
                "pixmap": it.pixmap,
                "suggested_name": it.suggested_name,
            }
            for it in self.model.favorite_items()
        ]

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
