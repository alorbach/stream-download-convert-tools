"""
Audio Tools - Unified Application

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
import csv
import re
import os
import sys
import threading
import subprocess
import json
from pathlib import Path

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI
from lib.gui_utils import GUIManager, LogManager
from lib.file_utils import FileManager
from lib.process_utils import ProcessManager
from lib.ffmpeg_utils import FFmpegManager


class AudioToolsUnifiedGUI(BaseAudioGUI):
    def __init__(self, root, auto_load_csv=None):
        super().__init__(root, "Audio Tools - Unified")
        self.root.geometry("1000x800")
        
        # YouTube Downloader attributes
        self.csv_file = None
        self.csv_data = []
        self.available_streams = []
        self.current_video_info = None
        
        # Video to MP3 Converter attributes
        self.selected_video_files = []
        self.conversion_queue = []
        
        # Audio Modifier attributes
        self.selected_audio_files = []
        self.modification_queue = []
        
        self.setup_ui()
        
        if auto_load_csv and os.path.isfile(auto_load_csv):
            self.root.after(100, lambda: self.load_csv_file(auto_load_csv))
    
    def setup_ui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create tabs
        self.tab_youtube = ttk.Frame(self.notebook)
        self.tab_converter = ttk.Frame(self.notebook)
        self.tab_modifier = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_youtube, text="YouTube Downloader")
        self.notebook.add(self.tab_converter, text="Video to MP3")
        self.notebook.add(self.tab_modifier, text="Audio Modifier")
        self.notebook.add(self.tab_settings, text="Settings")
        
        self.setup_youtube_tab()
        self.setup_converter_tab()
        self.setup_modifier_tab()
        self.setup_settings_tab()
    
    def setup_youtube_tab(self):
        # YouTube Downloader Tab
        top_frame = ttk.LabelFrame(self.tab_youtube, text="CSV File Selection", padding=10)
        top_frame.pack(fill='x', padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select CSV File", command=self.load_csv).pack(side='left', padx=5)
        self.lbl_csv_status = ttk.Label(btn_frame, text="No file loaded")
        self.lbl_csv_status.pack(side='left', padx=5)
        
        ttk.Label(top_frame, text="CSV Data:").pack(anchor='w', pady=(10, 5))
        
        tree_frame = ttk.Frame(top_frame)
        tree_frame.pack(fill='both', expand=True)
        
        csv_scroll_y = ttk.Scrollbar(tree_frame, orient='vertical')
        csv_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        
        self.csv_tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=csv_scroll_y.set,
            xscrollcommand=csv_scroll_x.set,
            show='tree headings',
            height=8
        )
        
        csv_scroll_y.config(command=self.csv_tree.yview)
        csv_scroll_x.config(command=self.csv_tree.xview)
        
        self.csv_tree.grid(row=0, column=0, sticky='nsew')
        csv_scroll_y.grid(row=0, column=1, sticky='ns')
        csv_scroll_x.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Video selection frame
        video_frame = ttk.LabelFrame(self.tab_youtube, text="Video Selection", padding=10)
        video_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(video_frame, text="Select Video:").pack(anchor='w')
        
        self.video_listbox = tk.Listbox(video_frame, height=6, selectmode=tk.EXTENDED)
        self.video_listbox.pack(fill='both', expand=True, pady=5)
        self.video_listbox.bind('<<ListboxSelect>>', self.on_video_select)
        
        ttk.Button(video_frame, text="Fetch Available Streams", command=self.fetch_streams).pack(pady=5)
        
        self.youtube_progress = ttk.Progressbar(video_frame, mode='indeterminate')
        self.youtube_progress.pack(fill='x', pady=5)
        self.youtube_progress_label = ttk.Label(video_frame, text="")
        self.youtube_progress_label.pack(anchor='w')
        
        # Streams frame
        streams_frame = ttk.LabelFrame(self.tab_youtube, text="Available Streams", padding=10)
        streams_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Format ID', 'Extension', 'Resolution', 'FPS', 'File Size', 'Audio Codec', 'Video Codec')
        self.stream_tree = ttk.Treeview(streams_frame, columns=columns, show='tree headings', height=8)
        
        self.stream_tree.heading('#0', text='Type')
        self.stream_tree.column('#0', width=100)
        
        for col in columns:
            self.stream_tree.heading(col, text=col)
            self.stream_tree.column(col, width=100)
        
        stream_scrollbar = ttk.Scrollbar(streams_frame, orient='vertical', command=self.stream_tree.yview)
        self.stream_tree.configure(yscrollcommand=stream_scrollbar.set)
        
        self.stream_tree.pack(side='left', fill='both', expand=True)
        stream_scrollbar.pack(side='right', fill='y')
        
        # Download frame
        download_frame = ttk.Frame(self.tab_youtube)
        download_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(download_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Download Selected Stream", command=self.download_stream).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Download Selected Videos", command=self.download_selected_videos).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Download All Videos", command=self.download_all_videos).pack(side='left', padx=5)
        
        self.youtube_log_text = scrolledtext.ScrolledText(download_frame, height=6)
        self.youtube_log_text.pack(fill='both', expand=True)
    
    def setup_converter_tab(self):
        # Video to MP3 Converter Tab
        top_frame = ttk.LabelFrame(self.tab_converter, text="File Selection", padding=10)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select Video Files", command=self.select_video_files).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Selection", command=self.clear_video_selection).pack(side='left', padx=5)
        
        self.lbl_video_status = ttk.Label(btn_frame, text="No files selected")
        self.lbl_video_status.pack(side='left', padx=10)
        
        ttk.Label(top_frame, text="Selected Files:").pack(anchor='w', pady=(10, 5))
        
        list_frame = ttk.Frame(top_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar_y = ttk.Scrollbar(list_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(list_frame, orient='horizontal')
        
        self.video_file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=8,
            selectmode=tk.EXTENDED
        )
        
        scrollbar_y.config(command=self.video_file_listbox.yview)
        scrollbar_x.config(command=self.video_file_listbox.xview)
        
        self.video_file_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        settings_frame = ttk.LabelFrame(self.tab_converter, text="Conversion Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.converter_folder_var = tk.StringVar(value=self.file_manager.converted_folder)
        ttk.Entry(settings_frame, textvariable=self.converter_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_converter_folder).grid(row=0, column=2)
        
        ttk.Label(settings_frame, text="Audio Quality:").grid(row=1, column=0, sticky='w', pady=5)
        self.converter_quality_var = tk.StringVar(value="192k")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.converter_quality_var, width=20, state='readonly')
        quality_combo['values'] = ('128k', '192k', '256k', '320k')
        quality_combo.grid(row=1, column=1, sticky='w', padx=5)
        
        convert_frame = ttk.Frame(self.tab_converter)
        convert_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(convert_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Convert Selected Files", command=self.start_conversion).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Convert All Files", command=self.convert_all_files).pack(side='left', padx=5)
        
        self.converter_progress = ttk.Progressbar(convert_frame, mode='determinate')
        self.converter_progress.pack(fill='x', pady=5)
        
        self.converter_progress_label = ttk.Label(convert_frame, text="")
        self.converter_progress_label.pack(anchor='w')
        
        log_frame = ttk.LabelFrame(self.tab_converter, text="Conversion Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.converter_log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.converter_log_text.pack(fill='both', expand=True)
        
        info_frame = ttk.Frame(self.tab_converter)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = "Supported formats: MP4, WEBM, M4A, AVI, MOV, MKV, FLV, WMV | Requires FFmpeg installed"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
    
    def setup_modifier_tab(self):
        # Audio Modifier Tab
        top_frame = ttk.LabelFrame(self.tab_modifier, text="File Selection", padding=10)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select Audio Files", command=self.select_audio_files).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Selection", command=self.clear_audio_selection).pack(side='left', padx=5)
        
        self.lbl_audio_status = ttk.Label(btn_frame, text="No files selected")
        self.lbl_audio_status.pack(side='left', padx=10)
        
        ttk.Label(top_frame, text="Selected Files:").pack(anchor='w', pady=(10, 5))
        
        list_frame = ttk.Frame(top_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar_y = ttk.Scrollbar(list_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(list_frame, orient='horizontal')
        
        self.audio_file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=8,
            selectmode=tk.EXTENDED
        )
        
        scrollbar_y.config(command=self.audio_file_listbox.yview)
        scrollbar_x.config(command=self.audio_file_listbox.xview)
        
        self.audio_file_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        settings_frame = ttk.LabelFrame(self.tab_modifier, text="Modification Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.modifier_folder_var = tk.StringVar(value=self.file_manager.output_folder)
        ttk.Entry(settings_frame, textvariable=self.modifier_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_modifier_folder).grid(row=0, column=2)
        
        ttk.Label(settings_frame, text="Speed Adjustment (%):").grid(row=1, column=0, sticky='w', pady=5)
        speed_frame = ttk.Frame(settings_frame)
        speed_frame.grid(row=1, column=1, sticky='w', padx=5)
        self.speed_var = tk.StringVar(value="0")
        speed_spinbox = ttk.Spinbox(speed_frame, textvariable=self.speed_var, from_=-50, to=100, width=10, increment=5)
        speed_spinbox.pack(side='left')
        ttk.Label(speed_frame, text=" (-50% to +100%, 0 = no change)").pack(side='left', padx=5)
        
        ttk.Label(settings_frame, text="Pitch Adjustment (semitones):").grid(row=2, column=0, sticky='w', pady=5)
        pitch_frame = ttk.Frame(settings_frame)
        pitch_frame.grid(row=2, column=1, sticky='w', padx=5)
        self.pitch_var = tk.StringVar(value="0")
        pitch_spinbox = ttk.Spinbox(pitch_frame, textvariable=self.pitch_var, from_=-12, to=12, width=10, increment=1)
        pitch_spinbox.pack(side='left')
        ttk.Label(pitch_frame, text=" (-12 to +12 semitones, 0 = no change)").pack(side='left', padx=5)
        
        ttk.Label(settings_frame, text="Audio Quality:").grid(row=3, column=0, sticky='w', pady=5)
        self.modifier_quality_var = tk.StringVar(value="192k")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.modifier_quality_var, width=20, state='readonly')
        quality_combo['values'] = ('128k', '192k', '256k', '320k')
        quality_combo.grid(row=3, column=1, sticky='w', padx=5)
        
        preset_frame = ttk.LabelFrame(self.tab_modifier, text="Quick Presets", padding=10)
        preset_frame.pack(fill='x', padx=10, pady=10)
        
        btn_preset_frame = ttk.Frame(preset_frame)
        btn_preset_frame.pack(fill='x')
        
        ttk.Button(btn_preset_frame, text="Slower -10%", command=lambda: self.apply_preset(-10, 0)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Faster +10%", command=lambda: self.apply_preset(10, 0)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Pitch -1", command=lambda: self.apply_preset(0, -1)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Pitch +1", command=lambda: self.apply_preset(0, 1)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Reset", command=lambda: self.apply_preset(0, 0)).pack(side='left', padx=2)
        
        modify_frame = ttk.Frame(self.tab_modifier)
        modify_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(modify_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Modify Selected Files", command=self.start_modification).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Modify All Files", command=self.modify_all_files).pack(side='left', padx=5)
        
        self.modifier_progress = ttk.Progressbar(modify_frame, mode='determinate')
        self.modifier_progress.pack(fill='x', pady=5)
        
        self.modifier_progress_label = ttk.Label(modify_frame, text="")
        self.modifier_progress_label.pack(anchor='w')
        
        log_frame = ttk.LabelFrame(self.tab_modifier, text="Modification Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.modifier_log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.modifier_log_text.pack(fill='both', expand=True)
        
        info_frame = ttk.Frame(self.tab_modifier)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = "Supported formats: MP3, M4A, WAV, OGG, FLAC | Speed: +/- tempo | Pitch: semitones | Requires FFmpeg"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
    
    def setup_settings_tab(self):
        # Settings Tab
        frame = ttk.LabelFrame(self.tab_settings, text="Folder Settings", padding=10)
        frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(frame, text="Download Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.download_folder_var = tk.StringVar(value=self.file_manager.downloads_folder)
        ttk.Entry(frame, textvariable=self.download_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="Browse", command=self.browse_download_folder).grid(row=0, column=2)
        
        ttk.Label(frame, text="Converted Folder:").grid(row=1, column=0, sticky='w', pady=5)
        self.converted_folder_var = tk.StringVar(value=self.file_manager.converted_folder)
        ttk.Entry(frame, textvariable=self.converted_folder_var, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(frame, text="Browse", command=self.browse_converted_folder).grid(row=1, column=2)
        
        ttk.Label(frame, text="Modified Folder:").grid(row=2, column=0, sticky='w', pady=5)
        self.modified_folder_var = tk.StringVar(value=self.file_manager.output_folder)
        ttk.Entry(frame, textvariable=self.modified_folder_var, width=50).grid(row=2, column=1, padx=5)
        ttk.Button(frame, text="Browse", command=self.browse_modified_folder).grid(row=2, column=2)
        
        # CSV subfolder info
        csv_frame = ttk.LabelFrame(self.tab_settings, text="CSV Subfolder", padding=10)
        csv_frame.pack(fill='x', padx=10, pady=10)
        
        self.csv_subfolder_var = tk.StringVar(value="No CSV loaded")
        ttk.Label(csv_frame, text="Current CSV:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Label(csv_frame, textvariable=self.csv_subfolder_var, foreground='blue').grid(row=0, column=1, sticky='w', padx=5)
        
        ttk.Label(csv_frame, text="Files will be saved to subfolders based on CSV filename").grid(
            row=1, column=0, columnspan=2, sticky='w', pady=5
        )
        
        # Filename pattern settings
        pattern_frame = ttk.LabelFrame(self.tab_settings, text="Filename Pattern", padding=10)
        pattern_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(pattern_frame, text="Pattern:").grid(row=0, column=0, sticky='w', pady=5)
        self.filename_var = tk.StringVar(value="{Rank}_{Song Title}_{Artist}")
        ttk.Entry(pattern_frame, textvariable=self.filename_var, width=50).grid(row=0, column=1, pady=5, columnspan=2)
        
        ttk.Label(pattern_frame, text="Available fields: {Rank}, {Song Title}, {Artist}, {Year}, {Views (Billions)}").grid(
            row=1, column=0, columnspan=3, sticky='w', pady=5
        )
        
        info_frame = ttk.LabelFrame(self.tab_settings, text="Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        info_text = """Audio Tools - Unified Application

Features:
- YouTube Downloader: Download videos from CSV lists
- Video to MP3 Converter: Convert video files to MP3
- Audio Modifier: Adjust speed and pitch of audio files
- Automatic venv management via launcher scripts
- Cross-platform support (Windows, Linux, Mac)

Workflow:
1. Use YouTube Downloader to download videos
2. Use Video to MP3 Converter to extract audio
3. Use Audio Modifier to adjust speed/pitch

Note: All tools require FFmpeg for processing.
"""
        info_label = ttk.Label(info_frame, text=info_text, justify='left')
        info_label.pack(anchor='w')
    
    # Common utility methods
    def set_busy(self, busy=True, message="", tab="youtube"):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            if tab == "youtube":
                self.youtube_progress.start(10)
                self.youtube_progress_label.config(text=message)
            elif tab == "converter":
                self.converter_progress_label.config(text=message)
            elif tab == "modifier":
                self.modifier_progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            self.youtube_progress.stop()
            self.youtube_progress_label.config(text="")
            self.converter_progress_label.config(text="")
            self.modifier_progress_label.config(text="")
    
    def log(self, message, tab="youtube"):
        if tab == "youtube":
            self.youtube_log_text.insert(tk.END, f"{message}\n")
            self.youtube_log_text.see(tk.END)
        elif tab == "converter":
            self.converter_log_text.insert(tk.END, f"{message}\n")
            self.converter_log_text.see(tk.END)
        elif tab == "modifier":
            self.modifier_log_text.insert(tk.END, f"{message}\n")
            self.modifier_log_text.see(tk.END)
    
    # YouTube Downloader methods
    def load_csv(self):
        file_path = self.select_files(
            title="Select CSV File",
            filetypes=self.file_manager.get_csv_filetypes(),
            initial_dir=os.path.join(self.root_dir, "input")
        )
        if file_path:
            file_path = file_path[0]  # select_files returns tuple, we need first item
        
        if not file_path:
            return
        
        self.load_csv_file(file_path)
    
    def load_csv_file(self, file_path):
        self.set_busy(True, "Loading CSV file...", "youtube")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.csv_data = list(reader)
            
            self.csv_file = file_path
            self.lbl_csv_status.config(text=f"Loaded: {os.path.basename(file_path)} ({len(self.csv_data)} rows)")
            
            # Set CSV basename for subfolder creation
            self.file_manager.set_csv_basename(file_path)
            
            # Update settings tab display
            if hasattr(self, 'csv_subfolder_var'):
                self.csv_subfolder_var.set(f"{self.file_manager.csv_basename} (subfolder)")
            
            self.display_csv_in_grid()
            self.populate_video_list()
            
            self.notebook.select(self.tab_youtube)
            
            self.log(f"[SUCCESS] Loaded {len(self.csv_data)} videos from CSV: {os.path.basename(file_path)}", "youtube")
            self.log(f"[INFO] Using subfolder: {self.file_manager.csv_basename}", "youtube")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")
            self.log(f"[ERROR] Failed to load CSV: {str(e)}", "youtube")
        finally:
            self.set_busy(False, tab="youtube")
    
    def display_csv_in_grid(self):
        for item in self.csv_tree.get_children():
            self.csv_tree.delete(item)
        
        if not self.csv_data:
            return
        
        columns = list(self.csv_data[0].keys())
        self.csv_tree['columns'] = columns
        
        self.csv_tree.heading('#0', text='#')
        self.csv_tree.column('#0', width=50, anchor='center')
        
        for col in columns:
            self.csv_tree.heading(col, text=col)
            if col == 'Video Link':
                self.csv_tree.column(col, width=300, anchor='w')
            elif col in ['Rank', 'Year']:
                self.csv_tree.column(col, width=60, anchor='center')
            elif col == 'Views (Billions)':
                self.csv_tree.column(col, width=120, anchor='center')
            elif col == 'Song Title':
                self.csv_tree.column(col, width=200, anchor='w')
            elif col == 'Artist':
                self.csv_tree.column(col, width=180, anchor='w')
            else:
                self.csv_tree.column(col, width=100, anchor='w')
        
        for i, row in enumerate(self.csv_data, 1):
            values = [row.get(col, '') for col in columns]
            self.csv_tree.insert('', 'end', text=str(i), values=values)
    
    def populate_video_list(self):
        self.video_listbox.delete(0, tk.END)
        for i, row in enumerate(self.csv_data):
            title = row.get('Song Title', 'Unknown')
            artist = row.get('Artist', 'Unknown')
            rank = row.get('Rank', i+1)
            self.video_listbox.insert(tk.END, f"{rank}. {title} - {artist}")
    
    def extract_youtube_url(self, text):
        if not text:
            return None
        
        self.log(f"[DEBUG] Extracting URL from: {text[:100]}...", "youtube")
        
        # Pattern 1: Markdown format [URL](URL)
        markdown_pattern = r'\[(https://www\.youtube\.com/watch\?v=[\w-]+)\]\(https://www\.youtube\.com/watch\?v=[\w-]+\)'
        match = re.search(markdown_pattern, text)
        if match:
            url = match.group(1)
            self.log(f"[DEBUG] Extracted URL (markdown): {url}", "youtube")
            return url
        
        # Pattern 2: Direct YouTube video URL
        url_pattern = r'https://www\.youtube\.com/watch\?v=[\w-]+'
        match = re.search(url_pattern, text)
        if match:
            url = match.group(0)
            self.log(f"[DEBUG] Extracted URL (direct): {url}", "youtube")
            return url
        
        # Pattern 3: YouTube search URL - extract search query and use it directly
        search_pattern = r'https://www\.youtube\.com/results\?search_query=([^&\s]+)'
        match = re.search(search_pattern, text)
        if match:
            search_query = match.group(1)
            # URL decode the search query
            import urllib.parse
            decoded_query = urllib.parse.unquote_plus(search_query)
            self.log(f"[DEBUG] Extracted search query: {decoded_query}", "youtube")
            self.log(f"[INFO] Using search query as yt-dlp input: {decoded_query}", "youtube")
            return decoded_query
        
        self.log(f"[ERROR] No supported URL pattern found in text", "youtube")
        return None
    
    def on_video_select(self, event):
        selection = self.video_listbox.curselection()
        if selection:
            self.stream_tree.delete(*self.stream_tree.get_children())
            self.log(f"Selected video #{selection[0] + 1}", "youtube")
    
    def fetch_streams(self):
        if self.is_busy:
            return
        
        selection = self.video_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a video first")
            return
        
        index = selection[0]
        row = self.csv_data[index]
        self.current_video_info = row
        
        self.log(f"[DEBUG] Available CSV fields: {list(row.keys())}", "youtube")
        video_link = row.get('Video Link', '')
        self.log(f"[DEBUG] Video Link field value: '{video_link}'", "youtube")
        
        url = self.extract_youtube_url(video_link)
        if not url:
            self.log(f"[ERROR] Could not extract YouTube URL from CSV", "youtube")
            messagebox.showerror("Error", "Could not extract YouTube URL from CSV")
            return
        
        self.log(f"[INFO] Fetching streams for: {url}", "youtube")
        self.set_busy(True, "Fetching available streams...", "youtube")
        
        thread = threading.Thread(target=self._fetch_streams_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def _fetch_streams_thread(self, url):
        try:
            result = subprocess.run(
                ['yt-dlp', '-J', url],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] {msg}", "youtube"))
                self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
                return
            
            data = json.loads(result.stdout)
            formats = data.get('formats', [])
            
            self.available_streams = formats
            self.root.after(0, lambda: self.display_streams(formats))
            self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Fetching streams: {msg}", "youtube"))
            self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
    
    def display_streams(self, formats):
        self.stream_tree.delete(*self.stream_tree.get_children())
        
        combined = []
        video_only = []
        audio_only = []
        
        for fmt in formats:
            if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                combined.append(fmt)
            elif fmt.get('vcodec') != 'none':
                video_only.append(fmt)
            elif fmt.get('acodec') != 'none':
                audio_only.append(fmt)
        
        if combined:
            parent = self.stream_tree.insert('', 'end', text='Video + Audio', open=True)
            for fmt in combined:
                self._insert_format(parent, fmt)
        
        if video_only:
            parent = self.stream_tree.insert('', 'end', text='Video Only', open=False)
            for fmt in video_only:
                self._insert_format(parent, fmt)
        
        if audio_only:
            parent = self.stream_tree.insert('', 'end', text='Audio Only', open=False)
            for fmt in audio_only:
                self._insert_format(parent, fmt)
        
        self.log(f"[SUCCESS] Found {len(formats)} streams ({len(combined)} combined, {len(video_only)} video, {len(audio_only)} audio)", "youtube")
    
    def _insert_format(self, parent, fmt):
        format_id = fmt.get('format_id', 'N/A')
        ext = fmt.get('ext', 'N/A')
        resolution = fmt.get('resolution', 'N/A')
        fps = str(fmt.get('fps', 'N/A'))
        filesize = self._format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))
        acodec = fmt.get('acodec', 'none')
        vcodec = fmt.get('vcodec', 'none')
        
        self.stream_tree.insert(
            parent, 'end',
            values=(format_id, ext, resolution, fps, filesize, acodec, vcodec),
            tags=(format_id,)
        )
    
    def _format_filesize(self, size):
        if not size:
            return 'Unknown'
        size = float(size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def download_stream(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        selection = self.stream_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a stream to download")
            return
        
        if not self.current_video_info:
            messagebox.showerror("Error", "No video selected")
            return
        
        item = selection[0]
        format_id = str(self.stream_tree.item(item)['values'][0])
        
        url = self.extract_youtube_url(self.current_video_info.get('Video Link', ''))
        if not url:
            messagebox.showerror("Error", "Could not extract YouTube URL")
            return
        
        filename_pattern = self.filename_var.get()
        filename = self.create_filename_from_pattern(filename_pattern, self.current_video_info)
        
        self.log(f"[INFO] Starting download: Format {format_id}", "youtube")
        self.log(f"[INFO] Output file: {filename}", "youtube")
        self.set_busy(True, "Downloading...", "youtube")
        
        thread = threading.Thread(target=self._download_thread, args=(url, format_id, filename))
        thread.daemon = True
        thread.start()
    
    
    def _download_thread(self, url, format_id, filename):
        try:
            output_path = os.path.join(self.file_manager.get_folder_path('downloads'), filename)
            
            cmd = [
                'yt-dlp',
                '-f', format_id,
                '-o', output_path + '.%(ext)s',
                url
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            for line in process.stdout:
                line_text = line.strip()
                if line_text:
                    self.root.after(0, lambda l=line_text: self.log(l, "youtube"))
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.log("[SUCCESS] Download completed successfully!", "youtube"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
                self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
            else:
                self.root.after(0, lambda: self.log("[ERROR] Download failed!", "youtube"))
                self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Download error: {msg}", "youtube"))
            self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
    
    def download_selected_videos(self):
        """Download selected videos using the same stream format"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        selection = self.video_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select at least one video")
            return
        
        stream_selection = self.stream_tree.selection()
        if not stream_selection:
            messagebox.showwarning("Warning", "Please select a stream format first")
            return
        
        item = stream_selection[0]
        format_id = str(self.stream_tree.item(item)['values'][0])
        
        selected_indices = list(selection)
        self.log(f"[INFO] Starting batch download of {len(selected_indices)} videos with format {format_id}", "youtube")
        
        self.set_busy(True, f"Downloading {len(selected_indices)} videos...", "youtube")
        
        thread = threading.Thread(target=self._batch_download_thread, args=(selected_indices, format_id))
        thread.daemon = True
        thread.start()
    
    def download_all_videos(self):
        """Download all videos using the same stream format"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        if not self.csv_data:
            messagebox.showwarning("Warning", "No CSV data loaded")
            return
        
        stream_selection = self.stream_tree.selection()
        if not stream_selection:
            messagebox.showwarning("Warning", "Please select a stream format first")
            return
        
        item = stream_selection[0]
        format_id = str(self.stream_tree.item(item)['values'][0])
        
        all_indices = list(range(len(self.csv_data)))
        self.log(f"[INFO] Starting batch download of all {len(all_indices)} videos with format {format_id}", "youtube")
        
        self.set_busy(True, f"Downloading all {len(all_indices)} videos...", "youtube")
        
        thread = threading.Thread(target=self._batch_download_thread, args=(all_indices, format_id))
        thread.daemon = True
        thread.start()
    
    def _batch_download_thread(self, video_indices, format_id):
        success_count = 0
        error_count = 0
        
        for i, index in enumerate(video_indices):
            try:
                row = self.csv_data[index]
                url = self.extract_youtube_url(row.get('Video Link', ''))
                
                if not url:
                    error_count += 1
                    self.root.after(0, lambda idx=index+1: self.log(f"[ERROR] Video {idx}: Could not extract URL", "youtube"))
                    continue
                
                filename_pattern = self.filename_var.get()
                filename = self.create_filename_from_pattern(filename_pattern, row)
                
                self.root.after(
                    0,
                    lambda idx=i+1, total=len(video_indices), name=row.get('Song Title', 'Unknown'):
                    self.set_busy(True, f"Downloading {idx}/{total}: {name}", "youtube")
                )
                
                self.root.after(
                    0,
                    lambda msg=f"\n[INFO] Downloading ({i+1}/{len(video_indices)}): {row.get('Song Title', 'Unknown')} - {row.get('Artist', 'Unknown')}":
                    self.log(msg, "youtube")
                )
                
                output_path = os.path.join(self.file_manager.get_folder_path('downloads'), filename)
                
                cmd = [
                    'yt-dlp',
                    '-f', format_id,
                    '-o', output_path + '.%(ext)s',
                    url
                ]
                
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if process.returncode == 0:
                    success_count += 1
                    self.root.after(
                        0,
                        lambda out=filename: self.log(f"[SUCCESS] Downloaded: {out}", "youtube")
                    )
                else:
                    error_count += 1
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg: self.log(f"[ERROR] Download failed: {err[:200]}", "youtube")
                    )
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}", "youtube")
                )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            self.log(f"\n[COMPLETE] Batch download finished: {s} succeeded, {e} failed", "youtube")
        )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            messagebox.showinfo(
                "Batch Download Complete",
                f"Batch download finished!\n\nSuccessful: {s}\nFailed: {e}"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False, tab="youtube"))
    
    # Video to MP3 Converter methods
    def select_video_files(self):
        files = self.select_files(
            title="Select Video/Audio Files",
            filetypes=self.file_manager.get_video_filetypes(),
            initial_dir=self.file_manager.get_folder_path('downloads')
        )
        
        if files:
            for file in files:
                if file not in self.selected_video_files:
                    self.selected_video_files.append(file)
            
            self.update_video_file_list()
            self.log(f"[INFO] Added {len(files)} file(s) to selection", "converter")
    
    def clear_video_selection(self):
        self.selected_video_files.clear()
        self.update_video_file_list()
        self.log("[INFO] Selection cleared", "converter")
    
    def update_video_file_list(self):
        self.video_file_listbox.delete(0, tk.END)
        
        for file in self.selected_video_files:
            filename = os.path.basename(file)
            self.video_file_listbox.insert(tk.END, filename)
        
        count = len(self.selected_video_files)
        self.lbl_video_status.config(text=f"{count} file(s) selected")
    
    def browse_converter_folder(self):
        folder = self.browse_folder(self.converter_folder_var.get())
        if folder:
            self.converter_folder_var.set(folder)
            self.file_manager.set_folder_path('converted', folder)
    
    def start_conversion(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        if not self.selected_video_files:
            messagebox.showwarning("Warning", "Please select at least one video file")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        self.file_manager.set_folder_path('converted', self.converter_folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('converted'))
        
        self.conversion_queue = self.selected_video_files.copy()
        
        self.log(f"[INFO] Starting conversion of {len(self.conversion_queue)} file(s)", "converter")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('converted')}", "converter")
        self.log(f"[INFO] Audio quality: {self.converter_quality_var.get()}", "converter")
        
        self.converter_progress['maximum'] = len(self.conversion_queue)
        self.converter_progress['value'] = 0
        
        self.set_busy(True, "Converting...", "converter")
        
        thread = threading.Thread(target=self._conversion_thread)
        thread.daemon = True
        thread.start()
    
    def _conversion_thread(self):
        success_count = 0
        error_count = 0
        
        for i, input_file in enumerate(self.conversion_queue):
            input_path = Path(input_file)
            output_file = os.path.join(self.file_manager.get_folder_path('converted'), f"{input_path.stem}.mp3")
            
            self.root.after(
                0,
                lambda idx=i+1, total=len(self.conversion_queue), name=input_path.name:
                self.set_busy(True, f"Converting {idx}/{total}: {name}", "converter")
            )
            
            self.root.after(
                0,
                lambda msg=f"\n[INFO] Converting ({i+1}/{len(self.conversion_queue)}): {input_path.name}":
                self.log(msg, "converter")
            )
            
            try:
                cmd = self.build_ffmpeg_command(
                    input_file, output_file, 
                    audio_codec='mp3', audio_bitrate=self.converter_quality_var.get()
                )
                
                process = self.run_ffmpeg_command(cmd)
                
                if process.returncode == 0:
                    success_count += 1
                    self.root.after(
                        0,
                        lambda out=output_file:
                        self.log(f"[SUCCESS] Saved: {os.path.basename(out)}", "converter")
                    )
                else:
                    error_count += 1
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg:
                        self.log(f"[ERROR] Conversion failed: {err[:200]}", "converter")
                    )
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Exception: {msg}", "converter")
                )
            
            self.root.after(0, lambda v=i+1: self.converter_progress.config(value=v))
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            self.log(f"\n[COMPLETE] Conversion finished: {s} succeeded, {e} failed", "converter")
        )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            messagebox.showinfo(
                "Conversion Complete",
                f"Conversion finished!\n\nSuccessful: {s}\nFailed: {e}"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False, tab="converter"))
    
    def convert_all_files(self):
        """Convert all files in the downloads folder"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        downloads_folder = self.file_manager.get_folder_path('downloads')
        if not os.path.exists(downloads_folder):
            messagebox.showerror("Error", "Downloads folder does not exist")
            return
        
        # Find all video files in downloads folder
        video_extensions = ['.mp4', '.webm', '.m4a', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        all_files = []
        
        for file in os.listdir(downloads_folder):
            file_path = os.path.join(downloads_folder, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in video_extensions:
                    all_files.append(file_path)
        
        if not all_files:
            messagebox.showwarning("Warning", "No video files found in downloads folder")
            return
        
        # Update the selected files list
        self.selected_video_files = all_files
        self.update_video_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} video files in downloads folder", "converter")
        
        # Start conversion with all files
        self.start_conversion()
    
    # Audio Modifier methods
    def select_audio_files(self):
        files = self.select_files(
            title="Select Audio Files",
            filetypes=self.file_manager.get_audio_filetypes(),
            initial_dir=self.file_manager.get_folder_path('converted')
        )
        
        if files:
            for file in files:
                if file not in self.selected_audio_files:
                    self.selected_audio_files.append(file)
            
            self.update_audio_file_list()
            self.log(f"[INFO] Added {len(files)} file(s) to selection", "modifier")
    
    def clear_audio_selection(self):
        self.selected_audio_files.clear()
        self.update_audio_file_list()
        self.log("[INFO] Selection cleared", "modifier")
    
    def update_audio_file_list(self):
        self.audio_file_listbox.delete(0, tk.END)
        
        for file in self.selected_audio_files:
            filename = os.path.basename(file)
            self.audio_file_listbox.insert(tk.END, filename)
        
        count = len(self.selected_audio_files)
        self.lbl_audio_status.config(text=f"{count} file(s) selected")
    
    def browse_modifier_folder(self):
        folder = self.browse_folder(self.modifier_folder_var.get())
        if folder:
            self.modifier_folder_var.set(folder)
            self.file_manager.set_folder_path('output', folder)
    
    def apply_preset(self, speed, pitch):
        self.speed_var.set(str(speed))
        self.pitch_var.set(str(pitch))
        self.log(f"[INFO] Applied preset: Speed {speed:+d}%, Pitch {pitch:+d} semitones", "modifier")
    
    def start_modification(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Modification already in progress")
            return
        
        if not self.selected_audio_files:
            messagebox.showwarning("Warning", "Please select at least one audio file")
            return
        
        try:
            speed_percent = float(self.speed_var.get())
            pitch_semitones = float(self.pitch_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid speed or pitch value. Please enter valid numbers.")
            return
        
        if speed_percent < -50 or speed_percent > 100:
            messagebox.showerror("Error", "Speed adjustment must be between -50% and +100%")
            return
        
        if pitch_semitones < -12 or pitch_semitones > 12:
            messagebox.showerror("Error", "Pitch adjustment must be between -12 and +12 semitones")
            return
        
        if speed_percent == 0 and pitch_semitones == 0:
            messagebox.showwarning("Warning", "No modifications specified (both speed and pitch are 0)")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        self.file_manager.set_folder_path('output', self.modifier_folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('output'))
        
        self.modification_queue = self.selected_audio_files.copy()
        
        self.log(f"[INFO] Starting modification of {len(self.modification_queue)} file(s)", "modifier")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('output')}", "modifier")
        self.log(f"[INFO] Speed: {speed_percent:+.1f}%, Pitch: {pitch_semitones:+.1f} semitones", "modifier")
        self.log(f"[INFO] Audio quality: {self.modifier_quality_var.get()}", "modifier")
        
        self.modifier_progress['maximum'] = len(self.modification_queue)
        self.modifier_progress['value'] = 0
        
        self.set_busy(True, "Modifying...", "modifier")
        
        thread = threading.Thread(target=self._modification_thread, args=(speed_percent, pitch_semitones))
        thread.daemon = True
        thread.start()
    
    def _modification_thread(self, speed_percent, pitch_semitones):
        success_count = 0
        error_count = 0
        
        for i, input_file in enumerate(self.modification_queue):
            input_path = Path(input_file)
            
            suffix_parts = []
            if speed_percent != 0:
                suffix_parts.append(f"speed{speed_percent:+.0f}pct")
            if pitch_semitones != 0:
                suffix_parts.append(f"pitch{pitch_semitones:+.0f}st")
            
            suffix = "_" + "_".join(suffix_parts) if suffix_parts else "_modified"
            output_file = os.path.join(self.file_manager.get_folder_path('output'), f"{input_path.stem}{suffix}{input_path.suffix}")
            
            self.root.after(
                0,
                lambda idx=i+1, total=len(self.modification_queue), name=input_path.name:
                self.set_busy(True, f"Modifying {idx}/{total}: {name}", "modifier")
            )
            
            self.root.after(
                0,
                lambda msg=f"\n[INFO] Modifying ({i+1}/{len(self.modification_queue)}): {input_path.name}":
                self.log(msg, "modifier")
            )
            
            try:
                filters = []
                
                if speed_percent != 0:
                    speed_factor = 1.0 + (speed_percent / 100.0)
                    filters.append(f"atempo={speed_factor}")
                
                if pitch_semitones != 0:
                    pitch_factor = 2 ** (pitch_semitones / 12.0)
                    filters.append(f"asetrate=44100*{pitch_factor},aresample=44100")
                
                cmd = self.build_ffmpeg_command(
                    input_file, output_file,
                    audio_filters=filters,
                    audio_bitrate=self.modifier_quality_var.get()
                )
                
                process = self.run_ffmpeg_command(cmd)
                
                if process.returncode == 0:
                    success_count += 1
                    self.root.after(
                        0,
                        lambda out=output_file:
                        self.log(f"[SUCCESS] Saved: {os.path.basename(out)}", "modifier")
                    )
                else:
                    error_count += 1
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg:
                        self.log(f"[ERROR] Modification failed: {err[:200]}", "modifier")
                    )
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg:
                    self.log(f"[ERROR] Exception: {msg}", "modifier")
                )
            
            self.root.after(0, lambda v=i+1: self.modifier_progress.config(value=v))
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            self.log(f"\n[COMPLETE] Modification finished: {s} succeeded, {e} failed", "modifier")
        )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            messagebox.showinfo(
                "Modification Complete",
                f"Modification finished!\n\nSuccessful: {s}\nFailed: {e}"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False, tab="modifier"))
    
    def modify_all_files(self):
        """Modify all files in the converted folder"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Modification already in progress")
            return
        
        converted_folder = self.file_manager.get_folder_path('converted')
        if not os.path.exists(converted_folder):
            messagebox.showerror("Error", "Converted folder does not exist")
            return
        
        # Find all audio files in converted folder
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
        self.selected_audio_files = all_files
        self.update_audio_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} audio files in converted folder", "modifier")
        
        # Start modification with all files
        self.start_modification()
    
    # Common FFmpeg methods
    def check_ffmpeg(self):
        return self.ffmpeg_manager.check_ffmpeg()
    
    def offer_ffmpeg_install(self):
        return self.ffmpeg_manager.offer_ffmpeg_install(self.show_message)
    
    def download_ffmpeg_windows(self):
        self.set_busy(True, "Downloading FFmpeg...", "converter")
        
        def progress_callback(message):
            self.root.after(0, lambda msg=message: self.log(f"[INFO] {msg}", "converter"))
        
        def success_callback(message):
            self.root.after(0, lambda msg=message: self.log("[SUCCESS] FFmpeg installed successfully!", "converter"))
            self.root.after(0, lambda msg=message: self.show_message("info", "Success", msg))
            self.root.after(0, lambda: self.set_busy(False, tab="converter"))
        
        def error_callback(message):
            self.root.after(0, lambda msg=message: self.log(f"[ERROR] FFmpeg download failed: {msg}", "converter"))
            self.root.after(0, lambda msg=message: self.show_message("error", "Download Failed", msg))
            self.root.after(0, lambda: self.set_busy(False, tab="converter"))
        
        self.ffmpeg_manager.download_ffmpeg_windows(progress_callback, success_callback, error_callback)
    
    # Settings methods
    def browse_download_folder(self):
        folder = self.browse_folder(self.download_folder_var.get())
        if folder:
            self.download_folder_var.set(folder)
            self.file_manager.set_folder_path('downloads', folder)
    
    def browse_converted_folder(self):
        folder = self.browse_folder(self.converted_folder_var.get())
        if folder:
            self.converted_folder_var.set(folder)
            self.file_manager.set_folder_path('converted', folder)
    
    def browse_modified_folder(self):
        folder = self.browse_folder(self.modified_folder_var.get())
        if folder:
            self.modified_folder_var.set(folder)
            self.file_manager.set_folder_path('output', folder)


def main():
    auto_load_csv = None
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        if os.path.isfile(csv_path):
            auto_load_csv = csv_path
        else:
            print(f"[WARNING] CSV file not found: {csv_path}")
    
    root = tk.Tk()
    app = AudioToolsUnifiedGUI(root, auto_load_csv=auto_load_csv)
    
    if auto_load_csv:
        print(f"[INFO] Auto-loading CSV file: {auto_load_csv}")
    
    root.mainloop()


if __name__ == '__main__':
    main()
