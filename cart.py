from __future__ import annotations

import argparse
import cmd
import getpass
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml


ROOT = Path.cwd()
PATTERNS_REPO_URL = "https://github.com/Togibu/contrib-art-patterns.git"
TOOL_REPO_URL = "https://github.com/Togibu/contrib-art.git"
CREDENTIALS_FILE = Path.home() / ".config" / "cart" / "credentials.yml"

DEFAULT_CONFIG: dict[str, Any] = {
    "repository": {"path": "./repo", "branch": "main"},
    "execution": {"max_commits_per_day": 8},
}

DEFAULT_PATTERNS: dict[str, Any] = {
    "sources": {"default": "https://example.com/pattern-repo"},
    "installed": [],
}

DEFAULT_SCHEDULE: dict[str, Any] = {"pattern": None, "schedule": {}}


def _read_credentials() -> dict[str, str]:
    if not CREDENTIALS_FILE.exists():
        return {}
    data = yaml.safe_load(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    return data or {}


def _write_credentials(data: dict[str, str]) -> None:
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    CREDENTIALS_FILE.chmod(0o600)


def login() -> None:
    creds = _read_credentials()
    if creds.get("username"):
        print(f"Already logged in as: {creds['username']}")
        answer = input("Log in with a different account? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            return

    username = input("GitHub username: ").strip()
    if not username:
        print("Aborted.")
        return

    token = getpass.getpass("Personal Access Token (hidden): ").strip()
    if not token:
        print("Aborted.")
        return

    _write_credentials({"username": username, "token": token})
    print(f"Logged in as: {username}")


def logout() -> None:
    if not CREDENTIALS_FILE.exists():
        print("Not logged in.")
        return
    creds = _read_credentials()
    CREDENTIALS_FILE.unlink()
    print(f"Logged out. (was: {creds.get('username', '?')})")


def update_tool() -> None:
    print("Checking for tool updates...")
    result = subprocess.run(
        ["git", "ls-remote", TOOL_REPO_URL, "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Could not reach GitHub. Are you connected to the internet?")
        return

    remote_sha = result.stdout.split()[0] if result.stdout.strip() else ""
    if not remote_sha:
        print("Could not determine remote hash.")
        return

    version_file = Path(__file__).parent / ".cart_version"
    local_sha = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else ""

    if local_sha and remote_sha == local_sha:
        print("Tool is up to date.")
        return

    if local_sha:
        print(f"Update available!\n  Local:  {local_sha[:12]}\n  Remote: {remote_sha[:12]}")
    else:
        print(f"Update available! Remote: {remote_sha[:12]}")

    answer = input("Update now? [Y/n]: ").strip().lower()
    if answer not in ("", "y", "yes"):
        print("Aborted.")
        return

    print("Downloading cart.py...")
    dl = subprocess.run(
        [
            "curl", "-fsSL",
            f"https://raw.githubusercontent.com/Togibu/contrib-art/{remote_sha}/cart.py",
            "-o", str(Path(__file__)),
        ],
        capture_output=True,
        text=True,
    )
    if dl.returncode != 0:
        print("Download failed. Are you connected to the internet?")
        return

    version_file.write_text(remote_sha, encoding="utf-8")
    print("cart.py updated. Please restart the tool.")


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def ensure_scaffold(root: Path, pull: bool | None = None) -> None:
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

    if pull is None:
        answer = input("Pull patterns from contrib-art-patterns? [Y/n]: ").strip().lower()
        pull = answer in ("", "y", "yes")

    if pull:
        pull_patterns(root)


def pull_patterns(root: Path) -> None:
    print(f"Cloning {PATTERNS_REPO_URL}...")
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", PATTERNS_REPO_URL, tmp],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("Clone failed. Are you connected to the internet?")
            return

        patterns_dir = root / "patterns"
        patterns_dir.mkdir(exist_ok=True)

        sha_result = subprocess.run(
            ["git", "-C", tmp, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        current_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""

        pulled: list[str] = []
        for src in sorted(Path(tmp).iterdir()):
            if not src.is_dir() or src.name.startswith("."):
                continue
            dest = patterns_dir / src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            pulled.append(src.name)

    if not pulled:
        print("No patterns found in repo.")
        return

    data = _read_patterns_cfg(root)
    installed = set(data.get("installed", []))
    installed.update(pulled)
    data["installed"] = sorted(installed)
    if current_sha:
        data["last_pull_sha"] = current_sha
    _write_patterns_cfg(root, data)
    print(f"Patterns pulled: {', '.join(pulled)}")


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
    local_sha = data.get("last_pull_sha", "")

    print("Checking for pattern updates...")
    result = subprocess.run(
        ["git", "ls-remote", PATTERNS_REPO_URL, "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Could not reach GitHub. Are you connected to the internet?")
        return

    remote_sha = result.stdout.split()[0] if result.stdout.strip() else ""

    if not remote_sha:
        print("Could not determine remote hash.")
        return

    if not local_sha:
        print("No local state saved. Run 'pattern pull' first.")
        return

    if remote_sha == local_sha:
        print("Patterns are up to date.")
        return

    print(f"Update available!\n  Local:  {local_sha[:12]}\n  Remote: {remote_sha[:12]}")
    answer = input("Pull now? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        pull_patterns(root)


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
    parser = argparse.ArgumentParser(prog="cart", description="Contribution graph art scheduler")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create required folders/files if missing")
    sub.add_parser("run", help="Run scheduled commits for today")
    sub.add_parser("update", help="Update cart.py from the remote repo")
    sub.add_parser("login", help="Save GitHub credentials for pushing commits")
    sub.add_parser("logout", help="Remove saved GitHub credentials")

    pat = sub.add_parser("pattern", help="Pattern management")
    pat_sub = pat.add_subparsers(dest="pattern_cmd", required=True)

    pat_sub.add_parser("list", help="List installed patterns")
    pat_sub.add_parser("pull", help="Pull patterns from contrib-art-patterns repo")
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

    if args.command == "update":
        update_tool()
        return

    if args.command == "login":
        login()
        return

    if args.command == "logout":
        logout()
        return

    ensure_scaffold(ROOT, pull=False)

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

        if args.pattern_cmd == "pull":
            pull_patterns(ROOT)
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


class CartShell(cmd.Cmd):
    intro = "cart interactive shell. Type 'help' or '?' for commands."
    prompt = "cart> "

    def do_init(self, arg: str) -> None:
        """Initialize required folders/files."""
        _execute_command(["init"])

    def do_update(self, arg: str) -> None:
        """Update cart.py from the remote repo."""
        update_tool()

    def do_login(self, arg: str) -> None:
        """Save GitHub credentials for pushing commits."""
        login()

    def do_logout(self, arg: str) -> None:
        """Remove saved GitHub credentials."""
        logout()

    def do_run(self, arg: str) -> None:
        """Run scheduled commits for today."""
        _execute_command(["run"])

    def do_pattern(self, arg: str) -> None:
        """Pattern management. Usage: pattern list|pull|choose <name>|install <name>|remove <name>|update"""
        argv = ["pattern"] + [a for a in arg.split() if a]
        if len(argv) == 1:
            print("Usage: pattern list|pull|choose <name>|install <name>|remove <name>|update")
            return
        _execute_command(argv)

    def complete_pattern(self, text: str, line: str, begidx: int, endidx: int):
        options = ["list", "pull", "choose", "install", "remove", "update"]
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
            CartShell().cmdloop()
            return
        _execute_command(sys.argv[1:] if argv is None else argv)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
