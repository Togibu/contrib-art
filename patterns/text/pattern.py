from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml


def _write_schedule(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run(context: dict[str, Any]) -> None:
    print("Text pattern generator")
    start = input("Start date (YYYY-MM-DD): ").strip()
    days = int(input("Number of days: ").strip())
    commits_per_day = int(input("Commits per day: ").strip())

    start_date = date.fromisoformat(start)
    schedule: dict[str, int] = {}
    for i in range(days):
        day = start_date + timedelta(days=i)
        schedule[day.isoformat()] = commits_per_day

    data = {"pattern": "text", "schedule": schedule}
    _write_schedule(context["schedule_path"], data)
    print(f"Wrote schedule with {len(schedule)} days.")
