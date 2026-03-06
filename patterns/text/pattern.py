from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml


def _write_schedule(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run(context: dict[str, Any]) -> None:
    print("Text pattern generator")
    text = input("Text (A-Z, 0-9, space): ").strip().upper()
    start = input("Start date for first column (Sunday) [YYYY-MM-DD, blank=next Sunday]: ").strip()
    commits_per_fill = int(input("Commits per filled cell: ").strip())

    font = {
        "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
        "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
        "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
        "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
        "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
        "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
        "G": [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
        "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
        "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
        "J": ["#####", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
        "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
        "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
        "M": ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
        "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
        "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
        "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
        "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
        "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
        "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
        "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
        "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
        "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
        "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
        "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
        "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
        "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
        "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
        "1": ["  #  ", " ##  ", "# #  ", "  #  ", "  #  ", "  #  ", "#####"],
        "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
        "3": ["#####", "    #", "   # ", "  ## ", "    #", "#   #", " ### "],
        "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
        "5": ["#####", "#    ", "#    ", "#### ", "    #", "#   #", " ### "],
        "6": [" ### ", "#   #", "#    ", "#### ", "#   #", "#   #", " ### "],
        "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
        "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
        "9": [" ### ", "#   #", "#   #", " ####", "    #", "#   #", " ### "],
        " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
    }

    def build_grid(text_value: str) -> list[str]:
        rows = [""] * 7
        for ch in text_value:
            glyph = font.get(ch, font[" "])
            for i in range(7):
                rows[i] += glyph[i] + " "
        return [r.rstrip() for r in rows]

    grid = build_grid(text)

    if start:
        start_date = date.fromisoformat(start)
    else:
        today = date.today()
        days_until_sun = (6 - today.weekday()) % 7
        start_date = today + timedelta(days=days_until_sun)

    end_date = start_date + timedelta(days=(len(grid[0]) * 7 - 1))

    print("\nPreview (7xN, # = filled):")
    for row in grid:
        print("".join("#" if c != " " else "." for c in row))

    print(f"\nDate range: {start_date.isoformat()} .. {end_date.isoformat()}")
    confirm = input("\nWrite schedule.yml? [Y/n]: ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("Aborted.")
        return

    schedule: dict[str, int] = {}
    for col in range(len(grid[0])):
        for row in range(7):
            if col >= len(grid[row]):
                continue
            if grid[row][col] != " ":
                day = start_date + timedelta(days=(col * 7 + row))
                schedule[day.isoformat()] = commits_per_fill

    data = {"pattern": "text", "schedule": schedule}
    _write_schedule(context["schedule_path"], data)
    print(f"Wrote schedule with {len(schedule)} days.")
