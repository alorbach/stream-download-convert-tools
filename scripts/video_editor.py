"""
Video Editor with Drag-and-Drop Grid

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
import os
import sys
import threading
import subprocess
import json
import hashlib
import random
from pathlib import Path
from PIL import Image, ImageTk

# Try to import cv2 for video preview
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[WARNING] OpenCV not available. Install with: pip install opencv-python")

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("[WARNING] tkinterdnd2 not available. Drag-and-drop from Explorer will not work.")
    print("[INFO] Install with: pip install tkinterdnd2")

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI
from lib.file_utils import FileManager
from lib.process_utils import ProcessManager
from lib.ffmpeg_utils import FFmpegManager


class VideoEditorGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Video Editor")
        self.root.geometry("1280x800")
        
        # Video list (ordered)
        self.video_files = []
        
        # Grid layout dimensions
        self.grid_cols = 5
        
        # Auto-export last frame option (default: False)
        self.auto_export_enabled = False
        self.auto_export_var = None  # Will be initialized in setup_ui()
        
        # Transition settings
        self.transition_enabled = False
        self.transition_type = "fade"  # Legacy single type (for backward compatibility)
        self.selected_transition_types = ["fade"]  # List of selected transition types for randomization
        self.transition_duration = 0.5  # Duration in seconds
        
        # Output video size settings
        self.output_width = None  # None means use first video's width
        self.output_height = None  # None means use first video's height
        self.use_first_video_size = True  # Default: use first video's size
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
        self.settings_file = os.path.join(self.root_dir, "video_editor_settings.json")
        
        # UI state
        self.drag_start_index = None
        self.drag_current_index = None
        
        # Check FFmpeg availability first
        self.check_ffmpeg()
        
        self.setup_ui()
        self.load_settings()
        # Update labels after UI is created
        if hasattr(self, 'transition_selection_label'):
            self.update_transition_selection_label()
        if hasattr(self, 'output_size_label'):
            self.update_output_size_label()
        self.check_ffmpeg_availability()
    
    def _escape_for_concat(self, file_path: str) -> str:
        """Return a POSIX-style path with quotes escaped for ffmpeg concat demuxer."""
        # Normalize to absolute POSIX path to avoid backslash escaping issues on Windows
        posix_path = Path(file_path).resolve().as_posix()
        # Escape single quotes per ffmpeg concat demuxer rules: 'path'with'quote' becomes 'path'\''with'\''quote'
        # This means: close quote, escaped quote, open quote
        return posix_path.replace("'", r"'\''")

    def _write_concat_file_for_batch(self, video_files) -> str:
        """Write concat file for a specific batch of videos."""
        concat_file = os.path.join(self.root_dir, f"temp_concat_{hashlib.md5(str(video_files).encode()).hexdigest()[:8]}.txt")
        with open(concat_file, 'w', encoding='utf-8', newline='\n') as f:
            for vf in video_files:
                if not os.path.isfile(vf):
                    continue
                safe_path = self._escape_for_concat(vf)
                f.write(f"file '{safe_path}'\n")
        return concat_file
    
    def _write_concat_file(self) -> str:
        """Write concat list file with proper escaping and return its path."""
        concat_file = os.path.join(self.root_dir, 'temp_concat.txt')
        lines_written = []
        with open(concat_file, 'w', encoding='utf-8', newline='\n') as f:
            for video_file in self.video_files:
                if not os.path.isfile(video_file):
                    self.log(f"[WARNING] File not found, skipping in concat: {video_file}")
                    continue
                safe_path = self._escape_for_concat(video_file)
                line = f"file '{safe_path}'\n"
                f.write(line)
                lines_written.append(line.strip())
        # Log concat file diagnostics (first few lines)
        preview_lines = lines_written[:4]
        self.log(f"[DEBUG] Concat file: {concat_file}")
        for l in preview_lines:
            self.log(f"[DEBUG] Concat line: {l}")
        return concat_file
    
    def _get_video_duration(self, video_file):
        """Get video duration in seconds."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
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
    
    def _get_video_resolution(self, video_file):
        """Get video resolution (width, height) from video file."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            probe_cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
            
            for line in probe_result.stderr.split('\n'):
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
            self.log(f"[WARNING] Could not get resolution for {os.path.basename(video_file)}: {e}")
            return None, None
    
    def _get_output_resolution(self, video_files):
        """Get output resolution - either configured or from first video."""
        if self.use_first_video_size and video_files:
            width, height = self._get_video_resolution(video_files[0])
            if width and height:
                return width, height
        
        # Use configured size or default
        if self.output_width and self.output_height:
            return self.output_width, self.output_height
        
        # Default fallback
        return 1920, 1080
    
    def _build_transition_filter(self, video_files):
        """Build FFmpeg filter graph for transitions between videos."""
        if not self.transition_enabled or len(video_files) < 2:
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
        
        # Get target resolution (configured or from first video)
        width, height = self._get_output_resolution(video_files)
        
        filter_parts = []
        transition_dur = self.transition_duration
        
        # Scale and normalize all video inputs
        for i in range(len(video_files)):
            filter_parts.append(f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
            filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
        
        # Calculate xfade offsets for chained transitions
        # CRITICAL: For xfade [v_prev][v_next]xfade=offset=X:duration=D:
        # - The offset X is relative to the START of v_prev (the first input)
        # - Output duration = X + duration[next] (where duration[next] is second input's duration)
        # - For chained xfades, we must track the actual output duration of each xfade
        xfade_offsets = []
        xfade_output_durations = []  # Track actual output duration of each xfade
        
        for i in range(len(video_files) - 1):
            if i == 0:
                # First xfade: [v0][v1]xfade
                # Offset is when v0 ends minus transition duration
                offset = max(0.1, durations[0] - transition_dur)
                # Output duration = offset + duration[1]
                output_dur = offset + durations[1]
            else:
                # Subsequent xfades: [v_prev_output][v_next]xfade
                # Previous xfade output duration is stored
                prev_output_dur = xfade_output_durations[i-1]
                # Offset is when previous output ends minus transition duration
                offset = max(0.1, prev_output_dur - transition_dur)
                # New output duration = offset + duration of next video
                output_dur = offset + durations[i+1]
            
            xfade_offsets.append(offset)
            xfade_output_durations.append(output_dur)
        
        # Debug: log offset and duration info
        if hasattr(self, 'root'):
            offset_debug = ", ".join([f"T{i}:{o:.2f}s" for i, o in enumerate(xfade_offsets[:5])])
            dur_debug = ", ".join([f"V{i}:{d:.2f}s" for i, d in enumerate(durations[:5])])
            # Calculate expected output durations for debug
            out_durs = []
            for i in range(min(5, len(xfade_offsets))):
                if i == 0:
                    out_dur = durations[0] + durations[1] - transition_dur
                else:
                    prev_out = sum(durations[:i+1]) - i * transition_dur
                    out_dur = prev_out + durations[i+1] - transition_dur
                out_durs.append(out_dur)
            out_dur_debug = ", ".join([f"O{i}:{d:.2f}s" for i, d in enumerate(out_durs)])
            self.root.after(0, lambda: self.log(f"[DEBUG] First 5 video durations: {dur_debug}"))
            self.root.after(0, lambda: self.log(f"[DEBUG] First 5 xfade output durations: {out_dur_debug}"))
            self.root.after(0, lambda: self.log(f"[DEBUG] First 5 xfade offsets: {offset_debug}"))
        
        # Randomly select transition types for each transition
        selected_transitions = []
        for i in range(len(video_files) - 1):
            transition_type = random.choice(self.selected_transition_types)
            selected_transitions.append(transition_type)
        
        # Log selected transitions for debugging (will be called from main thread or background)
        transition_names = []
        for trans_type in selected_transitions:
            for name, value in self.transition_types:
                if value == trans_type:
                    transition_names.append(name)
                    break
        # Use root.after to ensure thread-safe logging
        if hasattr(self, 'root'):
            self.root.after(0, lambda names=', '.join(transition_names): 
                          self.log(f"[INFO] Random transitions selected: {names}"))
        
        # Build xfade chain
        if len(video_files) == 2:
            # Simple two-video case
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[vout]")
            filter_parts.append(f"[a0][a1]acrossfade=d={transition_dur}[aout]")
        else:
            # Chain multiple xfade filters
            # First transition
            filter_parts.append(f"[v0][v1]xfade=transition={selected_transitions[0]}:duration={transition_dur}:offset={xfade_offsets[0]}[v01]")
            filter_parts.append(f"[a0][a1]acrossfade=d={transition_dur}[a01]")
            
            # Chain remaining videos
            for i in range(2, len(video_files)):
                prev_label = f"v{i-2}{i-1}" if i > 2 else "v01"
                prev_audio = f"a{i-2}{i-1}" if i > 2 else "a01"
                curr_label = f"v{i-1}{i}"
                curr_audio = f"a{i-1}{i}"
                
                # Use the calculated offset for this transition
                offset = xfade_offsets[i-1]
                filter_parts.append(f"[{prev_label}][v{i}]xfade=transition={selected_transitions[i-1]}:duration={transition_dur}:offset={offset}[{curr_label}]")
                filter_parts.append(f"[{prev_audio}][a{i}]acrossfade=d={transition_dur}[{curr_audio}]")
            
            # Final output labels - rename the last transition outputs to [vout] and [aout]
            final_v = f"v{len(video_files)-2}{len(video_files)-1}"
            final_a = f"a{len(video_files)-2}{len(video_files)-1}"
            # Use null/anull filters to rename outputs (they pass through unchanged)
            filter_parts.append(f"[{final_v}]null[vout]")
            filter_parts.append(f"[{final_a}]anull[aout]")
        
        filter_complex = ";".join(filter_parts)
        
        # Debug: verify filter graph structure
        if hasattr(self, 'root'):
            # Count xfade filters
            xfade_count = filter_complex.count('xfade')
            acrossfade_count = filter_complex.count('acrossfade')
            self.root.after(0, lambda: self.log(f"[DEBUG] Filter graph: {xfade_count} xfade filters, {acrossfade_count} acrossfade filters"))
            self.root.after(0, lambda: self.log(f"[DEBUG] Expected transitions: {len(video_files) - 1}"))
            # Log a sample of the filter graph to verify structure
            sample_length = min(500, len(filter_complex))
            self.root.after(0, lambda: self.log(f"[DEBUG] Filter graph sample (first {sample_length} chars): {filter_complex[:sample_length]}..."))
            # Check if final labels exist
            if f"[{final_v}]" in filter_complex and f"[{final_a}]" in filter_complex:
                self.root.after(0, lambda: self.log(f"[DEBUG] Final labels found: {final_v}, {final_a}"))
            else:
                self.root.after(0, lambda: self.log(f"[WARNING] Final labels missing: {final_v}, {final_a}"))
        
        return filter_complex

    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Add Videos", command=self.add_videos)
        file_menu.add_command(label="Remove Selected", command=self.remove_selected)
        file_menu.add_command(label="Clear All", command=self.clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Load Project", command=self.load_project)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Set Grid Columns", command=self.set_grid_columns)
        edit_menu.add_separator()
        self.auto_export_var = tk.BooleanVar(value=self.auto_export_enabled)
        edit_menu.add_checkbutton(label="Auto-export Last Frame", variable=self.auto_export_var, 
                                 command=self.toggle_auto_export)
        
        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill='x', pady=(0, 10))
        
        ttk.Button(toolbar, text="Add Videos", command=self.add_videos).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Remove Selected", command=self.remove_selected).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Clear All", command=self.clear_all).pack(side='left', padx=5)
        
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Button(toolbar, text="Preview Combined Video", command=self.preview_combined_video).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Export Combined Video", command=self.export_combined_video).pack(side='left', padx=5)
        
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Label(toolbar, text="Grid Columns:").pack(side='left', padx=5)
        self.grid_cols_var = tk.StringVar(value=str(self.grid_cols))
        grid_spin = ttk.Spinbox(toolbar, from_=1, to=20, textvariable=self.grid_cols_var, width=5)
        grid_spin.pack(side='left', padx=5)
        grid_spin.bind('<Return>', lambda e: self.update_grid())
        grid_spin.bind('<FocusOut>', lambda e: self.update_grid())  # Update when focus leaves spinbox
        grid_spin.bind('<ButtonRelease-1>', lambda e: self.update_grid())  # Update when using spinbox arrows
        
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        
        self.auto_export_checkbox = ttk.Checkbutton(toolbar, text="Auto-export Last Frame", 
                                                    variable=self.auto_export_var,
                                                    command=self.toggle_auto_export)
        self.auto_export_checkbox.pack(side='left', padx=5)
        
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # Transition controls
        ttk.Label(toolbar, text="Transitions:").pack(side='left', padx=5)
        self.transition_enabled_var = tk.BooleanVar(value=self.transition_enabled)
        ttk.Checkbutton(toolbar, text="Enable", variable=self.transition_enabled_var,
                        command=self.toggle_transitions).pack(side='left', padx=2)
        
        ttk.Button(toolbar, text="Select Types...", command=self.select_transition_types,
                  width=12).pack(side='left', padx=2)
        
        # Label showing selected count
        self.transition_selection_label = ttk.Label(toolbar, text="(0 selected)", 
                                                     font=('Arial', 8))
        self.transition_selection_label.pack(side='left', padx=2)
        
        ttk.Label(toolbar, text="Duration:").pack(side='left', padx=(5, 2))
        self.transition_duration_var = tk.StringVar(value=str(self.transition_duration))
        duration_spin = ttk.Spinbox(toolbar, from_=0.1, to=5.0, increment=0.1,
                                    textvariable=self.transition_duration_var, width=6)
        duration_spin.pack(side='left', padx=2)
        duration_spin.bind('<Return>', lambda e: self.update_transition_duration())
        
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=10)
        
        # Output size controls
        ttk.Label(toolbar, text="Output Size:").pack(side='left', padx=5)
        ttk.Button(toolbar, text="Configure...", command=self.configure_output_size,
                  width=10).pack(side='left', padx=2)
        self.output_size_label = ttk.Label(toolbar, text="(auto)", font=('Arial', 8))
        self.output_size_label.pack(side='left', padx=2)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(toolbar, textvariable=self.status_var)
        status_label.pack(side='right', padx=10)
        
        # Video grid area
        grid_frame = ttk.LabelFrame(main_frame, text="Video Grid - Drag to Reorder", padding=10)
        grid_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Canvas with scrollbar for grid
        canvas_frame = ttk.Frame(grid_frame)
        canvas_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='white')
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)
        scrollbar_x = ttk.Scrollbar(canvas_frame, orient='horizontal', command=self.canvas.xview)
        
        self.grid_widget = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.grid_widget, anchor='nw')
        
        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar_y.pack(side='right', fill='y')
        scrollbar_x.pack(side='bottom', fill='x')
        
        self.grid_widget.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=10)
        log_frame.pack(fill='both', expand=False, pady=(0, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6)
        self.log_text.pack(fill='both', expand=True)
        
        # Bind canvas events for drag and drop
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
        
        # Enable drag and drop from Windows Explorer (if available)
        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_file_drop)
    
    def update_grid(self):
        """Update grid layout."""
        try:
            new_cols = int(self.grid_cols_var.get())
            if new_cols < 1:
                new_cols = 1
            elif new_cols > 20:
                new_cols = 20
            self.grid_cols = new_cols
            self.grid_cols_var.set(str(self.grid_cols))
        except ValueError:
            self.grid_cols = 5
            self.grid_cols_var.set('5')
        
        self.save_settings()  # Save the grid columns setting
        self.status_var.set(f"Grid updated: {self.grid_cols} columns")
        self.refresh_grid()
    
    def add_videos(self):
        """Add video files."""
        files = self.select_files(
            title="Select Video Files",
            filetypes=[
                ("Video Files", "*.mp4 *.webm *.avi *.mov *.mkv *.flv *.wmv"),
                ("MP4 Files", "*.mp4"),
                ("All Files", "*.*")
            ]
        )
        
        if files:
            newly_added = []
            for file in files:
                self.video_files.append(file)
                newly_added.append(file)
            
            self.log(f"[INFO] Added {len(files)} video file(s)")
            self.refresh_grid()
            self.save_settings()
            
            # Automatically export last frame for newly added videos (if enabled)
            if newly_added and self.auto_export_enabled:
                self.auto_export_last_frames(newly_added)
    
    def remove_selected(self):
        """Remove selected videos."""
        # For now, just remove the last video (will be enhanced later)
        if self.video_files:
            removed = self.video_files.pop()
            self.log(f"[INFO] Removed: {os.path.basename(removed)}")
            self.refresh_grid()
            self.save_settings()
    
    def clear_all(self):
        """Clear all videos."""
        if self.video_files:
            self.video_files.clear()
            self.log("[INFO] Cleared all videos")
            self.refresh_grid()
            self.save_settings()
    
    def refresh_grid(self):
        """Refresh the video grid display."""
        # Clear existing widgets
        for widget in self.grid_widget.winfo_children():
            widget.destroy()
        
        if not self.video_files:
            ttk.Label(self.grid_widget, text="No videos added. Click 'Add Videos' to start.", 
                     font=('Arial', 12)).pack(pady=50)
            return
        
        # Create grid layout
        row = 0
        col = 0
        
        for i, video_file in enumerate(self.video_files):
            # Create video thumbnail frame
            video_frame = ttk.Frame(self.grid_widget, relief='raised', borderwidth=2)
            video_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            video_frame.index = i
            video_frame.file = video_file
            
            # Video thumbnail
            thumbnail_label = ttk.Label(video_frame, text="Loading...")
            thumbnail_label.pack(pady=5)
            
            # Video info
            filename = os.path.basename(video_file)
            info_label = ttk.Label(video_frame, text=filename[:30] + ("..." if len(filename) > 30 else ""), 
                                   font=('Arial', 8))
            info_label.pack()
            
            # Position label
            pos_label = ttk.Label(video_frame, text=f"Position: {i+1}", 
                                font=('Arial', 8, 'bold'), foreground='blue')
            pos_label.pack()
            
            # Bind events for drag and drop
            video_frame.bind('<Button-1>', lambda e, idx=i: self.on_video_click(e, idx))
            video_frame.bind('<B1-Motion>', lambda e, idx=i: self.on_video_drag(e, idx))
            video_frame.bind('<ButtonRelease-1>', lambda e, idx=i: self.on_video_release(e, idx))
            
            # Right-click context menu
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Export First Frame", 
                                   command=lambda vf=video_file: self.export_frame(vf, 'first'))
            context_menu.add_command(label="Export Last Frame", 
                                   command=lambda vf=video_file: self.export_frame(vf, 'last'))
            context_menu.add_command(label="Remove", 
                                   command=lambda idx=i: self.remove_video_by_index(idx))
            
            video_frame.bind('<Button-3>', lambda e, cm=context_menu: self.show_context_menu(e, cm))
            
            # Load thumbnail in background
            self.load_thumbnail(video_file, thumbnail_label)
            
            # Update grid position
            col += 1
            if col >= self.grid_cols:
                col = 0
                row += 1
        
        # Configure grid columns - ensure all columns up to grid_cols are configured
        for i in range(self.grid_cols):
            self.grid_widget.grid_columnconfigure(i, weight=1, uniform='col')
        # Unconfigure any extra columns beyond grid_cols
        for i in range(self.grid_cols, 20):  # Clear up to 20 columns max
            try:
                self.grid_widget.grid_columnconfigure(i, weight=0)
            except:
                pass
        
        # Enable drag and drop on grid widget (if available)
        if DND_AVAILABLE:
            self.grid_widget.drop_target_register(DND_FILES)
            self.grid_widget.dnd_bind('<<Drop>>', self.on_file_drop)
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self.on_file_drop)
    
    def load_thumbnail(self, video_file, label):
        """Load thumbnail from video in background thread."""
        def _load():
            try:
                # Get thumbnail using FFmpeg
                ffmpeg_cmd = self.get_ffmpeg_command()
                
                # Debug: Check if FFmpeg exists
                if not os.path.exists(ffmpeg_cmd):
                    self.log(f"[DEBUG] FFmpeg not found at: {ffmpeg_cmd}")
                    label.config(text="No FFmpeg")
                    return
                
                # Use unique temp filename based on video file path to avoid race conditions
                video_hash = hashlib.md5(video_file.encode('utf-8')).hexdigest()[:8]
                temp_thumb = os.path.join(self.root_dir, f'temp_thumb_{video_hash}.jpg')
                
                cmd = [ffmpeg_cmd, '-i', video_file, '-ss', '00:00:00', '-vframes', '1', 
                      '-q:v', '2', '-y', temp_thumb]
                
                self.log(f"[DEBUG] Thumbnail command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
                
                self.log(f"[DEBUG] FFmpeg return code: {result.returncode}")
                if result.stderr:
                    self.log(f"[DEBUG] FFmpeg stderr: {result.stderr[:200]}")
                
                if result.returncode == 0 and os.path.exists(temp_thumb):
                    # Load and resize thumbnail
                    img = Image.open(temp_thumb)
                    img.thumbnail((200, 150), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    label.config(image=photo)
                    label.image = photo  # Keep a reference
                    
                    # Clean up temp file
                    try:
                        os.remove(temp_thumb)
                    except:
                        pass
                else:
                    label.config(text="No thumbnail")
                    self.log(f"[WARNING] Failed to generate thumbnail for: {os.path.basename(video_file)}")
            except Exception as e:
                label.config(text="Error")
                self.log(f"[WARNING] Failed to load thumbnail: {e}")
                import traceback
                self.log(f"[DEBUG] Traceback: {traceback.format_exc()}")
        
        thread = threading.Thread(target=_load)
        thread.daemon = True
        thread.start()
    
    def on_video_click(self, event, index):
        """Handle video click."""
        self.drag_start_index = index
    
    def on_video_drag(self, event, index):
        """Handle video drag."""
        # Visual feedback could be added here
        pass
    
    def on_video_release(self, event, index):
        """Handle video release (drop)."""
        if self.drag_start_index is not None and self.drag_start_index != index:
            # Reorder videos
            video = self.video_files.pop(self.drag_start_index)
            self.video_files.insert(index, video)
            self.log(f"[INFO] Moved video from position {self.drag_start_index+1} to {index+1}")
            self.refresh_grid()
            self.save_settings()
        
        self.drag_start_index = None
    
    def on_canvas_click(self, event):
        """Handle canvas click."""
        pass
    
    def on_canvas_drag(self, event):
        """Handle canvas drag."""
        pass
    
    def on_canvas_release(self, event):
        """Handle canvas release."""
        pass
    
    def on_file_drop(self, event):
        """Handle file drop from Windows Explorer."""
        try:
            # Get dropped files - tkinterdnd2 sends them space-separated with curly braces
            self.log(f"[DEBUG] Drop event data: {event.data}")
            
            # Parse file paths properly handling spaces
            # Files are sent as {file1} {file2} etc, but spaces can break this
            import re
            
            # Try to extract complete file paths from the data
            # Look for patterns like: drive:/path/file.ext or {drive:/path/file.ext}
            files = []
            
            # Pattern to match Windows paths with spaces ending in video extensions
            # This handles paths like: D:/path with spaces/file.mp4
            pattern = r'\{?([A-Za-z]:/[^{}]+\.(?:mp4|webm|avi|mov|mkv|flv|wmv|m4v))\}?'
            matches = re.findall(pattern, event.data)
            
            for match in matches:
                if os.path.isfile(match):
                    files.append(match)
            
            # If no matches found, try simpler approach - check if whole string is a file
            if not files:
                cleaned = event.data.strip('{}').strip()
                if os.path.isfile(cleaned):
                    files.append(cleaned)
            
            self.log(f"[DEBUG] Parsed files: {files}")
            
            # Filter for video files
            video_extensions = ['.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v']
            video_files = []
            
            for file_path in files:
                self.log(f"[DEBUG] Processing file: {file_path}")
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file_path.lower())
                    self.log(f"[DEBUG] File extension: {ext}")
                    if ext in video_extensions:
                        video_files.append(file_path)
                    else:
                        self.log(f"[DEBUG] Skipped - not a video file: {ext}")
                else:
                    self.log(f"[DEBUG] Skipped - not a file: {file_path}")
            
            if video_files:
                # Add new videos (allow duplicates)
                newly_added = []
                for video_file in video_files:
                    self.video_files.append(video_file)
                    newly_added.append(video_file)
                
                if newly_added:
                    self.log(f"[INFO] Added {len(newly_added)} video file(s) via drag-and-drop")
                    self.refresh_grid()
                    self.save_settings()
                    
                    # Automatically export last frame for newly added videos (if enabled)
                    if self.auto_export_enabled:
                        self.auto_export_last_frames(newly_added)
            else:
                self.log("[WARNING] No video files found in dropped files")
        
        except Exception as e:
            self.log(f"[ERROR] Failed to handle file drop: {e}")
            import traceback
            self.log(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    def show_context_menu(self, event, menu):
        """Show context menu."""
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def remove_video_by_index(self, index):
        """Remove video by index."""
        if 0 <= index < len(self.video_files):
            removed = self.video_files.pop(index)
            self.log(f"[INFO] Removed: {os.path.basename(removed)}")
            self.refresh_grid()
            self.save_settings()
    
    def auto_export_last_frames(self, video_files):
        """Automatically export last frame for newly added videos in background."""
        if not video_files:
            return
        
        def _export_thread():
            for video_file in video_files:
                try:
                    self.export_frame_silent(video_file, 'last')
                except Exception as e:
                    self.root.after(0, lambda vf=video_file, err=str(e): 
                                   self.log(f"[WARNING] Auto-export failed for {os.path.basename(vf)}: {err}"))
        
        thread = threading.Thread(target=_export_thread)
        thread.daemon = True
        thread.start()
    
    def export_frame_silent(self, video_file, frame_type):
        """Export first or last frame as PNG (silent version without UI cursor changes)."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            base_name = os.path.splitext(video_file)[0]
            output_file = f"{base_name}_{frame_type}.png"
            
            if not os.path.exists(ffmpeg_cmd):
                self.root.after(0, lambda: self.log(f"[WARNING] FFmpeg not found, skipping frame export for {os.path.basename(video_file)}"))
                return
            
            if frame_type == 'first':
                # For first frame, use -ss after -i (input seeking)
                cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss 00:00:00 -vframes 1 -y "{output_file}"'
            else:  # last
                # Get video duration first
                duration_cmd = f'{ffmpeg_cmd} -i "{video_file}" -f null -'
                result = subprocess.run(duration_cmd, capture_output=True, text=True, shell=True)
                
                # Extract duration from stderr
                duration = None
                for line in result.stderr.split('\n'):
                    if 'Duration:' in line:
                        parts = line.split('Duration:')[1].split(',')[0].strip()
                        duration = parts
                        break
                
                if duration:
                    # For last frame, seek to the end minus 1 frame
                    # Parse duration and subtract a small amount
                    try:
                        # Duration format: HH:MM:SS.ms
                        parts = duration.split(':')
                        if len(parts) == 3:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            sec_ms = parts[2].split('.')
                            seconds = int(sec_ms[0])
                            ms = int(sec_ms[1]) if len(sec_ms) > 1 else 0
                            
                            # Calculate total seconds and subtract 0.1 seconds
                            total_seconds = hours * 3600 + minutes * 60 + seconds + ms / 100.0
                            seek_time = max(0, total_seconds - 0.1)
                            
                            # Format back as HH:MM:SS.ms
                            h = int(seek_time // 3600)
                            m = int((seek_time % 3600) // 60)
                            s = int(seek_time % 60)
                            ms_val = int((seek_time % 1) * 100)
                            seek_str = f"{h:02d}:{m:02d}:{s:02d}.{ms_val:02d}"
                            
                            cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss {seek_str} -vframes 1 -y "{output_file}"'
                        else:
                            raise Exception("Could not parse duration")
                    except Exception as e:
                        self.root.after(0, lambda err=str(e): self.log(f"[WARNING] Could not parse duration: {err}, using -t instead"))
                        # Alternative: use -t to get last second
                        cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss {duration} -t 00:00:01 -frames:v 1 -y "{output_file}"'
                else:
                    raise Exception("Could not determine video duration")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
            
            if result.returncode == 0:
                # Check if file actually exists
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    self.root.after(0, lambda: self.log(f"[SUCCESS] Auto-exported {frame_type} frame: {os.path.basename(output_file)} ({file_size} bytes)"))
                else:
                    # Check if file exists in current directory
                    alt_path = os.path.join(self.root_dir, os.path.basename(output_file))
                    if os.path.exists(alt_path):
                        self.root.after(0, lambda: self.log(f"[SUCCESS] Auto-exported {frame_type} frame: {os.path.basename(alt_path)}"))
                    else:
                        raise Exception(f"FFmpeg succeeded but file not found at: {output_file}")
            else:
                raise Exception(result.stderr)
        
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log(f"[WARNING] Auto-export failed for {os.path.basename(video_file)}: {err}"))
    
    def export_frame(self, video_file, frame_type):
        """Export first or last frame as PNG."""
        try:
            self.root.config(cursor='wait')
            self.root.update()
            
            ffmpeg_cmd = self.get_ffmpeg_command()
            base_name = os.path.splitext(video_file)[0]
            output_file = f"{base_name}_{frame_type}.png"
            
            self.log(f"[DEBUG] Video file: {video_file}")
            self.log(f"[DEBUG] Output frame: {output_file}")
            
            if frame_type == 'first':
                # For first frame, use -ss after -i (input seeking)
                cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss 00:00:00 -vframes 1 -y "{output_file}"'
            else:  # last
                # Get video duration first
                duration_cmd = f'{ffmpeg_cmd} -i "{video_file}" -f null -'
                result = subprocess.run(duration_cmd, capture_output=True, text=True, shell=True)
                
                # Extract duration from stderr
                duration = None
                for line in result.stderr.split('\n'):
                    if 'Duration:' in line:
                        parts = line.split('Duration:')[1].split(',')[0].strip()
                        duration = parts
                        break
                
                if duration:
                    # For last frame, seek to the end minus 1 frame
                    # Parse duration and subtract a small amount
                    try:
                        # Duration format: HH:MM:SS.ms
                        parts = duration.split(':')
                        if len(parts) == 3:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            sec_ms = parts[2].split('.')
                            seconds = int(sec_ms[0])
                            ms = int(sec_ms[1]) if len(sec_ms) > 1 else 0
                            
                            # Calculate total seconds and subtract 0.1 seconds
                            total_seconds = hours * 3600 + minutes * 60 + seconds + ms / 100.0
                            seek_time = max(0, total_seconds - 0.1)
                            
                            # Format back as HH:MM:SS.ms
                            h = int(seek_time // 3600)
                            m = int((seek_time % 3600) // 60)
                            s = int(seek_time % 60)
                            ms_val = int((seek_time % 1) * 100)
                            seek_str = f"{h:02d}:{m:02d}:{s:02d}.{ms_val:02d}"
                            
                            cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss {seek_str} -vframes 1 -y "{output_file}"'
                        else:
                            raise Exception("Could not parse duration")
                    except Exception as e:
                        self.log(f"[WARNING] Could not parse duration: {e}, using -t instead")
                        # Alternative: use -t to get last second
                        cmd = f'{ffmpeg_cmd} -i "{video_file}" -ss {duration} -t 00:00:01 -frames:v 1 -y "{output_file}"'
                else:
                    raise Exception("Could not determine video duration")
            
            self.log(f"[DEBUG] FFmpeg command: {cmd}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
            
            self.log(f"[DEBUG] FFmpeg return code: {result.returncode}")
            if result.stdout:
                self.log(f"[DEBUG] FFmpeg stdout: {result.stdout}")
            if result.stderr:
                self.log(f"[DEBUG] FFmpeg stderr: {result.stderr}")
            
            if result.returncode == 0:
                # Check if file actually exists
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    self.log(f"[SUCCESS] Exported {frame_type} frame: {os.path.basename(output_file)} ({file_size} bytes)")
                    self.log(f"[INFO] Location: {os.path.dirname(output_file)}")
                else:
                    # Check if file exists in current directory
                    alt_path = os.path.join(self.root_dir, os.path.basename(output_file))
                    if os.path.exists(alt_path):
                        self.log(f"[WARNING] File created in different location: {alt_path}")
                        self.log(f"[INFO] Location: {os.path.dirname(alt_path)}")
                    else:
                        raise Exception(f"FFmpeg succeeded but file not found at: {output_file}")
            else:
                raise Exception(result.stderr)
        
        except Exception as e:
            self.log(f"[ERROR] Failed to export frame: {e}")
            messagebox.showerror("Error", f"Failed to export frame:\n{e}")
        
        finally:
            self.root.config(cursor='')
    
    def preview_combined_video(self):
        """Preview combined video before saving."""
        if not self.video_files:
            self.log("[WARNING] No videos to combine")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        # Create temporary preview file
        preview_file = os.path.join(self.root_dir, 'temp_preview.mp4')
        
        self.log(f"[INFO] Creating preview of {len(self.video_files)} videos")
        self.root.config(cursor='wait')
        self.root.update()
        
        # Run in background thread
        thread = threading.Thread(target=self._preview_videos_thread, args=(preview_file,))
        thread.daemon = True
        thread.start()
    
    def _preview_videos_thread(self, preview_file):
        """Create preview video in background thread."""
        concat_file = None
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Check if transitions are enabled
            filter_complex = self._build_transition_filter(self.video_files)
            
            if filter_complex:
                # Use filter graph with transitions for preview
                self.root.after(0, lambda: self.log(f"[INFO] Creating preview with {self.transition_type} transitions ({self.transition_duration}s)"))
                
                # Build input arguments
                input_args = []
                for vf in self.video_files:
                    input_args.extend(['-i', vf])
                
                # Build command with filter complex (faster encoding for preview)
                cmd = [ffmpeg_cmd] + input_args + [
                    '-filter_complex', filter_complex,
                    '-map', '[vout]',
                    '-map', '[aout]',
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '28',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-y', preview_file
                ]
                
                self.root.after(0, lambda: self.log(f"[DEBUG] Preview FFmpeg command with transitions: {' '.join(cmd)}"))
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
                
                if result.returncode == 0 and os.path.exists(preview_file):
                    self.root.after(0, lambda: self.log(f"[SUCCESS] Preview with transitions created"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                    self.root.after(0, lambda: self._play_preview(preview_file))
                else:
                    error_msg = result.stderr[:2000] if result.stderr else "Unknown error"
                    self.root.after(0, lambda: self.log(f"[ERROR] Failed to create preview: {error_msg}"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to create preview:\n{error_msg}"))
            else:
                # Use simple concat for preview
                concat_file = self._write_concat_file()
                
                # Use concat demuxer with faster encoding for preview
                cmd = f'{ffmpeg_cmd} -f concat -safe 0 -i "{concat_file}" -c:v libx264 -preset ultrafast -crf 28 -c:a aac -b:a 128k -y "{preview_file}"'
                
                self.root.after(0, lambda: self.log(f"[DEBUG] Preview FFmpeg command: {cmd}"))
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
                
                # Clean up concat file
                if concat_file:
                    try:
                        os.remove(concat_file)
                    except:
                        pass
                
                if result.returncode == 0 and os.path.exists(preview_file):
                    self.root.after(0, lambda: self.log(f"[SUCCESS] Preview created"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                    self.root.after(0, lambda: self._play_preview(preview_file))
                else:
                    # Log more of stderr for diagnosis
                    error_msg = result.stderr[:2000] if result.stderr else "Unknown error"
                    self.root.after(0, lambda: self.log(f"[ERROR] Failed to create preview: {error_msg}"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to create preview:\n{error_msg}"))
        
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}"))
            self.root.after(0, lambda: self.root.config(cursor=''))
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Exception:\n{msg}"))
    
    def _play_preview(self, preview_file):
        """Play preview video."""
        if CV2_AVAILABLE:
            # Play preview in OpenCV window (embedded)
            self.log(f"[INFO] Opening preview in application window")
            self._play_video_cv2(preview_file)
        else:
            # Fallback to default player
            try:
                if sys.platform == 'win32':
                    os.startfile(preview_file)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', preview_file])
                else:
                    subprocess.run(['xdg-open', preview_file])
                
                self.log(f"[INFO] Preview opened in default player")
                self.log(f"[INFO] Total videos in preview: {len(self.video_files)}")
                self.log(f"[INFO] If you want to save, use 'Export Combined Video' button")
                
                # Clean up preview file after a delay
                def cleanup_preview():
                    try:
                        if os.path.exists(preview_file):
                            os.remove(preview_file)
                            self.log(f"[INFO] Cleaned up preview file")
                    except:
                        pass
                
                threading.Timer(5.0, cleanup_preview).start()
            
            except Exception as e:
                self.log(f"[ERROR] Failed to play preview: {e}")
                messagebox.showerror("Error", f"Failed to play preview:\n{e}")
    
    def _play_video_cv2(self, video_file):
        """Play video using OpenCV in a separate window."""
        def play_in_thread():
            try:
                cap = cv2.VideoCapture(video_file)
                
                if not cap.isOpened():
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not open video file"))
                    return
                
                # Get video properties
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                self.root.after(0, lambda: self.log(f"[INFO] Video: {width}x{height} @ {fps} fps"))
                
                window_name = "Video Preview - Press Q to close"
                try:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                except cv2.error as e:
                    # OpenCV GUI not available, fall back to system player
                    self.root.after(0, lambda: self.log(f"[WARNING] OpenCV GUI not available, using system player"))
                    cap.release()
                    self._play_preview_fallback(video_file)
                    return
                
                # Resize window to fit screen
                max_width = 1280
                max_height = 720
                if width > max_width or height > max_height:
                    scale = min(max_width / width, max_height / height)
                    width = int(width * scale)
                    height = int(height * scale)
                
                cv2.resizeWindow(window_name, width, height)
                
                frame_count = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        # Loop back to start
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    
                    # Resize frame for display
                    if frame.shape[1] != width or frame.shape[0] != height:
                        frame = cv2.resize(frame, (width, height))
                    
                    cv2.imshow(window_name, frame)
                    
                    # Check for key press (Q to quit) or window close
                    key = cv2.waitKey(int(1000 / fps)) & 0xFF
                    if key == ord('q') or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                        break
                    
                    frame_count += 1
                
                cap.release()
                cv2.destroyAllWindows()
                
                # Log preview complete and auto-save
                self.root.after(0, lambda: self.log(f"[INFO] Preview complete - Total videos: {len(self.video_files)}"))
                self.root.after(0, lambda: self.log(f"[INFO] If you want to save, use 'Export Combined Video' button"))
                
                # Clean up preview file
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                        self.log(f"[INFO] Cleaned up preview file")
                except:
                    pass
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Video playback error: {msg}"))
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Video playback error:\n{msg}"))
        
        thread = threading.Thread(target=play_in_thread)
        thread.daemon = True
        thread.start()
    
    def _play_preview_fallback(self, preview_file):
        """Fallback to system player when OpenCV GUI is not available."""
        try:
            if sys.platform == 'win32':
                os.startfile(preview_file)
            elif sys.platform == 'darwin':
                subprocess.run(['open', preview_file])
            else:
                subprocess.run(['xdg-open', preview_file])
            
            self.log(f"[INFO] Preview opened in default player")
            self.log(f"[INFO] Total videos in preview: {len(self.video_files)}")
            self.log(f"[INFO] If you want to save, use 'Export Combined Video' button")
            
            # Clean up preview file after a delay
            def cleanup_preview():
                try:
                    if os.path.exists(preview_file):
                        os.remove(preview_file)
                        self.log(f"[INFO] Cleaned up preview file")
                except:
                    pass
            
            threading.Timer(5.0, cleanup_preview).start()
        
        except Exception as e:
            self.log(f"[ERROR] Failed to play preview: {e}")
            messagebox.showerror("Error", f"Failed to play preview:\n{e}")
    
    def _create_final_video(self, output_file):
        """Create final high-quality video."""
        concat_file = None
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Create concat file
            concat_file = self._write_concat_file()
            
            # Use concat demuxer for lossless combination
            cmd = f'{ffmpeg_cmd} -f concat -safe 0 -i "{concat_file}" -c copy -y "{output_file}"'
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
            
            if result.returncode == 0:
                self.root.after(0, lambda: self.log(f"[SUCCESS] Final video saved: {os.path.basename(output_file)}"))
                self.root.after(0, lambda: self.root.config(cursor=''))
            else:
                # Retry with re-encode if stream copy fails
                error_msg = result.stderr[:2000] if result.stderr else "Unknown error"
                self.root.after(0, lambda: self.log(f"[WARNING] Copy combine failed, retrying with re-encode..."))
                reencode_cmd = f"{ffmpeg_cmd} -f concat -safe 0 -i \"{concat_file}\" -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 192k -movflags +faststart -y \"{output_file}\""
                self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg reencode command: {reencode_cmd}"))
                retry = subprocess.run(reencode_cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
                if retry.returncode == 0:
                    self.root.after(0, lambda: self.log(f"[SUCCESS] Final video saved (re-encoded): {os.path.basename(output_file)}"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                else:
                    error_msg2 = retry.stderr[:4000] if retry.stderr else "Unknown error"
                    self.root.after(0, lambda: self.log(f"[ERROR] Failed to save: {error_msg2}"))
                    self.root.after(0, lambda: self.root.config(cursor=''))
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to save:\n{error_msg2}"))
        
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}"))
            self.root.after(0, lambda: self.root.config(cursor=''))
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Exception:\n{msg}"))
        
        finally:
            # Clean up concat file after both attempts are complete
            if concat_file:
                try:
                    os.remove(concat_file)
                except:
                    pass
    
    def export_combined_video(self):
        """Export combined video without preview."""
        if not self.video_files:
            self.log("[WARNING] No videos to combine")
            return
        
        if not self.check_ffmpeg():
            self.offer_ffmpeg_install()
            return
        
        # Ask for output location
        first_video = self.video_files[0]
        base_name = os.path.splitext(first_video)[0]
        default_output = f"{base_name}_full.mp4"
        
        output_file = filedialog.asksaveasfilename(
            title="Save Combined Video",
            defaultextension='.mp4',
            filetypes=[('MP4 Files', '*.mp4'), ('All Files', '*.*')],
            initialfile=os.path.basename(default_output)
        )
        
        if not output_file:
            return
        
        self.log(f"[INFO] Starting video combination of {len(self.video_files)} videos")
        self.root.config(cursor='wait')
        self.root.update()
        
        # Run in background thread
        thread = threading.Thread(target=self._combine_videos_thread, args=(output_file,))
        thread.daemon = True
        thread.start()
    
    def _combine_videos_thread(self, output_file):
        """Combine videos in background thread."""
        concat_file = None
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Check if transitions are enabled
            filter_complex = self._build_transition_filter(self.video_files)
            
            if filter_complex:
                # Use filter graph with transitions
                # For large numbers of videos, use batch processing to avoid command line length limits
                MAX_VIDEOS_PER_BATCH = 10
                
                if len(self.video_files) > MAX_VIDEOS_PER_BATCH:
                    # Batch processing: combine in groups, then combine the groups
                    self.root.after(0, lambda: self.log(f"[INFO] Combining {len(self.video_files)} videos in batches of {MAX_VIDEOS_PER_BATCH}"))
                    
                    batch_outputs = []
                    num_batches = (len(self.video_files) + MAX_VIDEOS_PER_BATCH - 1) // MAX_VIDEOS_PER_BATCH
                    
                    for batch_idx in range(num_batches):
                        start_idx = batch_idx * MAX_VIDEOS_PER_BATCH
                        end_idx = min(start_idx + MAX_VIDEOS_PER_BATCH, len(self.video_files))
                        batch_videos = self.video_files[start_idx:end_idx]
                        
                        self.root.after(0, lambda idx=batch_idx+1, total=num_batches, count=len(batch_videos): 
                                      self.log(f"[INFO] Processing batch {idx}/{total} ({count} videos)"))
                        
                        # Create temporary output file for this batch
                        batch_output = os.path.join(self.root_dir, f"temp_batch_{batch_idx}.mp4")
                        batch_outputs.append(batch_output)
                        
                        # Combine this batch
                        batch_filter = self._build_transition_filter(batch_videos)
                        if batch_filter:
                            # Build input arguments for this batch
                            batch_input_args = []
                            for vf in batch_videos:
                                batch_input_args.extend(['-i', vf])
                            
                            # Build command for this batch
                            batch_cmd = [ffmpeg_cmd] + batch_input_args + [
                                '-filter_complex', batch_filter,
                                '-map', '[vout]',
                                '-map', '[aout]',
                                '-c:v', 'libx264',
                                '-preset', 'veryfast',
                                '-crf', '18',
                                '-c:a', 'aac',
                                '-b:a', '192k',
                                '-movflags', '+faststart',
                                '-y', batch_output
                            ]
                            
                            result = subprocess.run(batch_cmd, capture_output=True, text=True, cwd=self.root_dir)
                            
                            if result.returncode != 0:
                                error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
                                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Failed to combine batch {batch_idx+1}: {msg}"))
                                # Clean up any successful batches
                                for temp_file in batch_outputs:
                                    try:
                                        if os.path.exists(temp_file):
                                            os.remove(temp_file)
                                    except:
                                        pass
                                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Failed to combine batch:\n{msg}"))
                                return
                        else:
                            # No transitions, use concat
                            batch_concat = self._write_concat_file_for_batch(batch_videos)
                            batch_cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', batch_concat,
                                       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                                       '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                                       '-y', batch_output]
                            result = subprocess.run(batch_cmd, capture_output=True, text=True, cwd=self.root_dir)
                            if batch_concat:
                                try:
                                    os.remove(batch_concat)
                                except:
                                    pass
                            
                            if result.returncode != 0:
                                error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
                                self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Failed to combine batch {batch_idx+1}: {msg}"))
                                # Clean up any successful batches
                                for temp_file in batch_outputs:
                                    try:
                                        if os.path.exists(temp_file):
                                            os.remove(temp_file)
                                    except:
                                        pass
                                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Failed to combine batch:\n{msg}"))
                                return
                    
                    # Now combine all batch outputs
                    self.root.after(0, lambda: self.log(f"[INFO] Combining {len(batch_outputs)} batch outputs into final video"))
                    
                    # Use concat demuxer to combine batch outputs (faster and simpler)
                    final_concat = self._write_concat_file_for_batch(batch_outputs)
                    final_cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', final_concat,
                               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                               '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                               '-y', output_file]
                    
                    result = subprocess.run(final_cmd, capture_output=True, text=True, cwd=self.root_dir)
                    
                    # Clean up batch files
                    for temp_file in batch_outputs:
                        try:
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                        except:
                            pass
                    if final_concat:
                        try:
                            os.remove(final_concat)
                        except:
                            pass
                    
                    if result.returncode == 0:
                        self.root.after(0, lambda: self.log(f"[SUCCESS] Combined {len(self.video_files)} videos with transitions saved: {os.path.basename(output_file)}"))
                    else:
                        error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
                        self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Failed to combine batch outputs: {msg}"))
                        self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Failed to combine batch outputs:\n{msg}"))
                else:
                    # Small number of videos, use original method
                    self.root.after(0, lambda: self.log(f"[INFO] Combining {len(self.video_files)} videos with transitions ({self.transition_duration}s)"))
                    
                    # Build input arguments
                    input_args = []
                    for vf in self.video_files:
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
                    
                    self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg command with transitions: {' '.join(cmd)}"))
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
                    
                    if result.returncode == 0:
                        self.root.after(0, lambda: self.log(f"[SUCCESS] Combined video with transitions saved: {os.path.basename(output_file)}"))
                    else:
                        error_msg = result.stderr[:4000] if result.stderr else "Unknown error"
                        self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Failed to combine videos with transitions: {msg}"))
                        self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Failed to combine videos:\n{msg}"))
            else:
                # Use simple concat (no transitions)
                concat_file = self._write_concat_file()
                
                # Use concat demuxer
                cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', concat_file, 
                      '-c', 'copy', '-y', output_file]
                
                self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg command: {' '.join(cmd)}"))
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
                
                if result.returncode == 0:
                    self.root.after(0, lambda: self.log(f"[SUCCESS] Combined video saved: {os.path.basename(output_file)}"))
                else:
                    # Retry with re-encode fallback
                    error_msg = result.stderr[:2000] if result.stderr else "Unknown error"
                    self.root.after(0, lambda: self.log(f"[WARNING] Copy combine failed, retrying with re-encode..."))
                    reencode_cmd = f"{ffmpeg_cmd} -f concat -safe 0 -i \"{concat_file}\" -c:v libx264 -preset veryfast -crf 18 -c:a aac -b:a 192k -movflags +faststart -y \"{output_file}\""
                    self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg reencode command: {reencode_cmd}"))
                    retry = subprocess.run(reencode_cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
                    if retry.returncode == 0:
                        self.root.after(0, lambda: self.log(f"[SUCCESS] Combined video saved (re-encoded): {os.path.basename(output_file)}"))
                    else:
                        error_msg2 = retry.stderr[:4000] if retry.stderr else "Unknown error"
                        self.root.after(0, lambda: self.log(f"[ERROR] Failed to combine videos: {error_msg2}"))
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to combine videos:\n{error_msg2}"))
        
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.log(f"[ERROR] Exception: {msg}"))
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Exception:\n{msg}"))
        
        finally:
            # Clean up concat file if used
            if concat_file:
                try:
                    os.remove(concat_file)
                except:
                    pass
            self.root.after(0, lambda: self.root.config(cursor=''))
    
    def toggle_auto_export(self):
        """Toggle auto-export last frame option."""
        self.auto_export_enabled = self.auto_export_var.get()
        self.save_settings()
        status_text = "enabled" if self.auto_export_enabled else "disabled"
        self.log(f"[INFO] Auto-export last frame: {status_text}")
    
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
        self.transition_checkboxes = {}
        self.transition_checkbox_vars = {}
        
        for name, value in self.transition_types:
            var = tk.BooleanVar(value=value in self.selected_transition_types)
            self.transition_checkbox_vars[value] = var
            cb = ttk.Checkbutton(scrollable_frame, text=name, variable=var)
            cb.pack(anchor='w', padx=5, pady=2)
            self.transition_checkboxes[value] = cb
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def select_all():
            for var in self.transition_checkbox_vars.values():
                var.set(True)
        
        def deselect_all():
            for var in self.transition_checkbox_vars.values():
                var.set(False)
        
        def apply_selection():
            selected = []
            for value, var in self.transition_checkbox_vars.items():
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
    
    def on_transition_type_changed(self, event=None):
        """Handle transition type change (legacy method, kept for compatibility)."""
        # This method is no longer used but kept for backward compatibility
        pass
    
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
    
    def configure_output_size(self):
        """Configure output video size."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure Output Video Size")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Get first video resolution if available
        first_video_res = None, None
        if self.video_files:
            first_video_res = self._get_video_resolution(self.video_files[0])
        
        ttk.Label(dialog, text="Output Video Resolution", font=('Arial', 10, 'bold')).pack(pady=10)
        
        # Option: Use first video size
        use_first_var = tk.BooleanVar(value=self.use_first_video_size)
        use_first_cb = ttk.Checkbutton(dialog, text="Use first video's resolution (auto)", 
                                       variable=use_first_var)
        use_first_cb.pack(pady=5)
        
        if first_video_res[0] and first_video_res[1]:
            ttk.Label(dialog, text=f"First video: {first_video_res[0]}x{first_video_res[1]}", 
                     font=('Arial', 8), foreground='gray').pack()
        
        ttk.Separator(dialog, orient='horizontal').pack(fill='x', padx=20, pady=10)
        
        # Custom size inputs
        size_frame = ttk.Frame(dialog)
        size_frame.pack(pady=10)
        
        ttk.Label(size_frame, text="Width:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        width_var = tk.StringVar(value=str(self.output_width) if self.output_width else "1920")
        width_spin = ttk.Spinbox(size_frame, from_=320, to=7680, increment=16, 
                                textvariable=width_var, width=10, state='disabled' if self.use_first_video_size else 'normal')
        width_spin.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(size_frame, text="Height:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        height_var = tk.StringVar(value=str(self.output_height) if self.output_height else "1080")
        height_spin = ttk.Spinbox(size_frame, from_=240, to=4320, increment=16,
                                 textvariable=height_var, width=10, state='disabled' if self.use_first_video_size else 'normal')
        height_spin.grid(row=1, column=1, padx=5, pady=5)
        
        def toggle_custom_size():
            state = 'normal' if not use_first_var.get() else 'disabled'
            width_spin.config(state=state)
            height_spin.config(state=state)
        
        use_first_cb.config(command=toggle_custom_size)
        
        # Preset buttons
        preset_frame = ttk.Frame(dialog)
        preset_frame.pack(pady=5)
        
        presets = [
            ("720p", 1280, 720),
            ("1080p", 1920, 1080),
            ("1440p", 2560, 1440),
            ("4K", 3840, 2160),
        ]
        
        for preset_name, w, h in presets:
            def set_preset(pw=w, ph=h):
                use_first_var.set(False)
                width_var.set(str(pw))
                height_var.set(str(ph))
                toggle_custom_size()
            
            ttk.Button(preset_frame, text=preset_name, command=set_preset, width=8).pack(side='left', padx=2)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def apply_size():
            try:
                self.use_first_video_size = use_first_var.get()
                if not self.use_first_video_size:
                    self.output_width = int(width_var.get())
                    self.output_height = int(height_var.get())
                    if self.output_width < 320 or self.output_height < 240:
                        messagebox.showerror("Error", "Minimum size is 320x240")
                        return
                else:
                    self.output_width = None
                    self.output_height = None
                
                self.update_output_size_label()
                self.save_settings()
                self.log(f"[INFO] Output size: {'auto (first video)' if self.use_first_video_size else f'{self.output_width}x{self.output_height}'}")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid size values")
        
        ttk.Button(btn_frame, text="Apply", command=apply_size).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def update_output_size_label(self):
        """Update the output size label."""
        if self.use_first_video_size:
            self.output_size_label.config(text="(auto)")
        else:
            self.output_size_label.config(text=f"{self.output_width}x{self.output_height}")
    
    def set_grid_columns(self):
        """Set grid columns."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Grid Columns")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Number of columns:").pack(pady=20)
        
        cols_var = tk.StringVar(value=str(self.grid_cols))
        cols_spin = ttk.Spinbox(dialog, from_=1, to=20, textvariable=cols_var, width=10)
        cols_spin.pack(pady=10)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def apply_change():
            try:
                new_cols = int(cols_var.get())
                if new_cols < 1:
                    new_cols = 1
                elif new_cols > 20:
                    new_cols = 20
                self.grid_cols = new_cols
                self.grid_cols_var.set(str(self.grid_cols))
                self.save_settings()  # Save the grid columns setting
                self.refresh_grid()
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid number")
        
        ttk.Button(btn_frame, text="Apply", command=apply_change).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
    def save_project(self):
        """Save project to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension='.json',
            filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')]
        )
        
        if filename:
            try:
                project_data = {
                    'video_files': self.video_files,
                    'grid_cols': self.grid_cols,
                    'transition_enabled': self.transition_enabled,
                    'transition_type': self.transition_type,  # Legacy
                    'selected_transition_types': self.selected_transition_types,  # New
                    'transition_duration': self.transition_duration
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)
                
                self.log(f"[INFO] Project saved: {os.path.basename(filename)}")
                self.log("[SUCCESS] Project saved successfully")
            
            except Exception as e:
                self.log(f"[ERROR] Failed to save project: {e}")
                messagebox.showerror("Error", f"Failed to save project:\n{e}")
    
    def load_project(self):
        """Load project from file."""
        filename = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                self.video_files = project_data.get('video_files', [])
                self.grid_cols = project_data.get('grid_cols', 5)
                self.grid_cols_var.set(str(self.grid_cols))
                
                # Load transition settings if available
                if 'transition_enabled' in project_data:
                    self.transition_enabled = project_data['transition_enabled']
                    if hasattr(self, 'transition_enabled_var'):
                        self.transition_enabled_var.set(self.transition_enabled)
                
                # Load transition types (new multi-select or legacy single)
                if 'selected_transition_types' in project_data:
                    self.selected_transition_types = project_data['selected_transition_types']
                    if self.selected_transition_types:
                        self.transition_type = self.selected_transition_types[0]  # Keep first for compatibility
                elif 'transition_type' in project_data:
                    # Legacy: convert single type to list
                    self.transition_type = project_data['transition_type']
                    if self.transition_type != "none":
                        self.selected_transition_types = [self.transition_type]
                    else:
                        self.selected_transition_types = ["fade"]  # Default
                
                # Update UI label
                if hasattr(self, 'transition_selection_label'):
                    self.update_transition_selection_label()
                
                if 'transition_duration' in project_data:
                    self.transition_duration = project_data['transition_duration']
                    if hasattr(self, 'transition_duration_var'):
                        self.transition_duration_var.set(str(self.transition_duration))
                
                self.log(f"[INFO] Project loaded: {os.path.basename(filename)}")
                self.refresh_grid()
                self.save_settings()
            
            except Exception as e:
                self.log(f"[ERROR] Failed to load project: {e}")
                messagebox.showerror("Error", f"Failed to load project:\n{e}")
    
    def check_ffmpeg_availability(self):
        """Check if FFmpeg is available."""
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            self.log(f"[DEBUG] FFmpeg command: {ffmpeg_cmd}")
            
            # Try to run FFmpeg version check
            result = subprocess.run([ffmpeg_cmd, '-version'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else "Unknown"
                self.log(f"[INFO] FFmpeg available: {version_line}")
            else:
                self.log(f"[WARNING] FFmpeg command returned non-zero exit code")
                
        except FileNotFoundError:
            self.log(f"[ERROR] FFmpeg not found at: {ffmpeg_cmd}")
            self.log(f"[INFO] Thumbnail generation and frame export require FFmpeg")
            self.log(f"[INFO] Video combination features will not work without FFmpeg")
        except Exception as e:
            self.log(f"[WARNING] Could not verify FFmpeg: {e}")
    
    def log(self, message):
        """Log a message."""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def save_settings(self):
        """Save current settings to file."""
        try:
            settings = {
                'grid_cols': self.grid_cols,
                'auto_export_enabled': self.auto_export_enabled,
                'transition_enabled': self.transition_enabled,
                'transition_type': self.transition_type,  # Legacy single type
                'selected_transition_types': self.selected_transition_types,  # New multi-select
                'transition_duration': self.transition_duration,
                'output_width': self.output_width,
                'output_height': self.output_height,
                'use_first_video_size': self.use_first_video_size,
                'video_files': self.video_files[:10]  # Save first 10 for quick restore
            }
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            print(f"[WARNING] Failed to save settings: {e}")
    
    def load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                if 'grid_cols' in settings:
                    self.grid_cols = settings['grid_cols']
                    if hasattr(self, 'grid_cols_var'):
                        self.grid_cols_var.set(str(self.grid_cols))
                
                if 'auto_export_enabled' in settings:
                    self.auto_export_enabled = settings['auto_export_enabled']
                    if self.auto_export_var is not None:
                        self.auto_export_var.set(self.auto_export_enabled)
                
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
                
                # Update UI label if it exists
                if hasattr(self, 'transition_selection_label'):
                    self.update_transition_selection_label()
                
                if 'transition_duration' in settings:
                    self.transition_duration = settings['transition_duration']
                    if hasattr(self, 'transition_duration_var'):
                        self.transition_duration_var.set(str(self.transition_duration))
                
                # Load output size settings
                if 'use_first_video_size' in settings:
                    self.use_first_video_size = settings['use_first_video_size']
                if 'output_width' in settings:
                    self.output_width = settings['output_width']
                if 'output_height' in settings:
                    self.output_height = settings['output_height']
                
                # Update output size label if it exists
                if hasattr(self, 'output_size_label'):
                    self.update_output_size_label()
                
                self.log("[INFO] Settings loaded")
        
        except Exception as e:
            print(f"[WARNING] Failed to load settings: {e}")
    
    def on_closing(self):
        """Handle application closing."""
        self.save_settings()
        self.root.destroy()


def main():
    # Use TkinterDnD root if available
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = VideoEditorGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()


if __name__ == '__main__':
    main()

