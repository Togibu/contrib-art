# Pattern Development Guide

Patterns live in the `contrib-art-patterns` repo and are pulled into the local
`patterns/` folder via `cart pattern pull` or `cart pattern update`.

## Repo structure

Each pattern is a subdirectory at the root of `contrib-art-patterns`:

```
contrib-art-patterns/
├── text/
│   ├── manifest.yml
│   └── pattern.py
├── snake/
│   ├── manifest.yml
│   └── pattern.py
└── <new-pattern>/
    ├── manifest.yml
    └── pattern.py
```

## manifest.yml

```yaml
name: <pattern-name>
version: 1.0
entrypoint: pattern.py
```

## pattern.py interface

Every pattern must expose a `run(context)` function:

```python
def run(context: dict) -> None:
    ...
```

### context fields

| Key              | Type   | Description                        |
|------------------|--------|------------------------------------|
| `root`           | Path   | cart working directory             |
| `config_path`    | Path   | path to config.yml                 |
| `patterns_path`  | Path   | path to patterns.yml               |
| `schedule_path`  | Path   | path to schedule.yml — write here  |
| `pattern_dir`    | Path   | directory of this pattern          |
| `manifest`       | dict   | parsed manifest.yml                |

### Writing schedule.yml

The pattern is responsible for writing `schedule.yml`. Use this structure:

```python
import yaml
from pathlib import Path

data = {
    "pattern": "<name>",
    "meta": {
        # any settings the pattern used (shown in progress.yml)
        "preview": "<ascii preview string>",
    },
    "schedule": {
        "2026-03-08": 3,   # date -> commit count
        "2026-03-09": 1,
    },
}
context["schedule_path"].write_text(
    yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
)
```

### Year-boundary warning

If the schedule end date crosses into a new year, show a warning:

```python
if end_date.year > start_date.year:
    print(
        f"\nWarning: the schedule crosses into {end_date.year}. "
        "GitHub's contribution graph resets each year, so the pattern "
        "will be split across two graphs."
    )
```

---

# cart.py Tool Internals

## Constants

| Name                | Value                                                          |
|---------------------|----------------------------------------------------------------|
| `ROOT`              | `Path.cwd()` — working directory at startup                   |
| `PATTERNS_REPO_URL` | `https://github.com/Togibu/contrib-art-patterns.git`          |
| `TOOL_REPO_URL`     | `https://github.com/Togibu/contrib-art.git`                   |
| `CREDENTIALS_FILE`  | `~/.config/cart/credentials.yml` (chmod 600)                  |

## Credentials system

Credentials are stored in `~/.config/cart/credentials.yml` with fields `username`, `token`, `repo_url`.

- `_read_credentials()` — returns `{}` if file missing
- `_write_credentials(data)` — creates parent dirs, writes YAML, sets `chmod 600`

`login()` verifies the token via `GET https://api.github.com/user`, then asks whether to use an existing repo or create a new one via `POST https://api.github.com/user/repos`.

**Always use `curl` (subprocess), never `urllib`.** macOS has SSL certificate issues with Python's `urllib`.

## Update mechanism

`update_tool()` flow:
1. `git ls-remote TOOL_REPO_URL HEAD` → get `remote_sha`
2. Read `.cart_version` (next to `cart.py`) → `local_sha`
3. If they differ: prompt, download `cart.py` via `curl`, write `remote_sha` to `.cart_version`

The `.cart_version` file lives at `Path(__file__).parent / ".cart_version"`. It is written after every successful download. Without it, the tool always shows "Update available".

Pattern update check (`update_patterns`) works identically but compares against `last_pull_sha` in `patterns.yml`.

## Commit system

`perform_commits(root, count)` flow:
1. Read credentials from `~/.config/cart/credentials.yml`
2. `_auth_url(repo_url, username, token)` — injects `username:token@` into HTTPS URL
3. `_setup_repo(repo_dir, auth_url, username)` — clones or pulls `~/.config/cart/repo/`, sets `user.name` and `user.email`
4. Make `count` backdated commits to `data.txt` using `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` env vars (set to `{today}T12:00:00`)
5. Update `progress.yml` in the repo with real `datetime.now()` upload timestamp and append an entry
6. Commit `progress.yml`, then push via `git push auth_url`

`run_schedule(root)` reads today's entry from `schedule.yml`, calls `perform_commits`, removes the entry, and re-writes `schedule.yml`.

## Pattern loading

`choose_pattern(root, name)` flow:
1. Locate `patterns/<name>/`
2. `_load_manifest(pattern_dir)` — reads and validates `manifest.yml`
3. `_load_pattern_module(pattern_dir, entrypoint)` — loads Python file via `importlib.util.spec_from_file_location`
4. Builds `context` dict (see context fields table above) and calls `module.run(context)`

## Shell interface

Running `python3 cart.py` with no arguments starts `CartShell` — a `cmd.Cmd` interactive shell with `cart> ` prompt and tab completion.

Running with arguments (e.g. `python3 cart.py pattern pull`) goes through `_execute_command(argv)` → `_build_parser()` (argparse).

Available top-level commands: `init`, `run`, `update`, `login`, `logout`, `pattern`

`pattern` subcommands: `list`, `pull`, `choose <name>`, `install <name>`, `remove <name>`, `update`

## Planned patterns

(none — all originally planned patterns are now implemented in `contrib-art-patterns`)
