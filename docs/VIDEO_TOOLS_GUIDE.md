# Video Tools - Unified Application Guide

## Overview

Video Tools Unified combines former standalone tools into one application:

| Tab | Former tool | Purpose |
|-----|-------------|---------|
| Video to MP3 | video_to_mp3_converter | Extract MP3 from video files |
| Format and Crop | image_format_converter | Aspect ratio, crop, image/video format |
| MP3 to Video | mp3_to_video_converter | Create video from MP3 + image or looped video |
| Combine Videos | video_editor | Multi-clip grid, transitions, export |
| Split and Chunks | (new) | Fixed intervals, single segments, JSON plans, visual trim |

**Launcher:** `launchers/video_tools_unified.bat` (Windows) or `launchers/video_tools_unified.sh` (Linux/Mac)

**Settings:** `video_tools_unified_settings.json` in the project root. Legacy `*_settings.json` files are imported once per tab on first run.

---

## Video to MP3

1. Add video files (select or drag-and-drop).
2. Set downloads and output folders.
3. Choose audio quality (128k-320k).
4. Click **Convert Selected Files** or **Convert All Files** (scans downloads folder).

Output: MP3 files in the converted folder.

---

## Format and Crop

- Select images or videos.
- Pick aspect ratio preset or custom ratio.
- Crop position: center, top, bottom, left, right.
- Output: JPG, PNG, or MP4 (with optional forward+reverse 1s clip).
- **Truncate Selected** shortens video without cropping.

---

## MP3 to Video

1. Select MP3 files.
2. Choose image or looping video source.
3. Set resolution, codec, scaling, loop mode.
4. Optional transitions between batch outputs.
5. **Convert Selected**, **Convert All**, or **Convert and Merge with Transitions**.

---

## Combine Videos

- Add clips; reorder via drag-and-drop grid.
- Optional xfade or overlay transitions.
- Preview and export combined MP4.
- Save/load project JSON.
- Export first/last frame as PNG.

---

## Split and Chunks

### Mode: Visual trim (embedded editor)

Use when you want to pick cuts by watching the video (not a full NLE, but in-tab preview + timeline).

1. Add videos and **select one** in the list.
2. Choose **Visual trim (preview + timeline)**.
3. In the editor:
   - **Play / Pause / Stop** and drag the position slider to scrub (preview includes audio when loaded).
   - On the **timeline**, drag the yellow (In) and orange (Out) handles, or click to seek.
   - **Set In (I)** / **Set Out (O)** at the playhead, or type seconds in the fields.
   - Click **Add cut** for each region you want exported.
4. Click **Run Split** to export all regions **next to the source video** as `{basename}_{id}.mp4` and matching `{basename}_{id}.mp3`.
5. Optional: **Sync cuts to JSON** copies regions into the JSON plan mode for editing or reuse.

**Shortcuts:** `I` = In, `O` = Out, `Space` = Play/Pause.

**Requirements:** `opencv-python`, `Pillow`, `numpy`, and `sounddevice` (included in `requirements.txt`).

**Limitations:** One video at a time in the editor; preview quality is reduced for responsiveness (export uses FFmpeg on the full-quality source). Very long files may take a moment to load audio for preview.

### Mode: Fixed interval

Splits into equal-length segments (e.g. 6 seconds for short-form platforms).

- **Chunk length:** seconds per segment.
- **Max chunks:** 0 = no limit.
- **Name pattern:** `{basename}_part_{index:03d}.mp4`

### Mode: Single segment

Presets:

- **First N seconds** - start at 0.
- **Last N seconds** - from end.
- **Middle N seconds** - centered in timeline.
- **Custom** - start (seconds or `middle`) + duration.

### Mode: JSON chunk plan

Paste or load a JSON file. Example:

```json
{
  "version": 1,
  "output": {
    "folder": "chunks",
    "name_pattern": "{basename}_{id}.mp4"
  },
  "segments": [
    { "id": "intro", "start": 0, "duration": 30 },
    { "id": "middle", "start": "middle", "duration": 15 },
    { "id": "outro", "start": -30, "duration": 30 }
  ]
}
```

#### Field reference

| Field | Description |
|-------|-------------|
| `version` | Plan format (use `1`) |
| `output.folder` | Output directory (relative to project root or absolute) |
| `output.name_pattern` | `{basename}`, `{id}`, `{index}` placeholders |
| `segments[].id` | Label for filename |
| `segments[].start` | Seconds, `"middle"` / `"center"`, or negative (offset from end) |
| `segments[].duration` | Length in seconds |
| `segments[].end` | Alternative to duration (end time in seconds) |

Validation: segments are clamped to video duration; zero-length segments are skipped with a warning.

---

## Requirements

- Python 3.7+
- FFmpeg (auto-install offered on Windows in Settings tab)
- Optional: `tkinterdnd2` (drag-and-drop), `opencv-python` (in-app preview), Pillow (thumbnails)

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| FFmpeg not found | Settings tab - Check FFmpeg / Install (Windows) |
| Segment copy fails | Tool retries with re-encode (libx264 + AAC) |
| No drag-and-drop | `pip install tkinterdnd2` and restart |
| No preview window | `pip install opencv-python` or use OS default player |

---

## Related

Stream Download Convert Tools (unified) no longer includes Video to MP3. Use this app after downloading from YouTube.
