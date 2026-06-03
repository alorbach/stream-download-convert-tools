"""Shared video encode codec / quality / preset settings for Video Tools Unified."""

import re
from typing import Dict, List, Optional

VIDEO_CODEC_CHOICES = ('libx264', 'libx265', 'libvpx-vp9')
VIDEO_QUALITY_CHOICES = (
    'Very High Quality (CRF 15)',
    'High Quality (CRF 18)',
    'Medium Quality (CRF 23)',
    'Low Quality (CRF 28)',
    'Maximum Compression (CRF 32)',
)
VIDEO_PRESET_CHOICES = (
    'ultrafast', 'veryfast', 'fast', 'medium', 'slow', 'veryslow',
)

DEFAULT_VIDEO_CODEC = 'libx264'
DEFAULT_VIDEO_QUALITY = 'High Quality (CRF 18)'
DEFAULT_VIDEO_PRESET = 'veryfast'


def crf_from_quality_label(quality_label: str, video_codec: str) -> int:
    """Parse CRF from quality preset label; adjust per codec like Combine tab."""
    match = re.search(r'CRF\s+(\d+)', quality_label or '')
    base_crf = int(match.group(1)) if match else 23
    if video_codec == 'libx264':
        return base_crf
    if video_codec == 'libx265':
        return base_crf + 4
    if video_codec == 'libvpx-vp9':
        return min(base_crf + 6, 63)
    return base_crf


def build_encode_opts_dict(
    video_codec: Optional[str] = None,
    quality_label: Optional[str] = None,
    preset: Optional[str] = None,
) -> Dict[str, str]:
    """Dict for video_utils / FFmpeg (video_codec, crf, preset, audio_codec, audio_bitrate)."""
    codec = video_codec or DEFAULT_VIDEO_CODEC
    quality = quality_label or DEFAULT_VIDEO_QUALITY
    enc_preset = preset or DEFAULT_VIDEO_PRESET
    return {
        'video_codec': codec,
        'crf': str(crf_from_quality_label(quality, codec)),
        'preset': enc_preset,
        'audio_codec': 'aac',
        'audio_bitrate': '192k',
    }


def ffmpeg_video_encode_args(encode_opts: Dict[str, str]) -> List[str]:
    """FFmpeg output args for -c:v / -crf / -preset (and VP9 -b:v 0)."""
    codec = encode_opts.get('video_codec', DEFAULT_VIDEO_CODEC)
    args = [
        '-c:v', codec,
        '-crf', str(encode_opts.get('crf', '23')),
        '-preset', encode_opts.get('preset', DEFAULT_VIDEO_PRESET),
    ]
    if codec == 'libvpx-vp9':
        args.extend(['-b:v', '0'])
    return args


def encode_settings_summary(encode_opts: Dict[str, str]) -> str:
    """Short label for UI, e.g. libx265 CRF 18 veryfast."""
    return (
        f"{encode_opts.get('video_codec', DEFAULT_VIDEO_CODEC)} "
        f"CRF {encode_opts.get('crf', '?')} "
        f"{encode_opts.get('preset', DEFAULT_VIDEO_PRESET)}"
    )
