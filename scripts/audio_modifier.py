"""
Audio Modifier - Individual Application

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


class AudioModifierGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Audio Modifier")
        self.root.geometry("800x750")
        
        self.selected_files = []
        self.modification_queue = []
        self.current_index = 0
        
        self.setup_ui()
    
    def setup_ui(self):
        top_frame = ttk.LabelFrame(self.root, text="File Selection", padding=10)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select Audio Files", command=self.select_files).pack(side='left', padx=5)
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
            height=8,
            selectmode=tk.EXTENDED
        )
        
        scrollbar_y.config(command=self.file_listbox.yview)
        scrollbar_x.config(command=self.file_listbox.xview)
        
        self.file_listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Drag-and-drop support for adding audio files
        try:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self.on_drop_files)
        except Exception:
            pass
        
        settings_frame = ttk.LabelFrame(self.root, text="Modification Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Converted Folder:").grid(row=0, column=0, sticky='w', pady=5)
        self.converted_folder_var = tk.StringVar(value=self.file_manager.get_folder_path('converted'))
        ttk.Entry(settings_frame, textvariable=self.converted_folder_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_converted_folder).grid(row=0, column=2)
        
        ttk.Label(settings_frame, text="Output Folder:").grid(row=1, column=0, sticky='w', pady=5)
        self.folder_var = tk.StringVar(value=self.file_manager.get_folder_path('output'))
        ttk.Entry(settings_frame, textvariable=self.folder_var, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(settings_frame, text="Browse", command=self.browse_output_folder).grid(row=1, column=2)
        
        ttk.Label(settings_frame, text="Speed Adjustment (%):").grid(row=2, column=0, sticky='w', pady=5)
        speed_frame = ttk.Frame(settings_frame)
        speed_frame.grid(row=2, column=1, sticky='w', padx=5)
        self.speed_var = tk.StringVar(value="0")
        speed_spinbox = ttk.Spinbox(speed_frame, textvariable=self.speed_var, from_=-50, to=100, width=10, increment=5)
        speed_spinbox.pack(side='left')
        ttk.Label(speed_frame, text=" (-50% to +100%, 0 = no change)").pack(side='left', padx=5)
        
        ttk.Label(settings_frame, text="Pitch Adjustment (semitones):").grid(row=3, column=0, sticky='w', pady=5)
        pitch_frame = ttk.Frame(settings_frame)
        pitch_frame.grid(row=3, column=1, sticky='w', padx=5)
        self.pitch_var = tk.StringVar(value="0")
        pitch_spinbox = ttk.Spinbox(pitch_frame, textvariable=self.pitch_var, from_=-12, to=12, width=10, increment=1)
        pitch_spinbox.pack(side='left')
        ttk.Label(pitch_frame, text=" (-12 to +12 semitones, 0 = no change)").pack(side='left', padx=5)
        
        ttk.Label(settings_frame, text="Audio Quality:").grid(row=4, column=0, sticky='w', pady=5)
        self.quality_var = tk.StringVar(value="192k")
        quality_combo = ttk.Combobox(settings_frame, textvariable=self.quality_var, width=20, state='readonly')
        quality_combo['values'] = ('128k', '192k', '256k', '320k')
        quality_combo.grid(row=4, column=1, sticky='w', padx=5)
        
        preset_frame = ttk.LabelFrame(self.root, text="Quick Presets", padding=10)
        preset_frame.pack(fill='x', padx=10, pady=10)
        
        btn_preset_frame = ttk.Frame(preset_frame)
        btn_preset_frame.pack(fill='x')
        
        ttk.Button(btn_preset_frame, text="Slower -10%", command=lambda: self.apply_preset(-10, 0)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Faster +10%", command=lambda: self.apply_preset(10, 0)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Pitch -1", command=lambda: self.apply_preset(0, -1)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Pitch +1", command=lambda: self.apply_preset(0, 1)).pack(side='left', padx=2)
        ttk.Button(btn_preset_frame, text="Reset", command=lambda: self.apply_preset(0, 0)).pack(side='left', padx=2)
        
        modify_frame = ttk.Frame(self.root)
        modify_frame.pack(fill='x', padx=10, pady=10)
        
        # Batch processing buttons
        batch_frame = ttk.Frame(modify_frame)
        batch_frame.pack(fill='x', pady=5)
        
        ttk.Button(batch_frame, text="Modify Selected Files", command=self.start_modification).pack(side='left', padx=5)
        ttk.Button(batch_frame, text="Modify All Files", command=self.modify_all_files).pack(side='left', padx=5)
        
        self.progress = ttk.Progressbar(modify_frame, mode='determinate')
        self.progress.pack(fill='x', pady=5)
        
        self.progress_label = ttk.Label(modify_frame, text="")
        self.progress_label.pack(anchor='w')
        
        log_frame = ttk.LabelFrame(self.root, text="Modification Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12)
        self.log_text.pack(fill='both', expand=True)
        
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = "Supported formats: MP3, M4A, WAV, OGG, FLAC | Speed: +/- tempo | Pitch: semitones | Requires FFmpeg"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
    
    def apply_preset(self, speed, pitch):
        self.speed_var.set(str(speed))
        self.pitch_var.set(str(pitch))
        self.log(f"[INFO] Applied preset: Speed {speed:+d}%, Pitch {pitch:+d} semitones")
    
    def set_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            self.progress_label.config(text="")
    
    def browse_converted_folder(self):
        folder = super().browse_folder(self.converted_folder_var.get())
        if folder:
            self.converted_folder_var.set(folder)
            self.file_manager.set_folder_path('converted', folder)
    
    def browse_output_folder(self):
        folder = super().browse_folder(self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.file_manager.set_folder_path('output', folder)
    
    def select_files(self):
        files = super().select_files(
            title="Select Audio Files",
            filetypes=self.file_manager.get_audio_filetypes(),
            initial_dir=self.converted_folder_var.get()
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
        paths = self._parse_dropped_paths(event.data)
        allowed_ext = {'.mp3', '.m4a', '.wav', '.ogg', '.flac'}
        added = 0
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in allowed_ext and p not in self.selected_files:
                self.selected_files.append(p)
                added += 1
        if added:
            self.update_file_list()
            self.log(f"[INFO] Added {added} audio file(s) via drag and drop")
    
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
    
    def start_modification(self):
        if self.is_busy:
            messagebox.showwarning("Warning", "Modification already in progress")
            return
        
        if not self.selected_files:
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
        
        self.file_manager.set_folder_path('output', self.folder_var.get())
        self.ensure_directory(self.file_manager.get_folder_path('output'))
        
        self.modification_queue = self.selected_files.copy()
        self.current_index = 0
        
        self.log(f"[INFO] Starting modification of {len(self.modification_queue)} file(s)")
        self.log(f"[INFO] Output folder: {self.file_manager.get_folder_path('output')}")
        self.log(f"[INFO] Speed: {speed_percent:+.1f}%, Pitch: {pitch_semitones:+.1f} semitones")
        self.log(f"[INFO] Audio quality: {self.quality_var.get()}")
        
        self.progress['maximum'] = len(self.modification_queue)
        self.progress['value'] = 0
        
        self.set_busy(True, "Modifying...")
        
        thread = threading.Thread(target=self._modification_thread, args=(speed_percent, pitch_semitones))
        thread.daemon = True
        thread.start()
    
    def _modification_thread(self, speed_percent, pitch_semitones):
        success_count = 0
        error_count = 0
        
        for i, input_file in enumerate(self.modification_queue):
            self.current_index = i + 1
            
            input_path = Path(input_file)
            basename = input_path.stem
            extension = input_path.suffix
            
            suffix_parts = []
            if speed_percent != 0:
                suffix_parts.append(f"speed{speed_percent:+.0f}pct")
            if pitch_semitones != 0:
                suffix_parts.append(f"pitch{pitch_semitones:+.0f}st")
            
            suffix = "_" + "_".join(suffix_parts) if suffix_parts else "_modified"
            output_file = os.path.join(self.file_manager.get_folder_path('output'), f"{basename}{suffix}{extension}")
            
            self.root.after(
                0,
                lambda idx=i+1, total=len(self.modification_queue), name=input_path.name:
                self.set_busy(True, f"Modifying {idx}/{total}: {name}")
            )
            
            self.root.after(
                0,
                lambda msg=f"\n[INFO] Modifying ({i+1}/{len(self.modification_queue)}): {input_path.name}":
                self.log(msg)
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
                    audio_bitrate=self.quality_var.get()
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
                        self.log(f"[ERROR] Modification failed: {err[:200]}")
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
            self.log(f"\n[COMPLETE] Modification finished: {s} succeeded, {e} failed")
        )
        
        self.root.after(
            0,
            lambda s=success_count, e=error_count:
            messagebox.showinfo(
                "Modification Complete",
                f"Modification finished!\n\nSuccessful: {s}\nFailed: {e}"
            )
        )
        
        self.root.after(0, lambda: self.set_busy(False))
    
    def modify_all_files(self):
        """Modify all files in the converted folder"""
        if self.is_busy:
            messagebox.showwarning("Warning", "Modification already in progress")
            return
        
        converted_folder = self.converted_folder_var.get()
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
        self.selected_files = all_files
        self.update_file_list()
        
        self.log(f"[INFO] Found {len(all_files)} audio files in converted folder")
        
        # Start modification with all files
        self.start_modification()
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)


def main():
    root = TkinterDnD.Tk()
    app = AudioModifierGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

