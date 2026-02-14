"""
Legal Utilities

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

Handles legal disclaimer display and acceptance tracking.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox


# Marker filename for tracking user acceptance
ACCEPTANCE_MARKER = ".legal_accepted"


class LegalManager:
    """Manages legal disclaimer display and acceptance."""

    def __init__(self, root_dir):
        """
        Initialize legal manager.

        Args:
            root_dir: Root directory of the application (for storing acceptance marker)
        """
        self.root_dir = root_dir
        self.marker_path = os.path.join(root_dir, ACCEPTANCE_MARKER)

    def has_accepted(self):
        """
        Check if user has already accepted the legal disclaimer.

        Returns:
            bool: True if acceptance marker exists
        """
        return os.path.isfile(self.marker_path)

    def record_acceptance(self):
        """Create marker file to record that user accepted the disclaimer."""
        try:
            with open(self.marker_path, "w") as f:
                f.write("accepted\n")
        except OSError:
            pass

    def check_and_show_disclaimer(self, root):
        """
        Show legal disclaimer on first run. If user has not accepted before,
        display a modal dialog. Return False if user declines or closes,
        True if user accepts or has already accepted.

        Args:
            root: Tkinter root window

        Returns:
            bool: True to continue, False to abort (destroy window)
        """
        if self.has_accepted():
            return True

        disclaimer_text = """
LEGAL DISCLAIMER

This software is provided for educational and personal use only.

By using this software, you acknowledge that you are responsible for:
- Complying with applicable copyright laws in your jurisdiction
- Respecting YouTube's Terms of Service
- Only downloading content you have legal rights to access
- Understanding fair use guidelines for your intended use

IMPORTANT: This tool does not circumvent any digital rights management (DRM)
or access controls. You must ensure your use complies with all applicable
laws and platform terms of service.

The authors disclaim any responsibility for misuse of this software.

Do you accept these terms and wish to continue?
""".strip()

        # Create modal dialog
        dialog = tk.Toplevel(root)
        dialog.title("Legal Notice")
        dialog.transient(root)
        dialog.grab_set()
        dialog.resizable(True, True)

        # Center dialog on screen
        dialog.update_idletasks()
        width = 500
        height = 400
        x = (dialog.winfo_screenwidth() - width) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Content frame
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Text widget with disclaimer
        text = tk.Text(frame, wrap=tk.WORD, height=15, width=60, padx=5, pady=5)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, disclaimer_text)
        text.config(state=tk.DISABLED)

        result = {"accepted": False}

        def on_accept():
            result["accepted"] = True
            self.record_acceptance()
            dialog.destroy()

        def on_decline():
            result["accepted"] = False
            dialog.destroy()

        # Button frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="I Accept", command=on_accept).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Decline", command=on_decline).pack(side=tk.LEFT, padx=5)

        # Wait for dialog to close
        dialog.wait_window()
        return result["accepted"]
