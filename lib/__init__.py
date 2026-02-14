"""
Audio Tools Shared Library

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
from .legal_utils import LegalManager
from .security_utils import SecurityManager

__all__ = [
    'FFmpegManager',
    'GUIManager',
    'LogManager',
    'FileManager',
    'ProcessManager',
    'LegalManager',
    'SecurityManager',
]
