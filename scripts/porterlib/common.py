from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

_PACKAGE = Path(__file__).resolve().parent
PLUGIN_ROOT = _PACKAGE.parents[1]
KNOWLEDGE = PLUGIN_ROOT / "knowledge" if (PLUGIN_ROOT / "knowledge").is_dir() else _PACKAGE / "knowledge"
SCHEMAS = KNOWLEDGE / "schemas"
WORKSPACE_DIR = ".porter"

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
    "target", "vendor", ".gradle", ".idea", ".vscode", "site-packages", WORKSPACE_DIR,
    "coverage", ".next", ".nuxt", "_build", "deps", ".eggs", ".cache", "bower_components",
    ".bundle", "Pods", "obj",
}


class PorterError(Exception):
    """A user-facing failure with an exit code (1 = findings, 2 = usage or environment)."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def read_json(path: Path | str) -> Any:
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise PorterError(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        raise PorterError(f"invalid JSON in {path}: {exc}")


def write_json(path: Path | str, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except ValueError as exc:
        raise PorterError(f"{path.name}: {exc}. Write NaN and infinities as tags: "
                          '{"$float": "nan"}, {"$float": "inf"}, {"$float": "-inf"}') from exc
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError:
        raw = (json.dumps(data, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def write_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_path(path: Path, exclude: tuple[str, ...] = ()) -> str | None:
    """Content hash of a file, or of every file under a directory (sorted, path-salted)."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
        return "sha256:" + h.hexdigest()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = child.relative_to(path).as_posix()
        if any(child.match(pattern) for pattern in exclude):
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(child.read_bytes())
    return "sha256:" + h.hexdigest()


def find_workspace(explicit: str | None = None, must_exist: bool = True) -> Path:
    if explicit:
        ws = Path(explicit).resolve()
        if ws.name != WORKSPACE_DIR and (ws / WORKSPACE_DIR).is_dir():
            ws = ws / WORKSPACE_DIR
        if must_exist and not ws.is_dir():
            raise PorterError(f"no workspace at {ws}")
        return ws
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / WORKSPACE_DIR).is_dir():
            return candidate / WORKSPACE_DIR
    if must_exist:
        raise PorterError(
            "no .porter workspace found in this directory or its parents. "
            "Start a port with: porter.py init --source <path or git url> --to <language>"
        )
    return cwd / WORKSPACE_DIR


def emit(data: Any, as_json: bool, text: str | None = None) -> None:
    if as_json or text is None:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def iter_files(root: Path, skip_dirs: set[str] = SKIP_DIRS):
    """Yield files under root in sorted order, pruning vendored and generated directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            yield Path(dirpath) / name


def read_text_safe(path: Path, limit: int = 2_000_000) -> str | None:
    try:
        if path.stat().st_size > limit:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def nonblank_loc(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())
