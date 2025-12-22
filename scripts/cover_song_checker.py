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


class CoverSongCheckerGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Cover Song Checker")
        self.root.geometry("1400x1000")
        
        self.results = []
        self.is_analyzing = False
        
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
        # Main frame (no tabs, single view)
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.setup_check_tab(main_frame)
    
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
        ttk.Button(btn_frame, text="Select from AI-COVERS", command=self.select_from_ai_covers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Scan All AI-COVERS", command=self.scan_ai_covers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear Results", command=self.clear_results).pack(side='left', padx=5)
        
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
            'Oldest Age', 'Avg Views', 'Risk Level', 'Recommendation'
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
        """Load songs from CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                songs = []
                for row in reader:
                    # Try different column names
                    song_title = row.get('Song Title') or row.get('song_title') or row.get('Title') or row.get('title') or ''
                    artist = row.get('Artist') or row.get('artist') or row.get('Artist(s)') or ''
                    
                    if song_title:
                        songs.append((song_title, artist))
                
                if not songs:
                    messagebox.showwarning("Warning", "No songs found in CSV file")
                    return
                
                # Ask for confirmation
                if messagebox.askyesno("Confirm", f"Found {len(songs)} songs. Start analysis?"):
                    thread = threading.Thread(target=self.analyze_multiple_songs, args=(songs,), daemon=True)
                    thread.start()
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {str(e)}")
    
    def select_from_ai_covers(self):
        """Open dialog to select individual songs from AI-COVERS directory"""
        ai_covers_path = os.path.join(self.root_dir, 'AI', 'AI-COVERS')
        
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
        ai_covers_path = os.path.join(self.root_dir, 'AI', 'AI-COVERS')
        
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
            
            # Calculate risk level
            risk_level, recommendation = self.calculate_risk(analysis, song_title, artist)
            
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
    
    def calculate_risk(self, analysis, song_title, artist):
        """Calculate risk level and recommendation"""
        cover_count = analysis['cover_count']
        oldest_date = analysis['oldest_date']
        avg_views = analysis['avg_views']
        
        # Known problematic publishers
        problematic_publishers = ['Universal', 'Sony', 'Warner', 'EMI']
        is_problematic = any(pub.lower() in (song_title + ' ' + artist).lower() for pub in problematic_publishers)
        
        # Known problematic artists (based on real-world case)
        problematic_artists = ['Eminem', 'Drake', 'Rihanna', 'Taylor Swift', 'Ariana Grande']
        is_problematic_artist = any(art.lower() in artist.lower() for art in problematic_artists)
        
        # Risk calculation
        if cover_count == 0:
            risk_level = 'ROT'
            recommendation = 'RISKY - No cover history found'
        
        elif cover_count < 3:
            risk_level = 'ROT'
            recommendation = 'RISKY - Very few covers exist'
        
        elif is_problematic_artist or is_problematic:
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
        
        # Add to tree
        item = self.results_tree.insert('', 'end', values=(
            result['song_title'],
            result['artist'],
            result['cover_count'],
            f"{result['claims_percent']:.1f}%",
            f"{result['strikes_percent']:.1f}%",
            result['oldest_age'],
            f"{result['avg_views']:,}",
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
        
        info_text = f"""
Song: {result['song_title']}
Artist: {result['artist']}
Cover Count: {result['cover_count']}
Risk Level: {result['risk_level']}
Recommendation: {result['recommendation']}
Oldest Cover Age: {result['oldest_age']}
Average Views: {result['avg_views']:,}
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
                    'Avg Views', 'Risk Level', 'Recommendation'
                ])
                writer.writeheader()
                
                for result in self.results:
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
                        'Risk Level': result['risk_level'],
                        'Recommendation': result['recommendation']
                    })
            
            messagebox.showinfo("Success", f"Results exported to {file_path}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")


def main():
    root = tk.Tk()
    app = CoverSongCheckerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
