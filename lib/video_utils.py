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
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

CHUNK_PLAN_SAMPLE = """{
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
}"""

DEFAULT_ENCODE_OPTS = {
    'video_codec': 'libx264',
    'preset': 'medium',
    'crf': '23',
    'audio_codec': 'aac',
    'audio_bitrate': '192k',
}


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


def extract_segment_mp3(
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    start_sec: float,
    duration_sec: float,
) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    cmd = build_audio_segment_command(
        ffmpeg_cmd, input_path, output_path, start_sec, duration_sec,
    )
    ok, err = run_ffmpeg(cmd)
    if ok and os.path.exists(output_path):
        return True, ''
    return False, err


def split_fixed_interval(
    ffmpeg_cmd: str,
    input_path: str,
    output_dir: str,
    chunk_seconds: float,
    name_pattern: str = '{basename}_part_{index:03d}.mp4',
    max_chunks: Optional[int] = None,
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

    errors = [] if outputs else [err or 'No segment files created']
    return [str(p) for p in outputs], errors


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
                mp3_path = os.path.splitext(output_path)[0] + '.mp3'
                ok_mp3, err_mp3 = extract_segment_mp3(
                    ffmpeg_cmd, input_path, mp3_path,
                    seg['start_sec'], seg['duration'],
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
