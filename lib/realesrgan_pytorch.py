"""
Real-ESRGAN PyTorch backend (official realesrgan pip package).

Weights are cached under {project}/realesrgan/weights/.
"""

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# UI model id -> config for RealESRGANer
PYTORCH_GENERAL_V3 = 'realesr-general-x4v3'

PYTORCH_UI_MODELS = [
    'realesr-animevideov3',
    'realesrgan-x2plus',
    PYTORCH_GENERAL_V3,
    'realesrgan-x4plus-anime',
    'realesrgan-x4plus',
    'realesrnet-x4plus',
]

HEAVY_PYTORCH_UI_MODELS = frozenset({
    'realesrgan-x2plus',
    'realesrgan-x4plus',
    'realesrgan-x4plus-anime',
    'realesrnet-x4plus',
})

_UPSAMPLER_CACHE: Dict[Tuple[str, int, int], Any] = {}


def project_root() -> str:
    return str(Path(__file__).resolve().parent.parent)


def weights_dir(root_dir: Optional[str] = None) -> str:
    base = root_dir or project_root()
    path = os.path.join(base, 'realesrgan', 'weights')
    os.makedirs(path, exist_ok=True)
    return path


def is_available() -> Tuple[bool, str]:
    """Return (ok, status_message)."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, 'PyTorch is not installed. Run the launcher to install requirements.'
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False, 'opencv-python is not installed.'
    try:
        from realesrgan import RealESRGANer  # noqa: F401
    except ImportError:
        return False, 'realesrgan package is not installed. Run the launcher to install requirements.'
    import torch
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return True, f'CUDA available: {name}'
    return True, 'CPU only (CUDA not available; upscale will be very slow)'


def _clamp_denoise(value: Optional[float], default: float = 0.5) -> float:
    """UI slider: 0=keep detail, 1=strong denoise."""
    if value is None:
        return default
    return max(0.0, min(1.0, float(value)))


def _upstream_denoise(ui_denoise: float) -> float:
    """Map UI denoise to Real-ESRGAN -dn (1=general only, 0=wdn-heavy)."""
    return 1.0 - _clamp_denoise(ui_denoise)


def _ui_model_config(ui_model: str, denoise_strength: Optional[float] = None) -> Dict[str, Any]:
    """Map Upscale tab model id to architecture and download URLs."""
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan.archs.srvgg_arch import SRVGGNetCompact

    if ui_model == 'realesr-animevideov3':
        return {
            'pytorch_name': 'realesr-animevideov3',
            'model': SRVGGNetCompact(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type='prelu',
            ),
            'netscale': 4,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',
            ],
            'denoise_strength': None,
        }
    if ui_model == PYTORCH_GENERAL_V3:
        return {
            'pytorch_name': 'realesr-general-x4v3',
            'model': SRVGGNetCompact(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu',
            ),
            'netscale': 4,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth',
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth',
            ],
            'denoise_strength': _upstream_denoise(
                _clamp_denoise(denoise_strength, 0.5),
            ),
        }
    if ui_model == 'realesrgan-x2plus':
        return {
            'pytorch_name': 'RealESRGAN_x2plus',
            'model': RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2,
            ),
            'netscale': 2,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth',
            ],
            'denoise_strength': None,
        }
    if ui_model == 'realesrgan-x4plus-anime':
        return {
            'pytorch_name': 'RealESRGAN_x4plus_anime_6B',
            'model': RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4,
            ),
            'netscale': 4,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
            ],
            'denoise_strength': None,
        }
    if ui_model == 'realesrgan-x4plus':
        return {
            'pytorch_name': 'RealESRGAN_x4plus',
            'model': RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4,
            ),
            'netscale': 4,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
            ],
            'denoise_strength': None,
        }
    if ui_model == 'realesrnet-x4plus':
        return {
            'pytorch_name': 'RealESRNet_x4plus',
            'model': RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4,
            ),
            'netscale': 4,
            'urls': [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth',
            ],
            'denoise_strength': None,
        }
    raise ValueError(f'Unknown model: {ui_model}')


def _resolve_model_path(
    cfg: Dict[str, Any], models_dir: str, log_callback: Optional[Callable[[str], None]],
) -> Tuple[Any, Optional[List[float]]]:
    from basicsr.utils.download_util import load_file_from_url

    pytorch_name = cfg['pytorch_name']
    denoise = cfg.get('denoise_strength')

    if pytorch_name == 'realesr-general-x4v3' and denoise is not None:
        wdn_name = 'realesr-general-wdn-x4v3.pth'
        main_name = 'realesr-general-x4v3.pth'
        wdn_path = os.path.join(models_dir, wdn_name)
        main_path = os.path.join(models_dir, main_name)
        for url, fname in zip(cfg['urls'], [wdn_name, main_name]):
            path = os.path.join(models_dir, fname)
            if not os.path.isfile(path):
                if log_callback:
                    log_callback(f'[INFO] Downloading weights: {fname}...')
                load_file_from_url(
                    url=url, model_dir=models_dir, progress=True, file_name=fname,
                )
        if denoise >= 0.99:
            return wdn_path, None
        return [main_path, wdn_path], [denoise, 1.0 - denoise]

    fname = f'{pytorch_name}.pth'
    model_path = os.path.join(models_dir, fname)
    if not os.path.isfile(model_path):
        if log_callback:
            log_callback(f'[INFO] Downloading weights: {fname}...')
        url = cfg['urls'][0]
        model_path = load_file_from_url(
            url=url, model_dir=models_dir, progress=True, file_name=fname,
        )
    return model_path, None


def get_upsampler(
    ui_model: str,
    gpu_id: int = 0,
    tile: int = 0,
    tile_pad: int = 10,
    root_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    denoise_strength: Optional[float] = None,
):
    """Load or return cached RealESRGANer for a UI model id."""
    from realesrgan import RealESRGANer

    denoise_key = -1.0
    if ui_model == PYTORCH_GENERAL_V3:
        denoise_key = round(
            _upstream_denoise(_clamp_denoise(denoise_strength, 0.5)), 3,
        )
    cache_key = (ui_model, gpu_id, tile, denoise_key)
    if cache_key in _UPSAMPLER_CACHE:
        return _UPSAMPLER_CACHE[cache_key]

    cfg = _ui_model_config(ui_model, denoise_strength=denoise_strength)
    models_dir = weights_dir(root_dir)
    model_path, dni_weight = _resolve_model_path(cfg, models_dir, log_callback)

    upsampler = RealESRGANer(
        scale=cfg['netscale'],
        model_path=model_path,
        dni_weight=dni_weight,
        model=cfg['model'],
        tile=tile,
        tile_pad=tile_pad,
        pre_pad=0,
        half=True,
        gpu_id=gpu_id,
    )
    _UPSAMPLER_CACHE[cache_key] = upsampler
    return upsampler


def pytorch_tile_attempts(ui_model: str, cuda_available: bool) -> List[int]:
    """Tile sizes to try (0 = no tiling)."""
    if ui_model == 'realesr-animevideov3' and cuda_available:
        return [0]
    if ui_model in HEAVY_PYTORCH_UI_MODELS:
        return [512, 384, 256, 0]
    return [0]


def clear_upsampler_cache() -> None:
    _UPSAMPLER_CACHE.clear()


def upscale_frame_dir(
    in_dir: str,
    out_dir: str,
    ui_model: str,
    outscale: float,
    gpu_id: int = 0,
    tile: int = 0,
    root_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    denoise_strength: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Upscale PNG frames in in_dir -> out_dir (same basenames).
    Returns (ok, error_message).
    """
    import cv2

    def _png_sort_key(p: Path) -> int:
        import re
        m = re.search(r'(\d+)', p.stem)
        return int(m.group(1)) if m else 0

    frames = sorted(Path(in_dir).glob('*.png'), key=_png_sort_key)
    if not frames:
        return False, 'No input frames found'

    os.makedirs(out_dir, exist_ok=True)
    try:
        upsampler = get_upsampler(
            ui_model,
            gpu_id=gpu_id,
            tile=tile,
            root_dir=root_dir,
            log_callback=log_callback,
            denoise_strength=denoise_strength,
        )
    except Exception as e:
        return False, f'Failed to load model: {e}'

    total = len(frames)
    for i, src_path in enumerate(frames):
        if progress_callback:
            pct = (i / total) * 100.0 if total else 0.0
            progress_callback(pct, f'AI frame {i + 1}/{total}')
        img = cv2.imread(str(src_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            return False, f'Could not read frame: {src_path.name}'
        try:
            output, _ = upsampler.enhance(img, outscale=outscale)
        except RuntimeError as e:
            err = str(e)
            if 'out of memory' in err.lower() or 'cuda' in err.lower():
                return False, f'GPU out of memory (try a smaller tile): {err}'
            return False, err
        dest = os.path.join(out_dir, src_path.name)
        if not cv2.imwrite(dest, output):
            return False, f'Could not write frame: {dest}'

    if progress_callback:
        progress_callback(100.0, f'AI frames {total}/{total}')
    return True, ''
