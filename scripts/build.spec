import argparse
import platform
import subprocess
from pathlib import Path
from tomllib import load

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE
from PyInstaller.utils.hooks import copy_metadata

# Parsing the "portable" arg
parser = argparse.ArgumentParser()
parser.add_argument("--portable", action="store_true")
options = parser.parse_args()

with open("pyproject.toml", "rb") as file:
    pyproject = load(file)["project"]

system = platform.system()
name = pyproject["name"]
if system == "Windows":
    ICON = (Path(".") / "img" / "icon-Win.ico").resolve()
elif system == "Darwin":
    ICON = (Path(".") / "img" / "icon-Mac.icns").resolve()
else:  # Linux doesn't use built-into-EXE icons
    ICON = None

try:
    VERSION = (
        subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL,
        )
        .decode()
        .strip()
    )
except subprocess.CalledProcessError:
    VERSION = "dev-" + subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()

if not VERSION:
    raise ValueError("extracted git version was false, thats illegal.")

a = Analysis(
    ["../src/launcher.py"],
    pathex=["../src"],
    hex=[],
    binaries=[],
    datas=[
        *copy_metadata("ghostsubscribe-playlist-manager"),
        ("../img/icon.png", "img"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

include = [a.scripts]
if options.portable:
    include += [a.binaries, a.datas]
exe = EXE(
    pyz,
    *include,
    [],
    exclude_binaries=not options.portable,
    name=name,
    icon=ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = (
    None
    if options.portable
    else COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=name,
    )
)

if platform.system() == "Darwin":
    app = BUNDLE(
        exe if coll is None else coll,
        name=f"{name}.app",
        icon=ICON,
        bundle_identifier="com.thetimebreaker.ghostsubscribeplaylistmanager",
        version=VERSION,
        info_plist={
            "NSAppleScriptEnabled": False,
            "NSPrincipalClass": "NSApplication",
        },
    )
