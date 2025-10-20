"""
Base GUI Class

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

Base class for audio tools GUI applications with common functionality.
"""

import tkinter as tk
from tkinter import ttk
import os
import sys
from pathlib import Path

from .ffmpeg_utils import FFmpegManager
from .gui_utils import GUIManager, LogManager
from .file_utils import FileManager
from .process_utils import ProcessManager


class BaseAudioGUI:
    """Base class for audio tools GUI applications."""
    
    def __init__(self, root, title="Audio Tools"):
        """
        Initialize base GUI.
        
        Args:
            root: Tkinter root window
            title: Window title
        """
        self.root = root
        self.root.title(title)
        
        # Get root directory (assuming scripts are in scripts/ folder)
        self.root_dir = os.path.dirname(os.path.dirname(__file__))
        
        # Initialize managers
        self.gui_manager = GUIManager(root)
        self.file_manager = FileManager(self.root_dir)
        self.process_manager = ProcessManager(self.log_callback)
        self.ffmpeg_manager = FFmpegManager(self.root_dir, self.log_callback)
        
        # Initialize log manager (will be set by subclasses)
        self.log_manager = LogManager()
        
        # Common attributes
        self.is_busy = False
        self.selected_files = []
        
        # Setup common UI elements
        self.setup_common_ui()
    
    def setup_common_ui(self):
        """Setup common UI elements."""
        # This will be overridden by subclasses
        pass
    
    def log_callback(self, message):
        """Log callback for managers."""
        if self.log_manager:
            self.log_manager.log(message)
        else:
            print(message)
    
    def set_busy(self, busy=True, message="", progress_bar=None, progress_label=None):
        """Set busy state."""
        self.is_busy = busy
        self.gui_manager.set_busy(busy, message, progress_bar, progress_label)
    
    def log(self, message):
        """Log a message."""
        self.log_manager.log(message)
    
    def log_info(self, message):
        """Log an info message."""
        self.log_manager.log_info(message)
    
    def log_error(self, message):
        """Log an error message."""
        self.log_manager.log_error(message)
    
    def log_success(self, message):
        """Log a success message."""
        self.log_manager.log_success(message)
    
    def show_message(self, msg_type, title, message):
        """Show a message box."""
        return self.gui_manager.show_message(msg_type, title, message)
    
    def check_ffmpeg(self):
        """Check if FFmpeg is available."""
        return self.ffmpeg_manager.check_ffmpeg()
    
    def offer_ffmpeg_install(self):
        """Offer to install FFmpeg."""
        return self.ffmpeg_manager.offer_ffmpeg_install(self.show_message)
    
    def download_ffmpeg_windows(self, progress_callback=None, success_callback=None, error_callback=None):
        """Download FFmpeg for Windows."""
        return self.ffmpeg_manager.download_ffmpeg_windows(progress_callback, success_callback, error_callback)
    
    def get_ffmpeg_command(self):
        """Get FFmpeg command."""
        return self.ffmpeg_manager.get_ffmpeg_command()
    
    def select_files(self, title="Select Files", filetypes=None, initial_dir=None):
        """Select files."""
        return self.gui_manager.select_files(title, filetypes, initial_dir)
    
    def browse_folder(self, initial_dir=None, title="Select Folder"):
        """Browse for folder."""
        return self.gui_manager.browse_folder(initial_dir, title)
    
    def create_scrolled_text(self, parent, height=10):
        """Create scrolled text widget."""
        return self.gui_manager.create_scrolled_text(parent, height)
    
    def create_progress_bar(self, parent, mode='determinate'):
        """Create progress bar widget."""
        return self.gui_manager.create_progress_bar(parent, mode)
    
    def create_file_listbox(self, parent, height=8, selectmode=tk.EXTENDED):
        """Create file listbox with scrollbars."""
        return self.gui_manager.create_file_listbox(parent, height, selectmode)
    
    def update_file_list(self, listbox, files):
        """Update file listbox with files."""
        listbox.delete(0, tk.END)
        for file in files:
            filename = os.path.basename(file)
            listbox.insert(tk.END, filename)
    
    def validate_selection(self, files, min_count=1, error_message="Please select at least one file"):
        """Validate file selection."""
        if not files or len(files) < min_count:
            self.show_message('warning', 'Warning', error_message)
            return False
        return True
    
    def run_in_thread(self, target_func, args=(), kwargs=None):
        """Run function in thread."""
        return self.process_manager.run_in_thread(target_func, args, kwargs)
    
    def build_ffmpeg_command(self, input_file, output_file, audio_filters=None, 
                           video_filters=None, audio_codec='mp3', audio_bitrate='192k'):
        """Build FFmpeg command."""
        return self.process_manager.build_ffmpeg_command(
            self.get_ffmpeg_command(),
            input_file, output_file, audio_filters, video_filters,
            audio_codec, audio_bitrate
        )
    
    def run_ffmpeg_command(self, cmd):
        """Run FFmpeg command."""
        return self.process_manager.run_command(cmd)
    
    def run_ffmpeg_streaming(self, cmd, output_callback=None):
        """Run FFmpeg command with streaming output."""
        return self.process_manager.run_command_streaming(cmd, output_callback)
    
    def get_output_filename(self, input_file, suffix="", extension=None):
        """Get output filename."""
        return self.file_manager.get_output_filename(input_file, suffix, extension)
    
    def ensure_directory(self, directory):
        """Ensure directory exists."""
        return self.file_manager.ensure_directory(directory)
    
    def format_filesize(self, size_bytes):
        """Format file size."""
        return self.file_manager.format_filesize(size_bytes)
    
    def create_safe_filename(self, filename):
        """Create safe filename."""
        return self.file_manager.create_safe_filename(filename)
    
    def create_filename_from_pattern(self, pattern, data):
        """Create filename from pattern."""
        return self.file_manager.create_filename_from_pattern(pattern, data)
