"""
Real-ESRGAN ncnn-vulkan utilities (detect, download, install).

Portable Windows build from xinntao/Real-ESRGAN releases.
"""

import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

EXE_NAME = 'realesrgan-ncnn-vulkan.exe'

RELEASE_BASE = (
    'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0'
)
DOWNLOAD_URLS = {
    'Windows': f'{RELEASE_BASE}/realesrgan-ncnn-vulkan-20220424-windows.zip',
    'Linux': f'{RELEASE_BASE}/realesrgan-ncnn-vulkan-20220424-ubuntu.zip',
    'Darwin': f'{RELEASE_BASE}/realesrgan-ncnn-vulkan-20220424-macos.zip',
}

# Models that need weights not in the 2022 portable zip (video2x builds are incompatible).
UNSUPPORTED_NCNN_MODELS = frozenset({
    'realesr-general-x4v3',
    'realesr-general-wdn-x4v3',
})

HEAVY_TILE_MODELS = frozenset({
    'realesrgan-x4plus',
    'realesrgan-x4plus-anime',
    'realesrnet-x4plus',
})


class RealESRGANManager:
    """Manage local Real-ESRGAN ncnn-vulkan installation."""

    def __init__(self, root_dir: str, log_callback: Optional[Callable[[str], None]] = None):
        self.root_dir = root_dir
        self.install_folder = os.path.join(root_dir, 'realesrgan')
        self.exe_path: Optional[str] = None
        self.log_callback = log_callback or (lambda msg: print(f'[Real-ESRGAN] {msg}'))

    def log(self, message: str) -> None:
        self.log_callback(f'[Real-ESRGAN] {message}')

    def _subprocess_flags(self) -> int:
        return subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

    def find_installed_exe(self) -> Optional[str]:
        """Search install folder for the ncnn-vulkan executable."""
        if not os.path.isdir(self.install_folder):
            return None
        for root, _dirs, files in os.walk(self.install_folder):
            for name in files:
                if name.lower() == EXE_NAME.lower():
                    return os.path.join(root, name)
                if sys.platform != 'win32' and name == 'realesrgan-ncnn-vulkan':
                    path = os.path.join(root, name)
                    if os.access(path, os.X_OK):
                        return path
        return None

    def check_realesrgan(self, custom_path: Optional[str] = None) -> bool:
        """Return True if executable is available."""
        if custom_path and os.path.isfile(custom_path):
            self.exe_path = custom_path
            return True
        local = self.find_installed_exe()
        if local:
            self.exe_path = local
            self.log(f'Using local install: {local}')
            return True
        self.exe_path = None
        return False

    def get_exe_path(self) -> Optional[str]:
        if self.exe_path and os.path.isfile(self.exe_path):
            return self.exe_path
        if self.check_realesrgan():
            return self.exe_path
        return None

    def models_dir_for_exe(self, exe_path: Optional[str] = None) -> Optional[str]:
        exe = exe_path or self.get_exe_path()
        if not exe:
            return None
        return os.path.join(os.path.dirname(os.path.abspath(exe)), 'models')

    def model_files_present(self, models_dir: str, model_name: str) -> bool:
        param = os.path.join(models_dir, f'{model_name}.param')
        model_bin = os.path.join(models_dir, f'{model_name}.bin')
        return os.path.isfile(param) and os.path.isfile(model_bin)

    def ensure_ncnn_model(
        self,
        model_name: str,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Return False if model is known incompatible with the bundled ncnn build."""
        del log_callback, progress_callback
        return model_name not in UNSUPPORTED_NCNN_MODELS

    def offer_realesrgan_install(self, messagebox_callback=None) -> bool:
        """Prompt to download portable build. Returns True if install started."""
        system = platform.system()
        url = DOWNLOAD_URLS.get(system)

        if not url:
            if messagebox_callback:
                messagebox_callback(
                    'showerror',
                    'Real-ESRGAN',
                    'Auto-install is only available on Windows, Linux, and macOS.\n'
                    'See https://github.com/xinntao/Real-ESRGAN#portable-executable-files-ncnn',
                )
            return False

        if messagebox_callback:
            size_hint = '~45 MB' if system == 'Windows' else '~50 MB'
            response = messagebox_callback(
                'askyesno',
                'Real-ESRGAN Not Found',
                'AI upscale needs realesrgan-ncnn-vulkan.\n\n'
                f'Download portable build automatically ({size_hint})?\n'
                'Installs into the realesrgan/ folder in this project.\n'
                'No admin rights required.',
            )
            if not response:
                messagebox_callback(
                    'showinfo',
                    'Manual Installation',
                    'Download from:\n'
                    'https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0\n\n'
                    'Extract the zip and set Real-ESRGAN exe in the Upscale tab.',
                )
                return False

        self.download_portable(url)
        return True

    def download_portable(
        self,
        url: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        success_callback: Optional[Callable[[str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        if url is None:
            url = DOWNLOAD_URLS.get(platform.system())
        if not url:
            if error_callback:
                error_callback('No download URL for this platform.')
            return
        thread = threading.Thread(
            target=self._download_thread,
            args=(url, progress_callback, success_callback, error_callback),
            daemon=True,
        )
        thread.start()

    def download_windows(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        success_callback: Optional[Callable[[str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.download_portable(DOWNLOAD_URLS['Windows'], progress_callback, success_callback, error_callback)

    def _download_thread(
        self,
        url: str,
        progress_callback: Optional[Callable[[str], None]],
        success_callback: Optional[Callable[[str], None]],
        error_callback: Optional[Callable[[str], None]],
    ) -> None:
        temp_zip = os.path.join(self.root_dir, 'realesrgan_temp.zip')
        try:
            self.log(f'Downloading from {url}')
            if progress_callback:
                progress_callback('Downloading Real-ESRGAN...')

            def report(block_num: int, block_size: int, total_size: int) -> None:
                if total_size > 0 and block_num % 40 == 0 and progress_callback:
                    pct = int(block_num * block_size * 100 / total_size)
                    progress_callback(f'Download {min(pct, 99)}%')

            urllib.request.urlretrieve(url, temp_zip, reporthook=report)

            if progress_callback:
                progress_callback('Extracting...')
            self.log('Extracting archive...')

            if os.path.isdir(self.install_folder):
                shutil.rmtree(self.install_folder, ignore_errors=True)
            os.makedirs(self.install_folder, exist_ok=True)

            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(self.install_folder)

            if os.path.isfile(temp_zip):
                os.remove(temp_zip)

            exe = self.find_installed_exe()
            if not exe:
                raise FileNotFoundError(f'{EXE_NAME} not found after extract')

            self.exe_path = exe
            self.log(f'Installed: {exe}')
            msg = f'Real-ESRGAN installed.\n\n{exe}'
            if success_callback:
                success_callback(msg)
        except Exception as e:
            self.log(f'Install failed: {e}')
            if os.path.isfile(temp_zip):
                try:
                    os.remove(temp_zip)
                except OSError:
                    pass
            err = (
                f'Failed to install Real-ESRGAN:\n{e}\n\n'
                'Download manually:\n'
                'https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0'
            )
            if error_callback:
                error_callback(err)


def ensure_ncnn_model_for_exe(
    ai_exe: str,
    model_name: str,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Return False if model is known incompatible with the bundled ncnn build."""
    del ai_exe, log_callback, progress_callback
    return model_name not in UNSUPPORTED_NCNN_MODELS


def unsupported_ncnn_model_message(model_name: str) -> str:
    return (
        f'Model {model_name} is not supported by the bundled Real-ESRGAN ncnn '
        'build (2022). Use realesr-animevideov3, realesrgan-x4plus, or '
        'realesrgan-x4plus-anime.'
    )


def realesrgan_tile_attempts(src_w: int, src_h: int, model_name: str):
    """
    Tile sizes (-t) to try for heavy RRDB models, in order.
    None = omit -t (exe auto-tile, often ~100-200px -> visible seams).
    Prefer one tile (full frame) when the clip is small enough to fit in VRAM.
    """
    if model_name not in HEAVY_TILE_MODELS:
        return [None]
    longest = max(src_w, src_h)
    sizes = []
    if longest <= 1280:
        sizes.append(str(longest))
    for t in (512, 384, 256):
        ts = str(t)
        if t <= longest and ts not in sizes:
            sizes.append(ts)
    sizes.append(None)
    seen = set()
    out = []
    for s in sizes:
        key = s if s is not None else '__auto__'
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _tile_boundary_columns_src(src_w: int, tile: int):
    if tile <= 0 or tile >= src_w:
        return []
    out = []
    x = tile
    while x < src_w:
        out.append(x)
        x += tile
    return out


def _auto_tile_sizes_to_check(src_w: int):
    """Tile sizes the 2022 ncnn exe may pick when -t is omitted."""
    return [t for t in (512, 384, 256, 224, 200, 168, 128, 100, 64, 32) if t < src_w]


def frame_has_vertical_tile_seam(gray_im, src_w: int, scale: int, tile_t: Optional[str] = None) -> bool:
    """Detect a sharp vertical jump typical of ncnn tile stitching."""
    try:
        import numpy as np
    except ImportError:
        return False
    arr = np.asarray(gray_im, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] < 64:
        return False
    col_mean = arr.mean(axis=0)
    diffs = np.abs(np.diff(col_mean))
    med = float(np.median(diffs)) + 1e-3
    if tile_t is not None:
        try:
            tiles = [int(tile_t)]
        except ValueError:
            tiles = []
    else:
        tiles = _auto_tile_sizes_to_check(src_w)
    for tile in tiles:
        for bx_src in _tile_boundary_columns_src(src_w, tile):
            bx = bx_src * scale
            if bx < 4 or bx >= len(diffs) - 4:
                continue
            window = diffs[max(0, bx - 3): min(len(diffs), bx + 4)]
            if window.size == 0:
                continue
            peak = float(window.max())
            left = float(col_mean[max(0, bx - 24): bx].mean())
            right = float(col_mean[bx: min(col_mean.shape[0], bx + 24)].mean())
            jump = abs(left - right)
            if jump > 35.0:
                return True
            if peak > med * 3.0 and jump > 12.0:
                return True
    return False


def realesrgan_stderr_indicates_failure(stderr: str, stdout: str) -> bool:
    text = ((stderr or '') + '\n' + (stdout or '')).lower()
    markers = (
        'layer clip not exists',
        'parse error',
        'failed to',
        'error:',
        'exception',
    )
    return any(m in text for m in markers)


def validate_realesrgan_frames(
    out_dir: str,
    expected_w: int,
    expected_h: int,
    sample_count: int = 3,
    src_w: Optional[int] = None,
    ai_scale: int = 2,
    tile_t: Optional[str] = None,
    check_tile_seams: bool = False,
):
    """Return (ok, reason). Sample upscaled PNGs before encode."""
    paths = sorted(Path(out_dir).rglob('*.png'))
    if not paths:
        return False, 'no output PNGs'
    step = max(1, len(paths) // sample_count)
    samples = [paths[i] for i in range(0, len(paths), step)][:sample_count]
    try:
        from PIL import Image
    except ImportError:
        for p in samples:
            if p.stat().st_size < 3000:
                return False, f'suspiciously small frame: {p.name}'
        return True, ''
    src_w = src_w or (expected_w // max(ai_scale, 1))
    for p in samples:
        if p.stat().st_size < 3000:
            return False, f'suspiciously small frame: {p.name}'
        with Image.open(p) as im:
            w, h = im.size
            if abs(w - expected_w) > 4 or abs(h - expected_h) > 4:
                return False, (
                    f'frame size {w}x{h}, expected ~{expected_w}x{expected_h}'
                )
            gray = im.convert('L')
            lo, hi = gray.getextrema()
            if hi - lo < 3:
                return False, f'frame appears blank/flat: {p.name}'
            if check_tile_seams and frame_has_vertical_tile_seam(
                gray, src_w, ai_scale, tile_t=tile_t,
            ):
                label = tile_t or 'auto'
                return False, f'tile seam detected (tile {label})'
    return True, ''
