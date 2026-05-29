"""Video to MP3 tab for Video Tools Unified."""

import os
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from lib.video_utils import parse_dropped_paths

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.m4a', '.avi', '.mov', '.mkv', '.flv', '.wmv'}


class VideoToMp3Tab:
  TAB_NAME = 'Video to MP3'

  def __init__(self, app, parent):
    self.app = app
    self.parent = parent
    self.root = app.root
    self.selected_files = []
    self.conversion_queue = []
    self.setup_ui()

  def setup_ui(self):
    top_frame = ttk.LabelFrame(self.parent, text='File Selection', padding=10)
    top_frame.pack(fill='both', expand=True, padx=10, pady=10)

    btn_frame = ttk.Frame(top_frame)
    btn_frame.pack(fill='x', pady=5)
    ttk.Button(btn_frame, text='Select Video Files', command=self.select_files).pack(side='left', padx=5)
    ttk.Button(btn_frame, text='Clear Selection', command=self.clear_selection).pack(side='left', padx=5)
    self.lbl_status = ttk.Label(btn_frame, text='No files selected')
    self.lbl_status.pack(side='left', padx=10)

    list_frame = ttk.Frame(top_frame)
    list_frame.pack(fill='both', expand=True)
    sy = ttk.Scrollbar(list_frame, orient='vertical')
    sx = ttk.Scrollbar(list_frame, orient='horizontal')
    self.file_listbox = tk.Listbox(
      list_frame, yscrollcommand=sy.set, xscrollcommand=sx.set,
      height=8, selectmode=tk.EXTENDED,
    )
    sy.config(command=self.file_listbox.yview)
    sx.config(command=self.file_listbox.xview)
    self.file_listbox.grid(row=0, column=0, sticky='nsew')
    sy.grid(row=0, column=1, sticky='ns')
    sx.grid(row=1, column=0, sticky='ew')
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)
    if DND_FILES:
      try:
        self.file_listbox.drop_target_register(DND_FILES)
        self.file_listbox.dnd_bind('<<Drop>>', self.on_drop_files)
      except Exception:
        pass

    settings_frame = ttk.LabelFrame(self.parent, text='Conversion Settings', padding=10)
    settings_frame.pack(fill='x', padx=10, pady=5)
    ttk.Label(settings_frame, text='Downloads Folder:').grid(row=0, column=0, sticky='w', pady=5)
    self.downloads_folder_var = tk.StringVar(
      value=self.app.get_setting('v2m_downloads', self.app.file_manager.get_folder_path('downloads')))
    ttk.Entry(settings_frame, textvariable=self.downloads_folder_var, width=50).grid(row=0, column=1, padx=5)
    ttk.Button(settings_frame, text='Browse', command=self.browse_downloads).grid(row=0, column=2)

    ttk.Label(settings_frame, text='Output Folder:').grid(row=1, column=0, sticky='w', pady=5)
    self.folder_var = tk.StringVar(
      value=self.app.get_setting('v2m_output', self.app.file_manager.get_folder_path('converted')))
    ttk.Entry(settings_frame, textvariable=self.folder_var, width=50).grid(row=1, column=1, padx=5)
    ttk.Button(settings_frame, text='Browse', command=self.browse_output).grid(row=1, column=2)

    ttk.Label(settings_frame, text='Audio Quality:').grid(row=2, column=0, sticky='w', pady=5)
    self.quality_var = tk.StringVar(value=self.app.get_setting('v2m_quality', '192k'))
    q = ttk.Combobox(settings_frame, textvariable=self.quality_var, width=20, state='readonly')
    q['values'] = ('128k', '192k', '256k', '320k')
    q.grid(row=2, column=1, sticky='w', padx=5)

    convert_frame = ttk.Frame(self.parent)
    convert_frame.pack(fill='x', padx=10, pady=5)
    ttk.Button(convert_frame, text='Convert Selected Files', command=self.start_conversion).pack(side='left', padx=5)
    ttk.Button(convert_frame, text='Convert All Files', command=self.convert_all_files).pack(side='left', padx=5)
    self.progress = ttk.Progressbar(convert_frame, mode='determinate')
    self.progress.pack(fill='x', pady=5)
    self.progress_label = ttk.Label(convert_frame, text='')
    self.progress_label.pack(anchor='w')

  def log(self, message):
    self.app.log(message, self.TAB_NAME)

  def browse_downloads(self):
    folder = self.app.browse_folder(self.downloads_folder_var.get())
    if folder:
      self.downloads_folder_var.set(folder)
      self.app.set_setting('v2m_downloads', folder)

  def browse_output(self):
    folder = self.app.browse_folder(self.folder_var.get())
    if folder:
      self.folder_var.set(folder)
      self.app.set_setting('v2m_output', folder)

  def select_files(self):
    files = self.app.select_files(
      title='Select Video/Audio Files',
      filetypes=self.app.file_manager.get_video_filetypes(),
      initial_dir=self.downloads_folder_var.get(),
    )
    if files:
      for f in files:
        if f not in self.selected_files:
          self.selected_files.append(f)
      self.update_file_list()
      self.log(f'[INFO] Added {len(files)} file(s)')

  def clear_selection(self):
    self.selected_files.clear()
    self.update_file_list()

  def update_file_list(self):
    self.file_listbox.delete(0, tk.END)
    for f in self.selected_files:
      self.file_listbox.insert(tk.END, os.path.basename(f))
    self.lbl_status.config(text=f'{len(self.selected_files)} file(s) selected')

  def on_drop_files(self, event):
    paths = parse_dropped_paths(event.data)
    added = 0
    for p in paths:
      if os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS and p not in self.selected_files:
        self.selected_files.append(p)
        added += 1
    if added:
      self.update_file_list()
      self.log(f'[INFO] Added {added} file(s) via drag and drop')

  def start_conversion(self):
    if self.app.is_busy:
      messagebox.showwarning('Warning', 'Conversion already in progress')
      return
    if not self.selected_files:
      messagebox.showwarning('Warning', 'Please select at least one video file')
      return
    if not self.app.check_ffmpeg():
      self.app.offer_ffmpeg_install()
      return
    out = self.folder_var.get()
    self.app.ensure_directory(out)
    self.app.set_setting('v2m_output', out)
    self.app.set_setting('v2m_quality', self.quality_var.get())
    self.conversion_queue = list(self.selected_files)
    self.progress['maximum'] = len(self.conversion_queue)
    self.progress['value'] = 0
    self.app.set_busy(True, 'Converting...')
    threading.Thread(target=self._conversion_thread, args=(out,), daemon=True).start()

  def _conversion_thread(self, output_folder):
    ok, fail = 0, 0
    for i, input_file in enumerate(self.conversion_queue):
      out_file = os.path.join(output_folder, f'{Path(input_file).stem}.mp3')
      self.root.after(0, lambda n=i + 1, t=len(self.conversion_queue), f=Path(input_file).name:
                      self.app.set_busy(True, f'Converting {n}/{t}: {f}'))
      self.root.after(0, lambda m=f'\n[INFO] Converting ({i+1}/{len(self.conversion_queue)}): {Path(input_file).name}': self.log(m))
      try:
        cmd = self.app.build_ffmpeg_command(
          input_file, out_file, audio_codec='mp3', audio_bitrate=self.quality_var.get())
        proc = self.app.run_ffmpeg_command(cmd)
        if proc.returncode == 0:
          ok += 1
          self.root.after(0, lambda o=out_file: self.log(f'[SUCCESS] Saved: {os.path.basename(o)}'))
        else:
          fail += 1
          err = (proc.stderr or 'Unknown error')[:200]
          self.root.after(0, lambda e=err: self.log(f'[ERROR] {e}'))
      except Exception as e:
        fail += 1
        self.root.after(0, lambda m=str(e): self.log(f'[ERROR] {m}'))
      self.root.after(0, lambda v=i + 1: self.progress.config(value=v))
    self.root.after(0, lambda: self.log(f'\n[COMPLETE] {ok} succeeded, {fail} failed'))
    self.root.after(0, lambda: messagebox.showinfo('Done', f'Successful: {ok}\nFailed: {fail}'))
    self.root.after(0, lambda: self.app.set_busy(False))

  def convert_all_files(self):
    folder = self.downloads_folder_var.get()
    if not os.path.isdir(folder):
      messagebox.showerror('Error', 'Downloads folder does not exist')
      return
    found = []
    for name in os.listdir(folder):
      p = os.path.join(folder, name)
      if os.path.isfile(p) and os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
        found.append(p)
    if not found:
      messagebox.showwarning('Warning', 'No video files found in downloads folder')
      return
    self.selected_files = found
    self.update_file_list()
    self.log(f'[INFO] Found {len(found)} video files')
    self.start_conversion()
