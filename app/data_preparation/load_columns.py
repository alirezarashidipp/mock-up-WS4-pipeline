from pathlib import Path

import yaml

def load_columns(path: Path) -> list[dict[str, str]]:
    settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    return settings["columns"]
