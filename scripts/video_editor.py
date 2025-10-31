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
        self.grid_cols = 4
        
        # Settings file path
        self.settings_file = os.path.join(self.root_dir, "video_editor_settings.json")
        
        # UI state
        self.drag_start_index = None
        self.drag_current_index = None
        
        # Check FFmpeg availability first
        self.check_ffmpeg()
        
        self.setup_ui()
        self.load_settings()
        self.check_ffmpeg_availability()
    
    def _escape_for_concat(self, file_path: str) -> str:
        """Return a POSIX-style path with quotes escaped for ffmpeg concat demuxer."""
        # Normalize to absolute POSIX path to avoid backslash escaping issues on Windows
        posix_path = Path(file_path).resolve().as_posix()
        # Escape single quotes per ffmpeg concat demuxer rules
        return posix_path.replace("'", r"\'")

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
        grid_spin = ttk.Spinbox(toolbar, from_=1, to=10, textvariable=self.grid_cols_var, width=5)
        grid_spin.pack(side='left', padx=5)
        grid_spin.bind('<Return>', lambda e: self.update_grid())
        
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
            self.grid_cols = int(self.grid_cols_var.get())
        except ValueError:
            self.grid_cols = 4
            self.grid_cols_var.set('4')
        
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
            for file in files:
                if file not in self.video_files:
                    self.video_files.append(file)
            
            self.log(f"[INFO] Added {len(files)} video file(s)")
            self.refresh_grid()
            self.save_settings()
    
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
        
        # Configure grid columns
        for i in range(self.grid_cols):
            self.grid_widget.grid_columnconfigure(i, weight=1)
        
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
                
                temp_thumb = os.path.join(self.root_dir, 'temp_thumb.jpg')
                
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
                # Add new videos
                added_count = 0
                for video_file in video_files:
                    if video_file not in self.video_files:
                        self.video_files.append(video_file)
                        added_count += 1
                
                if added_count > 0:
                    self.log(f"[INFO] Added {added_count} video file(s) via drag-and-drop")
                    self.refresh_grid()
                    self.save_settings()
                else:
                    self.log("[INFO] All dropped videos already added")
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
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Create concat file
            concat_file = self._write_concat_file()
            
            # Use concat demuxer with faster encoding for preview
            cmd = f'{ffmpeg_cmd} -f concat -safe 0 -i "{concat_file}" -c:v libx264 -preset ultrafast -crf 28 -c:a aac -b:a 128k -y "{preview_file}"'
            
            self.root.after(0, lambda: self.log(f"[DEBUG] Preview FFmpeg command: {cmd}"))
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
            
            # Clean up concat file
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
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Create concat file
            concat_file = self._write_concat_file()
            
            # Use concat demuxer for lossless combination
            cmd = f'{ffmpeg_cmd} -f concat -safe 0 -i "{concat_file}" -c copy -y "{output_file}"'
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir, shell=True)
            
            # Clean up concat file
            try:
                os.remove(concat_file)
            except:
                pass
            
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
        try:
            ffmpeg_cmd = self.get_ffmpeg_command()
            
            # Create concat file
            concat_file = self._write_concat_file()
            
            # Use concat demuxer
            cmd = [ffmpeg_cmd, '-f', 'concat', '-safe', '0', '-i', concat_file, 
                  '-c', 'copy', '-y', output_file]
            
            self.root.after(0, lambda: self.log(f"[DEBUG] FFmpeg command: {' '.join(cmd)}"))
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root_dir)
            
            # Clean up concat file
            try:
                os.remove(concat_file)
            except:
                pass
            
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
            self.root.after(0, lambda: self.root.config(cursor=''))
    
    def set_grid_columns(self):
        """Set grid columns."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Set Grid Columns")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Number of columns:").pack(pady=20)
        
        cols_var = tk.StringVar(value=str(self.grid_cols))
        cols_spin = ttk.Spinbox(dialog, from_=1, to=10, textvariable=cols_var, width=10)
        cols_spin.pack(pady=10)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        
        def apply_change():
            try:
                self.grid_cols = int(cols_var.get())
                self.grid_cols_var.set(str(self.grid_cols))
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
                    'grid_cols': self.grid_cols
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
                self.grid_cols = project_data.get('grid_cols', 4)
                self.grid_cols_var.set(str(self.grid_cols))
                
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
                    self.grid_cols_var.set(str(self.grid_cols))
                
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

