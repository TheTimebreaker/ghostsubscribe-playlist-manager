from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from . import youtube
from .qt_ui import AutoAdderDialog, MainWindow


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
    app.setApplicationName("GhostSubscribe Playlist Manager")
    load_dotenv()
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
