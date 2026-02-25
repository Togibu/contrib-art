from __future__ import annotations

import argparse
import cmd
import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml


ROOT = Path.cwd()

DEFAULT_CONFIG: dict[str, Any] = {
    "repository": {"path": "./repo", "branch": "main"},
    "execution": {"max_commits_per_day": 8},
}

DEFAULT_PATTERNS: dict[str, Any] = {
    "sources": {"default": "https://example.com/pattern-repo"},
    "installed": ["text"],
}

DEFAULT_SCHEDULE: dict[str, Any] = {"pattern": None, "schedule": {}}

TEXT_PATTERN_VERSION = "1.1"

TEXT_PATTERN_MANIFEST = """name: text
version: 1.1
entrypoint: pattern.py
"""

TEXT_PATTERN_CODE = """from __future__ import annotations

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

    print("\\nPreview (7xN, # = filled):")
    for row in grid:
        print("".join("#" if c != " " else "." for c in row))

    print(f"\\nDate range: {start_date.isoformat()} .. {end_date.isoformat()}")
    confirm = input("\\nWrite schedule.yml? [Y/n]: ").strip().lower()
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
"""


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def ensure_scaffold(root: Path) -> None:
    (root / "patterns").mkdir(exist_ok=True)

    config_path = root / "config.yml"
    patterns_path = root / "patterns.yml"
    schedule_path = root / "schedule.yml"

    if not config_path.exists():
        _write_yaml(config_path, DEFAULT_CONFIG)

    if not patterns_path.exists():
        _write_yaml(patterns_path, DEFAULT_PATTERNS)

    if not schedule_path.exists():
        _write_yaml(schedule_path, DEFAULT_SCHEDULE)

    # Example pattern scaffold (text)
    text_dir = root / "patterns" / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = text_dir / "manifest.yml"
    pattern_path = text_dir / "pattern.py"

    current_version = None
    if manifest_path.exists():
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            current_version = str(manifest.get("version") or "")
        except Exception:
            current_version = None

    if (not manifest_path.exists()) or (current_version != TEXT_PATTERN_VERSION):
        manifest_path.write_text(TEXT_PATTERN_MANIFEST, encoding="utf-8")
        pattern_path.write_text(TEXT_PATTERN_CODE, encoding="utf-8")


def _read_patterns_cfg(root: Path) -> dict[str, Any]:
    path = root / "patterns.yml"
    if not path.exists():
        return {"sources": {}, "installed": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {"sources": {}, "installed": []}


def _write_patterns_cfg(root: Path, data: dict[str, Any]) -> None:
    path = root / "patterns.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def list_patterns(root: Path) -> list[str]:
    data = _read_patterns_cfg(root)
    return list(data.get("installed", []))


def _load_manifest(pattern_dir: Path) -> dict[str, Any]:
    manifest_path = pattern_dir / "manifest.yml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not data:
        raise ValueError(f"Invalid manifest: {manifest_path}")
    return data


def _load_pattern_module(pattern_dir: Path, entrypoint: str):
    module_path = pattern_dir / entrypoint
    if not module_path.exists():
        raise FileNotFoundError(f"Missing entrypoint: {module_path}")
    spec = importlib.util.spec_from_file_location("pattern", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load pattern module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def choose_pattern(root: Path, name: str) -> None:
    pattern_dir = root / "patterns" / name
    if not pattern_dir.exists():
        raise FileNotFoundError(f"Pattern not found: {name}")

    manifest = _load_manifest(pattern_dir)
    entrypoint = manifest.get("entrypoint")
    if not entrypoint:
        raise ValueError(f"Missing entrypoint in manifest for {name}")

    module = _load_pattern_module(pattern_dir, entrypoint)
    if not hasattr(module, "run"):
        raise AttributeError(f"Pattern {name} missing run(context) function")

    context = {
        "root": root,
        "config_path": root / "config.yml",
        "patterns_path": root / "patterns.yml",
        "schedule_path": root / "schedule.yml",
        "pattern_dir": pattern_dir,
        "manifest": manifest,
    }

    module.run(context)


def install_pattern(root: Path, name: str) -> None:
    data = _read_patterns_cfg(root)
    installed = set(data.get("installed", []))
    if name in installed:
        print(f"Pattern already installed: {name}")
        return
    pattern_dir = root / "patterns" / name
    if not pattern_dir.exists():
        raise FileNotFoundError(
            f"Pattern directory does not exist: {pattern_dir} (manual install required)"
        )
    installed.add(name)
    data["installed"] = sorted(installed)
    _write_patterns_cfg(root, data)
    print(f"Installed: {name}")


def remove_pattern(root: Path, name: str) -> None:
    data = _read_patterns_cfg(root)
    installed = set(data.get("installed", []))
    if name not in installed:
        print(f"Pattern not installed: {name}")
        return
    installed.remove(name)
    data["installed"] = sorted(installed)
    _write_patterns_cfg(root, data)
    print(f"Removed: {name}")


def update_patterns(root: Path) -> None:
    data = _read_patterns_cfg(root)
    sources = data.get("sources", {})
    if not sources:
        print("No sources configured.")
        return
    print("Pattern update is a stub. Configure sources to enable sync.")


def _read_schedule(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"pattern": None, "schedule": {}}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {"pattern": None, "schedule": {}}


def _write_schedule(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def perform_commits(root: Path, count: int) -> None:
    # Placeholder: integrate real Git operations here.
    print(f"[stub] Would perform {count} commits in repository at {root}")


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool", description="Contribution graph scheduler")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create required folders/files if missing")
    sub.add_parser("run", help="Run scheduled commits for today")

    pat = sub.add_parser("pattern", help="Pattern management")
    pat_sub = pat.add_subparsers(dest="pattern_cmd", required=True)

    pat_sub.add_parser("list", help="List installed patterns")
    choose = pat_sub.add_parser("choose", help="Choose a pattern and run its generator")
    choose.add_argument("name", help="Pattern name")

    install = pat_sub.add_parser("install", help="Install a pattern")
    install.add_argument("name", help="Pattern name")

    remove = pat_sub.add_parser("remove", help="Remove a pattern")
    remove.add_argument("name", help="Pattern name")

    pat_sub.add_parser("update", help="Update installed patterns")

    return parser


def _execute_command(argv: list[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        ensure_scaffold(ROOT)
        print("Initialized.")
        return

    ensure_scaffold(ROOT)

    if args.command == "run":
        run_schedule(ROOT)
        return

    if args.command == "pattern":
        if args.pattern_cmd == "list":
            patterns = list_patterns(ROOT)
            if not patterns:
                print("No patterns installed.")
            else:
                for name in patterns:
                    print(name)
            return

        if args.pattern_cmd == "choose":
            choose_pattern(ROOT, args.name)
            return

        if args.pattern_cmd == "install":
            install_pattern(ROOT, args.name)
            return

        if args.pattern_cmd == "remove":
            remove_pattern(ROOT, args.name)
            return

        if args.pattern_cmd == "update":
            update_patterns(ROOT)
            return


class ToolShell(cmd.Cmd):
    intro = "tool interactive shell. Type 'help' or '?' for commands."
    prompt = "tool> "

    def do_init(self, arg: str) -> None:
        """Initialize required folders/files."""
        _execute_command(["init"])

    def do_run(self, arg: str) -> None:
        """Run scheduled commits for today."""
        _execute_command(["run"])

    def do_pattern(self, arg: str) -> None:
        """Pattern management. Usage: pattern list|choose <name>|install <name>|remove <name>|update"""
        argv = ["pattern"] + [a for a in arg.split() if a]
        if len(argv) == 1:
            print("Usage: pattern list|choose <name>|install <name>|remove <name>|update")
            return
        _execute_command(argv)

    def complete_pattern(self, text: str, line: str, begidx: int, endidx: int):
        options = ["list", "choose", "install", "remove", "update"]
        tokens = line.split()
        if len(tokens) <= 2:
            return [o for o in options if o.startswith(text)]
        if len(tokens) == 3 and tokens[1] in {"choose", "install", "remove"}:
            patterns = list_patterns(ROOT)
            return [p for p in patterns if p.startswith(text)]
        return []

    def do_exit(self, arg: str) -> bool:
        """Exit the shell."""
        print("Bye.")
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the shell."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:
        return self.do_exit(arg)


def main(argv: list[str] | None = None) -> None:
    try:
        if argv is None and len(sys.argv) == 1:
            ToolShell().cmdloop()
            return
        _execute_command(sys.argv[1:] if argv is None else argv)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
