"""
FFmpeg Utilities

Handles FFmpeg detection, installation, and management across platforms.
"""

import os
import sys
import platform
import subprocess
import threading
import urllib.request
import zipfile
import shutil
from pathlib import Path


class FFmpegManager:
    """Manages FFmpeg installation and detection."""
    
    def __init__(self, root_dir, log_callback=None):
        """
        Initialize FFmpeg manager.
        
        Args:
            root_dir: Root directory of the application
            log_callback: Function to call for logging messages
        """
        self.root_dir = root_dir
        self.ffmpeg_folder = os.path.join(root_dir, "ffmpeg")
        self.ffmpeg_path = None
        self.log_callback = log_callback or (lambda msg: print(f"[FFmpeg] {msg}"))
    
    def log(self, message):
        """Log a message using the callback."""
        self.log_callback(f"[FFmpeg] {message}")
    
    def check_ffmpeg(self):
        """
        Check if FFmpeg is available (local or system).
        
        Returns:
            bool: True if FFmpeg is available, False otherwise
        """
        # Check local FFmpeg first
        local_ffmpeg = os.path.join(
            self.ffmpeg_folder, 
            'bin', 
            'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        )
        
        if os.path.exists(local_ffmpeg):
            self.ffmpeg_path = local_ffmpeg
            self.log(f"Using local FFmpeg: {local_ffmpeg}")
            return True
        
        # Check system FFmpeg
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                self.ffmpeg_path = 'ffmpeg'
                self.log("Using system FFmpeg")
                return True
        except FileNotFoundError:
            pass
        
        self.log("FFmpeg not found")
        return False
    
    def get_ffmpeg_command(self):
        """
        Get the FFmpeg command to use.
        
        Returns:
            str: FFmpeg command (path or 'ffmpeg')
        """
        return self.ffmpeg_path if self.ffmpeg_path else 'ffmpeg'
    
    def offer_ffmpeg_install(self, messagebox_callback=None):
        """
        Offer to install FFmpeg automatically.
        
        Args:
            messagebox_callback: Function to show message boxes
        """
        system = platform.system()
        
        if system == 'Windows':
            if messagebox_callback:
                response = messagebox_callback(
                    "askyesno",
                    "FFmpeg Not Found",
                    "FFmpeg is required for processing but was not found.\n\n"
                    "Would you like to download FFmpeg automatically?\n"
                    "(Portable version, no admin rights needed)\n\n"
                    "This will download approximately 80MB."
                )
                
                if response:
                    return self.download_ffmpeg_windows()
                else:
                    messagebox_callback(
                        "showinfo",
                        "Manual Installation",
                        "You can download FFmpeg manually from:\n"
                        "https://ffmpeg.org/download.html\n\n"
                        "Add it to your system PATH or place it in the\n"
                        "ffmpeg/bin folder within this project."
                    )
        else:
            install_cmd = ""
            if system == 'Linux':
                install_cmd = "sudo apt-get install ffmpeg"
            elif system == 'Darwin':
                install_cmd = "brew install ffmpeg"
            
            if messagebox_callback:
                messagebox_callback(
                    "showerror",
                    "FFmpeg Not Found",
                    f"FFmpeg is required for processing.\n\n"
                    f"Please install FFmpeg using:\n"
                    f"{install_cmd}\n\n"
                    f"Or download from: https://ffmpeg.org/download.html"
                )
            
            self.log(f"FFmpeg not found. Install command: {install_cmd}")
        
        return False
    
    def download_ffmpeg_windows(self, progress_callback=None, success_callback=None, error_callback=None):
        """
        Download FFmpeg for Windows.
        
        Args:
            progress_callback: Function to call for progress updates
            success_callback: Function to call on success
            error_callback: Function to call on error
        """
        self.log("Starting FFmpeg download...")
        
        thread = threading.Thread(target=self._download_ffmpeg_thread, 
                                args=(progress_callback, success_callback, error_callback))
        thread.daemon = True
        thread.start()
    
    def _download_ffmpeg_thread(self, progress_callback=None, success_callback=None, error_callback=None):
        """Download FFmpeg in a separate thread."""
        try:
            ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            temp_zip = os.path.join(self.root_dir, "ffmpeg_temp.zip")
            
            self.log(f"Downloading from: {ffmpeg_url}")
            self.log("This may take a few minutes...")
            
            def download_progress(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int((block_num * block_size / total_size) * 100)
                    if block_num % 50 == 0:
                        if progress_callback:
                            progress_callback(f"Download progress: {percent}%")
            
            urllib.request.urlretrieve(ffmpeg_url, temp_zip, download_progress)
            
            self.log("Download complete. Extracting...")
            
            os.makedirs(self.ffmpeg_folder, exist_ok=True)
            
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if '/bin/' in member and member.endswith(('.exe', '.dll')):
                        filename = os.path.basename(member)
                        target_path = os.path.join(self.ffmpeg_folder, 'bin', filename)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        
                        with zip_ref.open(member) as source:
                            with open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
            
            os.remove(temp_zip)
            
            self.log("FFmpeg installed successfully!")
            if success_callback:
                success_callback("FFmpeg has been installed successfully!\n\nYou can now process files.")
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"FFmpeg download failed: {error_msg}")
            if error_callback:
                error_callback(
                    f"Failed to download FFmpeg:\n{error_msg}\n\n"
                    "Please download manually from:\n"
                    "https://ffmpeg.org/download.html"
                )
