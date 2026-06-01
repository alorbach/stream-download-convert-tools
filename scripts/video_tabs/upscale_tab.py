"""Upscale Video tab for Video Tools Unified."""

import os
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from lib.video_utils import (
    UPSCALE_METHOD_AI,
    UPSCALE_METHOD_HIGH,
    UPSCALE_METHOD_MAXIMUM,
    UPSCALE_METHOD_STANDARD,
    align_even,
    parse_dropped_paths,
    probe_resolution,
    resolve_ffprobe_cmd,
    upscale_video_ffmpeg,
    upscale_video_realesrgan,
)

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}

RESOLUTION_PRESETS = {
    'Grok HD (1168 x 768)': (1168, 768),
    '720p (1280 x 720)': (1280, 720),
    '1080p (1920 x 1080)': (1920, 1080),
    'Custom': None,
}

METHOD_CHOICES = [
    (UPSCALE_METHOD_STANDARD, 'Standard (bicubic)'),
    (UPSCALE_METHOD_HIGH, 'High (Lanczos)'),
    (UPSCALE_METHOD_MAXIMUM, 'Maximum (2-step Lanczos + sharpen)'),
    (UPSCALE_METHOD_AI, 'AI (Real-ESRGAN)'),
]

AI_MODELS = [
    'realesr-animevideov3',
    'realesrgan-x4plus',
    'realesrgan-x4plus-anime',
    'realesrnet-x4plus',
]

PRESET_VALUES = [15, 16, 17, 18, 19, 20, 21, 22, 23]
X264_PRESETS = ['ultrafast', 'fast', 'medium', 'slow', 'veryslow']


def _strip_path(value: str) -> str:
    return (value or '').strip().strip('"')


def is_valid_output_dir(path: str) -> bool:
    """Reject empty or merged paths (e.g. ...streamD:\\...)."""
    path = _strip_path(path)
    if not path or path in ('.', '..'):
        return False
    if path.count(':') > 1:
        return False
    _drive, tail = os.path.splitdrive(path)
    if tail and ':' in tail:
        return False
    if path.startswith('\\\\'):
        return True
    if ':' in path and not (len(path) >= 2 and path[1] == ':'):
        return False
    return True


class UpscaleTab:
    TAB_NAME = 'Upscale Video'
    _settings_key = 'upscale'

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.root = app.root
        self.selected_files = []
        self._probe_after_id = None
        self.setup_ui()
        self.load_settings()
        self._apply_local_realesrgan_exe()

    def setup_ui(self):
        files_frame = ttk.LabelFrame(self.parent, text='Video Files', padding=6)
        files_frame.pack(fill='x', padx=10, pady=5)
        bf = ttk.Frame(files_frame)
        bf.pack(fill='x')
        ttk.Button(bf, text='Add Videos', command=self.add_files).pack(side='left', padx=5)
        ttk.Button(bf, text='Clear', command=self.clear_files).pack(side='left', padx=5)
        self.lbl_count = ttk.Label(bf, text='0 file(s)')
        self.lbl_count.pack(side='left', padx=10)
        self.lbl_source = ttk.Label(bf, text='')
        self.lbl_source.pack(side='left', padx=10)

        lf = ttk.Frame(files_frame)
        lf.pack(fill='x', pady=4)
        sy = ttk.Scrollbar(lf, orient='vertical')
        self.file_listbox = tk.Listbox(
            lf, yscrollcommand=sy.set, height=5, selectmode=tk.EXTENDED,
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

        target_frame = ttk.LabelFrame(self.parent, text='Target Resolution', padding=8)
        target_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(target_frame, text='Preset:').grid(row=0, column=0, sticky='w', pady=2)
        self.preset_var = tk.StringVar(value='Grok HD (1168 x 768)')
        preset_cb = ttk.Combobox(
            target_frame, textvariable=self.preset_var, width=28, state='readonly',
        )
        preset_cb['values'] = list(RESOLUTION_PRESETS.keys())
        preset_cb.grid(row=0, column=1, sticky='w', padx=5)
        preset_cb.bind('<<ComboboxSelected>>', self.on_preset_change)

        ttk.Label(target_frame, text='Width:').grid(row=1, column=0, sticky='w', pady=2)
        self.width_var = tk.IntVar(value=1168)
        self.width_spin = ttk.Spinbox(
            target_frame, from_=320, to=7680, increment=2,
            textvariable=self.width_var, width=8,
        )
        self.width_spin.grid(row=1, column=1, sticky='w', padx=5)
        self.width_var.trace_add('write', lambda *_: self._on_target_changed())

        ttk.Label(target_frame, text='Height:').grid(row=2, column=0, sticky='w', pady=2)
        self.height_var = tk.IntVar(value=768)
        self.height_spin = ttk.Spinbox(
            target_frame, from_=240, to=4320, increment=2,
            textvariable=self.height_var, width=8,
        )
        self.height_spin.grid(row=2, column=1, sticky='w', padx=5)
        self.height_var.trace_add('write', lambda *_: self._on_target_changed())

        self.lbl_scale = ttk.Label(target_frame, text='')
        self.lbl_scale.grid(row=3, column=0, columnspan=3, sticky='w', pady=4)

        method_frame = ttk.LabelFrame(self.parent, text='Upscale Method', padding=8)
        method_frame.pack(fill='x', padx=10, pady=5)

        self.method_var = tk.StringVar(value=UPSCALE_METHOD_HIGH)
        for val, label in METHOD_CHOICES:
            ttk.Radiobutton(
                method_frame, text=label, variable=self.method_var, value=val,
                command=self.on_method_change,
            ).pack(anchor='w')

        self.ai_frame = ttk.Frame(method_frame)
        self.ai_frame.pack(fill='x', pady=(6, 0))
        ttk.Label(self.ai_frame, text='Real-ESRGAN exe:').grid(row=0, column=0, sticky='w')
        self.ai_exe_var = tk.StringVar(value='')
        ttk.Entry(self.ai_frame, textvariable=self.ai_exe_var, width=48).grid(
            row=0, column=1, padx=5, sticky='ew',
        )
        ttk.Button(self.ai_frame, text='Browse', command=self.browse_ai_exe).grid(row=0, column=2)
        ttk.Button(
            self.ai_frame, text='Auto Install', command=self.install_realesrgan,
        ).grid(row=0, column=3, padx=(4, 0))
        ttk.Label(self.ai_frame, text='Model:').grid(row=1, column=0, sticky='w', pady=4)
        self.ai_model_var = tk.StringVar(value=AI_MODELS[0])
        model_cb = ttk.Combobox(
            self.ai_frame, textvariable=self.ai_model_var, width=28, state='readonly',
        )
        model_cb['values'] = AI_MODELS
        model_cb.grid(row=1, column=1, sticky='w', padx=5, pady=4)
        ttk.Label(
            self.ai_frame,
            text='Auto Install downloads the portable build into realesrgan/ (~45 MB).',
            wraplength=520,
        ).grid(row=2, column=0, columnspan=4, sticky='w')
        self.ai_frame.grid_columnconfigure(1, weight=1)

        enc_frame = ttk.LabelFrame(self.parent, text='Encode and Output', padding=8)
        enc_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(enc_frame, text='CRF:').grid(row=0, column=0, sticky='w')
        self.crf_var = tk.StringVar(value='18')
        ttk.Combobox(
            enc_frame, textvariable=self.crf_var, width=6, state='readonly',
            values=[str(v) for v in PRESET_VALUES],
        ).grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(enc_frame, text='x264 preset:').grid(row=0, column=2, sticky='w', padx=(12, 0))
        self.preset_enc_var = tk.StringVar(value='slow')
        ttk.Combobox(
            enc_frame, textvariable=self.preset_enc_var, width=10, state='readonly',
            values=X264_PRESETS,
        ).grid(row=0, column=3, sticky='w', padx=5)

        ttk.Label(enc_frame, text='Output folder:').grid(row=1, column=0, sticky='w', pady=4)
        default_out = self.app.file_manager.get_folder_path('converted')
        self.output_dir_var = tk.StringVar(value=default_out)
        ttk.Entry(enc_frame, textvariable=self.output_dir_var, width=42).grid(
            row=1, column=1, columnspan=2, sticky='ew', padx=5, pady=4,
        )
        ttk.Button(enc_frame, text='Browse', command=self.browse_output).grid(row=1, column=3)

        ttk.Label(enc_frame, text='Filename suffix:').grid(row=2, column=0, sticky='w')
        self.suffix_var = tk.StringVar(value='_upscaled')
        ttk.Entry(enc_frame, textvariable=self.suffix_var, width=20).grid(row=2, column=1, sticky='w', padx=5)

        self.same_dir_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            enc_frame, text='Write next to each source file (default; uncheck to use output folder)',
            variable=self.same_dir_var,
        ).grid(row=3, column=0, columnspan=4, sticky='w', pady=2)

        self.remove_temp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            enc_frame, text='Remove temp frames after AI upscale (success only)',
            variable=self.remove_temp_var,
        ).grid(row=4, column=0, columnspan=4, sticky='w')

        run_frame = ttk.Frame(self.parent)
        run_frame.pack(fill='x', padx=10, pady=8)
        ttk.Button(run_frame, text='Upscale Selected', command=self.start_upscale).pack(side='left', padx=5)
        ttk.Button(run_frame, text='Upscale All Listed', command=self.start_upscale_all).pack(side='left', padx=5)
        ttk.Label(run_frame, text='Files:').pack(anchor='w', pady=(8, 0))
        self.progress = ttk.Progressbar(run_frame, mode='determinate')
        self.progress.pack(fill='x', pady=2)
        ttk.Label(run_frame, text='Current file encode:').pack(anchor='w', pady=(4, 0))
        self.encode_progress = ttk.Progressbar(run_frame, mode='determinate', maximum=100)
        self.encode_progress.pack(fill='x', pady=2)
        self.progress_label = ttk.Label(run_frame, text='')
        self.progress_label.pack(anchor='w')

        self.on_method_change()

    def log(self, message):
        self.app.log(message, self.TAB_NAME)

    def on_method_change(self):
        is_ai = self.method_var.get() == UPSCALE_METHOD_AI
        for child in self.ai_frame.winfo_children():
            try:
                child.configure(state='normal' if is_ai else 'disabled')
            except tk.TclError:
                pass

    def on_preset_change(self, event=None):
        name = self.preset_var.get()
        dims = RESOLUTION_PRESETS.get(name)
        if dims:
            self.width_var.set(dims[0])
            self.height_var.set(dims[1])
        self._update_scale_label()

    def _on_target_changed(self):
        w, h = align_even(self.width_var.get(), self.height_var.get())
        if w != self.width_var.get():
            self.width_var.set(w)
        if h != self.height_var.get():
            self.height_var.set(h)
        self._update_scale_label()

    def _update_scale_label(self):
        tw, th = self.width_var.get(), self.height_var.get()
        sel = self._selected_path()
        if not sel or not self.app.check_ffmpeg():
            self.lbl_scale.config(text=f'Target: {tw} x {th}')
            return
        ffprobe = resolve_ffprobe_cmd(self.app.get_ffmpeg_command())
        src = probe_resolution(self.app.get_ffmpeg_command(), sel, ffprobe)
        if not src:
            self.lbl_scale.config(text=f'Target: {tw} x {th}')
            return
        sw, sh = src
        fx = tw / sw if sw else 0
        fy = th / sh if sh else 0
        self.lbl_scale.config(
            text=f'Source: {sw} x {sh} -> {tw} x {th}  (scale {fx:.2f}x / {fy:.2f}x)',
        )

    def _apply_local_realesrgan_exe(self) -> None:
        if _strip_path(self.ai_exe_var.get()) and os.path.isfile(self.ai_exe_var.get()):
            return
        local = self.app.get_realesrgan_exe()
        if local:
            self.ai_exe_var.set(local)

    def browse_ai_exe(self):
        path = filedialog.askopenfilename(
            title='Select realesrgan-ncnn-vulkan executable',
            filetypes=[('Executable', '*.exe'), ('All', '*.*')],
        )
        if path:
            self.ai_exe_var.set(path)
            self.save_settings()

    def install_realesrgan(self):
        local = self.app.get_realesrgan_exe()
        if local:
            self.ai_exe_var.set(local)
            messagebox.showinfo('Real-ESRGAN', f'Already installed:\n{local}')
            return
        self._prompt_realesrgan_download(pending_files=None)

    def _resolve_ai_exe_path(self) -> str:
        exe = _strip_path(self.ai_exe_var.get())
        if exe and os.path.isfile(exe):
            return exe
        if self.app.check_realesrgan():
            local = self.app.get_realesrgan_exe()
            if local:
                self.ai_exe_var.set(local)
                return local
        return ''

    def _ensure_ai_exe(self, files) -> bool:
        if self._resolve_ai_exe_path():
            return True
        self._prompt_realesrgan_download(pending_files=files)
        return False

    def _prompt_realesrgan_download(self, pending_files):
        if not messagebox.askyesno(
            'Real-ESRGAN Not Found',
            'AI upscale needs realesrgan-ncnn-vulkan.\n\n'
            'Download portable build automatically (~45 MB)?\n'
            'Installs into the realesrgan/ folder (no admin rights).',
        ):
            messagebox.showinfo(
                'Manual Installation',
                'Download from:\n'
                'https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0\n\n'
                'Then set Real-ESRGAN exe or click Auto Install.',
            )
            return
        self._start_realesrgan_download(pending_files)

    def _start_realesrgan_download(self, pending_files):
        self._pending_batch_files = pending_files
        self.log('[INFO] Downloading Real-ESRGAN...')
        self.app.set_busy(True, 'Installing Real-ESRGAN...')
        self.app.download_realesrgan(
            progress_callback=lambda m: self.root.after(0, lambda msg=m: self.log(f'[INFO] {msg}')),
            success_callback=lambda m: self.root.after(
                0, lambda msg=m: self._finish_realesrgan_install(True, msg),
            ),
            error_callback=lambda m: self.root.after(
                0, lambda msg=m: self._finish_realesrgan_install(False, msg),
            ),
        )

    def _finish_realesrgan_install(self, ok: bool, message: str):
        self.app.set_busy(False)
        if ok:
            exe = self.app.get_realesrgan_exe()
            if exe:
                self.ai_exe_var.set(exe)
                self.save_settings()
            self.log(f'[INFO] {message}')
            messagebox.showinfo('Real-ESRGAN', 'Install complete. You can run AI upscale now.')
            pending = getattr(self, '_pending_batch_files', None)
            self._pending_batch_files = None
            if pending:
                self._run_batch(pending)
        else:
            messagebox.showerror('Real-ESRGAN', message)

    def browse_output(self):
        folder = self.app.browse_folder(self.output_dir_var.get())
        if folder:
            self.output_dir_var.set(folder)
            self.save_settings()

    def add_files(self):
        files = self.app.select_files(
            title='Select Video Files',
            filetypes=self.app.file_manager.get_video_filetypes(),
        )
        if files:
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
            self._refresh_list()

    def clear_files(self):
        self.selected_files.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.selected_files:
            self.file_listbox.insert(tk.END, os.path.basename(f))
        self.lbl_count.config(text=f'{len(self.selected_files)} file(s)')
        self._update_scale_label()

    def on_drop(self, event):
        paths = parse_dropped_paths(event.data)
        added = 0
        for p in paths:
            if os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS and p not in self.selected_files:
                self.selected_files.append(p)
                added += 1
        if added:
            self._refresh_list()
            self.log(f'[INFO] Added {added} file(s) via drag and drop')

    def on_file_select(self, event=None):
        if self._probe_after_id:
            self.root.after_cancel(self._probe_after_id)
        self._probe_after_id = self.root.after(100, self._update_source_label)

    def _update_source_label(self):
        self._probe_after_id = None
        path = self._selected_path()
        if not path:
            self.lbl_source.config(text='')
            self._update_scale_label()
            return
        if not self.app.check_ffmpeg():
            self.lbl_source.config(text=os.path.basename(path))
            return
        ffprobe = resolve_ffprobe_cmd(self.app.get_ffmpeg_command())
        src = probe_resolution(self.app.get_ffmpeg_command(), path, ffprobe)
        if src:
            self.lbl_source.config(text=f'Selected: {src[0]} x {src[1]}')
        else:
            self.lbl_source.config(text=f'Selected: {os.path.basename(path)}')
        self._update_scale_label()

    def _selected_path(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return self.selected_files[0] if self.selected_files else None
        idx = sel[0]
        if idx < len(self.selected_files):
            return self.selected_files[idx]
        return None

    def _encode_opts(self):
        return {
            'crf': self.crf_var.get(),
            'preset': self.preset_enc_var.get(),
        }

    def _resolve_output_dir(self, input_path: str) -> str:
        """Output directory: same as source, valid custom folder, or source fallback."""
        source_dir = os.path.dirname(os.path.abspath(input_path))
        if self.same_dir_var.get():
            return source_dir
        out_dir = _strip_path(self.output_dir_var.get())
        if out_dir and is_valid_output_dir(out_dir):
            return os.path.normpath(out_dir)
        if out_dir and not getattr(self, '_warned_bad_output_dir', False):
            self._warned_bad_output_dir = True
            self.log(
                f'[WARNING] Invalid output folder "{out_dir}"; using source folder instead',
            )
        return source_dir

    def _output_path(self, input_path: str) -> str:
        stem = Path(input_path).stem
        suffix = self.suffix_var.get() or '_upscaled'
        out_name = f'{stem}{suffix}.mp4'
        out_dir = self._resolve_output_dir(input_path)
        os.makedirs(out_dir, exist_ok=True)
        return os.path.join(out_dir, out_name)

    def start_upscale_all(self):
        if not self.selected_files:
            messagebox.showwarning('Warning', 'Add at least one video file')
            return
        self._run_batch(list(self.selected_files))

    def start_upscale(self):
        sel = self.file_listbox.curselection()
        if sel:
            files = [self.selected_files[i] for i in sel if i < len(self.selected_files)]
        else:
            files = list(self.selected_files)
        if not files:
            messagebox.showwarning('Warning', 'Select or add video files')
            return
        self._run_batch(files)

    def _run_batch(self, files):
        if self.app.is_busy:
            messagebox.showwarning('Warning', 'Another operation is in progress')
            return
        if not self.app.check_ffmpeg():
            self.app.offer_ffmpeg_install()
            return
        method = self.method_var.get()
        if method == UPSCALE_METHOD_AI:
            if not self._ensure_ai_exe(files):
                return
        self.save_settings()
        self.progress['maximum'] = len(files)
        self.progress['value'] = 0
        self.encode_progress['value'] = 0
        self.progress_label.config(text='')
        self.app.set_busy(True, 'Upscaling...')
        threading.Thread(target=self._batch_thread, args=(files,), daemon=True).start()

    def _make_progress_callback(self, file_index: int, total_files: int):
        def on_progress(percent: float, message: str) -> None:
            def update() -> None:
                self.encode_progress['value'] = percent
                self.progress_label.config(
                    text=f'File {file_index + 1}/{total_files}: {message}',
                )
            self.root.after(0, update)
        return on_progress

    def _batch_thread(self, files):
        ffmpeg = self.app.get_ffmpeg_command()
        tw, th = align_even(self.width_var.get(), self.height_var.get())
        method = self.method_var.get()
        encode_opts = self._encode_opts()
        try:
            ok_count, fail_count = self._run_batch_files(
                files, ffmpeg, tw, th, method, encode_opts,
            )
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log(f'[ERROR] {err}'))
            self.root.after(
                0,
                lambda err=str(e): messagebox.showerror('Upscale failed', err),
            )
        finally:
            self.root.after(0, lambda: self.app.set_busy(False))

    def _run_batch_files(self, files, ffmpeg, tw, th, method, encode_opts):
        ok_count, fail_count = 0, 0
        for i, input_path in enumerate(files):
            name = os.path.basename(input_path)
            self.root.after(
                0,
                lambda n=i + 1, t=len(files), f=name: self.app.set_busy(
                    True, f'Upscaling {n}/{t}: {f}',
                ),
            )
            self.root.after(0, lambda f=name: self.log(f'[INFO] Processing: {f}'))
            self.root.after(0, lambda: self.encode_progress.configure(value=0))
            output_path = self._output_path(input_path)
            progress_cb = self._make_progress_callback(i, len(files))

            if method == UPSCALE_METHOD_AI:
                ok, err = upscale_video_realesrgan(
                    ffmpeg,
                    input_path,
                    output_path,
                    tw,
                    th,
                    ai_exe=self.ai_exe_var.get().strip(),
                    ai_model=self.ai_model_var.get(),
                    encode_opts=encode_opts,
                    remove_temp=self.remove_temp_var.get(),
                    log_callback=lambda m, self=self: self.root.after(0, lambda msg=m: self.log(msg)),
                    progress_callback=progress_cb,
                    timeout=7200,
                )
            else:
                ok, err = upscale_video_ffmpeg(
                    ffmpeg,
                    input_path,
                    output_path,
                    tw,
                    th,
                    method=method,
                    encode_opts=encode_opts,
                    timeout=3600,
                    progress_callback=progress_cb,
                )

            if ok:
                ok_count += 1
                self.root.after(
                    0,
                    lambda o=output_path: self.log(f'[SUCCESS] {os.path.basename(o)}'),
                )
            else:
                fail_count += 1
                self.root.after(0, lambda e=err: self.log(f'[ERROR] {e}'))

            self.root.after(0, lambda v=i + 1: self.progress.config(value=v))
            self.root.after(0, lambda: self.encode_progress.configure(value=0))

        self.root.after(
            0,
            lambda: self.log(f'[COMPLETE] {ok_count} succeeded, {fail_count} failed'),
        )
        self.root.after(
            0,
            lambda o=ok_count, f=fail_count: messagebox.showinfo(
                'Done', f'Successful: {o}\nFailed: {f}',
            ),
        )
        return ok_count, fail_count

    def load_settings(self):
        data = self.app.get_tab_settings(self._settings_key)
        if not data:
            return
        if 'target_w' in data:
            self.width_var.set(int(data['target_w']))
        if 'target_h' in data:
            self.height_var.set(int(data['target_h']))
        if 'preset' in data:
            self.preset_var.set(data['preset'])
        if 'method' in data:
            self.method_var.set(data['method'])
        if 'crf' in data:
            self.crf_var.set(str(data['crf']))
        if 'preset_enc' in data:
            self.preset_enc_var.set(data['preset_enc'])
        if 'output_dir' in data:
            saved_dir = _strip_path(data['output_dir'])
            if is_valid_output_dir(saved_dir):
                self.output_dir_var.set(saved_dir)
            else:
                default_out = self.app.file_manager.get_folder_path('converted')
                self.output_dir_var.set(default_out)
                self.log(
                    f'[WARNING] Ignored invalid saved output folder: {saved_dir}',
                )
        if 'suffix' in data:
            self.suffix_var.set(data['suffix'])
        if 'same_dir' in data:
            self.same_dir_var.set(bool(data['same_dir']))
        if 'ai_exe' in data:
            self.ai_exe_var.set(data['ai_exe'])
        if 'ai_model' in data:
            self.ai_model_var.set(data['ai_model'])
        if 'remove_temp' in data:
            self.remove_temp_var.set(bool(data['remove_temp']))
        self.on_method_change()
        self._update_scale_label()

    def save_settings(self):
        data = {
            'target_w': self.width_var.get(),
            'target_h': self.height_var.get(),
            'preset': self.preset_var.get(),
            'method': self.method_var.get(),
            'crf': self.crf_var.get(),
            'preset_enc': self.preset_enc_var.get(),
            'output_dir': self.output_dir_var.get(),
            'suffix': self.suffix_var.get(),
            'same_dir': self.same_dir_var.get(),
            'ai_exe': self.ai_exe_var.get(),
            'ai_model': self.ai_model_var.get(),
            'remove_temp': self.remove_temp_var.get(),
        }
        self.app.set_tab_settings(self._settings_key, data)

    def save_on_exit(self):
        self.save_settings()
