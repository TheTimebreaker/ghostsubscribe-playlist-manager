from __future__ import annotations

lazy import argparse
lazy import logging

lazy from PySide6.QtGui import Qt
lazy from PySide6.QtWidgets import QApplication

lazy from . import youtube
lazy from .__icon__ import ICON
lazy from .config import Config, Theme, config
lazy from .qt_ui import MainWindow


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
    app.setWindowIcon(ICON)

    app.setApplicationName("GhostSubscribe Playlist Manager")
    configure_app_style(app, config)

    try:
        youtube.Youtube()
    except Exception:
        logging.exception("Could not authorize with YouTube.")
        raise

    window = MainWindow(run_directly=args.automaticautoadder)
    window.show()

    app.exec()


if __name__ == "__main__":
    main()
