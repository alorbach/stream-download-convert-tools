import json
import os
import sys
import csv
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import requests
import base64
import urllib.parse
import glob
import time
import shutil
import re
import subprocess
from difflib import SequenceMatcher
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import Optional


def enable_long_paths(path: str) -> str:
    """
    Enable long path support on Windows by adding the \\?\\ prefix.
    This allows paths longer than 260 characters (MAX_PATH) to work properly.
    
    Args:
        path: The file or directory path
        
    Returns:
        Path with long path prefix if on Windows and path is long enough
    """
    if sys.platform == 'win32':
        # Convert to absolute path and normalize
        path = os.path.abspath(path)
        # Check if path is already in long path format
        if path.startswith('\\\\?\\'):
            return path
        # Check if path length exceeds MAX_PATH (260 chars)
        # Use 259 to account for null terminator
        if len(path) > 259:
            # Add long path prefix
            # For UNC paths, use \\?\UNC\ instead of \\?\\
            if path.startswith('\\\\'):
                # UNC path: \\server\share -> \\?\UNC\server\share
                return '\\\\?\\UNC\\' + path[2:]
            else:
                # Regular path: C:\path -> \\?\C:\path
                return '\\\\?\\' + path
    return path

# Try to import mutagen for MP3 duration and lyrics extraction
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, ID3NoHeaderError, USLT, SYLT
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


def _scale_image_to_half(image_path: str) -> Optional[str]:
    """Scale image to 50% and save to temp file. Returns temp path or None on error."""
    if not image_path or not os.path.isfile(image_path):
        return None
    try:
        with Image.open(image_path) as img:
            img.load()
            w, h = img.size
            new_size = (max(1, w // 2), max(1, h // 2))
            scaled = img.resize(new_size, Image.Resampling.LANCZOS)
            ext = os.path.splitext(image_path)[1].lower()
            fmt = 'PNG' if ext in ['.png'] else 'JPEG'
            fd, tmp_path = tempfile.mkstemp(suffix=ext or '.png')
            os.close(fd)
            scaled.save(tmp_path, format=fmt, quality=90)
            return tmp_path
    except Exception:
        return None


class ToolTip:
    """Create a tooltip for a widget."""
    def __init__(self, widget, text=''):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
        self.widget.bind('<ButtonPress>', self.leave)
    
    def enter(self, event=None):
        self.schedule()
    
    def leave(self, event=None):
        self.unschedule()
        self.hidetip()
    
    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)
    
    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    
    def showtip(self):
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                        font=("tahoma", "8", "normal"), wraplength=300)
        label.pack(ipadx=1)
    
    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()
    
    def set_text(self, text):
        self.text = text


def create_tooltip(widget, text):
    """Helper function to create a tooltip."""
    return ToolTip(widget, text)


def get_config_path() -> str:
    """Get the path to the config.json file in the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'suno_persona_config.json')


def get_project_root(config: dict = None) -> str:
    """
    Get the project root directory.
    If config is provided and contains a base_path setting, use that.
    Otherwise, calculate from script location.
    """
    if config:
        base_path = config.get('general', {}).get('base_path', '').strip()
        if base_path and os.path.exists(base_path) and os.path.isdir(base_path):
            return os.path.abspath(base_path)
    
    # Fall back to calculated path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, os.pardir))


def resolve_personas_path(config: dict = None) -> str:
    """Resolve default Personas path in AI/Personas/ relative to project root."""
    project_root = get_project_root(config)
    default_path = os.path.join(project_root, 'AI', 'Personas')
    return default_path


def resolve_prompts_path(config: dict = None) -> str:
    """Resolve default prompts path in AI/suno/prompts/ relative to project root."""
    project_root = get_project_root(config)
    default_path = os.path.join(project_root, 'AI', 'suno', 'prompts')
    return default_path


def resolve_styles_csv_path(config: dict = None) -> str:
    """Resolve default styles CSV path in AI/suno/suno_sound_styles.csv relative to project root."""
    project_root = get_project_root(config)
    return os.path.join(project_root, 'AI', 'suno', 'suno_sound_styles.csv')


def get_styles_csv_path(config: dict) -> str:
    """
    Get the styles CSV path from config, resolving relative paths to project root.
    Falls back to default if config value is empty or file not found.
    """
    csv_path = config.get('general', {}).get('styles_csv_path', 'AI/suno/suno_sound_styles.csv')

    # If it's an absolute path and exists, use it
    if os.path.isabs(csv_path) and os.path.exists(csv_path):
        return csv_path

    project_root = get_project_root(config)
    candidate = os.path.join(project_root, csv_path)

    if os.path.exists(candidate):
        return candidate

    return resolve_styles_csv_path(config)


def load_styles_from_csv(csv_path: str) -> list[dict]:
    """Load styles from CSV into a list of dicts."""
    styles = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                styles.append(row)
    except FileNotFoundError:
        print(f'Error: Styles CSV not found at {csv_path}')
    except Exception as exc:
        print(f'Error: Failed to read styles CSV:\n{exc}')
    return styles


def load_styles_from_css(css_path: str) -> list[dict]:
    """Load styles from a .css-style file into a list of dicts with 'style' and 'prompt'.
    Supports line-based 'Style Name: prompt text' and block 'Style Name { prompt text }'.
    """
    styles = []
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f'Error: Styles file not found at {css_path}')
        return []
    except Exception as exc:
        print(f'Error: Failed to read styles file:\n{exc}')
        return []

    # Block format: "Name { ... }"
    block_pattern = re.compile(r'([^{\s][^{]*?)\s*\{\s*([^}]*?)\s\}', re.DOTALL)
    for m in block_pattern.finditer(text):
        name = (m.group(1) or '').strip().strip('."\'')
        prompt = (m.group(2) or '').strip()
        if name:
            styles.append({'style': name, 'prompt': prompt})

    # Line-based format: "Name: prompt" (only if no blocks found, or add as supplement)
    if not styles:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            if ':' in line:
                idx = line.index(':')
                name = line[:idx].strip().strip('."\'')
                prompt = line[idx + 1:].strip()
                if name:
                    styles.append({'style': name, 'prompt': prompt})
    return styles


def load_styles_from_file(file_path: str) -> list[dict]:
    """Load styles from a CSV or CSS file. Returns list of dicts with at least 'style' and 'prompt'."""
    if not file_path or not os.path.isfile(file_path):
        return []
    lower = file_path.lower()
    if lower.endswith('.css'):
        return load_styles_from_css(file_path)
    if lower.endswith('.csv'):
        return load_styles_from_csv(file_path)
    return []


def resolve_styles_import_path(config: dict = None) -> str:
    """Resolve path for loading styles from CSV/CSS files (default: D:/AI/suno)."""
    rel = ''
    if config:
        rel = (config.get('general', {}) or {}).get('styles_import_path', '') or ''
    rel = rel.strip() if isinstance(rel, str) else ''
    if not rel:
        return 'D:/AI/suno'
    if os.path.isabs(rel):
        return rel
    return os.path.join(get_project_root(config), rel)


def get_styles_import_base_name(config: dict) -> str:
    """Get the base name filter for styles import (files starting with this)."""
    name = (config.get('general', {}) or {}).get('styles_import_base_name', '') or ''
    return name.strip() if isinstance(name, str) else ''


def resolve_analysis_data_path(config: dict = None) -> str:
    """Resolve path to SongStyleAnalyzer JSON outputs (default: data/)."""
    rel = ''
    if config:
        rel = (config.get('general', {}) or {}).get('analysis_data_path', '') or ''
    rel = rel.strip() if isinstance(rel, str) else ''
    if not rel:
        rel = 'data'
    if os.path.isabs(rel):
        return rel
    return os.path.join(get_project_root(config), rel)


def _normalize_analysis_key(text: str) -> str:
    text = (text or '').lower()
    text = re.sub(r'[\W_]+', ' ', text, flags=re.UNICODE).strip()
    # Remove leading track numbers like "01", "10", etc.
    text = re.sub(r'^\d+\s+', '', text).strip()
    return text


def _load_song_style_analyzer_entries_from_file(json_path: str) -> list[dict]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        if isinstance(data.get('results'), list):
            entries = data.get('results', [])
        else:
            entries = [data]
    else:
        return []

    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if 'style_analysis' in e or 'agent_usage_suggestions' in e or 'input_metadata' in e:
            out.append(e)
    return out


def _load_song_style_analyzer_entries_from_dir(data_dir: str) -> list[dict]:
    if not data_dir or not os.path.isdir(data_dir):
        return []
    entries: list[dict] = []
    for p in glob.glob(os.path.join(data_dir, '*.json')):
        entries.extend(_load_song_style_analyzer_entries_from_file(p))
    return entries


def _analysis_entry_display_name(entry: dict) -> str:
    meta = entry.get('input_metadata', {}) or {}
    title = str(meta.get('title', '') or '').strip()
    artist = str(meta.get('artist', '') or '').strip()
    if title and artist and artist.lower() != 'unknown':
        return f'{title} - {artist}'
    if title:
        return title
    task_id = str(entry.get('task_id', '') or '').strip()
    return task_id or 'Unknown'


def _analysis_entry_suno_style_prompt(entry: dict) -> str:
    usage = entry.get('agent_usage_suggestions', {}) or {}
    style = str(usage.get('suno_style_prompt', '') or '').strip()
    if style:
        return style
    style_analysis = entry.get('style_analysis', {}) or {}
    return str(style_analysis.get('prompt_string', '') or '').strip()


def _find_best_analysis_entry(song_name: str, artist: str, entries: list[dict]) -> Optional[dict]:
    sn = _normalize_analysis_key(song_name)
    ar = _normalize_analysis_key(artist)
    if not sn:
        return None

    best = None
    best_score = 0
    for e in entries:
        meta = e.get('input_metadata', {}) or {}
        title = str(meta.get('title', '') or '').strip()
        e_title = _normalize_analysis_key(title)
        e_artist = _normalize_analysis_key(str(meta.get('artist', '') or '').strip())
        task_id = _normalize_analysis_key(str(e.get('task_id', '') or '').strip())

        score = 0
        if sn and (sn == e_title or sn in e_title or e_title in sn):
            score += 4
        # Some analyzers embed artist in title like "10_First Time_The Kelly Family"
        if ar and (ar in e_title or ar in task_id or ar == e_artist):
            score += 2
        if sn and sn in task_id:
            score += 2
        if score > best_score:
            best_score = score
            best = e

    return best if best_score > 0 else None


def load_config() -> dict:
    """Load configuration from JSON file, create default if it doesn't exist."""
    config_path = get_config_path()
    default_config = {
        "general": {
            "base_path": "",
            "personas_path": "AI/Personas",
            "default_save_path": "",
            "styles_csv_path": "AI/suno/suno_sound_styles.csv",
            "styles_import_path": "D:/AI/suno",
            "styles_import_base_name": "",
            "analysis_data_path": "data",
            "auto_import_song_style_from_analysis": True
        },
        "profiles": {
            "text": {
                "endpoint": "https://your-endpoint.cognitiveservices.azure.com/",
                "model_name": "gpt-4",
                "deployment": "gpt-4",
                "subscription_key": "<your-api-key>",
                "api_version": "2024-12-01-preview"
            },
            "image_gen": {
                "endpoint": "https://your-endpoint.cognitiveservices.azure.com/",
                "model_name": "dall-e-3",
                "deployment": "dall-e-3",
                "subscription_key": "<your-api-key>",
                "api_version": "2024-02-15-preview"
            },
            "video_gen": {
                "endpoint": "https://your-endpoint.cognitiveservices.azure.com/",
                "model_name": "imagevideo",
                "deployment": "imagevideo",
                "subscription_key": "<your-api-key>",
                "api_version": "2024-02-15-preview"
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
                    elif key == 'general' and isinstance(config[key], dict):
                        for sub_key in default_config['general']:
                            if sub_key not in config[key]:
                                config[key][sub_key] = default_config['general'][sub_key]
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


def save_config(config: dict):
    """Save configuration to JSON file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as exc:
        print(f'Config Error: Failed to save config:\n{exc}')
        return False


def get_personas_path(config: dict) -> str:
    """Get the Personas directory path from config, resolving relative paths."""
    personas_path = config.get('general', {}).get('personas_path', 'AI/Personas')
    
    if os.path.isabs(personas_path) and os.path.exists(personas_path):
        return personas_path
    
    project_root = get_project_root(config)
    full_path = os.path.join(project_root, personas_path)
    
    if os.path.exists(full_path):
        return full_path
    
    return resolve_personas_path(config)


def get_prompt_template(template_name: str, config: dict = None) -> str:
    """Get prompt template by name from file system."""
    prompts_dir = resolve_prompts_path(config)
    template_file = os.path.join(prompts_dir, f'{template_name}.txt')
    
    try:
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f'Warning: Template file not found: {template_file}')
            return ''
    except Exception as e:
        print(f'Error loading template {template_name}: {e}')
        return ''


def call_azure_ai(
    config: dict,
    prompt: str,
    system_message: str = None,
    profile: str = 'text',
    max_tokens: int = 8000,
    temperature: float | None = 0.7
) -> dict:
    """Generic Azure AI caller function."""
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
        if temperature is not None:
            payload['temperature'] = temperature
        
        # Long storyboards can exceed 30s; allow more headroom
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        # Handle model-specific parameter restrictions
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_msg = str(error_data.get('error', {}).get('message', '')).lower()
                
                # Handle temperature restriction (some models only support default temperature=1)
                if ('temperature' in error_msg) and ('not support' in error_msg or 'only the default' in error_msg):
                    # Try forcing temperature=1 first
                    payload['temperature'] = 1
                    response = requests.post(url, headers=headers, json=payload, timeout=120)
                    if response.status_code == 400:
                        try:
                            error_data = response.json()
                            error_msg = str(error_data.get('error', {}).get('message', '')).lower()
                        except Exception:
                            error_msg = ''
                    # If still failing due to temperature, remove parameter entirely
                    if response.status_code == 400 and 'temperature' in error_msg:
                        payload.pop('temperature', None)
                        response = requests.post(url, headers=headers, json=payload, timeout=120)
                        if response.status_code == 400:
                            try:
                                error_data = response.json()
                                error_msg = str(error_data.get('error', {}).get('message', '')).lower()
                            except Exception:
                                error_msg = ''
                
                # Handle max_completion_tokens restriction (fallback to max_tokens for older API versions)
                if response.status_code == 400 and 'max_completion_tokens' in error_msg and 'not supported' in error_msg:
                    payload.pop('max_completion_tokens', None)
                    payload['max_tokens'] = max_tokens
                    response = requests.post(url, headers=headers, json=payload, timeout=120)
            except:
                pass
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return {
                'success': True,
                'content': content,
                'error': ''
            }
        else:
            return {
                'success': False,
                'content': '',
                'error': f'Azure AI error: {response.status_code} - {response.text}'
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


def call_azure_vision(config: dict, image_paths: list, prompt: str, system_message: str = None, profile: str = 'text') -> dict:
    """Call Azure Vision API with multiple images."""
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
        
        # Read and encode images
        image_contents = []
        for img_path in image_paths:
            try:
                with open(img_path, 'rb') as f:
                    img_data = f.read()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    # Determine image format from extension
                    ext = os.path.splitext(img_path)[1].lower()
                    if ext in ['.png']:
                        mime_type = 'image/png'
                    elif ext in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif ext in ['.gif']:
                        mime_type = 'image/gif'
                    elif ext in ['.webp']:
                        mime_type = 'image/webp'
                    else:
                        mime_type = 'image/png'  # default
                    
                    image_contents.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{mime_type};base64,{img_base64}'
                        }
                    })
            except Exception as e:
                return {
                    'success': False,
                    'content': '',
                    'error': f'Failed to read image {img_path}: {str(e)}'
                }
        
        # Build messages with images
        messages = []
        if system_message:
            messages.append({'role': 'system', 'content': system_message})
        
        # Create user message with text and images
        user_content = [{'type': 'text', 'text': prompt}]
        user_content.extend(image_contents)
        messages.append({'role': 'user', 'content': user_content})
        
        payload = {
            'messages': messages,
            'max_completion_tokens': 2000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        # Handle model-specific parameter restrictions
        if response.status_code == 400:
            try:
                error_data = response.json()
                error_msg = str(error_data.get('error', {}).get('message', '')).lower()
                
                # Handle max_completion_tokens restriction
                if 'max_completion_tokens' in error_msg and 'not supported' in error_msg:
                    payload.pop('max_completion_tokens', None)
                    payload['max_tokens'] = 2000
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
            except:
                pass
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return {
                'success': True,
                'content': content,
                'error': ''
            }
        else:
            return {
                'success': False,
                'content': '',
                'error': f'Azure Vision error: {response.status_code} - {response.text}'
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


def _sanitize_azure_endpoint(raw_endpoint: str) -> str:
    """Return base Azure endpoint without extra path or query."""
    if not raw_endpoint:
        return ''
    raw = raw_endpoint.strip().rstrip('/')
    try:
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return raw


def sanitize_image_prompt(prompt: str) -> str:
    """Sanitize image prompt to avoid Azure moderation blocks by replacing potentially problematic words."""
    # Replace words that might trigger moderation with safer alternatives
    replacements = {
        # Color-related (often flagged when combined with certain contexts)
        'black-glass': 'dark-glass',
        'black wires': 'dark wires',
        'black-and-blue': 'deep blue',
        'black wires sleep': 'dark wires rest',
        'black wires': 'dark wires',
        'black-': 'dark-',
        ' black ': ' dark ',
        ' black,': ' dark,',
        ' black.': ' dark.',
        
        # Potentially violent/forceful language
        'compressing inward': 'contracting inward',
        'bending under invisible force': 'curving subtly',
        'bending under': 'curving under',
        'compressing': 'contracting',
        'bending': 'curving',
        'under invisible force': 'subtly',
        'under force': 'subtly',
        
        # Religious content (sometimes flagged)
        'praying': 'pleading',
        'cathedral-like': 'temple-like',
        'cathedral': 'temple',
        
        # Other potentially problematic terms
        'void': 'empty space',
        'deep void': 'vast empty space',
        'the void': 'empty space',
        
        # Fear-related (can be flagged)
        'fear the future': 'worry about the future',
        'fear': 'concern',
    }
    
    sanitized = prompt
    # Apply replacements in order (longer phrases first to avoid partial matches)
    for old, new in sorted(replacements.items(), key=lambda x: -len(x[0])):
        sanitized = sanitized.replace(old, new)
    
    return sanitized


def sanitize_video_prompt(prompt: str, style: str = 'Realism') -> str:
    """Sanitize video prompt based on Video Style to avoid surreal/morphing artifacts.
    Realism: full replacements. Surrealism: passthrough. Artistic/Dreamlike/Cinematic: light."""
    if not prompt:
        return prompt
    s = (style or 'Realism').strip()
    if s == 'Surrealism':
        return prompt
    # Full replacements for Realism
    full_replacements = {
        'dissolve into': 'fade into',
        'dissolving into': 'fading into',
        'dissolves into': 'fades into',
        'melts into': 'blends into',
        'melt into': 'blend into',
        'like lines of fate': '',
        'like extinguished stars': '',
        'empty frame holds': 'static shot, empty composition',
        'cut on beat': 'hard cut',
    }
    # Light replacements for Artistic, Dreamlike, Cinematic (only incomplete/problematic)
    light_replacements = {
        'empty frame holds': 'static shot, empty composition',
    }
    if s == 'Realism':
        replacements = full_replacements
    else:
        replacements = light_replacements
    sanitized = prompt
    for old, new in sorted(replacements.items(), key=lambda x: -len(x[0])):
        if old:
            sanitized = sanitized.replace(old, new if new else ' ')
    sanitized = re.sub(r' +', ' ', sanitized)
    return sanitized


def call_azure_image(config: dict, prompt: str, size: str = '1024x1024', profile: str = 'image_gen', quality: str = 'medium', output_format: str = 'png', output_compression: int = 100) -> dict:
    """Call Azure OpenAI Images API to generate an image from a prompt.
    
    Args:
        config: Configuration dictionary
        prompt: Text prompt for image generation
        size: Image size (e.g., '1024x1024')
        profile: Profile name from config
        quality: Image quality ('standard' or 'hd')
        output_format: Output format ('png' or 'jpeg')
        output_compression: Compression level (0-100)
    """
    # Sanitize prompt to avoid moderation blocks
    prompt = sanitize_image_prompt(prompt)
    try:
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {
                'success': False,
                'image_bytes': b'',
                'error': f'Profile "{profile}" not found in configuration.'
            }

        profile_config = profiles[profile]
        endpoint_raw = profile_config.get('endpoint', '')
        endpoint = _sanitize_azure_endpoint(endpoint_raw)
        deployment = profile_config.get('deployment', '')
        api_version = profile_config.get('api_version', '2024-02-15-preview')
        subscription_key = profile_config.get('subscription_key', '')

        if not all([endpoint, deployment, subscription_key]):
            return {
                'success': False,
                'image_bytes': b'',
                'error': f'Missing Azure Image configuration for profile "{profile}". Please configure settings.'
            }

        url = f"{endpoint}/openai/deployments/{deployment}/images/generations?api-version={api_version}"

        headers = {
            'Content-Type': 'application/json',
            'api-key': subscription_key
        }

        payload = {
            'prompt': prompt,
            'size': size,
            'quality': quality,
            'output_compression': output_compression,
            'output_format': output_format,
            'n': 1
        }
        
        # Note: Azure DALL-E API doesn't support reference images directly
        # Reference images are handled by analyzing them first and including the description in the prompt

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', [])
            if not data:
                return {'success': False, 'image_bytes': b'', 'error': 'No image data returned.'}
            b64 = data[0].get('b64_json', '')
            if not b64:
                return {'success': False, 'image_bytes': b'', 'error': 'Missing b64_json in response.'}
            img_bytes = base64.b64decode(b64)
            return {'success': True, 'image_bytes': img_bytes, 'error': ''}

        if response.status_code == 404 and api_version != '2025-04-01-preview':
            fallback_version = '2025-04-01-preview'
            fallback_url = f"{endpoint}/openai/deployments/{deployment}/images/generations?api-version={fallback_version}"
            response_fb = requests.post(fallback_url, headers=headers, json=payload, timeout=60)
            if response_fb.status_code == 200:
                result = response_fb.json()
                data = result.get('data', [])
                if not data:
                    return {'success': False, 'image_bytes': b'', 'error': 'No image data returned.'}
                b64 = data[0].get('b64_json', '')
                if not b64:
                    return {'success': False, 'image_bytes': b'', 'error': 'Missing b64_json in response.'}
                img_bytes = base64.b64decode(b64)
                return {'success': True, 'image_bytes': img_bytes, 'error': ''}

        return {
            'success': False,
            'image_bytes': b'',
            'error': f'Azure Images error: {response.status_code} - {response.text}'
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'image_bytes': b'',
            'error': f'Request error: {e}'
        }
    except Exception as e:
        return {
            'success': False,
            'image_bytes': b'',
            'error': f'Unexpected error: {e}'
        }


class ExtraCommandsDialog(tk.Toplevel):
    """Dialog for entering extra commands to inject into the prompt."""
    
    def __init__(self, parent, current_prompt: str = ''):
        super().__init__(parent)
        self.title('Inject Extra Commands')
        self.geometry('700x450')
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self.create_widgets(current_prompt)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.extra_commands_text.focus_set()
    
    def create_widgets(self, current_prompt: str):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Enter extra commands to inject into the prompt:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(main_frame, text='Current prompt:', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        prompt_preview = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 8))
        prompt_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        prompt_preview.config(state=tk.NORMAL)
        prompt_preview.insert('1.0', current_prompt[:500] + ('...' if len(current_prompt) > 500 else ''))
        prompt_preview.config(state=tk.DISABLED)
        
        ttk.Label(main_frame, text='Extra commands (leave empty to use prompt as-is):', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        self.extra_commands_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, font=('Consolas', 9))
        self.extra_commands_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='OK', command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        self.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def ok_clicked(self):
        extra_commands = self.extra_commands_text.get('1.0', tk.END).strip()
        self.result = extra_commands if extra_commands else ''
        self.destroy()
    
    def cancel_clicked(self):
        self.result = None
        self.destroy()


class AIPromptDialog(tk.Toplevel):
    """Dialog for AI prompt enhancement with extra instructions."""
    
    def __init__(self, parent, field_name: str, current_value: str = ''):
        super().__init__(parent)
        self.title(f'AI Enhance: {field_name}')
        self.geometry('600x400')
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self.create_widgets(field_name, current_value)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.extra_instructions_text.focus_set()
    
    def create_widgets(self, field_name: str, current_value: str):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f'Enhance "{field_name}" with AI:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(main_frame, text='Current value:', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        current_preview = scrolledtext.ScrolledText(main_frame, height=3, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 8))
        current_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        current_preview.config(state=tk.NORMAL)
        current_preview.insert('1.0', current_value[:300] + ('...' if len(current_value) > 300 else ''))
        current_preview.config(state=tk.DISABLED)
        
        ttk.Label(main_frame, text='Additional instructions (optional):', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        self.extra_instructions_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, font=('Consolas', 9))
        self.extra_instructions_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='Generate', command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        self.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def ok_clicked(self):
        extra_instructions = self.extra_instructions_text.get('1.0', tk.END).strip()
        self.result = extra_instructions
        self.destroy()
    
    def cancel_clicked(self):
        self.result = None
        self.destroy()


class PromptGenerationIdeasDialog(tk.Toplevel):
    """Dialog for adding optional ideas before generating a cover/video prompt."""

    def __init__(self, parent, prompt_type: str, context: str = 'Song'):
        super().__init__(parent)
        self.prompt_type = prompt_type
        self.context = context
        self.title(f'Generate {prompt_type} Prompt')
        self.geometry('600x380')
        self.transient(parent)
        self.grab_set()

        self.result = None

        self.create_widgets()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        self.ideas_text.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_frame, text=f'Generate {self.prompt_type} Prompt ({self.context})', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(main_frame, text='Add basic ideas for the cover/video (optional):', font=('TkDefaultFont', 8, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        help_text = '(e.g., "dark and moody", "include a road", "noir aesthetic", "cinematic lighting")'
        ttk.Label(main_frame, text=help_text, font=('TkDefaultFont', 7), foreground='gray').pack(anchor=tk.W, pady=(0, 5))
        self.ideas_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD, font=('Consolas', 9))
        self.ideas_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='Generate', command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        self.bind('<Escape>', lambda e: self.cancel_clicked())

    def ok_clicked(self):
        self.result = self.ideas_text.get('1.0', tk.END).strip()
        self.destroy()

    def cancel_clicked(self):
        self.result = None
        self.destroy()


class PromptImprovementDialog(tk.Toplevel):
    """Dialog for requesting prompt improvements."""
    
    def __init__(self, parent, prompt_type: str, current_prompt: str = ''):
        super().__init__(parent)
        self.prompt_type = prompt_type
        self.title(f'Improve {prompt_type} Prompt')
        self.geometry('700x500')
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self.create_widgets(prompt_type, current_prompt)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.improvement_request_text.focus_set()
    
    def create_widgets(self, prompt_type: str, current_prompt: str):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f'Improve {prompt_type} Prompt', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(main_frame, text='Current prompt:', font=('TkDefaultFont', 8, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        current_preview = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 8))
        current_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        current_preview.config(state=tk.NORMAL)
        current_preview.insert('1.0', current_prompt)
        current_preview.config(state=tk.DISABLED)
        
        ttk.Label(main_frame, text='What changes would you like to make?', font=('TkDefaultFont', 8, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        help_text = '(e.g., "Make it more dramatic", "Add more color", "Change the mood to be darker")'
        if prompt_type == 'Album Cover':
            help_text += ' (Optional: Leave empty to automatically mix song cover prompts)'
        ttk.Label(main_frame, text=help_text, 
                 font=('TkDefaultFont', 7), foreground='gray').pack(anchor=tk.W, pady=(0, 5))
        self.improvement_request_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD, font=('Consolas', 9))
        self.improvement_request_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='Improve', command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        self.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def ok_clicked(self):
        improvement_request = self.improvement_request_text.get('1.0', tk.END).strip()
        # Allow empty input for Album Cover (will mix song cover prompts automatically)
        if not improvement_request and self.prompt_type != 'Album Cover':
            messagebox.showwarning('Warning', 'Please enter what changes you would like to make.')
            return
        self.result = improvement_request
        self.destroy()
    
    def cancel_clicked(self):
        self.result = None
        self.destroy()


class ImprovedPromptResultDialog(tk.Toplevel):
    """Dialog to show improved prompt and ask if user wants to save it."""
    
    def __init__(self, parent, improved_prompt: str, original_prompt: str = ''):
        super().__init__(parent)
        self.title('Improved Prompt')
        self.geometry('800x600')
        self.transient(parent)
        self.grab_set()
        
        self.result = False  # True = save, False = cancel
        
        self.create_widgets(improved_prompt, original_prompt)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self, improved_prompt: str, original_prompt: str = ''):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Improved Prompt Generated', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        if original_prompt:
            ttk.Label(main_frame, text='Original prompt:', font=('TkDefaultFont', 8, 'bold')).pack(anchor=tk.W, pady=(5, 2))
            original_preview = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 8))
            original_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            original_preview.config(state=tk.NORMAL)
            original_preview.insert('1.0', original_prompt)
            original_preview.config(state=tk.DISABLED)
        
        ttk.Label(main_frame, text='Improved prompt:', font=('TkDefaultFont', 8, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        self.improved_text = scrolledtext.ScrolledText(main_frame, height=12, wrap=tk.WORD, font=('Consolas', 9))
        self.improved_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.improved_text.insert('1.0', improved_prompt)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='Save', command=self.save_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        self.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def save_clicked(self):
        self.result = True
        self.destroy()
    
    def cancel_clicked(self):
        self.result = False
        self.destroy()


class StyleSelectionDialog(tk.Toplevel):
    """Popup to select one or more styles from the style library."""

    def __init__(self, parent, styles: list[dict], initial_text: str = ''):
        super().__init__(parent)
        self.title('Select Styles')
        self.geometry('620x520')
        self.transient(parent)
        self.grab_set()

        # Always keep styles sorted by style name (case-insensitive)
        self.styles = self._sort_styles(styles or [])
        self.filtered_styles = self.styles
        self.current_items = []
        self.selected_style = None
        self.status_var = tk.StringVar(value=f'{len(self.styles)} styles available')
        self.search_var = tk.StringVar()

        self.initial_selected = {
            s.strip().lower()
            for s in re.split(r'[,\n]+', initial_text)
            if s.strip()
        }

        self.create_widgets()
        self.apply_filter()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(search_frame, text='Search styles (style/artist/decade):').pack(side=tk.LEFT)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.search_var.trace_add('write', lambda *_: self.apply_filter())

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, exportselection=False)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind('<Double-Button-1>', lambda _evt: self.on_ok())

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(status_frame, textvariable=self.status_var, foreground='gray').pack(anchor=tk.W)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text='OK', command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def apply_filter(self):
        query = self.search_var.get().strip().lower()
        if query:
            self.filtered_styles = [
                row for row in self.styles
                if query in (row.get('style', '').lower())
                or query in (row.get('artists', '').lower())
                or query in (row.get('decade', '').lower())
            ]
        else:
            self.filtered_styles = self.styles

        self.filtered_styles = self._sort_styles(self.filtered_styles)
        self.populate_list()

    def _sort_styles(self, styles: list[dict]) -> list[dict]:
        """Sort styles by name (case-insensitive) for consistent display."""
        return sorted(
            styles,
            key=lambda r: (r.get('style', '') or '').lower()
        )

    def populate_list(self):
        self.listbox.delete(0, tk.END)
        self.current_items = []

        for row in self.filtered_styles:
            style_name = (row.get('style') or '').strip()
            if not style_name:
                continue

            extras = []
            artists = (row.get('artists') or row.get('artist') or '').strip()
            if artists:
                extras.append(artists)
            decade = (row.get('decade') or '').strip()
            if decade:
                extras.append(decade)

            display = style_name
            if extras:
                display += f"  ({' | '.join(extras)})"

            self.listbox.insert(tk.END, display)
            self.current_items.append(style_name)

            if style_name.lower() in self.initial_selected:
                self.listbox.selection_set(tk.END)

        self.status_var.set(f'{len(self.filtered_styles)} styles available')

    def on_ok(self):
        indices = self.listbox.curselection()
        if indices:
            idx = indices[0]
            if 0 <= idx < len(self.current_items):
                self.selected_style = self.current_items[idx]
        self.destroy()

    def on_cancel(self):
        self.selected_style = None
        self.destroy()


class ImagePreviewDialog(tk.Toplevel):
    """Dialog to preview a newly generated image and ask if user wants to overwrite existing one."""
    def __init__(self, parent, new_image_path: str, existing_image_path: str, scene_num: str):
        super().__init__(parent)
        self.title(f'Scene {scene_num} - Preview New Image')
        self.geometry('800x700')
        self.result = None  # True = overwrite, False = keep existing, None = cancelled
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f'+{x}+{y}')
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f'Scene {scene_num} - New Image Preview', font=('TkDefaultFont', 12, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Info label
        info_label = ttk.Label(main_frame, 
                               text=f'An image already exists for Scene {scene_num}.\nPreview the new image below and decide if you want to overwrite it.',
                               font=('TkDefaultFont', 9))
        info_label.pack(pady=(0, 10))
        
        # Image preview frame
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Load and display new image
        try:
            pil_image = Image.open(new_image_path)
            # Resize for display (max 600x600 while maintaining aspect ratio)
            max_size = 600
            width, height = pil_image.size
            if width > max_size or height > max_size:
                ratio = min(max_size / width, max_size / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(pil_image)
            image_label = ttk.Label(image_frame, image=photo)
            image_label.image = photo  # Keep a reference
            image_label.pack(pady=10)
        except Exception as e:
            error_label = ttk.Label(image_frame, text=f'Error loading image: {e}', foreground='red')
            error_label.pack(pady=10)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)
        
        ttk.Button(buttons_frame, text='Overwrite Existing', command=self.overwrite).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Keep Existing', command=self.keep_existing).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Cancel', command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Bind Escape key
        self.bind('<Escape>', lambda e: self.cancel())
    
    def overwrite(self):
        """User chose to overwrite existing image."""
        self.result = True
        self.destroy()
    
    def keep_existing(self):
        """User chose to keep existing image."""
        self.result = False
        self.destroy()
    
    def cancel(self):
        """User cancelled."""
        self.result = None
        self.destroy()


class ProgressDialog(tk.Toplevel):
    """Dialog for showing progress and allowing cancellation."""
    
    def __init__(self, parent, total_items: int, title: str = 'Progress'):
        super().__init__(parent)
        self.title(title)
        self.geometry('400x150')
        self.transient(parent)
        self.grab_set()
        
        self.total_items = total_items
        self.current_item = 0
        self.cancelled = False
        
        self.create_widgets()
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_label = ttk.Label(main_frame, text='Initializing...', font=('TkDefaultFont', 9))
        self.status_label.pack(pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100, length=350)
        self.progress_bar.pack(pady=10)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel).pack()
        
        self.protocol("WM_DELETE_WINDOW", self.cancel)
    
    def update_progress(self, current: int, status_text: str = ''):
        """Update progress bar and status text."""
        self.current_item = current
        progress = (current / self.total_items) * 100 if self.total_items > 0 else 0
        self.progress_var.set(progress)
        if status_text:
            self.status_label.config(text=status_text)
        self.update()
    
    def cancel(self):
        """Mark as cancelled."""
        self.cancelled = True
        self.status_label.config(text='Cancelling...')
        self.update()
    
    def is_cancelled(self):
        """Check if cancelled."""
        return self.cancelled


class BulkCoverDialog(tk.Toplevel):
    """Dialog for bulk cover generation settings."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Bulk Cover Generation')
        self.geometry('450x300')
        self.transient(parent)
        self.grab_set()
        
        self.result = None
        
        self.create_widgets()
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scope selection
        ttk.Label(main_frame, text='Scope:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        scope_frame = ttk.Frame(main_frame)
        scope_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.scope_var = tk.StringVar(value='current_album')
        ttk.Radiobutton(scope_frame, text='All songs from Persona', variable=self.scope_var, value='all_persona').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(scope_frame, text='Only songs from current Album', variable=self.scope_var, value='current_album').pack(anchor=tk.W, pady=2)
        
        # Format selection
        format_frame = ttk.Frame(main_frame)
        format_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(format_frame, text='Size:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.size_var = tk.StringVar(value='1:1 (1024x1024)')
        size_combo = ttk.Combobox(format_frame, textvariable=self.size_var,
                                  values=['1:1 (1024x1024)', '3:2 (1536x1024)', '16:9 (1792x1024)',
                                          '4:3 (1365x1024)', '2:3 (1024x1536)', '9:16 (1024x1792)', '21:9 (2048x1024)'],
                                  state='readonly', width=20)
        size_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 5))
        
        ttk.Label(format_frame, text='Format:', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.format_var = tk.StringVar(value='PNG')
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var,
                                    values=['PNG', 'JPEG'], state='readonly', width=20)
        format_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 5))
        
        # Overwrite option
        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text='Overwrite existing cover files', variable=self.overwrite_var).pack(anchor=tk.W, pady=(0, 5))
        # Include persona in cover (default on; applies when generating missing prompts in bulk)
        self.include_persona_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text='Include persona in cover', variable=self.include_persona_var).pack(anchor=tk.W, pady=(0, 15))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text='Cancel', command=self.cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text='Generate', command=self.ok).pack(side=tk.RIGHT)
        
        self.bind('<Return>', lambda e: self.ok())
        self.bind('<Escape>', lambda e: self.cancel())
    
    def ok(self):
        """Confirm and return result."""
        self.result = {
            'scope': self.scope_var.get(),
            'size': self.size_var.get(),
            'format': self.format_var.get(),
            'overwrite': self.overwrite_var.get(),
            'include_persona': self.include_persona_var.get()
        }
        self.destroy()
    
    def cancel(self):
        """Cancel dialog."""
        self.result = None
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Dialog for editing configuration settings."""
    
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title('Settings')
        self.geometry('600x500')
        self.transient(parent)
        self.grab_set()
        
        self.config = config.copy()
        self.result = None
        
        self.profile_vars = {}
        
        self.create_widgets()
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        general_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(general_frame, text='General')
        
        general_data = self.config.get('general', {})
        self.general_vars = {}
        
        # Base Path
        ttk.Label(general_frame, text='Base Path:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(5, 2), columnspan=3)
        ttk.Label(general_frame, text='Project root directory (leave empty to auto-detect):', font=('TkDefaultFont', 8)).grid(row=1, column=0, sticky=tk.W, pady=5, padx=(10, 0))
        self.general_vars['base_path'] = tk.StringVar(value=general_data.get('base_path', ''))
        base_path_entry = ttk.Entry(general_frame, textvariable=self.general_vars['base_path'], width=40)
        base_path_entry.grid(row=1, column=1, pady=5, padx=5, sticky=tk.W)
        ttk.Button(general_frame, text='Browse...', command=self.browse_base_path).grid(row=1, column=2, pady=5, padx=5)
        
        ttk.Label(general_frame, text='Personas Directory:', font=('TkDefaultFont', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=(15, 2), columnspan=3)
        ttk.Label(general_frame, text='Path:', font=('TkDefaultFont', 8)).grid(row=3, column=0, sticky=tk.W, pady=5, padx=(10, 0))
        self.general_vars['personas_path'] = tk.StringVar(value=general_data.get('personas_path', 'AI/Personas'))
        path_entry = ttk.Entry(general_frame, textvariable=self.general_vars['personas_path'], width=40)
        path_entry.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        ttk.Button(general_frame, text='Browse...', command=self.browse_personas_path).grid(row=3, column=2, pady=5, padx=5)

        ttk.Label(general_frame, text='Styles CSV (for style picker):', font=('TkDefaultFont', 9, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=(15, 2), columnspan=3)
        ttk.Label(general_frame, text='Path:', font=('TkDefaultFont', 8)).grid(row=5, column=0, sticky=tk.W, pady=5, padx=(10, 0))
        self.general_vars['styles_csv_path'] = tk.StringVar(value=general_data.get('styles_csv_path', 'AI/suno/suno_sound_styles.csv'))
        styles_entry = ttk.Entry(general_frame, textvariable=self.general_vars['styles_csv_path'], width=40)
        styles_entry.grid(row=5, column=1, pady=5, padx=5, sticky=tk.W)
        ttk.Button(general_frame, text='Browse...', command=self.browse_styles_csv).grid(row=5, column=2, pady=5, padx=5)

        ttk.Label(general_frame, text='Load Styles from File (CSV/CSS in folder):', font=('TkDefaultFont', 9, 'bold')).grid(row=6, column=0, sticky=tk.W, pady=(15, 2), columnspan=3)
        ttk.Label(general_frame, text='Folder:', font=('TkDefaultFont', 8)).grid(row=7, column=0, sticky=tk.W, pady=5, padx=(10, 0))
        self.general_vars['styles_import_path'] = tk.StringVar(value=general_data.get('styles_import_path', 'D:/AI/suno'))
        ttk.Entry(general_frame, textvariable=self.general_vars['styles_import_path'], width=40).grid(row=7, column=1, pady=5, padx=5, sticky=tk.W)
        ttk.Label(general_frame, text='Base name (filter):', font=('TkDefaultFont', 8)).grid(row=8, column=0, sticky=tk.W, pady=5, padx=(10, 0))
        self.general_vars['styles_import_base_name'] = tk.StringVar(value=general_data.get('styles_import_base_name', ''))
        ttk.Entry(general_frame, textvariable=self.general_vars['styles_import_base_name'], width=40).grid(row=8, column=1, pady=5, padx=5, sticky=tk.W)
        
        profiles = self.config.get('profiles', {})
        
        # Ensure default profiles exist
        default_profiles = ['text', 'image_gen', 'video_gen', 'transcribe', 'speech']
        for profile_name in default_profiles:
            if profile_name not in profiles:
                profiles[profile_name] = {}
        
        self.profile_vars = {}
        self.profile_order = list(profiles.keys())  # Preserve order
        
        # Create profile management frame
        profiles_management_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(profiles_management_frame, text='Profile Management')
        
        ttk.Label(profiles_management_frame, text='Manage Profiles:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10), columnspan=3)
        
        # Profile list with scrollbar
        list_frame = ttk.Frame(profiles_management_frame)
        list_frame.grid(row=1, column=0, columnspan=3, sticky='nsew', pady=5)
        
        profile_listbox_frame = ttk.Frame(list_frame)
        profile_listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(profile_listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.profile_listbox = tk.Listbox(profile_listbox_frame, yscrollcommand=scrollbar.set, height=8)
        self.profile_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.profile_listbox.yview)
        
        # Populate listbox
        for profile_name in self.profile_order:
            self.profile_listbox.insert(tk.END, profile_name)
        
        # Buttons for profile management
        btn_frame_manage = ttk.Frame(profiles_management_frame)
        btn_frame_manage.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(btn_frame_manage, text='Add Profile', command=self.add_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_manage, text='Remove Profile', command=self.remove_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_manage, text='Rename Profile', command=self.rename_profile).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(profiles_management_frame, text='Note: Core profiles (text, image_gen, video_gen, transcribe, speech) cannot be removed.', 
                 font=('TkDefaultFont', 8), foreground='gray').grid(row=3, column=0, columnspan=3, pady=5)
        
        # Create tabs for each profile
        for profile_name in self.profile_order:
            profile_data = profiles.get(profile_name, {})
            self.profile_vars[profile_name] = {}
            
            profile_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(profile_frame, text=profile_name.replace('_', ' ').title())
            
            # Checkbox for image generation profile
            self.profile_vars[profile_name]['is_image_profile'] = tk.BooleanVar(value=profile_data.get('is_image_profile', profile_name == 'image_gen' or 'image' in profile_name.lower() or 'dall' in profile_data.get('model_name', '').lower()))
            ttk.Checkbutton(profile_frame, text='Use for Image Generation', 
                          variable=self.profile_vars[profile_name]['is_image_profile']).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            
            ttk.Label(profile_frame, text='Endpoint:').grid(row=1, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['endpoint'] = tk.StringVar(value=profile_data.get('endpoint', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['endpoint'], width=50).grid(row=1, column=1, pady=5, padx=5)
            
            ttk.Label(profile_frame, text='Model Name:').grid(row=2, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['model_name'] = tk.StringVar(value=profile_data.get('model_name', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['model_name'], width=50).grid(row=2, column=1, pady=5, padx=5)
            
            ttk.Label(profile_frame, text='Deployment:').grid(row=3, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['deployment'] = tk.StringVar(value=profile_data.get('deployment', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['deployment'], width=50).grid(row=3, column=1, pady=5, padx=5)
            
            ttk.Label(profile_frame, text='Subscription Key:').grid(row=4, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['subscription_key'] = tk.StringVar(value=profile_data.get('subscription_key', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['subscription_key'], width=50, show='*').grid(row=4, column=1, pady=5, padx=5)
            
            ttk.Label(profile_frame, text='API Version:').grid(row=5, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['api_version'] = tk.StringVar(value=profile_data.get('api_version', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['api_version'], width=50).grid(row=5, column=1, pady=5, padx=5)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text='Save', command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def browse_base_path(self):
        """Browse for a base path directory."""
        current = self.general_vars['base_path'].get()
        initial_dir = current if current and os.path.exists(current) else os.getcwd()
        
        path = filedialog.askdirectory(
            title='Select Base Path (Project Root)',
            initialdir=initial_dir
        )
        if path:
            self.general_vars['base_path'].set(path)
    
    def browse_personas_path(self):
        project_root = get_project_root(self.config)
        initial_dir = os.path.join(project_root, 'AI', 'Personas')
        
        if not os.path.exists(initial_dir):
            initial_dir = project_root
        
        path = filedialog.askdirectory(
            title='Select Personas Directory',
            initialdir=initial_dir
        )
        if path:
            # Store relative path if within project
            try:
                rel_path = os.path.relpath(path, project_root)
                if not rel_path.startswith('..'):
                    self.general_vars['personas_path'].set(rel_path.replace('\\', '/'))
                else:
                    self.general_vars['personas_path'].set(path)
            except:
                self.general_vars['personas_path'].set(path)

    def browse_styles_csv(self):
        project_root = get_project_root(self.config)
        initial_dir = os.path.join(project_root, 'AI', 'suno')

        if not os.path.exists(initial_dir):
            initial_dir = project_root

        path = filedialog.askopenfilename(
            title='Select styles CSV',
            initialdir=initial_dir,
            filetypes=[('CSV Files', '*.csv'), ('All Files', '*.*')]
        )
        if path:
            try:
                rel_path = os.path.relpath(path, project_root)
                if not rel_path.startswith('..'):
                    self.general_vars['styles_csv_path'].set(rel_path.replace('\\', '/'))
                else:
                    self.general_vars['styles_csv_path'].set(path)
            except:
                self.general_vars['styles_csv_path'].set(path)
    
    def add_profile(self):
        """Add a new profile."""
        profile_name = simpledialog.askstring('Add Profile', 'Enter profile name:', initialvalue='')
        if profile_name and profile_name.strip():
            profile_name = profile_name.strip()
            if profile_name in self.profile_vars:
                messagebox.showwarning('Warning', f'Profile "{profile_name}" already exists.')
                return
            
            # Add to profile_vars
            self.profile_vars[profile_name] = {
                'is_image_profile': tk.BooleanVar(value=False),
                'endpoint': tk.StringVar(value=''),
                'model_name': tk.StringVar(value=''),
                'deployment': tk.StringVar(value=''),
                'subscription_key': tk.StringVar(value=''),
                'api_version': tk.StringVar(value='2024-02-15-preview')
            }
            
            # Add to listbox
            self.profile_listbox.insert(tk.END, profile_name)
            self.profile_order.append(profile_name)
            
            # Add tab to notebook
            if hasattr(self, 'notebook'):
                profile_frame = ttk.Frame(self.notebook, padding=10)
                self.notebook.add(profile_frame, text=profile_name.replace('_', ' ').title())
                
                # Checkbox for image generation profile
                ttk.Checkbutton(profile_frame, text='Use for Image Generation', 
                              variable=self.profile_vars[profile_name]['is_image_profile']).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
                
                ttk.Label(profile_frame, text='Endpoint:').grid(row=1, column=0, sticky=tk.W, pady=5)
                ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['endpoint'], width=50).grid(row=1, column=1, pady=5, padx=5)
                
                ttk.Label(profile_frame, text='Model Name:').grid(row=2, column=0, sticky=tk.W, pady=5)
                ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['model_name'], width=50).grid(row=2, column=1, pady=5, padx=5)
                
                ttk.Label(profile_frame, text='Deployment:').grid(row=3, column=0, sticky=tk.W, pady=5)
                ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['deployment'], width=50).grid(row=3, column=1, pady=5, padx=5)
                
                ttk.Label(profile_frame, text='Subscription Key:').grid(row=4, column=0, sticky=tk.W, pady=5)
                ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['subscription_key'], width=50, show='*').grid(row=4, column=1, pady=5, padx=5)
                
                ttk.Label(profile_frame, text='API Version:').grid(row=5, column=0, sticky=tk.W, pady=5)
                ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['api_version'], width=50).grid(row=5, column=1, pady=5, padx=5)
    
    def remove_profile(self):
        """Remove selected profile."""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a profile to remove.')
            return
        
        profile_name = self.profile_listbox.get(selection[0])
        core_profiles = ['text', 'image_gen', 'video_gen', 'transcribe', 'speech']
        
        if profile_name in core_profiles:
            messagebox.showwarning('Warning', f'Cannot remove core profile "{profile_name}".')
            return
        
        if messagebox.askyesno('Confirm', f'Remove profile "{profile_name}"?'):
            # Remove from listbox
            self.profile_listbox.delete(selection[0])
            # Remove from profile_vars
            if profile_name in self.profile_vars:
                del self.profile_vars[profile_name]
            # Remove from order
            if profile_name in self.profile_order:
                self.profile_order.remove(profile_name)
            
            # Remove tab from notebook
            if hasattr(self, 'notebook'):
                for tab_id in self.notebook.tabs():
                    if self.notebook.tab(tab_id, 'text').replace(' ', '_').lower() == profile_name.replace('_', ' ').lower():
                        self.notebook.forget(tab_id)
                        break
    
    def rename_profile(self):
        """Rename selected profile."""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a profile to rename.')
            return
        
        old_name = self.profile_listbox.get(selection[0])
        core_profiles = ['text', 'image_gen', 'video_gen', 'transcribe', 'speech']
        
        if old_name in core_profiles:
            messagebox.showwarning('Warning', f'Cannot rename core profile "{old_name}".')
            return
        
        new_name = simpledialog.askstring('Rename Profile', f'Enter new name for "{old_name}":', initialvalue=old_name)
        if new_name and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()
            if new_name in self.profile_vars:
                messagebox.showwarning('Warning', f'Profile "{new_name}" already exists.')
                return
            
            # Update profile_vars
            if old_name in self.profile_vars:
                self.profile_vars[new_name] = self.profile_vars.pop(old_name)
            
            # Update listbox
            self.profile_listbox.delete(selection[0])
            self.profile_listbox.insert(selection[0], new_name)
            
            # Update order
            if old_name in self.profile_order:
                idx = self.profile_order.index(old_name)
                self.profile_order[idx] = new_name
            
            # Update notebook tab
            if hasattr(self, 'notebook'):
                for tab_id in self.notebook.tabs():
                    if self.notebook.tab(tab_id, 'text').replace(' ', '_').lower() == old_name.replace('_', ' ').lower():
                        self.notebook.tab(tab_id, text=new_name.replace('_', ' ').title())
                        break
    
    def save_settings(self):
        general = {
            'base_path': self.general_vars['base_path'].get(),
            'personas_path': self.general_vars['personas_path'].get(),
            'default_save_path': self.config.get('general', {}).get('default_save_path', ''),
            'styles_csv_path': self.general_vars['styles_csv_path'].get(),
            'styles_import_path': self.general_vars['styles_import_path'].get(),
            'styles_import_base_name': self.general_vars['styles_import_base_name'].get()
        }
        
        profiles = {}
        for profile_name, vars_dict in self.profile_vars.items():
            profiles[profile_name] = {
                'is_image_profile': vars_dict.get('is_image_profile', tk.BooleanVar(value=False)).get(),
                'endpoint': vars_dict['endpoint'].get(),
                'model_name': vars_dict['model_name'].get(),
                'deployment': vars_dict['deployment'].get(),
                'subscription_key': vars_dict['subscription_key'].get(),
                'api_version': vars_dict['api_version'].get()
            }
        
        self.config['general'] = general
        self.config['profiles'] = profiles
        self.result = self.config
        self.destroy()


def call_azure_audio_transcription(config: dict, audio_file_path: str, profile: str = 'text', language: str = None, response_format: str = 'verbose_json', prompt: str = None) -> dict:
    """Call Azure OpenAI Whisper API to transcribe audio with timestamps.
    
    Args:
        config: Configuration dictionary
        audio_file_path: Path to audio file (MP3, WAV, etc.)
        profile: Profile name to use (default 'text')
        language: Optional language code (e.g., 'en', 'de')
        response_format: Response format - 'verbose_json' for timestamps, 'json' for simple, 'text' for plain text
        prompt: Optional prompt to guide transcription (e.g., style or vocabulary hints)
    
    Returns:
        Dictionary with 'success', 'content' (transcription text), 'segments' (with timestamps), 'error'
    """
    try:
        if not os.path.exists(audio_file_path):
            return {
                'success': False,
                'content': '',
                'segments': [],
                'error': f'Audio file not found: {audio_file_path}'
            }
        
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {
                'success': False,
                'content': '',
                'segments': [],
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
                'segments': [],
                'error': f'Missing Azure AI configuration for profile "{profile}". Please configure settings.'
            }
        
        # Azure OpenAI Whisper API endpoint
        # Note: Azure OpenAI Whisper uses /openai/deployments/{deployment}/audio/transcriptions
        url = f"{endpoint}/openai/deployments/{deployment}/audio/transcriptions?api-version={api_version}"
        
        # Debug logging
        print(f'[DEBUG] Transcription URL: {url}')
        print(f'[DEBUG] Endpoint: {endpoint}')
        print(f'[DEBUG] Deployment: {deployment}')
        print(f'[DEBUG] API Version: {api_version}')
        print(f'[DEBUG] Audio file: {audio_file_path}')
        
        headers = {
            'api-key': subscription_key
        }
        
        # Prepare multipart form data
        files = {
            'file': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/mpeg')
        }
        
        # Check if model is gpt-4o-transcribe (uses different API format)
        is_gpt4o_transcribe = 'gpt-4o' in deployment.lower() and 'transcribe' in deployment.lower()
        
        if is_gpt4o_transcribe:
            # gpt-4o-transcribe uses 'json' format but still supports timestamp_granularities
            actual_response_format = 'json'
            print(f'[DEBUG] Using gpt-4o-transcribe model - requesting word-level timestamps')
        else:
            # Standard Whisper models use verbose_json for timestamps
            actual_response_format = 'verbose_json' if response_format == 'verbose_json' else 'json'
        
        # Build form data as list of tuples to support multiple values for same key
        data = [
            ('response_format', actual_response_format)
        ]
        
        # Request word-level timestamps for all models that support it
        # gpt-4o-transcribe supports timestamp_granularities with 'word' and 'segment'
        if is_gpt4o_transcribe or actual_response_format == 'verbose_json':
            # Request both word and segment level timestamps
            # Send as separate form fields for proper multipart encoding
            data.append(('timestamp_granularities[]', 'word'))
            data.append(('timestamp_granularities[]', 'segment'))
        else:
            data.append(('timestamp_granularities[]', 'segment'))
        
        if language:
            data.append(('language', language))
        if prompt:
            data.append(('prompt', prompt))
        
        print(f'[DEBUG] Request data: {data}')
        print(f'[DEBUG] Actual response format: {actual_response_format}')
        print(f'[DEBUG] File size: {os.path.getsize(audio_file_path)} bytes')
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=300)
        files['file'][1].close()  # Close the file
        
        print(f'[DEBUG] Response status: {response.status_code}')
        print(f'[DEBUG] Response headers: {dict(response.headers)}')
        
        if response.status_code == 200:
            result = response.json()
            print(f'[DEBUG] Response JSON keys: {list(result.keys()) if isinstance(result, dict) else "Not a dict"}')
            
            # Extract common fields - both verbose_json and gpt-4o-transcribe json can have these
            text = result.get('text', '') if isinstance(result, dict) else str(result)
            segments = result.get('segments', []) if isinstance(result, dict) else []
            words = result.get('words', []) if isinstance(result, dict) else []
            
            print(f'[DEBUG] Found {len(words)} words, {len(segments)} segments')
            
            # Format lyrics with timestamps
            lyrics_lines = []
            if words:
                # Use word-level timestamps for precise timing
                for word_info in words:
                    word = word_info.get('word', '')
                    start = word_info.get('start', 0)
                    
                    # Format as [MM:SS.mmm] word
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    milliseconds = int((start % 1) * 1000)
                    timestamp = f"[{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"
                    lyrics_lines.append(f"{timestamp} {word}")
            elif segments:
                # Fallback to segment-level timestamps
                for segment in segments:
                    text_seg = segment.get('text', '').strip()
                    start = segment.get('start', 0)
                    if text_seg:
                        minutes = int(start // 60)
                        seconds = int(start % 60)
                        milliseconds = int((start % 1) * 1000)
                        timestamp = f"[{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"
                        lyrics_lines.append(f"{timestamp} {text_seg}")
            
            formatted_lyrics = '\n'.join(lyrics_lines) if lyrics_lines else text
            
            return {
                'success': True,
                'content': formatted_lyrics,
                'text': text,
                'segments': segments,
                'words': words,
                'raw_json': result if isinstance(result, dict) else {},
                'error': ''
            }
        else:
            error_msg = f'API error {response.status_code}'
            try:
                error_json = response.json()
                print(f'[DEBUG] Error response JSON: {error_json}')
                error_detail = error_json.get('error', {})
                if isinstance(error_detail, dict):
                    error_msg = f'{error_msg}: {error_detail.get("message", error_detail.get("code", str(error_detail)))}'
                else:
                    error_msg = f'{error_msg}: {str(error_detail)}'
            except:
                error_text = response.text[:500]
                print(f'[DEBUG] Error response text: {error_text}')
                error_msg = f'{error_msg}: {error_text}'
            
            return {
                'success': False,
                'content': '',
                'segments': [],
                'error': error_msg
            }
    
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'content': '',
            'segments': [],
            'error': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'content': '',
            'segments': [],
            'error': f'Unexpected error: {str(e)}'
        }


def call_azure_speech_transcription(config: dict, audio_file_path: str, profile: str = 'speech', language: str = 'en-US') -> dict:
    """Call Azure Cognitive Services Speech-to-Text API to transcribe audio with word-level timestamps.
    
    This uses the Azure Speech Services API (not OpenAI Whisper) which provides better
    accuracy for music/vocals and word-level timestamps.
    
    Args:
        config: Configuration dictionary
        audio_file_path: Path to audio file (WAV, MP3, etc.)
        profile: Profile name to use (default 'speech')
        language: Language code (e.g., 'en-US', 'de-DE')
    
    Returns:
        Dictionary with 'success', 'content' (transcription text), 'words' (with timestamps), 'error'
    """
    try:
        if not os.path.exists(audio_file_path):
            return {
                'success': False,
                'content': '',
                'words': [],
                'segments': [],
                'error': f'Audio file not found: {audio_file_path}'
            }
        
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {
                'success': False,
                'content': '',
                'words': [],
                'segments': [],
                'error': f'Profile "{profile}" not found in configuration.'
            }
        
        profile_config = profiles[profile]
        endpoint = profile_config.get('endpoint', '').rstrip('/')
        subscription_key = profile_config.get('subscription_key', '')
        api_version = profile_config.get('api_version', '2024-11-15')
        
        if not all([endpoint, subscription_key]):
            return {
                'success': False,
                'content': '',
                'words': [],
                'segments': [],
                'error': f'Missing Azure Speech configuration for profile "{profile}". Please configure endpoint and subscription_key.'
            }
        
        # Azure Speech Services transcription endpoint
        url = f"{endpoint}/speechtotext/transcriptions:transcribe?api-version={api_version}"
        
        print(f'[DEBUG] Azure Speech Transcription URL: {url}')
        print(f'[DEBUG] Endpoint: {endpoint}')
        print(f'[DEBUG] API Version: {api_version}')
        print(f'[DEBUG] Audio file: {audio_file_path}')
        print(f'[DEBUG] Language: {language}')
        
        headers = {
            'Ocp-Apim-Subscription-Key': subscription_key
        }
        
        # Prepare multipart form data
        # Determine content type based on file extension
        ext = os.path.splitext(audio_file_path)[1].lower()
        content_type_map = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.mp4': 'audio/mp4',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }
        content_type = content_type_map.get(ext, 'audio/mpeg')
        
        # Definition for enhanced mode with word-level timestamps
        definition = {
            "locales": [language],
            "profanityFilterMode": "None",
            "wordLevelTimestampsEnabled": True
        }
        
        print(f'[DEBUG] Definition: {json.dumps(definition)}')
        
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'audio': (os.path.basename(audio_file_path), audio_file, content_type),
                'definition': (None, json.dumps(definition), 'application/json')
            }
            
            response = requests.post(url, headers=headers, files=files, timeout=600)
        
        print(f'[DEBUG] Response status: {response.status_code}')
        print(f'[DEBUG] Response headers: {dict(response.headers)}')
        
        if response.status_code == 200:
            result = response.json()
            print(f'[DEBUG] Response JSON keys: {list(result.keys()) if isinstance(result, dict) else "Not a dict"}')
            
            # Parse Azure Speech response format
            # The response contains 'combinedPhrases' and 'phrases' with word-level timing
            combined_text = ''
            words = []
            segments = []
            
            # Get combined text
            combined_phrases = result.get('combinedPhrases', [])
            if combined_phrases:
                combined_text = ' '.join([p.get('text', '') for p in combined_phrases])
            
            # Get phrases with word-level timestamps
            phrases = result.get('phrases', [])
            for phrase in phrases:
                phrase_text = phrase.get('text', '')
                # Azure Speech API returns offsetMilliseconds, not offsetInTicks
                offset_ms = phrase.get('offsetMilliseconds', 0)
                duration_ms = phrase.get('durationMilliseconds', 0)
                
                # Convert milliseconds to seconds
                start_seconds = offset_ms / 1000.0
                end_seconds = start_seconds + (duration_ms / 1000.0)
                
                # Add segment
                segments.append({
                    'text': phrase_text,
                    'start': start_seconds,
                    'end': end_seconds
                })
                
                # Get word-level timestamps if available
                phrase_words = phrase.get('words', [])
                for word_info in phrase_words:
                    word_text = word_info.get('text', '')
                    # Azure Speech API returns offsetMilliseconds for words too
                    word_offset_ms = word_info.get('offsetMilliseconds', 0)
                    word_duration_ms = word_info.get('durationMilliseconds', 0)
                    
                    word_start = word_offset_ms / 1000.0
                    word_end = word_start + (word_duration_ms / 1000.0)
                    
                    words.append({
                        'word': word_text,
                        'start': word_start,
                        'end': word_end
                    })
            
            print(f'[DEBUG] Found {len(words)} words, {len(segments)} segments')
            
            # Format lyrics with timestamps
            lyrics_lines = []
            if words:
                for word_info in words:
                    word = word_info.get('word', '')
                    start = word_info.get('start', 0)
                    
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    milliseconds = int((start % 1) * 1000)
                    timestamp = f"[{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"
                    lyrics_lines.append(f"{timestamp} {word}")
            elif segments:
                for segment in segments:
                    text_seg = segment.get('text', '').strip()
                    start = segment.get('start', 0)
                    if text_seg:
                        minutes = int(start // 60)
                        seconds = int(start % 60)
                        milliseconds = int((start % 1) * 1000)
                        timestamp = f"[{minutes:02d}:{seconds:02d}.{milliseconds:03d}]"
                        lyrics_lines.append(f"{timestamp} {text_seg}")
            
            formatted_lyrics = '\n'.join(lyrics_lines) if lyrics_lines else combined_text
            
            return {
                'success': True,
                'content': formatted_lyrics,
                'text': combined_text,
                'segments': segments,
                'words': words,
                'raw_json': result,
                'error': ''
            }
        else:
            error_msg = f'API error {response.status_code}'
            try:
                error_json = response.json()
                print(f'[DEBUG] Error response JSON: {error_json}')
                error_detail = error_json.get('error', {})
                if isinstance(error_detail, dict):
                    error_msg = f'{error_msg}: {error_detail.get("message", error_detail.get("code", str(error_detail)))}'
                else:
                    error_msg = f'{error_msg}: {str(error_detail)}'
            except:
                error_text = response.text[:500]
                print(f'[DEBUG] Error response text: {error_text}')
                error_msg = f'{error_msg}: {error_text}'
            
            return {
                'success': False,
                'content': '',
                'words': [],
                'segments': [],
                'error': error_msg
            }
    
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'content': '',
            'words': [],
            'segments': [],
            'error': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'content': '',
            'words': [],
            'segments': [],
            'error': f'Unexpected error: {str(e)}'
        }


def call_azure_video(config: dict, prompt: str, size: str = '720x1280', seconds: str = '4', profile: str = 'video_gen') -> dict:
    """Call a video generations endpoint."""
    try:
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Profile "{profile}" not found'}

        profile_config = profiles[profile]
        endpoint = (profile_config.get('endpoint', '') or '').strip()
        model_name = profile_config.get('model_name', 'sora-2')
        deployment = profile_config.get('deployment', '')
        api_version = profile_config.get('api_version', '')
        subscription_key = profile_config.get('subscription_key', '')

        if not endpoint or not subscription_key:
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'Missing video endpoint or key'}

        url = endpoint.rstrip('/')
        try:
            parsed = urllib.parse.urlparse(endpoint)
            path_lower = (parsed.path or '').lower()
            is_base = (path_lower == '' or path_lower == '/')
        except Exception:
            is_base = False
            path_lower = ''

        use_jobs_api = False
        public_url = jobs_url = ''
        
        # Check endpoint type:
        # 1. /openai/v1/videos (plural, ends with 's') = direct API, no jobs, no api-version
        # 2. /openai/v1/video/generations/jobs = jobs API
        # 3. Base URL with deployment = try public first, fallback to jobs
        skip_api_version = False
        if path_lower.endswith('/videos') or '/v1/videos' in path_lower:
            # Direct video API (e.g., Azure Cognitive Services Sora endpoint)
            # Don't append /jobs, don't add api-version - use as-is with direct payload
            use_jobs_api = False
            skip_api_version = True
        elif 'openai/v1/video/' in path_lower or path_lower.endswith('/jobs'):
            # Jobs-based API
            if not url.endswith('/jobs'):
                url = f"{url}/jobs"
            use_jobs_api = True
        elif is_base and deployment:
            public_url = f"{url}/openai/deployments/{deployment}/video/generations"
            jobs_url = f"{url}/openai/deployments/{deployment}/video/generations/jobs"
            url = public_url
            use_jobs_api = False
        else:
            url = f"{url}/openai/v1/video/generations/jobs"
            use_jobs_api = True

        if api_version and 'api-version=' not in url and not skip_api_version:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}api-version={api_version}"

        headers = {
            'Content-Type': 'application/json',
            'Api-key': subscription_key
        }

        width, height = None, None
        try:
            parts = size.lower().split('x')
            if len(parts) == 2:
                width = str(int(parts[0]))
                height = str(int(parts[1]))
        except Exception:
            pass

        # Determine if using jobs-based API based on URL pattern
        using_jobs_api = use_jobs_api or (
            (('/openai/v1/video/' in url) or ('/openai/deployments/' in url and '/video/generations/jobs' in url))
            and (url.endswith('/jobs') or '/jobs?' in url)
        )

        if using_jobs_api:
            payload = {
                'prompt': prompt,
                'n_variants': '1',
                'n_seconds': str(seconds),
                'height': height or '1280',
                'width': width or '720',
                'model': model_name or deployment or 'sora-2'
            }
        else:
            payload = {
                'model': model_name or deployment or 'sora-2',
                'prompt': prompt,
                'size': size,
                'seconds': str(seconds)
            }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        ctype = resp.headers.get('Content-Type', '')
        debug_info = {
            'url': url,
            'api_version': api_version,
            'model': model_name,
            'size': size,
            'seconds': str(seconds),
            'status': resp.status_code,
            'content_type': ctype,
        }
        if resp.status_code == 200 and not using_jobs_api:
            if 'video' in ctype or 'application/octet-stream' in ctype:
                return {'success': True, 'video_bytes': resp.content, 'url': '', 'error': '', 'debug': debug_info}
            try:
                data = resp.json()
                if isinstance(data, dict):
                    # Check for async polling format (status: queued/processing with id)
                    video_id = data.get('id') or data.get('video_id')
                    status = (data.get('status') or '').lower()
                    if video_id and status in ['queued', 'processing', 'pending', 'in_progress', 'running']:
                        # Async API - need to poll for completion
                        base_url = endpoint.rstrip('/')
                        poll_url = f"{base_url}/{video_id}"
                        debug_info['poll_url'] = poll_url
                        debug_info['video_id'] = video_id
                        
                        start_time = time.time()
                        max_wait = 300  # 5 minutes max
                        while status not in ['completed', 'succeeded', 'failed', 'error'] and (time.time() - start_time) < max_wait:
                            time.sleep(5)
                            poll_resp = requests.get(poll_url, headers=headers, timeout=60)
                            try:
                                poll_data = poll_resp.json()
                                status = (poll_data.get('status') or '').lower()
                                debug_info['poll_status'] = status
                            except Exception:
                                continue
                        
                        if status in ['completed', 'succeeded']:
                            # Try to get video content
                            # Check for direct video URL in response
                            video_url = poll_data.get('output', {}).get('url') if isinstance(poll_data.get('output'), dict) else None
                            video_url = video_url or poll_data.get('video_url') or poll_data.get('url') or poll_data.get('result', {}).get('url') if isinstance(poll_data.get('result'), dict) else None
                            
                            if video_url:
                                vid_resp = requests.get(video_url, headers=headers, timeout=300)
                                if vid_resp.ok:
                                    return {'success': True, 'video_bytes': vid_resp.content, 'url': video_url, 'error': '', 'debug': debug_info}
                            
                            # Try content endpoint
                            content_url = f"{poll_url}/content"
                            vid_resp = requests.get(content_url, headers=headers, timeout=300)
                            if vid_resp.ok and vid_resp.content:
                                return {'success': True, 'video_bytes': vid_resp.content, 'url': '', 'error': '', 'debug': {**debug_info, 'content_url': content_url}}
                            
                            # Check for base64 in poll response
                            b64 = poll_data.get('b64_json') or poll_data.get('video_b64') or ''
                            if not b64 and 'output' in poll_data and isinstance(poll_data['output'], dict):
                                b64 = poll_data['output'].get('b64_json') or poll_data['output'].get('video_b64') or ''
                            if b64:
                                return {'success': True, 'video_bytes': base64.b64decode(b64), 'url': '', 'error': '', 'debug': debug_info}
                            
                            debug_info['final_poll_response'] = str(poll_data)[:500]
                            return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Video completed but could not retrieve content', 'debug': debug_info}
                        else:
                            error_msg = poll_data.get('error', {}).get('message') if isinstance(poll_data.get('error'), dict) else poll_data.get('error') or f'Video generation failed with status: {status}'
                            return {'success': False, 'video_bytes': b'', 'url': '', 'error': str(error_msg), 'debug': debug_info}
                    
                    # Check for immediate video URL response
                    url_value = data.get('url') or data.get('video_url') or ''
                    if url_value:
                        return {'success': True, 'video_bytes': b'', 'url': url_value, 'error': '', 'debug': debug_info}
                    b64 = ''
                    if 'data' in data and isinstance(data['data'], list) and data['data']:
                        b64 = data['data'][0].get('b64_json', '') or data['data'][0].get('video_b64', '')
                    b64 = b64 or data.get('b64_json', '') or data.get('video_b64', '')
                    if b64:
                        return {'success': True, 'video_bytes': base64.b64decode(b64), 'url': '', 'error': '', 'debug': debug_info}
                debug_info['body_preview'] = resp.text[:500]
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'Unknown video response format', 'debug': debug_info}
            except Exception as e:
                body_preview = ''
                try:
                    body_preview = resp.text[:500]
                except Exception:
                    pass
                debug_info['body_preview'] = body_preview
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Invalid JSON response: {e}', 'debug': debug_info}
        
        if (resp.status_code in (400, 404)) and (public_url and jobs_url) and (not using_jobs_api):
            body_text = ''
            try:
                body_text = resp.text
            except Exception:
                pass
            if ('private preview' in body_text.lower()) or (resp.status_code == 404):
                url = jobs_url
                if api_version and 'api-version=' not in url:
                    sep = '&' if '?' in url else '?'
                    url = f"{url}{sep}api-version={api_version}"
                payload = {
                    'prompt': prompt,
                    'n_variants': '1',
                    'n_seconds': str(seconds),
                    'height': height or '1280',
                    'width': width or '720',
                    'model': model_name or deployment or 'sora-2'
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
                ctype = resp.headers.get('Content-Type', '')
                debug_info.update({'url': url, 'status': resp.status_code, 'content_type': ctype})
                using_jobs_api = True

        if using_jobs_api:
            try:
                job = resp.json()
            except Exception as e:
                debug_info['body_preview'] = resp.text[:500] if resp.text else ''
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Invalid jobs JSON response: {e}', 'debug': debug_info}

            job_id = job.get('id') or job.get('job_id')
            status = job.get('status', '').lower()
            if not job_id:
                debug_info['body_preview'] = resp.text[:500] if resp.text else ''
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'No job id in response', 'debug': debug_info}

            base = endpoint.rstrip('/')
            status_url = f"{base}/openai/v1/video/generations/jobs/{job_id}"
            if api_version and 'api-version=' not in status_url:
                status_url += f"?api-version={api_version}"

            start_time = time.time()
            while status not in ['succeeded', 'failed'] and (time.time() - start_time) < 300:
                time.sleep(5)
                poll_resp = requests.get(status_url, headers=headers, timeout=60)
                try:
                    poll_json = poll_resp.json()
                except Exception:
                    return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Invalid status JSON ({poll_resp.status_code})', 'debug': debug_info}
                status = (poll_json.get('status') or '').lower()

            if status != 'succeeded':
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Job status: {status or "unknown"}', 'debug': debug_info}

            generations = poll_json.get('generations') or []
            if not generations:
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'No generations returned', 'debug': debug_info}
            generation_id = generations[0].get('id') or generations[0].get('generation_id')
            if not generation_id:
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'No generation id in response', 'debug': debug_info}

            video_url = f"{base}/openai/v1/video/generations/{generation_id}/content/video"
            if api_version and 'api-version=' not in video_url:
                video_url += f"?api-version={api_version}"
            vid_resp = requests.get(video_url, headers=headers, timeout=300)
            if vid_resp.ok and ('video' in vid_resp.headers.get('Content-Type', '') or vid_resp.content):
                return {'success': True, 'video_bytes': vid_resp.content, 'url': '', 'error': '', 'debug': {**debug_info, 'download_url': video_url}}
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Failed to download video ({vid_resp.status_code})', 'debug': {**debug_info, 'download_url': video_url}}
        else:
            body_preview = ''
            try:
                body_preview = resp.text[:500]
            except Exception:
                pass
            debug_info['body_preview'] = body_preview
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Video API error {resp.status_code}: {resp.text}', 'debug': debug_info}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Request error: {e}'}
    except Exception as e:
        return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Unexpected error: {e}'}


def load_persona_config(persona_path: str) -> dict:
    """Load persona config.json from persona folder."""
    config_file = os.path.join(persona_path, 'config.json')
    default_config = {
        'name': '',
        'age': '',
        'tagline': '',
        'vibe': '',
        'visual_aesthetic': '',
        'base_image_prompt': '',
        'bio': '',
        'genre_tags': [],
        'voice_style': '',
        'lyrics_style': '',
        'spotify_link': '',
        'itunes_link': '',
        'youtube_music_link': '',
        'image_presets': [
            {'key': 'default', 'label': 'Main', 'is_default': True, 'profile_prompt': '', 'profile_custom_prompt': ''}
        ],
        'current_image_preset': 'default'
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Merge with defaults
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                # Guarantee at least one preset exists
                presets = config.get('image_presets') or default_config['image_presets']
                if not isinstance(presets, list) or not presets:
                    presets = default_config['image_presets']
                config['image_presets'] = presets
                if not config.get('current_image_preset'):
                    config['current_image_preset'] = presets[0].get('key', 'default')
                return config
        except Exception as e:
            print(f'Error loading persona config: {e}')
            return default_config
    return default_config


def backup_file_if_exists(file_path: str) -> str | None:
    """Create a timestamped backup of a file if it exists.
    
    Args:
        file_path: Path to the file to backup
        
    Returns:
        Path to the backup file if backup was created, None otherwise
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base, ext = os.path.splitext(file_path)
        backup_path = f"{base}_backup_{timestamp}{ext}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        print(f'Warning: Failed to create backup of {file_path}: {e}')
        return None


def save_persona_config(persona_path: str, config: dict):
    """Save persona config.json to persona folder. Creates backup before overwriting."""
    persona_path = enable_long_paths(persona_path)
    config_file = enable_long_paths(os.path.join(persona_path, 'config.json'))
    try:
        os.makedirs(persona_path, exist_ok=True)
        # Create backup before overwriting
        backup_path = backup_file_if_exists(config_file)
        if backup_path:
            print(f'Backed up persona config to: {backup_path}')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f'Error saving persona config: {e}')
        return False


def load_song_config(song_path: str) -> dict:
    """Load song config.json from song folder."""
    config_file = os.path.join(song_path, 'config.json')
    default_config = {
        'song_name': '',
        'full_song_name': '',
        'album_id': '',
        'album_name': '',
        'lyric_ideas': '',
        'lyrics': '',
        'extracted_lyrics': '',
        'song_style': '',
        'merged_style': '',
        'storyboard_theme': '',
        'album_cover': '',
        'video_loop': '',
        'storyboard': [],
        'storyboard_metadata': {},
        'storyboard_seconds_per_video': 6,
        'storyboard_image_size': '3:2 (1536x1024)',
        'album_cover_size': '1:1 (1024x1024)',
        'album_cover_format': 'PNG',
        'include_persona_in_cover': True,
        'video_loop_size': '9:16 (720x1280)',
        'video_loop_duration': 6,
        'video_loop_multiscene': False,
        'overlay_lyrics_on_image': False,
        'embed_lyrics_in_prompt': True,
        'embed_keywords_in_prompt': False,
        'include_lyrics_in_export': True,
        'persona_scene_percent': 40,
        'storyboard_setup_count': 6,
        'persona_image_preset': 'default'
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except Exception as e:
            print(f'Error loading song config: {e}')
            return default_config
    return default_config


def save_song_config(song_path: str, config: dict):
    """Save song config.json to song folder."""
    song_path = enable_long_paths(song_path)
    config_file = enable_long_paths(os.path.join(song_path, 'config.json'))
    try:
        os.makedirs(song_path, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f'Error saving song config: {e}')
        return False


def load_album_config(album_path: str) -> dict:
    """Load album config.json from album folder."""
    config_file = os.path.join(album_path, 'config.json')
    default_config = {
        'album_id': '',
        'album_name': '',
        'songs': [],
        'cover_prompt': '',
        'cover_size': '1:1 (1024x1024)',
        'cover_format': 'PNG',
        'video_prompt': '',
        'video_size': '9:16 (720x1280)',
        'language': 'EN',
        'cover_image_file': '',
        'video_prompt_file': ''
    }
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except Exception as e:
            print(f'Error loading album config: {e}')
            return default_config
    return default_config


def save_album_config(album_path: str, config: dict):
    """Save album config.json to album folder."""
    config_file = os.path.join(album_path, 'config.json')
    try:
        os.makedirs(album_path, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f'Error saving album config: {e}')
        return False


def get_mp3_filename(full_song_name: str) -> str:
    """Generate safe MP3 filename from full song name.
    
    Example: 'AI's Shadow - Sister Smoke - (cyberpunk, blues, glitch)' 
    -> 'AI's Shadow - Sister Smoke - (cyberpunk, blues, glitch).mp3'
    
    Args:
        full_song_name: The full song name in format [Song] - [Persona] - (keywords)
    
    Returns:
        Safe filename with .mp3 extension
    """
    if not full_song_name:
        return 'song.mp3'
    
    # Replace invalid filename characters but keep the format intact
    safe_name = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
    
    # Ensure it ends with .mp3
    if not safe_name.lower().endswith('.mp3'):
        safe_name += '.mp3'
    
    return safe_name


class SunoPersona(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Set UTF-8 encoding for stdout/stderr on Windows to prevent encoding errors
        if sys.platform == 'win32':
            try:
                if hasattr(sys.stdout, 'reconfigure'):
                    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                if hasattr(sys.stderr, 'reconfigure'):
                    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                # If reconfiguration fails, continue anyway
                pass
        
        self.title('Suno Persona Manager')
        self.geometry('1450x1100')
        # Set maximum height (width can be flexible, height limited)
        self.maxsize(width=9999, height=1400)
        
        self.ai_config = load_config()
        self.known_band_names = self._load_known_band_names()
        self.personas_path = get_personas_path(self.ai_config)
        self.current_persona = None
        self.current_persona_path = None
        self.current_song = None
        self.current_song_path = None
        self.current_album = None
        self.current_album_id = None
        self.albums: dict[str, dict] = {}
        self.current_album_songs: list[str] = []
        self.last_song_cover_path = ''
        self.last_album_cover_path = ''
        self.scene_final_prompts = {}
        self.merge_song_weight = 50
        
        self.create_widgets()
        self.refresh_image_preset_controls()
        self.refresh_personas_list()
    
    def create_widgets(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Settings', menu=settings_menu)
        settings_menu.add_command(label='Settings...', command=self.open_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Help', menu=help_menu)
        help_menu.add_command(label='About', command=self.show_about)
        
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=8)
        
        ttk.Button(top_frame, text='New Persona', command=self.new_persona).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text='Delete Persona', command=self.delete_persona).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text='Refresh', command=self.refresh_personas_list).pack(side=tk.RIGHT, padx=4)
        
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left_panel.config(width=300)
        
        ttk.Label(left_panel, text='Personas:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        self.personas_tree = ttk.Treeview(left_panel, columns=('name',), show='headings', selectmode='browse')
        self.personas_tree.heading('name', text='Name')
        self.personas_tree.column('name', width=280, anchor=tk.W)
        
        tree_scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.personas_tree.yview)
        self.personas_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.personas_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.personas_tree.bind('<<TreeviewSelect>>', self.on_persona_select)
        
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        persona_tab = ttk.Frame(self.notebook)
        self.notebook.add(persona_tab, text='Persona Info')
        self.create_persona_tab(persona_tab)
        
        images_tab = ttk.Frame(self.notebook)
        self.notebook.add(images_tab, text='Persona Images')
        self.create_images_tab(images_tab)

        profile_images_tab = ttk.Frame(self.notebook)
        self.notebook.add(profile_images_tab, text='Profile Images')
        self.create_profile_images_tab(profile_images_tab)
        
        songs_tab = ttk.Frame(self.notebook)
        self.notebook.add(songs_tab, text='AI Songs')
        self.create_songs_tab(songs_tab)
        
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.status_var = tk.StringVar(value=f'Personas directory: {self.personas_path}')
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.debug_frame = ttk.LabelFrame(self, text='Debug Output', padding=5)
        self.debug_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
        
        self.debug_text = scrolledtext.ScrolledText(self.debug_frame, height=6, wrap=tk.WORD, font=('Consolas', 9))
        self.debug_text.pack(fill=tk.BOTH, expand=True)
        self.debug_text.config(state=tk.DISABLED)
        
        self.log_debug('INFO', 'Application initialized')
    
    def log_debug(self, level: str, message: str):
        """Log a debug/info message."""
        import datetime
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        
        # Ensure message is a proper string and handle encoding issues
        if isinstance(message, bytes):
            try:
                message = message.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    message = message.decode('latin-1')
                except UnicodeDecodeError:
                    message = message.decode('utf-8', errors='replace')
        elif not isinstance(message, str):
            message = str(message)
        
        formatted_message = f'[{timestamp}] [{level}] {message}\n'
        
        self.debug_text.config(state=tk.NORMAL)
        self.debug_text.insert(tk.END, formatted_message)
        self.debug_text.see(tk.END)
        self.debug_text.config(state=tk.DISABLED)
        # Also echo to console for full visibility with proper encoding handling
        try:
            # On Windows, ensure UTF-8 encoding for console output
            if sys.platform == 'win32':
                # Try to set console to UTF-8 if possible
                try:
                    import sys
                    if hasattr(sys.stdout, 'reconfigure'):
                        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                    elif hasattr(sys.stdout, 'buffer'):
                        # Write directly to buffer with UTF-8 encoding
                        sys.stdout.buffer.write(formatted_message.encode('utf-8', errors='replace'))
                        sys.stdout.buffer.flush()
                    else:
                        # Fallback: try to encode safely
                        safe_message = formatted_message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        print(safe_message, end='')
                except Exception:
                    # Final fallback: try to print with error handling
                    try:
                        safe_message = formatted_message.encode('ascii', errors='replace').decode('ascii')
                        print(safe_message, end='')
                    except Exception:
                        pass
            else:
                # On non-Windows, use regular print
                print(formatted_message, end='')
        except Exception:
            # Silently fail if console output fails
            pass
    
    def log_prompt_debug(self, title: str, prompt: str | None, system_message: str | None = None):
        """Log AI prompts (and optional system messages) without truncation."""
        prompt_text = prompt or ''
        total_len = len(prompt_text)
        self.log_debug('PROMPT', f'{title} ({total_len} chars):\n{prompt_text}')
        
        if system_message is not None:
            sys_len = len(system_message)
            self.log_debug('PROMPT', f'{title} system ({sys_len} chars):\n{system_message}')

    def _album_slug(self, name: str) -> str:
        """Create a filesystem-safe slug for an album name."""
        base = name.strip().lower()
        if not base:
            return 'album'
        base = re.sub(r'[^a-z0-9]+', '-', base)
        base = re.sub(r'-{2,}', '-', base).strip('-')
        return base or 'album'

    def _albums_dir(self) -> str | None:
        """Return the albums directory for the current persona."""
        if not self.current_persona_path:
            return None
        return os.path.join(self.current_persona_path, 'AI-Albums')

    def load_albums(self):
        """Load albums for the current persona."""
        self.albums = {}
        if not self.current_persona_path:
            return
        albums_dir = self._albums_dir()
        if not albums_dir or not os.path.exists(albums_dir):
            return
        try:
            for item in os.listdir(albums_dir):
                path = os.path.join(albums_dir, item)
                if not os.path.isdir(path):
                    continue
                config = load_album_config(path)
                album_id = config.get('album_id') or item
                config['album_id'] = album_id
                config['folder_name'] = item
                self.albums[album_id] = config
        except Exception as exc:
            self.log_debug('ERROR', f'Failed to load albums: {exc}')

    def _get_album_path(self, album_id: str) -> str | None:
        """Get album folder path by id."""
        albums_dir = self._albums_dir()
        if not albums_dir or not album_id:
            return None
        folder = self.albums.get(album_id, {}).get('folder_name') or album_id
        return os.path.join(albums_dir, folder)

    def _get_selected_song_ids(self) -> list[str]:
        """Return selected song folder ids (exclude album nodes)."""
        if not hasattr(self, 'songs_tree'):
            return []
        selected = []
        for iid in self.songs_tree.selection():
            if iid.startswith('album::'):
                continue
            selected.append(iid)
        return selected

    def show_image_preview(self, image_path: str, title: str = 'Preview'):
        """Open a simple preview window for an image."""
        if not image_path or not os.path.exists(image_path):
            messagebox.showwarning('Warning', f'Image not found:\n{image_path}')
            return
        try:
            from PIL import Image, ImageTk  # Pillow is already used elsewhere
            img = Image.open(image_path)
            max_w, max_h = 768, 768
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            preview = tk.Toplevel(self)
            preview.title(title)
            preview.geometry(f'{img.width + 20}x{img.height + 60}')
            tk.Label(preview, text=os.path.basename(image_path)).pack(pady=(6, 2))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(preview, image=photo)
            lbl.image = photo  # keep reference
            lbl.pack(padx=6, pady=6)
            ttk.Button(preview, text='Close', command=preview.destroy).pack(pady=(0, 8))
        except Exception as exc:
            messagebox.showerror('Error', f'Failed to preview image: {exc}')
            self.log_debug('ERROR', f'Preview failed: {exc}')

    def preview_last_song_cover(self):
        """Preview the last generated song cover."""
        if self.last_song_cover_path:
            self.show_image_preview(self.last_song_cover_path, 'Song Cover Preview')
        else:
            messagebox.showinfo('Info', 'No song cover generated yet.')

    def open_folder_in_explorer(self, path: str, select_file: bool = True) -> bool:
        """Open a folder (or file's parent) in the system file manager. Optionally select the file."""
        if not path or not os.path.exists(path):
            return False
        target = path
        if os.path.isfile(path) and select_file:
            target = os.path.dirname(path)
        try:
            target = os.path.normpath(os.path.abspath(target))
            if sys.platform == 'win32':
                if os.path.isfile(path) and select_file:
                    subprocess.run(['explorer', '/select,', path], check=False)
                else:
                    os.startfile(target)
            elif sys.platform == 'darwin':
                if os.path.isfile(path) and select_file:
                    subprocess.run(['open', '-R', path], check=False)
                else:
                    subprocess.run(['open', target], check=False)
            else:
                subprocess.run(['xdg-open', target], check=False)
            return True
        except Exception as e:
            self.log_debug('ERROR', f'Failed to open in Explorer: {e}')
            messagebox.showerror('Error', f'Failed to open folder: {e}')
            return False

    def explorer_song_cover(self):
        """Open song cover folder in Explorer. Uses last generated or existing cover path."""
        path = self.last_song_cover_path or self.get_album_cover_filepath()
        if not path and self.current_song_path:
            path = self.current_song_path
        if path:
            self.open_folder_in_explorer(path, select_file=bool(path and os.path.isfile(path)))
        else:
            messagebox.showwarning('Warning', 'No song selected. Select a song first.')

    def explorer_album_cover(self):
        """Open album cover folder in Explorer. Uses last generated or existing cover path."""
        path = self.last_album_cover_path or (self.current_album.get('cover_image_file', '') if self.current_album else '')
        if not path and self.current_album_id:
            album_path = self._get_album_path(self.current_album_id)
            if album_path and os.path.isdir(album_path):
                path = album_path
        if path:
            self.open_folder_in_explorer(path, select_file=bool(path and os.path.isfile(path)))
        else:
            messagebox.showwarning('Warning', 'No album cover path. Select an album or generate a cover first.')

    def preview_last_album_cover(self):
        """Preview the last generated album cover."""
        if self.last_album_cover_path:
            self.show_image_preview(self.last_album_cover_path, 'Album Cover Preview')
        else:
            messagebox.showinfo('Info', 'No album cover generated yet.')
    
    def _load_known_band_names(self) -> set[str]:
        """Collect artist/band names from the styles CSV for later sanitizing."""
        names: set[str] = set()
        try:
            csv_path = get_styles_csv_path(self.ai_config)
            for row in load_styles_from_csv(csv_path):
                artists_raw = (row.get('sample_artists') or '').replace('/', ';')
                if not artists_raw:
                    continue
                for name in re.split(r'[;,]', artists_raw):
                    clean = name.strip()
                    if not clean:
                        continue
                    if len(clean) <= 3 and not (clean.isupper() or re.search(r'\d', clean)):
                        continue
                    names.add(clean)
        except Exception as exc:
            self.log_debug('WARNING', f'Could not load band names from styles: {exc}')
        return names
    
    def _sanitize_style_keywords(self, text: str) -> str:
        """Remove known band/artist names from style text."""
        if not text:
            return text
        cleaned = text
        for name in sorted(self.known_band_names, key=len, reverse=True):
            pattern = r'\b' + re.escape(name) + r'\b'
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        cleaned = re.sub(r'\s+([,;])', r'\1', cleaned)
        return cleaned.strip(' ,;')

    def _remove_parenthetical_content(self, text: str) -> str:
        """Remove parenthetical content (e.g., ' - (devotional folk meditative)') from song names."""
        if not text:
            return text
        # Remove patterns like " - (content)" or " (content)" at the end
        # This handles both " - (content)" and " (content)" patterns
        cleaned = re.sub(r'\s*-\s*\([^)]*\)\s*$', '', text)
        cleaned = re.sub(r'\s*\([^)]*\)\s*$', '', cleaned)
        return cleaned.strip()

    def _safe_filename(self, name: str) -> str:
        """Return a filesystem-safe string for filenames."""
        return name.replace(' ', '-').replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')

    def _safe_persona_basename(self) -> str:
        """Safe base filename for current persona."""
        if self.current_persona:
            return self._safe_filename(self.current_persona.get('name', 'persona'))
        return 'persona'

    def _default_image_presets(self) -> list[dict]:
        """Return the default image preset structure."""
        return [{'key': 'default', 'label': 'Main', 'is_default': True, 'profile_prompt': '', 'profile_custom_prompt': ''}]

    def _get_persona_image_presets(self) -> list[dict]:
        """Return persona image presets ensuring at least one exists."""
        if not self.current_persona:
            return self._default_image_presets()
        presets = self.current_persona.get('image_presets') or []
        if not isinstance(presets, list) or not presets:
            presets = self._default_image_presets()
            self.current_persona['image_presets'] = presets
        # Ensure each preset has prompt fields
        for preset in presets:
            if 'profile_prompt' not in preset:
                preset['profile_prompt'] = ''
            if 'profile_custom_prompt' not in preset:
                preset['profile_custom_prompt'] = ''
        return presets

    def _get_default_image_preset_key(self) -> str:
        """Get the default preset key for current persona."""
        presets = self._get_persona_image_presets()
        for preset in presets:
            if preset.get('is_default'):
                return preset.get('key', 'default')
        return presets[0].get('key', 'default')
    
    def _find_default_persona_front_image(self) -> str | None:
        """Find a default persona's Front image to use as reference for new personas.
        
        Looks for:
        1. A persona named "Default" (case-insensitive)
        2. The first persona that has a Front image in the default preset
        
        Returns:
            Path to Front image if found, None otherwise
        """
        if not hasattr(self, 'personas_path') or not os.path.exists(self.personas_path):
            return None
        
        # First, try to find a persona named "Default"
        default_persona_names = ['Default', 'default', 'DEFAULT']
        for item in os.listdir(self.personas_path):
            item_path = os.path.join(self.personas_path, item)
            if not os.path.isdir(item_path) or item.startswith('_'):
                continue
            
            config_file = os.path.join(item_path, 'config.json')
            if not os.path.exists(config_file):
                continue
            
            try:
                config = load_persona_config(item_path)
                persona_name = config.get('name', '').strip()
                if persona_name in default_persona_names or item.lower() == 'default':
                    # Found default persona, check for Front image
                    safe_name = self._safe_filename(persona_name) if persona_name else item
                    default_preset_key = 'default'
                    # Try to get default preset from config
                    presets = config.get('image_presets', [])
                    for preset in presets:
                        if preset.get('is_default'):
                            default_preset_key = preset.get('key', 'default')
                            break
                    
                    # Check default preset path
                    if default_preset_key == 'default':
                        front_path = os.path.join(item_path, f'{safe_name}-Front.png')
                    else:
                        front_path = os.path.join(item_path, 'image_presets', default_preset_key, f'{safe_name}-Front.png')
                    
                    if os.path.exists(front_path):
                        self.log_debug('INFO', f'Found default persona Front image: {front_path}')
                        return front_path
            except Exception:
                continue
        
        # If no "Default" persona found, look for any persona with a Front image
        for item in os.listdir(self.personas_path):
            item_path = os.path.join(self.personas_path, item)
            if not os.path.isdir(item_path) or item.startswith('_'):
                continue
            
            config_file = os.path.join(item_path, 'config.json')
            if not os.path.exists(config_file):
                continue
            
            try:
                config = load_persona_config(item_path)
                persona_name = config.get('name', '').strip()
                safe_name = self._safe_filename(persona_name) if persona_name else item
                
                # Check default preset path
                default_preset_key = 'default'
                presets = config.get('image_presets', [])
                for preset in presets:
                    if preset.get('is_default'):
                        default_preset_key = preset.get('key', 'default')
                        break
                
                if default_preset_key == 'default':
                    front_path = os.path.join(item_path, f'{safe_name}-Front.png')
                else:
                    front_path = os.path.join(item_path, 'image_presets', default_preset_key, f'{safe_name}-Front.png')
                
                if os.path.exists(front_path):
                    self.log_debug('INFO', f'Found persona Front image to use as default reference: {front_path}')
                    return front_path
            except Exception:
                continue
        
        return None

    def _get_preset_record(self, key: str) -> dict:
        """Return a preset record, ensuring it exists."""
        presets = self._get_persona_image_presets()
        for preset in presets:
            if preset.get('key') == key:
                return preset
        # If missing, create one
        new_preset = {'key': key, 'label': key, 'is_default': False, 'profile_prompt': '', 'profile_custom_prompt': ''}
        presets.append(new_preset)
        self.current_persona['image_presets'] = presets
        return new_preset

    def _get_active_preset_key(self) -> str:
        """Return currently selected preset key."""
        if hasattr(self, 'image_preset_var') and self.image_preset_var.get():
            return self.image_preset_var.get()
        if self.current_persona and self.current_persona.get('current_image_preset'):
            return self.current_persona['current_image_preset']
        return self._get_default_image_preset_key()

    def _get_active_preset_prompts(self) -> tuple[str, str]:
        """Return (base_prompt, custom_prompt) for the active preset, falling back to persona."""
        key = self._get_active_preset_key()
        preset = self._get_preset_record(key)
        base_prompt = ''
        custom_prompt = ''
        if hasattr(self, 'profile_prompt_text'):
            try:
                base_prompt = self.profile_prompt_text.get('1.0', tk.END).strip()
            except Exception:
                base_prompt = ''
        if not base_prompt:
            base_prompt = preset.get('profile_prompt', '')
        if hasattr(self, 'profile_custom_prompt_text'):
            try:
                custom_prompt = self.profile_custom_prompt_text.get('1.0', tk.END).strip()
            except Exception:
                custom_prompt = ''
        if not custom_prompt:
            custom_prompt = preset.get('profile_custom_prompt', '')
        # Persona-level fallback
        if not base_prompt and self.current_persona:
            base_prompt = self.current_persona.get('base_image_prompt', '')
        return base_prompt, custom_prompt

    def _save_preset_prompts_from_ui(self, preset_key: str | None = None):
        """Persist profile/base prompts into the preset record."""
        if not self.current_persona:
            return
        key = preset_key or (self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default'))
        preset = self._get_preset_record(key)
        if hasattr(self, 'profile_prompt_text'):
            try:
                preset['profile_prompt'] = self.profile_prompt_text.get('1.0', tk.END).strip()
            except Exception:
                pass
        if hasattr(self, 'profile_custom_prompt_text'):
            try:
                preset['profile_custom_prompt'] = self.profile_custom_prompt_text.get('1.0', tk.END).strip()
            except Exception:
                pass
        save_persona_config(self.current_persona_path, self.current_persona)

    def _load_preset_prompts_into_ui(self, preset_key: str | None = None):
        """Load stored profile/base prompts from the preset into UI."""
        key = preset_key or (self.image_preset_var.get() if hasattr(self, 'image_preset_var') else None)
        if not key:
            key = self._get_default_image_preset_key()
        preset = self._get_preset_record(key)
        if hasattr(self, 'profile_prompt_text'):
            try:
                self.profile_prompt_text.delete('1.0', tk.END)
                self.profile_prompt_text.insert('1.0', preset.get('profile_prompt', ''))
            except Exception:
                pass
        if hasattr(self, 'profile_custom_prompt_text'):
            try:
                self.profile_custom_prompt_text.delete('1.0', tk.END)
                self.profile_custom_prompt_text.insert('1.0', preset.get('profile_custom_prompt', ''))
            except Exception:
                pass

    def _get_preset_label(self, key: str) -> str:
        """Friendly label for a preset key."""
        for preset in self._get_persona_image_presets():
            if preset.get('key') == key:
                return preset.get('label') or key
        return key or 'default'

    def get_persona_image_base_path(self, preset_key: str | None = None) -> str:
        """Resolve the base path where reference/profile images live for a preset."""
        base = self.current_persona_path or ''
        key = preset_key or (self.current_persona.get('current_image_preset') if self.current_persona else 'default') or 'default'
        if key == 'default':
            return base
        return os.path.join(base, 'image_presets', key)

    def _ensure_persona_image_preset_state(self):
        """Ensure preset selection state is initialized for the current persona."""
        if not self.current_persona:
            return
        presets = self._get_persona_image_presets()
        current_key = self.current_persona.get('current_image_preset')
        if (not current_key) or (not any(p.get('key') == current_key for p in presets)):
            current_key = self._get_default_image_preset_key()
            self.current_persona['current_image_preset'] = current_key
        if hasattr(self, 'image_preset_var'):
            self.image_preset_var.set(current_key)
        if hasattr(self, 'image_preset_caption_var'):
            default_label = self._get_preset_label(self._get_default_image_preset_key())
            caption = f"Using preset: {self._get_preset_label(current_key)}"
            if current_key == self._get_default_image_preset_key():
                caption += " (default)"
            elif default_label:
                caption += f" | Default: {default_label}"
            self.image_preset_caption_var.set(caption)

    def _get_song_persona_preset_key(self) -> str:
        """Get the active preset key for the current song."""
        if hasattr(self, 'song_persona_preset_var') and self.song_persona_preset_var.get():
            return self.song_persona_preset_var.get()
        if self.current_song and self.current_song.get('persona_image_preset'):
            return self.current_song.get('persona_image_preset')
        if self.current_persona:
            return self.current_persona.get('current_image_preset', self._get_default_image_preset_key())
        return 'default'
    
    def _get_sanitized_style_text(self) -> str:
        """Return merged/song style with band names stripped."""
        merged_style = self.merged_style_text.get('1.0', tk.END).strip() if hasattr(self, 'merged_style_text') else ''
        song_style = self.song_style_text.get('1.0', tk.END).strip() if hasattr(self, 'song_style_text') else ''
        style_text = merged_style or song_style
        return self._sanitize_style_keywords(style_text)

    def _extract_style_keywords(self, style_text: str) -> list[str]:
        """Extract up to three concise single-word keywords from style text."""
        if not style_text:
            return []
        
        band_name_lc = {name.lower() for name in getattr(self, 'known_band_names', set())}
        gender_stop = {
            'male', 'female', 'man', 'woman', 'boy', 'girl',
            'tenor', 'baritone', 'bass', 'alto', 'contralto',
            'mezzo', 'soprano', 'falsetto', 'vocal', 'vocals',
            'voice', 'singer', 'sung', 'sings', 'sang'
        }
        style_stop = {
            'style', 'styles', 'mix', 'blend', 'fusion', 'vibe', 'vibes',
            'music', 'song', 'track', 'sound', 'sounds', 'beat', 'beats',
            'tempo', 'bpm', 'version', 'remix', 'edit', 'intro', 'outro',
            'verse', 'chorus', 'hook', 'bridge', 'vocals', 'lyric', 'lyrics'
        }
        filler_stop = {
            'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'from',
            'with', 'and', 'or', 'but', 'by', 'into', 'over', 'under', 'out',
            'feat', 'featuring', 'ft', 'inspired', 'style', 'like', 'original',
            'effect', 'effects'
        }
        name_stop = {
            'tom', 'morello', 'john', 'jane', 'mike', 'michael', 'david',
            'sarah', 'sara', 'james', 'paul', 'peter', 'lisa', 'mark'
        }
        instrument_stop = {
            'guitar', 'drums', 'drummer', 'bass', 'piano', 'synth', 'synths',
            'synthesizer', 'keyboard', 'keys', 'violin', 'cello', 'harp',
            'trumpet', 'sax', 'saxophone', 'clarinet', 'flute', 'banjo',
            'mandolin', 'ukulele', 'accordion', 'harmonica', 'percussion',
            'trombone', 'tuba', 'viola', 'organ', 'drum', 'hi-hat', 'snare'
        }
        nonstyle_stop = {
            'effect', 'effects', 'riff', 'riffing', 'groove', 'grooves', 'accent', 'accents',
            'energy', 'attitude', 'reverb', 'delay', 'distortion', 'chorusfx',
            'chant', 'chants', 'crowd', 'call', 'response', 'hits', 'hit', 'punchy',
            'tight', 'minimal', 'explosive', 'politically', 'charged', 'shouted',
            'militant', 'vocals', 'live', 'drop', 'drops', 'tuned'
        }
        generic_adj_stop = {
            'raw', 'soulful', 'earthy', 'gritty', 'moody', 'dark', 'emotive',
            'emotional', 'passionate', 'cinematic', 'atmospheric', 'dramatic',
            'nostalgic', 'retro', 'vintage', 'classic', 'modern', 'organic'
        }
        # Helper: crude stem to avoid near-duplicates
        def stem(word: str) -> str:
            return re.sub(r'(ing|ed|ly|ical|icity|icity|ous|ness|ment|s)$', '', word.lower())
        normalized = style_text.replace('\n', ',')
        parts = [p.strip() for p in re.split(r'[;,\|/]', normalized) if p.strip()]
        
        keywords: list[str] = []
        seen = set()
        
        for part in parts:
            clean_part = re.sub(r'\s+', ' ', part).strip(' -')
            if not clean_part:
                continue
            words = re.findall(r"[A-Za-z0-9']+", clean_part)
            for word in words:
                if len(word) <= 2:
                    continue
                if word.isdigit():
                    continue
                lowered = word.lower()
                if lowered in gender_stop:
                    continue
                if lowered in style_stop:
                    continue
                if lowered in filler_stop:
                    continue
                if lowered in name_stop:
                    continue
                if lowered in instrument_stop:
                    continue
                if lowered in nonstyle_stop:
                    continue
                if lowered in generic_adj_stop:
                    continue
                if lowered in band_name_lc:
                    continue
                stemmed = stem(lowered)
                if stemmed in seen:
                    continue
                keywords.append(word)
                seen.add(stemmed)
                if len(keywords) >= 3:
                    return keywords
        
        if len(keywords) < 3:
            fallback_words = [
                w for w in re.findall(r"[A-Za-z0-9']+", style_text) if len(w) > 2
            ]
            for word in fallback_words:
                lowered = word.lower()
                if lowered in gender_stop:
                    continue
                if lowered in style_stop:
                    continue
                if lowered in filler_stop:
                    continue
                if lowered in name_stop:
                    continue
                if lowered in instrument_stop:
                    continue
                if lowered in nonstyle_stop:
                    continue
                if lowered in generic_adj_stop:
                    continue
                if lowered in band_name_lc:
                    continue
                stemmed = stem(lowered)
                if stemmed in seen:
                    continue
                keywords.append(word)
                seen.add(stemmed)
                if len(keywords) >= 3:
                    break
        
        # Backup pass: if still empty, harvest from any remaining words (non-stop)
        if not keywords:
            tokens = re.findall(r"[A-Za-z0-9']+", style_text)
            for word in tokens:
                if len(word) <= 2:
                    continue
                lowered = word.lower()
                if lowered in gender_stop or lowered in style_stop or lowered in filler_stop or lowered in name_stop or lowered in instrument_stop or lowered in nonstyle_stop or lowered in generic_adj_stop or lowered in band_name_lc:
                    continue
                stemmed = stem(lowered)
                if stemmed in seen:
                    continue
                keywords.append(word)
                seen.add(stemmed)
                if len(keywords) >= 3:
                    break

        return keywords[:3]

    def _extract_major_keyword(self, text: str) -> str:
        """Extract a simple major keyword from text (lyrics or prompt) using AI."""
        if not text:
            return ''
        
        # Try AI extraction first
        try:
            prompt = f"""Extract the single most important keyword from the following text. 
The keyword should be the main theme, subject, or central concept.

Text:
{text}

Return only the single most important keyword, nothing else. Just one word."""
            
            system_message = "You are a keyword extraction assistant. Extract the single most important keyword from the given text. Return only the keyword, no explanation or additional text."
            
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=50, temperature=0.3)
            
            if result.get('success') and result.get('content'):
                keyword = result.get('content', '').strip()
                # Clean up the response - remove quotes, extra whitespace, and take first word if multiple
                keyword = keyword.strip('"\'')
                keyword = keyword.split()[0] if keyword.split() else ''
                # Remove any trailing punctuation
                keyword = re.sub(r'[^\w\s-]', '', keyword)
                if keyword and len(keyword) > 2:
                    return keyword.lower()
        except Exception as e:
            self.log_debug('DEBUG', f'AI keyword extraction failed, falling back to rule-based: {e}')
        
        # Fallback to rule-based extraction if AI fails
        clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        words = [w.lower() for w in clean.split() if len(w) > 3]
        stop = {'this', 'that', 'with', 'from', 'into', 'over', 'under', 'about', 'above', 'below', 'there', 'here', 'they', 'them', 'were', 'your', 'yours', 'their', 'the', 'and', 'for', 'into', 'onto', 'upon', 'have', 'will', 'shall', 'would', 'could', 'should', 'ever', 'never'}
        words = [w for w in words if w not in stop]
        if not words:
            return ''
        # Pick the longest meaningful word as a crude "major keyword"
        words.sort(key=lambda w: (-len(w), w))
        return words[0]
    
    def azure_ai(self, prompt: str, system_message: str | None = None, profile: str = 'text', max_tokens: int = 8000, temperature: float | None = 0.7) -> dict:
        """Wrapper to call Azure AI and log the prompt/system message."""
        self.log_prompt_debug('Azure AI prompt', prompt, system_message)
        return call_azure_ai(self.ai_config, prompt, system_message=system_message, profile=profile, max_tokens=max_tokens, temperature=temperature)
    
    def azure_vision(self, image_paths: list, prompt: str, system_message: str | None = None, profile: str = 'text') -> dict:
        """Wrapper to call Azure Vision and log the prompt/system message."""
        self.log_prompt_debug('Azure Vision prompt', prompt, system_message)
        processed_paths = []
        for idx, path in enumerate(image_paths or []):
            try:
                with Image.open(path) as img:
                    # Skip if already small or explicitly downscaled
                    if max(img.width, img.height) <= 1536 or 'downscaled' in os.path.basename(path).lower():
                        processed_paths.append(path)
                        continue
                    new_w = max(1, img.width // 2)
                    new_h = max(1, img.height // 2)
                    downscaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    temp_dir = os.path.join(self.current_song_path or os.path.dirname(path) or os.getcwd(), 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    base, ext = os.path.splitext(os.path.basename(path))
                    out_path = os.path.join(temp_dir, f"{base}_downscaled{ext if ext else '.png'}")
                    downscaled.save(out_path, 'PNG')
                    processed_paths.append(out_path)
                    self.log_debug('DEBUG', f'Downscaled {path} to {out_path} ({img.width}x{img.height} -> {new_w}x{new_h}) before Azure Vision')
            except Exception as exc:
                self.log_debug('WARNING', f'Failed to downscale image {path}: {exc}')
                processed_paths.append(path)
        return call_azure_vision(self.ai_config, processed_paths if processed_paths else image_paths, prompt, system_message=system_message, profile=profile)
    
    def _get_available_image_profiles(self):
        """Get list of available image generation profiles from config.
        
        Returns profiles that are marked as image generation profiles via the
        'is_image_profile' flag, or profiles with 'image' in the name or
        'dall' in the model name (for backward compatibility).
        """
        if not hasattr(self, 'ai_config') or not self.ai_config:
            return ['image_gen']
        
        profiles = self.ai_config.get('profiles', {})
        available = []
        
        for profile_name, profile_data in profiles.items():
            # Check if explicitly marked as image profile
            if profile_data.get('is_image_profile', False):
                available.append(profile_name)
            # Backward compatibility: check name or model
            elif 'image' in profile_name.lower() or 'dall' in profile_data.get('model_name', '').lower():
                available.append(profile_name)
        
        # If no profiles found, default to image_gen (if it exists)
        if not available:
            if 'image_gen' in profiles:
                available = ['image_gen']
            elif profiles:
                # Fallback to first profile if no image profiles found
                available = [list(profiles.keys())[0]]
        
        return available if available else ['image_gen']
    
    def azure_image(self, prompt: str, size: str = '1024x1024', profile: str = 'image_gen', quality: str = 'medium', output_format: str = 'png', output_compression: int = 100) -> dict:
        """Wrapper to call Azure Image generation and log the prompt."""
        self.log_prompt_debug('Azure Image prompt', prompt, None)
        return call_azure_image(self.ai_config, prompt, size=size, profile=profile, quality=quality, output_format=output_format, output_compression=output_compression)
    
    def azure_video(self, prompt: str, size: str = '720x1280', seconds: str = '4', profile: str = 'video_gen') -> dict:
        """Wrapper to call Azure Video generation and log the prompt."""
        self.log_prompt_debug('Azure Video prompt', prompt, None)
        return call_azure_video(self.ai_config, prompt, size=size, seconds=seconds, profile=profile)
    
    def azure_transcription(self, audio_file_path: str, profile: str = 'text', language: str | None = None, response_format: str = 'verbose_json', prompt: str | None = None) -> dict:
        """Wrapper to call Azure transcription and log any guidance prompt."""
        if prompt:
            self.log_prompt_debug('Azure Transcription prompt', prompt, None)
        else:
            self.log_debug('PROMPT', 'Azure Transcription prompt: (none provided)')
        return call_azure_audio_transcription(self.ai_config, audio_file_path, profile=profile, language=language, response_format=response_format, prompt=prompt)
    
    def refresh_personas_list(self):
        """Refresh the personas list from the personas directory."""
        for item in self.personas_tree.get_children():
            self.personas_tree.delete(item)
        
        if not os.path.exists(self.personas_path):
            self.log_debug('WARNING', f'Personas directory does not exist: {self.personas_path}')
            return
        
        personas = []
        for item in os.listdir(self.personas_path):
            item_path = os.path.join(self.personas_path, item)
            
            # Skip if not a directory
            if not os.path.isdir(item_path):
                continue
            
            # Skip directories starting with underscore (hidden/temporary)
            if item.startswith('_'):
                continue
            
            # Skip directories without config.json (invalid personas)
            config_file = os.path.join(item_path, 'config.json')
            if not os.path.exists(config_file):
                continue
            
            # Try to load config to verify it's valid
            try:
                config = load_persona_config(item_path)
                # Only include if config loaded successfully
                personas.append((item, config.get('name', item)))
            except Exception:
                # Skip directories with invalid/corrupted config
                continue
        
        personas.sort(key=lambda x: x[1].lower())
        
        for folder_name, display_name in personas:
            self.personas_tree.insert('', tk.END, iid=folder_name, values=(display_name,), tags=(folder_name,))
        
        self.status_var.set(f'Found {len(personas)} personas in {self.personas_path}')
        self.log_debug('INFO', f'Refreshed personas list: {len(personas)} personas')
    
    def on_persona_select(self, event):
        """Handle persona selection."""
        sel = self.personas_tree.selection()
        if not sel:
            return
        
        folder_name = sel[0]
        self.current_persona_path = os.path.join(self.personas_path, folder_name)
        self.current_persona = load_persona_config(self.current_persona_path)
        
        self._ensure_persona_image_preset_state()
        self.refresh_image_preset_controls()
        self.load_persona_info()
        self._load_preset_prompts_into_ui()
        self._load_image_profile_selections()
        self.clear_album_form()
        self.refresh_songs_list()
        self.refresh_album_selector()
        self.refresh_persona_images()
        self.refresh_profile_images_gallery()
        self.update_profile_prompt_from_persona()
        self.refresh_song_preset_options()
        
        self.log_debug('INFO', f'Selected persona: {self.current_persona.get("name", folder_name)}')
    
    def new_persona(self):
        """Create a new persona."""
        dialog = tk.Toplevel(self)
        dialog.title('New Persona')
        dialog.geometry('400x150')
        dialog.transient(self)
        dialog.grab_set()
        
        ttk.Label(dialog, text='Persona Name:', font=('TkDefaultFont', 9, 'bold')).pack(pady=10)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=40)
        name_entry.pack(pady=5, padx=20)
        name_entry.focus_set()
        
        result = [None]
        
        def ok_clicked():
            name = name_var.get().strip()
            if name:
                result[0] = name
                dialog.destroy()
        
        def cancel_clicked():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text='OK', command=ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Return>', lambda e: ok_clicked())
        dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(dialog)
        
        if result[0]:
            safe_name = result[0].replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
            new_persona_path = os.path.join(self.personas_path, safe_name)
            
            if os.path.exists(new_persona_path):
                messagebox.showerror('Error', f'Persona "{safe_name}" already exists!')
                return
            
            new_persona_path = enable_long_paths(new_persona_path)
            os.makedirs(new_persona_path, exist_ok=True)
            os.makedirs(enable_long_paths(os.path.join(new_persona_path, 'AI-Songs')), exist_ok=True)
            
            # Get default image profile
            image_profiles = self._get_available_image_profiles()
            default_image_profile = 'image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen')
            
            config = {
                'name': result[0],
                'age': '',
                'tagline': '',
                'vibe': '',
                'visual_aesthetic': '',
                'base_image_prompt': '',
                'bio': '',
                'genre_tags': [],
                'voice_style': '',
                'lyrics_style': '',
                'image_presets': [
                    {'key': 'default', 'label': 'Main', 'is_default': True}
                ],
                'current_image_preset': 'default',
                'reference_image_profile': default_image_profile,
                'profile_image_profile': default_image_profile
            }
            
            save_persona_config(new_persona_path, config)
            self.refresh_personas_list()
            self.log_debug('INFO', f'Created new persona: {result[0]}')
    
    def delete_persona(self):
        """Delete the selected persona."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona to delete.')
            return
        
        persona_name = self.current_persona.get('name', os.path.basename(self.current_persona_path))
        response = messagebox.askyesno('Delete Persona', f'Are you sure you want to delete "{persona_name}"?\n\nThis will delete the entire persona folder and all its contents!')
        
        if response:
            try:
                shutil.rmtree(self.current_persona_path)
                self.current_persona = None
                self.current_persona_path = None
                self.current_song = None
                self.current_song_path = None
                self.refresh_personas_list()
                self.clear_persona_info()
                self.clear_songs_list()
                self.refresh_profile_images_gallery()
                self.log_debug('INFO', f'Deleted persona: {persona_name}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete persona: {e}')
                self.log_debug('ERROR', f'Failed to delete persona: {e}')
    
    def create_persona_tab(self, parent):
        """Create the persona info editing tab."""
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling for persona tab canvas (Windows and Linux)
        def on_mousewheel_persona(event):
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                canvas.yview_scroll(1, "units")
        canvas.bind("<MouseWheel>", on_mousewheel_persona)
        canvas.bind("<Button-4>", on_mousewheel_persona)
        canvas.bind("<Button-5>", on_mousewheel_persona)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel_persona)
        scrollable_frame.bind("<Button-4>", on_mousewheel_persona)
        scrollable_frame.bind("<Button-5>", on_mousewheel_persona)
        
        self.persona_fields = {}
        self.persona_widgets = {}
        
        fields = [
            ('name', 'Name', False),
            ('age', 'Age', False),
            ('tagline', 'Tagline', True),
            ('vibe', 'Vibe', True),
            ('visual_aesthetic', 'Visual Aesthetic', True),
            ('base_image_prompt', 'Base Image Prompt', True),
            ('bio', 'Bio (Backstory)', True),
            ('voice_style', 'Voice Style (From Suno)', True),
            ('lyrics_style', 'Lyrics Style (For Auto Generation)', True),
            ('spotify_link', 'Spotify Link', False),
            ('itunes_link', 'iTunes Link', False),
            ('youtube_music_link', 'YouTube Music Link', False)
        ]
        
        row = 0
        for key, label, is_multiline in fields:
            ttk.Label(scrollable_frame, text=f'{label}:', font=('TkDefaultFont', 9, 'bold')).grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=5
            )
            
            if is_multiline:
                text_frame = ttk.Frame(scrollable_frame)
                text_frame.grid(row=row, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
                
                text_widget = scrolledtext.ScrolledText(text_frame, height=3, wrap=tk.WORD, width=60)
                text_widget.pack(fill=tk.BOTH, expand=True)
                
                btn_frame = ttk.Frame(scrollable_frame)
                btn_frame.grid(row=row, column=2, padx=5, pady=5, sticky=tk.N)
                
                # Special handling for lyrics_style field - add Generate and Improve buttons
                if key == 'lyrics_style':
                    ttk.Button(btn_frame, text='Generate', command=self.generate_lyrics_style).pack(fill=tk.X, pady=(0, 2))
                    ttk.Button(btn_frame, text='Improve', command=self.improve_lyrics_style).pack(fill=tk.X, pady=(0, 2))
                    ttk.Button(btn_frame, text='AI Enhance', command=lambda k=key: self.ai_enhance_persona_field(k)).pack(fill=tk.X)
                else:
                    ttk.Button(btn_frame, text='AI Enhance', command=lambda k=key: self.ai_enhance_persona_field(k)).pack()
                
                self.persona_widgets[key] = text_widget
            else:
                var = tk.StringVar()
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=60)
                entry.grid(row=row, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
                
                btn_frame = ttk.Frame(scrollable_frame)
                btn_frame.grid(row=row, column=2, padx=5, pady=5)
                ttk.Button(btn_frame, text='AI Enhance', command=lambda k=key: self.ai_enhance_persona_field(k)).pack()
                
                self.persona_fields[key] = var
                self.persona_widgets[key] = entry
            
            row += 1
        
        genre_frame = ttk.LabelFrame(scrollable_frame, text='Genre Tags', padding=5)
        genre_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W+tk.E, padx=5, pady=5)
        
        self.genre_tags_text = scrolledtext.ScrolledText(genre_frame, height=3, wrap=tk.WORD, width=60)
        self.genre_tags_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(genre_frame, text='AI Enhance', command=lambda: self.ai_enhance_persona_field('genre_tags')).pack(pady=(5, 0))
        
        row += 1
        
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=10)
        
        ttk.Button(btn_frame, text='Save Persona', command=self.save_persona).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Reset Persona', command=self.reset_persona).pack(side=tk.LEFT, padx=5)
        
        scrollable_frame.columnconfigure(1, weight=1)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_images_tab(self, parent):
        """Create the persona images preview tab."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        preset_bar = ttk.Frame(main_frame)
        preset_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(preset_bar, text='Persona image preset:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 6))
        self.image_preset_var = tk.StringVar(value='default')
        self.image_preset_combo = ttk.Combobox(preset_bar, textvariable=self.image_preset_var, state='readonly', width=18)
        self.image_preset_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.image_preset_combo.bind('<<ComboboxSelected>>', self.on_image_preset_change)
        ttk.Button(preset_bar, text='New Preset', command=self.add_image_preset).pack(side=tk.LEFT, padx=4)
        ttk.Button(preset_bar, text='Set Default', command=self.set_default_image_preset).pack(side=tk.LEFT, padx=4)
        self.image_preset_caption_var = tk.StringVar(value='Using preset: default')
        ttk.Label(preset_bar, textvariable=self.image_preset_caption_var, foreground='gray').pack(side=tk.LEFT, padx=10)
        
        ttk.Label(main_frame, text='Reference Images Preview', font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 10))
        
        # Container for images
        images_container = ttk.Frame(main_frame)
        images_container.pack(fill=tk.BOTH, expand=True)
        
        # Create frames for each view
        self.image_frames = {}
        self.image_labels = {}
        self.image_photos = {}
        self.image_pil_cache = {}  # Cache original PIL images for resize events
        self.image_canvas_items = {}
        
        views = ['Front', 'Side', 'Back']
        for idx, view in enumerate(views):
            frame = ttk.LabelFrame(images_container, text=f'{view} View', padding=5)  # Reduced padding
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky=tk.N+tk.S+tk.E+tk.W)
            
            # Use Canvas for better image scaling - let it expand to fill frame
            canvas = tk.Canvas(frame, bg='white')
            canvas.pack(fill=tk.BOTH, expand=True)
            
            self.image_frames[view] = frame
            self.image_labels[view] = canvas  # Store canvas instead of label
            self.image_photos[view] = None
            self.image_canvas_items = {}  # Store canvas image items
        
        images_container.columnconfigure(0, weight=1)
        images_container.columnconfigure(1, weight=1)
        images_container.columnconfigure(2, weight=1)
        images_container.rowconfigure(0, weight=1)
        
        # Refresh button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text='Refresh Images', command=self.refresh_persona_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Generate Reference Images', command=self.generate_reference_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Generate From Reference Images', command=self.generate_from_reference_images).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(btn_frame, text='API Profile:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(10, 2))
        image_profiles = self._get_available_image_profiles()
        default_ref_profile = 'image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen')
        self.reference_image_profile_var = tk.StringVar(value=default_ref_profile)
        reference_image_profile_combo = ttk.Combobox(btn_frame, textvariable=self.reference_image_profile_var, 
                                                     values=image_profiles, state='readonly', width=15)
        reference_image_profile_combo.pack(side=tk.LEFT, padx=2)
        # Save profile selection when changed
        self.reference_image_profile_var.trace_add('write', lambda *args: self._save_image_profile_selections())
        
        ttk.Button(btn_frame, text='Regenerate Front', command=lambda: self.generate_single_reference_view('Front')).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text='Regenerate Side', command=lambda: self.generate_single_reference_view('Side')).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text='Regenerate Back', command=lambda: self.generate_single_reference_view('Back')).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text='Delete All Reference Images', command=self.delete_persona_reference_images).pack(side=tk.RIGHT, padx=5)

        # Profile image generator (lives here so prompts sit with persona reference context)
        profile_frame = ttk.LabelFrame(main_frame, text='Profile Image Generator', padding=8)
        profile_frame.pack(fill=tk.BOTH, expand=False, pady=(12, 0))
        
        ttk.Label(
            profile_frame,
            text='Create profile portraits that match the persona reference shots and theme. Customize the scene prompt and generate multiple variations.',
            wraplength=1200
        ).pack(fill=tk.X, pady=(0, 6))
        
        prompt_toolbar = ttk.Frame(profile_frame)
        prompt_toolbar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(prompt_toolbar, text='Reset From Persona', command=lambda: self.update_profile_prompt_from_persona(force=True)).pack(side=tk.LEFT, padx=(0, 6))
        
        ttk.Label(prompt_toolbar, text='Images to create:').pack(side=tk.LEFT, padx=(12, 4))
        self.profile_image_count_var = tk.IntVar(value=2)
        tk.Spinbox(prompt_toolbar, from_=1, to=10, width=5, textvariable=self.profile_image_count_var).pack(side=tk.LEFT)
        ttk.Label(prompt_toolbar, text='(1-10)').pack(side=tk.LEFT, padx=(4, 0))
        
        ttk.Label(prompt_toolbar, text='API Profile:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(12, 2))
        image_profiles = self._get_available_image_profiles()
        default_profile_profile = 'image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen')
        self.profile_image_profile_var = tk.StringVar(value=default_profile_profile)
        profile_image_profile_combo = ttk.Combobox(prompt_toolbar, textvariable=self.profile_image_profile_var, 
                                                   values=image_profiles, state='readonly', width=15)
        profile_image_profile_combo.pack(side=tk.LEFT, padx=2)
        # Save profile selection when changed
        self.profile_image_profile_var.trace_add('write', lambda *args: self._save_image_profile_selections())
        
        ttk.Button(prompt_toolbar, text='Generate Profile Images', command=self.generate_profile_images).pack(side=tk.RIGHT, padx=(6, 0))
        
        ttk.Label(profile_frame, text='Base/profile prompt:').pack(anchor=tk.W)
        self.profile_prompt_text = scrolledtext.ScrolledText(profile_frame, height=4, wrap=tk.WORD)
        self.profile_prompt_text.pack(fill=tk.BOTH, expand=True, pady=(2, 8))
        
        ttk.Label(profile_frame, text='Custom scene / add-on prompt:').pack(anchor=tk.W)
        self.profile_custom_prompt_text = scrolledtext.ScrolledText(profile_frame, height=3, wrap=tk.WORD)
        self.profile_custom_prompt_text.pack(fill=tk.BOTH, expand=True, pady=(2, 6))
        
        self.profile_status_var = tk.StringVar(value='Ready to create profile images.')
        ttk.Label(profile_frame, textvariable=self.profile_status_var, foreground='gray').pack(anchor=tk.W, pady=(0, 2))
        
        # Initialize prompt content
        self.update_profile_prompt_from_persona()

    def refresh_image_preset_controls(self):
        """Refresh preset dropdown and caption for persona images."""
        if not hasattr(self, 'image_preset_combo'):
            return
        presets = self._get_persona_image_presets()
        values = [p.get('key', 'default') for p in presets]
        self.image_preset_combo['values'] = values

        target = 'default'
        if self.current_persona:
            target = self.current_persona.get('current_image_preset') or self._get_default_image_preset_key()
        if values and target not in values:
            target = values[0]
        self.image_preset_var.set(target)

        if hasattr(self, 'image_preset_caption_var'):
            default_label = self._get_preset_label(self._get_default_image_preset_key())
            caption = f"Using preset: {self._get_preset_label(target)}"
            if target == self._get_default_image_preset_key():
                caption += " (default)"
            elif default_label:
                caption += f" | Default: {default_label}"
            self.image_preset_caption_var.set(caption)
        self._load_preset_prompts_into_ui(target)

    def on_image_preset_change(self, event=None):
        """Handle preset selection change."""
        if not self.current_persona:
            return
        # Save current UI prompts to the previous preset
        prev_key = self.current_persona.get('current_image_preset')
        self._save_preset_prompts_from_ui(prev_key)
        selected = self.image_preset_var.get() or self._get_default_image_preset_key()
        self.current_persona['current_image_preset'] = selected
        save_persona_config(self.current_persona_path, self.current_persona)
        self.refresh_image_preset_controls()
        self.refresh_persona_images()
        self.refresh_profile_images_gallery()
        self.refresh_song_preset_options()
        self._load_preset_prompts_into_ui(selected)

    def add_image_preset(self):
        """Create a new persona image preset."""
        if not self.current_persona_path or not self.current_persona:
            messagebox.showwarning('Warning', 'Select a persona before adding presets.')
            return
        name = simpledialog.askstring('New Image Preset', 'Preset name (e.g., Stage Look, Casual):', parent=self)
        if not name:
            return
        key = self._safe_filename(name.strip().lower())
        if not key:
            messagebox.showerror('Error', 'Please enter a valid preset name.')
            return
        presets = self._get_persona_image_presets()
        if any(p.get('key') == key for p in presets):
            messagebox.showerror('Error', f'Preset "{key}" already exists.')
            return

        presets.append({'key': key, 'label': name.strip(), 'is_default': False, 'profile_prompt': '', 'profile_custom_prompt': ''})
        self.current_persona['image_presets'] = presets
        self.current_persona['current_image_preset'] = key

        preset_dir = self.get_persona_image_base_path(key)
        os.makedirs(preset_dir, exist_ok=True)
        save_persona_config(self.current_persona_path, self.current_persona)

        self.refresh_image_preset_controls()
        self.refresh_persona_images()
        self.refresh_profile_images_gallery()
        self.refresh_song_preset_options()
        self.log_debug('INFO', f'Added persona image preset: {name.strip()} ({key})')

    def set_default_image_preset(self):
        """Mark the selected preset as default for this persona."""
        if not self.current_persona:
            return
        key = self.image_preset_var.get() or self._get_default_image_preset_key()
        presets = self._get_persona_image_presets()
        changed = False
        for preset in presets:
            was_default = preset.get('is_default', False)
            preset['is_default'] = preset.get('key') == key
            if preset['is_default'] != was_default:
                changed = True
        if changed:
            self.current_persona['image_presets'] = presets
            self.current_persona['current_image_preset'] = key
            save_persona_config(self.current_persona_path, self.current_persona)
            self.refresh_image_preset_controls()
            self.refresh_song_preset_options()
            self.log_debug('INFO', f'Set default image preset: {key}')
    
    def refresh_persona_images(self):
        """Refresh the persona images preview."""
        # Check if images tab has been created
        if not hasattr(self, 'image_labels') or not self.image_labels:
            return
        
        if not self.current_persona_path:
            # Clear all images
            for view in ['Front', 'Side', 'Back']:
                if view in self.image_labels:
                    canvas = self.image_labels[view]
                    canvas.delete('all')
                    canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2, 
                                     text='No persona selected', font=('TkDefaultFont', 9))
                    self.image_photos[view] = None
                    if view in self.image_pil_cache:
                        del self.image_pil_cache[view]
            return
        
        views = ['Front', 'Side', 'Back']
        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        base_path = self.get_persona_image_base_path(preset_key)
        safe_name = self._safe_persona_basename()
        
        for view in views:
            image_path = os.path.join(base_path, f'{safe_name}-{view}.png')
            canvas = self.image_labels[view]
            
            if os.path.exists(image_path):
                try:
                    # Ensure canvas has a size before trying to draw
                    canvas.update_idletasks()
                    canvas_width = max(400, canvas.winfo_width())
                    canvas_height = max(600, canvas.winfo_height())
                    
                    # Load image using PIL for proper resizing
                    pil_image = Image.open(image_path)
                    original_width, original_height = pil_image.size
                    
                    # Calculate scaling to fill canvas while maintaining aspect ratio
                    # Use full canvas dimensions (minus small padding for borders)
                    target_width = canvas_width - 4  # Small padding
                    target_height = canvas_height - 4  # Small padding
                    
                    scale_w = target_width / original_width
                    scale_h = target_height / original_height
                    scale = min(scale_w, scale_h)  # Maintain aspect ratio, fill as much as possible
                    
                    # Calculate new dimensions
                    new_width = int(original_width * scale)
                    new_height = int(original_height * scale)
                    
                    # Resize image using PIL (high-quality resampling)
                    if scale != 1.0:
                        resized_pil = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    else:
                        resized_pil = pil_image
                    
                    # Convert to PhotoImage for Tkinter
                    photo = ImageTk.PhotoImage(resized_pil)
                    
                    # Center image in canvas
                    x = canvas_width // 2
                    y = canvas_height // 2
                    
                    # Clear canvas and add image
                    canvas.delete('all')
                    canvas.create_image(x, y, image=photo, anchor=tk.CENTER)
                    
                    # Keep references to prevent garbage collection
                    self.image_photos[view] = photo
                    self.image_pil_cache[view] = pil_image  # Keep original PIL image for resize events
                    
                    # Bind resize event to update image when window resizes
                    def on_canvas_resize(event, v=view):
                        c = event.widget
                        cw = max(400, c.winfo_width())
                        ch = max(600, c.winfo_height())
                        
                        # Get original PIL image from cache
                        if v not in self.image_pil_cache:
                            return
                        orig_pil = self.image_pil_cache[v]
                        ow, oh = orig_pil.size
                        
                        # Calculate new scale
                        target_w = cw - 4
                        target_h = ch - 4
                        scale_w = target_w / ow
                        scale_h = target_h / oh
                        scale = min(scale_w, scale_h)
                        
                        nw = int(ow * scale)
                        nh = int(oh * scale)
                        
                        # Resize using PIL
                        resized_pil = orig_pil.resize((nw, nh), Image.Resampling.LANCZOS)
                        resized_photo = ImageTk.PhotoImage(resized_pil)
                        
                        c.delete('all')
                        c.create_image(cw//2, ch//2, image=resized_photo, anchor=tk.CENTER)
                        self.image_photos[v] = resized_photo  # Keep reference
                    
                    canvas.bind('<Configure>', on_canvas_resize)
                    
                except Exception as e:
                    canvas.delete('all')
                    canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2,
                                     text=f'Error loading image:\n{str(e)}', font=('TkDefaultFont', 9))
                    self.image_photos[view] = None
                    if view in self.image_pil_cache:
                        del self.image_pil_cache[view]
                    self.log_debug('ERROR', f'Failed to load {view} image: {e}')
            else:
                canvas.delete('all')
                canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2,
                                 text=f'No {view.lower()} image\n(Generate to create)', font=('TkDefaultFont', 9))
                self.image_photos[view] = None
                if view in self.image_pil_cache:
                    del self.image_pil_cache[view]

    def create_profile_images_tab(self, parent):
        """Create the persona profile images gallery tab."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text='Profile Images', font=('TkDefaultFont', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text='Refresh', command=self.refresh_profile_images_gallery).pack(side=tk.LEFT, padx=6)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        gallery_frame = ttk.Frame(canvas)

        gallery_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=gallery_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_mousewheel_profile(event):
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                canvas.yview_scroll(1, "units")

        canvas.bind("<MouseWheel>", on_mousewheel_profile)
        canvas.bind("<Button-4>", on_mousewheel_profile)
        canvas.bind("<Button-5>", on_mousewheel_profile)
        gallery_frame.bind("<MouseWheel>", on_mousewheel_profile)
        gallery_frame.bind("<Button-4>", on_mousewheel_profile)
        gallery_frame.bind("<Button-5>", on_mousewheel_profile)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.profile_gallery_canvas = canvas
        self.profile_gallery_frame = gallery_frame
        self.profile_image_thumbs = []

        # Initialize prompt content
        self.update_profile_prompt_from_persona()
        self.refresh_profile_images_gallery()

    def refresh_profile_images_gallery(self):
        """Refresh thumbnails for persona profile images."""
        if not hasattr(self, 'profile_gallery_frame'):
            return

        for child in self.profile_gallery_frame.winfo_children():
            child.destroy()
        self.profile_image_thumbs = []

        if not self.current_persona_path:
            ttk.Label(
                self.profile_gallery_frame,
                text='Select a persona to view profile images.',
                foreground='gray'
            ).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            return

        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        base_path = self.get_persona_image_base_path(preset_key)
        persona_name = self.current_persona.get('name', 'persona') if self.current_persona else 'persona'
        safe_name = self._safe_filename(persona_name)
        pattern = os.path.join(base_path, f'{safe_name}-Profile-*.png')
        image_files = glob.glob(pattern)

        def sort_key(path):
            match = re.search(r'Profile-(\d+)\.png', os.path.basename(path))
            if match:
                try:
                    # Return tuple (0, int) so integers sort before strings
                    return (0, int(match.group(1)))
                except ValueError:
                    # Return tuple (1, str) for non-numeric matches
                    return (1, path.lower())
            # Return tuple (1, str) for files without numeric pattern
            return (1, path.lower())

        image_files.sort(key=sort_key)

        if not image_files:
            ttk.Label(
                self.profile_gallery_frame,
                text='No profile images found.\nUse Generate Profile Images in the Persona Images tab.',
                foreground='gray',
                wraplength=480
            ).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            return

        max_cols = 3
        thumb_size = 320

        for idx, image_path in enumerate(image_files):
            row = idx // max_cols
            col = idx % max_cols
            frame = ttk.LabelFrame(self.profile_gallery_frame, text=os.path.basename(image_path), padding=6)
            frame.grid(row=row, column=col, padx=6, pady=6, sticky=tk.NW)

            try:
                pil_image = Image.open(image_path)
                pil_image.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                self.profile_image_thumbs.append(photo)
                ttk.Label(frame, image=photo).pack()
            except Exception as e:
                ttk.Label(frame, text=f'Error loading image:\n{e}', width=42, wraplength=280).pack()

            ttk.Button(frame, text='Open', command=lambda p=image_path: self.open_image_file(p)).pack(fill=tk.X, pady=(4, 0))

    def open_image_file(self, image_path: str):
        """Open an image with the default system viewer."""
        try:
            if sys.platform.startswith('win'):
                os.startfile(image_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', image_path], check=False)
            else:
                subprocess.run(['xdg-open', image_path], check=False)
        except Exception as e:
            messagebox.showerror('Error', f'Could not open image: {e}')
            self.log_debug('ERROR', f'Failed to open image {image_path}: {e}')
    
    def update_profile_prompt_from_persona(self, force: bool = False):
        """Build the profile image prompt from the current persona details."""
        if not hasattr(self, 'profile_prompt_text'):
            return
        
        # If not forcing and there is already content, keep it
        try:
            existing = self.profile_prompt_text.get('1.0', tk.END).strip()
        except Exception:
            existing = ''
        if (not force) and existing:
            return
        
        try:
            self.profile_prompt_text.delete('1.0', tk.END)
        except Exception:
            return
        
        if hasattr(self, 'profile_custom_prompt_text'):
            try:
                # Only clear custom prompt when forcing
                if force:
                    self.profile_custom_prompt_text.delete('1.0', tk.END)
            except Exception:
                pass
        
        if not self.current_persona:
            self.profile_prompt_text.insert('1.0', 'Select a persona to seed the profile prompt from its theme and reference images.')
            if hasattr(self, 'profile_status_var'):
                self.profile_status_var.set('Waiting for persona selection.')
            return
        
        name = self.current_persona.get('name', 'the persona')
        tagline = (self.current_persona.get('tagline') or '').strip()
        vibe = (self.current_persona.get('vibe') or '').strip()
        visual = (self.current_persona.get('visual_aesthetic') or '').strip()
        base_prompt = (self.current_persona.get('base_image_prompt') or '').strip()
        
        theme_bits = []
        if tagline:
            theme_bits.append(f"tagline: {tagline}")
        if vibe:
            theme_bits.append(f"vibe: {vibe}")
        if visual:
            theme_bits.append(f"visual aesthetic: {visual}")
        
        prompt_sections = []
        if base_prompt:
            prompt_sections.append(base_prompt)
        if theme_bits:
            prompt_sections.append("Persona theme cues: " + "; ".join(theme_bits))
        
        prompt_sections.append(
            f"Create a polished head-and-shoulders profile portrait of {name}. Keep the exact same character as the reference Front/Side/Back images with matching facial features, hair, clothing, and colors. Cinematic but clean composition, natural expression, soft directional lighting, shallow depth of field, no text or watermarks."
        )
        
        self.profile_prompt_text.insert('1.0', '\n\n'.join(prompt_sections))
        if hasattr(self, 'profile_status_var'):
            self.profile_status_var.set('Profile prompt seeded from persona.')
    
    def load_persona_info(self):
        """Load persona info into the form."""
        if not self.current_persona:
            return
        
        for key, widget in self.persona_widgets.items():
            if key == 'genre_tags':
                continue
            value = self.current_persona.get(key, '')
            if isinstance(widget, scrolledtext.ScrolledText):
                widget.delete('1.0', tk.END)
                widget.insert('1.0', value)
            elif isinstance(widget, ttk.Entry):
                if key in self.persona_fields:
                    self.persona_fields[key].set(value)
        
        genre_tags = self.current_persona.get('genre_tags', [])
        self.genre_tags_text.delete('1.0', tk.END)
        self.genre_tags_text.insert('1.0', ', '.join(genre_tags) if isinstance(genre_tags, list) else str(genre_tags))
    
    def clear_persona_info(self):
        """Clear persona info form."""
        for key, widget in self.persona_widgets.items():
            if key == 'genre_tags':
                self.genre_tags_text.delete('1.0', tk.END)
            elif isinstance(widget, scrolledtext.ScrolledText):
                widget.delete('1.0', tk.END)
            elif isinstance(widget, ttk.Entry):
                if key in self.persona_fields:
                    self.persona_fields[key].set('')
    
    def save_persona(self):
        """Save persona info to config.json."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona to save.')
            return
        
        config = dict(self.current_persona) if self.current_persona else {}
        for key, widget in self.persona_widgets.items():
            if key == 'genre_tags':
                tags_text = self.genre_tags_text.get('1.0', tk.END).strip()
                tags = [t.strip() for t in tags_text.split(',') if t.strip()]
                config[key] = tags
            elif isinstance(widget, scrolledtext.ScrolledText):
                config[key] = widget.get('1.0', tk.END).strip()
            elif isinstance(widget, ttk.Entry):
                if key in self.persona_fields:
                    config[key] = self.persona_fields[key].get().strip()
        # Preserve image preset metadata
        config['image_presets'] = self._get_persona_image_presets()
        if hasattr(self, 'image_preset_var'):
            config['current_image_preset'] = self.image_preset_var.get() or self._get_default_image_preset_key()
        
        # Save API profile selections
        if hasattr(self, 'reference_image_profile_var'):
            config['reference_image_profile'] = self.reference_image_profile_var.get()
        if hasattr(self, 'profile_image_profile_var'):
            config['profile_image_profile'] = self.profile_image_profile_var.get()
        
        if save_persona_config(self.current_persona_path, config):
            self.current_persona = config
            self.log_debug('INFO', 'Persona saved successfully')
            messagebox.showinfo('Success', 'Persona saved successfully!')
        else:
            messagebox.showerror('Error', 'Failed to save persona.')
            self.log_debug('ERROR', 'Failed to save persona')
    
    def _load_image_profile_selections(self):
        """Load saved API profile selections from persona config."""
        if not self.current_persona:
            return
        
        image_profiles = self._get_available_image_profiles()
        default_profile = 'image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen')
        
        # Load reference image profile
        if hasattr(self, 'reference_image_profile_var'):
            saved_ref_profile = self.current_persona.get('reference_image_profile', default_profile)
            # Validate the saved profile exists in available profiles
            if saved_ref_profile in image_profiles:
                self.reference_image_profile_var.set(saved_ref_profile)
            else:
                self.reference_image_profile_var.set(default_profile)
        
        # Load profile image profile
        if hasattr(self, 'profile_image_profile_var'):
            saved_profile_profile = self.current_persona.get('profile_image_profile', default_profile)
            # Validate the saved profile exists in available profiles
            if saved_profile_profile in image_profiles:
                self.profile_image_profile_var.set(saved_profile_profile)
            else:
                self.profile_image_profile_var.set(default_profile)
    
    def _save_image_profile_selections(self):
        """Save API profile selections to persona config."""
        if not self.current_persona_path or not self.current_persona:
            return
        
        config = dict(self.current_persona)
        
        # Save API profile selections
        if hasattr(self, 'reference_image_profile_var'):
            config['reference_image_profile'] = self.reference_image_profile_var.get()
        if hasattr(self, 'profile_image_profile_var'):
            config['profile_image_profile'] = self.profile_image_profile_var.get()
        
        # Save without showing message (silent save)
        if save_persona_config(self.current_persona_path, config):
            self.current_persona = config
    
    def reset_persona(self):
        """Reset persona info to saved values from config.json."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        response = messagebox.askyesno('Reset Persona', 'Are you sure you want to reset all fields to saved values? Unsaved changes will be lost.')
        if response:
            self.current_persona = load_persona_config(self.current_persona_path)
            self._ensure_persona_image_preset_state()
            self.refresh_image_preset_controls()
            self.refresh_song_preset_options()
            self.load_persona_info()
            self.log_debug('INFO', 'Persona reset to saved values')
            messagebox.showinfo('Success', 'Persona reset to saved values!')
    
    def generate_from_reference_images(self):
        """Generate persona fields from reference images using vision model."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        # Let user select multiple images
        image_paths = filedialog.askopenfilenames(
            title='Select Reference Images',
            filetypes=[
                ('Image Files', '*.png *.jpg *.jpeg *.gif *.webp'),
                ('PNG Files', '*.png'),
                ('JPEG Files', '*.jpg *.jpeg'),
                ('All Files', '*.*')
            ]
        )
        
        if not image_paths:
            return
        
        # Enable long paths for image paths
        image_paths = [enable_long_paths(path) for path in image_paths]
        
        self.log_debug('INFO', f'Processing {len(image_paths)} reference images...')
        self.config(cursor='wait')
        self.update()
        
        try:
            # Build prompt for vision model
            persona_name = self.current_persona.get('name', '')
            current_tagline = self.current_persona.get('tagline', '')
            current_vibe = self.current_persona.get('vibe', '')
            current_visual = self.current_persona.get('visual_aesthetic', '')
            current_base_prompt = self.current_persona.get('base_image_prompt', '')
            
            prompt = f"Analyze these reference images for the AI persona '{persona_name}' and generate improved values for the following fields:\n\n"
            prompt += f"1. Tagline: {current_tagline if current_tagline else '(empty)'}\n"
            prompt += f"2. Vibe: {current_vibe if current_vibe else '(empty)'}\n"
            prompt += f"3. Visual Aesthetic: {current_visual if current_visual else '(empty)'}\n"
            prompt += f"4. Base Image Prompt: {current_base_prompt if current_base_prompt else '(empty)'}\n\n"
            prompt += "Based on the visual elements, style, mood, and aesthetic of these images, provide improved values for each field.\n\n"
            prompt += "IMPORTANT: The Base Image Prompt must be EXTREMELY DETAILED and COMPREHENSIVE. It should include:\n"
            prompt += "- Complete physical appearance (face, body type, height, build)\n"
            prompt += "- Detailed clothing description (garments, colors, textures, patterns, accessories)\n"
            prompt += "- Hair style, color, and details\n"
            prompt += "- Facial features and expressions\n"
            prompt += "- Pose and body language\n"
            prompt += "- Any accessories, jewelry, or props\n"
            prompt += "- Color palette and visual style\n"
            prompt += "- Lighting and atmosphere\n"
            prompt += "- All distinctive visual characteristics visible in the images\n\n"
            prompt += "The Base Image Prompt should be detailed enough to recreate the exact same character consistently in different poses and angles.\n\n"
            prompt += "Output ONLY the values in this exact format:\n\n"
            prompt += "TAGLINE: [improved tagline]\n"
            prompt += "VIBE: [improved vibe]\n"
            prompt += "VISUAL_AESTHETIC: [improved visual aesthetic]\n"
            prompt += "BASE_IMAGE_PROMPT: [extremely detailed and comprehensive base image prompt with all visual characteristics]\n\n"
            prompt += "Do not include any explanations, just the four field values in the format above."
            
            system_message = "You are a visual analysis assistant specializing in creating detailed image generation prompts. Analyze images with extreme attention to detail and extract ALL visual elements, characteristics, colors, textures, styling, and aesthetic details. For the Base Image Prompt, create a comprehensive, highly detailed description that captures every visual aspect of the character. Output ONLY the field values in the requested format, with no additional text."
            
            result = self.azure_vision(list(image_paths), prompt, system_message=system_message, profile='text')
            
            if result['success']:
                content = result['content'].strip()
                self.log_debug('INFO', f'AI Response received (length: {len(content)} chars)')
                self.log_debug('DEBUG', f'Raw AI Response:\n{content[:500]}...')  # Log first 500 chars
                
                # Parse the response to extract field values
                tagline = ''
                vibe = ''
                visual_aesthetic = ''
                base_image_prompt = ''
                
                # Try to parse structured format first
                lines = content.split('\n')
                current_field = None
                current_value = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_field and current_value:
                            value = ' '.join(current_value).strip()
                            if current_field == 'tagline':
                                tagline = value
                            elif current_field == 'vibe':
                                vibe = value
                            elif current_field == 'visual_aesthetic':
                                visual_aesthetic = value
                            elif current_field == 'base_image_prompt':
                                base_image_prompt = value
                            current_value = []
                        current_field = None
                        continue
                    
                    # Check for field markers (case-insensitive)
                    line_lower = line.lower()
                    if 'tagline' in line_lower and ':' in line:
                        if current_field and current_value:
                            value = ' '.join(current_value).strip()
                            if current_field == 'tagline':
                                tagline = value
                        current_field = 'tagline'
                        current_value = [line.split(':', 1)[1].strip()] if ':' in line else []
                    elif 'vibe' in line_lower and ':' in line and 'visual' not in line_lower:
                        if current_field and current_value:
                            value = ' '.join(current_value).strip()
                            if current_field == 'vibe':
                                vibe = value
                        current_field = 'vibe'
                        current_value = [line.split(':', 1)[1].strip()] if ':' in line else []
                    elif 'visual' in line_lower and 'aesthetic' in line_lower and ':' in line:
                        if current_field and current_value:
                            value = ' '.join(current_value).strip()
                            if current_field == 'visual_aesthetic':
                                visual_aesthetic = value
                        current_field = 'visual_aesthetic'
                        current_value = [line.split(':', 1)[1].strip()] if ':' in line else []
                    elif 'base' in line_lower and 'image' in line_lower and 'prompt' in line_lower and ':' in line:
                        if current_field and current_value:
                            value = ' '.join(current_value).strip()
                            if current_field == 'base_image_prompt':
                                base_image_prompt = value
                        current_field = 'base_image_prompt'
                        current_value = [line.split(':', 1)[1].strip()] if ':' in line else []
                    elif current_field:
                        current_value.append(line)
                
                # Handle last field
                if current_field and current_value:
                    value = ' '.join(current_value).strip()
                    if current_field == 'tagline':
                        tagline = value
                    elif current_field == 'vibe':
                        vibe = value
                    elif current_field == 'visual_aesthetic':
                        visual_aesthetic = value
                    elif current_field == 'base_image_prompt':
                        base_image_prompt = value
                
                # Log parsed values
                self.log_debug('INFO', f'Parsed values - Tagline: {len(tagline)} chars, Vibe: {len(vibe)} chars, Visual Aesthetic: {len(visual_aesthetic)} chars, Base Image Prompt: {len(base_image_prompt)} chars')
                if visual_aesthetic:
                    self.log_debug('DEBUG', f'Visual Aesthetic value: {visual_aesthetic[:200]}...')
                
                # Update the fields if values were found
                if tagline and 'tagline' in self.persona_widgets:
                    widget = self.persona_widgets['tagline']
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', tagline)
                
                if vibe and 'vibe' in self.persona_widgets:
                    widget = self.persona_widgets['vibe']
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', vibe)
                
                if visual_aesthetic and 'visual_aesthetic' in self.persona_widgets:
                    widget = self.persona_widgets['visual_aesthetic']
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', visual_aesthetic)
                        self.log_debug('INFO', 'Visual Aesthetic field updated successfully')
                    else:
                        self.log_debug('WARNING', f'Visual Aesthetic widget is not ScrolledText, it is {type(widget)}')
                else:
                    if not visual_aesthetic:
                        self.log_debug('WARNING', 'Visual Aesthetic value is empty, not updating')
                    if 'visual_aesthetic' not in self.persona_widgets:
                        self.log_debug('WARNING', 'Visual Aesthetic widget not found in persona_widgets')
                
                if base_image_prompt and 'base_image_prompt' in self.persona_widgets:
                    widget = self.persona_widgets['base_image_prompt']
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', base_image_prompt)
                        self.log_debug('INFO', 'Base Image Prompt field updated successfully')
                    else:
                        self.log_debug('WARNING', f'Base Image Prompt widget is not ScrolledText, it is {type(widget)}')
                else:
                    if not base_image_prompt:
                        self.log_debug('WARNING', 'Base Image Prompt value is empty, not updating')
                    if 'base_image_prompt' not in self.persona_widgets:
                        self.log_debug('WARNING', 'Base Image Prompt widget not found in persona_widgets')
                
                # Log summary of what was updated
                updated_fields = []
                if tagline: updated_fields.append('Tagline')
                if vibe: updated_fields.append('Vibe')
                if visual_aesthetic: updated_fields.append('Visual Aesthetic')
                if base_image_prompt: updated_fields.append('Base Image Prompt')
                
                self.log_debug('INFO', f'Fields updated from reference images: {", ".join(updated_fields) if updated_fields else "None"}')
                messagebox.showinfo('Success', f'Persona fields updated from reference images!\n\nUpdated: {", ".join(updated_fields) if updated_fields else "None"}')
            else:
                messagebox.showerror('Error', f'Failed to analyze images: {result["error"]}')
                self.log_debug('ERROR', f'Failed to analyze images: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error processing images: {e}')
            self.log_debug('ERROR', f'Error processing images: {e}')
        finally:
            self.config(cursor='')
    
    def ai_enhance_persona_field(self, field_key: str):
        """Enhance a persona field using AI."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        current_value = ''
        if field_key == 'genre_tags':
            current_value = self.genre_tags_text.get('1.0', tk.END).strip()
        elif field_key in self.persona_widgets:
            widget = self.persona_widgets[field_key]
            if isinstance(widget, scrolledtext.ScrolledText):
                current_value = widget.get('1.0', tk.END).strip()
            elif isinstance(widget, ttk.Entry):
                if field_key in self.persona_fields:
                    current_value = self.persona_fields[field_key].get().strip()
        
        field_labels = {
            'name': 'Name',
            'age': 'Age',
            'tagline': 'Tagline',
            'vibe': 'Vibe',
            'visual_aesthetic': 'Visual Aesthetic',
            'base_image_prompt': 'Base Image Prompt',
            'bio': 'Bio (Backstory)',
            'voice_style': 'Voice Style',
            'lyrics_style': 'Lyrics Style',
            'genre_tags': 'Genre Tags'
        }
        
        dialog = AIPromptDialog(self, field_labels.get(field_key, field_key), current_value)
        self.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        extra_instructions = dialog.result
        
        persona_context = f"Persona Name: {self.current_persona.get('name', '')}\n"
        persona_context += f"Age: {self.current_persona.get('age', '')}\n"
        persona_context += f"Tagline: {self.current_persona.get('tagline', '')}\n"
        persona_context += f"Vibe: {self.current_persona.get('vibe', '')}\n"
        persona_context += f"Bio: {self.current_persona.get('bio', '')}\n"
        
        prompt = f"Given this persona information:\n\n{persona_context}\n\n"
        prompt += f"Current {field_labels.get(field_key, field_key)} value: {current_value}\n\n"
        prompt += f"Please improve or generate a better {field_labels.get(field_key, field_key)} for this persona."
        
        if extra_instructions:
            prompt += f"\n\nAdditional instructions: {extra_instructions}"
        
        # Create system message to ensure output-only behavior
        system_message = f"You are a field value generator. Output ONLY the {field_labels.get(field_key, field_key)} value itself, with no explanations, no labels, no additional text, and no markdown formatting. Just the raw value that should go directly into the field."
        
        if field_key == 'genre_tags':
            prompt += "\n\nOutput as a comma-separated list of genre tags."
            system_message += " Output as a comma-separated list only."
        elif field_key in ['bio', 'visual_aesthetic', 'base_image_prompt']:
            prompt += "\n\nProvide a detailed, comprehensive response."
            system_message += " Provide a detailed, comprehensive response."
        else:
            # For simple fields like tagline, name, age, etc., emphasize brevity
            system_message += " Keep it concise and direct."
        
        self.log_debug('INFO', f'Enhancing {field_key} with AI...')
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, system_message=system_message, profile='text')
            
            if result['success']:
                enhanced_value = result['content'].strip()
                
                # Clean up the response to extract only the value
                # Remove common prefixes and explanations
                lines = enhanced_value.split('\n')
                # If there are multiple lines, try to find the actual value
                # Often AI puts explanations first, then the value
                if len(lines) > 1:
                    # Look for lines that don't contain explanatory phrases
                    value_lines = []
                    skip_phrases = ['here are', 'here is', 'suggestions', 'options', 'alternatives', 
                                   'improved', 'better', 'consider', 'you can', 'pick one', 'try']
                    for line in lines:
                        line_lower = line.lower().strip()
                        # Skip empty lines and lines with explanatory phrases
                        if line_lower and not any(phrase in line_lower for phrase in skip_phrases):
                            # Remove markdown formatting
                            clean_line = line.replace('**', '').replace('*', '').replace('_', '').strip()
                            if clean_line:
                                value_lines.append(clean_line)
                    
                    # If we found clean value lines, use the first one (or join if multiple short ones)
                    if value_lines:
                        if field_key == 'genre_tags':
                            # For genre tags, join all clean lines
                            enhanced_value = ', '.join(value_lines)
                        else:
                            # For other fields, use first substantial line
                            enhanced_value = value_lines[0] if len(value_lines[0]) > 10 else ' '.join(value_lines[:2])
                
                # Remove markdown formatting that might remain
                enhanced_value = enhanced_value.replace('**', '').replace('*', '').replace('_', '').strip()
                
                if field_key == 'genre_tags':
                    self.genre_tags_text.delete('1.0', tk.END)
                    self.genre_tags_text.insert('1.0', enhanced_value)
                elif field_key in self.persona_widgets:
                    widget = self.persona_widgets[field_key]
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', enhanced_value)
                    elif isinstance(widget, ttk.Entry):
                        if field_key in self.persona_fields:
                            self.persona_fields[field_key].set(enhanced_value)
                
                self.log_debug('INFO', f'{field_key} enhanced successfully')
            else:
                messagebox.showerror('Error', f'Failed to enhance {field_key}: {result["error"]}')
                self.log_debug('ERROR', f'Failed to enhance {field_key}: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error enhancing {field_key}: {e}')
            self.log_debug('ERROR', f'Error enhancing {field_key}: {e}')
        finally:
            self.config(cursor='')
    
    def generate_lyrics_style(self):
        """Generate a comprehensive lyrics_style based on persona data."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        persona_name = self.current_persona.get('name', '')
        tagline = self.current_persona.get('tagline', '')
        vibe = self.current_persona.get('vibe', '')
        bio = self.current_persona.get('bio', '')
        voice_style = self.current_persona.get('voice_style', '')
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
        genre_tags = self.current_persona.get('genre_tags', [])
        genre_text = ', '.join(genre_tags) if isinstance(genre_tags, list) else str(genre_tags or '')
        
        prompt = f"""Analyze this musical persona and generate a comprehensive LYRICS STYLE definition.

=== PERSONA DATA ===
Name: {persona_name}
Tagline: {tagline}
Vibe: {vibe}
Bio: {bio[:500] if bio else 'Not provided'}
Voice Style: {voice_style}
Visual Aesthetic: {visual_aesthetic}
Genre Tags: {genre_text}

=== TASK ===
Create a detailed lyrics_style definition that will guide AI lyric generation for this persona.

The lyrics_style should define:
1. NARRATIVE APPROACH: How stories are told (first-person confessional, third-person observer, stream of consciousness, etc.)
2. EMOTIONAL REGISTER: The emotional range and intensity (raw vulnerability, controlled tension, explosive catharsis, etc.)
3. IMAGERY PREFERENCES: Types of images and metaphors that fit this persona (urban decay, natural elements, technological, domestic, etc.)
4. VOCABULARY LEVEL: Word choice character (street vernacular, poetic elevated, technical jargon, simple direct, etc.)
5. THEMATIC OBSESSIONS: Recurring themes this persona would explore (loss, rebellion, love, identity, survival, etc.)
6. STRUCTURAL TENDENCIES: Preferred lyrical structures (short punchy lines, flowing prose-like verses, call-and-response, etc.)
7. UNIQUE VOICE MARKERS: Specific phrases, verbal tics, or stylistic signatures that make this persona distinctive

=== CRITICAL RULES ===
- Be SPECIFIC to this persona - avoid generic descriptions
- Focus on what makes this artist's lyrics UNIQUE and RECOGNIZABLE
- Include guidance that helps AVOID cliched or overused imagery
- The style should feel like a creative brief for a songwriter

=== OUTPUT FORMAT ===
Provide a single paragraph (150-250 words) that captures all these elements in a flowing, usable style definition.
Do NOT use bullet points or numbered lists - write it as cohesive prose.
Output ONLY the lyrics_style text, no explanations or labels."""

        system_message = (
            "You are a music industry A&R specialist and lyricist who creates detailed artist style guides. "
            "Your output will be used directly as a lyrics_style field to guide AI lyric generation. "
            "Be specific, creative, and focused on what makes each artist unique. "
            "Output ONLY the style definition text - no labels, explanations, or formatting."
        )
        
        self.log_debug('INFO', 'Generating lyrics_style from persona data...')
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=1000)
            
            if result['success']:
                generated_style = result['content'].strip()
                # Clean up any markdown or labels
                generated_style = generated_style.replace('**', '').replace('*', '').strip()
                # Remove common prefixes if AI added them
                for prefix in ['Lyrics Style:', 'lyrics_style:', 'Style:', 'Here is', 'Here\'s']:
                    if generated_style.lower().startswith(prefix.lower()):
                        generated_style = generated_style[len(prefix):].strip()
                
                # Update the lyrics_style widget
                if 'lyrics_style' in self.persona_widgets:
                    widget = self.persona_widgets['lyrics_style']
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.delete('1.0', tk.END)
                        widget.insert('1.0', generated_style)
                
                self.log_debug('INFO', 'lyrics_style generated successfully')
                messagebox.showinfo('Success', 'Lyrics style generated from persona data.')
            else:
                messagebox.showerror('Error', f'Failed to generate lyrics_style: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate lyrics_style: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating lyrics_style: {e}')
            self.log_debug('ERROR', f'Error generating lyrics_style: {e}')
        finally:
            self.config(cursor='')
    
    def improve_lyrics_style(self):
        """Improve the existing lyrics_style with user customization options."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        # Get current lyrics_style
        current_style = ''
        if 'lyrics_style' in self.persona_widgets:
            widget = self.persona_widgets['lyrics_style']
            if isinstance(widget, scrolledtext.ScrolledText):
                current_style = widget.get('1.0', tk.END).strip()
        
        if not current_style:
            # If empty, offer to generate instead
            if messagebox.askyesno('No Lyrics Style', 'No lyrics style defined yet. Would you like to generate one from persona data?'):
                self.generate_lyrics_style()
            return
        
        # Create improvement dialog
        dialog = tk.Toplevel(self)
        dialog.title('Improve Lyrics Style')
        dialog.geometry('600x500')
        dialog.transient(self)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Current style display
        ttk.Label(main_frame, text='Current Lyrics Style:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        current_display = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        current_display.pack(fill=tk.X, pady=(5, 10))
        current_display.insert('1.0', current_style)
        current_display.config(state='disabled')
        
        # Improvement options
        ttk.Label(main_frame, text='Improvement Direction:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        
        direction_var = tk.StringVar(value='enhance')
        directions_frame = ttk.Frame(main_frame)
        directions_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(directions_frame, text='Enhance & Expand', variable=direction_var, value='enhance').pack(anchor=tk.W)
        ttk.Radiobutton(directions_frame, text='Make More Unique/Distinctive', variable=direction_var, value='unique').pack(anchor=tk.W)
        ttk.Radiobutton(directions_frame, text='Add Anti-Cliche Guidance', variable=direction_var, value='anticliche').pack(anchor=tk.W)
        ttk.Radiobutton(directions_frame, text='Simplify & Focus', variable=direction_var, value='simplify').pack(anchor=tk.W)
        ttk.Radiobutton(directions_frame, text='Custom Instructions', variable=direction_var, value='custom').pack(anchor=tk.W)
        
        # Custom instructions
        ttk.Label(main_frame, text='Custom Instructions (optional):', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        custom_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD)
        custom_text.pack(fill=tk.X, pady=5)
        custom_text.insert('1.0', 'Add specific guidance here...')
        
        result_holder = {'result': None}
        
        def apply_improvement():
            direction = direction_var.get()
            custom_instructions = custom_text.get('1.0', tk.END).strip()
            if custom_instructions == 'Add specific guidance here...':
                custom_instructions = ''
            
            persona_name = self.current_persona.get('name', '')
            vibe = self.current_persona.get('vibe', '')
            
            direction_prompts = {
                'enhance': "Expand and enrich this lyrics style with more specific, actionable guidance. Add depth to each aspect while maintaining the core identity.",
                'unique': "Make this lyrics style MORE DISTINCTIVE and UNIQUE. Add specific voice markers, unusual imagery preferences, and signature elements that would make lyrics instantly recognizable as this artist.",
                'anticliche': "Add strong anti-cliche guidance to this lyrics style. Include specific words, phrases, and imagery types to AVOID, and suggest fresh alternatives. Focus on preventing generic or overused lyrical tropes.",
                'simplify': "Distill this lyrics style to its essential, most impactful elements. Remove redundancy and focus on the core characteristics that define this artist's unique voice.",
                'custom': f"Modify this lyrics style according to these instructions: {custom_instructions}"
            }
            
            prompt = f"""Improve this lyrics_style definition for the persona "{persona_name}".

=== CURRENT LYRICS STYLE ===
{current_style}

=== PERSONA CONTEXT ===
Vibe: {vibe}

=== IMPROVEMENT DIRECTION ===
{direction_prompts.get(direction, direction_prompts['enhance'])}

{f'Additional instructions: {custom_instructions}' if custom_instructions and direction != 'custom' else ''}

=== OUTPUT REQUIREMENTS ===
- Output ONLY the improved lyrics_style text
- Keep it as flowing prose (150-250 words)
- No bullet points, labels, or explanations
- Make it immediately usable as a creative brief for lyric generation"""

            system_message = (
                "You are a music industry lyricist and style guide specialist. "
                "Improve the given lyrics_style definition to be more effective for guiding AI lyric generation. "
                "Output ONLY the improved style text - no labels, explanations, or formatting."
            )
            
            dialog.config(cursor='wait')
            dialog.update()
            
            try:
                result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=1000)
                
                if result['success']:
                    improved_style = result['content'].strip()
                    improved_style = improved_style.replace('**', '').replace('*', '').strip()
                    for prefix in ['Lyrics Style:', 'lyrics_style:', 'Style:', 'Here is', 'Here\'s', 'Improved:']:
                        if improved_style.lower().startswith(prefix.lower()):
                            improved_style = improved_style[len(prefix):].strip()
                    
                    result_holder['result'] = improved_style
                    dialog.destroy()
                else:
                    messagebox.showerror('Error', f'Failed to improve lyrics_style: {result["error"]}', parent=dialog)
            except Exception as e:
                messagebox.showerror('Error', f'Error improving lyrics_style: {e}', parent=dialog)
            finally:
                dialog.config(cursor='')
        
        def cancel():
            dialog.destroy()
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btn_frame, text='Apply Improvement', command=apply_improvement).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=cancel).pack(side=tk.LEFT, padx=5)
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f'+{x}+{y}')
        
        self.wait_window(dialog)
        
        if result_holder['result']:
            # Update the lyrics_style widget
            if 'lyrics_style' in self.persona_widgets:
                widget = self.persona_widgets['lyrics_style']
                if isinstance(widget, scrolledtext.ScrolledText):
                    widget.delete('1.0', tk.END)
                    widget.insert('1.0', result_holder['result'])
            
            self.log_debug('INFO', 'lyrics_style improved successfully')
            messagebox.showinfo('Success', 'Lyrics style improved.')
    
    def generate_profile_images(self):
        """Generate profile images using persona references and a custom prompt."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            if hasattr(self, 'profile_status_var'):
                self.profile_status_var.set('Select a persona to generate profile images.')
            return
        
        base_prompt = (self.current_persona.get('base_image_prompt') or '').strip()
        preset_base_prompt, preset_custom_prompt = self._get_active_preset_prompts()
        profile_prompt = preset_base_prompt
        custom_prompt = preset_custom_prompt
        
        if not profile_prompt and base_prompt:
            profile_prompt = base_prompt
        if not profile_prompt:
            messagebox.showwarning('Warning', 'Provide a profile prompt or set a Base Image Prompt first.')
            if hasattr(self, 'profile_status_var'):
                self.profile_status_var.set('Add a prompt before generating profile images.')
            return
        
        persona_name = self.current_persona.get('name', 'persona')
        vibe = (self.current_persona.get('vibe') or '').strip()
        visual = (self.current_persona.get('visual_aesthetic') or '').strip()
        tagline = (self.current_persona.get('tagline') or '').strip()
        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        base_path = self.get_persona_image_base_path(preset_key)
        os.makedirs(base_path, exist_ok=True)
        self.current_persona['current_image_preset'] = preset_key
        # Persist prompts into preset record
        self._save_preset_prompts_from_ui(preset_key)
        
        final_prompt = profile_prompt
        theme_bits = []
        if tagline:
            theme_bits.append(f"tagline: {tagline}")
        if vibe:
            theme_bits.append(f"vibe: {vibe}")
        if visual:
            theme_bits.append(f"visual aesthetic: {visual}")
        if theme_bits:
            final_prompt += "\n\nPersona theme cues: " + "; ".join(theme_bits)
        
        final_prompt += "\n\nPROFILE IMAGE REQUIREMENTS: head-and-shoulders or chest-up framing, clean backdrop, flattering cinematic lighting, eye contact, crisp focus, no text, no watermarks."
        
        if custom_prompt:
            final_prompt += f"\n\nCUSTOM SCENE / DETAILS: {custom_prompt}"
        
        # Add reference image description if Front image exists
        safe_name = self._safe_persona_basename()
        front_image_path = os.path.join(base_path, f'{safe_name}-Front.png') if self.current_persona_path else None
        
        if front_image_path and os.path.exists(front_image_path):
            try:
                from PIL import Image
                original_img = Image.open(front_image_path)
                new_width = max(1, original_img.width // 2)
                new_height = max(1, original_img.height // 2)
                downscaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                temp_dir = os.path.join(base_path, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                reference_image_path = os.path.join(temp_dir, f'{safe_name}-Front-downscaled.png')
                backup_path = backup_file_if_exists(reference_image_path)
                if backup_path:
                    self.log_debug('INFO', f'Backed up existing downscaled image to: {backup_path}')
                downscaled_img.save(reference_image_path, 'PNG')
                
                self.config(cursor='wait')
                self.update()
                vision_prompt = (
                    "Analyze this persona reference image in extreme detail. Provide a comprehensive description of the character's appearance, "
                    "including facial features, hair, clothing, colors, accessories, and all visual characteristics. "
                    "This description will be used to ensure the profile image matches the exact same character."
                )
                vision_system = (
                    "You are an image analysis assistant. Provide a highly detailed, objective description of the character's visual appearance "
                    "from the reference image. Focus on all visual characteristics that must stay consistent in the generated profile image."
                )
                vision_result = self.azure_vision([reference_image_path], vision_prompt, system_message=vision_system, profile='text')
                
                if vision_result['success']:
                    character_description = vision_result['content'].strip()
                    final_prompt = (
                        f"REFERENCE CHARACTER DESCRIPTION (from Front Persona Image - MUST MATCH EXACTLY):\n{character_description}\n\n"
                        f"{final_prompt}\n\n"
                        "CRITICAL REQUIREMENT: The profile image MUST feature this exact character with matching facial features, hair, clothing, styling, colors, and overall appearance."
                    )
                    self.log_debug('INFO', 'Added character description from Front Persona Image to profile prompt')
                else:
                    final_prompt += "\n\nIMPORTANT: Use the Front Persona Image as reference. The profile image must match the same character."
                    self.log_debug('WARNING', f'Failed to analyze Front reference image: {vision_result.get("error", "Unknown error")}')
            except Exception as e:
                self.log_debug('WARNING', f'Failed to prepare reference image for profile generation: {e}')
            finally:
                self.config(cursor='')
        
        try:
            count = int(self.profile_image_count_var.get()) if hasattr(self, 'profile_image_count_var') else 1
        except Exception:
            count = 1
        count = max(1, min(count, 10))
        
        if hasattr(self, 'profile_status_var'):
            self.profile_status_var.set(f'Generating {count} profile image(s)...')
        self.log_debug('INFO', f'Generating {count} profile image(s) for persona "{persona_name}"')
        self.config(cursor='wait')
        self.update()
        
        # Find first available index to avoid overwriting existing profile images
        next_index = 1
        while os.path.exists(os.path.join(base_path, f'{safe_name}-Profile-{next_index}.png')):
            next_index += 1
        
        successes = 0
        errors = 0
        last_filename = None
        
        for i in range(count):
            target_index = next_index + i
            filename = os.path.join(base_path, f'{safe_name}-Profile-{target_index}.png')
            variation_prompt = f"{final_prompt}\n\nPROFILE VARIATION {i+1}: keep the same character identity while varying camera angle, lighting, and subtle expression."
            
            try:
                self.log_prompt_debug('Persona Images: profile image', variation_prompt, None)
                selected_profile = self.profile_image_profile_var.get() if hasattr(self, 'profile_image_profile_var') else 'image_gen'
                result = self.azure_image(variation_prompt, size='1024x1024', profile=selected_profile)
                if result['success']:
                    img_bytes = result.get('image_bytes', b'')
                    if img_bytes:
                        backup_path = backup_file_if_exists(filename)
                        if backup_path:
                            self.log_debug('INFO', f'Backed up existing profile image to: {backup_path}')
                        with open(filename, 'wb') as f:
                            f.write(img_bytes)
                        successes += 1
                        last_filename = filename
                        self.log_debug('INFO', f'Profile image saved: {filename}')
                    else:
                        errors += 1
                        self.log_debug('ERROR', f'No image bytes received for profile image #{target_index}')
                else:
                    errors += 1
                    self.log_debug('ERROR', f'Failed to generate profile image #{target_index}: {result.get("error", "Unknown error")}')
            except Exception as e:
                errors += 1
                self.log_debug('ERROR', f'Error generating profile image #{target_index}: {e}')
        
        self.config(cursor='')
        
        if successes:
            messagebox.showinfo('Success', f'Generated {successes} profile image(s). Last saved:\n{last_filename}')
            if hasattr(self, 'profile_status_var'):
                self.profile_status_var.set(f'Generated {successes} profile image(s).')
        else:
            messagebox.showerror('Error', 'Failed to generate any profile images. Check the debug log for details.')
            if hasattr(self, 'profile_status_var'):
                self.profile_status_var.set('Profile image generation failed.')
        
        if errors and successes:
            self.log_debug('WARNING', f'{errors} profile image(s) failed during generation.')
        
        save_persona_config(self.current_persona_path, self.current_persona)
        self.refresh_profile_images_gallery()
    
    def generate_reference_images(self):
        """Generate reference images (Front, Side, Back) for the persona."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        preset_base_prompt, preset_custom_prompt = self._get_active_preset_prompts()
        base_prompt = preset_base_prompt or self.current_persona.get('base_image_prompt', '')
        if not base_prompt:
            messagebox.showwarning('Warning', 'Please set a Base Image Prompt first.')
            return
        if preset_custom_prompt:
            base_prompt = f"{base_prompt}\n\nCUSTOM SCENE DETAILS: {preset_custom_prompt}"
        
        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        base_path = self.get_persona_image_base_path(preset_key)
        os.makedirs(base_path, exist_ok=True)
        self.current_persona['current_image_preset'] = preset_key
        self._save_preset_prompts_from_ui(preset_key)
        safe_name = self._safe_persona_basename()
        front_image_path = None
        
        # Check if this is the first Front image (no Front exists yet)
        current_front_path = os.path.join(base_path, f'{safe_name}-Front.png')
        is_first_front = not os.path.exists(current_front_path)
        
        # Optionally extract face/identity description from default preset Front to keep persona consistent
        default_preset_key = self._get_default_image_preset_key() if hasattr(self, '_get_default_image_preset_key') else 'default'
        default_base_path = self.get_persona_image_base_path(default_preset_key)
        default_front_path = os.path.join(default_base_path, f'{safe_name}-Front.png')
        default_front_description = ''
        
        # CRITICAL: For initial Front image in default preset, use ONLY base_prompt, NO reference images
        is_initial_default_front = is_first_front and preset_key == default_preset_key
        
        if is_initial_default_front:
            # Initial Front image for default profile - use ONLY base_prompt, NO reference images
            self.log_debug('INFO', 'Generating initial Front image for default profile - using ONLY base image prompt, NO reference images')
            default_front_description = ''  # Explicitly set to empty to ensure no reference is used
        elif is_first_front:
            # For regenerations or custom presets, use reference images as before
            # If this is the first Front image, try to use default persona's Front as reference
            default_persona_front = self._find_default_persona_front_image()
            if default_persona_front and os.path.exists(default_persona_front):
                self.log_debug('INFO', f'Using default persona Front image as reference for first Front: {default_persona_front}')
                try:
                    analyze_prompt = (
                        "Analyze this reference image and describe the character's exact facial structure, hair, skin color, and overall appearance. "
                        "Provide a concise but complete identity description focusing on face, hair, and skin tone that must be matched exactly. "
                        "Exclude scene/background; focus on face, hair, skin color, and visible outfit silhouette."
                    )
                    analyze_default = self.azure_vision([default_persona_front], analyze_prompt, profile='text')
                    if analyze_default.get('success'):
                        default_front_description = analyze_default.get('content', '').strip()
                        self.log_debug('INFO', 'Default persona Front identity extracted for first Front generation.')
                    else:
                        self.log_debug('WARNING', f'Failed to analyze default persona Front image: {analyze_default.get("error", "Unknown error")}')
                except Exception as e:
                    self.log_debug('WARNING', f'Error analyzing default persona Front image: {e}')
        
        # ALWAYS use default preset Front image as reference when generating for a custom preset
        if default_preset_key != preset_key and os.path.exists(default_front_path):
            if not default_front_description:
                self.log_debug('INFO', f'Analyzing default preset Front image for identity anchor: {default_front_path}')
                try:
                    analyze_prompt = (
                        "Analyze this reference image and describe the character's exact facial structure, hair, skin color, and overall appearance. "
                        "Provide a concise but complete identity description focusing on face, hair, and skin tone that must be matched exactly. "
                        "Exclude scene/background; focus on face, hair, skin color, and visible outfit silhouette."
                    )
                    analyze_default = self.azure_vision([default_front_path], analyze_prompt, profile='text')
                    if analyze_default.get('success'):
                        default_front_description = analyze_default.get('content', '').strip()
                        self.log_debug('INFO', 'Default preset Front identity extracted for reuse in custom preset.')
                    else:
                        self.log_debug('WARNING', f'Failed to analyze default preset Front image: {analyze_default.get("error", "Unknown error")}')
                except Exception as e:
                    self.log_debug('WARNING', f'Error analyzing default preset Front image: {e}')
            else:
                # If we already have description from default persona, still prioritize default preset Front
                self.log_debug('INFO', f'Using default preset Front image as reference (overriding default persona reference): {default_front_path}')
                try:
                    analyze_prompt = (
                        "Analyze this reference image and describe the character's exact facial structure, hair, skin color, and overall appearance. "
                        "Provide a concise but complete identity description focusing on face, hair, and skin tone that must be matched exactly. "
                        "Exclude scene/background; focus on face, hair, skin color, and visible outfit silhouette."
                    )
                    analyze_default = self.azure_vision([default_front_path], analyze_prompt, profile='text')
                    if analyze_default.get('success'):
                        default_front_description = analyze_default.get('content', '').strip()
                        self.log_debug('INFO', 'Default preset Front identity extracted (overriding default persona).')
                except Exception as e:
                    self.log_debug('WARNING', f'Error analyzing default preset Front image: {e}')
        
        # Step 1: Generate Front image first
        self.log_debug('INFO', 'Generating Front reference image...')
        self.config(cursor='wait')
        self.update()
        
        try:
            # For initial Front image in default preset, use NO reference (identity_snippet stays empty)
            if is_initial_default_front:
                identity_snippet = ""  # Explicitly empty - use ONLY base_prompt
                # Restructure prompt to prioritize base_image_prompt and critical requirements
                prompt = f"""CRITICAL REQUIREMENTS (MUST FOLLOW EXACTLY):
1. FULL BODY VISIBILITY: Show entire figure from head to toe with feet and shoes clearly visible on floor. Do NOT crop ankles, feet, or shoes. Leave generous margin above head and below feet.
2. BACKGROUND: Pure white background only - no beige, no off-white, no textures, no elements.
3. PRIMARY CHARACTER DESCRIPTION (THIS CONTROLS POSE, COMPOSITION, AND STYLING - FOLLOW EXACTLY):
{base_prompt}

VIEW REQUIREMENTS (secondary to character description above):
- Full-body portrait, facing camera straight-on (not profile or 3/4)
- Eyes looking into camera
- Long shot to capture entire height
- Subject centered, no turning away
- Full-length portrait, entire figure in frame
- No cropping, no cut-off body parts, no close-up, no zoom-in

TECHNICAL REQUIREMENTS:
- Professional reference photo, studio photography, clean minimalist composition
- Even studio lighting with subtle dramatic shadows, high quality professional photography
- No background elements, no props except those described in the character description above
- Sharp focus, professional portrait photography style, reference sheet style, full-body shot"""
            else:
                view_specific = (
                    "full-body portrait, facing camera straight-on (not profile or 3/4), "
                    "shoulders squared, eyes looking into camera, standing upright, long shot, "
                    "camera distance set to capture entire height, subject centered, no turning away, "
                    "OVERRIDE any portrait/waist-up/head-and-shoulders/cropped instructions: MUST show entire figure head-to-toe with shoes and feet visible on floor, "
                    "leave margin above head and below feet, do NOT crop ankles or shoes"
                )
                if default_front_description:
                    if default_preset_key != preset_key:
                        # Always use default preset Front as reference for custom presets
                        identity_snippet = f"REFERENCE CHARACTER FROM DEFAULT PRESET FRONT IMAGE (MUST MATCH EXACTLY - face, skin color, hair): {default_front_description}. "
                    elif is_first_front:
                        identity_snippet = f"REFERENCE CHARACTER FROM DEFAULT PERSONA (MUST MATCH EXACTLY - face, skin color, hair): {default_front_description}. "
                    else:
                        identity_snippet = f"IDENTITY ANCHOR FROM DEFAULT PRESET: {default_front_description}. "
                else:
                    identity_snippet = ""
                prompt = f"{view_specific}, {identity_snippet}{base_prompt}, pure white background, "
                prompt += "FULL BODY VISIBLE from head to toe, feet and shoes clearly visible on floor, entire figure in frame, "
                prompt += "full-length portrait, generous margin above head and below feet, no cropping, no cut-off body parts, no close-up, no zoom-in, "
                prompt += "professional reference photo, studio photography, clean minimalist composition, "
                prompt += "even studio lighting with subtle dramatic shadows, high quality professional photography, "
                prompt += "no background elements, no props except those described in the base prompt, "
                prompt += "sharp focus, professional portrait photography style, reference sheet style, full-body shot"
            
            self.log_prompt_debug('Persona Images: Front reference image', prompt, None)
            # Use a supported tall aspect ratio to reduce cropping
            selected_profile = self.reference_image_profile_var.get() if hasattr(self, 'reference_image_profile_var') else 'image_gen'
            result = self.azure_image(prompt, size='1024x1536', profile=selected_profile)
            
            if result['success']:
                img_bytes = result.get('image_bytes', b'')
                if img_bytes:
                    front_filename = os.path.join(base_path, f'{safe_name}-Front.png')
                    backup_path = backup_file_if_exists(front_filename)
                    if backup_path:
                        self.log_debug('INFO', f'Backed up existing Front image to: {backup_path}')
                    with open(front_filename, 'wb') as f:
                        f.write(img_bytes)
                    front_image_path = front_filename
                    self.log_debug('INFO', f'Front reference image saved: {front_filename}')
                    self.refresh_persona_images()
                else:
                    self.log_debug('ERROR', 'No image bytes received for Front view')
                    messagebox.showerror('Error', 'Failed to generate Front image. Cannot generate Side and Back without Front reference.')
                    return
            else:
                self.log_debug('ERROR', f'Failed to generate Front image: {result["error"]}')
                messagebox.showerror('Error', f'Failed to generate Front image: {result["error"]}')
                return
        except Exception as e:
            self.log_debug('ERROR', f'Error generating Front image: {e}')
            messagebox.showerror('Error', f'Error generating Front image: {e}')
            return
        finally:
            self.config(cursor='')
        
        if not front_image_path or not os.path.exists(front_image_path):
            messagebox.showerror('Error', 'Front image was not saved correctly. Cannot proceed with Side and Back generation.')
            return
        
        # Step 2: Analyze Front image to get detailed character description
        self.log_debug('INFO', 'Analyzing Front image to extract character details for matching Side and Back views...')
        self.config(cursor='wait')
        self.update()
        
        character_description = ""
        try:
            analyze_prompt = "Analyze this Front reference image and provide a detailed description of the character's appearance. CRITICAL: You must include: "
            analyze_prompt += "EXACT SKIN COLOR AND TONE (describe precisely - e.g., dark brown, medium tan, light olive, etc.), "
            analyze_prompt += "facial features (face shape, eye color, nose, lips, bone structure), "
            analyze_prompt += "hair (color, texture, style, length), "
            analyze_prompt += "exact clothing details, colors, textures, styling, accessories, pose, lighting style, and all visual characteristics. "
            analyze_prompt += "Output ONLY a detailed character description that can be used to generate matching Side and Back views with the EXACT SAME skin color, facial features, and appearance."
            
            analyze_result = self.azure_vision([front_image_path], analyze_prompt, profile='text')
            
            if analyze_result['success']:
                character_description = analyze_result['content'].strip()
                self.log_debug('INFO', 'Front image analyzed successfully, extracted character description')
            else:
                self.log_debug('WARNING', f'Failed to analyze Front image: {analyze_result["error"]}')
        except Exception as e:
            self.log_debug('WARNING', f'Error analyzing Front image: {e}')
        finally:
            self.config(cursor='')
        
        if not character_description:
            messagebox.showerror('Error', 'Failed to extract character details from Front image. Please regenerate the Front view and try again before generating Side/Back.')
            return
        
        # Step 3: Generate Side and Back using Front image analysis
        views = ['Side', 'Back']
        
        for view in views:
            self.log_debug('INFO', f'Generating {view} reference image matching Front image...')
            self.config(cursor='wait')
            self.update()
            
            try:
                # Build view-specific description
                if view.lower() == 'side':
                    view_specific = (
                        "full-body side profile, facing right, standing upright, long shot, "
                        "camera distance set to capture entire height, subject centered, "
                        "include full figure head-to-toe with shoes/feet visible on floor, leave margin above head and below feet, do NOT crop ankles or shoes"
                    )
                elif view.lower() == 'back':
                    view_specific = (
                        "full-body view from behind, standing upright, long shot, "
                        "camera distance set to capture entire height, subject centered, "
                        "include full figure head-to-toe with shoes/feet visible on floor, leave margin above head and below feet, do NOT crop ankles or shoes"
                    )
                
                # Create prompt that uses the character description from Front image
                if character_description:
                    # Use the analyzed character description to ensure visual consistency
                    # CRITICAL: Emphasize matching skin color and facial features
                    image_prompt = f"REFERENCE CHARACTER FROM FRONT IMAGE (MUST MATCH EXACTLY): {character_description}. "
                    image_prompt += f"CRITICAL REQUIREMENT: The {view.lower()} view MUST have the EXACT SAME skin color, facial features, hair color, and overall appearance as the Front image. "
                    image_prompt += f"{view_specific}, pure white background, "
                else:
                    # Fallback to base prompt if analysis failed
                    image_prompt = f"{base_prompt}, {view_specific}, pure white background, "
                
                image_prompt += "FULL BODY VISIBLE from head to toe, feet and shoes clearly visible on floor, entire figure in frame, "
                image_prompt += "full-length portrait, generous margin above head and below feet, no cropping, no cut-off body parts, no close-up, no zoom-in, "
                image_prompt += "Match the EXACT SAME character appearance, skin color, facial features, clothing, styling, and visual details from the Front reference image, "
                image_prompt += "professional reference photo, studio photography, clean minimalist composition, "
                image_prompt += "even studio lighting with subtle dramatic shadows, high quality professional photography, "
                image_prompt += "no background elements, sharp focus, professional portrait photography style, reference sheet style, full-body shot"
                
                self.log_prompt_debug(f'Persona Images: {view} reference image', image_prompt, None)
                # Use a supported tall aspect ratio to reduce cropping
                selected_profile = self.reference_image_profile_var.get() if hasattr(self, 'reference_image_profile_var') else 'image_gen'
                result_img = self.azure_image(image_prompt, size='1024x1536', profile=selected_profile)
                
                if result_img['success']:
                    img_bytes = result_img.get('image_bytes', b'')
                    if img_bytes:
                        filename = os.path.join(base_path, f'{safe_name}-{view}.png')
                        backup_path = backup_file_if_exists(filename)
                        if backup_path:
                            self.log_debug('INFO', f'Backed up existing {view} image to: {backup_path}')
                        with open(filename, 'wb') as f:
                            f.write(img_bytes)
                        self.log_debug('INFO', f'{view} reference image saved: {filename}')
                        self.refresh_persona_images()
                    else:
                        self.log_debug('ERROR', f'No image bytes received for {view} view')
                else:
                    self.log_debug('ERROR', f'Failed to generate {view} image: {result_img["error"]}')
            except Exception as e:
                self.log_debug('ERROR', f'Error generating {view} image: {e}')
            finally:
                self.config(cursor='')
        
        # Final refresh to ensure all images are displayed
        save_persona_config(self.current_persona_path, self.current_persona)
        self.refresh_persona_images()
        messagebox.showinfo('Success', 'Reference images generation completed. Front generated first, then Side and Back matched to Front.')

    def delete_persona_reference_images(self):
        """Delete all persona reference images (Front, Side, Back) for the current preset."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        base_path = self.get_persona_image_base_path(preset_key)
        safe_name = self._safe_persona_basename()
        
        images_to_delete = []
        views = ['Front', 'Side', 'Back']
        for view in views:
            image_path = os.path.join(base_path, f'{safe_name}-{view}.png')
            if os.path.exists(image_path):
                images_to_delete.append((view, image_path))
        
        if not images_to_delete:
            messagebox.showinfo('Info', 'No reference images found to delete.')
            return
        
        image_list = '\n'.join([f'- {view}: {os.path.basename(path)}' for view, path in images_to_delete])
        preset_label = preset_key if preset_key != 'default' else 'default preset'
        response = messagebox.askyesno(
            'Confirm Delete',
            f'Delete all reference images for "{self.current_persona.get("name", "persona")}" ({preset_label})?\n\n{image_list}\n\nThis action cannot be undone.',
            icon='warning'
        )
        
        if response:
            deleted_count = 0
            failed = []
            for view, image_path in images_to_delete:
                try:
                    os.remove(image_path)
                    deleted_count += 1
                    self.log_debug('INFO', f'Deleted {view} image: {image_path}')
                except Exception as e:
                    failed.append(f'{view}: {str(e)}')
                    self.log_debug('ERROR', f'Failed to delete {view} image: {e}')
            
            if failed:
                messagebox.showerror('Error', f'Deleted {deleted_count} image(s), but failed to delete:\n' + '\n'.join(failed))
            else:
                messagebox.showinfo('Success', f'Successfully deleted {deleted_count} reference image(s).')
                self.refresh_persona_images()
    
    def generate_single_reference_view(self, view: str):
        """Regenerate a single reference view (Front, Side, or Back) for the current persona."""
        view = (view or '').strip().title()
        if view not in ('Front', 'Side', 'Back'):
            messagebox.showwarning('Warning', 'Invalid view selected.')
            return
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        preset_key = self.image_preset_var.get() if hasattr(self, 'image_preset_var') else self.current_persona.get('current_image_preset', 'default')
        default_preset_key = self._get_default_image_preset_key() if hasattr(self, '_get_default_image_preset_key') else 'default'
        base_path = self.get_persona_image_base_path(preset_key)
        os.makedirs(base_path, exist_ok=True)
        self.current_persona['current_image_preset'] = preset_key
        safe_name = self._safe_persona_basename()
        current_front_path = os.path.join(base_path, f'{safe_name}-Front.png')
        
        # Check if this is the initial Front image for default preset
        is_first_front = not os.path.exists(current_front_path)
        is_initial_default_front = is_first_front and preset_key == default_preset_key
        
        # CRITICAL: For initial Front image in default preset, use persona's base_image_prompt directly, NOT preset's profile_prompt
        if is_initial_default_front:
            # Use persona's base_image_prompt directly for initial Front image
            base_prompt = self.current_persona.get('base_image_prompt', '').strip()
            if not base_prompt:
                messagebox.showwarning('Warning', 'Please set a Base Image Prompt first.')
                return
            self.log_debug('INFO', 'Using persona base_image_prompt directly for initial Front image (ignoring preset profile_prompt)')
        else:
            # For regenerations or custom presets, use preset prompts with fallback
            preset_base_prompt, preset_custom_prompt = self._get_active_preset_prompts()
            base_prompt = preset_base_prompt or self.current_persona.get('base_image_prompt', '')
            if not base_prompt:
                messagebox.showwarning('Warning', 'Please set a Base Image Prompt first.')
                return
            if preset_custom_prompt:
                base_prompt = f"{base_prompt}\n\nCUSTOM SCENE DETAILS: {preset_custom_prompt}"
            self._save_preset_prompts_from_ui(preset_key)
        
        default_base_path = self.get_persona_image_base_path(default_preset_key)
        default_front_path = os.path.join(default_base_path, f'{safe_name}-Front.png')
        
        # For Side/Back we need the current Front image as anchor
        current_front_path = os.path.join(base_path, f'{safe_name}-Front.png')
        
        def analyze_identity(path):
            if not os.path.exists(path):
                return ''
            try:
                analyze_prompt = (
                    "Analyze this reference image and describe the character's exact facial structure, hair, and overall appearance. "
                    "Provide a concise but complete identity description to reuse in another style preset. "
                    "Exclude scene/background; focus on face, hair, and visible outfit silhouette."
                )
                result = self.azure_vision([path], analyze_prompt, profile='text')
                if result.get('success'):
                    return result.get('content', '').strip()
                return ''
            except Exception as exc:
                self.log_debug('WARNING', f'Identity analysis failed: {exc}')
                return ''
        
        # Build shared view-specific text
        def build_view_specific(vname, is_initial_default=False):
            if vname == 'Front':
                if is_initial_default:
                    # For initial Front image, use minimal view instructions to let base_image_prompt control the pose/composition
                    return (
                        "full-body portrait, facing camera straight-on (not profile or 3/4), "
                        "eyes looking into camera, long shot, "
                        "camera distance set to capture entire height, subject centered, no turning away, "
                        "MUST show entire figure head-to-toe, "
                        "leave margin above head and below feet, do NOT crop ankles or shoes"
                    )
                else:
                    return (
                        "full-body portrait, facing camera straight-on (not profile or 3/4), "
                        "shoulders squared, eyes looking into camera, standing upright, long shot, "
                        "camera distance set to capture entire height, subject centered, no turning away, "
                        "OVERRIDE any portrait/waist-up/head-and-shoulders/cropped instructions: MUST show entire figure head-to-toe with shoes and feet visible on floor, "
                        "leave margin above head and below feet, do NOT crop ankles or shoes"
                    )
            if vname == 'Side':
                return (
                    "full-body side profile, facing right, standing upright, long shot, "
                    "camera distance set to capture entire height, subject centered, "
                    "include full figure head-to-toe with shoes/feet visible on floor, leave margin above head and below feet, do NOT crop ankles or shoes"
                )
            return (
                "full-body view from behind, standing upright, long shot, "
                "camera distance set to capture entire height, subject centered, "
                "include full figure head-to-toe with shoes/feet visible on floor, leave margin above head and below feet, do NOT crop ankles or shoes"
            )
        
        self.log_debug('INFO', f'Regenerating {view} reference image for preset "{preset_key}"')
        self.config(cursor='wait')
        self.update()
        
        try:
            if view == 'Front':
                # Check if this is the first Front image (no Front exists yet) - already checked above
                # is_first_front already set above
                
                # CRITICAL: For initial Front image in default preset, use ONLY base_prompt, NO reference images
                # is_initial_default_front already set above
                
                identity_snippet = ''
                identity_text = ''
                
                if is_initial_default_front:
                    # Initial Front image for default profile - use ONLY base_prompt, NO reference images
                    self.log_debug('INFO', 'Generating initial Front image for default profile - using ONLY base image prompt, NO reference images')
                else:
                    # For regenerations or custom presets, use reference images as before
                    # If this is the first Front, try to use default persona's Front as reference
                    if is_first_front:
                        default_persona_front = self._find_default_persona_front_image()
                        if default_persona_front and os.path.exists(default_persona_front):
                            self.log_debug('INFO', f'Using default persona Front image as reference for first Front: {default_persona_front}')
                            analyze_prompt = (
                                "Analyze this reference image and describe the character's exact facial structure, hair, skin color, and overall appearance. "
                                "Provide a concise but complete identity description focusing on face, hair, and skin tone that must be matched exactly. "
                                "Exclude scene/background; focus on face, hair, skin color, and visible outfit silhouette."
                            )
                            analyze_result = self.azure_vision([default_persona_front], analyze_prompt, profile='text')
                            if analyze_result.get('success'):
                                identity_snippet = analyze_result.get('content', '').strip()
                                self.log_debug('INFO', 'Default persona Front identity extracted for first Front generation.')
                    
                    # ALWAYS use default preset Front if generating for a custom preset
                    if default_preset_key != preset_key and os.path.exists(default_front_path):
                        if not identity_snippet:
                            identity_snippet = analyze_identity(default_front_path)
                            self.log_debug('INFO', 'Using default preset Front image as reference for custom preset.')
                        else:
                            # Override with default preset Front (takes priority)
                            identity_snippet = analyze_identity(default_front_path)
                            self.log_debug('INFO', 'Default preset Front image overriding default persona reference for custom preset.')
                    
                    if identity_snippet:
                        if default_preset_key != preset_key:
                            # Always use default preset Front as reference for custom presets
                            identity_text = f"REFERENCE CHARACTER FROM DEFAULT PRESET FRONT IMAGE (MUST MATCH EXACTLY - face, skin color, hair): {identity_snippet}. "
                        elif is_first_front:
                            identity_text = f"REFERENCE CHARACTER FROM DEFAULT PERSONA (MUST MATCH EXACTLY - face, skin color, hair): {identity_snippet}. "
                        else:
                            identity_text = f"IDENTITY ANCHOR FROM DEFAULT PRESET: {identity_snippet}. "
                # Restructure prompt to prioritize base_image_prompt and critical requirements
                if is_initial_default_front:
                    # For initial Front image, base_image_prompt is PRIMARY - it controls pose, composition, and styling
                    prompt = f"""CRITICAL REQUIREMENTS (MUST FOLLOW EXACTLY):
1. FULL BODY VISIBILITY: Show entire figure from head to toe with feet and shoes clearly visible on floor. Do NOT crop ankles, feet, or shoes. Leave generous margin above head and below feet.
2. BACKGROUND: Pure white background only - no beige, no off-white, no textures, no elements.
3. PRIMARY CHARACTER DESCRIPTION (THIS CONTROLS POSE, COMPOSITION, AND STYLING - FOLLOW EXACTLY):
{base_prompt}

VIEW REQUIREMENTS (secondary to character description above):
- Full-body portrait, facing camera straight-on (not profile or 3/4)
- Eyes looking into camera
- Long shot to capture entire height
- Subject centered, no turning away
- Full-length portrait, entire figure in frame
- No cropping, no cut-off body parts, no close-up, no zoom-in

TECHNICAL REQUIREMENTS:
- Professional reference photo, studio photography, clean minimalist composition
- Even studio lighting with subtle dramatic shadows, high quality professional photography
- No background elements, no props except those described in the character description above
- Sharp focus, professional portrait photography style, reference sheet style, full-body shot"""
                else:
                    # For regenerations, use standard structure
                    prompt = f"{build_view_specific('Front', is_initial_default_front)}, {identity_text}{base_prompt}, pure white background, "
                    prompt += "FULL BODY VISIBLE from head to toe, feet and shoes clearly visible on floor, entire figure in frame, "
                    prompt += "full-length portrait, generous margin above head and below feet, no cropping, no cut-off body parts, no close-up, no zoom-in, "
                    prompt += "professional reference photo, studio photography, clean minimalist composition, "
                    prompt += "even studio lighting with subtle dramatic shadows, high quality professional photography, "
                    prompt += "no background elements, no props except those described in the base prompt, "
                    prompt += "sharp focus, professional portrait photography style, reference sheet style, full-body shot"
                
                self.log_prompt_debug('Persona Images: Front reference image (regenerate)', prompt, None)
                selected_profile = self.reference_image_profile_var.get() if hasattr(self, 'reference_image_profile_var') else 'image_gen'
                result = self.azure_image(prompt, size='1024x1536', profile=selected_profile)
                if result.get('success'):
                    img_bytes = result.get('image_bytes', b'')
                    if img_bytes:
                        front_filename = os.path.join(base_path, f'{safe_name}-Front.png')
                        backup_path = backup_file_if_exists(front_filename)
                        if backup_path:
                            self.log_debug('INFO', f'Backed up existing Front image to: {backup_path}')
                        with open(front_filename, 'wb') as f:
                            f.write(img_bytes)
                        self.log_debug('INFO', f'Front reference image regenerated: {front_filename}')
                        self.refresh_persona_images()
                        messagebox.showinfo('Success', 'Front reference image regenerated.')
                    else:
                        messagebox.showerror('Error', 'No image bytes received for Front view.')
                else:
                    messagebox.showerror('Error', f'Failed to regenerate Front image: {result.get("error", "Unknown error")}')
                return
            
            # Side or Back: need front for character description
            if not os.path.exists(current_front_path):
                messagebox.showerror('Error', 'Front image is required to regenerate Side or Back. Please regenerate Front first.')
                return
            
            # Analyze current front for identity/appearance
            character_description = ''
            try:
                analyze_prompt = "Analyze this Front reference image and provide a detailed description of the character's appearance. CRITICAL: You must include: "
                analyze_prompt += "EXACT SKIN COLOR AND TONE (describe precisely - e.g., dark brown, medium tan, light olive, etc.), "
                analyze_prompt += "facial features (face shape, eye color, nose, lips, bone structure), "
                analyze_prompt += "hair (color, texture, style, length), "
                analyze_prompt += "exact clothing details, colors, textures, styling, accessories, pose, lighting style, and all visual characteristics. "
                analyze_prompt += "Output ONLY a detailed character description that can be used to generate matching Side and Back views with the EXACT SAME skin color, facial features, and appearance."
                
                analyze_result = self.azure_vision([current_front_path], analyze_prompt, profile='text')
                if analyze_result.get('success'):
                    character_description = analyze_result.get('content', '').strip()
                    self.log_debug('INFO', 'Front image analyzed successfully for single-view generation')
                else:
                    self.log_debug('WARNING', f'Front analysis failed: {analyze_result.get("error", "Unknown error")}')
            except Exception as exc:
                self.log_debug('WARNING', f'Front analysis error: {exc}')
            
            if not character_description:
                messagebox.showerror('Error', 'Failed to extract character details from Front image. Please regenerate the Front view and try again.')
                return
            
            # CRITICAL: Emphasize matching skin color and facial features
            image_prompt = f"REFERENCE CHARACTER FROM FRONT IMAGE (MUST MATCH EXACTLY): {character_description}. "
            image_prompt += f"CRITICAL REQUIREMENT: The {view.lower()} view MUST have the EXACT SAME skin color, facial features, hair color, and overall appearance as the Front image. "
            image_prompt += f"{build_view_specific(view)}, pure white background, "
            
            image_prompt += "FULL BODY VISIBLE from head to toe, feet and shoes clearly visible on floor, entire figure in frame, "
            image_prompt += "full-length portrait, generous margin above head and below feet, no cropping, no cut-off body parts, no close-up, no zoom-in, "
            image_prompt += "Match the EXACT SAME character appearance, skin color, facial features, clothing, styling, and visual details from the Front reference image, "
            image_prompt += "professional reference photo, studio photography, clean minimalist composition, "
            image_prompt += "even studio lighting with subtle dramatic shadows, high quality professional photography, "
            image_prompt += "no background elements, sharp focus, professional portrait photography style, reference sheet style, full-body shot"
            
            self.log_prompt_debug(f'Persona Images: {view} reference image (regenerate)', image_prompt, None)
            selected_profile = self.reference_image_profile_var.get() if hasattr(self, 'reference_image_profile_var') else 'image_gen'
            result_img = self.azure_image(image_prompt, size='1024x1536', profile=selected_profile)
            if result_img.get('success'):
                img_bytes = result_img.get('image_bytes', b'')
                if img_bytes:
                    filename = os.path.join(base_path, f'{safe_name}-{view}.png')
                    backup_path = backup_file_if_exists(filename)
                    if backup_path:
                        self.log_debug('INFO', f'Backed up existing {view} image to: {backup_path}')
                    with open(filename, 'wb') as f:
                        f.write(img_bytes)
                    self.log_debug('INFO', f'{view} reference image regenerated: {filename}')
                    self.refresh_persona_images()
                    messagebox.showinfo('Success', f'{view} reference image regenerated.')
                else:
                    messagebox.showerror('Error', f'No image bytes received for {view} view.')
            else:
                messagebox.showerror('Error', f'Failed to regenerate {view} image: {result_img.get("error", "Unknown error")}')
        finally:
            self.config(cursor='')
    
    def create_songs_tab(self, parent):
        """Create the AI Songs management tab."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.include_persona_in_cover_var = tk.BooleanVar(value=True)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        top_row1 = ttk.Frame(top_frame)
        top_row1.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(top_row1, text='New Song', command=self.new_song).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_row1, text='Clone Song', command=self.clone_song).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_row1, text='Delete Song', command=self.delete_song).pack(side=tk.LEFT, padx=5)
        top_row2 = ttk.Frame(top_frame)
        top_row2.pack(fill=tk.X)
        ttk.Button(top_row2, text='Create Full Album (AI)', command=self.create_full_album_ai).pack(side=tk.LEFT, padx=5)
        
        songs_list_frame = ttk.LabelFrame(main_frame, text='Songs', padding=5)
        songs_list_frame.pack(fill=tk.X, pady=(0, 10))  # Fixed height, don't expand
        
        self.songs_tree = ttk.Treeview(
            songs_list_frame,
            columns=('album',),
            show='tree headings',
            selectmode='extended'
        )
        self.songs_tree.heading('#0', text='Song / Album')
        self.songs_tree.column('#0', width=260, anchor=tk.W)
        self.songs_tree.heading('album', text='Album')
        self.songs_tree.column('album', width=160, anchor=tk.W)
        
        songs_scrollbar = ttk.Scrollbar(songs_list_frame, orient=tk.VERTICAL, command=self.songs_tree.yview)
        self.songs_tree.configure(yscrollcommand=songs_scrollbar.set)
        
        self.songs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        songs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.songs_tree.bind('<<TreeviewSelect>>', self.on_song_select)
        
        # Configure songs list height (show about 10-11 items)
        self.songs_tree.config(height=11)
        
        # Enable mouse wheel scrolling for songs tree (Windows and Linux)
        def on_mousewheel_songs(event):
            if event.num == 4 or event.delta > 0:
                self.songs_tree.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                self.songs_tree.yview_scroll(1, "units")
        self.songs_tree.bind("<MouseWheel>", on_mousewheel_songs)
        self.songs_tree.bind("<Button-4>", on_mousewheel_songs)
        self.songs_tree.bind("<Button-5>", on_mousewheel_songs)
        
        self.details_notebook = ttk.Notebook(main_frame)
        self.details_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        albums_frame = ttk.Frame(self.details_notebook)
        self.details_notebook.add(albums_frame, text='Albums')
        self.create_album_tab(albums_frame)

        song_details_frame = ttk.Frame(self.details_notebook)
        self.details_notebook.add(song_details_frame, text='Song Details')
        self.create_song_details_form(song_details_frame)
    
    def create_song_details_form(self, parent):
        """Create the song details editing form with Song/Storyboard tabs."""
        # Action buttons above tabs
        header_actions = ttk.Frame(parent)
        header_actions.pack(fill=tk.X, pady=(0, 6))
        header_row1 = ttk.Frame(header_actions)
        header_row1.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(header_row1, text='Save Song', command=self.save_song).pack(side=tk.LEFT, padx=5)
        header_row2 = ttk.Frame(header_actions)
        header_row2.pack(fill=tk.X)
        ttk.Button(header_row2, text='Export YouTube Description', command=self.export_youtube_description).pack(side=tk.LEFT, padx=5)

        details_notebook = ttk.Notebook(parent)
        details_notebook.pack(fill=tk.BOTH, expand=True)

        song_details_tab = ttk.Frame(details_notebook)
        descriptions_tab = ttk.Frame(details_notebook)
        storyboard_tab = ttk.Frame(details_notebook)
        distribution_tab = ttk.Frame(details_notebook)
        details_notebook.add(song_details_tab, text='Song Details')
        details_notebook.add(descriptions_tab, text='Song Description')
        details_notebook.add(storyboard_tab, text='Storyboard')
        details_notebook.add(distribution_tab, text='Distribution')
        self.create_distribution_tab(distribution_tab)

        canvas = tk.Canvas(song_details_tab)
        scrollbar = ttk.Scrollbar(song_details_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling for song details canvas (Windows and Linux)
        def on_mousewheel_song_details(event):
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                canvas.yview_scroll(1, "units")
        canvas.bind("<MouseWheel>", on_mousewheel_song_details)
        canvas.bind("<Button-4>", on_mousewheel_song_details)
        canvas.bind("<Button-5>", on_mousewheel_song_details)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel_song_details)
        scrollable_frame.bind("<Button-4>", on_mousewheel_song_details)
        scrollable_frame.bind("<Button-5>", on_mousewheel_song_details)
        
        self.song_fields = {}
        self.song_widgets = {}
        
        ttk.Label(scrollable_frame, text='Song Name:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.song_name_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.song_name_var).grid(row=0, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5)
        
        ttk.Label(scrollable_frame, text='Full Song Name:', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.full_song_name_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=self.full_song_name_var).grid(row=1, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5)
        ttk.Button(scrollable_frame, text='Generate', command=self.generate_full_song_name).grid(row=1, column=3, padx=5)
        
        ttk.Label(scrollable_frame, text='Persona Image Preset:', font=('TkDefaultFont', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.song_persona_preset_var = tk.StringVar()
        self.song_persona_preset_combo = ttk.Combobox(scrollable_frame, textvariable=self.song_persona_preset_var, state='readonly')
        self.song_persona_preset_combo.grid(row=2, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5)
        ttk.Button(scrollable_frame, text='Refresh Presets', command=self.refresh_song_preset_options).grid(row=2, column=3, padx=5)
        
        # Play button for MP3 file (will be shown/hidden based on file existence)
        self.play_mp3_button = ttk.Button(scrollable_frame, text='▶ Play MP3', command=self.play_mp3, state=tk.DISABLED)
        self.play_mp3_button.grid(row=1, column=4, padx=5)
        
        ttk.Label(scrollable_frame, text='Lyric Ideas:', font=('TkDefaultFont', 9, 'bold')).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.lyric_ideas_text = scrolledtext.ScrolledText(scrollable_frame, height=3, wrap=tk.WORD)
        self.lyric_ideas_text.grid(row=3, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        ttk.Label(scrollable_frame, text='Lyrics:', font=('TkDefaultFont', 9, 'bold')).grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.lyrics_text = scrolledtext.ScrolledText(scrollable_frame, height=6, wrap=tk.WORD)
        self.lyrics_text.grid(row=4, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        lyrics_btn_frame = ttk.Frame(scrollable_frame)
        lyrics_btn_frame.grid(row=4, column=3, padx=5, pady=5, sticky=tk.N)
        ttk.Button(lyrics_btn_frame, text='Generate', command=self.generate_lyrics).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(lyrics_btn_frame, text='Improve Lyrics', command=self.improve_lyrics).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(lyrics_btn_frame, text='Copy Distro Lyrics', command=self.copy_distro_lyrics).pack(fill=tk.X)
        
        ttk.Label(scrollable_frame, text='Song Style:', font=('TkDefaultFont', 9, 'bold')).grid(row=5, column=0, sticky=tk.NW, pady=5)
        self.song_style_text = scrolledtext.ScrolledText(scrollable_frame, height=3, wrap=tk.WORD)
        self.song_style_text.grid(row=5, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)

        style_btn_frame = ttk.Frame(scrollable_frame)
        style_btn_frame.grid(row=5, column=3, padx=5, pady=5, sticky=tk.N)
        ttk.Button(style_btn_frame, text='Select Styles...', command=lambda: self.open_style_selector(False)).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(style_btn_frame, text='Select + Merge', command=lambda: self.open_style_selector(True)).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(style_btn_frame, text='Import Analysis', command=self.import_song_style_from_analysis_dialog).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(style_btn_frame, text='Load Styles from File...', command=self.load_styles_from_file_dialog).pack(fill=tk.X)
        
        ttk.Label(scrollable_frame, text='Merged Style:', font=('TkDefaultFont', 9, 'bold')).grid(row=6, column=0, sticky=tk.NW, pady=5)
        self.merged_style_text = scrolledtext.ScrolledText(scrollable_frame, height=3, wrap=tk.WORD)
        self.merged_style_text.grid(row=6, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        merged_btn_frame = ttk.Frame(scrollable_frame)
        merged_btn_frame.grid(row=6, column=3, padx=5, pady=5, sticky=tk.N)
        ttk.Button(merged_btn_frame, text='Merge', command=self.merge_song_style).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(merged_btn_frame, text='Improve', command=self.improve_merged_style).pack(fill=tk.X)

        ttk.Label(scrollable_frame, text='Exclude Style (Negative):', font=('TkDefaultFont', 9, 'bold')).grid(row=7, column=0, sticky=tk.NW, pady=5)
        self.exclude_style_text = scrolledtext.ScrolledText(scrollable_frame, height=2, wrap=tk.WORD)
        self.exclude_style_text.grid(row=7, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        exclude_btn_frame = ttk.Frame(scrollable_frame)
        exclude_btn_frame.grid(row=7, column=3, padx=5, pady=5, sticky=tk.N)
        ttk.Button(exclude_btn_frame, text='Clear', command=lambda: self.exclude_style_text.delete('1.0', tk.END)).pack(fill=tk.X)

        ttk.Label(scrollable_frame, text='Storyboard Theme / Global Image Style:', font=('TkDefaultFont', 9, 'bold')).grid(row=8, column=0, sticky=tk.NW, pady=5)
        self.storyboard_theme_text = scrolledtext.ScrolledText(scrollable_frame, height=3, wrap=tk.WORD)
        self.storyboard_theme_text.grid(row=8, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        theme_btn_frame = ttk.Frame(scrollable_frame)
        theme_btn_frame.grid(row=8, column=3, padx=5, pady=5, sticky=tk.N)
        ttk.Button(theme_btn_frame, text='Use Merged Style', command=self.set_storyboard_theme_from_merged_style).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(theme_btn_frame, text='Improve', command=self.improve_storyboard_theme).pack(fill=tk.X, pady=(0, 4))
        ttk.Button(theme_btn_frame, text='Translate', command=lambda: self.translate_prompt(self.storyboard_theme_text, 'Storyboard Theme')).pack(fill=tk.X)

        ai_results_notebook = ttk.Notebook(scrollable_frame)
        ai_results_notebook.grid(row=9, column=0, columnspan=4, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        album_cover_frame = ttk.Frame(ai_results_notebook)
        ai_results_notebook.add(album_cover_frame, text='Album Cover')
        
        album_cover_toolbar = ttk.Frame(album_cover_frame)
        album_cover_toolbar.pack(fill=tk.X, padx=2, pady=2)
        cover_row1 = ttk.Frame(album_cover_toolbar)
        cover_row1.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(cover_row1, text='Generate Prompt', command=self.generate_album_cover).pack(side=tk.LEFT, padx=2)
        ttk.Button(cover_row1, text='Improve', command=self.improve_album_cover_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(cover_row1, text='Translate', command=lambda: self.translate_prompt(self.album_cover_text, 'Song Cover Prompt')).pack(side=tk.LEFT, padx=2)
        ttk.Button(cover_row1, text='Run', command=self.run_image_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(cover_row1, text='Preview', command=self.preview_last_song_cover).pack(side=tk.LEFT, padx=2)
        song_explorer_btn = ttk.Button(cover_row1, text='\U0001F4C1 Explorer', command=self.explorer_song_cover)
        song_explorer_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(song_explorer_btn, 'Open song cover folder in file explorer')
        ttk.Button(cover_row1, text='Bulk Generate Covers', command=self.bulk_generate_covers).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(cover_row1, text='Include persona in cover', variable=self.include_persona_in_cover_var).pack(side=tk.LEFT, padx=(10, 2))
        cover_row2 = ttk.Frame(album_cover_toolbar)
        cover_row2.pack(fill=tk.X)
        ttk.Label(cover_row2, text='Size:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(0, 2))
        self.album_cover_size_var = tk.StringVar(value='1:1 (1024x1024)')
        album_cover_size_combo = ttk.Combobox(cover_row2, textvariable=self.album_cover_size_var,
                                              values=['1:1 (1024x1024)', '3:2 (1536x1024)', '16:9 (1792x1024)',
                                                      '4:3 (1365x1024)', '2:3 (1024x1536)', '9:16 (1024x1792)', '21:9 (2048x1024)'],
                                              state='readonly', width=18)
        album_cover_size_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(cover_row2, text='Format:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(10, 2))
        self.album_cover_format_var = tk.StringVar(value='PNG')
        album_cover_format_combo = ttk.Combobox(cover_row2, textvariable=self.album_cover_format_var,
                                               values=['PNG', 'JPEG'], state='readonly', width=8)
        album_cover_format_combo.pack(side=tk.LEFT, padx=2)
        ttk.Label(cover_row2, text='API Profile:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(10, 2))
        image_profiles = self._get_available_image_profiles()
        self.album_cover_profile_var = tk.StringVar(value='image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen'))
        album_cover_profile_combo = ttk.Combobox(cover_row2, textvariable=self.album_cover_profile_var,
                                                 values=image_profiles, state='readonly', width=15)
        album_cover_profile_combo.pack(side=tk.LEFT, padx=2)
        
        self.album_cover_text = scrolledtext.ScrolledText(album_cover_frame, height=6, wrap=tk.WORD)
        self.album_cover_text.pack(fill=tk.BOTH, expand=True)
        
        video_loop_frame = ttk.Frame(ai_results_notebook)
        ai_results_notebook.add(video_loop_frame, text='Video Loop')
        
        video_loop_toolbar = ttk.Frame(video_loop_frame)
        video_loop_toolbar.pack(fill=tk.X, padx=2, pady=2)
        ttk.Button(video_loop_toolbar, text='Generate Prompt', command=self.generate_video_loop).pack(side=tk.LEFT, padx=2)
        ttk.Button(video_loop_toolbar, text='Improve', command=self.improve_video_loop_prompt).pack(side=tk.LEFT, padx=2)
        ttk.Button(video_loop_toolbar, text='Run', command=self.run_video_loop_model).pack(side=tk.LEFT, padx=2)
        ttk.Button(video_loop_toolbar, text='Save', command=self.save_video_loop_prompt).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(video_loop_toolbar, text='Size:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(10, 2))
        self.video_loop_size_var = tk.StringVar(value='9:16 (720x1280)')
        video_loop_size_combo = ttk.Combobox(video_loop_toolbar, textvariable=self.video_loop_size_var, 
                                             values=['9:16 (720x1280)', '16:9 (1280x720)', '1:1 (1024x1024)', 
                                                     '21:9 (1920x1080)', '4:3 (1024x768)', '3:4 (768x1024)'],
                                             state='readonly', width=18)
        video_loop_size_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(video_loop_toolbar, text='Duration:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(10, 2))
        self.video_loop_duration_var = tk.StringVar(value='6')
        video_loop_duration_spin = ttk.Spinbox(video_loop_toolbar, from_=2, to=30, textvariable=self.video_loop_duration_var, width=4)
        video_loop_duration_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(video_loop_toolbar, text='sec', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
        
        self.video_loop_multiscene_var = tk.BooleanVar(value=False)
        multiscene_cb = ttk.Checkbutton(video_loop_toolbar, text='Multi-Scene', variable=self.video_loop_multiscene_var)
        multiscene_cb.pack(side=tk.LEFT, padx=(10, 2))
        create_tooltip(multiscene_cb, 'Generate scene-switching prompt with direct camera cuts')
        
        ttk.Label(video_loop_toolbar, text='Scene dur:', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(6, 2))
        self.video_loop_scene_duration_var = tk.StringVar(value='2')
        video_loop_scene_dur_spin = ttk.Spinbox(video_loop_toolbar, from_=1, to=10, textvariable=self.video_loop_scene_duration_var, width=3)
        video_loop_scene_dur_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(video_loop_toolbar, text='sec', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
        create_tooltip(video_loop_scene_dur_spin, 'Duration of each scene in multi-scene mode (1-10 seconds)')
        
        self.video_loop_text = scrolledtext.ScrolledText(video_loop_frame, height=6, wrap=tk.WORD)
        self.video_loop_text.pack(fill=tk.BOTH, expand=True)
        
        extracted_lyrics_frame = ttk.Frame(ai_results_notebook)
        ai_results_notebook.add(extracted_lyrics_frame, text='Extracted Lyrics')
        self.create_extracted_lyrics_tab(extracted_lyrics_frame)
        
        scrollable_frame.columnconfigure(1, weight=1)
        scrollable_frame.columnconfigure(2, weight=1)
        for r in (3, 4, 5, 6, 7, 8):
            scrollable_frame.rowconfigure(r, weight=1)
        scrollable_frame.rowconfigure(9, weight=1)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        desc_canvas = tk.Canvas(descriptions_tab)
        desc_scrollbar = ttk.Scrollbar(descriptions_tab, orient="vertical", command=desc_canvas.yview)
        desc_frame = ttk.Frame(desc_canvas)

        desc_frame.bind(
            "<Configure>",
            lambda e: desc_canvas.configure(scrollregion=desc_canvas.bbox("all"))
        )

        desc_canvas.create_window((0, 0), window=desc_frame, anchor="nw")
        desc_canvas.configure(yscrollcommand=desc_scrollbar.set)

        def on_mousewheel_descriptions(event):
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                desc_canvas.yview_scroll(-1, "units")
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                desc_canvas.yview_scroll(1, "units")
        desc_canvas.bind("<MouseWheel>", on_mousewheel_descriptions)
        desc_canvas.bind("<Button-4>", on_mousewheel_descriptions)
        desc_canvas.bind("<Button-5>", on_mousewheel_descriptions)
        desc_frame.bind("<MouseWheel>", on_mousewheel_descriptions)
        desc_frame.bind("<Button-4>", on_mousewheel_descriptions)
        desc_frame.bind("<Button-5>", on_mousewheel_descriptions)

        ttk.Label(desc_frame, text='Song Description:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.NW, pady=5)
        self.song_description_text = scrolledtext.ScrolledText(desc_frame, height=8, wrap=tk.WORD, width=60)
        self.song_description_text.grid(row=0, column=1, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        ttk.Button(desc_frame, text='Generate (EN)', command=self.generate_song_description).grid(row=0, column=2, padx=5, pady=5, sticky=tk.N)

        ttk.Label(desc_frame, text='Song Description (German):', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.song_description_de_text = scrolledtext.ScrolledText(desc_frame, height=9, wrap=tk.WORD, width=60)
        self.song_description_de_text.grid(row=1, column=1, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        ttk.Button(desc_frame, text='Generate (DE)', command=self.generate_song_description_de).grid(row=1, column=2, padx=5, pady=5, sticky=tk.N)

        desc_frame.columnconfigure(1, weight=1)
        desc_frame.rowconfigure(0, weight=1)
        desc_frame.rowconfigure(1, weight=1)
        desc_canvas.pack(side="left", fill="both", expand=True)
        desc_scrollbar.pack(side="right", fill="y")

        # Storyboard tab (full details) now lives beside Song Details
        self.create_storyboard_tab(storyboard_tab)

    def create_album_tab(self, parent):
        """Create the Albums manager UI on its own tab."""
        album_frame = ttk.Frame(parent, padding=8)
        album_frame.pack(fill=tk.BOTH, expand=True)

        album_top = ttk.Frame(album_frame)
        album_top.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(album_top, text='Album:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.album_select_var = tk.StringVar()
        self.album_select_combo = ttk.Combobox(album_top, textvariable=self.album_select_var, width=36, state='readonly')
        self.album_select_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 6))
        self.album_select_combo.bind('<<ComboboxSelected>>', self.on_album_select_combo)
        ttk.Button(album_top, text='Clear', command=self.clear_album_form).grid(row=0, column=2, padx=4, sticky=tk.W)
        ttk.Button(album_top, text='Rename Album', command=self.rename_album).grid(row=0, column=3, padx=4, sticky=tk.W)
        ttk.Button(album_top, text='Clone Album', command=self.clone_album).grid(row=0, column=4, padx=4, sticky=tk.W)
        ttk.Button(album_top, text='Delete Album', command=self.delete_album).grid(row=0, column=5, padx=4, sticky=tk.W)
        ttk.Button(album_top, text='Save Album', command=self.save_album).grid(row=0, column=6, padx=4, sticky=tk.W)

        ttk.Label(album_top, text='Name:', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(6, 2))
        self.album_name_var = tk.StringVar()
        ttk.Entry(album_top, textvariable=self.album_name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=(0, 6), pady=(6, 2))

        lang_frame = ttk.Frame(album_top)
        lang_frame.grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=4, pady=(6, 2))
        ttk.Label(lang_frame, text='Suggest language:').pack(side=tk.LEFT, padx=(0, 4))
        self.album_lang_var = tk.StringVar(value='EN')
        ttk.Radiobutton(lang_frame, text='EN', variable=self.album_lang_var, value='EN').pack(side=tk.LEFT)
        ttk.Radiobutton(lang_frame, text='DE', variable=self.album_lang_var, value='DE').pack(side=tk.LEFT, padx=(4, 0))

        sugg_frame = ttk.Frame(album_frame)
        sugg_frame.pack(fill=tk.X, pady=(4, 6))
        ttk.Button(sugg_frame, text='Suggest Album Names (AI)', command=self.suggest_album_names).pack(side=tk.LEFT, padx=(0, 6))
        self.album_suggestions_list = tk.Listbox(sugg_frame, height=4, activestyle='dotbox', selectmode=tk.SINGLE, exportselection=False, width=60)
        self.album_suggestions_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.album_suggestions_list.bind('<Double-Button-1>', self.apply_album_suggestion)

        songs_ops = ttk.Frame(album_frame)
        songs_ops.pack(fill=tk.X, pady=(4, 6))
        ttk.Button(songs_ops, text='New Album from Selected Songs', command=self.new_album_from_selection).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(songs_ops, text='Add Selected Songs', command=self.add_selected_songs_to_album).pack(side=tk.LEFT, padx=4)
        ttk.Button(songs_ops, text='Remove Selected Songs', command=self.remove_selected_album_songs).pack(side=tk.LEFT, padx=4)
        ttk.Button(songs_ops, text='Ungroup Selected Songs', command=self.ungroup_selected_songs).pack(side=tk.LEFT, padx=4)

        album_bottom = ttk.Frame(album_frame)
        album_bottom.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        album_song_frame = ttk.Frame(album_bottom)
        album_song_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        ttk.Label(album_song_frame, text='Album Songs:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        self.album_songs_list = tk.Listbox(album_song_frame, height=5, activestyle='dotbox', selectmode=tk.EXTENDED, exportselection=False)
        self.album_songs_list.pack(fill=tk.BOTH, expand=True, pady=(2, 2))

        album_prompt_frame = ttk.Frame(album_bottom)
        album_prompt_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cover_bar = ttk.Frame(album_prompt_frame)
        cover_bar.pack(fill=tk.X, pady=(0, 2))
        cover_album_row1 = ttk.Frame(cover_bar)
        cover_album_row1.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(cover_album_row1, text='Album Cover:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)
        ttk.Checkbutton(cover_album_row1, text='Include persona in cover', variable=self.include_persona_in_cover_var).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(cover_album_row1, text='Generate Prompt', command=self.generate_album_cover_prompt_album).pack(side=tk.LEFT, padx=4)
        ttk.Button(cover_album_row1, text='Improve', command=self.improve_album_cover_prompt_album).pack(side=tk.LEFT, padx=4)
        ttk.Button(cover_album_row1, text='Translate', command=lambda: self.translate_prompt(self.album_cover_album_text, 'Album Cover Prompt')).pack(side=tk.LEFT, padx=4)
        ttk.Button(cover_album_row1, text='Run Cover Image', command=self.run_album_cover_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(cover_album_row1, text='Preview', command=self.preview_last_album_cover).pack(side=tk.LEFT, padx=4)
        album_explorer_btn = ttk.Button(cover_album_row1, text='\U0001F4C1 Explorer', command=self.explorer_album_cover)
        album_explorer_btn.pack(side=tk.LEFT, padx=4)
        create_tooltip(album_explorer_btn, 'Open album cover folder in file explorer')
        cover_album_row2 = ttk.Frame(cover_bar)
        cover_album_row2.pack(fill=tk.X)
        ttk.Button(cover_album_row2, text='Bulk Generate Covers', command=self.bulk_generate_covers).pack(side=tk.LEFT, padx=4)

        size_bar = ttk.Frame(album_prompt_frame)
        size_bar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(size_bar, text='Size:').pack(side=tk.LEFT, padx=(0, 4))
        self.album_cover_size_album_var = tk.StringVar(value='1:1 (1024x1024)')
        ttk.Combobox(size_bar, textvariable=self.album_cover_size_album_var,
                     values=['1:1 (1024x1024)', '3:2 (1536x1024)', '16:9 (1792x1024)',
                             '4:3 (1365x1024)', '2:3 (1024x1536)', '9:16 (1024x1792)', '21:9 (2048x1024)'],
                     state='readonly', width=18).pack(side=tk.LEFT)
        ttk.Label(size_bar, text='Format:').pack(side=tk.LEFT, padx=(10, 4))
        self.album_cover_format_album_var = tk.StringVar(value='PNG')
        ttk.Combobox(size_bar, textvariable=self.album_cover_format_album_var,
                     values=['PNG', 'JPEG'], state='readonly', width=8).pack(side=tk.LEFT)

        self.album_cover_album_text = scrolledtext.ScrolledText(album_prompt_frame, height=4, wrap=tk.WORD, width=60)
        self.album_cover_album_text.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        video_bar = ttk.Frame(album_prompt_frame)
        video_bar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(video_bar, text='Album Video Prompt:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)
        ttk.Button(video_bar, text='Generate', command=self.generate_album_video_prompt).pack(side=tk.LEFT, padx=4)
        ttk.Button(video_bar, text='Improve', command=self.improve_album_video_prompt).pack(side=tk.LEFT, padx=4)
        ttk.Button(video_bar, text='Translate', command=lambda: self.translate_prompt(self.album_video_text, 'Album Video Prompt')).pack(side=tk.LEFT, padx=4)
        ttk.Button(video_bar, text='Save', command=self.save_album_video_prompt).pack(side=tk.LEFT, padx=4)

        video_size_bar = ttk.Frame(album_prompt_frame)
        video_size_bar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(video_size_bar, text='Size:').pack(side=tk.LEFT, padx=(0, 4))
        self.album_video_size_var = tk.StringVar(value='9:16 (720x1280)')
        ttk.Combobox(video_size_bar, textvariable=self.album_video_size_var,
                     values=['9:16 (720x1280)', '16:9 (1280x720)', '1:1 (1024x1024)',
                             '21:9 (1920x1080)', '4:3 (1024x768)', '3:4 (768x1024)'],
                     state='readonly', width=18).pack(side=tk.LEFT)
        
        ttk.Label(video_size_bar, text='Duration:').pack(side=tk.LEFT, padx=(10, 4))
        self.album_video_duration_var = tk.StringVar(value='6')
        ttk.Spinbox(video_size_bar, from_=2, to=30, textvariable=self.album_video_duration_var, width=4).pack(side=tk.LEFT)
        ttk.Label(video_size_bar, text='sec').pack(side=tk.LEFT, padx=(2, 0))
        
        self.album_video_multiscene_var = tk.BooleanVar(value=False)
        album_multiscene_cb = ttk.Checkbutton(video_size_bar, text='Multi-Scene', variable=self.album_video_multiscene_var)
        album_multiscene_cb.pack(side=tk.LEFT, padx=(10, 0))
        create_tooltip(album_multiscene_cb, 'Generate scene-switching prompt with direct camera cuts')
        
        ttk.Label(video_size_bar, text='Scene dur:').pack(side=tk.LEFT, padx=(6, 2))
        self.album_video_scene_duration_var = tk.StringVar(value='2')
        album_scene_dur_spin = ttk.Spinbox(video_size_bar, from_=1, to=10, textvariable=self.album_video_scene_duration_var, width=3)
        album_scene_dur_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(video_size_bar, text='sec').pack(side=tk.LEFT, padx=(2, 0))
        create_tooltip(album_scene_dur_spin, 'Duration of each scene in multi-scene mode (1-10 seconds)')

        self.album_video_text = scrolledtext.ScrolledText(album_prompt_frame, height=4, wrap=tk.WORD, width=60)
        self.album_video_text.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        action_row = ttk.Frame(album_frame)
        action_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(action_row, text='Save Album', command=self.save_album).pack(side=tk.LEFT, padx=(0, 6))

    def refresh_song_preset_options(self):
        """Sync the song-level preset selector with persona presets."""
        if not hasattr(self, 'song_persona_preset_combo'):
            return
        presets = self._get_persona_image_presets()
        values = [p.get('key', 'default') for p in presets]
        self.song_persona_preset_combo['values'] = values

        desired = None
        if self.current_song and self.current_song.get('persona_image_preset'):
            desired = self.current_song.get('persona_image_preset')
        if not desired and self.current_persona:
            desired = self.current_persona.get('current_image_preset', self._get_default_image_preset_key())
        if not desired:
            desired = 'default'

        if values and desired not in values:
            desired = values[0]
        self.song_persona_preset_var.set(desired)
    
    def create_extracted_lyrics_tab(self, parent):
        """Create the Extracted Lyrics tab for displaying lyrics extracted from MP3."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(controls_frame, text='Extract Lyrics from MP3', command=self.extract_and_display_lyrics).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text='Copy to Lyrics Field', command=self.copy_extracted_to_lyrics).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text='Sync with original Lyrics', command=self.sync_extracted_with_original_lyrics).pack(side=tk.LEFT, padx=5)
        
        # Transcription service selector
        ttk.Label(controls_frame, text='Service:', font=('TkDefaultFont', 9)).pack(side=tk.LEFT, padx=(20, 5))
        self.transcription_service_var = tk.StringVar(value=self.ai_config.get('transcription_service', 'ask'))
        transcription_service_combo = ttk.Combobox(
            controls_frame, 
            textvariable=self.transcription_service_var,
            values=['ask', 'speech', 'transcribe'],
            state='readonly',
            width=12
        )
        transcription_service_combo.pack(side=tk.LEFT, padx=5)
        transcription_service_combo.bind('<<ComboboxSelected>>', self._on_transcription_service_changed)
        
        # Tooltip-style label
        service_info = ttk.Label(controls_frame, text='(ask=prompt, speech=Azure Speech, transcribe=OpenAI)', 
                                font=('TkDefaultFont', 7), foreground='gray')
        service_info.pack(side=tk.LEFT, padx=5)
        
        # Extracted lyrics display
        lyrics_frame = ttk.LabelFrame(main_frame, text='Extracted Lyrics (with timestamps)', padding=5)
        lyrics_frame.pack(fill=tk.BOTH, expand=True)
        
        self.extracted_lyrics_text = scrolledtext.ScrolledText(lyrics_frame, height=20, wrap=tk.WORD, width=80, font=('Courier', 10))
        self.extracted_lyrics_text.pack(fill=tk.BOTH, expand=True)
        
        # Info label
        info_label = ttk.Label(main_frame, text='Lyrics are automatically extracted from MP3 when generating storyboard. Prefers (Vocals) variant when present. Click "Extract Lyrics from MP3" to extract manually.', 
                              font=('TkDefaultFont', 8), foreground='gray')
        info_label.pack(pady=(5, 0))
    
    def _on_transcription_service_changed(self, event=None):
        """Save the transcription service preference when changed."""
        service = self.transcription_service_var.get()
        self.ai_config['transcription_service'] = service
        save_config(self.ai_config)
        self.log_debug('INFO', f'Transcription service preference set to: {service}')
    
    def create_storyboard_tab(self, parent):
        """Create the Storyboard tab for generating music video scene prompts."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top controls - Row 1: main options
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(controls_frame, text='Sec/video:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        self.storyboard_seconds_var = tk.StringVar(value='6')
        ttk.Entry(controls_frame, textvariable=self.storyboard_seconds_var, width=4).pack(side=tk.LEFT, padx=2)

        ttk.Label(controls_frame, text='Image Size:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(8, 2))
        self.storyboard_image_size_var = tk.StringVar(value='3:2 (1536x1024)')
        image_size_combo = ttk.Combobox(controls_frame, textvariable=self.storyboard_image_size_var,
                                        values=['3:2 (1536x1024)', '16:9 (1792x1024)', '1:1 (1024x1024)',
                                                '4:3 (1365x1024)', '2:3 (1024x1536)', '9:16 (1024x1792)', '21:9 (2048x1024)'],
                                        state='readonly', width=14)
        image_size_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(controls_frame, text='API Profile:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(8, 2))
        image_profiles = self._get_available_image_profiles()
        self.storyboard_image_profile_var = tk.StringVar(value='image_gen' if 'image_gen' in image_profiles else (image_profiles[0] if image_profiles else 'image_gen'))
        ttk.Combobox(controls_frame, textvariable=self.storyboard_image_profile_var,
                     values=image_profiles, state='readonly', width=12).pack(side=tk.LEFT, padx=2)

        ttk.Label(controls_frame, text='Persona %:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(8, 2))
        self.persona_scene_percent_var = tk.StringVar(value='40')
        ttk.Spinbox(controls_frame, from_=0, to=100, textvariable=self.persona_scene_percent_var, width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(controls_frame, text='Setups:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(8, 2))
        self.storyboard_setup_count_var = tk.StringVar(value='6')
        ttk.Spinbox(controls_frame, from_=1, to=12, textvariable=self.storyboard_setup_count_var, width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(controls_frame, text='Video Style:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(8, 2))
        VIDEO_STYLE_CHOICES = ['Realism', 'Surrealism', 'Artistic', 'Dreamlike', 'Cinematic']
        self.storyboard_video_style_var = tk.StringVar(value='Realism')
        storyboard_video_style_combo = ttk.Combobox(controls_frame, textvariable=self.storyboard_video_style_var,
            values=VIDEO_STYLE_CHOICES, state='readonly', width=10)
        storyboard_video_style_combo.pack(side=tk.LEFT, padx=2)
        create_tooltip(storyboard_video_style_combo,
            'Controls prompt style for AI video: Realism=filmable/concrete; Surrealism=abstract/morphing; Artistic/Dreamlike/Cinematic=gradations between')

        # Row 2: Multi-Scene options (grouped, compact)
        multiscene_frame = ttk.LabelFrame(main_frame, text='Multi-Scene', padding=4)
        multiscene_frame.pack(fill=tk.X, pady=(0, 10))

        self.storyboard_multiscene_var = tk.BooleanVar(value=False)
        storyboard_multiscene_cb = ttk.Checkbutton(multiscene_frame, text='Multi-Scene', variable=self.storyboard_multiscene_var)
        storyboard_multiscene_cb.pack(side=tk.LEFT, padx=(0, 8))
        create_tooltip(storyboard_multiscene_cb, 'Generate scene prompts with direct camera cuts within each video segment')

        ttk.Label(multiscene_frame, text='Sub-scene/sec:', font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 2))
        self.storyboard_scene_duration_var = tk.StringVar(value='2')
        storyboard_scene_dur_spin = ttk.Spinbox(multiscene_frame, from_=1, to=10, textvariable=self.storyboard_scene_duration_var, width=3)
        storyboard_scene_dur_spin.pack(side=tk.LEFT, padx=2)
        ttk.Label(multiscene_frame, text='sec', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(0, 10))
        create_tooltip(storyboard_scene_dur_spin, 'Fixed mode: duration of each sub-scene. AI-decided mode: minimum sub-scene duration. Max = Seconds per video.')

        self.storyboard_ai_decides_subscene_var = tk.BooleanVar(value=False)
        storyboard_ai_subscene_cb = ttk.Checkbutton(multiscene_frame, text='AI-decided sub-scene cuts', variable=self.storyboard_ai_decides_subscene_var)
        storyboard_ai_subscene_cb.pack(side=tk.LEFT, padx=(0, 4))
        create_tooltip(storyboard_ai_subscene_cb, 'AI places sub-scene cuts based on lyrics (chorus, key phrases). Sub-scenes between Sub-scene/sec and Sec/video. Each scene stays exactly Sec/video.')

        def _toggle_multiscene_options(*args):
            enabled = self.storyboard_multiscene_var.get()
            state = 'normal' if enabled else 'disabled'
            storyboard_scene_dur_spin.configure(state=state)
            storyboard_ai_subscene_cb.configure(state=state)
        self.storyboard_multiscene_var.trace_add('write', lambda *a: _toggle_multiscene_options())
        _toggle_multiscene_options()

        # Button row for Generate Storyboard and Export Generated Prompts
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(button_frame, text='Generate Storyboard', command=self.generate_storyboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text='Generate All Prompts', command=self.generate_all_prompts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text='Export Generated Prompts', command=self.export_generated_prompts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text='Reprocess Latest Response', command=self.reprocess_latest_storyboard_response).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text='Reset Storyboard', command=self.reset_storyboard).pack(side=tk.LEFT, padx=5)
        self.include_lyrics_in_export_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(button_frame, text='Include Lyrics in Export', variable=self.include_lyrics_in_export_var).pack(side=tk.LEFT, padx=5)

        # Lyrics handling options (moved to storyboard)
        options_frame = ttk.LabelFrame(main_frame, text='Lyrics Handling', padding=5)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        self.overlay_lyrics_var = tk.BooleanVar(value=False)
        self.embed_lyrics_var = tk.BooleanVar(value=True)
        self.embed_keywords_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text='Overlay lyrics on image (bottom bar)', variable=self.overlay_lyrics_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text='Embed lyrics into scene prompts', variable=self.embed_lyrics_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text='Embed keywords into scene prompts', variable=self.embed_keywords_var).pack(anchor=tk.W, pady=2)
        
        # Storyboard scenes list
        list_frame = ttk.LabelFrame(main_frame, text='Storyboard Scenes', padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        
        # Create treeview for scenes
        columns = ('scene_num', 'timestamp', 'duration', 'lyrics', 'prompt')
        self.storyboard_tree = ttk.Treeview(tree_container, columns=columns, show='headings', selectmode='extended', height=10)
        self.storyboard_tree.heading('scene_num', text='Scene')
        self.storyboard_tree.heading('timestamp', text='Start')
        self.storyboard_tree.heading('duration', text='Duration')
        self.storyboard_tree.heading('lyrics', text='Lyrics')
        self.storyboard_tree.heading('prompt', text='Prompt')
        self.storyboard_tree.column('scene_num', width=60, anchor=tk.CENTER)
        self.storyboard_tree.column('timestamp', width=80, anchor=tk.CENTER)
        self.storyboard_tree.column('duration', width=80, anchor=tk.CENTER)
        self.storyboard_tree.column('lyrics', width=200, anchor=tk.W)
        self.storyboard_tree.column('prompt', width=400, anchor=tk.W)
        
        storyboard_scrollbar_y = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.storyboard_tree.yview)
        storyboard_scrollbar_x = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.storyboard_tree.xview)
        self.storyboard_tree.configure(yscrollcommand=storyboard_scrollbar_y.set, xscrollcommand=storyboard_scrollbar_x.set)
        
        self.storyboard_tree.grid(row=0, column=0, sticky='nsew')
        storyboard_scrollbar_y.grid(row=0, column=1, sticky='ns')
        storyboard_scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        # Enable mouse wheel scrolling
        def on_mousewheel_storyboard(event):
            if event.num == 4 or event.delta > 0:
                self.storyboard_tree.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                self.storyboard_tree.yview_scroll(1, "units")
        self.storyboard_tree.bind("<MouseWheel>", on_mousewheel_storyboard)
        self.storyboard_tree.bind("<Button-4>", on_mousewheel_storyboard)
        self.storyboard_tree.bind("<Button-5>", on_mousewheel_storyboard)

        # Auto-preview full prompt for selected scene
        self.storyboard_tree.bind('<<TreeviewSelect>>', self.on_storyboard_select)
        preview_frame = ttk.LabelFrame(main_frame, text='Selected Scene Preview', padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 8))
        self.storyboard_preview_text = scrolledtext.ScrolledText(preview_frame, height=6, wrap=tk.WORD, state='disabled')
        self.storyboard_preview_text.pack(fill=tk.BOTH, expand=True)
        
        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)
        
        ttk.Button(action_frame, text='Generate Image (Selected)', command=self.generate_storyboard_image_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text='Generate All Images', command=self.generate_storyboard_images_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text='Copy Prompt (Selected)', command=self.copy_selected_scene_prompt).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text='Regenerate Selected Scenes', command=self.regenerate_selected_scenes).pack(side=tk.LEFT, padx=5)
        
        # Add right-click context menu for copying prompts
        self.storyboard_context_menu = tk.Menu(self, tearoff=0)
        self.storyboard_context_menu.add_command(label='Copy Prompt', command=self.copy_selected_scene_prompt)
        self.storyboard_context_menu.add_command(label='Copy Lyrics', command=self.copy_selected_scene_lyrics)
        self.storyboard_context_menu.add_command(label='Copy Scene Info', command=self.copy_selected_scene_info)
        self.storyboard_context_menu.add_separator()
        self.storyboard_context_menu.add_command(label='Export Prompt to JSON', command=self.export_selected_scene_prompt)
        self.storyboard_context_menu.add_separator()
        self.storyboard_context_menu.add_command(label='Regenerate Selected Scenes', command=self.regenerate_selected_scenes)
        
        def show_storyboard_context_menu(event):
            """Show context menu on right-click."""
            item = self.storyboard_tree.identify_row(event.y)
            if item:
                self.storyboard_tree.selection_set(item)
                self.storyboard_context_menu.post(event.x_root, event.y_root)
        
        self.storyboard_tree.bind('<Button-3>', show_storyboard_context_menu)  # Right-click on Windows/Linux
        self.storyboard_tree.bind('<Button-2>', show_storyboard_context_menu)  # Right-click on Mac
    
    def copy_selected_scene_prompt(self):
        """Copy the prompt from the selected scene(s) to clipboard."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a scene to copy its prompt.')
            return
        
        prompts = []
        for item in selection:
            values = self.storyboard_tree.item(item, 'values')
            if len(values) >= 5:
                scene_num = values[0]
                lyrics = values[3]
                prompt = values[4]  # Prompt is in 5th column
                if prompt:
                    # Use get_scene_final_prompt to check saved generated_prompt first
                    final_prompt = self.get_scene_final_prompt(str(scene_num), prompt, lyrics)
                    safe_prompt = self.sanitize_lyrics_for_prompt(final_prompt)
                    prompts.append(f"Scene {scene_num}:\n{safe_prompt}")
            elif len(values) >= 3:
                # Fallback for old format
                scene_num = values[0]
                prompt = values[2]
                if prompt:
                    prompts.append(f"Scene {scene_num}:\n{prompt}")
        
        if prompts:
            text_to_copy = '\n\n---\n\n'.join(prompts)
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            self.update()
    
    def copy_selected_scene_lyrics(self):
        """Copy the lyrics from the selected scene(s) to clipboard."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a scene to copy its lyrics.')
            return
        
        lyrics_list = []
        for item in selection:
            values = self.storyboard_tree.item(item, 'values')
            if len(values) >= 5:
                scene_num = values[0]
                lyrics = values[3]  # Lyrics in 4th column
                if lyrics:
                    lyrics_list.append(f"Scene {scene_num}: {lyrics}")
        
        if lyrics_list:
            text_to_copy = '\n'.join(lyrics_list)
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            self.update()
    
    def copy_selected_scene_info(self):
        """Copy complete scene info (scene number, duration, lyrics, prompt) from selected scene(s) to clipboard."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a scene to copy its info.')
            return
        
        scenes_info = []
        for item in selection:
            values = self.storyboard_tree.item(item, 'values')
            if len(values) >= 5:
                scene_num = values[0]
                timestamp = values[1]
                duration = values[2]
                lyrics = values[3]
                prompt = values[4]
                scene_text = f"Scene {scene_num} @ {timestamp} ({duration}):\n"
                if lyrics:
                    scene_text += f"Lyrics: {lyrics}\n"
                scene_text += f"Prompt: {prompt}"
                scenes_info.append(scene_text)
            elif len(values) >= 3:
                scene_num = values[0]
                duration = values[1] if len(values) > 1 else ''
                prompt = values[2]
                scene_text = f"Scene {scene_num}"
                if duration:
                    scene_text += f" ({duration})"
                scene_text += f":\nPrompt: {prompt}"
                scenes_info.append(scene_text)
        
        if scenes_info:
            text_to_copy = '\n\n---\n\n'.join(scenes_info)
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)
            self.update()

    def export_selected_scene_prompt(self):
        """Export the full prompt from the selected scene to a JSON file."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'No song selected. Please select a song first.')
            return
        
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select a scene to export its prompt.')
            return
        
        # Get the first selected scene
        item = selection[0]
        values = self.storyboard_tree.item(item, 'values')
        
        if len(values) < 5:
            messagebox.showwarning('Warning', 'Invalid scene data.')
            return
        
        scene_num = values[0]
        lyrics = values[3]
        base_prompt = values[4]
        
        if not base_prompt:
            messagebox.showwarning('Warning', 'No prompt found for the selected scene.')
            return
        
        try:
            seconds_per_video = int(self.storyboard_seconds_var.get() or '6') if hasattr(self, 'storyboard_seconds_var') else 6
            is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
            # Clear cache so we get fresh prompt with word-level timing
            cache_suffix = f"|video" if is_multiscene else ""
            cache_key = f"{scene_num}|{self._get_song_persona_preset_key()}{cache_suffix}"
            if cache_key in self.scene_final_prompts:
                del self.scene_final_prompts[cache_key]
            # Get the FULL prompt for saving (not stripped)
            full_prompt = self.get_full_scene_prompt_for_saving(str(scene_num), base_prompt, lyrics)
            
            if not full_prompt:
                messagebox.showwarning('Warning', 'Could not generate full prompt for the selected scene.')
                return
            
            # Add word-level timing if missing (same logic as export_generated_prompts)
            include_lyrics = self.include_lyrics_in_export_var.get() if hasattr(self, 'include_lyrics_in_export_var') else False
            if lyrics and include_lyrics:
                storyboard = self.current_song.get('storyboard', []) if self.current_song else []
                scene_start_seconds = 0.0
                scene_num_int = int(scene_num) if str(scene_num).isdigit() else 0
                for s in storyboard:
                    if (s.get('scene') == scene_num_int or str(s.get('scene')) == str(scene_num)):
                        scene_start_seconds = self._parse_timestamp_to_seconds(s.get('timestamp', '0:00'))
                        break
                else:
                    scene_start_seconds = max(0.0, (scene_num_int - 1) * seconds_per_video) if scene_num_int else 0.0
                scene_end_seconds = scene_start_seconds + seconds_per_video
                lyrics_with_timestamps = lyrics
                extracted_lyrics = self.current_song.get('extracted_lyrics', '') if self.current_song else ''
                if extracted_lyrics and not re.search(r'\d+:\d+=\d+:\d+=', lyrics):
                    lyrics_with_timestamps = self._extract_timed_lyrics_for_scene(lyrics, extracted_lyrics, scene_start_seconds, scene_end_seconds)
                processed_lyrics = self._process_lyrics_for_lip_sync(lyrics_with_timestamps, scene_start_seconds, seconds_per_video)
                already_has_timing = ('Words and timeindex' in full_prompt or 'Words and time index' in full_prompt or
                                     re.search(r'\n\d+\.\d+s-\d+\.\d+s:', full_prompt))
                scene_has_no_characters = any(m in full_prompt.lower() for m in (
                    '[no characters]', 'no characters', 'no persona present', 'no human figures',
                    'purely environmental', 'purely abstract', '[no persona]', 'environmental shot - no human'
                ))
                if processed_lyrics and not already_has_timing and not scene_has_no_characters:
                    full_prompt += "\n\nIMPORTANT: Synchronize lyrics by time index for lip-sync. Each word has exact start and end time (relative to scene 0-6s):"
                    full_prompt += "\n\n" + processed_lyrics
            
            # Create safe filename
            safe_scene = str(scene_num).replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
            json_filename = os.path.join(self.current_song_path, f'storyboard_scene_{safe_scene}.json')
            
            # Build the export data
            export_data = {
                'scene_num': scene_num,
                'generated_prompt': full_prompt,
                'prompt_type': 'video',  # Full prompt is always 'video' type
                'is_multiscene': is_multiscene,
                'seconds_per_video': seconds_per_video
            }
            
            if lyrics:
                export_data['lyrics'] = lyrics
            
            # Add usage note
            if is_multiscene:
                export_data['usage_note'] = 'VIDEO PROMPT: Full prompt with all sub-scene information for video generation'
            
            # Write JSON file
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.log_debug('INFO', f'Exported prompt for scene {scene_num} to {json_filename}')
            messagebox.showinfo('Success', f'Prompt exported to:\n{json_filename}')
            
        except Exception as e:
            self.log_debug('ERROR', f'Error exporting prompt for scene {scene_num}: {e}')
            messagebox.showerror('Error', f'Failed to export prompt: {e}')

    def _parse_scenes_from_text(self, content: str, default_duration: int, lyric_segments: list, song_duration: float) -> list[dict]:
        """Parse AI storyboard text into scene dicts without touching the UI."""
        scenes = []
        lines = content.split('\n')
        current_scene = None
        current_prompt: list[str] = []
        scene_lyrics = ''
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.upper().startswith('SCENE'):
                if current_scene is not None and current_prompt:
                    prompt_text = '\n'.join(current_prompt).strip()
                    if not scene_lyrics or scene_lyrics.strip().lower() == '[no lyrics]':
                        prompt_text = self.sanitize_prompt_no_lyrics(prompt_text)
                        scene_lyrics = ''
                    if prompt_text:
                        scene_start_time = (current_scene - 1) * default_duration
                        scene_end_time = min(scene_start_time + default_duration, song_duration) if song_duration else scene_start_time + default_duration
                        lyrics_calc = scene_lyrics
                        if lyric_segments and song_duration > 0 and not lyrics_calc:
                            lyrics_calc = self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments)
                        scenes.append({
                            'scene': current_scene,
                            'duration': f'{default_duration}s',
                            'timestamp': self.format_timestamp(scene_start_time),
                            'lyrics': lyrics_calc,
                            'prompt': self.apply_storyboard_theme_prefix(prompt_text)
                        })
                parts = stripped.split(':')
                if parts:
                    num_match = [p for p in parts[0].split() if p.isdigit()]
                    current_scene = int(num_match[0]) if num_match else None
                current_prompt = []
                scene_lyrics = ''
            else:
                current_prompt.append(stripped)
        if current_scene is not None and current_prompt:
            prompt_text = '\n'.join(current_prompt).strip()
            if not scene_lyrics or scene_lyrics.strip().lower() == '[no lyrics]':
                prompt_text = self.sanitize_prompt_no_lyrics(prompt_text)
                scene_lyrics = ''
            if prompt_text:
                scene_start_time = (current_scene - 1) * default_duration
                scene_end_time = min(scene_start_time + default_duration, song_duration) if song_duration else scene_start_time + default_duration
                lyrics_calc = scene_lyrics
                if lyric_segments and song_duration > 0 and not lyrics_calc:
                    lyrics_calc = self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments)
                scenes.append({
                    'scene': current_scene,
                    'duration': f'{default_duration}s',
                    'timestamp': self.format_timestamp(scene_start_time),
                    'lyrics': lyrics_calc,
                    'prompt': self.apply_storyboard_theme_prefix(prompt_text)
                })
        return scenes

    def regenerate_selected_scenes(self):
        """Regenerate the selected storyboard scenes via AI to add variation."""
        if not hasattr(self, 'storyboard_tree'):
            return
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        if not self.current_song_path or not self.current_song:
            messagebox.showwarning('Warning', 'Please select a song first.')
            return
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select at least one scene to regenerate.')
            return
        
        try:
            seconds_per_video = int(self.storyboard_seconds_var.get() or '6')
        except Exception:
            seconds_per_video = 8
        if seconds_per_video < 1:
            seconds_per_video = 6
        
        mp3_path = self.get_mp3_filepath()
        if not mp3_path or not os.path.exists(mp3_path):
            messagebox.showwarning('Warning', 'MP3 file not found. Please ensure the MP3 exists before regenerating scenes.')
            return
        
        lyrics = ''
        if self.current_song:
            lyrics = self.current_song.get('extracted_lyrics', '').strip()
        if not lyrics:
            lyrics = self.get_extracted_lyrics(mp3_path, force_extract=False)
            if hasattr(self, 'extracted_lyrics_text') and lyrics:
                self.extracted_lyrics_text.delete('1.0', tk.END)
                self.extracted_lyrics_text.insert('1.0', lyrics)
        song_duration = self.get_mp3_duration(mp3_path)
        lyric_segments = self.parse_lyrics_with_timing(lyrics, song_duration) if lyrics and song_duration > 0 else []
        
        storyboard_theme = self.storyboard_theme_text.get('1.0', tk.END).strip() if hasattr(self, 'storyboard_theme_text') else ''
        merged_style = self._get_sanitized_style_text()
        persona_scene_percent = int(self.persona_scene_percent_var.get() or 40) if hasattr(self, 'persona_scene_percent_var') else 40
        try:
            storyboard_setup_count = int(self.storyboard_setup_count_var.get() or 6)
        except Exception:
            storyboard_setup_count = 6
        persona_name = self.current_persona.get('name', '') if self.current_persona else ''
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '') if self.current_persona else ''
        base_image_prompt = self.current_persona.get('base_image_prompt', '') if self.current_persona else ''
        vibe = self.current_persona.get('vibe', '') if self.current_persona else ''
        full_song_name = self.full_song_name_var.get().strip() if hasattr(self, 'full_song_name_var') else ''
        song_name = self.song_name_var.get().strip() if hasattr(self, 'song_name_var') else ''
        # Safely extract scene numbers from tree (guard against empty/invalid values)
        scene_nums_from_tree = []
        for i in self.storyboard_tree.get_children():
            try:
                vals = self.storyboard_tree.item(i, 'values')
                if vals and len(vals) >= 1:
                    sn = int(vals[0]) if str(vals[0]).isdigit() else None
                    if sn is not None:
                        scene_nums_from_tree.append(sn)
            except (IndexError, ValueError, TypeError):
                pass
        total_scenes = max(scene_nums_from_tree or [len(self.current_song.get('storyboard', [])) if self.current_song else 0] or [0])
        selected_scene_nums = []
        for i in selection:
            try:
                vals = self.storyboard_tree.item(i, 'values')
                if vals and len(vals) >= 1:
                    sn = int(vals[0]) if str(vals[0]).isdigit() else None
                    if sn is not None:
                        selected_scene_nums.append(sn)
            except (IndexError, ValueError, TypeError):
                pass
        selected_scene_nums = sorted(set(selected_scene_nums))
        if not selected_scene_nums:
            messagebox.showwarning('Warning', 'No valid scenes found in selection.')
            return
        
        video_style = (self.storyboard_video_style_var.get() or 'Realism').strip() if hasattr(self, 'storyboard_video_style_var') else 'Realism'
        style_note = (
            ' NEVER: dissolve, melt, morph, "like [abstract]". USE: fade, step into, static shot, hard cut.' if video_style == 'Realism' else
            ' USE: dissolve, morph, blend. NEVER: vague "something emerges". Write explicit surreal transitions.' if video_style == 'Surrealism' else
            ' PREFER: fade/transition. Use "dissolve" only when intentional. NEVER: empty frame holds, order emerges.' if video_style == 'Artistic' else
            ' USE: soft dissolve, subtle morph. NEVER: jarring abstract (order emerges, empty frame holds).' if video_style == 'Dreamlike' else
            ' USE: filmic terms. NEVER: empty frame holds, order emerges, uncontrolled morphing.' if video_style == 'Cinematic' else
            ""
        )
        system_message = (
            "You are a professional music video storyboard director. "
            "Regenerate ONLY the requested scenes. Output format for each: "
            "\"SCENE X: [duration] seconds\\n[prompt]\". No extra scenes, no questions."
            + style_note
        )
        
        regenerated = {}
        self.log_debug('INFO', f'Regenerating scenes: {selected_scene_nums}')
        self.config(cursor='wait')
        self.update()
        try:
            for scene_num in selected_scene_nums:
                batch_prompt = self._create_batch_storyboard_prompt(
                    song_name, full_song_name, lyrics, merged_style, storyboard_theme, persona_scene_percent,
                    storyboard_setup_count, persona_name, visual_aesthetic, base_image_prompt, vibe,
                    lyric_segments, song_duration, seconds_per_video, scene_num, scene_num, total_scenes
                )
                self.save_storyboard_prompt(
                    batch_prompt,
                    seconds_per_video,
                    {
                        'mode': 'regenerate',
                        'scene': scene_num,
                        'total_scenes': total_scenes,
                        'seconds_per_video': seconds_per_video
                    }
                )
                result = self.azure_ai(batch_prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=1)
                if not result.get('success'):
                    messagebox.showerror('Error', f'Failed to regenerate scene {scene_num}: {result.get("error")}')
                    self.log_debug('ERROR', f'Regenerate scene {scene_num} failed: {result.get("error")}')
                    continue
                parsed = self._parse_scenes_from_text(result.get('content', ''), seconds_per_video, lyric_segments, song_duration)
                if not parsed:
                    messagebox.showwarning('Warning', f'No scene parsed for scene {scene_num}.')
                    continue
                for scene_data in parsed:
                    regenerated[scene_data['scene']] = scene_data
        except Exception as exc:
            messagebox.showerror('Error', f'Error regenerating scenes: {exc}')
            self.log_debug('ERROR', f'Error regenerating scenes: {exc}')
        finally:
            self.config(cursor='')
        
        if not regenerated:
            return
        
        for item in self.storyboard_tree.get_children():
            values = self.storyboard_tree.item(item, 'values')
            if not values or len(values) < 5:
                continue
            scene_num = int(values[0])
            if scene_num in regenerated:
                data = regenerated[scene_num]
                new_values = (
                    scene_num,
                    data.get('timestamp', values[1]),
                    data.get('duration', values[2]),
                    data.get('lyrics', values[3]),
                    data.get('prompt', values[4])
                )
                self.storyboard_tree.item(item, values=new_values)
        
        if self.current_song is not None:
            storyboard_list = self.current_song.get('storyboard', [])
            updated = []
            # Track which scenes were updated
            updated_scene_nums = set()
            
            for scene in storyboard_list:
                scene_num = scene.get('scene')
                if scene_num in regenerated:
                    # Preserve all existing properties, only update the regenerated fields
                    new = scene.copy()
                    new['prompt'] = regenerated[scene_num].get('prompt', new.get('prompt', ''))
                    new['lyrics'] = regenerated[scene_num].get('lyrics', new.get('lyrics', ''))
                    new['duration'] = regenerated[scene_num].get('duration', new.get('duration', ''))
                    new['timestamp'] = regenerated[scene_num].get('timestamp', new.get('timestamp', ''))
                    updated.append(new)
                    updated_scene_nums.add(scene_num)
                else:
                    # Preserve scene as-is
                    updated.append(scene)
            
            # Add any new scenes that weren't in the original list
            for snum, sdata in regenerated.items():
                if snum not in updated_scene_nums:
                    # Create new scene with all standard fields
                    new_scene = {
                        'scene': snum,
                        'timestamp': sdata.get('timestamp', ''),
                        'duration': sdata.get('duration', ''),
                        'lyrics': sdata.get('lyrics', ''),
                        'prompt': sdata.get('prompt', '')
                    }
                    updated.append(new_scene)
            # Sort by scene number to preserve correct order (including newly added scenes)
            def _scene_sort_key(s):
                sn = s.get('scene')
                if sn is None:
                    return 9999
                try:
                    return int(sn)
                except (TypeError, ValueError):
                    return 9999
            updated.sort(key=_scene_sort_key)
            self.current_song['storyboard'] = updated
            
            # Rebuild generated_prompt for each regenerated scene (adds timing, persona, etc.)
            is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
            for scene_num, rdata in regenerated.items():
                base_prompt = rdata.get('prompt', '')
                lyrics = rdata.get('lyrics', '')
                if base_prompt:
                    cache_suffix = f"|video" if is_multiscene else ""
                    cache_key = f"{scene_num}|{self._get_song_persona_preset_key()}{cache_suffix}"
                    if cache_key in self.scene_final_prompts:
                        del self.scene_final_prompts[cache_key]
                    try:
                        final_prompt = self.build_scene_image_prompt(str(scene_num), base_prompt, lyrics, 'video')
                        self._save_storyboard_generated_prompt(str(scene_num), final_prompt, 'video')
                        self.log_debug('INFO', f'Rebuilt generated_prompt for scene {scene_num} (with lyrics timing)')
                    except Exception as e:
                        self.log_debug('WARNING', f'Could not rebuild generated_prompt for scene {scene_num}: {e}')
        
        self.log_debug('INFO', f'Regenerated {len(regenerated)} scene(s) successfully.')

    def create_distribution_tab(self, parent):
        """Create the Distribution tab for song distribution settings."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Spotify Category dropdown
        category_frame = ttk.Frame(main_frame)
        category_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5)
        
        ttk.Label(category_frame, text='Spotify Category:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        spotify_genres = [
            'Afrobeat',
            'Afropop',
            'Alternative',
            'Big Band',
            'Blues',
            "Children's Music",
            'Christian/Gospel',
            'Classical',
            'Comedy',
            'Country',
            'Dance',
            'Electronic',
            'Fitness & Workout',
            'Folk',
            'French Pop',
            'German Folk',
            'German Pop',
            'Hip Hop/Rap',
            'Holiday',
            'J-Pop',
            'Jazz',
            'K-Pop',
            'Latin',
            'Latin Urban',
            'Metal',
            'New Age',
            'Pop',
            'Punk',
            'R&B/Soul',
            'Reggae',
            'Rock',
            'Singer/Songwriter',
            'Soundtrack',
            'Spoken Word',
            'Vocal',
            'World'
        ]
        
        self.spotify_category_var = tk.StringVar()
        spotify_category_combo = ttk.Combobox(category_frame, textvariable=self.spotify_category_var, 
                                             values=spotify_genres, state='readonly', width=30)
        spotify_category_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Button(category_frame, text='AI Decide', command=self.ai_suggest_spotify_category).grid(row=0, column=2, padx=5)
        
        # Secondary Spotify Category dropdown
        secondary_category_frame = ttk.Frame(main_frame)
        secondary_category_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5)
        
        ttk.Label(secondary_category_frame, text='Spotify Category (Secondary):', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.spotify_category_secondary_var = tk.StringVar()
        spotify_category_secondary_combo = ttk.Combobox(secondary_category_frame, textvariable=self.spotify_category_secondary_var, 
                                                        values=spotify_genres, state='readonly', width=30)
        spotify_category_secondary_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Platform links
        links_frame = ttk.Frame(main_frame)
        links_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W+tk.E, pady=8, padx=5)
        
        ttk.Label(links_frame, text='YouTube URL:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.youtube_link_var = tk.StringVar()
        ttk.Entry(links_frame, textvariable=self.youtube_link_var, width=70).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5)
        
        ttk.Label(links_frame, text='Spotify URL:', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=(6, 0))
        self.spotify_link_var = tk.StringVar()
        ttk.Entry(links_frame, textvariable=self.spotify_link_var, width=70).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=(6, 0))
        
        ttk.Label(links_frame, text='Apple Music URL:', font=('TkDefaultFont', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=(0, 6), pady=(6, 0))
        self.apple_link_var = tk.StringVar()
        ttk.Entry(links_frame, textvariable=self.apple_link_var, width=70).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=(6, 0))
        
        category_frame.columnconfigure(1, weight=1)
        secondary_category_frame.columnconfigure(1, weight=1)
        links_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def _format_distribution_links_block(self, include_label: bool = True, lang: str = 'en') -> str:
        """Format streaming links as a small block with optional label."""
        yt = self.youtube_link_var.get().strip() if hasattr(self, 'youtube_link_var') else ''
        sp = self.spotify_link_var.get().strip() if hasattr(self, 'spotify_link_var') else ''
        ap = self.apple_link_var.get().strip() if hasattr(self, 'apple_link_var') else ''
        
        lines = []
        if include_label and (yt or sp or ap):
            lines.append("Links:" if lang != 'de' else "Links:")
        if ap:
            lines.append(f"Apple Music: {ap}")
        if sp:
            lines.append(f"Spotify: {sp}")
        if yt:
            lines.append(f"YouTube: {yt}")
        return '\n'.join(lines).strip()

    def _format_structured_description(self, text: str, lang: str = 'en') -> str:
        """Ensure labeled sections each start on their own line with blank lines between."""
        if not text:
            return ''
        labels = ['Story:', 'Persona:', 'Sound:', 'Spark:'] if lang != 'de' else ['Story:', 'Persona:', 'Sound:', 'Idee:', 'Idee/Prompt:']
        formatted = text.strip()
        for lbl in labels:
            formatted = re.sub(r'\s*' + re.escape(lbl), f'\n\n{lbl}', formatted, flags=re.IGNORECASE)
        formatted = formatted.strip()
        formatted = re.sub(r'\n{3,}', '\n\n', formatted)
        # remove leading blank lines if any
        formatted = formatted.lstrip('\n')
        return formatted

    def _get_tools_footer(self) -> str:
        """Footer line for English descriptions listing tools used."""
        return "TOOLS: gpt-chat-5.2+Python (Selfwritten) | MUSIC: Suno | VIDEO: gpt-image-1.5, grok imagine"

    def ai_suggest_spotify_category(self):
        """Use AI to analyze the song and suggest the appropriate Spotify category."""
        if not self.current_song:
            messagebox.showwarning('Warning', 'Please select a song first.')
            return
        
        song_name = self.song_name_var.get().strip() if hasattr(self, 'song_name_var') else ''
        song_style = self.song_style_text.get('1.0', tk.END).strip() if hasattr(self, 'song_style_text') else ''
        merged_style = self.merged_style_text.get('1.0', tk.END).strip() if hasattr(self, 'merged_style_text') else ''
        lyrics = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        
        # Get persona genre tags if available
        genre_tags = []
        if self.current_persona:
            genre_tags = self.current_persona.get('genre_tags', [])
            if isinstance(genre_tags, list):
                genre_tags_text = ', '.join([t for t in genre_tags if t])
            else:
                genre_tags_text = str(genre_tags or '')
        else:
            genre_tags_text = ''
        
        spotify_genres = [
            'Afrobeat', 'Afropop', 'Alternative', 'Big Band', 'Blues', "Children's Music",
            'Christian/Gospel', 'Classical', 'Comedy', 'Country', 'Dance', 'Electronic',
            'Fitness & Workout', 'Folk', 'French Pop', 'German Folk', 'German Pop',
            'Hip Hop/Rap', 'Holiday', 'J-Pop', 'Jazz', 'K-Pop', 'Latin', 'Latin Urban',
            'Metal', 'New Age', 'Pop', 'Punk', 'R&B/Soul', 'Reggae', 'Rock',
            'Singer/Songwriter', 'Soundtrack', 'Spoken Word', 'Vocal', 'World'
        ]
        
        system_message = (
            "You are a music categorization expert. Analyze the provided song information "
            "and determine the most appropriate Spotify category/genre. "
            "Return ONLY the exact category name from the provided list, nothing else."
        )
        
        prompt = (
            "Analyze this song and determine the most appropriate Spotify category.\n\n"
            f"Song Name: {song_name}\n"
            f"Song Style: {song_style}\n"
            f"Merged Style: {merged_style}\n"
        )
        
        if genre_tags_text:
            prompt += f"Genre Tags: {genre_tags_text}\n"
        
        if lyrics:
            # Include a sample of lyrics (first 500 chars) for context
            lyrics_sample = lyrics[:500] + ('...' if len(lyrics) > 500 else '')
            prompt += f"Lyrics Sample: {lyrics_sample}\n"
        
        prompt += (
            "\nAvailable Spotify Categories:\n"
            + ', '.join(spotify_genres) +
            "\n\nReturn the most appropriate PRIMARY category and optionally a SECONDARY category. "
            "Format your response as: PRIMARY: [category name]\nSECONDARY: [category name] (or leave blank if not needed). "
            "If you only provide one category, it will be used as the primary."
        )
        
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=100, temperature=0.3)
            
            if result.get('success'):
                ai_text = (result.get('content') or '').strip()
                
                # Extract primary and secondary categories from AI response
                suggested_primary = None
                suggested_secondary = None
                
                # Try to parse "PRIMARY: [category]" and "SECONDARY: [category]" format
                lines = ai_text.split('\n')
                for line in lines:
                    line_lower = line.lower().strip()
                    if 'primary:' in line_lower:
                        category_text = line_lower.split('primary:')[1].strip()
                        suggested_primary = self._find_matching_category(category_text, spotify_genres)
                    elif 'secondary:' in line_lower:
                        category_text = line_lower.split('secondary:')[1].strip()
                        if category_text and category_text not in ['', 'none', 'n/a']:
                            suggested_secondary = self._find_matching_category(category_text, spotify_genres)
                
                # If format parsing didn't work, try to find categories in the text
                if not suggested_primary:
                    # Look for the first matching category as primary
                    for genre in spotify_genres:
                        if genre.lower() in ai_text.lower():
                            suggested_primary = genre
                            break
                
                if not suggested_secondary and suggested_primary:
                    # Look for a second matching category as secondary
                    remaining_text = ai_text.lower().replace(suggested_primary.lower(), '', 1)
                    for genre in spotify_genres:
                        if genre.lower() in remaining_text and genre != suggested_primary:
                            suggested_secondary = genre
                            break
                
                # Fallback: if nothing returned, try heuristic guess from style/lyrics
                if not suggested_primary:
                    fallback_text = " ".join([song_style, merged_style, genre_tags_text or '', lyrics_sample if 'lyrics_sample' in locals() else '']).strip()
                    suggested_primary = self._guess_spotify_category(fallback_text, spotify_genres)
                    if suggested_primary:
                        self.log_debug('INFO', f'Heuristic Spotify category fallback used: {suggested_primary}')
                
                if suggested_primary:
                    self.spotify_category_var.set(suggested_primary)
                    self.log_debug('INFO', f'AI suggested primary Spotify category: {suggested_primary}')
                    
                    if suggested_secondary:
                        self.spotify_category_secondary_var.set(suggested_secondary)
                        self.log_debug('INFO', f'AI suggested secondary Spotify category: {suggested_secondary}')
                    else:
                        self.log_debug('INFO', f'AI suggested only primary category: {suggested_primary}')
                else:
                    self.log_debug('WARNING', f'AI response did not match any category. Response: {ai_text}')
                    messagebox.showwarning('AI Decide', 'Keine Kategorie erkannt. Bitte manuell waehlen oder erneut versuchen.')
            else:
                error_msg = result.get('error', 'Unknown error')
                self.log_debug('ERROR', f'AI category suggestion failed: {error_msg}')
        except Exception as exc:
            self.log_debug('ERROR', f'AI category suggestion exception: {exc}')
        finally:
            self.config(cursor='')
    
    def _find_matching_category(self, text: str, spotify_genres: list) -> str | None:
        """Find a matching Spotify category from text."""
        text_lower = text.lower().strip()
        
        # Try exact match first
        for genre in spotify_genres:
            if genre.lower() == text_lower:
                return genre
        
        # Try partial match
        for genre in spotify_genres:
            if genre.lower() in text_lower or text_lower in genre.lower():
                return genre
        
        return None

    def _guess_spotify_category(self, text: str, spotify_genres: list) -> str | None:
        """Heuristic fallback guess for Spotify category."""
        if not text:
            return None
        t = text.lower()
        keyword_map = {
            'r&b': 'R&B/Soul',
            'soul': 'R&B/Soul',
            'hip hop': 'Hip Hop/Rap',
            'rap': 'Hip Hop/Rap',
            'trap': 'Hip Hop/Rap',
            'rock': 'Rock',
            'metal': 'Metal',
            'jazz': 'Jazz',
            'blues': 'Blues',
            'classical': 'Classical',
            'orchestra': 'Classical',
            'pop': 'Pop',
            'dance': 'Dance',
            'electronic': 'Electronic',
            'edm': 'Electronic',
            'house': 'Dance',
            'techno': 'Electronic',
            'country': 'Country',
            'folk': 'Folk',
            'latin': 'Latin',
            'reggae': 'Reggae',
            'singer songwriter': 'Singer/Songwriter',
            'vocal': 'Vocal',
            'soundtrack': 'Soundtrack'
        }
        for key, genre in keyword_map.items():
            if key in t:
                if genre in spotify_genres:
                    return genre
        return None

    def on_storyboard_select(self, event=None):
        """Show full prompt for the first selected storyboard scene."""
        if not hasattr(self, 'storyboard_tree') or not hasattr(self, 'storyboard_preview_text'):
            return
        selection = self.storyboard_tree.selection()
        if not selection:
            self.storyboard_preview_text.config(state='normal')
            self.storyboard_preview_text.delete('1.0', tk.END)
            self.storyboard_preview_text.config(state='disabled')
            return
        item = selection[0]
        values = self.storyboard_tree.item(item, 'values')
        if len(values) < 5:
            return
        scene_num, timestamp, duration, lyrics, prompt = values[0], values[1], values[2], values[3], values[4]
        # Use get_scene_final_prompt to check saved generated_prompt first
        final_prompt = self.get_scene_final_prompt(str(scene_num), prompt, lyrics)
        text = f"Scene {scene_num} @ {timestamp} ({duration})\n"
        if lyrics:
            text += f"Lyrics: {lyrics}\n"
        text += "\n" + self.sanitize_lyrics_for_prompt(final_prompt)
        self.storyboard_preview_text.config(state='normal')
        self.storyboard_preview_text.delete('1.0', tk.END)
        self.storyboard_preview_text.insert('1.0', text)
        self.storyboard_preview_text.config(state='disabled')
    
    def refresh_songs_list(self):
        """Refresh the songs list for the current persona."""
        for item in self.songs_tree.get_children():
            self.songs_tree.delete(item)
        
        self.refresh_song_preset_options()
        if not self.current_persona_path:
            return
        
        songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
        if not os.path.exists(songs_dir):
            return
        
        # Load albums first
        self.load_albums()
        album_buckets: dict[str, list[tuple[str, str]]] = {}
        ungrouped: list[tuple[str, str]] = []
        
        for item in os.listdir(songs_dir):
            item_path = os.path.join(songs_dir, item)
            if os.path.isdir(item_path):
                config = load_song_config(item_path)
                song_name = config.get('song_name', item)
                album_id = config.get('album_id', '')
                if album_id:
                    album_buckets.setdefault(album_id, []).append((item, song_name))
                else:
                    ungrouped.append((item, song_name))
        
        # Sort within buckets
        for key in album_buckets:
            album_buckets[key].sort(key=lambda x: x[1].lower())
        ungrouped.sort(key=lambda x: x[1].lower())

        # Insert albums
        for album_id, album_cfg in sorted(self.albums.items(), key=lambda kv: kv[1].get('album_name', kv[0]).lower()):
            album_name = album_cfg.get('album_name') or album_id
            parent_id = f'album::{album_id}'
            self.songs_tree.insert('', tk.END, iid=parent_id, text=album_name, values=(album_name,), tags=('album',))
            for folder_name, display_name in album_buckets.get(album_id, []):
                self.songs_tree.insert(parent_id, tk.END, iid=folder_name, text=display_name, values=(album_name,), tags=(folder_name,))

        # Ungrouped section
        if ungrouped:
            ungroup_parent = 'album::ungrouped'
            self.songs_tree.insert('', tk.END, iid=ungroup_parent, text='Ungrouped', values=('Ungrouped',), tags=('album',))
            for folder_name, display_name in ungrouped:
                self.songs_tree.insert(ungroup_parent, tk.END, iid=folder_name, text=display_name, values=('Ungrouped',), tags=(folder_name,))
        
        self.refresh_album_selector()
        total_songs = sum(len(v) for v in album_buckets.values()) + len(ungrouped)
        self.log_debug('INFO', f'Refreshed songs list: {total_songs} songs')
    
    def clear_songs_list(self):
        """Clear the songs list."""
        for item in self.songs_tree.get_children():
            self.songs_tree.delete(item)
    
    def on_song_select(self, event):
        """Handle song selection."""
        sel = self.songs_tree.selection()
        if not sel:
            return
        
        folder_name = sel[0]
        if folder_name.startswith('album::'):
            # Album selected - switch to Albums tab and select in combobox
            if hasattr(self, 'details_notebook'):
                try:
                    # Find the Albums tab index
                    for i in range(self.details_notebook.index('end')):
                        if self.details_notebook.tab(i, 'text') == 'Albums':
                            self.details_notebook.select(i)
                            break
                except Exception as e:
                    self.log_debug('WARNING', f'Failed to switch to Albums tab: {e}')
            
            # Get album name from treeview item text and set in combobox
            try:
                album_name = self.songs_tree.item(folder_name, 'text')
                if album_name and hasattr(self, 'album_select_var'):
                    # Check if this album name exists in the combobox values
                    if hasattr(self, 'album_select_combo'):
                        combo_values = self.album_select_combo['values']
                        if album_name in combo_values:
                            self.album_select_var.set(album_name)
                            # Load the album into the form
                            if hasattr(self, 'on_album_select_combo'):
                                self.on_album_select_combo()
                            self.log_debug('INFO', f'Selected album in combobox: {album_name}')
                        else:
                            self.log_debug('WARNING', f'Album "{album_name}" not found in combobox values')
            except Exception as e:
                self.log_debug('WARNING', f'Failed to select album in combobox: {e}')
            return
        
        # Song selected - switch to Song Details tab and load song
        if hasattr(self, 'details_notebook'):
            try:
                # Find the Song Details tab index
                for i in range(self.details_notebook.index('end')):
                    if self.details_notebook.tab(i, 'text') == 'Song Details':
                        self.details_notebook.select(i)
                        break
            except Exception as e:
                self.log_debug('WARNING', f'Failed to switch to Song Details tab: {e}')
        
        self.current_song_path = os.path.join(self.current_persona_path, 'AI-Songs', folder_name)
        self.current_song = load_song_config(self.current_song_path)
        
        self.load_song_info()
        self.auto_import_song_style_from_analysis_if_needed()
        self.log_debug('INFO', f'Selected song: {self.current_song.get("song_name", folder_name)}')
        self.last_song_cover_path = ''
    
    def new_song(self):
        """Create a new song."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        dialog = tk.Toplevel(self)
        dialog.title('New Song')
        dialog.geometry('560x520')
        dialog.minsize(540, 500)
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = dialog.winfo_screenwidth()
            parent_h = dialog.winfo_screenheight()
        dlg_w = dialog.winfo_width()
        dlg_h = dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        header_frame = ttk.Frame(dialog, padding=(8, 0))
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text='Song Name:', font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(10, 2))
        name_var = tk.StringVar()
        name_entry = ttk.Entry(header_frame, textvariable=name_var, width=55)
        name_entry.grid(row=0, column=1, sticky=tk.W, pady=(10, 2), padx=(6, 4))
        name_entry.focus_set()
        
        ttk.Label(header_frame, text='Keyword hints (optional):', font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(6, 2))
        keyword_var = tk.StringVar()
        keyword_entry = ttk.Entry(header_frame, textvariable=keyword_var, width=55)
        keyword_entry.grid(row=1, column=1, sticky=tk.W, pady=(6, 2), padx=(6, 4))
        
        suggestions_list = tk.Listbox(
            dialog,
            height=4,
            activestyle='dotbox',
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black',
            highlightthickness=1,
            borderwidth=1
        )
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=suggestions_list.yview)
        suggestions_list.configure(yscrollcommand=scrollbar.set)
        
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 6))
        ttk.Label(list_frame, text='AI Title Suggestions (select to use):', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 4))
        
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.X, expand=False)
        suggestions_list.pack(in_=list_container, side=tk.LEFT, fill=tk.X, expand=False)
        scrollbar.pack(in_=list_container, side=tk.RIGHT, fill=tk.Y)
        
        ttk.Label(list_frame, text='Pick a title:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(8, 2))
        title_choice_var = tk.StringVar()
        radio_frame = ttk.Frame(list_frame)
        radio_frame.pack(fill=tk.BOTH, expand=False, padx=2, pady=(0, 6))
        
        status_var = tk.StringVar(value='Click "Suggest Titles" to generate options (optional).')
        status_label = ttk.Label(dialog, textvariable=status_var, foreground='gray')
        status_label.pack(pady=(4, 8))
        
        result = [None]
        
        def apply_selection(selection: str):
            if not selection:
                return
            name_var.set(selection)
            name_entry.icursor(tk.END)
            title_choice_var.set(selection)
        
        def on_list_select(event=None):
            sel = suggestions_list.curselection()
            if sel:
                apply_selection(suggestions_list.get(sel[0]))
        
        suggestions_list.bind('<Double-Button-1>', on_list_select)
        suggestions_list.bind('<<ListboxSelect>>', on_list_select)
        
        def fetch_title_suggestions():
            if not self.current_persona:
                messagebox.showwarning('Warning', 'Persona data not loaded. Please reopen or reselect the persona.')
                return
            
            persona = self.current_persona
            persona_name = persona.get('name', '').strip() or 'Unnamed Persona'
            tagline = persona.get('tagline', '').strip()
            vibe = persona.get('vibe', '').strip()
            visual = persona.get('visual_aesthetic', '').strip()
            bio = persona.get('bio', '').strip()
            genres = persona.get('genre_tags', [])
            voice_style = persona.get('voice_style', '').strip()
            lyrics_style = persona.get('lyrics_style', '').strip()
            
            keywords_text = keyword_var.get().strip()
            keywords_clause = f"\n- Keyword hints to weave in: {keywords_text}" if keywords_text else ""
            
            prompt = (
                f"You are helping write song titles for the persona \"{persona_name}\".\n\n"
                f"Persona snapshot:\n"
                f"- Tagline: {tagline or '(empty)'}\n"
                f"- Vibe: {vibe or '(empty)'}\n"
                f"- Visual Aesthetic: {visual or '(empty)'}\n"
                f"- Bio: {bio or '(empty)'}\n"
                f"- Genres: {', '.join(genres) if genres else '(none)'}\n"
                f"- Voice Style: {voice_style or '(empty)'}\n"
                f"- Lyrics Style: {lyrics_style or '(empty)'}{keywords_clause}\n\n"
                "Generate 10 concise, evocative song titles tailored to this persona.\n"
                "Rules:\n"
                "- 2 to 6 words each.\n"
                "- No quotation marks, numbering, or bullet symbols.\n"
                "- Avoid repeating the persona name in every title; only use if natural.\n"
                "- Mix moods and tempos (ballads, upbeat, anthems, introspective).\n"
                "- Keep titles radio-friendly and original.\n\n"
                "Return only the titles, one per line."
            )
            
            status_var.set('Requesting AI suggestions...')
            for widget in (name_entry,):
                widget.state(['disabled'])
            fetch_btn.state(['disabled'])
            dialog.update()
            
            try:
                result_ai = self.azure_ai(prompt, system_message='You generate creative song titles that fit the provided persona.', profile='text', max_tokens=600, temperature=0.85)
            except Exception as exc:
                result_ai = {'success': False, 'error': str(exc), 'content': ''}
            
            for widget in (name_entry,):
                widget.state(['!disabled'])
            fetch_btn.state(['!disabled'])
            
            if not result_ai.get('success'):
                status_var.set('Failed to get suggestions.')
                messagebox.showerror('Error', f"Failed to generate suggestions: {result_ai.get('error', 'Unknown error')}")
                self.log_debug('ERROR', f"AI title suggestions failed: {result_ai.get('error', 'Unknown error')}")
                return
            
            content = result_ai.get('content', '')
            self.log_debug('DEBUG', f'AI title suggestions raw content:\n{content}')
            lines = []
            for line in content.splitlines():
                stripped = re.sub(r'^\s*\d+[\).\-\s]*', '', line).strip().strip('"').strip("'")
                if stripped:
                    lines.append(stripped)
            unique = []
            for title in lines:
                if title not in unique:
                    unique.append(title)
                if len(unique) >= 10:
                    break
            
            suggestions_list.delete(0, tk.END)
            if not unique:
                suggestions_list.insert(tk.END, 'No suggestions returned')
                status_var.set('No suggestions returned. Try again.')
                return
            
            for title in unique:
                suggestions_list.insert(tk.END, title)
            
            # Build radio buttons for quick selection
            for child in radio_frame.winfo_children():
                child.destroy()
            title_choice_var.set('')
            for title in unique:
                ttk.Radiobutton(
                    radio_frame,
                    text=title,
                    variable=title_choice_var,
                    value=title,
                    command=lambda v=title: apply_selection(v)
                ).pack(anchor=tk.W, pady=1, fill=tk.X)
            
            status_var.set(f'Loaded {len(unique)} suggestions. Double-click to use one.')
            self.log_debug('INFO', f'Loaded {len(unique)} AI title suggestions: {unique}')
        
        def ok_clicked():
            name = name_var.get().strip()
            if name:
                result[0] = name
                dialog.destroy()
        
        def cancel_clicked():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 12))
        fetch_btn = ttk.Button(btn_frame, text='Suggest Titles', command=fetch_title_suggestions)
        fetch_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='OK', command=ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        dialog.bind('<Return>', lambda e: ok_clicked())
        dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(dialog)
        
        if result[0]:
            safe_name = result[0].replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
            songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
            new_song_path = enable_long_paths(os.path.join(songs_dir, safe_name))
            
            if os.path.exists(new_song_path):
                messagebox.showerror('Error', f'Song "{safe_name}" already exists!')
                return
            
            os.makedirs(new_song_path, exist_ok=True)
            
            config = {
                'song_name': result[0],
                'full_song_name': '',
                'lyric_ideas': '',
                'lyrics': '',
                'song_style': '',
                'merged_style': '',
                'song_description': '',
                    'song_description_de': '',
                    'youtube_link': '',
                    'spotify_link': '',
                    'apple_music_link': '',
                'album_cover': '',
                'video_loop': '',
                'storyboard': [],
                'storyboard_seconds_per_video': 6,
                'storyboard_setup_count': 6,
                'persona_scene_percent': 40,
                'persona_image_preset': self.current_persona.get('current_image_preset', 'default') if self.current_persona else 'default'
            }
            
            save_song_config(new_song_path, config)
            self.refresh_songs_list()
            self.log_debug('INFO', f'Created new song: {result[0]}')
    
    def delete_song(self):
        """Delete the selected song."""
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'Please select a song to delete.')
            return
        
        song_name = self.current_song.get('song_name', os.path.basename(self.current_song_path))
        response = messagebox.askyesno('Delete Song', f'Are you sure you want to delete "{song_name}"?')
        
        if response:
            try:
                shutil.rmtree(self.current_song_path)
                self.current_song = None
                self.current_song_path = None
                self.refresh_songs_list()
                self.clear_song_info()
                self.log_debug('INFO', f'Deleted song: {song_name}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete song: {e}')
                self.log_debug('ERROR', f'Failed to delete song: {e}')
    
    def clone_song(self):
        """Clone the selected song with a new name, copying only config (song data). Does not copy images or MP3 files."""
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'Please select a song to clone.')
            return
        
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'No persona selected.')
            return
        
        # Prefer full_song_name for default (richer display), fallback to song_name
        original_song_name = (
            self.current_song.get('full_song_name', '').strip()
            or self.current_song.get('song_name', os.path.basename(self.current_song_path))
        )
        
        # Create dialog for new song name
        dialog = tk.Toplevel(self)
        dialog.title('Clone Song')
        dialog.geometry('500x150')
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        
        # Center dialog on parent window
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = dialog.winfo_screenwidth()
            parent_h = dialog.winfo_screenheight()
        dlg_w = dialog.winfo_width()
        dlg_h = dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        ttk.Label(dialog, text='Enter new song name:', font=('TkDefaultFont', 10)).pack(pady=(15, 5))
        
        name_var = tk.StringVar(value=f'{original_song_name} copy')
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=60)
        name_entry.pack(pady=5, padx=20)
        name_entry.select_range(0, tk.END)
        name_entry.focus()
        
        result = [None]
        
        def ok_clicked():
            name = name_var.get().strip()
            if name:
                result[0] = name
                dialog.destroy()
        
        def cancel_clicked():
            dialog.destroy()
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(10, 12))
        ttk.Button(btn_frame, text='OK', command=ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        dialog.bind('<Return>', lambda e: ok_clicked())
        dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(dialog)
        
        if result[0]:
            # Create safe filename
            safe_name = result[0].replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
            songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
            new_song_path = os.path.join(songs_dir, safe_name)
            
            # Check if song already exists
            if os.path.exists(new_song_path):
                messagebox.showerror('Error', f'Song "{safe_name}" already exists!')
                return
            
            try:
                # Create new song directory
                os.makedirs(new_song_path, exist_ok=True)
                
                # Load config from source song
                source_config_file = os.path.join(self.current_song_path, 'config.json')
                if os.path.exists(source_config_file):
                    with open(source_config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # Update song name and full_song_name in config
                    config['song_name'] = result[0]
                    config['full_song_name'] = result[0]
                    
                    # Clear album assignment
                    config['album_id'] = ''
                    config['album_name'] = ''
                    
                    # Save config to new song folder
                    dest_config_file = os.path.join(new_song_path, 'config.json')
                    with open(dest_config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4)
                    
                    self.log_debug('INFO', f'Cloned song "{original_song_name}" to "{result[0]}" (config only, no images/MP3)')
                    messagebox.showinfo('Success', f'Song cloned successfully as "{result[0]}"\n\n(Only song data copied; images and MP3 files were not copied.)')
                else:
                    messagebox.showerror('Error', 'Source song config.json not found!')
                    shutil.rmtree(new_song_path)
                    return
                
                # Refresh song list and select the new song
                self.refresh_songs_list()
                try:
                    self.songs_tree.selection_set(safe_name)
                    self.songs_tree.see(safe_name)
                    self.on_song_select(None)
                except tk.TclError:
                    pass
                
            except Exception as e:
                messagebox.showerror('Error', f'Failed to clone song: {e}')
                self.log_debug('ERROR', f'Failed to clone song: {e}')
                # Clean up if something went wrong
                if os.path.exists(new_song_path):
                    try:
                        shutil.rmtree(new_song_path)
                    except:
                        pass
    
    def create_full_album_ai(self):
        """Ask AI to suggest and create a full album with a story arc."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Persona data not loaded. Please reopen or reselect the persona.')
            return
        
        # Step 1: Ask for theme/topic instructions
        theme_dialog = tk.Toplevel(self)
        theme_dialog.title('Album Theme & Settings')
        theme_dialog.geometry('600x400')
        theme_dialog.transient(self)
        theme_dialog.grab_set()
        theme_dialog.update_idletasks()
        
        # Center dialog
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or theme_dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or theme_dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = theme_dialog.winfo_screenwidth()
            parent_h = theme_dialog.winfo_screenheight()
        dlg_w = theme_dialog.winfo_width()
        dlg_h = theme_dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        theme_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        main_frame = ttk.Frame(theme_dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Number of Songs:', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        num_songs_var = tk.StringVar(value='10')
        num_songs_entry = ttk.Entry(main_frame, textvariable=num_songs_var, width=20)
        num_songs_entry.pack(anchor=tk.W, pady=(0, 15))
        
        ttk.Label(main_frame, text='Album Theme / Topic (optional):', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(main_frame, text='Describe the theme, topic, or story you want the album to explore:', font=('TkDefaultFont', 8), foreground='gray').pack(anchor=tk.W, pady=(0, 5))
        theme_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD, width=70)
        theme_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        theme_text.focus_set()
        
        theme_result = [None, None]
        
        def theme_ok_clicked():
            num_songs_str = num_songs_var.get().strip()
            theme_instructions = theme_text.get('1.0', tk.END).strip()
            
            try:
                num_songs = int(num_songs_str)
                if num_songs < 2:
                    messagebox.showwarning('Warning', 'Album must have at least 2 songs.')
                    return
                if num_songs > 30:
                    messagebox.showwarning('Warning', 'Album cannot have more than 30 songs.')
                    return
            except ValueError:
                messagebox.showerror('Error', 'Please enter a valid number.')
                return
            
            theme_result[0] = num_songs
            theme_result[1] = theme_instructions
            theme_dialog.destroy()
        
        def theme_cancel_clicked():
            theme_dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text='Continue', command=theme_ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=theme_cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        theme_dialog.bind('<Return>', lambda e: theme_ok_clicked())
        theme_dialog.bind('<Escape>', lambda e: theme_cancel_clicked())
        
        self.wait_window(theme_dialog)
        
        if theme_result[0] is None:
            return
        
        num_songs = theme_result[0]
        theme_instructions = theme_result[1]
        
        # Step 2: Generate album concept with AI (can be called multiple times for regeneration)
        regenerate_flag = [False]
        
        while True:
            persona = self.current_persona
            persona_name = persona.get('name', '').strip() or 'Unnamed Persona'
            tagline = persona.get('tagline', '').strip()
            vibe = persona.get('vibe', '').strip()
            visual = persona.get('visual_aesthetic', '').strip()
            bio = persona.get('bio', '').strip()
            genres = persona.get('genre_tags', [])
            voice_style = persona.get('voice_style', '').strip()
            lyrics_style = persona.get('lyrics_style', '').strip()
            merged_style = self._get_sanitized_style_text()
            
            theme_clause = f"\n\nAlbum Theme/Topic Instructions:\n{theme_instructions}" if theme_instructions else ""
            
            prompt = (
                f"You are creating a full concept album for the persona \"{persona_name}\".\n\n"
                f"Persona snapshot:\n"
                f"- Tagline: {tagline or '(empty)'}\n"
                f"- Vibe: {vibe or '(empty)'}\n"
                f"- Visual Aesthetic: {visual or '(empty)'}\n"
                f"- Bio: {bio or '(empty)'}\n"
                f"- Genres: {', '.join(genres) if genres else '(none)'}\n"
                f"- Voice Style: {voice_style or '(empty)'}\n"
                f"- Lyrics Style: {lyrics_style or '(empty)'}\n"
                f"- Merged Style: {merged_style or '(empty)'}{theme_clause}\n\n"
                f"Create a concept album with {num_songs} songs that tells a cohesive story from beginning to end.\n\n"
                f"Requirements:\n"
                f"1. Album Names: Provide EXACTLY 5 different album title options (2-6 words each)\n"
                f"2. Story Arc: Describe the overall narrative/story that connects all songs (2-3 paragraphs)\n"
                f"3. Song Options: For each of the {num_songs} songs, provide EXACTLY 5 different title options\n"
                f"4. Each song should advance the story and build on the previous one\n"
                f"5. Song titles should be 2-6 words each, evocative, and fit the persona\n"
                f"6. The album should have a clear beginning, middle, and end\n"
                f"7. Number each song position clearly (Song 1, Song 2, etc.)\n\n"
                f"Format your response as follows:\n"
                f"ALBUM_NAMES:\n1. [album title option 1]\n2. [album title option 2]\n3. [album title option 3]\n4. [album title option 4]\n5. [album title option 5]\n"
                f"STORY_ARC:\n[story description here]\n"
                f"SONG_1:\n1. [title option 1]\n2. [title option 2]\n3. [title option 3]\n4. [title option 4]\n5. [title option 5]\n"
                f"SONG_2:\n1. [title option 1]\n2. [title option 2]\n3. [title option 3]\n4. [title option 4]\n5. [title option 5]\n"
                f"...\n"
                f"SONG_{num_songs}:\n1. [title option 1]\n2. [title option 2]\n3. [title option 3]\n4. [title option 4]\n5. [title option 5]\n"
            )
            
            self.config(cursor='wait')
            self.update()
            
            try:
                result_ai = self.azure_ai(
                    prompt,
                    system_message='You are a creative music producer who creates concept albums with cohesive narratives.',
                    profile='text',
                    max_tokens=4000,
                    temperature=0.85
                )
            except Exception as exc:
                self.config(cursor='')
                messagebox.showerror('Error', f'Failed to generate album concept: {exc}')
                self.log_debug('ERROR', f'AI album generation failed: {exc}')
                return
            finally:
                self.config(cursor='')
            
            if not result_ai.get('success'):
                messagebox.showerror('Error', f'Failed to generate album concept: {result_ai.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'AI album generation failed: {result_ai.get("error", "Unknown error")}')
                return
            
            content = result_ai.get('content', '').strip()
            if not content:
                messagebox.showwarning('Warning', 'No album concept returned from AI.')
                return
            
            # Parse the response
            album_name_options = []
            story_arc = ''
            song_options = {}  # {song_number: [option1, option2, ...]}
            
            lines = content.splitlines()
            current_section = None
            story_lines = []
            current_song_num = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('ALBUM_NAMES:'):
                    current_section = 'album_names'
                    album_name_options = []
                elif line.startswith('STORY_ARC:'):
                    current_section = 'story'
                    story_lines = []
                elif line.startswith('SONG_'):
                    # Extract song number from "SONG_1:", "SONG_2:", etc.
                    match = re.match(r'SONG_(\d+):', line)
                    if match:
                        current_song_num = int(match.group(1))
                        current_section = 'song_options'
                        song_options[current_song_num] = []
                elif current_section == 'album_names':
                    # Parse album name option (format: "1. Title" or "1) Title" or just "Title")
                    option = re.sub(r'^\s*\d+[\).\-\s]*', '', line).strip().strip('"').strip("'").strip('-').strip()
                    if option:
                        album_name_options.append(option)
                elif current_section == 'story':
                    story_lines.append(line)
                elif current_section == 'song_options' and current_song_num:
                    # Parse song title option (format: "1. Title" or "1) Title" or just "Title")
                    option = re.sub(r'^\s*\d+[\).\-\s]*', '', line).strip().strip('"').strip("'").strip('-').strip()
                    if option:
                        if current_song_num not in song_options:
                            song_options[current_song_num] = []
                        song_options[current_song_num].append(option)
            
            story_arc = '\n'.join(story_lines).strip()
            
            # Validate parsed data
            if not album_name_options:
                # Fallback: try to extract from first few lines
                for line in lines[:10]:
                    if line.strip() and not line.strip().startswith(('STORY_ARC', 'SONG_', 'ALBUM_NAMES')):
                        option = line.strip().strip('"').strip("'")
                        if option:
                            album_name_options.append(option)
                            if len(album_name_options) >= 5:
                                break
            
            if not album_name_options:
                album_name_options = [f"{persona_name}'s Album"]
            
            # Ensure we have options for all songs
            missing_songs = []
            for i in range(1, num_songs + 1):
                if i not in song_options or len(song_options[i]) == 0:
                    missing_songs.append(i)
            
            if missing_songs:
                messagebox.showwarning(
                    'Warning',
                    f'AI did not generate options for songs: {missing_songs}. '
                    f'Proceeding with available options.'
                )
            
            # Fill in missing songs with placeholder options
            for i in range(1, num_songs + 1):
                if i not in song_options or len(song_options[i]) == 0:
                    song_options[i] = [f'Song {i}']
            
            # Ensure each song has at least 5 options (pad with variations if needed)
            for i in range(1, num_songs + 1):
                if i in song_options:
                    while len(song_options[i]) < 5:
                        base = song_options[i][0] if song_options[i] else f'Song {i}'
                        song_options[i].append(f'{base} (Variation {len(song_options[i]) + 1})')
                else:
                    song_options[i] = [f'Song {i} Option {j}' for j in range(1, 6)]
            
            # Ensure we have at least 5 album name options
            while len(album_name_options) < 5:
                album_name_options.append(f"{persona_name}'s Album (Option {len(album_name_options) + 1})")
            
            # Step 3: Show preview dialog with options
            preview_dialog = tk.Toplevel(self)
            preview_dialog.title('Album Preview - Select Options')
            preview_dialog.geometry('1100x700')
            preview_dialog.transient(self)
            preview_dialog.grab_set()
            preview_dialog.update_idletasks()
            
            # Center dialog
            try:
                parent_x = self.winfo_rootx()
                parent_y = self.winfo_rooty()
                parent_w = self.winfo_width() or preview_dialog.winfo_screenwidth()
                parent_h = self.winfo_height() or preview_dialog.winfo_screenheight()
            except Exception:
                parent_x = parent_y = 0
                parent_w = preview_dialog.winfo_screenwidth()
                parent_h = preview_dialog.winfo_screenheight()
            dlg_w = preview_dialog.winfo_width()
            dlg_h = preview_dialog.winfo_height()
            pos_x = parent_x + (parent_w - dlg_w) // 2
            pos_y = parent_y + (parent_h - dlg_h) // 2
            preview_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
            
            # Buttons at the top
            result = [False]
            selected_album_name = [None]
            selected_song_titles = [None]
            
            def confirm_clicked():
                selected_album_name[0] = album_name_var.get().strip()
                if not selected_album_name[0]:
                    messagebox.showwarning('Warning', 'Please select an album name.')
                    return
                
                selected_titles = []
                for i in range(1, num_songs + 1):
                    title = song_vars[i].get().strip()
                    if not title:
                        messagebox.showwarning('Warning', f'Please select a title for Song {i}.')
                        return
                    selected_titles.append(title)
                
                selected_song_titles[0] = selected_titles
                result[0] = True
                preview_dialog.destroy()
            
            def regenerate_clicked():
                regenerate_flag[0] = True
                preview_dialog.destroy()
            
            def cancel_clicked():
                preview_dialog.destroy()
            
            btn_frame = ttk.Frame(preview_dialog)
            btn_frame.pack(fill=tk.X, pady=(10, 10), padx=15)
            ttk.Button(btn_frame, text='Regenerate Options', command=regenerate_clicked).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frame, text='Confirm & Create', command=confirm_clicked).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=4)
            
            # Create scrollable frame
            canvas = tk.Canvas(preview_dialog)
            scrollbar = ttk.Scrollbar(preview_dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Preview content
            main_frame = ttk.Frame(scrollable_frame, padding=15)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Album name selection
            ttk.Label(main_frame, text='Album Name (select one):', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
            album_name_var = tk.StringVar(value=album_name_options[0] if album_name_options else '')
            album_name_combo = ttk.Combobox(main_frame, textvariable=album_name_var, values=album_name_options, width=90, state='readonly')
            album_name_combo.pack(fill=tk.X, pady=(0, 10))
            
            # Story arc display
            ttk.Label(main_frame, text='Story Arc:', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
            story_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD, width=100)
            story_text.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
            story_text.insert('1.0', story_arc if story_arc else 'No story arc provided.')
            story_text.config(state=tk.DISABLED)
            
            # Songs selection
            ttk.Label(main_frame, text=f'Song Titles (select one option for each song):', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
            
            songs_container = ttk.Frame(main_frame)
            songs_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            song_vars = {}
            for i in range(1, num_songs + 1):
                song_frame = ttk.LabelFrame(songs_container, text=f'Song {i}', padding=5)
                song_frame.pack(fill=tk.X, pady=3, padx=5)
                
                options = song_options.get(i, [f'Song {i}'])
                song_var = tk.StringVar(value=options[0] if options else f'Song {i}')
                song_vars[i] = song_var
                
                song_combo = ttk.Combobox(song_frame, textvariable=song_var, values=options, width=85, state='readonly')
                song_combo.pack(fill=tk.X)
            
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            preview_dialog.bind('<Return>', lambda e: confirm_clicked())
            preview_dialog.bind('<Escape>', lambda e: cancel_clicked())
            
            self.wait_window(preview_dialog)
            
            # Check if user wants to regenerate
            if regenerate_flag[0]:
                regenerate_flag[0] = False
                continue  # Loop back to regenerate
            
            if not result[0]:
                return
            
            # Get final selections
            final_album_name = selected_album_name[0]
            final_song_titles = selected_song_titles[0]
            break  # Exit the while loop
        
        # Step 4: Create album and songs
        try:
            self.config(cursor='wait')
            self.update()
            
            # Create album
            album_id = self._album_slug(final_album_name)
            albums_dir = self._albums_dir()
            if not albums_dir:
                messagebox.showerror('Error', 'Persona path not available.')
                return
            
            albums_dir = enable_long_paths(albums_dir)
            os.makedirs(albums_dir, exist_ok=True)
            album_path = enable_long_paths(os.path.join(albums_dir, album_id))
            os.makedirs(album_path, exist_ok=True)
            
            # Create songs
            songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
            created_song_ids = []
            
            for song_title in final_song_titles:
                safe_name = song_title.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
                new_song_path = enable_long_paths(os.path.join(songs_dir, safe_name))
                
                if os.path.exists(new_song_path):
                    self.log_debug('WARNING', f'Song "{safe_name}" already exists, skipping.')
                    continue
                
                os.makedirs(new_song_path, exist_ok=True)
                
                config = {
                    'song_name': song_title,
                    'full_song_name': '',
                    'lyric_ideas': '',
                    'lyrics': '',
                    'song_style': '',
                    'merged_style': merged_style or '',
                    'song_description': '',
                    'song_description_de': '',
                    'youtube_link': '',
                    'spotify_link': '',
                    'apple_music_link': '',
                    'album_cover': '',
                    'video_loop': '',
                    'storyboard': [],
                    'storyboard_seconds_per_video': 6,
                    'storyboard_setup_count': 6,
                    'persona_scene_percent': 40,
                    'persona_image_preset': self.current_persona.get('current_image_preset', 'default') if self.current_persona else 'default',
                    'album_id': album_id,
                    'album_name': final_album_name
                }
                
                save_song_config(new_song_path, config)
                created_song_ids.append(safe_name)
                self.log_debug('INFO', f'Created song: {song_title}')
            
            # Create album config
            album_config = load_album_config(album_path)
            album_config.update({
                'album_id': album_id,
                'album_name': final_album_name,
                'language': 'EN',
                'cover_size': '1:1 (1024x1024)',
                'cover_format': 'PNG',
                'video_size': '9:16 (720x1280)',
                'songs': created_song_ids,
                'cover_prompt': '',
                'video_prompt': ''
            })
            
            if save_album_config(album_path, album_config):
                self.load_albums()
                self.refresh_album_selector()
                self.refresh_songs_list()
                self.album_select_var.set(final_album_name)
                self.on_album_select_combo()
                
                messagebox.showinfo(
                    'Success',
                    f'Album "{final_album_name}" created successfully with {len(created_song_ids)} song(s).\n\n'
                    f'Story Arc:\n{story_arc[:200]}{"..." if len(story_arc) > 200 else ""}'
                )
                self.log_debug('INFO', f'Created full album "{final_album_name}" with {len(created_song_ids)} songs')
            else:
                messagebox.showerror('Error', 'Failed to save album config.')
        
        except Exception as e:
            messagebox.showerror('Error', f'Failed to create album: {e}')
            self.log_debug('ERROR', f'Failed to create album: {e}')
        finally:
            self.config(cursor='')
    
    def load_song_info(self):
        """Load song info into the form."""
        if not self.current_song:
            return
        # Reset cached final prompts for new song
        self.scene_final_prompts = {}
        
        self.song_name_var.set(self.current_song.get('song_name', ''))
        self.full_song_name_var.set(self.current_song.get('full_song_name', ''))
        self.refresh_song_preset_options()
        if hasattr(self, 'song_persona_preset_var'):
            preset_val = self.current_song.get('persona_image_preset') or (self.current_persona.get('current_image_preset') if self.current_persona else 'default')
            self.song_persona_preset_var.set(preset_val or 'default')
        self.lyric_ideas_text.delete('1.0', tk.END)
        self.lyric_ideas_text.insert('1.0', self.current_song.get('lyric_ideas', ''))
        self.lyrics_text.delete('1.0', tk.END)
        self.lyrics_text.insert('1.0', self.current_song.get('lyrics', ''))
        self.song_style_text.delete('1.0', tk.END)
        self.song_style_text.insert('1.0', self.current_song.get('song_style', ''))
        self.merged_style_text.delete('1.0', tk.END)
        self.merged_style_text.insert('1.0', self.current_song.get('merged_style', ''))
        if hasattr(self, 'exclude_style_text'):
            self.exclude_style_text.delete('1.0', tk.END)
            self.exclude_style_text.insert('1.0', self.current_song.get('exclude_style', ''))
        if hasattr(self, 'storyboard_theme_text'):
            self.storyboard_theme_text.delete('1.0', tk.END)
            self.storyboard_theme_text.insert('1.0', self.current_song.get('storyboard_theme', ''))
        if hasattr(self, 'persona_scene_percent_var'):
            self.persona_scene_percent_var.set(str(self.current_song.get('persona_scene_percent', 40)))
        if hasattr(self, 'storyboard_setup_count_var'):
            self.storyboard_setup_count_var.set(str(self.current_song.get('storyboard_setup_count', 6)))
        self.song_description_text.delete('1.0', tk.END)
        self.song_description_text.insert('1.0', self.current_song.get('song_description', ''))
        if hasattr(self, 'song_description_de_text'):
            self.song_description_de_text.delete('1.0', tk.END)
            self.song_description_de_text.insert('1.0', self.current_song.get('song_description_de', ''))
        self.album_cover_text.delete('1.0', tk.END)
        self.album_cover_text.insert('1.0', self.current_song.get('album_cover', ''))
        self.video_loop_text.delete('1.0', tk.END)
        self.video_loop_text.insert('1.0', self.current_song.get('video_loop', ''))
        if hasattr(self, 'overlay_lyrics_var'):
            self.overlay_lyrics_var.set(bool(self.current_song.get('overlay_lyrics_on_image', False)))
        if hasattr(self, 'embed_lyrics_var'):
            self.embed_lyrics_var.set(bool(self.current_song.get('embed_lyrics_in_prompt', True)))
        if hasattr(self, 'embed_keywords_var'):
            self.embed_keywords_var.set(bool(self.current_song.get('embed_keywords_in_prompt', False)))
        if hasattr(self, 'include_lyrics_in_export_var'):
            self.include_lyrics_in_export_var.set(bool(self.current_song.get('include_lyrics_in_export', True)))
        
        # Load album cover and video loop settings
        if hasattr(self, 'album_cover_size_var'):
            self.album_cover_size_var.set(self.current_song.get('album_cover_size', '1:1 (1024x1024)'))
        if hasattr(self, 'album_cover_format_var'):
            self.album_cover_format_var.set(self.current_song.get('album_cover_format', 'PNG'))
        if hasattr(self, 'include_persona_in_cover_var'):
            self.include_persona_in_cover_var.set(bool(self.current_song.get('include_persona_in_cover', True)))
        if hasattr(self, 'video_loop_size_var'):
            self.video_loop_size_var.set(self.current_song.get('video_loop_size', '9:16 (720x1280)'))
        if hasattr(self, 'video_loop_duration_var'):
            self.video_loop_duration_var.set(str(self.current_song.get('video_loop_duration', 6)))
        if hasattr(self, 'video_loop_multiscene_var'):
            self.video_loop_multiscene_var.set(self.current_song.get('video_loop_multiscene', False))
        
        # Load extracted lyrics (from config or lyrics_transcription.json if empty)
        if hasattr(self, 'extracted_lyrics_text'):
            self.extracted_lyrics_text.delete('1.0', tk.END)
            extracted = self.current_song.get('extracted_lyrics', '')
            if not extracted and self.current_song_path:
                extracted = self._load_extracted_lyrics_from_json(self.current_song_path)
            self.extracted_lyrics_text.insert('1.0', extracted)
        
        # Load storyboard
        if hasattr(self, 'storyboard_seconds_var'):
            self.storyboard_seconds_var.set(str(self.current_song.get('storyboard_seconds_per_video', 6)))
            if hasattr(self, 'storyboard_image_size_var'):
                self.storyboard_image_size_var.set(self.current_song.get('storyboard_image_size', '3:2 (1536x1024)'))
            self.load_storyboard()
        if hasattr(self, 'storyboard_multiscene_var'):
            self.storyboard_multiscene_var.set(self.current_song.get('storyboard_multiscene', False))
        if hasattr(self, 'storyboard_scene_duration_var'):
            self.storyboard_scene_duration_var.set(str(self.current_song.get('storyboard_scene_duration', 2)))
        if hasattr(self, 'storyboard_ai_decides_subscene_var'):
            self.storyboard_ai_decides_subscene_var.set(self.current_song.get('storyboard_ai_decides_subscene', False))
        if hasattr(self, 'storyboard_video_style_var'):
            self.storyboard_video_style_var.set(self.current_song.get('storyboard_video_style', 'Realism'))
        
        # Load Spotify Category
        if hasattr(self, 'spotify_category_var'):
            self.spotify_category_var.set(self.current_song.get('spotify_category', ''))
        if hasattr(self, 'spotify_category_secondary_var'):
            self.spotify_category_secondary_var.set(self.current_song.get('spotify_category_secondary', ''))
        if hasattr(self, 'youtube_link_var'):
            self.youtube_link_var.set(self.current_song.get('youtube_link', ''))
        if hasattr(self, 'spotify_link_var'):
            self.spotify_link_var.set(self.current_song.get('spotify_link', ''))
        if hasattr(self, 'apple_link_var'):
            self.apple_link_var.set(self.current_song.get('apple_music_link', ''))
        
        # Check if MP3 file exists and enable/disable play button
        self.update_play_button()
    
    def clear_song_info(self):
        """Clear song info form."""
        self.song_name_var.set('')
        self.full_song_name_var.set('')
        if hasattr(self, 'song_persona_preset_var'):
            default_preset = self.current_persona.get('current_image_preset', self._get_default_image_preset_key()) if self.current_persona else 'default'
            self.song_persona_preset_var.set(default_preset)
            self.refresh_song_preset_options()
        self.lyric_ideas_text.delete('1.0', tk.END)
        self.lyrics_text.delete('1.0', tk.END)
        if hasattr(self, 'extracted_lyrics_text'):
            self.extracted_lyrics_text.delete('1.0', tk.END)
        self.song_style_text.delete('1.0', tk.END)
        self.merged_style_text.delete('1.0', tk.END)
        if hasattr(self, 'exclude_style_text'):
            self.exclude_style_text.delete('1.0', tk.END)
        if hasattr(self, 'storyboard_theme_text'):
            self.storyboard_theme_text.delete('1.0', tk.END)
        if hasattr(self, 'persona_scene_percent_var'):
            self.persona_scene_percent_var.set('40')
        if hasattr(self, 'song_description_text'):
            self.song_description_text.delete('1.0', tk.END)
        if hasattr(self, 'song_description_de_text'):
            self.song_description_de_text.delete('1.0', tk.END)
        self.album_cover_text.delete('1.0', tk.END)
        self.video_loop_text.delete('1.0', tk.END)
        if hasattr(self, 'video_loop_duration_var'):
            self.video_loop_duration_var.set('6')
        if hasattr(self, 'video_loop_multiscene_var'):
            self.video_loop_multiscene_var.set(False)
        if hasattr(self, 'storyboard_multiscene_var'):
            self.storyboard_multiscene_var.set(False)
        if hasattr(self, 'storyboard_scene_duration_var'):
            self.storyboard_scene_duration_var.set('2')
        if hasattr(self, 'storyboard_ai_decides_subscene_var'):
            self.storyboard_ai_decides_subscene_var.set(False)
        if hasattr(self, 'storyboard_video_style_var'):
            self.storyboard_video_style_var.set('Realism')
        if hasattr(self, 'overlay_lyrics_var'):
            self.overlay_lyrics_var.set(False)
        if hasattr(self, 'embed_lyrics_var'):
            self.embed_lyrics_var.set(True)
        if hasattr(self, 'embed_keywords_var'):
            self.embed_keywords_var.set(False)
        if hasattr(self, 'include_lyrics_in_export_var'):
            self.include_lyrics_in_export_var.set(True)
        if hasattr(self, 'spotify_category_var'):
            self.spotify_category_var.set('')
        if hasattr(self, 'spotify_category_secondary_var'):
            self.spotify_category_secondary_var.set('')
        if hasattr(self, 'youtube_link_var'):
            self.youtube_link_var.set('')
        if hasattr(self, 'spotify_link_var'):
            self.spotify_link_var.set('')
        if hasattr(self, 'apple_link_var'):
            self.apple_link_var.set('')
        self.scene_final_prompts = {}
    
    def get_mp3_filepath(self) -> str:
        """Get the MP3 file path for the current song using Full Song Name.
        
        Returns:
            Full path to MP3 file: [song_folder]/[Full Song Name].mp3
            Example: .../AI-Songs/[song_folder]/AI's Shadow - Sister Smoke - (cyberpunk, blues, glitch).mp3
        """
        if not self.current_song_path:
            return ''
        
        full_song_name = self.full_song_name_var.get().strip()
        if not full_song_name:
            # Fallback to song name if full song name is not set
            full_song_name = self.song_name_var.get().strip() or 'song'
        
        mp3_filename = get_mp3_filename(full_song_name)
        return os.path.join(self.current_song_path, mp3_filename)

    def backup_file_if_exists(self, filepath: str) -> str | None:
        """Create a backup of a file if it exists.
        
        Args:
            filepath: Path to the file to backup
            
        Returns:
            Path to the backup file if backup was created, None otherwise
        """
        if not os.path.exists(filepath):
            return None
        
        try:
            import datetime
            # Create backup filename with timestamp
            base, ext = os.path.splitext(filepath)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{base}_backup_{timestamp}{ext}"
            
            # Copy file to backup location
            shutil.copy2(filepath, backup_path)
            self.log_debug('INFO', f'Created backup: {backup_path}')
            return backup_path
        except Exception as e:
            self.log_debug('WARNING', f'Failed to create backup for {filepath}: {e}')
            return None
    
    def get_album_cover_filepath(self) -> str:
        """Get the album cover image file path for the current song if it exists."""
        if not self.current_song_path:
            return ''

        full_song_name = self.full_song_name_var.get().strip()
        if not full_song_name:
            full_song_name = self.song_name_var.get().strip() or 'album_cover'

        safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
        
        # Get current aspect ratio suffix if available
        aspect_ratio_suffix = ''
        if hasattr(self, 'album_cover_size_var'):
            size_value = self.album_cover_size_var.get()
            match = re.search(r'^([^\(]+)', size_value)
            if match:
                aspect_ratio = match.group(1).strip()
                aspect_ratio_x = aspect_ratio.replace(':', 'x')
                if aspect_ratio_x != '1x1':
                    aspect_ratio_suffix = aspect_ratio_x
        
        # Check for current aspect ratio first, then fallback to old format
        candidates = []
        if aspect_ratio_suffix:
            candidates.extend([
                os.path.join(self.current_song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}.png'),
                os.path.join(self.current_song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}.jpg'),
                os.path.join(self.current_song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}.jpeg'),
            ])
        # Also check old format (without aspect ratio) for backward compatibility
        candidates.extend([
            os.path.join(self.current_song_path, f'{safe_basename}-Cover.png'),
            os.path.join(self.current_song_path, f'{safe_basename}-Cover.jpg'),
            os.path.join(self.current_song_path, f'{safe_basename}-Cover.jpeg'),
        ])
        
        for path in candidates:
            if os.path.exists(path):
                return path
        return ''
    
    def update_play_button(self):
        """Update play button state based on MP3 file existence."""
        if hasattr(self, 'play_mp3_button'):
            mp3_path = self.get_mp3_filepath()
            if mp3_path and os.path.exists(mp3_path):
                self.play_mp3_button.config(state=tk.NORMAL)
            else:
                self.play_mp3_button.config(state=tk.DISABLED)
    
    def play_mp3(self):
        """Play the MP3 file for the current song."""
        mp3_path = self.get_mp3_filepath()
        
        if not mp3_path:
            messagebox.showwarning('Warning', 'No song selected.')
            return
        
        if not os.path.exists(mp3_path):
            messagebox.showwarning('Warning', f'MP3 file not found:\n{mp3_path}')
            return
        
        try:
            # Use platform-specific method to play the file
            if sys.platform == 'win32':
                # Windows
                os.startfile(mp3_path)
            elif sys.platform == 'darwin':
                # macOS
                os.system(f'open "{mp3_path}"')
            else:
                # Linux and other Unix-like systems
                os.system(f'xdg-open "{mp3_path}"')
            
            self.log_debug('INFO', f'Playing MP3: {mp3_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to play MP3 file:\n{e}')
            self.log_debug('ERROR', f'Failed to play MP3: {e}')
    
    def extract_and_display_lyrics(self):
        """Extract lyrics from MP3 and display in the Extracted Lyrics tab."""
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'Please select a song first.')
            return
        
        mp3_path = self.get_mp3_filepath()
        if not mp3_path or not os.path.exists(mp3_path):
            messagebox.showwarning('Warning', 'MP3 file not found. Please ensure the MP3 file exists.')
            return
        
        self.log_debug('INFO', 'Extracting lyrics from MP3...')
        self.config(cursor='wait')
        self.update()
        
        try:
            # Force extraction (ignore cached)
            extracted_lyrics = self.get_extracted_lyrics(mp3_path, force_extract=True)
            if extracted_lyrics:
                if hasattr(self, 'extracted_lyrics_text'):
                    self.extracted_lyrics_text.delete('1.0', tk.END)
                    self.extracted_lyrics_text.insert('1.0', extracted_lyrics)
                messagebox.showinfo('Success', f'Extracted {len(extracted_lyrics)} characters of lyrics from MP3.')
                self.log_debug('INFO', f'Extracted lyrics: {len(extracted_lyrics)} characters')
            else:
                messagebox.showinfo('Info', 'No lyrics found in MP3 file metadata.')
                self.log_debug('INFO', 'No lyrics found in MP3 file')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to extract lyrics: {e}')
            self.log_debug('ERROR', f'Failed to extract lyrics: {e}')
        finally:
            self.config(cursor='')
    
    def copy_extracted_to_lyrics(self):
        """Copy extracted lyrics to the main lyrics field."""
        if not hasattr(self, 'extracted_lyrics_text'):
            return
        
        extracted_lyrics = self.extracted_lyrics_text.get('1.0', tk.END).strip()
        if not extracted_lyrics:
            messagebox.showwarning('Warning', 'No extracted lyrics to copy.')
            return
        
        self.lyrics_text.delete('1.0', tk.END)
        self.lyrics_text.insert('1.0', extracted_lyrics)
        self.log_debug('INFO', 'Copied extracted lyrics to lyrics field')
        messagebox.showinfo('Success', 'Copied extracted lyrics to lyrics field.')
    
    def sync_extracted_with_original_lyrics(self):
        """Sync extracted lyrics with original lyrics using AI to fix wrong word detections."""
        if not hasattr(self, 'extracted_lyrics_text'):
            messagebox.showwarning('Warning', 'Extracted lyrics text field not available.')
            return
        
        extracted_lyrics = self.extracted_lyrics_text.get('1.0', tk.END).strip()
        if not extracted_lyrics:
            messagebox.showwarning('Warning', 'No extracted lyrics to sync.')
            return
        
        original_lyrics = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        if not original_lyrics:
            messagebox.showwarning('Warning', 'No original lyrics found in lyrics field. Please add original lyrics first.')
            return
        
        self.log_debug('INFO', 'Syncing extracted lyrics with original lyrics using AI...')
        self.config(cursor='wait')
        self.update()
        
        try:
            # Helper function to extract text only (without timestamps) for comparison
            def extract_text_only(lyrics_with_timestamps):
                # Remove timestamp patterns like [00:12.34], 0:12=, etc.
                text = re.sub(r'\[?\d+:\d+(?:\.\d+)?\]?', '', lyrics_with_timestamps)
                text = re.sub(r'\d+:\d+=', '', text)
                # Remove extra whitespace
                text = ' '.join(text.split())
                return text.lower()
            
            # Helper function to split lyrics into chunks
            def split_lyrics_into_chunks(lyrics_text, chunk_size=60):
                """Split lyrics into chunks of approximately chunk_size lines."""
                # Ensure lyrics_text is a proper string (handle any encoding issues)
                if isinstance(lyrics_text, bytes):
                    try:
                        lyrics_text = lyrics_text.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            lyrics_text = lyrics_text.decode('latin-1')
                        except UnicodeDecodeError:
                            lyrics_text = lyrics_text.decode('utf-8', errors='replace')
                elif not isinstance(lyrics_text, str):
                    lyrics_text = str(lyrics_text)
                
                lines = lyrics_text.split('\n')
                chunks = []
                current_chunk = []
                current_line_count = 0
                
                for line in lines:
                    # Ensure each line is a proper string
                    if isinstance(line, bytes):
                        try:
                            line = line.decode('utf-8')
                        except UnicodeDecodeError:
                            line = line.decode('utf-8', errors='replace')
                    elif not isinstance(line, str):
                        line = str(line)
                    
                    current_chunk.append(line)
                    current_line_count += 1
                    
                    if current_line_count >= chunk_size:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
                        current_line_count = 0
                
                # Add remaining lines as last chunk
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                
                return chunks
            
            # Helper function to process a single chunk
            def process_chunk(chunk_extracted, chunk_index, total_chunks):
                # Ensure all text inputs are proper UTF-8 strings
                if isinstance(chunk_extracted, bytes):
                    try:
                        chunk_extracted = chunk_extracted.decode('utf-8')
                    except UnicodeDecodeError:
                        chunk_extracted = chunk_extracted.decode('utf-8', errors='replace')
                elif not isinstance(chunk_extracted, str):
                    chunk_extracted = str(chunk_extracted)
                
                safe_original_lyrics = original_lyrics
                if isinstance(original_lyrics, bytes):
                    try:
                        safe_original_lyrics = original_lyrics.decode('utf-8')
                    except UnicodeDecodeError:
                        safe_original_lyrics = original_lyrics.decode('utf-8', errors='replace')
                elif not isinstance(original_lyrics, str):
                    safe_original_lyrics = str(original_lyrics)
                
                prompt = f"""Review the extracted lyrics (with timestamps) and compare them with the original lyrics. Fix any wrong word detections while preserving the exact timestamp format.

EXTRACTED LYRICS (with timestamps) - Chunk {chunk_index + 1} of {total_chunks}:
{chunk_extracted}

ORIGINAL LYRICS (reference):
{safe_original_lyrics}

Instructions:
1. Compare the extracted lyrics with the original lyrics
2. Fix any wrong word detections in the extracted lyrics
3. Preserve the exact timestamp format (e.g., [00:12.34] or 0:12=text or similar)
4. Keep the timing information intact - only correct the words
5. Return the corrected extracted lyrics with timestamps in the same format as the input

IMPORTANT: Return your response as JSON in this exact format:
{{
  "success": true,
  "corrected_lyrics": "the corrected lyrics with timestamps here"
}}

If you cannot process this chunk (e.g., too long), set "success": false and include an "error" field with the reason."""
                
                system_message = "You are a lyrics correction assistant. Your task is to fix wrong word detections in extracted lyrics while preserving timestamp formatting exactly. Always return JSON format."
                
                result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=8000, temperature=0.3)
                
                response_text = (result.get('content') or '').strip()
                if not response_text:
                    return {'success': False, 'error': 'AI did not return a response'}
                
                # Try to parse JSON response
                try:
                    # Try to extract JSON from response (might be wrapped in markdown code blocks)
                    # Look for JSON object starting with { and containing "success"
                    json_start = response_text.find('{')
                    if json_start != -1:
                        # Find matching closing brace
                        brace_count = 0
                        json_end = json_start
                        for i in range(json_start, len(response_text)):
                            if response_text[i] == '{':
                                brace_count += 1
                            elif response_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if json_end > json_start:
                            json_str = response_text[json_start:json_end]
                            response_json = json.loads(json_str)
                        else:
                            # Try parsing the whole response as JSON
                            response_json = json.loads(response_text)
                    else:
                        # Try parsing the whole response as JSON
                        response_json = json.loads(response_text)
                    
                    if not response_json.get('success', False):
                        error_msg = response_json.get('error', 'Unknown error from AI')
                        return {'success': False, 'error': error_msg}
                    
                    corrected = response_json.get('corrected_lyrics', '').strip()
                    if not corrected:
                        return {'success': False, 'error': 'AI returned success but no corrected lyrics'}
                    
                    return {'success': True, 'corrected_lyrics': corrected}
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, check if it's an error message
                    if 'exceed' in response_text.lower() or 'too long' in response_text.lower() or 'split' in response_text.lower():
                        return {'success': False, 'error': 'Response too long - needs chunking'}
                    # Try to use the response as-is if it looks like lyrics
                    if any(char in response_text for char in ['=', '[', ':', '\n']):
                        return {'success': True, 'corrected_lyrics': response_text}
                    return {'success': False, 'error': 'Could not parse AI response as JSON or lyrics'}
            
            # Check if lyrics need to be chunked (estimate: if more than ~50 lines)
            extracted_lines = extracted_lyrics.split('\n')
            needs_chunking = len(extracted_lines) > 50
            
            if needs_chunking:
                # Split into chunks and process each
                chunks = split_lyrics_into_chunks(extracted_lyrics, chunk_size=50)
                self.log_debug('INFO', f'Splitting lyrics into {len(chunks)} chunks for processing')
                
                corrected_chunks = []
                total_words_changed = 0
                
                for i, chunk in enumerate(chunks):
                    self.log_debug('INFO', f'Processing chunk {i + 1} of {len(chunks)}')
                    try:
                        chunk_result = process_chunk(chunk, i, len(chunks))
                    except Exception as e:
                        # Handle encoding errors gracefully
                        error_msg = str(e)
                        if isinstance(e, (UnicodeDecodeError, UnicodeEncodeError)):
                            error_msg = f'Encoding error: {type(e).__name__}'
                        self.log_debug('ERROR', f'Chunk {i + 1} processing exception: {error_msg}')
                        messagebox.showerror('Error', f'Failed to process chunk {i + 1} of {len(chunks)}:\n{error_msg}')
                        return
                    
                    if not chunk_result.get('success', False):
                        error_msg = chunk_result.get('error', 'Unknown error')
                        # Ensure error message is safe for display
                        if isinstance(error_msg, bytes):
                            try:
                                error_msg = error_msg.decode('utf-8', errors='replace')
                            except Exception:
                                error_msg = 'Unknown error (encoding issue)'
                        messagebox.showerror('Error', f'Failed to process chunk {i + 1} of {len(chunks)}:\n{error_msg}')
                        self.log_debug('ERROR', f'Chunk {i + 1} failed: {error_msg}')
                        return
                    
                    corrected_chunks.append(chunk_result['corrected_lyrics'])
                
                # Combine all corrected chunks
                corrected_lyrics = '\n'.join(corrected_chunks)
            else:
                # Process as single chunk
                result = process_chunk(extracted_lyrics, 0, 1)
                
                if not result.get('success', False):
                    error_msg = result.get('error', 'Unknown error')
                    messagebox.showerror('Error', f'Failed to sync lyrics:\n{error_msg}')
                    self.log_debug('ERROR', f'Sync failed: {error_msg}')
                    return
                
                corrected_lyrics = result['corrected_lyrics']
            
            if not corrected_lyrics:
                messagebox.showerror('Error', 'AI did not return corrected lyrics.')
                self.log_debug('ERROR', 'AI did not return corrected lyrics')
                return
            
            # Count word differences between original and corrected extracted lyrics
            original_text = extract_text_only(extracted_lyrics)
            corrected_text = extract_text_only(corrected_lyrics)
            
            # Count word differences
            original_words = set(original_text.split())
            corrected_words = set(corrected_text.split())
            words_added = len(corrected_words - original_words)
            words_removed = len(original_words - corrected_words)
            words_changed = words_added + words_removed
            
            # Show confirmation dialog with statistics
            stats_msg = f"AI review completed.\n\n"
            stats_msg += f"Words added: {words_added}\n"
            stats_msg += f"Words removed: {words_removed}\n"
            stats_msg += f"Total changes: {words_changed}\n\n"
            stats_msg += f"Merge the corrected extracted lyrics?"
            
            response = messagebox.askyesno('Sync Lyrics', stats_msg)
            
            if response:
                # Update extracted lyrics with corrected version
                self.extracted_lyrics_text.delete('1.0', tk.END)
                self.extracted_lyrics_text.insert('1.0', corrected_lyrics)
                if self.current_song:
                    self.current_song['extracted_lyrics'] = corrected_lyrics
                    save_song_config(self.current_song_path, self.current_song)
                self.log_debug('INFO', f'Merged corrected extracted lyrics ({words_changed} words changed)')
                msg = f'Successfully merged corrected extracted lyrics.\n{words_changed} words were fixed.'
                if self.current_song and self.current_song.get('storyboard'):
                    msg += '\n\nConsider regenerating the storyboard for accurate scene-lyric alignment.'
                messagebox.showinfo('Success', msg)
            else:
                self.log_debug('INFO', 'User cancelled merging corrected extracted lyrics')
                
        except Exception as e:
            messagebox.showerror('Error', f'Failed to sync lyrics: {e}')
            self.log_debug('ERROR', f'Failed to sync lyrics: {e}')
        finally:
            self.config(cursor='')
    
    def save_song(self):
        """Save song info to config.json."""
        if not self.current_song_path:
            self.log_debug('WARNING', 'Please select a song to save.')
            return
        
        config = {
            'song_name': self.song_name_var.get().strip(),
            'full_song_name': self.full_song_name_var.get().strip(),
            'album_id': self.current_song.get('album_id', '') if self.current_song else '',
            'album_name': self.current_song.get('album_name', '') if self.current_song else '',
            'lyric_ideas': self.lyric_ideas_text.get('1.0', tk.END).strip(),
            'lyrics': self.lyrics_text.get('1.0', tk.END).strip(),
            'extracted_lyrics': self.extracted_lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'extracted_lyrics_text') else self.current_song.get('extracted_lyrics', '') if self.current_song else '',
            'song_style': self.song_style_text.get('1.0', tk.END).strip(),
            'merged_style': self.merged_style_text.get('1.0', tk.END).strip(),
            'exclude_style': self.exclude_style_text.get('1.0', tk.END).strip() if hasattr(self, 'exclude_style_text') else '',
            'storyboard_theme': self.storyboard_theme_text.get('1.0', tk.END).strip() if hasattr(self, 'storyboard_theme_text') else '',
            'persona_scene_percent': int(self.persona_scene_percent_var.get() or 40) if hasattr(self, 'persona_scene_percent_var') else 40,
            'song_description': self.song_description_text.get('1.0', tk.END).strip() if hasattr(self, 'song_description_text') else self.current_song.get('song_description', '') if self.current_song else '',
            'song_description_de': self.song_description_de_text.get('1.0', tk.END).strip() if hasattr(self, 'song_description_de_text') else self.current_song.get('song_description_de', '') if self.current_song else '',
            'album_cover': self.album_cover_text.get('1.0', tk.END).strip(),
            'video_loop': self.video_loop_text.get('1.0', tk.END).strip(),
            'youtube_link': self.youtube_link_var.get().strip() if hasattr(self, 'youtube_link_var') else '',
            'spotify_link': self.spotify_link_var.get().strip() if hasattr(self, 'spotify_link_var') else '',
            'apple_music_link': self.apple_link_var.get().strip() if hasattr(self, 'apple_link_var') else '',
            'storyboard': self.get_storyboard_data() if hasattr(self, 'storyboard_tree') else [],
            'storyboard_metadata': self.current_song.get('storyboard_metadata', {}) if self.current_song else {},
            'storyboard_seconds_per_video': int(self.storyboard_seconds_var.get() or '6') if hasattr(self, 'storyboard_seconds_var') else 6,
            'storyboard_image_size': self.storyboard_image_size_var.get() if hasattr(self, 'storyboard_image_size_var') else '3:2 (1536x1024)',
            'album_cover_size': self.album_cover_size_var.get() if hasattr(self, 'album_cover_size_var') else '1:1 (1024x1024)',
            'album_cover_format': self.album_cover_format_var.get() if hasattr(self, 'album_cover_format_var') else 'PNG',
            'include_persona_in_cover': bool(self.include_persona_in_cover_var.get()) if hasattr(self, 'include_persona_in_cover_var') else True,
            'video_loop_size': self.video_loop_size_var.get() if hasattr(self, 'video_loop_size_var') else '9:16 (720x1280)',
            'video_loop_duration': int(self.video_loop_duration_var.get() or 6) if hasattr(self, 'video_loop_duration_var') else 6,
            'video_loop_multiscene': bool(self.video_loop_multiscene_var.get()) if hasattr(self, 'video_loop_multiscene_var') else False,
            'storyboard_multiscene': bool(self.storyboard_multiscene_var.get()) if hasattr(self, 'storyboard_multiscene_var') else False,
            'storyboard_scene_duration': int(self.storyboard_scene_duration_var.get() or 2) if hasattr(self, 'storyboard_scene_duration_var') else 2,
            'storyboard_ai_decides_subscene': bool(self.storyboard_ai_decides_subscene_var.get()) if hasattr(self, 'storyboard_ai_decides_subscene_var') else False,
            'storyboard_video_style': (self.storyboard_video_style_var.get() or 'Realism').strip() if hasattr(self, 'storyboard_video_style_var') else 'Realism',
            'overlay_lyrics_on_image': bool(self.overlay_lyrics_var.get()) if hasattr(self, 'overlay_lyrics_var') else False,
            'embed_lyrics_in_prompt': bool(self.embed_lyrics_var.get()) if hasattr(self, 'embed_lyrics_var') else True,
            'embed_keywords_in_prompt': bool(self.embed_keywords_var.get()) if hasattr(self, 'embed_keywords_var') else False,
            'include_lyrics_in_export': bool(self.include_lyrics_in_export_var.get()) if hasattr(self, 'include_lyrics_in_export_var') else False,
            'storyboard_setup_count': int(self.storyboard_setup_count_var.get() or 6) if hasattr(self, 'storyboard_setup_count_var') else 6,
            'persona_image_preset': self.song_persona_preset_var.get().strip() if hasattr(self, 'song_persona_preset_var') and self.song_persona_preset_var.get() else self.current_persona.get('current_image_preset', 'default') if self.current_persona else 'default',
            'spotify_category': self.spotify_category_var.get().strip() if hasattr(self, 'spotify_category_var') else '',
            'spotify_category_secondary': self.spotify_category_secondary_var.get().strip() if hasattr(self, 'spotify_category_secondary_var') else ''
        }
        
        if save_song_config(self.current_song_path, config):
            # Reload config to get the latest data (including any generated_prompt fields that were preserved)
            try:
                config_file = os.path.join(self.current_song_path, 'config.json')
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        self.current_song = json.load(f)
                else:
                    self.current_song = config
            except Exception as e:
                self.log_debug('WARNING', f'Failed to reload config after save: {e}')
                self.current_song = config
            self.log_debug('INFO', 'Song saved successfully')
            # Update play button state after saving
            self.update_play_button()
        else:
            self.log_debug('ERROR', 'Failed to save song')

    def clear_album_form(self):
        """Reset album form fields."""
        self.current_album = None
        self.current_album_id = None
        self.album_select_var.set('')
        self.album_name_var.set('')
        self.album_lang_var.set('EN')
        self.album_cover_album_text.delete('1.0', tk.END)
        self.album_video_text.delete('1.0', tk.END)
        if hasattr(self, 'album_video_duration_var'):
            self.album_video_duration_var.set('6')
        if hasattr(self, 'album_video_multiscene_var'):
            self.album_video_multiscene_var.set(False)
        if hasattr(self, 'album_video_scene_duration_var'):
            self.album_video_scene_duration_var.set('2')
        self.album_suggestions_list.delete(0, tk.END)
        self.album_songs_list.delete(0, tk.END)
        self.current_album_songs = []
        self.last_album_cover_path = ''

    def refresh_album_selector(self):
        """Refresh album combobox options."""
        values = []
        for aid, cfg in sorted(self.albums.items(), key=lambda kv: kv[1].get('album_name', kv[0]).lower()):
            values.append(cfg.get('album_name') or aid)
        self.album_select_combo['values'] = values

    def on_album_select_combo(self, event=None):
        """Load album into form when selected."""
        sel_name = self.album_select_var.get()
        if not sel_name:
            return
        target_id = None
        for aid, cfg in self.albums.items():
            if cfg.get('album_name') == sel_name or aid == sel_name:
                target_id = aid
                break
        if not target_id:
            return
        self.current_album_id = target_id
        self.current_album = self.albums.get(target_id, {})
        self.album_name_var.set(self.current_album.get('album_name', ''))
        self.album_lang_var.set(self.current_album.get('language', 'EN') or 'EN')
        self.album_cover_size_album_var.set(self.current_album.get('cover_size', '1:1 (1024x1024)'))
        self.album_cover_format_album_var.set(self.current_album.get('cover_format', 'PNG'))
        self.album_video_size_var.set(self.current_album.get('video_size', '9:16 (720x1280)'))
        if hasattr(self, 'album_video_duration_var'):
            self.album_video_duration_var.set(str(self.current_album.get('video_duration', 6)))
        if hasattr(self, 'album_video_multiscene_var'):
            self.album_video_multiscene_var.set(self.current_album.get('video_multiscene', False))
        if hasattr(self, 'album_video_scene_duration_var'):
            self.album_video_scene_duration_var.set(str(self.current_album.get('video_scene_duration', 2)))
        self.album_cover_album_text.delete('1.0', tk.END)
        self.album_cover_album_text.insert('1.0', self.current_album.get('cover_prompt', ''))
        self.album_video_text.delete('1.0', tk.END)
        self.album_video_text.insert('1.0', self.current_album.get('video_prompt', ''))
        self.last_album_cover_path = self.current_album.get('cover_image_file', '') or ''
        self.album_songs_list.delete(0, tk.END)
        self.current_album_songs = list(self.current_album.get('songs', []))
        for s in self.current_album_songs:
            self.album_songs_list.insert(tk.END, s)

    def apply_album_suggestion(self, event=None):
        """Apply selected album suggestion."""
        sel = self.album_suggestions_list.curselection()
        if not sel:
            return
        value = self.album_suggestions_list.get(sel[0])
        self.album_name_var.set(value)

    def suggest_album_names(self):
        """Ask AI for album name suggestions."""
        selected_songs = self._get_selected_song_ids()
        if not selected_songs:
            messagebox.showwarning('Warning', 'Select one or more songs first.')
            return
        song_titles = []
        song_styles = []
        for sid in selected_songs:
            path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
            cfg = load_song_config(path)
            song_titles.append(cfg.get('song_name', sid))
            if cfg.get('song_style'):
                song_styles.append(cfg.get('song_style'))
        persona_name = self.current_persona.get('name', '') if self.current_persona else ''
        merged_style = self._get_sanitized_style_text()
        lang = self.album_lang_var.get() or 'EN'

        prompt = (
            "Propose 5 concise album title options. Language: {lang}."
            "\nConsider the persona name, merged style, and the selected song titles/styles."
            "\nReturn one suggestion per line, no numbering, no quotes."
            "\nPersona: {persona}\nMerged Style: {style}\nSongs:\n{songs}\nStyles:\n{styles}"
        ).format(
            lang=lang,
            persona=persona_name or 'N/A',
            style=merged_style or 'N/A',
            songs='\n'.join(song_titles) if song_titles else 'N/A',
            styles='\n'.join(song_styles) if song_styles else 'N/A'
        )

        try:
            self.config(cursor='wait')
            self.update()
            result = self.azure_ai(prompt, profile='text')
        except Exception as exc:
            self.config(cursor='')
            messagebox.showerror('Error', f'Failed to fetch album suggestions: {exc}')
            self.log_debug('ERROR', f'Album suggestion failed: {exc}')
            return
        finally:
            self.config(cursor='')

        if not result.get('success'):
            messagebox.showerror('Error', f'Failed to fetch album suggestions: {result.get("error", "Unknown error")}')
            return

        content = result.get('content', '').strip()
        if not content:
            messagebox.showwarning('Warning', 'No suggestions returned.')
            return
        suggestions = [line.strip(' -"') for line in content.splitlines() if line.strip()]
        self.album_suggestions_list.delete(0, tk.END)
        for sug in suggestions[:5]:
            self.album_suggestions_list.insert(tk.END, sug)

    def new_album_from_selection(self):
        """Create a new album from selected songs."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        selected = self._get_selected_song_ids()
        if not selected:
            messagebox.showwarning('Warning', 'Select one or more songs to group into an album.')
            return
        album_name = self.album_name_var.get().strip()
        if not album_name:
            messagebox.showwarning('Warning', 'Enter an album name first.')
            return
        album_id = self._album_slug(album_name)
        albums_dir = self._albums_dir()
        if not albums_dir:
            messagebox.showerror('Error', 'Persona path not available.')
            return
        os.makedirs(albums_dir, exist_ok=True)
        album_path = os.path.join(albums_dir, album_id)
        os.makedirs(album_path, exist_ok=True)

        config = load_album_config(album_path)
        config['album_id'] = album_id
        config['album_name'] = album_name
        config['language'] = self.album_lang_var.get() or 'EN'
        config['cover_size'] = self.album_cover_size_album_var.get()
        config['cover_format'] = self.album_cover_format_album_var.get()
        config['video_size'] = self.album_video_size_var.get()
        config['video_duration'] = int(self.album_video_duration_var.get() or 6) if hasattr(self, 'album_video_duration_var') else 6
        config['video_multiscene'] = bool(self.album_video_multiscene_var.get()) if hasattr(self, 'album_video_multiscene_var') else False
        config['video_scene_duration'] = int(self.album_video_scene_duration_var.get() or 2) if hasattr(self, 'album_video_scene_duration_var') else 2
        config['songs'] = selected
        config['cover_prompt'] = self.album_cover_album_text.get('1.0', tk.END).strip()
        config['video_prompt'] = self.album_video_text.get('1.0', tk.END).strip()

        if save_album_config(album_path, config):
            # Assign songs to album
            for sid in selected:
                song_path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
                song_cfg = load_song_config(song_path)
                song_cfg['album_id'] = album_id
                song_cfg['album_name'] = album_name
                save_song_config(song_path, song_cfg)
            self.load_albums()
            self.refresh_album_selector()
            self.refresh_songs_list()
            self.album_select_var.set(album_name)
            self.on_album_select_combo()
            messagebox.showinfo('Success', f'Album "{album_name}" created with {len(selected)} song(s).')
        else:
            messagebox.showerror('Error', 'Failed to save album.')

    def add_selected_songs_to_album(self):
        """Add selected songs to the current album list (form only)."""
        selected = self._get_selected_song_ids()
        if not selected:
            messagebox.showwarning('Warning', 'Select songs to add.')
            return
        for sid in selected:
            if sid not in self.current_album_songs:
                self.current_album_songs.append(sid)
                self.album_songs_list.insert(tk.END, sid)

    def remove_selected_album_songs(self):
        """Remove songs from current album list (form only)."""
        selections = list(self.album_songs_list.curselection())
        selections.sort(reverse=True)
        for idx in selections:
            value = self.album_songs_list.get(idx)
            self.album_songs_list.delete(idx)
            if value in self.current_album_songs:
                self.current_album_songs.remove(value)

    def ungroup_selected_songs(self):
        """Ungroup selected songs from any album."""
        selected = self._get_selected_song_ids()
        if not selected:
            messagebox.showwarning('Warning', 'Select songs to ungroup.')
            return
        for sid in selected:
            song_path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
            cfg = load_song_config(song_path)
            cfg['album_id'] = ''
            cfg['album_name'] = ''
            save_song_config(song_path, cfg)
        self.refresh_songs_list()
        messagebox.showinfo('Success', f'Ungrouped {len(selected)} song(s).')

    def save_album(self):
        """Persist the current album form to disk and update song configs."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        album_name = self.album_name_var.get().strip()
        if not album_name:
            messagebox.showwarning('Warning', 'Album name is required.')
            return
        album_id = self.current_album_id or self._album_slug(album_name)
        albums_dir = self._albums_dir()
        if not albums_dir:
            messagebox.showerror('Error', 'Persona path not available.')
            return
        os.makedirs(albums_dir, exist_ok=True)
        album_path = os.path.join(albums_dir, album_id)
        os.makedirs(album_path, exist_ok=True)

        songs = list(self.current_album_songs)
        # Ensure songs exist
        songs = [s for s in songs if os.path.isdir(os.path.join(self.current_persona_path, 'AI-Songs', s))]

        config = load_album_config(album_path)
        config.update({
            'album_id': album_id,
            'album_name': album_name,
            'language': self.album_lang_var.get() or 'EN',
            'cover_size': self.album_cover_size_album_var.get(),
            'cover_format': self.album_cover_format_album_var.get(),
            'video_size': self.album_video_size_var.get(),
            'video_duration': int(self.album_video_duration_var.get() or 6) if hasattr(self, 'album_video_duration_var') else 6,
            'video_multiscene': bool(self.album_video_multiscene_var.get()) if hasattr(self, 'album_video_multiscene_var') else False,
            'video_scene_duration': int(self.album_video_scene_duration_var.get() or 2) if hasattr(self, 'album_video_scene_duration_var') else 2,
            'cover_prompt': self.album_cover_album_text.get('1.0', tk.END).strip(),
            'video_prompt': self.album_video_text.get('1.0', tk.END).strip(),
            'songs': songs,
            'cover_image_file': self.last_album_cover_path or config.get('cover_image_file', '')
        })

        if save_album_config(album_path, config):
            # Update song configs
            for sid in songs:
                song_path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
                song_cfg = load_song_config(song_path)
                song_cfg['album_id'] = album_id
                song_cfg['album_name'] = album_name
                save_song_config(song_path, song_cfg)
            # Clear album assignment from songs no longer in album
            if self.current_album_id:
                prev_album_id = self.current_album_id
                for sid in os.listdir(os.path.join(self.current_persona_path, 'AI-Songs')):
                    if sid in songs:
                        continue
                    spath = os.path.join(self.current_persona_path, 'AI-Songs', sid)
                    if not os.path.isdir(spath):
                        continue
                    scfg = load_song_config(spath)
                    if scfg.get('album_id') == prev_album_id and scfg.get('album_name') == album_name:
                        scfg['album_id'] = ''
                        scfg['album_name'] = ''
                        save_song_config(spath, scfg)

            self.current_album_id = album_id
            self.current_album = config
            self.last_album_cover_path = config.get('cover_image_file', '') or self.last_album_cover_path
            self.load_albums()
            self.refresh_album_selector()
            self.refresh_songs_list()
            self.album_select_var.set(album_name)
            messagebox.showinfo('Success', f'Album "{album_name}" saved.')
        else:
            messagebox.showerror('Error', 'Failed to save album.')

    def delete_album(self):
        """Delete the selected album and ungroup its songs."""
        if not self.current_album_id:
            messagebox.showwarning('Warning', 'Select an album first.')
            return
        album_id = self.current_album_id
        album_cfg = self.albums.get(album_id, {})
        album_name = album_cfg.get('album_name', album_id)
        path = self._get_album_path(album_id)
        # Ungroup songs
        for sid in album_cfg.get('songs', []):
            song_path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
            cfg = load_song_config(song_path)
            cfg['album_id'] = ''
            cfg['album_name'] = ''
            save_song_config(song_path, cfg)
        # Delete config file only (respect user rule: do not delete files) -> set empty
        if path:
            blank = {
                'album_id': '',
                'album_name': '',
                'songs': [],
                'cover_prompt': '',
                'cover_size': '1:1 (1024x1024)',
                'cover_format': 'PNG',
                'video_prompt': '',
                'video_size': '9:16 (720x1280)',
                'language': 'EN',
                'cover_image_file': '',
                'video_prompt_file': ''
            }
            save_album_config(path, blank)
        self.load_albums()
        self.refresh_album_selector()
        self.refresh_songs_list()
        self.clear_album_form()
        messagebox.showinfo('Success', f'Album "{album_name}" deleted and songs ungrouped.')

    def rename_album(self):
        """Rename the selected album."""
        if not self.current_album_id:
            messagebox.showwarning('Warning', 'Select an album first.')
            return
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        old_album_id = self.current_album_id
        album_cfg = self.albums.get(old_album_id, {})
        old_album_name = album_cfg.get('album_name', old_album_id)
        
        new_album_name = simpledialog.askstring('Rename Album', 'Enter new album name:', initialvalue=old_album_name)
        if not new_album_name:
            return
        new_album_name = new_album_name.strip()
        if not new_album_name:
            messagebox.showwarning('Warning', 'Album name cannot be empty.')
            return
        
        new_album_id = self._album_slug(new_album_name)
        albums_dir = self._albums_dir()
        if not albums_dir:
            messagebox.showerror('Error', 'Persona path not available.')
            return
        
        old_path = self._get_album_path(old_album_id)
        if not old_path or not os.path.exists(old_path):
            messagebox.showerror('Error', 'Album folder not found.')
            return
        
        old_folder_name = album_cfg.get('folder_name') or old_album_id
        new_folder_name = new_album_id
        new_path = os.path.join(albums_dir, new_folder_name)
        
        if old_album_id != new_album_id and os.path.exists(new_path):
            messagebox.showerror('Error', f'An album with ID "{new_album_id}" already exists.')
            return
        
        try:
            if old_folder_name != new_folder_name:
                shutil.move(old_path, new_path)
                config_path = new_path
            else:
                config_path = old_path
            
            config = load_album_config(config_path)
            config.update({
                'album_id': new_album_id,
                'album_name': new_album_name,
                'folder_name': new_folder_name
            })
            
            if save_album_config(config_path, config):
                for sid in config.get('songs', []):
                    song_path = os.path.join(self.current_persona_path, 'AI-Songs', sid)
                    if os.path.isdir(song_path):
                        song_cfg = load_song_config(song_path)
                        song_cfg['album_id'] = new_album_id
                        song_cfg['album_name'] = new_album_name
                        save_song_config(song_path, song_cfg)
                
                self.current_album_id = new_album_id
                self.current_album = config
                self.load_albums()
                self.refresh_album_selector()
                self.refresh_songs_list()
                self.album_select_var.set(new_album_name)
                self.album_name_var.set(new_album_name)
                messagebox.showinfo('Success', f'Album renamed from "{old_album_name}" to "{new_album_name}".')
            else:
                messagebox.showerror('Error', 'Failed to save album config.')
        except Exception as exc:
            messagebox.showerror('Error', f'Failed to rename album: {exc}')
            self.log_debug('ERROR', f'Rename album failed: {exc}')

    def clone_album(self):
        """Clone an album with translation from English to German or German to English."""
        if not self.current_album_id:
            messagebox.showwarning('Warning', 'Select an album first.')
            return
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        album_cfg = self.albums.get(self.current_album_id, {})
        album_name = album_cfg.get('album_name', self.current_album_id)
        album_songs = album_cfg.get('songs', [])
        
        if not album_songs:
            messagebox.showwarning('Warning', 'Selected album has no songs.')
            return
        
        # Step 1: Select translation direction
        lang_dialog = tk.Toplevel(self)
        lang_dialog.title('Clone Album - Translation Direction')
        lang_dialog.geometry('400x200')
        lang_dialog.transient(self)
        lang_dialog.grab_set()
        lang_dialog.update_idletasks()
        
        # Center dialog
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or lang_dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or lang_dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = lang_dialog.winfo_screenwidth()
            parent_h = lang_dialog.winfo_screenheight()
        dlg_w = lang_dialog.winfo_width()
        dlg_h = lang_dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        lang_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        main_frame = ttk.Frame(lang_dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Select Translation Direction:', font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 15))
        
        lang_var = tk.StringVar(value='en_to_de')
        ttk.Radiobutton(main_frame, text='English → German', variable=lang_var, value='en_to_de').pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text='German → English', variable=lang_var, value='de_to_en').pack(anchor=tk.W, pady=5)
        
        result = [None]
        
        def ok_clicked():
            result[0] = lang_var.get()
            lang_dialog.destroy()
        
        def cancel_clicked():
            lang_dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text='OK', command=ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        lang_dialog.bind('<Return>', lambda e: ok_clicked())
        lang_dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(lang_dialog)
        
        if not result[0]:
            return
        
        translation_dir = result[0]
        source_lang = 'English' if translation_dir == 'en_to_de' else 'German'
        target_lang = 'German' if translation_dir == 'en_to_de' else 'English'
        
        # Step 2: Load all song configs
        song_configs = {}
        song_titles = []
        for song_id in album_songs:
            song_path = os.path.join(self.current_persona_path, 'AI-Songs', song_id)
            if os.path.isdir(song_path):
                song_cfg = load_song_config(song_path)
                song_configs[song_id] = song_cfg
                song_titles.append(song_cfg.get('song_name', song_id))
        
        # Step 3: Generate translation recommendations
        try:
            self.config(cursor='wait')
            self.update()
            
            # Generate album name recommendations
            album_prompt = (
                f"Translate the album title \"{album_name}\" from {source_lang} to {target_lang}.\n\n"
                f"Generate at least 10 translation options for this album title.\n"
                f"Consider:\n"
                f"- Musical/artistic context\n"
                f"- Natural, idiomatic translations\n"
                f"- Variations that maintain the original meaning and tone\n"
                f"- Creative alternatives that work well as album titles\n\n"
                f"Return one translation option per line, no numbering, no quotes, no bullet points.\n"
                f"Each line should be a complete album title translation."
            )
            
            album_result = self.azure_ai(album_prompt, system_message=f'You are a professional translator specializing in {source_lang} to {target_lang} translations for music and art.', profile='text', max_tokens=800, temperature=0.8)
            
            if not album_result.get('success'):
                self.config(cursor='')
                messagebox.showerror('Error', f'Failed to generate album name translations: {album_result.get("error", "Unknown error")}')
                return
            
            album_suggestions = [line.strip(' -"\'') for line in album_result.get('content', '').strip().splitlines() if line.strip()][:15]
            if not album_suggestions:
                self.config(cursor='')
                messagebox.showerror('Error', 'No album name translations generated.')
                return
            
            # Generate song title recommendations for each song
            song_suggestions_dict = {}
            for song_id, song_cfg in song_configs.items():
                song_name = song_cfg.get('song_name', song_id)
                song_prompt = (
                    f"Translate the song title \"{song_name}\" from {source_lang} to {target_lang}.\n\n"
                    f"Generate at least 10 translation options for this song title.\n"
                    f"Consider:\n"
                    f"- Musical/artistic context\n"
                    f"- Natural, idiomatic translations\n"
                    f"- Variations that maintain the original meaning and tone\n"
                    f"- Creative alternatives that work well as song titles\n\n"
                    f"Return one translation option per line, no numbering, no quotes, no bullet points.\n"
                    f"Each line should be a complete song title translation."
                )
                
                song_result = self.azure_ai(song_prompt, system_message=f'You are a professional translator specializing in {source_lang} to {target_lang} translations for music and art.', profile='text', max_tokens=800, temperature=0.8)
                
                if song_result.get('success'):
                    suggestions = [line.strip(' -"\'') for line in song_result.get('content', '').strip().splitlines() if line.strip()][:15]
                    song_suggestions_dict[song_id] = suggestions if suggestions else [song_name]
                else:
                    song_suggestions_dict[song_id] = [song_name]
            
            self.config(cursor='')
            
        except Exception as exc:
            self.config(cursor='')
            messagebox.showerror('Error', f'Failed to generate translations: {exc}')
            self.log_debug('ERROR', f'Clone album translation generation failed: {exc}')
            return
        
        # Step 4: Show selection dialog
        selection_dialog = tk.Toplevel(self)
        selection_dialog.title(f'Clone Album - Select Translations ({source_lang} → {target_lang})')
        selection_dialog.geometry('900x700')
        selection_dialog.transient(self)
        selection_dialog.grab_set()
        selection_dialog.update_idletasks()
        
        # Center dialog
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or selection_dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or selection_dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = selection_dialog.winfo_screenwidth()
            parent_h = selection_dialog.winfo_screenheight()
        dlg_w = selection_dialog.winfo_width()
        dlg_h = selection_dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        selection_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        main_frame = ttk.Frame(selection_dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Album name selection
        ttk.Label(main_frame, text='Album Name:', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        album_frame = ttk.Frame(main_frame)
        album_frame.pack(fill=tk.X, pady=(0, 15))
        
        album_var = tk.StringVar(value=album_suggestions[0] if album_suggestions else album_name)
        album_combo = ttk.Combobox(album_frame, textvariable=album_var, values=album_suggestions, width=70, state='readonly')
        album_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Songs selection frame with scrollbar
        songs_frame = ttk.LabelFrame(main_frame, text='Song Titles:', padding=10)
        songs_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        canvas = tk.Canvas(songs_frame)
        scrollbar = ttk.Scrollbar(songs_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        song_vars = {}
        for idx, (song_id, song_cfg) in enumerate(song_configs.items()):
            song_name = song_cfg.get('song_name', song_id)
            suggestions = song_suggestions_dict.get(song_id, [song_name])
            
            row_frame = ttk.Frame(scrollable_frame)
            row_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(row_frame, text=f'{song_name}:', font=('TkDefaultFont', 9), width=30, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
            
            song_var = tk.StringVar(value=suggestions[0] if suggestions else song_name)
            song_combo = ttk.Combobox(row_frame, textvariable=song_var, values=suggestions, width=50, state='readonly')
            song_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            song_vars[song_id] = song_var
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        result = [None, None]
        
        def clone_ok_clicked():
            selected_album_name = album_var.get().strip()
            if not selected_album_name:
                messagebox.showwarning('Warning', 'Please select an album name.')
                return
            
            selected_songs = {}
            for song_id, song_var in song_vars.items():
                selected_name = song_var.get().strip()
                if not selected_name:
                    messagebox.showwarning('Warning', f'Please select a translation for song: {song_configs[song_id].get("song_name", song_id)}')
                    return
                selected_songs[song_id] = selected_name
            
            result[0] = selected_album_name
            result[1] = selected_songs
            selection_dialog.destroy()
        
        def clone_cancel_clicked():
            selection_dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text='Clone Album', command=clone_ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=clone_cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        selection_dialog.bind('<Return>', lambda e: clone_ok_clicked())
        selection_dialog.bind('<Escape>', lambda e: clone_cancel_clicked())
        
        self.wait_window(selection_dialog)
        
        if not result[0] or not result[1]:
            return
        
        selected_album_name = result[0]
        selected_songs = result[1]
        
        # Step 5: Create cloned album and songs
        try:
            new_album_id = self._album_slug(selected_album_name)
            albums_dir = self._albums_dir()
            if not albums_dir:
                messagebox.showerror('Error', 'Persona path not available.')
                return
            
            # Check if album already exists
            new_album_path = os.path.join(albums_dir, new_album_id)
            if os.path.exists(new_album_path) and os.path.exists(os.path.join(new_album_path, 'config.json')):
                existing_cfg = load_album_config(new_album_path)
                if existing_cfg.get('album_name'):
                    messagebox.showerror('Error', f'An album with name "{selected_album_name}" already exists.')
                    return
            
            os.makedirs(new_album_path, exist_ok=True)
            
            # Clone songs
            new_song_ids = []
            songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
            
            for song_id, translated_name in selected_songs.items():
                # Create safe folder name
                safe_name = translated_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
                
                new_song_path = os.path.join(songs_dir, safe_name)
                
                # Check if song already exists
                if os.path.exists(new_song_path):
                    # Try with a number suffix
                    counter = 1
                    while os.path.exists(new_song_path):
                        safe_name_with_suffix = f'{safe_name} ({counter})'
                        new_song_path = os.path.join(songs_dir, safe_name_with_suffix)
                        counter += 1
                    safe_name = safe_name_with_suffix
                    new_song_path = os.path.join(songs_dir, safe_name)
                
                # Create new song directory
                os.makedirs(new_song_path, exist_ok=True)
                
                # Load original song config
                original_song_path = os.path.join(songs_dir, song_id)
                original_cfg = song_configs[song_id].copy()
                
                # Update song config with translated name
                original_cfg['song_name'] = translated_name
                original_cfg['album_id'] = new_album_id
                original_cfg['album_name'] = selected_album_name
                # Clear lyrics (user will translate separately)
                original_cfg['lyrics'] = ''
                original_cfg['extracted_lyrics'] = ''
                original_cfg['lyric_ideas'] = ''
                
                # Translate cover prompts if they exist
                if original_cfg.get('storyboard_theme'):
                    try:
                        self.config(cursor='wait')
                        self.update()
                        theme_prompt = (
                            f"Translate the following text from {source_lang} to {target_lang}, "
                            f"maintaining the artistic and visual context:\n\n{original_cfg['storyboard_theme']}\n\n"
                            f"Return only the translated text, no explanations."
                        )
                        theme_result = self.azure_ai(theme_prompt, system_message=f'You are a professional translator for music and visual art.', profile='text', max_tokens=500, temperature=0.7)
                        if theme_result.get('success'):
                            original_cfg['storyboard_theme'] = theme_result.get('content', '').strip()
                    except Exception as e:
                        self.log_debug('WARNING', f'Failed to translate storyboard theme: {e}')
                    finally:
                        self.config(cursor='')
                
                # Save new song config
                save_song_config(new_song_path, original_cfg)
                new_song_ids.append(safe_name)
            
            # Create album config
            new_album_cfg = album_cfg.copy()
            new_album_cfg['album_id'] = new_album_id
            new_album_cfg['album_name'] = selected_album_name
            new_album_cfg['songs'] = new_song_ids
            new_album_cfg['language'] = 'DE' if translation_dir == 'en_to_de' else 'EN'
            
            # Translate album cover prompt
            if album_cfg.get('cover_prompt'):
                try:
                    self.config(cursor='wait')
                    self.update()
                    cover_prompt_text = album_cfg['cover_prompt']
                    # Replace original album name and song titles with translated ones in the prompt
                    cover_prompt_text = cover_prompt_text.replace(album_name, selected_album_name)
                    for orig_id, orig_cfg in song_configs.items():
                        orig_title = orig_cfg.get('song_name', orig_id)
                        trans_title = selected_songs.get(orig_id, orig_title)
                        cover_prompt_text = cover_prompt_text.replace(orig_title, trans_title)
                    
                    # Translate the rest of the prompt
                    cover_prompt = (
                        f"Translate the following album cover image prompt from {source_lang} to {target_lang}, "
                        f"maintaining all artistic and visual descriptions. The album name and song titles have already been replaced with their translations.\n\n"
                        f"{cover_prompt_text}\n\n"
                        f"Return only the translated prompt text, no explanations."
                    )
                    cover_result = self.azure_ai(cover_prompt, system_message=f'You are a professional translator for visual art and music cover descriptions.', profile='text', max_tokens=2000, temperature=0.7)
                    if cover_result.get('success'):
                        new_album_cfg['cover_prompt'] = cover_result.get('content', '').strip()
                    else:
                        new_album_cfg['cover_prompt'] = cover_prompt_text
                except Exception as e:
                    self.log_debug('WARNING', f'Failed to translate album cover prompt: {e}')
                    new_album_cfg['cover_prompt'] = album_cfg.get('cover_prompt', '')
                finally:
                    self.config(cursor='')
            else:
                new_album_cfg['cover_prompt'] = ''
            
            # Translate album video prompt
            if album_cfg.get('video_prompt'):
                try:
                    self.config(cursor='wait')
                    self.update()
                    video_prompt_text = album_cfg['video_prompt']
                    # Replace original album name and song titles with translated ones
                    video_prompt_text = video_prompt_text.replace(album_name, selected_album_name)
                    for orig_id, orig_cfg in song_configs.items():
                        orig_title = orig_cfg.get('song_name', orig_id)
                        trans_title = selected_songs.get(orig_id, orig_title)
                        video_prompt_text = video_prompt_text.replace(orig_title, trans_title)
                    
                    # Translate the rest of the prompt
                    video_prompt = (
                        f"Translate the following album video loop prompt from {source_lang} to {target_lang}, "
                        f"maintaining all artistic and visual descriptions. The album name and song titles have already been replaced with their translations.\n\n"
                        f"{video_prompt_text}\n\n"
                        f"Return only the translated prompt text, no explanations."
                    )
                    video_result = self.azure_ai(video_prompt, system_message=f'You are a professional translator for visual art and music video descriptions.', profile='text', max_tokens=2000, temperature=0.7)
                    if video_result.get('success'):
                        new_album_cfg['video_prompt'] = video_result.get('content', '').strip()
                    else:
                        new_album_cfg['video_prompt'] = video_prompt_text
                except Exception as e:
                    self.log_debug('WARNING', f'Failed to translate album video prompt: {e}')
                    new_album_cfg['video_prompt'] = album_cfg.get('video_prompt', '')
                finally:
                    self.config(cursor='')
            else:
                new_album_cfg['video_prompt'] = ''
            
            # Clear cover image file reference (new album needs new cover)
            new_album_cfg['cover_image_file'] = ''
            new_album_cfg['video_prompt_file'] = ''
            
            # Save album config
            if save_album_config(new_album_path, new_album_cfg):
                self.load_albums()
                self.refresh_album_selector()
                self.refresh_songs_list()
                messagebox.showinfo('Success', f'Album cloned successfully as "{selected_album_name}" with {len(new_song_ids)} songs.\n\nNote: Song lyrics were not translated. You can translate them separately.')
            else:
                messagebox.showerror('Error', 'Failed to save cloned album config.')
        
        except Exception as exc:
            messagebox.showerror('Error', f'Failed to clone album: {exc}')
            self.log_debug('ERROR', f'Clone album failed: {exc}')

    def _album_cover_size_value(self) -> str:
        """Get album cover size value, mapped to supported sizes for gpt-image-1.5."""
        match = re.search(r'\((\d+x\d+)\)', self.album_cover_size_album_var.get() or '')
        if match:
            extracted_size = match.group(1)
            # Map to supported size
            return self._map_to_supported_image_size(extracted_size)
        return '1024x1024'

    def _album_video_size_value(self) -> str:
        match = re.search(r'\((\d+x\d+)\)', self.album_video_size_var.get() or '')
        return match.group(1) if match else '720x1280'

    def generate_album_cover_prompt_album(self):
        """Generate album-level cover prompt from selected songs/persona."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return

        dialog = PromptGenerationIdeasDialog(self, 'Album Cover', 'Album')
        self.wait_window(dialog)
        if dialog.result is None:
            return
        user_ideas = (dialog.result or '').strip()

        include_persona = self.include_persona_in_cover_var.get() if hasattr(self, 'include_persona_in_cover_var') else True
        album_name = self.album_name_var.get().strip()
        if not album_name:
            messagebox.showwarning('Warning', 'Enter an album name first.')
            return
        songs = self.current_album_songs or self._get_selected_song_ids()
        song_titles = []
        for sid in songs:
            spath = os.path.join(self.current_persona_path, 'AI-Songs', sid)
            scfg = load_song_config(spath)
            raw_title = scfg.get('song_name', sid)
            # Remove parenthetical content from song titles
            clean_title = self._remove_parenthetical_content(raw_title)
            song_titles.append(clean_title if clean_title else raw_title)

        merged_style = self._get_sanitized_style_text()
        storyboard_theme = self.storyboard_theme_text.get('1.0', tk.END).strip() if hasattr(self, 'storyboard_theme_text') else ''
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '') if include_persona else ''
        base_image_prompt = self.current_persona.get('base_image_prompt', '') if include_persona else ''
        vibe = self.current_persona.get('vibe', '') if include_persona else ''
        references = []
        if include_persona:
            preset_key = self._get_song_persona_preset_key()
            base_path = self.get_persona_image_base_path(preset_key)
            safe_name = self._safe_persona_basename()
            for view in ['Front', 'Side', 'Back']:
                p = os.path.join(base_path, f'{safe_name}-{view}.png')
                if os.path.exists(p):
                    references.append(p)

        prompt = (
            f"Create an album cover prompt for the album \"{album_name}\"."
            f"\nSongs: {', '.join(song_titles) if song_titles else 'N/A'}"
            f"\nMerged Style: {merged_style}"
        )
        if include_persona:
            prompt += f"\nPersona: {self.current_persona.get('name', '')}"
        else:
            prompt += "\nCRITICAL: No persona. No human figures, characters, or people in the image. Cover must be purely environmental, abstract, symbolic, or atmospheric."
        if storyboard_theme:
            prompt += f"\nStoryboard Theme (primary aesthetic): {storyboard_theme}"
        if visual_aesthetic:
            prompt += f"\nPersona Visual Aesthetic: {visual_aesthetic}"
        if base_image_prompt:
            prompt += f"\nPersona Base Image Prompt: {base_image_prompt}"
        if vibe:
            prompt += f"\nPersona Vibe: {vibe}"
        if user_ideas:
            prompt += f"\n\n=== ADDITIONAL USER IDEAS (MUST INCORPORATE) ===\n{user_ideas}\n=== END USER IDEAS ===\n"
        prompt += (
            "\nReturn only the album cover image prompt text."
            "\nMANDATORY TYPOGRAPHY: Render the full album title verbatim, with no truncation, no abbreviation, and no ellipsis. Text must be fully readable in the final cover."
        )
        if include_persona:
            prompt += " Also render the persona/artist name verbatim."
        prompt += (
            "\nTEXT LAYOUT RULES: Reserve clear space so the full title and artist fit without clipping. Do not crop or cut off any characters. Adjust composition/scale to keep 100% of the text visible and readable. No ellipsis, no partial words."
            "\nIMPORTANT: If any song names contain parenthetical content (e.g., ' - (devotional folk meditative)'), ignore it completely. Do not include any parenthetical descriptions or style keywords in the album cover prompt. Use only the core song titles without any parenthetical additions."
        )

        try:
            self.config(cursor='wait')
            self.update()
            if references:
                system_message = "You generate album cover prompts using reference images. Output only the prompt text."
                result = self.azure_vision(references, prompt, system_message=system_message, profile='text')
            else:
                system_message = "You generate album cover prompts. Output only the prompt text."
                result = self.azure_ai(prompt, system_message=system_message, profile='text')
        except Exception as exc:
            self.config(cursor='')
            messagebox.showerror('Error', f'Failed to generate album cover prompt: {exc}')
            self.log_debug('ERROR', f'Album cover prompt failed: {exc}')
            return
        finally:
            self.config(cursor='')

        if result.get('success'):
            text = result.get('content', '').strip()
            self.album_cover_album_text.delete('1.0', tk.END)
            self.album_cover_album_text.insert('1.0', text)
            if self.current_album is not None:
                self.current_album['cover_prompt'] = text
            # Keep album cover prompt handy for preview context
        else:
            messagebox.showerror('Error', f'Failed to generate album cover prompt: {result.get("error", "Unknown error")}')

    def run_album_cover_image(self):
        """Generate album cover image from the album prompt."""
        prompt = self.album_cover_album_text.get('1.0', tk.END).strip()
        if not prompt:
            messagebox.showwarning('Warning', 'Generate an album cover prompt first.')
            return
        self.last_album_cover_path = ''
        album_name = self.album_name_var.get().strip() or 'album'
        album_id = self.current_album_id or self._album_slug(album_name)
        size = self._album_cover_size_value()
        fmt = (self.album_cover_format_album_var.get() or 'PNG').lower()
        album_path = self._get_album_path(album_id) or os.path.join(self._albums_dir() or '', album_id)
        os.makedirs(album_path, exist_ok=True)
        
        # Generate safe filename from album name
        safe_basename = album_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
        
        # Extract aspect ratio from album cover size (e.g., "3:2 (1536x1024)" -> "3:2" -> "3x2")
        aspect_ratio_suffix = ''
        if hasattr(self, 'album_cover_size_album_var'):
            size_value = self.album_cover_size_album_var.get()
            # Extract aspect ratio part before parentheses (e.g., "3:2" from "3:2 (1536x1024)")
            match = re.search(r'^([^\(]+)', size_value)
            if match:
                aspect_ratio = match.group(1).strip()
                # Convert ":" to "x" (e.g., "3:2" -> "3x2", "1:1" -> "1x1")
                aspect_ratio_x = aspect_ratio.replace(':', 'x')
                # Only append if not 1x1
                if aspect_ratio_x != '1x1':
                    aspect_ratio_suffix = aspect_ratio_x
        
        filename = enable_long_paths(os.path.join(album_path, f'{safe_basename}{aspect_ratio_suffix}.{fmt}'))

        try:
            self.config(cursor='wait')
            self.update()
            result = self.azure_image(prompt, size=size, profile='image_gen')
        except Exception as exc:
            self.config(cursor='')
            messagebox.showerror('Error', f'Failed to generate cover: {exc}')
            self.log_debug('ERROR', f'Album cover image failed: {exc}')
            return
        finally:
            self.config(cursor='')

        if result.get('success'):
            img_bytes = result.get('image_bytes', b'')
            if img_bytes:
                # Create backup if file exists
                backup_path = self.backup_file_if_exists(filename)
                
                with open(filename, 'wb') as f:
                    f.write(img_bytes)
                success_msg = f'Album cover saved to {filename}'
                if backup_path:
                    success_msg += f'\n\nBackup created: {os.path.basename(backup_path)}'
                messagebox.showinfo('Success', success_msg)
                if self.current_album is not None:
                    self.current_album['cover_image_file'] = filename
                self.last_album_cover_path = filename
                self.show_image_preview(filename, 'Album Cover Preview')
            else:
                messagebox.showerror('Error', 'No image bytes received.')
        else:
            messagebox.showerror('Error', f'Failed to generate cover: {result.get("error", "Unknown error")}')

    def generate_album_video_prompt(self):
        """Generate album-level video loop prompt. Supports multi-scene mode with direct camera cuts."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return

        dialog = PromptGenerationIdeasDialog(self, 'Album Video', 'Album')
        self.wait_window(dialog)
        if dialog.result is None:
            return
        user_ideas = (dialog.result or '').strip()

        album_name = self.album_name_var.get().strip()
        base_prompt = self.album_cover_album_text.get('1.0', tk.END).strip()
        if not base_prompt:
            messagebox.showwarning('Warning', 'Generate album cover prompt first.')
            return
        
        # Get multi-scene settings
        is_multiscene = self.album_video_multiscene_var.get() if hasattr(self, 'album_video_multiscene_var') else False
        video_duration = int(self.album_video_duration_var.get() or 6) if hasattr(self, 'album_video_duration_var') else 6
        try:
            scene_duration = int(self.album_video_scene_duration_var.get() or 2) if hasattr(self, 'album_video_scene_duration_var') else 2
        except Exception:
            scene_duration = 2
        scene_duration = max(1, min(10, scene_duration))
        num_scenes = max(1, video_duration // scene_duration) if is_multiscene else 1
        
        merged_style = self._get_sanitized_style_text()
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
        base_image_prompt = self.current_persona.get('base_image_prompt', '')
        vibe = self.current_persona.get('vibe', '')
        
        if is_multiscene and num_scenes > 1:
            # Multi-scene prompt
            prompt = (
                f"Create a {video_duration}-second multi-scene video loop prompt for the album \"{album_name}\" "
                f"with {num_scenes} distinct scenes, each lasting {scene_duration} seconds.\n\n"
                f"Based on this cover description:\n{base_prompt}\n\nMerged Style: {merged_style}"
            )
            if user_ideas:
                prompt += f"\n\n=== ADDITIONAL USER IDEAS (MUST INCORPORATE) ===\n{user_ideas}\n=== END USER IDEAS ===\n"
            if visual_aesthetic:
                prompt += f"\nPersona Visual Aesthetic: {visual_aesthetic}"
            if base_image_prompt:
                prompt += f"\nPersona Base Image Prompt: {base_image_prompt}"
            if vibe:
                prompt += f"\nPersona Vibe: {vibe}"
            
            prompt += "\n\n=== MULTI-SCENE REQUIREMENTS (CRITICAL FOR AI VIDEO TOOLS) ==="
            prompt += "\n- Use HARD CUTS / JUMP CUTS between scenes - NO smooth transitions, NO fades, NO morphing, NO continuity"
            prompt += "\n- Each scene must RADICALLY change - wildly different environments, settings, or compositions every " + str(scene_duration) + " second(s)"
            prompt += "\n- Add keywords: 'rapid scene changes', 'montage style', 'abrupt transitions', 'hyper-fast cuts' to encourage the AI to actually change scenes"
            prompt += "\n- The persona/character must appear consistently across all scenes (if included)"
            prompt += "\n- Use explicit time markers in output - AI video tools (Runway, Kling, etc.) respond to timeline phrasing"
            prompt += "\n- Avoid: smooth gradual transition, slow motion, same scene persisting, boring, static"
            prompt += "\n\nFormat your output as (use exact timestamps):"
            for i in range(num_scenes):
                start_time = i * scene_duration
                end_time = start_time + scene_duration
                prompt += f"\n\n[{start_time}s-{end_time}s] Scene {i+1}: [describe a RADICALLY different scene - distinct setting, angle, or composition]"
            
            system_message = (
                f'You are a video prompt generator for AI video tools (Runway, Kling, Grok Imagine, etc.). '
                f'Create a {video_duration}-second multi-scene video with {num_scenes} distinct scenes ({scene_duration}s each). '
                'CRITICAL: Use HARD CUTS, JUMP CUTS - each scene must be wildly different. Add "rapid transitions", "montage style", "abrupt", "no continuity" to your output. '
                'AI video tools often smooth everything - your prompt must explicitly demand radical scene changes every second. '
                'Output ONLY the final prompt text with scene timestamps.'
            )
        else:
            # Single scene prompt (original behavior)
            prompt = (
                f"Create a seamless looping video prompt for the album \"{album_name}\" "
                f"based on this cover description:\n{base_prompt}\n\nMerged Style: {merged_style}"
            )
            if user_ideas:
                prompt += f"\n\n=== ADDITIONAL USER IDEAS (MUST INCORPORATE) ===\n{user_ideas}\n=== END USER IDEAS ===\n"
            if visual_aesthetic:
                prompt += f"\nPersona Visual Aesthetic: {visual_aesthetic}"
            if base_image_prompt:
                prompt += f"\nPersona Base Image Prompt: {base_image_prompt}"
            if vibe:
                prompt += f"\nPersona Vibe: {vibe}"
            prompt += "\nReturn only the final video prompt text."
            
            system_message = 'You are a video loop prompt generator. Output only the final prompt text.'

        scaled_cover_path = None
        try:
            self.config(cursor='wait')
            self.update()
            self.log_debug('INFO', f'Generating {"multi-scene " if is_multiscene else ""}album video prompt...')
            if hasattr(self, 'last_album_cover_path') and self.last_album_cover_path and os.path.isfile(self.last_album_cover_path):
                scaled_cover_path = _scale_image_to_half(self.last_album_cover_path)
                if scaled_cover_path:
                    prompt = f"This is the generated album cover image (scaled). Create a video prompt that matches and extends this visual.\n\n{prompt}"
                    result = self.azure_vision([scaled_cover_path], prompt, system_message=system_message, profile='text')
                    self.log_debug('INFO', 'Using album cover image for video prompt generation')
                else:
                    result = self.azure_ai(prompt, system_message=system_message, profile='text')
            else:
                result = self.azure_ai(prompt, system_message=system_message, profile='text')
        except Exception as exc:
            self.config(cursor='')
            messagebox.showerror('Error', f'Failed to generate album video prompt: {exc}')
            self.log_debug('ERROR', f'Album video prompt failed: {exc}')
            return
        finally:
            self.config(cursor='')
            if scaled_cover_path and os.path.exists(scaled_cover_path):
                try:
                    os.unlink(scaled_cover_path)
                except Exception:
                    pass

        if result.get('success'):
            text = result.get('content', '').strip()
            self.album_video_text.delete('1.0', tk.END)
            self.album_video_text.insert('1.0', text)
            if self.current_album is not None:
                self.current_album['video_prompt'] = text
            mode_str = f'multi-scene ({num_scenes} scenes)' if is_multiscene else 'single scene'
            self.log_debug('INFO', f'Album video prompt generated successfully ({mode_str})')
        else:
            messagebox.showerror('Error', f'Failed to generate video prompt: {result.get("error", "Unknown error")}')
    
    def save_album_video_prompt(self):
        """Save the album video prompt to a JSON file using the same basename as the album cover."""
        if not self.current_album_id:
            messagebox.showwarning('Warning', 'No album selected. Cannot save album video prompt.')
            return
        
        video_prompt = self.album_video_text.get('1.0', tk.END).strip()
        if not video_prompt:
            messagebox.showwarning('Warning', 'Album video prompt is empty. Please generate a prompt first.')
            return
        
        try:
            # Use album name as basename
            album_name = self.album_name_var.get().strip()
            if not album_name:
                album_name = 'album'
            
            # Generate safe filename from album name (same as album cover)
            safe_basename = album_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
            
            # Extract aspect ratio from video size (e.g., "9:16 (720x1280)" -> "9:16" -> "9x16")
            aspect_ratio_suffix = ''
            if hasattr(self, 'album_video_size_var'):
                size_value = self.album_video_size_var.get()
                # Extract aspect ratio part before parentheses (e.g., "9:16" from "9:16 (720x1280)")
                match = re.search(r'^([^\(]+)', size_value)
                if match:
                    aspect_ratio = match.group(1).strip()
                    # Convert ":" to "x" (e.g., "9:16" -> "9x16", "1:1" -> "1x1")
                    aspect_ratio_x = aspect_ratio.replace(':', 'x')
                    # Only append if not 1x1
                    if aspect_ratio_x != '1x1':
                        aspect_ratio_suffix = aspect_ratio_x
            
            # Get album path
            album_id = self.current_album_id
            album_path = self._get_album_path(album_id) or os.path.join(self._albums_dir() or '', album_id)
            os.makedirs(album_path, exist_ok=True)
            
            # Save with same basename as album cover image, as .json file (aspect ratio suffix if not 1:1)
            filename = enable_long_paths(os.path.join(album_path, f'{safe_basename}{aspect_ratio_suffix}.json'))
            
            # Create backup if file exists
            backup_path = self.backup_file_if_exists(filename)
            
            # Create JSON structure (same format as storyboard prompt export)
            export_data = {
                'generated_prompt': video_prompt
            }
            
            # Save the prompt to JSON file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.log_debug('INFO', f'Album video prompt saved to {filename}')
            success_msg = f'Album video prompt saved to:\n{filename}'
            if backup_path:
                success_msg += f'\n\nBackup created: {os.path.basename(backup_path)}'
            messagebox.showinfo('Success', success_msg)
            
            # Also save to config.json
            if self.current_album is not None:
                self.current_album['video_prompt'] = video_prompt
                if save_album_config(album_path, self.current_album):
                    self.log_debug('INFO', 'Config.json updated with album video prompt')
                else:
                    self.log_debug('WARNING', 'Failed to save config.json with album video prompt')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save album video prompt: {e}')
            self.log_debug('ERROR', f'Failed to save album video prompt: {e}')
    
    def improve_album_video_prompt(self):
        """Improve the album video prompt using AI based on user feedback."""
        current_prompt = self.album_video_text.get('1.0', tk.END).strip()
        if not current_prompt:
            messagebox.showwarning('Warning', 'Please generate an album video prompt first.')
            return

        dialog = PromptImprovementDialog(self, 'Album Video', current_prompt)
        self.wait_window(dialog)
        if not dialog.result:
            return

        improvement_request = dialog.result
        prompt = f"Improve the following album video prompt based on these requested changes:\n\n"
        prompt += f"REQUESTED CHANGES: {improvement_request}\n\n"
        prompt += f"CURRENT PROMPT:\n{current_prompt}\n\n"
        prompt += "Generate an improved version of the video prompt that incorporates the requested changes while maintaining the core concept, style, and scene structure. Output ONLY the improved prompt text, nothing else."

        try:
            self.config(cursor='wait')
            self.update()
            system_message = 'You are an expert at improving video generation prompts. Analyze the current prompt and requested changes, then generate an improved version that incorporates the changes while maintaining quality, coherence, and proper scene formatting. Output ONLY the improved prompt text.'
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)

            if result.get('success'):
                improved_prompt = result.get('content', '').strip()
                result_dialog = ImprovedPromptResultDialog(self, improved_prompt, current_prompt)
                self.wait_window(result_dialog)
                if result_dialog.result:
                    self.album_video_text.delete('1.0', tk.END)
                    self.album_video_text.insert('1.0', improved_prompt)
                    if self.current_album is not None:
                        self.current_album['video_prompt'] = improved_prompt
                    self.log_debug('INFO', 'Album video prompt improved and saved')
                    messagebox.showinfo('Success', 'Improved prompt saved.')
            else:
                messagebox.showerror('Error', f'Failed to improve prompt: {result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to improve album video prompt: {result.get("error", "Unknown error")}')
        except Exception as e:
            messagebox.showerror('Error', f'Error improving album video prompt: {e}')
            self.log_debug('ERROR', f'Error improving album video prompt: {e}')
        finally:
            self.config(cursor='')

    def _ask_language(self, title='Select Language'):
        """Show a dialog to select language (English or German). Returns 'en' or 'de', or None if cancelled."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry('300x200')
        dialog.transient(self)
        dialog.grab_set()
        
        result = [None]
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Select Language:', font=('TkDefaultFont', 9, 'bold')).pack(pady=(0, 10))
        
        lang_var = tk.StringVar(value='en')
        
        lang_frame = ttk.Frame(main_frame)
        lang_frame.pack(pady=10)
        
        ttk.Radiobutton(lang_frame, text='English (Default)', variable=lang_var, value='en').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text='German', variable=lang_var, value='de').pack(anchor=tk.W, pady=2)
        
        def ok_clicked():
            result[0] = lang_var.get()
            dialog.destroy()
        
        def cancel_clicked():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text='OK', command=ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Return>', lambda e: ok_clicked())
        dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(dialog)
        return result[0]
    
    def generate_full_song_name(self):
        """Generate full song name via AI prompt: [Song Name] - [Persona Name] - (3 keywords)."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        # Ask for language selection
        language = self._ask_language('Select Language for Song Name')
        if language is None:
            return  # User cancelled
        
        song_name = self.song_name_var.get().strip()
        persona_name = self.current_persona.get('name', '')
        raw_song_style = self.song_style_text.get('1.0', tk.END).strip()
        song_style = self._sanitize_style_keywords(raw_song_style)
        if song_style != raw_song_style:
            self.song_style_text.delete('1.0', tk.END)
            self.song_style_text.insert('1.0', song_style)
            self.log_debug('INFO', 'Removed band names from song style for full song name')
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        if not persona_name:
            messagebox.showwarning('Warning', 'Persona name is not set.')
            return
        
        # Use only the merged style for keywords (ignore raw song style, voice, gender)
        merged_style_raw = self.merged_style_text.get('1.0', tk.END).strip() if hasattr(self, 'merged_style_text') else ''
        style_text = merged_style_raw
        keywords = self._extract_style_keywords(style_text)
        keywords_text = ', '.join(keywords[:3]) if keywords else ''
        
        fallback_keywords = keywords.copy() if keywords else []
        if not fallback_keywords:
            fallback_keywords = ['style']
        while len(fallback_keywords) < 3:
            fallback_keywords.append(fallback_keywords[-1])
        fallback_full_song_name = f"{song_name} - {persona_name} - ({', '.join(fallback_keywords[:3])})"
        
        truncated_merged = merged_style_raw
        if len(truncated_merged) > 320:
            truncated_merged = truncated_merged[:320].rstrip() + '...'
        
        def _trim_text(value: str, limit: int = 200) -> str:
            if not value:
                return ''
            return value if len(value) <= limit else value[:limit].rstrip() + '...'
        
        lyrics_text = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        merged_style = merged_style_raw
        
        lyrics_trim = _trim_text(lyrics_text, 200)
        
        language_instruction = "Generate the song name in English." if language == 'en' else "Generate the song name in German."
        
        system_message = (
            "You format AI-generated song titles. Return exactly one line in the form:\n"
            "Song Title - Persona Name - (kw1, kw2, kw3)\n"
            "Rules: Use the provided Song Name verbatim. Use the Persona Name verbatim. "
            "Derive up to three single-word style keywords from the Style only. "
            "No artist/persona/band names, genders, voices, instruments, production terms, or non-style words. Only style words. "
            "Separate keywords with space inside parentheses. "
            "Do not invent band/artist names. "
            "Do not leave the answer blank. "
            f"{language_instruction} "
            "Output only the final title line, nothing else."
        )
        
        prompt = (
            "Create the formatted full song name.\n\n"
            f"Song Name: {song_name}\n"
            f"Persona Name: {persona_name}\n"
            f"Song Style: {song_style}\n"
            f"Merged Style: {merged_style}\n"
            f"Language: {'English' if language == 'en' else 'German'}\n"
            "Find threesingle-word style descriptors based on Style words (no names, no instruments, no production terms). "
            "If you cannot find three, reuse the strongest until you have three. "
            f"{language_instruction} "
            "Return exactly: Song Name - Persona Name - (kw1, kw2, kw3)"
        )
        
        ai_full_song_name = None
        try:
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=4096, temperature=0.2)
            self.log_debug(
                'PROMPT',
                f"AI full song name result: success={result.get('success')}, "
                f"error={result.get('error')}, "
                f"content_preview={(result.get('content') or '').strip()[:400]}"
            )
            if result.get('success'):
                ai_text = (result.get('content') or '').strip()
                self.log_debug('PROMPT', f'AI full song name raw response:\n{ai_text}')
                if ai_text:
                    first_line = ai_text.splitlines()[0].strip()
                    # Basic format validation
                    if ' - ' in first_line and '(' in first_line and ')' in first_line:
                        ai_full_song_name = first_line
                    else:
                        self.log_debug('WARNING', f'AI full song name not in expected format, using fallback. AI returned: {first_line}')
                else:
                    self.log_debug('WARNING', 'AI returned empty full song name, using fallback.')
            else:
                self.log_debug('ERROR', f"AI full song name failed: {result.get('error')}")
        except Exception as exc:
            self.log_debug('ERROR', f'AI full song name exception: {exc}')
        
        # Use AI result if valid; otherwise fall back to deterministic string
        full_song_name = ai_full_song_name or fallback_full_song_name
        if not ai_full_song_name:
            self.log_debug('PROMPT', f'Using fallback full song name: {full_song_name}')
        
        self.full_song_name_var.set(full_song_name)
        self.log_debug('INFO', f'Full song name generated: {full_song_name}')
        
        # Update play button state after generating full song name
        self.update_play_button()
    
    def generate_lyrics(self):
        """Generate lyrics for the song using AI with enhanced uniqueness and quality."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        # Ask for language selection
        language = self._ask_language('Select Language for Lyrics')
        if language is None:
            return  # User cancelled
        
        song_name = self.song_name_var.get().strip()
        lyric_ideas = self.lyric_ideas_text.get('1.0', tk.END).strip()
        lyrics_style = (self.current_persona.get('lyrics_style') or '').strip()
        voice_style = (self.current_persona.get('voice_style') or '').strip()
        persona_name = (self.current_persona.get('name') or '').strip()
        persona_vibe = (self.current_persona.get('vibe') or '').strip()
        tagline = (self.current_persona.get('tagline') or '').strip()
        bio = (self.current_persona.get('bio') or '').strip()
        genre_tags = self.current_persona.get('genre_tags', [])
        if isinstance(genre_tags, list):
            genre_tags_text = ', '.join([t for t in genre_tags if t])
        else:
            genre_tags_text = str(genre_tags or '')
        style_text = self._get_sanitized_style_text()
        theme_or_topic = lyric_ideas if lyric_ideas else song_name
        mood_text = persona_vibe if persona_vibe else 'introspective, authentic'
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        language_instruction = "Generate all lyrics in English." if language == 'en' else "Generate all lyrics in German."
        
        # Enhanced system message for unique, high-quality lyrics
        system_message = (
            f"You are {persona_name}, a distinctive artist with a unique voice. "
            "Your task is to write ORIGINAL, MEMORABLE lyrics that could only come from this specific persona. "
            "CRITICAL RULES FOR UNIQUENESS:\n"
            "1. AVOID generic poetic words: velvet, static, lullaby, whisper, echo, neon, shadow, void, pulse, haze, silk, chrome, fracture, hollow, drift, fade, shatter, crimson, amber, indigo\n"
            "2. USE concrete, specific imagery: real objects, places, actions, sensations that are UNIQUE to this song's theme\n"
            "3. PREFER active verbs over passive descriptions\n"
            "4. EACH LINE must advance the story or emotion - no filler lines\n"
            "5. The chorus must be SINGABLE and MEMORABLE - test it by imagining a crowd chanting it\n"
            "6. Use UNEXPECTED word combinations and fresh metaphors\n"
            f"{language_instruction} "
            "Return lyrics only with section headings - no explanations or commentary."
        )
        
        # Build rich persona context for better character embodiment
        persona_context = f"PERSONA IDENTITY: {persona_name}"
        if tagline:
            persona_context += f"\nESSENCE: {tagline}"
        if bio:
            # Extract key character traits from bio (first 300 chars for context)
            bio_excerpt = bio[:300] + "..." if len(bio) > 300 else bio
            persona_context += f"\nBACKSTORY: {bio_excerpt}"
        
        prompt_lines = [
            "=== LYRICS GENERATION TASK ===",
            "",
            persona_context,
            "",
            f"SONG TITLE: \"{song_name}\"",
            f"MUSICAL STYLE: {style_text or 'Original style matching persona'}",
            f"THEME/CONCEPT: {theme_or_topic}",
            f"EMOTIONAL TONE: {mood_text}",
            f"LANGUAGE: {'English' if language == 'en' else 'German'}",
            "",
            "=== PERSONA VOICE CHARACTERISTICS ===",
            f"Vocal delivery: {voice_style or 'Authentic to persona character'}",
            f"Lyrical approach: {lyrics_style or 'Narrative, emotionally honest, character-driven'}",
            f"Genre influences: {genre_tags_text or 'Derived from persona style'}",
            "",
            "=== CREATIVE DIRECTION ===",
            lyric_ideas if lyric_ideas else f"Explore the theme \"{song_name}\" through the lens of {persona_name}'s unique perspective and life experience.",
            "",
            "=== SONG STRUCTURE ===",
            "[Intro] - 2-4 lines, set the scene or mood",
            "[Verse 1] - Establish the situation, introduce the conflict or feeling",
            "[Pre-Chorus] - Build tension, 2-4 lines that lift toward the hook",
            "[Chorus / Hook] - The emotional core, MUST be memorable and singable",
            "[Verse 2] - Deepen the story, add new perspective or complication",
            "[Bridge] - Shift in perspective, revelation, or emotional peak",
            "[Final Hook] - Chorus variation with heightened intensity or resolution",
            "[Outro] - 2-4 lines, leave a lasting impression",
            "",
            "=== QUALITY REQUIREMENTS ===",
            "- Every line must EARN its place - cut anything generic",
            "- Rhymes should feel natural, not forced - near-rhymes and internal rhymes welcome",
            "- Vary line lengths for rhythmic interest",
            "- The hook must work standalone - imagine it on a billboard",
            "- Include at least ONE unexpected image or turn of phrase per verse",
            "- Ground abstract emotions in PHYSICAL, SENSORY details",
            "- Write for the VOICE - consider how words feel when sung",
            "",
            "OUTPUT: Complete lyrics with section headers. No explanations."
        ]
        
        prompt = "\n".join(prompt_lines)
        
        self.log_debug('INFO', 'Generating lyrics...')
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, system_message=system_message, profile='text')
            
            if result['success']:
                lyrics = result['content'].strip()
                self.lyrics_text.delete('1.0', tk.END)
                self.lyrics_text.insert('1.0', lyrics)
                self.log_debug('INFO', 'Lyrics generated successfully')
            else:
                messagebox.showerror('Error', f'Failed to generate lyrics: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate lyrics: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating lyrics: {e}')
            self.log_debug('ERROR', f'Error generating lyrics: {e}')
        finally:
            self.config(cursor='')

    def improve_lyrics(self):
        """Improve, change, or translate lyrics using AI."""
        lyrics = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        if not lyrics:
            messagebox.showwarning('Warning', 'No lyrics found. Please add lyrics first.')
            return
        
        # Create dialog for improvement options
        dialog = tk.Toplevel(self)
        dialog.title('Improve Lyrics')
        dialog.geometry('600x550')
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        
        # Center dialog on parent window
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = dialog.winfo_screenwidth()
            parent_h = dialog.winfo_screenheight()
        dlg_w = dialog.winfo_width()
        dlg_h = dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Select Operation:', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        operation_var = tk.StringVar(value='improve')
        
        ttk.Radiobutton(main_frame, text='Improve/Enhance Lyrics (quality, flow, rhymes)', variable=operation_var, value='improve').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(main_frame, text='Translate Lyrics', variable=operation_var, value='translate').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(main_frame, text='Change/Modify with Custom Instructions', variable=operation_var, value='custom').pack(anchor=tk.W, pady=2)
        
        # Language selection frame (for translation)
        lang_frame = ttk.LabelFrame(main_frame, text='Translation Target Language', padding=10)
        lang_frame.pack(fill=tk.X, pady=(10, 0))
        
        lang_var = tk.StringVar(value='de')
        ttk.Radiobutton(lang_frame, text='German', variable=lang_var, value='de').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text='English', variable=lang_var, value='en').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text='Spanish', variable=lang_var, value='es').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text='French', variable=lang_var, value='fr').pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(lang_frame, text='Italian', variable=lang_var, value='it').pack(anchor=tk.W, pady=2)
        
        # Custom instructions
        custom_frame = ttk.LabelFrame(main_frame, text='Custom Instructions', padding=10)
        custom_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        ttk.Label(custom_frame, text='Enter your custom instructions for modifying the lyrics:').pack(anchor=tk.W, pady=(0, 5))
        custom_text = scrolledtext.ScrolledText(custom_frame, height=6, wrap=tk.WORD)
        custom_text.pack(fill=tk.BOTH, expand=True)
        
        result = [None]
        
        def process_lyrics():
            operation = operation_var.get()
            target_lang = lang_var.get() if operation == 'translate' else ''
            custom_instructions = custom_text.get('1.0', tk.END).strip() if operation == 'custom' else ''
            
            if operation == 'custom' and not custom_instructions:
                messagebox.showwarning('Warning', 'Please enter custom instructions.')
                return
            
            self.log_debug('INFO', f'Processing lyrics with operation: {operation}')
            dialog.destroy()
            
            self.config(cursor='wait')
            self.update()
            
            try:
                if operation == 'improve':
                    prompt = f"""Improve and enhance the following song lyrics.

ORIGINAL LYRICS:
{lyrics}

INSTRUCTIONS:
1. Enhance the quality, flow, and rhyming scheme
2. Make the lyrics more poetic and impactful
3. Maintain the original meaning and theme
4. Keep the same language as the original
5. Preserve the structure (Verse, Chorus, Bridge, etc.)
6. Improve word choices and metaphors
7. Ensure strong hooks and memorable lines

Return ONLY the improved lyrics with section labels like [Verse 1], [Chorus], etc."""
                    
                    system_message = "You are an expert lyricist who improves song lyrics while maintaining their essence and structure."
                
                elif operation == 'translate':
                    lang_names = {'de': 'German', 'en': 'English', 'es': 'Spanish', 'fr': 'French', 'it': 'Italian'}
                    target_lang_name = lang_names.get(target_lang, 'German')
                    
                    prompt = f"""Translate the following song lyrics to {target_lang_name}.

ORIGINAL LYRICS:
{lyrics}

INSTRUCTIONS:
1. Translate all lyrics to {target_lang_name}
2. Maintain the rhythm and syllable count as much as possible
3. Preserve rhyming schemes where possible
4. Keep the same emotional tone and meaning
5. Adapt idioms and metaphors culturally when needed
6. Preserve section labels like [Verse 1], [Chorus], [Bridge], etc.
7. Make it singable in the target language

Return ONLY the translated lyrics with section labels."""
                    
                    system_message = f"You are an expert translator specializing in song lyrics, translating to {target_lang_name} while maintaining singability and emotional impact."
                
                elif operation == 'custom':
                    prompt = f"""Modify the following song lyrics according to the custom instructions below.

ORIGINAL LYRICS:
{lyrics}

CUSTOM INSTRUCTIONS:
{custom_instructions}

IMPORTANT:
1. Follow the custom instructions exactly
2. Preserve section labels like [Verse 1], [Chorus], [Bridge], etc.
3. Maintain the song structure unless instructed otherwise
4. Return ONLY the modified lyrics

Return the modified lyrics with section labels."""
                    
                    system_message = "You are an expert lyricist who modifies song lyrics according to specific instructions while maintaining quality and structure."
                
                else:
                    messagebox.showerror('Error', 'Invalid operation selected.')
                    self.config(cursor='')
                    return
                
                # Call AI
                result_ai = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)
                
                if result_ai.get('success'):
                    improved_lyrics = result_ai.get('content', '').strip()
                    
                    # Show preview dialog with accept/cancel
                    preview_dialog = tk.Toplevel(self)
                    preview_dialog.title('Preview Improved Lyrics')
                    preview_dialog.geometry('800x600')
                    preview_dialog.transient(self)
                    preview_dialog.grab_set()
                    
                    # Center preview dialog
                    preview_dialog.update_idletasks()
                    try:
                        parent_x = self.winfo_rootx()
                        parent_y = self.winfo_rooty()
                        parent_w = self.winfo_width() or preview_dialog.winfo_screenwidth()
                        parent_h = self.winfo_height() or preview_dialog.winfo_screenheight()
                    except Exception:
                        parent_x = parent_y = 0
                        parent_w = preview_dialog.winfo_screenwidth()
                        parent_h = preview_dialog.winfo_screenheight()
                    dlg_w = preview_dialog.winfo_width()
                    dlg_h = preview_dialog.winfo_height()
                    pos_x = parent_x + (parent_w - dlg_w) // 2
                    pos_y = parent_y + (parent_h - dlg_h) // 2
                    preview_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
                    
                    preview_frame = ttk.Frame(preview_dialog, padding=15)
                    preview_frame.pack(fill=tk.BOTH, expand=True)
                    
                    ttk.Label(preview_frame, text='Preview Improved Lyrics:', font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W, pady=(0, 10))
                    
                    preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=('TkDefaultFont', 10))
                    preview_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                    preview_text.insert('1.0', improved_lyrics)
                    preview_text.config(state=tk.DISABLED)
                    
                    accept_result = [False]
                    
                    def accept_lyrics():
                        accept_result[0] = True
                        preview_dialog.destroy()
                    
                    def cancel_lyrics():
                        preview_dialog.destroy()
                    
                    btn_frame = ttk.Frame(preview_frame)
                    btn_frame.pack(fill=tk.X)
                    ttk.Button(btn_frame, text='Accept & Replace Lyrics', command=accept_lyrics).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text='Cancel', command=cancel_lyrics).pack(side=tk.LEFT, padx=5)
                    
                    self.wait_window(preview_dialog)
                    
                    if accept_result[0]:
                        self.lyrics_text.delete('1.0', tk.END)
                        self.lyrics_text.insert('1.0', improved_lyrics)
                        self.log_debug('INFO', f'Lyrics {operation} completed successfully')
                        messagebox.showinfo('Success', f'Lyrics {operation} completed successfully!')
                    else:
                        self.log_debug('INFO', f'Lyrics {operation} cancelled by user')
                else:
                    messagebox.showerror('Error', f'Failed to process lyrics: {result_ai.get("error", "Unknown error")}')
                    self.log_debug('ERROR', f'Failed to process lyrics: {result_ai.get("error", "Unknown error")}')
            
            except Exception as e:
                messagebox.showerror('Error', f'Error processing lyrics: {e}')
                self.log_debug('ERROR', f'Error processing lyrics: {e}')
            finally:
                self.config(cursor='')
        
        def cancel_dialog():
            dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text='Process', command=process_lyrics).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=cancel_dialog).pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Escape>', lambda e: cancel_dialog())

    def copy_distro_lyrics(self):
        """Format lyrics for distribution platforms and copy to clipboard."""
        lyrics = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        if not lyrics:
            messagebox.showwarning('Warning', 'No lyrics found. Please add lyrics first.')
            return
        
        self.log_debug('INFO', 'Formatting lyrics for distribution...')
        self.config(cursor='wait')
        self.update()
        
        try:
            prompt = f"""Format the following song lyrics for distribution platforms like DistroKid.

RAW LYRICS:
{lyrics}

INSTRUCTIONS:
1. Remove section labels like [Intro], [Verse 1], [Chorus], [Bridge], [Outro], etc.
2. Remove stage directions, annotations, and metadata
3. Capitalize the first letter of each line using standard sentence capitalization
4. Remove punctuation at the end of lines (periods, commas, etc.)
5. If a line is intentionally shouted (all caps), normalize it to standard capitalization
6. Write out repeated sections fully - do not use shorthand like "chorus x2"
7. Remove blank lines except for single blank lines between logical sections (verses, hooks, bridges)
8. Keep one sentence or phrase per line - split very long lines if needed
9. Remove filler words like "yeah", "oh", "uh" unless they are clearly part of the sung lyrics
10. Convert stylized separators (dashes, em dashes) into plain words or spacing
11. Preserve the lyrical meaning, tone, and structure
12. Do not censor explicit language unless it was bleeped in the original
13. Preserve intentional line breaks that affect the flow

OUTPUT:
Return ONLY the formatted lyrics text. Do not include any explanations, error messages, or commentary. If the lyrics cannot be formatted, return them as-is with minimal formatting applied."""
            
            system_message = "You are a lyrics formatting assistant. Format the provided lyrics according to the instructions and return only the formatted lyrics text. Do not include error messages, explanations, or validation comments - just return the formatted lyrics."
            
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=8000, temperature=0.3)
            
            if result['success']:
                formatted_lyrics = result['content'].strip()
                if not formatted_lyrics:
                    messagebox.showerror('Error', 'AI did not return formatted lyrics.')
                    self.log_debug('ERROR', 'AI did not return formatted lyrics')
                    return
                
                # Copy to clipboard
                self.clipboard_clear()
                self.clipboard_append(formatted_lyrics)
                self.update()
                
                self.log_debug('INFO', 'Formatted lyrics copied to clipboard')
                messagebox.showinfo('Success', 'Distribution-ready lyrics have been copied to clipboard.')
            else:
                messagebox.showerror('Error', f'Failed to format lyrics: {result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to format lyrics: {result.get("error", "Unknown error")}')
                
        except Exception as e:
            messagebox.showerror('Error', f'Error formatting lyrics: {e}')
            self.log_debug('ERROR', f'Error formatting lyrics: {e}')
        finally:
            self.config(cursor='')

    def generate_song_description(self):
        """Generate a structured English song blurb for Facebook."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip() or song_name
        persona_name = self.current_persona.get('name', '')
        style = self._get_sanitized_style_text()
        lyric_ideas = self.lyric_ideas_text.get('1.0', tk.END).strip()
        lyrics = self.lyrics_text.get('1.0', tk.END).strip()
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        prompt = (
            f"Create a short, structured Facebook post for the song '{full_song_name}' "
            f"by the AI persona '{persona_name}'. "
            "Keep it human, vivid, and promotional. Avoid hashtags, emojis, bullet symbols, and quotes. "
            "Use 3-5 labeled lines, each 1-2 sentences max, like:"
            " Story: <what the song is about>"
            " Persona: <who the persona is / their role or backstory>"
            " Sound: <core sound styles, instruments, vibe>"
            " (optional) Spark: <what inspired the prompt or mood>"
            "Place each labeled line on its own line and insert a blank line between sections for readability."
        )
        if style:
            prompt += f"\nSound style hints: {style}"
        if lyric_ideas:
            prompt += f"\nLyric ideas or themes: {lyric_ideas[:400]}"
        if lyrics:
            prompt += f"\nUse the mood of these lyrics (optional, do not quote): {lyrics[:600]}"
        prompt += (
            "\nLength cap: about 650 characters total. Return only the 3-5 labeled lines."
            " Keep style words in English. Preserve the blank lines between sections."
        )
        
        self.log_debug('INFO', 'Generating song description...')
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, profile='text')
            if result['success']:
                desc_raw = result['content'].strip()
                desc = self._sanitize_style_keywords(desc_raw)
                desc = self._format_structured_description(desc, lang='en')
                if len(desc) > 700:
                    desc = desc[:700].rstrip()
                links_block = self._format_distribution_links_block()
                if links_block:
                    desc = f"{desc}\n\n{links_block}"
                tools_block = self._get_tools_footer()
                if tools_block:
                    desc = f"{desc}\n\n{tools_block}"
                self.song_description_text.delete('1.0', tk.END)
                self.song_description_text.insert('1.0', desc)
                self.log_debug('INFO', f'Song description generated ({len(desc)} chars including links)')
            else:
                messagebox.showerror('Error', f'Failed to generate song description: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate song description: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating song description: {e}')
            self.log_debug('ERROR', f'Error generating song description: {e}')
        finally:
            self.config(cursor='')

    def generate_song_description_de(self):
        """Generate a structured German song blurb for Facebook."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip() or song_name
        persona_name = self.current_persona.get('name', '')
        style = self._get_sanitized_style_text()
        lyric_ideas = self.lyric_ideas_text.get('1.0', tk.END).strip()
        lyrics = self.lyrics_text.get('1.0', tk.END).strip()
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        prompt = (
            f"Erstelle einen strukturierten deutschen Facebook-Text fuer den Song '{full_song_name}' "
            f"von der KI-Persona '{persona_name}'. "
            "Kein Marketing-Sprech, aber lebendig und verstaendlich. Keine Hashtags, Emojis oder Aufzaehlungs-Bullets. "
            "Nutze 3-5 kurze Zeilen mit Labels, je Zeile 1-2 Saetze, z. B.: "
            " Story: <kurz worum es geht> "
            " Persona: <wer die Persona ist, Rolle/Backstory> "
            " Sound: <wichtigste Sound-Styles, Instrumente, Vibe> "
            " (optional) Idee: <was den Prompt oder die Stimmung inspiriert hat> "
            "Stil/Vibe-Begriffe koennen englisch bleiben. "
            "Jede beschriftete Zeile steht einzeln und wird durch eine Leerzeile getrennt, damit es wie kurze Abschnitte wirkt."
        )
        if style:
            prompt += f"\nStil/Vibe: {style}"
        if lyric_ideas:
            prompt += f"\nIdeen oder Themen: {lyric_ideas[:400]}"
        if lyrics:
            prompt += f"\nStimmung aus diesen Lyrics (optional, nicht zitieren): {lyrics[:600]}"
        prompt += (
            "\nZeichenlimit: etwa 650 Zeichen gesamt. "
            "Liefere nur die 3-5 beschrifteten Zeilen, sonst nichts. "
            "Blanko-Zeilen zwischen den Abschnitten beibehalten."
        )
        
        self.log_debug('INFO', 'Generating German song description...')
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, profile='text')
            if result['success']:
                desc_raw = result['content'].strip()
                desc = self._sanitize_style_keywords(desc_raw)
                desc = self._format_structured_description(desc, lang='de')
                if len(desc) > 750:
                    desc = desc[:750].rstrip()
                links_block = self._format_distribution_links_block(lang='de')
                if links_block:
                    desc = f"{desc}\n\n{links_block}"
                self.song_description_de_text.delete('1.0', tk.END)
                self.song_description_de_text.insert('1.0', desc)
                self.log_debug('INFO', f'German song description generated ({len(desc)} chars including links)')
            else:
                messagebox.showerror('Error', f'Failed to generate German song description: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate German song description: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating German song description: {e}')
            self.log_debug('ERROR', f'Error generating German song description: {e}')
        finally:
            self.config(cursor='')

    def open_style_selector(self, auto_merge: bool = False):
        """Open the style picker popup and optionally auto-merge after selection."""
        csv_path = get_styles_csv_path(self.ai_config)
        styles = load_styles_from_csv(csv_path)
        if not styles:
            messagebox.showerror('Error', f'Styles CSV not found or empty:\n{csv_path}')
            self.log_debug('ERROR', f'Styles CSV missing or empty: {csv_path}')
            return []

        current_text = self.song_style_text.get('1.0', tk.END).strip()
        dialog = StyleSelectionDialog(self, styles, initial_text=current_text)
        self.wait_window(dialog)

        if dialog.selected_style is None:
            return []

        selected_name = dialog.selected_style
        selected_row = next((r for r in styles if (r.get('style', '').strip() == selected_name)), None)
        keywords = ''
        if selected_row:
            keywords = (selected_row.get('prompt') or '').strip()
            if not keywords:
                keywords = (selected_row.get('style') or '').strip()
        if not keywords:
            keywords = selected_name
        sanitized_keywords = self._sanitize_style_keywords(keywords)
        if sanitized_keywords != keywords:
            self.log_debug('INFO', 'Removed band names from selected style keywords')
        keywords = sanitized_keywords

        # Replace song style with the selected style keywords
        self.song_style_text.delete('1.0', tk.END)
        self.song_style_text.insert('1.0', keywords)
        self.log_debug('INFO', f'Selected style applied: {selected_name}')

        if auto_merge:
            self.merge_song_style()

        return [selected_name]

    def import_song_style_from_analysis_dialog(self):
        """Import Song Style from SongStyleAnalyzer JSON in data/."""
        entries = None
        json_path = ''

        # Reuse last loaded analysis without re-opening file picker
        cache = getattr(self, '_analysis_import_cache', None)
        if isinstance(cache, dict):
            cached_path = str(cache.get('path', '') or '')
            cached_entries = cache.get('entries')
            if cached_path and isinstance(cached_entries, list) and os.path.exists(cached_path):
                reuse = messagebox.askyesno(
                    'Reuse last analysis?',
                    f'Reuse the last loaded analysis file?\n\n{cached_path}\n\n(Choose No to load a different file.)'
                )
                if reuse:
                    json_path = cached_path
                    entries = cached_entries

        if entries is None:
            data_dir = resolve_analysis_data_path(self.ai_config)
            initial_dir = data_dir if os.path.isdir(data_dir) else os.getcwd()
            json_path = filedialog.askopenfilename(
                title='Select analysis JSON file (SongStyleAnalyzer output)',
                initialdir=initial_dir,
                filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')]
            )
            if not json_path:
                return
            entries = _load_song_style_analyzer_entries_from_file(json_path)

        if not entries:
            messagebox.showwarning('Warning', f'No valid SongStyleAnalyzer entries found in:\n{json_path}')
            return

        # Cache for next time (in-memory only)
        try:
            self._analysis_import_cache = {'path': json_path, 'entries': entries}
        except Exception:
            pass

        dialog = tk.Toplevel(self)
        dialog.title('Import Song Style from Analysis')
        dialog.geometry('820x520')
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        top = ttk.Frame(dialog, padding=10)
        top.pack(fill=tk.BOTH, expand=True)

        ttk.Label(top, text='Select entry:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top, textvariable=filter_var)
        filter_entry.pack(fill=tk.X, pady=(6, 4))
        status_var = tk.StringVar(value='')
        ttk.Label(top, textvariable=status_var, foreground='gray').pack(anchor=tk.W, pady=(0, 8))

        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True)
        lb = tk.Listbox(list_frame, exportselection=False)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _entry_search_blob(entry: dict) -> str:
            parts = []
            parts.append(_analysis_entry_display_name(entry))
            parts.append(_analysis_entry_suno_style_prompt(entry))
            style_analysis = entry.get('style_analysis', {}) or {}
            parts.append(str(style_analysis.get('prompt_string', '') or ''))
            taxonomy = (style_analysis.get('taxonomy', {}) or {})
            parts.append(str(taxonomy.get('primary_genre', '') or ''))
            parts.append(str(taxonomy.get('sub_genre', '') or ''))
            parts.append(str(taxonomy.get('mood', '') or ''))
            tags = taxonomy.get('fusion_tags', []) or []
            if isinstance(tags, list):
                parts.append(' '.join([str(t).strip() for t in tags if str(t).strip()]))
            instr = taxonomy.get('instrumentation', []) or []
            if isinstance(instr, list):
                parts.append(' '.join([str(i).strip() for i in instr if str(i).strip()]))
            usage = entry.get('agent_usage_suggestions', {}) or {}
            parts.append(str(usage.get('negative_prompt', '') or ''))
            return ' '.join([p for p in parts if p]).lower()

        display = []
        for e in entries:
            name = _analysis_entry_display_name(e)
            display.append({'name': name, 'entry': e, 'blob': _entry_search_blob(e)})
        display.sort(key=lambda x: x['name'].lower())
        filtered = {'items': display}

        def repopulate():
            raw = filter_var.get().strip().lower()
            # Split by whitespace and commas; require all terms to match (AND)
            terms = [t for t in re.split(r'[\s,]+', raw) if t]
            lb.delete(0, tk.END)
            items = display
            if terms:
                items = []
                for it in display:
                    blob = it.get('blob', '')
                    if all((t in blob) for t in terms):
                        items.append(it)
            filtered['items'] = items
            for it in items:
                lb.insert(tk.END, it.get('name', ''))
            status_var.set(f'Matches: {len(items)}/{len(display)}')

        repopulate()
        filter_entry.bind('<KeyRelease>', lambda _e: repopulate())

        def do_load():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning('Warning', 'Please select an entry.')
                return
            idx = sel[0]
            items = filtered['items']
            if idx < 0 or idx >= len(items):
                return
            name = items[idx].get('name', '')
            entry = items[idx].get('entry', {})
            style_text = _analysis_entry_suno_style_prompt(entry)
            style_text = (style_text or '').strip()
            if not style_text:
                messagebox.showwarning('Warning', f'No style text found for: {name}')
                return

            style_text = self._sanitize_style_keywords(style_text)
            self.song_style_text.delete('1.0', tk.END)
            self.song_style_text.insert('1.0', style_text)
            
            # Import negative_prompt into exclude_style field if available
            if hasattr(self, 'exclude_style_text'):
                usage = entry.get('agent_usage_suggestions', {}) or {}
                negative_prompt = str(usage.get('negative_prompt', '') or '').strip()
                if negative_prompt:
                    self.exclude_style_text.delete('1.0', tk.END)
                    self.exclude_style_text.insert('1.0', negative_prompt)
                    self.log_debug('INFO', f'Imported negative prompt as exclude style: {negative_prompt[:50]}...')
            
            self.log_debug('INFO', f'Imported analysis song style: {name}')
            dialog.destroy()

        btns = ttk.Frame(top)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text='Import', command=do_load).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns, text='Cancel', command=dialog.destroy).pack(side=tk.LEFT)

        lb.bind('<Double-Button-1>', lambda _e: do_load())
        dialog.bind('<Return>', lambda _e: do_load())
        dialog.bind('<Escape>', lambda _e: dialog.destroy())
        filter_entry.focus_set()

    def load_styles_from_file_dialog(self):
        """Load styles from a CSV or CSS file in the configured styles import path (e.g. D:\\AI\\suno), filtered by base name."""
        import_dir = resolve_styles_import_path(self.ai_config)
        base_name = get_styles_import_base_name(self.ai_config)
        if not os.path.isdir(import_dir):
            import_dir = os.getcwd()

        dialog = tk.Toplevel(self)
        dialog.title('Load Styles from File')
        dialog.geometry('560x420')
        dialog.transient(self)
        dialog.grab_set()

        main = ttk.Frame(dialog, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text='Folder:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        folder_var = tk.StringVar(value=import_dir)
        folder_entry = ttk.Entry(main, textvariable=folder_var, width=60)
        folder_entry.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(main, text='Base name (files starting with; leave empty for all):', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(10, 2))
        base_var = tk.StringVar(value=base_name)
        base_entry = ttk.Entry(main, textvariable=base_var, width=40)
        base_entry.pack(fill=tk.X, pady=(2, 4))

        list_frame = ttk.Frame(main)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 4))
        file_listbox = tk.Listbox(list_frame, exportselection=False, height=12)
        file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=file_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        file_listbox.configure(yscrollcommand=sb.set)

        status_var = tk.StringVar(value='')
        ttk.Label(main, textvariable=status_var, foreground='gray').pack(anchor=tk.W, pady=(2, 0))

        def refresh_list():
            folder = folder_var.get().strip()
            prefix = base_var.get().strip().lower()
            file_listbox.delete(0, tk.END)
            if not folder or not os.path.isdir(folder):
                status_var.set('Folder not found.')
                return
            candidates = []
            for name in sorted(os.listdir(folder)):
                low = name.lower()
                if not (low.endswith('.csv') or low.endswith('.css')):
                    continue
                if prefix and not low.startswith(prefix):
                    continue
                candidates.append(name)
            for name in candidates:
                file_listbox.insert(tk.END, name)
            status_var.set(f'{len(candidates)} file(s) (.csv / .css)')

        refresh_list()
        base_var.trace_add('write', lambda *_: refresh_list())
        folder_var.trace_add('write', lambda *_: refresh_list())

        def browse_folder():
            path = filedialog.askdirectory(title='Select folder (e.g. D:\\AI\\suno)', initialdir=folder_var.get() or os.getcwd())
            if path:
                folder_var.set(path)

        def do_open():
            sel = file_listbox.curselection()
            if not sel:
                messagebox.showwarning('Warning', 'Select a file.')
                return
            idx = sel[0]
            name = file_listbox.get(idx)
            folder = folder_var.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showerror('Error', 'Invalid folder.')
                return
            file_path = os.path.join(folder, name)
            styles = load_styles_from_file(file_path)
            dialog.destroy()
            if not styles:
                messagebox.showwarning('Warning', f'No styles found in:\n{file_path}')
                return
            current_text = self.song_style_text.get('1.0', tk.END).strip()
            style_dialog = StyleSelectionDialog(self, styles, initial_text=current_text)
            self.wait_window(style_dialog)
            if style_dialog.selected_style is None:
                return
            selected_name = style_dialog.selected_style
            selected_row = next((r for r in styles if (r.get('style', '').strip() == selected_name)), None)
            keywords = ''
            if selected_row:
                keywords = (selected_row.get('prompt') or '').strip()
                if not keywords:
                    keywords = (selected_row.get('style') or '').strip()
            if not keywords:
                keywords = selected_name
            sanitized = self._sanitize_style_keywords(keywords)
            self.song_style_text.delete('1.0', tk.END)
            self.song_style_text.insert('1.0', sanitized)
            self.log_debug('INFO', f'Loaded style from file: {selected_name}')

        btn_row = ttk.Frame(main)
        btn_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_row, text='Browse...', command=browse_folder).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text='Open', command=do_open).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text='Cancel', command=dialog.destroy).pack(side=tk.LEFT)

        file_listbox.bind('<Double-Button-1>', lambda _e: do_open())
        dialog.bind('<Return>', lambda _e: do_open())
        dialog.bind('<Escape>', lambda _e: dialog.destroy())

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')

    def auto_import_song_style_from_analysis_if_needed(self):
        """Auto-fill Song Style from analysis data if enabled and empty."""
        try:
            enabled = bool((self.ai_config.get('general', {}) or {}).get('auto_import_song_style_from_analysis', True))
        except Exception:
            enabled = True
        if not enabled:
            return
        if not hasattr(self, 'song_style_text'):
            return
        current_style = self.song_style_text.get('1.0', tk.END).strip()
        if current_style:
            return

        song_name = ''
        try:
            song_name = self.song_name_var.get().strip()
        except Exception:
            song_name = ''
        if not song_name:
            return

        data_dir = resolve_analysis_data_path(self.ai_config)
        entries = _load_song_style_analyzer_entries_from_dir(data_dir)
        if not entries:
            return

        best = _find_best_analysis_entry(song_name=song_name, artist='', entries=entries)
        if not best:
            return

        style_text = _analysis_entry_suno_style_prompt(best)
        style_text = (style_text or '').strip()
        if not style_text:
            return

        style_text = self._sanitize_style_keywords(style_text)
        self.song_style_text.delete('1.0', tk.END)
        self.song_style_text.insert('1.0', style_text)
        self.log_debug('INFO', f'Auto-imported analysis song style: { _analysis_entry_display_name(best) }')

    def _prompt_merge_style_weights(self):
        """Ask user how to weight song vs persona style during merging."""
        dialog = tk.Toplevel(self)
        dialog.title('Merge Style Weights')
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(dialog, text='Set how much each style should influence the merge:').pack(padx=12, pady=(10, 6))

        song_var = tk.IntVar(value=getattr(self, 'merge_song_weight', 50))
        song_label = ttk.Label(dialog, text=f'Song Style: {song_var.get()}%')
        song_label.pack(padx=12)
        persona_label = ttk.Label(dialog, text=f'Persona Style: {100 - song_var.get()}%')
        persona_label.pack(padx=12, pady=(0, 6))

        def update_labels(value=None):
            val = int(float(value)) if value is not None else song_var.get()
            val = max(0, min(100, val))
            song_var.set(val)
            song_label.config(text=f'Song Style: {val}%')
            persona_label.config(text=f'Persona Style: {100 - val}%')

        scale = ttk.Scale(dialog, from_=0, to=100, orient=tk.HORIZONTAL, variable=song_var, command=update_labels)
        scale.pack(fill=tk.X, padx=12, pady=(0, 10))
        update_labels()

        result = {'value': None}

        def on_ok():
            result['value'] = max(0, min(100, int(song_var.get())))
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(btn_frame, text='OK', command=on_ok).pack(side=tk.LEFT, expand=True, padx=6)
        ttk.Button(btn_frame, text='Cancel', command=on_cancel).pack(side=tk.RIGHT, expand=True, padx=6)

        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        dialog.wait_window()

        if result['value'] is None:
            return None

        self.merge_song_weight = result['value']
        return result['value'], 100 - result['value']

    def merge_song_style(self):
        """Merge song style with persona voice style."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        raw_song_style = self.song_style_text.get('1.0', tk.END).strip()
        song_style = self._sanitize_style_keywords(raw_song_style)
        if song_style != raw_song_style:
            self.song_style_text.delete('1.0', tk.END)
            self.song_style_text.insert('1.0', song_style)
            self.log_debug('INFO', 'Removed band names from song style before merging')
        voice_style = self.current_persona.get('voice_style', '')
        genre_tags = self.current_persona.get('genre_tags', '')
        
        if not song_style:
            messagebox.showwarning('Warning', 'Please enter a song style.')
            return
        
        if not voice_style:
            messagebox.showwarning('Warning', 'Persona voice style is not set.')
            return

        weights = self._prompt_merge_style_weights()
        if weights is None:
            self.log_debug('INFO', 'Merge cancelled: weights dialog closed')
            return
        song_weight, persona_weight = weights

        persona_style_context = voice_style
        if genre_tags:
            persona_style_context = f"{voice_style}\nGenre Tags: {genre_tags}"

        # Create explicit weighting instructions that emphasize the percentages
        if song_weight >= 70:
            weighting_emphasis = "CRITICAL: The Song Style should DOMINATE the merged result. Use {song_weight}% of elements, characteristics, and details from the Song Style, and only {persona_weight}% from the Persona Voice Style."
        elif song_weight <= 30:
            weighting_emphasis = "CRITICAL: The Persona Voice Style should DOMINATE the merged result. Use {persona_weight}% of elements, characteristics, and details from the Persona Voice Style, and only {song_weight}% from the Song Style."
        else:
            weighting_emphasis = "CRITICAL: Balance the styles according to these EXACT percentages: {song_weight}% Song Style influence and {persona_weight}% Persona Voice Style influence. The merged style must reflect this precise weighting."

        weighting_text = (
            "\n\n=== WEIGHTING REQUIREMENTS (MUST BE FOLLOWED EXACTLY) ===\n"
            f"Song Style Weight: {song_weight}%\n"
            f"Persona Voice Style Weight: {persona_weight}%\n\n"
            f"{weighting_emphasis.format(song_weight=song_weight, persona_weight=persona_weight)}\n\n"
            "When creating the merged style:\n"
            f"- If Song Style is {song_weight}%, prioritize {song_weight}% of musical elements, instrumentation, tempo, rhythm, and genre characteristics from the Song Style\n"
            f"- If Persona Voice Style is {persona_weight}%, incorporate {persona_weight}% of vocal characteristics, delivery style, emotional tone, and persona-specific elements\n"
            "- The percentages indicate the PROPORTIONAL INFLUENCE each style should have in the final merged description\n"
            "- Ensure the merged style description clearly reflects this {song_weight}/{persona_weight} balance\n"
            "=== END WEIGHTING REQUIREMENTS ===\n"
        )

        # Add instructions to MIX detailed phrases and keywords from song style with persona style
        phrase_mixing_text = (
            "\n\n=== PHRASE AND KEYWORD MIXING (CRITICAL) ===\n"
            "The Song Style contains detailed phrases and keyphrases that describe specific musical characteristics.\n"
            "These MUST be MIXED and BLENDED with the Persona Voice Style according to the weighting percentages:\n\n"
            f"- Take the longer keyphrases from the Song Style (e.g., 'A hard rock track with a driving tempo of approximately 120 BPM', 'distorted electric guitar playing a prominent riff', 'raw powerful delivery with a slightly raspy timbre')\n"
            f"- MIX these keyphrases with the Persona Voice Style elements according to the {song_weight}%/{persona_weight}% weighting\n"
            f"- For each keyphrase from the Song Style, blend it with corresponding Persona Voice Style elements\n"
            f"- If Song Style is {song_weight}%, that percentage of the keyphrases and their characteristics should be prominent in the mix\n"
            f"- If Persona Voice Style is {persona_weight}%, that percentage of vocal characteristics and persona elements should be integrated into the keyphrases\n"
            f"- Do NOT just list them separately - actively MIX and BLEND them together\n"
            f"- For example, if Song Style says 'raw powerful delivery' and Persona Style has specific vocal characteristics, blend them: incorporate {song_weight}% of the 'raw powerful delivery' concept with {persona_weight}% of the persona's vocal style\n"
            f"- The technical details (tempo, BPM, instrumentation) from Song Style should be mixed with persona elements according to the weighting\n"
            f"- The structural descriptions (verse/chorus, instrumental breaks) should be blended with persona's style characteristics\n"
            f"- The production characteristics should reflect the {song_weight}%/{persona_weight}% mix of both styles\n"
            f"- Create a unified, blended description where Song Style keyphrases are integrated with Persona Voice Style, not just appended\n"
            "=== END PHRASE MIXING ===\n"
        )

        template = get_prompt_template('merge_styles', self.ai_config)
        if template:
            # Override template's default prioritization with weighted approach
            # Let the AI decide how to mix based on the percentages
            prompt = (
                weighting_text + phrase_mixing_text + "\n\n" +
                "You are a music style expert. Your task is to merge music styles into a cohesive, unique style description optimized for music generation.\n\n" +
                f"Song Style ({song_weight}% weight):\n{song_style}\n\n" +
                f"Persona Voice Style ({persona_weight}% weight):\n{voice_style}\n" +
                (f"\nGenre Tags: {genre_tags}\n" if genre_tags else "") +
                "\nYour task is to MIX and BLEND these two styles according to the EXACT percentage weighting specified above.\n" +
                f"The merged style should reflect {song_weight}% influence from the Song Style and {persona_weight}% influence from the Persona Voice Style.\n" +
                "CRITICAL: Do not just combine them - actively MIX the longer keyphrases from the Song Style with the Persona Voice Style elements.\n" +
                "For each detailed phrase in the Song Style, blend it with corresponding Persona Voice Style characteristics according to the weighting.\n\n" +
                "Create a merged style description that:\n" +
                f"1. MIXES the longer keyphrases from Song Style with Persona Voice Style elements according to {song_weight}%/{persona_weight}% weighting\n" +
                "2. Blends technical details, instrumentation, and structural elements from Song Style with persona vocal characteristics\n" +
                "3. Results in a unified, integrated description where both styles are actively mixed, not just listed\n" +
                "4. The proportion of mixed elements from each style should match the weighting percentages\n" +
                "5. Each keyphrase should reflect the blend of both styles according to the percentages\n\n" +
                "OUTPUT REQUIREMENTS:\n" +
                "- Output ONLY the merged style description\n" +
                "- Include ONLY words, phrases, and descriptions that are relevant to the merged song style\n" +
                "- Do NOT include any explanations, labels, or meta-commentary\n" +
                "- Do NOT include phrases like 'This style...' or 'The merged style...'\n" +
                "- Output ONLY the actual style description itself - nothing else\n" +
                "- Be concise and include only relevant musical/style elements"
            )
            self.log_debug('INFO', f'Merging styles with weighted template (weights: {song_weight}% song, {persona_weight}% persona)')
        else:
            prompt = (
                weighting_text + phrase_mixing_text + "\n\n"
                "Merge the following styles according to the weighting and mixing requirements above:\n\n"
                f"Song Style ({song_weight}% weight):\n{song_style}\n\n"
                f"Persona Voice Style ({persona_weight}% weight):\n{voice_style}\n"
                f"{'Genre Tags: ' + genre_tags if genre_tags else ''}\n\n"
                "Your task is to MIX and BLEND these two styles according to the EXACT percentage weighting specified above.\n" +
                f"The merged style should reflect {song_weight}% influence from the Song Style and {persona_weight}% influence from the Persona Voice Style.\n" +
                "CRITICAL: Do not just combine them - actively MIX the longer keyphrases from the Song Style with the Persona Voice Style elements.\n" +
                "For each detailed phrase in the Song Style, blend it with corresponding Persona Voice Style characteristics according to the weighting.\n\n" +
                "Create a merged style description that:\n"
                f"1. MIXES the longer keyphrases from Song Style with Persona Voice Style elements according to {song_weight}%/{persona_weight}% weighting\n"
                "2. Blends technical details, instrumentation, tempo, and structural elements from Song Style with persona vocal characteristics\n"
                "3. Preserves and incorporates ALL detailed phrases, keywords, and technical descriptions from both styles\n"
                "4. Results in a unified, integrated description where both styles are actively mixed, not just listed\n"
                "5. The proportion of mixed elements from each style should match the weighting percentages\n"
                "6. Each keyphrase should reflect the blend of both styles according to the percentages\n\n"
                "OUTPUT REQUIREMENTS:\n" +
                "- Output ONLY the merged style description\n" +
                "- Include ONLY words, phrases, and descriptions that are relevant to the merged song style\n" +
                "- Do NOT include any explanations, labels, or meta-commentary\n" +
                "- Do NOT include phrases like 'This style...' or 'The merged style...'\n" +
                "- Output ONLY the actual style description itself - nothing else\n" +
                "- Be concise and include only relevant musical/style elements"
            )
            self.log_debug('INFO', f'Merging styles with fallback prompt (weights: {song_weight}% song, {persona_weight}% persona)')
        
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_ai(prompt, profile='text')
            
            if result['success']:
                merged_raw = result['content'].strip()
                merged = self._sanitize_style_keywords(merged_raw)
                self.merged_style_text.delete('1.0', tk.END)
                self.merged_style_text.insert('1.0', merged)
                self.log_debug('INFO', 'Styles merged successfully')
            else:
                messagebox.showerror('Error', f'Failed to merge styles: {result["error"]}')
                self.log_debug('ERROR', f'Failed to merge styles: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error merging styles: {e}')
            self.log_debug('ERROR', f'Error merging styles: {e}')
        finally:
            self.config(cursor='')

    def improve_merged_style(self):
        """Improve/modify merged style keywords based on user instructions."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        current_style = self.merged_style_text.get('1.0', tk.END).strip()
        if not current_style:
            messagebox.showwarning('Warning', 'Please merge styles first or enter merged style text.')
            return
        
        # Ask user for transformation instructions
        instruction = simpledialog.askstring(
            'Improve Merged Style',
            'How would you like to modify the keywords?\n(e.g., "change hardrock to metal", "make it more aggressive", "add electronic elements"):',
            initialvalue=''
        )
        
        if not instruction:
            self.log_debug('INFO', 'Improve merged style cancelled: no instruction provided')
            return
        
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip() or song_name
        persona_name = self.current_persona.get('name', '')
        
        prompt = (
            "Modify the following merged style description according to the user's instructions.\n"
            "CRITICAL: Preserve the overall structure and flow of the style description.\n"
            "Apply the requested changes while maintaining coherence and musical accuracy.\n"
            "Keep it concise and focused on musical/style elements.\n"
            "Avoid brand names and band/artist names. No bullet points. Return only the modified style text.\n\n"
            f"Song: {full_song_name if full_song_name else song_name}\n"
            f"Persona: {persona_name}\n\n"
            f"User's modification instruction: {instruction}\n\n"
            f"Current Merged Style:\n{current_style}\n\n"
            "Apply the modification and return ONLY the improved/modified style description."
        )
        
        self.log_debug('INFO', f'Improving merged style with instruction: {instruction}')
        self.config(cursor='wait')
        self.update()
        try:
            result = self.azure_ai(prompt, profile='text')
            if result.get('success'):
                improved_raw = result.get('content', '').strip()
                improved = self._sanitize_style_keywords(improved_raw)
                self.merged_style_text.delete('1.0', tk.END)
                self.merged_style_text.insert('1.0', improved)
                self.log_debug('INFO', 'Merged style improved with AI')
            else:
                messagebox.showerror('Error', f'Failed to improve merged style: {result.get("error")}')
                self.log_debug('ERROR', f'Failed to improve merged style: {result.get("error")}')
        except Exception as exc:
            messagebox.showerror('Error', f'Error improving merged style: {exc}')
            self.log_debug('ERROR', f'Error improving merged style: {exc}')
        finally:
            self.config(cursor='')

    def set_storyboard_theme_from_merged_style(self):
        """Copy merged style (or song style) into the storyboard theme field."""
        theme_text = self.merged_style_text.get('1.0', tk.END).strip()
        if not theme_text:
            theme_text = self.song_style_text.get('1.0', tk.END).strip()
        if hasattr(self, 'storyboard_theme_text'):
            self.storyboard_theme_text.delete('1.0', tk.END)
            if theme_text:
                self.storyboard_theme_text.insert('1.0', theme_text)
        if theme_text:
            self.log_debug('INFO', 'Storyboard theme updated from merged style')
    
    def improve_storyboard_theme(self):
        """AI-expand the storyboard theme from seed keywords into a concise global style."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        seed_theme = self.storyboard_theme_text.get('1.0', tk.END).strip()
        merged_style = self._get_sanitized_style_text()
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip() or song_name
        persona_name = self.current_persona.get('name', '')
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
        base_image_prompt = self.current_persona.get('base_image_prompt', '')
        vibe = self.current_persona.get('vibe', '')
        
        if not seed_theme and not merged_style:
            messagebox.showwarning('Warning', 'Please enter storyboard theme keywords or set a merged style first.')
            return
        
        # Get existing storyboard scenes if available
        existing_storyboard = None
        if hasattr(self, 'storyboard_tree') and self.storyboard_tree.get_children():
            existing_storyboard = self.get_storyboard_data()
        elif self.current_song and self.current_song.get('storyboard'):
            existing_storyboard = self.current_song.get('storyboard')
        
        # Build storyboard context if scenes exist
        storyboard_context = ""
        if existing_storyboard and len(existing_storyboard) > 0:
            # Include a sample of scenes (first 3-5) to give context without overwhelming the prompt
            sample_scenes = existing_storyboard[:5]
            storyboard_context = "\n\nExisting Storyboard Scenes (for context):\n"
            for scene in sample_scenes:
                scene_num = scene.get('scene', '')
                scene_prompt = scene.get('prompt', '') or scene.get('generated_prompt_image', '') or scene.get('generated_prompt_video', '') or scene.get('generated_prompt', '')
                if scene_prompt:
                    # Truncate long prompts to keep context manageable
                    truncated_prompt = scene_prompt[:200] + "..." if len(scene_prompt) > 200 else scene_prompt
                    storyboard_context += f"Scene {scene_num}: {truncated_prompt}\n"
            if len(existing_storyboard) > 5:
                storyboard_context += f"... and {len(existing_storyboard) - 5} more scenes\n"
            storyboard_context += "\nUse the existing storyboard scenes as reference to improve the theme while maintaining consistency."
        
        prompt = (
            "Improve and expand these storyboard theme keywords into a concise global visual style for all scenes.\n"
            "CRITICAL: Preserve ALL narrative elements, story concepts, characters, and plot points from the seed theme.\n"
            "If the seed mentions specific characters (like 'Devil', 'Drummer'), events (like 'hunting'), or story elements, these MUST remain in the improved theme.\n"
            "Expand the VISUAL description (palette, lighting, camera mood, texture, atmosphere) while keeping the core story/narrative intact.\n"
            "Keep it SFW and under 90 words. Focus on palette, lighting, camera mood, texture, and atmosphere.\n"
            "Avoid brand names and band/artist names. No bullet points. Return only the theme text.\n\n"
            f"Song: {full_song_name if full_song_name else song_name}\n"
            f"Persona: {persona_name}\n"
            f"Merged Style: {merged_style if merged_style else 'N/A'}\n"
            f"Persona Visual Aesthetic: {visual_aesthetic if visual_aesthetic else 'N/A'}\n"
            f"Persona Base Image Prompt: {base_image_prompt if base_image_prompt else 'N/A'}\n"
            f"Persona Vibe: {vibe if vibe else 'N/A'}\n"
            "Seed Theme Keywords (PRESERVE ALL NARRATIVE/STORY ELEMENTS):\n"
            f"{seed_theme if seed_theme else merged_style}"
            f"{storyboard_context}"
        )
        
        self.log_debug('INFO', 'Improving storyboard theme...')
        self.config(cursor='wait')
        self.update()
        try:
            result = self.azure_ai(prompt, profile='text')
            if result.get('success'):
                improved_raw = result.get('content', '').strip()
                improved = self._sanitize_style_keywords(improved_raw)
                if hasattr(self, 'storyboard_theme_text'):
                    self.storyboard_theme_text.delete('1.0', tk.END)
                    self.storyboard_theme_text.insert('1.0', improved)
                self.log_debug('INFO', 'Storyboard theme improved with AI')
            else:
                messagebox.showerror('Error', f'Failed to improve storyboard theme: {result.get("error")}')
                self.log_debug('ERROR', f'Failed to improve storyboard theme: {result.get("error")}')
        except Exception as exc:
            messagebox.showerror('Error', f'Error improving storyboard theme: {exc}')
            self.log_debug('ERROR', f'Error improving storyboard theme: {exc}')
        finally:
            self.config(cursor='')
    
    def generate_album_cover(self):
        """Generate album cover prompt."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return

        dialog = PromptGenerationIdeasDialog(self, 'Album Cover', 'Song')
        self.wait_window(dialog)
        if dialog.result is None:
            return
        user_ideas = (dialog.result or '').strip()

        include_persona = self.include_persona_in_cover_var.get() if hasattr(self, 'include_persona_in_cover_var') else True
        
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip()
        merged_style = self._get_sanitized_style_text()
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '') if include_persona else ''
        preset_key = self._get_song_persona_preset_key()
        base_path = self.get_persona_image_base_path(preset_key)
        storyboard_theme = self.storyboard_theme_text.get('1.0', tk.END).strip() if hasattr(self, 'storyboard_theme_text') else ''
        # Get song lyrics for character and scene inspiration
        song_lyrics = self.lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'lyrics_text') else ''
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        # Check if persona reference images exist (only when including persona)
        reference_images = []
        if include_persona:
            safe_name = self._safe_persona_basename()
            front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
            side_image_path = os.path.join(base_path, f'{safe_name}-Side.png')
            back_image_path = os.path.join(base_path, f'{safe_name}-Back.png')
            if os.path.exists(front_image_path):
                reference_images.append(front_image_path)
            if os.path.exists(side_image_path):
                reference_images.append(side_image_path)
            if os.path.exists(back_image_path):
                reference_images.append(back_image_path)
        
        # Get full persona visual description (only when including persona)
        base_image_prompt = self.current_persona.get('base_image_prompt', '') if include_persona else ''
        vibe = self.current_persona.get('vibe', '') if include_persona else ''
        
        # Build base prompt
        artist_name = self.current_persona.get('name', '')
        if include_persona:
            prompt = f"Generate an album cover prompt for '{song_name}' by the AI persona '{artist_name}'."
        else:
            prompt = f"Generate an album cover prompt for '{song_name}' (no persona or human figures in the image)."
        # Remove parenthetical content from full_song_name for prompt generation
        clean_full_song_name = self._remove_parenthetical_content(full_song_name) if full_song_name else ''
        prompt += f"\n\nFull Song Name: {clean_full_song_name if clean_full_song_name else full_song_name}"
        
        # Emphasize merged style for coloring and scene - CRITICAL for visual design
        if merged_style:
            prompt += f"\n\n=== MERGED STYLE (CRITICAL FOR COLORING AND SCENE) ==="
            prompt += f"\n{merged_style}"
            prompt += "\n\nIMPORTANT: The merged style MUST heavily influence:"
            prompt += "\n- COLOR PALETTE: Extract color schemes, tones, and mood colors from the merged style"
            prompt += "\n- SCENE SETTING: Use the merged style to determine the environment, atmosphere, and visual setting"
            prompt += "\n- LIGHTING: Apply lighting characteristics described in the merged style"
            prompt += "\n- OVERALL AESTHETIC: The merged style should be the PRIMARY driver for the visual design choices"
            prompt += "\n=== END MERGED STYLE ===\n"
        
        # Emphasize song lyrics for character and scene inspiration
        if song_lyrics:
            prompt += f"\n\n=== SONG LYRICS (CRITICAL FOR CHARACTER AND SCENE) ==="
            prompt += f"\n{song_lyrics}"
            prompt += "\n\nIMPORTANT: The song lyrics MUST heavily influence:"
            if include_persona:
                prompt += "\n- CHARACTER DEPICTION: Use lyrical themes, emotions, and narrative to shape how the persona appears"
            prompt += "\n- SCENE CONTENT: Extract visual elements, settings, and imagery directly from the lyrics"
            prompt += "\n- COLORING: Use colors and moods described or implied in the lyrics"
            prompt += "\n- ATMOSPHERE: The lyrics should inform the overall mood and visual tone of the cover"
            prompt += "\n- SYMBOLISM: Incorporate visual metaphors and symbols from the lyrics into the cover design"
            prompt += "\n=== END SONG LYRICS ===\n"
        
        if storyboard_theme:
            prompt += f"\n\nSTORYBOARD THEME (MANDATORY - primary art direction): {storyboard_theme}"
            prompt += "\nUse this storyboard theme 100% as the core visual aesthetic. All album cover decisions must align with it."
        # Ensure title/artist appear on the cover (artist only when including persona)
        album_title = clean_full_song_name if clean_full_song_name else (full_song_name if full_song_name else song_name)
        if album_title or (artist_name and include_persona):
            prompt += "\n\nMANDATORY TEXT ELEMENTS:"
            if album_title:
                prompt += f"\n- Include the album title \"{album_title}\" as integrated cover typography (no subtitle bars)."
            if artist_name and include_persona:
                prompt += f"\n- Include the artist name \"{artist_name}\" as integrated cover typography."
            prompt += (
                "\n- Render the listed strings visibly on the cover. Title and artist must be readable and distinct."
                "\n- Use cohesive typography that matches the storyboard theme; embed text into the scene (on armor plates, signage, HUD, ground, etc.), not as floating UI overlays."
                "\n- Keep text placement clean and legible while integrated with the environment."
                "\n- Do NOT truncate, abbreviate, or shorten the title or artist name. Render the full strings exactly as provided, verbatim."
                "\n- TEXT LAYOUT RULES: Reserve clear space so the full title and artist fit without clipping. Do not crop or cut off any characters. Adjust composition/scale to keep 100% of the text visible and readable. No ellipsis, no partial words."
            )
            prompt += "\n\nRENDER TEXT ON COVER (verbatim):"
            if album_title:
                prompt += f"\n1) \"{album_title}\""
            if artist_name and include_persona:
                prompt += f"\n2) \"{artist_name}\""
        
        if include_persona:
            # Include full persona visual description
            if visual_aesthetic:
                prompt += f"\n\nPersona Visual Aesthetic: {visual_aesthetic}"
            if base_image_prompt:
                prompt += f"\n\nPersona Base Image Prompt (Character Visual Description): {base_image_prompt}"
            if vibe:
                prompt += f"\n\nPersona Vibe: {vibe}"
            # Force non-centered, scene-driven placement for the persona
            prompt += (
                "\n\nComposition and placement rules:"
                "\n- Embed the persona into the environment; do NOT default to centering them."
                "\n- Place the persona wherever the scene reads best (left/right third, foreground or background, over-shoulder, partial silhouette, small-in-frame, or cropped)."
                "\n- Choose the strongest composition for this scene; only center if the scene explicitly benefits from it."
            )
        else:
            prompt += (
                "\n\nCRITICAL: No persona present. No characters. No human figures. No artist. No people."
                "\nThe generated image MUST NOT include ANY human figures. The cover must be purely environmental, abstract, symbolic, or atmospheric visuals."
            )
        
        # Instruction to ignore parenthetical content
        prompt += "\n\nIMPORTANT: If the song name contains parenthetical content (e.g., ' - (devotional folk meditative)'), ignore it completely. Do not include any parenthetical descriptions or style keywords in the album cover prompt. Use only the core song title without any parenthetical additions."

        if user_ideas:
            prompt += f"\n\n=== ADDITIONAL USER IDEAS (MUST INCORPORATE) ===\n{user_ideas}\n=== END USER IDEAS ===\n"

        # If reference images exist, use vision API to analyze them
        if reference_images:
            prompt += f"\n\nAnalyze the provided reference images of this persona and create an album cover prompt that matches the character's visual appearance, styling, and aesthetic from these images."
            prompt += "\n\nIMPORTANT: The album cover must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."
            if storyboard_theme:
                prompt += "\nMANDATORY: The storyboard theme overrides any conflicting cues. Keep the theme fully intact while merging persona visuals."
            prompt += "\n\nCreate a detailed album cover prompt suitable for image generation that incorporates ALL of the persona's visual characteristics, appearance, styling, and aesthetic."
            # Reinforce merged style and lyrics influence on coloring and scene
            if merged_style or song_lyrics:
                prompt += "\n\nCRITICAL REMINDER FOR COLORING AND SCENE:"
                if merged_style:
                    prompt += "\n- Use the merged style as the PRIMARY source for color palette, lighting, and overall visual aesthetic"
                if song_lyrics:
                    prompt += "\n- Use the song lyrics as the PRIMARY source for scene content, character depiction, and symbolic imagery"
                prompt += "\n- The merged style and lyrics should be the dominant influences on the final cover's coloring and scene composition"
            
            self.log_debug('INFO', f'Generating album cover prompt using {len(reference_images)} reference images...')
            self.config(cursor='wait')
            self.update()
            
            try:
                system_message = 'You are an image prompt generator. Analyze the reference images and create an album cover prompt that matches the character\'s visual appearance. Output ONLY the image prompt text, nothing else.'
                result = self.azure_vision(reference_images, prompt, system_message=system_message, profile='text')
            except Exception as e:
                messagebox.showerror('Error', f'Error generating album cover prompt: {e}')
                self.log_debug('ERROR', f'Error generating album cover prompt: {e}')
                return
        else:
            if include_persona:
                prompt += "\n\nIMPORTANT: The album cover must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."
                if storyboard_theme:
                    prompt += "\nMANDATORY: The storyboard theme overrides any conflicting cues. Keep the theme fully intact while merging persona visuals."
                prompt += "\n\nCreate a detailed album cover prompt suitable for image generation that incorporates ALL of the persona's visual characteristics, appearance, styling, and aesthetic."
            else:
                prompt += "\n\nCreate a detailed album cover prompt suitable for image generation. The image must contain NO human figures, characters, or people - only environmental, abstract, symbolic, or atmospheric visuals."
            # Reinforce merged style and lyrics influence on coloring and scene
            if merged_style or song_lyrics:
                prompt += "\n\nCRITICAL REMINDER FOR COLORING AND SCENE:"
                if merged_style:
                    prompt += "\n- Use the merged style as the PRIMARY source for color palette, lighting, and overall visual aesthetic"
                if song_lyrics:
                    prompt += "\n- Use the song lyrics as the PRIMARY source for scene content and symbolic imagery"
                prompt += "\n- The merged style and lyrics should be the dominant influences on the final cover's coloring and scene composition"
            
            self.log_debug('INFO', 'Generating album cover prompt (no reference images available)...' if include_persona else 'Generating album cover prompt (persona excluded)...')
            self.config(cursor='wait')
            self.update()
            
            try:
                if include_persona:
                    system_message = 'You are an image prompt generator. Output ONLY the image prompt text, nothing else.'
                else:
                    system_message = (
                        'You are an image prompt generator. Output ONLY the image prompt text, nothing else. '
                        'CRITICAL: The prompt must describe ONLY environments, landscapes, objects, abstract art, or symbolic imagery. '
                        'Do NOT describe any person, character, human figure, face, or artist. The image must have zero people in it.'
                    )
                result = self.azure_ai(prompt, system_message, profile='text')
            except Exception as e:
                messagebox.showerror('Error', f'Error generating album cover prompt: {e}')
                self.log_debug('ERROR', f'Error generating album cover prompt: {e}')
                return
        
        try:
            if result['success']:
                cover_prompt_raw = result['content'].strip()
                cover_prompt = self._sanitize_style_keywords(cover_prompt_raw)
                if not include_persona and cover_prompt and not cover_prompt.lower().startswith('no person'):
                    cover_prompt = 'No person present. No characters. No human figures. No people. ' + cover_prompt
                self.album_cover_text.delete('1.0', tk.END)
                self.album_cover_text.insert('1.0', cover_prompt)
                self.log_debug('INFO', 'Album cover prompt generated successfully')
            else:
                messagebox.showerror('Error', f'Failed to generate album cover prompt: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate album cover prompt: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error processing album cover prompt: {e}')
            self.log_debug('ERROR', f'Error processing album cover prompt: {e}')
        finally:
            self.config(cursor='')
    
    def improve_album_cover_prompt(self):
        """Improve the album cover prompt using AI based on user feedback."""
        current_prompt = self.album_cover_text.get('1.0', tk.END).strip()
        if not current_prompt:
            messagebox.showwarning('Warning', 'Please generate an album cover prompt first.')
            return
        
        # Open dialog to get improvement request
        dialog = PromptImprovementDialog(self, 'Album Cover', current_prompt)
        self.wait_window(dialog)
        
        if not dialog.result:
            return  # User cancelled
        
        improvement_request = dialog.result
        
        # Build improvement prompt
        prompt = f"Improve the following album cover prompt based on these requested changes:\n\n"
        prompt += f"REQUESTED CHANGES: {improvement_request}\n\n"
        prompt += f"CURRENT PROMPT:\n{current_prompt}\n\n"
        prompt += "Generate an improved version of the prompt that incorporates the requested changes while maintaining the core concept and style. Output ONLY the improved prompt text, nothing else."
        
        try:
            self.config(cursor='wait')
            self.update()
            
            system_message = 'You are an expert at improving image generation prompts. Analyze the current prompt and requested changes, then generate an improved version that incorporates the changes while maintaining quality and coherence. Output ONLY the improved prompt text.'
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)
            
            if result.get('success'):
                improved_prompt = result.get('content', '').strip()
                
                # Show result dialog
                result_dialog = ImprovedPromptResultDialog(self, improved_prompt, current_prompt)
                self.wait_window(result_dialog)
                
                if result_dialog.result:
                    # User wants to save
                    self.album_cover_text.delete('1.0', tk.END)
                    self.album_cover_text.insert('1.0', improved_prompt)
                    self.log_debug('INFO', 'Album cover prompt improved and saved')
                    messagebox.showinfo('Success', 'Improved prompt saved.')
            else:
                messagebox.showerror('Error', f'Failed to improve prompt: {result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to improve album cover prompt: {result.get("error", "Unknown error")}')
        except Exception as e:
            messagebox.showerror('Error', f'Error improving album cover prompt: {e}')
            self.log_debug('ERROR', f'Error improving album cover prompt: {e}')
        finally:
            self.config(cursor='')
    
    def improve_album_cover_prompt_album(self):
        """Improve the album cover prompt (album tab) by mixing all song cover prompts into the main album cover prompt.
        Always allows manual improvement feedback while also automatically incorporating song cover prompts."""
        current_prompt = self.album_cover_album_text.get('1.0', tk.END).strip()
        if not current_prompt:
            messagebox.showwarning('Warning', 'Please generate an album cover prompt first.')
            return
        
        # Collect all song cover prompts from songs in the current album
        song_cover_prompts = []
        if self.current_album and self.current_persona_path:
            album_songs = self.current_album.get('songs', [])
            if album_songs:
                songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
                for song_folder in album_songs:
                    song_path = os.path.join(songs_dir, song_folder)
                    if os.path.isdir(song_path):
                        song_config = load_song_config(song_path)
                        song_name = song_config.get('song_name', song_folder)
                        song_cover = song_config.get('album_cover', '').strip()
                        if song_cover:
                            song_cover_prompts.append({
                                'song_name': song_name,
                                'cover_prompt': song_cover
                            })
        
        # Always show dialog for manual improvement (user can provide feedback or leave empty)
        dialog = PromptImprovementDialog(self, 'Album Cover', current_prompt)
        self.wait_window(dialog)
        
        if dialog.result is None:
            return  # User cancelled
        
        improvement_request = dialog.result.strip() if dialog.result else ''
        
        # Build the improvement prompt
        prompt = "Improve and enhance the following album cover prompt"
        
        if improvement_request:
            prompt += f" based on these requested changes: {improvement_request}"
        
        if song_cover_prompts:
            prompt += " and by incorporating elements and themes from all the individual song cover prompts provided below"
        
        prompt += ".\n\n"
        prompt += f"MAIN ALBUM COVER PROMPT:\n{current_prompt}\n\n"
        
        if song_cover_prompts:
            prompt += "SONG COVER PROMPTS TO INCORPORATE:\n"
            for idx, song_data in enumerate(song_cover_prompts, 1):
                prompt += f"\nSong {idx}: {song_data['song_name']}\n"
                prompt += f"Cover Prompt: {song_data['cover_prompt']}\n"
            prompt += "\n"
        
        prompt += "TASK: Create an improved album cover prompt that:\n"
        prompt += "1. Maintains the core concept and style of the main album cover prompt\n"
        
        if improvement_request:
            prompt += "2. Incorporates the requested manual changes\n"
        
        if song_cover_prompts:
            if improvement_request:
                prompt += "3. Intelligently incorporates visual elements, themes, colors, moods, and stylistic features from all the song cover prompts\n"
                prompt += "4. Creates a cohesive and unified visual representation that represents the entire album\n"
                prompt += "5. Blends the different song aesthetics harmoniously without losing the main album identity\n"
                prompt += "6. Ensures the final prompt is detailed, evocative, and suitable for high-quality image generation\n"
            else:
                prompt += "2. Intelligently incorporates visual elements, themes, colors, moods, and stylistic features from all the song cover prompts\n"
                prompt += "3. Creates a cohesive and unified visual representation that represents the entire album\n"
                prompt += "4. Blends the different song aesthetics harmoniously without losing the main album identity\n"
                prompt += "5. Ensures the final prompt is detailed, evocative, and suitable for high-quality image generation\n"
        else:
            if improvement_request:
                prompt += "2. Incorporates the requested changes while maintaining quality and coherence\n"
        
        prompt += "\nOutput ONLY the improved album cover prompt text, nothing else."
        
        if song_cover_prompts:
            system_message = 'You are an expert at creating cohesive visual designs. You excel at blending multiple artistic concepts into a unified whole while maintaining the core identity. Generate an improved album cover prompt that harmoniously combines the main album concept with elements from all individual song covers.'
        else:
            system_message = 'You are an expert at improving image generation prompts. Analyze the current prompt and requested changes, then generate an improved version that incorporates the changes while maintaining quality and coherence. Output ONLY the improved prompt text.'
        
        try:
            self.config(cursor='wait')
            self.update()
            
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)
            
            if result.get('success'):
                improved_prompt = result.get('content', '').strip()
                
                # Show result dialog
                result_dialog = ImprovedPromptResultDialog(self, improved_prompt, current_prompt)
                self.wait_window(result_dialog)
                
                if result_dialog.result:
                    # User wants to save
                    self.album_cover_album_text.delete('1.0', tk.END)
                    self.album_cover_album_text.insert('1.0', improved_prompt)
                    if self.current_album is not None:
                        self.current_album['cover_prompt'] = improved_prompt
                    self.log_debug('INFO', 'Album cover prompt improved and saved')
                    if song_cover_prompts:
                        self.log_debug('INFO', f'Mixed {len(song_cover_prompts)} song cover prompts into album cover')
                    if improvement_request:
                        self.log_debug('INFO', 'Applied manual improvement request')
                    messagebox.showinfo('Success', 'Improved prompt saved.')
            else:
                messagebox.showerror('Error', f'Failed to improve prompt: {result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to improve album cover prompt: {result.get("error", "Unknown error")}')
        except Exception as e:
            messagebox.showerror('Error', f'Error improving album cover prompt: {e}')
            self.log_debug('ERROR', f'Error improving album cover prompt: {e}')
        finally:
            self.config(cursor='')
    
    def translate_prompt(self, text_widget, prompt_type: str):
        """Translate a prompt (cover prompt or storyboard theme) between English and German."""
        current_prompt = text_widget.get('1.0', tk.END).strip()
        if not current_prompt:
            messagebox.showwarning('Warning', f'Please enter a {prompt_type.lower()} first.')
            return
        
        # Detect language (simple heuristic: check for common German words/characters)
        # This is a basic detection - user can override
        has_umlauts = any(c in current_prompt for c in 'äöüÄÖÜß')
        has_common_german_words = any(word in current_prompt.lower() for word in ['der', 'die', 'das', 'und', 'ist', 'sind', 'mit', 'für', 'auf', 'in', 'zu'])
        likely_german = has_umlauts or (has_common_german_words and len([w for w in ['der', 'die', 'das', 'und', 'ist'] if w in current_prompt.lower()]) >= 2)
        
        # Show dialog to select translation direction
        lang_dialog = tk.Toplevel(self)
        lang_dialog.title(f'Translate {prompt_type}')
        lang_dialog.geometry('400x200')
        lang_dialog.transient(self)
        lang_dialog.grab_set()
        lang_dialog.update_idletasks()
        
        # Center dialog
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width() or lang_dialog.winfo_screenwidth()
            parent_h = self.winfo_height() or lang_dialog.winfo_screenheight()
        except Exception:
            parent_x = parent_y = 0
            parent_w = lang_dialog.winfo_screenwidth()
            parent_h = lang_dialog.winfo_screenheight()
        dlg_w = lang_dialog.winfo_width()
        dlg_h = lang_dialog.winfo_height()
        pos_x = parent_x + (parent_w - dlg_w) // 2
        pos_y = parent_y + (parent_h - dlg_h) // 2
        lang_dialog.geometry(f'+{max(0, pos_x)}+{max(0, pos_y)}')
        
        main_frame = ttk.Frame(lang_dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text='Select Translation Direction:', font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 15))
        
        # Default to detected language
        default_direction = 'de_to_en' if likely_german else 'en_to_de'
        lang_var = tk.StringVar(value=default_direction)
        ttk.Radiobutton(main_frame, text='English → German', variable=lang_var, value='en_to_de').pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text='German → English', variable=lang_var, value='de_to_en').pack(anchor=tk.W, pady=5)
        
        result = [None]
        
        def ok_clicked():
            result[0] = lang_var.get()
            lang_dialog.destroy()
        
        def cancel_clicked():
            lang_dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text='Translate', command=ok_clicked).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text='Cancel', command=cancel_clicked).pack(side=tk.LEFT, padx=4)
        
        lang_dialog.bind('<Return>', lambda e: ok_clicked())
        lang_dialog.bind('<Escape>', lambda e: cancel_clicked())
        
        self.wait_window(lang_dialog)
        
        if not result[0]:
            return
        
        translation_dir = result[0]
        source_lang = 'English' if translation_dir == 'en_to_de' else 'German'
        target_lang = 'German' if translation_dir == 'en_to_de' else 'English'
        
        # Translate the prompt
        try:
            self.config(cursor='wait')
            self.update()
            
            translate_prompt = (
                f"Translate the following {prompt_type.lower()} from {source_lang} to {target_lang}, "
                f"maintaining all artistic, visual, and technical descriptions exactly as they are.\n\n"
                f"IMPORTANT:\n"
                f"- Preserve all technical terms, artistic concepts, and visual descriptions\n"
                f"- Maintain the same level of detail and specificity\n"
                f"- Keep all formatting, structure, and style intact\n"
                f"- Do not add or remove any information\n"
                f"- Return only the translated text, no explanations\n\n"
                f"{prompt_type}:\n{current_prompt}"
            )
            
            system_message = f'You are a professional translator specializing in {source_lang} to {target_lang} translations for visual art, music, and creative prompts. Translate accurately while preserving all technical and artistic details.'
            
            translate_result = self.azure_ai(translate_prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)
            
            if translate_result.get('success'):
                translated_text = translate_result.get('content', '').strip()
                
                # Update the text widget
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', translated_text)
                
                # If this is an album cover prompt in album tab, update the album config
                if text_widget == self.album_cover_album_text and self.current_album is not None:
                    self.current_album['cover_prompt'] = translated_text
                
                # If this is an album video prompt in album tab, update the album config
                if text_widget == self.album_video_text and self.current_album is not None:
                    self.current_album['video_prompt'] = translated_text
                
                # If this is a song cover prompt, update the song config
                if text_widget == self.album_cover_text and self.current_song_path:
                    song_cfg = load_song_config(self.current_song_path)
                    song_cfg['album_cover'] = translated_text
                    save_song_config(self.current_song_path, song_cfg)
                    self.current_song = song_cfg
                
                # If this is a storyboard theme, update the song config
                if text_widget == self.storyboard_theme_text and self.current_song_path:
                    song_cfg = load_song_config(self.current_song_path)
                    song_cfg['storyboard_theme'] = translated_text
                    save_song_config(self.current_song_path, song_cfg)
                    self.current_song = song_cfg
                
                self.log_debug('INFO', f'{prompt_type} translated from {source_lang} to {target_lang}')
                messagebox.showinfo('Success', f'{prompt_type} translated successfully.')
            else:
                messagebox.showerror('Error', f'Failed to translate {prompt_type.lower()}: {translate_result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to translate {prompt_type}: {translate_result.get("error", "Unknown error")}')
        except Exception as e:
            messagebox.showerror('Error', f'Error translating {prompt_type.lower()}: {e}')
            self.log_debug('ERROR', f'Error translating {prompt_type}: {e}')
        finally:
            self.config(cursor='')

    def improve_video_loop_prompt(self):
        """Improve the song video loop prompt using AI based on user feedback."""
        current_prompt = self.video_loop_text.get('1.0', tk.END).strip()
        if not current_prompt:
            messagebox.showwarning('Warning', 'Please generate a video loop prompt first.')
            return

        dialog = PromptImprovementDialog(self, 'Video Loop', current_prompt)
        self.wait_window(dialog)
        if not dialog.result:
            return

        improvement_request = dialog.result
        prompt = f"Improve the following video loop prompt based on these requested changes:\n\n"
        prompt += f"REQUESTED CHANGES: {improvement_request}\n\n"
        prompt += f"CURRENT PROMPT:\n{current_prompt}\n\n"
        prompt += "Generate an improved version of the video prompt that incorporates the requested changes while maintaining the core concept, style, and scene structure. Output ONLY the improved prompt text, nothing else."

        try:
            self.config(cursor='wait')
            self.update()
            system_message = 'You are an expert at improving video generation prompts. Analyze the current prompt and requested changes, then generate an improved version that incorporates the changes while maintaining quality, coherence, and proper scene formatting. Output ONLY the improved prompt text.'
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=2000, temperature=0.7)

            if result.get('success'):
                improved_prompt = result.get('content', '').strip()
                result_dialog = ImprovedPromptResultDialog(self, improved_prompt, current_prompt)
                self.wait_window(result_dialog)
                if result_dialog.result:
                    self.video_loop_text.delete('1.0', tk.END)
                    self.video_loop_text.insert('1.0', improved_prompt)
                    self.log_debug('INFO', 'Video loop prompt improved and saved')
                    messagebox.showinfo('Success', 'Improved prompt saved.')
            else:
                messagebox.showerror('Error', f'Failed to improve prompt: {result.get("error", "Unknown error")}')
                self.log_debug('ERROR', f'Failed to improve video loop prompt: {result.get("error", "Unknown error")}')
        except Exception as e:
            messagebox.showerror('Error', f'Error improving video loop prompt: {e}')
            self.log_debug('ERROR', f'Error improving video loop prompt: {e}')
        finally:
            self.config(cursor='')

    def generate_video_loop(self):
        """Generate video loop prompt. Supports multi-scene mode with scene switches."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return

        dialog = PromptGenerationIdeasDialog(self, 'Video Loop', 'Song')
        self.wait_window(dialog)
        if dialog.result is None:
            return
        user_ideas = (dialog.result or '').strip()

        album_cover = self.album_cover_text.get('1.0', tk.END).strip()
        merged_style = self._get_sanitized_style_text()
        preset_key = self._get_song_persona_preset_key()
        base_path = self.get_persona_image_base_path(preset_key)
        
        if not album_cover:
            messagebox.showwarning('Warning', 'Please generate an album cover prompt first.')
            return
        
        # Get multi-scene settings
        is_multiscene = self.video_loop_multiscene_var.get() if hasattr(self, 'video_loop_multiscene_var') else False
        video_duration = int(self.video_loop_duration_var.get() or 6) if hasattr(self, 'video_loop_duration_var') else 6
        try:
            scene_duration = int(self.video_loop_scene_duration_var.get() or 2) if hasattr(self, 'video_loop_scene_duration_var') else 2
        except Exception:
            scene_duration = 2
        scene_duration = max(1, min(10, scene_duration))
        num_scenes = max(1, video_duration // scene_duration) if is_multiscene else 1
        
        # Check if persona reference images exist
        safe_name = self._safe_persona_basename()
        front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
        side_image_path = os.path.join(base_path, f'{safe_name}-Side.png')
        back_image_path = os.path.join(base_path, f'{safe_name}-Back.png')
        
        reference_images = []
        scaled_cover_path = None
        cover_path = self.get_album_cover_filepath() if hasattr(self, 'get_album_cover_filepath') else ''
        if cover_path and os.path.isfile(cover_path):
            scaled_cover_path = _scale_image_to_half(cover_path)
            if scaled_cover_path:
                reference_images.append(scaled_cover_path)
                self.log_debug('INFO', 'Including scaled album cover image in video prompt generation')
        if os.path.exists(front_image_path):
            reference_images.append(front_image_path)
        if os.path.exists(side_image_path):
            reference_images.append(side_image_path)
        if os.path.exists(back_image_path):
            reference_images.append(back_image_path)
        
        # Get full persona visual description
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
        base_image_prompt = self.current_persona.get('base_image_prompt', '')
        vibe = self.current_persona.get('vibe', '')
        
        # Build base prompt
        prompt = f"Generate a video loop prompt based on this album cover description:\n\n{album_cover}\n\nMerged Style: {merged_style}"

        if user_ideas:
            prompt += f"\n\n=== ADDITIONAL USER IDEAS (MUST INCORPORATE) ===\n{user_ideas}\n=== END USER IDEAS ===\n"

        # Include full persona visual description
        if visual_aesthetic:
            prompt += f"\n\nPersona Visual Aesthetic: {visual_aesthetic}"
        if base_image_prompt:
            prompt += f"\n\nPersona Base Image Prompt (Character Visual Description): {base_image_prompt}"
        if vibe:
            prompt += f"\n\nPersona Vibe: {vibe}"
        
        # Add multi-scene instructions if enabled
        if is_multiscene and num_scenes > 1:
            prompt += f"\n\n=== MULTI-SCENE VIDEO LOOP ({video_duration} seconds total) ==="
            prompt += f"\n\nCreate a {video_duration}-second video loop with {num_scenes} distinct scenes, each lasting {scene_duration} seconds."
            prompt += "\n\nIMPORTANT MULTI-SCENE REQUIREMENTS (CRITICAL FOR AI VIDEO TOOLS):"
            prompt += "\n- Use HARD CUTS / JUMP CUTS between scenes - NO smooth transitions, NO fades, NO morphing, NO continuity"
            prompt += "\n- Each scene must RADICALLY change - wildly different environments, settings, or compositions every " + str(scene_duration) + " second(s)"
            prompt += "\n- Add keywords: 'rapid scene changes', 'montage style', 'abrupt transitions', 'hyper-fast cuts' to encourage the AI to actually change scenes"
            prompt += "\n- The persona/character must appear consistently across all scenes (if included)"
            prompt += "\n- Use explicit time markers in output - AI video tools (Runway, Kling, etc.) respond to timeline phrasing"
            prompt += "\n- Avoid: smooth gradual transition, slow motion, same scene persisting, boring, static"
            prompt += "\n\nFormat your output as (use exact timestamps):"
            for i in range(num_scenes):
                start_time = i * scene_duration
                end_time = start_time + scene_duration
                prompt += f"\n\n[{start_time}s-{end_time}s] Scene {i+1}: [describe a RADICALLY different scene - distinct setting, angle, or composition]"
        
        # If reference images exist, use vision API to analyze them
        if reference_images:
            if cover_path and os.path.isfile(cover_path):
                prompt += "\n\nThe FIRST image is the generated album cover. Create a video prompt that matches and extends this visual."
            prompt += f"\n\nAnalyze the provided reference images of this persona and create a video loop prompt that matches the character's visual appearance, styling, and aesthetic from these images."
            prompt += "\n\nIMPORTANT: The video loop must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."
            if not is_multiscene:
                prompt += "\n\nCreate a seamless looping video prompt suitable for music visualization that incorporates ALL of the persona's visual characteristics, appearance, styling, and aesthetic."
            
            self.log_debug('INFO', f'Generating {"multi-scene " if is_multiscene else ""}video loop prompt using {len(reference_images)} reference images...')
            self.config(cursor='wait')
            self.update()
            
            try:
                if is_multiscene:
                    system_message = (
                        f'You are a video prompt generator for AI video tools (Runway, Kling, Grok Imagine, etc.). '
                        f'Create a {video_duration}-second multi-scene video with {num_scenes} distinct scenes ({scene_duration}s each). '
                        'CRITICAL: Use HARD CUTS, JUMP CUTS - each scene must be wildly different. Add "rapid transitions", "montage style", "abrupt", "no continuity" to your output. '
                        'Analyze the reference images and ensure the character appears consistently across all scenes. '
                        'AI video tools often smooth everything - your prompt must explicitly demand radical scene changes. Output ONLY the final video prompt text with scene timestamps.'
                    )
                else:
                    system_message = 'You are a professional video prompt generator for music visualizers. Analyze the reference images and create a video loop prompt that matches the character\'s visual appearance. Generate clean, artistic, SFW video prompts suitable for music content. Output ONLY the final video prompt text with no explanations.'
                result = self.azure_vision(reference_images, prompt, system_message=system_message, profile='text')
            except Exception as e:
                messagebox.showerror('Error', f'Error generating video loop prompt: {e}')
                self.log_debug('ERROR', f'Error generating video loop prompt: {e}')
                return
            finally:
                if scaled_cover_path and os.path.exists(scaled_cover_path):
                    try:
                        os.unlink(scaled_cover_path)
                    except Exception:
                        pass
        else:
            prompt += "\n\nIMPORTANT: The video loop must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."
            if not is_multiscene:
                prompt += "\n\nCreate a seamless looping video prompt suitable for music visualization that incorporates ALL of the persona's visual characteristics, appearance, styling, and aesthetic."
            
            self.log_debug('INFO', f'Generating {"multi-scene " if is_multiscene else ""}video loop prompt (no reference images available)...')
            self.config(cursor='wait')
            self.update()
            
            try:
                if is_multiscene:
                    system_message = (
                        f'You are a video prompt generator for AI video tools (Runway, Kling, Grok Imagine, etc.). '
                        f'Create a {video_duration}-second multi-scene video with {num_scenes} distinct scenes ({scene_duration}s each). '
                        'CRITICAL: Use HARD CUTS, JUMP CUTS - each scene must be wildly different. Add "rapid transitions", "montage style", "abrupt", "no continuity" to your output. '
                        'AI video tools often smooth everything - your prompt must explicitly demand radical scene changes. Output ONLY the final video prompt text with scene timestamps.'
                    )
                else:
                    system_message = 'You are a professional video prompt generator for music visualizers. Generate clean, artistic, SFW video prompts suitable for music content. Output ONLY the final video prompt text with no explanations.'
                result = self.azure_ai(prompt, system_message, profile='text')
            except Exception as e:
                messagebox.showerror('Error', f'Error generating video loop prompt: {e}')
                self.log_debug('ERROR', f'Error generating video loop prompt: {e}')
                return
        
        try:
            
            if result['success']:
                video_prompt_raw = result['content'].strip()
                video_prompt = self._sanitize_style_keywords(video_prompt_raw)
                self.video_loop_text.delete('1.0', tk.END)
                self.video_loop_text.insert('1.0', video_prompt)
                mode_str = f'multi-scene ({num_scenes} scenes)' if is_multiscene else 'single scene'
                self.log_debug('INFO', f'Video loop prompt generated successfully ({mode_str})')
            else:
                messagebox.showerror('Error', f'Failed to generate video loop prompt: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate video loop prompt: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating video loop prompt: {e}')
            self.log_debug('ERROR', f'Error generating video loop prompt: {e}')
        finally:
            self.config(cursor='')
    
    def load_storyboard(self):
        """Load storyboard scenes into the treeview."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        # Clear existing items
        for item in self.storyboard_tree.get_children():
            self.storyboard_tree.delete(item)
        
        storyboard = self.current_song.get('storyboard', [])
        if isinstance(storyboard, list):
            for scene in storyboard:
                scene_num = scene.get('scene')
                if scene_num is None:
                    scene_num = len(self.storyboard_tree.get_children()) + 1
                duration = scene.get('duration', '')
                timestamp = scene.get('timestamp', '')
                lyrics = scene.get('lyrics', '')
                prompt = self.apply_storyboard_theme_prefix(scene.get('prompt', ''))
                # Compute timestamp if missing
                if not timestamp:
                    try:
                        seconds_per_video = int(self.storyboard_seconds_var.get() or '6')
                        start_time = (int(scene_num) - 1) * seconds_per_video
                        timestamp = self.format_timestamp(start_time)
                    except Exception:
                        timestamp = '0:00'
                self.storyboard_tree.insert('', tk.END, values=(scene_num, timestamp, duration, lyrics, prompt))
    
    def reset_storyboard(self):
        """Reset the storyboard to empty state, clearing all scenes."""
        if not self.current_song_path or not self.current_song:
            messagebox.showwarning('Warning', 'No song selected. Please select a song first.')
            return
        
        # Confirm with user
        response = messagebox.askyesno(
            'Reset Storyboard',
            'Are you sure you want to reset the storyboard?\n\n'
            'This will delete all storyboard scenes and their generated prompts.\n'
            'This action cannot be undone.'
        )
        
        if not response:
            return
        
        # Clear the storyboard and metadata in the current song config
        self.current_song['storyboard'] = []
        self.current_song['storyboard_metadata'] = {}

        # Clear the treeview
        if hasattr(self, 'storyboard_tree'):
            for item in self.storyboard_tree.get_children():
                self.storyboard_tree.delete(item)
        
        # Clear the preview text
        if hasattr(self, 'storyboard_preview_text'):
            self.storyboard_preview_text.config(state='normal')
            self.storyboard_preview_text.delete('1.0', tk.END)
            self.storyboard_preview_text.config(state='disabled')
        
        # Clear the cached prompts
        self.scene_final_prompts = {}
        
        if hasattr(self, 'storyboard_video_style_var'):
            self.storyboard_video_style_var.set('Realism')
        
        # Save the updated config
        if save_song_config(self.current_song_path, self.current_song):
            self.log_debug('INFO', 'Storyboard reset successfully')
            messagebox.showinfo('Success', 'Storyboard has been reset.')
        else:
            self.log_debug('ERROR', 'Failed to save config after storyboard reset')
            messagebox.showerror('Error', 'Failed to save configuration.')
    
    def get_storyboard_data(self):
        """Get storyboard data from treeview, preserving all existing properties from config.json."""
        if not hasattr(self, 'storyboard_tree'):
            return []
        
        # Reload config.json to get the latest data including any generated_prompt fields
        # This ensures we preserve properties that were saved after the song was loaded
        existing_storyboard = {}
        if self.current_song_path:
            try:
                # Reload config.json directly to get latest data
                config_file = os.path.join(self.current_song_path, 'config.json')
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        latest_config = json.load(f)
                        existing_list = latest_config.get('storyboard', [])
                        for scene in existing_list:
                            scene_num = scene.get('scene')
                            if scene_num is not None:
                                try:
                                    key = int(scene_num) if not isinstance(scene_num, int) else scene_num
                                    existing_storyboard[key] = scene
                                except (ValueError, TypeError):
                                    existing_storyboard[scene_num] = scene
            except Exception as e:
                # Fallback to current_song if reload fails
                self.log_debug('WARNING', f'Failed to reload config.json for storyboard merge: {e}')
                if self.current_song:
                    existing_list = self.current_song.get('storyboard', [])
                    for scene in existing_list:
                        scene_num = scene.get('scene')
                        if scene_num is not None:
                            try:
                                key = int(scene_num) if not isinstance(scene_num, int) else scene_num
                                existing_storyboard[key] = scene
                            except (ValueError, TypeError):
                                existing_storyboard[scene_num] = scene
        elif self.current_song:
            # Fallback if no path available
            existing_list = self.current_song.get('storyboard', [])
            for scene in existing_list:
                scene_num = scene.get('scene')
                if scene_num is not None:
                    try:
                        key = int(scene_num) if not isinstance(scene_num, int) else scene_num
                        existing_storyboard[key] = scene
                    except (ValueError, TypeError):
                        existing_storyboard[scene_num] = scene
        
        storyboard = []
        for item in self.storyboard_tree.get_children():
            values = self.storyboard_tree.item(item, 'values')
            
            # Extract basic fields from treeview
            if len(values) >= 5:
                scene_num = int(values[0]) if str(values[0]).isdigit() else len(storyboard) + 1
                timestamp = values[1]
                duration = values[2]
                lyrics = values[3] if len(values) > 3 else ''
                prompt = values[4] if len(values) > 4 else values[3] if len(values) > 3 else ''
            elif len(values) >= 4:
                scene_num = int(values[0]) if str(values[0]).isdigit() else len(storyboard) + 1
                timestamp = '0:00'
                duration = values[1]
                lyrics = values[2] if len(values) > 2 else ''
                prompt = values[3] if len(values) > 3 else ''
            else:
                continue
            
            # Start with existing scene data if available, or create new dict
            if scene_num in existing_storyboard:
                scene_data = existing_storyboard[scene_num].copy()
            else:
                scene_data = {}
            
            # Update with current treeview values (these are the source of truth for displayed data)
            scene_data['scene'] = scene_num
            scene_data['timestamp'] = timestamp
            scene_data['duration'] = duration
            scene_data['lyrics'] = lyrics
            scene_data['prompt'] = prompt
            
            # Add lyrics_timing (word-level ms) when JSON source available for lip-sync
            if lyrics and self.current_song_path:
                scene_start = self._parse_timestamp_to_seconds(timestamp)
                dur_match = re.search(r'(\d+)', str(duration))
                scene_dur = int(dur_match.group(1)) if dur_match else 6
                scene_end = scene_start + scene_dur
                timing_list = self._get_lyrics_timing_list_for_scene(scene_start, scene_end)
                if timing_list:
                    scene_data['lyrics_timing'] = timing_list
            
            storyboard.append(scene_data)
        
        return storyboard

    def format_timestamp(self, seconds_value: float) -> str:
        """Format seconds as M:SS timestamp string (for display e.g. scene start)."""
        if seconds_value is None:
            return '0:00'
        try:
            total_seconds = max(0, float(seconds_value))
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            return f"{minutes}:{seconds:02d}"
        except Exception:
            return '0:00'

    def _format_timestamp_mm_ss_mmm(self, seconds_value: float) -> str:
        """Format seconds as M:SS.mmm (always 3 decimal places for lip-sync)."""
        try:
            total = max(0, float(seconds_value))
            minutes = int(total // 60)
            secs = int(total % 60)
            ms = min(999, int(round((total % 1) * 1000)))
            return f"{minutes}:{secs:02d}.{ms:03d}"
        except Exception:
            return '0:00.000'
    
    def get_mp3_duration(self, mp3_path: str) -> float:
        """Get MP3 duration in seconds."""
        if not os.path.exists(mp3_path):
            return 0.0
        
        if MUTAGEN_AVAILABLE:
            try:
                audio = MP3(mp3_path)
                return audio.info.length
            except Exception as e:
                self.log_debug('WARNING', f'Failed to get MP3 duration with mutagen: {e}')
        
        # Fallback: estimate based on file size (rough estimate: ~1MB per minute)
        try:
            file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
            estimated_duration = file_size_mb * 60  # Rough estimate
            return estimated_duration
        except Exception:
            return 0.0
    
    def get_extracted_lyrics(self, mp3_path: str, force_extract: bool = False) -> str:
        """Get extracted lyrics from config or extract from MP3 if not available.
        
        Args:
            mp3_path: Path to MP3 file
            force_extract: If True, always extract from MP3 even if config has lyrics
        
        Returns:
            Extracted lyrics string (with timestamps if available)
        """
        # Check config first if not forcing extraction
        if not force_extract and self.current_song:
            extracted_lyrics = self.current_song.get('extracted_lyrics', '').strip()
            if extracted_lyrics:
                self.log_debug('INFO', 'Using cached extracted lyrics from config')
                return extracted_lyrics
            # If config empty, try lyrics_transcription.json (from earlier extraction)
            if self.current_song_path:
                extracted_lyrics = self._load_extracted_lyrics_from_json(self.current_song_path)
                if extracted_lyrics:
                    self.log_debug('INFO', 'Using extracted lyrics from lyrics_transcription.json')
                    return extracted_lyrics
        
        # Extract from MP3
        if mp3_path and os.path.exists(mp3_path):
            extracted_lyrics = self.extract_lyrics_from_mp3(mp3_path)
            if extracted_lyrics:
                # Save to config
                if self.current_song:
                    self.current_song['extracted_lyrics'] = extracted_lyrics
                    save_song_config(self.current_song_path, self.current_song)
                    # Update UI if tab exists
                    if hasattr(self, 'extracted_lyrics_text'):
                        self.extracted_lyrics_text.delete('1.0', tk.END)
                        self.extracted_lyrics_text.insert('1.0', extracted_lyrics)
                return extracted_lyrics
        
        return ''
    
    def _get_embedded_lyrics_from_mp3(self, mp3_path: str) -> tuple:
        """Extract embedded lyrics from MP3 ID3 tags (USLT/SYLT).
        
        Returns:
            Tuple of (lyrics_with_timestamps, reference_text).
            - lyrics_with_timestamps: str in 0:00=0:01=word format if SYLT has timestamps, else ''
            - reference_text: str from USLT for alignment hint (when no SYLT or SYLT empty)
        """
        if not MUTAGEN_AVAILABLE or not mp3_path or not mp3_path.lower().endswith('.mp3'):
            return ('', '')
        try:
            tags = ID3(mp3_path)
        except Exception:
            return ('', '')
        
        lyrics_timed = ''
        reference_text = ''
        
        # Prefer SYLT (synced lyrics) when present and has timing
        sylt_frames = tags.getall('SYLT')
        for sylt in sylt_frames:
            if hasattr(sylt, 'text') and sylt.text:
                lines = []
                # sylt.text is list of (text, time) - time in ms (format=2) or frames (format=1)
                frame_format = getattr(sylt, 'format', 2)
                for i, (text, time_val) in enumerate(sylt.text):
                    if not (text and text.strip()):
                        continue
                    if frame_format == 2:
                        # Milliseconds
                        start_sec = time_val / 1000.0
                    else:
                        # MPEG frames: ~26.122ms per frame at 75 fps
                        start_sec = time_val / 75.0
                    end_sec = start_sec + 0.5  # Default 0.5s per word if no end
                    if i + 1 < len(sylt.text):
                        _, next_time = sylt.text[i + 1]
                        if frame_format == 2:
                            end_sec = next_time / 1000.0
                        else:
                            end_sec = next_time / 75.0
                    ts_start = self._format_timestamp_mm_ss_mmm(start_sec)
                    ts_end = self._format_timestamp_mm_ss_mmm(end_sec)
                    lines.append(f'{ts_start}={ts_end}={text.strip()}')
                if lines:
                    lyrics_timed = '\n'.join(lines)
                    self.log_debug('INFO', f'Using embedded SYLT lyrics from MP3 ({len(lines)} entries)')
                    return (lyrics_timed, '')
        
        # Fallback: USLT as reference text for AI alignment (no timestamps)
        uslt_frames = tags.getall('USLT')
        for uslt in uslt_frames:
            if hasattr(uslt, 'text') and uslt.text and uslt.text.strip():
                reference_text = uslt.text.strip()
                self.log_debug('INFO', f'Found embedded USLT lyrics for alignment reference ({len(reference_text)} chars)')
                break
        
        return (lyrics_timed, reference_text)
    
    def extract_lyrics_from_mp3(self, mp3_path: str) -> str:
        """Extract lyrics from MP3 or MP4 file using AI transcription.
        
        Prefers (Vocals) variant when present for better lyric extraction.
        If both MP3 and MP4 files exist with the same basename, asks user which to use.
        
        Returns:
            Lyrics string with timestamps from AI transcription, empty string on failure
        """
        if not os.path.exists(mp3_path):
            return ''
        
        base_path = os.path.splitext(mp3_path)[0]
        # Prefer vocal-only track for lyrics extraction when it exists
        vocals_mp3_path = base_path + ' (Vocals).mp3'
        vocals_mp4_path = base_path + ' (Vocals).mp4'
        if os.path.exists(vocals_mp3_path):
            self.log_debug('INFO', f'Using vocal file for lyrics extraction: {os.path.basename(vocals_mp3_path)}')
            lyrics_timed, ref_text = self._get_embedded_lyrics_from_mp3(vocals_mp3_path)
            if lyrics_timed:
                return lyrics_timed
            return self.extract_lyrics_with_ai(vocals_mp3_path, lyrics_reference=ref_text)
        if os.path.exists(vocals_mp4_path):
            self.log_debug('INFO', f'Using vocal file for lyrics extraction: {os.path.basename(vocals_mp4_path)}')
            return self.extract_lyrics_with_ai(vocals_mp4_path)
        
        # Check if MP4 file with same basename exists
        audio_path = mp3_path
        mp4_path = base_path + '.mp4'
        
        mp3_exists = os.path.exists(mp3_path)
        mp4_exists = os.path.exists(mp4_path)
        
        if mp3_exists and mp4_exists:
            # Both files exist - ask user which one to use
            result = messagebox.askquestion(
                'Select Audio Source',
                f'Both MP3 and MP4 files found:\n\n'
                f'MP3: {os.path.basename(mp3_path)}\n'
                f'MP4: {os.path.basename(mp4_path)}\n\n'
                f'Use MP4 file for transcription?\n\n'
                f'(Yes = MP4, No = MP3)',
                icon='question'
            )
            if result == 'yes':
                audio_path = mp4_path
                self.log_debug('INFO', f'User selected MP4 file for transcription: {mp4_path}')
            else:
                self.log_debug('INFO', f'User selected MP3 file for transcription: {mp3_path}')
        elif mp4_exists and not mp3_exists:
            # Only MP4 exists
            audio_path = mp4_path
            self.log_debug('INFO', f'Using MP4 file for transcription (no MP3 found): {mp4_path}')
        else:
            # Only MP3 exists (or neither, but we checked mp3_path exists above)
            self.log_debug('INFO', 'Extracting lyrics from MP3 using AI transcription...')
        
        # For MP3: try embedded USLT/SYLT first
        if audio_path.lower().endswith('.mp3'):
            lyrics_timed, ref_text = self._get_embedded_lyrics_from_mp3(audio_path)
            if lyrics_timed:
                return lyrics_timed
            return self.extract_lyrics_with_ai(audio_path, lyrics_reference=ref_text)
        return self.extract_lyrics_with_ai(audio_path)
    
    def extract_lyrics_with_ai(self, audio_path: str, lyrics_reference: str = '') -> str:
        """Extract lyrics from audio/video file using AI transcription.
        
        Supports multiple transcription backends:
        - Azure Speech Services (profile: 'speech') - Best for music/vocals with word-level timestamps
        - Azure OpenAI Whisper/gpt-4o-transcribe (profile: 'transcribe') - General purpose
        
        Args:
            audio_path: Path to audio file (MP3, MP4, or other supported format)
            lyrics_reference: Optional reference lyrics (e.g. from USLT) for alignment hint in transcription
        
        Returns:
            Lyrics string with timestamps in format [MM:SS.mmm] word
        """
        if not os.path.exists(audio_path):
            self.log_debug('ERROR', f'Audio file not found: {audio_path}')
            return ''
        
        self.log_debug('INFO', f'Starting AI transcription of: {audio_path}')
        
        # Check available transcription services
        speech_profile = self.ai_config.get('profiles', {}).get('speech', {})
        transcribe_profile = self.ai_config.get('profiles', {}).get('transcribe', {})
        
        speech_available = bool(speech_profile.get('endpoint') and speech_profile.get('subscription_key'))
        transcribe_available = bool(transcribe_profile.get('endpoint') and transcribe_profile.get('subscription_key'))
        
        # Get user preference from settings
        preferred_service = self.ai_config.get('transcription_service', 'ask')
        self.log_debug('DEBUG', f'Transcription service preference: {preferred_service}')
        
        # Determine which transcription service to use
        use_speech_services = False
        
        if preferred_service == 'speech':
            # User prefers Azure Speech Services
            if speech_available:
                use_speech_services = True
            elif transcribe_available:
                self.log_debug('WARNING', 'Azure Speech Services not configured, falling back to OpenAI transcribe')
                use_speech_services = False
            else:
                messagebox.showerror('Error', 'No transcription service configured. Please configure either "speech" or "transcribe" profile in AI Settings.')
                return ''
        elif preferred_service == 'transcribe':
            # User prefers OpenAI transcribe
            if transcribe_available:
                use_speech_services = False
            elif speech_available:
                self.log_debug('WARNING', 'OpenAI transcribe not configured, falling back to Azure Speech Services')
                use_speech_services = True
            else:
                messagebox.showerror('Error', 'No transcription service configured. Please configure either "speech" or "transcribe" profile in AI Settings.')
                return ''
        else:
            # 'ask' mode - prompt user if both are available
            if speech_available and transcribe_available:
                result = messagebox.askquestion(
                    'Select Transcription Service',
                    'Multiple transcription services are available:\n\n'
                    '1. Azure Speech Services (recommended for music)\n'
                    '   - Better accuracy for vocals with music\n'
                    '   - Word-level timestamps\n\n'
                    '2. Azure OpenAI (Whisper/gpt-4o-transcribe)\n'
                    '   - General purpose transcription\n\n'
                    'Use Azure Speech Services?\n\n'
                    '(Tip: Set "Service" dropdown to avoid this prompt)',
                    icon='question'
                )
                use_speech_services = (result == 'yes')
            elif speech_available:
                use_speech_services = True
            elif transcribe_available:
                use_speech_services = False
            else:
                messagebox.showerror('Error', 'No transcription service configured. Please configure either "speech" or "transcribe" profile in AI Settings.')
                return ''
        
        if use_speech_services:
            return self._extract_lyrics_with_speech_services(audio_path)
        else:
            return self._extract_lyrics_with_openai(audio_path, lyrics_reference=lyrics_reference)
    
    def _get_speech_locale_for_song(self) -> str:
        """Resolve Azure Speech locale from song/album language. Returns e.g. 'en-US' or 'de-DE'."""
        lang = None
        if self.current_song:
            album_id = self.current_song.get('album_id', '')
            if album_id and self.albums and album_id in self.albums:
                lang = self.albums[album_id].get('language', '') or None
        if not lang and self.current_album:
            lang = self.current_album.get('language', '') or None
        if not lang and hasattr(self, 'album_lang_var'):
            lang = self.album_lang_var.get() or None
        lang = (lang or 'EN').upper()[:2]
        locale_map = {'EN': 'en-US', 'DE': 'de-DE'}
        return locale_map.get(lang, 'en-US')
    
    def _extract_lyrics_with_speech_services(self, audio_path: str) -> str:
        """Extract lyrics using Azure Speech Services API."""
        locale = self._get_speech_locale_for_song()
        self.log_debug('INFO', f'Using Azure Speech Services for transcription (locale={locale})...')
        
        speech_profile = self.ai_config.get('profiles', {}).get('speech', {})
        self.log_debug('DEBUG', f'Speech profile endpoint: {speech_profile.get("endpoint", "NOT SET")}')
        self.log_debug('DEBUG', f'Speech profile API version: {speech_profile.get("api_version", "NOT SET")}')
        
        self.config(cursor='wait')
        self.update()
        
        try:
            result = call_azure_speech_transcription(
                self.ai_config,
                audio_path,
                profile='speech',
                language=locale
            )
            
            if result['success']:
                words = result.get('words', [])
                segments = result.get('segments', [])
                text_only = result.get('text', '')
                raw_json = result.get('raw_json', {})
                
                self.log_debug('INFO', f'Azure Speech transcription successful: {len(words)} words, {len(segments)} segments')
                
                # Create JSON formatted output with timestamps
                lyrics_json = []
                
                if words:
                    for word_info in words:
                        word = word_info.get('word', '').strip()
                        start = word_info.get('start', 0)
                        end = word_info.get('end', 0)
                        if word:
                            start_ms = int(start * 1000)
                            end_ms = int(end * 1000) if end else start_ms
                            timestamp_str = self._format_timestamp_mm_ss_mmm(start)
                            end_timestamp_str = self._format_timestamp_mm_ss_mmm(end) if end else timestamp_str
                            lyrics_json.append({
                                'timestamp': start,
                                'timestamp_ms': start_ms,
                                'timestamp_formatted': timestamp_str,
                                'text': word,
                                'end_timestamp': end,
                                'end_timestamp_ms': end_ms,
                                'end_timestamp_formatted': end_timestamp_str
                            })
                elif segments:
                    for segment in segments:
                        text_seg = segment.get('text', '').strip()
                        start = segment.get('start', 0)
                        end = segment.get('end', 0)
                        if text_seg:
                            start_ms = int(start * 1000)
                            end_ms = int(end * 1000) if end else start_ms
                            timestamp_str = self._format_timestamp_mm_ss_mmm(start)
                            end_timestamp_str = self._format_timestamp_mm_ss_mmm(end) if end else timestamp_str
                            lyrics_json.append({
                                'timestamp': start,
                                'timestamp_ms': start_ms,
                                'timestamp_formatted': timestamp_str,
                                'text': text_seg,
                                'end_timestamp': end,
                                'end_timestamp_ms': end_ms,
                                'end_timestamp_formatted': end_timestamp_str
                            })
                
                # Save formatted JSON with timestamps
                if lyrics_json and self.current_song_path:
                    json_filename = os.path.join(self.current_song_path, 'lyrics_transcription.json')
                    try:
                        with open(json_filename, 'w', encoding='utf-8') as f:
                            json.dump(lyrics_json, f, indent=2, ensure_ascii=False)
                        self.log_debug('INFO', f'Saved formatted lyrics JSON to: {json_filename}')
                    except Exception as e:
                        self.log_debug('WARNING', f'Failed to save lyrics JSON: {e}')
                
                # Save raw JSON data for reference
                if raw_json and self.current_song_path:
                    raw_json_filename = os.path.join(self.current_song_path, 'lyrics_transcription_raw.json')
                    try:
                        with open(raw_json_filename, 'w', encoding='utf-8') as f:
                            json.dump(raw_json, f, indent=2, ensure_ascii=False)
                        self.log_debug('INFO', f'Saved raw transcription JSON to: {raw_json_filename}')
                    except Exception as e:
                        self.log_debug('WARNING', f'Failed to save raw transcription JSON: {e}')
                
                # Format as text with timestamps for display (double-equals with ms for lip-sync)
                formatted_lines = []
                for entry in lyrics_json:
                    if 'end_timestamp' in entry and entry.get('end_timestamp') is not None:
                        formatted_lines.append(f"{entry['timestamp_formatted']}={entry['end_timestamp_formatted']}={entry['text']}")
                    else:
                        formatted_lines.append(f"{entry['timestamp_formatted']}={entry['text']}")
                
                return '\n'.join(formatted_lines) if formatted_lines else text_only
            else:
                error_msg = result.get('error', 'Unknown error')
                self.log_debug('ERROR', f'Azure Speech transcription failed: {error_msg}')
                messagebox.showerror('Transcription Error', f'Failed to transcribe audio:\n{error_msg}')
                return ''
        
        except Exception as e:
            self.log_debug('ERROR', f'Error during Azure Speech transcription: {e}')
            messagebox.showerror('Transcription Error', f'Error transcribing audio:\n{e}')
            return ''
        finally:
            self.config(cursor='')
    
    def _extract_lyrics_with_openai(self, audio_path: str, lyrics_reference: str = '') -> str:
        """Extract lyrics using Azure OpenAI (Whisper/gpt-4o-transcribe)."""
        lang = self._get_speech_locale_for_song().split('-')[0]
        self.log_debug('INFO', f'Transcribing with language={lang} (from song/album)')
        transcribe_profile = self.ai_config.get('profiles', {}).get('transcribe', {})
        self.log_debug('DEBUG', f'Transcribe profile endpoint: {transcribe_profile.get("endpoint", "NOT SET")}')
        self.log_debug('DEBUG', f'Transcribe profile deployment: {transcribe_profile.get("deployment", "NOT SET")}')
        self.log_debug('DEBUG', f'Transcribe profile API version: {transcribe_profile.get("api_version", "NOT SET")}')
        self.log_debug('DEBUG', f'Transcription request: file="{audio_path}", language="{lang}", response_format="verbose_json" (preferred), profile="transcribe"')
        
        # Guidance prompt for transcription (helps retain lyrical structure and punctuation)
        transcription_prompt = (
            "Transcribe the attached audio file with word-level timestamps."
            "Preserve repetitions, fillers, and non-verbal cues if present"
            "Output the result strictly as a vertical list where every single word is on a new line."
            "Use the format mm:ss=Word (with no spaces around the equals sign)."
            "Do not group phrases together; assign a specific start time to every individual word."
            "Do not include any other text or formatting."
        )
        # Optionally append known lyrics to guide alignment (from Lyrics field, or embedded USLT)
        known_lyrics = ''
        if hasattr(self, 'lyrics_text'):
            known_lyrics = self.lyrics_text.get('1.0', tk.END).strip()
        if not known_lyrics and lyrics_reference:
            known_lyrics = lyrics_reference
        if known_lyrics:
            transcription_prompt += (
                "\n\nHere are the original suno song lyrics for alignment with what you detect from the song:\n"
                f"{known_lyrics}"
            )

        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_transcription(
                audio_path,
                profile='transcribe',
                language=lang,
                response_format='verbose_json',
                prompt=transcription_prompt
            )
            
            if result['success']:
                lyrics_text = result.get('content', '')
                raw_json = result.get('raw_json', {})
                segments = result.get('segments', [])
                words = result.get('words', [])
                text_only = result.get('text', '')
                
                if lyrics_text or segments or words or text_only:
                    self.log_debug('INFO', f'AI transcription successful: {len(text_only or lyrics_text)} characters')
                    
                    # Create JSON formatted output with timestamps
                    lyrics_json = []
                    
                    if words:
                        # Use word-level timestamps for precise timing (with end from next word if missing)
                        for i, word_info in enumerate(words):
                            word = word_info.get('word', '').strip()
                            start = word_info.get('start', 0)
                            end = word_info.get('end')
                            if not end and i + 1 < len(words):
                                end = words[i + 1].get('start')
                            if word:
                                start_ms = int(start * 1000)
                                end_ms = int(end * 1000) if end else start_ms
                                entry = {
                                    'timestamp': start,
                                    'timestamp_ms': start_ms,
                                    'timestamp_formatted': self._format_timestamp_mm_ss_mmm(start),
                                    'text': word
                                }
                                if end is not None:
                                    entry['end_timestamp'] = end
                                    entry['end_timestamp_ms'] = end_ms
                                    entry['end_timestamp_formatted'] = self._format_timestamp_mm_ss_mmm(end)
                                lyrics_json.append(entry)
                    elif segments:
                        # Use segment-level timestamps (with end)
                        for segment in segments:
                            text_seg = segment.get('text', '').strip()
                            start = segment.get('start', 0)
                            end = segment.get('end')
                            if text_seg:
                                start_ms = int(start * 1000)
                                entry = {
                                    'timestamp': start,
                                    'timestamp_ms': start_ms,
                                    'timestamp_formatted': self._format_timestamp_mm_ss_mmm(start),
                                    'text': text_seg
                                }
                                if end is not None:
                                    entry['end_timestamp'] = end
                                    entry['end_timestamp_ms'] = int(end * 1000)
                                    entry['end_timestamp_formatted'] = self._format_timestamp_mm_ss_mmm(end)
                                lyrics_json.append(entry)
                    elif text_only:
                        import re
                        # If raw text already contains timestamped lines like "MM:SS=word",
                        # use those timestamps instead of estimating.
                        timestamped_lines = []
                        for line in text_only.splitlines():
                            match = re.match(r'(\d{2}):(\d{2})=(.+)', line.strip())
                            if match:
                                minutes = int(match.group(1))
                                seconds = int(match.group(2))
                                start_sec = minutes * 60 + seconds
                                text_part = match.group(3).strip()
                                if text_part:
                                    timestamped_lines.append((start_sec, text_part))
                        
                        if timestamped_lines:
                            song_duration = self.get_mp3_duration(audio_path)
                            for i, (start_sec, text_part) in enumerate(timestamped_lines):
                                # Use next start as end boundary when available; otherwise fall back to song duration if known.
                                if i + 1 < len(timestamped_lines):
                                    end_sec = timestamped_lines[i + 1][0]
                                else:
                                    end_sec = song_duration if song_duration > 0 else None
                                
                                entry = {
                                    'timestamp': start_sec,
                                    'timestamp_formatted': self._format_timestamp_mm_ss_mmm(start_sec),
                                    'text': text_part
                                }
                                if end_sec is not None:
                                    entry['end_timestamp'] = end_sec
                                    entry['end_timestamp_formatted'] = self._format_timestamp_mm_ss_mmm(end_sec)
                                
                                lyrics_json.append(entry)
                        else:
                            # No segments available - estimate timestamps based on text length and song duration
                            # Split text into sentences/phrases and distribute evenly
                            self.log_debug('WARNING', 'No segments/words in transcription; estimating timestamps based on song duration')
                            
                            # Get song duration
                            song_duration = self.get_mp3_duration(audio_path)
                            if song_duration > 0:
                                # Split text into sentences (by periods, commas, or line breaks)
                                # Split by sentence endings, commas, or natural breaks
                                sentences = re.split(r'[.!?]\s+|[,\n]', text_only)
                                sentences = [s.strip() for s in sentences if s.strip()]
                                
                                if sentences:
                                    # Distribute timestamps evenly across song duration
                                    time_per_sentence = song_duration / len(sentences)
                                    for i, sentence in enumerate(sentences):
                                        estimated_start = i * time_per_sentence
                                        minutes = int(estimated_start // 60)
                                        seconds = int(estimated_start % 60)
                                        lyrics_json.append({
                                            'timestamp': estimated_start,
                                            'timestamp_formatted': self._format_timestamp_mm_ss_mmm(estimated_start),
                                            'text': sentence,
                                            'estimated': True  # Mark as estimated
                                        })
                                else:
                                    # Fallback: treat entire text as one entry
                                    lyrics_json.append({
                                        'timestamp': 0.0,
                                        'timestamp_formatted': self._format_timestamp_mm_ss_mmm(0.0),
                                        'text': text_only,
                                        'estimated': True
                                    })
                            else:
                                # No duration available - just use 0:00.000
                                lyrics_json.append({
                                    'timestamp': 0.0,
                                    'timestamp_formatted': self._format_timestamp_mm_ss_mmm(0.0),
                                    'text': text_only,
                                    'estimated': True
                                })
                    
                    # Save formatted JSON with timestamps
                    if lyrics_json and self.current_song_path:
                        json_filename = os.path.join(self.current_song_path, 'lyrics_transcription.json')
                        try:
                            with open(json_filename, 'w', encoding='utf-8') as f:
                                json.dump(lyrics_json, f, indent=2, ensure_ascii=False)
                            self.log_debug('INFO', f'Saved formatted lyrics JSON to: {json_filename}')
                        except Exception as e:
                            self.log_debug('WARNING', f'Failed to save lyrics JSON: {e}')
                    
                    # Also save raw JSON data for reference
                    if raw_json and self.current_song_path:
                        raw_json_filename = os.path.join(self.current_song_path, 'lyrics_transcription_raw.json')
                        try:
                            with open(raw_json_filename, 'w', encoding='utf-8') as f:
                                json.dump(raw_json, f, indent=2, ensure_ascii=False)
                            self.log_debug('INFO', f'Saved raw transcription JSON to: {raw_json_filename}')
                        except Exception as e:
                            self.log_debug('WARNING', f'Failed to save raw transcription JSON: {e}')
                    
                    # Format as text with timestamps for display (double-equals with ms for lip-sync)
                    formatted_lines = []
                    for entry in lyrics_json:
                        if 'end_timestamp' in entry and entry.get('end_timestamp') is not None:
                            formatted_lines.append(f"{entry['timestamp_formatted']}={entry['end_timestamp_formatted']}={entry['text']}")
                        else:
                            formatted_lines.append(f"{entry['timestamp_formatted']}={entry['text']}")
                    
                    formatted_lyrics = '\n'.join(formatted_lines)
                    return formatted_lyrics
                else:
                    self.log_debug('WARNING', 'AI transcription returned empty content')
                    return ''
            else:
                error_msg = result.get('error', 'Unknown error')
                self.log_debug('ERROR', f'AI transcription failed: {error_msg}')
                messagebox.showerror('Transcription Error', f'Failed to transcribe audio:\n{error_msg}')
                return ''
        
        except Exception as e:
            self.log_debug('ERROR', f'Error during AI transcription: {e}')
            messagebox.showerror('Transcription Error', f'Error transcribing audio:\n{e}')
            return ''
        finally:
            self.config(cursor='')
    
    def parse_lyrics_with_timing(self, lyrics: str, song_duration: float) -> list:
        """Parse lyrics and extract timing information.
        
        Supports multiple timestamp formats:
        - [00:12] or [0:12] or (00:12) - minutes:seconds
        - [00:12.345] or [0:12.345] - minutes:seconds.milliseconds
        - [00:12:345] - minutes:seconds:milliseconds
        - 0:12=text or 00:12=text - MM:SS=text format (old AI transcription format)
        - 0:00=00:01=word - start_time=end_time=word format (new AI transcription format)
        
        Returns list of tuples: (start_time, end_time, lyric_line)
        """
        if not lyrics or not song_duration:
            return []
        
        lines = lyrics.strip().split('\n')
        lyric_segments = []
        
        # Try to parse timestamps in multiple formats:
        # Format 1: [00:12] or [0:12] or (00:12) - minutes:seconds
        # Format 2: [00:12.345] or [0:12.345] - minutes:seconds.milliseconds
        # Format 3: [00:12:345] - minutes:seconds:milliseconds
        # Format 4: 0:12=text or 00:12=text - MM:SS=text format (old AI transcription format)
        # Format 5: 0:00=00:01=word or 0:04.400=0:05.200=word - start_time=end_time=word (with optional ms)
        bracket_timestamp_pattern = re.compile(r'[\[\(](\d+):(\d+)(?:[:.](\d+))?[\]\)]')
        equals_timestamp_pattern = re.compile(r'^(\d+):(\d+)(?:\.(\d+))?=(.+)$')
        double_equals_timestamp_pattern = re.compile(r'^(\d+):(\d+)(?:\.(\d+))?=(\d+):(\d+)(?:\.(\d+))?=(.+)$')
        
        lines_with_timestamps = []
        lines_with_full_timing = []  # Lines with both start and end times
        lines_without_timestamps = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # First check for start_time=end_time=word format (with optional .mmm)
            double_equals_match = double_equals_timestamp_pattern.match(line)
            if double_equals_match:
                g = double_equals_match.groups()
                sm, ss, sms, em, es, ems, lyric_text = int(g[0]), int(g[1]), g[2], int(g[3]), int(g[4]), g[5], g[6].strip()
                lyric_text = self.clean_lyrics_text(lyric_text)
                start_time = sm * 60 + ss + (int(sms or 0) / 1000.0)
                end_time = em * 60 + es + (int(ems or 0) / 1000.0)
                if lyric_text:
                    lines_with_full_timing.append((start_time, end_time, lyric_text))
                continue
            
            # Check for MM:SS=text or M:SS.mmm=text format (old format)
            equals_match = equals_timestamp_pattern.match(line)
            if equals_match:
                minutes = int(equals_match.group(1))
                seconds = int(equals_match.group(2))
                ms = equals_match.group(3)
                lyric_text = equals_match.group(4).strip()
                lyric_text = self.clean_lyrics_text(lyric_text)
                timestamp_seconds = minutes * 60 + seconds + (int(ms or 0) / 1000.0)
                if lyric_text:
                    lines_with_timestamps.append((timestamp_seconds, lyric_text))
                continue
            
            # Check for bracket format [MM:SS] or (MM:SS)
            timestamp_match = bracket_timestamp_pattern.search(line)
            if timestamp_match:
                minutes = int(timestamp_match.group(1))
                seconds = int(timestamp_match.group(2))
                milliseconds = 0
                if timestamp_match.group(3):
                    milliseconds = int(timestamp_match.group(3))
                    # If milliseconds are 3 digits, they're already milliseconds
                    # If 1-2 digits, they might be centiseconds/deciseconds, treat as milliseconds
                    if len(timestamp_match.group(3)) < 3:
                        milliseconds = milliseconds * (10 ** (3 - len(timestamp_match.group(3))))
                
                timestamp_seconds = minutes * 60 + seconds + (milliseconds / 1000.0)
                # Remove timestamp from line
                lyric_text = bracket_timestamp_pattern.sub('', line).strip()
                # Clean structural markers from lyric text
                lyric_text = self.clean_lyrics_text(lyric_text)
                if lyric_text:
                    lines_with_timestamps.append((timestamp_seconds, lyric_text))
            else:
                # Keep non-empty lines without timestamps, but filter out structural markers
                cleaned_line = self.clean_lyrics_text(line)
                if cleaned_line:
                    lines_without_timestamps.append(cleaned_line)
        
        # If we have full timing (start and end), use them directly
        if lines_with_full_timing:
            lines_with_full_timing.sort(key=lambda x: x[0])  # Sort by start time
            lyric_segments = lines_with_full_timing
        # If we have timestamps (only start), calculate end times
        elif lines_with_timestamps:
            lines_with_timestamps.sort(key=lambda x: x[0])  # Sort by timestamp
            
            # Create segments with timing
            for i, (start_time, lyric_text) in enumerate(lines_with_timestamps):
                # End time is start of next line, or end of song
                if i + 1 < len(lines_with_timestamps):
                    end_time = lines_with_timestamps[i + 1][0]
                else:
                    end_time = song_duration
                
                lyric_segments.append((start_time, end_time, lyric_text))
        else:
            # No timestamps: distribute lyrics evenly across song duration
            if lines_without_timestamps:
                time_per_line = song_duration / len(lines_without_timestamps)
                for i, lyric_text in enumerate(lines_without_timestamps):
                    start_time = i * time_per_line
                    end_time = (i + 1) * time_per_line
                    lyric_segments.append((start_time, end_time, lyric_text))
        
        return lyric_segments
    
    def clean_lyrics_text(self, lyric_text: str) -> str:
        """Remove structural markers like [Intro], [Verse 1], etc. from lyrics."""
        if not lyric_text:
            return lyric_text
        
        # Pattern to match structural markers: [Intro], [Verse 1], [Chorus], [Bridge], [Outro], etc.
        # Also matches variations like (Intro), Verse 1:, etc.
        structural_pattern = re.compile(r'^\s*[\[\(]?(Intro|Outro|Verse\s*\d*|Chorus|Bridge|Pre-Chorus|Hook|Interlude|Solo|Instrumental|Break)\s*[:\]\)]?\s*$', re.IGNORECASE)
        
        # Split by lines and filter out structural markers
        lines = lyric_text.split('\n')
        cleaned_lines = []
        for line in lines:
            cleaned_line = line.strip()
            # Skip empty lines and structural markers
            if cleaned_line and not structural_pattern.match(cleaned_line):
                cleaned_lines.append(line)
        
        # Join back and clean up extra whitespace
        cleaned_text = '\n'.join(cleaned_lines).strip()
        
        # Also remove structural markers that might be inline (at start of line)
        cleaned_text = re.sub(r'^\s*[\[\(]?(Intro|Outro|Verse\s*\d*|Chorus|Bridge|Pre-Chorus|Hook|Interlude|Solo|Instrumental|Break)\s*[:\]\)]\s*', '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        return cleaned_text.strip()

    def sanitize_lyrics_for_prompt(self, text: str) -> str:
        """Remove pipe separators and tidy whitespace for prompt safety."""
        if not text:
            return text
        sanitized = re.sub(r'\s*\|\s*', ' ', text)
        sanitized = re.sub(r'\s{2,}', ' ', sanitized)
        return sanitized.strip()

    def _sanitize_no_character_scene_prompt_for_video(self, prompt: str) -> str:
        """Sanitize stored prompts for no-character scenes: remove lyric-embedding and lip-sync
        instructions that would cause the video model to render visible text.
        Use when returning a stored generated_prompt that has no-character markers."""
        if not prompt:
            return prompt
        result = self.sanitize_prompt_no_lyrics(prompt)
        # Remove lip-sync timing block (no character to sync - would cause video to render text)
        result = re.sub(
            r'\n\nIMPORTANT:\s*You shall synchronize[\s\S]*',
            '',
            result,
            flags=re.IGNORECASE | re.DOTALL
        )
        # Remove CRITICAL - LYRICS EMBEDDING / CRITICAL INSTRUCTIONS that mandate lyric embedding
        result = re.sub(
            r'\n\nCRITICAL\s*-\s*LYRICS\s*EMBEDDING[^\n]*(?:\n[^\n]*)*',
            '',
            result,
            flags=re.IGNORECASE
        )
        # Remove CRITICAL INSTRUCTIONS blocks that mandate lyric embedding
        result = re.sub(
            r'\n\nCRITICAL INSTRUCTIONS FOR THIS SCENE:\n(?:\d+\.\s*[^\n]*\n)*\d+\.\s*CRITICAL\s*-\s*LYRICS\s*EMBEDDING[^\n]*(?:\n[^\n]*)*',
            '',
            result,
            flags=re.IGNORECASE
        )
        # Remove LYRICS INTEGRATION instructions
        result = re.sub(
            r'\n\nLYRICS\s*INTEGRATION[^\n]*(?:\n[^\n]*)*(?:\n[^\n]*)*',
            '',
            result,
            flags=re.IGNORECASE
        )
        # Add strong no-text instruction
        result += "\n\nCRITICAL: No characters in this scene. Do NOT embed, carve, or display any lyric text. Use lyrics for mood and symbolism only; keep the scene completely text-free."
        return result.strip()

    def _strip_dialogue_from_no_character_prompt(self, prompt_text: str) -> str:
        """Remove DIALOGUE lines from prompts marked [NO CHARACTERS] - invalid, no character to sing."""
        if not prompt_text:
            return prompt_text
        no_char_markers = ['[no characters]', 'no characters', 'no persona present', 'no human figures',
                          'no persona', 'no people', 'no artist', '[no persona]', 'without any human',
                          'purely environmental', 'purely abstract', 'no human presence']
        prompt_lower = prompt_text.lower()
        if not any(m in prompt_lower for m in no_char_markers):
            return prompt_text
        # Strip DIALOGUE: ... lines (standalone or inline)
        result = re.sub(r'\n\s*DIALOGUE:\s*[^\n]+', '', prompt_text, flags=re.IGNORECASE)
        result = re.sub(r'DIALOGUE:\s*[^\n]+(?=\n|$)', '', result, flags=re.IGNORECASE)
        return result.strip()

    def sanitize_prompt_no_lyrics(self, prompt_text: str) -> str:
        """Remove lyric-embedding phrases when scene has no lyrics (time does not match).
        Only lyrics whose timing matches the scene should appear in the prompt."""
        if not prompt_text:
            return prompt_text
        result = prompt_text
        # Remove lyric-embedding sentences (lyrics text "X" is embedded / lyric words appear / lyric phrase readable)
        result = re.sub(
            r'[^.]*[Ll]yrics? text\s+"[^"]*"\s+is embedded[^.]*\.',
            ' ', result
        )
        result = re.sub(
            r'[^.]*[Ll]yrics? text\s+\'[^\']*\'[^.]*embedded[^.]*\.',
            ' ', result
        )
        result = re.sub(
            r'[^.]*[Ww]ith the lyrics text\s+["\'][^"\']*["\']\s+embedded[^.]*\.',
            ' ', result
        )
        result = re.sub(
            r'[^.]*[Ll]yric words appear [^.]*\.',
            ' ', result
        )
        result = re.sub(
            r'[^.]*[Ll]yric phrase readable only as[^.]*\.',
            ' ', result
        )
        result = re.sub(
            r'[^.;]*[Tt]he lyric text appears as[^.;]*[.;]',
            ' ', result
        )
        result = re.sub(
            r'[^.;]*[Ll]yric words become visible[^.;]*[.;]',
            ' ', result
        )
        result = re.sub(
            r'[^.;]*[Ff]ull lyric phrase is legible[^.;]*[.;]',
            ' ', result
        )
        result = re.sub(
            r'[^.;]*[Ee]tched words of the lyric[^.;]*[.;]',
            ' ', result
        )
        # Remove LYRICS FOR THIS SCENE lines
        result = re.sub(r'\s*LYRICS FOR THIS SCENE:\s*["\'][^"\']*["\']\s*\n?', '\n', result, flags=re.IGNORECASE)
        # Remove lines that start with "lyrics" (legacy)
        lines = result.splitlines()
        kept = []
        for line in lines:
            if re.search(r'^\s*lyrics\s*:', line, flags=re.IGNORECASE):
                continue
            kept.append(line)
        result = '\n'.join(kept)
        # Collapse multiple spaces/newlines
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)
        return result.strip()

    def is_non_lyric_marker(self, text: str) -> bool:
        """Return True if the text is a structural/non-lyric marker (e.g., instrumental intro)."""
        if not text:
            return True
        t = text.strip().lower()
        marker_words = {
            'instrumental', 'instrumental intro', 'intro', 'outro', 'bridge', 'chorus', 'verse', 'hook',
            '(instrumental)', '(instrumental intro)'
        }
        if t in marker_words:
            return True
        if ('instrumental' in t) and len(t) <= 80:
            return True
        if t.startswith('(') and t.endswith(')') and len(t) <= 80:
            return True
        return False

    def filter_sparse_trailing_lyrics(self, lyric_segments: list, gap_seconds: float = 20.0, max_words: int = 2) -> list:
        """Drop isolated, very short lyric fragments after long gaps (no fixed cutoff).
        
        If the time gap since the last kept lyric exceeds gap_seconds AND the current line
        has very few words (<= max_words), the line is dropped. Gaps reset after every kept line.
        """
        if not lyric_segments:
            return lyric_segments
        filtered = []
        last_kept_time = None
        for start, end, text in lyric_segments:
            word_count = len(text.strip().split())
            if last_kept_time is not None and (start - last_kept_time) > gap_seconds and word_count <= max_words:
                continue
            filtered.append((start, end, text))
            last_kept_time = start
        return filtered
    
    def get_lyrics_for_scene(self, scene_start_time: float, scene_end_time: float, lyric_segments: list) -> str:
        """Get lyrics that overlap the scene window (start < scene_end AND end > scene_start)."""
        matching_lyrics = []
        
        for lyric_start, lyric_end, lyric_text in lyric_segments:
            # Include lyrics that overlap the scene (span boundaries or fall entirely within)
            if lyric_start < scene_end_time and lyric_end > scene_start_time:
                cleaned_text = self.clean_lyrics_text(lyric_text)
                if cleaned_text and not self.is_non_lyric_marker(cleaned_text):
                    matching_lyrics.append(cleaned_text)
        
        if matching_lyrics:
            # Use spaces to avoid unwanted separator characters in prompts
            return ' '.join(matching_lyrics)
        return ''

    def _get_environmental_theme_prefix(self, theme_text: str) -> str:
        """Produce a character-free theme prefix for [NO CHARACTERS] scenes.
        Avoids naming persona/story characters so prompts paired with environmental
        reference images do not confuse the model into adding figures."""
        if not theme_text or not theme_text.strip():
            return "ENVIRONMENTAL SHOT - No human figures. Maintain visual mood and palette.\n"
        # Strip character names and narrative; keep mood/atmosphere keywords
        t = theme_text.strip()
        # Remove common character references (persona, story characters)
        persona_name = ''
        if self.current_persona:
            persona_name = self.current_persona.get('name', '').strip()
        for name in [persona_name, 'Melon Usk', 'Elon Musk', 'Papa Dust', 'Papa Dusk']:
            if name:
                t = re.sub(re.escape(name), '', t, flags=re.IGNORECASE)
        # Remove pronoun-heavy narrative (he/him/his, they, etc. referring to characters)
        t = re.sub(r'\b(he|him|his|they|them|their)\s+(?:finds?|is|was|tries?|run)\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\ba figure looking like\b[^.]*\.?', '', t, flags=re.IGNORECASE)
        # Condense: take meaningful phrases, limit length
        stop = ('the', 'and', 'for', 'out', 'but', 'his', 'him', 'has', 'not', 'from')
        words = [w for w in re.split(r'[\s,]+', t) if len(w) > 2 and w.lower() not in stop]
        mood = ' '.join(words[:25]).strip() if words else 'dark dystopian atmosphere'
        # Truncate incomplete trailing conjunctions (e.g. "collides with", "mood and")
        incomplete_endings = (' with', ' and', ' or', ' but', ' for', ' to')
        for ending in incomplete_endings:
            if mood.lower().endswith(ending):
                mood = mood[:-len(ending)].rstrip()
                break
        if not mood:
            mood = 'dark dystopian atmosphere'
        return f"ENVIRONMENTAL SHOT - No human figures. Visual mood: {mood}\n"

    def _get_video_style_instructions(self, style: str) -> str:
        """Return the instruction block for the selected Video Style.
        Used in storyboard generation to guide prompt language for AI video models.
        Each style has NEVER USE, USE INSTEAD, and GOOD EXAMPLES for hardening."""
        s = (style or 'Realism').strip()
        if s == 'Realism':
            return """
VIDEO REALISM - CRITICAL for AI video generation:
These prompts feed video models (Runway, Kling, etc.). To avoid surreal, melting, or morphing results:

NEVER USE (causes surreal/morphing in video AI):
- dissolve, dissolving, dissolves -> USE: fade, step into, walk into
- melt, melts into -> USE: blend into, transition to
- morph, swallow, consume (when objects merge) -> USE: fade, cut to, transition
- "like [abstract]" (e.g. "like lines of fate", "like extinguished stars") -> omit or describe literally
- empty frame holds, order emerges, cut on beat, no fractures now -> USE: static shot, hard cut, symmetry remains

USE INSTEAD: fade, step into, blend, static shot, hard cut, concrete camera terms (pan, tilt, dolly, close-up)
GOOD EXAMPLES: "Curtain opens.", "Light clicks off.", "Persona steps into street.", "Static wide of empty corridor."
Complete all sentences - never truncate mid-phrase.
"""
        if s == 'Surrealism':
            return """
VIDEO SURREALISM - Dreamlike, abstract AI video:

NEVER USE: incomplete sentences; vague "something emerges" (causes random glitches); accidental literal object-merging when you mean transition
USE: dissolve, morph, blend, transform; explicit "figure dissolves into X"; controlled surreal transitions
GOOD EXAMPLES: "Silhouette dissolves into corridor.", "Shapes morph between light and shadow.", "Reality bends at the edges."
Complete sentences - write explicit surreal transitions, not vague abstraction.
"""
        if s == 'Artistic':
            return """
VIDEO ARTISTIC - Stylized but controlled:

NEVER USE: harsh "dissolve" when "fade" gives more control; "like [abstract]" when it causes literal bizarre objects; empty frame holds, order emerges
PREFER: fade/transition when uncertain; use "dissolve" only for intentional effect; cinematic framing
GOOD EXAMPLES: "Light fades across the set.", "Persona steps through doorway.", "Soft transition to next frame."
Complete sentences; concrete actions preferred for key beats.
"""
        if s == 'Dreamlike':
            return """
VIDEO DREAMLIKE - Soft, ethereal, gentle transitions:

NEVER USE: jarring phrases (order emerges, empty frame holds); harsh cuts
USE: soft dissolve, subtle morph, gentle transition, atmospheric
GOOD EXAMPLES: "Figure fades into mist.", "Soft dissolve to next shot.", "Light drifts across the scene."
Complete sentences preferred.
"""
        if s == 'Cinematic':
            return """
VIDEO CINEMATIC - Traditional film language:

NEVER USE: empty frame holds, order emerges, extreme abstract; uncontrolled morphing
USE: filmic terms (pan, tilt, dolly); moderate metaphor; stable compositions
GOOD EXAMPLES: "Dolly forward as persona walks.", "Static wide, empty street.", "Hard cut to close-up."
Complete all sentences.
"""
        return """
VIDEO REALISM - For hyper-realistic AI video:
NEVER USE: dissolve, melt, morph, "like [abstract]". USE: fade, step into, blend, static shot, hard cut. Complete sentences.
"""

    def _get_video_style_examples(self, style: str) -> str:
        """Return BAD vs GOOD few-shot examples for the selected Video Style.
        Used in storyboard batch prompt to reinforce correct sub-scene writing."""
        s = (style or 'Realism').strip()
        if s == 'Realism':
            return """
EXAMPLE - BAD (do NOT write like this):
  [0s-2s] Companion dissolves into corridor. [2s-4s] Cables coil like lines of fate. [4s-6s] Empty frame holds.

EXAMPLE - GOOD (write like this):
  [0s-2s] Companion steps into corridor. [2s-4s] Cables coil on the floor. [4s-6s] Static shot, empty composition.
"""
        if s == 'Surrealism':
            return """
EXAMPLE - BAD (do NOT write like this):
  [0s-2s] Something emerges. [2s-4s] Order from chaos. [4s-6s] Things merge.

EXAMPLE - GOOD (write like this):
  [0s-2s] Silhouette dissolves into shadow. [2s-4s] Light morphs into geometric forms. [4s-6s] Figure blends into corridor.
"""
        if s == 'Artistic':
            return """
EXAMPLE - BAD (do NOT write like this):
  [0s-2s] Order emerges. [2s-4s] Empty frame holds. [4s-6s] Cables like fate.

EXAMPLE - GOOD (write like this):
  [0s-2s] Light fades across the set. [2s-4s] Persona steps through doorway. [4s-6s] Soft transition to next frame.
"""
        if s == 'Dreamlike':
            return """
EXAMPLE - BAD (do NOT write like this):
  [0s-2s] Order emerges. [2s-4s] Empty frame holds. [4s-6s] Hard cut.

EXAMPLE - GOOD (write like this):
  [0s-2s] Figure fades into mist. [2s-4s] Soft dissolve to next shot. [4s-6s] Light drifts across the scene.
"""
        if s == 'Cinematic':
            return """
EXAMPLE - BAD (do NOT write like this):
  [0s-2s] Empty frame holds. [2s-4s] Order emerges. [4s-6s] Things morph.

EXAMPLE - GOOD (write like this):
  [0s-2s] Dolly forward as persona walks. [2s-4s] Static wide, empty street. [4s-6s] Hard cut to close-up.
"""
        return ""

    def _is_persona_scene_quick(self, prompt_text: str) -> bool:
        """Quick check if prompt describes a persona scene (for theme handling).
        Avoids full AI analysis; used to condense theme for persona scenes."""
        if not prompt_text or not self.current_persona:
            return False
        pl = prompt_text.strip().lower()
        no_char = ['[no characters]', 'no characters', 'no persona present', 'no human figures',
                   'no persona', 'no people', 'no artist', '[no persona]']
        if any(m in pl for m in no_char):
            return False
        if 'character: persona' in pl or 'character : persona' in pl:
            return True
        pname = self.current_persona.get('name', '').lower()
        if pname and pname in pl:
            return True
        return False

    def _storyboard_has_any_persona_or_character(self) -> bool:
        """Check if any scene in the storyboard contains persona or a story character.
        Used for multi-scene mode: when True, scene 1 must use persona reference image."""
        # Prefer treeview data (get_storyboard_data) for latest state; fallback to current_song
        storyboard = []
        if hasattr(self, 'storyboard_tree') and self.storyboard_tree.get_children():
            storyboard = self.get_storyboard_data() if hasattr(self, 'get_storyboard_data') else []
        if not storyboard:
            storyboard = (self.current_song or {}).get('storyboard', [])
        if not storyboard:
            return False
        metadata = (self.current_song or {}).get('storyboard_metadata', {})
        char_ids = set((metadata.get('characters') or {}).keys())
        no_char_markers = ['[no characters]', 'no characters', 'no persona present', 'no human figures',
                          'no persona', 'no people', 'no artist', '[no persona]', 'without any human',
                          'purely environmental', 'purely abstract', 'no human presence']
        persona_char_keywords = ['character', 'persona', 'singer', 'artist', 'performer', 'person', 'figure',
                                'protagonist', 'main character', 'vocalist', 'musician']
        for scene in storyboard:
            prompt = (scene.get('prompt') or '').strip().lower()
            if not prompt:
                continue
            if any(m in prompt for m in no_char_markers):
                continue
            if 'character: persona' in prompt or 'character : persona' in prompt:
                return True
            for cid in char_ids:
                if f'character: {cid}' in prompt or f'character : {cid}' in prompt:
                    return True
            if self.current_persona:
                pname = self.current_persona.get('name', '').lower()
                if pname and pname in prompt:
                    return True
            if any(kw in prompt for kw in persona_char_keywords):
                return True
        return False

    def _build_setup_context_from_metadata(self) -> str:
        """Build a brief setup palette/location context from storyboard_metadata for prompt injection.
        Returns empty string if no setups defined. Used to guide visual consistency across scenes."""
        metadata = (self.current_song or {}).get('storyboard_metadata', {})
        setups = metadata.get('setups') or {}
        if not setups:
            return ''
        parts = []
        for sid, info in setups.items():
            desc = info.get('description', '') if isinstance(info, dict) else str(info)
            if desc:
                parts.append(f"{sid}: {desc}")
        if not parts:
            return ''
        return "SETUP PALETTES (use for visual consistency; match palette when scene fits):\n" + "; ".join(parts) + "\n\n"

    def apply_storyboard_theme_prefix(self, prompt_text: str, use_environmental_for_no_characters: bool = True, persona_scene: bool = False) -> str:
        """Prepend the storyboard theme to a prompt if provided.
        When prompt has [NO CHARACTERS], uses a character-free prefix to avoid
        confusing the model when pairing with environmental reference images.
        When persona_scene=True, uses condensed theme at end to avoid video model
        inferring same dialogue from repeated full theme."""
        if not prompt_text:
            return prompt_text
        theme_text = ''
        if hasattr(self, 'storyboard_theme_text'):
            theme_text = self.storyboard_theme_text.get('1.0', tk.END).strip()
        if theme_text:
            cleaned_prompt = prompt_text.strip()
            prompt_lower = cleaned_prompt.lower()
            no_char_markers = ['[no characters]', 'no characters', 'no persona present', 'no human figures']
            if use_environmental_for_no_characters and any(m in prompt_lower for m in no_char_markers):
                prefix = self._get_environmental_theme_prefix(theme_text)
                if cleaned_prompt.lower().startswith('environmental shot'):
                    return cleaned_prompt
                # Replace theme at start (avoid stripping scene descriptions like "A dystopian megacity...")
                if cleaned_prompt.lower().startswith(theme_text.lower()):
                    cleaned_prompt = cleaned_prompt[len(theme_text):].lstrip()
                # Remove "GLOBAL STORY THEME (prepend): ..." line if present
                cleaned_prompt = re.sub(
                    r'\n?GLOBAL STORY THEME\s*\(prepend\)\s*:[^\n]*(?:\n|$)',
                    '\n', cleaned_prompt, flags=re.IGNORECASE
                ).strip()
                # Remove standalone theme shorthand line (e.g. "Papa Dusk is hunting down Melon Usk...")
                theme_start = re.escape(theme_text[:40].strip()) if len(theme_text) > 20 else ''
                if theme_start:
                    cleaned_prompt = re.sub(
                        r'^' + theme_start + r'[^\n]*\n?',
                        '', cleaned_prompt, count=1, flags=re.IGNORECASE
                    ).strip()
                return f"{prefix}{cleaned_prompt}"
            if persona_scene:
                # For persona scenes: strip full theme from start, use condensed at end
                # so video model does not infer same dialogue from repeated narrative
                if cleaned_prompt.lower().startswith(theme_text.lower()):
                    cleaned_prompt = cleaned_prompt[len(theme_text):].lstrip()
                theme_start = re.escape(theme_text[:50].strip()) if len(theme_text) > 30 else ''
                if theme_start:
                    cleaned_prompt = re.sub(
                        r'^' + theme_start + r'[^\n]*(?:\n|$)',
                        '', cleaned_prompt, count=1, flags=re.IGNORECASE
                    ).strip()
                condensed = self._get_environmental_theme_prefix(theme_text).replace(
                    'ENVIRONMENTAL SHOT - No human figures. Visual mood: ', ''
                ).strip()
                instruction = 'Do NOT use the story theme as character dialogue. Character speaks/sings only the scene lyrics. '
                return f"{instruction}{cleaned_prompt}\n\nContext: {condensed}"
            if not cleaned_prompt.lower().startswith(theme_text.lower()):
                return f"{theme_text}\n{cleaned_prompt}"
            return cleaned_prompt
        return prompt_text

    def _are_prompts_similar(self, prompt_a: str, prompt_b: str, threshold: float = 0.55, min_len: int = 40) -> bool:
        """Determine if two prompts are similar using a simple ratio."""
        if not prompt_a or not prompt_b:
            return False
        a = prompt_a.strip().lower()
        b = prompt_b.strip().lower()
        if len(a) < min_len or len(b) < min_len:
            return False
        return SequenceMatcher(None, a, b).ratio() >= threshold

    def _get_scene_prompt_from_tree(self, scene_num: int) -> str:
        """Fetch prompt text for a given scene from the storyboard tree."""
        if not hasattr(self, 'storyboard_tree'):
            return ''
        for item in self.storyboard_tree.get_children():
            values = self.storyboard_tree.item(item, 'values')
            if len(values) >= 5:
                try:
                    if int(values[0]) == scene_num:
                        return str(values[4])
                except Exception:
                    continue
        return ''

    def _prepare_previous_scene_reference(self, scene_num: int, current_prompt: str) -> str:
        """If the previous scene is similar, analyze its image and return a reference blurb."""
        try:
            prev_scene_num = int(scene_num) - 1
        except Exception:
            return ''
        if prev_scene_num < 1 or not self.current_song_path:
            return ''

        prev_prompt = self._get_scene_prompt_from_tree(prev_scene_num)
        prev_prompt = self.apply_storyboard_theme_prefix(prev_prompt)

        if not self._are_prompts_similar(current_prompt, prev_prompt):
            return ''

        safe_prev = str(prev_scene_num).replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        prev_image_path = os.path.join(self.current_song_path, f'storyboard_scene_{safe_prev}.png')
        if not os.path.exists(prev_image_path):
            return ''

        try:
            downscale_dir = os.path.join(self.current_song_path, 'temp')
            os.makedirs(downscale_dir, exist_ok=True)
            downscaled_path = os.path.join(downscale_dir, f'storyboard_scene_{safe_prev}_ref.png')

            with Image.open(prev_image_path) as img:
                new_w = max(1, img.width // 2)
                new_h = max(1, img.height // 2)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                resized.save(downscaled_path, 'PNG')

            vision_prompt = (
                "Analyze this reference image (previous scene) and describe its key visual traits: composition, palette, lighting, mood, texture, and main elements. "
                "Keep it concise (<120 words)."
            )
            vision_system = (
                "You are an image analysis assistant. Provide a concise, objective description of the reference image focusing on visual traits only."
            )
            result = self.azure_vision([downscaled_path], vision_prompt, system_message=vision_system, profile='text')
            if not result.get('success'):
                return ''
            reference_desc = result.get('content', '').strip()
            if not reference_desc:
                return ''

            return (
                "REFERENCE IMAGE (previous scene, downscaled 50%): "
                f"{reference_desc} "
                "Use this only for continuity (lighting, palette, composition). Keep the new scene distinct while preserving continuity cues."
            )
        except Exception as exc:
            self.log_debug('WARNING', f'Failed to use previous scene reference: {exc}')
            return ''

    def _prepare_album_cover_reference(self) -> str:
        """Use album cover image as reference for the first scene if available."""
        cover_path = self.get_album_cover_filepath()
        if not cover_path:
            return ''
        try:
            downscale_dir = os.path.join(self.current_song_path, 'temp') if self.current_song_path else None
            if not downscale_dir:
                return ''
            os.makedirs(downscale_dir, exist_ok=True)
            downscaled_path = os.path.join(downscale_dir, 'album_cover_ref.png')

            with Image.open(cover_path) as img:
                new_w = max(1, img.width // 2)
                new_h = max(1, img.height // 2)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                resized.save(downscaled_path, 'PNG')

            vision_prompt = (
                "Analyze this album cover reference image and summarize key visual traits: palette, lighting, mood, composition, "
                "dominant motifs, textures, and overall vibe. Keep it concise (<120 words)."
            )
            vision_system = (
                "You are an image analysis assistant. Provide a concise, objective visual description of the album cover."
            )
            result = self.azure_vision([downscaled_path], vision_prompt, system_message=vision_system, profile='text')
            if not result.get('success'):
                return ''
            desc = result.get('content', '').strip()
            if not desc:
                return ''

            return (
                "REFERENCE IMAGE (album cover, downscaled 50%): "
                f"{desc} "
                "Use this cover as the starting visual tone for Scene 1; keep continuity but make the scene a moving shot."
            )
        except Exception as exc:
            self.log_debug('WARNING', f'Failed to use album cover reference: {exc}')
            return ''
    
    def generate_storyboard(self):
        """Analyze MP3 and generate storyboard prompts."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'Please select a song first.')
            return
        
        # Check if MP3 file exists
        mp3_path = self.get_mp3_filepath()
        if not mp3_path or not os.path.exists(mp3_path):
            messagebox.showwarning('Warning', 'MP3 file not found. Please ensure the MP3 file exists before generating storyboard.')
            return
        
        try:
            seconds_per_video = int(self.storyboard_seconds_var.get() or '6')
            if seconds_per_video < 1 or seconds_per_video > 20:
                messagebox.showwarning('Warning', 'Seconds per video must be between 1 and 20.')
                return
        except ValueError:
            messagebox.showwarning('Warning', 'Invalid seconds per video value.')
            return
        
        # Check if song is too long for single response (warn if > 30 scenes)
        song_duration = self.get_mp3_duration(mp3_path)
        if song_duration > 0:
            num_scenes = int(song_duration / seconds_per_video) + (1 if song_duration % seconds_per_video > 0 else 0)
            if num_scenes > 30:
                suggested_seconds = max(seconds_per_video + 2, int(song_duration / 25))  # Aim for ~25 scenes max
                response = messagebox.askyesno(
                    'Warning - Many Scenes',
                    f'This will generate {num_scenes} scenes ({song_duration:.0f}s song / {seconds_per_video}s per scene).\n\n'
                    f'The AI may not be able to generate all scenes in one response.\n\n'
                    f'Recommended: Increase "Seconds per video" to {suggested_seconds} or higher '
                    f'to create approximately {int(song_duration / suggested_seconds)} scenes.\n\n'
                    f'Continue anyway?'
                )
                if not response:
                    return
        
        song_name = self.song_name_var.get().strip()
        full_song_name = self.full_song_name_var.get().strip()
        merged_style = self.merged_style_text.get('1.0', tk.END).strip()
        storyboard_theme = self.storyboard_theme_text.get('1.0', tk.END).strip() if hasattr(self, 'storyboard_theme_text') else ''
        try:
            persona_scene_percent = int(self.persona_scene_percent_var.get() or 40) if hasattr(self, 'persona_scene_percent_var') else 40
        except Exception:
            persona_scene_percent = 40
        persona_scene_percent = max(0, min(100, persona_scene_percent))
        no_persona_percent = max(0, 100 - persona_scene_percent)
        try:
            storyboard_setup_count = int(self.storyboard_setup_count_var.get() or 6) if hasattr(self, 'storyboard_setup_count_var') else 6
        except Exception:
            storyboard_setup_count = 6
        storyboard_setup_count = max(1, min(12, storyboard_setup_count))
        
        # Get multi-scene settings
        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
        is_ai_decides_subscene = (
            self.storyboard_ai_decides_subscene_var.get()
            if hasattr(self, 'storyboard_ai_decides_subscene_var') else False
        )
        try:
            scene_duration = int(self.storyboard_scene_duration_var.get() or 2) if hasattr(self, 'storyboard_scene_duration_var') else 2
        except Exception:
            scene_duration = 2
        scene_duration = max(1, min(10, scene_duration))
        min_subscene_seconds = scene_duration
        max_subscene_seconds = seconds_per_video
        if is_multiscene and is_ai_decides_subscene:
            subscenes_per_video = 0
        else:
            subscenes_per_video = seconds_per_video // scene_duration if is_multiscene and scene_duration > 0 else 1

        persona_name = self.current_persona.get('name', '')
        visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
        base_image_prompt = self.current_persona.get('base_image_prompt', '')
        vibe = self.current_persona.get('vibe', '')

        # Auto-generate a global storyboard theme if missing
        if hasattr(self, 'storyboard_theme_text') and not storyboard_theme:
            try:
                theme_prompt = (
                    "Generate a concise global image/story style to be used as a prefix for all storyboard scenes.\n"
                    "Keep it under 80 words, focus on visual aesthetic (palette, lighting, texture, mood, camera vibe).\n"
                    "Inputs:\n"
                    f"- Song Title: {full_song_name if full_song_name else song_name}\n"
                    f"- Merged Style: {merged_style if merged_style else 'N/A'}\n"
                    f"- Persona Visual Aesthetic: {visual_aesthetic if visual_aesthetic else 'N/A'}\n"
                    f"- Persona Base Image Prompt: {base_image_prompt if base_image_prompt else 'N/A'}\n"
                    f"- Persona Vibe: {vibe if vibe else 'N/A'}\n"
                    "Output ONLY the style text, no labels."
                )
                theme_result = self.azure_ai(theme_prompt, system_message="You are a visual style summarizer.", profile='text')
                if theme_result.get('success'):
                    generated_theme = theme_result.get('content', '').strip()
                    if generated_theme:
                        storyboard_theme = generated_theme
                        self.storyboard_theme_text.delete('1.0', tk.END)
                        self.storyboard_theme_text.insert('1.0', generated_theme)
                        self.log_debug('INFO', 'Auto-generated storyboard theme from merged style/persona.')
            except Exception as exc:
                self.log_debug('WARNING', f'Failed to auto-generate storyboard theme: {exc}')
        
        # Reset cached prompts for fresh generation
        self.scene_final_prompts = {}

        if is_multiscene and is_ai_decides_subscene:
            multiscene_info = f' (multi-scene: AI-decided sub-scene cuts min {min_subscene_seconds}s max {max_subscene_seconds}s)'
        elif is_multiscene and subscenes_per_video > 1:
            multiscene_info = f' (multi-scene: {subscenes_per_video}x{scene_duration}s per video)'
        else:
            multiscene_info = ''
        self.log_debug('INFO', f'Generating storyboard for MP3: {mp3_path}{multiscene_info}')
        self.config(cursor='wait')
        self.update()
        
        try:
            # ALWAYS prefer already-extracted lyrics; only analyze MP3 if missing
            lyrics = ''
            if self.current_song:
                lyrics = self.current_song.get('extracted_lyrics', '').strip()

            # Stale-data guard: if user edited extracted_lyrics_text, use displayed version
            if hasattr(self, 'extracted_lyrics_text'):
                displayed = self.extracted_lyrics_text.get('1.0', tk.END).strip()
                if displayed and displayed != lyrics:
                    self.log_debug('INFO', 'Using displayed extracted lyrics (user edits) for LYRICS_TIMING')
                    lyrics = displayed
                    if self.current_song:
                        self.current_song['extracted_lyrics'] = lyrics
                        save_song_config(self.current_song_path, self.current_song)

            if not lyrics:
                self.log_debug('INFO', 'Extracting lyrics from MP3 (only because none cached)...')
                lyrics = self.get_extracted_lyrics(mp3_path, force_extract=True)
                if hasattr(self, 'extracted_lyrics_text') and lyrics:
                    self.extracted_lyrics_text.delete('1.0', tk.END)
                    self.extracted_lyrics_text.insert('1.0', lyrics)

            if not lyrics:
                messagebox.showwarning(
                    'No Lyrics Found',
                    'Could not extract lyrics from MP3 file. Storyboard generation requires extracted lyrics with timing data.\n\n'
                    'Please extract lyrics first using the "Extract Lyrics" button, or ensure the MP3 file contains lyrics metadata.'
                )
                self.config(cursor='')
                return

            # Pre-storyboard: offer sync when original lyrics exist for better precision
            original_lyrics = ''
            if hasattr(self, 'lyrics_text'):
                original_lyrics = self.lyrics_text.get('1.0', tk.END).strip()
            if original_lyrics and hasattr(self, 'extracted_lyrics_text'):
                sync_offered = messagebox.askyesno(
                    'Sync Lyrics for Precision',
                    'Original lyrics are available in the Lyrics field. Syncing extracted with original can fix wrong word detections and improve scene alignment.\n\n'
                    'Sync extracted lyrics with original now before generating storyboard?',
                    icon='question'
                )
                if sync_offered:
                    self.sync_extracted_with_original_lyrics()
                    lyrics = self.extracted_lyrics_text.get('1.0', tk.END).strip() if hasattr(self, 'extracted_lyrics_text') else lyrics
                    if not lyrics:
                        self.config(cursor='')
                        return

            # Validate timestamp format; warn if estimated
            has_precise = bool(re.search(r'\d+:\d+(?:\.\d+)?=\d+:\d+(?:\.\d+)?=', lyrics)) or bool(re.search(r'\[\d+:\d+(?:[.:]\d+)*\]', lyrics))
            if not has_precise and lyrics.strip():
                proceed = messagebox.askyesno(
                    'Lyrics Timestamps May Be Estimated',
                    'Lyrics timestamps may be estimated rather than word-level precise. Scene-lyric alignment could be less accurate.\n\n'
                    'Consider using "Sync with original Lyrics" or re-extracting with Azure Speech Services for better alignment.\n\n'
                    'Continue with storyboard generation anyway?',
                    icon='warning'
                )
                if not proceed:
                    self.config(cursor='')
                    return
            
            self.log_debug('INFO', f'Using extracted lyrics with timing data ({len(lyrics)} characters)')
            
            # Get MP3 duration and parse lyrics with timing
            song_duration = self.get_mp3_duration(mp3_path)
            lyric_segments = []
            if lyrics and song_duration > 0:
                lyric_segments = self.parse_lyrics_with_timing(lyrics, song_duration)
                # Drop isolated tiny fragments if they're separated by more than one scene length
                lyric_segments = self.filter_sparse_trailing_lyrics(
                    lyric_segments,
                    gap_seconds=float(seconds_per_video),
                    max_words=2
                )
                if lyric_segments:
                    self.log_debug('INFO', f'Parsed {len(lyric_segments)} lyric segments from song duration {song_duration:.1f}s')
            else:
                self.log_debug('WARNING', 'No lyrics or invalid song duration; skipping lyric-based storyboard hints')
            # Calculate scenes needed
            num_scenes = int(song_duration / seconds_per_video) + (1 if song_duration % seconds_per_video > 0 else 0)
            
            # Build scene-by-scene lyrics information if available
            scene_lyrics_info = ""
            scene_lyrics_dict = {}
            if song_duration > 0:
                scene_lyrics_info = "\n<LYRICS_TIMING>\n"
                current_time = 0.0
                for scene_idx in range(1, num_scenes + 1):
                    scene_start_time = current_time
                    scene_end_time = min(current_time + seconds_per_video, song_duration)
                    scene_lyrics = ""
                    if lyric_segments:
                        scene_lyrics = self.sanitize_lyrics_for_prompt(self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments))
                    ts_label = self.format_timestamp(scene_start_time)
                    scene_lyrics_info += f"Scene {scene_idx} ({ts_label}): {scene_lyrics if scene_lyrics else '[NO LYRICS]'}\n"
                    if scene_lyrics:
                        scene_lyrics_dict[scene_idx] = scene_lyrics
                    current_time = scene_end_time
                    if current_time >= song_duration:
                        break
                scene_lyrics_info += "</LYRICS_TIMING>\n"
                self.log_debug('DEBUG', f'LYRICS_TIMING block for storyboard prompt:\n{scene_lyrics_info}')

            # For AI-decided sub-scene mode: lyric timestamps within each scene so AI can align cuts
            scene_lyrics_within_info = ""
            if is_multiscene and is_ai_decides_subscene and lyric_segments and song_duration > 0:
                scene_lyrics_within_info = "\n<LYRICS_WITHIN_SCENE for sub-scene cut alignment>\n"
                current_time = 0.0
                for scene_idx in range(1, num_scenes + 1):
                    scene_start_time = current_time
                    scene_end_time = min(current_time + seconds_per_video, song_duration)
                    parts = []
                    for ly_start, ly_end, ly_text in lyric_segments:
                        if ly_start < scene_end_time and ly_end > scene_start_time:
                            rel_start = max(0.0, ly_start - scene_start_time)
                            rel_end = min(seconds_per_video, ly_end - scene_start_time)
                            clean = self.sanitize_lyrics_for_prompt(ly_text)
                            if clean:
                                parts.append(f"{rel_start:.1f}s-{rel_end:.1f}s: \"{clean}\"")
                    scene_lyrics_within_info += f"Scene {scene_idx} (0s-{seconds_per_video}s): " + (" | ".join(parts) if parts else "[NO LYRICS]") + "\n"
                    current_time = scene_end_time
                    if current_time >= song_duration:
                        break
                scene_lyrics_within_info += "</LYRICS_WITHIN_SCENE>\n"
                self.log_debug('DEBUG', f'LYRICS_WITHIN_SCENE block:\n{scene_lyrics_within_info}')

            embed_lyrics = bool(self.embed_lyrics_var.get()) if hasattr(self, 'embed_lyrics_var') else True
            if scene_lyrics_info:
                if embed_lyrics:
                    lyrics_rule = """
   - Each scene MUST use ONLY the lyrics from LYRICS_TIMING that match that scene's time range
   - For scenes marked [NO LYRICS]: do NOT embed any lyric text; keep the scene text-free (mood/atmosphere only)
   - For scenes WITH lyrics: embed those lyrics INTO the environment (carved in walls, neon signs, formed by patterns)
   - NEVER use lyrics from a different scene's time range
   - NEVER use text overlays, subtitles, or floating text"""
                else:
                    lyrics_rule = """
   - Each scene should reflect the mood/meaning of its lyrics from LYRICS_TIMING
   - Do NOT render or embed any visible text or lyrics in the scene
   - Keep all scenes text-free (no overlays, no environmental text)
   - [NO LYRICS] marker should be used to indicate that the scene has no lyrics."""
            else:
                lyrics_rule = """
   - Visualize song theme and mood in each scene
   - [NO LYRICS] marker should be used to indicate that the scene has no lyrics."""
            
            # Prepare lyrics block for prompt (scene-timestamped if available)
            scene_lyrics_block = scene_lyrics_info.strip() if scene_lyrics_info and scene_lyrics_info.strip() else 'No timestamped lyrics available'

            # Build improved prompt with clear structure and best practices
            prompt = f"""Generate {num_scenes} music video scene prompts for a {song_duration:.1f} second song ({seconds_per_video}s per scene).

<SONG_INFO>
Title: {full_song_name if full_song_name else song_name}
Artist: {persona_name}
Style: {merged_style if merged_style else 'Not specified'}
</SONG_INFO>
"""
            if storyboard_theme:
                prompt += f"""
<STORY_THEME>
This is the global image/story style that must be prepended to EVERY scene prompt.
THEME PREFIX: {storyboard_theme}
Start every scene with this prefix as the general image aesthetic, then add the scene-specific description so all scenes share the same tone.
</STORY_THEME>
"""

            prompt += f"""
<PERSONA_REFERENCE>
Use ONLY when persona appears (~{persona_scene_percent}% of scenes). Keep references brief - just "{persona_name}" or "the artist".
Visual: {visual_aesthetic if visual_aesthetic else 'N/A'}
Look: {base_image_prompt if base_image_prompt else 'N/A'}
Vibe: {vibe if vibe else 'N/A'}
DIALOGUE FOR VIDEO: When persona appears AND the scene has lyrics in LYRICS_TIMING, you MUST add "DIALOGUE: [exact scene lyrics]" so video generation can lip-sync. Use ONLY the lyrics for that scene's time range - never lyrics from other scenes.
Never add DIALOGUE to [NO CHARACTERS] or No persona present scenes - there is no character to sing.
When persona has lyrics: avoid "silent", "mute", "no dialogue", "not speaking" - use "singing", "lips moving", "performing", "mouthing the words".
</PERSONA_REFERENCE>

<LYRICS>
{scene_lyrics_block}
</LYRICS>
"""
            if scene_lyrics_within_info:
                prompt += scene_lyrics_within_info
            prompt += """

LYRIC EVENTS DRIVE SCENES: Each scene corresponds to a specific time range. Use LYRICS_TIMING to align visual events with lyric content. Important lyric lines should drive the visual narrative for their time window. Treat lyric events as anchors for scene content (mood, imagery, dialogue).

<RULES priority="high-to-low">
1. CONTINUOUS STORY NARRATIVE: Create a FLOWING, CONNECTED story across ALL scenes. This is not just individual lyric visualizations - it's ONE continuous narrative journey.
   - Each scene must build on the previous scene and set up the next scene
   - Create visual continuity: objects, locations, or elements from earlier scenes should reappear or evolve in later scenes
   - Build a story thread that connects beginning to end - like chapters in a book
   - Scenes should feel like a sequence, not isolated moments
   - Use visual callbacks: reference elements from previous scenes (a broken drum, a crossroads, a neon sign) to create narrative flow
   - The story should progress logically: discovery → conflict → struggle → resolution
   - Think of it as a visual journey where each scene is a step forward in the story

2. NARRATIVE ARC: Build a visual story following the song's emotional journey (intro-build-climax-resolution). Each scene advances the narrative AND connects to the overall story thread.

3. SCENE DISTRIBUTION:
   - ~{no_persona_percent}% abstract/environmental scenes (mark with "[NO CHARACTERS]" at start)
   - ~{persona_scene_percent}% persona scenes (never consecutive)
   - Abstract scenes: purely environmental, symbolic, atmospheric - zero human figures
   - STORY CHARACTERS: You may introduce 1-2 story characters (distinct from the persona) that fit naturally into the narrative. These characters should serve the story, match the theme, and appear organically as part of the continuous narrative. Use them sparingly and purposefully - they should enhance the story, not distract from it. Mark scenes with story characters (not persona) clearly.

4. DISTINCT SETUPS: Use only {storyboard_setup_count} unique visual setups (industry sweet spot is 3-4).
   - A setup = location + lighting + base composition. You may "cheat" by re-lighting a corner to create multiple looks.
   - Reuse these setups by changing shot type, angle, lens, blocking, props, and motion. Do NOT introduce new locations beyond the {storyboard_setup_count} setups.
   - Highlight high-energy sections (hooks/chorus) by swapping to the most striking setup; return to calmer setups for verses/outro.
   - Assign EACH setup its own base color palette family (e.g., warm amber/gold, teal+orange, indigo+silver, coral+violet, sepia+turquoise). Keep a setup’s base palette when revisiting it (small lighting/accent shifts are fine), but ensure different setups use different hue families. If the global theme leans green, only one setup may stay green; the others must use clearly different palettes (warm/cool/neon/dusk contrasts). This prevents all scenes from defaulting to the same green tone.

5. VISUAL VARIETY: Every scene must differ significantly:
   - Rotate shot types: extreme close-up, medium, wide, aerial, macro
   - Alternate: dark/light, warm/cool, organic/geometric, static/dynamic
   - Vary: angles, lighting, textures, settings, color palettes

6. PERSONA VARIETY: When persona appears, change everything:
   - Different pose, expression, camera angle, lighting, setting each time
   - Brief mention only - focus on scene, not persona details
   - For persona scenes WITH lyrics: include "DIALOGUE: [exact lyrics for this scene]" - required for video lip-sync. Do NOT use "silent", "mute", or "no dialogue" when lyrics exist; use "singing", "lips moving", or "performing"

7. LYRICS INTEGRATION:"""
            prompt += lyrics_rule
            
            prompt += f"""

8. GLOBAL THEME:
   - Begin EVERY scene description with the theme prefix: {storyboard_theme if storyboard_theme else '[If no theme is set, skip this prefix]'}
   - Treat this as the overall image aesthetic; keep visuals aligned with it across all scenes

9. CONTENT SAFETY (use these alternatives):
   - "black" -> "dark", "shadowy", "charcoal"
   - "void" -> "vast emptiness", "expansive darkness"  
   - "praying" -> "pleading", "hoping", "seeking"
   - Avoid violent/forceful language - use artistic alternatives

10. COMPOSITION FOR PERSONA (when present):
   - Embed the persona into the environment; do NOT default to centering them
   - Place them where the scene reads best (left/right third, foreground or background, over-shoulder, partial silhouette, small-in-frame, or cropped)
   - Choose the strongest composition for the shot; only center if it clearly benefits the scene
</RULES>

<OUTPUT_FORMAT>
IMPORTANT: SAMPLE FORMAT ONLY. DO NOT COPY ANY SAMPLE TEXT INTO THE ACTUAL OUTPUT.
Start immediately with SCENE 1. No preamble or questions.
"""
            # Add multi-scene format instructions if enabled
            if is_multiscene and is_ai_decides_subscene:
                prompt += f"""
=== MULTI-SCENE MODE (AI-decided sub-scene cuts) ===
Each video segment is exactly {seconds_per_video} seconds. YOU decide how to split it into sub-scenes.
- Each sub-scene must be between {min_subscene_seconds} and {max_subscene_seconds} seconds.
- Sub-scenes must sum to exactly {seconds_per_video}s. Use LYRICS_WITHIN_SCENE to place cuts at important lyric moments (chorus, key phrases, emotional peaks).
- Use DIRECT CAMERA CUTS between sub-scenes (NO smooth transitions, NO fades, NO morphing).
- Each sub-scene must be visually distinct but thematically connected.
- The persona/character must appear consistently across sub-scenes when present.
- When a character appears in a sub-scene, use CHARACTER: persona or CHARACTER: [story_character_id] - full descriptions go in STORYBOARD_METADATA.
- When persona appears and scene has lyrics, add: DIALOGUE: [exact lyrics for this scene from LYRICS_TIMING].

CRITICAL FOR VIDEO GENERATION: When persona or any story character appears in ANY scene, you MUST include the persona in SCENE 1.

IMPORTANT FOR IMAGE GENERATION:
- When generating an IMAGE (not video), use ONLY the FIRST sub-scene [0s-Xs]
- Generate exactly ONE single image - NOT a collage or multi-panel layout

Format each scene with sub-scene timestamps, e.g.:
SCENE 1: {seconds_per_video} seconds total
  [0s-Xs] Sub-scene 1: [description]
  [Xs-Ys] Sub-scene 2: [description]
  ...
  (sub-scenes must sum to {seconds_per_video}s)

...continue through SCENE {num_scenes}...
"""
            elif is_multiscene and subscenes_per_video > 1:
                prompt += f"""
=== MULTI-SCENE MODE ({scene_duration}s sub-scenes) ===
Each video segment ({seconds_per_video}s) contains {subscenes_per_video} sub-scenes of {scene_duration} seconds each.
Use DIRECT CAMERA CUTS between sub-scenes (NO smooth transitions, NO fades, NO morphing).
Each sub-scene must be visually distinct but thematically connected.
The persona/character must appear consistently across sub-scenes when present.
When a character appears in a sub-scene, use CHARACTER: persona or CHARACTER: [story_character_id] (e.g. mysterious_figure) - full appearance descriptions go in the STORYBOARD_METADATA block at the end.
When persona appears and scene has lyrics, add: DIALOGUE: [exact lyrics for this scene from LYRICS_TIMING].

CRITICAL FOR VIDEO GENERATION: When persona or any story character appears in ANY scene, you MUST include the persona in SCENE 1. Scene 1's image is the reference for the video generator - if persona appears only in later scenes, the video generator will lack a reference image and cannot render the character correctly.

IMPORTANT FOR IMAGE GENERATION:
- When generating an IMAGE (not video) from these prompts, use ONLY the FIRST sub-scene [0s-{scene_duration}s]
- Generate exactly ONE single image - NOT a collage, triptych, or multi-panel layout
- The sub-scene timestamps are for VIDEO sequencing; for IMAGE, focus on one unified composition

SCENE 1: {seconds_per_video} seconds total"""
                for sub in range(subscenes_per_video):
                    sub_start = sub * scene_duration
                    sub_end = sub_start + scene_duration
                    prompt += f"""
  [{sub_start}s-{sub_end}s] Sub-scene {sub + 1}: [describe this {scene_duration}s segment with distinct camera angle/composition]"""
                prompt += f"""

SCENE 2: {seconds_per_video} seconds total"""
                for sub in range(subscenes_per_video):
                    sub_start = sub * scene_duration
                    sub_end = sub_start + scene_duration
                    prompt += f"""
  [{sub_start}s-{sub_end}s] Sub-scene {sub + 1}: [different shot type and palette from Scene 1]"""
                prompt += f"""

...continue through SCENE {num_scenes}...
"""
            else:
                prompt += f"""
SCENE 1: {seconds_per_video} seconds
[NO CHARACTERS] [If LYRICS_TIMING shows [NO LYRICS] for this scene, leave it text-free and do NOT invent or embed any lyrics.]

SCENE 2: {seconds_per_video} seconds
[NO CHARACTERS] [Detailed abstract/environmental scene - atmospheric visuals, symbolic imagery, no human figures. Different shot type and palette from Scene 1.]

...continue through SCENE {num_scenes}...
"""
            prompt += """</OUTPUT_FORMAT>

<EXECUTION>
- Generate ALL {num_scenes} scenes without stopping
- If response limit reached, continue in batches (1-14, 15-28, etc.)
- No questions, no options, no explanations - just scenes
- At the END of your response, after all scenes, output a <STORYBOARD_METADATA> block (see format below)
</EXECUTION>

<STORYBOARD_METADATA FORMAT>
After all scenes, append exactly this block:
<STORYBOARD_METADATA>
CHARACTERS:
- persona: [Artist/Persona name] - [full appearance: clothing, features, colors, styling]
- [story_character_id]: [label] - [full appearance for each story character you introduced]
SETUPS: (optional)
- [setup_id]: palette, location for each distinct visual setup used
</STORYBOARD_METADATA>
</STORYBOARD_METADATA FORMAT>

Begin with SCENE 1:""".format(num_scenes=num_scenes)
            
            # Enhanced system message with clear role and constraints
            system_message = f"""You are a professional music video storyboard director creating {num_scenes} scene prompts that tell ONE CONTINUOUS, FLOWING STORY.

ABSOLUTE RULES:
1. Output ONLY scene prompts in format: "SCENE X: [duration] seconds\\n[prompt]"
2. Generate ALL {num_scenes} scenes - no stopping, no questions
3. CONTINUOUS NARRATIVE: Create a flowing story where each scene builds on the previous one. Think of it as a visual journey - scenes should connect and progress like chapters in a story. Use visual callbacks (objects, locations, elements from earlier scenes) to create narrative continuity. The story should flow from beginning to end as ONE connected narrative, not isolated moments.
4. STORY CHARACTERS: You may introduce 1-2 story characters (distinct from the persona) that fit naturally into the narrative. These characters should serve the story purpose, match the theme/aesthetic, and appear organically as the story progresses. Use them sparingly and purposefully - they should enhance the narrative flow, not distract. Examples: a mysterious figure, a lost soul, a companion, an antagonist, a symbolic character. When introducing story characters, describe them briefly and ensure they fit the visual aesthetic and story theme.
5. ~{no_persona_percent}% of scenes must be [NO CHARACTERS] - purely environmental/abstract. ~{persona_scene_percent}% persona scenes (non-consecutive).
6. Use only {storyboard_setup_count} distinct setups (location + lighting). Rotate through them; do NOT introduce new setups beyond this count.
7. Every scene must be visually distinct from all others (change shot type/angle/light/palette). No two consecutive scenes may share the same palette + setup combination; change palette OR lighting OR shot type between adjacent scenes.
8. Keep modern pacing: think 2-4 second shots; refresh visuals on section changes (verse/chorus/bridge) using the strongest setups for hooks.
9. If hitting response limits, batch output (scenes 1-14, then 15-28, etc.)
"""
            next_rule_num = 10
            if storyboard_theme:
                system_message += f"{next_rule_num}. Every scene prompt must START with this theme prefix before anything else: {storyboard_theme}\n"
                next_rule_num += 1
            system_message += f"{next_rule_num}. Target persona presence: about {persona_scene_percent}% of scenes (non-consecutive). Maintain variety.\n"
            next_rule_num += 1
            system_message += f"{next_rule_num}. When persona appears, avoid default centering. Embed them in the environment and pick the best composition (rule of thirds, foreground/background, over-shoulder, partial silhouette, small-in-frame, or cropped). Center only if it clearly strengthens the shot.\n"
            next_rule_num += 1
            system_message += f"{next_rule_num}. When persona appears with lyrics: NEVER use 'silent', 'mute', 'no dialogue', or 'not speaking'. Use 'singing', 'lips moving', 'performing', or 'mouthing the words' instead.\n"
            next_rule_num += 1
            video_style = (self.storyboard_video_style_var.get() or 'Realism').strip() if hasattr(self, 'storyboard_video_style_var') else 'Realism'
            if video_style == 'Realism':
                system_message += f"{next_rule_num}. VIDEO REALISM: NEVER: dissolve, melt, morph, \"like [abstract]\". USE: fade, step into, static shot, hard cut.\n"
            elif video_style == 'Surrealism':
                system_message += f"{next_rule_num}. VIDEO SURREALISM: USE: dissolve, morph, blend. NEVER: vague \"something emerges\". Write explicit surreal transitions.\n"
            elif video_style == 'Artistic':
                system_message += f"{next_rule_num}. VIDEO ARTISTIC: PREFER: fade/transition. Use \"dissolve\" only when intentional. NEVER: empty frame holds, order emerges.\n"
            elif video_style == 'Dreamlike':
                system_message += f"{next_rule_num}. VIDEO DREAMLIKE: USE: soft dissolve, subtle morph. NEVER: jarring abstract (order emerges, empty frame holds).\n"
            elif video_style == 'Cinematic':
                system_message += f"{next_rule_num}. VIDEO CINEMATIC: USE: filmic terms. NEVER: empty frame holds, order emerges, uncontrolled morphing.\n"
            else:
                system_message += f"{next_rule_num}. VIDEO STYLE ({video_style}): Follow the prompt guidelines for this style.\n"
            next_rule_num += 1

            # Add multi-scene rules to system message if enabled
            if is_multiscene and is_ai_decides_subscene:
                system_message += f"""{next_rule_num}. MULTI-SCENE MODE (AI-decided): Each {seconds_per_video}s scene must be split into sub-scenes of {min_subscene_seconds}-{max_subscene_seconds}s each. Sub-scenes must sum to exactly {seconds_per_video}s.
   - Use LYRICS_WITHIN_SCENE to place sub-scene boundaries at important lyric moments (chorus, key phrases, emotional peaks)
   - Format each scene with sub-scene timestamps: [0s-Xs], [Xs-Ys], etc. You decide X, Y based on lyrics
   - Use DIRECT CAMERA CUTS between sub-scenes (NO smooth transitions, NO fades, NO morphing)
   - Each sub-scene must have a different camera angle, composition, or framing
   - The persona/character must appear consistently across sub-scenes when present
   - When a character appears in a sub-scene, use CHARACTER: persona or CHARACTER: [story_character_id] - full descriptions go in STORYBOARD_METADATA
   - CRITICAL: When persona or any story character appears in ANY scene, you MUST include the persona in SCENE 1.
"""
            elif is_multiscene and subscenes_per_video > 1:
                system_message += f"""{next_rule_num}. MULTI-SCENE MODE: Each {seconds_per_video}s scene must contain {subscenes_per_video} sub-scenes of {scene_duration}s each.
   - Format each scene with sub-scene timestamps: [0s-{scene_duration}s], [{scene_duration}s-{scene_duration*2}s], etc.
   - Use DIRECT CAMERA CUTS between sub-scenes (NO smooth transitions, NO fades, NO morphing)
   - Each sub-scene must have a different camera angle, composition, or framing
   - The persona/character must appear consistently across sub-scenes when present
   - When a character appears in a sub-scene, use CHARACTER: persona or CHARACTER: [story_character_id] so descriptions can be looked up - full descriptions go in STORYBOARD_METADATA
   - Sub-scenes should feel dynamic and match the music energy
   - CRITICAL: When persona or any story character appears in ANY scene, you MUST include the persona in SCENE 1. Scene 1's image is the reference for the video generator - if persona appears only in later scenes, the video generator will lack a reference image and cannot render the character correctly.
"""
            system_message += f"""

Start immediately with "SCENE 1:" - no introduction or commentary."""
            
            # Calculate estimated tokens needed (rough estimate: ~100 tokens per scene)
            # song_duration and num_scenes already calculated above
            estimated_tokens = num_scenes * 100  # ~100 tokens per scene
            
            # Use much higher token limit for storyboard generation
            # GPT-4/5 models support 8k, 16k, 32k, 64k, or 128k tokens depending on model
            # For storyboard generation, use up to 64k tokens to handle very long songs
            # Add generous buffer: estimated + 50% buffer, minimum 8000, maximum 64000
            max_tokens = min(max(int(estimated_tokens * 1.5), 8000), 64000)
            self.log_debug('INFO', f'Using max_tokens: {max_tokens} for {num_scenes} scenes (estimated: {estimated_tokens} tokens)')
            self.log_debug('DEBUG', f'Storyboard prompt (about to send):\n{"="*80}\n{prompt}\n{"="*80}')
            self.save_storyboard_prompt(
                prompt,
                seconds_per_video,
                {
                    'mode': 'single',
                    'num_scenes': num_scenes,
                    'seconds_per_video': seconds_per_video,
                    'multiscene': is_multiscene,
                    'scene_duration': scene_duration if is_multiscene else None,
                    'subscenes_per_video': subscenes_per_video if is_multiscene else None
                }
            )
            
            result = self.azure_ai(prompt, system_message=system_message, profile='text', max_tokens=max_tokens, temperature=1)
            
            if result['success']:
                content = result['content'].strip()
                self.log_debug('INFO', f'Received storyboard response (length: {len(content)} chars)')
                
                # Always log full AI response for debugging
                self.log_debug('DEBUG', f'Full AI response:\n{"="*80}\n{content}\n{"="*80}')
                # Also surface the storyboard prompts in debug for quick review
                self.log_debug('DEBUG', f'Storyboard prompts (latest response):\n{content}')

                # Persist raw response for auditing
                self.save_storyboard_raw_response(
                    content,
                    seconds_per_video,
                    {
                        'mode': 'single',
                        'num_scenes': num_scenes,
                        'seconds_per_video': seconds_per_video
                    }
                )
                
                if not content:
                    self.log_debug('ERROR', 'Storyboard response is empty!')
                    messagebox.showerror('Error', 'Storyboard generation returned empty content.')
                    return
                
                # Check if AI refused to generate scenes (asked questions instead or hit length limit)
                refusal_keywords = ['choose one option', 'which option', 'multiple parts', 'exceeds', 'too long', 'would you like', 
                                   "can't generate", "cannot generate", "response of that length", "too many", "limit", 
                                   "begin scenes", "confirm", "sequential messages", "multiple sequential"]
                content_lower = content.lower()
                has_scenes = 'SCENE 1:' in content.upper() or 'SCENE 1' in content.upper()
                
                # Check if AI is asking for batch confirmation
                asking_for_batch = any(keyword in content_lower for keyword in ['begin scenes', 'confirm', 'sequential messages', 'multiple sequential', 'message 1', 'message 2', 'message 3'])
                
                if asking_for_batch and not has_scenes:
                    self.log_debug('INFO', 'AI requested batch generation - automatically generating in batches')
                    # Automatically generate in batches
                    song_duration = self.get_mp3_duration(mp3_path)
                    num_scenes = int(song_duration / seconds_per_video) + (1 if song_duration % seconds_per_video > 0 else 0)
                    
                    # Generate in batches of ~14 scenes each
                    batch_size = 14
                    all_scenes_content = []
                    
                    for batch_start in range(1, num_scenes + 1, batch_size):
                        batch_end = min(batch_start + batch_size - 1, num_scenes)
                        self.log_debug('INFO', f'Generating batch: Scenes {batch_start}-{batch_end} of {num_scenes}')
                        
                        # Create batch-specific prompt
                        batch_prompt = self._create_batch_storyboard_prompt(
                            song_name, full_song_name, lyrics, merged_style, storyboard_theme, persona_scene_percent, storyboard_setup_count, persona_name,
                            visual_aesthetic, base_image_prompt, vibe, lyric_segments,
                            song_duration, seconds_per_video, batch_start, batch_end, num_scenes
                        )
                        self.log_debug('DEBUG', f'Storyboard prompt batch {batch_start}-{batch_end} (about to send):\n{"="*80}\n{batch_prompt[:4000]}\n{"="*80}')
                        self.save_storyboard_prompt(
                            batch_prompt,
                            seconds_per_video,
                            {
                                'mode': 'batch',
                                'batch_start': batch_start,
                                'batch_end': batch_end,
                                'num_scenes': num_scenes,
                                'seconds_per_video': seconds_per_video
                            }
                        )
                        
                        batch_result = self.azure_ai(batch_prompt, system_message=system_message, profile='text', max_tokens=max_tokens, temperature=1)
                        
                        if batch_result['success']:
                            batch_content = batch_result['content'].strip()
                            self.log_debug('DEBUG', f'Batch {batch_start}-{batch_end} response (length: {len(batch_content)} chars)')
                            self.log_debug('DEBUG', f'Storyboard prompts batch {batch_start}-{batch_end}:\n{batch_content}')
                            self.save_storyboard_raw_response(
                                batch_content,
                                seconds_per_video,
                                {
                                    'mode': 'batch',
                                    'batch_start': batch_start,
                                    'batch_end': batch_end,
                                    'num_scenes': num_scenes,
                                    'seconds_per_video': seconds_per_video
                                }
                            )
                            all_scenes_content.append(batch_content)
                        else:
                            self.log_debug('ERROR', f'Batch {batch_start}-{batch_end} failed: {batch_result["error"]}')
                            messagebox.showerror('Error', f'Failed to generate batch {batch_start}-{batch_end}: {batch_result["error"]}')
                            return
                    
                    # Combine all batches
                    combined_content = '\n\n'.join(all_scenes_content)
                    self.log_debug('INFO', f'Combined all batches (total length: {len(combined_content)} chars)')
                    self.parse_storyboard_response(combined_content, seconds_per_video)
                    self.save_song()
                    self.log_debug('INFO', 'Storyboard generated successfully in batches')
                    return
                
                if any(keyword in content_lower for keyword in refusal_keywords) and not has_scenes and not asking_for_batch:
                    self.log_debug('ERROR', 'AI refused to generate scenes due to length limit')
                    
                    # Calculate how many scenes would be needed
                    song_duration = self.get_mp3_duration(mp3_path)
                    num_scenes = int(song_duration / seconds_per_video) + (1 if song_duration % seconds_per_video > 0 else 0)
                    
                    # Suggest increasing seconds per video to reduce scene count
                    suggested_seconds = max(seconds_per_video + 2, int(song_duration / 30))  # Aim for ~30 scenes max
                    
                    error_msg = f'The AI cannot generate all {num_scenes} scenes in one response (song is {song_duration:.0f} seconds).\n\n'
                    error_msg += f'Current setting: {seconds_per_video} seconds per scene = {num_scenes} scenes\n\n'
                    error_msg += f'Solution: Increase "Seconds per video" to {suggested_seconds} or higher '
                    error_msg += f'to create fewer scenes (approximately {int(song_duration / suggested_seconds)} scenes).\n\n'
                    error_msg += f'AI Response: {content}'
                    messagebox.showerror('Error - Too Many Scenes', error_msg)
                    return
                
                combined_content = self.ensure_complete_storyboard_response(
                    content, song_name, full_song_name, lyrics, merged_style, storyboard_theme, persona_scene_percent, storyboard_setup_count, persona_name,
                    visual_aesthetic, base_image_prompt, vibe, lyric_segments,
                    song_duration, seconds_per_video, num_scenes, system_message, max_tokens
                )
                if not combined_content:
                    return
                
                self.parse_storyboard_response(combined_content, seconds_per_video)
                self.save_song()
                self.log_debug('INFO', 'Storyboard generated successfully')
            else:
                messagebox.showerror('Error', f'Failed to generate storyboard: {result["error"]}')
                self.log_debug('ERROR', f'Failed to generate storyboard: {result["error"]}')
        except Exception as e:
            messagebox.showerror('Error', f'Error generating storyboard: {e}')
            self.log_debug('ERROR', f'Error generating storyboard: {e}')
        finally:
            self.config(cursor='')
    
    def _create_batch_storyboard_prompt(self, song_name, full_song_name, lyrics, merged_style, storyboard_theme, persona_scene_percent, storyboard_setup_count, persona_name,
                                        visual_aesthetic, base_image_prompt, vibe, lyric_segments,
                                        song_duration, seconds_per_video, batch_start, batch_end, total_scenes):
        """Create a prompt for generating a specific batch of scenes."""
        embed_lyrics = bool(self.embed_lyrics_var.get()) if hasattr(self, 'embed_lyrics_var') else True
        # Check multi-scene settings
        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
        is_ai_decides_subscene = self.storyboard_ai_decides_subscene_var.get() if hasattr(self, 'storyboard_ai_decides_subscene_var') else False
        try:
            scene_duration = int(self.storyboard_scene_duration_var.get() or 2) if hasattr(self, 'storyboard_scene_duration_var') else 2
        except Exception:
            scene_duration = 2
        scene_duration = max(1, min(10, scene_duration))
        min_subscene_seconds = scene_duration
        max_subscene_seconds = seconds_per_video
        if is_multiscene and is_ai_decides_subscene:
            subscenes_per_video = 0
        else:
            subscenes_per_video = seconds_per_video // scene_duration if is_multiscene and scene_duration > 0 else 1

        prompt = f"Generate ONLY scenes {batch_start} through {batch_end} (out of {total_scenes} total scenes) for this music video storyboard.\n\n"
        prompt += f"Song: {full_song_name if full_song_name else song_name}\n"
        prompt += f"Artist/Persona: {persona_name}\n"
        if lyrics:
            prompt += f"Lyrics:\n{lyrics}\n\n"
        if merged_style:
            prompt += f"Style: {merged_style}\n\n"
        if storyboard_theme:
            prompt += f"GLOBAL STORY THEME (prepend to every scene): {storyboard_theme}\n"
            prompt += "Every scene description must start with this theme text, then add scene specifics.\n\n"
        prompt += f"Target persona presence: about {persona_scene_percent}% of scenes (non-consecutive). Keep plenty of non-persona scenes for variety.\n\n"
        prompt += f"Use only {storyboard_setup_count} distinct visual setups (location + lighting). Rotate through them; do NOT add more setups. You may 'cheat' by relighting a corner to make multiple looks. Use the most striking setup for hooks/chorus; calmer setups for verses/outro.\n"
        prompt += "Keep modern pacing: imagine 2-4 second shots and refresh visuals on section changes.\n"
        prompt += (
            "COLOR VARIATION: Each scene MUST include a COLOR PALETTE line and rotate distinct palettes across scenes. "
            "Do NOT reuse the same base palette in consecutive scenes; avoid repeating the previous two palettes. "
            "Examples: teal+orange neon, warm amber dusk, cool moonlit blue, crimson/gold stage, pastel haze, emerald+violet, silver+magenta, sepia+turquoise. "
            f"Assign each of the {storyboard_setup_count} setups its own base palette family (e.g., warm, cool, neon, dusk). When you revisit a setup, keep its base palette but you may tweak lighting accents. If the global theme suggests green, limit green to a single setup and force other setups into contrasting palettes (warm/cool/neon/dusk) so the storyboard is not all green. "
            "Keep a palette consistent within a scene but shift between scenes while fitting the theme and lyrics mood.\n\n"
        )
        prompt += (
            "CONSECUTIVE VARIATION: No two consecutive scenes may reuse the same palette AND setup combination. "
            "If a location repeats, change the lighting, camera angle, and palette. "
            "Always change at least one of: palette, lighting, shot type, or focal subject between adjacent scenes.\n\n"
        )
        
        # Include persona visual description only as reference (not for every scene)
        prompt += "\nPERSONA REFERENCE (only use when persona appears in scenes - see requirements below):\n"
        if visual_aesthetic:
            prompt += f"Visual Aesthetic: {visual_aesthetic}\n"
        if base_image_prompt:
            prompt += f"Character Description: {base_image_prompt}\n"
        if vibe:
            prompt += f"Vibe: {vibe}\n"
        prompt += "\n"
        
        # Add lyrics timing for this batch only
        scene_lyrics_info = ""
        scene_lyrics_dict = {}  # Store lyrics for each scene number in this batch
        if lyric_segments and song_duration > 0:
            scene_lyrics_info = "\n\nLYRICS TIMING FOR THIS BATCH (use ONLY lyrics that match each scene's time):\n"
            current_time = (batch_start - 1) * seconds_per_video
            for scene_idx in range(batch_start, batch_end + 1):
                scene_start_time = current_time
                scene_end_time = min(current_time + seconds_per_video, song_duration)
                scene_lyrics = self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments)
                scene_lyrics_info += f"Scene {scene_idx} ({scene_start_time:.1f}s - {scene_end_time:.1f}s): {scene_lyrics if scene_lyrics else '[NO LYRICS]'}\n"
                if scene_lyrics:
                    scene_lyrics_dict[scene_idx] = scene_lyrics
                current_time = scene_end_time
                if current_time >= song_duration:
                    break
            scene_lyrics_info += "\nCRITICAL: For scenes marked [NO LYRICS], do NOT embed any lyric text. Keep those scenes text-free.\n"
            prompt += scene_lyrics_info
        
        prompt += f"STORYBOARD THEME: '{full_song_name if full_song_name else song_name}'\n"
        prompt += "FOCUS ON THE SONG THEME, LYRICS, AND MOOD - not the persona. Use the song title and lyrics as the primary inspiration.\n\n"
        prompt += "CRITICAL - CONTINUOUS NARRATIVE: This is part of a larger story. Create scenes that flow and connect:\n"
        prompt += "- Each scene should build on previous scenes and set up future scenes\n"
        prompt += "- Use visual callbacks: reference objects, locations, or elements from earlier scenes to create narrative continuity\n"
        prompt += "- Think of this as ONE continuous story journey, not isolated moments\n"
        prompt += "- If this is a later batch (scenes 15+), reference elements from earlier scenes (the broken drum, the crossroads, the neon sign, etc.) to maintain story flow\n"
        prompt += "- The story should progress logically: each scene is a step forward in the narrative\n\n"
        prompt += "STORY CHARACTERS: You may introduce 1-2 story characters (distinct from the persona) that fit naturally into the narrative. These characters should serve the story purpose, match the theme/aesthetic, and appear organically as the story progresses. Use them sparingly and purposefully - they should enhance the narrative flow, not distract. Examples: a mysterious figure, a lost soul, a companion, an antagonist, a symbolic character. When introducing story characters, describe them briefly and ensure they fit the visual aesthetic and story theme. If story characters were introduced in earlier scenes, you may reference or continue their story thread.\n\n"
        prompt += f"The persona ({persona_name}) should only appear in about {persona_scene_percent}% of scenes. When the persona appears, keep descriptions brief - just mention '{persona_name}' or 'the artist'. Do NOT repeat full persona descriptions.\n"
        prompt += "CRITICAL: When a prompt says 'No persona present. No characters. No human figures. No artist. No people.', the generated image MUST NOT include ANY human figures. These scenes should be purely environmental, abstract, symbolic, or atmospheric visuals. However, story characters (distinct from persona) may appear in scenes if they serve the narrative - just ensure they are clearly story characters, not the persona.\n"
        prompt += "CONTENT SAFETY: All scene prompts MUST be safe for content moderation. Use creative alternatives: 'dark' instead of 'black', 'empty space' instead of 'void', 'curving' instead of 'bending under force', 'pleading' instead of 'praying'. Focus on visual poetry and atmosphere.\n\n"
        if scene_lyrics_info:
            if batch_start > 1:
                prompt += f"STORY CONTINUITY NOTE: You are generating scenes {batch_start}-{batch_end} of a {total_scenes}-scene story. Previous scenes have established the narrative world, locations, and story elements. Continue the story thread - reference or evolve elements from earlier scenes to maintain narrative flow.\n\n"
            prompt += f"CRITICAL: Generate ONLY scenes {batch_start} through {batch_end}. For EACH scene, you MUST:\n"
            if embed_lyrics:
                prompt += "1. Include the exact lyrics that play during that scene's time period (from LYRICS TIMING section above)\n"
                prompt += "2. Format: SCENE X: [duration] seconds\nLYRICS FOR THIS SCENE: \"[exact lyrics text]\"\nCRITICAL INSTRUCTIONS FOR THIS SCENE:\n"
                prompt += f"   a. ~{100 - persona_scene_percent}% of scenes MUST NOT include the persona. If this is a scene WITHOUT the persona AND without story characters, you MUST start the scene prompt with 'No persona present. No characters. No human figures. No artist. No people.' and create a purely abstract, environmental, symbolic, or atmospheric visual that represents the lyrics WITHOUT any human presence. However, if a story character (distinct from persona) fits naturally into this scene and serves the narrative, you may include them - but mark it clearly as a story character scene, not a persona scene.\n"
                prompt += "   b. The image must visually represent and incorporate the lyrics above - include visual elements that match what the lyrics describe\n"
                prompt += "   c. The lyrics text MUST be embedded and integrated into the scene and background, merging seamlessly with the surroundings. The lyrics should appear as part of the environment - written on surfaces, integrated into textures, blended into the background, appearing on signs/walls/objects in the scene, or woven into the visual design itself. They should NOT appear as a floating text overlay, but rather as an organic part of the scene that merges with the background and surroundings\n"
                prompt += "   d. Format the image prompt to include: [visual description] + \"with the lyrics text '[exact lyrics]' embedded INTO THE ENVIRONMENT ONLY (e.g., carved into walls, glowing in neon signs, written on objects, formed by patterns, integrated into textures) - NO text overlays, NO bottom bars, NO subtitles, NO floating text\"\n"
                prompt += "3. The image prompt MUST directly incorporate and visualize what the lyrics describe AND include instructions to embed the lyrics text into the scene design, merging with the background and surroundings\n"
                prompt += "4. CRITICAL: When a scene prompt starts with 'No persona present', the generated image MUST be completely free of ANY human figures, characters, or people. Only environmental, abstract, symbolic, or atmospheric elements should be present.\n"
                prompt += "5. DIALOGUE FOR VIDEO: When persona (CHARACTER: persona) appears in a scene that has lyrics: you MUST add \"DIALOGUE: [exact lyrics for this scene from LYRICS TIMING]\" for video lip-sync. Use ONLY the lyrics matching that scene's time range. Never add DIALOGUE to scenes marked \"No persona present\" or \"[NO CHARACTERS]\" - there is no character to sing.\n"
            else:
                prompt += "1. Include the lyrics that play during that scene's time period for MOOD REFERENCE ONLY (from LYRICS TIMING section above)\n"
                prompt += "2. Format: SCENE X: [duration] seconds\nLYRICS FOR THIS SCENE (mood reference only): \"[exact lyrics text]\"\nCRITICAL INSTRUCTIONS FOR THIS SCENE:\n"
                prompt += f"   a. ~{100 - persona_scene_percent}% of scenes MUST NOT include the persona. If this is a scene WITHOUT the persona AND without story characters, you MUST start the scene prompt with 'No persona present. No characters. No human figures. No artist. No people.' and create a purely abstract, environmental, symbolic, or atmospheric visual that represents the lyrics WITHOUT any human presence. However, if a story character (distinct from persona) fits naturally into this scene and serves the narrative, you may include them - but mark it clearly as a story character scene, not a persona scene.\n"
                prompt += "   b. Do NOT render or embed any visible text or lyrics in the scene. Keep all scenes text-free (no overlays, no environmental text)\n"
                prompt += "   c. Use the feeling of the lyrics to shape lighting, color, and symbolism only - convey the mood and meaning through visuals, not through displayed text\n"
                prompt += "   d. The image prompt MUST visually represent the lyrics' mood and meaning through atmosphere, color, lighting, and symbolic imagery - NO visible lyric text anywhere in the scene\n"
                prompt += "3. CRITICAL: When a scene prompt starts with 'No persona present', the generated image MUST be completely free of ANY human figures, characters, or people. Only environmental, abstract, symbolic, or atmospheric elements should be present.\n"
                prompt += "4. DIALOGUE FOR VIDEO: When persona (CHARACTER: persona) appears in a scene that has lyrics: you MUST add \"DIALOGUE: [exact lyrics for this scene from LYRICS TIMING]\" for video lip-sync. Use ONLY the lyrics matching that scene's time range. Never add DIALOGUE to scenes marked \"No persona present\" or \"[NO CHARACTERS]\" - there is no character to sing.\n"
            prompt += f"Start immediately with SCENE {batch_start}:, no preamble, no explanations.\n\n"
        else:
            prompt += f"CRITICAL: Generate ONLY scenes {batch_start} through {batch_end}. Start immediately with SCENE {batch_start}:, no preamble, no explanations.\n\n"
        prompt += "Output format (must include COLOR PALETTE before each scene prompt):\n"
        if scene_lyrics_info:
            # Include actual lyrics in the format examples
            scene1_lyrics = scene_lyrics_dict.get(batch_start, '')
            scene2_lyrics = scene_lyrics_dict.get(batch_start + 1, '') if batch_start < batch_end else ''
            
            if scene1_lyrics:
                if embed_lyrics:
                    prompt += f"SCENE {batch_start}: [duration] seconds\nLYRICS FOR THIS SCENE: \"{scene1_lyrics}\"\nCOLOR PALETTE: [distinct palette for this scene]\n"
                    prompt += "CRITICAL INSTRUCTIONS FOR THIS SCENE:\n"
                    prompt += "1. CONTENT SAFETY: Use safe, artistic language. Avoid 'black' (use 'dark', 'shadowy'), 'void' (use 'empty space'), 'compressing/bending under force' (use 'curving', 'warping'), 'praying' (use 'pleading', 'hoping'). Create visually poetic prompts that pass content moderation.\n"
                    prompt += "2. The image must visually represent and incorporate the lyrics above - include visual elements that match what the lyrics describe.\n"
                    prompt += "3. CRITICAL - LYRICS EMBEDDING: The lyrics text MUST be embedded and integrated INTO THE SCENE ENVIRONMENT ONLY - written on surfaces, integrated into textures, blended into backgrounds, appearing on signs/walls/objects, or woven into the visual design. They MUST merge seamlessly with the surroundings as an organic part of the scene.\n"
                    prompt += "   - DO NOT add lyrics as text overlays, subtitles, captions, or bottom bars\n"
                    prompt += "   - DO NOT add lyrics floating on top of the image\n"
                    prompt += "   - Lyrics should ONLY appear as part of the environment itself (e.g., carved into walls, glowing in neon signs, written on objects, formed by patterns, etc.)\n"
                    prompt += "   - If lyrics cannot be naturally integrated into the environment, focus on visual representation of the lyrics' meaning instead\n"
                    prompt += f"3. Format the image prompt to include: [visual description] + \"with the lyrics text '{scene1_lyrics}' embedded INTO THE ENVIRONMENT ONLY (e.g., carved into walls, glowing in neon signs, written on objects, formed by patterns, integrated into textures) - NO text overlays, NO bottom bars, NO subtitles, NO floating text\"\n\n"
                else:
                    prompt += f"SCENE {batch_start}: [duration] seconds\nLYRICS FOR THIS SCENE (mood reference only): \"{scene1_lyrics}\"\nCOLOR PALETTE: [distinct palette for this scene]\n"
                    prompt += "Mood/symbolism only - NO visible lyric text. Use lighting, color, and symbolism to convey the lyrics' feeling. [detailed image prompt]\n\n"
            else:
                prompt += f"SCENE {batch_start}: [duration] seconds\n[NO LYRICS - do NOT embed any lyrics text]\nCOLOR PALETTE: [distinct palette for this scene]\n[detailed image prompt - mood and atmosphere only, NO lyric text, keep scene text-free]\n\n"
            
            if batch_start < batch_end:
                if scene2_lyrics:
                    if embed_lyrics:
                        prompt += f"SCENE {batch_start + 1}: [duration] seconds\nLYRICS FOR THIS SCENE: \"{scene2_lyrics}\"\nCOLOR PALETTE: [distinct palette for this scene]\n"
                        prompt += "CRITICAL INSTRUCTIONS FOR THIS SCENE:\n"
                        prompt += "1. CONTENT SAFETY: Use safe, artistic language. Avoid 'black' (use 'dark', 'shadowy'), 'void' (use 'empty space'), 'compressing/bending under force' (use 'curving', 'warping'), 'praying' (use 'pleading', 'hoping'). Create visually poetic prompts that pass content moderation.\n"
                        prompt += "2. The image must visually represent and incorporate the lyrics above - include visual elements that match what the lyrics describe.\n"
                        prompt += "3. CRITICAL - LYRICS EMBEDDING: The lyrics text MUST be embedded and integrated INTO THE SCENE ENVIRONMENT ONLY - written on surfaces, integrated into textures, blended into backgrounds, appearing on signs/walls/objects, or woven into the visual design. They MUST merge seamlessly with the surroundings as an organic part of the scene.\n"
                        prompt += "   - DO NOT add lyrics as text overlays, subtitles, captions, or bottom bars\n"
                        prompt += "   - DO NOT add lyrics floating on top of the image\n"
                        prompt += "   - Lyrics should ONLY appear as part of the environment itself (e.g., carved into walls, glowing in neon signs, written on objects, formed by patterns, etc.)\n"
                        prompt += "   - If lyrics cannot be naturally integrated into the environment, focus on visual representation of the lyrics' meaning instead\n"
                        prompt += f"4. Format the image prompt to include: [visual description] + \"with the lyrics text '{scene2_lyrics}' embedded INTO THE ENVIRONMENT ONLY (e.g., carved into walls, glowing in neon signs, written on objects, formed by patterns, integrated into textures) - NO text overlays, NO bottom bars, NO subtitles, NO floating text\"\n\n"
                    else:
                        prompt += f"SCENE {batch_start + 1}: [duration] seconds\nLYRICS FOR THIS SCENE (mood reference only): \"{scene2_lyrics}\"\nCOLOR PALETTE: [distinct palette for this scene]\n"
                        prompt += "Mood/symbolism only - NO visible lyric text. Use lighting, color, and symbolism to convey the lyrics' feeling. [detailed image prompt]\n\n"
                else:
                    prompt += f"SCENE {batch_start + 1}: [duration] seconds\n[NO LYRICS - do NOT embed any lyrics text]\nCOLOR PALETTE: [distinct palette for this scene]\n[detailed image prompt - mood and atmosphere only, NO lyric text, keep scene text-free]\n\n"
        else:
            prompt += f"SCENE {batch_start}: [duration] seconds\nCOLOR PALETTE: [distinct palette for this scene]\n[detailed image prompt]\n\n"
            if batch_start < batch_end:
                prompt += f"SCENE {batch_start + 1}: [duration] seconds\nCOLOR PALETTE: [distinct palette for this scene]\n[detailed image prompt]\n\n"
        prompt += f"(Continue through SCENE {batch_end})\n"

        # Add Video Style instructions (Realism, Surrealism, Artistic, etc.)
        video_style = (self.storyboard_video_style_var.get() or 'Realism').strip() if hasattr(self, 'storyboard_video_style_var') else 'Realism'
        prompt += self._get_video_style_instructions(video_style)
        prompt += self._get_video_style_examples(video_style)

        # Add lyrics-within-scene for AI-decided sub-scene cut alignment
        if is_multiscene and is_ai_decides_subscene and lyric_segments and song_duration > 0:
            prompt += "\n\nLYRICS_WITHIN_SCENE for sub-scene cut alignment (place cuts at important lyric moments):\n"
            current_time = (batch_start - 1) * seconds_per_video
            for scene_idx in range(batch_start, batch_end + 1):
                scene_start_time = current_time
                scene_end_time = min(current_time + seconds_per_video, song_duration)
                parts = []
                for ly_start, ly_end, ly_text in lyric_segments:
                    if ly_start < scene_end_time and ly_end > scene_start_time:
                        rel_start = max(0.0, ly_start - scene_start_time)
                        rel_end = min(seconds_per_video, ly_end - scene_start_time)
                        clean = self.sanitize_lyrics_for_prompt(ly_text)
                        if clean:
                            parts.append(f"{rel_start:.1f}s-{rel_end:.1f}s: \"{clean}\"")
                prompt += f"Scene {scene_idx} (0s-{seconds_per_video}s): " + (" | ".join(parts) if parts else "[NO LYRICS]") + "\n"
                current_time = scene_end_time
                if current_time >= song_duration:
                    break
            prompt += "\n"

        # Add multi-scene format instructions if enabled
        if is_multiscene and is_ai_decides_subscene:
            prompt += f"""
=== MULTI-SCENE MODE (AI-decided sub-scene cuts) ===
Each video segment is exactly {seconds_per_video}s. YOU decide how to split it into sub-scenes of {min_subscene_seconds}-{max_subscene_seconds}s each.
Use LYRICS_WITHIN_SCENE above to place cuts at important lyric moments. Sub-scenes must sum to exactly {seconds_per_video}s.
Format: [0s-Xs] Sub-scene 1: [description], [Xs-Ys] Sub-scene 2: ...
Use DIRECT CAMERA CUTS between sub-scenes. Each sub-scene must have a different camera angle/composition.

At the END of your response, append <STORYBOARD_METADATA> with CHARACTERS (persona + any story characters) and optionally SETUPS.
"""
        elif is_multiscene and subscenes_per_video > 1:
            prompt += f"""
=== MULTI-SCENE MODE ({scene_duration}s sub-scenes) ===
Each video segment ({seconds_per_video}s) contains {subscenes_per_video} sub-scenes of {scene_duration} seconds each.
Use DIRECT CAMERA CUTS between sub-scenes (NO smooth transitions, NO fades, NO morphing).
Each sub-scene must be visually distinct but thematically connected.
The persona/character must appear consistently across sub-scenes when present.
When a character appears in a sub-scene, use CHARACTER: persona or CHARACTER: [story_character_id] - full descriptions go in STORYBOARD_METADATA at end.
CRITICAL FOR VIDEO GENERATION: When persona or any story character appears in ANY scene in this batch, you MUST include the persona in SCENE 1 if this batch includes SCENE 1. Scene 1's image is the reference for the video generator - if persona appears only in later scenes, the video generator will lack a reference image.

CRITICAL: Format each scene with sub-scene timestamps like this:
[0s-{scene_duration}s] Sub-scene 1: [describe this {scene_duration}s segment with distinct camera angle/composition]
[{scene_duration}s-{scene_duration*2}s] Sub-scene 2: [different shot type and angle]
"""
            if subscenes_per_video > 2:
                prompt += f"[{scene_duration*2}s-{scene_duration*3}s] Sub-scene 3: [another distinct composition]\n"
            prompt += "\nEach sub-scene MUST have a different camera angle, composition, or framing.\n"
            prompt += "\nAt the END of your response, append <STORYBOARD_METADATA> with CHARACTERS (persona + any story characters in this batch) and optionally SETUPS.\n"

        return prompt

    def _get_max_scene_number_from_text(self, content: str) -> int:
        """Extract the highest scene number mentioned in the content."""
        if not content:
            return 0
        matches = re.findall(r'SCENE\s+(\d+)', content, flags=re.IGNORECASE)
        if not matches:
            return 0
        return max(int(m) for m in matches)

    def _get_all_scene_numbers_from_text(self, content: str) -> set:
        """Extract all scene numbers mentioned in the content."""
        if not content:
            return set()
        matches = re.findall(r'SCENE\s+(\d+)', content, flags=re.IGNORECASE)
        return set(int(m) for m in matches)
    
    def ensure_complete_storyboard_response(self, initial_content: str, song_name: str, full_song_name: str,
                                            lyrics: str, merged_style: str, storyboard_theme: str, persona_scene_percent: int, storyboard_setup_count: int, persona_name: str,
                                            visual_aesthetic: str, base_image_prompt: str, vibe: str,
                                            lyric_segments: list, song_duration: float, seconds_per_video: int,
                                            total_scenes: int, system_message: str, max_tokens: int) -> str | None:
        """Ensure we have prompts for all scenes by requesting additional batches if needed."""
        if not initial_content:
            return None
        
        aggregated_contents = [initial_content]
        max_scene = self._get_max_scene_number_from_text(initial_content)
        if max_scene >= total_scenes:
            return initial_content
        
        self.log_debug('INFO', f'Initial storyboard response ended at scene {max_scene} of {total_scenes}. Requesting remaining scenes automatically.')
        batch_size = 14
        safety_counter = 0
        
        while max_scene < total_scenes and safety_counter < 10:
            batch_start = max_scene + 1
            batch_end = min(batch_start + batch_size - 1, total_scenes)
            self.log_debug('INFO', f'Requesting additional scenes {batch_start}-{batch_end}')
            
            batch_prompt = self._create_batch_storyboard_prompt(
                song_name, full_song_name, lyrics, merged_style, storyboard_theme, persona_scene_percent, storyboard_setup_count, persona_name,
                visual_aesthetic, base_image_prompt, vibe, lyric_segments,
                song_duration, seconds_per_video, batch_start, batch_end, total_scenes
            )
            
            batch_result = self.azure_ai(batch_prompt, system_message=system_message, profile='text', max_tokens=max_tokens, temperature=1)
            if not batch_result['success']:
                error_msg = f'Failed to generate scenes {batch_start}-{batch_end}: {batch_result["error"]}'
                self.log_debug('ERROR', error_msg)
                messagebox.showerror('Error', error_msg)
                return None
            
            batch_content = batch_result['content'].strip()
            if not batch_content:
                error_msg = f'Failed to generate scenes {batch_start}-{batch_end}: Empty response'
                self.log_debug('ERROR', error_msg)
                messagebox.showerror('Error', error_msg)
                return None
            
            self.log_debug('DEBUG', f'Additional scenes {batch_start}-{batch_end} received (length: {len(batch_content)} chars)')
            aggregated_contents.append(batch_content)
            self.save_storyboard_raw_response(
                batch_content,
                seconds_per_video,
                {
                    'mode': 'auto_batch',
                    'batch_start': batch_start,
                    'batch_end': batch_end,
                    'num_scenes': total_scenes,
                    'seconds_per_video': seconds_per_video
                }
            )
            
            previous_max = max_scene
            new_max = self._get_max_scene_number_from_text(batch_content)
            if new_max <= previous_max:
                self.log_debug('WARNING', f'Additional response did not contain higher scene numbers (max {new_max}). Stopping to avoid infinite loop.')
                break
            max_scene = new_max
            safety_counter += 1
        
        if max_scene < total_scenes:
            error_msg = f'Storyboard still incomplete after additional requests (last scene: {max_scene}, expected: {total_scenes}).'
            self.log_debug('ERROR', error_msg)
            messagebox.showerror('Error', error_msg)
            return None

        combined_content = '\n\n'.join(aggregated_contents)
        expected_scenes = set(range(1, total_scenes + 1))
        found_scenes = self._get_all_scene_numbers_from_text(combined_content)
        missing_scenes = expected_scenes - found_scenes
        if missing_scenes:
            self.log_debug('WARNING', f'Scene gap detected: missing scene(s) {sorted(missing_scenes)}. Some scenes may not parse correctly.')
        self.log_debug('INFO', f'All {total_scenes} scenes collected successfully.')
        return combined_content

    def _parse_storyboard_metadata(self, content: str) -> tuple[dict, str]:
        """Extract STORYBOARD_METADATA block from AI response and return (metadata_dict, content_without_block).

        The metadata block format:
        <STORYBOARD_METADATA>
        CHARACTERS:
        - id: label - description
        SETUPS: (optional)
        - id: palette, location
        </STORYBOARD_METADATA>

        Returns:
            Tuple of (metadata dict with characters and setups, content with block removed)
        """
        metadata = {'characters': {}, 'setups': {}}
        content_cleaned = content
        last_end = 0

        # Find and extract all metadata blocks (batch responses may have multiple)
        start_marker = '<STORYBOARD_METADATA>'
        end_marker = '</STORYBOARD_METADATA>'
        while True:
            start_idx = content.find(start_marker, last_end)
            end_idx = content.find(end_marker, start_idx) if start_idx >= 0 else -1

            if start_idx < 0 or end_idx <= start_idx:
                break

            last_end = end_idx + len(end_marker)
            block = content[start_idx + len(start_marker):end_idx].strip()
            self.log_debug('INFO', 'Found STORYBOARD_METADATA block, parsing...')

            # Parse CHARACTERS section
            chars_match = re.search(r'CHARACTERS?\s*:(.*?)(?=SETUPS?\s*:|$)', block, re.DOTALL | re.IGNORECASE)
            if chars_match:
                chars_text = chars_match.group(1).strip()
                for line in chars_text.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Match formats: "id: label - description", "id: label (description)", or "id: label – description"
                    line = re.sub(r'^-\s*', '', line)
                    part_match = re.match(r'([a-zA-Z0-9_]+)\s*:\s*(.+?)\s+[-–]\s+(.+)', line, re.DOTALL)
                    if not part_match:
                        # Parenthetical: "story_character_1: Melon Usk (tech magnate antagonist, ...)"
                        part_match = re.match(r'([a-zA-Z0-9_]+)\s*:\s*(.+?)\s*\(([^)]+)\)\s*$', line, re.DOTALL)
                        if part_match:
                            label = part_match.group(2).strip()
                            desc = part_match.group(3).strip()
                            cid = part_match.group(1).strip().lower().replace(' ', '_')
                            metadata['characters'][cid] = {
                                'id': cid,
                                'label': label,
                                'description': desc,
                                'source': 'persona' if cid == 'persona' else 'story'
                            }
                            part_match = None  # skip normal handling
                    if part_match:
                        cid = part_match.group(1).strip().lower().replace(' ', '_')
                        label = part_match.group(2).strip()
                        desc = part_match.group(3).strip()
                        metadata['characters'][cid] = {
                            'id': cid,
                            'label': label,
                            'description': desc,
                            'source': 'persona' if cid == 'persona' else 'story'
                        }
                    elif ':' in line and re.search(r'\s[-–]\s', line):
                        # Fallback: split on first " - " or " – " for description
                        parts = re.split(r'\s+[-–]\s+', line, maxsplit=1)
                        if len(parts) == 2:
                            left = parts[0].strip()
                            desc = parts[1].strip()
                            if ':' in left:
                                id_part, label = left.split(':', 1)
                                cid = id_part.strip().lower().replace(' ', '_')
                                metadata['characters'][cid] = {
                                    'id': cid,
                                    'label': label.strip(),
                                    'description': desc,
                                    'source': 'persona' if cid == 'persona' else 'story'
                                }

            # Parse SETUPS section (optional)
            setups_match = re.search(r'SETUPS?\s*:(.*?)$', block, re.DOTALL | re.IGNORECASE)
            if setups_match:
                setups_text = setups_match.group(1).strip()
                for line in setups_text.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    line = re.sub(r'^-\s*', '', line)
                    if ':' in line:
                        sid, rest = line.split(':', 1)
                        sid = sid.strip().lower().replace(' ', '_')
                        rest = rest.strip()
                        metadata['setups'][sid] = {'description': rest}

        # Remove all metadata blocks from content for scene parsing
        content_cleaned = re.sub(
            r'<STORYBOARD_METADATA>.*?</STORYBOARD_METADATA>',
            '',
            content,
            flags=re.DOTALL
        ).strip()

        return metadata, content_cleaned

    def parse_storyboard_response(self, content: str, default_duration: int):
        """Parse the AI response and populate storyboard treeview.
        
        Args:
            content: AI response with scene descriptions
            default_duration: Default duration in seconds for each scene
        """
        if not hasattr(self, 'storyboard_tree'):
            self.log_debug('ERROR', 'Storyboard treeview not found')
            return
        
        # Clear cached prompts for a fresh parse
        self.scene_final_prompts = {}

        # Extract STORYBOARD_METADATA block first (characters, setups) and remove from content
        metadata, content = self._parse_storyboard_metadata(content)

        # Merge persona description from current persona (always prefer our persona data when available)
        if self.current_persona:
            persona_name = self.current_persona.get('name', 'Artist').strip()
            base_image_prompt = self.current_persona.get('base_image_prompt', '').strip()
            visual_aesthetic = self.current_persona.get('visual_aesthetic', '').strip()
            persona_desc = base_image_prompt
            if visual_aesthetic:
                persona_desc = f"{persona_desc} {visual_aesthetic}".strip() if persona_desc else visual_aesthetic
            if persona_desc:
                metadata.setdefault('characters', {})['persona'] = {
                    'id': 'persona',
                    'label': persona_name,
                    'description': persona_desc,
                    'source': 'persona'
                }

        if metadata.get('characters') or metadata.get('setups'):
            self.current_song['storyboard_metadata'] = metadata
            self.log_debug('INFO', f'Stored storyboard_metadata: {len(metadata.get("characters", {}))} characters, {len(metadata.get("setups", {}))} setups')

        self.log_debug('INFO', f'Parsing storyboard response (length: {len(content)} chars, default_duration: {default_duration}s)')
        self.log_debug('DEBUG', f'Response preview (first 500 chars): {content[:500]}')
        
        # Clear existing items
        for item in self.storyboard_tree.get_children():
            self.storyboard_tree.delete(item)
        
        # Get extracted lyrics and song duration for calculating scene lyrics
        lyrics = ''
        if self.current_song:
            lyrics = self.current_song.get('extracted_lyrics', '').strip()
        if not lyrics and hasattr(self, 'get_mp3_filepath'):
            mp3_path = self.get_mp3_filepath()
            if mp3_path:
                lyrics = self.get_extracted_lyrics(mp3_path, force_extract=False)
                # Keep UI in sync
                if hasattr(self, 'extracted_lyrics_text') and lyrics:
                    self.extracted_lyrics_text.delete('1.0', tk.END)
                    self.extracted_lyrics_text.insert('1.0', lyrics)
        mp3_path = self.get_mp3_filepath() if hasattr(self, 'get_mp3_filepath') else ''
        song_duration = self.get_mp3_duration(mp3_path) if mp3_path else 0.0
        lyric_segments = []
        if lyrics and song_duration > 0:
            lyric_segments = self.parse_lyrics_with_timing(lyrics, song_duration)
        
        # Parse scenes from response
        lines = content.split('\n')
        self.log_debug('DEBUG', f'Total lines in response: {len(lines)}')
        
        current_scene = None
        current_prompt = []
        scene_lyrics = ''
        scene_num = 1
        scenes_found = 0
        skipped_empty_scenes = []

        for line_idx, line in enumerate(lines):
            original_line = line
            line = line.strip()
            if not line:
                continue
            
            # Check for scene marker
            if line.upper().startswith('SCENE'):
                self.log_debug('DEBUG', f'Found scene marker at line {line_idx + 1}: {line}')
                # Save previous scene if exists
                if current_scene is not None and current_prompt:
                    prompt_text = '\n'.join(current_prompt).strip()
                    # If no lyrics for this scene, strip any "lyrics" lines from prompt
                    if not scene_lyrics or scene_lyrics.strip().lower() == '[no lyrics]':
                        prompt_text = self.sanitize_prompt_no_lyrics(prompt_text)
                        scene_lyrics = ''
                    prompt_text = self._strip_dialogue_from_no_character_prompt(prompt_text)
                    if prompt_text:
                        # Calculate lyrics for this scene
                        prompt_text = self.apply_storyboard_theme_prefix(prompt_text)
                        scene_lyrics_calc = scene_lyrics
                        if lyric_segments and song_duration > 0 and not scene_lyrics_calc:
                            scene_start_time = (current_scene - 1) * default_duration
                            scene_end_time = min(scene_start_time + default_duration, song_duration)
                            scene_lyrics_calc = self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments)
                        scene_timestamp = self.format_timestamp((current_scene - 1) * default_duration)
                        self.storyboard_tree.insert('', tk.END, values=(current_scene, scene_timestamp, f'{default_duration}s', scene_lyrics_calc, prompt_text))
                        scenes_found += 1
                        self.log_debug('DEBUG', f'Saved scene {current_scene} with prompt length {len(prompt_text)} chars, lyrics: {scene_lyrics_calc[:50] if scene_lyrics_calc else "none"}')
                    else:
                        skipped_empty_scenes.append(current_scene)
                        self.log_debug('WARNING', f'Scene {current_scene} has empty prompt, skipping')
                
                # Extract scene number and duration
                parts = line.split(':')
                if len(parts) >= 2:
                    scene_part = parts[0].strip()
                    duration_part = parts[1].strip() if len(parts) > 1 else f'{default_duration}s'
                    # Extract duration from duration_part (e.g., "8 seconds" -> 8)
                    duration_match = re.search(r'(\d+)', duration_part)
                    if duration_match:
                        scene_duration = int(duration_match.group(1))
                        self.log_debug('DEBUG', f'Extracted duration: {scene_duration}s from "{duration_part}"')
                    else:
                        scene_duration = default_duration
                        self.log_debug('DEBUG', f'Using default duration: {default_duration}s')
                    # Extract scene number
                    scene_num_match = [s for s in scene_part.split() if s.isdigit()]
                    if scene_num_match:
                        current_scene = int(scene_num_match[0])
                        self.log_debug('DEBUG', f'Extracted scene number: {current_scene} from "{scene_part}"')
                    else:
                        current_scene = scene_num
                        scene_num += 1
                        self.log_debug('DEBUG', f'Using auto-increment scene number: {current_scene}')
                    current_prompt = []
                else:
                    self.log_debug('WARNING', f'Scene marker format unexpected: {line}')
                scene_lyrics = ''
            elif current_scene is not None:
                # Add to current prompt
                current_prompt.append(line)
            elif line_idx < 10:  # Log first few non-scene lines for debugging
                self.log_debug('DEBUG', f'Line {line_idx + 1} (before scene): {line[:100]}')
        
        # Save last scene
        if current_scene is not None and current_prompt:
            prompt_text = '\n'.join(current_prompt).strip()
            prompt_text = self._strip_dialogue_from_no_character_prompt(prompt_text)
            if prompt_text:
                # Calculate lyrics for last scene
                prompt_text = self.apply_storyboard_theme_prefix(prompt_text)
                scene_lyrics = ''
                if lyric_segments and song_duration > 0:
                    scene_start_time = (current_scene - 1) * default_duration
                    scene_end_time = min(scene_start_time + default_duration, song_duration)
                    scene_lyrics = self.get_lyrics_for_scene(scene_start_time, scene_end_time, lyric_segments)
                
                scene_timestamp = self.format_timestamp((current_scene - 1) * default_duration)
                self.storyboard_tree.insert('', tk.END, values=(current_scene, scene_timestamp, f'{default_duration}s', scene_lyrics, prompt_text))
                scenes_found += 1
                self.log_debug('DEBUG', f'Saved final scene {current_scene} with prompt length {len(prompt_text)} chars, lyrics: {scene_lyrics[:50] if scene_lyrics else "none"}')
            else:
                skipped_empty_scenes.append(current_scene)
                self.log_debug('WARNING', f'Final scene {current_scene} has empty prompt, skipping')
        
        if skipped_empty_scenes:
            self.log_debug('INFO', f'Parsing complete: Found {scenes_found} scenes, skipped {len(skipped_empty_scenes)} empty scene(s): {skipped_empty_scenes}')
        else:
            self.log_debug('INFO', f'Parsing complete: Found {scenes_found} scenes')
        if scenes_found == 0:
            self.log_debug('ERROR', 'No scenes were parsed from the response!')
            self.log_debug('DEBUG', f'Full response content:\n{content}')
    
    def save_storyboard_raw_response(self, response_text: str, seconds_per_video: int, metadata=None):
        """Save raw storyboard AI response to JSON file in current song directory."""
        if not response_text:
            return
        song_path = getattr(self, 'current_song_path', '')
        if not song_path:
            self.log_debug('WARNING', 'Cannot save storyboard raw response - song path is not set.')
            return
        try:
            os.makedirs(song_path, exist_ok=True)
            import datetime
            timestamp = datetime.datetime.now()
            filename = os.path.join(song_path, f'storyboard_response_{timestamp.strftime("%Y%m%d_%H%M%S")}.json')
            persona_name = ''
            if hasattr(self, 'current_persona') and self.current_persona:
                persona_name = self.current_persona.get('name', '')
            data = {
                'timestamp': timestamp.isoformat(),
                'song_name': self.song_name_var.get().strip() if hasattr(self, 'song_name_var') else '',
                'full_song_name': self.full_song_name_var.get().strip() if hasattr(self, 'full_song_name_var') else '',
                'persona': persona_name,
                'seconds_per_video': seconds_per_video,
                'metadata': metadata or {},
                'raw_response': response_text
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_debug('INFO', f'Storyboard raw response saved to {filename}')
        except Exception as exc:
            self.log_debug('WARNING', f'Failed to save storyboard raw response: {exc}')

    def reprocess_latest_storyboard_response(self):
        """Load the latest storyboard_response_*.json in the song dir, parse it, update tree and config."""
        song_path = getattr(self, 'current_song_path', '')
        if not song_path:
            self.log_debug('WARNING', 'Cannot reprocess - song path is not set.')
            messagebox.showwarning('Warning', 'No song selected. Select a song first.')
            return
        pattern = os.path.join(song_path, 'storyboard_response_*.json')
        files = glob.glob(pattern)
        if not files:
            self.log_debug('WARNING', 'No storyboard_response_*.json files found.')
            messagebox.showwarning('Warning', f'No storyboard response files found in:\n{song_path}')
            return
        # Filter to valid format storyboard_response_YYYYMMDD_HHMMSS.json and sort by timestamp
        valid_pattern = re.compile(r'storyboard_response_(\d{8}_\d{6})\.json$')
        valid_files = []
        for p in files:
            base = os.path.basename(p)
            m = valid_pattern.match(base)
            if m:
                valid_files.append((m.group(1), p))
        if not valid_files:
            self.log_debug('WARNING', 'No valid storyboard_response_YYYYMMDD_HHMMSS.json files found.')
            messagebox.showwarning('Warning', f'No valid storyboard response files (expected format: storyboard_response_YYYYMMDD_HHMMSS.json) in:\n{song_path}')
            return
        valid_files.sort(key=lambda x: x[0], reverse=True)
        latest_path = valid_files[0][1]
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.log_debug('WARNING', f'Failed to load {latest_path}: {e}')
            messagebox.showerror('Error', f'Failed to load response file:\n{e}')
            return
        raw_response = data.get('raw_response', '')
        seconds_per_video = int(data.get('seconds_per_video', 6))
        if not raw_response:
            messagebox.showwarning('Warning', f'File has no raw_response:\n{os.path.basename(latest_path)}')
            return
        if hasattr(self, 'storyboard_seconds_var'):
            self.storyboard_seconds_var.set(str(seconds_per_video))
        self.parse_storyboard_response(raw_response, seconds_per_video)
        self.save_song()
        self.log_debug('INFO', f'Reprocessed storyboard from {os.path.basename(latest_path)}')
        messagebox.showinfo('Success', f'Reprocessed latest response:\n{os.path.basename(latest_path)}\nSaved to config.')

    def reproduce_storyboard_response_json(self):
        """Reconstruct and save storyboard_response_*.json from current storyboard data in config/tree.
        Produces the same JSON structure as save_storyboard_raw_response for reproducibility/debugging."""
        song_path = getattr(self, 'current_song_path', '')
        if not song_path:
            self.log_debug('WARNING', 'Cannot reproduce storyboard response - song path is not set.')
            messagebox.showwarning('Warning', 'No song selected. Select a song first.')
            return
        storyboard = []
        if hasattr(self, 'storyboard_tree') and self.storyboard_tree.get_children():
            storyboard = self.get_storyboard_data()
        elif self.current_song and self.current_song.get('storyboard'):
            storyboard = self.current_song.get('storyboard', [])
        if not storyboard:
            self.log_debug('WARNING', 'No storyboard data to reproduce.')
            messagebox.showwarning('Warning', 'No storyboard scenes found. Generate a storyboard first.')
            return
        # Determine seconds_per_video from first scene duration or config
        seconds_per_video = 6
        first_dur = storyboard[0].get('duration', '')
        if first_dur:
            m = re.search(r'(\d+)', str(first_dur))
            if m:
                seconds_per_video = int(m.group(1))
        if self.current_song and 'storyboard_seconds_per_video' in self.current_song:
            seconds_per_video = int(self.current_song.get('storyboard_seconds_per_video', 6))
        if hasattr(self, 'storyboard_seconds_var') and self.storyboard_seconds_var.get():
            try:
                seconds_per_video = int(self.storyboard_seconds_var.get())
            except ValueError:
                pass
        # Build raw_response in same format as AI response: "SCENE N: X seconds  \n<prompt>\n\n"
        parts = []
        for scene in storyboard:
            scene_num = scene.get('scene', len(parts) + 1)
            prompt = scene.get('prompt', '').strip()
            parts.append(f"SCENE {scene_num}: {seconds_per_video} seconds  \n{prompt}")
        raw_response = '\n\n'.join(parts)
        metadata = {'mode': 'reproduced', 'num_scenes': len(storyboard), 'seconds_per_video': seconds_per_video}
        self.save_storyboard_raw_response(raw_response, seconds_per_video, metadata)
        messagebox.showinfo('Success', f'Storyboard response JSON reproduced ({len(storyboard)} scenes).')

    def save_storyboard_prompt(self, prompt_text: str, seconds_per_video: int, metadata=None):
        """Save the full storyboard prompt to a text file for debugging."""
        if not prompt_text:
            return
        song_path = getattr(self, 'current_song_path', '')
        if not song_path:
            self.log_debug('WARNING', 'Cannot save storyboard prompt - song path is not set.')
            return
        try:
            os.makedirs(song_path, exist_ok=True)
            import datetime
            timestamp = datetime.datetime.now()
            filename = os.path.join(song_path, f'storyboard_prompt_{timestamp.strftime("%Y%m%d_%H%M%S")}.txt')
            data = {
                'timestamp': timestamp.isoformat(),
                'seconds_per_video': seconds_per_video,
                'metadata': metadata or {},
                'prompt': prompt_text
            }
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
            self.log_debug('INFO', f'Storyboard prompt saved to {filename}')
        except Exception as exc:
            self.log_debug('WARNING', f'Failed to save storyboard prompt: {exc}')

    def _get_scenes_from_tree(self, items: list) -> list:
        """Extract (scene_num, prompt, lyrics) from storyboard treeview items.

        Args:
            items: List of treeview item ids (e.g. from selection or get_children)

        Returns:
            List of (scene_num, prompt, lyrics) tuples for items with non-empty prompts, sorted by scene_num
        """
        scenes = []
        for item in items:
            values = self.storyboard_tree.item(item, 'values')
            if len(values) >= 5:
                scene_num = values[0]
                lyrics = values[3] if len(values) > 3 else ''
                prompt = values[4]
            elif len(values) >= 3:
                scene_num = values[0]
                prompt = values[2]
                lyrics = ''
            else:
                continue
            if prompt:
                scenes.append((scene_num, prompt, lyrics))
        # Sort by scene_num (as int when possible) for consistent ordering
        try:
            scenes.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0])
        except (TypeError, ValueError):
            pass
        return scenes

    def generate_storyboard_image_selected(self):
        """Generate images for the selected storyboard scenes (supports multiple selection)."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        selection = self.storyboard_tree.selection()
        if not selection:
            messagebox.showwarning('Warning', 'Please select one or more scenes to generate images for.')
            return
        
        scenes_to_generate = self._get_scenes_from_tree(selection)
        if not scenes_to_generate:
            messagebox.showwarning('Warning', 'No valid scenes found in selection.')
            return
        
        # Ask for confirmation if multiple scenes
        if len(scenes_to_generate) > 1:
            response = messagebox.askyesno('Generate Multiple Images', f'Generate images for {len(scenes_to_generate)} selected scenes? This may take a while.')
            if not response:
                return
        
        # Create progress dialog for multiple images
        progress_dialog = None
        if len(scenes_to_generate) > 1:
            progress_dialog = ProgressDialog(self, len(scenes_to_generate), 'Generating Storyboard Images')
            progress_dialog.update()
        
        # Generate images for all selected scenes
        successful = 0
        failed = 0
        for idx, (scene_num, prompt, lyrics) in enumerate(scenes_to_generate, 1):
            if progress_dialog:
                if progress_dialog.is_cancelled():
                    self.log_debug('INFO', 'Image generation cancelled by user')
                    break
                progress_dialog.update_progress(idx, f'Generating scene {scene_num} ({idx}/{len(scenes_to_generate)})...')
            
            if self.generate_storyboard_image(scene_num, prompt, show_success_message=False, lyrics=lyrics):
                successful += 1
            else:
                failed += 1
        
        # Close progress dialog
        if progress_dialog:
            progress_dialog.destroy()
        
        # Show summary if multiple images
        if len(scenes_to_generate) > 1:
            messagebox.showinfo('Generation Complete', f'Generated {successful} image(s) successfully.\n{failed} failed.' if failed > 0 else f'Generated {successful} image(s) successfully.')
    
    def generate_storyboard_images_all(self):
        """Generate images for all storyboard scenes."""
        if not hasattr(self, 'storyboard_tree'):
            return
        
        items = self.storyboard_tree.get_children()
        if not items:
            messagebox.showwarning('Warning', 'No scenes found. Please generate storyboard first.')
            return
        
        response = messagebox.askyesno('Generate All Images', f'Generate images for all {len(items)} scenes? This may take a while.')
        if not response:
            return

        scenes_to_generate = self._get_scenes_from_tree(items)
        if not scenes_to_generate:
            messagebox.showwarning('Warning', 'No valid scenes found.')
            return
        
        # Create progress dialog
        progress_dialog = ProgressDialog(self, len(scenes_to_generate), 'Generating Storyboard Images')
        progress_dialog.update()
        
        # Generate images for all scenes
        successful = 0
        failed = 0
        try:
            for idx, (scene_num, prompt, lyrics) in enumerate(scenes_to_generate, 1):
                if progress_dialog.is_cancelled():
                    self.log_debug('INFO', 'Image generation cancelled by user')
                    break
                progress_dialog.update_progress(idx, f'Generating scene {scene_num} ({idx}/{len(scenes_to_generate)})...')
                
                if self.generate_storyboard_image(scene_num, prompt, show_success_message=False, lyrics=lyrics):
                    successful += 1
                else:
                    failed += 1
        finally:
            progress_dialog.destroy()
        
        # Show summary
        messagebox.showinfo('Generation Complete', f'Generated {successful} image(s) successfully.\n{failed} failed.' if failed > 0 else f'Generated {successful} image(s) successfully.')
    
    def get_storyboard_image_size(self) -> str:
        """Get the image size string for storyboard images.
        
        Returns:
            Size string like '1536x1024' mapped to supported sizes for gpt-image-1.5
        """
        if hasattr(self, 'storyboard_image_size_var'):
            size_value = self.storyboard_image_size_var.get()
            # Extract size from format like "3:2 (1536x1024)" -> "1536x1024"
            match = re.search(r'\((\d+x\d+)\)', size_value)
            if match:
                extracted_size = match.group(1)
                # Map to supported size
                return self._map_to_supported_image_size(extracted_size)
        # Default to 3:2 aspect ratio
        return '1536x1024'
    
    def _map_to_supported_image_size(self, size_str: str) -> str:
        """Map image size to supported sizes for gpt-image-1.5 model.
        
        Supported sizes: 1024x1024, 1536x1024, 1024x1536
        
        Args:
            size_str: Size string like '1024x1024' or '1024x1792'
            
        Returns:
            Mapped size string that is supported by the model
        """
        # Parse width and height
        match = re.match(r'(\d+)x(\d+)', size_str)
        if not match:
            return '1024x1024'  # Default fallback
        
        width = int(match.group(1))
        height = int(match.group(2))
        
        # If already a supported size, return as-is
        if size_str in ['1024x1024', '1536x1024', '1024x1536']:
            return size_str
        
        # Determine aspect ratio
        aspect_ratio = width / height if height > 0 else 1.0
        
        # Map to closest supported size
        if aspect_ratio == 1.0:
            # Square
            return '1024x1024'
        elif aspect_ratio > 1.0:
            # Landscape (wider than tall)
            return '1536x1024'
        else:
            # Portrait (taller than wide)
            return '1024x1536'
    
    def get_album_cover_image_size(self) -> str:
        """Get the image size string for album cover images.
        
        Returns:
            Size string like '1024x1024' mapped to supported sizes for gpt-image-1.5
        """
        if hasattr(self, 'album_cover_size_var'):
            size_value = self.album_cover_size_var.get()
            # Extract size from format like "1:1 (1024x1024)" -> "1024x1024"
            match = re.search(r'\((\d+x\d+)\)', size_value)
            if match:
                extracted_size = match.group(1)
                # Map to supported size
                return self._map_to_supported_image_size(extracted_size)
        # Default to 1:1 aspect ratio
        return '1024x1024'
    
    def get_album_cover_format(self) -> str:
        """Get the image format for album cover (PNG or JPEG).
        
        Returns:
            Format string: 'png' or 'jpeg'
        """
        if hasattr(self, 'album_cover_format_var'):
            format_value = self.album_cover_format_var.get().upper()
            if format_value == 'JPEG':
                return 'jpeg'
            return 'png'
        return 'png'
    
    def get_video_loop_size(self) -> str:
        """Get the video size string for video loop.
        
        Returns:
            Size string like '720x1280' extracted from dropdown value
        """
        if hasattr(self, 'video_loop_size_var'):
            size_value = self.video_loop_size_var.get()
            # Extract size from format like "9:16 (720x1280)" -> "720x1280"
            match = re.search(r'\((\d+x\d+)\)', size_value)
            if match:
                return match.group(1)
        # Default to 9:16 aspect ratio
        return '720x1280'
    
    def overlay_lyrics_on_image(self, image_path: str, lyrics: str, scene_num: str = '') -> bool:
        """Overlay lyrics text on an image.
        
        Args:
            image_path: Path to the image file
            lyrics: Lyrics text to overlay
            scene_num: Scene number (for logging)
        
        Returns:
            True if successful, False otherwise
        """
        if not lyrics or not lyrics.strip():
            return False
        
        try:
            # Open the image
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            
            # Get image dimensions
            width, height = img.size
            
            # Try to load a font, fallback to default if not available
            try:
                # Try to use a larger, readable font
                font_size = max(24, int(height / 30))  # Scale font size with image height
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Prepare text - wrap long lines
            max_chars_per_line = int(width / (font_size * 0.6))  # Approximate chars per line
            words = lyrics.split(' | ')  # Split by separator if present
            lines = []
            current_line = []
            current_length = 0
            
            for word in words:
                word_length = len(word) + 1  # +1 for space
                if current_length + word_length > max_chars_per_line and current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    current_line.append(word)
                    current_length += word_length
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Limit to 3-4 lines max to avoid covering too much of the image
            if len(lines) > 4:
                lines = lines[:4]
                lines[-1] = lines[-1][:max_chars_per_line-3] + '...'
            
            # Calculate text position (bottom of image with padding)
            line_height = font_size + 8
            total_text_height = len(lines) * line_height
            padding = 20
            y_start = height - total_text_height - padding
            
            # Draw semi-transparent background rectangle
            bg_height = total_text_height + padding * 2
            bg_overlay = Image.new('RGBA', (width, bg_height), (0, 0, 0, 180))  # Black with 70% opacity
            img.paste(bg_overlay, (0, y_start - padding), bg_overlay)
            
            # Draw text lines
            y_pos = y_start
            for line in lines:
                # Get text bounding box for centering
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (width - text_width) // 2
                
                # Draw text with white color and slight shadow for readability
                # Shadow
                draw.text((x_pos + 2, y_pos + 2), line, font=font, fill=(0, 0, 0, 255))
                # Main text
                draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255, 255))
                
                y_pos += line_height
            
            # Save the modified image
            img.save(image_path, 'PNG')
            self.log_debug('INFO', f'Overlaid lyrics on scene {scene_num} image: {len(lines)} lines')
            return True
            
        except Exception as e:
            self.log_debug('WARNING', f'Failed to overlay lyrics on image: {e}')
            return False

    def get_scene_final_prompt(self, scene_num: str, base_prompt: str = None, lyrics: str = None, prompt_type: str = 'image') -> str:
        """Get the final prompt for a scene, checking saved generated_prompt_image/generated_prompt_video first.
        
        This checks in order:
        1. Saved generated_prompt_image or generated_prompt_video from config.json (if available)
        2. In-memory cache (scene_final_prompts)
        3. Builds a new prompt if neither exists
        
        Args:
            scene_num: Scene number
            base_prompt: Base prompt text (optional, will be retrieved from scene if not provided)
            lyrics: Lyrics text (optional, will be retrieved from scene if not provided)
            prompt_type: Type of prompt - 'image' or 'video'
        
        Returns:
            Final prompt string ready for image/video generation
        """
        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
        scene_num_int = int(scene_num) if str(scene_num).isdigit() else None

        # For multi-scene scene 1 image: always build fresh (persona reference)
        skip_stored_for_multiscene_scene1 = is_multiscene and scene_num_int == 1 and prompt_type == 'image'

        # Field name for stored prompt
        stored_field = 'generated_prompt_image' if prompt_type == 'image' else 'generated_prompt_video'

        # First, check if there's a saved prompt in config.json
        if self.current_song and not skip_stored_for_multiscene_scene1:
            storyboard = self.current_song.get('storyboard', [])
            for scene in storyboard:
                scene_value = scene.get('scene')
                if (scene_num_int is not None and scene_value == scene_num_int) or str(scene_value) == str(scene_num):
                    stored_prompt = scene.get(stored_field, '')
                    if stored_prompt:
                        no_char_markers = ('[no characters]', 'no characters', 'no persona present', 'no human figures',
                                          'no persona', 'no people', 'no artist', '[no persona]', 'without any human',
                                          'purely environmental', 'purely abstract', 'no human presence')
                        if any(m in stored_prompt.lower() for m in no_char_markers):
                            stored_prompt = self._sanitize_no_character_scene_prompt_for_video(stored_prompt)
                        if prompt_type == 'image' and re.search(r'\[\d+(?:\.\d+)?s[-–]\d+(?:\.\d+)?s\]', stored_prompt):
                            stored_prompt = self._extract_first_subscene_for_single_image(stored_prompt)
                        self.log_debug('INFO', f'Using saved {stored_field} for scene {scene_num}')
                        return stored_prompt
                    if base_prompt is None:
                        base_prompt = scene.get('prompt', '')
                    if lyrics is None:
                        lyrics = scene.get('lyrics', '')
                    break

        if skip_stored_for_multiscene_scene1 and self.current_song and (base_prompt is None or lyrics is None):
            storyboard = self.current_song.get('storyboard', [])
            for scene in storyboard:
                scene_value = scene.get('scene')
                if (scene_num_int is not None and scene_value == scene_num_int) or str(scene_value) == str(scene_num):
                    if base_prompt is None:
                        base_prompt = scene.get('prompt', '')
                    if lyrics is None:
                        lyrics = scene.get('lyrics', '')
                    break

        # Second, check in-memory cache (unified: base_key -> {'image': str, 'video': str})
        base_cache_key = f"{scene_num}|{self._get_song_persona_preset_key()}"
        if not skip_stored_for_multiscene_scene1 and base_cache_key in self.scene_final_prompts:
            cached = self.scene_final_prompts[base_cache_key]
            if isinstance(cached, dict):
                cached_prompt = cached.get(prompt_type, '')
            else:
                cached_prompt = cached if isinstance(cached, str) else ''
            if cached_prompt:
                no_char_markers = ('[no characters]', 'no characters', 'no persona present', 'no human figures',
                                  'no persona', 'no people', 'no artist', '[no persona]', 'without any human',
                                  'purely environmental', 'purely abstract', 'no human presence')
                if prompt_type == 'video' and any(m in cached_prompt.lower() for m in no_char_markers):
                    cached_prompt = self._sanitize_no_character_scene_prompt_for_video(cached_prompt)
                return cached_prompt

        # Third, build a new prompt
        if base_prompt:
            return self.build_scene_image_prompt(scene_num, base_prompt, lyrics, prompt_type)

        return ''
    
    def _build_multiscene_reference_image_prompt(self, cache_key: str) -> str:
        """Build a clean single-image prompt for multi-scene mode scene 1.
        
        This generates ONLY a single reference image of the character.
        NO scene information, NO sub-scenes, NO storyboard elements.
        The image will be used as reference for subsequent video generation.
        
        Args:
            cache_key: Cache key for storing the result
        
        Returns:
            Clean prompt for generating a single reference character image
        """
        prompt_parts = [
            "CRITICAL: Generate exactly ONE SINGLE IMAGE. Do NOT create:",
            "- Multiple panels or frames",
            "- Triptych or split-screen layouts", 
            "- Collages or montages",
            "- Comic strips or storyboards",
            "- Before/after comparisons",
            "- Any kind of multi-image composition",
            "",
            "Create ONE clean, focused image of the character.",
            ""
        ]
        
        # Get persona visual characteristics
        if self.current_persona:
            visual_aesthetic = self.current_persona.get('visual_aesthetic', '').strip()
            base_image_prompt = self.current_persona.get('base_image_prompt', '').strip()
            persona_name = self.current_persona.get('name', '').strip()
            vibe = self.current_persona.get('vibe', '').strip()
            
            if persona_name:
                prompt_parts.append(f"CHARACTER: {persona_name}")
            if base_image_prompt:
                prompt_parts.append(f"APPEARANCE: {base_image_prompt}")
            if visual_aesthetic:
                prompt_parts.append(f"STYLE: {visual_aesthetic}")
            if vibe:
                prompt_parts.append(f"MOOD: {vibe}")
        
        # Try to get character description from reference image
        if self.current_persona_path:
            preset_key = self._get_song_persona_preset_key()
            base_path = self.get_persona_image_base_path(preset_key)
            safe_name = self._safe_persona_basename()
            front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
            
            if os.path.exists(front_image_path):
                try:
                    from PIL import Image
                    original_img = Image.open(front_image_path)
                    new_width = original_img.width // 2
                    new_height = original_img.height // 2
                    downscaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    temp_dir = os.path.join(self.current_song_path if self.current_song_path else os.path.dirname(front_image_path), 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    reference_image_path = os.path.join(temp_dir, f'{safe_name}-Front-downscaled.png')
                    downscaled_img.save(reference_image_path, 'PNG')
                    
                    vision_prompt = (
                        "Describe this character's appearance in detail for image generation. "
                        "Include: physical features, clothing, styling, colors, accessories. "
                        "Be specific and detailed."
                    )
                    vision_result = self.azure_vision([reference_image_path], vision_prompt, profile='text')
                    
                    if vision_result.get('success'):
                        character_description = vision_result['content'].strip()
                        prompt_parts.append("")
                        prompt_parts.append(f"DETAILED CHARACTER DESCRIPTION:\n{character_description}")
                except Exception as e:
                    self.log_debug('WARNING', f'Failed to analyze reference image: {e}')
        
        prompt_parts.extend([
            "",
            "REQUIREMENTS:",
            "- Single unified image composition",
            "- Character should be the clear focal point",
            "- Clean background or simple environment",
            "- No text, titles, or labels in the image",
            "- No panel borders or dividing lines",
            "- Professional quality, suitable as video reference"
        ])
        
        prompt = "\n".join(prompt_parts)
        self.scene_final_prompts[cache_key] = prompt
        self.log_debug('INFO', 'Built multi-scene reference image prompt (single image only)')
        return prompt
    
    def _extract_first_subscene_for_single_image(self, prompt: str) -> str:
        """Extract first sub-scene from a prompt with [0s-2s] structure for single image generation.
        
        Builds a single-image prompt without video structure. No MULTI-SCENE VIDEO,
        HARD CUT, or multi-panel content - only the first sub-scene.
        
        Args:
            prompt: Prompt with [0s-2s], [2s-4s], [4s-6s] sub-scene structure
        
        Returns:
            Single-image prompt suitable for image generation
        """
        subscene_pattern = r'\[(\d+(?:\.\d+)?)s[-–](\d+(?:\.\d+)?)s\]\s*(?:Sub-scene\s*\d+:?)?\s*'

        if not re.search(subscene_pattern, prompt):
            single_image_prefix = (
                "IMPORTANT: Generate exactly ONE single image. "
                "Do NOT create multiple panels, triptych, collage, or split-screen layouts.\n\n"
            )
            return single_image_prefix + prompt

        first_subscene_content = ""
        prefix_content = (re.split(subscene_pattern, prompt)[0] or "").strip()
        matches = list(re.finditer(subscene_pattern, prompt))
        if matches:
            start_idx = matches[0].end()
            end_idx = matches[1].start() if len(matches) > 1 else len(prompt)
            first_subscene_content = prompt[start_idx:end_idx].strip()

        prefix_content = re.sub(subscene_pattern, '', prefix_content).strip()
        prefix_content = re.sub(r'\d+\s*seconds?\s*total', '', prefix_content, flags=re.IGNORECASE).strip()

        cleaned_parts = [
            "CRITICAL: Generate exactly ONE SINGLE IMAGE.",
            "Do NOT create:",
            "- Multiple panels or frames",
            "- Triptych or split-screen layouts",
            "- Collages or montages",
            "- Comic strips or storyboards",
            "- Scene sequences or before/after comparisons",
            "",
            "Create ONE focused, unified image composition.",
            ""
        ]
        if prefix_content:
            cleaned_parts.append(prefix_content)
        if first_subscene_content:
            cleaned_parts.append("")
            cleaned_parts.append("SCENE CONTENT:")
            cleaned_parts.append(first_subscene_content)

        self.log_debug('INFO', 'Extracted first sub-scene for single image prompt')
        return "\n".join(cleaned_parts)

    def _inject_character_descriptions_into_subscenes(self, prompt: str, character_registry: dict) -> str:
        """Inject character descriptions into sub-scenes that feature characters but lack descriptions.

        For video generation with multi-scene, each sub-scene needs explicit character
        descriptions when they appear, since they may not be on the reference image.

        Args:
            prompt: Prompt text with sub-scene structure [Xs-Ys] Sub-scene N: ...
            character_registry: Dict mapping character id to {label, description} or id to description string

        Returns:
            Prompt with CHARACTER: [label] - [description] prepended to sub-scenes that need it
        """
        if not character_registry:
            return prompt

        subscene_pattern = re.compile(
            r'\[\d+(?:\.\d+)?s[-–]\d+(?:\.\d+)?s\]\s*(?:Sub-scene\s*\d+:?)?\s*',
            re.IGNORECASE
        )
        matches = list(subscene_pattern.finditer(prompt))
        no_char_markers = [
            '[no characters]', 'no characters', 'no persona present', 'no human figures',
            'purely environmental', 'purely abstract', 'no human presence'
        ]

        # Fallback: when prompt has no [Xs-Ys] sub-scene structure, prepend primary character
        # description so single-shot persona/character scenes get needed context
        if not matches:
            prompt_start = (prompt[:300] or '').lower()
            if any(m in prompt_start for m in no_char_markers):
                return prompt
            if 'character:' in prompt_start and ' - ' in prompt[:300]:
                return prompt
            primary = character_registry.get('persona') or next(iter(character_registry.values()), None)
            if not primary:
                return prompt
            entry = primary if isinstance(primary, dict) else {'label': 'Artist', 'description': str(primary)}
            label = entry.get('label', 'Artist')
            desc = entry.get('description', '')
            if not desc or len(desc) < 10:
                return prompt
            return f"CHARACTER ({label}): {desc}. " + prompt.strip()

        def find_character_for_block(block: str):
            block_lower = block.lower()
            if any(m in block_lower for m in no_char_markers):
                return None
            # Skip injection only when block already has full description (id - description format)
            if 'character:' in block_lower and ' - ' in block:
                return None
            for cid, info in character_registry.items():
                entry = info if isinstance(info, dict) else {'label': cid, 'description': str(info)}
                label = entry.get('label', cid)
                desc = entry.get('description', '')
                if not desc or len(desc) < 10:
                    continue
                if cid in block_lower or (label and label.lower() in block_lower):
                    return (label, desc)
            return None

        # Do not cross scene boundaries: content for a sub-scene must not include
        # text from the next SCENE N: block (theme/character names there cause false matches)
        scene_boundary_pattern = re.compile(r'\n\s*SCENE\s+\d+\s*:', re.IGNORECASE)

        result_parts = [prompt[:matches[0].start()]]
        for i, m in enumerate(matches):
            result_parts.append(prompt[m.start():m.end()])
            end_next = matches[i + 1].start() if i + 1 < len(matches) else len(prompt)
            # Cap content at next scene boundary to avoid matching characters from next scene's theme
            scene_bound = scene_boundary_pattern.search(prompt, m.end())
            content_end = min(end_next, scene_bound.start()) if scene_bound and scene_bound.start() < end_next else end_next
            # Also cap at first double-newline: sub-scene text is one line; appended blocks (CRITICAL REQUIREMENT,
            # Persona Base Image Prompt, etc.) contain character names and cause false injection
            para_break = prompt.find('\n\n', m.end())
            if para_break >= 0 and para_break < content_end:
                content_end = para_break
            content = prompt[m.end():content_end]
            found = find_character_for_block(content)
            if found:
                label, desc = found
                injected = f"CHARACTER ({label}): {desc}. "
                if not content.strip().lower().startswith('character'):
                    content = injected + content.strip()
            result_parts.append(content)

        return ''.join(result_parts)

    def build_scene_prompts_both(self, scene_num: str, base_prompt: str, lyrics: str = None) -> dict:
        """Build IMAGE and VIDEO prompts in a single pass with shared AI work (persona detection, vision).

        Runs persona detection and reference image analysis once, then derives both prompt types
        without additional API calls.

        Returns:
            {'image': str, 'video': str}
        """
        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
        scene_num_int = int(scene_num) if str(scene_num).isdigit() else 0
        base_key = f"{scene_num}|{self._get_song_persona_preset_key()}"

        # Check unified cache (both prompts stored under one key)
        if base_key in self.scene_final_prompts:
            cached = self.scene_final_prompts[base_key]
            if isinstance(cached, dict):
                return {'image': cached.get('image', ''), 'video': cached.get('video', '')}

        # Multi-scene scene 1 image: persona reference - we still need full logic for video
        multiscene_scene1_image_special = (
            is_multiscene and scene_num_int == 1 and self.current_persona
            and self._storyboard_has_any_persona_or_character()
        )

        prompt = self.sanitize_lyrics_for_prompt(base_prompt)
        persona_in_scene_early = self._is_persona_scene_quick(prompt)
        prompt = self.apply_storyboard_theme_prefix(prompt, persona_scene=persona_in_scene_early)
        lyrics_text = self.sanitize_lyrics_for_prompt(lyrics) if lyrics else ''
        if not lyrics_text or lyrics_text.strip().upper() == '[NO LYRICS]':
            prompt = self.sanitize_prompt_no_lyrics(prompt)
        embed_lyrics_enabled = bool(self.embed_lyrics_var.get()) if hasattr(self, 'embed_lyrics_var') else True
        embed_keywords_enabled = bool(self.embed_keywords_var.get()) if hasattr(self, 'embed_keywords_var') else False
        keyword = ''
        if embed_keywords_enabled:
            keyword = self._extract_major_keyword(f"{lyrics_text} {prompt}")

        reference_note = self._prepare_previous_scene_reference(
            int(scene_num) if str(scene_num).isdigit() else scene_num, prompt
        )
        if str(scene_num).isdigit() and int(scene_num) == 1:
            cover_note = self._prepare_album_cover_reference()
            if cover_note:
                reference_note = f"{cover_note}\n\n{reference_note}" if reference_note else cover_note
        if reference_note:
            prompt = f"{reference_note}\n\n{prompt}"

        setup_context = self._build_setup_context_from_metadata()
        if setup_context:
            prompt = setup_context + prompt

        persona_in_scene = False
        prompt_lower = prompt.lower()
        no_character_markers = [
            '[no characters]', '[no persona]', 'no characters', 'no persona present',
            'no human figures', 'no persona', 'no people', 'no artist', 'without any human',
            'purely environmental', 'purely abstract', 'no human presence',
            'characters: none', 'environmental shot - no human'
        ]
        scene_has_no_characters = any(marker in prompt_lower for marker in no_character_markers)
        if scene_has_no_characters:
            persona_in_scene = False
        if not scene_has_no_characters and self.current_persona:
            persona_name = self.current_persona.get('name', '').lower()
            visual_aesthetic = self.current_persona.get('visual_aesthetic', '').lower()
            base_image_prompt_cfg = self.current_persona.get('base_image_prompt', '').lower()

            if 'character: persona' in prompt_lower or 'character : persona' in prompt_lower:
                persona_in_scene = True
            else:
                metadata = self.current_song.get('storyboard_metadata', {}) if self.current_song else {}
                story_char_ids = [cid for cid, info in (metadata.get('characters') or {}).items()
                                 if isinstance(info, dict) and info.get('source') == 'story']
                has_story_char_only = False
                for sid in story_char_ids:
                    if f'character: {sid}' in prompt_lower or f'character : {sid}' in prompt_lower:
                        has_story_char_only = True
                        break
                if not has_story_char_only:
                    char_matches = re.findall(r'character\s*:\s*([a-zA-Z0-9_]+)', prompt_lower)
                    if char_matches and all(cid != 'persona' for cid in char_matches):
                        has_story_char_only = True
                if has_story_char_only:
                    persona_in_scene = False
                elif persona_name and persona_name in prompt_lower:
                    persona_in_scene = True
                elif any(kw in prompt_lower for kw in ['character', 'persona', 'singer', 'artist', 'performer', 'person', 'figure', 'protagonist', 'main character', 'vocalist', 'musician']):
                    persona_in_scene = True
                elif visual_aesthetic or base_image_prompt_cfg:
                    try:
                        self.config(cursor='wait')
                        self.update()
                        analysis_prompt = (
                            "Analyze this music video scene prompt and determine if it should feature the main artist/performer character.\n\n"
                            f"Scene Prompt: {prompt}\n\n"
                            f"Artist/Persona Name: {self.current_persona.get('name', '')}\n"
                        )
                        if visual_aesthetic:
                            analysis_prompt += f"Persona Visual Aesthetic: {self.current_persona.get('visual_aesthetic', '')}\n"
                        if base_image_prompt_cfg:
                            analysis_prompt += f"Persona Base Image Description: {self.current_persona.get('base_image_prompt', '')}\n"
                        analysis_prompt += "\nRespond with ONLY 'YES' if the persona should be featured, or 'NO' if not."
                        analysis_result = self.azure_ai(
                            analysis_prompt,
                            system_message="You are a music video analysis assistant. Respond with only YES or NO.",
                            profile='text'
                        )
                        if analysis_result['success']:
                            analysis_response = analysis_result['content'].strip().upper()
                            persona_in_scene = 'YES' in analysis_response
                        else:
                            persona_in_scene = False
                    except Exception as e:
                        self.log_debug('WARNING', f'Persona detection failed for scene {scene_num}: {e}')
                    finally:
                        self.config(cursor='')

        if persona_in_scene and self.current_persona:
            visual_aesthetic = self.current_persona.get('visual_aesthetic', '').strip()
            base_image_prompt = self.current_persona.get('base_image_prompt', '').strip()

            if self.current_persona_path:
                preset_key = self._get_song_persona_preset_key()
                base_path = self.get_persona_image_base_path(preset_key)
                safe_name = self._safe_persona_basename()
                front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
                if os.path.exists(front_image_path):
                    try:
                        from PIL import Image
                        original_img = Image.open(front_image_path)
                        new_width = original_img.width // 2
                        new_height = original_img.height // 2
                        downscaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        temp_dir = os.path.join(self.current_song_path if self.current_song_path else os.path.dirname(front_image_path), 'temp')
                        os.makedirs(temp_dir, exist_ok=True)
                        reference_image_path = os.path.join(temp_dir, f'{safe_name}-Front-downscaled.png')
                        backup_path = backup_file_if_exists(reference_image_path)
                        if backup_path:
                            self.log_debug('INFO', f'Backed up existing downscaled image to: {backup_path}')
                        downscaled_img.save(reference_image_path, 'PNG')

                        self.config(cursor='wait')
                        self.update()
                        vision_prompt = (
                            "Analyze this persona reference image in extreme detail. Provide a comprehensive description of the character's appearance, "
                            "including physical features, clothing, styling, colors, accessories, pose, and all visual characteristics. "
                            "This description will be used to ensure the scene image features the exact same character."
                        )
                        vision_system = (
                            "You are an image analysis assistant. Provide a highly detailed, objective description of the character's visual appearance "
                            "from the reference image. Focus on all visual characteristics that should be preserved in the scene image."
                        )
                        vision_result = self.azure_vision([reference_image_path], vision_prompt, system_message=vision_system, profile='text')
                        if vision_result['success']:
                            character_description = vision_result['content'].strip()
                            prompt = (
                                f"REFERENCE CHARACTER DESCRIPTION (from Front Persona Image - MUST MATCH EXACTLY):\n{character_description}\n\n"
                                f"{prompt}\n\n"
                                "CRITICAL REQUIREMENT: The character in this scene MUST be visually identical to the reference character description above. "
                                "Match all physical features, clothing, styling, colors, accessories, and visual characteristics exactly. "
                                "The character appearance must be consistent with the reference image."
                            )
                        else:
                            prompt += "\n\nIMPORTANT: Use the Front Persona Image as reference. The scene must feature this exact character with matching appearance, styling, and visual characteristics."

                        persona_visual_parts = []
                        if visual_aesthetic:
                            persona_visual_parts.append(f"Persona Visual Aesthetic: {visual_aesthetic}")
                        if base_image_prompt:
                            persona_visual_parts.append(f"Persona Base Image Prompt (Character Visual Description): {base_image_prompt}")
                        if persona_visual_parts:
                            prompt += "\n\n" + "\n".join(persona_visual_parts)
                            prompt += "\n\nIMPORTANT: The character in this scene must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."
                    except Exception as e:
                        self.log_debug('WARNING', f'Failed to prepare persona reference for scene {scene_num}: {e}')
                    finally:
                        self.config(cursor='')
            else:
                persona_visual_parts = []
                if visual_aesthetic:
                    persona_visual_parts.append(f"Persona Visual Aesthetic: {visual_aesthetic}")
                if base_image_prompt:
                    persona_visual_parts.append(f"Persona Base Image Prompt (Character Visual Description): {base_image_prompt}")
                if persona_visual_parts:
                    prompt += "\n\n" + "\n".join(persona_visual_parts)
                    prompt += "\n\nIMPORTANT: The character in this scene must fully incorporate ALL visual characteristics from the persona's Visual Aesthetic and Base Image Prompt descriptions above."

        if lyrics_text and '[NO LYRICS]' not in lyrics_text.upper():
            if scene_has_no_characters:
                prompt = self.sanitize_prompt_no_lyrics(prompt)
                prompt += (
                    "\n\nLyrics for mood only (keep scene text-free): "
                    f"\"{lyrics_text}\". Use the feeling of these words to shape lighting, color, and symbolism, but render NO visible text anywhere. "
                    "Do NOT embed, carve, or display the lyric words in the environment."
                )
            elif embed_lyrics_enabled:
                prompt += (
                    "\n\nLYRICS INTEGRATION (environment only, no overlays): "
                    f"\"{lyrics_text}\". Embed the words physically into the scene using materials like neon, etched metal, floor seams, glass reflections, or carved wood. "
                    "Do not float text or use subtitles; make the lyrics feel part of the environment."
                )
            else:
                prompt += (
                    "\n\nLyrics for mood only (keep scene text-free): "
                    f"\"{lyrics_text}\". Use the feeling of these words to shape lighting, color, and symbolism, but render no visible text."
                )
        if keyword and '[NO LYRICS]' not in (lyrics_text or '').upper() and not scene_has_no_characters:
            prompt += (
                f"\n\nOPTIONAL KEYWORD: \"{keyword}\". Only embed this word as diegetic text (signage, hologram, graffiti, screen UI) IF it naturally fits the scene and does not conflict with aesthetics. "
                "If it feels forced or breaks immersion, omit it and keep the scene text-free."
            )
        elif not lyrics_text:
            prompt += "\n\nNo lyrics for this scene; keep visuals text-free."

        enriched_prompt = prompt

        # Derive VIDEO prompt (add lip-sync, timing, multi-scene, character injection)
        video_prompt = enriched_prompt
        has_lyrics = bool(lyrics_text) and '[NO LYRICS]' not in (lyrics_text or '').upper()
        if persona_in_scene and has_lyrics:
            video_prompt += (
                f'\n\nCHARACTER SPEAKS/SINGS (lip-sync): "{lyrics_text}" '
                'The character must mouth these exact words. Do NOT use the story theme as dialogue.'
            )
        elif not scene_has_no_characters and not has_lyrics:
            video_prompt += (
                "\n\nCRITICAL - NO DIALOGUE IN THIS SCENE: "
                "This scene has NO lyrics. ALL characters, personas, and humans MUST be completely SILENT. "
                "DO NOT speak, DO NOT talk, DO NOT sing, DO NOT mouth any words. "
                "Lips closed, no dialogue, no voice, no singing, no speech. "
                "Characters may react visually only - no verbal communication whatsoever."
            )
        if lyrics_text and '[NO LYRICS]' not in lyrics_text.upper() and not scene_has_no_characters:
            try:
                seconds_per_video = int(self.storyboard_seconds_var.get() or '6') if hasattr(self, 'storyboard_seconds_var') else 6
                scene_start_seconds = 0.0
                storyboard = self.current_song.get('storyboard', []) if self.current_song else []
                for s in storyboard:
                    sv = s.get('scene')
                    if sv is not None and (sv == scene_num_int or str(sv) == str(scene_num)):
                        scene_start_seconds = self._parse_timestamp_to_seconds(s.get('timestamp', '0:00'))
                        break
                else:
                    scene_start_seconds = max(0.0, (scene_num_int - 1) * seconds_per_video) if scene_num_int else 0.0
                scene_end_seconds = scene_start_seconds + seconds_per_video
                extracted_lyrics = self.current_song.get('extracted_lyrics', '') if self.current_song else ''
                lyrics_with_timestamps = lyrics_text
                if extracted_lyrics and not re.search(r'\d+:\d+=\d+:\d+=', lyrics_text):
                    lyrics_with_timestamps = self._extract_timed_lyrics_for_scene(lyrics_text, extracted_lyrics, scene_start_seconds, scene_end_seconds)
                if lyrics_with_timestamps:
                    processed_lyrics = self._process_lyrics_for_lip_sync(lyrics_with_timestamps, scene_start_seconds, seconds_per_video)
                    if processed_lyrics:
                        video_prompt += "\n\nIMPORTANT: Synchronize lyrics by time index for lip-sync. Each word has exact start and end time (relative to scene 0-6s):"
                        video_prompt += "\n\n" + processed_lyrics
            except Exception as e:
                self.log_debug('WARNING', f'Failed to add lyrics timing to scene prompt: {e}')

        if is_multiscene and scene_has_no_characters and re.search(r'\[\d+(?:\.\d+)?s[-–]\d+(?:\.\d+)?s\]', video_prompt):
            seconds_val = int(self.storyboard_seconds_var.get() or '6') if hasattr(self, 'storyboard_seconds_var') else 6
            scene_dur = int(self.storyboard_scene_duration_var.get() or '2') if hasattr(self, 'storyboard_scene_duration_var') else 2
            cut1 = scene_dur
            cut2 = scene_dur * 2
            instruction = (
                f"MULTI-SCENE VIDEO: Create a {seconds_val}-second video with 3 DISTINCT shots. "
                f"HARD CUT at {cut1} seconds. HARD CUT at {cut2} seconds. "
                "Each [Xs-Ys] block describes a DIFFERENT shot - the video MUST show 3 different visuals/camera angles, not one continuous shot.\n\n"
            )
            video_prompt = instruction + video_prompt

        if is_multiscene and not scene_has_no_characters:
            character_registry = {}
            metadata = self.current_song.get('storyboard_metadata', {}) if self.current_song else {}
            for cid, info in (metadata.get('characters') or {}).items():
                if isinstance(info, dict) and info.get('description'):
                    character_registry[cid] = info
            if self.current_persona and 'persona' not in character_registry:
                base_ip = self.current_persona.get('base_image_prompt', '').strip()
                va = self.current_persona.get('visual_aesthetic', '').strip()
                if base_ip or va:
                    character_registry['persona'] = {
                        'label': self.current_persona.get('name', 'Artist'),
                        'description': f"{base_ip} {va}".strip()
                    }
            if character_registry:
                video_prompt = self._inject_character_descriptions_into_subscenes(video_prompt, character_registry)

        video_style = (self.storyboard_video_style_var.get() or 'Realism').strip() if hasattr(self, 'storyboard_video_style_var') else 'Realism'
        video_prompt = sanitize_video_prompt(video_prompt, video_style)

        # Derive IMAGE prompt - for multi-scene, use ONLY first sub-scene (single image, not triptych)
        if multiscene_scene1_image_special:
            image_prompt = self._build_multiscene_reference_image_prompt(base_key)
        else:
            image_prompt = enriched_prompt
            if re.search(r'\[\d+(?:\.\d+)?s[-–]\d+(?:\.\d+)?s\]', image_prompt):
                image_prompt = self._extract_first_subscene_for_single_image(image_prompt)

        result = {'image': image_prompt, 'video': video_prompt}
        self.scene_final_prompts[base_key] = result
        return result

    def build_scene_image_prompt(self, scene_num: str, base_prompt: str, lyrics: str = None, prompt_type: str = 'image') -> str:
        """Build the final prompt that gets sent to the image or video model.

        Thin wrapper over build_scene_prompts_both. Both prompts are built in one pass
        with shared AI work; returns the requested type.
        """
        both = self.build_scene_prompts_both(scene_num, base_prompt, lyrics)
        return both.get(prompt_type, '')
    
    def get_full_scene_prompt_for_saving(self, scene_num: str, base_prompt: str = None, lyrics: str = None) -> str:
        """Get the FULL scene prompt for saving/exporting, without any stripping.
        
        This is used when saving prompts to config.json or exporting - we want the
        complete multi-scene information preserved, not the stripped version used
        for single image generation.
        
        Args:
            scene_num: Scene number
            base_prompt: Base prompt text (optional)
            lyrics: Lyrics text (optional)
        
        Returns:
            Full prompt string with all multi-scene information intact
        """
        base_cache_key = f"{scene_num}|{self._get_song_persona_preset_key()}"
        if base_cache_key in self.scene_final_prompts:
            cached = self.scene_final_prompts[base_cache_key]
            if isinstance(cached, dict):
                return cached.get('video', '') or self.build_scene_image_prompt(scene_num, base_prompt, lyrics, 'video')
            if isinstance(cached, str):
                return cached

        return self.build_scene_image_prompt(scene_num, base_prompt, lyrics, 'video')
    
    def _save_storyboard_generated_prompt(self, scene_num: str, generated_prompt: str, prompt_type: str = 'image'):
        """Save the generated prompt to the storyboard scene in config.json.
        
        Args:
            scene_num: Scene number
            generated_prompt: The final prompt that was used for image or video generation
            prompt_type: Type of prompt - 'image' or 'video'
        """
        if not self.current_song_path or not self.current_song:
            return
        
        try:
            scene_num_int = int(scene_num) if str(scene_num).isdigit() else None
            # Prefer get_storyboard_data (tree + config merge) for latest state
            storyboard = []
            if hasattr(self, 'get_storyboard_data') and hasattr(self, 'storyboard_tree') and self.storyboard_tree.get_children():
                storyboard = self.get_storyboard_data()
            if not storyboard:
                storyboard = self.current_song.get('storyboard', [])
            
            # Find the scene in the storyboard
            for scene in storyboard:
                scene_value = scene.get('scene')
                # Handle both int and string scene numbers
                if (scene_num_int is not None and scene_value == scene_num_int) or str(scene_value) == str(scene_num):
                    # Save to the appropriate field (generated_prompt_image or generated_prompt_video)
                    field = 'generated_prompt_image' if prompt_type == 'image' else 'generated_prompt_video'
                    scene[field] = generated_prompt
                    # Remove legacy fields if present
                    scene.pop('generated_prompt', None)
                    scene.pop('generated_prompt_type', None)
                    self.log_debug('INFO', f'Saved {field} for scene {scene_num} to config.json')
                    
                    # Build config with updated storyboard (preserve other fields from current_song)
                    config_to_save = dict(self.current_song)
                    config_to_save['storyboard'] = storyboard
                    if save_song_config(self.current_song_path, config_to_save):
                        self.current_song['storyboard'] = storyboard
                        self.log_debug('INFO', f'Config.json updated with generated prompt for scene {scene_num}')
                    else:
                        self.log_debug('WARNING', f'Failed to save config.json for scene {scene_num}')
                    return
            
            # If scene not found, log a warning
            self.log_debug('WARNING', f'Scene {scene_num} not found in storyboard, could not save generated prompt')
        except Exception as e:
            self.log_debug('ERROR', f'Error saving generated prompt for scene {scene_num}: {e}')

    def get_multiscene_prompts_for_scene(self, scene_num: str, base_prompt: str = None, lyrics: str = None) -> dict:
        """Get both image and video prompts for a scene when multi-scene mode is enabled.

        Uses build_scene_prompts_both for a single pass when both are needed.

        Returns:
            Dictionary with 'image_prompt' and 'video_prompt' keys
        """
        if (base_prompt is None or lyrics is None) and self.current_song:
            storyboard = self.current_song.get('storyboard', [])
            scene_num_int = int(scene_num) if str(scene_num).isdigit() else None
            for scene in storyboard:
                sv = scene.get('scene')
                if (scene_num_int is not None and sv == scene_num_int) or str(sv) == str(scene_num):
                    if base_prompt is None:
                        base_prompt = scene.get('prompt', '')
                    if lyrics is None:
                        lyrics = scene.get('lyrics', '')
                    break
        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
        both = self.build_scene_prompts_both(scene_num, base_prompt or '', lyrics)

        image_prompt = both.get('image', '')
        video_prompt = both.get('video', '')

        if not is_multiscene:
            return {
                'image_prompt': image_prompt,
                'video_prompt': image_prompt,  # Same when not multi-scene
                'is_multiscene': False
            }
        return {
            'image_prompt': image_prompt,
            'video_prompt': video_prompt,
            'is_multiscene': True
        }

    def export_generated_prompts(self):
        """Export generated prompts to JSON files for each scene. User chooses IMAGE or VIDEO prompt type."""
        self.log_debug('DEBUG', '=== export_generated_prompts: Starting export ===')

        if not self.current_song_path or not self.current_song:
            self.log_debug('DEBUG', 'export_generated_prompts: No song selected')
            messagebox.showwarning('Warning', 'No song selected. Please select a song first.')
            return

        # Always export VIDEO prompts (images are generated directly via suno_persona.py)
        export_prompt_type = 'video'
        self.log_debug('DEBUG', 'export_generated_prompts: Export type: VIDEO (always)')

        self.log_debug('DEBUG', f'export_generated_prompts: Song path: {self.current_song_path}')

        storyboard = self.current_song.get('storyboard', [])
        self.log_debug('DEBUG', f'export_generated_prompts: Found {len(storyboard)} scenes in storyboard')
        
        if not storyboard:
            self.log_debug('DEBUG', 'export_generated_prompts: No storyboard scenes found')
            messagebox.showwarning('Warning', 'No storyboard scenes found.')
            return
        
        exported_count = 0
        skipped_count = 0
        errors = []
        
        # Get seconds per video for calculating scene duration
        seconds_per_video = int(self.storyboard_seconds_var.get() or '6') if hasattr(self, 'storyboard_seconds_var') else 6
        self.log_debug('DEBUG', f'export_generated_prompts: Seconds per video: {seconds_per_video}')
        
        stored_field = 'generated_prompt_image' if export_prompt_type == 'image' else 'generated_prompt_video'

        for idx, scene in enumerate(storyboard, 1):
            scene_num = scene.get('scene')
            stored_prompt = scene.get(stored_field, '')

            self.log_debug('DEBUG', f'export_generated_prompts: Processing scene {scene_num} ({idx}/{len(storyboard)})')
            self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - has {stored_field}: {bool(stored_prompt)}')

            # Get or build prompt
            final_prompt = stored_prompt or self.get_scene_final_prompt(
                str(scene_num), scene.get('prompt', ''), scene.get('lyrics', ''), export_prompt_type
            )
            if not final_prompt:
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Skipping (no prompt)')
                skipped_count += 1
                continue
            
            try:
                safe_scene = str(scene_num).replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
                json_filename = os.path.join(self.current_song_path, f'storyboard_scene_{safe_scene}.json')
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - JSON filename: {json_filename}')
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - prompt length: {len(final_prompt)} chars')
                
                lyrics = scene.get('lyrics', '')
                processed_lyrics = ''
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - has lyrics: {bool(lyrics)}, lyrics length: {len(lyrics) if lyrics else 0} chars')
                
                # Check if lyrics should be included (checkbox enabled)
                include_lyrics = self.include_lyrics_in_export_var.get() if hasattr(self, 'include_lyrics_in_export_var') else False
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - include_lyrics checkbox: {include_lyrics}')
                
                # Add exact lyrics timing for any scene with lyrics when include_lyrics is on
                if lyrics and include_lyrics:
                    # Parse scene start time from timestamp
                    scene_timestamp = scene.get('timestamp', '0:00')
                    scene_start_seconds = self._parse_timestamp_to_seconds(scene_timestamp)
                    scene_end_seconds = scene_start_seconds + seconds_per_video
                    self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - timestamp: {scene_timestamp}, start_seconds: {scene_start_seconds}, end_seconds: {scene_end_seconds}')
                    
                    # Check if lyrics are in timestamp format, if not, try to get from extracted_lyrics
                    lyrics_with_timestamps = lyrics
                    if not re.search(r'\d+:\d+=\d+:\d+=', lyrics):
                        # Lyrics are plain text, try to get timed lyrics from extracted_lyrics
                        self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Lyrics are plain text, looking up timestamps from extracted_lyrics')
                        extracted_lyrics = self.current_song.get('extracted_lyrics', '')
                        if extracted_lyrics:
                            lyrics_with_timestamps = self._extract_timed_lyrics_for_scene(lyrics, extracted_lyrics, scene_start_seconds, scene_end_seconds)
                            self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Extracted timed lyrics length: {len(lyrics_with_timestamps) if lyrics_with_timestamps else 0} chars')
                        else:
                            self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - No extracted_lyrics available, cannot convert plain text to timed format')
                            lyrics_with_timestamps = ''
                    
                    # Convert to scene-relative times (0:00-0:06) for lip-sync within the 6s clip
                    processed_lyrics = self._process_lyrics_for_lip_sync(lyrics_with_timestamps, scene_start_seconds, seconds_per_video)
                    self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - processed_lyrics length: {len(processed_lyrics) if processed_lyrics else 0} chars')
                else:
                    if not include_lyrics:
                        self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Skipping lyrics timing (include_lyrics checkbox disabled)')
                    elif not lyrics:
                        self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Skipping lyrics timing (no lyrics)')
                
                # Add lyrics timing only for VIDEO prompts and only when scene has a character to lip-sync
                scene_has_no_characters = any(m in final_prompt.lower() for m in (
                    '[no characters]', 'no characters', 'no persona present', 'no human figures',
                    'purely environmental', 'purely abstract', '[no persona]', 'environmental shot - no human'
                ))
                if export_prompt_type == 'video' and processed_lyrics and not scene_has_no_characters:
                    has_timing = ('Words and timeindex' in final_prompt or 'Words and time index' in final_prompt or
                                  re.search(r'\n\d+\.\d+s-\d+\.\d+s:', final_prompt))
                    if not has_timing:
                        final_prompt += "\n\nIMPORTANT: Synchronize lyrics by time index for lip-sync. Each word has exact start and end time (relative to scene 0-6s):"
                        final_prompt += "\n\n" + processed_lyrics

                # Ensure VIDEO prompts for persona/character scenes without lyrics include explicit NO DIALOGUE block
                if export_prompt_type == 'video' and not lyrics:
                    lyrics_clean = (lyrics or '').strip().upper()
                    if not lyrics_clean or lyrics_clean == '[NO LYRICS]':
                        no_char = [
                            '[no characters]', 'no characters', 'no persona present', 'no human figures',
                            'purely environmental', 'purely abstract', '[no persona]', 'environmental shot - no human'
                        ]
                        prompt_lower = final_prompt.lower()
                        if not any(m in prompt_lower for m in no_char):
                            if 'CRITICAL - NO DIALOGUE' not in final_prompt and 'completely SILENT' not in final_prompt:
                                final_prompt += (
                                    "\n\nCRITICAL - NO DIALOGUE IN THIS SCENE: "
                                    "This scene has NO lyrics. ALL characters, personas, and humans MUST be completely SILENT. "
                                    "DO NOT speak, DO NOT talk, DO NOT sing, DO NOT mouth any words. "
                                    "Lips closed, no dialogue, no voice, no singing, no speech. "
                                    "Characters may react visually only - no verbal communication whatsoever."
                                )
                                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Added NO DIALOGUE block (persona scene, no lyrics)')

                is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
                usage_note = 'IMAGE PROMPT: Use this prompt for image generation.' if export_prompt_type == 'image' else 'VIDEO PROMPT: Use this prompt for video generation.'
                export_data = {
                    'generated_prompt': final_prompt,
                    'prompt_type': export_prompt_type,
                    'is_multiscene': is_multiscene,
                    'usage_note': usage_note
                }

                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Final prompt length: {len(final_prompt)} chars, type: {export_prompt_type}')
                
                # Write JSON file
                with open(json_filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                exported_count += 1
                self.log_debug('INFO', f'Exported generated prompt for scene {scene_num} to {json_filename}')
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Export successful')
                
            except Exception as e:
                error_msg = f'Error exporting scene {scene_num}: {e}'
                errors.append(error_msg)
                self.log_debug('ERROR', error_msg)
                import traceback
                self.log_debug('DEBUG', f'export_generated_prompts: Scene {scene_num} - Exception traceback:\n{traceback.format_exc()}')
        
        # Show result message
        self.log_debug('DEBUG', f'=== export_generated_prompts: Summary ===')
        self.log_debug('DEBUG', f'export_generated_prompts: Exported: {exported_count}, Skipped: {skipped_count}, Errors: {len(errors)}')
        
        if exported_count > 0:
            if errors:
                messagebox.showwarning('Partial Success', 
                    f'Exported {exported_count} scene(s) successfully.\n\nErrors:\n' + '\n'.join(errors))
            else:
                messagebox.showinfo('Success', f'Exported {exported_count} scene(s) successfully.')
        else:
            messagebox.showwarning('Warning', f'No scenes with {stored_field} found to export. (Skipped {skipped_count} scenes without prompt)')
    
    def _load_extracted_lyrics_from_json(self, song_path: str) -> str:
        """Load extracted_lyrics format from lyrics_transcription.json when config has none."""
        if not song_path or not os.path.isdir(song_path):
            return ''
        json_path = os.path.join(song_path, 'lyrics_transcription.json')
        if not os.path.isfile(json_path):
            return ''
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            lines = []
            for entry in data:
                if not isinstance(entry, dict) or not entry.get('text'):
                    continue
                start = entry.get('timestamp', 0)
                end = entry.get('end_timestamp')
                if end is not None:
                    ts = self._format_timestamp_mm_ss_mmm(start)
                    end_ts = self._format_timestamp_mm_ss_mmm(end)
                    lines.append(f"{ts}={end_ts}={entry['text']}")
                else:
                    ts = self._format_timestamp_mm_ss_mmm(start)
                    lines.append(f"{ts}={entry['text']}")
            return '\n'.join(lines) if lines else ''
        except Exception:
            return ''

    def _get_lyrics_timing_list_for_scene(self, scene_start_seconds: float, scene_end_seconds: float) -> list:
        """Get word-level lyrics timing as list of {text, start_ms, end_ms} for lip-sync.
        Loads from lyrics_transcription.json or lyrics_transcription_raw.json when available.
        """
        song_path = getattr(self, 'current_song_path', None) or ''
        if not song_path or not os.path.isdir(song_path):
            return []
        result = []
        json_path = os.path.join(song_path, 'lyrics_transcription.json')
        if os.path.isfile(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for entry in data:
                    if not isinstance(entry, dict) or not entry.get('text'):
                        continue
                    start = entry.get('timestamp', 0)
                    end = entry.get('end_timestamp', start)
                    if start < scene_end_seconds and end > scene_start_seconds:
                        result.append({
                            'text': entry['text'],
                            'start_ms': int(start * 1000),
                            'end_ms': int(end * 1000)
                        })
                if result:
                    return result
            except Exception:
                pass
        raw_path = os.path.join(song_path, 'lyrics_transcription_raw.json')
        if os.path.isfile(raw_path):
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                scene_start_ms = int(scene_start_seconds * 1000)
                scene_end_ms = int(scene_end_seconds * 1000)
                for phrase in raw_data.get('phrases', []):
                    for w in phrase.get('words', []):
                        offset_ms = w.get('offsetMilliseconds', 0)
                        dur_ms = w.get('durationMilliseconds', 0)
                        end_ms = offset_ms + dur_ms
                        if offset_ms < scene_end_ms and end_ms > scene_start_ms:
                            result.append({'text': w.get('text', ''), 'start_ms': offset_ms, 'end_ms': end_ms})
                if result:
                    return result
            except Exception:
                pass
        return []

    def _parse_timestamp_with_ms_to_seconds(self, ts_str: str) -> float:
        """Parse timestamp 'M:SS' or 'M:SS.mmm' to seconds."""
        try:
            if '.' in ts_str:
                main, ms_part = ts_str.rsplit('.', 1)
                ms = int(ms_part[:3].ljust(3, '0'))  # up to 3 digits
            else:
                main, ms = ts_str, 0
            parts = main.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1]) + (ms / 1000.0)
            return 0.0
        except Exception:
            return 0.0

    def _extract_timed_lyrics_for_scene(self, plain_lyrics: str, extracted_lyrics: str, scene_start_seconds: float, scene_end_seconds: float) -> str:
        """Extract timed lyrics that fall within the scene time range.

        Prefers lyrics_transcription.json or lyrics_transcription_raw.json when available
        (millisecond precision). Falls back to extracted_lyrics text parsing.

        Supports formats:
        - Double-equals: 0:32=00:42=hit or 0:04.400=0:05.200=Morgengrauen (start=end=word)
        - Single-equals: 0:43=You (timestamp=word)

        Returns:
            Timed lyrics string (start=end=word format) that fall within scene bounds
        """
        song_path = getattr(self, 'current_song_path', None) or ''
        if song_path and os.path.isdir(song_path):
            # Prefer lyrics_transcription.json (word-level with end_timestamp)
            json_path = os.path.join(song_path, 'lyrics_transcription.json')
            if os.path.isfile(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        lyrics_data = json.load(f)
                    matched = []
                    for entry in lyrics_data:
                        if not isinstance(entry, dict) or not entry.get('text'):
                            continue
                        start = entry.get('timestamp', 0)
                        end = entry.get('end_timestamp')
                        if end is None:
                            end = start
                        if start < scene_end_seconds and end > scene_start_seconds:
                            ts_fmt = self._format_timestamp_mm_ss_mmm(start)
                            end_fmt = self._format_timestamp_mm_ss_mmm(end)
                            matched.append(f"{ts_fmt}={end_fmt}={entry['text']}")
                    if matched:
                        return '\n'.join(matched)
                except Exception as e:
                    self.log_debug('DEBUG', f'_extract_timed_lyrics: lyrics_transcription.json load failed: {e}')
            # Prefer lyrics_transcription_raw.json (millisecond precision)
            raw_path = os.path.join(song_path, 'lyrics_transcription_raw.json')
            if os.path.isfile(raw_path):
                try:
                    with open(raw_path, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)
                    scene_start_ms = int(scene_start_seconds * 1000)
                    scene_end_ms = int(scene_end_seconds * 1000)
                    matched = []
                    for phrase in raw_data.get('phrases', []):
                        for w in phrase.get('words', []):
                            offset_ms = w.get('offsetMilliseconds', 0)
                            dur_ms = w.get('durationMilliseconds', 0)
                            end_ms = offset_ms + dur_ms
                            if offset_ms < scene_end_ms and end_ms > scene_start_ms:
                                start_sec = offset_ms / 1000.0
                                end_sec = end_ms / 1000.0
                                ts_fmt = self._format_timestamp_mm_ss_mmm(start_sec)
                                end_fmt = self._format_timestamp_mm_ss_mmm(end_sec)
                                matched.append(f"{ts_fmt}={end_fmt}={w.get('text', '')}")
                    if matched:
                        return '\n'.join(matched)
                except Exception as e:
                    self.log_debug('DEBUG', f'_extract_timed_lyrics: lyrics_transcription_raw.json load failed: {e}')

        if not extracted_lyrics:
            return ''

        lines = extracted_lyrics.strip().split('\n')
        double_equals_pattern = re.compile(r'^(\d+):(\d+)(?:\.(\d+))?=(\d+):(\d+)(?:\.(\d+))?=(.+)$')
        single_equals_pattern = re.compile(r'^(\d+):(\d+)(?:\.(\d+))?=(.+)$')
        matched_entries = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            match = double_equals_pattern.match(line)
            if match:
                sm, ss, sms, em, es, ems, word = match.groups()
                absolute_start = int(sm) * 60 + int(ss) + (int(sms or 0) / 1000.0)
                absolute_end = int(em) * 60 + int(es) + (int(ems or 0) / 1000.0)
                if absolute_start < scene_end_seconds and absolute_end > scene_start_seconds:
                    matched_entries.append(line)
                continue

            single_match = single_equals_pattern.match(line)
            if single_match:
                sm, ss, sms, word = single_match.group(1), single_match.group(2), single_match.group(3), single_match.group(4).strip()
                absolute_start = int(sm) * 60 + int(ss) + (int(sms or 0) / 1000.0)
                if absolute_start >= scene_end_seconds:
                    continue
                if absolute_start < scene_start_seconds:
                    continue
                # Infer end: next line's start, or start+0.5s
                next_start = None
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    nm = single_equals_pattern.match(next_line)
                    if nm:
                        next_start = int(nm.group(1)) * 60 + int(nm.group(2)) + (int(nm.group(3) or 0) / 1000.0)
                        break
                    dm = double_equals_pattern.match(next_line)
                    if dm:
                        next_start = int(dm.group(1)) * 60 + int(dm.group(2)) + (int(dm.group(3) or 0) / 1000.0)
                        break
                absolute_end = next_start if next_start is not None else absolute_start + 0.5
                ts_fmt = self._format_timestamp_mm_ss_mmm(absolute_start)
                end_fmt = self._format_timestamp_mm_ss_mmm(absolute_end)
                matched_entries.append(f"{ts_fmt}={end_fmt}={word}")

        return '\n'.join(matched_entries)
    
    def _parse_timestamp_to_seconds(self, timestamp: str) -> float:
        """Parse timestamp string (M:SS or M:SS.mmm format) to seconds."""
        try:
            parts = timestamp.split(':')
            if len(parts) == 2:
                minutes = int(parts[0])
                sec_part = parts[1]
                if '.' in sec_part:
                    sec_str, ms_str = sec_part.split('.', 1)
                    seconds = int(sec_str) + int(ms_str[:3].ljust(3, '0')) / 1000.0
                else:
                    seconds = int(sec_part)
                return minutes * 60 + seconds
            return 0.0
        except Exception:
            return 0.0
    
    def _process_lyrics_for_lip_sync(self, lyrics: str, scene_start_seconds: float, scene_duration: int) -> str:
        """Process lyrics to convert time indices from absolute to relative (starting from 0).
        Output preserves start and end for precise lip-sync: "0.000s-0.800s: Morgengrauen"

        Args:
            lyrics: Lyrics text with timestamps in format 0:32=00:42=hit or 0:04.400=0:05.200=word
            scene_start_seconds: Scene start time in seconds (absolute)
            scene_duration: Scene duration in seconds

        Returns:
            Processed lyrics with relative start-end per word for lip-sync
        """
        if not lyrics:
            return ''
        lines = lyrics.strip().split('\n')
        processed_lines = []
        double_equals_pattern = re.compile(r'^(\d+):(\d+)(?:\.(\d+))?=(\d+):(\d+)(?:\.(\d+))?=(.+)$')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = double_equals_pattern.match(line)
            if match:
                sm, ss, sms, em, es, ems, word = match.groups()
                absolute_start = int(sm) * 60 + int(ss) + (int(sms or 0) / 1000.0)
                absolute_end = int(em) * 60 + int(es) + (int(ems or 0) / 1000.0)
                relative_start = max(0.0, absolute_start - scene_start_seconds)
                relative_end = absolute_end - scene_start_seconds
                if relative_start >= scene_duration:
                    continue
                clamped_end = min(relative_end, float(scene_duration))
                processed_line = f"{relative_start:.3f}s-{clamped_end:.3f}s: {word.strip()}"
                processed_lines.append(processed_line)
        return '\n'.join(processed_lines)

    def _format_lyrics_extracted_style(self, lyrics_with_timestamps: str) -> str:
        """Format timed lyrics in extracted_lyrics style: timestamp=word (absolute times).
        
        The video AI needs per-word timing like extracted_lyrics (e.g. 0:43=You, 0:44=built).
        Input is double-equals format (start=end=word); output is single-equals (timestamp=word).
        
        Args:
            lyrics_with_timestamps: Timed lyrics in 0:32=00:42=word format
            
        Returns:
            Lyrics in extracted_lyrics format: M:SS=word per line
        """
        if not lyrics_with_timestamps:
            return ''
        lines = lyrics_with_timestamps.strip().split('\n')
        double_equals_pattern = re.compile(r'^(\d+):(\d+)=(\d+):(\d+)=(.+)$')
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = double_equals_pattern.match(line)
            if m:
                start_min, start_sec, word = int(m.group(1)), int(m.group(2)), m.group(5).strip()
                out.append(f"{start_min}:{start_sec:02d}={word}")
        return '\n'.join(out)

    def generate_all_prompts(self):
        """Generate prompts for all storyboard scenes and save them to config.json."""
        if not self.current_song_path or not self.current_song:
            messagebox.showwarning('Warning', 'No song selected. Please select a song first.')
            return
        
        # Reload storyboard from config.json on disk to use actual file state (avoids stale in-memory data)
        storyboard = []
        config_file = os.path.join(self.current_song_path, 'config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    disk_config = json.load(f)
                    storyboard = disk_config.get('storyboard', [])
                if storyboard:
                    self.current_song['storyboard'] = storyboard
            except Exception as e:
                self.log_debug('WARNING', f'Could not reload config from disk: {e}')
        if not storyboard:
            storyboard = self.current_song.get('storyboard', [])
        if not storyboard:
            messagebox.showwarning('Warning', 'No storyboard scenes found. Please generate storyboard first.')
            return
        
        response = messagebox.askyesno('Generate All Prompts', 
            f'Generate prompts for all {len(storyboard)} scenes? This may take a while.')
        if not response:
            return
        
        # Clear prompt cache so prompts are rebuilt with current logic (e.g. lyrics timing)
        self.scene_final_prompts = {}
        
        # Create progress dialog
        progress_dialog = ProgressDialog(self, len(storyboard), 'Generating Storyboard Prompts')
        progress_dialog.update()
        
        generated_count = 0
        errors = []
        
        for idx, scene in enumerate(storyboard, 1):
            if progress_dialog.is_cancelled():
                self.log_debug('INFO', 'Prompt generation cancelled by user')
                break
            
            scene_num = scene.get('scene')
            base_prompt = scene.get('prompt', '')
            lyrics = scene.get('lyrics', '')
            
            # Fallback for scenes with no base prompt: use lyrics or a generic placeholder
            if not base_prompt:
                base_prompt = (lyrics or '').strip()
            if not base_prompt:
                base_prompt = "Atmospheric scene matching the song's mood and narrative flow."
            
            try:
                progress_dialog.update_progress(idx, f'Generating prompts for scene {scene_num} ({idx}/{len(storyboard)})...')
                self.update()  # Flush UI so each scene is visible before slow build_scene_prompts_both runs

                # Build both prompts in one pass (1x AI work per scene)
                both = self.build_scene_prompts_both(str(scene_num), base_prompt, lyrics)
                image_prompt = both.get('image', '')
                video_prompt = both.get('video', '')

                if image_prompt:
                    self._save_storyboard_generated_prompt(str(scene_num), image_prompt, 'image')
                if video_prompt:
                    self._save_storyboard_generated_prompt(str(scene_num), video_prompt, 'video')

                generated_count += 1
                self.log_debug('INFO', f'Generated and saved image+video prompts for scene {scene_num}')
                
            except Exception as e:
                error_msg = f'Error generating prompt for scene {scene_num}: {e}'
                errors.append(error_msg)
                self.log_debug('ERROR', error_msg)
        
        # Close progress dialog
        progress_dialog.destroy()
        
        # Show result message
        if generated_count > 0:
            if errors:
                messagebox.showwarning('Partial Success', 
                    f'Generated {generated_count} prompt(s) successfully.\n\nErrors:\n' + '\n'.join(errors))
            else:
                messagebox.showinfo('Success', f'Generated {generated_count} prompt(s) successfully and saved to config.json.')
        else:
            messagebox.showwarning('Warning', 'No prompts were generated.')

    def generate_storyboard_image(self, scene_num: str, prompt: str, show_success_message: bool = True, lyrics: str = None):
        """Generate image for a storyboard scene.
        
        Args:
            scene_num: Scene number
            prompt: Image generation prompt
            show_success_message: If True, show success messagebox (default True for single image generation)
            lyrics: Optional lyrics text to overlay on the image
        
        Returns:
            True if image was generated successfully or already exists, False otherwise
        """
        if not self.current_song_path:
            return False

        safe_scene = str(scene_num).replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        image_filename = os.path.join(self.current_song_path, f'storyboard_scene_{safe_scene}.png')
        image_exists = os.path.exists(image_filename)

        if image_exists:
            self.log_debug('INFO', f'Scene {scene_num} image already exists, will show preview dialog: {image_filename}')

        # Get the final prompt, checking saved generated_prompt first
        final_prompt = self.get_scene_final_prompt(scene_num, prompt, lyrics)
        
        # Apply embed_lyrics setting (for both stored and newly built prompts)
        embed_enabled = bool(self.embed_lyrics_var.get()) if hasattr(self, 'embed_lyrics_var') else True
        if not embed_enabled:
            embed_note = "\n\nDO NOT embed lyrics as text in the scene. No visible text anywhere. Focus on visuals only."
            # Only add if not already present (to avoid duplication)
            if embed_note.strip() not in final_prompt:
                final_prompt += embed_note
        self.log_debug('INFO', f'Generating image for scene {scene_num}...')
        self.config(cursor='wait')
        self.update()

        image_size = self.get_storyboard_image_size()
        
        # Get selected profile for storyboard images
        selected_profile = 'image_gen'
        if hasattr(self, 'storyboard_image_profile_var'):
            selected_profile = self.storyboard_image_profile_var.get() or 'image_gen'

        try:
            result = self.azure_image(final_prompt, size=image_size, profile=selected_profile)

            if result['success']:
                img_bytes = result.get('image_bytes', b'')
                if img_bytes:
                    if image_exists:
                        temp_filename = os.path.join(self.current_song_path, f'storyboard_scene_{safe_scene}_temp.png')
                        with open(temp_filename, 'wb') as f:
                            f.write(img_bytes)
                        self.log_debug('INFO', f'Scene {scene_num} image generated, saved to temp file: {temp_filename}')

                        preview_dialog = ImagePreviewDialog(self, temp_filename, image_filename, scene_num)
                        self.wait_window(preview_dialog)

                        if preview_dialog.result is True:
                            shutil.move(temp_filename, image_filename)
                            self.log_debug('INFO', f'Scene {scene_num} image overwritten: {image_filename}')
                            overlay_enabled = bool(self.overlay_lyrics_var.get()) if hasattr(self, 'overlay_lyrics_var') else False
                            if lyrics and overlay_enabled:
                                self.overlay_lyrics_on_image(image_filename, lyrics, scene_num)
                            # Save generated prompt: for scene 1 multi-scene with persona, save actual prompt used (reference image)
                            is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
                            use_ref_for_scene1 = (is_multiscene and str(scene_num) == '1' and self.current_persona and
                                                self._storyboard_has_any_persona_or_character())
                            if use_ref_for_scene1:
                                self._save_storyboard_generated_prompt(scene_num, final_prompt, 'image')
                            else:
                                full_prompt_for_save = self.get_full_scene_prompt_for_saving(scene_num, prompt, lyrics)
                                self._save_storyboard_generated_prompt(scene_num, full_prompt_for_save, 'video')
                            if show_success_message:
                                messagebox.showinfo('Success', f'Scene {scene_num} image generated and saved!')
                            return True
                        elif preview_dialog.result is False:
                            try:
                                os.remove(temp_filename)
                                self.log_debug('INFO', f'Scene {scene_num} - kept existing image, deleted temp file')
                            except Exception as e:
                                self.log_debug('WARNING', f'Failed to delete temp file: {e}')
                            if show_success_message:
                                messagebox.showinfo('Info', f'Scene {scene_num} - kept existing image.')
                            return True
                        else:
                            try:
                                os.remove(temp_filename)
                                self.log_debug('INFO', f'Scene {scene_num} - cancelled, deleted temp file')
                            except Exception as e:
                                self.log_debug('WARNING', f'Failed to delete temp file: {e}')
                            return False
                    else:
                        with open(image_filename, 'wb') as f:
                            f.write(img_bytes)
                        self.log_debug('INFO', f'Scene {scene_num} image saved: {image_filename}')

                        overlay_enabled = bool(self.overlay_lyrics_var.get()) if hasattr(self, 'overlay_lyrics_var') else False
                        if lyrics and overlay_enabled:
                            self.overlay_lyrics_on_image(image_filename, lyrics, scene_num)

                        # Save generated prompt: for scene 1 multi-scene with persona, save actual prompt used (reference image)
                        is_multiscene = self.storyboard_multiscene_var.get() if hasattr(self, 'storyboard_multiscene_var') else False
                        use_ref_for_scene1 = (is_multiscene and str(scene_num) == '1' and self.current_persona and
                                            self._storyboard_has_any_persona_or_character())
                        if use_ref_for_scene1:
                            self._save_storyboard_generated_prompt(scene_num, final_prompt, 'image')
                        else:
                            full_prompt_for_save = self.get_full_scene_prompt_for_saving(scene_num, prompt, lyrics)
                            self._save_storyboard_generated_prompt(scene_num, full_prompt_for_save, 'video')
                        if show_success_message:
                            messagebox.showinfo('Success', f'Scene {scene_num} image generated successfully!')
                        return True
                else:
                    self.log_debug('ERROR', f'No image bytes received for scene {scene_num}')
                    if show_success_message:
                        messagebox.showerror('Error', f'No image bytes received for scene {scene_num}')
                    return False
            else:
                self.log_debug('ERROR', f'Failed to generate image for scene {scene_num}: {result["error"]}')
                if show_success_message:
                    messagebox.showerror('Error', f'Failed to generate image for scene {scene_num}: {result["error"]}')
                return False
        except Exception as e:
            self.log_debug('ERROR', f'Error generating image for scene {scene_num}: {e}')
            if show_success_message:
                messagebox.showerror('Error', f'Error generating image for scene {scene_num}: {e}')
            return False
        finally:
            self.config(cursor='')
    
    def run_image_model(self):
        """Run the image generation model."""
        prompt = self.album_cover_text.get('1.0', tk.END).strip()
        if not prompt or prompt.startswith('Error:'):
            messagebox.showwarning('Warning', 'Please generate an album cover prompt first.')
            return
        self.last_song_cover_path = ''
        
        dialog = ExtraCommandsDialog(self, prompt)
        self.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        if dialog.result:
            prompt = f"{prompt} {dialog.result}"
        
        include_persona = self.include_persona_in_cover_var.get() if hasattr(self, 'include_persona_in_cover_var') else True
        # Check if Front Persona Image exists and analyze it for reference (only when including persona in cover)
        if include_persona and self.current_persona and self.current_persona_path:
            preset_key = self._get_song_persona_preset_key()
            base_path = self.get_persona_image_base_path(preset_key)
            safe_name = self._safe_persona_basename()
            front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
            
            if os.path.exists(front_image_path):
                try:
                    # Downscale Front image by 50% for analysis
                    from PIL import Image
                    original_img = Image.open(front_image_path)
                    new_width = original_img.width // 2
                    new_height = original_img.height // 2
                    downscaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Save to temporary file
                    temp_dir = os.path.join(self.current_song_path if self.current_song_path else os.path.dirname(front_image_path), 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    reference_image_path = os.path.join(temp_dir, f'{safe_name}-Front-downscaled.png')
                    backup_path = backup_file_if_exists(reference_image_path)
                    if backup_path:
                        self.log_debug('INFO', f'Backed up existing downscaled image to: {backup_path}')
                    downscaled_img.save(reference_image_path, 'PNG')
                    
                    # Analyze the reference image using vision API to get detailed description
                    self.log_debug('INFO', f'Analyzing Front Persona Image for album cover reference...')
                    vision_prompt = "Analyze this persona reference image in extreme detail. Provide a comprehensive description of the character's appearance, including: physical features, clothing, styling, colors, accessories, pose, and all visual characteristics. This description will be used to ensure the album cover features the exact same character."
                    vision_system = "You are an image analysis assistant. Provide a highly detailed, objective description of the character's visual appearance from the reference image. Focus on all visual characteristics that should be preserved in the album cover."
                    
                    vision_result = self.azure_vision([reference_image_path], vision_prompt, system_message=vision_system, profile='text')
                    
                    if vision_result['success']:
                        character_description = vision_result['content'].strip()
                        prompt += f"\n\nREFERENCE CHARACTER DESCRIPTION (from Front Persona Image):\n{character_description}\n\n"
                        prompt += "IMPORTANT: The album cover MUST feature this exact character with matching appearance, styling, and visual characteristics as described above. The character in the album cover must be visually consistent with the reference image."
                        self.log_debug('INFO', f'Added character description from Front Persona Image to prompt')
                    else:
                        # Fallback: just reference the image exists
                        prompt += f"\n\nIMPORTANT: Use the Front Persona Image as reference. The album cover must feature this exact character with matching appearance, styling, and visual characteristics."
                        self.log_debug('WARNING', f'Failed to analyze reference image: {vision_result.get("error", "Unknown error")}')
                    
                    self.log_debug('INFO', f'Using Front Persona Image as reference: {front_image_path}')
                except Exception as e:
                    self.log_debug('WARNING', f'Failed to prepare reference image: {e}')
        
        full_song_name = self.full_song_name_var.get().strip() or 'album_cover'
        safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        
        self.log_debug('INFO', 'Calling Azure Image model...')
        self.config(cursor='wait')
        self.update()
        
        # Get image size and format from configuration
        image_size = self.get_album_cover_image_size()
        image_format = self.get_album_cover_format()
        
        # Get selected profile for album cover
        selected_profile = 'image_gen'
        if hasattr(self, 'album_cover_profile_var'):
            selected_profile = self.album_cover_profile_var.get() or 'image_gen'
        
        try:
            result = self.azure_image(prompt, size=image_size, profile=selected_profile, output_format=image_format)
        finally:
            self.config(cursor='')
        
        if not result['success']:
            messagebox.showerror('Error', f"Image generation failed: {result['error']}")
            self.log_debug('ERROR', f"Image generation failed: {result['error']}")
            return
        
        img_bytes = result.get('image_bytes', b'')
        if not img_bytes:
            messagebox.showerror('Error', 'No image bytes received')
            return
        
        # Save to song folder with Full Song Name
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'No song selected. Cannot save album cover.')
            return
        
        full_song_name = self.full_song_name_var.get().strip()
        if not full_song_name:
            full_song_name = self.song_name_var.get().strip() or 'album_cover'
        
        # Generate safe filename from Full Song Name with correct extension
        safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
        file_extension = '.jpg' if image_format == 'jpeg' else '.png'
        
        # Extract aspect ratio from size (e.g., "1:1 (1024x1024)" -> "1:1" -> "1x1")
        aspect_ratio_suffix = ''
        if hasattr(self, 'album_cover_size_var'):
            size_value = self.album_cover_size_var.get()
            # Extract aspect ratio part before parentheses (e.g., "1:1" from "1:1 (1024x1024)")
            match = re.search(r'^([^\(]+)', size_value)
            if match:
                aspect_ratio = match.group(1).strip()
                # Convert ":" to "x" (e.g., "1:1" -> "1x1", "3:2" -> "3x2")
                aspect_ratio_x = aspect_ratio.replace(':', 'x')
                # Only append if not 1x1
                if aspect_ratio_x != '1x1':
                    aspect_ratio_suffix = aspect_ratio_x
        
        filename = os.path.join(self.current_song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}{file_extension}')
        
        # Create backup if file exists
        backup_path = self.backup_file_if_exists(filename)
        
        try:
            with open(filename, 'wb') as f:
                f.write(img_bytes)
            self.log_debug('INFO', f'Album cover saved to {filename}')
            success_msg = f'Album cover saved to:\n{filename}'
            if backup_path:
                success_msg += f'\n\nBackup created: {os.path.basename(backup_path)}'
            messagebox.showinfo('Success', success_msg)
            self.last_song_cover_path = filename
            self.show_image_preview(filename, 'Song Cover Preview')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save album cover: {e}')
            self.log_debug('ERROR', f'Failed to save album cover: {e}')
    
    def bulk_generate_covers(self):
        """Open dialog for bulk cover generation."""
        if not self.current_persona_path:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        dialog = BulkCoverDialog(self)
        self.wait_window(dialog)
        
        if not dialog.result:
            return
        
        scope = dialog.result['scope']
        size = dialog.result['size']
        format_type = dialog.result['format']
        overwrite = dialog.result['overwrite']
        include_persona = dialog.result.get('include_persona', True)
        
        # Get songs based on scope
        songs_to_process = []
        songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
        
        if scope == 'all_persona':
            # All songs from persona
            if os.path.exists(songs_dir):
                for item in os.listdir(songs_dir):
                    item_path = os.path.join(songs_dir, item)
                    if os.path.isdir(item_path):
                        songs_to_process.append(item_path)
        elif scope == 'current_album':
            # Only songs from current album
            if not self.current_album_id:
                messagebox.showwarning('Warning', 'No album selected. Please select an album first or choose "All songs from Persona".')
                return
            if os.path.exists(songs_dir):
                for item in os.listdir(songs_dir):
                    item_path = os.path.join(songs_dir, item)
                    if os.path.isdir(item_path):
                        config = load_song_config(item_path)
                        if config.get('album_id') == self.current_album_id:
                            songs_to_process.append(item_path)
        
        if not songs_to_process:
            messagebox.showwarning('Warning', 'No songs found to process.')
            return
        
        # Confirm before proceeding
        confirm_msg = f'Generate covers for {len(songs_to_process)} song(s)?\n\n'
        confirm_msg += f'Format: {size}\n'
        confirm_msg += f'File Format: {format_type}\n'
        confirm_msg += f'Overwrite existing: {"Yes" if overwrite else "No"}\n'
        confirm_msg += f'Include persona in cover: {"Yes" if include_persona else "No"}'
        
        if not messagebox.askyesno('Confirm Bulk Cover Generation', confirm_msg):
            return
        
        # Process songs (include_persona is for future use when generating missing prompts in bulk)
        self._process_bulk_covers(songs_to_process, size, format_type, overwrite, include_persona)
    
    def _process_bulk_covers(self, song_paths: list[str], size: str, format_type: str, overwrite: bool, include_persona: bool = True):
        """Process bulk cover generation for multiple songs. include_persona is reserved for future use when generating missing prompts in bulk."""
        # Track albums being processed
        albums_processed = set()
        
        progress_dialog = ProgressDialog(self, len(song_paths), 'Generating Covers')
        progress_dialog.update()
        
        generated_count = 0
        skipped_count = 0
        errors = []
        
        for idx, song_path in enumerate(song_paths, 1):
            if progress_dialog.is_cancelled():
                self.log_debug('INFO', 'Bulk cover generation cancelled by user')
                break
            
            song_config = load_song_config(song_path)
            song_name = song_config.get('song_name', os.path.basename(song_path))
            full_song_name = song_config.get('full_song_name', song_name)
            
            # Track album for video prompt generation
            album_id = song_config.get('album_id', '')
            if album_id:
                albums_processed.add(album_id)
            
            progress_dialog.update_progress(idx, f'Processing: {song_name} ({idx}/{len(song_paths)})...')
            
            try:
                # Check if cover already exists
                safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
                file_extension = '.jpg' if format_type.lower() == 'jpeg' else '.png'
                
                # Extract aspect ratio from size (e.g., "1:1 (1024x1024)" -> "1:1" -> "1x1")
                aspect_ratio_suffix = ''
                match = re.search(r'^([^\(]+)', size)
                if match:
                    aspect_ratio = match.group(1).strip()
                    aspect_ratio_x = aspect_ratio.replace(':', 'x')
                    if aspect_ratio_x != '1x1':
                        aspect_ratio_suffix = aspect_ratio_x
                
                filename = os.path.join(song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}{file_extension}')
                
                if os.path.exists(filename) and not overwrite:
                    skipped_count += 1
                    self.log_debug('INFO', f'Skipped {song_name}: cover already exists')
                    continue
                
                # Get cover prompt from song config
                cover_prompt = song_config.get('album_cover', '')
                if not cover_prompt:
                    errors.append(f'{song_name}: No cover prompt found')
                    continue
                
                # Generate cover using existing logic
                success = self._generate_single_cover(song_path, song_config, cover_prompt, size, format_type, filename, overwrite)
                
                if success:
                    generated_count += 1
                    self.log_debug('INFO', f'Generated cover for {song_name}')
                else:
                    errors.append(f'{song_name}: Failed to generate cover')
                    
            except Exception as e:
                error_msg = f'{song_name}: {e}'
                errors.append(error_msg)
                self.log_debug('ERROR', error_msg)
        
        # Process album video prompts
        video_prompts_generated = 0
        video_prompts_skipped = 0
        
        if albums_processed and not progress_dialog.is_cancelled():
            # Update progress dialog for video prompts
            total_items = len(song_paths) + len(albums_processed)
            progress_dialog.total_items = total_items
            progress_dialog.update_progress(len(song_paths), f'Processing album video prompts ({len(albums_processed)} albums)...')
            
            for album_idx, album_id in enumerate(albums_processed, 1):
                if progress_dialog.is_cancelled():
                    self.log_debug('INFO', 'Album video prompt generation cancelled by user')
                    break
                
                try:
                    album_path = self._get_album_path(album_id)
                    if not album_path or not os.path.exists(album_path):
                        continue
                    
                    album_config = load_album_config(album_path)
                    album_name = album_config.get('album_name', album_id)
                    
                    progress_dialog.update_progress(len(song_paths) + album_idx, f'Processing album: {album_name} ({album_idx}/{len(albums_processed)})...')
                    
                    # Extract aspect ratio from size for video prompt filename
                    aspect_ratio_suffix = ''
                    match = re.search(r'^([^\(]+)', size)
                    if match:
                        aspect_ratio = match.group(1).strip()
                        aspect_ratio_x = aspect_ratio.replace(':', 'x')
                        if aspect_ratio_x != '1x1':
                            aspect_ratio_suffix = aspect_ratio_x
                    
                    # Check if video prompt file already exists
                    safe_basename = album_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
                    video_prompt_file = os.path.join(album_path, f'{safe_basename}{aspect_ratio_suffix}.json')
                    
                    # Check if video prompt exists in config or file
                    existing_video_prompt = album_config.get('video_prompt', '')
                    video_prompt_exists = existing_video_prompt or os.path.exists(video_prompt_file)
                    
                    if video_prompt_exists and not overwrite:
                        video_prompts_skipped += 1
                        self.log_debug('INFO', f'Skipped album {album_name}: video prompt already exists')
                        continue
                    
                    # Get cover prompt from album config
                    cover_prompt = album_config.get('cover_prompt', '')
                    if not cover_prompt:
                        # Try to get from first song in album
                        songs_dir = os.path.join(self.current_persona_path, 'AI-Songs')
                        if os.path.exists(songs_dir):
                            for item in os.listdir(songs_dir):
                                item_path = os.path.join(songs_dir, item)
                                if os.path.isdir(item_path):
                                    song_cfg = load_song_config(item_path)
                                    if song_cfg.get('album_id') == album_id:
                                        cover_prompt = song_cfg.get('album_cover', '')
                                        if cover_prompt:
                                            break
                    
                    if not cover_prompt:
                        errors.append(f'Album {album_name}: No cover prompt found for video prompt generation')
                        continue
                    
                    # Generate video prompt
                    success = self._generate_album_video_prompt(album_id, album_name, album_path, cover_prompt, aspect_ratio_suffix, video_prompt_file, overwrite)
                    
                    if success:
                        video_prompts_generated += 1
                        self.log_debug('INFO', f'Generated video prompt for album {album_name}')
                    else:
                        errors.append(f'Album {album_name}: Failed to generate video prompt')
                        
                except Exception as e:
                    error_msg = f'Album {album_id}: {e}'
                    errors.append(error_msg)
                    self.log_debug('ERROR', error_msg)
        
        progress_dialog.destroy()
        
        # Show results
        result_msg = f'Covers Generated: {generated_count}\n'
        if skipped_count > 0:
            result_msg += f'Covers Skipped: {skipped_count}\n'
        if video_prompts_generated > 0:
            result_msg += f'Video Prompts Generated: {video_prompts_generated}\n'
        if video_prompts_skipped > 0:
            result_msg += f'Video Prompts Skipped: {video_prompts_skipped}\n'
        if errors:
            result_msg += f'Errors: {len(errors)}\n\n'
            result_msg += '\n'.join(errors[:10])
            if len(errors) > 10:
                result_msg += f'\n... and {len(errors) - 10} more errors'
        else:
            result_msg += '\nAll covers and video prompts generated successfully!'
        
        if errors:
            messagebox.showwarning('Bulk Cover Generation Complete', result_msg)
        else:
            messagebox.showinfo('Success', result_msg)
    
    def _generate_single_cover(self, song_path: str, song_config: dict, prompt: str, size: str, format_type: str, filename: str, overwrite: bool) -> bool:
        """Generate a single cover image for a song."""
        try:
            # Enhance prompt with persona reference only if song has include_persona_in_cover and prompt does not request no person
            include_persona = bool(song_config.get('include_persona_in_cover', True))
            prompt_lower = prompt.lower()
            no_persona_markers = ('no person', 'no human', 'no character', 'no people', 'no figures', 'no persona present')
            exclude_persona = not include_persona or any(m in prompt_lower for m in no_persona_markers)
            enhanced_prompt = prompt
            
            if not exclude_persona and self.current_persona and self.current_persona_path:
                preset_key = song_config.get('persona_image_preset', self.current_persona.get('current_image_preset', 'default'))
                base_path = self.get_persona_image_base_path(preset_key)
                safe_name = self._safe_persona_basename()
                front_image_path = os.path.join(base_path, f'{safe_name}-Front.png')
                
                if os.path.exists(front_image_path):
                    try:
                        from PIL import Image
                        original_img = Image.open(front_image_path)
                        new_width = original_img.width // 2
                        new_height = original_img.height // 2
                        downscaled_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        temp_dir = os.path.join(song_path, 'temp')
                        os.makedirs(temp_dir, exist_ok=True)
                        reference_image_path = os.path.join(temp_dir, f'{safe_name}-Front-downscaled.png')
                        backup_file_if_exists(reference_image_path)
                        downscaled_img.save(reference_image_path, 'PNG')
                        
                        self.log_debug('INFO', f'Analyzing Front Persona Image for cover reference...')
                        vision_prompt = "Analyze this persona reference image in extreme detail. Provide a comprehensive description of the character's appearance, including: physical features, clothing, styling, colors, accessories, pose, and all visual characteristics. This description will be used to ensure the album cover features the exact same character."
                        vision_system = "You are an image analysis assistant. Provide a highly detailed, objective description of the character's visual appearance from the reference image. Focus on all visual characteristics that should be preserved in the album cover."
                        
                        vision_result = self.azure_vision([reference_image_path], vision_prompt, system_message=vision_system, profile='text')
                        
                        if vision_result['success']:
                            character_description = vision_result['content'].strip()
                            enhanced_prompt += f"\n\nREFERENCE CHARACTER DESCRIPTION (from Front Persona Image):\n{character_description}\n\n"
                            enhanced_prompt += "IMPORTANT: The album cover MUST feature this exact character with matching appearance, styling, and visual characteristics as described above. The character in the album cover must be visually consistent with the reference image."
                        else:
                            enhanced_prompt += f"\n\nIMPORTANT: Use the Front Persona Image as reference. The album cover must feature this exact character with matching appearance, styling, and visual characteristics."
                    except Exception as e:
                        self.log_debug('WARNING', f'Failed to prepare reference image: {e}')
            
            # Map size to actual dimensions
            size_value = self._map_cover_size_to_value(size)
            
            # Convert format to lowercase (Azure API requires lowercase: 'png' or 'jpeg')
            format_lower = format_type.lower()
            if format_lower == 'jpeg':
                format_lower = 'jpeg'
            elif format_lower == 'png':
                format_lower = 'png'
            else:
                format_lower = 'png'  # Default fallback
            
            # Generate image
            result = self.azure_image(enhanced_prompt, size=size_value, profile='image_gen', output_format=format_lower)
            
            if not result.get('success'):
                self.log_debug('ERROR', f'Image generation failed: {result.get("error", "Unknown error")}')
                return False
            
            img_bytes = result.get('image_bytes', b'')
            if not img_bytes:
                self.log_debug('ERROR', 'No image bytes received')
                return False
            
            # Handle overwrite
            if os.path.exists(filename) and not overwrite:
                return False
            
            # Create backup if file exists
            if os.path.exists(filename):
                self.backup_file_if_exists(filename)
            
            # Save image
            with open(filename, 'wb') as f:
                f.write(img_bytes)
            
            # Update song config
            song_config['album_cover_size'] = size
            song_config['album_cover_format'] = format_type
            save_song_config(song_path, song_config)
            
            return True
            
        except Exception as e:
            self.log_debug('ERROR', f'Error generating cover: {e}')
            return False
    
    def _map_cover_size_to_value(self, size_str: str) -> str:
        """Map cover size string to actual dimensions value, mapped to supported Azure Image API sizes."""
        # Extract dimensions from string like "1:1 (1024x1024)" -> "1024x1024"
        match = re.search(r'\((\d+x\d+)\)', size_str)
        if match:
            extracted_size = match.group(1)
            # Map to supported size (1024x1024, 1536x1024, 1024x1536)
            return self._map_to_supported_image_size(extracted_size)
        # Fallback to default
        return '1024x1024'
    
    def _generate_album_video_prompt(self, album_id: str, album_name: str, album_path: str, cover_prompt: str, aspect_ratio_suffix: str, video_prompt_file: str, overwrite: bool) -> bool:
        """Generate and save album video prompt."""
        try:
            if not self.current_persona:
                return False
            
            merged_style = self._get_sanitized_style_text()
            visual_aesthetic = self.current_persona.get('visual_aesthetic', '')
            base_image_prompt = self.current_persona.get('base_image_prompt', '')
            vibe = self.current_persona.get('vibe', '')
            
            prompt = (
                f"Create a seamless looping video prompt for the album \"{album_name}\" "
                f"based on this cover description:\n{cover_prompt}\n\nMerged Style: {merged_style}"
            )
            if visual_aesthetic:
                prompt += f"\nPersona Visual Aesthetic: {visual_aesthetic}"
            if base_image_prompt:
                prompt += f"\nPersona Base Image Prompt: {base_image_prompt}"
            if vibe:
                prompt += f"\nPersona Vibe: {vibe}"
            prompt += "\nReturn only the final video prompt text."
            
            # Generate video prompt
            system_message = 'You are a video loop prompt generator. Output only the final prompt text.'
            result = self.azure_ai(prompt, system_message=system_message, profile='text')
            
            if not result.get('success'):
                self.log_debug('ERROR', f'Video prompt generation failed: {result.get("error", "Unknown error")}')
                return False
            
            video_prompt = result.get('content', '').strip()
            if not video_prompt:
                self.log_debug('ERROR', 'No video prompt received')
                return False
            
            # Handle overwrite
            if os.path.exists(video_prompt_file) and not overwrite:
                return False
            
            # Create backup if file exists
            if os.path.exists(video_prompt_file):
                self.backup_file_if_exists(video_prompt_file)
            
            # Save video prompt to JSON file
            export_data = {
                'generated_prompt': video_prompt
            }
            
            os.makedirs(album_path, exist_ok=True)
            with open(video_prompt_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            # Update album config
            album_config = load_album_config(album_path)
            album_config['video_prompt'] = video_prompt
            save_album_config(album_path, album_config)
            
            self.log_debug('INFO', f'Album video prompt saved to {video_prompt_file}')
            return True
            
        except Exception as e:
            self.log_debug('ERROR', f'Error generating album video prompt: {e}')
            return False
    
    def run_video_loop_model(self):
        """Run the video generation model."""
        prompt = self.video_loop_text.get('1.0', tk.END).strip()
        if not prompt or prompt.startswith('Error:'):
            messagebox.showwarning('Warning', 'Please generate a video loop prompt first.')
            return
        
        dialog = ExtraCommandsDialog(self, prompt)
        self.wait_window(dialog)
        
        if dialog.result is None:
            return
        
        if dialog.result:
            prompt = f"{prompt} {dialog.result}"
        
        full_song_name = self.full_song_name_var.get().strip() or 'video'
        safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        
        # Get video size from configuration
        video_size = self.get_video_loop_size()
        
        # Log video generation parameters
        video_profile = self.ai_config.get('profiles', {}).get('video_gen', {})
        video_endpoint = video_profile.get('endpoint', 'Not configured')
        video_model = video_profile.get('model_name', video_profile.get('deployment', 'Not configured'))
        self.log_debug('INFO', f'Calling Azure Video model...')
        self.log_debug('DEBUG', f'Video endpoint: {video_endpoint}')
        self.log_debug('DEBUG', f'Video model: {video_model}, size: {video_size}')
        
        self.config(cursor='wait')
        self.update()
        
        try:
            result = self.azure_video(prompt, size=video_size, seconds='4', profile='video_gen')
        finally:
            self.config(cursor='')
        
        # Log debug info from result
        debug_info = result.get('debug', {})
        if debug_info:
            self.log_debug('DEBUG', f"Video API URL: {debug_info.get('url', 'N/A')}")
            self.log_debug('DEBUG', f"Video API status: {debug_info.get('status', 'N/A')}, content-type: {debug_info.get('content_type', 'N/A')}")
            if debug_info.get('body_preview'):
                self.log_debug('DEBUG', f"Response preview: {debug_info.get('body_preview', '')[:200]}")
        
        if not result['success']:
            messagebox.showerror('Error', f"Video generation failed: {result['error']}")
            self.log_debug('ERROR', f"Video generation failed: {result['error']}")
            return
        
        video_bytes = result.get('video_bytes', b'')
        if not video_bytes:
            url = result.get('url', '')
            if url:
                messagebox.showinfo('Info', f'Video generated. URL: {url}')
            else:
                messagebox.showerror('Error', 'No video content returned')
            return
        
        filename = filedialog.asksaveasfilename(
            title='Save Generated Video',
            defaultextension='.mp4',
            filetypes=[('MP4 Video', '*.mp4'), ('All Files', '*.*')],
            initialfile=f"{safe_basename}.mp4"
        )
        
        if filename:
            try:
                filename = enable_long_paths(filename)
                with open(filename, 'wb') as f:
                    f.write(video_bytes)
                self.log_debug('INFO', f'Video saved to {filename}')
                messagebox.showinfo('Success', f'Video saved to {filename}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save video: {e}')
                self.log_debug('ERROR', f'Failed to save video: {e}')
    
    def save_video_loop_prompt(self):
        """Save the video loop prompt to a JSON file using the same basename as the album cover."""
        if not self.current_song_path:
            messagebox.showwarning('Warning', 'No song selected. Cannot save video loop prompt.')
            return
        
        video_prompt = self.video_loop_text.get('1.0', tk.END).strip()
        if not video_prompt:
            messagebox.showwarning('Warning', 'Video loop prompt is empty. Please generate a prompt first.')
            return
        
        try:
            # Use the same basename logic as album cover
            full_song_name = self.full_song_name_var.get().strip()
            if not full_song_name:
                full_song_name = self.song_name_var.get().strip() or 'album_cover'
            
            # Generate safe filename from Full Song Name (same as album cover)
            safe_basename = full_song_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", "'").replace('<', '_').replace('>', '_').replace('|', '_')
            
            # Extract aspect ratio from video loop size (e.g., "9:16 (720x1280)" -> "9:16" -> "9x16")
            aspect_ratio_suffix = ''
            if hasattr(self, 'video_loop_size_var'):
                size_value = self.video_loop_size_var.get()
                # Extract aspect ratio part before parentheses (e.g., "9:16" from "9:16 (720x1280)")
                match = re.search(r'^([^\(]+)', size_value)
                if match:
                    aspect_ratio = match.group(1).strip()
                    # Convert ":" to "x" (e.g., "9:16" -> "9x16", "1:1" -> "1x1")
                    aspect_ratio_x = aspect_ratio.replace(':', 'x')
                    # Only append if not 1x1
                    if aspect_ratio_x != '1x1':
                        aspect_ratio_suffix = aspect_ratio_x
            
            # Save with same basename as album cover image, but as .json file
            filename = os.path.join(self.current_song_path, f'{safe_basename}-Cover{aspect_ratio_suffix}.json')
            
            # Create backup if file exists
            backup_path = self.backup_file_if_exists(filename)
            
            # Create JSON structure (same format as storyboard prompt export)
            export_data = {
                'generated_prompt': video_prompt
            }
            
            # Save the prompt to JSON file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.log_debug('INFO', f'Video loop prompt saved to {filename}')
            success_msg = f'Video loop prompt saved to:\n{filename}'
            if backup_path:
                success_msg += f'\n\nBackup created: {os.path.basename(backup_path)}'
            messagebox.showinfo('Success', success_msg)
            
            # Also save to config.json using the same approach as _save_storyboard_generated_prompt
            if self.current_song:
                self.current_song['video_loop'] = video_prompt
                if save_song_config(self.current_song_path, self.current_song):
                    self.log_debug('INFO', 'Config.json updated with video loop prompt')
                else:
                    self.log_debug('WARNING', 'Failed to save config.json with video loop prompt')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save video loop prompt: {e}')
            self.log_debug('ERROR', f'Failed to save video loop prompt: {e}')
    
    def export_youtube_description(self):
        """Export YouTube description for the song."""
        if not self.current_persona:
            messagebox.showwarning('Warning', 'Please select a persona first.')
            return
        
        song_name = self.song_name_var.get().strip()
        persona_name = self.current_persona.get('name', '')
        
        if not song_name:
            messagebox.showwarning('Warning', 'Please enter a song name.')
            return
        
        full_song_name = self.full_song_name_var.get().strip()
        lyrics = self.lyrics_text.get('1.0', tk.END).strip()
        song_style = self.song_style_text.get('1.0', tk.END).strip()
        merged_style = self.merged_style_text.get('1.0', tk.END).strip()
        album_cover = self.album_cover_text.get('1.0', tk.END).strip()
        video_loop = self.video_loop_text.get('1.0', tk.END).strip()
        
        style_source = merged_style if merged_style else song_style
        hashtags = self.generate_youtube_hashtags(song_name, persona_name, style_source)
        
        title = f"{merged_style} - {persona_name} _{song_name}_"
        
        desc = f"TITLE: {title}\n\n"
        desc += f"🎵 AI Song | {persona_name}\n"
        desc += f"Listen to \"{song_name}\" by the AI persona {persona_name}.\n\n"
        desc += f"This AI-generated song features {merged_style.lower()} elements.\n\n"
        desc += "🎧 SUBSCRIBE for more AI music!\n"
        desc += "🔔 Turn on notifications!\n"
        desc += "👍 Like this video!\n\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "📋 CREDITS & INFORMATION\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += f"Song: \"{song_name}\"\n"
        desc += f"AI Persona: {persona_name}\n"
        desc += f"Style: {merged_style}\n"
        desc += f"Video Type: AI-Generated Music\n\n"
        
        # Add music platform links if available (persona-level or song-level overrides)
        spotify_link = (self.spotify_link_var.get().strip() if hasattr(self, 'spotify_link_var') else '') or self.current_persona.get('spotify_link', '').strip()
        itunes_link = (self.apple_link_var.get().strip() if hasattr(self, 'apple_link_var') else '') or self.current_persona.get('itunes_link', '').strip()
        youtube_music_link = (self.youtube_link_var.get().strip() if hasattr(self, 'youtube_link_var') else '') or self.current_persona.get('youtube_music_link', '').strip()
        
        if spotify_link or itunes_link or youtube_music_link:
            desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            desc += "🎵 LISTEN ON\n"
            desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            if itunes_link:
                desc += f"Apple Music: {itunes_link}\n"
            if spotify_link:
                desc += f"Spotify: {spotify_link}\n"
            if youtube_music_link:
                desc += f"YouTube Music: {youtube_music_link}\n"
            desc += "\n"
        
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "⚠️ DISCLAIMER\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += "This is an AI-generated song created by an AI persona. "
        desc += "All content is original and created using AI technology.\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "🏷️ HASHTAGS\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += f"{hashtags}\n\n"
        
        # Derive simple tag list from song style (use merged style if available)
        if style_source:
            # Build a short, comma-separated tag list from style keywords
            style_tags = [t.strip() for t in style_source.replace('|', ',').split(',') if t.strip()]
            if style_tags:
                desc += "Derived tags: " + ", ".join(style_tags[:10]) + "\n\n"
        
        content = "=" * 70 + "\n"
        content += "YOUTUBE TITLE\n"
        content += "=" * 70 + "\n\n"
        content += f"{title}\n\n"
        content += "=" * 70 + "\n"
        content += "SONG DETAILS\n"
        content += "=" * 70 + "\n\n"
        content += f"Full Song Name: {full_song_name}\n"
        content += f"Song Name: {song_name}\n"
        content += f"AI Persona: {persona_name}\n"
        content += f"Song Style: {song_style}\n"
        content += f"Merged Style: {merged_style}\n"
        content += f"Lyrics: {lyrics}\n"
        links_block = self._format_distribution_links_block(include_label=False)
        if links_block:
            content += "Links:\n" + links_block + "\n"
        content += f"Album Cover Prompt: {album_cover}\n"
        content += f"Video Loop Prompt: {video_loop}\n"
        content += "\n" + "=" * 70 + "\n"
        content += "YOUTUBE DESCRIPTION\n"
        content += "=" * 70 + "\n\n"
        content += desc
        
        safe_basename = full_song_name.replace(':', '_').replace('/', '_') if full_song_name else song_name.replace(' ', '_')
        
        filename = filedialog.asksaveasfilename(
            title='Save YouTube Description',
            defaultextension='.txt',
            filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')],
            initialfile=f"{safe_basename}.txt"
        )
        
        if filename:
            try:
                filename = enable_long_paths(filename)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_debug('INFO', f'YouTube description exported to {filename}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to export: {e}')
                self.log_debug('ERROR', f'Failed to export: {e}')
    
    def generate_youtube_hashtags(self, song_name: str, persona_name: str, style_description: str):
        """Generate optimized YouTube hashtags with style-first emphasis, cap 500 words."""
        style_name = style_description if style_description else persona_name
        if style_name and ',' in style_name:
            style_name = style_name.split(',')[0].strip()
        
        template = get_prompt_template('youtube_hashtags', self.ai_config)
        if not template:
            self.log_debug('ERROR', 'Failed to load youtube_hashtags template')
            return self._generate_fallback_hashtags(song_name, persona_name, style_name)
        
        prompt = template.replace('{SONG_NAME}', song_name)
        prompt = prompt.replace('{ARTIST}', persona_name)
        prompt = prompt.replace('{STYLE_NAME}', style_name if style_name else '')
        prompt += (
            "\nOrder the hashtags by highest viral potential and SEO relevance. "
            "Prioritize style/genre keywords first, then song name and persona name. "
            "Output only comma-separated hashtags starting with #, no numbering or bullets."
        )
        
        self.log_debug('INFO', 'Generating optimized hashtags with AI...')
        self.config(cursor='wait')
        self.update()
        try:
            result = self.azure_ai(prompt, profile='text')
        finally:
            self.config(cursor='')
        
        if result['success']:
            ai_raw = result['content'].strip()
            ai_raw = ai_raw.replace('Hashtags:', '').replace('hashtags:', '').strip()
            style_tags = self._derive_style_tags(style_description, max_tags=12)
            ai_tags = self._normalize_hashtag_list(ai_raw)
            combined_tags = style_tags + [tag for tag in ai_tags if tag not in style_tags]
            hashtags = ', '.join(combined_tags)
            return self._limit_hashtags_words(hashtags, 500)
        
        self.log_debug('WARNING', 'AI hashtag generation failed, using fallback')
        return self._generate_fallback_hashtags(song_name, persona_name, style_name)
    
    def _generate_fallback_hashtags(self, song_name: str, persona_name: str, style_name: str):
        """Generate basic hashtags as fallback."""
        tags = []
        # Style tags first
        tags.extend(self._derive_style_tags(style_name, max_tags=12))
        # Core identifiers
        tags.append(f"#{song_name.replace(' ', '')}")
        if persona_name:
            tags.append(f"#{persona_name.replace(' ', '')}")
        # Light generic music tags (non-AI)
        tags.extend(["#Music", "#Cover", "#Song"])
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for tag in tags:
            if tag and tag not in seen:
                deduped.append(tag)
                seen.add(tag)
        return self._limit_hashtags_words(', '.join(deduped), 500)
    
    def _derive_style_tags(self, style_text: str, max_tags: int = 12) -> list[str]:
        """Create a list of hashtags derived from style/genre phrases."""
        if not style_text:
            return []
        clean_text = style_text.replace('|', ',')
        parts = []
        for chunk in clean_text.replace(',', ' ').split():
            token = ''.join(ch for ch in chunk if ch.isalnum())
            if token:
                parts.append(f"#{token}")
        tags = []
        seen = set()
        for tag in parts:
            if tag not in seen:
                tags.append(tag)
                seen.add(tag)
            if len(tags) >= max_tags:
                break
        return tags
    
    def _normalize_hashtag_list(self, raw_tags: str) -> list[str]:
        """Normalize AI returned hashtags into a unique #tag list."""
        if not raw_tags:
            return []
        separators = [',', '\n', '\t']
        normalized = raw_tags
        for sep in separators:
            normalized = normalized.replace(sep, ' ')
        tokens = normalized.split()
        tags = []
        seen = set()
        for tok in tokens:
            token = tok.lstrip('#').strip()
            token = ''.join(ch for ch in token if ch.isalnum())
            if not token:
                continue
            tag = f"#{token}"
            if tag not in seen:
                tags.append(tag)
                seen.add(tag)
        return tags
    
    def _limit_hashtags_words(self, hashtags: str, max_words: int) -> str:
        """Limit a hashtag string to a maximum word count."""
        words = hashtags.replace(',', ' ').split()
        if len(words) <= max_words:
            return hashtags
        limited = ' '.join(words[:max_words])
        return limited
    
    def open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self, self.ai_config)
        self.wait_window(dialog)
        if dialog.result:
            self.ai_config = dialog.result
            if save_config(self.ai_config):
                self.personas_path = get_personas_path(self.ai_config)
                self.refresh_personas_list()
                self.log_debug('INFO', 'Settings saved successfully.')
            else:
                self.log_debug('ERROR', 'Failed to save settings.')
    
    def show_about(self):
        """Show about dialog."""
        about_text = """Suno Persona Manager

A tool for managing AI Personas and their AI-generated songs.

Features:
- Create and manage AI Personas
- Edit persona information with AI enhancement
- Generate reference images (Front, Side, Back)
- Manage AI Songs for each persona
- Generate lyrics, styles, and prompts
- Export YouTube descriptions

Version: 1.0"""
        self.log_debug('INFO', about_text)


def main():
    app = SunoPersona()
    app.mainloop()


if __name__ == '__main__':
    main()


