"""
MP3 to Video Converter

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

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinterdnd2 import DND_FILES, TkinterDnD
import os
import sys
import threading
import subprocess
import json
from pathlib import Path
from PIL import Image

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI
from lib.gui_utils import GUIManager, LogManager
from lib.file_utils import FileManager
from lib.process_utils import ProcessManager
from lib.ffmpeg_utils import FFmpegManager


class MP3ToVideoConverterGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "MP3 to Video Converter")
        self.root.geometry("900x700")
        
        # File attributes
        self.selected_mp3_files = []
        self.selected_image_file = None
        self.selected_video_file = None
        self.conversion_queue = []
        
        # Video source type
        self.video_source_type = tk.StringVar(value="image")
        
        # Loop settings
        self.loop_mode = tk.StringVar(value="forward")
        
        # Image dimensions (will be set when image is selected)
        self.image_width = None
        self.image_height = None
        
        # Video dimensions (will be set when video is selected)
        self.video_width = None
        self.video_height = None
        
        # Scaling mode for aspect ratio handling
        self.scaling_mode = tk.StringVar(value="stretch")
        
        # Settings file path
        self.settings_file = os.path.join(self.root_dir, "mp3_to_video_converter_settings.json")
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # MP3 Files Selection
        self.mp3_frame = ttk.LabelFrame(main_frame, text="MP3 Files Selection", padding=10)
        self.mp3_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.btn_mp3_frame = ttk.Frame(self.mp3_frame)
        self.btn_mp3_frame.pack(fill='x', pady=5)
        
        ttk.Button(self.btn_mp3_frame, text="Select MP3 Files", command=self.select_mp3_files).pack(side='left', padx=5)
        ttk.Button(self.btn_mp3_frame, text="Clear Selection", command=self.clear_mp3_selection).pack(side='left', padx=5)
        
        self.lbl_mp3_status = ttk.Label(self.btn_mp3_frame, text="No files selected")
        self.lbl_mp3_status.pack(side='left', padx=10)
        
        ttk.Label(self.mp3_frame, text="Selected MP3 Files:").pack(anchor='w', pady=(10, 5))
        
        list_frame = ttk.Frame(self.mp3_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar_y = ttk.Scrollbar(list_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(list_frame, orient='horizontal')
        
        self.mp3_file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=6,
            selectmode=tk.EXTENDED
        )
        
        scrollbar_y.config(command=self.mp3_file_listbox.yview)
        scrollbar_x.config(command=self.mp3_file_listbox.xview)
        
        self.mp3_file_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Drag-and-drop: allow dropping MP3/audio files onto the list
        try:
            self.mp3_file_listbox.drop_target_register(DND_FILES)
            self.mp3_file_listbox.dnd_bind('<<Drop>>', self.on_drop_mp3_files)
            # Also allow dropping anywhere in the MP3 section
            self.mp3_frame.drop_target_register(DND_FILES)
            self.mp3_frame.dnd_bind('<<Drop>>', self.on_drop_mp3_files)
            self.btn_mp3_frame.drop_target_register(DND_FILES)
            self.btn_mp3_frame.dnd_bind('<<Drop>>', self.on_drop_mp3_files)
            print("[DEBUG] DnD registered: mp3_file_listbox, mp3_frame, btn_mp3_frame")
        except Exception:
            pass
        
        # Video Source Selection
        source_frame = ttk.LabelFrame(main_frame, text="Video Source", padding=10)
        source_frame.pack(fill='x', pady=(0, 10))
        
        # Source type selection
        type_frame = ttk.Frame(source_frame)
        type_frame.pack(fill='x', pady=5)
        
        ttk.Label(type_frame, text="Source Type:").pack(side='left')
        ttk.Radiobutton(type_frame, text="Image", variable=self.video_source_type, 
                       value="image", command=self.on_source_type_change).pack(side='left', padx=10)
        ttk.Radiobutton(type_frame, text="Video", variable=self.video_source_type, 
                       value="video", command=self.on_source_type_change).pack(side='left', padx=10)
        
        # Image file selection
        self.image_frame = ttk.Frame(source_frame)
        self.image_frame.pack(fill='x', pady=5)
        
        btn_image_frame = ttk.Frame(self.image_frame)
        btn_image_frame.pack(fill='x')
        
        ttk.Button(btn_image_frame, text="Select Image File", command=self.select_image_file).pack(side='left', padx=5)
        ttk.Button(btn_image_frame, text="Clear Image", command=self.clear_image_selection).pack(side='left', padx=5)
        
        self.lbl_image_status = ttk.Label(btn_image_frame, text="No image selected")
        self.lbl_image_status.pack(side='left', padx=10)

        # Drag-and-drop: allow dropping image file onto the image area label
        try:
            self.lbl_image_status.drop_target_register(DND_FILES)
            self.lbl_image_status.dnd_bind('<<Drop>>', self.on_drop_image_file)
            print("[DEBUG] DnD registered: lbl_image_status")
        except Exception:
            pass
        
        # Video file selection
        self.video_frame = ttk.Frame(source_frame)
        self.video_frame.pack(fill='x', pady=5)
        
        self.btn_video_frame = ttk.Frame(self.video_frame)
        self.btn_video_frame.pack(fill='x')
        
        ttk.Button(self.btn_video_frame, text="Select Video File", command=self.select_video_file).pack(side='left', padx=5)
        ttk.Button(self.btn_video_frame, text="Clear Video", command=self.clear_video_selection).pack(side='left', padx=5)
        
        self.lbl_video_status = ttk.Label(self.btn_video_frame, text="No video selected")
        self.lbl_video_status.pack(side='left', padx=10)

        # Drag-and-drop: allow dropping video file onto the video area label and containers
        try:
            self.lbl_video_status.drop_target_register(DND_FILES)
            self.lbl_video_status.dnd_bind('<<Drop>>', self.on_drop_video_file)
            self.video_frame.drop_target_register(DND_FILES)
            self.video_frame.dnd_bind('<<Drop>>', self.on_drop_video_file)
            self.btn_video_frame.drop_target_register(DND_FILES)
            self.btn_video_frame.dnd_bind('<<Drop>>', self.on_drop_video_file)
            print("[DEBUG] DnD registered: lbl_video_status, video_frame, btn_video_frame")
        except Exception:
            pass
        
        # Loop settings (only for video source)
        self.loop_frame = ttk.LabelFrame(source_frame, text="Loop Settings", padding=10)
        self.loop_frame.pack(fill='x', pady=5)
        
        loop_type_frame = ttk.Frame(self.loop_frame)
        loop_type_frame.pack(fill='x')
        
        ttk.Label(loop_type_frame, text="Loop Mode:").pack(side='left')
        ttk.Radiobutton(loop_type_frame, text="Forward Only", variable=self.loop_mode, 
                       value="forward").pack(side='left', padx=10)
        ttk.Radiobutton(loop_type_frame, text="Forward & Reverse", variable=self.loop_mode, 
                       value="forward_reverse").pack(side='left', padx=10)
        
        # Conversion Settings
        settings_frame = ttk.LabelFrame(main_frame, text="Conversion Settings", padding=10)
        settings_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.output_folder_var = tk.StringVar(value=self.file_manager.output_folder)
        ttk.Entry(settings_frame, textvariable=self.output_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_output_folder).grid(row=0, column=2)
        
        ttk.Label(settings_frame, text="Video Quality:").grid(row=1, column=0, sticky='w', pady=5)
        self.video_quality_var = tk.StringVar(value="Auto")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.video_quality_var, width=20, state='readonly')
        quality_combo['values'] = ('Auto', '480p', '720p', '1080p', 'Mobile Portrait (9:16)', 'Mobile Landscape (16:9)', 'Instagram Square (1:1)', 'Instagram Story (9:16)', 'Portrait 2:3', 'Landscape 3:2', 'Source Size')
        quality_combo.grid(row=1, column=1, sticky='w', padx=5)
        
        # Image/Video dimensions display
        self.image_dimensions_label = ttk.Label(settings_frame, text="", foreground='blue')
        self.image_dimensions_label.grid(row=1, column=2, sticky='w', padx=5)
        
        ttk.Label(settings_frame, text="Video Codec:").grid(row=2, column=0, sticky='w', pady=5)
        self.video_codec_var = tk.StringVar(value="libx264")
        codec_combo = ttk.Combobox(settings_frame, textvariable=self.video_codec_var, width=20, state='readonly')
        codec_combo['values'] = ('libx264', 'libx265', 'libvpx-vp9')
        codec_combo.grid(row=2, column=1, sticky='w', padx=5)
        
        ttk.Label(settings_frame, text="Video Quality:").grid(row=3, column=0, sticky='w', pady=5)
        self.video_bitrate_var = tk.StringVar(value="High Quality (CRF 18)")
        bitrate_combo = ttk.Combobox(settings_frame, textvariable=self.video_bitrate_var, width=20, state='readonly')
        bitrate_combo['values'] = (
            'High Quality (CRF 18)',
            'Medium Quality (CRF 23)',
            'Low Quality (CRF 28)',
            'Very High Quality (CRF 15)',
            'Maximum Compression (CRF 32)'
        )
        bitrate_combo.grid(row=3, column=1, sticky='w', padx=5)
        
        # Quality description
        quality_desc_frame = ttk.Frame(settings_frame)
        quality_desc_frame.grid(row=3, column=2, sticky='w', padx=5)
        ttk.Label(quality_desc_frame, text="Lower CRF = Higher Quality", font=('Arial', 8), foreground='gray').pack()
        ttk.Label(quality_desc_frame, text="Recommended: Medium (23)", font=('Arial', 8), foreground='gray').pack()
        
        ttk.Label(settings_frame, text="Scaling Mode:").grid(row=4, column=0, sticky='w', pady=5)
        self.scaling_mode_var = tk.StringVar(value="stretch")
        scaling_combo = ttk.Combobox(settings_frame, textvariable=self.scaling_mode_var, width=20, state='readonly')
        scaling_combo['values'] = ('stretch', 'expand', 'truncate')
        scaling_combo.grid(row=4, column=1, sticky='w', padx=5)
        
        # Scaling mode description
        scaling_desc_frame = ttk.Frame(settings_frame)
        scaling_desc_frame.grid(row=4, column=2, sticky='w', padx=5)
        ttk.Label(scaling_desc_frame, text="Stretch: Fill frame (may distort)", font=('Arial', 8), foreground='gray').pack()
        ttk.Label(scaling_desc_frame, text="Expand: Fit with black bars", font=('Arial', 8), foreground='gray').pack()
        ttk.Label(scaling_desc_frame, text="Truncate: Crop to fit", font=('Arial', 8), foreground='gray').pack()
        
        # Conversion Controls
        convert_frame = ttk.Frame(main_frame)
        convert_frame.pack(fill='x', pady=(0, 10))
        
        batch_frame = ttk.Frame(convert_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Convert Selected Files", command=self.start_conversion).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Convert All Files", command=self.convert_all_files).pack(side='left', padx=5)
        
        self.progress = ttk.Progressbar(convert_frame, mode='determinate')
        self.progress.pack(fill='x', pady=5)
        
        self.progress_label = ttk.Label(convert_frame, text="")
        self.progress_label.pack(anchor='w')
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Conversion Log", padding=10)
        log_frame.pack(fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill='both', expand=True)
        
        # Initialize log manager
        self.log_manager = LogManager(self.log_text)
        
        # Info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=5)
        
        info_text = "Supported formats: MP3 audio | JPG/PNG images | MP4/WEBM/AVI/MOV videos | Requires FFmpeg"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
        
        # Initialize UI state
        self.on_source_type_change()
        
        # Bind settings save events
        self.output_folder_var.trace('w', self.save_settings)
        self.video_quality_var.trace('w', self.save_settings)
        self.video_codec_var.trace('w', self.save_settings)
        self.video_bitrate_var.trace('w', self.save_settings)
        self.scaling_mode_var.trace('w', self.save_settings)
        self.video_source_type.trace('w', self.save_settings)
        self.loop_mode.trace('w', self.save_settings)

        # Global drag-and-drop as a safety net (window and main container)
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop_any)
            print("[DEBUG] DnD registered: root")
        except Exception:
            pass
        try:
            main_frame.drop_target_register(DND_FILES)
            main_frame.dnd_bind('<<Drop>>', self.on_drop_any)
            print("[DEBUG] DnD registered: main_frame")
        except Exception:
            pass
    
    def on_source_type_change(self):
        """Handle video source type change."""
        source_type = self.video_source_type.get()
        
        if source_type == "image":
            self.image_frame.pack(fill='x', pady=5)
            self.video_frame.pack_forget()
            self.loop_frame.pack_forget()
        else:  # video
            self.image_frame.pack_forget()
            self.video_frame.pack(fill='x', pady=5)
            self.loop_frame.pack(fill='x', pady=5)
    
    def select_mp3_files(self):
        """Select MP3 files."""
        files = self.select_files(
            title="Select MP3 Files",
            filetypes=[
                ("MP3 Files", "*.mp3"),
                ("Audio Files", "*.mp3 *.m4a *.wav *.ogg *.flac"),
                ("All Files", "*.*")
            ],
            initial_dir=self.file_manager.get_folder_path('converted')
        )
        
        if files:
            for file in files:
                if file not in self.selected_mp3_files:
                    self.selected_mp3_files.append(file)
            
            self.update_mp3_file_list()
            self.log(f"[INFO] Added {len(files)} MP3 file(s) to selection")
            # Auto-set output folder to the folder of the first selected MP3
            self._auto_set_output_from_mp3(files[0])
    
    def clear_mp3_selection(self):
        """Clear MP3 file selection."""
        self.selected_mp3_files.clear()
        self.update_mp3_file_list()
        self.log("[INFO] MP3 selection cleared")
    
    def update_mp3_file_list(self):
        """Update MP3 file listbox."""
        self.mp3_file_listbox.delete(0, tk.END)
        
        for file in self.selected_mp3_files:
            filename = os.path.basename(file)
            self.mp3_file_listbox.insert(tk.END, filename)
        
        count = len(self.selected_mp3_files)
        self.lbl_mp3_status.config(text=f"{count} file(s) selected")

    def _parse_dropped_paths(self, data):
        """Parse dropped file list from DND event data (supports {path with spaces})."""
        import re
        if not data:
            return []
        # Match sequences wrapped in { }, or in double quotes, or bare non-space tokens
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
        print(f"[DEBUG] Parsed drop data: {paths}")
        return paths

    def on_drop_mp3_files(self, event):
        print(f"[DEBUG] on_drop_mp3_files from {event.widget}: {event.data}")
        paths = self._parse_dropped_paths(event.data)
        allowed_ext = {'.mp3', '.m4a', '.wav', '.ogg', '.flac'}
        added = 0
        first_added = None
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in allowed_ext and p not in self.selected_mp3_files:
                self.selected_mp3_files.append(p)
                added += 1
                if first_added is None:
                    first_added = p
        if added:
            self.update_mp3_file_list()
            self.log(f"[INFO] Added {added} audio file(s) via drag and drop")
            if first_added:
                self._auto_set_output_from_mp3(first_added)
        else:
            print("[DEBUG] No valid audio files in drop")

    def on_drop_image_file(self, event):
        print(f"[DEBUG] on_drop_image_file from {event.widget}: {event.data}")
        paths = self._parse_dropped_paths(event.data)
        image_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in image_ext:
                self.selected_image_file = p
                filename = os.path.basename(self.selected_image_file)
                self.lbl_image_status.config(text=f"Selected: {filename}")
                # Get dimensions if possible
                try:
                    from PIL import Image
                    with Image.open(self.selected_image_file) as img:
                        self.image_width, self.image_height = img.size
                        self.image_dimensions_label.config(text=f"({self.image_width}x{self.image_height})")
                except Exception:
                    self.image_width, self.image_height = None, None
                    self.image_dimensions_label.config(text="")
                self.log(f"[INFO] Image selected via drag and drop: {filename}")
                break
        else:
            print("[DEBUG] No valid image file in drop")

    def on_drop_video_file(self, event):
        print(f"[DEBUG] on_drop_video_file from {event.widget}: {event.data}")
        paths = self._parse_dropped_paths(event.data)
        video_ext = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in video_ext:
                self.selected_video_file = p
                filename = os.path.basename(self.selected_video_file)
                self.lbl_video_status.config(text=f"Selected: {filename}")
                
                # Get video dimensions
                self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
                if self.video_width and self.video_height:
                    self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})")
                    self.log(f"[INFO] Video selected via drag and drop: {filename} ({self.video_width}x{self.video_height})")
                else:
                    self.video_width, self.video_height = None, None
                    self.image_dimensions_label.config(text="(dimensions unknown)")
                    self.log(f"[INFO] Video selected via drag and drop: {filename}")
                break
        else:
            print("[DEBUG] No valid video file in drop")

    def on_drop_any(self, event):
        """Catch-all drop handler: accepts MP3s into list and a single video file."""
        print(f"[DEBUG] on_drop_any from {event.widget}: {event.data}")
        paths = self._parse_dropped_paths(event.data)
        audio_ext = {'.mp3', '.m4a', '.wav', '.ogg', '.flac'}
        video_ext = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        added_audio = 0
        set_video = False
        first_added_audio = None
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in audio_ext:
                if p not in self.selected_mp3_files:
                    self.selected_mp3_files.append(p)
                    added_audio += 1
                    if first_added_audio is None:
                        first_added_audio = p
            elif ext in video_ext and not set_video:
                self.selected_video_file = p
                filename = os.path.basename(self.selected_video_file)
                self.lbl_video_status.config(text=f"Selected: {filename}")
                
                # Get video dimensions
                self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
                if self.video_width and self.video_height:
                    self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})")
                else:
                    self.video_width, self.video_height = None, None
                    self.image_dimensions_label.config(text="(dimensions unknown)")
                
                set_video = True
        if added_audio:
            self.update_mp3_file_list()
            self.log(f"[INFO] Added {added_audio} audio file(s) via drag and drop")
            if first_added_audio:
                self._auto_set_output_from_mp3(first_added_audio)
        if set_video:
            self.log("[INFO] Video selected via drag and drop (global handler)")

    def _auto_set_output_from_mp3(self, reference_file):
        """Set output folder to the directory of the reference MP3 file."""
        try:
            folder = os.path.dirname(reference_file)
            if folder and os.path.isdir(folder):
                self.output_folder_var.set(folder)
                self.file_manager.set_folder_path('output', folder)
                self.log(f"[INFO] Output folder set to: {folder}")
        except Exception as e:
            print(f"[DEBUG] Failed to auto-set output folder: {e}")
    
    def select_image_file(self):
        """Select image file."""
        files = self.select_files(
            title="Select Image File",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("JPEG Files", "*.jpg *.jpeg"),
                ("PNG Files", "*.png"),
                ("All Files", "*.*")
            ]
        )
        
        if files:
            self.selected_image_file = files[0]
            filename = os.path.basename(self.selected_image_file)
            self.lbl_image_status.config(text=f"Selected: {filename}")
            
            # Get image dimensions
            try:
                with Image.open(self.selected_image_file) as img:
                    self.image_width, self.image_height = img.size
                    self.image_dimensions_label.config(text=f"({self.image_width}x{self.image_height})")
                    self.log(f"[INFO] Selected image: {filename} ({self.image_width}x{self.image_height})")
            except Exception as e:
                self.image_width, self.image_height = None, None
                self.image_dimensions_label.config(text="(dimensions unknown)")
                self.log(f"[WARNING] Could not read image dimensions: {str(e)}")
                self.log(f"[INFO] Selected image: {filename}")
    
    def clear_image_selection(self):
        """Clear image selection."""
        self.selected_image_file = None
        self.image_width, self.image_height = None, None
        self.lbl_image_status.config(text="No image selected")
        self.image_dimensions_label.config(text="")
        # Reset to Auto when image is cleared
        self.video_quality_var.set("Auto")
        self.log("[INFO] Image selection cleared")
    
    def _get_video_resolution(self, video_file):
        """Get video resolution (width, height) from video file."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            probe_cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            # Use bytes mode and decode manually to avoid encoding issues
            probe_result = subprocess.run(
                probe_cmd, 
                capture_output=True, 
                timeout=5
            )
            
            # Decode stderr with error handling
            try:
                stderr_text = probe_result.stderr.decode('utf-8', errors='replace')
            except:
                try:
                    stderr_text = probe_result.stderr.decode('cp1252', errors='replace')
                except:
                    stderr_text = ''
            
            for line in stderr_text.split('\n'):
                if 'Video:' in line and 'x' in line:
                    try:
                        parts = line.split('Video:')[1].split(',')
                        for part in parts:
                            if 'x' in part:
                                res_part = part.strip().split()[0]
                                if 'x' in res_part and res_part.replace('x', '').replace('-', '').isdigit():
                                    w, h = res_part.split('x')
                                    return int(w), int(h)
                    except:
                        pass
            return None, None
        except Exception as e:
            # Silently fail - don't log to avoid encoding issues in log
            return None, None
    
    def select_video_file(self):
        """Select video file."""
        files = self.select_files(
            title="Select Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.webm *.avi *.mov *.mkv *.flv *.wmv"),
                ("MP4 Files", "*.mp4"),
                ("WEBM Files", "*.webm"),
                ("All Files", "*.*")
            ]
        )
        
        if files:
            self.selected_video_file = files[0]
            filename = os.path.basename(self.selected_video_file)
            self.lbl_video_status.config(text=f"Selected: {filename}")
            
            # Get video dimensions
            self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
            if self.video_width and self.video_height:
                self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})")
                self.log(f"[INFO] Selected video: {filename} ({self.video_width}x{self.video_height})")
            else:
                self.video_width, self.video_height = None, None
                self.image_dimensions_label.config(text="(dimensions unknown)")
                self.log(f"[WARNING] Could not read video dimensions")
                self.log(f"[INFO] Selected video: {filename}")
    
    def clear_video_selection(self):
        """Clear video selection."""
        self.selected_video_file = None
        self.video_width, self.video_height = None, None
        self.lbl_video_status.config(text="No video selected")
        self.image_dimensions_label.config(text="")
        # Reset to Auto when video is cleared
        self.video_quality_var.set("Auto")
        self.log("[INFO] Video selection cleared")
    
    def browse_output_folder(self):
        """Browse for output folder."""
        folder = self.browse_folder(self.output_folder_var.get())
        if folder:
            self.output_folder_var.set(folder)
            self.file_manager.set_folder_path('output', folder)
    
    def start_conversion(self):
        """Start conversion process."""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        if not self.selected_mp3_files:
            messagebox.showwarning("Warning", "Please select at least one MP3 file")
            return
        
        source_type = self.video_source_type.get()
        if source_type == "image" and not self.selected_image_file:
            messagebox.showwarning("Warning", "Please select an image file")
            return
        elif source_type == "video" and not self.selected_video_file:
            messagebox.showwarning("Warning", "Please select a video file")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        self.file_manager.set_folder_path('output', self.output_folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('output'))
        
        self.conversion_queue = self.selected_mp3_files.copy()
        
        self.log(f"[INFO] Starting conversion of {len(self.conversion_queue)} file(s)")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('output')}")
        self.log(f"[INFO] Video source: {source_type}")
        self.log(f"[INFO] Video resolution: {self.video_quality_var.get()}")
        self.log(f"[INFO] Video quality/bitrate: {self.video_bitrate_var.get()}")
        self.log(f"[INFO] Video codec: {self.video_codec_var.get()}")
        
        self.progress['maximum'] = len(self.conversion_queue)
        self.progress['value'] = 0
        
        self.set_busy(True, "Converting...")
        
        thread = threading.Thread(target=self._conversion_thread)
        thread.daemon = True
        thread.start()
    
    def _conversion_thread(self):
        """Conversion thread."""
        success_count = 0
        error_count = 0
        
        source_type = self.video_source_type.get()
        loop_mode = self.loop_mode.get()
        video_quality = self.video_quality_var.get()
        video_codec = self.video_codec_var.get()
        video_bitrate = self.video_bitrate_var.get()
        scaling_mode = self.scaling_mode_var.get()
        
        for i, input_file in enumerate(self.conversion_queue):
            input_path = Path(input_file)
            output_file = os.path.join(
                self.file_manager.get_folder_path('output'), 
                f"{input_path.stem}_video.mp4"
            )
            
            self.root.after(
                0,
                lambda idx=i+1, total=len(self.conversion_queue), name=input_path.name:
                self.set_busy(True, f"Converting {idx}/{total}: {name}")
            )
            
            self.root.after(
                0,
                lambda msg=f"\n[INFO] Converting ({i+1}/{len(self.conversion_queue)}): {input_path.name}":
                self.log(msg)
            )
            
            try:
                cmd = self._build_conversion_command(
                    input_file, output_file, source_type, loop_mode, video_quality, video_codec, video_bitrate, scaling_mode
                )
                
                # Debug: Log the FFmpeg command
                self.root.after(0, lambda cmd_str=' '.join(cmd): self.log(f"[DEBUG] FFmpeg command: {cmd_str}"))
                
                process = self.run_ffmpeg_command(cmd)
                
                # Log stdout and stderr
                if process.stdout:
                    self.root.after(0, lambda out=process.stdout: self.log(f"[DEBUG] FFmpeg stdout: {out}"))
                if process.stderr:
                    self.root.after(0, lambda err=process.stderr: self.log(f"[DEBUG] FFmpeg stderr: {err}"))
                self.root.after(0, lambda code=process.returncode: self.log(f"[DEBUG] FFmpeg return code: {code}"))
                
                if process.returncode == 0:
                    success_count += 1
                    self.root.after(
                        0,
                        lambda out=output_file:
                        self.log(f"[SUCCESS] Saved: {os.path.basename(out)}")
                    )
                else:
                    error_count += 1
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg:
                        self.log(f"[ERROR] Conversion failed: {err[:500]}")
                    )
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Exception: {msg}")
                )
            
            self.root.after(0, lambda v=i+1: self.progress.config(value=v))
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            self.log(f"\n[COMPLETE] Conversion finished: {s} succeeded, {e} failed")
        )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            messagebox.showinfo(
                "Conversion Complete",
                f"Conversion finished!\n\nSuccessful: {s}\nFailed: {e}"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False))
    
    def _get_scaling_filter(self, target_width, target_height, scaling_mode):
        """Get FFmpeg scaling filter based on scaling mode."""
        if scaling_mode == "stretch":
            # Direct scaling - may distort aspect ratio
            return f"scale={target_width}:{target_height}"
        elif scaling_mode == "expand":
            # Fit within frame with black bars (letterbox/pillarbox)
            return f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
        elif scaling_mode == "truncate":
            # Crop to fit frame (may cut off parts)
            return f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase,crop={target_width}:{target_height}"
        else:
            # Default to stretch
            return f"scale={target_width}:{target_height}"
    
    def _get_crf_value(self, video_bitrate, video_codec):
        """Get CRF value based on quality preset and codec."""
        # Extract CRF number from quality string (e.g., "High Quality (CRF 18)" -> 18)
        import re
        match = re.search(r'CRF\s+(\d+)', video_bitrate)
        if match:
            base_crf = int(match.group(1))
        else:
            # Default fallback
            base_crf = 23
        
        # Adjust for different codecs (x265 and VP9 use different ranges)
        if video_codec == 'libx264':
            return base_crf  # x264: 0-51, typical 18-28
        elif video_codec == 'libx265':
            # x265: 0-51, but typically 20-30 for similar quality to x264
            return min(base_crf + 2, 51)  # Slightly higher for similar quality
        elif video_codec == 'libvpx-vp9':
            # VP9: 0-63, but typically 30-50 for similar quality
            return min(base_crf + 12, 63)  # Much higher for similar quality
        else:
            return base_crf
    
    def _build_conversion_command(self, input_file, output_file, source_type, loop_mode, video_quality, video_codec, video_bitrate, scaling_mode):
        """Build FFmpeg conversion command."""
        ffmpeg_cmd = self.get_ffmpeg_command()
        
        # Base command
        cmd = [ffmpeg_cmd, '-y']  # -y to overwrite output files
        
        if source_type == "image":
            # Image + MP3 = Video
            cmd.extend(['-loop', '1', '-i', self.selected_image_file])
            cmd.extend(['-i', input_file])
            
            # Map audio and video
            cmd.extend(['-map', '0:v:0', '-map', '1:a:0'])
            
            # Video settings
            if video_quality == "480p":
                scale_filter = self._get_scaling_filter(854, 480, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "720p":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "1080p":
                scale_filter = self._get_scaling_filter(1920, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Mobile Portrait (9:16)":
                scale_filter = self._get_scaling_filter(720, 1280, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Mobile Landscape (16:9)":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Instagram Square (1:1)":
                scale_filter = self._get_scaling_filter(1080, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Instagram Story (9:16)":
                scale_filter = self._get_scaling_filter(1080, 1920, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Portrait 2:3":
                scale_filter = self._get_scaling_filter(720, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Landscape 3:2":
                scale_filter = self._get_scaling_filter(1080, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Source Size":
                # Use source dimensions (image for image source, video for video source)
                if self.image_width and self.image_height:
                    scale_filter = self._get_scaling_filter(self.image_width, self.image_height, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
                else:
                    # Fallback to 720p if dimensions not available
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
            elif video_quality == "Auto":
                # Auto mode: use source dimensions if available, otherwise default to 720p
                if self.image_width and self.image_height:
                    scale_filter = self._get_scaling_filter(self.image_width, self.image_height, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
                else:
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
            
            # Audio settings
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            
            # Video codec
            cmd.extend(['-c:v', video_codec])
            
            # Video quality (CRF)
            crf_value = self._get_crf_value(video_bitrate, video_codec)
            if video_codec == 'libx264':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-preset', 'medium'])  # Balance between speed and compression
            elif video_codec == 'libx265':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-preset', 'medium'])
            elif video_codec == 'libvpx-vp9':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-b:v', '0'])  # VP9 requires -b:v 0 when using CRF
            
            # Duration (match audio length)
            cmd.extend(['-shortest'])
            
        else:  # video source
            # Video + MP3 = New Video (loop video to match audio length)
            cmd.extend(['-stream_loop', '-1', '-i', self.selected_video_file])  # Loop video indefinitely
            cmd.extend(['-i', input_file])
            
            # Get scaling filter for the selected quality
            if video_quality == "480p":
                scale_filter = self._get_scaling_filter(854, 480, scaling_mode)
            elif video_quality == "720p":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "1080p":
                scale_filter = self._get_scaling_filter(1920, 1080, scaling_mode)
            elif video_quality == "Mobile Portrait (9:16)":
                scale_filter = self._get_scaling_filter(720, 1280, scaling_mode)
            elif video_quality == "Mobile Landscape (16:9)":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "Instagram Square (1:1)":
                scale_filter = self._get_scaling_filter(1080, 1080, scaling_mode)
            elif video_quality == "Instagram Story (9:16)":
                scale_filter = self._get_scaling_filter(1080, 1920, scaling_mode)
            elif video_quality == "Portrait 2:3":
                scale_filter = self._get_scaling_filter(720, 1080, scaling_mode)
            elif video_quality == "Landscape 3:2":
                scale_filter = self._get_scaling_filter(1080, 720, scaling_mode)
            elif video_quality == "Source Size":
                # Use source dimensions (video for video source)
                if self.video_width and self.video_height:
                    scale_filter = self._get_scaling_filter(self.video_width, self.video_height, scaling_mode)
                else:
                    # Fallback to 720p if dimensions not available
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "Auto":
                # Auto mode: use source dimensions if available, otherwise default to 720p
                if self.video_width and self.video_height:
                    scale_filter = self._get_scaling_filter(self.video_width, self.video_height, scaling_mode)
                else:
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            else:
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)  # Default fallback
            
            if loop_mode == "forward_reverse":
                # Create forward-reverse loop effect - use temp file approach
                temp_video = os.path.join(os.path.dirname(output_file), f"temp_forward_reverse_{os.path.basename(output_file)}")
                
                # Step 1: Create forward-reverse segment (no looping yet)
                ffmpeg_cmd = self.get_ffmpeg_command()
                temp_cmd = [ffmpeg_cmd, '-y']
                temp_cmd.extend(['-i', self.selected_video_file])
                temp_cmd.extend(['-filter_complex', 
                               f'[0:v]{scale_filter}[v_scaled];[0:v]{scale_filter}[v_scaled2];[v_scaled2]reverse[v_rev];[v_scaled][v_rev]concat=n=2:v=1:a=0[v_final]'])
                temp_cmd.extend(['-map', '[v_final]'])
                temp_cmd.extend(['-c:v', video_codec])
                # Add CRF for temp video too
                crf_value = self._get_crf_value(video_bitrate, video_codec)
                if video_codec == 'libx264':
                    temp_cmd.extend(['-crf', str(crf_value)])
                    temp_cmd.extend(['-preset', 'medium'])
                elif video_codec == 'libx265':
                    temp_cmd.extend(['-crf', str(crf_value)])
                    temp_cmd.extend(['-preset', 'medium'])
                elif video_codec == 'libvpx-vp9':
                    temp_cmd.extend(['-crf', str(crf_value)])
                    temp_cmd.extend(['-b:v', '0'])
                temp_cmd.append(temp_video)
                
                # Execute temp video creation
                try:
                    self.log(f"[DEBUG] Temp video creation command: {' '.join(temp_cmd)}")
                    result = subprocess.run(
                        temp_cmd, 
                        capture_output=True, 
                        text=True, 
                        encoding='utf-8',
                        errors='replace',
                        cwd=self.root_dir
                    )
                    self.log(f"[DEBUG] Temp video creation stdout: {result.stdout}")
                    self.log(f"[DEBUG] Temp video creation stderr: {result.stderr}")
                    self.log(f"[DEBUG] Temp video creation return code: {result.returncode}")
                    if result.returncode != 0:
                        raise Exception(f"Temp video creation failed: {result.stderr}")
                    
                    # Step 2: Loop the temp video to match audio length
                    cmd = [ffmpeg_cmd, '-y']
                    cmd.extend(['-stream_loop', '-1', '-i', temp_video])  # Loop temp video indefinitely
                    cmd.extend(['-i', input_file])  # Input audio
                    cmd.extend(['-map', '0:v:0'])
                    cmd.extend(['-map', '1:a:0'])
                    cmd.extend(['-shortest'])  # End when audio ends
                    
                    self.log(f"[DEBUG] Final conversion command: {' '.join(cmd)}")
                    
                    # Clean up temp file after conversion
                    def cleanup_temp():
                        try:
                            if os.path.exists(temp_video):
                                os.remove(temp_video)
                        except:
                            pass
                    
                    # Schedule cleanup after conversion
                    import threading
                    threading.Timer(5.0, cleanup_temp).start()
                    
                except Exception as e:
                    raise Exception(f"Forward-reverse temp video creation failed: {str(e)}")
            else:
                # Forward only loop - video is already looping via stream_loop
                cmd.extend(['-vf', scale_filter])
                cmd.extend(['-map', '0:v:0'])
                cmd.extend(['-map', '1:a:0'])
            
            # Audio settings
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            
            # Video codec
            cmd.extend(['-c:v', video_codec])
            
            # Video quality (CRF)
            crf_value = self._get_crf_value(video_bitrate, video_codec)
            if video_codec == 'libx264':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-preset', 'medium'])  # Balance between speed and compression
            elif video_codec == 'libx265':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-preset', 'medium'])
            elif video_codec == 'libvpx-vp9':
                cmd.extend(['-crf', str(crf_value)])
                cmd.extend(['-b:v', '0'])  # VP9 requires -b:v 0 when using CRF
            
            # Duration (match audio length)
            cmd.extend(['-shortest'])
        
        # Output file
        cmd.append(output_file)
        
        return cmd
    
    def convert_all_files(self):
        """Convert all MP3 files in the converted folder."""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        converted_folder = self.file_manager.get_folder_path('converted')
        if not os.path.exists(converted_folder):
            messagebox.showerror("Error", "Converted folder does not exist")
            return
        
        # Find all MP3 files in converted folder
        audio_extensions = ['.mp3', '.m4a', '.wav', '.ogg', '.flac']
        all_files = []
        
        for file in os.listdir(converted_folder):
            file_path = os.path.join(converted_folder, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in audio_extensions:
                    all_files.append(file_path)
        
        if not all_files:
            messagebox.showwarning("Warning", "No audio files found in converted folder")
            return
        
        # Update the selected files list
        self.selected_mp3_files = all_files
        self.update_mp3_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} audio files in converted folder")
        
        # Start conversion with all files
        self.start_conversion()
    
    def log(self, message):
        """Log a message."""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def save_settings(self, *args):
        """Save current settings to file."""
        try:
            settings = {
                'output_folder': self.output_folder_var.get(),
                'video_quality': self.video_quality_var.get(),
                'video_codec': self.video_codec_var.get(),
                'video_bitrate': self.video_bitrate_var.get(),
                'scaling_mode': self.scaling_mode_var.get(),
                'video_source_type': self.video_source_type.get(),
                'loop_mode': self.loop_mode.get(),
                'selected_image_file': self.selected_image_file,
                'selected_video_file': self.selected_video_file,
                'image_width': self.image_width,
                'image_height': self.image_height,
                'video_width': self.video_width,
                'video_height': self.video_height
            }
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            # Don't show error to user, just log it
            print(f"[WARNING] Failed to save settings: {e}")
    
    def load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # Restore UI settings
                if 'output_folder' in settings:
                    self.output_folder_var.set(settings['output_folder'])
                    self.file_manager.set_folder_path('output', settings['output_folder'])
                
                if 'video_quality' in settings:
                    quality = settings['video_quality']
                    # Migrate old option names to "Source Size"
                    if quality in ("Image Size", "Input Video Size"):
                        quality = "Source Size"
                    self.video_quality_var.set(quality)
                
                if 'video_codec' in settings:
                    self.video_codec_var.set(settings['video_codec'])
                
                if 'video_bitrate' in settings:
                    self.video_bitrate_var.set(settings['video_bitrate'])
                
                if 'scaling_mode' in settings:
                    self.scaling_mode_var.set(settings['scaling_mode'])
                
                if 'video_source_type' in settings:
                    self.video_source_type.set(settings['video_source_type'])
                
                if 'loop_mode' in settings:
                    self.loop_mode.set(settings['loop_mode'])
                
                # Restore file selections
                if 'selected_image_file' in settings and settings['selected_image_file']:
                    if os.path.exists(settings['selected_image_file']):
                        self.selected_image_file = settings['selected_image_file']
                        filename = os.path.basename(self.selected_image_file)
                        self.lbl_image_status.config(text=f"Selected: {filename}")
                        
                        # Restore image dimensions
                        if 'image_width' in settings and 'image_height' in settings:
                            self.image_width = settings['image_width']
                            self.image_height = settings['image_height']
                            self.image_dimensions_label.config(text=f"({self.image_width}x{self.image_height})")
                
                if 'selected_video_file' in settings and settings['selected_video_file']:
                    if os.path.exists(settings['selected_video_file']):
                        self.selected_video_file = settings['selected_video_file']
                        filename = os.path.basename(self.selected_video_file)
                        self.lbl_video_status.config(text=f"Selected: {filename}")
                        
                        # Restore video dimensions or try to get them
                        if 'video_width' in settings and 'video_height' in settings:
                            self.video_width = settings['video_width']
                            self.video_height = settings['video_height']
                            if self.video_width and self.video_height:
                                self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})")
                        else:
                            # Try to get dimensions if not saved
                            self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
                            if self.video_width and self.video_height:
                                self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})")
                
                # Update UI state
                self.on_source_type_change()
                
                self.log("[INFO] Settings loaded from previous session")
                
        except Exception as e:
            # Don't show error to user, just log it
            print(f"[WARNING] Failed to load settings: {e}")
    
    def on_closing(self):
        """Handle application closing."""
        self.save_settings()
        self.root.destroy()


def main():
    root = TkinterDnD.Tk()
    app = MP3ToVideoConverterGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()


if __name__ == '__main__':
    main()
