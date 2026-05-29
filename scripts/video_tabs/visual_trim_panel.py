"""Embedded visual trim editor: preview, timeline handles, region list."""

import os
import subprocess
import threading
import time
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import cv2
    from PIL import Image, ImageTk
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_PREVIEW_AVAILABLE = True
except ImportError:
    np = None
    sd = None
    AUDIO_PREVIEW_AVAILABLE = False

from lib.video_utils import probe_duration, format_output_name, _subprocess_flags

PREVIEW_MAX_W = 640
PREVIEW_MAX_H = 360
TIMELINE_H = 56
HANDLE_W = 8
PAD = 12


def format_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f'{h:d}:{m:02d}:{s:05.2f}'
    return f'{m:d}:{s:05.2f}'


class VisualTrimPanel(ttk.Frame):
    """In-tab preview and timeline for marking multiple cut regions."""

    @staticmethod
    def is_available() -> bool:
        return CV2_AVAILABLE

    def __init__(self, parent, root, log_callback=None):
        super().__init__(parent)
        self.root = root
        self.log_callback = log_callback or (lambda msg: None)

        self.video_path = None
        self.duration = 0.0
        self.fps = 25.0
        self.cap = None
        self._photo = None
        self._play_running = False
        self._play_thread = None
        self._scrub_after_id = None
        self._last_scrub_draw = 0.0
        self._ffmpeg_cmd = 'ffmpeg'
        self._audio_samples = None
        self._audio_sr = 44100
        self._audio_load_thread = None

        self.current_time = tk.DoubleVar(value=0.0)
        self.in_time = tk.DoubleVar(value=0.0)
        self.out_time = tk.DoubleVar(value=0.0)
        self.regions = []

        self._drag_target = None
        self._timeline_w = 400

        self._build_ui()
        self._bind_keys()

    def log(self, message: str):
        self.log_callback(message)

    def _build_ui(self):
        if not CV2_AVAILABLE:
            ttk.Label(
                self,
                text='Visual trim requires opencv-python and Pillow. Install via requirements.txt.',
                wraplength=500,
            ).pack(padx=10, pady=20)
            return

        top = ttk.Frame(self)
        top.pack(fill='x', pady=(0, 4))
        self.lbl_video = ttk.Label(top, text='No video loaded')
        self.lbl_video.pack(side='left')
        self.lbl_time = ttk.Label(top, text='00:00.00 / 00:00.00')
        self.lbl_time.pack(side='right')

        self.preview_canvas = tk.Canvas(self, width=PREVIEW_MAX_W, height=PREVIEW_MAX_H, bg='#222222', highlightthickness=1)
        self.preview_canvas.pack(fill='x', pady=4)

        transport = ttk.Frame(self)
        transport.pack(fill='x', pady=2)
        ttk.Button(transport, text='Play', command=self.play).pack(side='left', padx=2)
        ttk.Button(transport, text='Pause', command=self.pause).pack(side='left', padx=2)
        ttk.Button(transport, text='Stop', command=self.stop).pack(side='left', padx=2)
        audio_hint = 'Audio: on' if AUDIO_PREVIEW_AVAILABLE else 'Audio: install sounddevice'
        self.lbl_audio = ttk.Label(transport, text=audio_hint)
        self.lbl_audio.pack(side='left', padx=(8, 0))
        ttk.Label(transport, text='Position:').pack(side='left', padx=(12, 2))
        self.time_scale = ttk.Scale(transport, from_=0, to=100, orient='horizontal', command=self._on_scale_scrub)
        self.time_scale.pack(side='left', fill='x', expand=True, padx=4)

        ttk.Label(self, text='Timeline (drag handles or click to seek):').pack(anchor='w')
        self.timeline_canvas = tk.Canvas(self, height=TIMELINE_H, bg='#333333', highlightthickness=1)
        self.timeline_canvas.pack(fill='x', pady=4)
        self.timeline_canvas.bind('<Configure>', self._on_timeline_resize)
        self.timeline_canvas.bind('<ButtonPress-1>', self._on_timeline_press)
        self.timeline_canvas.bind('<B1-Motion>', self._on_timeline_drag)
        self.timeline_canvas.bind('<ButtonRelease-1>', self._on_timeline_release)

        marks = ttk.Frame(self)
        marks.pack(fill='x', pady=4)
        ttk.Button(marks, text='Set In (I)', command=self.set_in).pack(side='left', padx=2)
        ttk.Button(marks, text='Set Out (O)', command=self.set_out).pack(side='left', padx=2)
        ttk.Label(marks, text='In (s):').pack(side='left', padx=(8, 0))
        self.in_entry = ttk.Entry(marks, textvariable=self.in_time, width=10)
        self.in_entry.pack(side='left', padx=2)
        self.in_entry.bind('<Return>', self._on_in_entry)
        self.in_entry.bind('<FocusOut>', self._on_in_entry)
        ttk.Label(marks, text='Out (s):').pack(side='left', padx=(8, 0))
        self.out_entry = ttk.Entry(marks, textvariable=self.out_time, width=10)
        self.out_entry.pack(side='left', padx=2)
        self.out_entry.bind('<Return>', self._on_out_entry)
        self.out_entry.bind('<FocusOut>', self._on_out_entry)
        ttk.Button(marks, text='Add cut', command=self.add_region).pack(side='left', padx=8)

        reg_frame = ttk.LabelFrame(self, text='Cut regions', padding=4)
        reg_frame.pack(fill='both', expand=True, pady=4)
        cols = ('id', 'start', 'end', 'duration')
        self.regions_tree = ttk.Treeview(reg_frame, columns=cols, show='headings', height=4)
        for c, w in zip(cols, (80, 90, 90, 80)):
            self.regions_tree.heading(c, text=c.capitalize())
            self.regions_tree.column(c, width=w, anchor='center')
        sy = ttk.Scrollbar(reg_frame, orient='vertical', command=self.regions_tree.yview)
        self.regions_tree.configure(yscrollcommand=sy.set)
        self.regions_tree.pack(side='left', fill='both', expand=True)
        sy.pack(side='right', fill='y')
        self.regions_tree.bind('<<TreeviewSelect>>', self._on_region_select)

        rb = ttk.Frame(reg_frame)
        rb.pack(fill='x', pady=(4, 0))
        ttk.Button(rb, text='Remove selected', command=self.remove_region).pack(side='left', padx=2)
        ttk.Button(rb, text='Clear all', command=self.clear_regions).pack(side='left', padx=2)

        hint = ttk.Label(
            self,
            text='Shortcuts: I = In, O = Out, Space = Play/Pause. Select a video in the list above.',
            font=('Arial', 8),
        )
        hint.pack(anchor='w', pady=2)

    def _bind_keys(self):
        for w in (self, self.preview_canvas, self.timeline_canvas):
            w.bind('<KeyPress-i>', lambda e: self.set_in())
            w.bind('<KeyPress-I>', lambda e: self.set_in())
            w.bind('<KeyPress-o>', lambda e: self.set_out())
            w.bind('<KeyPress-O>', lambda e: self.set_out())
            w.bind('<KeyPress-space>', lambda e: self._toggle_play())
            w.bind('<Button-1>', lambda e: e.widget.focus_set(), add='+')

    def _toggle_play(self):
        if self._play_running:
            self.pause()
        else:
            self.play()

    def _stop_audio(self):
        if AUDIO_PREVIEW_AVAILABLE and sd is not None:
            try:
                sd.stop()
            except Exception:
                pass

    def _start_audio_at(self, t: float):
        if not AUDIO_PREVIEW_AVAILABLE or self._audio_samples is None:
            return
        self._stop_audio()
        start_sample = int(max(0.0, t) * self._audio_sr)
        if start_sample >= len(self._audio_samples):
            return
        remaining = self._audio_samples[start_sample:]
        if len(remaining) == 0:
            return
        try:
            sd.play(remaining, self._audio_sr, blocking=False)
        except Exception:
            pass

    def _load_audio_async(self, path: str, ffmpeg_cmd: str):
        if not AUDIO_PREVIEW_AVAILABLE:
            return

        def worker():
            self._audio_samples = None
            self.root.after(0, lambda: self.lbl_audio.config(text='Audio: loading...'))
            try:
                cmd = [
                    ffmpeg_cmd, '-i', path, '-vn',
                    '-f', 'f32le', '-acodec', 'pcm_f32le',
                    '-ac', '2', '-ar', str(self._audio_sr), '-',
                ]
                result = subprocess.run(
                    cmd, capture_output=True,
                    creationflags=_subprocess_flags(), timeout=900,
                )
                if result.returncode != 0 or not result.stdout:
                    self.root.after(0, lambda: self.lbl_audio.config(text='Audio: none'))
                    return
                data = np.frombuffer(result.stdout, dtype=np.float32)
                if len(data) < 2:
                    self.root.after(0, lambda: self.lbl_audio.config(text='Audio: none'))
                    return
                if len(data) % 2:
                    data = data[:-1]
                self._audio_samples = data.reshape(-1, 2)
                self.root.after(0, lambda: self.lbl_audio.config(text='Audio: ready'))
            except Exception:
                self._audio_samples = None
                self.root.after(0, lambda: self.lbl_audio.config(text='Audio: failed'))

        if self._audio_load_thread and self._audio_load_thread.is_alive():
            pass
        self._audio_load_thread = threading.Thread(target=worker, daemon=True)
        self._audio_load_thread.start()

    def release_capture(self):
        self.stop()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def load_video(self, path: str, ffmpeg_cmd: str = 'ffmpeg') -> bool:
        if not CV2_AVAILABLE:
            return False
        self.release_capture()
        self._ffmpeg_cmd = ffmpeg_cmd
        self._audio_samples = None
        self.regions.clear()
        self._refresh_regions_tree()
        self.video_path = path
        if not path or not os.path.isfile(path):
            self.duration = 0.0
            self.lbl_video.config(text='No video loaded')
            self._redraw_timeline()
            self.preview_canvas.delete('all')
            return False

        ffmpeg = None
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            self.cap = None
            messagebox.showerror('Error', f'Could not open video:\n{path}')
            return False

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        if self.fps <= 0:
            self.fps = 25.0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if frame_count > 0:
            self.duration = frame_count / self.fps
        else:
            self.duration = probe_duration(ffmpeg_cmd, path) or 0.0

        if self.duration <= 0:
            messagebox.showerror('Error', 'Could not determine video duration')
            self.release_capture()
            return False

        self.lbl_video.config(text=os.path.basename(path))
        self.in_time.set(0.0)
        self.out_time.set(min(5.0, self.duration))
        self.current_time.set(0.0)
        self.time_scale.config(to=self.duration)
        self.time_scale.set(0)
        self._seek_and_show(0.0)
        self._redraw_timeline()
        self._load_audio_async(path, ffmpeg_cmd)
        self.log(f'[INFO] Loaded {os.path.basename(path)} ({format_time(self.duration)})')
        return True

    def _time_to_x(self, t: float) -> float:
        if self.duration <= 0:
            return PAD
        usable = max(1, self._timeline_w - 2 * PAD)
        return PAD + (t / self.duration) * usable

    def _x_to_time(self, x: float) -> float:
        usable = max(1, self._timeline_w - 2 * PAD)
        t = ((x - PAD) / usable) * self.duration
        return max(0.0, min(t, self.duration))

    def _on_timeline_resize(self, event=None):
        self._timeline_w = self.timeline_canvas.winfo_width()
        self._redraw_timeline()

    def _redraw_timeline(self):
        c = self.timeline_canvas
        c.delete('all')
        w = self._timeline_w
        h = TIMELINE_H
        if self.duration <= 0:
            c.create_text(w // 2, h // 2, text='Load a video', fill='white')
            return

        y0, y1 = 16, h - 16
        c.create_rectangle(PAD, y0, w - PAD, y1, fill='#555555', outline='#888888')
        for seg in self.regions:
            x1 = self._time_to_x(seg['start_sec'])
            x2 = self._time_to_x(seg['end_sec'])
            c.create_rectangle(x1, y0, x2, y1, fill='#336633', outline='#228822')

        t_in = self.in_time.get()
        t_out = self.out_time.get()
        if t_out < t_in:
            t_out = t_in
        xi = self._time_to_x(t_in)
        xo = self._time_to_x(t_out)
        c.create_rectangle(xi, y0, xo, y1, fill='#4477aa', outline='')
        c.create_rectangle(xi - HANDLE_W, y0 - 4, xi + HANDLE_W, y1 + 4, fill='#ffcc00', tags='handle_in')
        c.create_rectangle(xo - HANDLE_W, y0 - 4, xo + HANDLE_W, y1 + 4, fill='#ff6600', tags='handle_out')
        xp = self._time_to_x(self.current_time.get())
        c.create_line(xp, 4, xp, h - 4, fill='#ffffff', width=2, tags='playhead')

    def _hit_handle(self, x: float, y: float):
        items = self.timeline_canvas.find_overlapping(x, y, x, y)
        for item in items:
            tags = self.timeline_canvas.gettags(item)
            if 'handle_in' in tags:
                return 'in'
            if 'handle_out' in tags:
                return 'out'
        return None

    def _on_timeline_press(self, event):
        self.timeline_canvas.focus_set()
        handle = self._hit_handle(event.x, event.y)
        if handle:
            self._drag_target = handle
        else:
            self._drag_target = 'seek'
            t = self._x_to_time(event.x)
            self._set_current_time(t, restart_audio=self._play_running)

    def _on_timeline_drag(self, event):
        t = self._x_to_time(event.x)
        if self._drag_target == 'in':
            t = min(t, self.out_time.get() - 0.05)
            self.in_time.set(max(0.0, t))
        elif self._drag_target == 'out':
            t = max(t, self.in_time.get() + 0.05)
            self.out_time.set(min(self.duration, t))
        elif self._drag_target == 'seek':
            self._set_current_time(t, restart_audio=self._play_running)
        self._redraw_timeline()

    def _on_timeline_release(self, event):
        self._drag_target = None

    def _on_scale_scrub(self, value):
        if self.duration <= 0:
            return
        now = time.time()
        if now - self._last_scrub_draw < 0.066:
            if self._scrub_after_id:
                self.root.after_cancel(self._scrub_after_id)
            self._scrub_after_id = self.root.after(66, lambda v=value: self._apply_scale(v))
            return
        self._apply_scale(value)

    def _apply_scale(self, value):
        self._scrub_after_id = None
        self._last_scrub_draw = time.time()
        self._set_current_time(
            float(value), update_scale=False, restart_audio=self._play_running,
        )

    def _set_current_time(self, t: float, update_scale: bool = True, restart_audio: bool = False):
        t = max(0.0, min(t, self.duration))
        self.current_time.set(t)
        if update_scale:
            self.time_scale.set(t)
        if restart_audio and self._play_running:
            self._start_audio_at(t)
        self.lbl_time.config(text=f'{format_time(t)} / {format_time(self.duration)}')
        self._seek_and_show(t)
        self._redraw_timeline()

    def _seek_and_show(self, t: float):
        if not self.cap or not CV2_AVAILABLE:
            return
        self.cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = self.cap.read()
        if not ret:
            return
        self._show_frame(frame)

    def _show_frame(self, frame):
        h, w = frame.shape[:2]
        scale = min(PREVIEW_MAX_W / w, PREVIEW_MAX_H / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        if nw < 1 or nh < 1:
            return
        resized = cv2.resize(frame, (nw, nh))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        self._photo = ImageTk.PhotoImage(img)
        self.preview_canvas.delete('all')
        x = (PREVIEW_MAX_W - nw) // 2
        y = (PREVIEW_MAX_H - nh) // 2
        self.preview_canvas.create_image(x, y, anchor='nw', image=self._photo)

    def set_in(self):
        self.in_time.set(self.current_time.get())
        if self.out_time.get() <= self.in_time.get():
            self.out_time.set(min(self.duration, self.in_time.get() + 1.0))
        self._redraw_timeline()

    def set_out(self):
        self.out_time.set(self.current_time.get())
        if self.out_time.get() <= self.in_time.get():
            self.in_time.set(max(0.0, self.out_time.get() - 1.0))
        self._redraw_timeline()

    def _on_in_entry(self, event=None):
        try:
            t = float(self.in_time.get())
            t = max(0.0, min(t, self.duration))
            self.in_time.set(t)
            if self.out_time.get() <= t:
                self.out_time.set(min(self.duration, t + 0.1))
            self._redraw_timeline()
        except ValueError:
            pass

    def _on_out_entry(self, event=None):
        try:
            t = float(self.out_time.get())
            t = max(0.0, min(t, self.duration))
            self.out_time.set(t)
            if t <= self.in_time.get():
                self.in_time.set(max(0.0, t - 0.1))
            self._redraw_timeline()
        except ValueError:
            pass

    def add_region(self):
        if self.duration <= 0:
            messagebox.showwarning('Warning', 'Load a video first')
            return
        start = float(self.in_time.get())
        end = float(self.out_time.get())
        if end - start < 0.05:
            messagebox.showwarning('Warning', 'Out must be after In (at least 0.05s)')
            return
        seg_id = f'cut_{len(self.regions) + 1:02d}'
        self.regions.append({
            'id': seg_id,
            'start_sec': start,
            'end_sec': end,
            'duration': end - start,
        })
        self._refresh_regions_tree()
        self.log(f'[INFO] Added region {seg_id}: {format_time(start)} - {format_time(end)}')

    def remove_region(self):
        sel = self.regions_tree.selection()
        if not sel:
            return
        idx = self.regions_tree.index(sel[0])
        if 0 <= idx < len(self.regions):
            self.regions.pop(idx)
            self._refresh_regions_tree()

    def clear_regions(self):
        self.regions.clear()
        self._refresh_regions_tree()

    def _refresh_regions_tree(self):
        for item in self.regions_tree.get_children():
            self.regions_tree.delete(item)
        for seg in self.regions:
            self.regions_tree.insert('', 'end', values=(
                seg['id'],
                f'{seg["start_sec"]:.2f}',
                f'{seg["end_sec"]:.2f}',
                f'{seg["duration"]:.2f}',
            ))

    def _on_region_select(self, event=None):
        sel = self.regions_tree.selection()
        if not sel:
            return
        idx = self.regions_tree.index(sel[0])
        if 0 <= idx < len(self.regions):
            seg = self.regions[idx]
            self.in_time.set(seg['start_sec'])
            self.out_time.set(seg['end_sec'])
            self._set_current_time(seg['start_sec'])
            self._redraw_timeline()

    def get_segments(self):
        return list(self.regions)

    def get_chunk_plan(self, output_folder='chunks', name_pattern='{basename}_{id}.mp4'):
        return {
            'version': 1,
            'output': {'folder': output_folder, 'name_pattern': name_pattern},
            'segments': [
                {'id': s['id'], 'start': s['start_sec'], 'duration': s['duration']}
                for s in self.regions
            ],
        }

    def play(self):
        if not self.cap or self.duration <= 0 or self._play_running:
            return
        self._play_running = True
        self._start_audio_at(self.current_time.get())
        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def pause(self):
        self._play_running = False
        self._stop_audio()

    def stop(self):
        self._play_running = False
        self._stop_audio()
        if self.duration > 0:
            self._set_current_time(0.0)

    def _play_loop(self):
        while self._play_running and self.cap:
            t = self.current_time.get()
            if t >= self.duration - 0.02:
                self.root.after(0, lambda: self._set_current_time(0.0, restart_audio=True))
                t = 0.0
            next_t = t + 1.0 / self.fps
            self.root.after(0, lambda nt=next_t: self._set_current_time(nt))
            time.sleep(1.0 / self.fps)

    def destroy(self):
        self._stop_audio()
        self.release_capture()
        super().destroy()
