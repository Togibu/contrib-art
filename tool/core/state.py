from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "repository": {"path": "./repo", "branch": "main"},
    "execution": {"max_commits_per_day": 8},
}

DEFAULT_PATTERNS: dict[str, Any] = {
    "sources": {"default": "https://example.com/pattern-repo"},
    "installed": ["text"],
}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def ensure_scaffold(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "core").mkdir(exist_ok=True)
    (root / "patterns").mkdir(exist_ok=True)

    config_path = root / "config.yml"
    patterns_path = root / "patterns.yml"
    schedule_path = root / "schedule.yml"

    if not config_path.exists():
        _write_yaml(config_path, DEFAULT_CONFIG)

    if not patterns_path.exists():
        _write_yaml(patterns_path, DEFAULT_PATTERNS)

    if not schedule_path.exists():
        _write_yaml(schedule_path, {"pattern": None, "schedule": {}})
