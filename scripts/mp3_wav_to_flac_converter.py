"""
MP3/WAV to FLAC Converter - Individual Application

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


class MP3WAVToFLACConverterGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "MP3/WAV to FLAC Converter")
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
        
        ttk.Button(btn_frame, text="Select MP3/WAV Files", command=self.select_files).pack(side='left', padx=5)
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
        
        ttk.Label(settings_frame, text="Input Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.input_folder_var = tk.StringVar(value=self.file_manager.get_folder_path('converted'))
        ttk.Entry(settings_frame, textvariable=self.input_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_input_folder).grid(row=0, column=2)
        
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.grid(row=1, column=0, columnspan=3, sticky='w', pady=5)
        ttk.Label(quality_frame, text="Output Format:", font=('Arial', 9, 'bold')).pack(side='left')
        self.output_format_var = tk.StringVar(value='FLAC')
        self.output_format_combo = ttk.Combobox(
            quality_frame, textvariable=self.output_format_var,
            values=['FLAC', 'WAV', 'MP3'], width=10, state='readonly'
        )
        self.output_format_combo.pack(side='left', padx=5)
        self.output_format_combo.set('FLAC')
        ttk.Label(quality_frame, text="(44.1 kHz)", font=('Arial', 8)).pack(side='left', padx=2)

        extract_frame = ttk.Frame(settings_frame)
        extract_frame.grid(row=2, column=0, columnspan=3, sticky='w', pady=5)
        self.extract_enabled_var = tk.BooleanVar(value=False)
        self.extract_check = ttk.Checkbutton(
            extract_frame, text="Extract first", variable=self.extract_enabled_var,
            command=self._toggle_extract_minutes
        )
        self.extract_check.pack(side='left')
        self.extract_minutes_var = tk.StringVar(value='1')
        self.extract_minutes_combo = ttk.Combobox(
            extract_frame, textvariable=self.extract_minutes_var,
            values=['1', '2', '3', '4', '5'], width=4, state='readonly'
        )
        self.extract_minutes_combo.pack(side='left', padx=5)
        self.extract_minutes_combo.set('1')
        ttk.Label(extract_frame, text="minutes").pack(side='left', padx=2)
        self._toggle_extract_minutes()
        
        info_frame_settings = ttk.Frame(settings_frame)
        info_frame_settings.grid(row=3, column=0, columnspan=3, sticky='w', pady=5)
        ttk.Label(info_frame_settings, text="Output files will be saved in the same folder as input files", font=('Arial', 8)).pack(side='left')
        
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
        
        info_text = "Supported formats: MP3, WAV | Output: FLAC, WAV or MP3 (44.1 kHz) saved in same folder | Optional: extract first 1-5 minutes | Requires FFmpeg installed"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
    
    def set_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            self.progress_label.config(text="")
    
    def _toggle_extract_minutes(self):
        """Enable or disable the minutes selector based on checkbox state."""
        enabled = self.extract_enabled_var.get()
        if enabled:
            self.extract_minutes_combo.config(state='readonly')
        else:
            self.extract_minutes_combo.config(state='disabled')
    
    def browse_input_folder(self):
        folder = super().browse_folder(self.input_folder_var.get())
        if folder:
            self.input_folder_var.set(folder)
            self.file_manager.set_folder_path('converted', folder)
    
    def select_files(self):
        files = super().select_files(
            title="Select MP3/WAV Files",
            filetypes=[("Audio Files", "*.mp3 *.wav"), ("MP3 Files", "*.mp3"), ("WAV Files", "*.wav"), ("All Files", "*.*")],
            initial_dir=self.input_folder_var.get()
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
        # Accept MP3 and WAV input types
        allowed_ext = {'.mp3', '.wav'}
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
            messagebox.showwarning("Warning", "Please select at least one MP3 or WAV file")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        self.conversion_queue = self.selected_files.copy()
        self.current_index = 0
        
        # Capture settings for use in conversion thread
        self._conversion_format = self.output_format_var.get().upper()
        if self._conversion_format not in ('FLAC', 'WAV', 'MP3'):
            self._conversion_format = 'FLAC'
        extract_enabled = self.extract_enabled_var.get()
        extract_minutes = 0
        if extract_enabled:
            try:
                extract_minutes = int(self.extract_minutes_var.get())
                if extract_minutes < 1 or extract_minutes > 5:
                    extract_minutes = 1
            except (ValueError, TypeError):
                extract_minutes = 1
        self._extract_seconds = extract_minutes * 60 if extract_minutes else 0
        
        format_desc = f"{self._conversion_format} 44.1 kHz"
        if self._conversion_format == 'FLAC':
            format_desc += " (lossless)"
        elif self._conversion_format == 'MP3':
            format_desc += " (320 kbps)"
        self.log(f"[INFO] Starting conversion of {len(self.conversion_queue)} file(s) to {self._conversion_format}")
        self.log(f"[INFO] Output files will be saved in the same folder as input files")
        self.log(f"[INFO] Output format: {format_desc}")
        if self._extract_seconds:
            self.log(f"[INFO] Extracting first {self._extract_seconds // 60} minute(s)")
        
        self.progress['maximum'] = len(self.conversion_queue)
        self.progress['value'] = 0
        
        self.set_busy(True, "Converting...")
        
        thread = threading.Thread(target=self._conversion_thread)
        thread.daemon = True
        thread.start()
    
    def _conversion_thread(self):
        success_count = 0
        error_count = 0
        
        if self._conversion_format == 'FLAC':
            out_ext = '.flac'
        elif self._conversion_format == 'WAV':
            out_ext = '.wav'
        else:
            out_ext = '.mp3'
        
        for i, input_file in enumerate(self.conversion_queue):
            self.current_index = i + 1
            
            input_path = Path(input_file)
            basename = input_path.stem
            if self._extract_seconds:
                minutes = self._extract_seconds // 60
                basename = f"{basename}_{minutes}min"
            output_file = os.path.join(input_path.parent, f"{basename}{out_ext}")
            
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
                ffmpeg_path = self.get_ffmpeg_command()
                cmd = [ffmpeg_path, '-i', str(input_file)]
                if self._extract_seconds:
                    cmd.extend(['-t', str(self._extract_seconds)])
                cmd.extend([
                    '-vn',  # No video
                    '-ar', '44100',  # Sample rate: 44.1 kHz
                    '-ac', '2',  # Channels: stereo
                ])
                if self._conversion_format == 'FLAC':
                    cmd.extend([
                        '-acodec', 'flac',
                        '-compression_level', '5',
                    ])
                elif self._conversion_format == 'WAV':
                    cmd.extend(['-acodec', 'pcm_s16le'])
                else:
                    cmd.extend([
                        '-acodec', 'libmp3lame',
                        '-b:a', '320k',
                    ])
                cmd.extend(['-y', str(output_file)])
                
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
        """Convert all MP3/WAV files in the input folder"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Conversion already in progress")
            return
        
        input_folder = self.input_folder_var.get()
        if not os.path.exists(input_folder):
            messagebox.showerror("Error", "Input folder does not exist")
            return
        
        # Find all MP3 and WAV files in input folder
        audio_extensions = ['.mp3', '.wav']
        all_files = []
        
        for file in os.listdir(input_folder):
            file_path = os.path.join(input_folder, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in audio_extensions:
                    all_files.append(file_path)
        
        if not all_files:
            messagebox.showwarning("Warning", "No MP3 or WAV files found in input folder")
            return
        
        # Update the selected files list
        self.selected_files = all_files
        self.update_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} MP3/WAV files in input folder")
        
        # Start conversion with all files
        self.start_conversion()
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)


def main():
    root = TkinterDnD.Tk()
    app = MP3WAVToFLACConverterGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
