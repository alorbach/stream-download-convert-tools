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
from pathlib import Path

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI


class YouTubeDownloaderGUI(BaseAudioGUI):
    def __init__(self, root, auto_load_csv=None):
        super().__init__(root, "YouTube Downloader")
        self.root.geometry("900x750")
        
        self.csv_file = None
        self.csv_data = []
        self.available_streams = []
        self.current_video_info = None
        
        self.setup_ui()
        
        if auto_load_csv and os.path.isfile(auto_load_csv):
            self.root.after(100, lambda: self.load_csv_file(auto_load_csv))
    
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tab_load = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_load, text="Load CSV")
        self.notebook.add(self.tab_download, text="Download Videos")
        self.notebook.add(self.tab_settings, text="Settings")
        
        self.setup_load_tab()
        self.setup_download_tab()
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
        
        self.log_text = scrolledtext.ScrolledText(bottom_frame, height=8)
        self.log_text.pack(fill='both', expand=True)
    
    def setup_settings_tab(self):
        frame = ttk.LabelFrame(self.tab_settings, text="Download Settings", padding=10)
        frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(frame, text="Download Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.folder_var = tk.StringVar(value=self.file_manager.get_folder_path('downloads'))
        ttk.Entry(frame, textvariable=self.folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="Browse", command=self.browse_folder).grid(row=0, column=2)
        
        ttk.Label(frame, text="Filename Pattern:").grid(row=1, column=0, sticky='w', pady=5)
        self.filename_var = tk.StringVar(value="{Rank}_{Song Title}_{Artist}")
        ttk.Entry(frame, textvariable=self.filename_var, width=50).grid(row=1, column=1, padx=5, columnspan=2)
        
        ttk.Label(frame, text="Available fields: {Rank}, {Song Title}, {Artist}, {Year}, {Views (Billions)}").grid(
            row=2, column=0, columnspan=3, sticky='w', pady=5
        )
        
        info_frame = ttk.LabelFrame(self.tab_settings, text="Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        info_text = """YouTube Downloader with GUI

Features:
- Load CSV files with YouTube links
- View available video/audio streams
- Select specific quality and format
- Download with custom filenames based on CSV fields
- Automatic venv management via launcher scripts

Instructions:
1. Load a CSV file containing YouTube links
2. Select a video from the list
3. Fetch available streams
4. Choose your preferred stream (video+audio, video only, or audio only)
5. Download to the configured folder

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
        else:
            self.root.config(cursor="")
            self.progress.stop()
            self.progress_label.config(text="")
    
    def browse_folder(self):
        folder = super().browse_folder(self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.file_manager.set_folder_path('downloads', folder)
    
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
            self.lbl_csv_status.config(text=f"Loaded: {os.path.basename(file_path)} ({len(self.csv_data)} rows)")
            
            self.display_csv_in_grid()
            self.populate_video_list()
            
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
    
    def extract_youtube_url(self, text):
        if not text:
            return None
        
        self.log(f"[DEBUG] Extracting URL from: {text[:100]}...")
        
        markdown_pattern = r'\[(https://www\.youtube\.com/watch\?v=[\w-]+)\]\(https://www\.youtube\.com/watch\?v=[\w-]+\)'
        match = re.search(markdown_pattern, text)
        if match:
            url = match.group(1)
            self.log(f"[DEBUG] Extracted URL (markdown): {url}")
            return url
        
        url_pattern = r'https://www\.youtube\.com/watch\?v=[\w-]+'
        match = re.search(url_pattern, text)
        if match:
            url = match.group(0)
            self.log(f"[DEBUG] Extracted URL (plain): {url}")
            return url
        
        self.log(f"[ERROR] No URL pattern matched in text")
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
            result = subprocess.run(
                ['yt-dlp', '-J', url],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
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
        
        self.log(f"[INFO] Starting download: Format {format_id}")
        self.log(f"[INFO] Output file: {filename}")
        self.set_busy(True, "Downloading...")
        
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
                    self.root.after(0, lambda l=line_text: self.log(l))
            
            process.wait()
            
            if process.returncode == 0:
                self.root.after(0, lambda: self.log("[SUCCESS] Download completed successfully!"))
                self.root.after(0, lambda: messagebox.showinfo("Success", "Download completed!"))
                self.root.after(0, lambda: self.set_busy(False))
            else:
                self.root.after(0, lambda: self.log("[ERROR] Download failed!"))
                self.root.after(0, lambda: self.set_busy(False))
                
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Download error: {msg}"))
            self.root.after(0, lambda: self.set_busy(False))
    
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
                        lambda out=filename: self.log(f"[SUCCESS] Downloaded: {out}")
                    )
                else:
                    error_count += 1
                    error_msg = process.stderr if process.stderr else "Unknown error"
                    self.root.after(
                        0,
                        lambda err=error_msg: self.log(f"[ERROR] Download failed: {err[:200]}")
                    )
                
            except Exception as e:
                error_count += 1
                error_msg = str(e)
                self.root.after(
                    0,
                    lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}")
                )
        
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
        
        self.root.after(0, lambda: self.set_busy(False))
    
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

