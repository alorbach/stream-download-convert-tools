"""
Song Style Analyzer - Analyze songs for generative conditioning using Azure Whisper API

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
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import csv
import threading
import time
import requests
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# Try to import mutagen for MP3 and FLAC metadata
try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC
    from mutagen.id3 import ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# Import shared libraries
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.base_gui import BaseAudioGUI


def get_config_path() -> str:
    """Get the path to the suno_persona_config.json file in the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'suno_persona_config.json')


def load_config() -> dict:
    """Load configuration from JSON file, create default if it doesn't exist."""
    config_path = get_config_path()
    default_config = {
        "general": {
            "personas_path": "AI/Personas",
            "default_save_path": "",
            "styles_csv_path": "AI/suno/suno_sound_styles.csv"
        },
        "profiles": {
            "text": {
                "endpoint": "https://your-endpoint.cognitiveservices.azure.com/",
                "model_name": "gpt-4",
                "deployment": "gpt-4",
                "subscription_key": "<your-api-key>",
                "api_version": "2024-12-01-preview"
            },
            "transcribe": {
                "endpoint": "https://your-endpoint.cognitiveservices.azure.com/",
                "model_name": "whisper-1",
                "deployment": "whisper-1",
                "subscription_key": "<your-api-key>",
                "api_version": "2024-12-01-preview"
            }
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # Merge with defaults to ensure all keys exist
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                    elif key == 'profiles' and isinstance(config[key], dict):
                        for profile_name in default_config['profiles']:
                            if profile_name not in config['profiles']:
                                config['profiles'][profile_name] = default_config['profiles'][profile_name]
                            else:
                                for setting_key in default_config['profiles'][profile_name]:
                                    if setting_key not in config['profiles'][profile_name]:
                                        config['profiles'][profile_name][setting_key] = default_config['profiles'][profile_name][setting_key]
                return config
        except Exception as exc:
            print(f'Config Error: Failed to load config:\n{exc}')
            return default_config
    else:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
        except Exception as exc:
            print(f'Config Error: Failed to create config:\n{exc}')
        return default_config


def call_azure_ai(
    config: dict,
    prompt: str,
    system_message: str = None,
    profile: str = 'text',
    max_tokens: int = 4000,
    temperature: float = 0.7
) -> dict:
    """Call Azure OpenAI API for text generation/analysis.
    
    Args:
        config: Configuration dictionary
        prompt: User prompt
        system_message: Optional system message
        profile: Profile name to use (default 'text')
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
    
    Returns:
        Dictionary with 'success', 'content', 'error'
    """
    try:
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {
                'success': False,
                'content': '',
                'error': f'Profile "{profile}" not found in configuration.'
            }
        
        profile_config = profiles[profile]
        endpoint = profile_config.get('endpoint', '').rstrip('/')
        deployment = profile_config.get('deployment', '')
        api_version = profile_config.get('api_version', '2024-12-01-preview')
        subscription_key = profile_config.get('subscription_key', '')
        
        if not all([endpoint, deployment, subscription_key]):
            return {
                'success': False,
                'content': '',
                'error': f'Missing Azure AI configuration for profile "{profile}". Please configure settings.'
            }
        
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': subscription_key
        }
        
        messages = []
        if system_message:
            messages.append({'role': 'system', 'content': system_message})
        messages.append({'role': 'user', 'content': prompt})
        
        payload = {
            'messages': messages,
            'max_completion_tokens': max_tokens
        }
        # Only add temperature if it's not None and not 1 (some models only support default value of 1)
        # For models that don't support temperature, we'll omit it
        if temperature is not None and temperature != 1:
            try:
                payload['temperature'] = temperature
            except:
                # If temperature is not supported, just omit it
                pass
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        # If temperature was included and we got a 400 error about it, retry without temperature
        if response.status_code == 400 and 'temperature' in payload:
            try:
                error_json = response.json()
                error_detail = error_json.get('error', {})
                error_message = str(error_detail.get('message', '')).lower() if isinstance(error_detail, dict) else str(error_detail).lower()
                if 'temperature' in error_message:
                    # Retry without temperature
                    payload.pop('temperature', None)
                    response = requests.post(url, headers=headers, json=payload, timeout=120)
            except:
                pass
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return {
                'success': True,
                'content': content,
                'error': ''
            }
        else:
            error_msg = f'API error {response.status_code}'
            try:
                error_json = response.json()
                error_detail = error_json.get('error', {})
                if isinstance(error_detail, dict):
                    error_msg = f'{error_msg}: {error_detail.get("message", error_detail.get("code", str(error_detail)))}'
                else:
                    error_msg = f'{error_msg}: {str(error_detail)}'
            except:
                error_text = response.text[:500]
                error_msg = f'{error_msg}: {error_text}'
            
            return {
                'success': False,
                'content': '',
                'error': error_msg
            }
    
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'content': '',
            'error': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'content': '',
            'error': f'Unexpected error: {str(e)}'
        }


def call_azure_audio_transcription(config: dict, audio_file_path: str, profile: str = 'transcribe', language: str = None, response_format: str = 'json', prompt: str = None) -> dict:
    """Call Azure OpenAI Whisper API to transcribe audio.
    
    Args:
        config: Configuration dictionary
        audio_file_path: Path to audio file (MP3, FLAC, WAV, etc.)
        profile: Profile name to use (default 'transcribe')
        language: Optional language code (e.g., 'en', 'de')
        response_format: Response format - 'json' for simple, 'text' for plain text
        prompt: Optional prompt to guide transcription
    
    Returns:
        Dictionary with 'success', 'content' (transcription text), 'error'
    """
    try:
        if not os.path.exists(audio_file_path):
            return {
                'success': False,
                'content': '',
                'error': f'Audio file not found: {audio_file_path}'
            }
        
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {
                'success': False,
                'content': '',
                'error': f'Profile "{profile}" not found in configuration.'
            }
        
        profile_config = profiles[profile]
        endpoint = profile_config.get('endpoint', '').rstrip('/')
        deployment = profile_config.get('deployment', '')
        api_version = profile_config.get('api_version', '2024-12-01-preview')
        subscription_key = profile_config.get('subscription_key', '')
        
        if not all([endpoint, deployment, subscription_key]):
            return {
                'success': False,
                'content': '',
                'error': f'Missing Azure AI configuration for profile "{profile}". Please configure settings in suno_persona_config.json'
            }
        
        # Azure OpenAI Whisper API endpoint
        url = f"{endpoint}/openai/deployments/{deployment}/audio/transcriptions?api-version={api_version}"
        
        headers = {
            'api-key': subscription_key
        }
        
        # Prepare multipart form data with appropriate MIME type
        file_ext = os.path.splitext(audio_file_path)[1].lower()
        if file_ext == '.flac':
            mime_type = 'audio/flac'
        elif file_ext == '.mp3':
            mime_type = 'audio/mpeg'
        else:
            mime_type = 'audio/mpeg'  # Default fallback
        
        files = {
            'file': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), mime_type)
        }
        
        data = {
            'response_format': response_format
        }
        
        if language:
            data['language'] = language
        if prompt:
            data['prompt'] = prompt
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=300)
        files['file'][1].close()  # Close the file
        
        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '') if isinstance(result, dict) else str(result)
            
            return {
                'success': True,
                'content': text,
                'error': ''
            }
        else:
            error_msg = f'API error {response.status_code}'
            try:
                error_json = response.json()
                error_detail = error_json.get('error', {})
                if isinstance(error_detail, dict):
                    error_msg = f'{error_msg}: {error_detail.get("message", error_detail.get("code", str(error_detail)))}'
                else:
                    error_msg = f'{error_msg}: {str(error_detail)}'
            except:
                error_text = response.text[:500]
                error_msg = f'{error_msg}: {error_text}'
            
            return {
                'success': False,
                'content': '',
                'error': error_msg
            }
    
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'content': '',
            'error': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'content': '',
            'error': f'Unexpected error: {str(e)}'
        }


class SongStyleAnalyzerGUI(BaseAudioGUI):
    def __init__(self, root):
        super().__init__(root, "Song Style Analyzer")
        self.root.geometry("1200x800")
        
        self.ai_config = load_config()
        self.is_processing = False
        self.cancel_requested = False
        self.processed_files = []
        self.results = []
        
        self.setup_ui()
        
        # Check dependencies
        if not MUTAGEN_AVAILABLE:
            self.log_error("mutagen library not available. Audio metadata extraction will be limited.")
        
        # Check Azure configuration
        transcribe_profile = self.ai_config.get('profiles', {}).get('transcribe', {})
        if not transcribe_profile.get('subscription_key') or transcribe_profile.get('subscription_key') == '<your-api-key>':
            self.log_error("Azure transcription not configured. Please configure 'transcribe' profile in suno_persona_config.json")
        else:
            self.log("Azure transcription configured (using 'transcribe' profile from suno_persona_config.json)")
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Azure Configuration", padding=10)
        settings_frame.pack(fill='x', pady=(0, 10))
        
        settings_inner = ttk.Frame(settings_frame)
        settings_inner.pack(fill='x')
        
        ttk.Label(settings_inner, 
                 text="Using 'transcribe' profile from suno_persona_config.json", 
                 foreground='gray').pack(side='left', padx=5)
        
        status_label = ttk.Label(settings_inner, text="", foreground='gray')
        status_label.pack(side='left', padx=10)
        
        transcribe_profile = self.ai_config.get('profiles', {}).get('transcribe', {})
        if transcribe_profile.get('subscription_key') and transcribe_profile.get('subscription_key') != '<your-api-key>':
            status_label.config(text="✓ Azure configured", foreground='green')
        else:
            status_label.config(text="⚠ Azure not configured", foreground='orange')
        
        self.azure_status_label = status_label
        
        # Input frame
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding=10)
        input_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # File selection
        file_frame = ttk.Frame(input_frame)
        file_frame.pack(fill='x', pady=5)
        
        ttk.Button(file_frame, text="Select Audio File", 
                  command=self.select_single_file).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Select Directory (Recursive)", 
                  command=self.select_directory).pack(side='left', padx=5)
        
        # Options frame
        options_frame = ttk.LabelFrame(input_frame, text="Options", padding=10)
        options_frame.pack(fill='x', pady=10)
        
        self.require_metadata_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Require valid artist and song name in metadata", 
                       variable=self.require_metadata_var).pack(anchor='w', pady=2)
        
        output_format_frame = ttk.Frame(options_frame)
        output_format_frame.pack(fill='x', pady=5)
        ttk.Label(output_format_frame, text="Output Format:").pack(side='left', padx=(0, 5))
        self.output_format_var = tk.StringVar(value='json')
        ttk.Radiobutton(output_format_frame, text="JSON", variable=self.output_format_var, 
                       value='json').pack(side='left', padx=5)
        ttk.Radiobutton(output_format_frame, text="CSV", variable=self.output_format_var, 
                       value='csv').pack(side='left', padx=5)
        
        # File list
        list_frame = ttk.Frame(input_frame)
        list_frame.pack(fill='both', expand=True, pady=5)
        
        label_frame = ttk.Frame(list_frame)
        label_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(label_frame, text="Files to Process:").pack(side='left')
        if DND_AVAILABLE:
            ttk.Label(label_frame, text="(Drag and drop MP3/FLAC files or folders here)", 
                     foreground='gray', font=('TkDefaultFont', 8)).pack(side='left', padx=(10, 0))
        
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill='both', expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side='right', fill='y')
        
        self.file_listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set, height=8)
        self.file_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.file_listbox.yview)
        
        # Drag-and-drop support for adding audio files
        if DND_AVAILABLE:
            try:
                self.file_listbox.drop_target_register(DND_FILES)
                self.file_listbox.dnd_bind('<<Drop>>', self.on_drop_files)
                # Also allow dropping on the list container frame
                list_container.drop_target_register(DND_FILES)
                list_container.dnd_bind('<<Drop>>', self.on_drop_files)
            except Exception as e:
                self.log(f"Warning: Could not enable drag-and-drop: {e}")
        
        # Control buttons
        control_frame = ttk.Frame(input_frame)
        control_frame.pack(fill='x', pady=5)
        
        self.process_button = ttk.Button(control_frame, text="Start Analysis", 
                                         command=self.start_analysis, state='normal')
        self.process_button.pack(side='left', padx=5)
        
        self.cancel_button = ttk.Button(control_frame, text="Cancel", 
                                       command=self.cancel_analysis, state='disabled')
        self.cancel_button.pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Clear List", 
                  command=self.clear_file_list).pack(side='left', padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=10)
        progress_frame.pack(fill='x', pady=(0, 10))
        
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor='w')
        
        self.progress_bar = self.create_progress_bar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=10)
        results_frame.pack(fill='both', expand=True)
        
        results_inner = ttk.Frame(results_frame)
        results_inner.pack(fill='both', expand=True)
        
        # Export button
        button_frame = ttk.Frame(results_inner)
        button_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(button_frame, text="Export Results", 
                  command=self.export_results).pack(side='left', padx=5)
        ttk.Label(button_frame, text="Double-click a row to view details", 
                 foreground='gray', font=('TkDefaultFont', 8)).pack(side='left', padx=10)
        
        # Results grid (Treeview)
        tree_container = ttk.Frame(results_inner)
        tree_container.pack(fill='both', expand=True)
        
        scroll_y = ttk.Scrollbar(tree_container, orient='vertical')
        scroll_x = ttk.Scrollbar(tree_container, orient='horizontal')
        
        self.results_tree = ttk.Treeview(tree_container, columns=(
            'Artist', 'Title', 'Genre', 'Mood', 'Duration', 'Has Vocals'
        ), show='headings', yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.results_tree.yview)
        scroll_x.config(command=self.results_tree.xview)
        
        # Column headers
        self.results_tree.heading('#0', text='#')
        self.results_tree.heading('Artist', text='Artist')
        self.results_tree.heading('Title', text='Title')
        self.results_tree.heading('Genre', text='Genre')
        self.results_tree.heading('Mood', text='Mood')
        self.results_tree.heading('Duration', text='Duration')
        self.results_tree.heading('Has Vocals', text='Vocals')
        
        # Column widths
        self.results_tree.column('#0', width=40, minwidth=40)
        self.results_tree.column('Artist', width=150, minwidth=100)
        self.results_tree.column('Title', width=200, minwidth=150)
        self.results_tree.column('Genre', width=150, minwidth=100)
        self.results_tree.column('Mood', width=120, minwidth=80)
        self.results_tree.column('Duration', width=80, minwidth=60)
        self.results_tree.column('Has Vocals', width=70, minwidth=50)
        
        self.results_tree.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Bind double-click to show details
        self.results_tree.bind('<Double-1>', self.on_result_double_click)
    
    
    def select_single_file(self):
        """Select a single audio file (MP3 or FLAC)."""
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[("Audio files", "*.mp3 *.flac"), ("MP3 files", "*.mp3"), ("FLAC files", "*.flac"), ("All files", "*.*")]
        )
        
        if file_path:
            self.file_listbox.delete(0, tk.END)
            self.file_listbox.insert(tk.END, file_path)
            self.log(f"Selected file: {os.path.basename(file_path)}")
    
    def select_directory(self):
        """Select a directory and scan for audio files (MP3/FLAC)."""
        directory = filedialog.askdirectory(title="Select Directory to Scan")
        
        if not directory:
            return
        
        self.log(f"Scanning directory: {directory}")
        audio_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac')):
                    file_path = os.path.join(root, file)
                    
                    # Check metadata if required
                    if self.require_metadata_var.get():
                        artist, title = self.extract_metadata(file_path)
                        if not artist or not title:
                            continue
                    
                    audio_files.append(file_path)
        
        if not audio_files:
            messagebox.showinfo("Info", "No audio files (MP3/FLAC) found (or none with valid metadata if requirement is enabled)")
            return
        
        self.file_listbox.delete(0, tk.END)
        for file_path in audio_files:
            self.file_listbox.insert(tk.END, file_path)
        
        self.log(f"Found {len(audio_files)} audio file(s)")
    
    def extract_metadata(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract artist and title from audio file metadata (MP3 or FLAC)."""
        if not MUTAGEN_AVAILABLE:
            return None, None
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # Handle MP3 files
            if file_ext == '.mp3':
                audio = MP3(file_path, ID3=ID3)
                
                # Try to get title
                title = None
                if audio.tags:
                    title_tag = audio.tags.get('TIT2')
                    if title_tag:
                        title = str(title_tag.text[0]) if title_tag.text else None
                    
                    # Try alternative tag names
                    if not title:
                        for tag_name in ['TITLE', 'TIT2']:
                            if tag_name in audio.tags:
                                title = str(audio.tags[tag_name].text[0])
                                break
                    
                    # Try to get artist
                    artist = None
                    artist_tag = audio.tags.get('TPE1')
                    if artist_tag:
                        artist = str(artist_tag.text[0]) if artist_tag.text else None
                    
                    if not artist:
                        for tag_name in ['ARTIST', 'TPE1', 'TPE2']:
                            if tag_name in audio.tags:
                                artist = str(audio.tags[tag_name].text[0])
                                break
                    
                    return artist, title
            
            # Handle FLAC files
            elif file_ext == '.flac':
                audio = FLAC(file_path)
                
                if audio.tags:
                    # Get title
                    title = None
                    if 'TITLE' in audio.tags:
                        title = str(audio.tags['TITLE'][0]) if audio.tags['TITLE'] else None
                    
                    # Get artist
                    artist = None
                    if 'ARTIST' in audio.tags:
                        artist = str(audio.tags['ARTIST'][0]) if audio.tags['ARTIST'] else None
                    elif 'ALBUMARTIST' in audio.tags:
                        artist = str(audio.tags['ALBUMARTIST'][0]) if audio.tags['ALBUMARTIST'] else None
                    
                    return artist, title
            
        except ID3NoHeaderError:
            pass
        except Exception as e:
            self.log(f"Error extracting metadata from {os.path.basename(file_path)}: {e}")
        
        return None, None
    
    def clear_file_list(self):
        """Clear the file list."""
        self.file_listbox.delete(0, tk.END)
        self.log("File list cleared")
    
    def _parse_dropped_paths(self, data):
        """Parse dropped file list from DND event data (supports {path with spaces})."""
        if not data:
            return []
        # Handle paths with spaces wrapped in curly braces or quotes
        tokens = re.findall(r"\{[^}]+\}|\"[^\"]+\"|\S+", data)
        paths = []
        for t in tokens:
            t = t.strip()
            if t.startswith('{') and t.endswith('}'):
                t = t[1:-1]
            if t.startswith('"') and t.endswith('"'):
                t = t[1:-1]
            if t:
                paths.append(t)
        return paths
    
    def on_drop_files(self, event):
        """Handle files dropped onto the file list."""
        if not DND_AVAILABLE:
            return
        
        paths = self._parse_dropped_paths(event.data)
        added = 0
        skipped = 0
        
        for path in paths:
            # Check if it's a directory
            if os.path.isdir(path):
                # Scan directory for audio files
                for root, dirs, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(('.mp3', '.flac')):
                            file_path = os.path.join(root, file)
                            
                            # Check if already in list
                            if file_path not in list(self.file_listbox.get(0, tk.END)):
                                # Check metadata if required
                                if self.require_metadata_var.get():
                                    artist, title = self.extract_metadata(file_path)
                                    if not artist or not title:
                                        skipped += 1
                                        continue
                                
                                self.file_listbox.insert(tk.END, file_path)
                                added += 1
            elif os.path.isfile(path) and path.lower().endswith(('.mp3', '.flac')):
                # Check if already in list
                if path not in list(self.file_listbox.get(0, tk.END)):
                    # Check metadata if required
                    if self.require_metadata_var.get():
                        artist, title = self.extract_metadata(path)
                        if not artist or not title:
                            skipped += 1
                            continue
                    
                    self.file_listbox.insert(tk.END, path)
                    added += 1
        
        if added > 0:
            self.log(f"Added {added} audio file(s) via drag and drop")
        if skipped > 0:
            self.log(f"Skipped {skipped} file(s) (no valid metadata if requirement is enabled)")
    
    def start_analysis(self):
        """Start analyzing files."""
        transcribe_profile = self.ai_config.get('profiles', {}).get('transcribe', {})
        if not transcribe_profile.get('subscription_key') or transcribe_profile.get('subscription_key') == '<your-api-key>':
            messagebox.showerror("Error", "Azure transcription not configured. Please configure 'transcribe' profile in suno_persona_config.json")
            return
        
        files = list(self.file_listbox.get(0, tk.END))
        if not files:
            messagebox.showwarning("Warning", "No files selected")
            return
        
        self.is_processing = True
        self.cancel_requested = False
        self.processed_files = []
        self.results = []
        
        self.process_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = len(files)
        
        # Clear results grid
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Start processing in thread
        thread = threading.Thread(target=self.process_files, args=(files,), daemon=True)
        thread.start()
    
    def cancel_analysis(self):
        """Cancel the analysis."""
        self.cancel_requested = True
        self.log("Cancellation requested...")
    
    def process_files(self, files: List[str]):
        """Process files in background thread."""
        total = len(files)
        
        for idx, file_path in enumerate(files):
            if self.cancel_requested:
                self.log("Analysis cancelled by user")
                break
            
            self.progress_var.set(f"Processing {idx + 1}/{total}: {os.path.basename(file_path)}")
            self.progress_bar['value'] = idx
            
            try:
                result = self.analyze_file(file_path)
                if result:
                    self.results.append(result)
                    self.processed_files.append(file_path)
                    
                    # Update results display
                    self.root.after(0, self.update_results_display, result)
                    
            except Exception as e:
                self.log_error(f"Error processing {os.path.basename(file_path)}: {e}")
        
        # Finalize
        self.progress_bar['value'] = total if not self.cancel_requested else len(self.processed_files)
        self.progress_var.set(f"Completed: {len(self.processed_files)}/{total} files processed")
        
        self.is_processing = False
        self.root.after(0, lambda: self.process_button.config(state='normal'))
        self.root.after(0, lambda: self.cancel_button.config(state='disabled'))
        
        if not self.cancel_requested:
            self.log_success(f"Analysis complete: {len(self.results)} files analyzed")
    
    def extract_style_from_transcription(self, transcription: str, artist: str, title: str) -> Dict:
        """Extract style information from transcription using Azure OpenAI."""
        if not transcription or not transcription.strip():
            return {
                "prompt_string": "",
                "taxonomy": {
                    "primary_genre": "",
                    "sub_genre": "",
                    "fusion_tags": [],
                    "mood": "",
                    "instrumentation": [],
                    "production_quality": ""
                },
                "suno_style_prompt": "",
                "negative_prompt": ""
            }
        
        # Create prompt for style analysis
        system_message = """You are a music analysis expert specializing in extracting style information from song lyrics and metadata for Suno AI music generation. 
You understand Suno's style prompt format and best practices for generating effective style keywords and negative prompts.
Analyze the provided song information and extract detailed style characteristics including genre, mood, instrumentation, and production qualities.
Return your analysis in a structured JSON format."""
        
        prompt = f"""Analyze the following song and extract comprehensive style information:

Artist: {artist}
Title: {title}
Lyrics/Transcription:
{transcription}

Please analyze this song and provide:
1. A natural language style description (prompt_string) - A dense, adjective-rich sentence describing the "vibe" and composition
2. Genre classification (primary_genre, sub_genre, fusion_tags as array)
3. Mood/Valence (mood)
4. Instrumentation (as array, e.g., ["Electric Guitar", "Drums", "Bass", "Vocals"])
5. Production quality description
6. A Suno-style prompt (suno_style_prompt) - Comma-separated style keywords/phrases up to 1000 characters
7. A negative prompt (negative_prompt) - Clear, specific things to avoid, comma-separated

CRITICAL INSTRUCTIONS FOR SUNO_STYLE_PROMPT:
- TARGET 800-1000 characters when useful - be comprehensive and detailed, don't be brief
- Maximum 1000 characters total (use the full space if it adds value)
- Order keywords by importance (most important first)
- Use the Suno Prompt Formula: [Mood] + [Genre/Era] + [Key Instruments] + [Vocal Type] + [Production/Mix Tone] + [Tempo/Energy]
- Include: BPM (if determinable), Genre/Era, Key Instruments, Vocal Type, Production/Mix Tone, Tempo/Energy
- Use comma-separated tags/phrases (e.g., "128 BPM, Synthwave, Retrowave, Analog Synthesizer, Male Vocals, Wide Stereo, Mid-tempo")
- Be specific: Use "80s synth-pop" not just "pop", "analog synth bass" not just "bass"
- Include production descriptors: "lo-fi warmth", "wide stereo", "tape-saturated", "clean and modern", "stadium reverb", "vinyl crackle", "live acoustic space"
- Include mood descriptors: "uplifting", "melancholic", "dreamy", "energetic", "nostalgic", "heartbroken", "spiritual", "reflective"
- Include tempo/energy: "slow tempo", "mid-tempo", "fast-paced", "high-energy", "relaxed vibe"
- Include additional details: vocal characteristics, rhythmic patterns, harmonic elements, texture descriptions, era-specific production techniques
- DO NOT include artist names - describe their style instead
- Expand with additional relevant descriptors to reach 800-1000 characters when the song has rich stylistic elements
- Examples of comprehensive style prompts (aim for this level of detail):
  * "128 BPM, Melancholic 2000s indie rock, electric guitar with clean tone, warm synth pads, subtle reverb, male lead vocals with nostalgic vocal tone, wide cinematic mix, mid-tempo, lo-fi warmth, tape-saturated production, organic textures, gentle dynamics"
  * "Dreamy 80s synth-pop, female vocals with breathy delivery, analog synth bass with warm sub frequencies, bright arpeggiated synths, glossy retro mix with gated reverb, mid-tempo (108 BPM), nostalgic production, wide stereo imaging, analog warmth"
  * "Gothic, Alternative Metal, Ethereal Female Voice with ethereal reverb, atmospheric synths with dark pads, distorted rhythm guitars, deep bass lines, dark production with heavy compression, slow tempo, cinematic reverb, moody textures"

CRITICAL INSTRUCTIONS FOR NEGATIVE_PROMPT:
- Be clear and specific about what to exclude
- Use direct language: "no vocals", "avoid distorted guitars", "no heavy bass", "exclude autotune"
- Avoid ambiguous phrasing like "without singing unless background only" or "no sounds that are bad"
- Focus on elements that would conflict with the desired style
- Examples of good negative prompts:
  * "no vocals, no risers, no heavy distortion"
  * "avoid autotune, exclude electronic drums, no synthesizers"
  * "no rap verses, no aggressive vocals, avoid heavy bass drops"
- If nothing specific needs to be excluded, use empty string

Return ONLY valid JSON in this exact format:
{{
  "prompt_string": "A detailed style description...",
  "taxonomy": {{
    "primary_genre": "Genre name",
    "sub_genre": "Sub-genre name",
    "fusion_tags": ["tag1", "tag2"],
    "mood": "Mood description",
    "instrumentation": ["Instrument1", "Instrument2"],
    "production_quality": "Production quality description"
  }},
  "suno_style_prompt": "BPM, Genre/Era, Key Instruments, Vocal Type, Production/Mix Tone, Tempo/Energy - up to 1000 chars, important first",
  "negative_prompt": "Clear, specific exclusions, comma-separated, or empty string if none"
}}

If information cannot be determined, use empty strings or empty arrays. Be specific and detailed. Prioritize accuracy over completeness."""
        
        result = call_azure_ai(
            self.ai_config,
            prompt,
            system_message=system_message,
            profile='text',
            max_tokens=3000,  # Increased to allow for longer style prompts (up to 1000 chars)
            temperature=None  # Use None to let the function handle it (will retry without if needed)
        )
        
        if result.get('success'):
            try:
                content = result.get('content', '').strip()
                # Try to extract JSON from response (might have markdown code blocks)
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()
                
                style_data = json.loads(content)
                return style_data
            except json.JSONDecodeError as e:
                self.log(f"Warning: Could not parse style analysis JSON: {e}")
                # Try to extract basic info from text response
                return self._parse_style_from_text(result.get('content', ''))
        else:
            self.log(f"Warning: Style analysis failed: {result.get('error', 'Unknown error')}")
            return {
                "prompt_string": "",
                "taxonomy": {
                    "primary_genre": "",
                    "sub_genre": "",
                    "fusion_tags": [],
                    "mood": "",
                    "instrumentation": [],
                    "production_quality": ""
                },
                "suno_style_prompt": "",
                "negative_prompt": ""
            }
    
    def _parse_style_from_text(self, text: str) -> Dict:
        """Fallback: Try to extract style info from unstructured text."""
        # Basic fallback parsing
        return {
            "prompt_string": text[:200] if text else "",
            "taxonomy": {
                "primary_genre": "",
                "sub_genre": "",
                "fusion_tags": [],
                "mood": "",
                "instrumentation": [],
                "production_quality": ""
            },
            "suno_style_prompt": "",
            "negative_prompt": ""
        }
    
    def analyze_file(self, file_path: str) -> Optional[Dict]:
        """Analyze a single audio file (MP3 or FLAC)."""
        try:
            # Extract metadata
            artist, title = self.extract_metadata(file_path)
            
            # Get file duration and detect format
            duration = None
            detected_format = "unknown"
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if MUTAGEN_AVAILABLE:
                try:
                    if file_ext == '.mp3':
                        audio = MP3(file_path)
                        duration = int(audio.info.length)
                        detected_format = "mp3"
                    elif file_ext == '.flac':
                        audio = FLAC(file_path)
                        duration = int(audio.info.length)
                        detected_format = "flac"
                except:
                    # Fallback format detection from extension
                    if file_ext == '.mp3':
                        detected_format = "mp3"
                    elif file_ext == '.flac':
                        detected_format = "flac"
            
            # Validate duration
            if duration and duration < 10:
                self.log(f"Skipping {os.path.basename(file_path)}: too short (< 10 seconds)")
                return None
            
            if duration and duration > 480:
                self.log(f"Warning: {os.path.basename(file_path)} is longer than 8 minutes, may be truncated")
            
            # Transcribe with Azure Whisper
            transcription = self.transcribe_audio(file_path)
            
            if not transcription:
                self.log(f"Warning: No transcription obtained for {os.path.basename(file_path)}")
                return None
            
            # Extract style information from transcription
            self.log(f"Extracting style information for {os.path.basename(file_path)}...")
            style_info = self.extract_style_from_transcription(transcription, artist or "Unknown", title or os.path.splitext(os.path.basename(file_path))[0])
            
            # Build result structure based on task specification
            result = {
                "task_id": f"analysis_{int(time.time())}_{os.path.basename(file_path)}",
                "status": "success",
                "analysis_timestamp": datetime.now().isoformat(),
                "input_metadata": {
                    "file_path": file_path,
                    "duration_seconds": duration,
                    "detected_format": detected_format,
                    "artist": artist or "Unknown",
                    "title": title or os.path.splitext(os.path.basename(file_path))[0]
                },
                "style_analysis": {
                    "prompt_string": style_info.get("prompt_string", ""),
                    "taxonomy": style_info.get("taxonomy", {
                        "primary_genre": "",
                        "sub_genre": "",
                        "fusion_tags": [],
                        "mood": "",
                        "instrumentation": [],
                        "production_quality": ""
                    }),
                    "technical_specs": {
                        "bpm": None,  # Would need audio analysis
                        "key": None,  # Would need audio analysis
                        "time_signature": None,  # Would need audio analysis
                        "vocal_presence": bool(transcription and transcription.strip())
                    }
                },
                "lyric_analysis": {
                    "detected_language": "en",  # Azure Whisper detects language
                    "has_vocals": bool(transcription and transcription.strip()),
                    "vocal_gender": None,  # Would need additional analysis
                    "vocal_style": None,  # Would need additional analysis
                    "structured_lyrics": transcription if transcription else ""
                },
                "agent_usage_suggestions": {
                    "suno_style_prompt": style_info.get("suno_style_prompt", ""),
                    "negative_prompt": style_info.get("negative_prompt", "")
                }
            }
            
            return result
            
        except Exception as e:
            self.log_error(f"Error analyzing {os.path.basename(file_path)}: {e}")
            import traceback
            self.log_error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def transcribe_audio(self, file_path: str) -> Optional[str]:
        """Transcribe audio using Azure Whisper API via REST API."""
        result = call_azure_audio_transcription(
            self.ai_config, 
            file_path, 
            profile='transcribe',
            language='en',
            response_format='json'
        )
        
        if result.get('success'):
            return result.get('content', '')
        else:
            error = result.get('error', 'Unknown error')
            self.log_error(f"Transcription error for {os.path.basename(file_path)}: {error}")
            return None
    
    def update_results_display(self, result: Dict):
        """Update the results grid with a new result."""
        input_meta = result.get('input_metadata', {})
        lyric_meta = result.get('lyric_analysis', {})
        style_meta = result.get('style_analysis', {})
        taxonomy = style_meta.get('taxonomy', {})
        
        artist = input_meta.get('artist', 'Unknown')
        title = input_meta.get('title', 'Unknown')
        duration = input_meta.get('duration_seconds', '')
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
        has_vocals = lyric_meta.get('has_vocals', False)
        
        # Extract genre info
        primary_genre = taxonomy.get('primary_genre', '')
        sub_genre = taxonomy.get('sub_genre', '')
        if sub_genre:
            genre_str = f"{primary_genre} / {sub_genre}" if primary_genre else sub_genre
        else:
            genre_str = primary_genre or "Unknown"
        
        mood = taxonomy.get('mood', '') or "N/A"
        
        # Insert row into treeview (result is already appended to self.results)
        row_num = len(self.results)
        item_id = self.results_tree.insert('', 'end', text=str(row_num), values=(
            artist,
            title,
            genre_str,
            mood,
            duration_str,
            'Yes' if has_vocals else 'No'
        ))
        
        # Store result index is already available via row_num - 1 (no need to store separately)
        
        # Scroll to bottom
        self.results_tree.see(item_id)
    
    def on_result_double_click(self, event):
        """Handle double-click on result row to show details."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        # Get row index from the item text (#0 column)
        try:
            row_index = int(self.results_tree.item(item_id, 'text')) - 1
            if 0 <= row_index < len(self.results):
                self.show_result_details(self.results[row_index])
        except (ValueError, IndexError):
            # Fallback: find by matching artist and title
            item_values = self.results_tree.item(item_id, 'values')
            if len(item_values) >= 2:
                artist = item_values[0]
                title = item_values[1]
                for result in self.results:
                    input_meta = result.get('input_metadata', {})
                    if (input_meta.get('artist', '') == artist and 
                        input_meta.get('title', '') == title):
                        self.show_result_details(result)
                        break
    
    def show_result_details(self, result: Dict):
        """Show detailed view of a result in a dialog window."""
        detail_window = tk.Toplevel(self.root)
        input_meta = result.get('input_metadata', {})
        artist = input_meta.get('artist', 'Unknown')
        title = input_meta.get('title', 'Unknown')
        detail_window.title(f"Details: {artist} - {title}")
        detail_window.geometry("900x800")
        
        # Center dialog
        detail_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (detail_window.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (detail_window.winfo_height() // 2)
        detail_window.geometry(f"+{x}+{y}")
        
        # Main frame with notebook for tabs
        main_frame = ttk.Frame(detail_window, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True)
        
        # Summary tab
        summary_frame = ttk.Frame(notebook, padding=10)
        notebook.add(summary_frame, text='Summary')
        
        style_meta = result.get('style_analysis', {})
        taxonomy = style_meta.get('taxonomy', {})
        usage_suggestions = result.get('agent_usage_suggestions', {})
        
        summary_text = f"""File Path: {input_meta.get('file_path', 'N/A')}
Artist: {input_meta.get('artist', 'Unknown')}
Title: {input_meta.get('title', 'Unknown')}
Duration: {input_meta.get('duration_seconds', 'N/A')} seconds
Format: {input_meta.get('detected_format', 'N/A')}
Analysis Timestamp: {result.get('analysis_timestamp', 'N/A')}

Style Analysis:
  Prompt String: {style_meta.get('prompt_string', 'N/A')}
  Primary Genre: {taxonomy.get('primary_genre', 'N/A')}
  Sub Genre: {taxonomy.get('sub_genre', 'N/A')}
  Fusion Tags: {', '.join(taxonomy.get('fusion_tags', [])) or 'N/A'}
  Mood: {taxonomy.get('mood', 'N/A')}
  Instrumentation: {', '.join(taxonomy.get('instrumentation', [])) or 'N/A'}
  Production Quality: {taxonomy.get('production_quality', 'N/A')}

Vocal Analysis:
  Has Vocals: {result.get('lyric_analysis', {}).get('has_vocals', False)}
  Detected Language: {result.get('lyric_analysis', {}).get('detected_language', 'N/A')}
  Vocal Gender: {result.get('lyric_analysis', {}).get('vocal_gender', 'N/A')}
  Vocal Style: {result.get('lyric_analysis', {}).get('vocal_style', 'N/A')}

Technical Specs:
  BPM: {style_meta.get('technical_specs', {}).get('bpm', 'N/A')}
  Key: {style_meta.get('technical_specs', {}).get('key', 'N/A')}
  Time Signature: {style_meta.get('technical_specs', {}).get('time_signature', 'N/A')}
  Vocal Presence: {style_meta.get('technical_specs', {}).get('vocal_presence', False)}

Usage Suggestions:
  Suno Style Prompt: {usage_suggestions.get('suno_style_prompt', 'N/A')}
  Negative Prompt: {usage_suggestions.get('negative_prompt', 'N/A')}
"""
        
        # Use Text widget with wrapping instead of Label for proper text wrapping
        # Get the frame's background color for seamless appearance
        try:
            frame_bg = summary_frame.cget('background')
        except:
            frame_bg = 'SystemButtonFace'  # Default Windows background
        
        summary_text_widget = tk.Text(summary_frame, wrap=tk.WORD, font=('TkDefaultFont', 9), 
                                     relief='flat', bg=frame_bg, 
                                     padx=10, pady=10, state='disabled', borderwidth=0)
        summary_text_widget.insert('1.0', summary_text)
        summary_text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Copy buttons for Usage Suggestions
        usage_button_frame = ttk.Frame(summary_frame)
        usage_button_frame.pack(fill='x', pady=(10, 0))
        
        suno_style_prompt = usage_suggestions.get('suno_style_prompt', '')
        negative_prompt = usage_suggestions.get('negative_prompt', '')
        
        def copy_suno_style_prompt():
            if suno_style_prompt and suno_style_prompt != 'N/A':
                detail_window.clipboard_clear()
                detail_window.clipboard_append(suno_style_prompt)
                self.log("Suno Style Prompt copied to clipboard")
                messagebox.showinfo("Copied", "Suno Style Prompt copied to clipboard!")
            else:
                messagebox.showwarning("Warning", "No Suno Style Prompt available")
        
        def copy_negative_prompt():
            if negative_prompt and negative_prompt != 'N/A':
                detail_window.clipboard_clear()
                detail_window.clipboard_append(negative_prompt)
                self.log("Negative Prompt copied to clipboard")
                messagebox.showinfo("Copied", "Negative Prompt copied to clipboard!")
            else:
                messagebox.showwarning("Warning", "No Negative Prompt available")
        
        def copy_both_prompts():
            if (suno_style_prompt and suno_style_prompt != 'N/A') or (negative_prompt and negative_prompt != 'N/A'):
                combined = ""
                if suno_style_prompt and suno_style_prompt != 'N/A':
                    combined += f"Suno Style Prompt: {suno_style_prompt}\n"
                if negative_prompt and negative_prompt != 'N/A':
                    combined += f"Negative Prompt: {negative_prompt}"
                detail_window.clipboard_clear()
                detail_window.clipboard_append(combined.strip())
                self.log("Both prompts copied to clipboard")
                messagebox.showinfo("Copied", "Usage Suggestions copied to clipboard!")
            else:
                messagebox.showwarning("Warning", "No Usage Suggestions available")
        
        ttk.Label(usage_button_frame, text="Usage Suggestions:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
        ttk.Button(usage_button_frame, text="Copy Suno Style Prompt", command=copy_suno_style_prompt).pack(side='left', padx=2)
        ttk.Button(usage_button_frame, text="Copy Negative Prompt", command=copy_negative_prompt).pack(side='left', padx=2)
        ttk.Button(usage_button_frame, text="Copy Both", command=copy_both_prompts).pack(side='left', padx=2)
        
        # Lyrics tab
        lyrics_frame = ttk.Frame(notebook, padding=10)
        notebook.add(lyrics_frame, text='Lyrics')
        
        # Copy button for lyrics
        lyrics_button_frame = ttk.Frame(lyrics_frame)
        lyrics_button_frame.pack(fill='x', pady=(0, 5))
        
        def copy_lyrics():
            detail_window.clipboard_clear()
            detail_window.clipboard_append(lyrics_content)
            self.log("Lyrics copied to clipboard")
            messagebox.showinfo("Copied", "Lyrics copied to clipboard!")
        
        ttk.Button(lyrics_button_frame, text="Copy Lyrics to Clipboard", command=copy_lyrics).pack(side='left', padx=5)
        
        lyrics_text_widget = tk.Text(lyrics_frame, wrap=tk.WORD, font=('TkDefaultFont', 10))
        lyrics_scroll = ttk.Scrollbar(lyrics_frame, orient='vertical', command=lyrics_text_widget.yview)
        lyrics_text_widget.config(yscrollcommand=lyrics_scroll.set)
        
        lyrics_content = result.get('lyric_analysis', {}).get('structured_lyrics', 'No lyrics available')
        lyrics_text_widget.insert('1.0', lyrics_content)
        lyrics_text_widget.config(state='disabled')
        
        lyrics_text_widget.pack(side='left', fill='both', expand=True)
        lyrics_scroll.pack(side='right', fill='y')
        
        # JSON tab
        json_frame = ttk.Frame(notebook, padding=10)
        notebook.add(json_frame, text='Full JSON')
        
        json_text_widget = tk.Text(json_frame, wrap=tk.NONE, font=('Consolas', 9))
        json_scroll_y = ttk.Scrollbar(json_frame, orient='vertical', command=json_text_widget.yview)
        json_scroll_x = ttk.Scrollbar(json_frame, orient='horizontal', command=json_text_widget.xview)
        json_text_widget.config(yscrollcommand=json_scroll_y.set, xscrollcommand=json_scroll_x.set)
        
        json_content = json.dumps(result, indent=2, ensure_ascii=False)
        json_text_widget.insert('1.0', json_content)
        json_text_widget.config(state='disabled')
        
        json_text_widget.grid(row=0, column=0, sticky='nsew')
        json_scroll_y.grid(row=0, column=1, sticky='ns')
        json_scroll_x.grid(row=1, column=0, sticky='ew')
        json_frame.grid_rowconfigure(0, weight=1)
        json_frame.grid_columnconfigure(0, weight=1)
        
        # Close button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        def copy_json():
            detail_window.clipboard_clear()
            detail_window.clipboard_append(json_content)
            self.log("JSON copied to clipboard")
        
        ttk.Button(button_frame, text="Copy JSON to Clipboard", command=copy_json).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=detail_window.destroy).pack(side='right', padx=5)
    
    def export_results(self):
        """Export results to CSV or JSON file."""
        if not self.results:
            messagebox.showwarning("Warning", "No results to export")
            return
        
        output_format = self.output_format_var.get()
        extension = '.json' if output_format == 'json' else '.csv'
        
        file_path = filedialog.asksaveasfilename(
            title="Save Results",
            defaultextension=extension,
            filetypes=[(f"{output_format.upper()} files", f"*{extension}"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            if output_format == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, indent=2, ensure_ascii=False)
            else:  # CSV
                # Flatten results for CSV
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = [
                        'file_path', 'artist', 'title', 'duration_seconds',
                        'has_vocals', 'detected_language', 'lyrics', 'analysis_timestamp'
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for result in self.results:
                        input_meta = result.get('input_metadata', {})
                        lyric_meta = result.get('lyric_analysis', {})
                        
                        writer.writerow({
                            'file_path': input_meta.get('file_path', ''),
                            'artist': input_meta.get('artist', ''),
                            'title': input_meta.get('title', ''),
                            'duration_seconds': input_meta.get('duration_seconds', ''),
                            'has_vocals': lyric_meta.get('has_vocals', False),
                            'detected_language': lyric_meta.get('detected_language', ''),
                            'lyrics': lyric_meta.get('structured_lyrics', ''),
                            'analysis_timestamp': result.get('analysis_timestamp', '')
                        })
            
            self.log_success(f"Results exported to: {file_path}")
            messagebox.showinfo("Success", f"Results exported successfully to:\n{file_path}")
            
        except Exception as e:
            self.log_error(f"Failed to export results: {e}")
            messagebox.showerror("Error", f"Failed to export results: {str(e)}")


def main():
    # Use TkinterDnD root if available for drag-and-drop support
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = SongStyleAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
