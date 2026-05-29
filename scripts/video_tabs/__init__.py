"""Video Tools unified application tabs."""

from .v2m_tab import VideoToMp3Tab
from .format_tab import FormatCropTab
from .mp3_video_tab import Mp3ToVideoTab
from .combine_tab import CombineVideosTab
from .split_tab import SplitChunksTab

__all__ = [
    'VideoToMp3Tab',
    'FormatCropTab',
    'Mp3ToVideoTab',
    'CombineVideosTab',
    'SplitChunksTab',
]
