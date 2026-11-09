from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with cfg_path.open() as f:
        data = yaml.safe_load(f) or {}
    # Resolve relative paths against project root
    paper = data.setdefault("paper", {})
    pos = paper.get("positions_file", "data/positions.json")
    p = Path(pos)
    if not p.is_absolute():
        paper["positions_file"] = str(ROOT / p)
    return data
