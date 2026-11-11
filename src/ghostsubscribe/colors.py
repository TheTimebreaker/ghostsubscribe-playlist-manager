import json
import os


def __load_colors() -> dict[str, str]:
    theme = os.getenv("THEME", "light")
    match theme:
        case "light":
            colors_path = "colors/light.json"
        case "dark":
            colors_path = "colors/dark.json"
        case _:
            colors_path = "colors/light.json"
    with open(colors_path, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)
        return data


colors = __load_colors()
