"""
Launcher GUI - Scans and presents available launcher scripts

Tools are grouped by function: Video & Audio Edit | Suno Tools | Private Tools.
Slim top bar with horizontal tool strip and expandable log panel (pypdf-toolbox style).

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
from tkinter import ttk, messagebox, scrolledtext
import os
import sys
import subprocess
import platform
import threading
import queue
from pathlib import Path
from datetime import datetime


class LauncherGUI:
    """Slim top-bar launcher with tools grouped by function and expandable log panel."""

    LAUNCHER_HEIGHT = 70
    LAUNCHER_PADDING = 10

    def __init__(self, root):
        self.root = root
        self.root.title("Launcher - Audio/Video Tools")

        self.script_dir = Path(__file__).parent
        self.root_dir = self.script_dir.parent

        self.is_windows = platform.system() == "Windows"
        self.launcher_ext = ".bat" if self.is_windows else ".sh"

        self.launchers = []
        self.running_processes = {}  # key -> {"process", "launcher", "thread"}
        self._launch_counter = 0

        self.log_panel_visible = False
        self.log_queue = queue.Queue()

        self._position_launcher()
        self.setup_ui()
        self.scan_launchers()
        self.populate_tools()
        self.process_log_queue()

    def _position_launcher(self):
        """Set initial window size and position (full screen width)."""
        try:
            self._screen_width = self.root.winfo_screenwidth()
            self._screen_height = self.root.winfo_screenheight()
        except tk.TclError:
            self._screen_width, self._screen_height = 1280, 720
        width = self._screen_width - 2 * self.LAUNCHER_PADDING
        self.root.geometry(f"{width}x{self.LAUNCHER_HEIGHT}+{self.LAUNCHER_PADDING}+{self.LAUNCHER_PADDING}")
        self.root.resizable(True, False)
        self.root.minsize(800, self.LAUNCHER_HEIGHT)

    def _get_tool_category(self, name, from_private=False):
        """Return category for display/sort: video_audio, suno, private."""
        if from_private:
            return "private"
        name_lower = name.lower()
        if "suno" in name_lower or "song_style_analyzer" in name_lower:
            return "suno"
        return "video_audio"

    def _get_tool_icon(self, name):
        """Return a short label/icon for the tool."""
        name_lower = name.lower()
        if "youtube" in name_lower or "download" in name_lower:
            return "\u25b6"
        if "video" in name_lower and "mp3" in name_lower:
            return "\u2192"
        if "mp3" in name_lower and "video" in name_lower:
            return "\u2190"
        if "audio" in name_lower or "modifier" in name_lower:
            return "\u266b"
        if "editor" in name_lower:
            return "\u270e"
        if "suno" in name_lower:
            return "\u2600"
        if "cover" in name_lower or "checker" in name_lower:
            return "\u2713"
        if "image" in name_lower or "format" in name_lower:
            return "\u25a1"
        if "flac" in name_lower or "wav" in name_lower:
            return "\u266a"
        if "style" in name_lower or "analyzer" in name_lower:
            return "\u2699"
        if "unified" in name_lower:
            return "\u2630"
        if "grok" in name_lower or "imagine" in name_lower:
            return "\u2728"
        return "\u2731"

    def setup_ui(self):
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main, padding=5)
        top.pack(side="top", fill="x")

        left = ttk.Frame(top)
        left.pack(side="left", fill="y")
        ttk.Label(
            left,
            text="Launcher - Audio/Video Tools",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(5, 15))

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=5)

        self.tools_frame = ttk.Frame(top)
        self.tools_frame.pack(side="left", fill="both", expand=True)

        self.tools_canvas = tk.Canvas(
            self.tools_frame,
            height=50,
            highlightthickness=0,
        )
        self.tools_scrollbar = ttk.Scrollbar(
            self.tools_frame,
            orient="horizontal",
            command=self.tools_canvas.xview,
        )
        self.tools_canvas.configure(xscrollcommand=self.tools_scrollbar.set)
        self.tools_canvas.pack(side="top", fill="both", expand=True)
        self.tools_scrollbar.pack(side="bottom", fill="x")

        self.buttons_frame = ttk.Frame(self.tools_canvas)
        self.canvas_window = self.tools_canvas.create_window(
            (0, 0), window=self.buttons_frame, anchor="nw"
        )

        def on_buttons_configure(_):
            bbox = self.tools_canvas.bbox("all")
            if bbox:
                self.tools_canvas.configure(scrollregion=bbox)

        def on_canvas_configure(_):
            h = self.tools_canvas.winfo_height()
            if h > 1:
                self.tools_canvas.itemconfig(self.canvas_window, height=h)

        self.buttons_frame.bind("<Configure>", on_buttons_configure)
        self.tools_canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else 0
            self.tools_canvas.xview_scroll(delta, "units")

        self.tools_canvas.bind("<MouseWheel>", on_mousewheel)
        self.buttons_frame.bind("<MouseWheel>", on_mousewheel)

        ttk.Separator(top, orient="vertical").pack(side="right", fill="y", padx=5)
        right = ttk.Frame(top)
        right.pack(side="right", fill="y")

        ttk.Button(right, text="Refresh", width=7, command=self.refresh_launchers).pack(
            side="left", padx=2
        )
        ttk.Button(right, text="Close All", width=8, command=self._close_all_tools).pack(
            side="left", padx=2
        )
        self.log_toggle_btn = ttk.Button(
            right, text="Log", width=6, command=self.toggle_log_panel
        )
        self.log_toggle_btn.pack(side="left", padx=2)
        ttk.Button(right, text="Clear", width=6, command=self.clear_console).pack(
            side="left", padx=2
        )
        ttk.Button(right, text="Exit", width=5, command=self._on_close).pack(
            side="left", padx=2
        )
        self.status_label = ttk.Label(right, text="", font=("Segoe UI", 8))
        self.status_label.pack(side="left", padx=5)

        self.create_log_panel(main)

    def create_log_panel(self, parent):
        """Create the expandable log panel (packed when visible)."""
        self.log_panel = ttk.LabelFrame(parent, text="Console Output", padding=5)
        # Do not pack here; pack in toggle_log_panel when shown

        header = ttk.Frame(self.log_panel)
        header.pack(fill="x", pady=(0, 5))
        ttk.Button(header, text="Clear", width=6, command=self.clear_console).pack(
            side="right"
        )

        self.console_text = scrolledtext.ScrolledText(
            self.log_panel,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
        )
        self.console_text.pack(fill="both", expand=True)
        self.console_text.config(state=tk.DISABLED)

        self.console_text.tag_configure("timestamp", foreground="#6a9955")
        self.console_text.tag_configure("tool_name", foreground="#4ec9b0", font=("Consolas", 9, "bold"))
        self.console_text.tag_configure("error", foreground="#f14c4c")
        self.console_text.tag_configure("info", foreground="#3794ff")

    def toggle_log_panel(self):
        width = getattr(self, "_screen_width", self.root.winfo_screenwidth()) - 2 * self.LAUNCHER_PADDING
        if self.log_panel_visible:
            self.log_panel.pack_forget()
            self.log_panel_visible = False
            self.log_toggle_btn.config(text="Log")
            self.root.geometry(f"{width}x{self.LAUNCHER_HEIGHT}")
        else:
            self.log_panel.pack(side="top", fill="both", expand=True)
            self.log_panel_visible = True
            self.log_toggle_btn.config(text="Hide Log")
            self.root.geometry(f"{width}x450")
        self.root.update_idletasks()

    def process_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self._append_log_direct(*item)
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def _append_log_direct(self, text, tool_name=None, is_error=False):
        self.console_text.config(state=tk.NORMAL)
        self.console_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] ", "timestamp")
        if tool_name:
            self.console_text.insert(tk.END, f"[{tool_name}] ", "tool_name")
        tag = "error" if is_error else None
        self.console_text.insert(tk.END, text + "\n", tag)
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)

    def append_console(self, text, tool_name=None, is_error=False):
        """Thread-safe append to log."""
        self.log_queue.put((text.rstrip() if isinstance(text, str) else str(text), tool_name, is_error))

    def clear_console(self):
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        self.console_text.config(state=tk.DISABLED)

    def scan_launchers(self):
        self.launchers = []
        for base_dir, from_private in [
            (self.root_dir / "launchers", False),
            (self.root_dir / "private" / "launchers", True),
        ]:
            if not base_dir.exists():
                continue
            for f in base_dir.glob(f"*{self.launcher_ext}"):
                name = f.stem
                cat = self._get_tool_category(name, from_private=from_private)
                display = name.replace("_", " ").title()
                self.launchers.append({
                    "name": name,
                    "display_name": display,
                    "path": f,
                    "category": cat,
                    "icon": self._get_tool_icon(name),
                    "from_private": from_private,
                })
        order = ("video_audio", "suno", "private")
        self.launchers.sort(
            key=lambda x: (
                order.index(x["category"]) if x["category"] in order else 99,
                x["name"],
            )
        )

    def populate_tools(self):
        for w in self.buttons_frame.winfo_children():
            w.destroy()

        if not self.launchers:
            ttk.Label(
                self.buttons_frame,
                text="No launchers found in launchers/ or private/launchers/",
                font=("Segoe UI", 9),
            ).pack(padx=10, pady=10)
            self.status_label.config(text="0 tools")
            return

        category_names = {
            "video_audio": "Video & Audio Edit",
            "suno": "Suno Tools",
            "private": "Private Tools",
        }
        current_cat = None
        for launcher in self.launchers:
            cat = launcher["category"]
            if cat != current_cat:
                if current_cat is not None:
                    sep = ttk.Frame(self.buttons_frame)
                    sep.pack(side="left", padx=8, pady=5)
                    ttk.Separator(sep, orient="vertical").pack(fill="y", expand=True)
                lbl = ttk.Label(
                    self.buttons_frame,
                    text=category_names.get(cat, cat),
                    font=("Segoe UI", 8, "bold"),
                )
                lbl.pack(side="left", padx=(10, 4), pady=5)
                current_cat = cat
            self._create_tool_button(launcher)

        self.root.after_idle(
            lambda: self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))
        )
        self.status_label.config(text=f"{len(self.launchers)} tools")

    def _get_python_script_path(self, launcher):
        """Resolve the Python script path for this launcher (no console launch)."""
        name = launcher["name"]
        if launcher.get("from_private"):
            script = self.root_dir / "private" / "grok" / f"{name}.py"
        else:
            script = self.root_dir / "scripts" / f"{name}.py"
        return script if script.exists() else None

    def _get_venv_python(self):
        """Return path to venv Python executable, or None."""
        if self.is_windows:
            exe = self.root_dir / "venv" / "Scripts" / "python.exe"
        else:
            exe = self.root_dir / "venv" / "bin" / "python"
        return exe if exe.exists() else None

    def _create_tool_button(self, launcher):
        frame = ttk.Frame(self.buttons_frame)
        frame.pack(side="left", padx=3, pady=5)
        btn_text = f"{launcher['icon']} {launcher['display_name']}"
        btn = ttk.Button(
            frame,
            text=btn_text,
            command=lambda l=launcher: self.launch_script(l),
            width=max(14, len(launcher["display_name"]) + 3),
        )
        btn.pack()
        launcher["button"] = btn

    def read_output(self, process, stream, tool_name=None):
        try:
            while True:
                line = stream.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    import time
                    time.sleep(0.01)
                    continue
                self.log_queue.put((line.rstrip() if line else "", tool_name, False))
        except Exception as e:
            self.log_queue.put((f"Error reading output: {e}", tool_name, True))
        finally:
            try:
                if not stream.closed:
                    stream.close()
            except Exception:
                pass

    def launch_script(self, launcher):
        path = launcher["path"]
        name = launcher["name"]
        display = launcher["display_name"]

        if not path.exists():
            messagebox.showerror("Error", f"Launcher not found:\n{path}")
            return

        self.status_label.config(text=f"Launching {display}...")
        self.append_console("=" * 50, name)
        self.append_console(f"Launching: {display}", name)
        self.append_console(str(path), name)
        self.append_console("=" * 50, name)
        self.root.update()

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        self._launch_counter += 1
        run_key = f"{name}_{self._launch_counter}"

        try:
            if self.is_windows:
                script_path = self._get_python_script_path(launcher)
                python_exe = self._get_venv_python()
                if script_path and python_exe:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    process = subprocess.Popen(
                        [str(python_exe), str(script_path)],
                        cwd=str(self.root_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        shell=False,
                        env=env,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW if getattr(subprocess, "CREATE_NO_WINDOW", None) else 0,
                    )
                else:
                    process = subprocess.Popen(
                        ["cmd", "/u", "/c", str(path)],
                        cwd=str(self.root_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        shell=False,
                        env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW if getattr(subprocess, "CREATE_NO_WINDOW", None) else 0,
                    )
            else:
                script_path = self._get_python_script_path(launcher)
                python_exe = self._get_venv_python()
                if script_path and python_exe:
                    process = subprocess.Popen(
                        [str(python_exe), str(script_path)],
                        cwd=str(self.root_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        shell=False,
                        env=env,
                    )
                else:
                    process = subprocess.Popen(
                        ["bash", str(path)],
                        cwd=str(self.root_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        shell=False,
                        env=env,
                    )

            out_thread = threading.Thread(
                target=self.read_output,
                args=(process, process.stdout, name),
                daemon=True,
            )
            out_thread.start()
            self.running_processes[run_key] = {
                "process": process,
                "launcher": launcher,
                "thread": out_thread,
            }

            def send_enter():
                import time
                time.sleep(0.5)
                if process.stdin and process.poll() is None:
                    try:
                        process.stdin.write("\n")
                        process.stdin.flush()
                    except (BrokenPipeError, OSError):
                        pass

            threading.Thread(target=send_enter, daemon=True).start()
            self._monitor_process(run_key)
            n = len([p for p in self.running_processes.values() if p["process"].poll() is None])
            self.status_label.config(text=f"Running: {display} ({n} app(s) active)")
        except Exception as e:
            self.append_console(f"Failed to launch: {e}", name, is_error=True)
            messagebox.showerror("Error", f"Failed to launch {display}:\n{e}")
            self.status_label.config(text="Error")

    def _monitor_process(self, run_key):
        def check():
            entry = self.running_processes.get(run_key)
            if not entry:
                return
            process = entry["process"]
            launcher = entry["launcher"]
            if process.poll() is not None:
                ret = process.poll()
                self.running_processes.pop(run_key, None)
                self.root.after(0, self.append_console, f"Process finished (exit {ret})", launcher["name"])
                n = len([p for p in self.running_processes.values() if p["process"].poll() is None])
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Finished: {launcher['display_name']}" + (f" ({n} still running)" if n else "")
                ))
            else:
                self.root.after(100, check)
        self.root.after(100, check)

    def _close_all_tools(self):
        to_stop = [
            (key, entry["process"], entry["launcher"]["display_name"])
            for key, entry in list(self.running_processes.items())
            if entry["process"].poll() is None
        ]
        if not to_stop:
            self.status_label.config(text="No tools running")
            return
        for key, process, display in to_stop:
            try:
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass
            self.running_processes.pop(key, None)
        self.status_label.config(text=f"Closed {len(to_stop)} tool(s)")
        self.root.after(2000, lambda: self.status_label.config(text=f"{len(self.launchers)} tools"))

    def refresh_launchers(self):
        self.scan_launchers()
        self.populate_tools()
        self.status_label.config(text=f"{len(self.launchers)} tools")

    def _on_close(self):
        running = [p for p in self.running_processes.values() if p["process"].poll() is None]
        if running:
            if messagebox.askyesno("Exit", f"{len(running)} tool(s) still running. Stop all and exit?"):
                for entry in list(self.running_processes.values()):
                    proc = entry["process"]
                    if proc.poll() is None:
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        except Exception:
                            pass
        self.root.quit()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = LauncherGUI(root)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
