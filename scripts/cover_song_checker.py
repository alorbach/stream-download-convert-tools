"""
Cover Song Checker - Check copyright risk before YouTube upload

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
from tkinter import ttk, filedialog, messagebox, scrolledtext
import csv
import re
import os
import sys
import threading
import subprocess
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import urllib.parse

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI


def get_config_path():
    """Get the path to the config.json file in the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'cover_song_checker_config.json')


def load_config():
    """Load configuration from JSON file."""
    config_path = get_config_path()
    default_config = {
        'ai_covers_base_dir': ''  # Empty means use default: root_dir/AI/AI-COVERS
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
    
    return default_config


def save_config(config):
    """Save configuration to JSON file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


class CoverSongCheckerGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Cover Song Checker")
        self.root.geometry("1400x1000")
        
        self.results = []
        self.is_analyzing = False
        
        # Load configuration
        self.config = load_config()
        
        # Initialize UMPG artist list
        self.umpg_artists = self._load_umpg_artists()
        
        # Universal Music Group labels and affiliates for generic UMG check
        self.umg_labels = self._load_umg_labels()
        
        # Get ffmpeg path for yt-dlp - check first to ensure path is set
        ffmpeg_found = self.check_ffmpeg()
        self.ffmpeg_path = self.get_ffmpeg_command()
        
        self.setup_ui()
        
        # Log ffmpeg status after UI is set up
        if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
            if os.path.exists(self.ffmpeg_path):
                ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                self.log(f"FFmpeg found at: {self.ffmpeg_path}")
                self.log(f"FFmpeg directory for yt-dlp: {ffmpeg_dir}")
            else:
                self.log(f"Warning: FFmpeg path set but file not found: {self.ffmpeg_path}")
        elif self.ffmpeg_path == 'ffmpeg':
            self.log("Using system FFmpeg (from PATH)")
        else:
            self.log("FFmpeg not found - yt-dlp warnings may appear")
            self.log(f"Checked: {self.ffmpeg_manager.ffmpeg_folder}")
    
    def setup_ui(self):
        # Create menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configure AI-COVERS Directory...", command=self.open_settings)
        
        # Main frame (no tabs, single view)
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.setup_check_tab(main_frame)
    
    def get_ai_covers_path(self):
        """Get the path to AI-COVERS directory from config or default."""
        base_dir = self.config.get('ai_covers_base_dir', '').strip()
        
        if base_dir and os.path.exists(base_dir) and os.path.isdir(base_dir):
            return base_dir
        
        # Default: use root_dir/AI/AI-COVERS
        return os.path.join(self.root_dir, 'AI', 'AI-COVERS')
    
    def setup_check_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Song Information", padding=10)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Warning label
        warning_frame = ttk.Frame(frame)
        warning_frame.pack(fill='x', pady=(0, 10))
        warning_label = ttk.Label(
            warning_frame, 
            text="NOTE: This tool analyzes cover video history. Actual Content ID claims/strikes require YouTube Data API v3.",
            foreground='orange',
            font=('TkDefaultFont', 8, 'italic'),
            wraplength=600
        )
        warning_label.pack()
        
        # Song Title
        title_frame = ttk.Frame(frame)
        title_frame.pack(fill='x', pady=5)
        ttk.Label(title_frame, text="Song Title:").pack(side='left', padx=(0, 5))
        self.song_title_var = tk.StringVar()
        ttk.Entry(title_frame, textvariable=self.song_title_var, width=50).pack(side='left', fill='x', expand=True)
        
        # Artist
        artist_frame = ttk.Frame(frame)
        artist_frame.pack(fill='x', pady=5)
        ttk.Label(artist_frame, text="Artist:").pack(side='left', padx=(0, 5))
        self.artist_var = tk.StringVar()
        ttk.Entry(artist_frame, textvariable=self.artist_var, width=50).pack(side='left', fill='x', expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        
        ttk.Button(btn_frame, text="Check Song", command=self.check_song).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Load CSV", command=self.load_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Load from Input Folder", command=self.load_csv_from_input).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Select from AI-COVERS", command=self.select_from_ai_covers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Scan All AI-COVERS", command=self.scan_ai_covers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Results", command=self.clear_results).pack(side='left', padx=5)
        
        # Second row of buttons for UMG mode
        btn_frame2 = ttk.Frame(frame)
        btn_frame2.pack(pady=5)
        
        umg_btn = ttk.Button(btn_frame2, text="UMG Check Mode", command=self.open_umg_check_mode)
        umg_btn.pack(side='left', padx=5)
        
        # Add tooltip-like label
        ttk.Label(btn_frame2, text="(Find all Universal Music protected artists/songs)", 
                 font=('TkDefaultFont', 8, 'italic'), foreground='gray').pack(side='left', padx=5)
        
        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.progress_var).pack(pady=10)
        
        self.progress_bar = ttk.Progressbar(frame, mode='indeterminate')
        self.progress_bar.pack(fill='x', pady=5)
        
        # Results Tree (above log)
        results_frame = ttk.LabelFrame(frame, text="Results", padding=5)
        results_frame.pack(fill='both', expand=True, pady=(10, 5))
        
        tree_container = ttk.Frame(results_frame)
        tree_container.pack(fill='both', expand=True)
        
        scroll_y = ttk.Scrollbar(tree_container, orient='vertical')
        scroll_x = ttk.Scrollbar(tree_container, orient='horizontal')
        
        self.results_tree = ttk.Treeview(tree_container, columns=(
            'Song Title', 'Artist', 'Cover Count', 'Claims %', 'Strikes %', 
            'Oldest Age', 'Avg Views', 'UMPG', 'Risk Level', 'Recommendation'
        ), show='headings', yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, height=8)
        
        scroll_y.config(command=self.results_tree.yview)
        scroll_x.config(command=self.results_tree.xview)
        
        # Column headers
        self.results_tree.heading('Song Title', text='Song Title')
        self.results_tree.heading('Artist', text='Artist')
        self.results_tree.heading('Cover Count', text='Cover Count')
        self.results_tree.heading('Claims %', text='Claims %')
        self.results_tree.heading('Strikes %', text='Strikes %')
        self.results_tree.heading('Oldest Age', text='Oldest Age')
        self.results_tree.heading('Avg Views', text='Avg Views')
        self.results_tree.heading('UMPG', text='UMPG')
        self.results_tree.heading('Risk Level', text='Risk Level')
        self.results_tree.heading('Recommendation', text='Recommendation')
        
        # Column widths
        self.results_tree.column('Song Title', width=180)
        self.results_tree.column('Artist', width=150)
        self.results_tree.column('Cover Count', width=100)
        self.results_tree.column('Claims %', width=80)
        self.results_tree.column('Strikes %', width=80)
        self.results_tree.column('Oldest Age', width=120)
        self.results_tree.column('Avg Views', width=120)
        self.results_tree.column('UMPG', width=60)
        self.results_tree.column('Risk Level', width=100)
        self.results_tree.column('Recommendation', width=300)
        
        self.results_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Bind double-click event
        self.results_tree.bind('<Double-1>', self.on_result_double_click)
        
        # Bind right-click for context menu
        self.results_tree.bind('<Button-3>', self.on_result_right_click)  # Windows
        self.results_tree.bind('<Button-2>', self.on_result_right_click)  # Mac/Linux
        
        # Configure tag colors for UMPG
        self.results_tree.tag_configure('umpg', foreground='red', font=('TkDefaultFont', 9, 'bold'))
        
        # Export button for results
        export_btn_frame = ttk.Frame(results_frame)
        export_btn_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(export_btn_frame, text="Export Results to CSV", command=self.export_csv).pack(side='left', padx=5)
        ttk.Label(export_btn_frame, text="(Double-click a result to view details)", font=('TkDefaultFont', 8, 'italic')).pack(side='left', padx=10)
        
        # Log (below results)
        log_frame = ttk.LabelFrame(frame, text="Log", padding=5)
        log_frame.pack(fill='both', expand=True, pady=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)
    
    
    def log(self, message):
        """Log message to text widget"""
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def _load_umpg_artists(self):
        """Load list of artists represented by Universal Music Publishing Group (UMPG)
        
        Based on information from UMPG official websites and Wikipedia.
        UMPG distributes copyright strikes, so artists represented by them
        are at higher risk for copyright issues.
        """
        ump_artists = {
            # Global major artists (from Wikipedia and UMPG global)
            'Taylor Swift', 'Bad Bunny', 'Drake', 'Kendrick Lamar', 'The Weeknd',
            'Rosalia', 'Steve Lacy', 'Elton John', 'Adele', 'SZA', 'Harry Styles',
            'Post Malone', 'Bob Dylan', 'Sting', 'Neil Diamond', 'Billie Eilish',
            'Alicia Keys', 'Brandi Carlile',
            
            # Germany/Europe (UMPG DE)
            'ABBA', 'Ariana Grande', 'Axwell', 'Alejandro Sanz',
            
            # USA / Nashville (Country)
            'Sam Hunt', 'Keith Urban', 'Luke Combs', 'Shania Twain', 'Maren Morris',
            
            # Additional major artists commonly associated with UMPG
            'Coldplay', 'Florence + The Machine', 'Florence and the Machine',
            'The Rolling Stones', 'Paul McCartney', 'John Lennon', 'George Harrison',
            'Ringo Starr', 'The Beatles', 'U2', 'Bon Jovi', 'Guns N\' Roses',
            'Metallica', 'Red Hot Chili Peppers', 'Pearl Jam', 'Nirvana',
            'Green Day', 'Blink-182', 'Linkin Park', 'Eminem', 'Dr. Dre',
            '50 Cent', 'Snoop Dogg', 'Ice Cube', 'Jay-Z', 'Kanye West',
            'Rihanna', 'Beyonce', 'Lady Gaga', 'Katy Perry', 'Bruno Mars',
            'Justin Timberlake', 'Justin Bieber', 'Ed Sheeran', 'Sam Smith',
            'Dua Lipa', 'The Weeknd', 'Lana Del Rey', 'Lorde', 'Halsey',
            'Imagine Dragons', 'Maroon 5', 'OneRepublic', 'The Chainsmokers',
            'Calvin Harris', 'David Guetta', 'Avicii', 'Swedish House Mafia',
            'Skrillex', 'Deadmau5', 'Tiësto', 'Armin van Buuren',
            
            # Additional songwriters and producers
            'Max Martin', 'Shellback', 'Dr. Luke', 'Ryan Tedder', 'Benny Blanco',
            'Pharrell Williams', 'Timbaland', 'The-Dream', 'Tricky Stewart',
        }
        
        # Create normalized lookup (case-insensitive, handle variations)
        normalized_lookup = {}
        for artist in ump_artists:
            # Store original and normalized versions
            normalized = artist.lower().strip()
            normalized_lookup[normalized] = artist
            # Also store without special characters for fuzzy matching
            normalized_clean = re.sub(r'[^\w\s]', '', normalized)
            if normalized_clean != normalized:
                normalized_lookup[normalized_clean] = artist
        
        return normalized_lookup
    
    def _load_umg_labels(self):
        """Load list of Universal Music Group labels and affiliates
        
        This is used for generic UMG detection mode to find all content
        potentially protected by Universal Music Group and its subsidiaries.
        """
        umg_labels = {
            # Major UMG Labels
            'Universal Music Group', 'UMG', 'Universal Music',
            'Interscope Records', 'Interscope', 'Interscope Geffen A&M',
            'Geffen Records', 'Geffen', 'A&M Records', 'A&M',
            'Republic Records', 'Republic', 
            'Def Jam Recordings', 'Def Jam', 'GOOD Music',
            'Island Records', 'Island Def Jam', 'Island',
            'Capitol Records', 'Capitol Music Group', 'Capitol',
            'Virgin Records', 'Virgin EMI', 'Virgin Music',
            'Polydor Records', 'Polydor',
            'Motown Records', 'Motown',
            'Mercury Records', 'Mercury',
            'Verve Records', 'Verve', 'Verve Label Group',
            'Decca Records', 'Decca', 'Deutsche Grammophon',
            'ECM Records', 'ECM',
            'Blue Note Records', 'Blue Note',
            'Harvest Records', 'Harvest',
            'Caroline Records', 'Caroline', 'Caroline International',
            
            # Regional UMG Labels
            'Universal Music Deutschland', 'Universal Music Germany',
            'Universal Music France', 'Universal Music UK',
            'Universal Music Japan', 'Universal Music Australia',
            'Universal Music Latin', 'Universal Music Latino',
            
            # Publishing
            'Universal Music Publishing Group', 'UMPG',
            'Universal Music Publishing',
            
            # Historical/Merged Labels now under UMG
            'PolyGram', 'Polygram Records',
            'MCA Records', 'MCA',
            'GRP Records', 'GRP',
            'Fontana Records', 'Fontana',
            'Philips Records', 'Philips',
            'London Records', 'London',
            'Casablanca Records', 'Casablanca',
            'RSO Records', 'RSO',
            'Rocket Records',
            
            # Dance/Electronic Labels under UMG
            'Big Beat Records', 'Big Beat',
            'Astralwerks', 'Astral Werks',
            'Spinnin Records', 'Spinnin',
            
            # Hip-Hop/R&B Labels under UMG
            'Cash Money Records', 'Cash Money', 'Young Money',
            'Bad Boy Records', 'Bad Boy',
            'Aftermath Entertainment', 'Aftermath',
            'Shady Records',
            'Top Dawg Entertainment', 'TDE',
            'Quality Control Music', 'Quality Control', 'QC',
            'Roc Nation', 'Roc-A-Fella',
            
            # Country Labels under UMG
            'MCA Nashville', 'Mercury Nashville',
            'Capitol Nashville', 'EMI Nashville',
            'Lost Highway Records',
            
            # Rock/Metal Labels under UMG
            'Roadrunner Records', 'Roadrunner',
            'Spinefarm Records', 'Spinefarm',
            'Nuclear Blast', # Distribution deal
            
            # Classical Labels under UMG
            'DG', 'Archiv Produktion',
        }
        
        # Create normalized lookup
        normalized = {}
        for label in umg_labels:
            norm = label.lower().strip()
            normalized[norm] = label
            # Also add without special characters
            norm_clean = re.sub(r'[^\w\s]', '', norm)
            if norm_clean != norm:
                normalized[norm_clean] = label
        
        return normalized
    
    def check_umg_label(self, text):
        """Check if text contains any UMG label reference
        
        Args:
            text: Text to check (could be description, channel name, etc.)
            
        Returns:
            tuple: (is_umg, matched_labels) where is_umg is bool and matched_labels is list
        """
        if not text or not text.strip():
            return False, []
        
        text_lower = text.lower().strip()
        text_clean = re.sub(r'[^\w\s]', '', text_lower)
        
        matched = []
        for label_norm, label_orig in self.umg_labels.items():
            # Check if label appears in text
            if label_norm in text_lower or label_norm in text_clean:
                if label_orig not in matched:
                    matched.append(label_orig)
        
        return len(matched) > 0, matched
    
    def check_umpg_artist(self, artist_name):
        """Check if an artist is represented by UMPG
        
        Args:
            artist_name: Name of the artist to check
            
        Returns:
            tuple: (is_umpg, match_info) where is_umpg is bool and match_info is str
        """
        if not artist_name or not artist_name.strip():
            return False, ''
        
        artist_lower = artist_name.lower().strip()
        artist_clean = re.sub(r'[^\w\s]', '', artist_lower)
        
        # Direct match
        if artist_lower in self.umpg_artists:
            return True, self.umpg_artists[artist_lower]
        
        # Clean match (without special characters)
        if artist_clean in self.umpg_artists:
            return True, self.umpg_artists[artist_clean]
        
        # Partial match (check if artist name contains or is contained in UMPG artist)
        for ump_artist_norm, ump_artist_orig in self.umpg_artists.items():
            ump_artist_clean = re.sub(r'[^\w\s]', '', ump_artist_norm)
            
            # Check if artist name is contained in UMPG artist name
            if artist_lower in ump_artist_norm or artist_clean in ump_artist_clean:
                return True, ump_artist_orig
            
            # Check if UMPG artist name is contained in artist name
            if ump_artist_norm in artist_lower or ump_artist_clean in artist_clean:
                return True, ump_artist_orig
        
        return False, ''
    
    def check_song(self):
        """Check a single song"""
        song_title = self.song_title_var.get().strip()
        artist = self.artist_var.get().strip()
        
        if not song_title:
            messagebox.showwarning("Warning", "Please enter a song title")
            return
        
        if self.is_analyzing:
            messagebox.showwarning("Warning", "Analysis already in progress")
            return
        
        # Start analysis in thread
        thread = threading.Thread(target=self.analyze_song, args=(song_title, artist), daemon=True)
        thread.start()
    
    def load_csv(self):
        """Load songs from CSV file via file dialog"""
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.join(self.root_dir, 'input')
        )
        
        if not file_path:
            return
        
        self._process_csv_file(file_path)
    
    def load_csv_from_input(self):
        """Load CSV file from input folder"""
        input_dir = os.path.join(self.root_dir, 'input')
        
        if not os.path.exists(input_dir):
            messagebox.showerror("Error", f"Input directory not found: {input_dir}")
            return
        
        # Get list of CSV files
        csv_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.csv')]
        
        if not csv_files:
            messagebox.showwarning("Warning", f"No CSV files found in {input_dir}")
            return
        
        # If only one file, use it directly
        if len(csv_files) == 1:
            file_path = os.path.join(input_dir, csv_files[0])
            self.log(f"Loading CSV from input folder: {csv_files[0]}")
            self._process_csv_file(file_path)
            return
        
        # Multiple files - show selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select CSV File from Input Folder")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Select a CSV file to load:", 
                 font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        
        # Listbox for files
        listbox_frame = ttk.Frame(main_frame)
        listbox_frame.pack(fill='both', expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side='right', fill='y')
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, font=('TkDefaultFont', 9))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Populate listbox
        for csv_file in sorted(csv_files):
            listbox.insert(tk.END, csv_file)
        
        listbox.selection_set(0)  # Select first item
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        def load_selected():
            selection = listbox.curselection()
            if selection:
                selected_file = csv_files[selection[0]]
                file_path = os.path.join(input_dir, selected_file)
                dialog.destroy()
                self.log(f"Loading CSV from input folder: {selected_file}")
                self._process_csv_file(file_path)
        
        ttk.Button(btn_frame, text="Load Selected", command=load_selected).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)
        
        # Double-click to load
        def on_double_click(event):
            load_selected()
        
        listbox.bind('<Double-1>', on_double_click)
    
    def _process_csv_file(self, file_path):
        """Process a CSV file and extract songs"""
        try:
            self.log(f"Loading CSV file: {os.path.basename(file_path)}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                songs = []
                skipped_rows = 0
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    # Try different column name variations
                    song_title = (row.get('Song Title') or row.get('song_title') or 
                                row.get('Title') or row.get('title') or 
                                row.get('Song') or row.get('song') or '').strip()
                    
                    artist = (row.get('Artist') or row.get('artist') or 
                            row.get('Artist(s)') or row.get('Artists') or 
                            row.get('artist(s)') or '').strip()
                    
                    # Skip rows with N/A or empty song titles
                    if not song_title or song_title.upper() == 'N/A':
                        skipped_rows += 1
                        continue
                    
                    # Clean up song title (remove quotes if present)
                    song_title = song_title.strip('"\'')
                    artist = artist.strip('"\'')
                    
                    songs.append((song_title, artist))
                
                if not songs:
                    messagebox.showwarning("Warning", 
                        f"No valid songs found in CSV file.\n"
                        f"Skipped {skipped_rows} empty/invalid rows.")
                    return
                
                # Log summary
                self.log(f"Loaded {len(songs)} songs from CSV")
                if skipped_rows > 0:
                    self.log(f"Skipped {skipped_rows} invalid/empty rows")
                
                # Show preview
                preview_text = f"Found {len(songs)} songs in CSV file:\n\n"
                for i, (title, artist) in enumerate(songs[:5], 1):
                    preview_text += f"{i}. {title}"
                    if artist:
                        preview_text += f" - {artist}"
                    preview_text += "\n"
                if len(songs) > 5:
                    preview_text += f"... and {len(songs) - 5} more\n"
                
                preview_text += "\nStart analysis?"
                
                # Ask for confirmation
                if messagebox.askyesno("Confirm", preview_text):
                    self.log(f"Starting analysis for {len(songs)} songs")
                    thread = threading.Thread(target=self.analyze_multiple_songs, args=(songs,), daemon=True)
                    thread.start()
        
        except FileNotFoundError:
            messagebox.showerror("Error", f"File not found: {file_path}")
        except Exception as e:
            error_msg = f"Failed to load CSV: {str(e)}"
            self.log(f"Error: {error_msg}")
            messagebox.showerror("Error", error_msg)
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
    
    def select_from_ai_covers(self):
        """Open dialog to select individual songs from AI-COVERS directory"""
        ai_covers_path = self.get_ai_covers_path()
        
        if not os.path.exists(ai_covers_path):
            messagebox.showerror("Error", f"AI-COVERS directory not found: {ai_covers_path}")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Songs from AI-COVERS")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Instructions
        ttk.Label(main_frame, text="Select songs to analyze (use Ctrl/Cmd to select multiple):", 
                 font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        
        # Tree view for songs
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=5)
        
        scroll_y = ttk.Scrollbar(tree_frame, orient='vertical')
        scroll_x = ttk.Scrollbar(tree_frame, orient='horizontal')
        
        songs_tree = ttk.Treeview(tree_frame, columns=('Song', 'Artist', 'Decade'), 
                                 show='tree headings', yscrollcommand=scroll_y.set, 
                                 xscrollcommand=scroll_x.set, selectmode='extended')
        
        scroll_y.config(command=songs_tree.yview)
        scroll_x.config(command=songs_tree.xview)
        
        # Column headers
        songs_tree.heading('#0', text='AI Cover Name')
        songs_tree.heading('Song', text='Song Name')
        songs_tree.heading('Artist', text='Artist')
        songs_tree.heading('Decade', text='Decade')
        
        # Column widths
        songs_tree.column('#0', width=300)
        songs_tree.column('Song', width=200)
        songs_tree.column('Artist', width=200)
        songs_tree.column('Decade', width=80)
        
        songs_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Store song data
        song_data_map = {}
        
        # Scan and populate tree
        self.log("Scanning AI-COVERS directory for song selection...")
        try:
            # Iterate through decade directories
            for decade_dir in sorted(os.listdir(ai_covers_path)):
                decade_path = os.path.join(ai_covers_path, decade_dir)
                if not os.path.isdir(decade_path):
                    continue
                
                # Create decade node
                decade_node = songs_tree.insert('', 'end', text=decade_dir, 
                                               values=('', '', decade_dir), tags=('decade',))
                
                # Iterate through song directories
                for song_dir in sorted(os.listdir(decade_path)):
                    song_path = os.path.join(decade_path, song_dir)
                    if not os.path.isdir(song_path):
                        continue
                    
                    # Look for JSON file
                    json_files = [f for f in os.listdir(song_path) 
                                 if f.endswith('.json') and not f.startswith('grok_')]
                    if not json_files:
                        continue
                    
                    # Load JSON
                    json_path = os.path.join(song_path, json_files[0])
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            song_data = json.load(f)
                        
                        song_name = song_data.get('song_name', '').strip()
                        artist = song_data.get('artist', '').strip()
                        ai_cover_name = song_data.get('ai_cover_name', song_dir)
                        
                        if song_name:
                            # Create song node
                            item_id = songs_tree.insert(decade_node, 'end', 
                                                       text=ai_cover_name[:60],  # Truncate long names
                                                       values=(song_name, artist, decade_dir),
                                                       tags=('song',))
                            
                            # Store song data
                            song_data_map[item_id] = {
                                'song_name': song_name,
                                'artist': artist,
                                'decade': decade_dir,
                                'json_path': json_path
                            }
                    except Exception:
                        continue
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan AI-COVERS: {str(e)}")
            dialog.destroy()
            return
        
        # Tag colors
        songs_tree.tag_configure('decade', font=('TkDefaultFont', 9, 'bold'))
        songs_tree.tag_configure('song', font=('TkDefaultFont', 8))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        def select_all():
            """Select all songs"""
            for item in songs_tree.get_children():
                songs_tree.selection_add(item)
                # Also select children
                for child in songs_tree.get_children(item):
                    songs_tree.selection_add(child)
        
        def deselect_all():
            """Deselect all"""
            songs_tree.selection_remove(songs_tree.selection())
        
        def analyze_selected():
            """Analyze selected songs"""
            selected_items = songs_tree.selection()
            if not selected_items:
                messagebox.showwarning("Warning", "Please select at least one song")
                return
            
            # Get song data for selected items
            songs_to_analyze = []
            for item_id in selected_items:
                if item_id in song_data_map:
                    song_info = song_data_map[item_id]
                    songs_to_analyze.append((song_info['song_name'], song_info['artist']))
            
            if not songs_to_analyze:
                messagebox.showwarning("Warning", "No valid songs selected")
                return
            
            dialog.destroy()
            
            # Start analysis
            self.log(f"Starting analysis for {len(songs_to_analyze)} selected songs")
            thread = threading.Thread(target=self.analyze_multiple_songs, args=(songs_to_analyze,), daemon=True)
            thread.start()
        
        ttk.Button(btn_frame, text="Select All", command=select_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Deselect All", command=deselect_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Analyze Selected", command=analyze_selected).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)
        
        # Status label
        status_label = ttk.Label(main_frame, text=f"Found songs in tree - select and click 'Analyze Selected'")
        status_label.pack(pady=(5, 0))
        
        # Update status when selection changes
        def update_status(event=None):
            selected = len(songs_tree.selection())
            status_label.config(text=f"{selected} song(s) selected")
        
        songs_tree.bind('<<TreeviewSelect>>', update_status)
    
    def scan_ai_covers(self):
        """Scan AI/AI-COVERS directory for all songs and analyze them"""
        ai_covers_path = self.get_ai_covers_path()
        
        if not os.path.exists(ai_covers_path):
            messagebox.showerror("Error", f"AI-COVERS directory not found: {ai_covers_path}")
            return
        
        self.log(f"Scanning AI-COVERS directory: {ai_covers_path}")
        
        # Scan for JSON files
        songs = []
        decades_found = []
        
        try:
            # Iterate through decade directories
            for decade_dir in os.listdir(ai_covers_path):
                decade_path = os.path.join(ai_covers_path, decade_dir)
                if not os.path.isdir(decade_path):
                    continue
                
                decades_found.append(decade_dir)
                
                # Iterate through song directories
                for song_dir in os.listdir(decade_path):
                    song_path = os.path.join(decade_path, song_dir)
                    if not os.path.isdir(song_path):
                        continue
                    
                    # Look for JSON file in this directory
                    json_files = [f for f in os.listdir(song_path) 
                                 if f.endswith('.json') and not f.startswith('grok_')]
                    if not json_files:
                        continue
                    
                    # Try to load the first JSON file found
                    json_path = os.path.join(song_path, json_files[0])
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            song_data = json.load(f)
                        
                        song_name = song_data.get('song_name', '').strip()
                        artist = song_data.get('artist', '').strip()
                        
                        if song_name:
                            songs.append((song_name, artist))
                            self.log(f"Found: {song_name} - {artist} ({decade_dir})")
                    except Exception as e:
                        self.log(f"Error loading {json_path}: {str(e)}")
                        continue
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan AI-COVERS directory: {str(e)}")
            return
        
        if not songs:
            messagebox.showwarning("Warning", "No songs found in AI-COVERS directory")
            return
        
        # Show summary and ask for confirmation
        summary = f"Found {len(songs)} songs in {len(decades_found)} decades:\n"
        summary += f"Decades: {', '.join(sorted(decades_found))}\n\n"
        summary += f"Start batch analysis?"
        
        if messagebox.askyesno("Confirm Batch Analysis", summary):
            self.log(f"Starting batch analysis for {len(songs)} songs from AI-COVERS")
            thread = threading.Thread(target=self.analyze_multiple_songs, args=(songs,), daemon=True)
            thread.start()
    
    def analyze_multiple_songs(self, songs):
        """Analyze multiple songs from CSV"""
        self.is_analyzing = True
        self.progress_bar.start()
        self.progress_var.set(f"Analyzing {len(songs)} songs...")
        
        try:
            for i, (song_title, artist) in enumerate(songs):
                self.progress_var.set(f"Analyzing {i+1}/{len(songs)}: {song_title}")
                self.analyze_song(song_title, artist, show_progress=False)
                time.sleep(1)  # Rate limiting
        
        finally:
            self.is_analyzing = False
            self.progress_bar.stop()
            self.progress_var.set("Analysis complete")
            messagebox.showinfo("Complete", f"Analyzed {len(songs)} songs")
    
    def analyze_song(self, song_title, artist="", show_progress=True):
        """Analyze a single song"""
        if show_progress:
            self.is_analyzing = True
            self.progress_bar.start()
            self.progress_var.set(f"Analyzing: {song_title}")
        
        try:
            self.log(f"Starting analysis for: {song_title} - {artist}")
            
            # Search for cover videos
            search_query = f"{song_title} {artist} cover".strip()
            covers = self.search_youtube_covers(search_query)
            
            if not covers:
                self.log(f"No cover videos found for: {song_title}")
                # Check UMPG representation even if no covers found
                is_umpg, ump_artist_match = self.check_umpg_artist(artist)
                if is_umpg:
                    self.log(f"UMPG WARNING: Artist '{artist}' is represented by UMPG (matched: {ump_artist_match})")
                
                result = {
                    'song_title': song_title,
                    'artist': artist,
                    'cover_count': 0,
                    'claims_count': 0,
                    'strikes_count': 0,
                    'claims_percent': 0,
                    'strikes_percent': 0,
                    'oldest_age': 'N/A',
                    'avg_views': 0,
                    'is_umpg': is_umpg,
                    'ump_artist_match': ump_artist_match,
                    'risk_level': 'ROT',
                    'recommendation': 'RISKY - No cover history found',
                    'covers': [],  # Store empty list
                    'analysis': {'oldest_age': 'N/A', 'avg_views': 0}
                }
                self.add_result(result)
                return
            
            self.log(f"Found {len(covers)} cover videos")
            
            # Show found covers
            if covers:
                self.log("Cover videos found:")
                for i, cover in enumerate(covers[:10], 1):  # Show first 10
                    title = cover.get('title', 'Unknown')[:60]  # Truncate long titles
                    url = cover.get('url', '')
                    self.log(f"  {i}. {title}")
                    self.log(f"     URL: {url}")
                if len(covers) > 10:
                    self.log(f"  ... and {len(covers) - 10} more")
            
            # Analyze covers
            analysis = self.analyze_covers(covers)
            
            # Log analysis details
            self.log("Analysis results:")
            self.log(f"  Total covers found: {len(covers)}")
            self.log(f"  Oldest cover age: {analysis['oldest_age']}")
            self.log(f"  Average views: {analysis['avg_views']:,}")
            self.log(f"  Claims detected: {analysis['claims_count']} ({analysis['claims_percent']:.1f}%)")
            self.log(f"  Strikes detected: {analysis['strikes_count']} ({analysis['strikes_percent']:.1f}%)")
            
            # Check UMPG representation
            is_umpg, ump_artist_match = self.check_umpg_artist(artist)
            if is_umpg:
                self.log(f"UMPG WARNING: Artist '{artist}' is represented by UMPG (matched: {ump_artist_match})")
            
            # Calculate risk level
            risk_level, recommendation = self.calculate_risk(analysis, song_title, artist, is_umpg)
            
            result = {
                'song_title': song_title,
                'artist': artist,
                'cover_count': len(covers),
                'claims_count': analysis['claims_count'],
                'strikes_count': analysis['strikes_count'],
                'claims_percent': analysis['claims_percent'],
                'strikes_percent': analysis['strikes_percent'],
                'oldest_age': analysis['oldest_age'],
                'avg_views': analysis['avg_views'],
                'is_umpg': is_umpg,
                'ump_artist_match': ump_artist_match,
                'risk_level': risk_level,
                'recommendation': recommendation,
                'covers': covers,  # Store cover videos for detail view
                'analysis': analysis  # Store analysis data
            }
            
            # Debug: Verify covers are stored
            self.log(f"[DEBUG] Storing {len(covers)} covers in result")
            if covers:
                self.log(f"[DEBUG] First cover in result: {covers[0].get('title', 'No title')}")
            
            self.add_result(result)
            self.log(f"Risk Assessment: {risk_level} - {recommendation}")
            self.log("=" * 60)
        
        except Exception as e:
            self.log(f"Error analyzing song: {str(e)}")
            messagebox.showerror("Error", f"Failed to analyze song: {str(e)}")
        
        finally:
            if show_progress:
                self.is_analyzing = False
                self.progress_bar.stop()
                self.progress_var.set("Ready")
    
    def search_youtube_covers(self, query, max_results=20):
        """Search YouTube for cover videos using yt-dlp"""
        covers = []
        
        try:
            self.log(f"Searching YouTube for: '{query}'")
            
            # Use yt-dlp to search - only metadata, no downloads
            ydl_opts = {
                'quiet': True,
                'no_warnings': False,  # Keep warnings for debugging, but quiet=True should suppress most
                'extract_flat': True,  # Only extract metadata, don't process video
                'skip_download': True,  # Explicitly skip download
                'noplaylist': True,  # Don't process playlists
                'default_search': 'ytsearch',
                'ignoreerrors': True,
            }
            
            # Add ffmpeg path if available (yt-dlp needs directory containing ffmpeg executable)
            if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
                ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                if os.path.exists(ffmpeg_dir) and os.path.exists(self.ffmpeg_path):
                    # yt-dlp expects the directory containing ffmpeg, not the executable path
                    ydl_opts['ffmpeg_location'] = ffmpeg_dir
                    self.log(f"Configuring yt-dlp to use FFmpeg from: {ffmpeg_dir}")
                else:
                    self.log(f"Warning: FFmpeg directory or executable not found")
                    self.log(f"  Directory: {ffmpeg_dir} (exists: {os.path.exists(ffmpeg_dir)})")
                    self.log(f"  Executable: {self.ffmpeg_path} (exists: {os.path.exists(self.ffmpeg_path)})")
            else:
                self.log("FFmpeg not in local directory, yt-dlp will use system PATH (if available)")
            
            import yt_dlp
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Search for covers
                search_url = f"ytsearch{max_results}:{query}"
                self.log(f"Search URL: {search_url}")
                info = ydl.extract_info(search_url, download=False)
                
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            video_id = entry.get('id', '')
                            title = entry.get('title', 'Unknown')
                            url = entry.get('url', f"https://www.youtube.com/watch?v={video_id}")
                            
                            covers.append({
                                'id': video_id,
                                'title': title,
                                'url': url,
                                'duration': entry.get('duration', 0),
                                'view_count': entry.get('view_count', 0),
                                'upload_date': entry.get('upload_date', ''),
                            })
            
            if covers:
                self.log(f"Successfully found {len(covers)} cover videos")
            else:
                self.log("No cover videos found in search results")
        
        except Exception as e:
            self.log(f"Error searching YouTube: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        return covers[:max_results]
    
    def analyze_covers(self, covers):
        """Analyze cover videos for claims and strikes
        
        NOTE: yt-dlp cannot directly detect Content ID claims or strikes.
        We can only analyze what's visible (video exists, views, age).
        For actual claim/strike detection, YouTube Data API v3 would be needed.
        This tool provides risk assessment based on cover video history.
        """
        claims_count = 0
        strikes_count = 0
        total_views = 0
        oldest_date = None
        videos_with_views = 0
        
        # Note: yt-dlp cannot directly detect Content ID claims or strikes
        # We can only analyze what's visible (video exists, views, age)
        # For actual claim detection, we'd need YouTube Data API v3
        
        self.log(f"Analyzing {len(covers)} cover videos...")
        
        for i, cover in enumerate(covers, 1):
            try:
                # Try to get more info about the video
                video_id = cover.get('id', '')
                title = cover.get('title', 'Unknown')[:50]
                
                if not video_id:
                    continue
                
                # Try to get detailed info (this might fail for some videos)
                # NOTE: We use extract_flat=True to avoid downloading anything, only get metadata
                try:
                    import yt_dlp
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': False,  # Keep warnings for debugging
                        'extract_flat': True,  # Only extract metadata, don't process video
                        'skip_download': True,  # Explicitly skip download
                        'noplaylist': True,  # Don't process playlists
                    }
                    
                    # Add ffmpeg path if available (yt-dlp needs directory, not executable path)
                    if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
                        ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                        if os.path.exists(ffmpeg_dir):
                            ydl_opts['ffmpeg_location'] = ffmpeg_dir
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_info = ydl.extract_info(video_url, download=False)
                        
                        if video_info:
                            views = video_info.get('view_count', 0) or 0
                            total_views += views
                            if views > 0:
                                videos_with_views += 1
                            
                            # Update cover with detailed info
                            cover['view_count'] = views
                            cover['duration'] = video_info.get('duration', cover.get('duration', 0))
                            cover['upload_date'] = video_info.get('upload_date', cover.get('upload_date', ''))
                            
                            # Get upload date
                            upload_date = cover.get('upload_date', '')
                            if upload_date:
                                try:
                                    date_obj = datetime.strptime(upload_date, '%Y%m%d')
                                    if oldest_date is None or date_obj < oldest_date:
                                        oldest_date = date_obj
                                except:
                                    pass
                            
                            # Log video details
                            if i <= 5:  # Log first 5 in detail
                                self.log(f"  Video {i}: {title}")
                                self.log(f"    Views: {views:,}, Upload: {upload_date or 'Unknown'}")
                
                except Exception as e:
                    # If detailed extraction fails, use basic info from cover
                    views = cover.get('view_count', 0) or 0
                    total_views += views
                    if views > 0:
                        videos_with_views += 1
                    
                    upload_date = cover.get('upload_date', '')
                    if upload_date:
                        try:
                            date_obj = datetime.strptime(upload_date, '%Y%m%d')
                            if oldest_date is None or date_obj < oldest_date:
                                oldest_date = date_obj
                        except:
                            pass
                    
                    # Ensure cover has at least basic fields
                    if 'view_count' not in cover:
                        cover['view_count'] = 0
                    if 'duration' not in cover:
                        cover['duration'] = 0
                    if 'upload_date' not in cover:
                        cover['upload_date'] = ''
            
            except Exception as e:
                self.log(f"Error analyzing cover {cover.get('id', 'unknown')}: {str(e)}")
                continue
        
        # Calculate statistics
        cover_count = len(covers)
        avg_views = total_views / videos_with_views if videos_with_views > 0 else 0
        
        # Calculate age
        if oldest_date:
            age_delta = datetime.now() - oldest_date
            if age_delta.days > 365:
                oldest_age = f"{age_delta.days // 365} years"
            elif age_delta.days > 30:
                oldest_age = f"{age_delta.days // 30} months"
            else:
                oldest_age = f"{age_delta.days} days"
        else:
            oldest_age = "Unknown"
        
        # Note: We cannot detect actual claims/strikes without YouTube Data API v3
        # These are placeholders - in real implementation, you'd need API access
        # The risk assessment is based on cover count and age, not actual claims/strikes
        claims_percent = 0  # Would need YouTube Data API v3 to detect
        strikes_percent = 0  # Would need YouTube Data API v3 to detect
        
        # Ensure all covers have required fields
        for cover in covers:
            if 'view_count' not in cover:
                cover['view_count'] = 0
            if 'duration' not in cover:
                cover['duration'] = 0
            if 'upload_date' not in cover:
                cover['upload_date'] = ''
            if 'url' not in cover and 'id' in cover:
                cover['url'] = f"https://www.youtube.com/watch?v={cover['id']}"
        
        return {
            'cover_count': cover_count,
            'claims_count': claims_count,
            'strikes_count': strikes_count,
            'claims_percent': claims_percent,
            'strikes_percent': strikes_percent,
            'oldest_age': oldest_age,
            'avg_views': int(avg_views),
            'oldest_date': oldest_date
        }
    
    def calculate_risk(self, analysis, song_title, artist, is_umpg=False):
        """Calculate risk level and recommendation
        
        Args:
            analysis: Analysis data dictionary
            song_title: Song title
            artist: Artist name
            is_umpg: Whether artist is represented by UMPG (increases risk)
        """
        cover_count = analysis['cover_count']
        oldest_date = analysis['oldest_date']
        avg_views = analysis['avg_views']
        
        # Known problematic publishers
        problematic_publishers = ['Universal', 'Sony', 'Warner', 'EMI']
        is_problematic = any(pub.lower() in (song_title + ' ' + artist).lower() for pub in problematic_publishers)
        
        # UMPG representation significantly increases risk (they distribute copyright strikes)
        ump_risk_note = ''
        if is_umpg:
            ump_risk_note = ' - UMPG represented (high strike risk)'
        
        # Risk calculation
        if cover_count == 0:
            risk_level = 'ROT'
            if is_umpg:
                recommendation = f'RISKY - No cover history found{ump_risk_note}'
            else:
                recommendation = 'RISKY - No cover history found'
        
        elif cover_count < 3:
            risk_level = 'ROT'
            if is_umpg:
                recommendation = f'RISKY - Very few covers exist{ump_risk_note}'
            else:
                recommendation = 'RISKY - Very few covers exist'
        
        elif is_umpg:
            # UMPG artists are always high risk, regardless of cover count
            risk_level = 'ROT'
            recommendation = f'RISKY - UMPG represented artist{ump_risk_note}'
        
        elif is_problematic:
            risk_level = 'ROT'
            recommendation = 'RISKY - Known problematic publisher/artist'
        
        elif cover_count >= 20:
            if oldest_date and (datetime.now() - oldest_date).days > 180:
                risk_level = 'GRUEN'
                recommendation = 'SAFE - Many covers exist for months/years'
            else:
                risk_level = 'GELB'
                recommendation = 'CAUTION - Many covers but recent'
        
        elif cover_count >= 10:
            if oldest_date and (datetime.now() - oldest_date).days > 90:
                risk_level = 'GELB'
                recommendation = 'CAUTION - Moderate cover history'
            else:
                risk_level = 'ROT'
                recommendation = 'RISKY - Covers are too recent'
        
        else:
            risk_level = 'GELB'
            recommendation = 'CAUTION - Limited cover history, check manually'
        
        return risk_level, recommendation
    
    def add_result(self, result):
        """Add result to tree view"""
        result_index = len(self.results)
        self.results.append(result)
        
        # Format UMPG status
        ump_status = 'YES' if result.get('is_umpg', False) else 'NO'
        if result.get('is_umpg', False) and result.get('ump_artist_match'):
            ump_status = 'YES*'  # Indicate match found
        
        # Add to tree
        item = self.results_tree.insert('', 'end', values=(
            result['song_title'],
            result['artist'],
            result['cover_count'],
            f"{result['claims_percent']:.1f}%",
            f"{result['strikes_percent']:.1f}%",
            result['oldest_age'],
            f"{result['avg_views']:,}",
            ump_status,
            result['risk_level'],
            result['recommendation']
        ), tags=(str(result_index),))
        
        # Color code by risk level
        if result['risk_level'] == 'GRUEN':
            self.results_tree.set(item, 'Risk Level', 'GRUEN')
        elif result['risk_level'] == 'GELB':
            self.results_tree.set(item, 'Risk Level', 'GELB')
        elif result['risk_level'] == 'ROT':
            self.results_tree.set(item, 'Risk Level', 'ROT')
        
        # Highlight UMPG status
        if result.get('is_umpg', False):
            self.results_tree.set(item, 'UMPG', 'YES*')
            # Tag for styling if needed
            current_tags = list(self.results_tree.item(item, 'tags'))
            if 'umpg' not in current_tags:
                current_tags.append('umpg')
                self.results_tree.item(item, tags=current_tags)
    
    def on_result_double_click(self, event):
        """Handle double-click on result to show details"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.results_tree.item(item, 'tags')
        if not tags:
            return
        
        try:
            result_index = int(tags[0])
            if 0 <= result_index < len(self.results):
                result = self.results[result_index]
                self.show_result_details(result)
        except (ValueError, IndexError):
            pass
    
    def on_result_right_click(self, event):
        """Handle right-click on result to show context menu"""
        item = self.results_tree.identify_row(event.y)
        if not item:
            return
        
        # Select the item
        self.results_tree.selection_set(item)
        
        # Get result data
        tags = self.results_tree.item(item, 'tags')
        if not tags:
            return
        
        try:
            result_index = int(tags[0])
            if 0 <= result_index < len(self.results):
                result = self.results[result_index]
                
                # Create context menu
                context_menu = tk.Menu(self.root, tearoff=0)
                
                # Get values from tree
                values = self.results_tree.item(item, 'values')
                song_title = values[0] if len(values) > 0 else result.get('song_title', '')
                artist = values[1] if len(values) > 1 else result.get('artist', '')
                
                # Add copy options
                if song_title:
                    context_menu.add_command(
                        label=f"Copy Song Title: {song_title[:40]}",
                        command=lambda: self.copy_to_clipboard(song_title)
                    )
                
                if artist:
                    context_menu.add_command(
                        label=f"Copy Artist: {artist[:40]}",
                        command=lambda: self.copy_to_clipboard(artist)
                    )
                
                if song_title and artist:
                    context_menu.add_command(
                        label=f"Copy: {song_title} - {artist}",
                        command=lambda: self.copy_to_clipboard(f"{song_title} - {artist}")
                    )
                
                context_menu.add_separator()
                context_menu.add_command(
                    label="View Details",
                    command=lambda: self.show_result_details(result)
                )
                
                # Show menu at cursor position
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
        
        except (ValueError, IndexError):
            pass
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.log(f"Copied to clipboard: {text[:50]}")
        except Exception as e:
            self.log(f"Failed to copy to clipboard: {str(e)}")
    
    def show_result_details(self, result):
        """Show detailed window with cover videos"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Details: {result['song_title']} - {result['artist']}")
        detail_window.geometry("1000x700")
        
        # Main frame
        main_frame = ttk.Frame(detail_window, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Summary info
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
        summary_frame.pack(fill='x', pady=(0, 10))
        
        ump_info = ''
        if result.get('is_umpg', False):
            match_info = result.get('ump_artist_match', '')
            ump_info = f"\nUMPG Representation: YES (matched: {match_info})"
            ump_info += "\nWARNING: UMPG distributes copyright strikes - HIGH RISK"
        else:
            ump_info = "\nUMPG Representation: NO"
        
        info_text = f"""
Song: {result['song_title']}
Artist: {result['artist']}
Cover Count: {result['cover_count']}
Risk Level: {result['risk_level']}
Recommendation: {result['recommendation']}
Oldest Cover Age: {result['oldest_age']}
Average Views: {result['avg_views']:,}{ump_info}
        """.strip()
        
        ttk.Label(summary_frame, text=info_text, justify='left', font=('TkDefaultFont', 9)).pack(anchor='w')
        
        # Cover videos list
        videos_frame = ttk.LabelFrame(main_frame, text=f"Cover Videos ({result['cover_count']})", padding=10)
        videos_frame.pack(fill='both', expand=True)
        
        # Tree view for videos
        tree_container = ttk.Frame(videos_frame)
        tree_container.pack(fill='both', expand=True)
        
        scroll_y = ttk.Scrollbar(tree_container, orient='vertical')
        scroll_x = ttk.Scrollbar(tree_container, orient='horizontal')
        
        videos_tree = ttk.Treeview(tree_container, columns=(
            'Title', 'URL', 'Views', 'Duration', 'Upload Date'
        ), show='headings', yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=videos_tree.yview)
        scroll_x.config(command=videos_tree.xview)
        
        # Column headers
        videos_tree.heading('Title', text='Title')
        videos_tree.heading('URL', text='URL')
        videos_tree.heading('Views', text='Views')
        videos_tree.heading('Duration', text='Duration')
        videos_tree.heading('Upload Date', text='Upload Date')
        
        # Column widths
        videos_tree.column('Title', width=300)
        videos_tree.column('URL', width=400)
        videos_tree.column('Views', width=100)
        videos_tree.column('Duration', width=100)
        videos_tree.column('Upload Date', width=100)
        
        videos_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Populate videos
        covers = result.get('covers', [])
        
        # Debug: Log to main window
        self.log(f"[DEBUG] Detail window opened for: {result.get('song_title', 'Unknown')}")
        self.log(f"[DEBUG] Found {len(covers)} covers in result")
        self.log(f"[DEBUG] Cover count field: {result.get('cover_count', 'N/A')}")
        
        if covers and len(covers) > 0:
            self.log(f"[DEBUG] Processing {len(covers)} covers for display")
            for i, cover in enumerate(covers):
                title = cover.get('title', 'Unknown')
                url = cover.get('url', '')
                views = cover.get('view_count', 0) or 0
                duration = cover.get('duration', 0)
                upload_date = cover.get('upload_date', '')
                
                # Debug first cover
                if i == 0:
                    self.log(f"[DEBUG] First cover: title={title[:50]}, url={url[:50]}, views={views}")
                
                # Format duration
                if duration and duration > 0:
                    minutes = int(duration) // 60
                    seconds = int(duration) % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "Unknown"
                
                # Format upload date
                if upload_date:
                    try:
                        # Try different date formats
                        if len(upload_date) == 8:  # YYYYMMDD
                            date_obj = datetime.strptime(upload_date, '%Y%m%d')
                            upload_date_str = date_obj.strftime('%Y-%m-%d')
                        else:
                            upload_date_str = upload_date
                    except:
                        upload_date_str = upload_date
                else:
                    upload_date_str = "Unknown"
                
                # Ensure URL is set
                if not url and cover.get('id'):
                    url = f"https://www.youtube.com/watch?v={cover.get('id')}"
                
                videos_tree.insert('', 'end', values=(
                    title[:80] if title else "Unknown",  # Truncate long titles
                    url,
                    f"{views:,}" if views else "Unknown",
                    duration_str,
                    upload_date_str
                ))
            
            self.log(f"[DEBUG] Successfully added {len(covers)} videos to tree")
        else:
            videos_tree.insert('', 'end', values=("No videos found", "", "", "", ""))
            self.log(f"[DEBUG] No covers in result. Result keys: {list(result.keys())}")
            self.log(f"[DEBUG] Cover count in result: {result.get('cover_count', 'N/A')}")
            self.log(f"[DEBUG] Covers type: {type(covers)}, Length: {len(covers) if covers else 0}")
            if covers is None:
                self.log(f"[DEBUG] Covers is None!")
            elif isinstance(covers, list) and len(covers) == 0:
                self.log(f"[DEBUG] Covers is an empty list!")
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        def open_selected_video():
            selection = videos_tree.selection()
            if selection:
                item = videos_tree.item(selection[0])
                values = item['values']
                if len(values) > 1 and values[1]:
                    import webbrowser
                    webbrowser.open(values[1])
        
        ttk.Button(btn_frame, text="Open Selected Video in Browser", command=open_selected_video).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=detail_window.destroy).pack(side='right', padx=5)
    
    def clear_results(self):
        """Clear all results"""
        if messagebox.askyesno("Confirm", "Clear all results?"):
            self.results = []
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            self.log_text.delete(1.0, tk.END)
    
    def export_csv(self):
        """Export results to CSV"""
        if not self.results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save Results as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Song Title', 'Artist', 'Cover Count', 'Claims Count', 
                    'Strikes Count', 'Claims %', 'Strikes %', 'Oldest Age', 
                    'Avg Views', 'UMPG', 'UMPG Match', 'Risk Level', 'Recommendation'
                ])
                writer.writeheader()
                
                for result in self.results:
                    ump_status = 'YES' if result.get('is_umpg', False) else 'NO'
                    ump_match = result.get('ump_artist_match', '')
                    
                    writer.writerow({
                        'Song Title': result['song_title'],
                        'Artist': result['artist'],
                        'Cover Count': result['cover_count'],
                        'Claims Count': result['claims_count'],
                        'Strikes Count': result['strikes_count'],
                        'Claims %': f"{result['claims_percent']:.1f}",
                        'Strikes %': f"{result['strikes_percent']:.1f}",
                        'Oldest Age': result['oldest_age'],
                        'Avg Views': result['avg_views'],
                        'UMPG': ump_status,
                        'UMPG Match': ump_match,
                        'Risk Level': result['risk_level'],
                        'Recommendation': result['recommendation']
                    })
            
            messagebox.showinfo("Success", f"Results exported to {file_path}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.root, self.config)
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Update config
            self.config = dialog.result
            save_config(self.config)
            self.log("Settings saved")
            messagebox.showinfo("Settings", "Settings saved successfully")
    
    def open_umg_check_mode(self):
        """Open the Universal Music Group Check Mode dialog
        
        This mode searches more generically for content protected by UMG
        and all its subsidiaries, helping to identify risky songs/artists.
        """
        dialog = UMGCheckModeDialog(self.root, self)
        dialog.wait_window()
    
    def search_umg_protected_content(self, search_type, search_term, max_results=50, progress_callback=None):
        """Search for content that might be protected by Universal Music Group
        
        Args:
            search_type: 'artist', 'song', 'label', or 'generic'
            search_term: Search term to use
            max_results: Maximum results to return
            progress_callback: Optional callback for progress updates
            
        Returns:
            list of dict with video info and UMG detection results
        """
        results = []
        
        try:
            import yt_dlp
            
            # Build search queries based on type
            search_queries = []
            
            if search_type == 'artist':
                search_queries = [
                    f'"{search_term}" official music video',
                    f'"{search_term}" official audio',
                    f'"{search_term}" VEVO',
                    f'"{search_term}" Universal Music',
                ]
            elif search_type == 'song':
                search_queries = [
                    f'"{search_term}" official',
                    f'"{search_term}" music video',
                    f'"{search_term}" audio',
                ]
            elif search_type == 'label':
                search_queries = [
                    f'{search_term} official music video',
                    f'{search_term} records artist',
                ]
            else:  # generic
                search_queries = [
                    f'{search_term} Universal Music',
                    f'{search_term} UMG',
                    f'{search_term} Interscope',
                    f'{search_term} Def Jam',
                    f'{search_term} Republic Records',
                    f'{search_term} Capitol Records',
                ]
            
            # Search each query
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'skip_download': True,
                'noplaylist': False,
                'default_search': 'ytsearch',
                'ignoreerrors': True,
            }
            
            # Add ffmpeg path if available
            if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
                ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                if os.path.exists(ffmpeg_dir):
                    ydl_opts['ffmpeg_location'] = ffmpeg_dir
            
            seen_ids = set()
            total_queries = len(search_queries)
            
            for i, query in enumerate(search_queries):
                if progress_callback:
                    progress_callback(f"Searching: {query[:50]}...", (i + 1) / total_queries * 50)
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        search_url = f"ytsearch{max_results // len(search_queries)}:{query}"
                        info = ydl.extract_info(search_url, download=False)
                        
                        if info and 'entries' in info:
                            for entry in info['entries']:
                                if not entry:
                                    continue
                                
                                video_id = entry.get('id', '')
                                if video_id in seen_ids:
                                    continue
                                seen_ids.add(video_id)
                                
                                title = entry.get('title', 'Unknown')
                                channel = entry.get('channel', entry.get('uploader', ''))
                                description = entry.get('description', '')
                                
                                # Check for UMG indicators
                                umg_detected, umg_labels = self._detect_umg_indicators(
                                    title, channel, description, entry
                                )
                                
                                result = {
                                    'id': video_id,
                                    'title': title,
                                    'url': f"https://www.youtube.com/watch?v={video_id}",
                                    'channel': channel,
                                    'view_count': entry.get('view_count', 0) or 0,
                                    'upload_date': entry.get('upload_date', ''),
                                    'duration': entry.get('duration', 0),
                                    'umg_detected': umg_detected,
                                    'umg_labels': umg_labels,
                                    'search_query': query
                                }
                                
                                results.append(result)
                
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Error in query: {str(e)[:50]}", (i + 1) / total_queries * 50)
                    continue
                
                # Rate limiting
                time.sleep(0.5)
            
            # Now get detailed info for UMG-detected results
            if progress_callback:
                progress_callback("Analyzing detected content...", 60)
            
            umg_results = [r for r in results if r['umg_detected']]
            
            for i, result in enumerate(umg_results[:20]):  # Limit detailed analysis
                if progress_callback:
                    progress_callback(f"Analyzing: {result['title'][:40]}...", 60 + (i / 20) * 35)
                
                try:
                    detailed = self._get_detailed_umg_info(result['id'])
                    if detailed:
                        result.update(detailed)
                except Exception:
                    pass
                
                time.sleep(0.3)
            
            if progress_callback:
                progress_callback("Complete", 100)
        
        except Exception as e:
            self.log(f"Error in UMG search: {str(e)}")
        
        return results
    
    def _detect_umg_indicators(self, title, channel, description, entry):
        """Detect UMG indicators in video metadata
        
        Returns:
            tuple: (is_umg, list of detected labels/indicators)
        """
        indicators = []
        
        # Check title
        is_umg_title, labels_title = self.check_umg_label(title)
        indicators.extend(labels_title)
        
        # Check channel name
        is_umg_channel, labels_channel = self.check_umg_label(channel)
        indicators.extend(labels_channel)
        
        # Check description
        is_umg_desc, labels_desc = self.check_umg_label(description or '')
        indicators.extend(labels_desc)
        
        # Check for VEVO channels (often UMG affiliated)
        if 'vevo' in channel.lower():
            indicators.append('VEVO Channel')
        
        # Check for "official" in title with high view count (likely major label)
        if 'official' in title.lower():
            view_count = entry.get('view_count', 0) or 0
            if view_count > 10000000:  # 10M+ views
                indicators.append('Official (High Views)')
        
        # Check channel patterns
        channel_lower = channel.lower()
        umg_channel_patterns = [
            'universalmusic', 'universal music', 'umg',
            'interscope', 'geffen', 'defjam', 'def jam',
            'republic records', 'capitol records', 'island records',
            'motown', 'polydor', 'virgin', 'mercury records',
        ]
        for pattern in umg_channel_patterns:
            if pattern in channel_lower:
                indicators.append(f'Channel: {channel[:30]}')
                break
        
        # Remove duplicates
        indicators = list(set(indicators))
        
        return len(indicators) > 0, indicators
    
    def _get_detailed_umg_info(self, video_id):
        """Get detailed information about a video to confirm UMG status"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            if self.ffmpeg_path and self.ffmpeg_path != 'ffmpeg':
                ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                if os.path.exists(ffmpeg_dir):
                    ydl_opts['ffmpeg_location'] = ffmpeg_dir
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                url = f"https://www.youtube.com/watch?v={video_id}"
                info = ydl.extract_info(url, download=False)
                
                if info:
                    # Check license info if available
                    license_info = info.get('license', '')
                    artist = info.get('artist', info.get('creator', ''))
                    album = info.get('album', '')
                    
                    # Check if artist is in UMPG list
                    is_umpg, umpg_match = self.check_umpg_artist(artist)
                    
                    return {
                        'artist': artist,
                        'album': album,
                        'license': license_info,
                        'is_umpg_artist': is_umpg,
                        'umpg_match': umpg_match,
                        'description': info.get('description', '')[:500],
                    }
        
        except Exception:
            pass
        
        return None


class UMGCheckModeDialog(tk.Toplevel):
    """Dialog for Universal Music Group detection mode
    
    This mode provides generic search to find all artists and songs
    that might be protected by UMG and its subsidiaries.
    """
    
    def __init__(self, parent, checker_app):
        super().__init__(parent)
        self.title("UMG Check Mode - Find Universal Music Protected Content")
        self.geometry("1200x800")
        self.transient(parent)
        
        self.checker_app = checker_app
        self.results = []
        self.is_searching = False
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        # Info label
        info_frame = ttk.LabelFrame(main_frame, text="About UMG Check Mode", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        info_text = """This tool uses the official UMPG (Universal Music Publishing Group) search to check if songs are protected.

How to use:
1. Enter an artist/song name and click "Search on UMPG" to open the official database
2. Or load your AI-COVERS and right-click on any song to check it on UMPG
3. The "Checked" column shows which songs you've already verified

The UMPG database at umusicpub.com is the authoritative source for checking Universal Music protection."""
        
        ttk.Label(info_frame, text=info_text, justify='left', wraplength=1150).pack(anchor='w')
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="UMPG Search", padding=10)
        search_frame.pack(fill='x', pady=(0, 10))
        
        # Search term
        term_frame = ttk.Frame(search_frame)
        term_frame.pack(fill='x', pady=5)
        
        ttk.Label(term_frame, text="Artist or Song:").pack(side='left', padx=(0, 5))
        self.search_term_var = tk.StringVar()
        self.search_type_var = tk.StringVar(value='artist')  # Keep for compatibility
        search_entry = ttk.Entry(term_frame, textvariable=self.search_term_var, width=50)
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        # Bind Enter key
        search_entry.bind('<Return>', lambda e: self.start_search())
        
        ttk.Button(term_frame, text="Search on UMPG", command=self.start_search).pack(side='left', padx=5)
        
        # Load buttons
        load_frame = ttk.Frame(search_frame)
        load_frame.pack(fill='x', pady=5)
        
        ttk.Label(load_frame, text="Load songs to check:").pack(side='left', padx=(0, 5))
        ttk.Button(load_frame, text="Load AI-COVERS", command=self.scan_ai_covers_for_umg).pack(side='left', padx=5)
        ttk.Button(load_frame, text="Load Known UMPG Artists", command=self.search_all_umpg).pack(side='left', padx=5)
        
        # Official UMPG search button
        umpg_frame = ttk.Frame(search_frame)
        umpg_frame.pack(fill='x', pady=5)
        
        ttk.Label(umpg_frame, text="Direct link:", font=('TkDefaultFont', 9)).pack(side='left', padx=(0, 5))
        ttk.Button(umpg_frame, text="Open UMPG Official Music Search", 
                  command=self.open_umpg_official_search).pack(side='left', padx=5)
        ttk.Label(umpg_frame, text="(Search the official UMPG database for protected songs/artists)", 
                 font=('TkDefaultFont', 8, 'italic'), foreground='gray').pack(side='left', padx=5)
        
        # Progress
        progress_frame = ttk.Frame(search_frame)
        progress_frame.pack(fill='x', pady=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side='left')
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(side='left', padx=10, fill='x', expand=True)
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=5)
        results_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Filter frame
        filter_frame = ttk.Frame(results_frame)
        filter_frame.pack(fill='x', pady=(0, 5))
        
        self.result_count_var = tk.StringVar(value="0 songs")
        ttk.Label(filter_frame, textvariable=self.result_count_var).pack(side='left')
        
        # Filter checkbox for protected only
        self.show_protected_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Show PROTECTED only", 
                       variable=self.show_protected_only_var, 
                       command=self._display_results).pack(side='right', padx=10)
        
        # Results tree with UMPG protection status
        tree_container = ttk.Frame(results_frame)
        tree_container.pack(fill='both', expand=True)
        
        scroll_y = ttk.Scrollbar(tree_container, orient='vertical')
        scroll_x = ttk.Scrollbar(tree_container, orient='horizontal')
        
        self.results_tree = ttk.Treeview(tree_container, columns=(
            'Artist', 'Title', 'Status', 'Decade', 'Source'
        ), show='headings', yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.results_tree.yview)
        scroll_x.config(command=self.results_tree.xview)
        
        # Column headers
        self.results_tree.heading('Artist', text='Artist')
        self.results_tree.heading('Title', text='Song Title')
        self.results_tree.heading('Status', text='UMPG Status')
        self.results_tree.heading('Decade', text='Decade')
        self.results_tree.heading('Source', text='Source')
        
        # Column widths
        self.results_tree.column('Artist', width=250)
        self.results_tree.column('Title', width=250)
        self.results_tree.column('Status', width=180)
        self.results_tree.column('Decade', width=80)
        self.results_tree.column('Source', width=120)
        
        self.results_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Configure tags for visual feedback
        self.results_tree.tag_configure('protected', background='#ffcccc', foreground='#8b0000')
        self.results_tree.tag_configure('not_protected', background='#ccffcc', foreground='#006400')
        self.results_tree.tag_configure('error', background='#ffffcc', foreground='#8b8b00')
        
        # Bind double-click
        self.results_tree.bind('<Double-1>', self.on_result_double_click)
        
        # Bind right-click for context menu
        self.results_tree.bind('<Button-3>', self.on_result_right_click)  # Windows
        self.results_tree.bind('<Button-2>', self.on_result_right_click)  # Mac
        
        # Debug log frame
        log_frame = ttk.LabelFrame(main_frame, text="Debug Log", padding=5)
        log_frame.pack(fill='both', expand=False, pady=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD, font=('Consolas', 8))
        self.log_text.pack(fill='both', expand=True)
        
        # Buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        
        ttk.Button(btn_frame, text="Export Results", command=self.export_results).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add Protected to Main", command=self.add_to_main_results).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Results", command=self.clear_results).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Log", command=self.clear_log).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=5)
    
    def log(self, message):
        """Log message to debug text widget"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.update_idletasks()
    
    def clear_log(self):
        """Clear the debug log"""
        self.log_text.delete(1.0, tk.END)
    
    def quick_search(self, label):
        """Quick search for a specific label"""
        self.search_type_var.set('label')
        self.search_term_var.set(label)
        self.start_search()
    
    def open_umpg_official_search(self):
        """Open the official UMPG Music Library search in browser
        
        This is the authoritative source for checking if a song/artist
        is protected by Universal Music Publishing Group.
        URL format: https://www.umusicpub.com/us/Digital-Music-Library/search/{SearchTerm}
        """
        import webbrowser
        
        # Use the current search term if available
        search_term = self.search_term_var.get().strip()
        base_url = "https://www.umusicpub.com/us/Digital-Music-Library/search"
        
        if search_term:
            # URL encode the search term for the path
            search_encoded = urllib.parse.quote(search_term)
            webbrowser.open(f"{base_url}/{search_encoded}")
        else:
            # Just open the search page if no term entered
            webbrowser.open(base_url)
    
    def start_search(self):
        """Start the UMG search"""
        search_term = self.search_term_var.get().strip()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term")
            return
        
        if self.is_searching:
            messagebox.showwarning("Warning", "Search already in progress")
            return
        
        self.is_searching = True
        
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results = []
        
        # Start search in thread
        thread = threading.Thread(target=self._run_search, 
                                 args=(self.search_type_var.get(), search_term),
                                 daemon=True)
        thread.start()
    
    def search_all_umpg(self):
        """Search for all known UMPG artists"""
        if self.is_searching:
            messagebox.showwarning("Warning", "Search already in progress")
            return
        
        # Get list of UMPG artists
        umpg_artists = list(set(self.checker_app.umpg_artists.values()))
        
        if not umpg_artists:
            messagebox.showwarning("Warning", "No UMPG artists in database")
            return
        
        # Show confirmation
        msg = f"This will search for {len(umpg_artists)} known UMPG artists.\n"
        msg += "This may take several minutes.\n\nContinue?"
        
        if not messagebox.askyesno("Confirm", msg):
            return
        
        self.is_searching = True
        
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results = []
        
        # Start search in thread
        thread = threading.Thread(target=self._run_umpg_artist_search, 
                                 args=(umpg_artists[:30],),  # Limit to first 30 for speed
                                 daemon=True)
        thread.start()
    
    def scan_ai_covers_for_umg(self):
        """Scan all AI-COVERS directory for UMG protection"""
        if self.is_searching:
            messagebox.showwarning("Warning", "Search already in progress")
            return
        
        # Get AI-COVERS path
        ai_covers_path = self.checker_app.get_ai_covers_path()
        
        if not os.path.exists(ai_covers_path):
            messagebox.showerror("Error", f"AI-COVERS directory not found: {ai_covers_path}")
            return
        
        # Scan for songs in AI-COVERS
        songs = []
        try:
            for decade_dir in os.listdir(ai_covers_path):
                decade_path = os.path.join(ai_covers_path, decade_dir)
                if not os.path.isdir(decade_path):
                    continue
                
                for song_dir in os.listdir(decade_path):
                    song_path = os.path.join(decade_path, song_dir)
                    if not os.path.isdir(song_path):
                        continue
                    
                    # Look for JSON file
                    json_files = [f for f in os.listdir(song_path) 
                                 if f.endswith('.json') and not f.startswith('grok_')]
                    if not json_files:
                        continue
                    
                    json_path = os.path.join(song_path, json_files[0])
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            song_data = json.load(f)
                        
                        song_name = song_data.get('song_name', '').strip()
                        artist = song_data.get('artist', '').strip()
                        
                        if song_name:
                            songs.append({
                                'song_name': song_name,
                                'artist': artist,
                                'decade': decade_dir,
                                'json_path': json_path
                            })
                    except Exception:
                        continue
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan AI-COVERS: {str(e)}")
            return
        
        if not songs:
            messagebox.showwarning("Warning", "No songs found in AI-COVERS directory")
            return
        
        # Show confirmation
        msg = f"Found {len(songs)} songs in AI-COVERS directory.\n"
        msg += "This will check each song for UMG protection.\n"
        msg += "This may take several minutes.\n\nContinue?"
        
        if not messagebox.askyesno("Confirm AI-COVERS UMG Scan", msg):
            return
        
        self.is_searching = True
        
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results = []
        
        # Start search in thread
        thread = threading.Thread(target=self._run_ai_covers_umg_scan, 
                                 args=(songs,),
                                 daemon=True)
        thread.start()
    
    def _check_umpg_search_playwright(self, page, search_term, label, navigate_first=True):
        """Check UMPG by using the search form (not URL) and return if results were found
        
        Args:
            page: Playwright page object
            search_term: Term to search for
            label: Label for logging (e.g., "Artist" or "Song")
            navigate_first: If True, navigate to the search page first
            
        Returns:
            tuple: (has_results, result_count, error_message)
        """
        try:
            self.after(0, lambda st=search_term: self.log(f"  {label} search: {st}"))
            
            # Navigate to the UMPG search page if needed
            if navigate_first:
                self.after(0, lambda: self.log(f"  Navigating to UMPG search page..."))
                page.goto('https://www.umusicpub.com/us/Digital-Music-Library/search', wait_until='networkidle', timeout=30000)
            
            # Wait for the search input to be available
            search_input_selector = 'input.advanced-search__input'
            self.after(0, lambda: self.log(f"  Waiting for search input..."))
            page.wait_for_selector(search_input_selector, timeout=15000)
            
            # Clear any existing text and type the search term
            search_input = page.locator(search_input_selector)
            search_input.clear()
            search_input.fill(search_term)
            self.after(0, lambda st=search_term: self.log(f"  Entered search term: {st}"))
            
            # Click the search button
            search_button_selector = 'button.advanced-search__submit'
            page.wait_for_selector(search_button_selector, timeout=5000)
            page.click(search_button_selector)
            self.after(0, lambda: self.log(f"  Clicked search button, waiting for results..."))
            
            # Wait at least 10 seconds for results to load (UMPG can be slow)
            time.sleep(10)
            
            # Then wait for results to load
            # Either the results table appears OR the "no results" message appears
            try:
                page.wait_for_selector(
                    'umpg-results-grid-table-v2 tbody.table__body, .results-grid--no-results',
                    timeout=10000
                )
                self.after(0, lambda: self.log(f"  Search completed."))
            except Exception:
                # Timeout - give it a bit more time
                self.after(0, lambda: self.log(f"  Timeout waiting for results, checking page..."))
                time.sleep(2)
            
            # Get the page content after JavaScript rendering
            content = page.content()
            
            # Debug: log content length
            self.after(0, lambda cl=len(content): self.log(f"  Page content length: {cl} chars"))
            
            # Look for the results count indicator: "X-Y of Z Results"
            # This is the most reliable way to detect if there are results
            import re
            results_match = re.search(r'(\d+)-(\d+)\s+of\s+(\d+)\s+Results', content)
            
            if results_match:
                # Found results! Extract the total count
                total_results = int(results_match.group(3))
                self.after(0, lambda tr=total_results: self.log(f"  Found results indicator: {tr} total results"))
                has_results = total_results > 0
                result_count = total_results
            else:
                # No results indicator found - check for explicit "no results" message
                # or check if the results grid has the no-results class
                has_no_results_class = 'results-grid--no-results' in content
                
                # Also check for song links as backup detection
                song_links = content.count('/us/Digital-Music-Library/song/')
                
                if has_no_results_class:
                    self.after(0, lambda l=label: self.log(f"  {l}: No results found on UMPG (no-results class)"))
                    has_results = False
                    result_count = 0
                elif song_links > 0:
                    # Found song links even without the counter
                    self.after(0, lambda sl=song_links: self.log(f"  Found {sl} song links (no counter found)"))
                    has_results = True
                    result_count = song_links
                else:
                    self.after(0, lambda l=label: self.log(f"  {l}: No results found on UMPG"))
                    has_results = False
                    result_count = 0
            
            if has_results:
                self.after(0, lambda l=label, rc=result_count: self.log(f"  >>> {l.upper()} FOUND ON UMPG! ({rc} results)"))
            
            return has_results, result_count, None
            
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda l=label, err=error_msg: self.log(f"  {l} ERROR: {err}"))
            return False, 0, error_msg
    
    def _run_ai_covers_umg_scan(self, songs):
        """Scan AI-COVERS songs for UMPG protection by checking the official UMPG website
        
        Uses Playwright to render the JavaScript-based UMPG search page.
        Checks each song/artist on https://www.umusicpub.com/us/Digital-Music-Library/search/
        """
        playwright_obj = None
        context = None
        
        try:
            from playwright.sync_api import sync_playwright
            
            all_results = []
            total = len(songs)
            protected_count = 0
            not_protected_count = 0
            error_count = 0
            
            self.after(0, lambda: self.log(f"Starting UMPG scan for {total} songs..."))
            self.after(0, lambda: self.log(f"Using Playwright browser for JavaScript rendering"))
            self.after(0, lambda: self.log(f"UMPG search URL: https://www.umusicpub.com/us/Digital-Music-Library/search/"))
            self.after(0, lambda: self.log("=" * 60))
            
            # Launch browser once and reuse for all checks
            # Use persistent context to save/restore browser profile (cookies, session, etc.)
            self.after(0, lambda: self.log("Launching headless browser..."))
            playwright_obj = sync_playwright().start()
            
            # Create browser profile directory
            browser_profile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'browser_data', 'umpg_profile')
            os.makedirs(browser_profile_dir, exist_ok=True)
            self.after(0, lambda bpd=browser_profile_dir: self.log(f"Browser profile: {bpd}"))
            
            context = playwright_obj.chromium.launch_persistent_context(
                browser_profile_dir,
                headless=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            self.after(0, lambda: self.log("Browser ready."))
            
            # Navigate to search page once at the start
            self.after(0, lambda: self.log("Navigating to UMPG search page..."))
            page.goto('https://www.umusicpub.com/us/Digital-Music-Library/search', wait_until='networkidle', timeout=30000)
            
            for i, song_info in enumerate(songs):
                song_name = song_info['song_name']
                artist = song_info['artist']
                decade = song_info['decade']
                
                self.progress_var.set(f"Checking {i+1}/{total}: {artist[:20]} - {song_name[:25]}")
                self.progress_bar['value'] = (i / total) * 100
                self.update_idletasks()
                
                # Build UMPG search URLs (for reference/logging)
                umpg_search_artist = urllib.parse.quote(artist) if artist else ''
                umpg_search_song = urllib.parse.quote(song_name) if song_name else ''
                umpg_url_artist = f"https://www.umusicpub.com/us/Digital-Music-Library/search/{umpg_search_artist}"
                umpg_url_song = f"https://www.umusicpub.com/us/Digital-Music-Library/search/{umpg_search_song}"
                
                self.after(0, lambda a=artist, s=song_name, d=decade, num=i+1, t=total: 
                    self.log(f"\n[{num}/{t}] Checking: {a} - {s} ({d})"))
                
                # Check artist on UMPG
                artist_protected = False
                song_protected = False
                check_error = False
                
                # Check artist using search form (don't navigate again, we're already on the page)
                if artist:
                    has_results, count, error = self._check_umpg_search_playwright(page, artist, "Artist", navigate_first=False)
                    if error:
                        check_error = True
                    elif has_results:
                        artist_protected = True
                
                # Small delay between requests
                time.sleep(0.5)
                
                # Check song name using search form
                if song_name:
                    has_results, count, error = self._check_umpg_search_playwright(page, song_name, "Song", navigate_first=False)
                    if error:
                        check_error = True
                    elif has_results:
                        song_protected = True
                
                # Determine protection status
                is_protected = artist_protected or song_protected
                
                if check_error:
                    status = 'Error'
                    error_count += 1
                    self.after(0, lambda: self.log(f"  RESULT: Error checking"))
                elif is_protected:
                    if artist_protected and song_protected:
                        status = 'PROTECTED (Artist + Song)'
                    elif artist_protected:
                        status = 'PROTECTED (Artist)'
                    else:
                        status = 'PROTECTED (Song)'
                    protected_count += 1
                    self.after(0, lambda s=status: self.log(f"  RESULT: {s} <<<"))
                else:
                    status = 'Not Protected'
                    not_protected_count += 1
                    self.after(0, lambda: self.log(f"  RESULT: Not Protected"))
                
                result = {
                    'title': song_name,
                    'artist': artist,
                    'decade': decade,
                    'umpg_url_artist': umpg_url_artist,
                    'umpg_url_song': umpg_url_song,
                    'source': 'AI-COVERS',
                    'checked': True,
                    'is_protected': is_protected,
                    'artist_protected': artist_protected,
                    'song_protected': song_protected,
                    'status': status,
                    'check_error': check_error,
                }
                
                all_results.append(result)
                
                # Rate limiting - be nice to the server
                time.sleep(0.5)
            
            self.results = all_results
            self.after(0, self._display_results)
            
            # Log final summary
            self.after(0, lambda: self.log("\n" + "=" * 60))
            self.after(0, lambda: self.log("SCAN COMPLETE - SUMMARY"))
            self.after(0, lambda: self.log("=" * 60))
            self.after(0, lambda t=total: self.log(f"Total songs checked: {t}"))
            self.after(0, lambda p=protected_count: self.log(f"PROTECTED (found on UMPG): {p}"))
            self.after(0, lambda n=not_protected_count: self.log(f"Not Protected: {n}"))
            if error_count > 0:
                self.after(0, lambda e=error_count: self.log(f"Errors: {e}"))
            self.after(0, lambda: self.log("=" * 60))
            
            summary = f"UMPG Check Complete!\n\n"
            summary += f"Total songs checked: {total}\n"
            summary += f"PROTECTED (found on UMPG): {protected_count}\n"
            summary += f"Not Protected: {not_protected_count}\n"
            if error_count > 0:
                summary += f"Errors: {error_count}\n"
            summary += f"\nRight-click to verify any result on UMPG website."
            
            self.after(0, lambda: messagebox.showinfo("UMPG Check Complete", summary))
        
        except ImportError:
            self.after(0, lambda: self.log("ERROR: Playwright not installed!"))
            self.after(0, lambda: self.log("Please run: pip install playwright"))
            self.after(0, lambda: self.log("Then run: playwright install chromium"))
            self.after(0, lambda: messagebox.showerror("Error", 
                "Playwright not installed.\n\nRun these commands:\npip install playwright\nplaywright install chromium"))
        
        except Exception as e:
            self.after(0, lambda err=str(e): self.log(f"FATAL ERROR: {err}"))
            self.after(0, lambda: messagebox.showerror("Error", f"Check failed: {str(e)}"))
        
        finally:
            # Clean up browser resources (persistent context)
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright_obj:
                try:
                    playwright_obj.stop()
                except Exception:
                    pass
            
            self.is_searching = False
            self.after(0, lambda: self.progress_var.set("Ready"))
            self.after(0, lambda: self.progress_bar.configure(value=0))
    
    def _run_search(self, search_type, search_term):
        """Search UMPG using Playwright with visible browser - uses search form"""
        playwright_obj = None
        context = None
        
        try:
            from playwright.sync_api import sync_playwright
            
            search_encoded = urllib.parse.quote(search_term)
            umpg_url = f"https://www.umusicpub.com/us/Digital-Music-Library/search/{search_encoded}"
            
            self.after(0, lambda: self.log(f"Searching UMPG for: {search_term}"))
            self.after(0, lambda: self.log("Launching visible browser..."))
            
            # Launch browser in visible mode (headless=False) with persistent profile
            playwright_obj = sync_playwright().start()
            
            # Create browser profile directory
            browser_profile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'browser_data', 'umpg_profile')
            os.makedirs(browser_profile_dir, exist_ok=True)
            self.after(0, lambda bpd=browser_profile_dir: self.log(f"Browser profile: {bpd}"))
            
            context = playwright_obj.chromium.launch_persistent_context(
                browser_profile_dir,
                headless=False,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Use the search form method instead of URL navigation
            has_results, result_count, error = self._check_umpg_search_playwright(page, search_term, search_type.capitalize(), navigate_first=True)
            
            # Determine status
            if error:
                status = 'Error'
                is_protected = False
            elif has_results:
                status = f'PROTECTED ({result_count} results)'
                is_protected = True
            else:
                status = 'Not Protected'
                is_protected = False
            
            # Add to results list
            result = {
                'title': search_term if search_type == 'song' else '',
                'artist': search_term if search_type == 'artist' else '',
                'decade': '',
                'umpg_url_artist': umpg_url if search_type == 'artist' else '',
                'umpg_url_song': umpg_url if search_type == 'song' else '',
                'source': 'Manual Search',
                'checked': True,
                'is_protected': is_protected,
                'artist_protected': is_protected if search_type == 'artist' else False,
                'song_protected': is_protected if search_type == 'song' else False,
                'status': status,
                'check_error': error is not None,
            }
            
            self.results.append(result)
            self.after(0, self._display_results)
            
            # Keep browser open for a moment so user can see results
            self.after(0, lambda: self.log("Browser will close in 5 seconds..."))
            time.sleep(5)
        
        except ImportError:
            self.after(0, lambda: self.log("ERROR: Playwright not installed!"))
            self.after(0, lambda: messagebox.showerror("Error", 
                "Playwright not installed.\n\nRun these commands:\npip install playwright\nplaywright install chromium"))
        
        except Exception as e:
            self.after(0, lambda err=str(e): self.log(f"ERROR: {err}"))
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to search UMPG: {str(e)}"))
        
        finally:
            # Clean up browser resources (persistent context)
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright_obj:
                try:
                    playwright_obj.stop()
                except Exception:
                    pass
            
            self.is_searching = False
            self.after(0, lambda: self.progress_var.set("Ready"))
            self.after(0, lambda: self.progress_bar.configure(value=0))
    
    def _run_umpg_artist_search(self, artists):
        """Check known UMPG artists on the official UMPG website
        
        Uses Playwright to render the JavaScript-based UMPG search page.
        Verifies each artist on https://www.umusicpub.com/us/Digital-Music-Library/search/
        """
        playwright_obj = None
        context = None
        
        try:
            from playwright.sync_api import sync_playwright
            
            all_results = []
            total = len(artists)
            protected_count = 0
            not_protected_count = 0
            error_count = 0
            
            self.after(0, lambda: self.log(f"Starting UMPG artist check for {total} artists..."))
            self.after(0, lambda: self.log(f"Using Playwright browser for JavaScript rendering"))
            self.after(0, lambda: self.log("=" * 60))
            
            # Launch browser once and reuse for all checks
            # Use persistent context to save/restore browser profile (cookies, session, etc.)
            self.after(0, lambda: self.log("Launching headless browser..."))
            playwright_obj = sync_playwright().start()
            
            # Create browser profile directory
            browser_profile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'browser_data', 'umpg_profile')
            os.makedirs(browser_profile_dir, exist_ok=True)
            self.after(0, lambda bpd=browser_profile_dir: self.log(f"Browser profile: {bpd}"))
            
            context = playwright_obj.chromium.launch_persistent_context(
                browser_profile_dir,
                headless=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            self.after(0, lambda: self.log("Browser ready."))
            
            # Navigate to search page once at the start
            self.after(0, lambda: self.log("Navigating to UMPG search page..."))
            page.goto('https://www.umusicpub.com/us/Digital-Music-Library/search', wait_until='networkidle', timeout=30000)
            
            for i, artist in enumerate(artists):
                self.progress_var.set(f"Checking artist {i+1}/{total}: {artist[:30]}")
                self.progress_bar['value'] = (i / total) * 100
                self.update_idletasks()
                
                artist_encoded = urllib.parse.quote(artist)
                umpg_url = f"https://www.umusicpub.com/us/Digital-Music-Library/search/{artist_encoded}"
                
                self.after(0, lambda a=artist, num=i+1, t=total: self.log(f"\n[{num}/{t}] Checking artist: {a}"))
                
                # Check artist on UMPG using search form
                has_results, count, error = self._check_umpg_search_playwright(page, artist, "Artist", navigate_first=False)
                
                is_protected = has_results
                check_error = error is not None
                
                if check_error:
                    status = 'Error'
                    error_count += 1
                elif is_protected:
                    status = 'PROTECTED'
                    protected_count += 1
                else:
                    status = 'Not Protected'
                    not_protected_count += 1
                    self.after(0, lambda: self.log(f"  Not found on UMPG"))
                
                result = {
                    'title': '',
                    'artist': artist,
                    'decade': '',
                    'umpg_url_artist': umpg_url,
                    'umpg_url_song': '',
                    'source': 'Known UMPG Artist',
                    'checked': True,
                    'is_protected': is_protected,
                    'artist_protected': is_protected,
                    'song_protected': False,
                    'status': status,
                    'check_error': check_error,
                }
                
                all_results.append(result)
                
                # Rate limiting
                time.sleep(0.5)
            
            self.results = all_results
            self.after(0, self._display_results)
            
            # Log final summary
            self.after(0, lambda: self.log("\n" + "=" * 60))
            self.after(0, lambda: self.log("ARTIST CHECK COMPLETE - SUMMARY"))
            self.after(0, lambda: self.log("=" * 60))
            self.after(0, lambda t=total: self.log(f"Total artists checked: {t}"))
            self.after(0, lambda p=protected_count: self.log(f"PROTECTED (found on UMPG): {p}"))
            self.after(0, lambda n=not_protected_count: self.log(f"Not Found on UMPG: {n}"))
            if error_count > 0:
                self.after(0, lambda e=error_count: self.log(f"Errors: {e}"))
            self.after(0, lambda: self.log("=" * 60))
            
            summary = f"UMPG Artist Check Complete!\n\n"
            summary += f"Total artists checked: {total}\n"
            summary += f"PROTECTED (found on UMPG): {protected_count}\n"
            summary += f"Not Found on UMPG: {not_protected_count}\n"
            if error_count > 0:
                summary += f"Errors: {error_count}\n"
            summary += f"\nRight-click to verify any result on UMPG website."
            
            self.after(0, lambda: messagebox.showinfo("UMPG Artist Check Complete", summary))
        
        except ImportError:
            self.after(0, lambda: self.log("ERROR: Playwright not installed!"))
            self.after(0, lambda: self.log("Please run: pip install playwright"))
            self.after(0, lambda: self.log("Then run: playwright install chromium"))
            self.after(0, lambda: messagebox.showerror("Error", 
                "Playwright not installed.\n\nRun these commands:\npip install playwright\nplaywright install chromium"))
        
        except Exception as e:
            self.after(0, lambda err=str(e): self.log(f"FATAL ERROR: {err}"))
            self.after(0, lambda: messagebox.showerror("Error", f"Check failed: {str(e)}"))
        
        finally:
            # Clean up browser resources (persistent context)
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if playwright_obj:
                try:
                    playwright_obj.stop()
                except Exception:
                    pass
            
            self.is_searching = False
            self.after(0, lambda: self.progress_var.set("Ready"))
            self.after(0, lambda: self.progress_bar.configure(value=0))
    
    def _display_results(self):
        """Display results in tree view with UMPG protection status"""
        # Clear tree
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        show_protected_only = self.show_protected_only_var.get()
        
        displayed = 0
        protected_count = 0
        not_protected_count = 0
        
        for i, result in enumerate(self.results):
            is_protected = result.get('is_protected', False)
            
            if is_protected:
                protected_count += 1
            else:
                not_protected_count += 1
            
            # Filter if needed
            if show_protected_only and not is_protected:
                continue
            
            displayed += 1
            
            # Determine tag based on status
            status = result.get('status', 'Not Checked')
            if result.get('check_error'):
                tag = 'error'
            elif is_protected:
                tag = 'protected'
            else:
                tag = 'not_protected'
            
            tags = (str(i), tag)
            
            self.results_tree.insert('', 'end', values=(
                result.get('artist', '')[:40],
                result.get('title', '')[:40],
                status,
                result.get('decade', ''),
                result.get('source', '')[:15]
            ), tags=tags)
        
        self.result_count_var.set(f"{displayed} shown | {protected_count} PROTECTED | {not_protected_count} Not Protected")
    
    def filter_results(self):
        """Filter displayed results"""
        self._display_results()
    
    def on_result_double_click(self, event):
        """Open video URL on double-click"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.results_tree.item(item, 'tags')
        if not tags:
            return
        
        try:
            result_index = int(tags[0])
            if 0 <= result_index < len(self.results):
                result = self.results[result_index]
                # Open UMPG search for the artist
                umpg_url = result.get('umpg_url_artist', '')
                if umpg_url:
                    import webbrowser
                    webbrowser.open(umpg_url)
                    # Mark as checked
                    result['checked'] = True
                    self._display_results()
        except (ValueError, IndexError):
            pass
    
    def on_result_right_click(self, event):
        """Handle right-click to show context menu with search options"""
        item = self.results_tree.identify_row(event.y)
        if not item:
            return
        
        # Select the item
        self.results_tree.selection_set(item)
        
        tags = self.results_tree.item(item, 'tags')
        if not tags:
            return
        
        try:
            result_index = int(tags[0])
            if 0 <= result_index < len(self.results):
                result = self.results[result_index]
                self._show_context_menu(event, result)
        except (ValueError, IndexError):
            pass
    
    def _show_context_menu(self, event, result):
        """Show context menu with UMPG search options"""
        import webbrowser
        
        title = result.get('title', '')
        artist = result.get('artist', '')
        result_index = None
        
        # Find result index
        for i, r in enumerate(self.results):
            if r is result:
                result_index = i
                break
        
        # Create context menu
        context_menu = tk.Menu(self, tearoff=0)
        
        # Build search terms
        artist_encoded = urllib.parse.quote(artist) if artist else ''
        title_encoded = urllib.parse.quote(title) if title else ''
        
        # UMPG base URL
        umpg_base_url = "https://www.umusicpub.com/us/Digital-Music-Library/search"
        
        def open_umpg_and_mark(url):
            """Open UMPG search and mark as checked"""
            webbrowser.open(url)
            if result_index is not None:
                self.results[result_index]['checked'] = True
                self._display_results()
        
        # UMPG search options - this is the main feature
        if artist:
            context_menu.add_command(
                label=f"Check Artist on UMPG: \"{artist[:35]}\"",
                command=lambda: open_umpg_and_mark(f"{umpg_base_url}/{artist_encoded}")
            )
        if title:
            context_menu.add_command(
                label=f"Check Song on UMPG: \"{title[:35]}\"",
                command=lambda: open_umpg_and_mark(f"{umpg_base_url}/{title_encoded}")
            )
        
        if not artist and not title:
            context_menu.add_command(
                label="Open UMPG Music Search",
                command=lambda: webbrowser.open(umpg_base_url)
            )
        
        context_menu.add_separator()
        
        # Copy options
        copy_menu = tk.Menu(context_menu, tearoff=0)
        
        if title:
            copy_menu.add_command(
                label=f"Copy Song Title",
                command=lambda: self._copy_to_clipboard(title)
            )
        if artist:
            copy_menu.add_command(
                label=f"Copy Artist",
                command=lambda: self._copy_to_clipboard(artist)
            )
        if title and artist:
            copy_menu.add_command(
                label=f"Copy \"{artist} - {title[:20]}\"",
                command=lambda: self._copy_to_clipboard(f"{artist} - {title}")
            )
        
        context_menu.add_cascade(label="Copy", menu=copy_menu)
        
        # Copy options
        context_menu.add_separator()
        copy_menu = tk.Menu(context_menu, tearoff=0)
        
        if title:
            copy_menu.add_command(
                label=f"Copy Title: \"{title[:40]}\"",
                command=lambda: self._copy_to_clipboard(title)
            )
        if artist:
            copy_menu.add_command(
                label=f"Copy Artist: \"{artist[:30]}\"",
                command=lambda: self._copy_to_clipboard(artist)
            )
        if title and artist:
            copy_menu.add_command(
                label=f"Copy: \"{title[:25]} - {artist[:20]}\"",
                command=lambda: self._copy_to_clipboard(f"{title} - {artist}")
            )
        
        # Copy UMPG URL
        umpg_url = result.get('umpg_url_artist', '')
        if umpg_url:
            copy_menu.add_command(
                label="Copy UMPG Search URL",
                command=lambda: self._copy_to_clipboard(umpg_url)
            )
        
        context_menu.add_cascade(label="Copy", menu=copy_menu)
        
        # Show menu
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass
    
    def clear_results(self):
        """Clear all results"""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results = []
        self.result_count_var.set("0 results")
    
    def export_results(self):
        """Export results to CSV"""
        if not self.results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export UMG Check Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'Artist', 'Song Title', 'UMPG Status', 'Artist Protected', 'Song Protected',
                    'Decade', 'Source', 'UMPG URL Artist', 'UMPG URL Song'
                ])
                writer.writeheader()
                
                for result in self.results:
                    writer.writerow({
                        'Artist': result.get('artist', ''),
                        'Song Title': result.get('title', ''),
                        'UMPG Status': result.get('status', 'Not Checked'),
                        'Artist Protected': 'Yes' if result.get('artist_protected') else 'No',
                        'Song Protected': 'Yes' if result.get('song_protected') else 'No',
                        'Decade': result.get('decade', ''),
                        'Source': result.get('source', ''),
                        'UMPG URL Artist': result.get('umpg_url_artist', ''),
                        'UMPG URL Song': result.get('umpg_url_song', '')
                    })
            
            messagebox.showinfo("Success", f"Exported {len(self.results)} results to {file_path}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    def add_to_main_results(self):
        """Add UMPG-protected items to the main results view"""
        protected_results = [r for r in self.results if r.get('is_protected')]
        
        if not protected_results:
            messagebox.showwarning("Warning", "No UMPG-protected items to add")
            return
        
        added = 0
        for result in protected_results:
            title = result.get('title', '')
            artist = result.get('artist', '')
            status = result.get('status', 'PROTECTED')
            
            # Check local UMPG artist list too
            is_umpg, umpg_match = self.checker_app.check_umpg_artist(artist)
            
            main_result = {
                'song_title': title,
                'artist': artist,
                'cover_count': 0,
                'claims_count': 0,
                'strikes_count': 0,
                'claims_percent': 0,
                'strikes_percent': 0,
                'oldest_age': 'N/A',
                'avg_views': 0,
                'is_umpg': True,  # Confirmed via UMPG website
                'ump_artist_match': umpg_match or artist,
                'risk_level': 'ROT',
                'recommendation': f'UMPG PROTECTED: {status}',
                'covers': [],
                'analysis': {'oldest_age': 'N/A', 'avg_views': 0}
            }
            
            self.checker_app.add_result(main_result)
            added += 1
        
        messagebox.showinfo("Added", f"Added {added} UMPG-protected songs to main results")


class SettingsDialog(tk.Toplevel):
    """Settings dialog for configuring AI-COVERS base directory"""
    
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("Settings - Cover Song Checker")
        self.geometry("600x200")
        self.transient(parent)
        self.grab_set()
        
        self.config = config.copy()
        self.result = None
        
        # Center dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # AI-COVERS Base Directory
        ttk.Label(main_frame, text="AI-COVERS Base Directory:", 
                 font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        
        ttk.Label(main_frame, 
                 text="Leave empty to use default: <Project Root>/AI/AI-COVERS", 
                 font=('TkDefaultFont', 8, 'italic')).pack(anchor='w', pady=(0, 10))
        
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill='x', pady=5)
        
        self.path_var = tk.StringVar(value=self.config.get('ai_covers_base_dir', ''))
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        ttk.Button(path_frame, text="Browse...", command=self.browse_directory).pack(side='left')
        
        # Current path display
        current_path = self.path_var.get().strip()
        if not current_path:
            # Calculate default path (same logic as in get_ai_covers_path)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
            default_path = os.path.join(root_dir, 'AI', 'AI-COVERS')
            current_path = f"Default: {default_path}"
        else:
            current_path = f"Current: {current_path}"
        
        self.path_label = ttk.Label(main_frame, text=current_path, 
                 font=('TkDefaultFont', 8), foreground='gray')
        self.path_label.pack(anchor='w', pady=(5, 0))
        
        # Update path display when path changes
        def update_path_display(*args):
            path = self.path_var.get().strip()
            if not path:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
                default_path = os.path.join(root_dir, 'AI', 'AI-COVERS')
                self.path_label.config(text=f"Default: {default_path}")
            else:
                self.path_label.config(text=f"Current: {path}")
        
        self.path_var.trace('w', update_path_display)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(btn_frame, text="Save", command=self.save_settings).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side='right', padx=5)
    
    def browse_directory(self):
        """Browse for AI-COVERS directory"""
        current = self.path_var.get()
        initial_dir = current if current and os.path.exists(current) else os.getcwd()
        
        path = filedialog.askdirectory(
            title="Select AI-COVERS Base Directory",
            initialdir=initial_dir
        )
        
        if path:
            self.path_var.set(path)
    
    def save_settings(self):
        """Save settings and close dialog"""
        self.config['ai_covers_base_dir'] = self.path_var.get().strip()
        self.result = self.config
        self.destroy()
    
    def cancel(self):
        """Cancel without saving"""
        self.result = None
        self.destroy()


def main():
    root = tk.Tk()
    app = CoverSongCheckerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
