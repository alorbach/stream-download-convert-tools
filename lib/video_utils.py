"""
Video processing utilities (probe, segment, chunk plans).

Copyright 2025 Andre Lorbach

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

ProgressCallback = Callable[[float, str], None]

CHUNK_PLAN_SAMPLE = """{
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
}"""

DEFAULT_ENCODE_OPTS = {
    'video_codec': 'libx264',
    'preset': 'medium',
    'crf': '23',
    'audio_codec': 'aac',
    'audio_bitrate': '192k',
}

DEFAULT_UPSCALE_ENCODE_OPTS = {
    'video_codec': 'libx264',
    'preset': 'slow',
    'crf': '18',
    'audio_codec': 'aac',
    'audio_bitrate': '192k',
}

UPSCALE_METHOD_STANDARD = 'standard'
UPSCALE_METHOD_HIGH = 'high'
UPSCALE_METHOD_MAXIMUM = 'maximum'
UPSCALE_METHOD_AI = 'ai'

_LANCZOS_FLAGS = 'flags=lanczos+accurate_rnd+full_chroma_int'
_LANCZOS_SIMPLE = 'flags=lanczos'


def source_output_dir(input_path: str) -> str:
    """Directory containing the source video (default export location)."""
    return os.path.dirname(os.path.abspath(input_path))


def parse_dropped_paths(data: str) -> List[str]:
    """Parse DND event data (supports {path with spaces})."""
    if not data:
        return []
    tokens = re.findall(r"\{[^}]+\}|\"[^\"]+\"|\S+", data)
    paths = []
    for t in tokens:
        t = t.strip()
        if t.startswith('{') and t.endswith('}'):
            t = t[1:-1]
        if t.startswith('"') and t.endswith('"'):
            t = t[1:-1]
        if t:
            paths.append(t)
    return paths


def _subprocess_flags():
    return subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0


def _parse_duration_from_stderr(stderr_text: str) -> Optional[float]:
    for line in stderr_text.split('\n'):
        if 'Duration:' in line:
            parts = line.split('Duration:')[1].split(',')[0].strip()
            time_parts = parts.split(':')
            if len(time_parts) == 3:
                try:
                    hours = float(time_parts[0])
                    minutes = float(time_parts[1])
                    sec_ms = time_parts[2].split('.')
                    seconds = float(sec_ms[0])
                    if len(sec_ms) > 1:
                        seconds += float('0.' + sec_ms[1])
                    return hours * 3600 + minutes * 60 + seconds
                except ValueError:
                    pass
    return None


def probe_duration(ffmpeg_cmd: str, input_path: str, ffprobe_cmd: Optional[str] = None) -> Optional[float]:
    """Return video duration in seconds."""
    if ffprobe_cmd:
        try:
            result = subprocess.run(
                [
                    ffprobe_cmd, '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', input_path
                ],
                capture_output=True, text=True,
                creationflags=_subprocess_flags(), timeout=60
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

    try:
        result = subprocess.run(
            [ffmpeg_cmd, '-i', input_path],
            capture_output=True, text=True,
            creationflags=_subprocess_flags(), timeout=60
        )
        return _parse_duration_from_stderr(result.stderr or '')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def probe_resolution(ffmpeg_cmd: str, input_path: str, ffprobe_cmd: Optional[str] = None) -> Optional[Tuple[int, int]]:
    """Return (width, height) or None."""
    if ffprobe_cmd:
        try:
            result = subprocess.run(
                [
                    ffprobe_cmd, '-v', 'error', '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'csv=p=0:s=x', input_path
                ],
                capture_output=True, text=True,
                creationflags=_subprocess_flags(), timeout=60
            )
            if result.returncode == 0 and 'x' in result.stdout:
                w, h = result.stdout.strip().split('x')
                return int(w), int(h)
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            pass

    try:
        result = subprocess.run(
            [ffmpeg_cmd, '-i', input_path],
            capture_output=True, text=True,
            creationflags=_subprocess_flags(), timeout=60
        )
        for line in (result.stderr or '').split('\n'):
            if 'Video:' in line:
                parts = line.split('Video:')[1].split(',')
                for part in parts:
                    part = part.strip()
                    if 'x' in part and part[0].isdigit():
                        res_part = part.split()[0]
                        if 'x' in res_part:
                            w_h = res_part.split('x')
                            if len(w_h) == 2:
                                try:
                                    return int(w_h[0]), int(w_h[1])
                                except ValueError:
                                    pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def align_even(width: int, height: int) -> Tuple[int, int]:
    """Force dimensions to multiples of 2 for H.264."""
    w = max(2, int(width))
    h = max(2, int(height))
    if w % 2:
        w -= 1
    if h % 2:
        h -= 1
    return w, h


def resolve_ffprobe_cmd(ffmpeg_cmd: str) -> Optional[str]:
    """Return ffprobe path adjacent to ffmpeg, or None."""
    if not ffmpeg_cmd:
        return None
    base = ffmpeg_cmd
    if base.lower().endswith('ffmpeg.exe'):
        candidate = base[:-10] + 'ffprobe.exe'
    elif base.lower().endswith('ffmpeg'):
        candidate = base[:-6] + 'ffprobe'
    else:
        candidate = ffmpeg_cmd.replace('ffmpeg', 'ffprobe')
    if os.path.isfile(candidate):
        return candidate
    try:
        result = subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            creationflags=_subprocess_flags(),
            timeout=15,
        )
        if result.returncode == 0:
            return 'ffprobe'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _parse_frame_rate(rate_str: str) -> Optional[float]:
    rate_str = (rate_str or '').strip()
    if not rate_str or rate_str == '0/0':
        return None
    if '/' in rate_str:
        num, den = rate_str.split('/', 1)
        try:
            n, d = float(num), float(den)
            if d > 0:
                return n / d
        except ValueError:
            return None
    try:
        return float(rate_str)
    except ValueError:
        return None


def probe_fps(
    ffmpeg_cmd: str,
    input_path: str,
    ffprobe_cmd: Optional[str] = None,
) -> Optional[float]:
    """Return average video frame rate or None."""
    probe = ffprobe_cmd or resolve_ffprobe_cmd(ffmpeg_cmd)
    if probe:
        for field in ('avg_frame_rate', 'r_frame_rate'):
            try:
                result = subprocess.run(
                    [
                        probe, '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', f'stream={field}',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        input_path,
                    ],
                    capture_output=True, text=True,
                    creationflags=_subprocess_flags(), timeout=60,
                )
                if result.returncode == 0 and result.stdout.strip():
                    fps = _parse_frame_rate(result.stdout.strip())
                    if fps and fps > 0:
                        return fps
            except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
                pass
    return None


def probe_has_audio(
    ffmpeg_cmd: str,
    input_path: str,
    ffprobe_cmd: Optional[str] = None,
) -> bool:
    """Return True if the file has at least one audio stream."""
    probe = ffprobe_cmd or resolve_ffprobe_cmd(ffmpeg_cmd)
    if probe:
        try:
            result = subprocess.run(
                [
                    probe, '-v', 'error', '-select_streams', 'a',
                    '-show_entries', 'stream=codec_type',
                    '-of', 'csv=p=0', input_path,
                ],
                capture_output=True, text=True,
                creationflags=_subprocess_flags(), timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    try:
        result = subprocess.run(
            [ffmpeg_cmd, '-i', input_path],
            capture_output=True, text=True,
            creationflags=_subprocess_flags(), timeout=60,
        )
        return 'Audio:' in (result.stderr or '')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def build_upscale_vf(
    target_w: int,
    target_h: int,
    method: str = UPSCALE_METHOD_HIGH,
    src_w: Optional[int] = None,
    src_h: Optional[int] = None,
) -> str:
    """Build FFmpeg -vf filter string for upscaling to exact dimensions."""
    tw, th = align_even(target_w, target_h)
    method = (method or UPSCALE_METHOD_HIGH).lower()

    if method == UPSCALE_METHOD_STANDARD:
        return f'scale={tw}:{th}'

    if method == UPSCALE_METHOD_HIGH:
        return f'scale={tw}:{th}:{_LANCZOS_FLAGS}'

    if method == UPSCALE_METHOD_MAXIMUM:
        use_two_step = True
        if src_w and src_h and src_w > 0 and src_h > 0:
            factor = max(tw / src_w, th / src_h)
            use_two_step = factor > 1.25
        if use_two_step:
            return (
                f'scale=iw*2:ih*2:{_LANCZOS_SIMPLE},'
                f'scale={tw}:{th}:{_LANCZOS_FLAGS},'
                'unsharp=3:3:0.35:3:3:0.0'
            )
        return f'scale={tw}:{th}:{_LANCZOS_FLAGS},unsharp=3:3:0.35:3:3:0.0'

    return f'scale={tw}:{th}:{_LANCZOS_FLAGS}'


def pick_realesrgan_scale(
    src_w: int,
    src_h: int,
    target_w: int,
    target_h: int,
) -> int:
    """Pick Real-ESRGAN integer scale (2 or 4) before final FFmpeg resize."""
    need = max(target_w / max(src_w, 1), target_h / max(src_h, 1))
    if need <= 2.0:
        return 2
    return 4


def build_upscale_command(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    method: str = UPSCALE_METHOD_HIGH,
    encode_opts: Optional[Dict[str, str]] = None,
    audio_copy: bool = True,
    src_w: Optional[int] = None,
    src_h: Optional[int] = None,
) -> List[str]:
    """Build ffmpeg command to upscale a video file."""
    opts = {**DEFAULT_UPSCALE_ENCODE_OPTS, **(encode_opts or {})}
    tw, th = align_even(target_w, target_h)
    vf = build_upscale_vf(tw, th, method, src_w=src_w, src_h=src_h)
    cmd = [ffmpeg_cmd, '-y', '-i', input_path, '-vf', vf]
    if audio_copy:
        cmd.extend(['-c:a', 'copy'])
    else:
        cmd.extend(['-c:a', opts['audio_codec'], '-b:a', opts['audio_bitrate']])
    cmd.extend([
        '-c:v', opts['video_codec'],
        '-preset', opts['preset'],
        '-crf', opts['crf'],
        '-movflags', '+faststart',
        output_path,
    ])
    return cmd


def _run_upscale_encode(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    method: str,
    encode_opts: Optional[Dict[str, str]],
    audio_copy: bool,
    src_w: Optional[int],
    src_h: Optional[int],
    timeout: int,
    progress_callback: Optional[ProgressCallback] = None,
) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    ffprobe = resolve_ffprobe_cmd(ffmpeg_cmd)
    duration = probe_duration(ffmpeg_cmd, input_path, ffprobe)
    cmd = build_upscale_command(
        ffmpeg_cmd, input_path, output_path, target_w, target_h,
        method=method, encode_opts=encode_opts, audio_copy=audio_copy,
        src_w=src_w, src_h=src_h,
    )
    ok, err = run_ffmpeg_with_progress(
        cmd, duration_sec=duration, progress_callback=progress_callback, timeout=timeout,
    )
    if ok and os.path.exists(output_path):
        return True, ''
    if audio_copy:
        cmd = build_upscale_command(
            ffmpeg_cmd, input_path, output_path, target_w, target_h,
            method=method, encode_opts=encode_opts, audio_copy=False,
            src_w=src_w, src_h=src_h,
        )
        ok, err = run_ffmpeg_with_progress(
            cmd, duration_sec=duration, progress_callback=progress_callback, timeout=timeout,
        )
        if ok and os.path.exists(output_path):
            return True, ''
    return False, err


def upscale_video_ffmpeg(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    method: str = UPSCALE_METHOD_HIGH,
    encode_opts: Optional[Dict[str, str]] = None,
    audio_copy: bool = True,
    timeout: int = 3600,
    progress_callback: Optional[ProgressCallback] = None,
) -> Tuple[bool, str]:
    """Upscale video with FFmpeg filters. Returns (ok, error_message)."""
    ffprobe = resolve_ffprobe_cmd(ffmpeg_cmd)
    src = probe_resolution(ffmpeg_cmd, input_path, ffprobe)
    src_w, src_h = (src if src else (None, None))
    return _run_upscale_encode(
        ffmpeg_cmd, input_path, output_path, target_w, target_h,
        method, encode_opts, audio_copy, src_w, src_h, timeout,
        progress_callback=progress_callback,
    )


def _cleanup_temp_dir(temp_dir: str, remove: bool) -> None:
    if remove and temp_dir and os.path.isdir(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except OSError:
            pass


def upscale_video_realesrgan(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    target_w: int,
    target_h: int,
    ai_exe: str,
    ai_model: str = 'realesr-animevideov3',
    encode_opts: Optional[Dict[str, str]] = None,
    audio_copy: bool = True,
    remove_temp: bool = True,
    log_callback: Optional[Any] = None,
    progress_callback: Optional[ProgressCallback] = None,
    timeout: int = 7200,
) -> Tuple[bool, str]:
    """
    Upscale via frame extract -> Real-ESRGAN ncnn-vulkan -> FFmpeg encode.
    Returns (ok, error_message).
    """
    def _log(msg: str) -> None:
        if log_callback:
            log_callback(msg)

    def _stage(pct: float, msg: str) -> None:
        if progress_callback:
            progress_callback(pct, msg)

    if not ai_exe or not os.path.isfile(ai_exe):
        return False, f'Real-ESRGAN executable not found: {ai_exe}'

    ffprobe = resolve_ffprobe_cmd(ffmpeg_cmd)
    src = probe_resolution(ffmpeg_cmd, input_path, ffprobe)
    if not src:
        return False, 'Could not read source video resolution'
    src_w, src_h = src
    tw, th = align_even(target_w, target_h)
    ai_scale = pick_realesrgan_scale(src_w, src_h, tw, th)
    fps = probe_fps(ffmpeg_cmd, input_path, ffprobe) or 24.0
    duration = probe_duration(ffmpeg_cmd, input_path, ffprobe)
    has_audio = probe_has_audio(ffmpeg_cmd, input_path, ffprobe)

    basename = Path(input_path).stem
    temp_dir = os.path.join(
        tempfile.gettempdir(),
        f'video_upscale_{basename}_{os.getpid()}',
    )
    in_frames = os.path.join(temp_dir, 'in')
    out_frames = os.path.join(temp_dir, 'out')
    os.makedirs(in_frames, exist_ok=True)
    os.makedirs(out_frames, exist_ok=True)
    _log(f'[INFO] Temp frames: {temp_dir}')

    in_pattern = os.path.join(in_frames, '%06d.png')
    extract_cmd = [
        ffmpeg_cmd, '-y', '-i', input_path,
        '-vsync', '0', in_pattern,
    ]
    def _extract_progress(inner_pct: float, msg: str) -> None:
        _stage(min(14.0, inner_pct * 0.14), msg)

    _stage(0.0, 'Extracting frames...')
    ok, err = run_ffmpeg_with_progress(
        extract_cmd, duration_sec=duration, progress_callback=_extract_progress, timeout=timeout,
    )
    if not ok:
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, f'Frame extract failed: {err}'

    frame_files = sorted(Path(in_frames).glob('*.png'))
    if not frame_files:
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, 'No frames extracted from video'

    _stage(15.0, f'AI upscaling {len(frame_files)} frames ({ai_scale}x)...')
    _log(f'[INFO] Extracted {len(frame_files)} frames; running Real-ESRGAN {ai_scale}x...')
    esr_cmd = [
        ai_exe,
        '-i', in_frames,
        '-o', out_frames,
        '-n', ai_model,
        '-s', str(ai_scale),
    ]
    try:
        result = subprocess.run(
            esr_cmd,
            capture_output=True, text=True,
            creationflags=_subprocess_flags(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, 'Real-ESRGAN timed out'
    except FileNotFoundError:
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, f'Could not run: {ai_exe}'

    if result.returncode != 0:
        err_text = (result.stderr or result.stdout or 'Real-ESRGAN failed')[-500:]
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, err_text

    _stage(85.0, 'Encoding upscaled video...')
    upscaled = sorted(Path(out_frames).glob('*.png'))
    if not upscaled:
        _cleanup_temp_dir(temp_dir, remove_temp)
        return False, 'Real-ESRGAN produced no output frames'

    out_pattern = os.path.join(out_frames, '%06d.png')
    if not os.path.isfile(os.path.join(out_frames, '000001.png')):
        for i, fp in enumerate(upscaled, start=1):
            dest = os.path.join(out_frames, f'{i:06d}.png')
            if str(fp) != dest:
                try:
                    shutil.copy2(fp, dest)
                except OSError as copy_err:
                    _cleanup_temp_dir(temp_dir, remove_temp)
                    return False, str(copy_err)

    final_vf = build_upscale_vf(tw, th, UPSCALE_METHOD_HIGH, src_w=src_w * ai_scale, src_h=src_h * ai_scale)
    opts = {**DEFAULT_UPSCALE_ENCODE_OPTS, **(encode_opts or {})}
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    encode_cmd = [
        ffmpeg_cmd, '-y',
        '-framerate', str(fps),
        '-i', out_pattern,
        '-i', input_path,
        '-map', '0:v:0',
    ]
    if has_audio:
        encode_cmd.extend(['-map', '1:a:0'])
    encode_cmd.extend(['-vf', final_vf, '-c:v', opts['video_codec'],
                       '-preset', opts['preset'], '-crf', opts['crf']])
    if has_audio:
        if audio_copy:
            encode_cmd.extend(['-c:a', 'copy'])
        else:
            encode_cmd.extend(['-c:a', opts['audio_codec'], '-b:a', opts['audio_bitrate']])
    else:
        encode_cmd.append('-an')
    encode_cmd.extend(['-movflags', '+faststart', output_path])

    encode_duration = len(frame_files) / fps if fps > 0 else duration

    def _encode_progress(inner_pct: float, msg: str) -> None:
        _stage(85.0 + min(14.0, inner_pct * 0.14), msg)

    ok, err = run_ffmpeg_with_progress(
        encode_cmd, duration_sec=encode_duration,
        progress_callback=_encode_progress, timeout=timeout,
    )
    if not ok and has_audio and audio_copy:
        encode_cmd = [
            ffmpeg_cmd, '-y',
            '-framerate', str(fps),
            '-i', out_pattern,
            '-i', input_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-vf', final_vf,
            '-c:v', opts['video_codec'], '-preset', opts['preset'], '-crf', opts['crf'],
            '-c:a', opts['audio_codec'], '-b:a', opts['audio_bitrate'],
            '-movflags', '+faststart', output_path,
        ]
        ok, err = run_ffmpeg_with_progress(
            encode_cmd, duration_sec=encode_duration,
            progress_callback=_encode_progress, timeout=timeout,
        )

    if ok and os.path.exists(output_path):
        _stage(100.0, 'Complete')
        _cleanup_temp_dir(temp_dir, remove_temp)
        return True, ''

    _cleanup_temp_dir(temp_dir, remove_temp)
    return False, err or 'Upscale encode failed'


def resolve_start_time(duration: float, start_spec: Union[str, int, float]) -> float:
    """
    Resolve start position in seconds.
    - number >= 0: absolute seconds
    - negative number: seconds before end (start = duration + start_spec)
    - "middle" / "center": centered segment (caller must add duration/2 offset)
    """
    if isinstance(start_spec, str):
        s = start_spec.strip().lower()
        if s in ('middle', 'center'):
            return duration / 2.0
        try:
            start_spec = float(start_spec)
        except ValueError:
            return 0.0

    start = float(start_spec)
    if start < 0:
        return max(0.0, duration + start)
    return min(start, max(0.0, duration))


def segment_bounds(
    duration: float,
    start_spec: Union[str, int, float],
    duration_sec: Optional[float] = None,
    end_sec: Optional[float] = None,
) -> Tuple[float, float]:
    """Return (start_sec, end_sec) clamped to video duration."""
    start = resolve_start_time(duration, start_spec)
    if isinstance(start_spec, str) and str(start_spec).strip().lower() in ('middle', 'center'):
        if duration_sec is not None and duration_sec > 0:
            start = max(0.0, start - duration_sec / 2.0)

    if end_sec is not None:
        end = min(float(end_sec), duration)
    elif duration_sec is not None:
        end = min(start + float(duration_sec), duration)
    else:
        end = duration

    start = max(0.0, min(start, duration))
    end = max(start, min(end, duration))
    return start, end


def format_output_name(pattern: str, basename: str, seg_id: str, index: int) -> str:
    """Apply name pattern placeholders."""
    name = pattern.format(
        basename=basename,
        id=seg_id or f'part_{index:03d}',
        index=index,
    )
    try:
        name = name.format(index=index)
    except (KeyError, ValueError):
        pass
    return name


def validate_chunk_plan(plan: Dict[str, Any], video_duration: float) -> Tuple[List[Dict], List[str]]:
    """
    Validate plan and return list of segment dicts with start, end, id, warnings.
    Each segment: {id, start_sec, end_sec, duration}
    """
    warnings = []
    segments_raw = plan.get('segments') or []
    if not segments_raw:
        raise ValueError('Chunk plan must contain a non-empty "segments" array')

    resolved = []
    for i, seg in enumerate(segments_raw):
        seg_id = str(seg.get('id', f'part_{i:03d}'))
        start_spec = seg.get('start', 0)
        dur = seg.get('duration')
        end_val = seg.get('end')
        if dur is None and end_val is None:
            raise ValueError(f'Segment "{seg_id}" needs "duration" or "end"')
        start_sec, end_sec = segment_bounds(
            video_duration, start_spec,
            duration_sec=float(dur) if dur is not None else None,
            end_sec=float(end_val) if end_val is not None else None,
        )
        seg_dur = end_sec - start_sec
        if seg_dur <= 0:
            warnings.append(f'Segment "{seg_id}" skipped (zero length)')
            continue
        if end_sec > video_duration + 0.05:
            warnings.append(f'Segment "{seg_id}" end clamped to video duration')
        resolved.append({
            'id': seg_id,
            'start_sec': start_sec,
            'end_sec': end_sec,
            'duration': seg_dur,
        })
    return resolved, warnings


def parse_chunk_plan_json(text: str) -> Dict[str, Any]:
    plan = json.loads(text)
    if not isinstance(plan, dict):
        raise ValueError('Chunk plan must be a JSON object')
    return plan


def build_segment_command(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    use_copy: bool = True,
    encode_opts: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Build ffmpeg command to extract one segment."""
    opts = {**DEFAULT_ENCODE_OPTS, **(encode_opts or {})}
    cmd = [
        ffmpeg_cmd, '-y',
        '-ss', str(start_sec),
        '-i', input_path,
        '-t', str(duration_sec),
    ]
    if use_copy:
        cmd.extend(['-c', 'copy', '-avoid_negative_ts', 'make_zero'])
    else:
        cmd.extend([
            '-c:v', opts['video_codec'],
            '-preset', opts['preset'],
            '-crf', opts['crf'],
            '-c:a', opts['audio_codec'],
            '-b:a', opts['audio_bitrate'],
        ])
    cmd.extend(['-movflags', '+faststart', output_path])
    return cmd


def run_ffmpeg(cmd: List[str], timeout: int = 600) -> Tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=_subprocess_flags(), timeout=timeout
        )
        if result.returncode == 0:
            return True, ''
        err = (result.stderr or result.stdout or 'Unknown error')[-500:]
        return False, err
    except subprocess.TimeoutExpired:
        return False, 'FFmpeg operation timed out'
    except Exception as e:
        return False, str(e)


def _inject_ffmpeg_progress(cmd: List[str]) -> List[str]:
    """Insert -nostats -progress pipe:1 after ffmpeg binary (and optional -y)."""
    if not cmd or '-progress' in cmd:
        return cmd
    out = [cmd[0]]
    idx = 1
    if idx < len(cmd) and cmd[idx] == '-y':
        out.append('-y')
        idx += 1
    out.extend(['-nostats', '-progress', 'pipe:1'])
    out.extend(cmd[idx:])
    return out


def run_ffmpeg_with_progress(
    cmd: List[str],
    duration_sec: Optional[float] = None,
    progress_callback: Optional[ProgressCallback] = None,
    timeout: int = 600,
) -> Tuple[bool, str]:
    """
    Run FFmpeg and report encode progress via -progress pipe:1.
    progress_callback(percent 0-100, message).
    """
    if progress_callback is None:
        return run_ffmpeg(cmd, timeout=timeout)

    progress_cmd = _inject_ffmpeg_progress(cmd)
    if progress_callback:
        progress_callback(0.0, 'Starting...')

    err_lines: List[str] = []
    last_pct = -1.0

    try:
        proc = subprocess.Popen(
            progress_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=_subprocess_flags(),
        )
    except Exception as e:
        return False, str(e)

    def _read_stdout() -> None:
        nonlocal last_pct
        if not proc.stdout:
            return
        for line in proc.stdout:
            line = line.strip()
            if line == 'progress=end':
                continue
            if not line.startswith('out_time_ms='):
                continue
            try:
                us = int(line.split('=', 1)[1])
            except ValueError:
                continue
            sec = us / 1_000_000.0
            if duration_sec and duration_sec > 0:
                pct = min(99.0, (sec / duration_sec) * 100.0)
            else:
                pct = min(99.0, sec)
            if pct - last_pct >= 0.4 or pct >= 98.0:
                last_pct = pct
                if duration_sec and duration_sec > 0:
                    msg = f'Encoding {pct:.0f}% ({sec:.1f}s / {duration_sec:.1f}s)'
                else:
                    msg = f'Encoding {sec:.1f}s'
                progress_callback(pct, msg)

    def _read_stderr() -> None:
        if not proc.stderr:
            return
        for line in proc.stderr:
            err_lines.append(line)

    t_out = threading.Thread(target=_read_stdout, daemon=True)
    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, 'FFmpeg operation timed out'

    t_out.join(timeout=3)
    t_err.join(timeout=3)

    if proc.returncode == 0:
        progress_callback(100.0, 'Encode complete')
        return True, ''

    progress_callback(last_pct if last_pct >= 0 else 0.0, 'Encode failed')
    err = ''.join(err_lines)[-500:] or 'Unknown error'
    return False, err


def extract_segment(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    use_copy: bool = True,
) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    cmd = build_segment_command(
        ffmpeg_cmd, input_path, output_path, start_sec, duration_sec, use_copy=use_copy
    )
    ok, err = run_ffmpeg(cmd)
    if ok and os.path.exists(output_path):
        return True, ''
    if use_copy:
        cmd = build_segment_command(
            ffmpeg_cmd, input_path, output_path, start_sec, duration_sec, use_copy=False
        )
        ok, err = run_ffmpeg(cmd)
        if ok and os.path.exists(output_path):
            return True, ''
    return False, err


def build_audio_segment_command(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
    audio_bitrate: str = '192k',
) -> List[str]:
    """Build ffmpeg command to extract one segment as MP3."""
    return [
        ffmpeg_cmd, '-y',
        '-ss', str(start_sec),
        '-i', input_path,
        '-t', str(duration_sec),
        '-vn',
        '-c:a', 'libmp3lame',
        '-b:a', audio_bitrate,
        output_path,
    ]


def companion_mp3_path(media_path: str) -> str:
    """MP3 path with same basename as a video/audio chunk file."""
    return os.path.splitext(media_path)[0] + '.mp3'


def extract_mp3_from_file(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
) -> Tuple[bool, str]:
    """Extract full audio track from a media file to MP3 (used for interval chunks)."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    last_err = ''
    encode_attempts = [
        ['-c:a', 'libmp3lame', '-b:a', '192k'],
        ['-c:a', 'libmp3lame', '-q:a', '2'],
        ['-b:a', '192k'],
    ]
    for audio_args in encode_attempts:
        cmd = [ffmpeg_cmd, '-y', '-i', input_path, '-vn'] + audio_args + [output_path]
        ok, err = run_ffmpeg(cmd)
        if ok and os.path.exists(output_path):
            return True, ''
        last_err = err
    return False, last_err or 'MP3 export failed'


def extract_segment_mp3(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    last_err = ''
    encode_attempts = [
        ['-c:a', 'libmp3lame', '-b:a', '192k'],
        ['-c:a', 'libmp3lame', '-q:a', '2'],
        ['-b:a', '192k'],
    ]
    for audio_args in encode_attempts:
        cmd = [
            ffmpeg_cmd, '-y',
            '-ss', str(start_sec),
            '-i', input_path,
            '-t', str(duration_sec),
            '-vn',
        ] + audio_args + [output_path]
        ok, err = run_ffmpeg(cmd)
        if ok and os.path.exists(output_path):
            return True, ''
        last_err = err
    return False, last_err or 'MP3 export failed'


def split_fixed_interval(
    ffmpeg_cmd: str,
    input_path: str,
    output_dir: str,
    chunk_seconds: float,
    name_pattern: str = '{basename}_part_{index:03d}.mp4',
    max_chunks: Optional[int] = None,
    also_mp3: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Split video into fixed-length chunks. Returns (output_paths, errors).
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = Path(input_path).stem
    pattern_path = os.path.join(output_dir, name_pattern)
    if '{basename}' not in name_pattern and '{index' not in name_pattern:
        out_template = os.path.join(output_dir, f'{basename}_part_%03d.mp4')
    else:
        first_name = format_output_name(name_pattern, basename, 'part', 0)
        out_template = os.path.join(output_dir, first_name.replace('part', '%03d'))

    cmd = [
        ffmpeg_cmd, '-y', '-i', input_path,
        '-f', 'segment', '-segment_time', str(chunk_seconds),
        '-reset_timestamps', '1', '-c', 'copy',
        '-map', '0', out_template,
    ]
    ok, err = run_ffmpeg(cmd, timeout=1800)
    outputs = sorted(Path(output_dir).glob(f'{basename}*.mp4'))
    if not outputs:
        outputs = sorted(Path(output_dir).glob('*.mp4'))

    if not ok or not outputs:
        cmd = [
            ffmpeg_cmd, '-y', '-i', input_path,
            '-f', 'segment', '-segment_time', str(chunk_seconds),
            '-reset_timestamps', '1',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-map', '0', out_template,
        ]
        ok, err = run_ffmpeg(cmd, timeout=1800)
        outputs = sorted(Path(output_dir).glob(f'{basename}*.mp4'))
        if not outputs:
            outputs = sorted(Path(output_dir).glob('*.mp4'))

    if max_chunks and len(outputs) > max_chunks:
        for extra in outputs[max_chunks:]:
            try:
                extra.unlink()
            except OSError:
                pass
        outputs = outputs[:max_chunks]

    mp4_paths = [str(p) for p in outputs]
    all_outputs = list(mp4_paths)
    errors = [] if mp4_paths else [err or 'No segment files created']

    if also_mp3 and mp4_paths:
        for i, mp4_path in enumerate(mp4_paths):
            mp3_path = companion_mp3_path(mp4_path)
            ok_mp3, err_mp3 = extract_mp3_from_file(ffmpeg_cmd, mp4_path, mp3_path)
            if ok_mp3:
                all_outputs.append(mp3_path)
            else:
                errors.append(f'{Path(mp4_path).name} mp3: {err_mp3}')

    return all_outputs, errors


def apply_chunk_plan(
    ffmpeg_cmd: str,
    input_path: str,
    plan: Dict[str, Any],
    output_base_dir: str,
    also_mp3: bool = True,
) -> Tuple[List[str], List[str]]:
    """Apply JSON chunk plan to one video. Returns (outputs, errors)."""
    duration = probe_duration(ffmpeg_cmd, input_path)
    if duration is None or duration <= 0:
        return [], ['Could not determine video duration']

    out_cfg = plan.get('output') or {}
    folder = out_cfg.get('folder', 'chunks')
    name_pattern = out_cfg.get('name_pattern', '{basename}_{id}.mp4')
    output_dir = folder if os.path.isabs(folder) else os.path.join(output_base_dir, folder)
    os.makedirs(output_dir, exist_ok=True)

    basename = Path(input_path).stem
    segments, warnings = validate_chunk_plan(plan, duration)
    outputs = []
    errors = list(warnings)

    for i, seg in enumerate(segments):
        out_name = format_output_name(name_pattern, basename, seg['id'], i)
        if not out_name.lower().endswith('.mp4'):
            out_name += '.mp4'
        output_path = os.path.join(output_dir, out_name)
        ok, err = extract_segment(
            ffmpeg_cmd, input_path, output_path,
            seg['start_sec'], seg['duration'],
        )
        if ok:
            outputs.append(output_path)
            if also_mp3:
                mp3_path = companion_mp3_path(output_path)
                ok_mp3, err_mp3 = extract_segment_mp3(
                    ffmpeg_cmd, input_path, mp3_path,
                    seg['start_sec'], seg['duration'],
                )
                if not ok_mp3:
                    ok_mp3, err_mp3 = extract_mp3_from_file(
                        ffmpeg_cmd, output_path, mp3_path,
                    )
                if ok_mp3:
                    outputs.append(mp3_path)
                else:
                    errors.append(f'{seg["id"]} mp3: {err_mp3}')
        else:
            errors.append(f'{seg["id"]}: {err}')

    return outputs, errors


def segments_to_plan(
    segments: List[Dict[str, Any]],
    output_folder: str = 'chunks',
    name_pattern: str = '{basename}_{id}.mp4',
) -> Dict[str, Any]:
    """Build a chunk plan dict from visual trim region list."""
    plan_segments = []
    for seg in segments:
        entry = {'id': seg.get('id', 'cut')}
        if 'start_sec' in seg:
            entry['start'] = seg['start_sec']
        elif 'start' in seg:
            entry['start'] = seg['start']
        if 'duration' in seg:
            entry['duration'] = seg['duration']
        elif 'end_sec' in seg:
            entry['end'] = seg['end_sec']
        plan_segments.append(entry)
    return {
        'version': 1,
        'output': {'folder': output_folder, 'name_pattern': name_pattern},
        'segments': plan_segments,
    }


def export_visual_segments(
    ffmpeg_cmd: str,
    input_path: str,
    segments: List[Dict[str, Any]],
    output_base_dir: str = '',
    name_pattern: str = '{basename}_{id}.mp4',
    also_mp3: bool = True,
) -> Tuple[List[str], List[str]]:
    """Export cuts next to the source video (MP4 + matching MP3 per cut)."""
    if not segments:
        return [], ['No cut regions defined']
    source_dir = os.path.dirname(os.path.abspath(input_path))
    plan = segments_to_plan(segments, output_folder='.', name_pattern=name_pattern)
    return apply_chunk_plan(
        ffmpeg_cmd, input_path, plan, source_dir, also_mp3=also_mp3,
    )
