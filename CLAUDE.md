# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MP4 カットエディタ — a PyQt6 desktop app for marking In/Out segments on a video timeline and exporting them with frame-accurate "smart cut" via ffmpeg. Targets Windows primarily (ffmpeg lookup falls back to WinGet install paths; subprocesses use `CREATE_NO_WINDOW`), though the repo lives on a WSL-mounted drive.

## Commands

```bash
pip install -r requirements.txt   # only dependency: PyQt6
python main.py                    # run the app (ffmpeg + ffprobe must be on PATH)
python -c "from app.main_window import MainWindow; print('OK')"   # import smoke check (no GUI)
```

There is no test suite, linter config, or build/packaging script in the repo. The import smoke check above is the only non-interactive way to catch a syntax/import break; everything else must be verified by launching the app.

## Architecture

- `main.py` — creates `QApplication`, applies the dark Fusion palette, verifies ffmpeg exists, opens `MainWindow`.
- `app/main_window.py` — the central controller. Owns all editing state (`_source_path`, `_in_point_ms`, `_out_point_ms`, `_segments: list[Segment]`) and wires child widgets together via Qt signals in `_connect_signals()`. Child widgets (`VideoPlayer`, `TimelineWidget`, `TransportControls`, `SegmentList`) do not hold authoritative state; they emit signals (seek, set in/out, add/remove segment) and are pushed updates back via setters (`set_segments`, `set_in_point`, ...). The one exception is `TimelineWidget`, which owns its own view state (`_zoom`, `_view_start_ms`) that `MainWindow` never sees; all of its drawing and hit-testing goes through `_ms_to_x` / `_x_to_ms`, so new timeline features must use those rather than assuming the full clip is on screen.
- Keyboard shortcuts are **not** Qt `QAction` shortcuts. The `Ctrl+O`-style hints in the menu strings are cosmetic text baked into `app/i18n.py`; the real dispatch is the single `MainWindow.keyPressEvent` if/elif chain. Adding or changing a shortcut means editing both places, and the chain is order-sensitive (an earlier bare-key branch shadows a later modifier branch for the same key).
- Long-running ffmpeg work runs off the UI thread using the `QObject` worker + `moveToThread(QThread)` pattern (`ExportWorker`, `WaveformWorker` in `main_window.py`). Follow this pattern for any new ffmpeg calls.
- `app/ffmpeg_runner.py` — all ffmpeg/ffprobe invocations. Pure functions, no Qt imports.
  - **Smart cut** (`_smart_export_segment`): per segment, scans keyframes (`pict_type=I` via ffprobe), re-encodes only the HEAD (start → first inner keyframe) and TAIL (last inner keyframe → end) with libx264 CRF 17 / AAC, stream-copies the MIDDLE, then concats the parts. Falls back to full re-encode when no inner keyframe exists. `export()` concatenates all segments into one file; `export_split()` writes `{base}_{NNN}.mp4` per segment starting at `start_number` (`MainWindow._export` passes `{source stem}_output` as the base, so files land as `clip_output_001.mp4`).
  - Every public function re-resolves the binaries via `find_ffmpeg()`; there is no cached handle to thread through.
  - Temp files go in `tempfile.mkdtemp(prefix="mp4cut_")` and are removed in `finally`.
  - `extract_waveform()` decodes mono 8 kHz f32 audio to compute normalized RMS bins for the timeline.
- `app/utils.py` — `Segment` / `VideoInfo` dataclasses and time formatting. All times throughout the app are **integer milliseconds**.
- `app/i18n.py` — in-code string table (`_STRINGS["ja"]`, `_STRINGS["en"]`) with `tr(key)`; falls back to `ja`, then the key. Language is persisted in `QSettings("mp4cut", "mp4cut")`. Switching language calls `MainWindow.retranslate_ui()`, which rebuilds the menu and calls each widget's `retranslate_ui()`.
  - Every user-visible string (including ffmpeg_runner error messages) goes through `tr()`; add new keys to **both** `ja` and `en`, and if a widget shows text, make sure its `retranslate_ui()` refreshes it.
- Project files (`.mp4cut`) are JSON written by `MainWindow._save_project`: `{"version": 1, "source_path", "in_point_ms", "out_point_ms", "segments": [{"start_ms", "end_ms"}]}`. Bump `version` if the schema changes.

## Conventions

- UI default language is Japanese; code comments and commit messages are in English.
- Source files are LF (enforced by `.gitattributes`: `* text=auto eol=lf`). On Windows, `core.autocrlf=true` can make a couple of files *look* CRLF in the working tree without git considering them modified — that's a local checkout artifact, not a real inconsistency; don't "fix" it with a commit.
- `.claude/` is gitignored, so editor/agent config there is local-only.
