"""
Security Utilities

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

Input validation and security checks for URLs, filenames, and file paths.
"""

import os
import re
from urllib.parse import urlparse


# Allowed YouTube domain patterns
YOUTUBE_DOMAINS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
)
YOUTUBE_DOMAIN_PATTERN = re.compile(
    r"^https?://([a-zA-Z0-9.-]*)?(youtube\.com|youtu\.be)/",
    re.IGNORECASE,
)

# Dangerous filename characters
UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Reserved filenames on Windows
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


class SecurityManager:
    """Manages security validation for URLs, filenames, and paths."""

    def validate_youtube_url(self, url):
        """
        Validate that a URL appears to be a valid YouTube URL.

        Args:
            url: URL string to validate

        Returns:
            bool: True if URL looks like a valid YouTube URL
        """
        if not url or not isinstance(url, str):
            return False
        url = url.strip()
        if not url:
            return False
        return bool(YOUTUBE_DOMAIN_PATTERN.match(url))

    def sanitize_filename(self, filename):
        """
        Create a safe filename by removing invalid characters.

        Args:
            filename: Original filename

        Returns:
            str: Sanitized filename
        """
        if not filename or not isinstance(filename, str):
            return ""
        safe = UNSAFE_FILENAME_CHARS.sub("_", filename)
        safe = re.sub(r"_+", "_", safe).strip("_")
        if safe.upper() in RESERVED_NAMES:
            safe = "_" + safe
        if len(safe) > 255:
            safe = safe[:255]
        return safe or "unnamed"

    def validate_file_path(self, filepath):
        """
        Validate file path for security issues (traversal, dangerous chars).

        Args:
            filepath: Path to validate

        Returns:
            bool: True if path appears safe
        """
        if not filepath or not isinstance(filepath, str):
            return False
        try:
            normalized = os.path.normpath(filepath)
            if ".." in normalized or "\x00" in filepath:
                return False
            name = os.path.basename(normalized)
            if len(name) > 255:
                return False
            if name.upper() in RESERVED_NAMES:
                return False
            return True
        except Exception:
            return False

    def validate_file_extension(self, filepath, allowed_extensions=None):
        """
        Validate that file has an allowed extension.

        Args:
            filepath: Path to the file
            allowed_extensions: List of allowed extensions (e.g. ['.mp3', '.mp4']),
                               or None to allow any

        Returns:
            bool: True if extension is allowed
        """
        if not filepath or not isinstance(filepath, str):
            return False
        ext = os.path.splitext(filepath)[1].lower()
        if allowed_extensions is None:
            return True
        return ext in [e.lower() if e.startswith(".") else f".{e.lower()}" for e in allowed_extensions]

    def is_safe_for_download(self, url):
        """
        Check if URL is safe for download (YouTube-like and no obvious abuse).

        Args:
            url: URL to check

        Returns:
            bool: True if URL appears safe
        """
        return self.validate_youtube_url(url)

    def validate_csv_data(self, csv_data):
        """
        Validate CSV data structure for sanity and safety.

        Args:
            csv_data: List of rows (each row is a list or tuple)

        Returns:
            bool: True if data appears valid
        """
        if csv_data is None:
            return False
        if not isinstance(csv_data, (list, tuple)):
            return False
        if len(csv_data) > 100000:
            return False
        for row in csv_data[:1000]:
            if not isinstance(row, (list, tuple)):
                return False
            if len(row) > 100:
                return False
            for cell in row:
                if cell is not None and not isinstance(cell, (str, int, float)):
                    return False
                if isinstance(cell, str) and len(cell) > 10000:
                    return False
        return True
