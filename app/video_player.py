from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl


class VideoPlayer(QWidget):
    positionChanged = pyqtSignal(int)   # ms
    durationChanged = pyqtSignal(int)   # ms
    playbackStateChanged = pyqtSignal(QMediaPlayer.PlaybackState)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)

        self._video_widget = QVideoWidget(self)
        self._video_widget.setStyleSheet("background: black;")
        self._player.setVideoOutput(self._video_widget)

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
