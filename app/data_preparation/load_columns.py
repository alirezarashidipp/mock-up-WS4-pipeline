from pathlib import Path

import yaml

from app.models import ColumnDefinition


def load_columns(path: Path) -> list[dict[str, str]]:
    settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ColumnDefinition.model_validate(field).model_dump() for field in settings["columns"]]
