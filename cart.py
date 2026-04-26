from __future__ import annotations

import argparse
import cmd
import getpass
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
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


def _create_github_repo(username: str, token: str, repo_name: str, private: bool) -> str | None:
    payload = json.dumps({"name": repo_name, "private": private, "auto_init": True})
    result = subprocess.run(
        [
            "curl", "-fsSL",
            "-X", "POST",
            "-H", f"Authorization: token {token}",
            "-H", "Accept: application/vnd.github+json",
            "-H", "Content-Type: application/json",
            "-d", payload,
            "https://api.github.com/user/repos",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Failed to create repo. Are you connected to the internet?")
        return None
    try:
        data = json.loads(result.stdout)
        if "clone_url" not in data:
            print(f"Failed to create repo: {data.get('message', 'unknown error')}")
            return None
        return data["clone_url"]
    except Exception as e:
        print(f"Failed to create repo: {e}")
        return None


def login() -> None:
    creds = _read_credentials()
    if creds.get("username"):
        print(f"Already logged in as: {creds['username']}")
        answer = input("Log in with a different account? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            return

    print(
        "To get a Personal Access Token:\n"
        "  1. Go to github.com → your profile icon → Settings\n"
        "  2. Scroll down → Developer settings → Personal access tokens → Tokens (classic)\n"
        "  3. Click 'Generate new token (classic)'\n"
        "  4. Enable the 'repo' scope\n"
        "  5. Copy the token — it is only shown once\n"
    )
    token = getpass.getpass("Personal Access Token (hidden): ").strip()
    if not token:
        print("Aborted.")
        return

    print("Verifying token...")
    verify = subprocess.run(
        [
            "curl", "-fsSL",
            "-H", f"Authorization: token {token}",
            "-H", "Accept: application/vnd.github+json",
            "https://api.github.com/user",
        ],
        capture_output=True,
        text=True,
    )
    if verify.returncode != 0:
        print("Could not reach GitHub. Are you connected to the internet?")
        return
    try:
        user_data = json.loads(verify.stdout)
        username = user_data.get("login", "")
        if not username:
            print("Invalid token. Please check your Personal Access Token.")
            return
        print(f"Token verified. Hello, {username}!")
    except Exception:
        print("Invalid token. Please check your Personal Access Token.")
        return

    print(
        "\nWhich repo should cart push commits to?\n"
        "  [1] Use an existing repo\n"
        "  [2] Create a new repo\n"
    )
    choice = input("Choice [1/2]: ").strip()

    repo_url: str = ""

    if choice == "1":
        repo_name = input("Repo name (just the name, not the full URL): ").strip()
        if not repo_name:
            print("Aborted.")
            return
        repo_url = f"https://github.com/{username}/{repo_name}.git"

    elif choice == "2":
        repo_name = input("New repo name: ").strip()
        if not repo_name:
            print("Aborted.")
            return
        visibility = input("Private repo? [y/N]: ").strip().lower()
        private = visibility in ("y", "yes")
        print(f"Creating repo '{repo_name}'...")
        repo_url = _create_github_repo(username, token, repo_name, private) or ""
        if not repo_url:
            return
        print(f"Repo created: {repo_url}")

    else:
        print("Aborted.")
        return

    _write_credentials({"username": username, "token": token, "repo_url": repo_url})
    print(f"\nLogged in as: {username}")
    print(f"Target repo:  {repo_url}")


def logout() -> None:
    if not CREDENTIALS_FILE.exists():
        print("Not logged in.")
        return
    creds = _read_credentials()
    CREDENTIALS_FILE.unlink()
    print(f"Logged out. (was: {creds.get('username', '?')})")


def update_tool(auto_yes: bool = False) -> None:
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

    if not auto_yes:
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


def pull_patterns(root: Path, auto_yes: bool = False) -> None:
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
    previous_remote = set(data.get("pulled_from_remote", []))
    current_remote = set(pulled)

    # Patterns that were in the remote at the last pull but no longer are
    # (renamed or deleted upstream). Local-only patterns from
    # `cart pattern install` are never in `pulled_from_remote`, so they're left alone.
    stale = previous_remote - current_remote
    removed: list[str] = []
    for name in sorted(stale):
        local_dir = patterns_dir / name
        if not local_dir.exists():
            installed.discard(name)
            continue
        if auto_yes:
            answer = "y"
        else:
            answer = input(
                f"Pattern '{name}' is no longer in the remote (likely renamed "
                "or deleted upstream). Remove local copy? [Y/n]: "
            ).strip().lower()
        if answer in ("", "y", "yes"):
            shutil.rmtree(local_dir)
            installed.discard(name)
            removed.append(name)

    installed.update(pulled)
    data["installed"] = sorted(installed)
    data["pulled_from_remote"] = sorted(current_remote)
    if current_sha:
        data["last_pull_sha"] = current_sha
    _write_patterns_cfg(root, data)

    print(f"Patterns pulled: {', '.join(pulled)}")
    if removed:
        print(f"Patterns removed (gone from remote): {', '.join(removed)}")


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


def update_patterns(root: Path, auto_yes: bool = False) -> None:
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
    if auto_yes:
        pull_patterns(root, auto_yes=True)
        return
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


def _auth_url(repo_url: str, username: str, token: str) -> str:
    return repo_url.replace("https://", f"https://{username}:{token}@")


def _setup_repo(repo_dir: Path, auth_url: str, username: str) -> bool:
    if not (repo_dir / ".git").exists():
        print("Cloning target repo...")
        result = subprocess.run(
            ["git", "clone", auth_url, str(repo_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("Failed to clone target repo. Are you connected to the internet?")
            return False
    else:
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull"],
            capture_output=True,
            text=True,
        )

    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", username],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email",
         f"{username}@users.noreply.github.com"],
        capture_output=True,
    )
    return True


def perform_commits(root: Path, count: int) -> None:
    creds = _read_credentials()
    if not creds.get("token") or not creds.get("repo_url"):
        print("Not logged in. Run 'cart login' first.")
        return

    username = creds["username"]
    token = creds["token"]
    repo_url = creds["repo_url"]
    auth_url = _auth_url(repo_url, username, token)

    repo_dir = Path.home() / ".config" / "cart" / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    if not _setup_repo(repo_dir, auth_url, username):
        return

    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_date = f"{today}T12:00:00"
    commit_env = {**os.environ, "GIT_AUTHOR_DATE": commit_date, "GIT_COMMITTER_DATE": commit_date}

    # Make N backdated commits to data.txt
    data_file = repo_dir / "data.txt"
    for i in range(count):
        with open(data_file, "a", encoding="utf-8") as f:
            f.write(f"{today} {i + 1}/{count}\n")
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", "data.txt"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", f"cart: {today} ({i + 1}/{count})"],
            capture_output=True,
            text=True,
            env=commit_env,
        )

    # Update progress.yml with real upload timestamp
    progress_path = repo_dir / "progress.yml"
    schedule_data = _read_schedule(root / "schedule.yml")
    new_pattern = schedule_data.get("pattern")
    new_meta = schedule_data.get("meta", {})
    new_entry = {"date": today, "uploaded_at": now, "commits": count}

    if not progress_path.exists():
        progress_data: dict[str, Any] = {
            "pattern": new_pattern,
            "meta": new_meta,
            "entries": [new_entry],
        }
    else:
        progress_data = yaml.safe_load(progress_path.read_text(encoding="utf-8")) or {}
        if progress_data.get("pattern") != new_pattern:
            # Pattern changed — archive the previous run and start a fresh header.
            previous = progress_data.get("previous_runs", [])
            previous.append({
                "pattern": progress_data.get("pattern"),
                "meta": progress_data.get("meta", {}),
                "entries": progress_data.get("entries", []),
            })
            print(
                f"Pattern changed: {progress_data.get('pattern')} → {new_pattern}. "
                "Archived previous run in progress.yml."
            )
            progress_data = {
                "pattern": new_pattern,
                "meta": new_meta,
                "entries": [new_entry],
                "previous_runs": previous,
            }
        else:
            entries = progress_data.get("entries", [])
            entries.append(new_entry)
            progress_data["entries"] = entries

    progress_path.write_text(yaml.safe_dump(progress_data, sort_keys=False), encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_dir), "add", "progress.yml"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", f"cart: progress {today} {now}"],
        capture_output=True,
        text=True,
        env=commit_env,
    )

    # Push
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "push", auth_url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Push failed. Are you connected to the internet?")
        return

    print(f"Pushed {count} commits for {today}.")


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


def reset_schedule(root: Path, auto_yes: bool = False) -> None:
    schedule_path = root / "schedule.yml"
    print(
        "This will reset schedule.yml (the active commit plan).\n"
        "Credentials, installed patterns, and the target repo are NOT touched."
    )
    if not auto_yes:
        answer = input("Reset schedule.yml? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
    _write_yaml(schedule_path, DEFAULT_SCHEDULE)
    print("schedule.yml reset.")


CRON_MARKER_RUN = "# cart-auto-run"
CRON_MARKER_UPDATE = "# cart-auto-update"


def _get_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def _write_crontab(content: str) -> bool:
    result = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Failed to write crontab: {result.stderr.strip()}")
        return False
    return True


def _ask_time(label: str, default: str = "08:00") -> tuple[int, int] | None:
    time_str = input(f"{label} (HH:MM) [{default}]: ").strip() or default
    try:
        hh, mm = time_str.split(":")
        hh, mm = int(hh), int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
        return hh, mm
    except ValueError:
        print("Invalid time. Please use HH:MM format (e.g. 08:00).")
        return None


def setup_cron(cron_type: str = "run") -> None:
    cart_path = str(Path(__file__).resolve())
    python = sys.executable

    if cron_type == "run":
        marker = CRON_MARKER_RUN
        existing_crontab = _get_crontab()
        if marker in existing_crontab:
            print("A cart run cron job already exists.")
            answer = input("Replace it? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted.")
                return

        time = _ask_time("Daily run time", "08:00")
        if time is None:
            return
        hh, mm = time

        dir_str = input(f"Working directory (blank = current: {ROOT}): ").strip()
        work_dir = Path(dir_str).resolve() if dir_str else ROOT
        if not work_dir.is_dir():
            print(f"Directory not found: {work_dir}")
            return

        print(
            "\nNote: if you move the working directory, you must run "
            "'cron remove' and 'cron setup' again to update the cron job."
        )

        cron_entry = f"{mm} {hh} * * * cd {work_dir} && {python} {cart_path} run"
        lines = [ln for ln in existing_crontab.splitlines() if marker not in ln]
        lines.append(f"{cron_entry}  {marker}")
        if not _write_crontab("\n".join(lines) + "\n"):
            return
        print(f"Run cron job set: daily at {hh:02d}:{mm:02d}")
        print(f"  {cron_entry}")

    elif cron_type == "update":
        marker = CRON_MARKER_UPDATE
        existing_crontab = _get_crontab()
        if marker in existing_crontab:
            print("A cart update cron job already exists.")
            answer = input("Replace it? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted.")
                return

        time = _ask_time("Daily update time", "06:00")
        if time is None:
            return
        hh, mm = time

        print("\nWhat should the cron job update?")
        print("  [1] Tool only (cart.py)")
        print("  [2] Patterns only")
        print("  [3] Both")
        choice = input("Choice [1/2/3]: ").strip()
        if choice == "1":
            cmd_parts = [f"{python} {cart_path} update -y"]
        elif choice == "2":
            cmd_parts = [f"{python} {cart_path} pattern update -y"]
        elif choice == "3":
            cmd_parts = [
                f"{python} {cart_path} update -y",
                f"{python} {cart_path} pattern update -y",
            ]
        else:
            print("Aborted.")
            return

        dir_str = input(f"Working directory (blank = current: {ROOT}): ").strip()
        work_dir = Path(dir_str).resolve() if dir_str else ROOT
        if not work_dir.is_dir():
            print(f"Directory not found: {work_dir}")
            return

        cron_cmd = " && ".join(cmd_parts)
        cron_entry = f"{mm} {hh} * * * cd {work_dir} && {cron_cmd}"
        lines = [ln for ln in existing_crontab.splitlines() if marker not in ln]
        lines.append(f"{cron_entry}  {marker}")
        if not _write_crontab("\n".join(lines) + "\n"):
            return
        print(f"Update cron job set: daily at {hh:02d}:{mm:02d}")
        print(f"  {cron_entry}")


def remove_cron() -> None:
    existing = _get_crontab()
    markers = [CRON_MARKER_RUN, CRON_MARKER_UPDATE]
    found = [m for m in markers if m in existing]
    if not found:
        print("No cart cron jobs found.")
        return
    lines = [ln for ln in existing.splitlines() if not any(m in ln for m in markers)]
    _write_crontab("\n".join(lines) + "\n")
    print(f"Removed {len(found)} cart cron job(s).")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cart", description="Contribution graph art scheduler")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create required folders/files if missing")
    sub.add_parser("run", help="Run scheduled commits for today")
    update_p = sub.add_parser("update", help="Update cart.py from the remote repo")
    update_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    reset_p = sub.add_parser("reset", help="Reset schedule.yml to empty (does not log out)")
    reset_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    sub.add_parser("login", help="Save GitHub credentials for pushing commits")
    sub.add_parser("logout", help="Remove saved GitHub credentials")

    cron = sub.add_parser("cron", help="Manage the daily cron job (Linux)")
    cron_sub = cron.add_subparsers(dest="cron_cmd", required=True)
    setup_p = cron_sub.add_parser("setup", help="Create or update a cron job")
    setup_p.add_argument(
        "type", nargs="?", choices=["run", "update"], default="run",
        help="'run' = daily commits (default), 'update' = auto-update tool/patterns",
    )
    cron_sub.add_parser("remove", help="Remove all cart cron jobs")

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

    pat_update_p = pat_sub.add_parser("update", help="Update installed patterns")
    pat_update_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    return parser


def _execute_command(argv: list[str]) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        ensure_scaffold(ROOT)
        print("Initialized.")
        return

    if args.command == "update":
        update_tool(auto_yes=args.yes)
        return

    if args.command == "login":
        login()
        return

    if args.command == "logout":
        logout()
        return

    if args.command == "cron":
        if args.cron_cmd == "setup":
            setup_cron(args.type)
        elif args.cron_cmd == "remove":
            remove_cron()
        return

    ensure_scaffold(ROOT, pull=False)

    if args.command == "run":
        run_schedule(ROOT)
        return

    if args.command == "reset":
        reset_schedule(ROOT, auto_yes=args.yes)
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
            update_patterns(ROOT, auto_yes=args.yes if hasattr(args, "yes") else False)
            return


class CartShell(cmd.Cmd):
    intro = "cart interactive shell. Type 'help' or '?' for commands."
    prompt = "cart> "

    def do_init(self, arg: str) -> None:
        """Initialize required folders/files."""
        _execute_command(["init"])

    def do_update(self, arg: str) -> None:
        """Update cart.py from the remote repo. Use -y to skip confirmation."""
        auto_yes = "-y" in arg.split() or "--yes" in arg.split()
        update_tool(auto_yes=auto_yes)

    def do_login(self, arg: str) -> None:
        """Save GitHub credentials for pushing commits."""
        login()

    def do_logout(self, arg: str) -> None:
        """Remove saved GitHub credentials."""
        logout()

    def do_run(self, arg: str) -> None:
        """Run scheduled commits for today."""
        _execute_command(["run"])

    def do_reset(self, arg: str) -> None:
        """Reset schedule.yml to empty (does not log out). Use -y to skip confirmation."""
        auto_yes = "-y" in arg.split() or "--yes" in arg.split()
        ensure_scaffold(ROOT, pull=False)
        reset_schedule(ROOT, auto_yes=auto_yes)

    def do_cron(self, arg: str) -> None:
        """Manage daily cron job. Usage: cron setup [run|update]|remove"""
        parts = arg.split()
        if not parts:
            print("Usage: cron setup [run|update] | cron remove")
            return
        if parts[0] == "setup":
            cron_type = parts[1] if len(parts) > 1 and parts[1] in ("run", "update") else "run"
            setup_cron(cron_type)
        elif parts[0] == "remove":
            remove_cron()
        else:
            print("Usage: cron setup [run|update] | cron remove")

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

    def do_bye(self, arg: str) -> bool:
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
