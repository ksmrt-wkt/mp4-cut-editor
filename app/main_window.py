import json
import os
import threading

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QProgressDialog,
    QStatusBar, QLabel, QApplication,
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QLineEdit, QPushButton,
)
from PyQt6.QtCore import QSettings

from .i18n import tr, set_language, get_language
from .video_player import VideoPlayer
from .timeline_widget import TimelineWidget
from .transport_controls import TransportControls
from .segment_list import SegmentList
from .utils import Segment, VideoInfo, format_display_time
from . import ffmpeg_runner


class SplitExportDialog(QDialog):
    def __init__(self, default_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_split_title"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit(default_dir)
        self._folder_edit.setPlaceholderText(tr("dlg_split_folder_placeholder"))
        browse_btn = QPushButton(tr("dlg_split_browse"))
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(browse_btn)
        form.addRow(tr("dlg_split_folder"), folder_row)

        self._spin = QSpinBox()
        self._spin.setRange(0, 9999)
        self._spin.setValue(1)
        form.addRow(tr("dlg_split_start_num"), self._spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("dlg_split_folder_select"), self._folder_edit.text())
        if d:
            self._folder_edit.setText(d)

    def _on_accept(self):
        if not self._folder_edit.text().strip():
            QMessageBox.warning(self, tr("dlg_input_error"), tr("dlg_split_folder_error"))
            return
        self.accept()

    def output_dir(self) -> str:
        return self._folder_edit.text().strip()

    def start_number(self) -> int:
        return self._spin.value()


class ExportWorker(QObject):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(list)  # list of output paths
    error = pyqtSignal(str)

    def __init__(self, source, segments, output, split: bool = False, output_dir: str = "", base_name: str = "", start_number: int = 1):
        super().__init__()
        self.source = source
        self.segments = segments
        self.output = output
        self.split = split
        self.output_dir = output_dir
        self.base_name = base_name
        self.start_number = start_number

    def run(self):
        try:
            if self.split:
                paths = ffmpeg_runner.export_split(
                    self.source,
                    self.segments,
                    self.output_dir,
                    self.base_name,
                    lambda p, msg: self.progress.emit(p, msg),
                    self.start_number,
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
        self.resize(1100, 700)

        self._source_path: str = ""
        self._video_info: VideoInfo | None = None
        self._in_point_ms: int = -1
        self._out_point_ms: int = -1
        self._segments: list[Segment] = []

        # Load saved language
        settings = QSettings("mp4cut", "mp4cut")
        saved_lang = settings.value("language", "ja")
        set_language(saved_lang)

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self.setWindowTitle(tr("app_title"))

    # ----- UI construction -----

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._player = VideoPlayer()
        self._player.setMinimumHeight(200)
        splitter.addWidget(self._player)

        self._timeline = TimelineWidget()
        self._timeline.setFixedHeight(80)
        splitter.addWidget(self._timeline)

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

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel(tr("status_open_hint"))
        self._status.addWidget(self._status_label)

    def _build_menu(self):
        menubar = self.menuBar()
        menubar.clear()

        file_menu = menubar.addMenu(tr("menu_file"))
        file_menu.addAction(tr("menu_open"), self._open_file)
        file_menu.addSeparator()
        file_menu.addAction(tr("menu_project_open"), self._load_project)
        self._save_project_action = file_menu.addAction(tr("menu_project_save"), self._save_project)
        self._save_project_action.setEnabled(bool(self._source_path))
        file_menu.addSeparator()
        self._export_action = file_menu.addAction(tr("menu_export"), self._export)
        self._export_action.setEnabled(bool(self._source_path))
        file_menu.addSeparator()
        file_menu.addAction(tr("menu_quit"), self.close)

        edit_menu = menubar.addMenu(tr("menu_edit"))
        edit_menu.addAction(tr("menu_set_in"), self._set_in_at_current)
        edit_menu.addAction(tr("menu_set_out"), self._set_out_at_current)
        edit_menu.addAction(tr("menu_add_segment"), self._add_segment)
        edit_menu.addSeparator()
        edit_menu.addAction(tr("menu_clear_segments"), self._clear_segments)

        settings_menu = menubar.addMenu(tr("menu_settings"))
        lang_menu = settings_menu.addMenu(tr("menu_language"))
        act_ja = lang_menu.addAction(tr("menu_lang_ja"), lambda: self._set_language("ja"))
        act_en = lang_menu.addAction(tr("menu_lang_en"), lambda: self._set_language("en"))
        act_ja.setCheckable(True)
        act_en.setCheckable(True)
        act_ja.setChecked(get_language() == "ja")
        act_en.setChecked(get_language() == "en")

    def _connect_signals(self):
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        self._timeline.seekRequested.connect(self._player.seek)
        self._timeline.inPointChanged.connect(self._set_in_point)
        self._timeline.outPointChanged.connect(self._set_out_point)
        self._timeline.segmentAddRequested.connect(self._add_segment)
        self._timeline.segmentRemoveRequested.connect(self._remove_segment)

        self._player.seekDelta.connect(self._adjust_cursor)

        self._transport.playPauseClicked.connect(self._player.toggle_play)
        self._transport.setInClicked.connect(self._set_in_at_current)
        self._transport.setOutClicked.connect(self._set_out_at_current)
        self._transport.addSegmentClicked.connect(self._add_segment)
        self._transport.stepBackClicked.connect(self._step_back)
        self._transport.stepForwardClicked.connect(self._step_forward)
        self._transport.cursorAdjustRequested.connect(self._adjust_cursor)
        self._transport.volumeChanged.connect(self._player.set_volume)

        self._segment_list.segmentRemoveRequested.connect(self._remove_segment)

    # ----- Language -----

    def _set_language(self, lang: str) -> None:
        set_language(lang)
        QSettings("mp4cut", "mp4cut").setValue("language", lang)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._build_menu()
        self._transport.retranslate_ui()
        self._segment_list.retranslate_ui()
        self._timeline.update()  # redraws placeholder text
        self._update_title()
        self._update_status()

    def _update_title(self) -> None:
        if self._source_path:
            fname = os.path.basename(self._source_path)
            self.setWindowTitle(f"{tr('app_title')} — {fname}")
        else:
            self.setWindowTitle(tr("app_title"))

    # ----- File operations -----

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg_open_title"), "", tr("dlg_open_filter")
        )
        if not path:
            return
        try:
            info = ffmpeg_runner.probe(path)
        except Exception as e:
            QMessageBox.critical(self, tr("err_load_title"), tr("err_load_msg").format(e=e))
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
        self._save_project_action.setEnabled(True)

        self._update_title()
        self._update_status()

    def _save_project(self):
        if not self._source_path:
            return
        base, _ = os.path.splitext(self._source_path)
        default_path = base + ".mp4cut"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_save_project_title"), default_path, tr("dlg_save_project_filter")
        )
        if not path:
            return
        data = {
            "version": 1,
            "source_path": self._source_path,
            "in_point_ms": self._in_point_ms,
            "out_point_ms": self._out_point_ms,
            "segments": [{"start_ms": s.start_ms, "end_ms": s.end_ms} for s in self._segments],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, tr("err_save_project_title"), tr("err_save_project_msg").format(e=e))

    def _load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg_load_project_title"), "", tr("dlg_load_project_filter")
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, tr("err_load_project_title"), tr("err_load_project_msg").format(e=e))
            return

        source = data.get("source_path", "")
        if not os.path.exists(source):
            QMessageBox.warning(self, tr("warn_source_missing_title"),
                                tr("warn_source_missing").format(path=source))
            return

        try:
            info = ffmpeg_runner.probe(source)
        except Exception as e:
            QMessageBox.critical(self, tr("err_load_title"), tr("err_load_msg").format(e=e))
            return

        self._source_path = source
        self._video_info = info
        self._segments = [Segment(s["start_ms"], s["end_ms"]) for s in data.get("segments", [])]
        self._in_point_ms = data.get("in_point_ms", -1)
        self._out_point_ms = data.get("out_point_ms", -1)

        self._player.load(source)
        self._timeline.set_duration(info.duration_ms)
        self._timeline.set_segments(self._segments)
        if self._in_point_ms >= 0:
            self._timeline.set_in_point(self._in_point_ms)
        else:
            self._timeline.clear_in_out()
        if self._out_point_ms >= 0:
            self._timeline.set_out_point(self._out_point_ms)
        self._transport.update_in_time(self._in_point_ms)
        self._transport.update_out_time(self._out_point_ms)
        self._segment_list.update_segments(self._segments)
        self._export_action.setEnabled(True)
        self._save_project_action.setEnabled(True)

        self._update_title()
        self._update_status()

    def _export(self):
        if not self._source_path:
            return
        if not self._segments:
            QMessageBox.warning(self, tr("warn_no_segments_title"), tr("warn_no_segments"))
            return

        msg = QMessageBox(self)
        msg.setWindowTitle(tr("dlg_export_method_title"))
        msg.setText(tr("dlg_export_method_text").format(n=len(self._segments)))
        btn_concat = msg.addButton(tr("dlg_export_concat"), QMessageBox.ButtonRole.AcceptRole)
        btn_split  = msg.addButton(tr("dlg_export_split"),  QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(tr("dlg_cancel"), QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked not in (btn_concat, btn_split):
            return
        split = (clicked == btn_split)

        base, _ = os.path.splitext(self._source_path)
        base_name = os.path.basename(base)

        if split:
            dlg = SplitExportDialog(os.path.dirname(self._source_path), self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            worker = ExportWorker(
                self._source_path, list(self._segments), "",
                split=True, output_dir=dlg.output_dir(),
                base_name=base_name + "_output",
                start_number=dlg.start_number(),
            )
        else:
            default_out = base + "_output.mp4"
            out_path, _ = QFileDialog.getSaveFileName(
                self, tr("dlg_export_save_title"), default_out, tr("dlg_export_filter")
            )
            if not out_path:
                return
            worker = ExportWorker(self._source_path, list(self._segments), out_path)

        progress_dlg = QProgressDialog(tr("dlg_exporting"), tr("dlg_cancel"), 0, 100, self)
        progress_dlg.setWindowTitle(tr("dlg_export_title"))
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)

        thread = QThread(self)
        worker.moveToThread(thread)

        worker.progress.connect(lambda p, m: (
            progress_dlg.setValue(int(p * 100)),
            progress_dlg.setLabelText(m),
        ))
        worker.finished.connect(lambda paths: self._on_export_finished(progress_dlg, thread, paths))
        worker.error.connect(lambda e: self._on_export_error(progress_dlg, thread, e))
        thread.started.connect(worker.run)
        thread.start()

        progress_dlg.exec()
        if progress_dlg.wasCanceled():
            thread.quit()

    def _on_export_finished(self, dlg, thread, paths: list):
        dlg.setValue(100)
        thread.quit()
        thread.wait()
        if len(paths) == 1:
            QMessageBox.information(self, tr("dlg_complete"),
                                    tr("export_done_single").format(path=paths[0]))
        else:
            files = "\n".join(os.path.basename(p) for p in paths)
            QMessageBox.information(self, tr("dlg_complete"),
                                    tr("export_done_multi_header").format(
                                        n=len(paths), dir=os.path.dirname(paths[0]), files=files))

    def _on_export_error(self, dlg, thread, error_msg):
        dlg.cancel()
        thread.quit()
        thread.wait()
        QMessageBox.critical(self, tr("err_export_title"), error_msg)

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
            QMessageBox.warning(self, tr("warn_no_inout_title"), tr("warn_no_inout"))
            return
        if self._out_point_ms <= self._in_point_ms:
            QMessageBox.warning(self, tr("warn_range_error_title"), tr("warn_range_error"))
            return

        new_seg = Segment(self._in_point_ms, self._out_point_ms)

        for seg in self._segments:
            if not (new_seg.end_ms <= seg.start_ms or new_seg.start_ms >= seg.end_ms):
                QMessageBox.warning(self, tr("warn_overlap_title"), tr("warn_overlap"))
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
        reply = QMessageBox.question(self, tr("warn_clear_title"), tr("warn_clear_msg"),
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
        return 33

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
            self._status_label.setText(tr("status_open_hint"))
            return

        fname = os.path.basename(self._source_path)
        n = len(self._segments)
        total_ms = sum(s.duration_ms for s in self._segments)
        in_str = format_display_time(self._in_point_ms) if self._in_point_ms >= 0 else tr("status_in_unset")
        out_str = format_display_time(self._out_point_ms) if self._out_point_ms >= 0 else tr("status_out_unset")
        self._status_label.setText(
            f"{fname}  |  {n} / {format_display_time(total_ms)}  "
            f"|  In: {in_str}  Out: {out_str}"
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
        elif key == Qt.Key.Key_O and mod & Qt.KeyboardModifier.ControlModifier and mod & Qt.KeyboardModifier.ShiftModifier:
            self._load_project()
        elif key == Qt.Key.Key_O and mod & Qt.KeyboardModifier.ControlModifier:
            self._open_file()
        elif key == Qt.Key.Key_S and mod & Qt.KeyboardModifier.ControlModifier:
            self._save_project()
        elif key == Qt.Key.Key_E and mod & Qt.KeyboardModifier.ControlModifier:
            self._export()
        else:
            super().keyPressEvent(event)
