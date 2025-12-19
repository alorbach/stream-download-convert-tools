"""
Image Format Converter - Aspect Ratio and Format Conversion Tool

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
from pathlib import Path
from PIL import Image, ImageTk

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
try:
    from lib.base_gui import BaseAudioGUI
    from lib.ffmpeg_utils import FFmpegManager
except ImportError:
    # Fallback if base_gui is not available
    class BaseAudioGUI:
        def __init__(self, root, title):
            self.root = root
            self.root.title(title)
            self.is_busy = False
        
        def log(self, message):
            print(message)
        
        def browse_folder(self, initial_dir=None):
            folder = filedialog.askdirectory(initialdir=initial_dir)
            return folder if folder else None
    
    class FFmpegManager:
        def __init__(self, root_dir, log_callback=None):
            self.root_dir = root_dir
            self.ffmpeg_path = None
        
        def check_ffmpeg(self):
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.ffmpeg_path = 'ffmpeg'
                    return True
            except:
                pass
            return False
        
        def get_ffmpeg_command(self):
            return self.ffmpeg_path if self.ffmpeg_path else 'ffmpeg'


class ImageFormatConverterGUI(BaseAudioGUI):
    def __init__(self, root):
        if DND_AVAILABLE:
            super().__init__(root, "Image & Video Format Converter")
        else:
            super().__init__(root, "Image & Video Format Converter")
        self.root.geometry("900x800")
        
        self.selected_files = []
        self.log_text = None  # Will be initialized in setup_ui()
        
        # Initialize FFmpeg manager (with safe log callback)
        root_dir = os.path.dirname(os.path.dirname(__file__))
        self.ffmpeg_manager = FFmpegManager(root_dir, log_callback=lambda msg: self._safe_log(f"[FFmpeg] {msg}"))
        
        # Aspect ratio presets (width:height) with standard resolutions
        self.aspect_ratios = {
            "1x1 (Square)": (1, 1),
            "16x9 (Landscape)": (16, 9),
            "9x16 (Portrait)": (9, 16),
            "4x3 (Standard)": (4, 3),
            "3x4 (Portrait Standard)": (3, 4),
            "21x9 (Ultrawide)": (21, 9),
            "9x21 (Tall)": (9, 21),
            "5x4 (Classic)": (5, 4),
            "4x5 (Portrait Classic)": (4, 5),
        }
        
        # Standard resolutions for common aspect ratios (width, height)
        self.standard_resolutions = {
            (1, 1): [(1080, 1080), (720, 720), (512, 512)],
            (16, 9): [(1920, 1080), (1280, 720), (854, 480)],
            (9, 16): [(1080, 1920), (720, 1280), (540, 960)],
            (4, 3): [(1920, 1440), (1280, 960), (640, 480)],
            (3, 4): [(1080, 1440), (720, 960), (540, 720)],
            (21, 9): [(2560, 1080), (1920, 822)],
            (9, 21): [(1080, 2520), (720, 1680)],
            (5, 4): [(1280, 1024), (800, 640)],
            (4, 5): [(1080, 1350), (720, 900)],
        }
        
        self.setup_ui()
        
        # Check FFmpeg after UI is initialized
        if not self.ffmpeg_manager.check_ffmpeg():
            self.log("[WARNING] FFmpeg not found. Video conversion will not be available.")
    
    def setup_ui(self):
        # File selection frame
        top_frame = ttk.LabelFrame(self.root, text="File Selection", padding=10)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="Select Image Files", command=self.select_files).pack(side='left', padx=5)
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

        # Drag-and-drop support for adding image files
        if DND_AVAILABLE:
            try:
                self.file_listbox.drop_target_register(DND_FILES)
                self.file_listbox.dnd_bind('<<Drop>>', self.on_drop_files)
            except Exception:
                pass
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.root, text="Conversion Settings", padding=10)
        settings_frame.pack(fill='x', padx=10, pady=10)
        
        # Info label about output location
        info_label = ttk.Label(settings_frame, text="Output: Same folder as source file with aspect ratio suffix (e.g., image_16x9.jpg)", 
                               font=('Arial', 8), foreground="gray")
        info_label.grid(row=0, column=0, columnspan=3, sticky='w', pady=5)
        
        # Aspect ratio selection
        ttk.Label(settings_frame, text="Target Aspect Ratio:").grid(row=1, column=0, sticky='w', pady=5)
        self.aspect_ratio_var = tk.StringVar(value="16x9 (Landscape)")
        self.aspect_combo = ttk.Combobox(settings_frame, textvariable=self.aspect_ratio_var, width=25, state='readonly')
        self.aspect_combo['values'] = tuple(self.aspect_ratios.keys())
        self.aspect_combo.grid(row=1, column=1, sticky='w', padx=5)
        self.aspect_combo.bind('<<ComboboxSelected>>', self.on_aspect_ratio_change)
        
        # Custom aspect ratio
        custom_frame = ttk.Frame(settings_frame)
        custom_frame.grid(row=2, column=0, columnspan=3, sticky='w', pady=5)
        ttk.Label(custom_frame, text="Custom Ratio:").pack(side='left', padx=5)
        self.custom_width_var = tk.StringVar(value="16")
        self.custom_height_var = tk.StringVar(value="9")
        ttk.Entry(custom_frame, textvariable=self.custom_width_var, width=5).pack(side='left', padx=2)
        ttk.Label(custom_frame, text=":").pack(side='left')
        ttk.Entry(custom_frame, textvariable=self.custom_height_var, width=5).pack(side='left', padx=2)
        ttk.Button(custom_frame, text="Apply Custom", command=self.apply_custom_ratio).pack(side='left', padx=5)
        
        # Crop position
        ttk.Label(settings_frame, text="Crop Position:").grid(row=3, column=0, sticky='w', pady=5)
        crop_frame = ttk.Frame(settings_frame)
        crop_frame.grid(row=3, column=1, sticky='w', padx=5)
        self.crop_position_var = tk.StringVar(value="center")
        ttk.Radiobutton(crop_frame, text="Center", variable=self.crop_position_var, value="center").pack(side='left', padx=5)
        ttk.Radiobutton(crop_frame, text="Top", variable=self.crop_position_var, value="top").pack(side='left', padx=5)
        ttk.Radiobutton(crop_frame, text="Bottom", variable=self.crop_position_var, value="bottom").pack(side='left', padx=5)
        ttk.Radiobutton(crop_frame, text="Left", variable=self.crop_position_var, value="left").pack(side='left', padx=5)
        ttk.Radiobutton(crop_frame, text="Right", variable=self.crop_position_var, value="right").pack(side='left', padx=5)
        
        # Output format
        ttk.Label(settings_frame, text="Output Format:").grid(row=4, column=0, sticky='w', pady=5)
        self.output_format_var = tk.StringVar(value="JPG")
        format_frame = ttk.Frame(settings_frame)
        format_frame.grid(row=4, column=1, sticky='w', padx=5)
        ttk.Radiobutton(format_frame, text="JPG", variable=self.output_format_var, value="JPG").pack(side='left', padx=5)
        ttk.Radiobutton(format_frame, text="PNG", variable=self.output_format_var, value="PNG").pack(side='left', padx=5)
        ttk.Radiobutton(format_frame, text="MP4", variable=self.output_format_var, value="MP4").pack(side='left', padx=5)
        
        # Input format detection display
        ttk.Label(settings_frame, text="Input Format:").grid(row=5, column=0, sticky='w', pady=5)
        self.input_format_label = ttk.Label(settings_frame, text="No file selected", foreground="gray")
        self.input_format_label.grid(row=5, column=1, sticky='w', padx=5)
        
        # Processing frame
        process_frame = ttk.Frame(self.root)
        process_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(process_frame, text="Convert Selected Files", command=self.convert_selected).pack(side='left', padx=5)
        ttk.Button(process_frame, text="Convert All Files", command=self.convert_all).pack(side='left', padx=5)
        
        self.progress = ttk.Progressbar(process_frame, mode='determinate')
        self.progress.pack(fill='x', padx=5, pady=5, expand=True)
        
        self.progress_label = ttk.Label(process_frame, text="")
        self.progress_label.pack(anchor='w')
        
        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Conversion Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.pack(fill='both', expand=True)
        
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = "Supported formats: Images (JPG, PNG, BMP, GIF, TIFF, WEBP) | Videos (MP4, AVI, MOV, MKV, WEBM, FLV) | Drag and drop files to add them"
        ttk.Label(info_frame, text=info_text, font=('Arial', 8)).pack()
        
        # Bind selection change to update input format display
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_selection_change)
    
    
    def on_aspect_ratio_change(self, event=None):
        ratio_name = self.aspect_ratio_var.get()
        if ratio_name in self.aspect_ratios:
            width, height = self.aspect_ratios[ratio_name]
            self.custom_width_var.set(str(width))
            self.custom_height_var.set(str(height))
    
    def apply_custom_ratio(self):
        try:
            width = int(self.custom_width_var.get())
            height = int(self.custom_height_var.get())
            if width <= 0 or height <= 0:
                raise ValueError("Dimensions must be positive")
            # Update combobox to show custom ratio
            custom_name = f"{width}:{height} (Custom)"
            if custom_name not in self.aspect_ratios:
                self.aspect_ratios[custom_name] = (width, height)
                # Update combobox values
                current_values = list(self.aspect_combo['values'])
                if custom_name not in current_values:
                    self.aspect_combo['values'] = tuple(list(current_values) + [custom_name])
            self.aspect_ratio_var.set(custom_name)
            self.log(f"[INFO] Applied custom aspect ratio: {width}:{height}")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid positive numbers for aspect ratio.\n{str(e)}")
    
    def is_video_file(self, file_path):
        """Check if file is a video based on extension."""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ogv'}
        ext = os.path.splitext(file_path)[1].lower()
        return ext in video_extensions
    
    def get_video_resolution(self, video_file):
        """Get video resolution (width, height) from video file."""
        try:
            ffmpeg_cmd = self.ffmpeg_manager.get_ffmpeg_command()
            probe_cmd = [ffmpeg_cmd, '-i', video_file, '-f', 'null', '-']
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            
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
    
    def on_file_selection_change(self, event=None):
        selection = self.file_listbox.curselection()
        if selection:
            idx = selection[0]
            if idx < len(self.selected_files):
                file_path = self.selected_files[idx]
                try:
                    if self.is_video_file(file_path):
                        # Handle video file
                        width, height = self.get_video_resolution(file_path)
                        if width and height:
                            aspect_ratio = width / height if height > 0 else 0
                            ext = os.path.splitext(file_path)[1].upper().replace('.', '')
                            self.input_format_label.config(
                                text=f"Video ({ext}) - {width}x{height} ({aspect_ratio:.2f}:1)",
                                foreground="black"
                            )
                        else:
                            self.input_format_label.config(text=f"Video - Unable to read resolution", foreground="orange")
                    else:
                        # Handle image file
                        with Image.open(file_path) as img:
                            width, height = img.size
                            format_name = img.format or "Unknown"
                            aspect_ratio = width / height if height > 0 else 0
                            self.input_format_label.config(
                                text=f"{format_name} - {width}x{height} ({aspect_ratio:.2f}:1)",
                                foreground="black"
                            )
                except Exception as e:
                    self.input_format_label.config(text=f"Error reading file: {str(e)}", foreground="red")
        else:
            self.input_format_label.config(text="No file selected", foreground="gray")
    
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select Image or Video Files",
            filetypes=[
                ("All Supported", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp *.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.m4v"),
                ("Image Files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.webp"),
                ("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.m4v"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All Files", "*.*")
            ]
        )
        
        if files:
            added = 0
            has_video = False
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
                    added += 1
                    if self.is_video_file(file):
                        has_video = True
            
            self.update_file_list()
            # Auto-select MP4 format if video files were added
            if has_video:
                self.output_format_var.set("MP4")
            self.log(f"[INFO] Added {added} file(s) to selection")
    
    def clear_selection(self):
        self.selected_files.clear()
        self.update_file_list()
        self.input_format_label.config(text="No file selected", foreground="gray")
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
        if not DND_AVAILABLE:
            return
        
        paths = self._parse_dropped_paths(event.data)
        allowed_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp',
                      '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ogv'}
        added = 0
        has_video = False
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext in allowed_ext and p not in self.selected_files:
                self.selected_files.append(p)
                added += 1
                if self.is_video_file(p):
                    has_video = True
        if added:
            self.update_file_list()
            # Auto-select MP4 format if video files were added
            if has_video:
                self.output_format_var.set("MP4")
            self.log(f"[INFO] Added {added} file(s) via drag and drop")
    
    def _safe_log(self, message):
        """Safe log method that works even before UI is initialized"""
        print(message)
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
            except:
                pass
    
    def log(self, message):
        """Log message to both console and UI log text widget"""
        print(message)
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
            except:
                pass
    
    def get_target_aspect_ratio(self):
        ratio_name = self.aspect_ratio_var.get()
        if ratio_name in self.aspect_ratios:
            return self.aspect_ratios[ratio_name]
        else:
            # Try to parse custom ratio
            try:
                width = int(self.custom_width_var.get())
                height = int(self.custom_height_var.get())
                return (width, height)
            except:
                return (16, 9)  # Default
    
    def get_aspect_ratio_suffix(self, target_ratio):
        """Get the aspect ratio suffix string (e.g., '16x9' or '3x2')"""
        width, height = target_ratio
        return f"{width}x{height}"
    
    def get_standard_resolution(self, target_ratio, original_width=None, original_height=None):
        """Get the best standard resolution for the target aspect ratio"""
        if target_ratio not in self.standard_resolutions:
            # Fallback: calculate based on original dimensions
            if original_width and original_height:
                if original_width / original_height > target_ratio[0] / target_ratio[1]:
                    # Wider than target - use height as base
                    height = original_height
                    width = int(height * target_ratio[0] / target_ratio[1])
                else:
                    # Taller than target - use width as base
                    width = original_width
                    height = int(width / (target_ratio[0] / target_ratio[1]))
                # Make even
                width = width - (width % 2)
                height = height - (height % 2)
                return width, height
            # Default fallback
            return 720, 1280 if target_ratio == (9, 16) else (1280, 720)
        
        # Get standard resolutions for this aspect ratio
        resolutions = self.standard_resolutions[target_ratio]
        
        # If we have original dimensions, pick the closest standard resolution
        if original_width and original_height:
            original_area = original_width * original_height
            best_res = resolutions[0]  # Default to highest quality
            best_diff = float('inf')
            
            for res in resolutions:
                res_area = res[0] * res[1]
                diff = abs(res_area - original_area)
                if diff < best_diff:
                    best_diff = diff
                    best_res = res
            
            return best_res
        
        # Default to highest quality (first in list)
        return resolutions[0]
    
    def convert_image(self, input_path, output_path, target_ratio, crop_position, output_format):
        """Convert a single image to target aspect ratio and format"""
        try:
            with Image.open(input_path) as img:
                # Convert to RGB if necessary (for formats like PNG with transparency)
                if output_format == "JPG" and img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                original_width, original_height = img.size
                original_ratio = original_width / original_height if original_height > 0 else 0
                target_ratio_value = target_ratio[0] / target_ratio[1] if target_ratio[1] > 0 else 0
                
                # Calculate new dimensions
                if original_ratio > target_ratio_value:
                    # Image is wider than target - crop width
                    new_height = original_height
                    new_width = int(original_height * target_ratio_value)
                else:
                    # Image is taller than target - crop height
                    new_width = original_width
                    new_height = int(original_width / target_ratio_value)
                
                # Calculate crop box based on crop position
                left = 0
                top = 0
                right = new_width
                bottom = new_height
                
                if crop_position == "center":
                    left = (original_width - new_width) // 2
                    top = (original_height - new_height) // 2
                    right = left + new_width
                    bottom = top + new_height
                elif crop_position == "top":
                    left = (original_width - new_width) // 2
                    top = 0
                    right = left + new_width
                    bottom = new_height
                elif crop_position == "bottom":
                    left = (original_width - new_width) // 2
                    top = original_height - new_height
                    right = left + new_width
                    bottom = original_height
                elif crop_position == "left":
                    left = 0
                    top = (original_height - new_height) // 2
                    right = new_width
                    bottom = top + new_height
                elif crop_position == "right":
                    left = original_width - new_width
                    top = (original_height - new_height) // 2
                    right = original_width
                    bottom = top + new_height
                
                # Crop image
                cropped_img = img.crop((left, top, right, bottom))
                
                # Save with appropriate format
                if output_format == "MP4":
                    # Convert image to MP4 video (single frame, 1 second duration)
                    return self._convert_image_to_mp4(cropped_img, output_path, target_ratio)
                elif output_format == "JPG":
                    cropped_img.save(output_path, "JPEG", quality=95)
                else:
                    cropped_img.save(output_path, "PNG")
                
                return True, None
        except Exception as e:
            return False, str(e)
    
    def _convert_image_to_mp4(self, img, output_path, target_ratio=None):
        """Convert a PIL Image to MP4 video (single frame, 1 second)"""
        try:
            ffmpeg_cmd = self.ffmpeg_manager.get_ffmpeg_command()
            if not ffmpeg_cmd or not self.ffmpeg_manager.check_ffmpeg():
                return False, "FFmpeg not available. Please install FFmpeg."
            
            # Save image to temporary file
            import tempfile
            temp_img = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            img.save(temp_img.name, "PNG")
            temp_img.close()
            
            try:
                width, height = img.size
                # If target ratio provided, use standard resolution
                if target_ratio:
                    output_width, output_height = self.get_standard_resolution(target_ratio, width, height)
                else:
                    output_width, output_height = width, height
                
                # Create 1-second video from image
                cmd = [ffmpeg_cmd, '-loop', '1', '-i', temp_img.name, 
                      '-t', '1', '-vf', f'scale={output_width}:{output_height}',
                      '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                      '-pix_fmt', 'yuv420p', '-y', output_path]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    return True, None
                else:
                    error_msg = result.stderr[-500:] if result.stderr else "Unknown FFmpeg error"
                    return False, error_msg
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_img.name)
                except:
                    pass
        except Exception as e:
            return False, str(e)
    
    def convert_video(self, input_path, output_path, target_ratio, crop_position, output_format):
        """Convert a video to target aspect ratio and format using FFmpeg"""
        try:
            ffmpeg_cmd = self.ffmpeg_manager.get_ffmpeg_command()
            if not ffmpeg_cmd or not self.ffmpeg_manager.check_ffmpeg():
                return False, "FFmpeg not available. Please install FFmpeg."
            
            # Get video resolution
            original_width, original_height = self.get_video_resolution(input_path)
            if not original_width or not original_height:
                return False, "Could not determine video resolution"
            
            # Get standard resolution for target aspect ratio
            output_width, output_height = self.get_standard_resolution(target_ratio, original_width, original_height)
            
            original_ratio = original_width / original_height if original_height > 0 else 0
            target_ratio_value = target_ratio[0] / target_ratio[1] if target_ratio[1] > 0 else 0
            
            # Calculate crop dimensions to match target aspect ratio
            if original_ratio > target_ratio_value:
                # Video is wider than target - crop width, keep full height
                crop_height = original_height
                crop_width = int(original_height * target_ratio_value)
            else:
                # Video is taller than target - crop height, keep full width
                crop_width = original_width
                crop_height = int(original_width / target_ratio_value)
            
            # Calculate crop position (x, y offsets)
            if crop_position == "center":
                crop_x = (original_width - crop_width) // 2
                crop_y = (original_height - crop_height) // 2
            elif crop_position == "top":
                crop_x = (original_width - crop_width) // 2
                crop_y = 0
            elif crop_position == "bottom":
                crop_x = (original_width - crop_width) // 2
                crop_y = original_height - crop_height
            elif crop_position == "left":
                crop_x = 0
                crop_y = (original_height - crop_height) // 2
            elif crop_position == "right":
                crop_x = original_width - crop_width
                crop_y = (original_height - crop_height) // 2
            else:
                crop_x = (original_width - crop_width) // 2
                crop_y = (original_height - crop_height) // 2
            
            # Build FFmpeg filter: crop then scale to exact output dimensions
            # This ensures the final output has exact aspect ratio
            crop_filter = f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y},scale={output_width}:{output_height}"
            
            # Build FFmpeg command
            cmd = [ffmpeg_cmd, '-i', input_path, '-vf', crop_filter]
            
            # Set output format and codec (videos always output as MP4)
            cmd.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])
            # Try to copy audio, fallback to AAC if copy fails
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            
            cmd.extend(['-y', output_path])  # -y to overwrite
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return True, None
            else:
                error_msg = result.stderr[-500:] if result.stderr else "Unknown FFmpeg error"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "FFmpeg operation timed out"
        except Exception as e:
            return False, str(e)
    
    def convert_selected(self):
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select files to convert.")
            return
        
        files_to_convert = [self.selected_files[idx] for idx in selection]
        self.convert_files(files_to_convert)
    
    def convert_all(self):
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please add files first.")
            return
        
        self.convert_files(self.selected_files)
    
    def convert_files(self, files_to_convert):
        if not files_to_convert:
            return
        
        if self.is_busy:
            messagebox.showwarning("Busy", "Conversion already in progress.")
            return
        
        target_ratio = self.get_target_aspect_ratio()
        crop_position = self.crop_position_var.get()
        output_format = self.output_format_var.get()
        aspect_suffix = self.get_aspect_ratio_suffix(target_ratio)
        
        # Check for overwrites first
        existing_files = []
        files_to_process = []
        
        for input_path in files_to_convert:
            # Get source file directory and base name
            source_dir = os.path.dirname(input_path)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            
            # Determine output extension based on input type and format selection
            if self.is_video_file(input_path):
                # Videos: use MP4 format (always MP4 for videos)
                ext = ".mp4"
            else:
                # Images: use selected format
                if output_format == "MP4":
                    # MP4 selected for images - convert to MP4 video (single frame)
                    ext = ".mp4"
                else:
                    ext = ".jpg" if output_format == "JPG" else ".png"
            
            # Create output filename with aspect ratio suffix: originalname_16x9.jpg/mp4
            output_filename = f"{base_name}_{aspect_suffix}{ext}"
            output_path = os.path.join(source_dir, output_filename)
            
            if os.path.exists(output_path):
                existing_files.append(os.path.basename(output_path))
            files_to_process.append((input_path, output_path))
        
        # Ask user about overwriting if any files exist
        if existing_files:
            file_list = "\n".join(existing_files[:5])
            if len(existing_files) > 5:
                file_list += f"\n... and {len(existing_files) - 5} more"
            
            result = messagebox.askyesno(
                "Files Will Be Overwritten",
                f"The following {len(existing_files)} file(s) already exist:\n\n{file_list}\n\n"
                f"Overwrite these files?"
            )
            
            if not result:
                self.log("[INFO] Conversion cancelled by user (overwrite declined)")
                return
        
        if not files_to_process:
            messagebox.showinfo("No Files", "No files to convert.")
            return
        
        # Start conversion in thread
        thread = threading.Thread(
            target=self._convert_files_thread,
            args=(files_to_process, target_ratio, crop_position, output_format)
        )
        thread.daemon = True
        thread.start()
    
    def _convert_files_thread(self, files_to_process, target_ratio, crop_position, output_format):
        self.is_busy = True
        self.set_busy(True, "Converting files...")
        
        total = len(files_to_process)
        success_count = 0
        error_count = 0
        
        self.progress['maximum'] = total
        self.progress['value'] = 0
        
        for idx, (input_path, output_path) in enumerate(files_to_process):
            self.progress['value'] = idx + 1
            self.progress_label.config(text=f"Processing {idx + 1}/{total}: {os.path.basename(input_path)}")
            self.root.update_idletasks()
            
            # Determine if file is video or image and call appropriate conversion method
            if self.is_video_file(input_path):
                success, error = self.convert_video(input_path, output_path, target_ratio, crop_position, output_format)
            else:
                success, error = self.convert_image(input_path, output_path, target_ratio, crop_position, output_format)
            
            if success:
                success_count += 1
                self.log(f"[SUCCESS] Converted: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
            else:
                error_count += 1
                self.log(f"[ERROR] Failed to convert {os.path.basename(input_path)}: {error}")
        
        self.set_busy(False)
        self.progress_label.config(text=f"Completed: {success_count} successful, {error_count} errors")
        
        messagebox.showinfo(
            "Conversion Complete",
            f"Conversion finished!\n\nSuccess: {success_count}\nErrors: {error_count}"
        )
    
    def set_busy(self, busy=True, message=""):
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            self.progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            self.progress_label.config(text="")


def main():
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    app = ImageFormatConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
