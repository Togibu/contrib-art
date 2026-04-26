# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# contrib-art / cart

CLI tool that generates GitHub contribution graph art through automated, backdated Git commits to a separate target repo.

## Running

`cart` is a single-file Python 3 script — there is no install step.

```
python3 cart.py                  # no args → interactive CartShell (cmd.Cmd, tab completion)
python3 cart.py <command> [...]  # one-shot via argparse
```

Only runtime dep is `pyyaml`. There is no test suite, lint config, or build step.

## Key files

| File           | Purpose                                                           |
|----------------|-------------------------------------------------------------------|
| `cart.py`      | Entire CLI — every command, the shell, and the argparse wiring   |
| `config.yml`   | Repo path and `max_commits_per_day` (created by `init`)          |
| `patterns.yml` | Installed-pattern registry + `last_pull_sha` for update checks   |
| `schedule.yml` | Active schedule: `{date: commit_count}` — pattern writes, `run` consumes/pops |
| `patterns/`    | Local pattern modules (populated by `cart pattern pull`)         |
| `.cart_version`| Sibling of `cart.py`; SHA used by `update` to detect new versions |

## Commands

```
cart init                       # scaffold config files, offer to pull patterns
cart login / logout             # save GitHub credentials to ~/.config/cart/
cart run                        # execute today's scheduled commits
cart reset [-y]                 # reset schedule.yml to empty (does not log out)
cart update [-y]                # update cart.py from GitHub (-y skips prompt, used by cron)
cart cron setup [run|update]    # install daily crontab entry (run = commits, update = self-update)
cart cron remove                # remove all cart-managed crontab entries
cart pattern list               # list installed patterns
cart pattern pull               # clone patterns repo and install all patterns
cart pattern update [-y]        # check for pattern updates and pull if available
cart pattern choose <name>      # run a pattern's generator → writes schedule.yml
cart pattern install <name>     # register an already-present pattern folder
cart pattern remove <name>      # unregister a pattern
```

## Architecture: end-to-end flow

The data flow is the most important thing to understand before changing code:

1. **Pattern generates** — `cart pattern choose <name>` loads `patterns/<name>/pattern.py`
   via `importlib.util.spec_from_file_location` and calls its `run(context)`. The pattern
   writes `schedule.yml` (`{date: count}`) in the cart working directory. cart.py never
   knows about specific patterns; the contract is just `run(context)` + writing
   `schedule_path`. See `AGENTS.md` for the full pattern-author interface.
2. **Cron fires daily** — typically `cart run` from `setup_cron("run")`.
3. **`run_schedule(root)`** reads today's entry from `schedule.yml`, calls
   `perform_commits`, then pops the entry and re-writes the file.
4. **`perform_commits`** clones (or pulls) the target repo into `~/.config/cart/repo/`,
   makes `count` backdated commits to `data.txt` using `GIT_AUTHOR_DATE` /
   `GIT_COMMITTER_DATE` set to `{today}T12:00:00`, appends an entry to `progress.yml`
   (with the real upload timestamp), and pushes via an auth URL with the token injected
   inline (`https://user:token@github.com/...`).
5. **GitHub** renders the backdated commits in the contribution graph.

Two repos are involved and easily confused: this **tool repo** (`contrib-art`) hosts
`cart.py`; the **target repo** (configured via `cart login`) is where backdated commits
are pushed. They are unrelated except via `TOOL_REPO_URL` / the user's credentials.

## Self-update mechanism

`cart update` and `cart pattern update` both follow the same pattern:
`git ls-remote <repo> HEAD` for the remote SHA, compare against a stored local SHA
(`.cart_version` for the tool, `last_pull_sha` in `patterns.yml` for patterns), download
if different, write the new SHA. **Without the SHA file, the tool always reports
"Update available"** — so any code path that downloads must also write the SHA.

## Dual command interface

Every user-facing command exists in **two places** that must stay in sync:

- `_build_parser()` (argparse) — used for one-shot invocations like `python3 cart.py run`.
- `CartShell` (cmd.Cmd) — used for the interactive `cart>` prompt; each `do_<name>`
  method either calls business logic directly or shells out to `_execute_command(argv)`.

When adding a command, wire both. `complete_pattern` provides tab completion for the
shell's `pattern` subcommands and reads `list_patterns(ROOT)` for dynamic completion of
pattern names.

## HTTP: always curl, never urllib

All HTTP calls (`api.github.com/user`, repo creation, `cart.py` download) use `curl` via
`subprocess.run`, **not** Python's `urllib`. macOS ships Python with SSL certificate
issues that break `urllib` against GitHub. Do not "modernize" these to `urllib` or
`requests` — keep them as curl subprocesses.

## Credentials

`~/.config/cart/credentials.yml` (chmod 600), fields: `username`, `token`, `repo_url`.
`username` is read from the token via `GET /user`, never typed by the user. The token
needs the `repo` scope. `_auth_url` injects `username:token@` inline for git operations
— this is intentional (avoids needing a credential helper) and means the token is in
process arg lists during pushes.

## Pattern development

See [AGENTS.md](AGENTS.md) for the full pattern authoring guide: the `run(context)`
interface, `schedule.yml` format (including the `meta` block surfaced in `progress.yml`),
the year-boundary warning convention, and the list of planned patterns.
