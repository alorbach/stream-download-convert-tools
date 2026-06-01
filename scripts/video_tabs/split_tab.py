"""Split and Chunks tab for Video Tools Unified."""

import json
import os
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from lib.video_utils import (
    CHUNK_PLAN_SAMPLE,
    apply_chunk_plan,
    companion_mp3_path,
    export_visual_segments,
    extract_segment,
    extract_segment_mp3,
    extract_mp3_from_file,
    parse_chunk_plan_json,
    parse_dropped_paths,
    probe_duration,
    segment_bounds,
    segments_to_plan,
    source_output_dir,
    split_fixed_interval,
)
from .visual_trim_panel import VisualTrimPanel

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}


class SplitChunksTab:
    TAB_NAME = 'Split and Chunks'

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.root = app.root
        self.selected_files = []
        self.mode_var = tk.StringVar(value='interval')
        self._visual_available = VisualTrimPanel.is_available()
        self.setup_ui()

    def setup_ui(self):
        files_frame = ttk.LabelFrame(self.parent, text='Video Files', padding=6)
        files_frame.pack(fill='x', padx=10, pady=5)
        bf = ttk.Frame(files_frame)
        bf.pack(fill='x')
        ttk.Button(bf, text='Add Videos', command=self.add_files).pack(side='left', padx=5)
        ttk.Button(bf, text='Clear', command=self.clear_files).pack(side='left', padx=5)
        self.lbl_count = ttk.Label(bf, text='0 file(s)')
        self.lbl_count.pack(side='left', padx=10)
        lf = ttk.Frame(files_frame)
        lf.pack(fill='x')
        sy = ttk.Scrollbar(lf, orient='vertical')
        self.file_listbox = tk.Listbox(
            lf, yscrollcommand=sy.set, height=4, selectmode=tk.EXTENDED,
        )
        sy.config(command=self.file_listbox.yview)
        self.file_listbox.pack(side='left', fill='x', expand=True)
        sy.pack(side='right', fill='y')
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        if DND_FILES:
            try:
                self.file_listbox.drop_target_register(DND_FILES)
                self.file_listbox.dnd_bind('<<Drop>>', self.on_drop)
            except Exception:
                pass

        mode_frame = ttk.LabelFrame(self.parent, text='Split Mode', padding=8)
        mode_frame.pack(fill='x', padx=10, pady=5)
        modes = [
            ('interval', 'Fixed interval (e.g. 6 sec chunks)'),
            ('single', 'Single segment (first / last / middle / custom)'),
            ('json', 'JSON chunk plan'),
            ('visual', 'Visual trim (preview + timeline)'),
        ]
        for val, label in modes:
            rb = ttk.Radiobutton(
                mode_frame, text=label, variable=self.mode_var, value=val,
                command=self.on_mode_change,
            )
            rb.pack(anchor='w')
            if val == 'visual' and not self._visual_available:
                rb.config(state='disabled')

        self.opts_frame = ttk.Frame(self.parent)
        self.opts_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self._build_interval_opts()
        self._build_single_opts()
        self._build_json_opts()

        self.visual_frame = ttk.LabelFrame(self.opts_frame, text='Visual Trim Editor', padding=4)
        self.visual_panel = VisualTrimPanel(
            self.visual_frame, self.root, log_callback=self.log,
        )
        self.visual_panel.pack(fill='both', expand=True)

        out_frame = ttk.LabelFrame(self.parent, text='Output', padding=10)
        out_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(
            out_frame,
            text=(
                'All modes: for each chunk, MP4 and MP3 are saved in the same folder as the '
                'source video (e.g. mysong_part_001.mp4 and mysong_part_001.mp3).'
            ),
            wraplength=700,
        ).pack(anchor='w')

        self.on_mode_change()

        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text='Run Split', command=self.run_split).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Sync cuts to JSON', command=self.sync_to_json).pack(side='left', padx=5)
        ttk.Button(btn_frame, text='Chunk Plan Help', command=self.show_help).pack(side='left', padx=5)
        self.progress = ttk.Progressbar(btn_frame, mode='determinate')
        self.progress.pack(fill='x', pady=5, padx=0)

    def _build_interval_opts(self):
        self.interval_frame = ttk.LabelFrame(self.opts_frame, text='Fixed Interval', padding=8)
        ttk.Label(self.interval_frame, text='Chunk length (seconds):').grid(row=0, column=0, sticky='w')
        self.chunk_sec_var = tk.StringVar(value=self.app.get_setting('split_chunk_sec', '6'))
        ttk.Entry(self.interval_frame, textvariable=self.chunk_sec_var, width=10).grid(row=0, column=1, sticky='w')
        ttk.Label(self.interval_frame, text='Max chunks (0 = all):').grid(row=1, column=0, sticky='w', pady=4)
        self.max_chunks_var = tk.StringVar(value=self.app.get_setting('split_max_chunks', '0'))
        ttk.Entry(self.interval_frame, textvariable=self.max_chunks_var, width=10).grid(row=1, column=1, sticky='w')
        ttk.Label(self.interval_frame, text='Name pattern:').grid(row=2, column=0, sticky='w', pady=4)
        self.interval_pattern_var = tk.StringVar(
            value=self.app.get_setting('split_interval_pattern', '{basename}_part_{index:03d}.mp4'))
        ttk.Entry(self.interval_frame, textvariable=self.interval_pattern_var, width=45).grid(
            row=2, column=1, columnspan=2, sticky='w')

    def _build_single_opts(self):
        self.single_frame = ttk.LabelFrame(self.opts_frame, text='Single Segment', padding=8)
        self.single_preset_var = tk.StringVar(value='first')
        presets = ttk.Frame(self.single_frame)
        presets.pack(fill='x')
        for val, label in (
            ('first', 'First N seconds'),
            ('last', 'Last N seconds'),
            ('middle', 'Middle N seconds'),
            ('custom', 'Custom start + duration'),
        ):
            ttk.Radiobutton(presets, text=label, variable=self.single_preset_var, value=val).pack(
                side='left', padx=4)
        row = ttk.Frame(self.single_frame)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text='Duration (sec):').pack(side='left')
        self.single_duration_var = tk.StringVar(value='30')
        ttk.Entry(row, textvariable=self.single_duration_var, width=8).pack(side='left', padx=5)
        ttk.Label(row, text='Start (sec or middle):').pack(side='left', padx=(15, 0))
        self.single_start_var = tk.StringVar(value='0')
        ttk.Entry(row, textvariable=self.single_start_var, width=12).pack(side='left', padx=5)
        ttk.Label(self.single_frame, text='Output suffix:').pack(anchor='w')
        self.single_suffix_var = tk.StringVar(value='_clip')
        ttk.Entry(self.single_frame, textvariable=self.single_suffix_var, width=20).pack(anchor='w')

    def _build_json_opts(self):
        self.json_frame = ttk.LabelFrame(self.opts_frame, text='JSON Plan', padding=8)
        jf = ttk.Frame(self.json_frame)
        jf.pack(fill='x')
        ttk.Button(jf, text='Load JSON File', command=self.load_json_file).pack(side='left', padx=5)
        ttk.Button(jf, text='Reset Sample', command=self.reset_json_sample).pack(side='left', padx=5)
        self.json_text = scrolledtext.ScrolledText(self.json_frame, height=8, width=70)
        self.json_text.pack(fill='both', expand=True, pady=5)
        self.reset_json_sample()

    def on_mode_change(self):
        for f in (self.interval_frame, self.single_frame, self.json_frame, self.visual_frame):
            f.pack_forget()
        m = self.mode_var.get()
        if m == 'interval':
            self.interval_frame.pack(fill='x')
        elif m == 'single':
            self.single_frame.pack(fill='x')
        elif m == 'json':
            self.json_frame.pack(fill='both', expand=True)
        elif m == 'visual' and self._visual_available:
            self.visual_frame.pack(fill='both', expand=True)
            self._load_selected_video_into_visual()

    def on_file_select(self, event=None):
        if self.mode_var.get() == 'visual':
            self._load_selected_video_into_visual()

    def _get_selected_video_path(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if 0 <= idx < len(self.selected_files):
            return self.selected_files[idx]
        return None

    def _load_selected_video_into_visual(self):
        path = self._get_selected_video_path()
        if not path or not self._visual_available:
            return
        ffmpeg = self.app.get_ffmpeg_command()
        self.visual_panel.load_video(path, ffmpeg)

    def sync_to_json(self):
        if not self._visual_available:
            messagebox.showinfo('Info', 'Visual trim is not available (install opencv-python).')
            return
        segments = self.visual_panel.get_segments()
        if not segments:
            messagebox.showwarning('Warning', 'No cut regions to sync')
            return
        plan = segments_to_plan(segments, output_folder='.', name_pattern='{basename}_{id}.mp4')
        self.json_text.delete('1.0', tk.END)
        self.json_text.insert('1.0', json.dumps(plan, indent=2))
        self.mode_var.set('json')
        self.on_mode_change()
        self.log('[INFO] Synced cut regions to JSON plan')

    def reset_json_sample(self):
        self.json_text.delete('1.0', tk.END)
        self.json_text.insert('1.0', CHUNK_PLAN_SAMPLE)

    def show_help(self):
        guide = os.path.join(self.app.root_dir, 'docs', 'VIDEO_TOOLS_GUIDE.md')
        msg = (
            'Modes: fixed interval, single segment, JSON plan, or visual trim.\n\n'
            'Every chunk exports MP4 + MP3 next to the source video file '
            '(same basename, e.g. mysong_part_001.mp4 and mysong_part_001.mp3).\n\n'
            'Visual trim: select a video, drag In/Out handles, Add cut, Run Split.\n'
            'Shortcuts: I = In, O = Out, Space = Play/Pause.\n\n'
            'See docs/VIDEO_TOOLS_GUIDE.md for chunk JSON format.'
        )
        if os.path.isfile(guide):
            msg += f'\n\nGuide: {guide}'
        messagebox.showinfo('Split and Chunks Help', msg)

    def load_json_file(self):
        path = filedialog.askopenfilename(
            title='Load chunk plan JSON',
            filetypes=[('JSON', '*.json'), ('All', '*.*')],
        )
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                self.json_text.delete('1.0', tk.END)
                self.json_text.insert('1.0', f.read())

    def log(self, message):
        self.app.log(message, self.TAB_NAME)

    def add_files(self):
        files = self.app.select_files(
            title='Select videos',
            filetypes=[('Video', '*.mp4 *.webm *.avi *.mov *.mkv'), ('All', '*.*')],
        )
        if files:
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
            self.refresh_list()
            if len(self.selected_files) == len(files):
                self.file_listbox.selection_set(0)
                self.on_file_select()

    def clear_files(self):
        self.selected_files.clear()
        self.refresh_list()
        if self._visual_available:
            self.visual_panel.release_capture()

    def refresh_list(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.selected_files:
            self.file_listbox.insert(tk.END, os.path.basename(f))
        self.lbl_count.config(text=f'{len(self.selected_files)} file(s)')

    def on_drop(self, event):
        for p in parse_dropped_paths(event.data):
            if os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS and p not in self.selected_files:
                self.selected_files.append(p)
        self.refresh_list()

    def run_split(self):
        if self.app.is_busy:
            messagebox.showwarning('Warning', 'Operation in progress')
            return
        mode = self.mode_var.get()
        if mode == 'visual':
            path = self._get_selected_video_path()
            if not path:
                messagebox.showwarning('Warning', 'Select one video in the list for visual trim export')
                return
            if not self.visual_panel.get_segments():
                messagebox.showwarning('Warning', 'Add at least one cut region in the visual editor')
                return
            videos = [path]
        else:
            if not self.selected_files:
                messagebox.showwarning('Warning', 'Add at least one video file')
                return
            videos = self.selected_files
        if not self.app.check_ffmpeg():
            self.app.offer_ffmpeg_install()
            return
        self.app.set_busy(True, 'Splitting...')
        self.progress['maximum'] = len(videos)
        self.progress['value'] = 0
        threading.Thread(target=self._split_thread, args=(videos, mode), daemon=True).start()

    def _split_thread(self, videos, mode):
        ffmpeg = self.app.get_ffmpeg_command()
        total_out = 0
        for idx, video in enumerate(videos):
            self.root.after(0, lambda i=idx, v=video: self.log(f'\n[INFO] Processing: {os.path.basename(v)}'))
            try:
                if mode == 'interval':
                    total_out += self._do_interval(ffmpeg, video)
                elif mode == 'single':
                    total_out += self._do_single(ffmpeg, video)
                elif mode == 'visual':
                    total_out += self._do_visual(ffmpeg, video)
                else:
                    total_out += self._do_json(ffmpeg, video)
            except Exception as e:
                self.root.after(0, lambda m=str(e): self.log(f'[ERROR] {m}'))
            self.root.after(0, lambda v=idx + 1: self.progress.config(value=v))
        self.root.after(0, lambda: self.log(f'\n[COMPLETE] Created {total_out} output file(s)'))
        self.root.after(0, lambda: messagebox.showinfo('Done', f'Created {total_out} output file(s)'))
        self.root.after(0, lambda: self.app.set_busy(False))

    def _do_visual(self, ffmpeg, video):
        segments = self.visual_panel.get_segments()
        outs, errs = export_visual_segments(ffmpeg, video, segments)
        for e in errs:
            self.root.after(0, lambda m=e: self.log(f'[WARN] {m}'))
        for o in outs:
            self.root.after(0, lambda p=o: self.log(f'[SUCCESS] {p}'))
        return len(outs)

    def _do_interval(self, ffmpeg, video):
        chunk = float(self.chunk_sec_var.get())
        max_c = int(self.max_chunks_var.get() or 0)
        max_chunks = max_c if max_c > 0 else None
        outs, errs = split_fixed_interval(
            ffmpeg, video, source_output_dir(video), chunk,
            name_pattern=self.interval_pattern_var.get(),
            max_chunks=max_chunks,
        )
        for e in errs:
            self.root.after(0, lambda m=e: self.log(f'[WARN] {m}'))
        for o in outs:
            self.root.after(0, lambda p=o: self.log(f'[SUCCESS] {p}'))
        return len(outs)

    def _do_single(self, ffmpeg, video):
        duration = probe_duration(ffmpeg, video)
        if not duration:
            raise ValueError('Could not read video duration')
        dur = float(self.single_duration_var.get())
        preset = self.single_preset_var.get()
        if preset == 'first':
            start, end = segment_bounds(duration, 0, duration_sec=dur)
        elif preset == 'last':
            start, end = segment_bounds(duration, -dur, duration_sec=dur)
        elif preset == 'middle':
            start, end = segment_bounds(duration, 'middle', duration_sec=dur)
        else:
            start_spec = self.single_start_var.get().strip()
            try:
                start_spec = float(start_spec)
            except ValueError:
                pass
            start, end = segment_bounds(duration, start_spec, duration_sec=dur)
        seg_dur = end - start
        out_dir = source_output_dir(video)
        os.makedirs(out_dir, exist_ok=True)
        suffix = self.single_suffix_var.get() or '_clip'
        out = os.path.join(out_dir, f'{Path(video).stem}{suffix}.mp4')
        ok, err = extract_segment(ffmpeg, video, out, start, seg_dur)
        if not ok:
            raise ValueError(err)
        count = 1
        mp3_out = companion_mp3_path(out)
        ok_mp3, err_mp3 = extract_segment_mp3(ffmpeg, video, mp3_out, start, seg_dur)
        if not ok_mp3:
            ok_mp3, err_mp3 = extract_mp3_from_file(ffmpeg, out, mp3_out)
        if ok_mp3:
            count += 1
            self.root.after(0, lambda p=mp3_out: self.log(f'[SUCCESS] {p}'))
        elif err_mp3:
            self.root.after(0, lambda m=err_mp3: self.log(f'[WARN] mp3: {m}'))
        self.root.after(0, lambda p=out: self.log(f'[SUCCESS] {p}'))
        return count

    def _do_json(self, ffmpeg, video):
        plan = parse_chunk_plan_json(self.json_text.get('1.0', tk.END))
        plan.setdefault('output', {})['folder'] = '.'
        outs, errs = apply_chunk_plan(ffmpeg, video, plan, source_output_dir(video))
        for w in errs:
            self.root.after(0, lambda m=w: self.log(f'[WARN] {m}'))
        for o in outs:
            self.root.after(0, lambda p=o: self.log(f'[SUCCESS] {p}'))
        return len(outs)
