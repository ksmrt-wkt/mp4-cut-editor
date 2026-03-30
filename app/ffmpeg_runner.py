import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from .i18n import tr
from .utils import Segment, VideoInfo, ms_to_timestamp

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def find_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe

    winget_base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_base.exists():
        for entry in winget_base.iterdir():
            if "FFmpeg" in entry.name or "ffmpeg" in entry.name:
                for bin_path in entry.rglob("ffmpeg.exe"):
                    ffmpeg = str(bin_path)
                    ffprobe = str(bin_path.parent / "ffprobe.exe")
                    if Path(ffprobe).exists():
                        return ffmpeg, ffprobe

    raise RuntimeError(tr("ffmpeg_not_found"))


def probe(path: str) -> VideoInfo:
    _, ffprobe = find_ffmpeg()
    cmd = [
        ffprobe, "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=30, creationflags=_NO_WINDOW,
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if result.returncode != 0 or not stdout.strip():
        raise RuntimeError(tr("ffprobe_error").format(stderr=stderr or tr("ffprobe_no_output")))

    data = json.loads(stdout)
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if not video_stream:
        raise RuntimeError(tr("ffmpeg_no_video_stream"))

    duration_s = float(
        data.get("format", {}).get("duration") or video_stream.get("duration", 0)
    )
    fps = 30.0
    fps_str = video_stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        if int(den) > 0:
            fps = int(num) / int(den)

    return VideoInfo(
        duration_ms=int(duration_s * 1000),
        fps=fps,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        codec=video_stream.get("codec_name", "unknown"),
    )


# ---------------------------------------------------------------------------
# Keyframe detection  (frame-based, pict_type=I for reliability)
# ---------------------------------------------------------------------------

def find_keyframes_in_range(source_path: str, ffprobe: str,
                             start_ms: int, end_ms: int) -> list[int]:
    """Return sorted keyframe timestamps (ms) in [start_ms-30s, end_ms+30s]."""
    buf = 30_000
    scan_start = max(0.0, (start_ms - buf) / 1000)
    scan_end = (end_ms + buf) / 1000

    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-read_intervals", f"{scan_start:.3f}%{scan_end:.3f}",
        "-show_entries", "frame=best_effort_timestamp_time,pict_type",
        "-of", "csv=p=0",
        source_path,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=120, creationflags=_NO_WINDOW,
    )
    keyframes: list[int] = []
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 2 and parts[1].strip() == "I":
            try:
                keyframes.append(int(float(parts[0]) * 1000))
            except ValueError:
                pass
    return sorted(set(keyframes))


# ---------------------------------------------------------------------------
# Low-level ffmpeg helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str, timeout: int = 600) -> None:
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, creationflags=_NO_WINDOW,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(tr("ffmpeg_run_failed").format(label=label, stderr=stderr[-2000:]))


def _stream_copy(ffmpeg: str, source: str, start_ms: int, end_ms: int, out: str) -> None:
    """Stream-copy a keyframe-aligned range (start must be a keyframe)."""
    duration_ms = end_ms - start_ms
    _run([
        ffmpeg, "-y",
        "-ss", ms_to_timestamp(start_ms),   # input: fast seek to keyframe
        "-i", source,
        "-t", ms_to_timestamp(duration_ms),  # output: duration (more precise than -to)
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-map_metadata", "0",
        out,
    ], f"stream copy [{ms_to_timestamp(start_ms)}+{ms_to_timestamp(duration_ms)}]")


def _re_encode(ffmpeg: str, source: str, start_ms: int, end_ms: int, out: str) -> None:
    """Re-encode an edge segment with frame-accurate in/out using output -t."""
    duration_ms = end_ms - start_ms
    _run([
        ffmpeg, "-y",
        "-ss", ms_to_timestamp(start_ms),   # input: fast seek (accurate_seek decodes to exact frame)
        "-i", source,
        "-t", ms_to_timestamp(duration_ms),  # output: exact duration
        "-c:v", "libx264", "-crf", "17", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-avoid_negative_ts", "make_zero",
        out,
    ], f"re-encode [{ms_to_timestamp(start_ms)}+{ms_to_timestamp(duration_ms)}]")


def _concat_files(ffmpeg: str, files: list[str], out: str, tmpdir: str, tag: str) -> None:
    list_path = os.path.join(tmpdir, f"{tag}_concat.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for fp in files:
            escaped = fp.replace("\\", "/").replace("'", "\\'")
            f.write(f"file '{escaped}'\n")
    _run([
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        out,
    ], f"concat {tag}")


# ---------------------------------------------------------------------------
# Smart cut per segment
# ---------------------------------------------------------------------------

def _smart_export_segment(
    ffmpeg: str, ffprobe: str, source: str,
    start_ms: int, end_ms: int,
    tmpdir: str, seg_idx: int,
    tol_ms: int = 1,
) -> str:
    """
    Frame-accurate export of one segment:
    - HEAD : re-encode from start_ms to first keyframe inside segment
    - MIDDLE: stream-copy keyframe-to-keyframe (lossless)
    - TAIL  : re-encode from last keyframe inside segment to end_ms
    Falls back to full re-encode when no inner keyframe exists.
    """
    kfs = find_keyframes_in_range(source, ffprobe, start_ms, end_ms)

    start_on_kf = any(abs(kf - start_ms) <= tol_ms for kf in kfs)
    end_on_kf   = any(abs(kf - end_ms)   <= tol_ms for kf in kfs)

    # Keyframe to begin stream-copy (first KF strictly after start)
    copy_start = next((kf for kf in kfs if kf > start_ms + tol_ms), None)
    # Keyframe to end stream-copy (last KF strictly before end)
    copy_end   = next((kf for kf in reversed(kfs) if kf < end_ms - tol_ms), None)

    if start_on_kf:
        copy_start = start_ms
    if end_on_kf:
        copy_end = end_ms

    # Build parts list
    parts: list[str] = []

    # HEAD: re-encode start_ms → copy_start (skip when start is on keyframe)
    if copy_start is not None and not start_on_kf and copy_start > start_ms:
        p = os.path.join(tmpdir, f"s{seg_idx}_head.mp4")
        _re_encode(ffmpeg, source, start_ms, copy_start, p)
        parts.append(p)
        mid_start = copy_start
    else:
        mid_start = start_ms if start_on_kf else copy_start

    # TAIL reference point
    if copy_end is not None and not end_on_kf and copy_end < end_ms:
        mid_end = copy_end
    else:
        mid_end = end_ms if end_on_kf else copy_end

    # MIDDLE: stream-copy (only when there is a meaningful range)
    if mid_start is not None and mid_end is not None and mid_end > mid_start:
        p = os.path.join(tmpdir, f"s{seg_idx}_mid.mp4")
        _stream_copy(ffmpeg, source, mid_start, mid_end, p)
        parts.append(p)

    # TAIL: re-encode copy_end → end_ms (skip when end is on keyframe)
    if copy_end is not None and not end_on_kf and copy_end < end_ms:
        p = os.path.join(tmpdir, f"s{seg_idx}_tail.mp4")
        _re_encode(ffmpeg, source, copy_end, end_ms, p)
        parts.append(p)

    # Fallback: nothing was built → re-encode entire segment
    if not parts:
        p = os.path.join(tmpdir, f"s{seg_idx}_all.mp4")
        _re_encode(ffmpeg, source, start_ms, end_ms, p)
        return p

    out = os.path.join(tmpdir, f"s{seg_idx}_segment.mp4")
    if len(parts) == 1:
        shutil.copy2(parts[0], out)
    else:
        _concat_files(ffmpeg, parts, out, tmpdir, f"s{seg_idx}")
    return out


# ---------------------------------------------------------------------------
# Public export
# ---------------------------------------------------------------------------

def export_split(
    source_path: str,
    segments: list[Segment],
    output_dir: str,
    base_name: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    start_number: int = 1,
) -> list[str]:
    """
    Export each segment to an individual file.
    Returns a list of output paths.
    """
    ffmpeg, ffprobe = find_ffmpeg()
    tmpdir = tempfile.mkdtemp(prefix="mp4cut_")
    output_paths: list[str] = []
    try:
        total = len(segments)
        for i, seg in enumerate(segments):
            if progress_cb:
                progress_cb(i / total, tr("export_progress_segment").format(i=i + 1, total=total))
            out_path = os.path.join(output_dir, f"{base_name}_{start_number + i:03d}.mp4")
            tmp_out = _smart_export_segment(
                ffmpeg, ffprobe, source_path,
                seg.start_ms, seg.end_ms,
                tmpdir, i,
            )
            shutil.copy2(tmp_out, out_path)
            output_paths.append(out_path)

        if progress_cb:
            progress_cb(1.0, tr("export_progress_done"))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return output_paths


def export(
    source_path: str,
    segments: list[Segment],
    output_path: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> None:
    """
    Frame-accurate smart-cut export.
    Each segment boundary is re-encoded at near-lossless quality (CRF 17).
    The interior of each segment is stream-copied (truly lossless).
    """
    ffmpeg, ffprobe = find_ffmpeg()
    tmpdir = tempfile.mkdtemp(prefix="mp4cut_")
    try:
        total = len(segments)
        segment_files: list[str] = []

        for i, seg in enumerate(segments):
            if progress_cb:
                progress_cb(i / total, tr("export_progress_segment").format(i=i + 1, total=total))

            out = _smart_export_segment(
                ffmpeg, ffprobe, source_path,
                seg.start_ms, seg.end_ms,
                tmpdir, i,
            )
            segment_files.append(out)

        if progress_cb:
            progress_cb(0.95, tr("export_progress_merging"))

        if len(segment_files) == 1:
            shutil.copy2(segment_files[0], output_path)
        else:
            _concat_files(ffmpeg, segment_files, output_path, tmpdir, "final")

        if progress_cb:
            progress_cb(1.0, tr("export_progress_done"))

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
