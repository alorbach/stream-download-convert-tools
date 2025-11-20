import csv
import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import requests
import base64
import urllib.parse
import glob
import time


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


def resolve_csv_path() -> str:
    """Resolve default CSV path in AI/suno/suno_sound_styles.csv relative to project root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    default_path = os.path.join(project_root, 'AI', 'suno', 'suno_sound_styles.csv')
    return default_path


def get_config_path() -> str:
    """Get the path to the config.json file in the script's directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'suno_style_browser_config.json')


def resolve_prompts_path() -> str:
    """Resolve default prompts path in AI/suno/prompts/ relative to project root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    default_path = os.path.join(project_root, 'AI', 'suno', 'prompts')
    return default_path


def load_config() -> dict:
    """Load configuration from JSON file, create default if it doesn't exist."""
    config_path = get_config_path()
    default_config = {
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
            }
        },
        "song_details": {
            "song_name": "",
            "artist": "",
            "lyrics": "",
            "styles": "",
            "merged_style": "",
            "album_cover": "",
            "video_loop": ""
        },
        "last_selected_style": ""
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # Backward compatibility: convert old config format to new format
                if 'profiles' not in config:
                    # Old format - migrate to new format
                    old_config = config.copy()
                    config = default_config.copy()
                    config['profiles']['text'] = {
                        'endpoint': old_config.get('endpoint', ''),
                        'model_name': old_config.get('model_name', ''),
                        'deployment': old_config.get('deployment', ''),
                        'subscription_key': old_config.get('subscription_key', ''),
                        'api_version': old_config.get('api_version', '')
                    }
                    # Preserve song_details and last_selected_style
                    if 'song_details' in old_config:
                        config['song_details'] = old_config['song_details']
                    if 'last_selected_style' in old_config:
                        config['last_selected_style'] = old_config['last_selected_style']
                
                # Merge with defaults to ensure all keys exist
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                    elif key == 'profiles' and isinstance(config[key], dict):
                        # Merge profiles sub-dict
                        for profile_name in default_config['profiles']:
                            if profile_name not in config['profiles']:
                                config['profiles'][profile_name] = default_config['profiles'][profile_name]
                            else:
                                # Merge individual profile settings
                                for setting_key in default_config['profiles'][profile_name]:
                                    if setting_key not in config['profiles'][profile_name]:
                                        config['profiles'][profile_name][setting_key] = default_config['profiles'][profile_name][setting_key]
                    elif key == 'song_details' and isinstance(config[key], dict):
                        # Merge song_details sub-dict
                        for sub_key in default_config['song_details']:
                            if sub_key not in config[key]:
                                config[key][sub_key] = default_config['song_details'][sub_key]
                return config
        except Exception as exc:
            print(f'Config Error: Failed to load config:\n{exc}')
            return default_config
    else:
        # Create default config file
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


def load_styles(csv_path: str):
    styles = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                styles.append(row)
    except FileNotFoundError:
        print(f'Error: CSV not found:\n{csv_path}')
    except Exception as exc:
        print(f'Error: Failed to read CSV:\n{exc}')
    return styles


def get_prompt_template(template_name: str) -> str:
    """Get prompt template by name from file system."""
    prompts_dir = resolve_prompts_path()
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


def call_azure_ai(config: dict, prompt: str, system_message: str = None, profile: str = 'text') -> dict:
    """
    Generic Azure AI caller function.
    
    Args:
        config: Configuration dict with profiles (text, image_gen, video_gen)
        prompt: User prompt/message
        system_message: Optional system message
        profile: Profile name ('text', 'image_gen', 'video_gen') - defaults to 'text'
    
    Returns:
        dict with 'success' (bool), 'content' (str), 'error' (str)
    """
    try:
        # Get profile configuration
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
        
        # All profiles use chat completions API for generating text prompts
        # Different profiles allow using different Azure deployments/models
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
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
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


def _sanitize_azure_endpoint(raw_endpoint: str) -> str:
    """Return base Azure endpoint without extra path or query (e.g., https://<res>.openai.azure.com)."""
    if not raw_endpoint:
        return ''
    raw = raw_endpoint.strip()
    # Remove trailing slashes
    raw = raw.rstrip('/')
    # If full URL with path/query is provided, keep only scheme://netloc
    try:
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return raw


def call_azure_image(config: dict, prompt: str, size: str = '1024x1024', profile: str = 'image_gen', quality: str = 'medium', output_format: str = 'png', output_compression: int = 100) -> dict:
    """
    Call Azure OpenAI Images API to generate an image from a prompt.
    Returns dict with success, image_bytes (bytes) or error.
    """
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
                'error': f'Missing Azure Image configuration for profile "{profile}". Please configure settings. '
                         f'(endpoint={endpoint or "<empty>"}, deployment={deployment or "<empty>"})'
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

        attempted = []
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        attempted.append({'api_version': api_version, 'url': url, 'status': response.status_code})
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

        # If 404, retry with a known-good preview version if different
        if response.status_code == 404 and api_version != '2025-04-01-preview':
            fallback_version = '2025-04-01-preview'
            fallback_url = f"{endpoint}/openai/deployments/{deployment}/images/generations?api-version={fallback_version}"
            response_fb = requests.post(fallback_url, headers=headers, json=payload, timeout=60)
            attempted.append({'api_version': fallback_version, 'url': fallback_url, 'status': response_fb.status_code})
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
            else:
                return {
                    'success': False,
                    'image_bytes': b'',
                    'error': (
                        f'Azure Images error: {response.status_code} - {response.text}. '
                        f'Attempted versions/urls: {attempted}'
                    )
                }

        return {
            'success': False,
            'image_bytes': b'',
            'error': (
                f'Azure Images error: {response.status_code} - {response.text}. '
                f'Attempted versions/urls: {attempted}'
            )
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


def call_azure_video(config: dict, prompt: str, size: str = '720x1280', seconds: str = '4', profile: str = 'video_gen') -> dict:
    """
    Call a video generations endpoint (expects Azure-like auth with Api-key header).
    Uses profile endpoint as-is (no path added) to allow custom URLs.
    Returns dict with success, video_bytes (optional), url (optional), error.
    """
    try:
        profiles = config.get('profiles', {})
        if profile not in profiles:
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Profile "{profile}" not found'}

        profile_config = profiles[profile]
        endpoint = (profile_config.get('endpoint', '') or '').strip()
        model_name = profile_config.get('model_name', 'sora-2')
        deployment = profile_config.get('deployment', '')
        api_version = profile_config.get('api_version', '')  # optional for custom endpoints
        subscription_key = profile_config.get('subscription_key', '')

        if not endpoint or not subscription_key:
            return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'Missing video endpoint or key'}

        # Decide URL pattern
        # 1) If endpoint already includes openai/v1/video path → use as-is (append /jobs if missing)
        # 2) Else if base resource URL AND deployment provided → try PUBLIC first: /openai/deployments/{deployment}/video/generations
        #    and have JOBS fallback: /openai/deployments/{deployment}/video/generations/jobs
        # 3) Else default to openai/v1/video/generations/jobs pattern from provided endpoint
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
        if 'openai/v1/video' in path_lower:
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

        # Append api-version if provided and missing
        if api_version and 'api-version=' not in url:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}api-version={api_version}"

        headers = {
            'Content-Type': 'application/json',
            'Api-key': subscription_key  # matches provided curl sample
        }

        # Parse size into width/height if using jobs API; otherwise send size string
        width, height = None, None
        try:
            parts = size.lower().split('x')
            if len(parts) == 2:
                width = str(int(parts[0]))
                height = str(int(parts[1]))
        except Exception:
            pass

        using_jobs_api = (
            ('/openai/v1/video/' in url) or ('/openai/deployments/' in url and '/video/generations/jobs' in url)
        ) and (url.endswith('/jobs') or '/jobs?' in url)

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
            # If binary video is returned
            if 'video' in ctype or 'application/octet-stream' in ctype:
                return {'success': True, 'video_bytes': resp.content, 'url': '', 'error': '', 'debug': debug_info}
            # Otherwise try JSON structure
            try:
                data = resp.json()
                # Common patterns: direct URL
                if isinstance(data, dict):
                    url_value = data.get('url') or data.get('video_url') or ''
                    if url_value:
                        return {'success': True, 'video_bytes': b'', 'url': url_value, 'error': '', 'debug': debug_info}
                    # Base64 variants
                    b64 = ''
                    if 'data' in data and isinstance(data['data'], list) and data['data']:
                        b64 = data['data'][0].get('b64_json', '') or data['data'][0].get('video_b64', '')
                    b64 = b64 or data.get('b64_json', '') or data.get('video_b64', '')
                    if b64:
                        return {'success': True, 'video_bytes': base64.b64decode(b64), 'url': '', 'error': '', 'debug': debug_info}
                debug_info['body_preview'] = resp.text[:500]
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': 'Unknown video response format', 'debug': debug_info}
            except Exception as e:
                # Attach a short preview of body to help debugging
                body_preview = ''
                try:
                    body_preview = resp.text[:500]
                except Exception:
                    pass
                debug_info['body_preview'] = body_preview
                return {'success': False, 'video_bytes': b'', 'url': '', 'error': f'Invalid JSON response: {e}', 'debug': debug_info}
        
        # Public API fallback: if we tried public and got 404/400 suggesting preview mode, try jobs URL automatically
        if (resp.status_code in (400, 404)) and (public_url and jobs_url) and (not using_jobs_api):
            body_text = ''
            try:
                body_text = resp.text
            except Exception:
                pass
            if ('private preview' in body_text.lower()) or (resp.status_code == 404):
                # Switch to jobs
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

        # Jobs API flow: expect JSON with id/status, then poll and download
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

            # Build status URL
            base = endpoint.rstrip('/')
            status_url = f"{base}/openai/v1/video/generations/jobs/{job_id}"
            if api_version and 'api-version=' not in status_url:
                status_url += f"?api-version={api_version}"

            # Poll
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

            # Download video content
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
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'image_bytes': b'',
            'error': f'Request error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'image_bytes': b'',
            'error': f'Unexpected error: {str(e)}'
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
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        # Focus on the text widget
        self.extra_commands_text.focus_set()
    
    def create_widgets(self, current_prompt: str):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Label
        ttk.Label(main_frame, text='Enter extra commands to inject into the prompt:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        # Show current prompt (read-only)
        ttk.Label(main_frame, text='Current prompt:', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        prompt_preview = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 8))
        prompt_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        prompt_preview.config(state=tk.NORMAL)
        prompt_preview.insert('1.0', current_prompt[:500] + ('...' if len(current_prompt) > 500 else ''))
        prompt_preview.config(state=tk.DISABLED)
        
        # Extra commands input
        ttk.Label(main_frame, text='Extra commands (leave empty to use prompt as-is):', font=('TkDefaultFont', 8)).pack(anchor=tk.W, pady=(5, 2))
        self.extra_commands_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, font=('Consolas', 9))
        self.extra_commands_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text='OK', command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        # Bind Escape key to Cancel
        self.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def ok_clicked(self):
        extra_commands = self.extra_commands_text.get('1.0', tk.END).strip()
        # Use empty string to indicate "use prompt as-is", None is reserved for Cancel
        self.result = extra_commands if extra_commands else ''
        self.destroy()
    
    def cancel_clicked(self):
        self.result = None
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Dialog for editing Azure AI configuration settings with multiple profiles."""
    
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title('Azure AI Settings')
        self.geometry('600x500')
        self.transient(parent)
        self.grab_set()
        
        self.config = config.copy()
        self.result = None
        
        # Store StringVars for each profile
        self.profile_vars = {}
        
        self.create_widgets()
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Get profiles from config
        profiles = self.config.get('profiles', {})
        
        # Create tab for each profile
        self.profile_vars = {}
        for profile_name in ['text', 'image_gen', 'video_gen']:
            profile_data = profiles.get(profile_name, {})
            self.profile_vars[profile_name] = {}
            
            # Create frame for this profile
            profile_frame = ttk.Frame(notebook, padding=10)
            notebook.add(profile_frame, text=profile_name.replace('_', ' ').title())
            
            # Endpoint
            ttk.Label(profile_frame, text='Endpoint:').grid(row=0, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['endpoint'] = tk.StringVar(value=profile_data.get('endpoint', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['endpoint'], width=50).grid(row=0, column=1, pady=5, padx=5)
            
            # Model Name
            ttk.Label(profile_frame, text='Model Name:').grid(row=1, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['model_name'] = tk.StringVar(value=profile_data.get('model_name', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['model_name'], width=50).grid(row=1, column=1, pady=5, padx=5)
            
            # Deployment
            ttk.Label(profile_frame, text='Deployment:').grid(row=2, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['deployment'] = tk.StringVar(value=profile_data.get('deployment', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['deployment'], width=50).grid(row=2, column=1, pady=5, padx=5)
            
            # Subscription Key
            ttk.Label(profile_frame, text='Subscription Key:').grid(row=3, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['subscription_key'] = tk.StringVar(value=profile_data.get('subscription_key', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['subscription_key'], width=50, show='*').grid(row=3, column=1, pady=5, padx=5)
            
            # API Version
            ttk.Label(profile_frame, text='API Version:').grid(row=4, column=0, sticky=tk.W, pady=5)
            self.profile_vars[profile_name]['api_version'] = tk.StringVar(value=profile_data.get('api_version', ''))
            ttk.Entry(profile_frame, textvariable=self.profile_vars[profile_name]['api_version'], width=50).grid(row=4, column=1, pady=5, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text='Save', command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Cancel', command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_settings(self):
        # Update profiles in config
        profiles = {}
        for profile_name, vars_dict in self.profile_vars.items():
            profiles[profile_name] = {
                'endpoint': vars_dict['endpoint'].get(),
                'model_name': vars_dict['model_name'].get(),
                'deployment': vars_dict['deployment'].get(),
                'subscription_key': vars_dict['subscription_key'].get(),
                'api_version': vars_dict['api_version'].get()
            }
        
        self.config['profiles'] = profiles
        self.result = self.config
        self.destroy()


class SunoStyleBrowser(tk.Tk):
    def __init__(self, csv_path: str):
        super().__init__()
        self.title('Suno Style Browser')
        self.geometry('1280x900')
        self.csv_path = csv_path
        self.styles = load_styles(csv_path)
        self.filtered = list(self.styles)
        self.sort_column = None
        self.sort_reverse = False
        self.ai_config = load_config()
        self.current_row = None

        self.create_widgets()
        # Sort initially by style
        self.sort_by_column('style')
        self.populate_tree(self.filtered)
        self.restore_song_details()
        self.restore_last_selected_style()
        # Try load last saved album cover preview if available
        self.try_load_last_album_cover()

    def create_widgets(self):
        # Menu bar
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Settings', menu=settings_menu)
        settings_menu.add_command(label='Azure AI Settings...', command=self.open_settings)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Help', menu=help_menu)
        help_menu.add_command(label='Keyboard Shortcuts', command=self.show_shortcuts)
        help_menu.add_command(label='About', command=self.show_about)
        
        # Top single-line bar: search, filters, and actions
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=8)

        # Search
        ttk.Label(top_frame, text='Search:').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=24)
        search_entry.pack(side=tk.LEFT, padx=6)
        search_entry.bind('<KeyRelease>', lambda e: self.apply_filter())

        # Style
        ttk.Label(top_frame, text='Style:').pack(side=tk.LEFT, padx=(10, 0))
        self.style_var = tk.StringVar()
        style_entry = ttk.Entry(top_frame, textvariable=self.style_var, width=18)
        style_entry.pack(side=tk.LEFT, padx=4)
        style_entry.bind('<KeyRelease>', lambda e: self.apply_filter())

        # Artists
        ttk.Label(top_frame, text='Artists:').pack(side=tk.LEFT, padx=(10, 0))
        self.artists_var = tk.StringVar()
        artists_entry = ttk.Entry(top_frame, textvariable=self.artists_var, width=18)
        artists_entry.pack(side=tk.LEFT, padx=4)
        artists_entry.bind('<KeyRelease>', lambda e: self.apply_filter())

        # Decade
        ttk.Label(top_frame, text='Decade:').pack(side=tk.LEFT, padx=(10, 0))
        self.decade_var = tk.StringVar()
        decade_entry = ttk.Entry(top_frame, textvariable=self.decade_var, width=10)
        decade_entry.pack(side=tk.LEFT, padx=4)
        decade_entry.bind('<KeyRelease>', lambda e: self.apply_filter())

        # Tempo
        ttk.Label(top_frame, text='Tempo:').pack(side=tk.LEFT, padx=(10, 0))
        self.tempo_var = tk.StringVar()
        tempo_entry = ttk.Entry(top_frame, textvariable=self.tempo_var, width=10)
        tempo_entry.pack(side=tk.LEFT, padx=4)
        tempo_entry.bind('<KeyRelease>', lambda e: self.apply_filter())

        # Right-side actions
        open_csv_btn = ttk.Button(top_frame, text='Open CSV', command=self.choose_csv)
        open_csv_btn.pack(side=tk.RIGHT, padx=4)
        create_tooltip(open_csv_btn, 'Open a different CSV file')
        
        reload_btn = ttk.Button(top_frame, text='Reload', command=self.reload_csv)
        reload_btn.pack(side=tk.RIGHT, padx=4)
        create_tooltip(reload_btn, 'Reload current CSV file (F5)')
        
        clear_filters_btn = ttk.Button(top_frame, text='Clear Filters', command=self.clear_filters)
        clear_filters_btn.pack(side=tk.RIGHT, padx=4)
        create_tooltip(clear_filters_btn, 'Clear all filter fields')

        # Main content area: 30% list, 70% details
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        
        # Left panel: Style list (30%)
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left_panel.config(width=384)  # ~30% of 1280
        
        # Only show 'style' column in the tree
        columns = ('style',)
        self.tree = ttk.Treeview(left_panel, columns=columns, show='headings', selectmode='browse')
        self.tree.heading('style', text='Style', command=lambda: self.sort_by_column('style'))
        self.tree.column('style', width=364, anchor=tk.W)

        # Add vertical scrollbar for styles list
        tree_scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        # Pack tree and scrollbar side-by-side
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)

        # Right panel: Details (70%)
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Style Details
        details_tab = ttk.Frame(self.notebook)
        self.notebook.add(details_tab, text='Style Details')
        self.create_details_tab(details_tab)
        
        # Tab 2: Song Details
        song_tab = ttk.Frame(self.notebook)
        self.notebook.add(song_tab, text='Song Details')
        self.create_song_tab(song_tab)
        
        # Status bar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.status_var = tk.StringVar(value=f'Loaded {len(self.styles)} styles from {self.csv_path}')
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        # Collapsible Debug output section
        self.debug_collapsed = False
        debug_header_frame = ttk.Frame(self)
        debug_header_frame.pack(fill=tk.X, padx=10, pady=(0, 0))
        
        self.debug_toggle_btn = ttk.Button(debug_header_frame, text='▼ Debug Output', command=self.toggle_debug)
        self.debug_toggle_btn.pack(side=tk.LEFT)
        create_tooltip(self.debug_toggle_btn, 'Click to show/hide debug output (Ctrl+D)')
        
        debug_clear_btn = ttk.Button(debug_header_frame, text='Clear', command=self.clear_debug)
        debug_clear_btn.pack(side=tk.RIGHT, padx=(5, 0))
        create_tooltip(debug_clear_btn, 'Clear debug output')
        
        self.debug_frame = ttk.LabelFrame(self, text='Debug Output', padding=5)
        self.debug_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
        
        self.debug_text = scrolledtext.ScrolledText(self.debug_frame, height=8, wrap=tk.WORD, font=('Consolas', 9))
        self.debug_text.pack(fill=tk.BOTH, expand=True)
        self.debug_text.config(state=tk.DISABLED)
        
        # Add initial debug message
        self.log_debug('INFO', 'Application initialized')
        
        # Store search entry reference for focus
        self.search_entry = search_entry
        
        # Bind keyboard shortcuts
        self.bind_all('<Control-s>', lambda e: self.save_song_details())
        self.bind_all('<Control-d>', lambda e: self.toggle_debug())
        self.bind_all('<Control-f>', lambda e: self.focus_search())
        self.bind_all('<F5>', lambda e: self.reload_csv())
    
    def create_details_tab(self, parent):
        """Create the style details tab with copyable fields."""
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Define fields to display
        self.detail_fields = {
            'style': 'Style',
            'mood': 'Mood',
            'tempo_bpm': 'Tempo (BPM)',
            'instrumentation': 'Instrumentation',
            'vocal_style': 'Vocal Style',
            'sample_artists': 'Sample Artists',
            'decade_range': 'Decade Range',
            'production_notes': 'Production Notes',
            'prompt': 'Prompt'
        }
        
        self.detail_widgets = {}
        row = 0
        
        for key, label in self.detail_fields.items():
            # Label
            ttk.Label(scrollable_frame, text=f'{label}:', font=('TkDefaultFont', 9, 'bold')).grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=5
            )
            
            # Text widget with scrollbar for multi-line content
            text_frame = ttk.Frame(scrollable_frame)
            text_frame.grid(row=row, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
            
            text_widget = scrolledtext.ScrolledText(text_frame, height=3, wrap=tk.WORD, width=50)
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.config(state=tk.DISABLED)
            
            # Copy button
            copy_btn = ttk.Button(scrollable_frame, text='Copy', command=lambda k=key: self.copy_field(k))
            copy_btn.grid(row=row, column=2, padx=5, pady=5)
            
            self.detail_widgets[key] = text_widget
            row += 1
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_song_tab(self, parent):
        """Create the song details input tab."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # AI Cover Name
        ttk.Label(main_frame, text='AI Cover Name:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.ai_cover_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.ai_cover_name_var, width=60).grid(
            row=0, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5
        )
        
        # Song Name
        ttk.Label(main_frame, text='Song Name:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.song_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.song_name_var, width=60).grid(
            row=1, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5
        )
        
        # Artist
        ttk.Label(main_frame, text='Artist:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.artist_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.artist_var, width=60).grid(
            row=2, column=1, columnspan=2, sticky=tk.W+tk.E, pady=5, padx=5
        )
        
        # Lyrics with character counter
        lyrics_label_frame = ttk.Frame(main_frame)
        lyrics_label_frame.grid(row=3, column=0, sticky=tk.NW, pady=5)
        ttk.Label(lyrics_label_frame, text='Lyrics:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        self.lyrics_char_count = tk.StringVar(value='0 / 20000')
        lyrics_counter = ttk.Label(lyrics_label_frame, textvariable=self.lyrics_char_count, font=('TkDefaultFont', 7), foreground='gray')
        lyrics_counter.pack(anchor=tk.W)
        
        self.lyrics_text = scrolledtext.ScrolledText(main_frame, height=4, wrap=tk.WORD, width=60)
        self.lyrics_text.grid(row=3, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        # Update character counter on text change
        def update_lyrics_counter(event=None):
            current = self.lyrics_text.get('1.0', tk.END)
            char_count = len(current.rstrip('\n'))
            self.lyrics_char_count.set(f'{char_count} / 20000')
            if char_count > 20000:
                lyrics_counter.config(foreground='red')
            elif char_count > 18000:
                lyrics_counter.config(foreground='orange')
            else:
                lyrics_counter.config(foreground='gray')
        
        # Limit lyrics to 20000 characters
        def validate_lyrics_insert(event):
            if event.keysym == 'BackSpace' or event.keysym == 'Delete':
                self.after(10, update_lyrics_counter)
                return None
            current = self.lyrics_text.get('1.0', tk.END)
            if len(current) + len(event.char if event.char else '') > 20000:
                return 'break'
            self.after(10, update_lyrics_counter)
            return None
        
        def validate_lyrics_paste(event):
            try:
                text = self.lyrics_text.clipboard_get()
                current = self.lyrics_text.get('1.0', tk.END)
                if len(current) + len(text) > 20000:
                    self.log_debug('WARNING', 'Lyrics Limit: Pasted text exceeds the 20000 character limit.')
                    return 'break'
                self.after(10, update_lyrics_counter)
            except:
                pass
            return None
        
        self.lyrics_text.bind('<KeyPress>', validate_lyrics_insert)
        self.lyrics_text.bind('<Control-v>', validate_lyrics_paste)
        self.lyrics_text.bind('<KeyRelease>', update_lyrics_counter)
        update_lyrics_counter()
        
        # Styles (can add multiple)
        ttk.Label(main_frame, text='Styles:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=4, column=0, sticky=tk.NW, pady=5
        )
        self.styles_text = scrolledtext.ScrolledText(main_frame, height=3, wrap=tk.WORD, width=60)
        self.styles_text.grid(row=4, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        # Merged Style Result
        ttk.Label(main_frame, text='Merged Style:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=5, column=0, sticky=tk.NW, pady=5
        )
        self.merged_style_text = scrolledtext.ScrolledText(main_frame, height=3, wrap=tk.WORD, width=60)
        self.merged_style_text.grid(row=5, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        # AI Results (tabbed)
        ttk.Label(main_frame, text='AI Results:', font=('TkDefaultFont', 9, 'bold')).grid(
            row=6, column=0, sticky=tk.NW, pady=5
        )
        
        # Create notebook for AI results
        ai_results_notebook = ttk.Notebook(main_frame)
        ai_results_notebook.grid(row=6, column=1, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)
        
        # Tab 1: Album Cover Prompt
        album_cover_frame = ttk.Frame(ai_results_notebook)
        ai_results_notebook.add(album_cover_frame, text='Album Cover')
        
        album_cover_toolbar = ttk.Frame(album_cover_frame)
        album_cover_toolbar.pack(fill=tk.X, padx=2, pady=2)
        album_copy_btn = ttk.Button(album_cover_toolbar, text='Copy', command=lambda: self.copy_to_clipboard(self.album_cover_text))
        album_copy_btn.pack(side=tk.RIGHT, padx=2)
        create_tooltip(album_copy_btn, 'Copy album cover prompt to clipboard')
        
        self.album_cover_text = scrolledtext.ScrolledText(album_cover_frame, height=6, wrap=tk.WORD, width=60)
        self.album_cover_text.pack(fill=tk.BOTH, expand=True)
        
        # Tab 2: Video Loop Prompt
        video_loop_frame = ttk.Frame(ai_results_notebook)
        ai_results_notebook.add(video_loop_frame, text='Video Loop')
        
        video_loop_toolbar = ttk.Frame(video_loop_frame)
        video_loop_toolbar.pack(fill=tk.X, padx=2, pady=2)
        video_copy_btn = ttk.Button(video_loop_toolbar, text='Copy', command=lambda: self.copy_to_clipboard(self.video_loop_text))
        video_copy_btn.pack(side=tk.RIGHT, padx=2)
        create_tooltip(video_copy_btn, 'Copy video loop prompt to clipboard')
        
        self.video_loop_text = scrolledtext.ScrolledText(video_loop_frame, height=6, wrap=tk.WORD, width=60)
        self.video_loop_text.pack(fill=tk.BOTH, expand=True)

        # Album Cover Preview section
        preview_frame = ttk.LabelFrame(main_frame, text='Album Cover Preview', padding=5)
        preview_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W+tk.E, pady=(8, 0))
        self.album_cover_photo = None
        self.album_cover_preview = ttk.Label(preview_frame, text='No image generated yet')
        self.album_cover_preview.pack(fill=tk.BOTH, expand=True)

        # Video Options (size/seconds)
        video_opts = ttk.LabelFrame(main_frame, text='Video Options', padding=5)
        video_opts.grid(row=8, column=0, columnspan=3, sticky=tk.W+tk.E, pady=(8, 0))
        ttk.Label(video_opts, text='Size:').pack(side=tk.LEFT)
        self.video_size_var = tk.StringVar(value='720x1280')
        sizes = ['720x1280', '1280x720']
        self.video_size_combo = ttk.Combobox(video_opts, textvariable=self.video_size_var, values=sizes, width=12, state='readonly')
        self.video_size_combo.pack(side=tk.LEFT, padx=6)
        ttk.Label(video_opts, text='Seconds:').pack(side=tk.LEFT, padx=(10, 0))
        self.video_seconds_var = tk.StringVar(value='4')
        seconds_vals = ['4', '8', '12']
        self.video_seconds_combo = ttk.Combobox(video_opts, textvariable=self.video_seconds_var, values=seconds_vals, width=6, state='readonly')
        self.video_seconds_combo.pack(side=tk.LEFT, padx=6)
        
        # Buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=9, column=0, columnspan=3, pady=10, sticky=tk.W)

        # Two rows of buttons
        btn_row1 = ttk.Frame(btn_frame)
        btn_row1.pack(fill=tk.X, expand=True)
        btn_row2 = ttk.Frame(btn_frame)
        btn_row2.pack(fill=tk.X, expand=True, pady=(6, 0))

        # Row 1: Data & Styles (Grouped)
        # 1. Data Management
        clear_btn = ttk.Button(btn_row1, text='Clear All', command=self.clear_song_fields)
        clear_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(clear_btn, 'Clear all song detail fields')
        
        save_btn = ttk.Button(btn_row1, text='Save', command=self.save_song_details)
        save_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(save_btn, 'Save song details to config (Ctrl+S)')
        
        load_btn = ttk.Button(btn_row1, text='Load', command=self.load_song_details)
        load_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(load_btn, 'Load song details from settings file')

        ttk.Separator(btn_row1, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        # 2. Style Operations
        merge_btn = ttk.Button(btn_row1, text='Merge Styles', command=self.merge_styles)
        merge_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(merge_btn, 'Merge multiple styles using AI')

        transform_btn = ttk.Button(btn_row1, text='Transform Style', command=lambda: self.transform_style(merge_original=False))
        transform_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(transform_btn, 'Transform style for viral potential using AI')

        merge_transform_btn = ttk.Button(btn_row1, text='Merge+Transform Style', command=lambda: self.transform_style(merge_original=True))
        merge_transform_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(merge_transform_btn, 'Merge selected style and transform for viral potential')
        
        gen_name_btn = ttk.Button(btn_row1, text='Generate AI Cover Name', command=self.generate_ai_cover_name)
        gen_name_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(gen_name_btn, 'Generate AI cover name from song and style')

        # Row 2: Media & Export
        
        # Album Cover
        gen_cover_btn = ttk.Button(btn_row2, text='Gen Album Cover Prompt', command=self.generate_album_cover)
        gen_cover_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(gen_cover_btn, 'Generate album cover prompt using AI')

        run_cover_btn = ttk.Button(btn_row2, text='Run Album Cover Prompt', command=self.run_image_model)
        run_cover_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(run_cover_btn, 'Generate album cover image from prompt')
        
        ttk.Separator(btn_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        # Video Loop
        gen_video_btn = ttk.Button(btn_row2, text='Gen Video Loop Prompt', command=self.generate_video_loop)
        gen_video_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(gen_video_btn, 'Generate video loop prompt using AI')
        
        run_video_btn = ttk.Button(btn_row2, text='Run Video Loop Prompt', command=self.run_video_loop_model)
        run_video_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(run_video_btn, 'Generate video loop from prompt')

        ttk.Separator(btn_row2, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        export_btn = ttk.Button(btn_row2, text='Export YouTube Description', command=self.export_youtube_description)
        export_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(export_btn, 'Export YouTube description and song details')
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        main_frame.rowconfigure(4, weight=1)
        main_frame.rowconfigure(5, weight=1)
        main_frame.rowconfigure(6, weight=1)
    
    def create_ai_tab(self, parent):
        """Create the AI prompts tab."""
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Prompt output
        ttk.Label(main_frame, text='Generated Prompt:', font=('TkDefaultFont', 9, 'bold')).pack(anchor=tk.W)
        self.ai_prompt_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.ai_prompt_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        gen_prompt_btn = ttk.Button(btn_frame, text='Generate Prompt', command=self.generate_prompt)
        gen_prompt_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(gen_prompt_btn, 'Generate AI prompt from song details')
        
        copy_prompt_btn = ttk.Button(btn_frame, text='Copy Prompt', command=self.copy_ai_prompt)
        copy_prompt_btn.pack(side=tk.LEFT, padx=5)
        create_tooltip(copy_prompt_btn, 'Copy prompt to clipboard')
    
    def log_debug(self, level: str, message: str):
        """Log a debug/info message to the debug output field."""
        import datetime
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        formatted_message = f'[{timestamp}] [{level}] {message}\n'
        
        self.debug_text.config(state=tk.NORMAL)
        self.debug_text.insert(tk.END, formatted_message)
        self.debug_text.see(tk.END)  # Auto-scroll to bottom
        self.debug_text.config(state=tk.DISABLED)
    
    def toggle_debug(self):
        """Toggle debug section visibility."""
        if self.debug_collapsed:
            self.debug_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
            self.debug_collapsed = False
            self.debug_toggle_btn.config(text='▼ Debug Output')
        else:
            self.debug_frame.pack_forget()
            self.debug_collapsed = True
            self.debug_toggle_btn.config(text='▶ Debug Output')
    
    def focus_search(self):
        """Focus on the search entry."""
        if hasattr(self, 'search_entry'):
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)
    
    def clear_debug(self):
        """Clear the debug output field."""
        self.debug_text.config(state=tk.NORMAL)
        self.debug_text.delete('1.0', tk.END)
        self.debug_text.config(state=tk.DISABLED)
        self.log_debug('INFO', 'Debug output cleared')

    def populate_tree(self, rows):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, row in enumerate(rows):
            style = row.get('style', '')
            self.tree.insert('', tk.END, iid=str(idx), values=(style,))
        self.status_var.set(f'{len(rows)} styles shown')
        self.log_debug('INFO', f'Populated tree with {len(rows)} styles')

    def sort_by_column(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        direction = ' ↓' if self.sort_reverse else ' ↑'
        self.tree.heading('style', text='Style' + direction)
        self.apply_sorting()

    def apply_sorting(self):
        def sort_key(row):
            value = row.get(self.sort_column, '')
            
            if self.sort_column == 'decade_range':
                if '-' in value:
                    start_year = value.split('-')[0]
                else:
                    start_year = value
                try:
                    return int(start_year.replace('s', ''))
                except:
                    return 9999
            elif self.sort_column == 'tempo_bpm':
                if '-' in value:
                    avg_tempo = sum(int(x) for x in value.split('-')) / 2
                    return avg_tempo
                try:
                    return int(value)
                except:
                    return 0
            return str(value).lower()
        
        self.filtered.sort(key=sort_key, reverse=self.sort_reverse)
        self.populate_tree(self.filtered)

    def apply_filter(self):
        general_term = self.search_var.get().strip().lower()
        style_term = self.style_var.get().strip().lower()
        artists_term = self.artists_var.get().strip().lower()
        decade_term = self.decade_var.get().strip().lower()
        tempo_term = self.tempo_var.get().strip().lower()
        
        self.filtered = list(self.styles)
        
        if general_term:
            def general_match(row):
                for key in row.keys():
                    val = (row.get(key) or '').lower()
                    if general_term in val:
                        return True
                return False
            self.filtered = [r for r in self.filtered if general_match(r)]
        
        if style_term:
            self.filtered = [r for r in self.filtered if style_term in (r.get('style', '').lower())]
        
        if artists_term:
            self.filtered = [r for r in self.filtered if artists_term in (r.get('sample_artists', '').lower())]
        
        if decade_term:
            self.filtered = [r for r in self.filtered if decade_term in (r.get('decade_range', '').lower())]
        
        if tempo_term:
            self.filtered = [r for r in self.filtered if tempo_term in (r.get('tempo_bpm', '').lower())]
        
        self.apply_sorting()

    def clear_filters(self):
        self.search_var.set('')
        self.style_var.set('')
        self.artists_var.set('')
        self.decade_var.set('')
        self.tempo_var.set('')
        self.apply_filter()

    def on_select(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self.filtered):
            return
        
        self.current_row = self.filtered[idx]
        
        # Save selected style to config
        style_name = self.current_row.get('style', '')
        if style_name:
            self.ai_config['last_selected_style'] = style_name
            save_config(self.ai_config)
            self.log_debug('INFO', f'Selected style: {style_name}')
        
        # Populate detail fields
        for key, widget in self.detail_widgets.items():
            widget.config(state=tk.NORMAL)
            widget.delete('1.0', tk.END)
            value = self.current_row.get(key, '')
            widget.insert('1.0', value)
            widget.config(state=tk.DISABLED)
    
    def copy_field(self, field_key):
        """Copy a specific field to clipboard."""
        if not self.current_row:
            self.log_debug('WARNING', 'Copy Field: No style selected.')
            return
        
        value = self.current_row.get(field_key, '')
        if not value:
            self.log_debug('WARNING', f'Copy Field: Field {field_key} is empty.')
            return
        
        self.clipboard_clear()
        self.clipboard_append(value)
        self.update()
        self.log_debug('INFO', f'{self.detail_fields[field_key]} copied to clipboard.')
    
    def copy_to_clipboard(self, text_widget):
        """Copy text from a text widget to clipboard."""
        text = text_widget.get('1.0', tk.END).strip()
        if not text:
            self.log_debug('WARNING', 'Copy: No text to copy.')
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.log_debug('INFO', 'Text copied to clipboard.')
    
    def merge_styles(self):
        """Merge multiple styles using AI."""
        styles = self.styles_text.get('1.0', tk.END).strip()
        if not styles:
            self.log_debug('WARNING', 'Merge Styles: Please enter styles to merge.')
            return
        
        self.log_debug('INFO', 'Starting style merge operation')
        
        # Get the currently selected style as context
        original_style = ''
        if self.current_row:
            original_style = self.current_row.get('style', '')
        
        self.log_debug('DEBUG', f'Styles to merge: {styles[:50]}...')
        self.log_debug('DEBUG', f'Original style context: {original_style if original_style else "None"}')
        
        # Show processing message
        self.merged_style_text.delete('1.0', tk.END)
        self.merged_style_text.insert('1.0', 'Processing... Please wait.')
        self.update()
        
        # Get prompt template
        template = get_prompt_template('merge_styles')
        if not template:
            self.log_debug('ERROR', 'Failed to load merge_styles template')
            return
        
        self.log_debug('DEBUG', 'Loaded merge_styles template')
        
        # Replace template variables
        prompt = template.replace('{STYLES_TO_MERGE}', styles)
        prompt = prompt.replace('{ORIGINAL_STYLE}', original_style if original_style else 'None selected')
        
        # Call Azure AI
        self.log_debug('INFO', 'Calling Azure AI API...')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, profile='text')
        finally:
            self.config(cursor='')
        
        # Display result
        self.merged_style_text.delete('1.0', tk.END)
        if result['success']:
            self.merged_style_text.insert('1.0', result['content'])
            self.log_debug('INFO', 'Styles merged successfully')
        else:
            self.merged_style_text.insert('1.0', f'Error: {result["error"]}')
            self.log_debug('ERROR', f'Failed to merge styles: {result["error"]}')

    def transform_style(self, merge_original=False):
        """Transform style for viral potential using AI.
        
        Args:
            merge_original: If True, merges the selected row's style with the styles in the text box using merge_styles logic, then transforms.
        """
        song_name = self.song_name_var.get().strip()
        artist = self.artist_var.get().strip()
        
        if not song_name or not artist:
            self.log_debug('WARNING', 'Transform Style: Please enter Song Name and Artist.')
            return

        styles = self.styles_text.get('1.0', tk.END).strip()
        
        # If merge_original is True, we first need to "merge" the styles intelligently
        # instead of just string concatenation.
        if merge_original:
            # 1. Get Original Style
            original_style = ''
            if self.current_row:
                original_style = self.current_row.get('style', '')
            
            if not original_style and not styles:
                self.log_debug('WARNING', 'Merge+Transform Style: Please select a style or enter styles to merge.')
                return

            # 2. Perform Merge if we have both, or just use what we have
            if original_style and styles:
                # We need to call the AI to merge them first
                 self.log_debug('INFO', 'Step 1/2: Merging styles...')
                 
                 # Show processing message
                 self.merged_style_text.delete('1.0', tk.END)
                 self.merged_style_text.insert('1.0', 'Step 1/2: Merging styles...')
                 self.update()

                 template = get_prompt_template('merge_styles')
                 if not template:
                    self.log_debug('ERROR', 'Failed to load merge_styles template')
                    return
                
                 prompt = template.replace('{STYLES_TO_MERGE}', styles)
                 prompt = prompt.replace('{ORIGINAL_STYLE}', original_style)
                 
                 self.config(cursor='wait')
                 self.update()
                 try:
                    result = call_azure_ai(self.ai_config, prompt, profile='text')
                 finally:
                    self.config(cursor='')
                
                 if not result['success']:
                     self.merged_style_text.insert('1.0', f'Error merging: {result["error"]}')
                     return
                 
                 # Update styles with the merged result for the transformation step
                 styles = result['content']
                 self.log_debug('INFO', 'Styles merged successfully. Step 2/2: Transforming...')

            elif original_style:
                styles = original_style

        if not styles:
            self.log_debug('WARNING', 'Transform Style: Please enter styles to transform.')
            return
        
        self.log_debug('INFO', f'Starting style transformation (Merge={merge_original})')
        
        # Show processing message
        self.merged_style_text.delete('1.0', tk.END)
        self.merged_style_text.insert('1.0', 'Processing... Please wait.')
        self.update()
        
        # Get prompt template
        template = get_prompt_template('transform_style')
        if not template:
            self.log_debug('ERROR', 'Failed to load transform_style template')
            return
            
        self.log_debug('DEBUG', 'Loaded transform_style template')
        
        # Replace template variables
        prompt = template.replace('{SONG_NAME}', song_name)
        prompt = prompt.replace('{ARTIST}', artist)
        prompt = prompt.replace('{STYLE_KEYWORDS}', styles)
        
        # Call Azure AI
        self.log_debug('INFO', 'Calling Azure AI API...')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, profile='text')
        finally:
            self.config(cursor='')
            
        # Display result
        self.merged_style_text.delete('1.0', tk.END)
        if result['success']:
            self.merged_style_text.insert('1.0', result['content'])
            self.log_debug('INFO', 'Style transformed successfully')
        else:
            self.merged_style_text.insert('1.0', f'Error: {result["error"]}')
            self.log_debug('ERROR', f'Failed to transform style: {result["error"]}')
    
    def generate_ai_cover_name(self):
        """Generate AI Cover Name using style keywords."""
        song_name = self.song_name_var.get().strip()
        artist = self.artist_var.get().strip()
        
        if not song_name or not artist:
            self.log_debug('WARNING', 'Generate AI Cover Name: Please enter Song Name and Artist.')
            return
        
        # Get style keywords - prefer Merged Style, fallback to Styles field
        style_keywords = self.merged_style_text.get('1.0', tk.END).strip()
        if not style_keywords or style_keywords.startswith('Error:'):
            style_keywords = self.styles_text.get('1.0', tk.END).strip()
        
        if not style_keywords:
            self.log_debug('WARNING', 'Generate AI Cover Name: Please merge styles first or enter styles in the Styles field.')
            return
        
        self.log_debug('INFO', 'Starting AI Cover Name generation')
        
        # Show processing message
        self.ai_cover_name_var.set('Processing... Please wait.')
        self.update()
        
        # Get prompt template
        template = get_prompt_template('ai_cover_name')
        if not template:
            self.log_debug('ERROR', 'Failed to load ai_cover_name template')
            return
        
        self.log_debug('DEBUG', 'Loaded ai_cover_name template')
        
        # Replace template variables
        prompt = template.replace('{SONG_NAME}', song_name)
        prompt = prompt.replace('{ARTIST}', artist)
        prompt = prompt.replace('{STYLE_KEYWORDS}', style_keywords)
        
        # Call Azure AI
        self.log_debug('INFO', 'Calling Azure AI API...')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, profile='text')
        finally:
            self.config(cursor='')
        
        # Display result
        if result['success']:
            self.ai_cover_name_var.set(result['content'].strip())
            self.log_debug('INFO', 'AI Cover Name generated successfully')
        else:
            self.ai_cover_name_var.set(f'Error: {result["error"]}')
            self.log_debug('ERROR', f'Failed to generate AI Cover Name: {result["error"]}')
    
    def generate_album_cover(self):
        """Generate album cover prompt using AI."""
        song_name = self.song_name_var.get().strip()
        artist = self.artist_var.get().strip()
        
        if not song_name or not artist:
            self.log_debug('WARNING', 'Generate Album Cover: Please enter Song Name and Artist.')
            return
        
        # Get style - prefer Merged Style result, fallback to Styles field
        style_keywords = self.merged_style_text.get('1.0', tk.END).strip()
        if not style_keywords or style_keywords.startswith('Error:'):
            style_keywords = self.styles_text.get('1.0', tk.END).strip()
        
        if not style_keywords:
            self.log_debug('WARNING', 'Generate Album Cover: Please merge styles first or enter styles in the Styles field.')
            return
        
        if not self.current_row:
            self.log_debug('WARNING', 'Generate Album Cover: Please select a music style from the list.')
            return
        
        self.log_debug('INFO', 'Starting album cover generation')
        
        # Get style properties from selected row
        style_description = self.current_row.get('style', '')
        mood_description = self.current_row.get('mood', '')
        decade_range = self.current_row.get('decade_range', '')
        
        # Derive visual tone from style description
        visual_tone = f'{mood_description}, {decade_range} era aesthetic'
        
        # Derive visual elements from instrumentation and style
        instrumentation = self.current_row.get('instrumentation', '')
        suggested_elements = f'musical instruments, {instrumentation}, {mood_description} atmosphere'
        
        # Derive typography from era
        if '1980s' in decade_range or '1990s' in decade_range:
            typography_style = 'retro-futuristic fonts, bold typography'
        elif '2000s' in decade_range or '2010s' in decade_range:
            typography_style = 'modern sans-serif, clean and bold'
        else:
            typography_style = 'classic, elegant typography'
        
        # Show processing message
        self.album_cover_text.delete('1.0', tk.END)
        self.album_cover_text.insert('1.0', 'Generating album cover prompt... Please wait.')
        self.update()
        
        # Get prompt template
        template = get_prompt_template('album_cover')
        if not template:
            self.log_debug('ERROR', 'Failed to load album_cover template')
            return
        
        self.log_debug('DEBUG', 'Loaded album_cover template')
        
        # Get AI Cover Name
        ai_cover_name = self.ai_cover_name_var.get().strip()
        if not ai_cover_name:
            ai_cover_name = f"{style_keywords} - {artist} _{song_name}_ Cover"
        
        # Replace template variables
        prompt = template.replace('{SONG_TITLE}', song_name)
        prompt = prompt.replace('{ORIGINAL_ARTIST}', artist)
        prompt = prompt.replace('{STYLE_DESCRIPTION}', style_keywords)
        prompt = prompt.replace('{MOOD_DESCRIPTION}', mood_description)
        prompt = prompt.replace('{VISUAL_TONE}', visual_tone)
        prompt = prompt.replace('{SUGGESTED_VISUAL_ELEMENTS}', suggested_elements)
        prompt = prompt.replace('{TYPOGRAPHY_STYLE}', typography_style)
        prompt = prompt.replace('{AI_COVER_NAME}', ai_cover_name)
        
        # Call Azure AI with system message to output only the prompt
        # TODO: Change to profile='image_gen' when image generation endpoint is implemented
        self.log_debug('INFO', 'Calling Azure AI for album cover generation...')
        system_message = 'You are an image prompt generator. Output ONLY the image prompt text, nothing else. No explanations, no labels, just the prompt itself.'
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, system_message, profile='text')
        finally:
            self.config(cursor='')
        
        # Display result
        self.album_cover_text.delete('1.0', tk.END)
        if result['success']:
            self.album_cover_text.insert('1.0', result['content'])
            self.log_debug('INFO', 'Album cover prompt generated successfully')
        else:
            self.album_cover_text.insert('1.0', f'Error: {result["error"]}')
            self.log_debug('ERROR', f'Failed to generate album cover: {result["error"]}')
    
    def generate_video_loop(self):
        """Generate video loop prompt from album cover and style."""
        # Check if album cover prompt exists
        album_cover_description = self.album_cover_text.get('1.0', tk.END).strip()
        
        if not album_cover_description or album_cover_description.startswith('Error:'):
            self.log_debug('WARNING', 'Generate Video Loop: Please generate an album cover prompt first.')
            return
        
        if not self.current_row:
            self.log_debug('WARNING', 'Generate Video Loop: Please select a music style from the list.')
            return
        
        self.log_debug('INFO', 'Starting video loop generation')
        
        # Get style properties from selected row
        style_description = self.current_row.get('style', '')
        mood_description = self.current_row.get('mood', '')
        instrumentation = self.current_row.get('instrumentation', '')
        decade_range = self.current_row.get('decade_range', '')
        
        # Derive video scene from style
        mood_keywords = mood_description if mood_description else 'cinematic, atmospheric'
        
        # Determine camera style based on mood
        if 'relaxed' in mood_description.lower() or 'chill' in mood_description.lower():
            camera_style = 'Static shot with shallow depth of field, gentle parallax from ambient elements'
        elif 'energetic' in mood_description.lower() or 'upbeat' in mood_description.lower():
            camera_style = 'Dynamic tracking shot with smooth movement, slight dolly forward'
        else:
            camera_style = 'Cinematic static shot with subtle movement, shallow depth of field'
        
        # Determine lighting based on mood and era
        if '80s' in decade_range or 'retro' in style_description.lower():
            lighting_description = 'Retro neon color palette with warm tones and soft ambient illumination'
        elif 'warm' in mood_description.lower() or 'cozy' in mood_description.lower():
            lighting_description = 'Warm color temperature with soft illumination and gentle ambient transitions'
        else:
            lighting_description = 'Professional video lighting with balanced shadows and highlights for visual clarity'
        
        # Generate visual elements for video
        visual_elements = f'{instrumentation}, {mood_description} atmosphere'
        
        # Animation/effects description
        if 'lo-fi' in style_description.lower() or 'vinyl' in instrumentation.lower():
            animation_description = 'Gentle analog texture overlay, subtle film grain, peaceful ambient motion'
        elif 'rock' in style_description.lower() or 'energetic' in mood_description.lower():
            animation_description = 'Dynamic lighting shifts, occasional camera motion, energetic feel'
        else:
            animation_description = 'Subtle atmospheric movement, soft transitions, cinematic effects'
        
        # Create video scene description based on album cover
        video_scene_description = f'A professional music visualizer scene representing the {style_description} aesthetic. Animate the album cover design elements with subtle motion and visual effects suitable for music visualization.'
        
        # Show processing message
        self.video_loop_text.delete('1.0', tk.END)
        self.video_loop_text.insert('1.0', 'Generating video loop prompt... Please wait.')
        self.update()
        
        # Get prompt template
        template = get_prompt_template('video_loop')
        if not template:
            self.log_debug('ERROR', 'Failed to load video_loop template')
            return
        
        self.log_debug('DEBUG', 'Loaded video_loop template')
        
        # Replace template variables
        prompt = template.replace('{ALBUM_COVER_DESCRIPTION}', album_cover_description)
        prompt = prompt.replace('{STYLE_DESCRIPTION}', style_description)
        prompt = prompt.replace('{MOOD_DESCRIPTION}', mood_description)
        prompt = prompt.replace('{VIDEO_SCENE_DESCRIPTION}', video_scene_description)
        prompt = prompt.replace('{MOOD_KEYWORDS}', mood_keywords)
        prompt = prompt.replace('{VISUAL_ELEMENTS}', visual_elements)
        prompt = prompt.replace('{CAMERA_STYLE}', camera_style)
        prompt = prompt.replace('{LIGHTING_DESCRIPTION}', lighting_description)
        prompt = prompt.replace('{ANIMATION_DESCRIPTION}', animation_description)
        
        # Call Azure AI with system message to output only the prompt
        # TODO: Change to profile='video_gen' when video generation endpoint is implemented
        self.log_debug('INFO', 'Calling Azure AI for video loop generation...')
        system_message = 'You are a professional video prompt generator for music visualizers. Generate clean, artistic, SFW video prompts suitable for music content. CRITICAL: Adapt the prompt to comply with Azure AI Content Safety guidelines (https://ai.azure.com/doc/azure/ai-foundry/ai-services/content-safety-overview). Ensure the prompt avoids any content that could violate safety policies including violence, sexual content, hate speech, self-harm, or any harmful or inappropriate material. If the input contains potentially problematic elements, adapt them to safe, artistic alternatives suitable for music visualization. Output ONLY the final video prompt text with no explanations or extra labels.'
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, system_message, profile='text')
        finally:
            self.config(cursor='')
        
        # Display result
        self.video_loop_text.delete('1.0', tk.END)
        if result['success']:
            self.video_loop_text.insert('1.0', result['content'])
            self.log_debug('INFO', 'Video loop prompt generated successfully')
        else:
            self.video_loop_text.insert('1.0', f'Error: {result["error"]}')
            self.log_debug('ERROR', f'Failed to generate video loop: {result["error"]}')

    def run_video_loop_model(self):
        """Placeholder for running the video loop model using the generated prompt."""
        self.log_debug('INFO', 'Run Video Loop Prompt clicked')
        # Retrieve current prompt
        prompt = self.video_loop_text.get('1.0', tk.END).strip()
        if not prompt or prompt.startswith('Error:'):
            self.log_debug('WARNING', 'Run Video Loop Prompt: Please generate a video loop prompt first.')
            return

        # Show dialog to inject extra commands
        dialog = ExtraCommandsDialog(self, prompt)
        self.wait_window(dialog)
        
        # If user canceled, abort
        if dialog.result is None:
            self.log_debug('INFO', 'Run Video Loop Prompt canceled by user')
            return
        
        # Inject extra commands if provided (empty string means use prompt as-is)
        if dialog.result:
            # Append extra commands to the prompt
            prompt = f"{prompt} {dialog.result}"
            self.log_debug('INFO', f'Extra commands injected: {dialog.result[:100]}...')

        # Read options
        size = self.video_size_var.get().strip() or '720x1280'
        seconds = self.video_seconds_var.get().strip() or '4'

        # Call video endpoint
        self.log_debug('DEBUG', f'Video options: size={size}, seconds={seconds}')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_video(self.ai_config, prompt, size=size, seconds=seconds, profile='video_gen')
        finally:
            self.config(cursor='')

        if not result['success']:
            self.log_debug('ERROR', f"Video generation failed: {result['error']}")
            dbg = result.get('debug', {})
            if dbg:
                self.log_debug('DEBUG', f"Video call debug: url={dbg.get('url','')}, status={dbg.get('status','')}, ctype={dbg.get('content_type','')}")
                self.log_debug('DEBUG', f"Video call options: size={dbg.get('size','')}, seconds={dbg.get('seconds','')}, model={dbg.get('model','')}, api_version={dbg.get('api_version','')}")
                if dbg.get('body_preview'):
                    self.log_debug('DEBUG', f"Body preview: {dbg.get('body_preview')}")
            # messagebox.showerror('Run Video Loop Prompt', f"Failed to generate video:\n{result['error']}")
            return

        # If URL returned, show and optionally open
        url = result.get('url', '')
        if url:
            self.log_debug('INFO', f'Video generated. URL: {url}')
            return

        # If bytes returned, ask to save
        video_bytes = result.get('video_bytes', b'')
        if not video_bytes:
            self.log_debug('ERROR', 'No video content returned from the API.')
            return

        # Choose filename
        ai_cover_name = self.ai_cover_name_var.get().strip() or 'video'
        safe_basename = ai_cover_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        filename = filedialog.asksaveasfilename(
            title='Save Generated Video',
            defaultextension='.mp4',
            filetypes=[('MP4 Video', '*.mp4'), ('All Files', '*.*')],
            initialfile=f"{safe_basename}.mp4"
        )
        if not filename:
            self.log_debug('INFO', 'Save video canceled by user')
            return

        try:
            with open(filename, 'wb') as f:
                f.write(video_bytes)
            self.log_debug('INFO', f'Video saved to {filename}')
        except Exception as e:
            self.log_debug('ERROR', f'Failed to save video: {e}')

    def run_image_model(self):
        """Run the image generation model on the Album Cover prompt and save the image."""
        # Ensure there is an album cover prompt
        prompt = self.album_cover_text.get('1.0', tk.END).strip()
        if not prompt or prompt.startswith('Error:'):
            self.log_debug('WARNING', 'Run Image Model: Please generate an album cover prompt first.')
            return

        # Show dialog to inject extra commands
        dialog = ExtraCommandsDialog(self, prompt)
        self.wait_window(dialog)
        
        # If user canceled, abort
        if dialog.result is None:
            self.log_debug('INFO', 'Run Album Cover Prompt canceled by user')
            return
        
        # Inject extra commands if provided (empty string means use prompt as-is)
        if dialog.result:
            # Append extra commands to the prompt
            prompt = f"{prompt} {dialog.result}"
            self.log_debug('INFO', f'Extra commands injected: {dialog.result[:100]}...')

        # Determine default filename from AI Cover Name (fallback to Song - Artist)
        ai_cover_name = self.ai_cover_name_var.get().strip()
        if not ai_cover_name:
            song_name = self.song_name_var.get().strip()
            artist = self.artist_var.get().strip()
            ai_cover_name = f'{artist} - {song_name}'.strip(' -') if (artist or song_name) else 'album_cover'

        safe_basename = ai_cover_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')

        # Call Azure Images API
        profiles = self.ai_config.get('profiles', {})
        img_profile = profiles.get('image_gen', {})
        ep = _sanitize_azure_endpoint((img_profile.get('endpoint', '') or ''))
        dep = img_profile.get('deployment', '')
        ver = img_profile.get('api_version', '2024-02-15-preview')
        self.log_debug('INFO', f'Calling Azure Image model...')
        self.log_debug('DEBUG', f'Image profile details: endpoint={ep or "<empty>"}, deployment={dep or "<empty>"}, api_version={ver}')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_image(self.ai_config, prompt, size='1024x1024', profile='image_gen')
        finally:
            self.config(cursor='')

        if not result['success']:
            self.log_debug('ERROR', f"Image generation failed: {result['error']}")
            return

        img_bytes = result.get('image_bytes', b'')
        if not img_bytes:
            self.log_debug('ERROR', 'No image bytes received from image model')
            return

        # Show preview inside UI
        try:
            # Encode to base64 string for Tk PhotoImage
            b64_data = base64.b64encode(img_bytes).decode('ascii')
            photo = tk.PhotoImage(data=b64_data)
            # Downscale if very large
            max_dim = 512
            w, h = photo.width(), photo.height()
            if w > max_dim or h > max_dim:
                # Compute integer subsample factor (>=1)
                factor = max(1, max(w // max_dim, h // max_dim))
                photo = photo.subsample(factor, factor)
            self.album_cover_photo = photo  # keep reference
            self.album_cover_preview.config(image=self.album_cover_photo, text='')
            self.log_debug('INFO', f'Preview updated ({w}x{h})')
        except Exception as e:
            self.log_debug('ERROR', f'Failed to render preview: {e}')

        # Ask user where to save
        filename = filedialog.asksaveasfilename(
            title='Save Generated Album Cover',
            defaultextension='.png',
            filetypes=[('PNG Image', '*.png'), ('All Files', '*.*')],
            initialfile=f"{safe_basename}.png"
        )
        if not filename:
            self.log_debug('INFO', 'Save image canceled by user')
            return

        try:
            with open(filename, 'wb') as f:
                f.write(img_bytes)
            self.log_debug('INFO', f'Image saved to {filename}')
            # Persist last saved image path and dir
            try:
                song_details = self.ai_config.get('song_details', {})
                song_details['album_cover_image_path'] = filename
                song_details['album_cover_image_dir'] = os.path.dirname(filename)
                self.ai_config['song_details'] = song_details
                save_config(self.ai_config)
            except Exception as e:
                self.log_debug('ERROR', f'Failed to persist last image path: {e}')
        except Exception as e:
            self.log_debug('ERROR', f'Failed to save image: {e}')

    def try_load_last_album_cover(self):
        """Attempt to load last album cover image from saved path or directory."""
        try:
            song_details = self.ai_config.get('song_details', {})
            last_path = song_details.get('album_cover_image_path', '')
            if last_path and os.path.isfile(last_path):
                self._load_album_cover_preview_from_path(last_path)
                return
            last_dir = song_details.get('album_cover_image_dir', '')
            if last_dir and os.path.isdir(last_dir):
                pngs = glob.glob(os.path.join(last_dir, '*.png'))
                if pngs:
                    # Pick most recent by mtime
                    latest = max(pngs, key=lambda p: os.path.getmtime(p))
                    self._load_album_cover_preview_from_path(latest)
        except Exception as e:
            self.log_debug('ERROR', f'Failed to load last album cover: {e}')

    def _load_album_cover_preview_from_path(self, path: str):
        """Load and display album cover preview from a PNG file path."""
        try:
            photo = tk.PhotoImage(file=path)
            max_dim = 512
            w, h = photo.width(), photo.height()
            if w > max_dim or h > max_dim:
                factor = max(1, max(w // max_dim, h // max_dim))
                photo = photo.subsample(factor, factor)
            self.album_cover_photo = photo
            self.album_cover_preview.config(image=self.album_cover_photo, text='')
            self.log_debug('INFO', f'Loaded album cover preview from {path} ({w}x{h})')
        except Exception as e:
            self.log_debug('ERROR', f'Failed to load preview from {path}: {e}')
    
    def export_youtube_description(self):
        """Export song details and YouTube description to a text file."""
        song_name = self.song_name_var.get().strip()
        artist = self.artist_var.get().strip()
        
        if not song_name or not artist:
            self.log_debug('WARNING', 'Export: Please enter Song Name and Artist.')
            return
        
        # Get all fields
        ai_cover_name = self.ai_cover_name_var.get().strip()
        lyrics = self.lyrics_text.get('1.0', tk.END).strip()
        styles_input = self.styles_text.get('1.0', tk.END).strip()
        merged_style = self.merged_style_text.get('1.0', tk.END).strip()
        album_cover_result = self.album_cover_text.get('1.0', tk.END).strip()
        video_loop_result = self.video_loop_text.get('1.0', tk.END).strip()
        
        # Get selected style info
        style_info = ''
        if self.current_row:
            style_info = self.current_row.get('style', '')
        
        # Use merged style or styles input
        style_description = merged_style if merged_style and not merged_style.startswith('Error:') else styles_input
        
        # Generate YouTube description
        youtube_desc = self.generate_youtube_description(song_name, artist, style_description, style_info)
        
        # Extract title from description
        title = ""
        if youtube_desc.startswith("TITLE:"):
            title = youtube_desc.split("\n")[0].replace("TITLE:", "").strip()
            youtube_desc = "\n".join(youtube_desc.split("\n")[2:])  # Remove title lines
        
        # Prepare full content
        content = "=" * 70 + "\n"
        content += "YOUTUBE TITLE\n"
        content += "=" * 70 + "\n\n"
        content += f"{title}\n\n"
        content += "=" * 70 + "\n"
        content += "SONG DETAILS\n"
        content += "=" * 70 + "\n\n"
        content += f"AI Cover Name: {ai_cover_name}\n"
        content += f"Song Name: {song_name}\n"
        content += f"Artist: {artist}\n"
        content += f"Style Info: {style_info}\n"
        content += f"Styles Input: {styles_input}\n"
        content += f"Merged Style: {merged_style}\n"
        content += f"Lyrics: {lyrics}\n"
        content += f"Album Cover Prompt: {album_cover_result}\n"
        content += f"Video Loop Prompt: {video_loop_result}\n"
        content += "\n" + "=" * 70 + "\n"
        content += "YOUTUBE DESCRIPTION\n"
        content += "=" * 70 + "\n\n"
        content += youtube_desc
        
        # Ask for save location
        if ai_cover_name:
            safe_basename = ai_cover_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
        else:
            safe_basename = title.replace(' ', '_').replace(':', '_').replace('/', '_')

        filename = filedialog.asksaveasfilename(
            title='Save YouTube Description',
            defaultextension='.txt',
            filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')],
            initialfile=f"{safe_basename}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_debug('INFO', f'YouTube description exported to {filename}')
            except Exception as e:
                self.log_debug('ERROR', f'Failed to export: {e}')
    
    def generate_youtube_hashtags(self, song_name, artist, style_description, style_info):
        """Generate optimized YouTube hashtags using AI, max 500 characters."""
        # Extract style name from style_description or style_info
        style_name = style_description if style_description else style_info
        
        # Get prompt template
        template = get_prompt_template('youtube_hashtags')
        if not template:
            self.log_debug('ERROR', 'Failed to load youtube_hashtags template')
            # Fallback to basic hashtags if template fails
            return self._generate_fallback_hashtags(song_name, artist, style_name)
        
        # Replace template variables
        prompt = template.replace('{SONG_NAME}', song_name)
        prompt = prompt.replace('{ARTIST}', artist)
        prompt = prompt.replace('{STYLE_NAME}', style_name)
        
        self.log_debug('INFO', 'Generating optimized hashtags with AI...')
        self.config(cursor='wait')
        self.update()
        try:
            result = call_azure_ai(self.ai_config, prompt, profile='text')
        finally:
            self.config(cursor='')
        
        if result['success']:
            hashtags = result['content'].strip()
            # Remove any unwanted prefixes like "Hashtags:" or newlines
            hashtags = hashtags.replace('Hashtags:', '').replace('hashtags:', '').strip()
            # Limit to 500 characters
            if len(hashtags) > 500:
                hashtags = hashtags[:497] + '...'
            return hashtags
        else:
            # Fallback to basic hashtags if AI fails
            self.log_debug('WARNING', 'AI hashtag generation failed, using fallback')
            return self._generate_fallback_hashtags(song_name, artist, style_name)
    
    def _generate_fallback_hashtags(self, song_name, artist, style_name):
        """Generate basic hashtags as fallback."""
        hashtags = []
        hashtags.append(song_name.replace(' ', ''))
        hashtags.append(artist.replace(' ', ''))
        if style_name:
            # Take first 3 words from style name
            style_words = style_name.split()[:3]
            hashtags.extend([w.replace(' ', '') for w in style_words])
        hashtags.extend(['AICover', 'AIMusic', 'MusicCover', 'DeltaAICovers'])
        return ', '.join(['#' + tag for tag in hashtags])[:500]
    
    def generate_youtube_description(self, song_name, artist, style_description, style_info):
        """Generate SEO-optimized YouTube description text."""
        # Extract style name from style_description or style_info
        style_name = style_description if style_description else style_info
        
        # Clean up style name (take first part if comma-separated)
        if ',' in style_name:
            style_name = style_name.split(',')[0].strip()
        
        # Generate full title in the format: "1930s Smoky Lo-Fi Swing - The Chainsmokers ft. Halsey _Closer_ Cover"
        title = f"{style_name} - {artist} _{song_name}_ Cover"
        
        # SEO-optimized description structure
        desc = f"TITLE: {title}\n\n"
        
        # Hook - First 2 lines are critical for SEO and CTR
        desc += f"🎵 AI Cover Song | {style_name} Version\n"
        desc += f"Listen to \"{song_name}\" by {artist} transformed into a {style_name.lower()} style through AI music generation.\n\n"
        
        # Rich keyword content for SEO
        desc += f"Experience {artist}'s hit song \"{song_name}\" completely reimagined with {style_name.lower()} elements. "
        desc += f"This AI-generated cover brings new life to the original with authentic {style_name.lower()} instrumentation, "
        desc += f"atmospheric production, and a fresh musical perspective.\n\n"
        
        # What's Different Section (keyword-rich)
        desc += "🔄 What's Different in This Cover:\n"
        
        # Extract key elements from merged style if available
        if style_description and not style_description.startswith('Error:'):
            keywords = style_description.split(',')[:6]  # Take first 6 keywords for better SEO
            for keyword in keywords:
                desc += f"✓ {keyword.strip()}\n"
        else:
            desc += f"✓ {style_name} instrumentation and arrangement\n"
            desc += f"✓ Atmospheric production with authentic period sound\n"
            desc += f"✓ Reimagined harmonies and musical textures\n"
            desc += f"✓ Professional AI music generation\n"
        
        desc += "\n"
        
        # Call to Action - Multiple CTAs for better engagement
        desc += "🎧 SUBSCRIBE for weekly AI covers and remixes!\n"
        desc += "🔔 Turn on notifications to never miss a new cover!\n"
        desc += "👍 Like this video if you enjoy AI music transformations!\n"
        desc += "💬 Comment your song requests for future covers!\n\n"
        
        # Credits Section
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "📋 CREDITS & INFORMATION\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += f"Original Song: \"{song_name}\" by {artist}\n"
        desc += f"AI Cover Style: {style_name}\n"
        desc += f"Video Type: AI-Generated Music Cover\n"
        desc += f"Channel: Delta AI Covers\n\n"
        
        # Channel Description
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "📺 ABOUT DELTA AI COVERS\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += "Delta AI Covers transforms your favorite songs into completely new genres and styles using advanced AI music generation. "
        desc += "From classic hits to modern pop, we create unique covers in styles like jazz, lo-fi, swing, and more. "
        desc += "Subscribe to discover how AI can reinvent music!\n\n"
        
        # Links section (placeholder for actual links)
        desc += "🔗 LINKS\n"
        desc += "• Subscribe: [Your Channel Link]\n"
        desc += "• Instagram: [Your Instagram]\n"
        desc += "• Twitter: [Your Twitter]\n\n"
        
        # Disclaimer (important for avoiding strikes)
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "⚠️ DISCLAIMER\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += "This is an AI-generated cover version of the original song. "
        desc += "All rights to the original composition belong to their respective owners. "
        desc += "This video is created for entertainment and artistic purposes only. "
        desc += "We do not claim ownership of the original song and fully support the original artists.\n\n"
        desc += "Fair Use Disclaimer: This cover qualifies as fair use under copyright law as it is transformative, "
        desc += "uses minimal copyrighted material, has no commercial purpose, and promotes the original work.\n"

        # Keywords Section (hidden but SEO-important)
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "🎹 KEYWORDS FOR SEARCH\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        desc += f"{song_name} ai cover, {artist} ai cover, {style_name.lower()} cover, "
        desc += f"ai music {song_name}, {song_name} remix, ai generated music, "
        desc += f"{style_name.lower()} music, cover song ai, ai music generation\n\n"
        
        # Hashtags Section
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        desc += "🏷️ HASHTAGS:\n"
        desc += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        # Generate optimized hashtags using AI (max 500 chars)
        hashtags = self.generate_youtube_hashtags(song_name, artist, style_description, style_info)
        desc += hashtags + '\n\n'


        return desc
    
    def save_song_details(self):
        """Save song details to config file."""
        song_details = {
            'ai_cover_name': self.ai_cover_name_var.get(),
            'song_name': self.song_name_var.get(),
            'artist': self.artist_var.get(),
            'lyrics': self.lyrics_text.get('1.0', tk.END).strip(),
            'styles': self.styles_text.get('1.0', tk.END).strip(),
            'merged_style': self.merged_style_text.get('1.0', tk.END).strip(),
            'album_cover': self.album_cover_text.get('1.0', tk.END).strip(),
            'video_loop': self.video_loop_text.get('1.0', tk.END).strip()
        }
        self.ai_config['song_details'] = song_details
        if save_config(self.ai_config):
            self.log_debug('INFO', 'Song details saved successfully to config')
            
            # If AI Cover Name is set, ask user to save settings to separate file
            ai_cover_name = self.ai_cover_name_var.get().strip()
            if ai_cover_name:
                # Use same basename logic as run_image_model
                safe_basename = ai_cover_name.replace(':', '_').replace('/', '_').replace('\\', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace("'", '_').replace('<', '_').replace('>', '_').replace('|', '_')
                
                # Ask user if they want to save to a separate file
                response = messagebox.askyesno(
                    'Save Settings File',
                    f'AI Cover Name is set. Would you like to save settings to a separate file?\n\nSuggested filename: {safe_basename}.json'
                )
                
                if response:
                    # Get the directory from last saved album cover image if available
                    default_dir = self.ai_config.get('song_details', {}).get('album_cover_image_dir', '')
                    if not default_dir:
                        # Fallback to script directory
                        default_dir = os.path.dirname(os.path.abspath(__file__))
                    
                    filename = filedialog.asksaveasfilename(
                        title='Save Song Details Settings',
                        defaultextension='.json',
                        filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')],
                        initialdir=default_dir,
                        initialfile=f"{safe_basename}.json"
                    )
                    
                    if filename:
                        try:
                            with open(filename, 'w', encoding='utf-8') as f:
                                json.dump(song_details, f, indent=4)
                            self.log_debug('INFO', f'Song details saved to {filename}')
                        except Exception as e:
                            self.log_debug('ERROR', f'Failed to save settings file: {e}')
    
    def load_song_details(self):
        """Load song details from a settings file."""
        # Get the directory from last saved album cover image if available
        default_dir = self.ai_config.get('song_details', {}).get('album_cover_image_dir', '')
        if not default_dir:
            # Fallback to script directory
            default_dir = os.path.dirname(os.path.abspath(__file__))
        
        filename = filedialog.askopenfilename(
            title='Load Song Details Settings',
            defaultextension='.json',
            filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')],
            initialdir=default_dir
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                song_details = json.load(f)
            
            # Populate fields from loaded settings
            if isinstance(song_details, dict):
                self.ai_cover_name_var.set(song_details.get('ai_cover_name', ''))
                self.song_name_var.set(song_details.get('song_name', ''))
                self.artist_var.set(song_details.get('artist', ''))
                self.lyrics_text.delete('1.0', tk.END)
                self.lyrics_text.insert('1.0', song_details.get('lyrics', ''))
                self.styles_text.delete('1.0', tk.END)
                self.styles_text.insert('1.0', song_details.get('styles', ''))
                self.merged_style_text.delete('1.0', tk.END)
                self.merged_style_text.insert('1.0', song_details.get('merged_style', ''))
                self.album_cover_text.delete('1.0', tk.END)
                self.album_cover_text.insert('1.0', song_details.get('album_cover', ''))
                self.video_loop_text.delete('1.0', tk.END)
                self.video_loop_text.insert('1.0', song_details.get('video_loop', ''))
                
                self.log_debug('INFO', f'Song details loaded from {filename}')
            else:
                self.log_debug('ERROR', 'Load Settings: Invalid settings file format.')
        except json.JSONDecodeError as e:
            self.log_debug('ERROR', f'Failed to parse JSON file: {e}')
        except Exception as e:
            self.log_debug('ERROR', f'Failed to load settings file: {e}')
    
    def restore_song_details(self):
        """Restore song details from config file."""
        song_details = self.ai_config.get('song_details', {})
        if song_details:
            self.ai_cover_name_var.set(song_details.get('ai_cover_name', ''))
            self.song_name_var.set(song_details.get('song_name', ''))
            self.artist_var.set(song_details.get('artist', ''))
            self.lyrics_text.delete('1.0', tk.END)
            self.lyrics_text.insert('1.0', song_details.get('lyrics', ''))
            self.styles_text.delete('1.0', tk.END)
            self.styles_text.insert('1.0', song_details.get('styles', ''))
            self.merged_style_text.delete('1.0', tk.END)
            self.merged_style_text.insert('1.0', song_details.get('merged_style', ''))
            self.album_cover_text.delete('1.0', tk.END)
            self.album_cover_text.insert('1.0', song_details.get('album_cover', ''))
            self.video_loop_text.delete('1.0', tk.END)
            self.video_loop_text.insert('1.0', song_details.get('video_loop', ''))
    
    def restore_last_selected_style(self):
        """Restore and select the last chosen style from config."""
        last_style = self.ai_config.get('last_selected_style', '')
        if not last_style:
            return
        
        # Find the style in the filtered list
        for idx, row in enumerate(self.filtered):
            if row.get('style', '') == last_style:
                # Select the row in the tree
                self.tree.selection_set(str(idx))
                self.tree.focus(str(idx))
                self.tree.see(str(idx))
                # Trigger the on_select event to populate details
                self.on_select(None)
                break
    
    def clear_song_fields(self):
        """Clear all song detail fields."""
        self.ai_cover_name_var.set('')
        self.song_name_var.set('')
        self.artist_var.set('')
        self.lyrics_text.delete('1.0', tk.END)
        self.styles_text.delete('1.0', tk.END)
        self.merged_style_text.delete('1.0', tk.END)
        self.album_cover_text.delete('1.0', tk.END)
        self.video_loop_text.delete('1.0', tk.END)
        # Clear album cover preview image
        self.album_cover_photo = None
        self.album_cover_preview.config(image='', text='No image generated yet')
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """Keyboard Shortcuts:

Ctrl+S          - Save song details
Ctrl+D          - Toggle debug output
Ctrl+F          - Focus search field
F5              - Reload CSV file

All shortcuts work globally when the application is focused."""
        self.log_debug('INFO', shortcuts)
    
    def show_about(self):
        """Show about dialog."""
        about_text = """Suno Style Browser

A tool for browsing music styles and generating AI prompts for album covers and video loops.

Features:
- Browse and filter music styles from CSV
- Generate AI cover names and prompts
- Create album cover images
- Generate video loop prompts
- Export YouTube descriptions

Version: 1.0"""
        self.log_debug('INFO', about_text)
    
    def open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self, self.ai_config)
        self.wait_window(dialog)
        if dialog.result:
            self.ai_config = dialog.result
            if save_config(self.ai_config):
                self.log_debug('INFO', 'Settings saved successfully.')
            else:
                self.log_debug('ERROR', 'Failed to save settings.')

    def choose_csv(self):
        initial = os.path.dirname(self.csv_path) if os.path.exists(self.csv_path) else os.path.dirname(resolve_csv_path())
        path = filedialog.askopenfilename(
            title='Select Suno Styles CSV',
            filetypes=[('CSV Files', '*.csv')],
            initialdir=initial
        )
        if path:
            self.csv_path = path
            self.reload_csv()

    def reload_csv(self):
        self.styles = load_styles(self.csv_path)
        self.filtered = list(self.styles)
        self.apply_filter()
        self.status_var.set(f'Loaded {len(self.styles)} styles from {self.csv_path}')


def main():
    csv_path = resolve_csv_path()
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    app = SunoStyleBrowser(csv_path)
    app.mainloop()


if __name__ == '__main__':
    main()
