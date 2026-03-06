# contrib-art / cart

CLI tool that generates GitHub contribution graph art through automated Git commits.

## Key files

| File        | Purpose                                      |
|-------------|----------------------------------------------|
| `cart.py`   | Main CLI — all commands live here            |
| `config.yml`| Repo path and max-commits-per-day settings   |
| `patterns.yml` | Installed patterns registry               |
| `schedule.yml` | Active commit schedule (date → count)     |
| `patterns/` | Local pattern modules (populated by `cart pattern pull`) |

## Commands

```
cart init                    # scaffold config files, offer to pull patterns
cart login / logout          # save GitHub credentials to ~/.config/cart/
cart run                     # execute today's scheduled commits
cart update                  # update cart.py from GitHub
cart pattern list            # list installed patterns
cart pattern pull            # clone patterns repo and install all patterns
cart pattern update          # check for pattern updates and pull if available
cart pattern choose <name>   # run a pattern's generator → writes schedule.yml
cart pattern install <name>  # register an already-present pattern folder
cart pattern remove <name>   # unregister a pattern
```

## Credentials

Stored in `~/.config/cart/credentials.yml` (chmod 600):
- `username` — GitHub username (read from token automatically)
- `token` — Personal Access Token (repo scope required)
- `repo_url` — target repo for commits

## Pattern development

See [AGENTS.md](AGENTS.md) for the full pattern authoring guide, the
`run(context)` interface, schedule.yml format, and the list of planned patterns.
