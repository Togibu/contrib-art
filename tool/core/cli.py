from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.pattern_loader import (
    list_patterns,
    choose_pattern,
    install_pattern,
    remove_pattern,
    update_patterns,
)
from core.scheduler import run_schedule
from core.state import ensure_scaffold


ROOT = Path.cwd() / "tool"


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


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
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

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
