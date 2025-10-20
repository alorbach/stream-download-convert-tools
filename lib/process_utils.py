"""
Process Utilities

Handles subprocess execution, threading, and background operations.
"""

import os
import sys
import threading
import subprocess
from pathlib import Path


class ProcessManager:
    """Manages subprocess execution and threading."""
    
    def __init__(self, log_callback=None):
        """
        Initialize process manager.
        
        Args:
            log_callback: Function to call for logging messages
        """
        self.log_callback = log_callback or (lambda msg: print(f"[Process] {msg}"))
    
    def log(self, message):
        """Log a message using the callback."""
        self.log_callback(f"[Process] {message}")
    
    def run_command(self, cmd, capture_output=True, text=True):
        """
        Run a command using subprocess.run.
        
        Args:
            cmd: Command to run (list of strings)
            capture_output: Whether to capture output
            text: Whether to return text output
            
        Returns:
            subprocess.CompletedProcess: Process result
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=text,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result
        except Exception as e:
            self.log(f"Command execution failed: {e}")
            raise
    
    def run_command_streaming(self, cmd, output_callback=None):
        """
        Run a command with streaming output.
        
        Args:
            cmd: Command to run (list of strings)
            output_callback: Function to call for each output line
            
        Returns:
            int: Process return code
        """
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREate_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            for line in process.stdout:
                line_text = line.strip()
                if line_text and output_callback:
                    output_callback(line_text)
            
            process.wait()
            return process.returncode
            
        except Exception as e:
            self.log(f"Streaming command execution failed: {e}")
            raise
    
    def run_in_thread(self, target_func, args=(), kwargs=None, daemon=True):
        """
        Run a function in a separate thread.
        
        Args:
            target_func: Function to run
            args: Function arguments
            kwargs: Function keyword arguments
            daemon: Whether thread should be daemon
            
        Returns:
            threading.Thread: Thread object
        """
        if kwargs is None:
            kwargs = {}
        
        thread = threading.Thread(target=target_func, args=args, kwargs=kwargs)
        thread.daemon = daemon
        thread.start()
        return thread
    
    def build_ffmpeg_command(self, ffmpeg_path, input_file, output_file, 
                           audio_filters=None, video_filters=None, 
                           audio_codec='mp3', audio_bitrate='192k',
                           sample_rate=44100, channels=2):
        """
        Build FFmpeg command for audio/video processing.
        
        Args:
            ffmpeg_path: Path to FFmpeg executable
            input_file: Input file path
            output_file: Output file path
            audio_filters: List of audio filters
            video_filters: List of video filters
            audio_codec: Audio codec to use
            audio_bitrate: Audio bitrate
            sample_rate: Sample rate
            channels: Number of channels
            
        Returns:
            list: FFmpeg command as list of strings
        """
        cmd = [ffmpeg_path, '-i', str(input_file)]
        
        # Add video filters
        if video_filters:
            filter_str = ','.join(video_filters)
            cmd.extend(['-vf', filter_str])
        
        # Add audio filters
        if audio_filters:
            filter_str = ','.join(audio_filters)
            cmd.extend(['-af', filter_str])
        
        # Add audio settings
        cmd.extend([
            '-vn',  # No video
            '-ar', str(sample_rate),
            '-ac', str(channels),
            '-b:a', audio_bitrate,
            '-y',  # Overwrite output file
            str(output_file)
        ])
        
        return cmd
    
    def build_ytdlp_command(self, url, format_id, output_path):
        """
        Build yt-dlp command for downloading.
        
        Args:
            url: YouTube URL
            format_id: Format ID to download
            output_path: Output path template
            
        Returns:
            list: yt-dlp command as list of strings
        """
        return [
            'yt-dlp',
            '-f', format_id,
            '-o', output_path + '.%(ext)s',
            url
        ]
    
    def check_command_exists(self, command):
        """
        Check if a command exists in the system.
        
        Args:
            command: Command to check
            
        Returns:
            bool: True if command exists, False otherwise
        """
        try:
            result = subprocess.run(
                [command, '--version'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_system_info(self):
        """
        Get system information.
        
        Returns:
            dict: System information
        """
        return {
            'platform': sys.platform,
            'is_windows': sys.platform == 'win32',
            'is_linux': sys.platform.startswith('linux'),
            'is_macos': sys.platform == 'darwin'
        }
