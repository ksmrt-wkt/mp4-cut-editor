from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame
)

from .utils import format_display_time


class TransportControls(QWidget):
    playPauseClicked = pyqtSignal()
    setInClicked = pyqtSignal()
    setOutClicked = pyqtSignal()
    addSegmentClicked = pyqtSignal()
    stepBackClicked = pyqtSignal()
    stepForwardClicked = pyqtSignal()
    # カーソル位置を delta_ms だけ移動する
    cursorAdjustRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        # --- Row 1: 再生コントロール ---
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self._btn_step_back = QPushButton("◀◀")
        self._btn_step_back.setToolTip("1フレーム戻る (←)")
        self._btn_step_back.setFixedWidth(36)
        self._btn_step_back.clicked.connect(self.stepBackClicked)

        self._btn_play = QPushButton("▶")
        self._btn_play.setToolTip("再生/一時停止 (Space)")
        self._btn_play.setFixedWidth(40)
        self._btn_play.clicked.connect(self.playPauseClicked)

        self._btn_step_fwd = QPushButton("▶▶")
        self._btn_step_fwd.setToolTip("1フレーム進む (→)")
        self._btn_step_fwd.setFixedWidth(36)
        self._btn_step_fwd.clicked.connect(self.stepForwardClicked)

        self._time_label = QLabel("--:--.- / --:--.-")
        self._time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._time_label.setMinimumWidth(160)

        zoom_hint = QLabel("ズーム: Ctrl+ホイール  /  スクロール: ホイール  /  リセット: ダブルクリック")
        zoom_hint.setStyleSheet("font-size: 9px; color: #666;")

        for btn in [self._btn_step_back, self._btn_play, self._btn_step_fwd]:
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        row1.addWidget(self._btn_step_back)
        row1.addWidget(self._btn_play)
        row1.addWidget(self._btn_step_fwd)
        row1.addWidget(self._time_label)
        row1.addStretch()
        row1.addWidget(zoom_hint)

        # --- Row 2: カーソル微調整 + イン/アウト点設定 ---
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        # カーソル微調整ボタン
        cur_label = QLabel("カーソル微調整:")
        cur_label.setStyleSheet("font-size: 11px;")

        self._btn_m1s   = self._make_adj_btn("-1秒",   "カーソルを1秒戻す (Shift+←)")
        self._btn_m100  = self._make_adj_btn("-100ms",  "カーソルを100ms戻す")
        self._btn_m10   = self._make_adj_btn("-10ms",   "カーソルを10ms戻す")
        self._btn_p10   = self._make_adj_btn("+10ms",   "カーソルを10ms進める")
        self._btn_p100  = self._make_adj_btn("+100ms",  "カーソルを100ms進める")
        self._btn_p1s   = self._make_adj_btn("+1秒",   "カーソルを1秒進める (Shift+→)")

        self._btn_m1s.clicked.connect(lambda: self.cursorAdjustRequested.emit(-1000))
        self._btn_m100.clicked.connect(lambda: self.cursorAdjustRequested.emit(-100))
        self._btn_m10.clicked.connect(lambda: self.cursorAdjustRequested.emit(-10))
        self._btn_p10.clicked.connect(lambda: self.cursorAdjustRequested.emit(10))
        self._btn_p100.clicked.connect(lambda: self.cursorAdjustRequested.emit(100))
        self._btn_p1s.clicked.connect(lambda: self.cursorAdjustRequested.emit(1000))

        sep1 = self._make_sep()

        # イン/アウト点設定ボタン
        self._btn_in = QPushButton("[ イン点設定  (I)")
        self._btn_in.setToolTip("現在のカーソル位置をイン点に設定")
        self._btn_in.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._btn_in.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_in.clicked.connect(self.setInClicked)

        self._btn_out = QPushButton("アウト点設定 ]  (O)")
        self._btn_out.setToolTip("現在のカーソル位置をアウト点に設定")
        self._btn_out.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._btn_out.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_out.clicked.connect(self.setOutClicked)

        self._btn_add = QPushButton("+ セグメント追加  (Enter)")
        self._btn_add.setToolTip("イン〜アウト範囲をセグメントに追加")
        self._btn_add.setStyleSheet("color: #50A050; font-size: 11px;")
        self._btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add.clicked.connect(self.addSegmentClicked)

        sep2 = self._make_sep()

        # イン/アウト点の現在値表示
        in_lbl = QLabel("イン:")
        in_lbl.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._in_time_label = QLabel("--:--.---")
        self._in_time_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #FFDC32; min-width: 78px;"
        )
        out_lbl = QLabel("アウト:")
        out_lbl.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._out_time_label = QLabel("--:--.---")
        self._out_time_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #FFDC32; min-width: 78px;"
        )

        row2.addWidget(cur_label)
        row2.addWidget(self._btn_m1s)
        row2.addWidget(self._btn_m100)
        row2.addWidget(self._btn_m10)
        row2.addWidget(self._btn_p10)
        row2.addWidget(self._btn_p100)
        row2.addWidget(self._btn_p1s)
        row2.addWidget(sep1)
        row2.addWidget(self._btn_in)
        row2.addWidget(self._btn_out)
        row2.addWidget(self._btn_add)
        row2.addWidget(sep2)
        row2.addWidget(in_lbl)
        row2.addWidget(self._in_time_label)
        row2.addWidget(out_lbl)
        row2.addWidget(self._out_time_label)
        row2.addStretch()

        root.addLayout(row1)
        root.addLayout(row2)

    def _make_adj_btn(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedWidth(54)
        btn.setFixedHeight(22)
        btn.setStyleSheet("font-size: 10px;")
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #444;")
        return sep

    def update_time(self, position_ms: int, duration_ms: int) -> None:
        pos = format_display_time(position_ms)
        dur = format_display_time(duration_ms)
        self._time_label.setText(f"{pos} / {dur}")

    def update_in_time(self, ms: int) -> None:
        self._in_time_label.setText("--:--.---" if ms < 0 else _ms_precise(ms))

    def update_out_time(self, ms: int) -> None:
        self._out_time_label.setText("--:--.---" if ms < 0 else _ms_precise(ms))

    def set_playing(self, is_playing: bool) -> None:
        self._btn_play.setText("⏸" if is_playing else "▶")


def _ms_precise(ms: int) -> str:
    total_s = ms // 1000
    millis = ms % 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}.{millis:03d}"
