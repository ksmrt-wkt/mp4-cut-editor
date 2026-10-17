# Session Notes — 2026-10-17

Record of work done in this Claude Code session, for resuming later.
Branch: `master`. All changes below are committed; nothing is staged
or pending. Delete this file (or fold its content into git history
context) once it's no longer needed.

## Completed this session (newest first)

- **`dad06c1`** Store settings in an INI file instead of the Windows
  registry. Added `MainWindow._app_settings()` (QSettings with
  `IniFormat`/`UserScope`) → `%APPDATA%\mp4cut\mp4cut.ini` on
  Windows. Use this helper for any new persisted setting instead of
  constructing `QSettings` directly.
  - Follow-up not done: the old registry key
    `HKEY_CURRENT_USER\Software\mp4cut\mp4cut` is now orphaned
    (unused) but wasn't deleted — the harness's permission classifier
    blocks registry writes/deletes. Remove manually via `regedit` if
    wanted.

- **`d15c9e6`** Default UI language is now English (`app/i18n.py`'s
  `_lang` and the `QSettings`/INI fallback both default to `"en"`).
  Switching via Settings > Language still persists as before. (Note:
  the INI currently has `language=ja` — someone switched it back to
  Japanese via the Settings menu after this change; that's expected,
  not a bug.)

- **`c0dc1b3`** The "Add Segment" button/menu item/timeline context
  menu entry relabel to "Finish Editing" (with a blue tint on the
  button) while a segment is being live-edited (see `b78a13d`
  below), and revert when editing stops.

- **`b78a13d`** New feature: click a row in the Segments list to
  live-edit that segment's Start/End. The existing I/O keys, +/-
  nudge buttons, Set In/Out buttons, and timeline right-click
  "set in/out point here" now apply directly to the selected
  segment (validated: order + overlap, excluding itself) instead of
  staging a new one. Edits land immediately. Esc, the Add/Finish
  button, or removing the edited segment all end edit mode. The
  edited segment is highlighted blue on the timeline and selected in
  the list; the status bar shows "Editing segment N (Esc to
  finish)".
  - Design discussion/decision trail: user proposed selecting a
    segment to reload it into In/Out; we discussed alternatives
    (drag-handles on timeline, numeric-entry dialog, live-edit
    hybrid) and the user picked **list-row-click to select** +
    **live/immediate apply** (no explicit commit step) — see the two
    `AskUserQuestion` answers earlier in this conversation if more
    context is needed later.

- **`2fb4a29`** The "Gap:" transport readout now shows the interval
  between the cursor and whichever single In/Out point is set (not
  just when both are set), live-updating during playback/scrubbing.
  Negative (cursor on the other side of the point) shows with a `-`
  prefix.

- **`2760181`** The bottom "controller" pane (transport controls +
  segment list) now starts at its minimum height on launch instead
  of claiming a share of the window's initial space (stretch factor
  0 + explicit `splitter.setSizes(...)`). Still freely draggable.

- **`5a047bf`** (supersedes/refines `e1877ab`) Smart-cut export bug:
  a segment's stream-copied MIDDLE part could start several seconds
  *before* the requested `start_ms`, picking up unwanted footage.
  Root cause: `find_keyframes_in_range()` truncated a keyframe's PTS
  to ms, which could land a fraction of a millisecond before the
  keyframe's true timestamp — just enough for ffmpeg's `-c copy`
  "-ss" (coarse, nearest-keyframe-at-or-before seek) to undershoot
  onto the *previous* keyframe. Fix: nudge `_stream_copy`'s own
  `-ss` forward by a small (2ms) safety margin, while leaving
  `find_keyframes_in_range()`'s rounding as the original floor
  (confirmed via pixel-diffing actual decoded frames that the
  TAIL/`_re_encode` accurate-seek path tolerates sub-ms error fine,
  so it didn't need — and would have been broken by — rounding the
  other way). Repro/verification used a real file
  (`NO6_01_06.mp4`/`NO6_01_06_output*.mp4` in the repo root — **not
  committed, user's own test media, left in place**; several
  `_fixed*`/`_new` variants from testing are also sitting there and
  can be deleted if unwanted).

- **`2256696`** Fixed `Ctrl+O` / `Ctrl+Shift+O` being unreachable:
  the bare `Key_O` branch in `MainWindow.keyPressEvent` matched
  before the Ctrl-qualified branches in the elif chain.

- **`20d23ce`** Added `CLAUDE.md` (via `/init`) and `.gitattributes`
  (`* text=auto eol=lf`) after discovering the apparent CRLF in two
  files was just a local Windows `core.autocrlf` checkout artifact,
  not a real repo inconsistency.

## Known loose ends / things flagged but not acted on

- `find_keyframes_in_range()` (`app/ffmpeg_runner.py`) matches
  keyframes via `pict_type=I` only, not the container's true
  random-access (`key_frame`) packet flag. In this session's test
  file that never caused a problem (the `pict_type=I` entries that
  weren't true keyframes were never the ones picked), but it's a
  latent source of the same class of bug (`5a047bf`) on footage with
  open-GOP non-IDR I-frames. Not fixed — flagged only.
- Old Windows registry key `HKEY_CURRENT_USER\Software\mp4cut\mp4cut`
  (see `dad06c1` above) — orphaned, needs manual removal if desired.
- Repo root has several untracked test video files from debugging
  the `5a047bf` smart-cut fix (`NO6_01_06.mp4`,
  `NO6_01_06_output.mp4`, `NO6_01_06_output_fixed.mp4`,
  `NO6_01_06_output_fixed2.mp4`, `NO6_01_06_output_new.mp4`). Not
  gitignored, not committed. Safe to delete except the original
  source `NO6_01_06.mp4` if still wanted for testing.

## How to verify the app still works after resuming

```bash
python -c "from app.main_window import MainWindow; print('OK')"   # import smoke check
python main.py                                                     # full manual check (ffmpeg/ffprobe on PATH)
```

There's no automated test suite (see `CLAUDE.md`).
