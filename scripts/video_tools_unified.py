"""
Video Tools - Unified Application

Combines video editor, format converter, MP3/video converters, and chunk splitting.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from tkinterdnd2 import TkinterDnD
    DND_ROOT = TkinterDnD.Tk
except ImportError:
    DND_ROOT = tk.Tk

from lib.base_gui import BaseAudioGUI
from lib.gui_utils import LogManager

from video_tabs import (
    VideoToMp3Tab,
    FormatCropTab,
    Mp3ToVideoTab,
    CombineVideosTab,
    SplitChunksTab,
    MergeSplitTab,
    UpscaleTab,
)

SETTINGS_FILE = 'video_tools_unified_settings.json'
LEGACY_SETTINGS = {
    'combine': 'video_editor_settings.json',
    'mp3_video': 'mp3_to_video_converter_settings.json',
    'format': 'image_format_converter_settings.json',
}
# v2m tab uses app-level keys (v2m_*), not legacy file import


class VideoToolsUnifiedGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, 'Video Tools - Unified')
        self.root.geometry('1280x950')
        self.settings_path = os.path.join(self.root_dir, SETTINGS_FILE)
        self._settings = {}
        self._tabs = {}
        self.load_all_settings()
        self.setup_ui()
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

    def setup_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=5, pady=5)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True)

        self.tab_v2m = ttk.Frame(self.notebook)
        self.tab_format = ttk.Frame(self.notebook)
        self.tab_mp3_video = ttk.Frame(self.notebook)
        self.tab_combine = ttk.Frame(self.notebook)
        self.tab_split = ttk.Frame(self.notebook)
        self.tab_merge_split = ttk.Frame(self.notebook)
        self.tab_upscale = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_v2m, text='Video to MP3')
        self.notebook.add(self.tab_format, text='Format and Crop')
        self.notebook.add(self.tab_mp3_video, text='MP3 to Video')
        self.notebook.add(self.tab_combine, text='Combine Videos')
        self.notebook.add(self.tab_split, text='Split and Chunks')
        self.notebook.add(self.tab_merge_split, text='Merge Split + Lip Sync')
        self.notebook.add(self.tab_upscale, text='Upscale Video')
        self.notebook.add(self.tab_settings, text='Settings')

        self._tabs['v2m'] = VideoToMp3Tab(self, self.tab_v2m)
        self._tabs['format'] = FormatCropTab(self, self.tab_format)
        self._tabs['mp3_video'] = Mp3ToVideoTab(self, self.tab_mp3_video)
        self._tabs['combine'] = CombineVideosTab(self, self.tab_combine)
        self._tabs['split'] = SplitChunksTab(self, self.tab_split)
        self._tabs['merge_split'] = MergeSplitTab(self, self.tab_merge_split)
        self._tabs['upscale'] = UpscaleTab(self, self.tab_upscale)
        self.setup_settings_tab()

        progress_frame = ttk.Frame(main)
        progress_frame.pack(fill='x', pady=(5, 0))
        self.global_progress = ttk.Progressbar(progress_frame, mode='determinate', maximum=100)
        self.global_progress.pack(fill='x')
        self.global_progress_label = ttk.Label(progress_frame, text='')
        self.global_progress_label.pack(anchor='w')

        log_frame = ttk.LabelFrame(main, text='Log', padding=5)
        log_frame.pack(fill='x', pady=(5, 0))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill='both', expand=True)
        self.log_manager = LogManager(self.log_text)

        if not self.check_ffmpeg():
            self.log('[WARNING] FFmpeg not found. Use Settings tab or install FFmpeg.')

    def setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Video Tools Settings', font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        ttk.Label(frame, text=f'Settings file: {self.settings_path}').pack(anchor='w')
        ttk.Label(frame, text='FFmpeg status:').pack(anchor='w', pady=(10, 0))
        status = 'Available' if self.check_ffmpeg() else 'Not found'
        ttk.Label(frame, text=status).pack(anchor='w')
        btn_row = ttk.Frame(frame)
        btn_row.pack(anchor='w', pady=15)
        ttk.Button(btn_row, text='Check FFmpeg', command=self._check_ffmpeg_ui).pack(side='left', padx=5)
        ttk.Button(btn_row, text='Offer FFmpeg Install (Windows)', command=self.offer_ffmpeg_install).pack(side='left', padx=5)
        ttk.Label(
            frame,
            text='Documentation: docs/VIDEO_TOOLS_GUIDE.md',
            wraplength=700,
        ).pack(anchor='w', pady=10)
        ttk.Label(
            frame,
            text='Legacy per-tool settings are imported once from video_editor_settings.json, '
                 'mp3_to_video_converter_settings.json, and image_format_converter_settings.json.',
            wraplength=700,
        ).pack(anchor='w')

    def _check_ffmpeg_ui(self):
        if self.check_ffmpeg():
            messagebox.showinfo('FFmpeg', 'FFmpeg is available.')
        else:
            messagebox.showwarning('FFmpeg', 'FFmpeg was not found.')

    def log(self, message, tab=None):
        prefix = f'[{tab}] ' if tab else ''
        self.log_manager.log(f'{prefix}{message}')

    def log_callback(self, message):
        self.log(message)

    def set_progress(self, value=None, maximum=100, message='', indeterminate=False):
        def _apply():
            bar = self.global_progress
            label = self.global_progress_label
            bar.stop()
            if indeterminate:
                bar.configure(mode='indeterminate', maximum=100, value=0)
                label.config(text=message or 'Processing...')
                bar.start(10)
            else:
                bar.configure(mode='determinate')
                if maximum is not None:
                    bar['maximum'] = max(int(maximum), 1)
                if value is not None:
                    bar['value'] = value
                label.config(text=message or '')
        self.root.after(0, _apply)

    def reset_progress(self):
        def _apply():
            self.global_progress.stop()
            self.global_progress.configure(mode='determinate', maximum=100, value=0)
            self.global_progress_label.config(text='')
        self.root.after(0, _apply)

    def set_busy(self, busy=True, message='', progress_bar=None, progress_label=None):
        super().set_busy(busy, message, progress_bar, progress_label)
        if not busy:
            self.reset_progress()

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value
        self.save_all_settings()

    def get_tab_settings(self, tab_key):
        tabs = self._settings.get('tabs', {})
        data = tabs.get(tab_key)
        if data:
            return data
        legacy_name = LEGACY_SETTINGS.get(tab_key)
        if legacy_name:
            legacy_path = os.path.join(self.root_dir, legacy_name)
            if os.path.isfile(legacy_path):
                try:
                    with open(legacy_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    tabs[tab_key] = data
                    self._settings['tabs'] = tabs
                    self.save_all_settings()
                    return data
                except (json.JSONDecodeError, OSError):
                    pass
        return {}

    def set_tab_settings(self, tab_key, data):
        if 'tabs' not in self._settings:
            self._settings['tabs'] = {}
        self._settings['tabs'][tab_key] = data
        self.save_all_settings()

    def load_all_settings(self):
        if os.path.isfile(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    self._settings = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._settings = {}
        else:
            self._settings = {}

    def save_all_settings(self):
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except OSError as e:
            print(f'[WARNING] Could not save settings: {e}')

    def on_closing(self):
        for tab in self._tabs.values():
            if hasattr(tab, 'save_settings'):
                try:
                    tab.save_settings()
                except Exception:
                    pass
            if hasattr(tab, 'save_on_exit'):
                try:
                    tab.save_on_exit()
                except Exception:
                    pass
        self.save_all_settings()
        self.root.destroy()


def main():
    root = DND_ROOT()
    app = VideoToolsUnifiedGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
