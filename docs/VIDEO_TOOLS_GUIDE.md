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
| Merge Split + Lip Sync | (new) | Combine split parts with optional LatentSync clips + full song MP3 |
| Upscale Video | (new) | High-quality resize (e.g. 672x448 to 1168x768), optional Real-ESRGAN |

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

Simple concat (no transitions) **re-encodes video at constant frame rate** from the first clip (usually 24 fps), then muxes clip or external audio. Stream copy is no longer used for export, because many short clips otherwise show ~23.9 fps average in the combined file.

---

## Split and Chunks

All modes write **MP4 + matching MP3** files **next to each source video** (same folder as the input file). The JSON plan `output.folder` field is ignored at export time; use `"."` in samples.

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
- **Name pattern:** `{basename}_part_{index:03d}.mp4` (plus matching `.mp3` per part).

Each chunk is exported at **constant frame rate** matching the source (probed from the input file). Older builds used FFmpeg segment + stream copy, which cut on keyframes and could yield ~23.3-23.8 fps on some chunks even when the source was labeled 24 fps.

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
    "folder": ".",
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

## Merge Split + Lip Sync

Use after **Split and Chunks** and optional LatentSync lip-sync on selected parts. Builds one combined MP4 in scene order; the **original song MP3** replaces all clip audio (same idea as Combine Videos with external audio enabled).

### Typical workflow

1. Split a storyboard video into parts (e.g. `storyboard_scene_004_000.mp4` in a `split` folder).
2. Run LatentSync on some parts; outputs often land in `split/latentsync_synced/`.
3. Open this tab, set folders and the full song MP3 (e.g. `storyboard_scene.mp3`).
4. Click **Scan / Refresh** to preview which clips use lip-sync vs original split.
5. Click **Export Combined Video**.

### Lip-sync file matching

For each split file `storyboard_scene_004_000.mp4`, the tool looks in the lip-sync folder for:

`storyboard_scene_004_000__*.mp4`

If several files match (re-runs), the **newest** file (by modification time) is used. Parts with no match keep the original split MP4.

### Fields

| Field | Description |
|-------|-------------|
| Split parts folder | Folder containing split MP4s (top-level only; subfolders such as `latentsync_synced` are not scanned as split input) |
| Lip-sync folder | LatentSync output folder (defaults to `{split}/latentsync_synced` when that path exists) |
| Original song (MP3) | Full track muxed as the output audio (`-shortest` trims to shorter of video or song) |
| Output MP4 | Combined export path |

Export **re-encodes video at constant frame rate** (from the first split clip, usually 24 fps). Stream-copy concat was avoided because LatentSync clips often differ slightly in frame count (e.g. 144 frames vs 145 per segment), which makes Windows report ~23.95 fps average even when each source is labeled 24 fps.

Settings are stored under `tabs.merge_split` in `video_tools_unified_settings.json`.

---

## Upscale Video

Batch-upscale videos to an exact width and height. Useful for raising Grok or other low-resolution exports (e.g. **672x448** to **1168x768**).

### Steps

1. Add videos (select or drag-and-drop).
2. Choose a **target resolution** preset or set width/height (even dimensions enforced).
3. Pick an **upscale method** (see below).
4. Outputs go **next to each source file** by default (`_upscaled` suffix). Uncheck that option to use a separate output folder.
5. Click **Upscale Selected** or **Upscale All Listed**.

While processing, the tab shows **file batch** progress and a **current file encode** bar with percent and time (from FFmpeg). AI mode also shows stage labels during frame extract and Real-ESRGAN.

### Methods

| Method | Description |
|--------|-------------|
| Standard (bicubic) | Fast FFmpeg `scale`; baseline quality |
| High (Lanczos) | Lanczos with accurate rounding; good default for ~1.5-2x upscale |
| Maximum | Two-step Lanczos when scale factor > 1.25x, plus light unsharp |
| AI (Real-ESRGAN) | Frame extract, AI 2x/4x upscale, then Lanczos to exact target |

### AI backends

| Backend | Description |
|---------|-------------|
| **PyTorch (venv, default)** | Official `realesrgan` Python package in the project venv. Supports all models below including **general v3**. Best quality; first run downloads weights to `realesrgan/weights/`. |
| **ncnn-vulkan (portable exe)** | Small ~45 MB portable build (2022). Fewer models; x4plus may show tile seams on video. Use **Auto Install** or browse to `realesrgan-ncnn-vulkan.exe`. |

**PyTorch models (dropdown when PyTorch backend selected):**

| Model | Best for |
|-------|----------|
| realesr-animevideov3 | AI/Grok/stylized video (default) |
| realesrgan-x2plus | Native 2x RRDB; good when target scale is ~2x |
| realesr-general-x4v3 | General scenes; use **General denoise** slider (0-1) |
| realesrgan-x4plus-anime | Anime stills / art |
| realesrgan-x4plus | Photos |
| realesrnet-x4plus | Softer than x4plus GAN |

**ncnn models:** subset of the above (no general v3). Prefer PyTorch for Grok storyboard clips.

FFmpeg modes re-encode with **libx264**, default **CRF 18** and **slow** preset. Audio is copied when possible; otherwise AAC fallback.

### Presets

- **Grok HD (1168 x 768)** - common target for Grok clips
- **720p**, **1080p**, or **Custom**

### AI mode (Real-ESRGAN)

**PyTorch (recommended):**

1. Run `launchers/video_tools_unified.bat` once so the venv installs `torch` from `requirements.txt` and runs `scripts/install_ai_upscale_deps.py` for patched `basicsr` + `realesrgan` (large download). If that script fails, run it manually: `venv\Scripts\python scripts\install_ai_upscale_deps.py`.
2. On the Upscale tab, set **AI backend** to **PyTorch (venv, recommended)**. Status should show CUDA if an NVIDIA GPU is available.
3. For **GPU speed** on Windows/NVIDIA (e.g. RTX 3060), install CUDA-enabled PyTorch in the venv (one-time):

   ```bat
   venv\Scripts\activate
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
   ```

4. Choose a model; **realesr-animevideov3** for Grok clips. First use of each model downloads weights into `realesrgan/weights/`.
5. Set **GPU id** to `0` for the primary NVIDIA card if you have multiple GPUs.

**ncnn-vulkan (optional):**

1. Set **AI backend** to **ncnn-vulkan (portable exe)**.
2. Click **Auto Install** or download from [Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0).

Expect slow processing (many PNG frames per clip). Temp frames live under `%TEMP%\video_upscale_*`; uncheck **Remove temp frames** to keep them for inspection.

AI upscale uses integer **2x** or **4x** first, then FFmpeg scales to your exact target size.

### Limitations

- Upscaling cannot add true detail beyond interpolation / AI enhancement.
- PyTorch mode needs sufficient GPU VRAM; CPU mode works but is very slow.
- ncnn mode uses a separate executable (optional fallback).
- Very long videos consume large temp disk space in AI mode.

---

## Requirements

- Python 3.10+ recommended (3.7+ minimum)
- FFmpeg (auto-install offered on Windows in Settings tab)
- AI PyTorch mode: `torch`, `realesrgan`, `basicsr` (installed via launcher); NVIDIA GPU + CUDA PyTorch recommended
- Optional: `tkinterdnd2` (drag-and-drop), `opencv-python` (in-app preview), Pillow (thumbnails)

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| FFmpeg not found | Settings tab - Check FFmpeg / Install (Windows) |
| Segment copy fails | Tool retries with re-encode (libx264 + AAC) |
| No drag-and-drop | `pip install tkinterdnd2` and restart |
| No preview window | `pip install opencv-python` or use OS default player |
| AI upscale fails | Verify exe path; check log for frame extract or encode errors |
| Output not exact size | Width/height are rounded down to even values for H.264 |

---

## Related

Stream Download Convert Tools (unified) no longer includes Video to MP3. Use this app after downloading from YouTube.
