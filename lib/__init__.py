"""
Audio Tools Shared Library

This package contains shared utilities and components used across
the audio tools applications to avoid code duplication.
"""

__version__ = "1.0.0"
__author__ = "Audio Tools Team"

# Import main modules for easy access
from .ffmpeg_utils import FFmpegManager
from .gui_utils import GUIManager, LogManager
from .file_utils import FileManager
from .process_utils import ProcessManager

__all__ = [
    'FFmpegManager',
    'GUIManager', 
    'LogManager',
    'FileManager',
    'ProcessManager'
]
