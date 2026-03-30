from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from PyQt6.QtWidgets import QWidget, QMenu, QApplication

from .i18n import tr
from .utils import Segment, format_display_time


class TimelineWidget(QWidget):
    seekRequested = pyqtSignal(int)       # ms
    inPointChanged = pyqtSignal(int)      # ms
    outPointChanged = pyqtSignal(int)     # ms
    segmentAddRequested = pyqtSignal()
    segmentRemoveRequested = pyqtSignal(int)  # index

    # Colors
    BG_COLOR = QColor(30, 30, 30)
    RULER_COLOR = QColor(60, 60, 60)
    SEGMENT_COLOR = QColor(50, 160, 80, 180)
    SEGMENT_BORDER = QColor(80, 200, 100)
    PLAYHEAD_COLOR = QColor(255, 255, 255)
    IN_COLOR = QColor(255, 220, 50)
    OUT_COLOR = QColor(255, 220, 50)
    RANGE_COLOR = QColor(255, 220, 50, 60)
    ZOOM_BAR_COLOR = QColor(80, 80, 80)
    ZOOM_BAR_HANDLE = QColor(120, 120, 120)
    WAVEFORM_COLOR = QColor(70, 180, 130, 200)

    WAVEFORM_HEIGHT = 28
    RULER_HEIGHT = 20
    MIN_WIDTH = 1
    MAX_ZOOM = 200.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(self.WAVEFORM_HEIGHT + self.RULER_HEIGHT + 40)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._duration_ms: int = 0
        self._position_ms: int = 0
        self._in_point_ms: int = -1
        self._out_point_ms: int = -1
        self._segments: list[Segment] = []
        self._dragging = False
        self._waveform: list[float] = []

        # Zoom / scroll state
        self._zoom: float = 1.0          # 1.0 = full view
        self._view_start_ms: int = 0     # left edge of visible area

    # --- Public API ---

    def set_duration(self, ms: int) -> None:
        self._duration_ms = ms
        self._zoom = 1.0
        self._view_start_ms = 0
        self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = ms
        self._ensure_visible(ms)
        self.update()

    def set_in_point(self, ms: int) -> None:
        self._in_point_ms = ms
        self.update()

    def set_out_point(self, ms: int) -> None:
        self._out_point_ms = ms
        self.update()

    def set_segments(self, segments: list[Segment]) -> None:
        self._segments = list(segments)
        self.update()

    def clear_in_out(self) -> None:
        self._in_point_ms = -1
        self._out_point_ms = -1
        self.update()

    def set_waveform(self, data: list[float]) -> None:
        self._waveform = data
        self.update()

    def zoom_level(self) -> float:
        return self._zoom

    # --- Zoom helpers ---

    def _view_duration_ms(self) -> int:
        """How many ms are visible in the current view."""
        if self._duration_ms <= 0:
            return 1
        return max(1, int(self._duration_ms / self._zoom))

    def _clamp_view(self) -> None:
        vd = self._view_duration_ms()
        self._view_start_ms = max(0, min(self._view_start_ms, self._duration_ms - vd))

    def _ensure_visible(self, ms: int) -> None:
        """Scroll so that ms is within the visible range."""
        if self._duration_ms <= 0:
            return
        vd = self._view_duration_ms()
        if ms < self._view_start_ms:
            self._view_start_ms = ms
        elif ms > self._view_start_ms + vd:
            self._view_start_ms = ms - vd
        self._clamp_view()

    # --- Coordinate conversion ---

    def _x_to_ms(self, x: int) -> int:
        if self._duration_ms <= 0 or self.width() <= self.MIN_WIDTH:
            return 0
        vd = self._view_duration_ms()
        ms = self._view_start_ms + int(x / self.width() * vd)
        return max(0, min(ms, self._duration_ms))

    def _ms_to_x(self, ms: int) -> int:
        if self._duration_ms <= 0:
            return 0
        vd = self._view_duration_ms()
        if vd <= 0:
            return 0
        return int((ms - self._view_start_ms) / vd * self.width())

    # --- Paint ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()
        ruler_top = self.WAVEFORM_HEIGHT
        track_top = self.WAVEFORM_HEIGHT + self.RULER_HEIGHT
        track_h = h - track_top

        # Background
        painter.fillRect(0, 0, w, h, self.BG_COLOR)

        if self._duration_ms <= 0:
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, tr("tl_open_hint"))
            return

        # Waveform area
        self._draw_waveform(painter, w)

        # Ruler background
        painter.fillRect(0, ruler_top, w, self.RULER_HEIGHT, self.RULER_COLOR)

        # Ruler ticks & labels
        self._draw_ruler(painter, w, ruler_top)

        # Segments (green bars)
        for seg in self._segments:
            x1 = self._ms_to_x(seg.start_ms)
            x2 = self._ms_to_x(seg.end_ms)
            if x2 < 0 or x1 > w:
                continue
            painter.fillRect(x1, track_top, max(x2 - x1, 2), track_h, self.SEGMENT_COLOR)
            painter.setPen(QPen(self.SEGMENT_BORDER, 1))
            painter.drawRect(x1, track_top, max(x2 - x1, 2), track_h - 1)

        # In/Out range highlight
        if self._in_point_ms >= 0 and self._out_point_ms > self._in_point_ms:
            x1 = self._ms_to_x(self._in_point_ms)
            x2 = self._ms_to_x(self._out_point_ms)
            painter.fillRect(x1, track_top, x2 - x1, track_h, self.RANGE_COLOR)

        # In-point marker
        if self._in_point_ms >= 0:
            x = self._ms_to_x(self._in_point_ms)
            if -2 <= x <= w + 2:
                painter.setPen(QPen(self.IN_COLOR, 2))
                painter.drawLine(x, track_top, x, h)
                painter.drawLine(x, track_top, x + 8, track_top)
                painter.drawLine(x, h - 2, x + 8, h - 2)

        # Out-point marker
        if self._out_point_ms >= 0:
            x = self._ms_to_x(self._out_point_ms)
            if -2 <= x <= w + 2:
                painter.setPen(QPen(self.OUT_COLOR, 2))
                painter.drawLine(x, track_top, x, h)
                painter.drawLine(x - 8, track_top, x, track_top)
                painter.drawLine(x - 8, h - 2, x, h - 2)

        # Playhead
        px = self._ms_to_x(self._position_ms)
        painter.setPen(QPen(self.PLAYHEAD_COLOR, 2))
        painter.drawLine(px, ruler_top, px, h)

        # Zoom indicator (mini scrollbar at bottom)
        if self._zoom > 1.0:
            self._draw_zoom_bar(painter, w, h)

    def _draw_zoom_bar(self, painter: QPainter, w: int, h: int) -> None:
        bar_h = 4
        bar_y = h - bar_h
        painter.fillRect(0, bar_y, w, bar_h, self.ZOOM_BAR_COLOR)
        if self._duration_ms > 0:
            vd = self._view_duration_ms()
            hx = int(self._view_start_ms / self._duration_ms * w)
            hw = max(4, int(vd / self._duration_ms * w))
            painter.fillRect(hx, bar_y, hw, bar_h, self.ZOOM_BAR_HANDLE)

    def _draw_waveform(self, painter: QPainter, w: int) -> None:
        wf_h = self.WAVEFORM_HEIGHT - 2
        if not self._waveform:
            # Show dim placeholder when no data yet
            painter.fillRect(0, 0, w, self.WAVEFORM_HEIGHT, QColor(25, 25, 25))
            return
        painter.fillRect(0, 0, w, self.WAVEFORM_HEIGHT, QColor(20, 20, 20))
        total = len(self._waveform)
        vd = self._view_duration_ms()
        painter.setPen(Qt.PenStyle.NoPen)
        for x in range(w):
            ms = self._view_start_ms + int(x / w * vd)
            idx = int(ms / self._duration_ms * total)
            idx = max(0, min(idx, total - 1))
            amp = self._waveform[idx]
            bar_h = max(1, int(amp * wf_h))
            y = self.WAVEFORM_HEIGHT - 1 - bar_h
            painter.fillRect(x, y, 1, bar_h, self.WAVEFORM_COLOR)

    def _draw_ruler(self, painter: QPainter, w: int, ruler_top: int = 0) -> None:
        vd_s = self._view_duration_ms() / 1000
        view_start_s = self._view_start_ms / 1000

        pixels_per_sec = w / max(vd_s, 0.001)
        intervals = [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]
        min_pixels = 60
        tick_interval_s = intervals[-1]
        for iv in intervals:
            if pixels_per_sec * iv >= min_pixels:
                tick_interval_s = iv
                break

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(150, 150, 150))

        import math
        t_start = math.floor(view_start_s / tick_interval_s) * tick_interval_s
        t = t_start
        while t <= view_start_s + vd_s + tick_interval_s * 0.5:
            if t >= 0:
                x = int((t - view_start_s) / vd_s * w) if vd_s > 0 else 0
                if 0 <= x <= w:
                    painter.drawLine(x, ruler_top + self.RULER_HEIGHT - 5, x, ruler_top + self.RULER_HEIGHT)
                    label = format_display_time(int(t * 1000))
                    painter.drawText(x + 2, ruler_top, 100, self.RULER_HEIGHT, Qt.AlignmentFlag.AlignVCenter, label)
            t += tick_interval_s

    # --- Mouse / wheel events ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            ms = self._x_to_ms(event.pos().x())
            self.seekRequested.emit(ms)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.pos())

    def mouseMoveEvent(self, event):
        if self._dragging:
            ms = self._x_to_ms(event.pos().x())
            self.seekRequested.emit(ms)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def wheelEvent(self, event):
        if self._duration_ms <= 0:
            return
        delta = event.angleDelta().y()
        mods = event.modifiers()

        if mods & Qt.KeyboardModifier.ControlModifier:
            # Zoom in/out centered on cursor position
            cursor_ms = self._x_to_ms(event.position().x())
            factor = 1.3 if delta > 0 else (1 / 1.3)
            new_zoom = max(1.0, min(self.MAX_ZOOM, self._zoom * factor))
            if new_zoom == self._zoom:
                return
            # Keep cursor_ms at same screen position after zoom
            old_vd = self._view_duration_ms()
            self._zoom = new_zoom
            new_vd = self._view_duration_ms()
            ratio = event.position().x() / max(self.width(), 1)
            self._view_start_ms = int(cursor_ms - ratio * new_vd)
            self._clamp_view()
        elif mods & Qt.KeyboardModifier.ShiftModifier:
            # Seek cursor position
            step_ms = max(1, int(abs(delta) / 120 * 100))
            direction = 1 if delta < 0 else -1
            new_pos = max(0, min(self._position_ms + direction * step_ms, self._duration_ms))
            self.seekRequested.emit(new_pos)
        else:
            # Horizontal scroll
            vd = self._view_duration_ms()
            scroll_ms = int(vd * 0.15 * (-1 if delta > 0 else 1))
            self._view_start_ms = max(0, min(
                self._view_start_ms + scroll_ms,
                self._duration_ms - vd
            ))

        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Reset zoom on double click
            self._zoom = 1.0
            self._view_start_ms = 0
            self.update()

    def _show_context_menu(self, pos: QPoint) -> None:
        ms = self._x_to_ms(pos.x())
        menu = QMenu(self)

        menu.addAction(tr("tl_ctx_set_in").format(time=format_display_time(ms)),
                       lambda: self.inPointChanged.emit(ms))
        menu.addAction(tr("tl_ctx_set_out").format(time=format_display_time(ms)),
                       lambda: self.outPointChanged.emit(ms))
        menu.addSeparator()

        can_add = self._in_point_ms >= 0 and self._out_point_ms > self._in_point_ms
        act = menu.addAction(tr("tl_ctx_add_seg"), self.segmentAddRequested)
        act.setEnabled(can_add)

        if self._zoom > 1.0:
            menu.addSeparator()
            menu.addAction(tr("tl_ctx_reset_zoom"), self._reset_zoom)

        clicked_seg_idx = self._segment_at(ms)
        if clicked_seg_idx >= 0:
            menu.addSeparator()
            menu.addAction(
                tr("tl_ctx_remove_seg").format(n=clicked_seg_idx + 1),
                lambda idx=clicked_seg_idx: self.segmentRemoveRequested.emit(idx),
            )

        menu.exec(QCursor.pos())

    def _reset_zoom(self) -> None:
        self._zoom = 1.0
        self._view_start_ms = 0
        self.update()

    def _segment_at(self, ms: int) -> int:
        for i, seg in enumerate(self._segments):
            if seg.start_ms <= ms <= seg.end_ms:
                return i
        return -1
