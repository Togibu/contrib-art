from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml


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
