lazy import shutil
lazy import sys
lazy from enum import StrEnum

lazy import platformdirs
lazy from pydantic import BaseModel, Field
lazy from PySide6.QtCore import Qt
lazy from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

lazy from .__icon__ import ICON

_pl = platformdirs.PlatformDirs("GhostSubscribe Playlist Manager", "TheTimebreaker")

CONFIG_PATH = _pl.user_config_path / "config.json"
CREDENTIALS_PATH = _pl.user_config_path / "credentials.json"
AUTO_ADDER_PATH = _pl.user_config_path / "auto-adder-config"
TOKEN_PATH = _pl.user_state_path / "token.json"

CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)


class Theme(StrEnum):
    """This enum lets you define a theme for the application."""

    SYSTEM = "Automatic"
    LIGHT = "Light Mode"
    DARK = "Dark Mode"


class Config(BaseModel):
    theme: Theme = Field(
        Theme.SYSTEM,
        title="Theme",
        description="Sets the theme of the GUI.",
    )

    kept_video_ids: int = Field(
        500,
        title="Kept Video IDs",
        description=(
            "Choose, how many video IDs per channel will be kept for future references. Larger numbers slightly increase load times, "
            "while small numbers can cause issues when some videos are deleted."
        ),
    )


config: Config
if CONFIG_PATH.is_file():
    config = Config.model_validate_json(CONFIG_PATH.read_text())
else:
    config = Config.model_construct()

if not CREDENTIALS_PATH.is_file():
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        raise Exception
    app.setWindowIcon(ICON)

    prompt = QMessageBox()
    prompt.setIcon(QMessageBox.Icon.Warning)
    prompt.setWindowTitle("Credentials file missing")
    prompt.setText(
        "The credentials file is missing. See the "
        '<a href="https://github.com/TheTimebreaker/GhostSubscribe-Playlist-Manager#Get-started">'
        "Get started</a> chapter on GitHub for instructions, or select an existing credentials.json file."
    )
    prompt.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    choose_button = prompt.addButton("Choose credentials.json…", QMessageBox.ButtonRole.AcceptRole)
    prompt.addButton("Exit", QMessageBox.ButtonRole.RejectRole)
    prompt.exec()

    if prompt.clickedButton() is choose_button:
        selected_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select credentials.json",
            str(CREDENTIALS_PATH.parent),
            "JSON files (*.json)",
        )
        if selected_path:
            try:
                shutil.move(selected_path, CREDENTIALS_PATH)
            except OSError as exc:
                QMessageBox.critical(None, "Could not move credentials file", str(exc))
                app.quit()
                raise SystemExit(1) from exc
        else:
            app.quit()
            raise SystemExit(1)
    else:
        app.quit()
        raise SystemExit(1)
