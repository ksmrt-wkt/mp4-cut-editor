from dataclasses import dataclass


@dataclass
class Segment:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class VideoInfo:
    duration_ms: int
    fps: float
    width: int
    height: int
    codec: str


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS.mmm string for ffmpeg."""
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def format_display_time(ms: int) -> str:
    """Convert milliseconds to human-friendly HH:MM:SS.ss display (10ms precision)."""
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}.{millis // 10:02d}"
