# Installing

AgentPorter is a set of skills, subagents, reference files and one Python helper. All install paths
need Python 3.11 or newer on the PATH as `python3`. Nothing else is required. Node is only needed for
REA (artifact mode) and for oracles and harnesses in JavaScript or TypeScript.

## One command

```sh
curl -fsSL https://raw.githubusercontent.com/WebEferen/AgentPorter/main/install.sh | sh
```

[`install.sh`](../install.sh) installs:

- the Claude Code plugin, when `claude` is on the PATH;
- the Codex plugin, when `codex` is on the PATH;
- the `agentporter` CLI, with uv when it is installed (uv fetches Python 3.11 or newer if needed), else
  pipx, else a private virtualenv in `~/.local/share/agentporter` linked into `~/.local/bin`.

It warns when `python3` is older than 3.11, because the plugin skills run `python3` directly. Running it
again updates everything it installed. Options go after `sh -s --`:

| Option | Effect |
| --- | --- |
| `--ref <ref>` | Install a branch or tag instead of `main` (also `AGENTPORTER_REF`). |
| `--no-cli` | Skip the CLI. |
| `--no-claude` | Skip the Claude Code plugin. |
| `--no-codex` | Skip the Codex plugin. |

The sections below do the same steps by hand.

## Claude Code

```text
/plugin marketplace add WebEferen/AgentPorter
/plugin install agentporter@agentporter
```

Or from a shell:

```text
claude plugin marketplace add WebEferen/AgentPorter
claude plugin install agentporter@agentporter
```

The skills appear as `/agentporter:port`, `/agentporter:status` and so on. Updating and removing:

```text
claude plugin marketplace update agentporter
claude plugin update agentporter@agentporter
claude plugin uninstall agentporter@agentporter
```

To try a local checkout without installing it:

```text
claude --plugin-dir /path/to/AgentPorter
```

## Codex

```text
codex plugin marketplace add WebEferen/AgentPorter
codex plugin add agentporter@agentporter
```

Codex reads `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json` and copies the plugin
into its cache. The skills find `scripts/porter.py` two directories above their own `SKILL.md`, so they
work from that cache. Remove the plugin with `codex plugin remove agentporter@agentporter`.

## The helper CLI on its own

For CI jobs, scripts, or agents that are not plugin-aware:

```text
pipx install git+https://github.com/WebEferen/AgentPorter
agentporter --version
```

The package bundles the schemas, templates and reference files. `agentporter <command>` behaves exactly
like `python3 scripts/porter.py <command>` in a checkout. See [cli.md](cli.md).

## Other agents

Any agent that reads skills from a folder can use AgentPorter. Clone the repository somewhere permanent
and point the agent at its `skills/` folder. Each skill finds `porter.py` relative to its own `SKILL.md`,
so copying a single skill folder out of the repository breaks it. Symlink the whole repository instead.

## Optional tools

| Tool | Needed for |
| --- | --- |
| git | Pinning a source checkout and per-unit commits |
| Node 22.19 or newer | REA in artifact mode, JavaScript and TypeScript oracles and harnesses |
| Ghidra, Hopper or IDA | REA function-level analysis of native binaries without Go or Rust metadata |
| The source language toolchain | Running the original as an oracle (Python, Node, Go, a JDK, PHP) |
| The target language toolchain | Building and testing the port |

## Network access

The deps phase calls package registry APIs (npm, PyPI, crates.io, the Go proxy, Maven Central,
Packagist, RubyGems, NuGet, Hex) and caches the answers in `.porter/cache/registry/` for 24 hours.
`porter.py registry ... --offline` uses only the cache. The only other network calls `porter.py`
makes are `git clone` for a source URL and the `npx` download of REA. Your agent's own network use is
governed by its permission settings.
