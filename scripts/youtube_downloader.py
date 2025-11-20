"""
YouTube Downloader - Individual Application

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
import random
import time
from pathlib import Path

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI


class YouTubeDownloaderGUI(BaseAudioGUI):
    def __init__(self, root, auto_load_csv=None):
        super().__init__(root, "YouTube Downloader")
        self.root.geometry("900x750")
        
        self.csv_file = None
        self.csv_basename = None
        self.csv_data = []
        self.available_streams = []
        self.current_video_info = None
        self.cancel_download = False
        self.current_process = None
        self.use_android_client = False  # Default: disabled (use web client for more formats)
        self.user_agent = self.generate_user_agent()  # Randomize user agent on startup
        self.cookie_file = None  # Path to cookies file
        self.download_delay = 2.0  # Delay between downloads in seconds
        self.use_stealth_mode = True  # Enable additional stealth options
        
        # Direct link tab attributes
        self.direct_link_url = None
        self.direct_link_streams = []
        self.direct_link_video_info = None
        
        self.setup_ui()
        
        if auto_load_csv and os.path.isfile(auto_load_csv):
            self.root.after(100, lambda: self.load_csv_file(auto_load_csv))
    
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tab_load = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.tab_direct_link = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_load, text="Load CSV")
        self.notebook.add(self.tab_download, text="Download Videos")
        self.notebook.add(self.tab_direct_link, text="Direct Link")
        self.notebook.add(self.tab_settings, text="Settings")
        
        self.setup_load_tab()
        self.setup_download_tab()
        self.setup_direct_link_tab()
        self.setup_settings_tab()
    
    def setup_load_tab(self):
        frame = ttk.LabelFrame(self.tab_load, text="CSV File Selection", padding=10)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select CSV File", command=self.load_csv).pack(side='left', padx=5)
        self.lbl_csv_status = ttk.Label(btn_frame, text="No file loaded")
        self.lbl_csv_status.pack(side='left', padx=5)
        
        ttk.Label(frame, text="CSV Data:").pack(anchor='w', pady=(10, 5))
        
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill='both', expand=True)
        
        csv_scroll_y = ttk.Scrollbar(tree_frame, orient='vertical')
        csv_scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        
        self.csv_tree = ttk.Treeview(
            tree_frame,
            yscrollcommand=csv_scroll_y.set,
            xscrollcommand=csv_scroll_x.set,
            show='tree headings',
            height=15
        )
        
        csv_scroll_y.config(command=self.csv_tree.yview)
        csv_scroll_x.config(command=self.csv_tree.xview)
        
        self.csv_tree.grid(row=0, column=0, sticky='nsew')
        csv_scroll_y.grid(row=0, column=1, sticky='ns')
        csv_scroll_x.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
    
    def setup_download_tab(self):
        top_frame = ttk.Frame(self.tab_download)
        top_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(top_frame, text="Select Video:").pack(anchor='w')
        
        self.video_listbox = tk.Listbox(top_frame, height=8, selectmode=tk.EXTENDED)
        self.video_listbox.pack(fill='both', expand=True, pady=5)
        self.video_listbox.bind('<<ListboxSelect>>', self.on_video_select)
        
        ttk.Button(top_frame, text="Fetch Available Streams", command=self.fetch_streams).pack(pady=5)
        
        self.progress = ttk.Progressbar(top_frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=5)
        self.progress_label = ttk.Label(top_frame, text="")
        self.progress_label.pack(anchor='w')
        
        mid_frame = ttk.LabelFrame(self.tab_download, text="Available Streams", padding=10)
        mid_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Format ID', 'Extension', 'Resolution', 'FPS', 'File Size', 'Audio Codec', 'Video Codec')
        self.stream_tree = ttk.Treeview(mid_frame, columns=columns, show='tree headings', height=10)
        
        self.stream_tree.heading('#0', text='Type')
        self.stream_tree.column('#0', width=100)
        
        for col in columns:
            self.stream_tree.heading(col, text=col)
            self.stream_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(mid_frame, orient='vertical', command=self.stream_tree.yview)
        self.stream_tree.configure(yscrollcommand=scrollbar.set)
        
        self.stream_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        bottom_frame = ttk.Frame(self.tab_download)
        bottom_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(bottom_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Download Selected Stream", command=self.download_stream).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Download Selected Videos", command=self.download_selected_videos).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Download All Videos", command=self.download_all_videos).pack(side='left', padx=5)
        self.cancel_button = ttk.Button(batch_frame, text="Cancel Download", command=self.cancel_download_action, state='disabled')
        self.cancel_button.pack(side='left', padx=5)
        
        # Auto-download lowest resolution buttons
        auto_frame = ttk.Frame(bottom_frame)
        auto_frame.pack(fill='x', pady=5)
        ttk.Label(auto_frame, text="Auto Download (Lowest Resolution):", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=5)
        ttk.Button(auto_frame, text="Selected Videos", command=self.auto_download_lowest_resolution_selected).pack(side='left', padx=5)
        ttk.Button(auto_frame, text="All Videos", command=self.auto_download_lowest_resolution_all).pack(side='left', padx=5)
        
        self.log_text = scrolledtext.ScrolledText(bottom_frame, height=8)
        self.log_text.pack(fill='both', expand=True)
    
    def setup_direct_link_tab(self):
        # URL input frame
        url_frame = ttk.LabelFrame(self.tab_direct_link, text="YouTube URL", padding=10)
        url_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(url_frame, text="Enter YouTube URL:").pack(anchor='w', pady=(0, 5))
        
        url_input_frame = ttk.Frame(url_frame)
        url_input_frame.pack(fill='x', pady=5)
        
        self.direct_link_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_input_frame, textvariable=self.direct_link_url_var, width=70)
        url_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        url_entry.bind('<Return>', lambda e: self.fetch_direct_link_streams())
        
        ttk.Button(url_input_frame, text="Fetch Streams", command=self.fetch_direct_link_streams).pack(side='left')
        
        self.direct_link_progress = ttk.Progressbar(url_frame, mode='indeterminate')
        self.direct_link_progress.pack(fill='x', pady=5)
        self.direct_link_progress_label = ttk.Label(url_frame, text="")
        self.direct_link_progress_label.pack(anchor='w')
        
        # Video info frame
        info_frame = ttk.LabelFrame(self.tab_direct_link, text="Video Information", padding=10)
        info_frame.pack(fill='x', padx=10, pady=10)
        
        self.direct_link_info_text = scrolledtext.ScrolledText(info_frame, height=4, wrap=tk.WORD)
        self.direct_link_info_text.pack(fill='both', expand=True)
        
        # Streams frame
        streams_frame = ttk.LabelFrame(self.tab_direct_link, text="Available Streams", padding=10)
        streams_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Format ID', 'Extension', 'Resolution', 'FPS', 'File Size', 'Audio Codec', 'Video Codec')
        self.direct_link_stream_tree = ttk.Treeview(streams_frame, columns=columns, show='tree headings', height=10)
        
        self.direct_link_stream_tree.heading('#0', text='Type')
        self.direct_link_stream_tree.column('#0', width=100)
        
        for col in columns:
            self.direct_link_stream_tree.heading(col, text=col)
            self.direct_link_stream_tree.column(col, width=100)
        
        stream_scrollbar = ttk.Scrollbar(streams_frame, orient='vertical', command=self.direct_link_stream_tree.yview)
        self.direct_link_stream_tree.configure(yscrollcommand=stream_scrollbar.set)
        
        self.direct_link_stream_tree.pack(side='left', fill='both', expand=True)
        stream_scrollbar.pack(side='right', fill='y')
        
        # Download frame
        download_frame = ttk.Frame(self.tab_direct_link)
        download_frame.pack(fill='x', padx=10, pady=10)
        
        btn_frame = ttk.Frame(download_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Label(btn_frame, text="Filename:").pack(side='left', padx=5)
        self.direct_link_filename_var = tk.StringVar()
        filename_entry = ttk.Entry(btn_frame, textvariable=self.direct_link_filename_var, width=40)
        filename_entry.pack(side='left', padx=5, fill='x', expand=True)
        
        ttk.Button(btn_frame, text="Download Selected Stream", command=self.download_direct_link_stream).pack(side='left', padx=5)
        self.direct_link_cancel_button = ttk.Button(btn_frame, text="Cancel Download", command=self.cancel_download_action, state='disabled')
        self.direct_link_cancel_button.pack(side='left', padx=5)
        
        self.direct_link_log_text = scrolledtext.ScrolledText(download_frame, height=8)
        self.direct_link_log_text.pack(fill='both', expand=True)
    
    def setup_settings_tab(self):
        frame = ttk.LabelFrame(self.tab_settings, text="Download Settings", padding=10)
        frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(frame, text="Download Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.folder_var = tk.StringVar(value=self.file_manager.get_folder_path('downloads'))
        ttk.Entry(frame, textvariable=self.folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="Browse", command=self.browse_folder).grid(row=0, column=2)
        
        self.actual_path_label = ttk.Label(frame, text="Actual download path: (load CSV to see)", foreground='gray')
        self.actual_path_label.grid(row=1, column=0, columnspan=3, sticky='w', pady=2)
        
        ttk.Label(frame, text="Filename Pattern:").grid(row=2, column=0, sticky='w', pady=5)
        self.filename_var = tk.StringVar(value="{Rank}_{Song Title}_{Artist}")
        ttk.Entry(frame, textvariable=self.filename_var, width=50).grid(row=2, column=1, padx=5, columnspan=2)
        
        ttk.Label(frame, text="Available fields: {Rank}, {Song Title}, {Artist}, {Year}, {Views (Billions)}").grid(
            row=3, column=0, columnspan=3, sticky='w', pady=5
        )
        
        ttk.Label(frame, text="Stealth Mode:").grid(row=4, column=0, sticky='w', pady=5)
        self.stealth_mode_var = tk.BooleanVar(value=True)
        stealth_check = ttk.Checkbutton(
            frame,
            text="Enable stealth mode (recommended to avoid 403 errors)",
            variable=self.stealth_mode_var,
            command=self.on_stealth_mode_changed
        )
        stealth_check.grid(row=4, column=1, columnspan=2, sticky='w', padx=5)
        
        ttk.Label(frame, text="Client Type:").grid(row=5, column=0, sticky='w', pady=5)
        self.client_type_var = tk.StringVar(value="web")
        client_frame = ttk.Frame(frame)
        client_frame.grid(row=5, column=1, columnspan=2, sticky='w', padx=5)
        ttk.Radiobutton(client_frame, text="Web (more formats)", variable=self.client_type_var, value="web").pack(side='left', padx=5)
        ttk.Radiobutton(client_frame, text="Android (better stealth)", variable=self.client_type_var, value="android").pack(side='left', padx=5)
        ttk.Radiobutton(client_frame, text="iOS (best stealth)", variable=self.client_type_var, value="ios").pack(side='left', padx=5)
        ttk.Radiobutton(client_frame, text="TV (alternative)", variable=self.client_type_var, value="tv").pack(side='left', padx=5)
        
        ttk.Label(frame, text="Cookie File (optional):").grid(row=6, column=0, sticky='w', pady=5)
        cookie_frame = ttk.Frame(frame)
        cookie_frame.grid(row=6, column=1, columnspan=2, sticky='ew', padx=5)
        frame.grid_columnconfigure(1, weight=1)
        self.cookie_file_var = tk.StringVar()
        ttk.Entry(cookie_frame, textvariable=self.cookie_file_var, width=40).pack(side='left', fill='x', expand=True, padx=(0, 5))
        ttk.Button(cookie_frame, text="Browse", command=self.browse_cookie_file).pack(side='left')
        ttk.Label(frame, text="Export cookies from browser (Netscape format) for better stealth", foreground='gray', font=('TkDefaultFont', 8)).grid(
            row=7, column=0, columnspan=3, sticky='w', padx=5
        )
        
        ttk.Label(frame, text="Delay Between Downloads (seconds):").grid(row=8, column=0, sticky='w', pady=5)
        self.delay_var = tk.DoubleVar(value=2.0)
        delay_spin = ttk.Spinbox(frame, from_=0.0, to=60.0, increment=0.5, textvariable=self.delay_var, width=10)
        delay_spin.grid(row=8, column=1, sticky='w', padx=5)
        ttk.Label(frame, text="(Higher delay = less likely to be detected, but slower)", foreground='gray', font=('TkDefaultFont', 8)).grid(
            row=9, column=0, columnspan=3, sticky='w', padx=5
        )
        
        info_frame = ttk.LabelFrame(self.tab_settings, text="Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        info_text = """YouTube Downloader with GUI

Features:
- Load CSV files with YouTube links
- View available video/audio streams
- Select specific quality and format
- Download with custom filenames based on CSV fields
- Stealth mode to avoid 403 errors
- Multiple client types (Web, Android, iOS, TV)
- Cookie file support for better stealth
- Automatic venv management via launcher scripts

Stealth Mode Tips:
- Enable Stealth Mode (recommended) to avoid 403 errors
- Use iOS client for best stealth (may have fewer formats)
- Use Android client for good balance of stealth and formats
- Export browser cookies (Netscape format) and load them for better results
- Increase delay between downloads if you still get 403 errors
- The tool automatically tries alternative clients if 403 is detected

Instructions:
1. Load a CSV file containing YouTube links
2. Configure stealth settings in this tab
3. Select a video from the list
4. Fetch available streams
5. Choose your preferred stream (video+audio, video only, or audio only)
6. Download to the configured folder

Note: Links in CSV can be in markdown format [URL](URL) or plain URLs.
"""
        info_label = ttk.Label(info_frame, text=info_text, justify='left')
        info_label.pack(anchor='w')
    
    def set_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.progress.start(10)
            self.progress_label.config(text=message)
            self.cancel_button.config(state='normal')
        else:
            self.root.config(cursor="")
            self.progress.stop()
            self.progress_label.config(text="")
            self.cancel_button.config(state='disabled')
    
    def cancel_download_action(self):
        """Cancel the current download operation"""
        self.cancel_download = True
        if self.current_process:
            try:
                self.current_process.terminate()
                self.log("[INFO] Download cancelled by user")
            except Exception as e:
                self.log(f"[WARNING] Error cancelling process: {str(e)}")
        self.set_busy(False)
    
    def update_actual_path_label(self):
        """Update the actual download path label"""
        actual_path = self.get_download_path()
        if self.csv_basename:
            self.actual_path_label.config(
                text=f"Actual download path: {actual_path}",
                foreground='black'
            )
        else:
            self.actual_path_label.config(
                text="Actual download path: (load CSV to see)",
                foreground='gray'
            )
    
    def on_android_client_changed(self):
        """Callback when Android client checkbox is toggled"""
        self.use_android_client = self.android_client_var.get()
    
    def on_stealth_mode_changed(self):
        """Callback when stealth mode checkbox is toggled"""
        self.use_stealth_mode = self.stealth_mode_var.get()
    
    def browse_cookie_file(self):
        """Browse for cookie file"""
        file_path = filedialog.askopenfilename(
            title="Select Cookie File",
            filetypes=[("Netscape Cookie File", "*.txt"), ("All Files", "*.*")],
            initialdir=self.root_dir
        )
        if file_path:
            self.cookie_file_var.set(file_path)
            self.cookie_file = file_path
    
    def browse_folder(self):
        folder = super().browse_folder(self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.file_manager.set_folder_path('downloads', folder)
            self.update_actual_path_label()
    
    def load_csv(self):
        file_path = super().select_files(
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
        self.set_busy(True, "Loading CSV file...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.csv_data = list(reader)
            
            self.csv_file = file_path
            self.csv_basename = os.path.splitext(os.path.basename(file_path))[0]
            self.lbl_csv_status.config(text=f"Loaded: {os.path.basename(file_path)} ({len(self.csv_data)} rows)")
            
            self.display_csv_in_grid()
            self.populate_video_list()
            self.update_actual_path_label()
            
            self.notebook.select(self.tab_download)
            
            self.log(f"[SUCCESS] Loaded {len(self.csv_data)} videos from CSV: {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")
            self.log(f"[ERROR] Failed to load CSV: {str(e)}")
        finally:
            self.set_busy(False)
    
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
    
    def get_download_path(self):
        """Get download path with CSV basename as subfolder"""
        base_path = self.file_manager.get_folder_path('downloads')
        if self.csv_basename:
            download_path = os.path.join(base_path, self.csv_basename)
            os.makedirs(download_path, exist_ok=True)
            return download_path
        return base_path
    
    def generate_user_agent(self):
        """Generate a randomized Chrome user agent string"""
        # Randomize Chrome version (120-130 range)
        chrome_major = random.randint(120, 130)
        chrome_minor = random.randint(0, 9)
        chrome_patch = random.randint(0, 9)
        
        # Randomize WebKit version slightly (537.30 - 537.40)
        webkit_major = 537
        webkit_minor = random.randint(30, 40)
        
        # Randomize Safari version to match WebKit
        safari_major = webkit_major
        safari_minor = webkit_minor
        
        user_agent = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/{webkit_major}.{webkit_minor} (KHTML, like Gecko) "
            f"Chrome/{chrome_major}.{chrome_minor}.{chrome_patch}.0 "
            f"Safari/{safari_major}.{safari_minor}"
        )
        
        return user_agent
    
    def build_ytdlp_command(self, base_args):
        """Build yt-dlp command with anti-403 stealth options
        
        Args:
            base_args: List of yt-dlp arguments
        """
        cmd = [
            sys.executable,
            '-m', 'yt_dlp',
        ]
        
        # User agent (always set)
        cmd.extend(['--user-agent', self.user_agent])
        
        # Cookie file (if provided)
        cookie_file = self.cookie_file_var.get().strip() if hasattr(self, 'cookie_file_var') else self.cookie_file
        if cookie_file and os.path.isfile(cookie_file):
            cmd.extend(['--cookies', cookie_file])
        
        # Client type based on settings
        client_type = self.client_type_var.get() if hasattr(self, 'client_type_var') else ('android' if self.use_android_client else 'web')
        
        # Stealth mode options
        if self.use_stealth_mode:
            # Set referer to YouTube
            cmd.extend(['--referer', 'https://www.youtube.com/'])
            
            # Add extractor args for client type
            if client_type == 'android':
                cmd.extend(['--extractor-args', 'youtube:player_client=android'])
            elif client_type == 'ios':
                cmd.extend(['--extractor-args', 'youtube:player_client=ios'])
            elif client_type == 'tv':
                cmd.extend(['--extractor-args', 'youtube:player_client=tv'])
            # web is default, no extractor args needed
            
            # Additional stealth options
            cmd.extend([
                '--extractor-args', 'youtube:include_live_chat=false',  # Disable live chat to reduce requests
                '--no-check-certificate',  # Skip certificate validation (may help with some proxies)
            ])
            
            # Add headers to mimic browser
            cmd.extend([
                '--add-header', 'Accept-Language:en-US,en;q=0.9',
                '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '--add-header', 'Accept-Encoding:gzip, deflate',
                '--add-header', 'DNT:1',
            ])
        else:
            # Minimal stealth when disabled
            if client_type == 'android':
                cmd.extend(['--extractor-args', 'youtube:player_client=android'])
        
        return cmd + base_args
    
    def extract_youtube_url(self, text):
        if not text:
            return None
        
        self.log(f"[DEBUG] Extracting URL from: {text[:100]}...")
        
        # Pattern 1: Markdown format [URL](URL)
        markdown_pattern = r'\[(https://www\.youtube\.com/watch\?v=[\w-]+)\]\(https://www\.youtube\.com/watch\?v=[\w-]+\)'
        match = re.search(markdown_pattern, text)
        if match:
            url = match.group(1)
            self.log(f"[DEBUG] Extracted URL (markdown): {url}")
            return url
        
        # Pattern 2: Direct YouTube video URL
        url_pattern = r'https://www\.youtube\.com/watch\?v=[\w-]+'
        match = re.search(url_pattern, text)
        if match:
            url = match.group(0)
            self.log(f"[DEBUG] Extracted URL (direct): {url}")
            return url
        
        # Pattern 3: YouTube search URL - extract search query and use it directly
        search_pattern = r'https://www\.youtube\.com/results\?search_query=([^&\s]+)'
        match = re.search(search_pattern, text)
        if match:
            search_query = match.group(1)
            # URL decode the search query
            import urllib.parse
            decoded_query = urllib.parse.unquote_plus(search_query)
            self.log(f"[DEBUG] Extracted search query: {decoded_query}")
            self.log(f"[INFO] Using search query as yt-dlp input: {decoded_query}")
            return decoded_query
        
        self.log(f"[ERROR] No supported URL pattern found in text")
        return None
    
    def on_video_select(self, event):
        selection = self.video_listbox.curselection()
        if selection:
            self.stream_tree.delete(*self.stream_tree.get_children())
            self.log(f"Selected video #{selection[0] + 1}")
    
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
        
        self.log(f"[DEBUG] Available CSV fields: {list(row.keys())}")
        video_link = row.get('Video Link', '')
        self.log(f"[DEBUG] Video Link field value: '{video_link}'")
        
        url = self.extract_youtube_url(video_link)
        if not url:
            self.log(f"[ERROR] Could not extract YouTube URL from CSV")
            messagebox.showerror("Error", "Could not extract YouTube URL from CSV")
            return
        
        self.log(f"[INFO] Fetching streams for: {url}")
        self.set_busy(True, "Fetching available streams...")
        
        thread = threading.Thread(target=self._fetch_streams_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def _fetch_streams_thread(self, url):
        try:
            # Try with current setting first (web client by default for more formats)
            cmd = self.build_ytdlp_command(['-J', url])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # If web client fails with 403 and Android client is disabled, try Android client
            if (result.returncode != 0 and 
                ('403' in result.stderr or 'Forbidden' in result.stderr) and 
                not self.use_android_client):
                self.root.after(0, lambda: self.log("[INFO] Web client blocked, trying Android client..."))
                # Temporarily enable Android client for this fetch
                original_setting = self.use_android_client
                self.use_android_client = True
                cmd = self.build_ytdlp_command(['-J', url])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                # Restore original setting
                self.use_android_client = original_setting
                if result.returncode == 0:
                    self.root.after(0, lambda: self.log("[INFO] Consider enabling Android Client Mode in Settings to avoid 403 errors"))
            
            if result.returncode != 0:
                error_msg = result.stderr
                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] {msg}"))
                self.root.after(0, lambda: self.set_busy(False))
                return
            
            data = json.loads(result.stdout)
            formats = data.get('formats', [])
            
            self.available_streams = formats
            self.root.after(0, lambda: self.display_streams(formats))
            self.root.after(0, lambda: self.set_busy(False))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Fetching streams: {msg}"))
            self.root.after(0, lambda: self.set_busy(False))
    
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
        
        self.log(f"[SUCCESS] Found {len(formats)} streams ({len(combined)} combined, {len(video_only)} video, {len(audio_only)} audio)")
    
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
        
        self.cancel_download = False
        self.current_process = None
        
        self.log(f"[INFO] Starting download: Format {format_id}")
        self.log(f"[INFO] Output file: {filename}")
        self.set_busy(True, "Downloading...")
        
        thread = threading.Thread(target=self._download_thread, args=(url, format_id, filename))
        thread.daemon = True
        thread.start()
    
    
    def _download_thread(self, url, format_id, filename):
        try:
            if self.cancel_download:
                self.root.after(0, lambda: self.log("[INFO] Download cancelled"))
                self.root.after(0, lambda: self.set_busy(False))
                return
            
            output_path = os.path.join(self.get_download_path(), filename)
            
            cmd = self.build_ytdlp_command([
                '-f', format_id,
                '-o', output_path + '.%(ext)s',
                url
            ])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            self.current_process = process
            
            for line in process.stdout:
                if self.cancel_download:
                    process.terminate()
                    self.root.after(0, lambda: self.log("[INFO] Download cancelled by user"))
                    self.root.after(0, lambda: self.set_busy(False))
                    return
                
                line_text = line.strip()
                if line_text:
                    self.root.after(0, lambda l=line_text: self.log(l))
            
            process.wait()
            
            if self.cancel_download:
                self.root.after(0, lambda: self.log("[INFO] Download cancelled"))
                self.root.after(0, lambda: self.set_busy(False))
                return
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.log("[SUCCESS] Download completed successfully!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
                self.root.after(0, lambda: self.set_busy(False))
            else:
                self.root.after(0, lambda: self.log("[ERROR] Download failed!"))
                self.root.after(0, lambda: self.set_busy(False))
                
        except Exception as e:
            if not self.cancel_download:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Download error: {msg}"))
            self.root.after(0, lambda: self.set_busy(False))
        finally:
            self.current_process = None
    
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
        
        self.cancel_download = False
        self.current_process = None
        
        selected_indices = list(selection)
        self.log(f"[INFO] Starting batch download of {len(selected_indices)} videos with format {format_id}")
        
        self.set_busy(True, f"Downloading {len(selected_indices)} videos...")
        
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
        
        self.cancel_download = False
        self.current_process = None
        
        all_indices = list(range(len(self.csv_data)))
        self.log(f"[INFO] Starting batch download of all {len(all_indices)} videos with format {format_id}")
        
        self.set_busy(True, f"Downloading all {len(all_indices)} videos...")
        
        thread = threading.Thread(target=self._batch_download_thread, args=(all_indices, format_id))
        thread.daemon = True
        thread.start()
    
    def _batch_download_thread(self, video_indices, format_id):
        success_count = 0
        error_count = 0
        
        for i, index in enumerate(video_indices):
            if self.cancel_download:
                self.root.after(0, lambda: self.log("[INFO] Batch download cancelled by user"))
                break
            
            try:
                row = self.csv_data[index]
                url = self.extract_youtube_url(row.get('Video Link', ''))
                
                if not url:
                    error_count += 1
                    self.root.after(0, lambda idx=index+1: self.log(f"[ERROR] Video {idx}: Could not extract URL"))
                    continue
                
                filename_pattern = self.filename_var.get()
                filename = self.create_filename_from_pattern(filename_pattern, row)
                
                self.root.after(
                    0,
                    lambda idx=i+1, total=len(video_indices), name=row.get('Song Title', 'Unknown'):
                    self.set_busy(True, f"Downloading {idx}/{total}: {name}")
                )
                
                self.root.after(
                    0,
                    lambda msg=f"\n[INFO] Downloading ({i+1}/{len(video_indices)}): {row.get('Song Title', 'Unknown')} - {row.get('Artist', 'Unknown')}":
                    self.log(msg)
                )
                
                output_path = os.path.join(self.get_download_path(), filename)
                
                # Rotate user agent for each download to avoid detection
                if i > 0 and i % 5 == 0:  # Change user agent every 5 downloads
                    self.user_agent = self.generate_user_agent()
                    self.root.after(0, lambda: self.log(f"[DEBUG] Rotated user agent for stealth"))
                
                cmd = self.build_ytdlp_command([
                    '-f', format_id,
                    '-o', output_path + '.%(ext)s',
                    url
                ])
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                self.current_process = process
                
                stdout, stderr = process.communicate()
                
                if self.cancel_download:
                    try:
                        process.terminate()
                    except:
                        pass
                    self.root.after(0, lambda: self.log("[INFO] Batch download cancelled by user"))
                    break
                
                if process.returncode == 0:
                    success_count += 1
                    self.root.after(
                        0,
                        lambda out=filename: self.log(f"[SUCCESS] Downloaded: {out}")
                    )
                else:
                    error_count += 1
                    error_msg = stderr if stderr else "Unknown error"
                    
                    # If 403 error, try with different client
                    if '403' in error_msg or 'Forbidden' in error_msg:
                        self.root.after(0, lambda: self.log(f"[WARNING] 403 detected, trying alternative client..."))
                        # Try with iOS client as fallback
                        original_client = self.client_type_var.get() if hasattr(self, 'client_type_var') else 'web'
                        if original_client != 'ios':
                            self.client_type_var.set('ios') if hasattr(self, 'client_type_var') else None
                            cmd_fallback = self.build_ytdlp_command([
                                '-f', format_id,
                                '-o', output_path + '.%(ext)s',
                                url
                            ])
                            process_fallback = subprocess.run(
                                cmd_fallback,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                            )
                            if process_fallback.returncode == 0:
                                success_count += 1
                                error_count -= 1
                                self.root.after(0, lambda fname=filename: self.log(f"[SUCCESS] Downloaded with fallback client: {fname}"))
                            else:
                                self.root.after(0, lambda err=error_msg: self.log(f"[ERROR] Download failed: {err[:200]}"))
                            if hasattr(self, 'client_type_var'):
                                self.client_type_var.set(original_client)
                        else:
                            self.root.after(0, lambda err=error_msg: self.log(f"[ERROR] Download failed: {err[:200]}"))
                    else:
                        self.root.after(0, lambda err=error_msg: self.log(f"[ERROR] Download failed: {err[:200]}"))
                
                # Add delay between downloads to avoid rate limiting
                if i < len(video_indices) - 1:  # Don't delay after last download
                    delay = self.delay_var.get() if hasattr(self, 'delay_var') else self.download_delay
                    if delay > 0:
                        # Add some randomness to delay (80-120% of base delay)
                        actual_delay = delay * random.uniform(0.8, 1.2)
                        time.sleep(actual_delay)
                
            except Exception as e:
                if not self.cancel_download:
                    error_count += 1
                    error_msg = str(e)
                    self.root.after(
                        0,
                        lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}")
                    )
            finally:
                self.current_process = None
        
        if not self.cancel_download:
            self.root.after(
                0,
                lambda s=success_count, e=error_count:
                self.log(f"\n[COMPLETE] Batch download finished: {s} succeeded, {e} failed")
            )
            
            self.root.after(
                0,
                lambda s=success_count, e=error_count:
                messagebox.showinfo(
                    "Batch Download Complete",
                    f"Batch download finished!\n\nSuccessful: {s}\nFailed: {e}"
                )
            )
        else:
            self.root.after(
                0,
                lambda s=success_count, e=error_count:
                self.log(f"\n[CANCELLED] Batch download stopped: {s} succeeded, {e} failed")
            )
        
        self.root.after(0, lambda: self.set_busy(False))
    
    def auto_download_lowest_resolution_selected(self):
        """Auto-download lowest resolution for selected videos"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        selection = self.video_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select at least one video")
            return
        
        self.cancel_download = False
        self.current_process = None
        
        selected_indices = list(selection)
        self.log(f"[INFO] Starting auto-download of lowest resolution for {len(selected_indices)} videos")
        
        self.set_busy(True, f"Auto-downloading {len(selected_indices)} videos (lowest resolution)...")
        
        thread = threading.Thread(target=self._auto_download_lowest_resolution_thread, args=(selected_indices,))
        thread.daemon = True
        thread.start()
    
    def auto_download_lowest_resolution_all(self):
        """Auto-download lowest resolution for all videos"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        if not self.csv_data:
            messagebox.showwarning("Warning", "No CSV data loaded")
            return
        
        self.cancel_download = False
        self.current_process = None
        
        all_indices = list(range(len(self.csv_data)))
        self.log(f"[INFO] Starting auto-download of lowest resolution for all {len(all_indices)} videos")
        
        self.set_busy(True, f"Auto-downloading all {len(all_indices)} videos (lowest resolution)...")
        
        thread = threading.Thread(target=self._auto_download_lowest_resolution_thread, args=(all_indices,))
        thread.daemon = True
        thread.start()
    
    def _find_lowest_resolution_stream(self, formats):
        """Find video streams sorted from lowest to highest resolution
        
        Args:
            formats: List of format dictionaries from yt-dlp
            
        Returns:
            List of format_ids sorted from lowest to highest resolution, or empty list if none found
        """
        if not formats:
            return []
        
        # Filter for video streams (combined video+audio preferred, then video-only)
        video_streams = []
        for fmt in formats:
            vcodec = fmt.get('vcodec', 'none')
            if vcodec != 'none':
                # Prefer combined streams (have both video and audio)
                is_combined = fmt.get('acodec', 'none') != 'none'
                resolution = fmt.get('resolution', 'unknown')
                height = fmt.get('height', 0)
                width = fmt.get('width', 0)
                
                # Extract numeric height if resolution is like "720p" or "480p"
                if not height and resolution and resolution != 'unknown':
                    height_match = re.search(r'(\d+)p?', str(resolution))
                    if height_match:
                        height = int(height_match.group(1))
                
                video_streams.append({
                    'format_id': fmt.get('format_id'),
                    'height': height,
                    'width': width,
                    'resolution': resolution,
                    'is_combined': is_combined,
                    'format': fmt
                })
        
        if not video_streams:
            return []
        
        # Sort by height (lowest first), prefer combined streams
        video_streams.sort(key=lambda x: (x['height'] or 0, not x['is_combined']))
        
        # Return list of format_ids sorted from lowest to highest
        return [stream['format_id'] for stream in video_streams]
    
    def _auto_download_lowest_resolution_thread(self, video_indices):
        """Thread that handles auto-download of lowest resolution streams"""
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for i, index in enumerate(video_indices):
            if self.cancel_download:
                self.root.after(0, lambda: self.log("[INFO] Auto-download cancelled by user"))
                break
            
            try:
                row = self.csv_data[index]
                url = self.extract_youtube_url(row.get('Video Link', ''))
                
                if not url:
                    error_count += 1
                    self.root.after(0, lambda idx=index+1: self.log(f"[ERROR] Video {idx}: Could not extract URL"))
                    continue
                
                filename_pattern = self.filename_var.get()
                filename = self.create_filename_from_pattern(filename_pattern, row)
                
                self.root.after(
                    0,
                    lambda idx=i+1, total=len(video_indices), name=row.get('Song Title', 'Unknown'):
                    self.set_busy(True, f"Auto-downloading {idx}/{total}: {name} (fetching streams...)")
                )
                
                self.root.after(
                    0,
                    lambda msg=f"\n[INFO] Processing ({i+1}/{len(video_indices)}): {row.get('Song Title', 'Unknown')} - {row.get('Artist', 'Unknown')}":
                    self.log(msg)
                )
                
                # Fetch available streams
                cmd = self.build_ytdlp_command(['-J', url])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                # Try alternative client if 403 error
                if (result.returncode != 0 and 
                    ('403' in result.stderr or 'Forbidden' in result.stderr)):
                    self.root.after(0, lambda: self.log(f"[WARNING] 403 detected, trying alternative client..."))
                    original_client = self.client_type_var.get() if hasattr(self, 'client_type_var') else 'web'
                    if original_client != 'ios':
                        if hasattr(self, 'client_type_var'):
                            self.client_type_var.set('ios')
                        cmd = self.build_ytdlp_command(['-J', url])
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                        )
                        if hasattr(self, 'client_type_var'):
                            self.client_type_var.set(original_client)
                
                if result.returncode != 0:
                    error_count += 1
                    error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                    self.root.after(0, lambda err=error_msg, idx=index+1: self.log(f"[ERROR] Video {idx}: Failed to fetch streams - {err}"))
                    continue
                
                # Parse stream data
                try:
                    data = json.loads(result.stdout)
                    formats = data.get('formats', [])
                except json.JSONDecodeError:
                    error_count += 1
                    self.root.after(0, lambda idx=index+1: self.log(f"[ERROR] Video {idx}: Failed to parse stream data"))
                    continue
                
                # Find all video streams sorted from lowest to highest resolution
                format_ids = self._find_lowest_resolution_stream(formats)
                if not format_ids:
                    skipped_count += 1
                    self.root.after(0, lambda idx=index+1: self.log(f"[WARNING] Video {idx}: No video streams found, skipping"))
                    continue
                
                # Rotate user agent periodically
                if i > 0 and i % 5 == 0:
                    self.user_agent = self.generate_user_agent()
                    self.root.after(0, lambda: self.log(f"[DEBUG] Rotated user agent for stealth"))
                
                # Try each resolution from lowest to highest until one works
                output_path = os.path.join(self.get_download_path(), filename)
                download_success = False
                
                for attempt_idx, format_id in enumerate(format_ids):
                    if self.cancel_download:
                        break
                    
                    # Get stream info for logging
                    stream_info = next((f for f in formats if f.get('format_id') == format_id), None)
                    resolution = stream_info.get('resolution', 'unknown') if stream_info else 'unknown'
                    
                    if attempt_idx == 0:
                        self.root.after(0, lambda res=resolution, fid=format_id: self.log(f"[INFO] Trying lowest resolution: {res} (format {fid})"))
                    else:
                        self.root.after(0, lambda res=resolution, fid=format_id, att=attempt_idx+1: self.log(f"[INFO] Previous failed, trying next resolution ({att}/{len(format_ids)}): {res} (format {fid})"))
                    
                    # Try download with current format
                    cmd = self.build_ytdlp_command([
                        '-f', format_id,
                        '-o', output_path + '.%(ext)s',
                        url
                    ])
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                    
                    self.current_process = process
                    
                    stdout, stderr = process.communicate()
                    
                    if self.cancel_download:
                        try:
                            process.terminate()
                        except:
                            pass
                        self.root.after(0, lambda: self.log("[INFO] Auto-download cancelled by user"))
                        break
                    
                    if process.returncode == 0:
                        # Success! Stop trying other resolutions
                        download_success = True
                        success_count += 1
                        self.root.after(
                            0,
                            lambda out=filename, res=resolution: self.log(f"[SUCCESS] Downloaded: {out} (resolution: {res})")
                        )
                        break
                    else:
                        error_msg = stderr[:200] if stderr else "Unknown error"
                        
                        # Try with iOS client as fallback if 403
                        if '403' in error_msg or 'Forbidden' in error_msg:
                            self.root.after(0, lambda: self.log(f"[WARNING] 403 detected, trying iOS client fallback..."))
                            original_client = self.client_type_var.get() if hasattr(self, 'client_type_var') else 'web'
                            if original_client != 'ios':
                                if hasattr(self, 'client_type_var'):
                                    self.client_type_var.set('ios')
                                cmd_fallback = self.build_ytdlp_command([
                                    '-f', format_id,
                                    '-o', output_path + '.%(ext)s',
                                    url
                                ])
                                process_fallback = subprocess.run(
                                    cmd_fallback,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                                )
                                if hasattr(self, 'client_type_var'):
                                    self.client_type_var.set(original_client)
                                
                                if process_fallback.returncode == 0:
                                    # Success with fallback client!
                                    download_success = True
                                    success_count += 1
                                    self.root.after(0, lambda fname=filename, res=resolution: self.log(f"[SUCCESS] Downloaded with fallback client: {fname} (resolution: {res})"))
                                    break
                                else:
                                    # Fallback also failed, continue to next resolution
                                    self.root.after(0, lambda err=error_msg, res=resolution: self.log(f"[WARNING] Resolution {res} failed: {err[:100]}"))
                            else:
                                # Already using iOS, continue to next resolution
                                self.root.after(0, lambda err=error_msg, res=resolution: self.log(f"[WARNING] Resolution {res} failed: {err[:100]}"))
                        else:
                            # Non-403 error, continue to next resolution
                            self.root.after(0, lambda err=error_msg, res=resolution: self.log(f"[WARNING] Resolution {res} failed: {err[:100]}"))
                
                # If all resolutions failed, mark as error
                if not download_success and not self.cancel_download:
                    error_count += 1
                    self.root.after(0, lambda idx=index+1, total=len(format_ids): self.log(f"[ERROR] Video {idx}: All {total} resolutions failed, skipping"))
                
                # Add delay between downloads
                if i < len(video_indices) - 1:
                    delay = self.delay_var.get() if hasattr(self, 'delay_var') else self.download_delay
                    if delay > 0:
                        actual_delay = delay * random.uniform(0.8, 1.2)
                        time.sleep(actual_delay)
                
            except Exception as e:
                if not self.cancel_download:
                    error_count += 1
                    error_msg = str(e)
                    self.root.after(
                        0,
                        lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}")
                    )
            finally:
                self.current_process = None
        
        if not self.cancel_download:
            self.root.after(
                0,
                lambda s=success_count, e=error_count, sk=skipped_count:
                self.log(f"\n[COMPLETE] Auto-download finished: {s} succeeded, {e} failed, {sk} skipped")
            )
            
            self.root.after(
                0,
                lambda s=success_count, e=error_count, sk=skipped_count:
                messagebox.showinfo(
                    "Auto-Download Complete",
                    f"Auto-download finished!\n\nSuccessful: {s}\nFailed: {e}\nSkipped: {sk}"
                )
            )
        else:
            self.root.after(
                0,
                lambda s=success_count, e=error_count, sk=skipped_count:
                self.log(f"\n[CANCELLED] Auto-download stopped: {s} succeeded, {e} failed, {sk} skipped")
            )
        
        self.root.after(0, lambda: self.set_busy(False))
    
    # Direct Link Tab methods
    def fetch_direct_link_streams(self):
        if self.is_busy:
            return
        
        url = self.direct_link_url_var.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a YouTube URL")
            return
        
        # Extract URL if it's in markdown format or validate it
        extracted_url = self.extract_youtube_url(url)
        if not extracted_url:
            # Try to use the URL as-is (might be a search query or other format)
            extracted_url = url
        
        self.direct_link_url = extracted_url
        self.direct_link_log(f"[INFO] Fetching streams for: {extracted_url}")
        self.set_direct_link_busy(True, "Fetching available streams...")
        
        thread = threading.Thread(target=self._fetch_direct_link_streams_thread, args=(extracted_url,))
        thread.daemon = True
        thread.start()
    
    def _fetch_direct_link_streams_thread(self, url):
        try:
            cmd = self.build_ytdlp_command(['-J', url])
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if (result.returncode != 0 and 
                ('403' in result.stderr or 'Forbidden' in result.stderr) and 
                not self.use_android_client):
                self.root.after(0, lambda: self.direct_link_log("[INFO] Web client blocked, trying Android client..."))
                original_setting = self.use_android_client
                self.use_android_client = True
                cmd = self.build_ytdlp_command(['-J', url])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.use_android_client = original_setting
                if result.returncode == 0:
                    self.root.after(0, lambda: self.direct_link_log("[INFO] Consider enabling Android Client Mode in Settings to avoid 403 errors"))
            
            if result.returncode != 0:
                error_msg = result.stderr
                self.root.after(0, lambda msg=error_msg: self.direct_link_log(f"[ERROR] {msg}"))
                self.root.after(0, lambda: self.set_direct_link_busy(False))
                return
            
            data = json.loads(result.stdout)
            formats = data.get('formats', [])
            
            # Store video info
            self.direct_link_video_info = {
                'title': data.get('title', 'Unknown'),
                'uploader': data.get('uploader', 'Unknown'),
                'duration': data.get('duration', 0),
                'view_count': data.get('view_count', 0),
                'description': data.get('description', '')[:500]  # Limit description length
            }
            
            self.direct_link_streams = formats
            self.root.after(0, lambda: self.display_direct_link_streams(formats, data))
            self.root.after(0, lambda: self.set_direct_link_busy(False))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.direct_link_log(f"[ERROR] Fetching streams: {msg}"))
            self.root.after(0, lambda: self.set_direct_link_busy(False))
    
    def display_direct_link_streams(self, formats, video_data):
        self.direct_link_stream_tree.delete(*self.direct_link_stream_tree.get_children())
        self.direct_link_info_text.delete('1.0', tk.END)
        
        # Display video information
        info_text = f"Title: {video_data.get('title', 'Unknown')}\n"
        info_text += f"Uploader: {video_data.get('uploader', 'Unknown')}\n"
        duration = video_data.get('duration', 0)
        if duration:
            minutes = duration // 60
            seconds = duration % 60
            info_text += f"Duration: {minutes}:{seconds:02d}\n"
        info_text += f"Views: {video_data.get('view_count', 0):,}"
        self.direct_link_info_text.insert('1.0', info_text)
        
        # Auto-generate filename from video title
        title = video_data.get('title', 'video')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
        self.direct_link_filename_var.set(safe_title)
        
        # Display streams
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
            parent = self.direct_link_stream_tree.insert('', 'end', text='Video + Audio', open=True)
            for fmt in combined:
                self._insert_direct_link_format(parent, fmt)
        
        if video_only:
            parent = self.direct_link_stream_tree.insert('', 'end', text='Video Only', open=False)
            for fmt in video_only:
                self._insert_direct_link_format(parent, fmt)
        
        if audio_only:
            parent = self.direct_link_stream_tree.insert('', 'end', text='Audio Only', open=False)
            for fmt in audio_only:
                self._insert_direct_link_format(parent, fmt)
        
        self.direct_link_log(f"[SUCCESS] Found {len(formats)} streams ({len(combined)} combined, {len(video_only)} video, {len(audio_only)} audio)")
    
    def _insert_direct_link_format(self, parent, fmt):
        format_id = fmt.get('format_id', 'N/A')
        ext = fmt.get('ext', 'N/A')
        resolution = fmt.get('resolution', 'N/A')
        fps = str(fmt.get('fps', 'N/A'))
        filesize = self._format_filesize(fmt.get('filesize') or fmt.get('filesize_approx'))
        acodec = fmt.get('acodec', 'none')
        vcodec = fmt.get('vcodec', 'none')
        
        self.direct_link_stream_tree.insert(
            parent, 'end',
            values=(format_id, ext, resolution, fps, filesize, acodec, vcodec),
            tags=(format_id,)
        )
    
    def download_direct_link_stream(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        selection = self.direct_link_stream_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a stream to download")
            return
        
        if not self.direct_link_url:
            messagebox.showerror("Error", "No URL available")
            return
        
        item = selection[0]
        format_id = str(self.direct_link_stream_tree.item(item)['values'][0])
        
        filename = self.direct_link_filename_var.get().strip()
        if not filename:
            filename = "video"
        
        self.cancel_download = False
        self.current_process = None
        
        self.direct_link_log(f"[INFO] Starting download: Format {format_id}")
        self.direct_link_log(f"[INFO] Output file: {filename}")
        self.set_direct_link_busy(True, "Downloading...")
        
        thread = threading.Thread(target=self._download_direct_link_thread, args=(self.direct_link_url, format_id, filename))
        thread.daemon = True
        thread.start()
    
    def _download_direct_link_thread(self, url, format_id, filename):
        try:
            if self.cancel_download:
                self.root.after(0, lambda: self.direct_link_log("[INFO] Download cancelled"))
                self.root.after(0, lambda: self.set_direct_link_busy(False))
                return
            
            output_path = os.path.join(self.file_manager.get_folder_path('downloads'), filename)
            
            cmd = self.build_ytdlp_command([
                '-f', format_id,
                '-o', output_path + '.%(ext)s',
                url
            ])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            self.current_process = process
            
            for line in process.stdout:
                if self.cancel_download:
                    process.terminate()
                    self.root.after(0, lambda: self.direct_link_log("[INFO] Download cancelled by user"))
                    self.root.after(0, lambda: self.set_direct_link_busy(False))
                    return
                
                line_text = line.strip()
                if line_text:
                    self.root.after(0, lambda l=line_text: self.direct_link_log(l))
            
            process.wait()
            
            if self.cancel_download:
                self.root.after(0, lambda: self.direct_link_log("[INFO] Download cancelled"))
                self.root.after(0, lambda: self.set_direct_link_busy(False))
                return
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.direct_link_log("[SUCCESS] Download completed successfully!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
                self.root.after(0, lambda: self.set_direct_link_busy(False))
            else:
                self.root.after(0, lambda: self.direct_link_log("[ERROR] Download failed!"))
                self.root.after(0, lambda: self.set_direct_link_busy(False))
                
        except Exception as e:
            if not self.cancel_download:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: self.direct_link_log(f"[ERROR] Download error: {msg}"))
            self.root.after(0, lambda: self.set_direct_link_busy(False))
        finally:
            self.current_process = None
    
    def set_direct_link_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.direct_link_progress.start(10)
            self.direct_link_progress_label.config(text=message)
            self.direct_link_cancel_button.config(state='normal')
        else:
            self.root.config(cursor="")
            self.direct_link_progress.stop()
            self.direct_link_progress_label.config(text="")
            self.direct_link_cancel_button.config(state='disabled')
    
    def direct_link_log(self, message):
        self.direct_link_log_text.insert(tk.END, f"{message}\n")
        self.direct_link_log_text.see(tk.END)
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)


def main():
    auto_load_csv = None
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        if os.path.isfile(csv_path):
            auto_load_csv = csv_path
        else:
            print(f"[WARNING] CSV file not found: {csv_path}")
    
    root = tk.Tk()
    app = YouTubeDownloaderGUI(root, auto_load_csv=auto_load_csv)
    
    if auto_load_csv:
        print(f"[INFO] Auto-loading CSV file: {auto_load_csv}")
    
    root.mainloop()


if __name__ == '__main__':
    main()

