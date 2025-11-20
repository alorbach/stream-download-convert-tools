"""
Video to MP3 Converter - Individual Application

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
from pathlib import Path

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI


class VideoToMP3ConverterGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Video to MP3 Converter")
        self.root.geometry("800x700")
        
        self.selected_files = []
        self.conversion_queue = []
        self.current_index = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        top_frame = ttk.LabelFrame(self.root, text="File Selection", padding=10)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select Video Files", command=self.select_files).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Selection", command=self.clear_selection).pack(side='left', padx=5)
        
        self.lbl_status = ttk.Label(btn_frame, text="No files selected")
        self.lbl_status.pack(side='left', padx=10)
        
        ttk.Label(top_frame, text="Selected Files:").pack(anchor='w', pady=(10, 5))
        
        list_frame = ttk.Frame(top_frame)
        list_frame.pack(fill='both', expand=True)
        
        scrollbar_y = ttk.Scrollbar(list_frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(list_frame, orient='horizontal')
        
        self.file_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=10,
            selectmode=tk.EXTENDED
        )
        
        scrollbar_y.config(command=self.file_listbox.yview)
        scrollbar_x.config(command=self.file_listbox.xview)
        
        self.file_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Drag-and-drop support for adding files
        try:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self.on_drop_files)
        except Exception:
            # If DnD not available, silently ignore
            pass
        
        settings_frame = ttk.LabelFrame(self.root, text="Conversion Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Downloads Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.downloads_folder_var = tk.StringVar(value=self.file_manager.get_folder_path('downloads'))
        ttk.Entry(settings_frame, textvariable=self.downloads_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_downloads_folder).grid(row=0, column=2)
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=1, column=0, sticky='w', pady=5)
        self.folder_var = tk.StringVar(value=self.file_manager.get_folder_path('converted'))
        ttk.Entry(settings_frame, textvariable=self.folder_var, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_output_folder).grid(row=1, column=2)
        
        ttk.Label(settings_frame, text="Audio Quality:").grid(row=2, column=0, sticky='w', pady=5)
        self.quality_var = tk.StringVar(value="192k")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.quality_var, width=20, state='readonly')
        quality_combo['values'] = ('128k', '192k', '256k', '320k')
        quality_combo.grid(row=2, column=1, sticky='w', padx=5)
        
        convert_frame = ttk.Frame(self.root)
        convert_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(convert_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Convert Selected Files", command=self.start_conversion).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Convert All Files", command=self.convert_all_files).pack(side='left', padx=5)
        
        self.progress = ttk.Progressbar(convert_frame, mode='determinate')
        self.progress.pack(fill='x', pady=5)
        
        self.progress_label = ttk.Label(convert_frame, text="")
        self.progress_label.pack(anchor='w')
        
        log_frame = ttk.LabelFrame(self.root, text="Conversion Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12)
        self.log_text.pack(fill='both', expand=True)
        
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = "Supported formats: MP4, WEBM, M4A, AVI, MOV, MKV, FLV, WMV | Requires FFmpeg installed"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
    
    def set_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            self.progress_label.config(text="")
    
    def browse_downloads_folder(self):
        folder = super().browse_folder(self.downloads_folder_var.get())
        if folder:
            self.downloads_folder_var.set(folder)
            self.file_manager.set_folder_path('downloads', folder)
    
    def browse_output_folder(self):
        folder = super().browse_folder(self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.file_manager.set_folder_path('converted', folder)
    
    def select_files(self):
        files = super().select_files(
            title="Select Video/Audio Files",
            filetypes=self.file_manager.get_video_filetypes(),
            initial_dir=self.downloads_folder_var.get()
        )
        
        if files:
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
            
            self.update_file_list()
            self.log(f"[INFO] Added {len(files)} file(s) to selection")
    
    def clear_selection(self):
        self.selected_files.clear()
        self.update_file_list()
        self.log("[INFO] Selection cleared")
    
    def update_file_list(self):
        self.file_listbox.delete(0, tk.END)
        
        for file in self.selected_files:
            filename = os.path.basename(file)
            self.file_listbox.insert(tk.END, filename)
        
        count = len(self.selected_files)
        self.lbl_status.config(text=f"{count} file(s) selected")

    def _parse_dropped_paths(self, data):
        """Parse dropped file list from DND event data (supports {path with spaces})."""
        import re
        if not data:
            return []
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
        return paths

    def on_drop_files(self, event):
        """Handle files dropped onto the listbox."""
        paths = self._parse_dropped_paths(event.data)
        # Accept video/audio input types supported by this tool
        allowed_ext = {'.mp4', '.webm', '.m4a', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        added = 0
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in allowed_ext and p not in self.selected_files:
                self.selected_files.append(p)
                added += 1
        if added:
            self.update_file_list()
            self.log(f"[INFO] Added {added} file(s) via drag and drop")
    
    def check_ffmpeg(self):
        return super().check_ffmpeg()
    
    def offer_ffmpeg_install(self):
        return super().offer_ffmpeg_install()
    
    def download_ffmpeg_windows(self):
        self.set_busy(True, "Downloading FFmpeg...")
        
        def progress_callback(message):
            self.root.after(0, lambda msg=message: self.log(f"[INFO] {msg}"))
        
        def success_callback(message):
            self.root.after(0, lambda msg=message: self.log("[SUCCESS] FFmpeg installed successfully!"))
            self.root.after(0, lambda msg=message: self.show_message("info", "Success", msg))
            self.root.after(0, lambda: self.set_busy(False))
        
        def error_callback(message):
            self.root.after(0, lambda msg=message: self.log(f"[ERROR] FFmpeg download failed: {msg}"))
            self.root.after(0, lambda msg=message: self.show_message("error", "Download Failed", msg))
            self.root.after(0, lambda: self.set_busy(False))
        
        super().download_ffmpeg_windows(progress_callback, success_callback, error_callback)
    
    def start_conversion(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        if not self.selected_files:
            messagebox.showwarning("Warning", "Please select at least one video file")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        self.file_manager.set_folder_path('converted', self.folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('converted'))
        
        self.conversion_queue = self.selected_files.copy()
        self.current_index = 0
        
        self.log(f"[INFO] Starting conversion of {len(self.conversion_queue)} file(s)")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('converted')}")
        self.log(f"[INFO] Audio quality: {self.quality_var.get()}")
        
        self.progress['maximum'] = len(self.conversion_queue)
        self.progress['value'] = 0
        
        self.set_busy(True, "Converting...")
        
        thread = threading.Thread(target=self._conversion_thread)
        thread.daemon = True
        thread.start()
    
    def _conversion_thread(self):
        success_count = 0
        error_count = 0
        
        for i, input_file in enumerate(self.conversion_queue):
            self.current_index = i + 1
            
            input_path = Path(input_file)
            basename = input_path.stem
            output_file = os.path.join(self.file_manager.get_folder_path('converted'), f"{basename}.mp3")
            
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
                cmd = self.build_ffmpeg_command(
                    input_file, output_file,
                    audio_codec='mp3', audio_bitrate=self.quality_var.get()
                )
                
                process = self.run_ffmpeg_command(cmd)
                
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
                        self.log(f"[ERROR] Conversion failed: {err[:200]}")
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
    
    def convert_all_files(self):
        """Convert all files in the downloads folder"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        downloads_folder = self.downloads_folder_var.get()
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
        self.selected_files = all_files
        self.update_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} video files in downloads folder")
        
        # Start conversion with all files
        self.start_conversion()
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)


def main():
    root = TkinterDnD.Tk()
    app = VideoToMP3ConverterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

