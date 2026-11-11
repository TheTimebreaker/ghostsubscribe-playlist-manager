from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

import wget
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import auto_adder, youtube
from .config import config

LOGGER = logging.getLogger(__name__)
AUTO_ADDER_PATH = Path("auto_adder_config")
VIDEO_FILTERS = (
    ("All videos", "all_videos"),
    ("Full videos only", "full_videos_only"),
    ("Livestreams only", "livestreams_only"),
    ("Shorts only", "shorts_only"),
)


def show_error(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def handle_error(parent: QWidget, title: str) -> None:
    LOGGER.exception("%s", title)
    show_error(parent, title, "The operation failed. See the application log for details.")


class LogBridge(QObject):
    message = Signal(str)


class WindowLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge, level: int = logging.ERROR) -> None:
        super().__init__(level)
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        self.bridge.message.emit(self.format(record))


class LoggedDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_display = QPlainTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumBlockCount(1000)
        self.log_display.hide()
        self.log_bridge = LogBridge(self)
        self.log_bridge.message.connect(self._show_log)
        self.log_handler = WindowLogHandler(self.log_bridge)
        logging.getLogger().addHandler(self.log_handler)
        self.finished.connect(self._detach_log_handler)

    def _show_log(self, message: str) -> None:
        if not self.log_display.isVisible():
            layout = self.layout()
            if layout is None:
                raise RuntimeError("The dialog layout has not been initialized.")
            layout.addWidget(self.log_display)
            self.log_display.show()
        self.log_display.appendPlainText(message)

    def _detach_log_handler(self, _: int = 0) -> None:
        logging.getLogger().removeHandler(self.log_handler)

    @override
    def closeEvent(self, event: Any) -> None:
        self._detach_log_handler()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, run_directly: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("YouTube manager")
        self.setMinimumSize(640, 420)

        utils_menu = self.menuBar().addMenu("Utils")
        utilities: tuple[tuple[str, Callable[[], None]], ...] = (
            ("Add to Playlist", self.add_to_playlist),
            ("Download Channel Icon", self.download_channel_icon),
            ("Remove Playlist entries up to index", self.remove_playlist_entries),
        )
        for label, callback in utilities:
            action = QAction(label, self)
            action.triggered.connect(callback)
            utils_menu.addAction(action)

        about_menu = self.menuBar().addMenu("About")
        about_action = QAction("Show about", self)
        about_action.triggered.connect(self.about)
        about_menu.addAction(about_action)

        self.auto_adders = AutoAdderPanel(self, run_directly=run_directly)
        self.setCentralWidget(self.auto_adders)

    def about(self) -> None:
        QMessageBox.about(self, "About", "Development:\nTheTimebreaker\n\nContributors:\nTheTimebreaker")

    def add_to_playlist(self) -> None:
        AddToPlaylistDialog(self).exec()

    def download_channel_icon(self) -> None:
        DownloadChannelIconDialog(self).exec()

    def remove_playlist_entries(self) -> None:
        RemovePlaylistEntriesDialog(self).exec()

    @override
    def closeEvent(self, event: Any) -> None:
        worker = self.auto_adders.worker
        if worker and worker.isRunning():
            self.auto_adders.close_when_done = True
            self.auto_adders.stop_event.set()
            self.auto_adders.run_all_button.setText("Cancelling...")
            self.auto_adders.run_all_button.setEnabled(False)
            event.ignore()
            return
        self.auto_adders.shutdown()
        super().closeEvent(event)


class AddToPlaylistDialog(LoggedDialog):
    SOURCES = ("Video", "Playlist", "Channel Uploads")

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add to playlist")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Please select your options for adding something to a playlist.", self))

        self.source_group = QButtonGroup(self)
        source_layout = QFormLayout()
        self.source_entries: dict[str, QLineEdit] = {}
        self.source_radios: dict[str, QRadioButton] = {}
        for index, source in enumerate(self.SOURCES):
            radio = QRadioButton(source, self)
            entry = QLineEdit(self)
            radio.toggled.connect(lambda checked, entry=entry: entry.setEnabled(checked))
            self.source_group.addButton(radio, index)
            source_layout.addRow(radio, entry)
            self.source_entries[source] = entry
            self.source_radios[source] = radio
        self.source_radios["Video"].setChecked(True)
        layout.addLayout(source_layout)

        self.filter_combo = QComboBox(self)
        for label, _ in VIDEO_FILTERS:
            self.filter_combo.addItem(label)
        self.filter_combo.hide()
        layout.addWidget(self.filter_combo)
        self.source_radios["Channel Uploads"].toggled.connect(self.filter_combo.setVisible)

        form = QFormLayout()
        self.target_entry = QLineEdit(self)
        form.addRow("Target playlist ID:", self.target_entry)
        layout.addLayout(form)
        self._add_buttons(layout, self.confirm, self.reject)

    def confirm(self) -> None:
        source = self.SOURCES[self.source_group.checkedId()]
        source_id = self.source_entries[source].text().strip()
        target_id = self.target_entry.text().strip()
        if not source_id:
            show_error(self, "Missing source", f"No source {source} ID given.")
            return
        if not target_id:
            show_error(self, "Missing target", "No target playlist ID given.")
            return

        try:
            target = youtube.Playlist(target_id)
            if not target.verify():
                show_error(self, "Invalid playlist", "The entered target playlist ID is invalid.")
                return

            if source == "Video":
                video = youtube.Video(source_id)
                if not video.verify():
                    show_error(self, "Invalid video", "The entered source video ID is invalid.")
                    return
                success = youtube.add_video_to_playlist(video.id, target_playlist=target)
            elif source == "Playlist":
                playlist = youtube.Playlist(source_id)
                if not playlist.verify():
                    show_error(self, "Invalid playlist", "The entered source playlist ID is invalid.")
                    return
                success = youtube.add_playlist_to_playlist(src_playlist=playlist, target_playlist=target)
            else:
                channel = youtube.Channel(source_id)
                if not channel.verify():
                    show_error(self, "Invalid channel", "The entered source channel ID is invalid.")
                    return
                filter_value = VIDEO_FILTERS[self.filter_combo.currentIndex()][1]
                success = youtube.add_channeluploads_to_playlist(
                    src_channel=channel,
                    target_playlist=target,
                    full_videos_only=filter_value == "full_videos_only",
                    livestreams_only=filter_value == "livestreams_only",
                    shorts_only=filter_value == "shorts_only",
                )
        except Exception:
            handle_error(self, "Could not add content to the playlist")
            return

        if success:
            QMessageBox.information(self, "Success", "All videos have been successfully added to your target playlist.")
            self.accept()
        else:
            show_error(self, "Adding failed", "Some videos could not be added to your target playlist.")

    def _add_buttons(self, layout: QVBoxLayout, confirm: Callable[[], None], cancel: Callable[[], None]) -> None:
        buttons = QHBoxLayout()
        ok_button = QPushButton("Confirm", self)
        ok_button.clicked.connect(confirm)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(cancel)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)


class RemovePlaylistEntriesDialog(LoggedDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Remove Playlist entries up to index")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.playlist_entry = QLineEdit(self)
        form.addRow("Playlist ID:", self.playlist_entry)
        self.index = QSpinBox(self)
        self.index.setRange(1, 5000)
        self.index.setValue(1)
        form.addRow("Remove this many videos:", self.index)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        remove_button = QPushButton("Remove", self)
        remove_button.clicked.connect(self.confirm)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(remove_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def confirm(self) -> None:
        playlist_id = self.playlist_entry.text().strip()
        if not playlist_id:
            show_error(self, "Missing playlist", "No source playlist ID given.")
            return
        try:
            playlist = youtube.Playlist(playlist_id)
            if not playlist.verify():
                show_error(self, "Invalid playlist", "The entered playlist ID is invalid.")
                return
            success = True
            removed = 0
            for index, video in enumerate(playlist.yield_elements(["id"])):
                if index >= self.index.value():
                    break
                success = playlist.remove_video(video_playlist_id=video["id"]) and success
                removed += 1
        except Exception:
            handle_error(self, "Could not remove playlist entries")
            return

        if success:
            QMessageBox.information(self, "Success", f"Removed {removed} playlist entr{'y' if removed == 1 else 'ies'}.")
            self.accept()
        else:
            show_error(self, "Removal failed", "Some playlist entries could not be removed.")


class DownloadChannelIconDialog(LoggedDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Download Channel Icon")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.channel_entry = QLineEdit(self)
        form.addRow("Channel ID / URL:", self.channel_entry)
        self.dimensions = QSpinBox(self)
        self.dimensions.setRange(0, 5000)
        self.dimensions.setValue(900)
        form.addRow("Image dimensions (pixels):", self.dimensions)

        location_layout = QHBoxLayout()
        self.location_entry = QLineEdit(self)
        self.location_entry.setReadOnly(True)
        self.location_entry.setPlaceholderText("Select a download folder")
        location_layout.addWidget(self.location_entry)
        browse_button = QPushButton("Select Location", self)
        browse_button.clicked.connect(self.select_location)
        location_layout.addWidget(browse_button)
        form.addRow("Download location:", location_layout)
        layout.addLayout(form)

        self.download_button = QPushButton("Download Image", self)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download)
        self.channel_entry.textChanged.connect(self._update_enabled)
        self.location_entry.textChanged.connect(self._update_enabled)
        layout.addWidget(self.download_button)
        cancel_button = QPushButton("Close", self)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

    def _update_enabled(self) -> None:
        self.download_button.setEnabled(bool(self.channel_entry.text().strip() and self.location_entry.text()))

    def select_location(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select download location")
        if path:
            self.location_entry.setText(path)

    def download(self) -> None:
        try:
            channel = youtube.Channel(self.channel_entry.text().strip())
            if not channel.verify():
                show_error(self, "Invalid channel", "The Channel ID / URL could not be verified.")
                return
            url = channel.get_profile_image(self.dimensions.value())
            destination = os.path.join(self.location_entry.text(), channel.id + ".jpg")
            wget.download(url, destination)
        except Exception:
            handle_error(self, "Could not download the channel icon")
            return
        QMessageBox.information(self, "Success", f"Channel icon saved to:\n{destination}")
        self.accept()


class AutoAdderWorker(QThread):
    progress = Signal(str, int, int)
    completed = Signal(bool, str)

    def __init__(self, paths: list[Path], stop_event: threading.Event) -> None:
        super().__init__()
        self.paths = paths
        self.stop_event = stop_event

    def run(self) -> None:
        try:
            for path in self.paths:
                for message, progress, total in auto_adder.process(str(path), self.stop_event):
                    self.progress.emit(message, progress, total)
        except auto_adder.ThreadStoppedError:
            self.completed.emit(False, "Auto adder was cancelled.")
        except Exception as error:
            LOGGER.exception("Auto adder failed.")
            self.completed.emit(False, str(error))
        else:
            self.completed.emit(not self.stop_event.is_set(), "")


class AutoAdderPanel(QWidget):
    def __init__(self, parent: QWidget, run_directly: bool = False) -> None:
        super().__init__(parent)
        self.stop_event = threading.Event()
        self.worker: AutoAdderWorker | None = None
        self.run_directly = run_directly
        self.close_when_done = False
        self._last_run_success = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.adders_scroll = QScrollArea(self)
        self.adders_scroll.setWidgetResizable(True)
        self.adders_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.adders_content = QWidget(self.adders_scroll)
        self.adders_layout = QVBoxLayout(self.adders_content)
        self.adders_layout.setContentsMargins(4, 4, 4, 4)
        self.adders_layout.setSpacing(6)
        self.adders_layout.addStretch()
        self.adders_scroll.setWidget(self.adders_content)
        layout.addWidget(self.adders_scroll, 1)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)
        self.progress_area = QWidget(self)
        progress_layout = QVBoxLayout(self.progress_area)
        progress_layout.setContentsMargins(4, 2, 4, 2)
        progress_layout.setSpacing(4)
        self.progress_status = QWidget(self.progress_area)
        status_layout = QVBoxLayout(self.progress_status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        self.progress_label = QLabel("", self.progress_area)
        self.progress_label.setWordWrap(True)
        self.progress = QProgressBar(self.progress_area)
        self.progress.setTextVisible(False)
        status_layout.addWidget(self.progress_label)
        status_layout.addWidget(self.progress)
        progress_layout.addWidget(self.progress_status)
        self.progress_status.hide()
        self.exit_after_run_checkbox = QCheckBox("Exit after successful run", self.progress_area)
        self.exit_after_run_checkbox.setChecked(run_directly)
        progress_layout.addWidget(self.exit_after_run_checkbox)
        layout.addWidget(self.progress_area)
        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        self.adder_buttons: list[QPushButton] = []
        self.config_buttons: list[QPushButton] = []
        self.adder_rows: list[QWidget] = []
        self.adder_paths: list[Path] = []

        controls = QHBoxLayout()
        add_button = QPushButton("Add new", self)
        add_button.clicked.connect(self.create_auto_adder)
        controls.addWidget(add_button)
        controls.addStretch()
        self.run_all_button = QPushButton("Run All", self)
        self.run_all_button.clicked.connect(self._run_all_or_cancel)
        controls.addWidget(self.run_all_button)
        layout.addLayout(controls)

        self.log_display = QPlainTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumBlockCount(1000)
        self.log_display.hide()
        self.log_bridge = LogBridge(self)
        self.log_bridge.message.connect(self._show_log)
        self.log_handler = WindowLogHandler(self.log_bridge)
        logging.getLogger().addHandler(self.log_handler)

        self._reload()

        if run_directly:
            self.run_all_button.setEnabled(bool(self.adder_paths))
            QTimer.singleShot(0, self._start_direct_run)

    def create_auto_adder(self) -> None:
        dialog = CreateAutoAdderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def configure_auto_adder(self, path: Path) -> None:
        if ConfigureAutoAdderDialog(path, self).exec() == QDialog.DialogCode.Accepted:
            self._reload()

    def _show_log(self, message: str) -> None:
        if not self.log_display.isVisible():
            layout = self.layout()
            if layout is None:
                raise RuntimeError("The auto-adder layout has not been initialized.")
            layout.addWidget(self.log_display)
            self.log_display.show()
        self.log_display.appendPlainText(message)

    def _reload(self) -> None:
        for row in self.adder_rows:
            self.adders_layout.removeWidget(row)
            row.deleteLater()
        self.adder_buttons.clear()
        self.config_buttons.clear()
        self.adder_rows.clear()
        self.adder_paths.clear()
        try:
            paths = sorted(path for path in AUTO_ADDER_PATH.iterdir() if path.is_file() and path.name != "template.json")
            for path in paths:
                settings = auto_adder.read_settings(str(path))
                row = QWidget(self.adders_content)
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(8, 4, 8, 4)
                name = QLabel(settings.global_settings.name, row)
                row_layout.addWidget(name, 1)
                config_button = QPushButton("Config", row)
                config_button.clicked.connect(lambda _checked=False, item=path: self.configure_auto_adder(item))
                row_layout.addWidget(config_button)
                button = QPushButton("Run", row)
                button.clicked.connect(lambda _checked=False, item=path: self.run_paths([item]))
                row_layout.addWidget(button)
                self.adder_buttons.append(button)
                self.config_buttons.append(config_button)
                self.adder_rows.append(row)
                self.adder_paths.append(path)
                self.adders_layout.insertWidget(self.adders_layout.count() - 1, row)
        except Exception:
            handle_error(self, "Could not load auto-adder configurations")

    def _start_direct_run(self) -> None:
        if not self.adder_paths:
            QMessageBox.information(self, "No auto adders", "There are no auto adders to run.")
            return
        self.run_paths(self.adder_paths)

    def _run_all_or_cancel(self) -> None:
        if self.worker and self.worker.isRunning():
            self.stop_event.set()
            self.run_all_button.setText("Cancelling...")
            self.run_all_button.setEnabled(False)
            return
        self.run_paths(self.adder_paths)

    def run_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.stop_event = threading.Event()
        self._set_running(True)
        self.worker = AutoAdderWorker(paths, self.stop_event)
        self.worker.progress.connect(self._update_progress)
        self.worker.completed.connect(self._complete)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _set_running(self, running: bool) -> None:
        for button in self.adder_buttons:
            button.setEnabled(not running)
        for button in self.config_buttons:
            button.setEnabled(not running)
        self.run_all_button.setEnabled(True)
        self.run_all_button.setText("Cancel" if running else "Run All")
        self.progress_status.setVisible(running)

    def _update_progress(self, message: str, current: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(min(current + 1, max(total, 1)))
        msg = f"{current + 1} / {total} - {message.replace(chr(10), ' ')}"
        self.progress_label.setText(msg)
        print(msg)

    def _complete(self, success: bool, error: str) -> None:
        self._set_running(False)
        self._last_run_success = success
        if error and error != "Auto adder was cancelled." and not self.close_when_done:
            show_error(self, "Auto adder failed", error)
        self.progress_label.setText(error or "Finished.")

    def _worker_finished(self) -> None:
        if self._last_run_success and self.exit_after_run_checkbox.isChecked():
            self.window().close()
        elif self._last_run_success and not self.close_when_done:
            QMessageBox.information(self, "Success", "Auto adder finished successfully.")
        if self.close_when_done:
            self.close_when_done = False
            self.window().close()

    @override
    def closeEvent(self, event: Any) -> None:
        if self.worker and self.worker.isRunning():
            self.stop_event.set()
            self.run_all_button.setText("Cancelling...")
            self.run_all_button.setEnabled(False)
            event.ignore()
            return
        logging.getLogger().removeHandler(self.log_handler)
        event.accept()

    def shutdown(self) -> None:
        logging.getLogger().removeHandler(self.log_handler)


class CreateAutoAdderDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Auto Adder")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.filename = QLineEdit(self)
        form.addRow("Filename:", self.filename)
        self.display_name = QLineEdit(self)
        form.addRow("Display name:", self.display_name)
        self.target_playlist = QLineEdit(self)
        form.addRow("Target playlist:", self.target_playlist)
        self.selector = QComboBox(self)
        for label, value in VIDEO_FILTERS:
            self.selector.addItem(label, value)
        form.addRow("Video filter:", self.selector)
        layout.addLayout(form)
        self._add_buttons(layout, self.create_adder)

    def create_adder(self) -> None:
        filename = self.filename.text().strip()
        name = self.display_name.text().strip()
        target_id = self.target_playlist.text().strip()
        if not filename or not name or not target_id:
            show_error(self, "Missing fields", "Please fill in the filename, display name, and target playlist.")
            return
        if Path(filename).name != filename or filename in {".", ".."}:
            show_error(self, "Invalid filename", "Enter a filename without folder paths.")
            return
        filename = filename.removesuffix(".json") + ".json"
        path = AUTO_ADDER_PATH / filename
        if path.exists():
            show_error(self, "Filename exists", "Choose a filename that does not already exist.")
            return
        try:
            playlist = youtube.Playlist(target_id)
            if not playlist.verify():
                show_error(self, "Invalid playlist", "The target playlist entered is invalid.")
                return
            auto_adder.create(filename, name, playlist.id, self.selector.currentData())
        except Exception:
            handle_error(self, "Could not create auto adder")
            return
        QMessageBox.information(self, "Success", "New auto adder successfully created.")
        self.accept()

    def _add_buttons(self, layout: QVBoxLayout, action: Callable[[], None]) -> None:
        buttons = QHBoxLayout()
        confirm = QPushButton("Create", self)
        confirm.clicked.connect(action)
        cancel = QPushButton("Cancel", self)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(confirm)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)


class ConfigureAutoAdderDialog(QDialog):
    def __init__(self, filepath: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.setMinimumWidth(600)
        self.filepath = filepath
        self.old_config = auto_adder.read_settings(str(filepath))
        self.new_config = self.old_config.model_copy(deep=True)
        self.setWindowTitle(f"Configure: {self.old_config.global_settings.name}")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b><u>General config</u></b>", self))
        form = QFormLayout()
        self.name = QLineEdit(self.old_config.global_settings.name, self)
        form.addRow("Display name:", self.name)
        self.target = QLineEdit(self.old_config.global_settings.target_playlist_id, self)
        form.addRow("Target playlist:", self.target)
        self.selector = QComboBox(self)
        for label, value in VIDEO_FILTERS:
            self.selector.addItem(label, value)
        self.selector.setCurrentIndex(self.selector.findData(self.old_config.global_settings.selector))
        form.addRow("Video filter:", self.selector)
        layout.addLayout(form)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        layout.addWidget(QLabel("<b><u>Add channel</u></b>", self))
        channel_form = QFormLayout()
        self.channel_id = QLineEdit(self)
        channel_form.addRow("Channel ID / URL:", self.channel_id)
        self.channel_name = QLineEdit(self)
        channel_form.addRow("Channel name:", self.channel_name)
        self.channel_filter = QComboBox(self)
        for label, value in VIDEO_FILTERS:
            self.channel_filter.addItem(label, value)
        channel_form.addRow("Video filter:", self.channel_filter)
        layout.addLayout(channel_form)

        self.video_mode = QComboBox(self)
        self.video_mode.addItem("Add new videos", "new")
        self.video_mode.addItem("Add all videos", "all")
        channel_form.addRow("Videos to add:", self.video_mode)

        add_channel = QPushButton("Add channel", self)
        add_channel.clicked.connect(self.add_channel_to_config)
        layout.addWidget(add_channel)
        layout.addWidget(divider)

        buttons = QHBoxLayout()
        save_back = QPushButton("Save", self)
        save_back.clicked.connect(self.save)
        buttons.addWidget(save_back)
        layout.addLayout(buttons)

    def add_channel_to_config(self) -> None:
        channel_id = self.channel_id.text().strip()
        channel_name = self.channel_name.text().strip()
        if not channel_id or not channel_name:
            show_error(self, "Missing fields", "Enter both a channel ID/URL and a channel name.")
            return
        try:
            channel = youtube.Channel(channel_id)
            if not channel.verify():
                show_error(self, "Invalid channel", "The channel ID / URL could not be verified.")
                return
            if channel.id in self.new_config.channels:
                show_error(self, "Channel exists", "This channel is already in the auto-adder.")
                return
            selector = self.channel_filter.currentData()
            seen_ids = (
                list(
                    channel.list_uploads(
                        size=config.kept_video_ids,
                        full_videos_only=selector == "full_videos_only",
                        livestreams_only=selector == "livestreams_only",
                        shorts_only=selector == "shorts_only",
                    )
                )
                if self.video_mode.currentData() == "new"
                else []
            )
            self.new_config.channels[channel.id] = auto_adder.SettingsChannels(
                channel_name=channel_name,
                seen_video_ids=seen_ids,
                settings=auto_adder.PerChannelSettings(selector=selector),
            )
        except Exception:
            handle_error(self, "Could not add channel")
            return
        self.channel_id.clear()
        self.channel_name.clear()
        QMessageBox.information(self, "Channel added", "The channel will be saved with the auto-adder configuration.")

    def _save(self) -> bool:
        name = self.name.text().strip()
        target_id = self.target.text().strip()
        if not name or not target_id:
            show_error(self, "Missing fields", "Display name and target playlist are required.")
            return False
        try:
            target = youtube.Playlist(target_id)
            if not target.verify():
                show_error(self, "Invalid playlist", "The target playlist could not be verified.")
                return False
            self.new_config.global_settings.name = name
            self.new_config.global_settings.target_playlist_id = target.id
            self.new_config.global_settings.selector = self.selector.currentData()
            auto_adder.write_settings(str(self.filepath), self.new_config)
        except Exception:
            handle_error(self, "Could not save auto-adder configuration")
            return False
        return True

    def save(self) -> None:
        if self._save():
            self.accept()
