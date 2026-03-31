"""
Spectrum Analyzer - Real-time scrolling spectrogram (20 Hz - 20 kHz)

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

import os
import re
import sys
import threading
import subprocess
from itertools import islice
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.figure import Figure
import numpy as np
import sounddevice as sd

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from lib.base_gui import BaseAudioGUI


TARGET_SR = 48000
BLOCK_SIZE = 2048
N_FFT = 2048
N_FREQ_ROWS = 256
N_TIME_COLS = 480
MAX_HISTORY_COLS = 120000
F_MIN = 10.0
F_MAX = 20000.0
MAX_DECODE_BYTES = 520_000_000

# Per-frame relative dB (peak bin = 0 dB) so raw FFT dB does not clip the colormap.
SPEC_DB_VMIN = -78.0
SPEC_DB_VMAX = 0.0
SPEC_SILENCE_SPREAD_DB = 2.0

CHART_TEXT = "#f5f5f5"
CHART_SPINE = "#6a6a78"

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".opus", ".aac", ".wma"}


def _academo_cmap():
    colors = [
        (0.0, "#020208"),
        (0.08, "#060618"),
        (0.18, "#101030"),
        (0.30, "#1c1c52"),
        (0.42, "#3a2870"),
        (0.52, "#5c2888"),
        (0.62, "#8840a0"),
        (0.72, "#b05020"),
        (0.82, "#d07010"),
        (0.90, "#e8a028"),
        (0.96, "#f0c868"),
        (1.0, "#fff4e0"),
    ]
    return LinearSegmentedColormap.from_list("academo_like", colors, N=512)


def parse_dnd_file_list(data):
    paths = []
    s = (data or "").strip()
    while s:
        if s.startswith("{"):
            end = s.find("}")
            if end == -1:
                break
            paths.append(s[1:end])
            s = s[end + 1 :].strip()
        else:
            m = re.match(r"(\S+)", s)
            if not m:
                break
            paths.append(m.group(1))
            s = s[m.end() :].strip()
    return paths


def display_frequencies(n_rows, log_scale):
    if log_scale:
        return np.geomspace(F_MIN, F_MAX, n_rows)
    return np.linspace(F_MIN, F_MAX, n_rows)


class SpectrumAnalyzerGUI(BaseAudioGUI):
    def __init__(self, root):
        self._pcm = np.zeros(0, dtype=np.float32)
        self._play_pos = 0
        self._play_lock = threading.Lock()
        self._viz_lock = threading.Lock()
        self._viz_block = None
        self._stream = None
        self._playing = False
        self._poll_after_id = None
        self._log_scale_var = tk.BooleanVar(value=True)
        self._current_path = None
        self._hann = np.hanning(N_FFT).astype(np.float32)
        self._fft_freqs = np.fft.rfftfreq(N_FFT, 1.0 / TARGET_SR)
        self._spec = np.full((N_FREQ_ROWS, N_TIME_COLS), SPEC_DB_VMIN, dtype=np.float32)
        self._cmap = _academo_cmap()
        self._hist_columns = []
        self._follow_live = True
        self._hist_pos = tk.IntVar(value=100)
        self._suppress_scroll = False

        super().__init__(root, "Spectrum Analyzer")
        try:
            if not root.winfo_exists():
                return
        except tk.TclError:
            return
        self.root.geometry("1000x720")
        self._rebuild_freq_grid()
        self._setup_ui()
        self.log_manager.set_log_widget(self._log_text)
        self._check_audio()

    def setup_common_ui(self):
        pass

    def _check_audio(self):
        try:
            sd.check_output_settings(samplerate=TARGET_SR, channels=1, dtype="float32")
        except Exception as e:
            self.log(f"[WARNING] Audio output check: {e}")

    def _rebuild_freq_grid(self):
        self._disp_freqs = display_frequencies(N_FREQ_ROWS, self._log_scale_var.get())

    def _setup_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Open file", command=self._open_file).pack(side=tk.LEFT, padx=4)
        self._play_btn = ttk.Button(top, text="Play", command=self._play, state=tk.DISABLED)
        self._play_btn.pack(side=tk.LEFT, padx=4)
        self._pause_btn = ttk.Button(top, text="Pause", command=self._pause, state=tk.DISABLED)
        self._pause_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Stop", command=self._stop).pack(side=tk.LEFT, padx=4)

        ttk.Checkbutton(
            top,
            text="Log frequency scale",
            variable=self._log_scale_var,
            command=self._on_log_toggle,
        ).pack(side=tk.LEFT, padx=12)

        self._file_label = ttk.Label(top, text="No file loaded")
        self._file_label.pack(side=tk.LEFT, padx=8)

        spec_frame = ttk.LabelFrame(self.root, text="Spectrogram (10 Hz - 20 kHz)", padding=4)
        spec_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._fig = Figure(figsize=(10, 4.5), dpi=100, facecolor="#1a1a22")
        self._ax = self._fig.add_subplot(111, facecolor="#0d0d12")
        self._spec_norm = Normalize(vmin=SPEC_DB_VMIN, vmax=SPEC_DB_VMAX, clip=True)
        self._img = self._ax.imshow(
            self._spec,
            aspect="auto",
            origin="lower",
            cmap=self._cmap,
            norm=self._spec_norm,
            interpolation="nearest",
        )
        self._fig.tight_layout()
        self._canvas = FigureCanvasTkAgg(self._fig, master=spec_frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._update_y_ticks()

        hist_row = ttk.Frame(spec_frame)
        hist_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(hist_row, text="Older").pack(side=tk.LEFT, padx=(0, 4))
        self._hist_scale = tk.Scale(
            hist_row,
            from_=10,
            to=100,
            resolution=10,
            orient=tk.HORIZONTAL,
            variable=self._hist_pos,
            command=self._on_hist_scroll,
            showvalue=True,
            tickinterval=10,
        )
        self._hist_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(hist_row, text="Live").pack(side=tk.LEFT, padx=(4, 0))

        drop_zone = ttk.LabelFrame(self.root, text="Drop audio file here", padding=6)
        drop_zone.pack(fill=tk.X, padx=8, pady=4)

        log_frame = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        log_frame.pack(fill=tk.BOTH)
        ttk.Label(log_frame, text="Log:").pack(anchor=tk.W)
        self._log_text = scrolledtext.ScrolledText(log_frame, height=5, wrap=tk.WORD)
        self._log_text.pack(fill=tk.BOTH, expand=True)

        if DND_AVAILABLE:
            for w in (self.root, spec_frame, drop_zone, self._canvas.get_tk_widget()):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_drop)
                except tk.TclError:
                    pass

    def _apply_chart_style(self):
        ax = self._ax
        ax.set_xlabel("Time ->", color=CHART_TEXT, fontsize=11)
        ax.set_ylabel("Frequency (Hz)", color=CHART_TEXT, fontsize=11)
        ax.tick_params(
            axis="both",
            colors=CHART_TEXT,
            labelsize=10,
            width=1,
            length=5,
            labelcolor=CHART_TEXT,
        )
        for spine in ax.spines.values():
            spine.set_color(CHART_SPINE)
            spine.set_linewidth(1.0)
        for label in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
            label.set_color(CHART_TEXT)

    def _update_y_ticks(self):
        targets = list(range(10, 101, 10)) + [200, 500, 1000, 2000, 5000, 10000, 20000]
        targets = sorted(set(targets))
        rows = []
        labels = []
        used_idx = set()
        freqs = self._disp_freqs
        for t in targets:
            if not (F_MIN <= t <= F_MAX):
                continue
            idx = int(np.argmin(np.abs(freqs - t)))
            if idx in used_idx:
                continue
            used_idx.add(idx)
            rows.append(idx)
            if t >= 1000:
                labels.append(f"{t/1000:g}k")
            else:
                labels.append(str(int(t)))
        self._ax.set_yticks(rows)
        self._ax.set_yticklabels(labels)
        self._apply_chart_style()
        self._canvas.draw_idle()

    def _on_log_toggle(self):
        self._rebuild_freq_grid()
        self._update_y_ticks()
        self._refresh_hist_view()

    def _clear_hist_buffer(self):
        self._hist_columns.clear()
        self._follow_live = True
        self._suppress_scroll = True
        self._hist_pos.set(100)
        self._suppress_scroll = False

    def _hist_pos_clamped(self):
        v = int(round(float(self._hist_pos.get())))
        v = int(round(v / 10) * 10)
        return max(10, min(100, v))

    def _on_hist_scroll(self, v):
        if self._suppress_scroll:
            return
        try:
            x = int(round(float(v)))
        except (TypeError, ValueError):
            return
        x = int(round(x / 10) * 10)
        x = max(10, min(100, x))
        self._follow_live = x >= 100
        self._refresh_hist_view()

    def _refresh_hist_view(self):
        n = len(self._hist_columns)
        if n == 0:
            self._spec.fill(SPEC_DB_VMIN)
        else:
            max_start = max(0, n - N_TIME_COLS)
            if self._follow_live:
                start = max_start
            else:
                s = self._hist_pos_clamped()
                frac = (s - 10) / 90.0
                frac = max(0.0, min(1.0, frac))
                start = int(round((1.0 - frac) * max_start)) if max_start > 0 else 0
            cols = list(islice(self._hist_columns, start, start + N_TIME_COLS))
            w = len(cols)
            if w == 0:
                self._spec.fill(SPEC_DB_VMIN)
            else:
                self._spec[:, :w] = np.column_stack(cols)
                if w < N_TIME_COLS:
                    self._spec[:, w:].fill(SPEC_DB_VMIN)
        self._img.set_data(self._spec)
        self._canvas.draw_idle()

    def _spectrum_column(self, samples):
        n = len(samples)
        if n < N_FFT:
            x = np.zeros(N_FFT, dtype=np.float32)
            x[:n] = samples
        else:
            x = samples[-N_FFT:].astype(np.float32, copy=False)
        xw = x * self._hann
        spec = np.fft.rfft(xw)
        mag = np.abs(spec) + 1e-12
        db = 20.0 * np.log10(mag)
        freqs = self._fft_freqs
        mask = (freqs >= F_MIN) & (freqs <= F_MAX)
        fx = freqs[mask]
        fy = db[mask]
        if fx.size < 2:
            return np.full(N_FREQ_ROWS, SPEC_DB_VMIN, dtype=np.float32)
        out = np.interp(self._disp_freqs, fx, fy, left=fy[0], right=fy[-1])
        return out.astype(np.float32)

    def _column_relative_db(self, col):
        cmax = float(np.max(col))
        cmin = float(np.min(col))
        if cmax - cmin < SPEC_SILENCE_SPREAD_DB:
            return np.full(N_FREQ_ROWS, SPEC_DB_VMIN, dtype=np.float32)
        out = col.astype(np.float64, copy=False) - cmax
        np.clip(out, SPEC_DB_VMIN, SPEC_DB_VMAX, out=out)
        return out.astype(np.float32)

    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            pass
        with self._play_lock:
            pcm = self._pcm
            pos = self._play_pos
            n_pcm = len(pcm)
            if n_pcm == 0 or pos >= n_pcm:
                outdata.fill(0)
                if self._playing and n_pcm > 0 and pos >= n_pcm:
                    self.root.after(0, self._on_playback_finished)
                return
            end = min(pos + frames, n_pcm)
            chunk = pcm[pos:end]
            got = len(chunk)
            if got < frames:
                outdata[:got, 0] = chunk
                outdata[got:, 0] = 0
            else:
                outdata[:, 0] = chunk[:frames]
            take = chunk[:frames] if got >= frames else np.pad(chunk, (0, frames - got))
            self._play_pos = pos + frames
            finished = self._play_pos >= n_pcm
        block = np.ascontiguousarray(take, dtype=np.float32)
        with self._viz_lock:
            self._viz_block = block
        if finished:
            self.root.after(0, self._on_playback_finished)

    def _on_playback_finished(self):
        if not self._playing:
            return
        self._pause()
        self.log("[INFO] Playback finished")

    def _poll_visual(self):
        self._poll_after_id = None
        if not self._playing:
            return
        block = None
        with self._viz_lock:
            if self._viz_block is not None:
                block = self._viz_block
                self._viz_block = None
        if block is not None:
            col = self._column_relative_db(self._spectrum_column(block))
            self._hist_columns.append(col)
            if len(self._hist_columns) > MAX_HISTORY_COLS:
                del self._hist_columns[: len(self._hist_columns) - MAX_HISTORY_COLS]
            if self._follow_live:
                self._suppress_scroll = True
                self._hist_pos.set(100)
                self._suppress_scroll = False
            self._refresh_hist_view()
        self._poll_after_id = self.root.after(25, self._poll_visual)

    def _stop_poll(self):
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None

    def _decode_file(self, path):
        if not self.check_ffmpeg():
            if not self.offer_ffmpeg_install():
                return None
        ff = self.get_ffmpeg_command()
        cmd = [
            ff,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            path,
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(TARGET_SR),
            "-",
        ]
        run_kw = {"capture_output": True, "timeout": 3600}
        if sys.platform == "win32":
            run_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(cmd, **run_kw)
        except subprocess.TimeoutExpired:
            self.log("[ERROR] FFmpeg decode timed out")
            return None
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[:500]
            self.log(f"[ERROR] FFmpeg: {err}")
            return None
        raw = proc.stdout
        if len(raw) > MAX_DECODE_BYTES:
            self.log("[ERROR] File too large after decode (limit ~520 MB float32)")
            return None
        pcm = np.frombuffer(raw, dtype=np.float32).copy()
        if pcm.size == 0:
            self.log("[ERROR] No audio decoded")
            return None
        return pcm

    def _load_path(self, path):
        path = os.path.normpath(path)
        if not os.path.isfile(path):
            self.log(f"[ERROR] Not a file: {path}")
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in AUDIO_EXTENSIONS:
            self.log(f"[WARNING] Unsupported extension {ext}, trying anyway")
        self._stop()
        self._clear_hist_buffer()
        self.log(f"[INFO] Decoding: {os.path.basename(path)}")
        self.root.update_idletasks()
        pcm = self._decode_file(path)
        if pcm is None:
            return
        self._pcm = pcm
        self._current_path = path
        self._file_label.config(text=os.path.basename(path))
        dur = len(pcm) / TARGET_SR
        self.log(f"[INFO] Loaded {dur:.1f}s mono @ {TARGET_SR} Hz")
        self._refresh_hist_view()
        self._play_btn.config(state=tk.NORMAL)

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open audio file",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.flac *.m4a *.ogg *.opus *.aac *.wma"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._load_path(path)

    def _on_drop(self, event):
        try:
            paths = parse_dnd_file_list(event.data)
            for p in paths:
                p = p.strip()
                if not p:
                    continue
                if os.path.isfile(p):
                    ext = os.path.splitext(p)[1].lower()
                    if ext in AUDIO_EXTENSIONS:
                        self._load_path(p)
                        return
            self.log("[WARNING] No supported audio file in drop")
        except Exception as e:
            self.log(f"[ERROR] Drop failed: {e}")

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _play(self):
        if len(self._pcm) == 0:
            return
        self._close_stream()
        with self._play_lock:
            wrapped = self._play_pos >= len(self._pcm)
            if wrapped:
                self._play_pos = 0
            from_start = self._play_pos == 0
        if wrapped:
            self._clear_hist_buffer()
            self._refresh_hist_view()
        elif from_start and len(self._hist_columns) > 0:
            self._clear_hist_buffer()
            self._refresh_hist_view()
        self._playing = True
        self._play_btn.config(state=tk.DISABLED)
        self._pause_btn.config(state=tk.NORMAL)
        try:
            self._stream = sd.OutputStream(
                samplerate=TARGET_SR,
                channels=1,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            self._playing = False
            self._play_btn.config(state=tk.NORMAL)
            self._pause_btn.config(state=tk.DISABLED)
            self.log(f"[ERROR] Cannot open audio device: {e}")
            messagebox.showerror("Audio error", str(e))
            return
        self._poll_visual()

    def _pause(self):
        self._playing = False
        self._stop_poll()
        self._close_stream()
        with self._viz_lock:
            self._viz_block = None
        self._play_btn.config(state=tk.NORMAL if len(self._pcm) else tk.DISABLED)
        self._pause_btn.config(state=tk.DISABLED)

    def _stop(self):
        self._pause()
        with self._play_lock:
            self._play_pos = 0

def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = SpectrumAnalyzerGUI(root)
    try:
        if root.winfo_exists():
            root.mainloop()
    except tk.TclError:
        pass


if __name__ == "__main__":
    main()
