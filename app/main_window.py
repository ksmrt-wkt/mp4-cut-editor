import os
import threading

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QProgressDialog,
    QStatusBar, QLabel, QApplication,
)

from .video_player import VideoPlayer
from .timeline_widget import TimelineWidget
from .transport_controls import TransportControls
from .segment_list import SegmentList
from .utils import Segment, VideoInfo, format_display_time
from . import ffmpeg_runner


class ExportWorker(QObject):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(list)  # list of output paths
    error = pyqtSignal(str)

    def __init__(self, source, segments, output, split: bool = False, output_dir: str = "", base_name: str = ""):
        super().__init__()
        self.source = source
        self.segments = segments
        self.output = output
        self.split = split
        self.output_dir = output_dir
        self.base_name = base_name

    def run(self):
        try:
            if self.split:
                paths = ffmpeg_runner.export_split(
                    self.source,
                    self.segments,
                    self.output_dir,
                    self.base_name,
                    lambda p, msg: self.progress.emit(p, msg),
                )
                self.finished.emit(paths)
            else:
                ffmpeg_runner.export(
                    self.source,
                    self.segments,
                    self.output,
                    lambda p, msg: self.progress.emit(p, msg),
                )
                self.finished.emit([self.output])
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP4 カットエディタ")
        self.resize(1100, 700)

        self._source_path: str = ""
        self._video_info: VideoInfo | None = None
        self._in_point_ms: int = -1
        self._out_point_ms: int = -1
        self._segments: list[Segment] = []

        self._build_ui()
        self._build_menu()
        self._connect_signals()

    # ----- UI construction -----

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Video player
        self._player = VideoPlayer()
        self._player.setMinimumHeight(200)
        splitter.addWidget(self._player)

        # Timeline
        self._timeline = TimelineWidget()
        self._timeline.setFixedHeight(80)
        splitter.addWidget(self._timeline)

        # Bottom: transport + segment list
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._transport = TransportControls()
        self._segment_list = SegmentList()
        self._segment_list.setMaximumWidth(320)

        bottom_layout.addWidget(self._transport, 1)
        bottom_layout.addWidget(self._segment_list)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)

        root.addWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("ファイルを開いてください  (Ctrl+O)")
        self._status.addWidget(self._status_label)

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル(&F)")
        file_menu.addAction("開く... (&O)\tCtrl+O", self._open_file)
        file_menu.addSeparator()
        self._export_action = file_menu.addAction("エクスポート... (&E)\tCtrl+E", self._export)
        self._export_action.setEnabled(False)
        file_menu.addSeparator()
        file_menu.addAction("終了 (&Q)\tCtrl+Q", self.close)

        edit_menu = menubar.addMenu("編集(&E)")
        edit_menu.addAction("イン点を設定\tI", self._set_in_at_current)
        edit_menu.addAction("アウト点を設定\tO", self._set_out_at_current)
        edit_menu.addAction("セグメント追加\tEnter", self._add_segment)
        edit_menu.addSeparator()
        edit_menu.addAction("全セグメントをクリア", self._clear_segments)

    def _connect_signals(self):
        # Player → timeline / transport
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Timeline → main
        self._timeline.seekRequested.connect(self._player.seek)
        self._timeline.inPointChanged.connect(self._set_in_point)
        self._timeline.outPointChanged.connect(self._set_out_point)
        self._timeline.segmentAddRequested.connect(self._add_segment)
        self._timeline.segmentRemoveRequested.connect(self._remove_segment)

        # Transport controls → main
        self._transport.playPauseClicked.connect(self._player.toggle_play)
        self._transport.setInClicked.connect(self._set_in_at_current)
        self._transport.setOutClicked.connect(self._set_out_at_current)
        self._transport.addSegmentClicked.connect(self._add_segment)
        self._transport.stepBackClicked.connect(self._step_back)
        self._transport.stepForwardClicked.connect(self._step_forward)
        self._transport.cursorAdjustRequested.connect(self._adjust_cursor)
        self._transport.volumeChanged.connect(self._player.set_volume)

        # Segment list → main
        self._segment_list.segmentRemoveRequested.connect(self._remove_segment)

    # ----- File operations -----

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "MP4ファイルを開く", "",
            "動画ファイル (*.mp4 *.MP4 *.m4v *.mov *.mkv *.avi);;全ファイル (*)"
        )
        if not path:
            return
        try:
            info = ffmpeg_runner.probe(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイルの読み込みに失敗しました:\n{e}")
            return

        self._source_path = path
        self._video_info = info
        self._segments.clear()
        self._in_point_ms = -1
        self._out_point_ms = -1

        self._player.load(path)
        self._timeline.set_duration(info.duration_ms)
        self._timeline.set_segments([])
        self._timeline.clear_in_out()
        self._transport.update_in_time(-1)
        self._transport.update_out_time(-1)
        self._segment_list.update_segments([])
        self._export_action.setEnabled(True)

        fname = os.path.basename(path)
        self.setWindowTitle(f"MP4 カットエディタ — {fname}")
        self._update_status()

    def _export(self):
        if not self._source_path:
            return
        if not self._segments:
            QMessageBox.warning(self, "セグメントなし",
                                "エクスポートするセグメントがありません。\n"
                                "イン点とアウト点を設定してセグメントを追加してください。")
            return

        # 連結 / 分割 の選択
        msg = QMessageBox(self)
        msg.setWindowTitle("エクスポート方法")
        msg.setText(f"エクスポート方法を選択してください\n({len(self._segments)} セグメント)")
        btn_concat = msg.addButton("連結して1ファイル", QMessageBox.ButtonRole.AcceptRole)
        btn_split  = msg.addButton("セグメントごとに分割", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked not in (btn_concat, btn_split):
            return
        split = (clicked == btn_split)

        base, _ = os.path.splitext(self._source_path)
        base_name = os.path.basename(base)

        if split:
            output_dir = QFileDialog.getExistingDirectory(
                self, "出力フォルダを選択", os.path.dirname(self._source_path)
            )
            if not output_dir:
                return
            worker = ExportWorker(
                self._source_path, list(self._segments), "",
                split=True, output_dir=output_dir, base_name=base_name + "_output",
            )
        else:
            default_out = base + "_output.mp4"
            out_path, _ = QFileDialog.getSaveFileName(
                self, "保存先を選択", default_out,
                "MP4ファイル (*.mp4);;全ファイル (*)"
            )
            if not out_path:
                return
            worker = ExportWorker(self._source_path, list(self._segments), out_path)

        # Progress dialog
        dlg = QProgressDialog("エクスポート中...", "キャンセル", 0, 100, self)
        dlg.setWindowTitle("エクスポート")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)

        thread = QThread(self)
        worker.moveToThread(thread)

        worker.progress.connect(lambda p, msg: (
            dlg.setValue(int(p * 100)),
            dlg.setLabelText(msg),
        ))
        worker.finished.connect(lambda paths: self._on_export_finished(dlg, thread, paths))
        worker.error.connect(lambda e: self._on_export_error(dlg, thread, e))
        thread.started.connect(worker.run)
        thread.start()

        dlg.exec()
        if dlg.wasCanceled():
            thread.quit()

    def _on_export_finished(self, dlg, thread, paths: list):
        dlg.setValue(100)
        thread.quit()
        thread.wait()
        if len(paths) == 1:
            QMessageBox.information(self, "完了", f"エクスポートが完了しました:\n{paths[0]}")
        else:
            files = "\n".join(os.path.basename(p) for p in paths)
            QMessageBox.information(self, "完了",
                f"{len(paths)} ファイルをエクスポートしました:\n"
                f"{os.path.dirname(paths[0])}\n\n{files}"
            )

    def _on_export_error(self, dlg, thread, error_msg):
        dlg.cancel()
        thread.quit()
        thread.wait()
        QMessageBox.critical(self, "エクスポートエラー", error_msg)

    # ----- In/Out points -----

    def _set_in_at_current(self):
        self._set_in_point(self._player.position())

    def _set_out_at_current(self):
        self._set_out_point(self._player.position())

    def _set_in_point(self, ms: int):
        self._in_point_ms = ms
        self._timeline.set_in_point(ms)
        self._transport.update_in_time(ms)
        self._update_status()

    def _set_out_point(self, ms: int):
        self._out_point_ms = ms
        self._timeline.set_out_point(ms)
        self._transport.update_out_time(ms)
        self._update_status()

    def _adjust_cursor(self, delta_ms: int):
        dur = self._player.duration() or (self._video_info.duration_ms if self._video_info else 0)
        new_ms = max(0, min(self._player.position() + delta_ms, dur))
        self._player.seek(new_ms)

    # ----- Segments -----

    def _add_segment(self):
        if self._in_point_ms < 0 or self._out_point_ms < 0:
            QMessageBox.warning(self, "イン/アウト点未設定",
                                "イン点とアウト点を設定してからセグメントを追加してください。")
            return
        if self._out_point_ms <= self._in_point_ms:
            QMessageBox.warning(self, "範囲エラー",
                                "アウト点はイン点より後に設定してください。")
            return

        new_seg = Segment(self._in_point_ms, self._out_point_ms)

        # Check overlap
        for seg in self._segments:
            if not (new_seg.end_ms <= seg.start_ms or new_seg.start_ms >= seg.end_ms):
                QMessageBox.warning(self, "重複エラー",
                                    "既存のセグメントと重複しています。")
                return

        self._segments.append(new_seg)
        self._segments.sort(key=lambda s: s.start_ms)

        self._in_point_ms = -1
        self._out_point_ms = -1
        self._timeline.clear_in_out()
        self._transport.update_in_time(-1)
        self._transport.update_out_time(-1)
        self._timeline.set_segments(self._segments)
        self._segment_list.update_segments(self._segments)
        self._update_status()

    def _remove_segment(self, index: int):
        if 0 <= index < len(self._segments):
            self._segments.pop(index)
            self._timeline.set_segments(self._segments)
            self._segment_list.update_segments(self._segments)
            self._update_status()

    def _clear_segments(self):
        if not self._segments:
            return
        reply = QMessageBox.question(self, "確認", "全セグメントを削除しますか？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._segments.clear()
            self._timeline.set_segments([])
            self._segment_list.update_segments([])
            self._update_status()

    # ----- Playback helpers -----

    def _step_back(self):
        frame_ms = self._frame_ms()
        self._player.seek(max(0, self._player.position() - frame_ms))

    def _step_forward(self):
        frame_ms = self._frame_ms()
        dur = self._player.duration()
        self._player.seek(min(dur, self._player.position() + frame_ms))

    def _frame_ms(self) -> int:
        if self._video_info and self._video_info.fps > 0:
            return int(1000 / self._video_info.fps)
        return 33  # ~30fps fallback

    # ----- Signal handlers -----

    def _on_position_changed(self, ms: int):
        self._timeline.set_position(ms)
        dur = self._player.duration()
        self._transport.update_time(ms, dur)

    def _on_duration_changed(self, ms: int):
        self._timeline.set_duration(ms)
        self._transport.update_time(self._player.position(), ms)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        self._transport.set_playing(
            state == QMediaPlayer.PlaybackState.PlayingState
        )

    # ----- Status bar -----

    def _update_status(self):
        if not self._source_path:
            self._status_label.setText("ファイルを開いてください  (Ctrl+O)")
            return

        fname = os.path.basename(self._source_path)
        n = len(self._segments)
        total_ms = sum(s.duration_ms for s in self._segments)
        in_str = format_display_time(self._in_point_ms) if self._in_point_ms >= 0 else "未設定"
        out_str = format_display_time(self._out_point_ms) if self._out_point_ms >= 0 else "未設定"
        self._status_label.setText(
            f"{fname}  |  セグメント: {n}個 / {format_display_time(total_ms)}  "
            f"|  イン: {in_str}  アウト: {out_str}"
        )

    # ----- Keyboard shortcuts -----

    def keyPressEvent(self, event):
        key = event.key()
        mod = event.modifiers()

        if key == Qt.Key.Key_Space:
            self._player.toggle_play()
        elif key == Qt.Key.Key_I:
            self._set_in_at_current()
        elif key == Qt.Key.Key_O:
            self._set_out_at_current()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._add_segment()
        elif key == Qt.Key.Key_Left:
            if mod & Qt.KeyboardModifier.ShiftModifier:
                self._player.seek(max(0, self._player.position() - 5000))
            else:
                self._step_back()
        elif key == Qt.Key.Key_Right:
            if mod & Qt.KeyboardModifier.ShiftModifier:
                dur = self._player.duration()
                self._player.seek(min(dur, self._player.position() + 5000))
            else:
                self._step_forward()
        elif key == Qt.Key.Key_O and mod & Qt.KeyboardModifier.ControlModifier:
            self._open_file()
        elif key == Qt.Key.Key_E and mod & Qt.KeyboardModifier.ControlModifier:
            self._export()
        else:
            super().keyPressEvent(event)
