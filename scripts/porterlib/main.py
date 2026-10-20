"""Command-line entry point shared by scripts/porter.py and the installed `agentporter` command."""
from __future__ import annotations

import argparse
import importlib
import sys

from . import __version__
from .common import PorterError

MODULES = ("state", "source", "recover", "survey", "target", "depsgraph", "usage", "registry", "decompose", "fixtures", "cli", "parity")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentPorter deterministic helpers")
    parser.add_argument("--version", action="version", version=f"agentporter {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in MODULES:
        try:
            module = importlib.import_module(f"{__package__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__package__}.{name}":
                continue
            raise
        module.register(sub)
    return parser


def _hoist_workspace(argv: list[str]) -> list[str]:
    """Move --workspace next to the command group, the only place group parsers accept it."""
    for i, a in enumerate(argv):
        if a.startswith("--workspace=") and i > 1:
            return [argv[0], a] + argv[1:i] + argv[i + 1:]
        if a == "--workspace" and i > 1 and i + 1 < len(argv):
            return [argv[0], a, argv[i + 1]] + argv[1:i] + argv[i + 2:]
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else list(argv)
    _, extra = parser.parse_known_args(argv)
    misplaced = any(x == "--workspace" or x.startswith("--workspace=") for x in extra)
    args = parser.parse_args(_hoist_workspace(argv) if misplaced else argv)
    try:
        return int(args.func(args) or 0)
    except PorterError as exc:
        sys.stderr.write(f"porter: {exc}\n")
        return exc.code
    except KeyboardInterrupt:
        return 130
