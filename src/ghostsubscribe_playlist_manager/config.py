from typing import Literal

import platformdirs
from pydantic import BaseModel, Field

_pl = platformdirs.PlatformDirs("GhostSubscribe Playlist Manager", "TheTimebreaker")

CONFIG_PATH = _pl.user_config_path / "config.json"
CREDENTIALS_PATH = _pl.user_config_path / "credentials.json"
TOKEN_PATH = _pl.user_state_path / "token.json"

CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)


class Config(BaseModel):
    theme: Literal["dark", "light", "auto"] = Field(
        "dark",
        title="Theme",
        description="Sets the theme of the GUI to light, dark or auto (based on your OS' settings)",
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
