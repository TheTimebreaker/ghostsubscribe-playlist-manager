from __future__ import annotations

import argparse
import logging

from PySide6.QtGui import Qt
from PySide6.QtWidgets import QApplication

from . import youtube
from .config import Config, Theme, config
from .qt_ui import AutoAdderDialog, MainWindow


def configure_app_style(app: QApplication, settings: Config) -> None:
    theme = settings.theme
    hints = app.styleHints()
    if theme == Theme.LIGHT:
        hints.setColorScheme(Qt.ColorScheme.Light)
    elif theme == Theme.DARK:
        hints.setColorScheme(Qt.ColorScheme.Dark)
    elif theme == Theme.SYSTEM:
        hints.unsetColorScheme()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-aaa",
        "--automaticautoadder",
        action="store_true",
        help="Runs all auto adders immediately and exits automatically if no errors were detected.",
    )
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise Exception

    app.setApplicationName("GhostSubscribe Playlist Manager")
    configure_app_style(app, config)

    try:
        youtube.Youtube()
    except Exception:
        logging.exception("Could not authorize with YouTube.")
        raise

    window = MainWindow()
    window.show()
    if args.automaticautoadder:
        window.hide()
        dialog = AutoAdderDialog(window, run_directly=True)
        dialog.finished.connect(lambda _: app.quit())
        dialog.open()

    app.exec()


if __name__ == "__main__":
    main()
