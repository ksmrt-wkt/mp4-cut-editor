from PyQt6.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl


class VideoPlayer(QWidget):
    positionChanged = pyqtSignal(int)   # ms
    durationChanged = pyqtSignal(int)   # ms
    playbackStateChanged = pyqtSignal(QMediaPlayer.PlaybackState)
    seekDelta = pyqtSignal(int)         # delta ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)

        self._video_widget = QVideoWidget(self)
        self._video_widget.setStyleSheet("background: black;")
        self._player.setVideoOutput(self._video_widget)
        self._video_widget.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)

        self._player.positionChanged.connect(
            lambda ms: self.positionChanged.emit(int(ms))
        )
        self._player.durationChanged.connect(
            lambda d: self.durationChanged.emit(int(d))
        )
        self._player.playbackStateChanged.connect(self.playbackStateChanged)

        # Hold-to-seek timer
        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(200)
        self._hold_timer.timeout.connect(self._on_hold_tick)
        self._hold_delta = 0

    def load(self, path: str) -> None:
        self._player.setSource(QUrl.fromLocalFile(path))

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def seek(self, ms: int) -> None:
        self._player.setPosition(ms)

    def position(self) -> int:
        return int(self._player.position())

    def duration(self) -> int:
        return int(self._player.duration())

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 - 1.0"""
        self._audio.setVolume(volume)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step_ms = max(1, int(abs(delta) / 120 * 100))
        direction = 1 if delta < 0 else -1
        self.seekDelta.emit(direction * step_ms)
        event.accept()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._video_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.RightButton:
                    self._hold_delta = 2000
                    self._hold_timer.start()
                    return True
                elif event.button() == Qt.MouseButton.LeftButton:
                    self._hold_delta = -2000
                    self._hold_timer.start()
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.LeftButton):
                    self._hold_timer.stop()
                    self._hold_delta = 0
                    return True
        return super().eventFilter(obj, event)

    def _on_hold_tick(self) -> None:
        if self._hold_delta != 0:
            self.seekDelta.emit(self._hold_delta)
