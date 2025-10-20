"""
File Utilities

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

Handles file selection, validation, and path operations.
"""

import os
import re
from pathlib import Path


class FileManager:
    """Manages file operations and validation."""
    
    def __init__(self, root_dir):
        """
        Initialize file manager.
        
        Args:
            root_dir: Root directory of the application
        """
        self.root_dir = root_dir
        self.downloads_folder = os.path.join(root_dir, "downloads")
        self.converted_folder = os.path.join(root_dir, "converted")
        self.output_folder = os.path.join(root_dir, "converted_changed")
        
        # CSV basename for subfolder creation
        self.csv_basename = None
        
        # Create directories
        os.makedirs(self.downloads_folder, exist_ok=True)
        os.makedirs(self.converted_folder, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)
    
    def get_folder_path(self, folder_type):
        """
        Get path for a specific folder type.
        
        Args:
            folder_type: Type of folder ('downloads', 'converted', 'output')
            
        Returns:
            str: Folder path
        """
        base_folder = None
        if folder_type == 'downloads':
            base_folder = self.downloads_folder
        elif folder_type == 'converted':
            base_folder = self.converted_folder
        elif folder_type == 'output':
            base_folder = self.output_folder
        else:
            return self.root_dir
        
        # Add CSV basename subfolder if available
        if self.csv_basename and base_folder:
            subfolder_path = os.path.join(base_folder, self.csv_basename)
            self.ensure_directory(subfolder_path)
            return subfolder_path
        
        return base_folder
    
    def set_folder_path(self, folder_type, path):
        """
        Set path for a specific folder type.
        
        Args:
            folder_type: Type of folder ('downloads', 'converted', 'output')
            path: New folder path
        """
        if folder_type == 'downloads':
            self.downloads_folder = path
        elif folder_type == 'converted':
            self.converted_folder = path
        elif folder_type == 'output':
            self.output_folder = path
    
    def set_csv_basename(self, csv_file_path):
        """
        Set CSV basename for subfolder creation.
        
        Args:
            csv_file_path: Path to the CSV file
        """
        if csv_file_path:
            csv_filename = os.path.basename(csv_file_path)
            self.csv_basename = os.path.splitext(csv_filename)[0]
        else:
            self.csv_basename = None
    
    def validate_file(self, file_path, allowed_extensions=None):
        """
        Validate if a file exists and has allowed extension.
        
        Args:
            file_path: Path to the file
            allowed_extensions: List of allowed extensions (e.g., ['.mp3', '.mp4'])
            
        Returns:
            bool: True if file is valid, False otherwise
        """
        if not os.path.exists(file_path):
            return False
        
        if allowed_extensions:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in allowed_extensions:
                return False
        
        return True
    
    def get_audio_filetypes(self):
        """Get file types for audio files."""
        return [
            ("Audio Files", "*.mp3 *.m4a *.wav *.ogg *.flac"),
            ("MP3 Files", "*.mp3"),
            ("M4A Files", "*.m4a"),
            ("WAV Files", "*.wav"),
            ("All Files", "*.*")
        ]
    
    def get_video_filetypes(self):
        """Get file types for video files."""
        return [
            ("Video/Audio Files", "*.mp4 *.webm *.avi *.mov *.mkv *.flv *.wmv *.m4a"),
            ("MP4 Files", "*.mp4"),
            ("WEBM Files", "*.webm"),
            ("M4A Files", "*.m4a"),
            ("All Files", "*.*")
        ]
    
    def get_csv_filetypes(self):
        """Get file types for CSV files."""
        return [
            ("CSV Files", "*.csv"),
            ("All Files", "*.*")
        ]
    
    def create_safe_filename(self, filename):
        """
        Create a safe filename by removing invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Safe filename
        """
        # Remove invalid characters
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove multiple underscores
        safe_filename = re.sub(r'_+', '_', safe_filename)
        
        # Remove leading/trailing underscores
        safe_filename = safe_filename.strip('_')
        
        return safe_filename
    
    def create_filename_from_pattern(self, pattern, data):
        """
        Create filename from pattern using data fields.
        
        Args:
            pattern: Filename pattern with placeholders like {Rank}, {Title}
            data: Dictionary with field values
            
        Returns:
            str: Generated filename
        """
        filename = pattern
        
        # Replace placeholders with data values
        for key, value in data.items():
            placeholder = f"{{{key}}}"
            if placeholder in filename:
                safe_value = self.create_safe_filename(str(value))
                filename = filename.replace(placeholder, safe_value)
        
        # Remove any remaining placeholders
        filename = re.sub(r'\{[^}]+\}', '', filename)
        
        # Clean up the filename
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('_')
        
        return filename
    
    def get_output_filename(self, input_file, suffix="", extension=None):
        """
        Generate output filename based on input file.
        
        Args:
            input_file: Input file path
            suffix: Suffix to add to filename
            extension: Output extension (if None, keeps original)
            
        Returns:
            str: Output filename
        """
        input_path = Path(input_file)
        basename = input_path.stem
        
        if extension is None:
            extension = input_path.suffix
        
        if suffix:
            return f"{basename}{suffix}{extension}"
        else:
            return f"{basename}{extension}"
    
    def format_filesize(self, size_bytes):
        """
        Format file size in human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if not size_bytes:
            return 'Unknown'
        
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def ensure_directory(self, directory):
        """
        Ensure directory exists, create if it doesn't.
        
        Args:
            directory: Directory path
            
        Returns:
            str: Directory path
        """
        os.makedirs(directory, exist_ok=True)
        return directory
