"""Merge Split + Lip Sync tab for Video Tools Unified."""

import os
import threading
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from lib.video_utils import (
    build_merge_clip_list,
    concat_videos_with_external_audio,
    default_lipsync_folder,
    probe_fps,
    suggest_full_song_mp3,
)


class MergeSplitTab:
    TAB_NAME = 'Merge Split + Lip Sync'
    _settings_key = 'merge_split'

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.root = app.root
        self.clip_rows = []
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        paths_frame = ttk.LabelFrame(self.parent, text='Input folders and audio', padding=8)
        paths_frame.pack(fill='x', padx=10, pady=5)

        self.split_dir_var = tk.StringVar()
        self.lipsync_dir_var = tk.StringVar()
        self.audio_mp3_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self._add_path_row(
            paths_frame, 0, 'Split parts folder:', self.split_dir_var,
            self.browse_split_dir, self.on_split_dir_change,
        )
        self._add_path_row(
            paths_frame, 1, 'Lip-sync folder:', self.lipsync_dir_var,
            self.browse_lipsync_dir,
        )
        self._add_path_row(
            paths_frame, 2, 'Original song (MP3):', self.audio_mp3_var,
            self.browse_audio_mp3,
        )
        self._add_path_row(
            paths_frame, 3, 'Output MP4:', self.output_var,
            self.browse_output,
        )

        btn_row = ttk.Frame(self.parent)
        btn_row.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_row, text='Scan / Refresh', command=self.scan_clips).pack(side='left', padx=5)
        ttk.Button(btn_row, text='Export Combined Video', command=self.export_combined).pack(side='left', padx=5)
        self.lbl_summary = ttk.Label(btn_row, text='')
        self.lbl_summary.pack(side='left', padx=10)

        preview_frame = ttk.LabelFrame(self.parent, text='Clip preview (export order)', padding=6)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=5)

        cols = ('order', 'split_file', 'source', 'used_file')
        self.tree = ttk.Treeview(preview_frame, columns=cols, show='headings', height=14)
        self.tree.heading('order', text='#')
        self.tree.heading('split_file', text='Split file')
        self.tree.heading('source', text='Source')
        self.tree.heading('used_file', text='Used file')
        self.tree.column('order', width=40, anchor='center')
        self.tree.column('split_file', width=220)
        self.tree.column('source', width=70, anchor='center')
        self.tree.column('used_file', width=380)
        sy = ttk.Scrollbar(preview_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sy.pack(side='right', fill='y')

        ttk.Label(
            self.parent,
            text=(
                'Lip-sync match: {split_stem}__*.mp4 in lip-sync folder. '
                'Export uses original song MP3 as audio (like Combine Videos external audio).'
            ),
            wraplength=900,
        ).pack(anchor='w', padx=10, pady=(0, 8))

    def _add_path_row(self, parent, row, label, var, browse_cmd, trace_cmd=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=3)
        entry = ttk.Entry(parent, textvariable=var, width=70)
        entry.grid(row=row, column=1, sticky='ew', padx=5, pady=3)
        ttk.Button(parent, text='Browse...', command=browse_cmd).grid(row=row, column=2, pady=3)
        parent.columnconfigure(1, weight=1)
        if trace_cmd:
            var.trace_add('write', lambda *_: trace_cmd())

    def log(self, message):
        self.app.log(message, self.TAB_NAME)

    def browse_split_dir(self):
        path = filedialog.askdirectory(title='Select split parts folder')
        if path:
            self.split_dir_var.set(path)
            self.on_split_dir_change()
            self.save_settings()

    def browse_lipsync_dir(self):
        path = filedialog.askdirectory(title='Select lip-sync folder')
        if path:
            self.lipsync_dir_var.set(path)
            self.save_settings()

    def browse_audio_mp3(self):
        path = filedialog.askopenfilename(
            title='Select original song MP3',
            filetypes=[('MP3', '*.mp3'), ('Audio', '*.mp3 *.wav *.m4a'), ('All', '*.*')],
        )
        if path:
            self.audio_mp3_var.set(path)
            self.save_settings()

    def browse_output(self):
        initial = self.output_var.get().strip()
        initial_dir = os.path.dirname(initial) if initial and os.path.dirname(initial) else self.split_dir_var.get()
        path = filedialog.asksaveasfilename(
            title='Save combined video',
            defaultextension='.mp4',
            filetypes=[('MP4', '*.mp4'), ('All', '*.*')],
            initialdir=initial_dir or None,
            initialfile=os.path.basename(initial) if initial else 'combined.mp4',
        )
        if path:
            self.output_var.set(path)
            self.save_settings()

    def on_split_dir_change(self):
        split_dir = self.split_dir_var.get().strip()
        if not split_dir or not os.path.isdir(split_dir):
            return
        lipsync_default = default_lipsync_folder(split_dir)
        if os.path.isdir(lipsync_default) and not self.lipsync_dir_var.get().strip():
            self.lipsync_dir_var.set(lipsync_default)
        if not self.audio_mp3_var.get().strip():
            suggested = suggest_full_song_mp3(split_dir)
            if suggested:
                self.audio_mp3_var.set(suggested)
        if not self.output_var.get().strip():
            suggested = suggest_full_song_mp3(split_dir)
            if suggested:
                stem = os.path.splitext(os.path.basename(suggested))[0]
                self.output_var.set(os.path.join(split_dir, f'{stem}_combined.mp4'))
            else:
                self.output_var.set(os.path.join(split_dir, 'combined.mp4'))

    def scan_clips(self):
        split_dir = self.split_dir_var.get().strip()
        if not split_dir or not os.path.isdir(split_dir):
            messagebox.showwarning('Warning', 'Select a valid split parts folder.')
            return
        lipsync_dir = self.lipsync_dir_var.get().strip()
        if lipsync_dir and not os.path.isdir(lipsync_dir):
            messagebox.showwarning('Warning', 'Lip-sync folder path is not valid.')
            return
        self.clip_rows = build_merge_clip_list(split_dir, lipsync_dir or '')
        self._refresh_tree()
        lipsync_count = sum(1 for _b, _p, src in self.clip_rows if src == 'lipsync')
        split_count = len(self.clip_rows) - lipsync_count
        summary = f'{len(self.clip_rows)} clip(s): {lipsync_count} lip-sync, {split_count} split'
        self.lbl_summary.config(text=summary)
        self.log(f'[INFO] {summary}')
        if self.clip_rows and lipsync_count == 0 and lipsync_dir:
            self.log('[WARNING] No lip-sync matches found (check folder and naming)')
        if not self.clip_rows:
            messagebox.showwarning('Warning', 'No MP4 split parts found in the selected folder.')
        self.save_settings()

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, (split_name, used_path, source) in enumerate(self.clip_rows, start=1):
            self.tree.insert(
                '', 'end',
                values=(idx, split_name, source, os.path.basename(used_path)),
            )

    def export_combined(self):
        if self.app.is_busy:
            messagebox.showwarning('Warning', 'Another operation is in progress.')
            return
        if not self.clip_rows:
            self.scan_clips()
        if not self.clip_rows:
            return
        audio = self.audio_mp3_var.get().strip()
        if not audio or not os.path.isfile(audio):
            messagebox.showwarning('Warning', 'Select a valid original song MP3.')
            return
        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning('Warning', 'Select an output MP4 path.')
            return
        if not self.app.check_ffmpeg():
            self.app.offer_ffmpeg_install()
            return
        self.save_settings()
        self.app.set_busy(True, 'Merging split clips...')
        self.app.set_progress(indeterminate=True, message='Merging...')
        threading.Thread(target=self._export_thread, args=(output, audio), daemon=True).start()

    def _export_thread(self, output_path, audio_path):
        video_paths = [row[1] for row in self.clip_rows]
        ffmpeg = self.app.get_ffmpeg_command()
        target_fps = probe_fps(ffmpeg, video_paths[0]) or 24.0
        fps_label = int(target_fps) if abs(target_fps - round(target_fps)) < 0.01 else round(target_fps, 3)
        self.root.after(0, lambda: self.log(
            f'[INFO] Merging {len(video_paths)} clip(s) at {fps_label} fps (constant) '
            f'with {os.path.basename(audio_path)}',
        ))
        ok, err = concat_videos_with_external_audio(
            ffmpeg, video_paths, audio_path, output_path,
            timeout=7200, constant_fps=target_fps,
        )
        if ok:
            self.root.after(0, lambda: self.log(f'[SUCCESS] Saved: {output_path}'))
            self.root.after(0, lambda: messagebox.showinfo(
                'Done', f'Combined video saved:\n{output_path}',
            ))
        else:
            self.root.after(0, lambda: self.log(f'[ERROR] {err}'))
            self.root.after(0, lambda: messagebox.showerror('Error', f'Merge failed:\n{err}'))
        self.root.after(0, lambda: self.app.set_busy(False))

    def load_settings(self):
        data = self.app.get_tab_settings(self._settings_key)
        if not data:
            return
        if data.get('split_dir'):
            self.split_dir_var.set(data['split_dir'])
        if data.get('lipsync_dir'):
            self.lipsync_dir_var.set(data['lipsync_dir'])
        if data.get('audio_mp3'):
            self.audio_mp3_var.set(data['audio_mp3'])
        if data.get('last_output'):
            self.output_var.set(data['last_output'])
        if self.split_dir_var.get().strip():
            self.on_split_dir_change()
        if self.split_dir_var.get().strip():
            self.scan_clips()

    def save_settings(self):
        data = {
            'split_dir': self.split_dir_var.get().strip(),
            'lipsync_dir': self.lipsync_dir_var.get().strip(),
            'audio_mp3': self.audio_mp3_var.get().strip(),
            'last_output': self.output_var.get().strip(),
        }
        self.app.set_tab_settings(self._settings_key, data)

    def save_on_exit(self):
        self.save_settings()
