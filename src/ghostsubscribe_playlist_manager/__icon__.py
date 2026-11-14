import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def _get_img_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle
        return Path(sys._MEIPASS) / "img"  # type: ignore

    # Running from source
    return Path(__file__).resolve().parents[2] / "img"


ICON_PATH = _get_img_dir() / "icon.png"
ICON = QIcon(str(ICON_PATH))
