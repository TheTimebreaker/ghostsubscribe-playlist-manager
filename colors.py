import json
import os
from dotenv import load_dotenv

def load_colors() -> dict:
    theme = os.getenv('THEME', 'light')
    match theme:
        case 'light':
            colors_path = 'colors/light.json'
        case 'dark':
            colors_path = 'colors/dark.json'
        case _:
            colors_path = 'colors/light.json'
    with open(colors_path, 'r', encoding= 'utf-8') as f:
        return json.load(f)


def main() -> None:
    load_dotenv()
    load_colors()
if __name__ == '__main__':
    main()
