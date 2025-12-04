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
import random
import hashlib
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
        
        # Transition settings
        self.transition_enabled = False
        self.transition_type = "fade"  # Legacy single type (for backward compatibility)
        self.selected_transition_types = ["fade"]  # List of selected transition types for randomization
        self.transition_duration = 0.5  # Duration in seconds
        self.transition_types = [
            ("Fade", "fade"),
            ("Wipe Left", "wipeleft"),
            ("Wipe Right", "wiperight"),
            ("Wipe Up", "wipeup"),
            ("Wipe Down", "wipedown"),
            ("Slide Left", "slideleft"),
            ("Slide Right", "slideright"),
            ("Slide Up", "slideup"),
            ("Slide Down", "slidedown"),
            ("Circle Crop", "circlecrop"),
            ("Distance", "distance"),
            ("Fade Black", "fadeblack"),
            ("Fade White", "fadewhite"),
            ("Radial", "radial"),
            ("Dissolve", "dissolve"),
            ("Pixelize", "pixelize"),
        ]
        
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
        self.video_quality_var = tk.StringVar(value="Auto (720p default)")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.video_quality_var, width=20, state='readonly')
        quality_combo['values'] = (
            'Auto (720p default)',
            '480p (854x480)',
            '720p HD (1280x720)',
            '1080p Full HD (1920x1080)',
            'Mobile Portrait 9:16 (720x1280)',
            'Mobile Landscape 16:9 (1280x720)',
            'Instagram Square 1:1 (1080x1080)',
            'Instagram Story 9:16 (1080x1920)',
            'Portrait 2:3 (720x1080)',
            'Landscape 3:2 (1080x720)',
            'Source Size (Match Input)'
        )
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
        self.video_bitrate_var = tk.StringVar(value="Medium Quality (CRF 23)")
        bitrate_combo = ttk.Combobox(settings_frame, textvariable=self.video_bitrate_var, width=20, state='readonly')
        bitrate_combo['values'] = (
            'Very High Quality (CRF 15)',
            'High Quality (CRF 18)',
            'Medium Quality (CRF 23)',
            'Low Quality (CRF 28)',
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
        
        # Transition Settings (only shown when multiple files selected)
        self.transition_frame = ttk.LabelFrame(main_frame, text="Transition Settings", padding=10)
        self.transition_frame.pack(fill='x', pady=(0, 10))
        
        transition_controls = ttk.Frame(self.transition_frame)
        transition_controls.pack(fill='x')
        
        ttk.Label(transition_controls, text="Transitions:").pack(side='left', padx=5)
        self.transition_enabled_var = tk.BooleanVar(value=self.transition_enabled)
        ttk.Checkbutton(transition_controls, text="Enable", variable=self.transition_enabled_var,
                        command=self.toggle_transitions).pack(side='left', padx=2)
        
        ttk.Button(transition_controls, text="Select Types...", command=self.select_transition_types,
                  width=12).pack(side='left', padx=2)
        
        # Label showing selected count
        self.transition_selection_label = ttk.Label(transition_controls, text="(1 selected)", 
                                                     font=('Arial', 8))
        self.transition_selection_label.pack(side='left', padx=2)
        
        ttk.Label(transition_controls, text="Duration:").pack(side='left', padx=(5, 2))
        self.transition_duration_var = tk.StringVar(value=str(self.transition_duration))
        duration_spin = ttk.Spinbox(transition_controls, from_=0.1, to=5.0, increment=0.1,
                                    textvariable=self.transition_duration_var, width=6)
        duration_spin.pack(side='left', padx=2)
        duration_spin.bind('<Return>', lambda e: self.update_transition_duration())
        duration_spin.bind('<FocusOut>', lambda e: self.update_transition_duration())
        
        # Conversion Controls
        convert_frame = ttk.Frame(main_frame)
        convert_frame.pack(fill='x', pady=(0, 10))
        
        batch_frame = ttk.Frame(convert_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Convert Selected Files", command=self.start_conversion).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Convert All Files", command=self.convert_all_files).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Convert & Merge with Transitions", command=self.convert_and_merge).pack(side='left', padx=5)
        
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
        if hasattr(self, 'transition_enabled_var'):
            self.transition_enabled_var.trace('w', lambda *args: self.save_settings())
        
        # Update transition label after UI is created
        if hasattr(self, 'transition_selection_label'):
            self.update_transition_selection_label()

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
        self.video_quality_var.set("Auto (720p default)")
        self.log("[INFO] Image selection cleared")
    
    def _get_video_resolution(self, video_file):
        """Get video resolution (width, height) from video file using multiple methods."""
        if not video_file or not os.path.exists(video_file):
            return None, None
        
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            if not ffmpeg_cmd:
                return None, None
            
            # Method 1: Try ffprobe if available (more reliable)
            ffprobe_cmd = ffmpeg_cmd.replace('ffmpeg', 'ffprobe')
            if os.path.exists(ffprobe_cmd):
                try:
                    probe_cmd = [ffprobe_cmd, '-v', 'error', '-select_streams', 'v:0',
                                '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_file]
                    probe_result = subprocess.run(
                        probe_cmd,
                        capture_output=True,
                        timeout=5
                    )
                    
                    if probe_result.returncode == 0:
                        try:
                            output = probe_result.stdout.decode('utf-8', errors='replace').strip()
                            if output and 'x' in output:
                                parts = output.split('x')
                                if len(parts) == 2:
                                    w, h = int(parts[0].strip()), int(parts[1].strip())
                                    if w > 0 and h > 0:
                                        return w, h
                        except:
                            pass
                except:
                    pass
            
            # Method 2: Use FFmpeg probe (fallback)
            probe_cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            probe_result = subprocess.run(
                probe_cmd, 
                capture_output=True, 
                timeout=10
            )
            
            # Decode stderr with error handling
            try:
                stderr_text = probe_result.stderr.decode('utf-8', errors='replace')
            except:
                try:
                    stderr_text = probe_result.stderr.decode('cp1252', errors='replace')
                except:
                    stderr_text = ''
            
            # Try multiple patterns to find resolution
            patterns = [
                r'Video:.*?(\d{3,5})x(\d{3,5})',  # Standard pattern
                r'(\d{3,5})\s*x\s*(\d{3,5})',     # Generic WxH pattern
                r'Stream.*?Video:.*?(\d{3,5})x(\d{3,5})',  # Stream pattern
            ]
            
            import re
            for pattern in patterns:
                matches = re.findall(pattern, stderr_text)
                if matches:
                    try:
                        w, h = int(matches[0][0]), int(matches[0][1])
                        if w > 0 and h > 0:
                            return w, h
                    except:
                        continue
            
            # Fallback: parse line by line
            for line in stderr_text.split('\n'):
                if 'Video:' in line and 'x' in line:
                    try:
                        parts = line.split('Video:')[1].split(',')
                        for part in parts:
                            if 'x' in part:
                                res_part = part.strip().split()[0]
                                # More flexible parsing
                                if 'x' in res_part:
                                    w_h = res_part.split('x')
                                    if len(w_h) == 2:
                                        w = w_h[0].strip()
                                        h = w_h[1].strip()
                                        # Remove any non-digit characters
                                        w = ''.join(filter(str.isdigit, w))
                                        h = ''.join(filter(str.isdigit, h))
                                        if w and h:
                                            w, h = int(w), int(h)
                                            if w > 0 and h > 0:
                                                return w, h
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
        self.video_quality_var.set("Auto (720p default)")
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
        
        # Sync transition state from checkbox
        if hasattr(self, 'transition_enabled_var'):
            self.transition_enabled = self.transition_enabled_var.get()
        
        self.file_manager.set_folder_path('output', self.output_folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('output'))
        
        self.conversion_queue = self.selected_mp3_files.copy()
        
        self.log(f"[INFO] Starting conversion of {len(self.conversion_queue)} file(s)")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('output')}")
        self.log(f"[INFO] Video source: {source_type}")
        self.log(f"[INFO] Transitions: {'enabled' if self.transition_enabled else 'disabled'}")
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
        # Sync transition state from checkbox
        if hasattr(self, 'transition_enabled_var'):
            self.transition_enabled = self.transition_enabled_var.get()
        
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
            if video_quality == "480p (854x480)" or video_quality == "480p":
                scale_filter = self._get_scaling_filter(854, 480, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "720p HD (1280x720)" or video_quality == "720p":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "1080p Full HD (1920x1080)" or video_quality == "1080p":
                scale_filter = self._get_scaling_filter(1920, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Mobile Portrait 9:16 (720x1280)" or "Mobile Portrait" in video_quality:
                scale_filter = self._get_scaling_filter(720, 1280, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Mobile Landscape 16:9 (1280x720)" or "Mobile Landscape" in video_quality:
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Instagram Square 1:1 (1080x1080)" or "Instagram Square" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Instagram Story 9:16 (1080x1920)" or "Instagram Story" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 1920, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Portrait 2:3 (720x1080)" or "Portrait 2:3" in video_quality:
                scale_filter = self._get_scaling_filter(720, 1080, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Landscape 3:2 (1080x720)" or "Landscape 3:2" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 720, scaling_mode)
                cmd.extend(['-vf', scale_filter])
            elif video_quality == "Source Size (Match Input)" or video_quality == "Source Size":
                # Use source dimensions (image for image source) - detect if not already detected
                if not (self.image_width and self.image_height) and self.selected_image_file:
                    # Try to detect dimensions on-the-fly
                    try:
                        with Image.open(self.selected_image_file) as img:
                            self.image_width, self.image_height = img.size
                    except:
                        pass
                
                if self.image_width and self.image_height:
                    scale_filter = self._get_scaling_filter(self.image_width, self.image_height, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
                else:
                    # Fallback to 720p if dimensions not available
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
                    cmd.extend(['-vf', scale_filter])
            elif video_quality == "Auto (720p default)" or video_quality == "Auto":
                # Auto mode: use source dimensions if available, otherwise default to 720p
                if not (self.image_width and self.image_height) and self.selected_image_file:
                    # Try to detect dimensions on-the-fly
                    try:
                        with Image.open(self.selected_image_file) as img:
                            self.image_width, self.image_height = img.size
                    except:
                        pass
                
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
            
            # Get scaling filter for the selected quality
            if video_quality == "480p (854x480)" or video_quality == "480p":
                scale_filter = self._get_scaling_filter(854, 480, scaling_mode)
            elif video_quality == "720p HD (1280x720)" or video_quality == "720p":
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "1080p Full HD (1920x1080)" or video_quality == "1080p":
                scale_filter = self._get_scaling_filter(1920, 1080, scaling_mode)
            elif video_quality == "Mobile Portrait 9:16 (720x1280)" or "Mobile Portrait" in video_quality:
                scale_filter = self._get_scaling_filter(720, 1280, scaling_mode)
            elif video_quality == "Mobile Landscape 16:9 (1280x720)" or "Mobile Landscape" in video_quality:
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "Instagram Square 1:1 (1080x1080)" or "Instagram Square" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 1080, scaling_mode)
            elif video_quality == "Instagram Story 9:16 (1080x1920)" or "Instagram Story" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 1920, scaling_mode)
            elif video_quality == "Portrait 2:3 (720x1080)" or "Portrait 2:3" in video_quality:
                scale_filter = self._get_scaling_filter(720, 1080, scaling_mode)
            elif video_quality == "Landscape 3:2 (1080x720)" or "Landscape 3:2" in video_quality:
                scale_filter = self._get_scaling_filter(1080, 720, scaling_mode)
            elif video_quality == "Source Size (Match Input)" or video_quality == "Source Size":
                if not (self.video_width and self.video_height) and self.selected_video_file:
                    self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
                    if self.video_width and self.video_height:
                        self.root.after(0, lambda: self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})"))
                
                if self.video_width and self.video_height:
                    scale_filter = self._get_scaling_filter(self.video_width, self.video_height, scaling_mode)
                else:
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            elif video_quality == "Auto (720p default)" or video_quality == "Auto":
                if not (self.video_width and self.video_height) and self.selected_video_file:
                    self.video_width, self.video_height = self._get_video_resolution(self.selected_video_file)
                    if self.video_width and self.video_height:
                        self.root.after(0, lambda: self.image_dimensions_label.config(text=f"({self.video_width}x{self.video_height})"))
                
                if self.video_width and self.video_height:
                    scale_filter = self._get_scaling_filter(self.video_width, self.video_height, scaling_mode)
                else:
                    scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            else:
                scale_filter = self._get_scaling_filter(1280, 720, scaling_mode)
            
            # Check if transitions are enabled for looping video
            if self.transition_enabled and loop_mode != "forward_reverse":
                # Build looped video with transitions between each loop
                return self._build_looped_video_with_transitions_command(
                    input_file, output_file, scale_filter, video_codec, video_bitrate
                )
            
            # Standard approach without transitions
            cmd.extend(['-stream_loop', '-1', '-i', self.selected_video_file])
            cmd.extend(['-i', input_file])
            
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
    
    def convert_and_merge(self):
        """Convert MP3s to videos and merge them with transitions."""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        if not self.selected_mp3_files:
            messagebox.showwarning("Warning", "Please select at least one MP3 file")
            return
        
        # Allow single file with transitions (will create repeating segments with transitions)
        
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
        
        # Sync transition state from checkbox
        if hasattr(self, 'transition_enabled_var'):
            self.transition_enabled = self.transition_enabled_var.get()
        
        self.file_manager.set_folder_path('output', self.output_folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('output'))
        
        self.log(f"[INFO] Starting conversion and merge of {len(self.selected_mp3_files)} file(s)")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('output')}")
        self.log(f"[INFO] Transitions: {'enabled' if self.transition_enabled else 'disabled'}")
        
        self.progress['maximum'] = len(self.selected_mp3_files) + 1  # +1 for merge step
        self.progress['value'] = 0
        
        self.set_busy(True, "Converting and merging...")
        
        thread = threading.Thread(target=self._convert_and_merge_thread)
        thread.daemon = True
        thread.start()
    
    def _convert_and_merge_thread(self):
        """Convert MP3s to videos and merge with transitions."""
        # Sync transition state from checkbox (in case it changed)
        if hasattr(self, 'transition_enabled_var'):
            self.transition_enabled = self.transition_enabled_var.get()
        
        # Step 1: Convert all MP3s to individual videos
        converted_videos = []
        source_type = self.video_source_type.get()
        loop_mode = self.loop_mode.get()
        video_quality = self.video_quality_var.get()
        video_codec = self.video_codec_var.get()
        video_bitrate = self.video_bitrate_var.get()
        scaling_mode = self.scaling_mode_var.get()
        
        for i, input_file in enumerate(self.selected_mp3_files):
            input_path = Path(input_file)
            output_file = os.path.join(
                self.file_manager.get_folder_path('output'), 
                f"{input_path.stem}_video.mp4"
            )
            
            self.root.after(
                0,
                lambda idx=i+1, total=len(self.selected_mp3_files), name=input_path.name:
                self.set_busy(True, f"Converting {idx}/{total}: {name}")
            )
            
            self.root.after(
                0,
                lambda msg=f"\n[INFO] Converting ({i+1}/{len(self.selected_mp3_files)}): {input_path.name}":
                self.log(msg)
            )
            
            try:
                cmd = self._build_conversion_command(
                    input_file, output_file, source_type, loop_mode, video_quality, video_codec, video_bitrate, scaling_mode
                )
                
                process = self.run_ffmpeg_command(cmd)
                
                if process.returncode == 0:
                    converted_videos.append(output_file)
                    self.root.after(
                        0,
                        lambda out=output_file:
                        self.log(f"[SUCCESS] Converted: {os.path.basename(out)}")
                    )
                else:
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg:
                        self.log(f"[ERROR] Conversion failed: {err[:500]}")
                    )
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Exception: {msg}")
                )
            
            self.root.after(0, lambda v=i+1: self.progress.config(value=v))
        
        # Step 2: Merge videos with transitions if enabled
        self.root.after(0, lambda: self.log(f"[DEBUG] Transition enabled state: {self.transition_enabled}"))
        self.root.after(0, lambda: self.log(f"[DEBUG] Number of converted videos: {len(converted_videos)}"))
        
        if len(converted_videos) >= 1 and self.transition_enabled:
            # For single video, duplicate it to create transitions between repeats
            if len(converted_videos) == 1:
                # Create 2 additional copies for transitions (total 3 segments)
                original_video = converted_videos[0]
                video_files_for_transitions = [original_video, original_video, original_video]
                self.root.after(0, lambda: self.log(f"\n[INFO] Creating transitions with repeating video (3 segments)"))
            else:
                video_files_for_transitions = converted_videos
                self.root.after(0, lambda: self.log(f"\n[INFO] Merging {len(converted_videos)} videos with transitions"))
            
            self.root.after(0, lambda: self.set_busy(True, "Merging videos..."))
            
            merged_output = os.path.join(
                self.file_manager.get_folder_path('output'),
                "merged_video.mp4"
            )
            
            try:
                self._merge_videos_with_transitions(video_files_for_transitions, merged_output)
                self.root.after(0, lambda: self.progress.config(value=len(self.selected_mp3_files) + 1))
                self.root.after(
                    0,
                    lambda:
                    self.log(f"[SUCCESS] Merged video saved: {os.path.basename(merged_output)}")
                )
            except Exception as e:
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Merge failed: {msg}")
                )
        elif len(converted_videos) >= 2:
            # Merge without transitions (simple concat)
            self.root.after(0, lambda: self.log(f"\n[INFO] Merging {len(converted_videos)} videos (no transitions)"))
            merged_output = os.path.join(
                self.file_manager.get_folder_path('output'),
                "merged_video.mp4"
            )
            try:
                self._merge_videos_simple(converted_videos, merged_output)
                self.root.after(0, lambda: self.progress.config(value=len(self.selected_mp3_files) + 1))
                self.root.after(
                    0,
                    lambda:
                    self.log(f"[SUCCESS] Merged video saved: {os.path.basename(merged_output)}")
                )
            except Exception as e:
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Merge failed: {msg}")
                )
        
        self.root.after(
            0,
            lambda s=len(converted_videos):
            self.log(f"\n[COMPLETE] Conversion finished: {s} video(s) created")
        )
        
        self.root.after(
            0,
            lambda s=len(converted_videos):
            messagebox.showinfo(
                "Conversion Complete",
                f"Conversion finished!\n\nCreated: {s} video(s)"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False))
    
    def log(self, message):
        """Log a message."""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def _get_audio_duration(self, audio_file):
        """Get audio duration in seconds."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            cmd = [ffmpeg_cmd, '-i', audio_file, '-f', 'null', '-']
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    parts = line.split('Duration:')[1].split(',')[0].strip()
                    time_parts = parts.split(':')
                    if len(time_parts) == 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        sec_ms = time_parts[2].split('.')
                        seconds = int(sec_ms[0])
                        ms = int(sec_ms[1]) if len(sec_ms) > 1 else 0
                        return hours * 3600 + minutes * 60 + seconds + ms / 100.0
            return None
        except Exception as e:
            return None
    
    def _build_looped_video_with_transitions_command(self, audio_file, output_file, scale_filter, video_codec, video_bitrate):
        """Build FFmpeg command for looped video with transitions between each loop."""
        ffmpeg_cmd = self.get_ffmpeg_command()
        
        # Get durations
        audio_duration = self._get_audio_duration(audio_file)
        video_duration = self._get_video_duration(self.selected_video_file)
        
        if not audio_duration or not video_duration:
            self.log(f"[WARNING] Could not get durations, falling back to simple loop")
            return self._build_simple_loop_command(audio_file, output_file, scale_filter, video_codec, video_bitrate)
        
        # Calculate number of loops needed
        transition_dur = self.transition_duration
        # Account for transition overlap when calculating loops
        effective_video_duration = video_duration - transition_dur
        if effective_video_duration <= 0:
            effective_video_duration = video_duration
        
        num_loops = int((audio_duration / effective_video_duration) + 1)
        num_loops = max(2, min(num_loops, 20))  # At least 2, max 20 loops
        
        self.log(f"[INFO] Building looped video with transitions: {num_loops} loops, {transition_dur}s transitions")
        self.log(f"[INFO] Audio duration: {audio_duration:.1f}s, Video duration: {video_duration:.1f}s")
        
        # Randomly select transition types for each loop
        selected_transitions = []
        for i in range(num_loops - 1):
            transition_type = random.choice(self.selected_transition_types)
            selected_transitions.append(transition_type)
        
        # Log selected transitions
        transition_names = []
        for trans_type in selected_transitions:
            for name, value in self.transition_types:
                if value == trans_type:
                    transition_names.append(name)
                    break
        self.log(f"[INFO] Transitions: {', '.join(transition_names)}")
        
        # Build filter graph
        filter_parts = []
        
        # Create scaled copies for each loop using split
        filter_parts.append(f"[0:v]{scale_filter},split={num_loops}" + "".join([f"[v{i}]" for i in range(num_loops)]))
        
        # Calculate xfade offsets
        xfade_offsets = []
        xfade_output_durations = []
        
        for i in range(num_loops - 1):
            if i == 0:
                offset = max(0.1, video_duration - transition_dur)
                output_dur = offset + video_duration
            else:
                prev_output_dur = xfade_output_durations[i-1]
                offset = max(0.1, prev_output_dur - transition_dur)
                output_dur = offset + video_duration
            
            xfade_offsets.append(offset)
            xfade_output_durations.append(output_dur)
        
        # Build xfade chain
        if num_loops == 2:
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[vout]")
        else:
            # Chain multiple xfade filters
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[v01]")
            
            for i in range(2, num_loops):
                prev_label = f"v{i-2}{i-1}" if i > 2 else "v01"
                if i == num_loops - 1:
                    curr_label = "vout"
                else:
                    curr_label = f"v{i-1}{i}"
                
                offset = xfade_offsets[i-1]
                filter_parts.append(f"[{prev_label}][v{i}]xfade=transition={selected_transitions[i-1]}:duration={transition_dur}:offset={offset}[{curr_label}]")
        
        filter_complex = ";".join(filter_parts)
        
        # Build command
        cmd = [ffmpeg_cmd, '-y']
        cmd.extend(['-i', self.selected_video_file])
        cmd.extend(['-i', audio_file])
        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', '[vout]'])
        cmd.extend(['-map', '1:a:0'])
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
        cmd.extend(['-c:v', video_codec])
        
        crf_value = self._get_crf_value(video_bitrate, video_codec)
        if video_codec == 'libx264':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-preset', 'medium'])
        elif video_codec == 'libx265':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-preset', 'medium'])
        elif video_codec == 'libvpx-vp9':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-b:v', '0'])
        
        cmd.extend(['-t', str(audio_duration)])  # Match audio duration
        cmd.append(output_file)
        
        return cmd
    
    def _build_simple_loop_command(self, audio_file, output_file, scale_filter, video_codec, video_bitrate):
        """Build simple loop command without transitions (fallback)."""
        ffmpeg_cmd = self.get_ffmpeg_command()
        
        cmd = [ffmpeg_cmd, '-y']
        cmd.extend(['-stream_loop', '-1', '-i', self.selected_video_file])
        cmd.extend(['-i', audio_file])
        cmd.extend(['-vf', scale_filter])
        cmd.extend(['-map', '0:v:0'])
        cmd.extend(['-map', '1:a:0'])
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
        cmd.extend(['-c:v', video_codec])
        
        crf_value = self._get_crf_value(video_bitrate, video_codec)
        if video_codec == 'libx264':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-preset', 'medium'])
        elif video_codec == 'libx265':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-preset', 'medium'])
        elif video_codec == 'libvpx-vp9':
            cmd.extend(['-crf', str(crf_value)])
            cmd.extend(['-b:v', '0'])
        
        cmd.extend(['-shortest'])
        cmd.append(output_file)
        
        return cmd
    
    def _get_video_duration(self, video_file):
        """Get video duration in seconds."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    parts = line.split('Duration:')[1].split(',')[0].strip()
                    # Parse HH:MM:SS.ms
                    time_parts = parts.split(':')
                    if len(time_parts) == 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        sec_ms = time_parts[2].split('.')
                        seconds = int(sec_ms[0])
                        ms = int(sec_ms[1]) if len(sec_ms) > 1 else 0
                        return hours * 3600 + minutes * 60 + seconds + ms / 100.0
            return None
        except Exception as e:
            self.log(f"[WARNING] Could not get duration for {os.path.basename(video_file)}: {e}")
            return None
    
    def _get_output_resolution_for_transitions(self, video_files):
        """Get output resolution for transitions - use first video's resolution."""
        if video_files:
            width, height = self._get_video_resolution(video_files[0])
            if width and height:
                return width, height
        
        # Default fallback
        return 1920, 1080
    
    def _build_transition_filter(self, video_files):
        """Build FFmpeg filter graph for transitions between videos."""
        if not self.transition_enabled:
            return None
        
        # Allow single video (will be duplicated in merge function)
        if len(video_files) < 1:
            return None
        
        # Ensure we have at least one transition type selected
        if not self.selected_transition_types:
            self.selected_transition_types = ["fade"]  # Default fallback
        
        # Get video durations for calculating offsets
        durations = []
        for vf in video_files:
            dur = self._get_video_duration(vf)
            if dur is None:
                dur = 5.0  # Default fallback
            durations.append(dur)
        
        # Get target resolution (from first video)
        width, height = self._get_output_resolution_for_transitions(video_files)
        
        filter_parts = []
        transition_dur = self.transition_duration
        
        # Scale and normalize all video inputs
        for i in range(len(video_files)):
            filter_parts.append(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
            filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
        
        # Calculate xfade offsets for chained transitions
        xfade_offsets = []
        xfade_output_durations = []
        
        for i in range(len(video_files) - 1):
            if i == 0:
                offset = max(0.1, durations[0] - transition_dur)
                output_dur = offset + durations[1]
            else:
                prev_output_dur = xfade_output_durations[i-1]
                offset = max(0.1, prev_output_dur - transition_dur)
                output_dur = offset + durations[i+1]
            
            xfade_offsets.append(offset)
            xfade_output_durations.append(output_dur)
        
        # Randomly select transition types for each transition
        selected_transitions = []
        for i in range(len(video_files) - 1):
            transition_type = random.choice(self.selected_transition_types)
            selected_transitions.append(transition_type)
        
        # Log selected transitions
        transition_names = []
        for trans_type in selected_transitions:
            for name, value in self.transition_types:
                if value == trans_type:
                    transition_names.append(name)
                    break
        self.root.after(0, lambda names=', '.join(transition_names): 
                      self.log(f"[INFO] Random transitions selected: {names}"))
        
        # Build xfade chain
        if len(video_files) == 2:
            # Simple two-video case
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[vout]")
            filter_parts.append(f"[a0][a1]acrossfade=d={transition_dur}[aout]")
        else:
            # Chain multiple xfade filters
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[v01]")
            filter_parts.append(f"[a0][a1]acrossfade=d={transition_dur}[a01]")
            
            # Chain remaining videos
            for i in range(2, len(video_files)):
                prev_label = f"v{i-2}{i-1}" if i > 2 else "v01"
                prev_audio = f"a{i-2}{i-1}" if i > 2 else "a01"
                curr_label = f"v{i-1}{i}"
                curr_audio = f"a{i-1}{i}"
                
                offset = xfade_offsets[i-1]
                filter_parts.append(f"[{prev_label}][v{i}]xfade=transition={selected_transitions[i-1]}:duration={transition_dur}:offset={offset}[{curr_label}]")
                filter_parts.append(f"[{prev_audio}][a{i}]acrossfade=d={transition_dur}[{curr_audio}]")
            
            # Final output labels
            final_v = f"v{len(video_files)-2}{len(video_files)-1}"
            final_a = f"a{len(video_files)-2}{len(video_files)-1}"
            filter_parts.append(f"[{final_v}]null[vout]")
            filter_parts.append(f"[{final_a}]anull[aout]")
        
        filter_complex = ";".join(filter_parts)
        return filter_complex
    
    def _build_looped_transition_filter(self, video_file, video_duration, num_segments=3):
        """Build FFmpeg filter for transitions with a single looping video using multiple inputs."""
        if not self.transition_enabled:
            return None
        
        # Ensure we have at least one transition type selected
        if not self.selected_transition_types:
            self.selected_transition_types = ["fade"]
        
        # Get target resolution
        width, height = self._get_video_resolution(video_file)
        if not width or not height:
            width, height = 1920, 1080
        
        filter_parts = []
        transition_dur = self.transition_duration
        
        # Scale and normalize all inputs (same file passed multiple times)
        for i in range(num_segments):
            filter_parts.append(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
            filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
        
        # Randomly select transition types
        selected_transitions = []
        for i in range(num_segments - 1):
            transition_type = random.choice(self.selected_transition_types)
            selected_transitions.append(transition_type)
        
        # Log selected transitions
        transition_names = []
        for trans_type in selected_transitions:
            for name, value in self.transition_types:
                if value == trans_type:
                    transition_names.append(name)
                    break
        self.root.after(0, lambda names=', '.join(transition_names): 
                      self.log(f"[INFO] Random transitions selected for loop: {names}"))
        
        # Calculate xfade offsets
        xfade_offsets = []
        xfade_output_durations = []
        
        for i in range(num_segments - 1):
            if i == 0:
                offset = max(0.1, video_duration - transition_dur)
                output_dur = offset + video_duration
            else:
                prev_output_dur = xfade_output_durations[i-1]
                offset = max(0.1, prev_output_dur - transition_dur)
                output_dur = offset + video_duration
            
            xfade_offsets.append(offset)
            xfade_output_durations.append(output_dur)
        
        # Build xfade chain for 3 segments
        filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[v01]")
        filter_parts.append(f"[a0][a1]acrossfade=d={transition_dur}[a01]")
        filter_parts.append(f"[v01][v2]xfade=transition={selected_transitions[1]}:duration={transition_dur}:offset={xfade_offsets[1]}[vout]")
        filter_parts.append(f"[a01][a2]acrossfade=d={transition_dur}[aout]")
        
        filter_complex = ";".join(filter_parts)
        return filter_complex
    
    def _write_concat_file_for_batch(self, video_files):
        """Write concat file for a specific batch of videos."""
        concat_file = os.path.join(self.root_dir, f"temp_concat_{hashlib.md5(str(video_files).encode()).hexdigest()[:8]}.txt")
        with open(concat_file, 'w', encoding='utf-8', newline='\n') as f:
            for vf in video_files:
                if not os.path.isfile(vf):
                    continue
                # Escape path for concat demuxer
                posix_path = Path(vf).resolve().as_posix()
                safe_path = posix_path.replace("'", r"'\''")
                f.write(f"file '{safe_path}'\n")
        return concat_file
    
    def _merge_videos_with_transitions(self, video_files, output_file):
        """Merge videos with transitions using FFmpeg filter complex."""
        ffmpeg_cmd = self.get_ffmpeg_command()
        
        # Debug logging
        self.root.after(0, lambda: self.log(f"[DEBUG] _merge_videos_with_transitions called with {len(video_files)} files"))
        self.root.after(0, lambda: self.log(f"[DEBUG] Transition enabled: {self.transition_enabled}"))
        
        # Check if we have a single video that needs looping (all files are the same)
        is_single_video_loop = len(video_files) > 0 and len(set(video_files)) == 1
        self.root.after(0, lambda: self.log(f"[DEBUG] Is single video loop: {is_single_video_loop}"))
        
        if is_single_video_loop:
            # Use multiple inputs of same file to create transitions between repeats
            original_video = video_files[0]
            video_duration = self._get_video_duration(original_video)
            if video_duration is None:
                video_duration = 5.0
            
            # Determine number of segments (use existing count if we have multiple copies, otherwise create 3)
            num_segments = len(video_files) if len(video_files) >= 2 else 3
            
            # Create filter for looped transitions
            filter_complex = self._build_looped_transition_filter(original_video, video_duration, num_segments=num_segments)
            self.root.after(0, lambda: self.log(f"[DEBUG] Looped transition filter built: {filter_complex is not None}"))
            if filter_complex:
                self.root.after(0, lambda: self.log(f"[DEBUG] Using looped transition filter with {num_segments} segments"))
                # Pass the same file multiple times as separate inputs
                input_args = []
                for _ in range(num_segments):
                    input_args.extend(['-i', original_video])
                
                cmd = [ffmpeg_cmd] + input_args + [
                    '-filter_complex', filter_complex,
                    '-map', '[vout]',
                    '-map', '[aout]',
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '18',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-movflags', '+faststart',
                    '-y', output_file
                ]
            else:
                # Fallback: use standard transition filter
                if len(video_files) < 3:
                    video_files = [original_video] * 3
                filter_complex = self._build_transition_filter(video_files)
                if not filter_complex:
                    self._merge_videos_simple([original_video], output_file)
                    return
                
                input_args = []
                for vf in video_files:
                    input_args.extend(['-i', vf])
                
                cmd = [ffmpeg_cmd] + input_args + [
                    '-filter_complex', filter_complex,
                    '-map', '[vout]',
                    '-map', '[aout]',
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '18',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-movflags', '+faststart',
                    '-y', output_file
                ]
        else:
            # Multiple different videos - use standard approach
            filter_complex = self._build_transition_filter(video_files)
            self.root.after(0, lambda: self.log(f"[DEBUG] Standard transition filter built: {filter_complex is not None}"))
            
            if not filter_complex:
                # Fallback to simple merge
                self.root.after(0, lambda: self.log(f"[WARNING] Transition filter is None, falling back to simple merge"))
                self._merge_videos_simple(video_files, output_file)
                return
            
            # Build input arguments
            input_args = []
            for vf in video_files:
                input_args.extend(['-i', vf])
            
            # Build command with filter complex
            cmd = [ffmpeg_cmd] + input_args + [
                '-filter_complex', filter_complex,
                '-map', '[vout]',
                '-map', '[aout]',
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '18',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-movflags', '+faststart',
                '-y', output_file
            ]
        
        self.root.after(0, lambda: self.log(f"[DEBUG] Merge command: {' '.join(cmd)}"))
        self.root.after(0, lambda: self.log(f"[DEBUG] Filter complex: {filter_complex[:200] if filter_complex else 'None'}..."))
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            cwd=self.root_dir
        )
        
        if result.returncode != 0:
            error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
            self.root.after(0, lambda err=error_msg: self.log(f"[ERROR] FFmpeg stderr: {err}"))
            raise Exception(f"Merge failed: {error_msg}")
        else:
            self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg completed successfully"))
            if result.stderr:
                self.root.after(0, lambda err=result.stderr[:500]: self.log(f"[DEBUG] FFmpeg stderr (first 500 chars): {err}"))
    
    def _merge_videos_simple(self, video_files, output_file):
        """Merge videos using simple concat (no transitions)."""
        ffmpeg_cmd = self.get_ffmpeg_command()
        concat_file = self._write_concat_file_for_batch(video_files)
        
        try:
            # Use concat demuxer
            cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', concat_file, 
                  '-c', 'copy', '-y', output_file]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                cwd=self.root_dir
            )
            
            if result.returncode != 0:
                # Retry with re-encode
                reencode_cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', concat_file,
                              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                              '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                              '-y', output_file]
                result = subprocess.run(
                    reencode_cmd, 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8',
                    errors='replace',
                    cwd=self.root_dir
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
                    raise Exception(f"Merge failed: {error_msg}")
        finally:
            # Clean up concat file
            if concat_file and os.path.exists(concat_file):
                try:
                    os.remove(concat_file)
                except:
                    pass
    
    def toggle_transitions(self):
        """Toggle transitions option."""
        self.transition_enabled = self.transition_enabled_var.get()
        self.save_settings()
        status_text = "enabled" if self.transition_enabled else "disabled"
        self.log(f"[INFO] Transitions: {status_text}")
    
    def select_transition_types(self):
        """Open dialog to select multiple transition types."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Transition Types")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Instructions
        info_label = ttk.Label(dialog, 
                              text="Select multiple transition types.\nThey will be randomly applied between clips.",
                              justify='center')
        info_label.pack(pady=10)
        
        # Frame with scrollbar for checkboxes
        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(frame, bg='white')
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create checkboxes for each transition type
        transition_checkbox_vars = {}
        
        for name, value in self.transition_types:
            var = tk.BooleanVar(value=value in self.selected_transition_types)
            transition_checkbox_vars[value] = var
            cb = ttk.Checkbutton(scrollable_frame, text=name, variable=var)
            cb.pack(anchor='w', padx=5, pady=2)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def select_all():
            for var in transition_checkbox_vars.values():
                var.set(True)
        
        def deselect_all():
            for var in transition_checkbox_vars.values():
                var.set(False)
        
        def apply_selection():
            selected = []
            for value, var in transition_checkbox_vars.items():
                if var.get():
                    selected.append(value)
            
            if not selected:
                messagebox.showwarning("Warning", "Please select at least one transition type.")
                return
            
            self.selected_transition_types = selected
            self.transition_type = selected[0]  # Keep first for backward compatibility
            self.update_transition_selection_label()
            self.save_settings()
            self.log(f"[INFO] Selected {len(selected)} transition type(s) for randomization")
            dialog.destroy()
        
        ttk.Button(btn_frame, text="Select All", command=select_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Deselect All", command=deselect_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Apply", command=apply_selection).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def update_transition_selection_label(self):
        """Update the label showing how many transitions are selected."""
        count = len(self.selected_transition_types)
        if count == 0:
            self.transition_selection_label.config(text="(none selected)")
        elif count == 1:
            # Show the name of the single selected transition
            for name, value in self.transition_types:
                if value == self.selected_transition_types[0]:
                    self.transition_selection_label.config(text=f"({name})")
                    break
        else:
            self.transition_selection_label.config(text=f"({count} types - randomized)")
    
    def update_transition_duration(self):
        """Update transition duration."""
        try:
            self.transition_duration = float(self.transition_duration_var.get())
            if self.transition_duration < 0.1:
                self.transition_duration = 0.1
                self.transition_duration_var.set('0.1')
            elif self.transition_duration > 5.0:
                self.transition_duration = 5.0
                self.transition_duration_var.set('5.0')
            self.save_settings()
            self.log(f"[INFO] Transition duration: {self.transition_duration}s")
        except ValueError:
            self.transition_duration_var.set(str(self.transition_duration))
    
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
                'video_height': self.video_height,
                'transition_enabled': self.transition_enabled,
                'transition_type': self.transition_type,  # Legacy single type
                'selected_transition_types': self.selected_transition_types,  # New multi-select
                'transition_duration': self.transition_duration
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
                    # Migrate old option names to new format
                    if quality in ("Image Size", "Input Video Size"):
                        quality = "Source Size (Match Input)"
                    elif quality == "Auto":
                        quality = "Auto (720p default)"
                    elif quality == "480p":
                        quality = "480p (854x480)"
                    elif quality == "720p":
                        quality = "720p HD (1280x720)"
                    elif quality == "1080p":
                        quality = "1080p Full HD (1920x1080)"
                    elif quality == "Source Size":
                        quality = "Source Size (Match Input)"
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
                
                # Load transition settings
                if 'transition_enabled' in settings:
                    self.transition_enabled = settings['transition_enabled']
                    if hasattr(self, 'transition_enabled_var'):
                        self.transition_enabled_var.set(self.transition_enabled)
                
                # Load transition types (new multi-select or legacy single)
                if 'selected_transition_types' in settings:
                    self.selected_transition_types = settings['selected_transition_types']
                    if self.selected_transition_types:
                        self.transition_type = self.selected_transition_types[0]  # Keep first for compatibility
                elif 'transition_type' in settings:
                    # Legacy: convert single type to list
                    self.transition_type = settings['transition_type']
                    if self.transition_type != "none":
                        self.selected_transition_types = [self.transition_type]
                    else:
                        self.selected_transition_types = ["fade"]  # Default
                
                # Update transition label if it exists
                if hasattr(self, 'transition_selection_label'):
                    self.update_transition_selection_label()
                
                if 'transition_duration' in settings:
                    self.transition_duration = settings['transition_duration']
                    if hasattr(self, 'transition_duration_var'):
                        self.transition_duration_var.set(str(self.transition_duration))
                
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
