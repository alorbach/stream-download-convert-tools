"""
Install basicsr + realesrgan for PyTorch AI upscale.

PyPI basicsr 1.4.2 fails on Python 3.11+ (setup.py KeyError: '__version__').
This script downloads the tag, patches setup.py, and installs into the active venv.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASICSR_TAG_ZIP = (
    'https://github.com/xinntao/BasicSR/archive/refs/tags/v1.4.2.zip'
)
SETUP_VERSION_PATCH = re.compile(
    r"def get_version\(\):\s*"
    r"with open\(version_file, 'r'\) as f:\s*"
    r"exec\(compile\(f\.read\(\), version_file, 'exec'\)\)\s*"
    r"return locals\(\)\['__version__'\]",
    re.MULTILINE,
)


def _log(msg: str) -> None:
    print(f'[install_ai_upscale_deps] {msg}', flush=True)


def _pip(*args: str) -> None:
    subprocess.check_call([sys.executable, '-m', 'pip', *args])


def basicsr_importable() -> bool:
    try:
        import basicsr  # noqa: F401
        return True
    except ImportError:
        return False


def realesrgan_importable() -> bool:
    try:
        import realesrgan  # noqa: F401
        return True
    except ImportError:
        return False


def patch_degradations_py(content: str) -> str:
    """torchvision 0.15+ removed functional_tensor."""
    return content.replace(
        'from torchvision.transforms.functional_tensor import rgb_to_grayscale',
        'from torchvision.transforms.functional import rgb_to_grayscale',
    )


def patch_setup_py(setup_text: str) -> str:
    if "return '1.4.2'" in setup_text and "locals()['__version__']" not in setup_text:
        return setup_text
    patched, n = SETUP_VERSION_PATCH.subn(
        "def get_version():\n    return '1.4.2'",
        setup_text,
    )
    if n:
        return patched
    return setup_text.replace(
        "return locals()['__version__']",
        "return '1.4.2'",
    )


def install_basicsr_patched() -> None:
    _patch_installed_degradations_if_needed()
    if basicsr_importable():
        _log('basicsr already installed')
        return

    _log('Downloading BasicSR v1.4.2...')
    tmp = tempfile.mkdtemp(prefix='basicsr_install_')
    zip_path = os.path.join(tmp, 'basicsr.zip')
    try:
        urllib.request.urlretrieve(BASICSR_TAG_ZIP, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmp)
        src_dirs = [p for p in Path(tmp).iterdir() if p.is_dir() and p.name.startswith('BasicSR')]
        if not src_dirs:
            raise RuntimeError('BasicSR source folder not found in archive')
        src = src_dirs[0]
        setup_path = src / 'setup.py'
        setup_path.write_text(
            patch_setup_py(setup_path.read_text(encoding='utf-8')),
            encoding='utf-8',
        )
        deg_path = src / 'basicsr' / 'data' / 'degradations.py'
        if deg_path.is_file():
            deg_path.write_text(
                patch_degradations_py(deg_path.read_text(encoding='utf-8')),
                encoding='utf-8',
            )
        _log('Installing patched basicsr (no build isolation)...')
        _pip('install', str(src), '--no-build-isolation')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _patch_installed_degradations_if_needed()
    if not basicsr_importable():
        raise RuntimeError('basicsr install finished but import failed')


def _patch_installed_degradations_if_needed() -> None:
    """Fix torchvision API in an already-installed basicsr (upgrade path)."""
    try:
        import site
        for base in site.getsitepackages():
            deg = Path(base) / 'basicsr' / 'data' / 'degradations.py'
            if deg.is_file():
                text = deg.read_text(encoding='utf-8')
                patched = patch_degradations_py(text)
                if patched != text:
                    deg.write_text(patched, encoding='utf-8')
                    _log('Patched installed basicsr/data/degradations.py')
                return
    except Exception as e:
        _log(f'Note: could not patch installed degradations.py: {e}')


def install_realesrgan() -> None:
    if realesrgan_importable():
        _log('realesrgan already installed')
        return
    _log('Installing realesrgan...')
    _pip('install', 'realesrgan>=0.3.0')


def main() -> int:
    os.chdir(Path(__file__).resolve().parent.parent)
    try:
        install_basicsr_patched()
        install_realesrgan()
    except Exception as e:
        _log(f'ERROR: {e}')
        return 1
    _log('AI upscale dependencies OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
