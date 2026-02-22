from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from core.git_ops import perform_commits


def _read_schedule(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"pattern": None, "schedule": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {"pattern": None, "schedule": {}}


def _write_schedule(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run_schedule(root: Path) -> None:
    schedule_path = root / "schedule.yml"
    data = _read_schedule(schedule_path)

    today = date.today().isoformat()
    schedule = data.get("schedule", {})
    if today not in schedule:
        print("No scheduled commits for today.")
        return

    count = schedule.get(today, 0)
    if not isinstance(count, int) or count <= 0:
        print("Invalid commit count for today.")
        schedule.pop(today, None)
        _write_schedule(schedule_path, data)
        return

    perform_commits(root, count)

    schedule.pop(today, None)
    data["schedule"] = schedule
    _write_schedule(schedule_path, data)
    print(f"Executed {count} commits for {today}.")
