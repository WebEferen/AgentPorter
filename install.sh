#!/bin/sh
# AgentPorter installer.
#   curl -fsSL https://raw.githubusercontent.com/WebEferen/AgentPorter/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/WebEferen/AgentPorter/main/install.sh | sh -s -- --no-codex
# Safe to re-run: it updates whatever is already installed.
set -eu

REPO="WebEferen/AgentPorter"
REF="${AGENTPORTER_REF:-main}"
DO_CLI=1
DO_CLAUDE=1
DO_CODEX=1

usage() {
  cat <<EOF
Install AgentPorter: the Claude Code plugin, the Codex plugin and the agentporter CLI.
Plugins are installed for each agent found on the PATH.

Usage: install.sh [--ref <branch or tag>] [--no-cli] [--no-claude] [--no-codex]

  --ref <ref>   branch or tag to install from (default: main, or \$AGENTPORTER_REF)
  --no-cli      skip the agentporter CLI
  --no-claude   skip the Claude Code plugin
  --no-codex    skip the Codex plugin

The CLI is installed with uv, pipx, or a private virtualenv, whichever is available first.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) [ $# -ge 2 ] || { echo "--ref needs a value" >&2; exit 2; }; REF="$2"; shift 2 ;;
    --ref=*) REF="${1#*=}"; shift ;;
    --no-cli) DO_CLI=0; shift ;;
    --no-claude) DO_CLAUDE=0; shift ;;
    --no-codex) DO_CODEX=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

say() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
has() { command -v "$1" >/dev/null 2>&1; }
python_ok() { has python3 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; }

ARCHIVE="https://github.com/$REPO/archive/$REF.tar.gz"
FAILED=0

install_cli() {
  if has uv; then
    say "Installing the agentporter CLI with uv"
    uv tool install --force --reinstall --python ">=3.11" "agentporter @ $ARCHIVE"
  elif has pipx && python_ok; then
    say "Installing the agentporter CLI with pipx"
    pipx install --force "$ARCHIVE"
  elif python_ok; then
    venv="${XDG_DATA_HOME:-$HOME/.local/share}/agentporter/venv"
    bin="$HOME/.local/bin"
    say "Installing the agentporter CLI into $venv"
    python3 -m venv "$venv" &&
      "$venv/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$ARCHIVE" &&
      mkdir -p "$bin" &&
      ln -sf "$venv/bin/agentporter" "$bin/agentporter" || return 1
    case ":$PATH:" in
      *":$bin:"*) ;;
      *) warn "$bin is not on your PATH; add it to use the agentporter command" ;;
    esac
  else
    warn "skipping the CLI: it needs uv, or Python 3.11 or newer as python3"
    return 1
  fi
}

install_claude() {
  say "Installing the Claude Code plugin"
  if claude plugin marketplace list 2>/dev/null | grep -qw agentporter; then
    claude plugin marketplace update agentporter || return 1
  else
    claude plugin marketplace add "https://github.com/$REPO.git#$REF" || return 1
  fi
  claude plugin install agentporter@agentporter && claude plugin update agentporter@agentporter
}

install_codex() {
  say "Installing the Codex plugin"
  codex plugin marketplace add "$REPO" --ref "$REF" &&
    codex plugin marketplace upgrade agentporter &&
    codex plugin add agentporter@agentporter
}

if [ "$DO_CLI" = 1 ]; then install_cli || FAILED=1; fi

FOUND=0
if [ "$DO_CLAUDE" = 1 ] && has claude; then FOUND=1; install_claude || { warn "Claude Code plugin install failed"; FAILED=1; }; fi
if [ "$DO_CODEX" = 1 ] && has codex; then FOUND=1; install_codex || { warn "Codex plugin install failed"; FAILED=1; }; fi
if [ "$FOUND" = 0 ] && { [ "$DO_CLAUDE" = 1 ] || [ "$DO_CODEX" = 1 ]; }; then
  warn "neither claude nor codex is on the PATH, so no plugin was installed"
fi

if ! python_ok; then
  warn "the plugin skills run python3 and need Python 3.11 or newer; install it (python.org, Homebrew, your package manager, or 'uv python install')"
fi

if [ "$FAILED" = 1 ]; then exit 1; fi
say "Done. In Claude Code, start a port with /agentporter:port; from a shell, run agentporter --help"
