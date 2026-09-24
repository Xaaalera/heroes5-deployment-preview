import os
from pathlib import Path
import subprocess
import sys

MOD_ROOT = Path(__file__).resolve().parents[1]
DEVKIT = MOD_ROOT / 'devkit'
if not (DEVKIT / 'scripts/workspace.py').is_file():
    raise RuntimeError('Initialize the pinned devkit: git submodule update --init --recursive')
sys.path.insert(0, str(DEVKIT / 'scripts'))
WORKSPACE = Path(os.environ.get('H5_WORKSPACE') or MOD_ROOT).expanduser().resolve()
BUILD = Path(os.environ.get('H5_PREVIEW_BUILD') or MOD_ROOT / '.local/build/deployment-preview-native').resolve()


def vcvarsall():
    configured = os.environ.get('H5_VCVARSALL')
    if configured:
        return Path(configured)
    locator = Path(os.environ.get('ProgramFiles(x86)', '')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if locator.is_file():
        result = subprocess.run([str(locator), '-latest', '-products', '*', '-requires',
                                 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-find',
                                 'VC/Auxiliary/Build/vcvarsall.bat'], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            return Path(result.stdout.splitlines()[0])
    return MOD_ROOT / '__missing_vcvarsall__'
