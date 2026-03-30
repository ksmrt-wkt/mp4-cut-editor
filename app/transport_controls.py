from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame, QSlider
)

from .i18n import tr
from .utils import format_display_time


class TransportControls(QWidget):
    playPauseClicked = pyqtSignal()
    setInClicked = pyqtSignal()
    setOutClicked = pyqtSignal()
    addSegmentClicked = pyqtSignal()
    stepBackClicked = pyqtSignal()
    stepForwardClicked = pyqtSignal()
    cursorAdjustRequested = pyqtSignal(int)
    volumeChanged = pyqtSignal(float)  # 0.0 - 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        # --- Row 1 ---
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self._btn_step_back = QPushButton("◀◀")
        self._btn_step_back.setFixedWidth(36)
        self._btn_step_back.clicked.connect(self.stepBackClicked)

        self._btn_play = QPushButton("▶")
        self._btn_play.setFixedWidth(40)
        self._btn_play.clicked.connect(self.playPauseClicked)

        self._btn_step_fwd = QPushButton("▶▶")
        self._btn_step_fwd.setFixedWidth(36)
        self._btn_step_fwd.clicked.connect(self.stepForwardClicked)

        self._time_label = QLabel("--:--.-- / --:--.--")
        self._time_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        self._time_label.setMinimumWidth(160)

        self._zoom_hint = QLabel()
        self._zoom_hint.setStyleSheet("font-size: 9px; color: #666;")

        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("font-size: 12px;")

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(100)
        self._vol_slider.setFixedWidth(80)
        self._vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vol_slider.valueChanged.connect(
            lambda v: self.volumeChanged.emit(v / 100.0)
        )

        for btn in [self._btn_step_back, self._btn_play, self._btn_step_fwd]:
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        row1.addWidget(self._btn_step_back)
        row1.addWidget(self._btn_play)
        row1.addWidget(self._btn_step_fwd)
        row1.addWidget(self._time_label)
        row1.addStretch()
        row1.addWidget(vol_label)
        row1.addWidget(self._vol_slider)
        row1.addWidget(self._zoom_hint)

        # --- Row 2 ---
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        self._cur_label = QLabel()
        self._cur_label.setStyleSheet("font-size: 11px;")

        self._btn_m1s  = self._make_adj_btn()
        self._btn_m100 = self._make_adj_btn()
        self._btn_m10  = self._make_adj_btn()
        self._btn_p10  = self._make_adj_btn()
        self._btn_p100 = self._make_adj_btn()
        self._btn_p1s  = self._make_adj_btn()

        self._btn_m1s.clicked.connect(lambda: self.cursorAdjustRequested.emit(-1000))
        self._btn_m100.clicked.connect(lambda: self.cursorAdjustRequested.emit(-100))
        self._btn_m10.clicked.connect(lambda: self.cursorAdjustRequested.emit(-10))
        self._btn_p10.clicked.connect(lambda: self.cursorAdjustRequested.emit(10))
        self._btn_p100.clicked.connect(lambda: self.cursorAdjustRequested.emit(100))
        self._btn_p1s.clicked.connect(lambda: self.cursorAdjustRequested.emit(1000))

        sep1 = self._make_sep()

        self._btn_in = QPushButton()
        self._btn_in.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._btn_in.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_in.clicked.connect(self.setInClicked)

        self._btn_out = QPushButton()
        self._btn_out.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._btn_out.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_out.clicked.connect(self.setOutClicked)

        self._btn_add = QPushButton()
        self._btn_add.setStyleSheet("color: #50A050; font-size: 11px;")
        self._btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add.clicked.connect(self.addSegmentClicked)

        sep2 = self._make_sep()

        self._in_lbl = QLabel()
        self._in_lbl.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._in_time_label = QLabel("--:--.---")
        self._in_time_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #FFDC32; min-width: 78px;"
        )
        self._out_lbl = QLabel()
        self._out_lbl.setStyleSheet("color: #FFDC32; font-size: 11px;")
        self._out_time_label = QLabel("--:--.---")
        self._out_time_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #FFDC32; min-width: 78px;"
        )
        self._dur_lbl = QLabel()
        self._dur_lbl.setStyleSheet("color: #AADDAA; font-size: 11px;")
        self._dur_label = QLabel("--:--.---")
        self._dur_label.setStyleSheet(
            "font-family: monospace; font-size: 11px; color: #AADDAA; min-width: 78px;"
        )

        self._in_ms:  int = -1
        self._out_ms: int = -1

        row2.addWidget(self._cur_label)
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
        row2.addWidget(self._in_lbl)
        row2.addWidget(self._in_time_label)
        row2.addWidget(self._out_lbl)
        row2.addWidget(self._out_time_label)
        row2.addWidget(self._dur_lbl)
        row2.addWidget(self._dur_label)
        row2.addStretch()

        root.addLayout(row1)
        root.addLayout(row2)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._btn_step_back.setToolTip(tr("tt_step_back"))
        self._btn_play.setToolTip(tr("tt_play"))
        self._btn_step_fwd.setToolTip(tr("tt_step_fwd"))
        self._vol_slider.setToolTip(tr("tt_volume"))
        self._zoom_hint.setText(tr("zoom_hint"))
        self._cur_label.setText(tr("cursor_adj_label"))

        adj_buttons = [
            (self._btn_m1s,  "btn_m1s",  "tt_m1s"),
            (self._btn_m100, "btn_m100", "tt_m100"),
            (self._btn_m10,  "btn_m10",  "tt_m10"),
            (self._btn_p10,  "btn_p10",  "tt_p10"),
            (self._btn_p100, "btn_p100", "tt_p100"),
            (self._btn_p1s,  "btn_p1s",  "tt_p1s"),
        ]
        for btn, text_key, tip_key in adj_buttons:
            btn.setText(tr(text_key))
            btn.setToolTip(tr(tip_key))

        self._btn_in.setText(tr("btn_in"))
        self._btn_in.setToolTip(tr("tt_btn_in"))
        self._btn_out.setText(tr("btn_out"))
        self._btn_out.setToolTip(tr("tt_btn_out"))
        self._btn_add.setText(tr("btn_add_seg"))
        self._btn_add.setToolTip(tr("tt_btn_add"))

        self._in_lbl.setText(tr("lbl_in"))
        self._out_lbl.setText(tr("lbl_out"))
        self._dur_lbl.setText(tr("lbl_dur"))

    def _make_adj_btn(self) -> QPushButton:
        btn = QPushButton()
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
        self._in_ms = ms
        self._in_time_label.setText("--:--.---" if ms < 0 else _ms_precise(ms))
        self._update_duration()

    def update_out_time(self, ms: int) -> None:
        self._out_ms = ms
        self._out_time_label.setText("--:--.---" if ms < 0 else _ms_precise(ms))
        self._update_duration()

    def _update_duration(self) -> None:
        if self._in_ms >= 0 and self._out_ms >= 0 and self._out_ms > self._in_ms:
            self._dur_label.setText(_ms_precise(self._out_ms - self._in_ms))
        else:
            self._dur_label.setText("--:--.---")

    def set_playing(self, is_playing: bool) -> None:
        self._btn_play.setText("⏸" if is_playing else "▶")


def _ms_precise(ms: int) -> str:
    total_s = ms // 1000
    millis = ms % 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}.{millis:03d}"
