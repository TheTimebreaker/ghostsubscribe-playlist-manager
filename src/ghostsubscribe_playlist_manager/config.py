from enum import StrEnum

import platformdirs
from pydantic import BaseModel, Field

_pl = platformdirs.PlatformDirs("GhostSubscribe Playlist Manager", "TheTimebreaker")

CONFIG_PATH = _pl.user_config_path / "config.json"
CREDENTIALS_PATH = _pl.user_config_path / "credentials.json"
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
