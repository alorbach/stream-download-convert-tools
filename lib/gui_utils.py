"""
GUI Utilities

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

Common GUI components and utilities for audio tools applications.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os


class GUIManager:
    """Manages common GUI operations."""
    
    def __init__(self, root):
        """
        Initialize GUI manager.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.is_busy = False
    
    def center_window(self, window, width=None, height=None):
        """
        Center a window on the screen.
        
        Args:
            window: Tkinter window to center
            width: Window width (optional, uses current width if not provided)
            height: Window height (optional, uses current height if not provided)
        """
        # Update window to get current size if not provided
        window.update_idletasks()
        
        if width is None or height is None:
            # Get actual window dimensions after content is loaded
            width = window.winfo_reqwidth()
            height = window.winfo_reqheight()
            
            # Fallback to geometry if reqwidth/reqheight don't work
            if width <= 1 or height <= 1:
                current_geometry = window.geometry()
                if '+' in current_geometry:
                    # Format: "WIDTHxHEIGHT+X+Y"
                    size_part = current_geometry.split('+')[0]
                    width, height = map(int, size_part.split('x'))
                else:
                    # Format: "WIDTHxHEIGHT"
                    width, height = map(int, current_geometry.split('x'))
        
        # Get screen dimensions
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Calculate position to center the window
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set the window position
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def set_busy(self, busy=True, message="", progress_bar=None, progress_label=None):
        """
        Set busy state for the application.
        
        Args:
            busy: Whether the app is busy
            message: Status message to display
            progress_bar: Progress bar widget to animate
            progress_label: Label widget to update
        """
        self.is_busy = busy
        if busy:
            self.root.config(cursor="wait")
            if progress_bar:
                progress_bar.start(10)
            if progress_label:
                progress_label.config(text=message)
        else:
            self.root.config(cursor="")
            if progress_bar:
                progress_bar.stop()
            if progress_label:
                progress_label.config(text="")
    
    def browse_folder(self, initial_dir=None, title="Select Folder"):
        """
        Open folder browser dialog.
        
        Args:
            initial_dir: Initial directory to show
            title: Dialog title
            
        Returns:
            str: Selected folder path or None
        """
        folder = filedialog.askdirectory(
            initialdir=initial_dir,
            title=title
        )
        return folder if folder else None
    
    def select_files(self, title="Select Files", filetypes=None, initial_dir=None):
        """
        Open file selection dialog.
        
        Args:
            title: Dialog title
            filetypes: List of file type tuples
            initial_dir: Initial directory to show
            
        Returns:
            tuple: Selected file paths or empty tuple
        """
        if filetypes is None:
            filetypes = [("All Files", "*.*")]
        
        files = filedialog.askopenfilenames(
            title=title,
            filetypes=filetypes,
            initialdir=initial_dir
        )
        return files if files else ()
    
    def show_message(self, msg_type, title, message):
        """
        Show a message box.
        
        Args:
            msg_type: Type of message ('info', 'warning', 'error', 'askyesno')
            title: Message box title
            message: Message content
            
        Returns:
            bool: Result for askyesno, None for others
        """
        if msg_type == 'info':
            messagebox.showinfo(title, message)
        elif msg_type == 'warning':
            messagebox.showwarning(title, message)
        elif msg_type == 'error':
            messagebox.showerror(title, message)
        elif msg_type == 'askyesno':
            return messagebox.askyesno(title, message)
        return None
    
    def create_scrolled_text(self, parent, height=10):
        """
        Create a scrolled text widget.
        
        Args:
            parent: Parent widget
            height: Height in lines
            
        Returns:
            ScrolledText: Scrolled text widget
        """
        return scrolledtext.ScrolledText(parent, height=height)
    
    def create_progress_bar(self, parent, mode='determinate'):
        """
        Create a progress bar widget.
        
        Args:
            parent: Parent widget
            mode: Progress bar mode ('determinate' or 'indeterminate')
            
        Returns:
            ttk.Progressbar: Progress bar widget
        """
        return ttk.Progressbar(parent, mode=mode)
    
    def create_file_listbox(self, parent, height=8, selectmode=tk.EXTENDED):
        """
        Create a file listbox with scrollbars.
        
        Args:
            parent: Parent widget
            height: Height in lines
            selectmode: Selection mode
            
        Returns:
            tuple: (listbox, frame) - listbox widget and its frame
        """
        frame = ttk.Frame(parent)
        
        scrollbar_y = ttk.Scrollbar(frame, orient='vertical')
        scrollbar_x = ttk.Scrollbar(frame, orient='horizontal')
        
        listbox = tk.Listbox(
            frame,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            height=height,
            selectmode=selectmode
        )
        
        scrollbar_y.config(command=listbox.yview)
        scrollbar_x.config(command=listbox.xview)
        
        listbox.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        return listbox, frame


class LogManager:
    """Manages logging for GUI applications."""
    
    def __init__(self, log_widget=None):
        """
        Initialize log manager.
        
        Args:
            log_widget: ScrolledText widget for logging
        """
        self.log_widget = log_widget
    
    def set_log_widget(self, log_widget):
        """Set the log widget."""
        self.log_widget = log_widget
    
    def log(self, message):
        """
        Log a message to the widget.
        
        Args:
            message: Message to log
        """
        if self.log_widget:
            self.log_widget.insert(tk.END, f"{message}\n")
            self.log_widget.see(tk.END)
        else:
            print(f"[LOG] {message}")
    
    def log_info(self, message):
        """Log an info message."""
        self.log(f"[INFO] {message}")
    
    def log_error(self, message):
        """Log an error message."""
        self.log(f"[ERROR] {message}")
    
    def log_success(self, message):
        """Log a success message."""
        self.log(f"[SUCCESS] {message}")
    
    def log_debug(self, message):
        """Log a debug message."""
        self.log(f"[DEBUG] {message}")
    
    def clear_log(self):
        """Clear the log widget."""
        if self.log_widget:
            self.log_widget.delete(1.0, tk.END)
