"""Pin the source: record a local checkout, or clone a git URL into .porter/cache/source."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .common import PorterError, find_workspace, read_json, write_json


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise PorterError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def fetch(ws: Path, ref: str | None = None) -> dict:
    cfg = read_json(ws / "config.json")
    src = cfg["source"]
    ref = ref or src.get("ref")
    location = src["location"]
    local = Path(location).expanduser()
    dest = ws / "cache" / "source"
    if local.is_dir():
        is_git = subprocess.run(["git", "-C", str(local), "rev-parse", "--git-dir"], capture_output=True).returncode == 0
        if ref and is_git:
            head = _git("-C", str(local), "rev-parse", "HEAD")
            want = _git("-C", str(local), "rev-parse", f"{ref}^{{commit}}")
            if head != want:
                if not dest.exists():
                    _git("clone", "--quiet", "--no-checkout", str(local.resolve()), str(dest))
                _git("-C", str(dest), "checkout", "--quiet", want)
                path = dest
            else:
                path = local.resolve()
        else:
            path = local.resolve()
    else:
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            _git("clone", "--quiet", location, str(dest))
        else:
            _git("-C", str(dest), "fetch", "--quiet", "--tags", "origin")
        if ref:
            _git("-C", str(dest), "checkout", "--quiet", ref)
        path = dest
    commit, dirty = None, None
    if subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"], capture_output=True).returncode == 0:
        commit = _git("-C", str(path), "rev-parse", "HEAD")
        dirty = bool(_git("-C", str(path), "status", "--porcelain"))
    src.update({"path": str(path), "commit": commit, "dirty": dirty, "ref": ref})
    write_json(ws / "config.json", cfg)
    return src


def cmd_source(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    src = fetch(ws, args.ref)
    print(f"source: {src['location']}")
    print(f"path:   {src['path']}")
    print(f"commit: {src['commit'] or 'not a git checkout (record the version by hand in survey.md)'}"
          + (" (DIRTY: uncommitted changes, results may not be reproducible)" if src.get("dirty") else ""))
    if src.get("ref"):
        print(f"ref:    {src['ref']}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("source", help="pin the source checkout (clone a URL, or record a local path and commit)")
    p.add_argument("action", choices=("fetch",))
    p.add_argument("--ref", help="tag, branch or commit to pin")
    p.add_argument("--workspace")
    p.set_defaults(func=cmd_source)
