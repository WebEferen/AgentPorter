# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `install.sh`: one-command install of the Claude Code plugin, the Codex plugin and the CLI.
- Four more examples, each with the original next to the port: go-shellquote (Go to Python), scule
  (TypeScript to Go), compare-versions (TypeScript to Rust) and pyhumps (Python to Rust). ms-to-go moved
  into the same `original/` and `port/` layout.
- `parity reftests cargo` imports `cargo test` output, with ref tags in comments above `#[test]` functions.
- The JavaScript oracle loads unbuilt TypeScript on Node 22.18 or newer, including extensionless and
  `.js`-suffixed relative imports.

### Changed

- New logo: a hotel service bell whose dome is split by a chevron, from source (slate) to target (teal).
  The README shows the symbol only, leads with the one-command install, and draws the pipeline as a diagram.
- A unit at GAP can move to VERIFIED with `--note` once the user accepts the divergence.
- The Go oracle keeps a non-zero value returned next to an error.
- The Rust harness template is rustfmt and clippy clean.
- Docs cover Go sources without `go.mod`, the oracles' 64-level serialization limit, lone surrogates, and
  where each language's test runner puts ref tags.

### Fixed

- The Claude Code plugin manifest had a `displayName` key that `claude plugin install` rejects.
- Fixtures holding lone UTF-16 surrogates crashed fixture hashing and report writing.
- The JavaScript oracle recorded a module that failed to load as the outcome of every case. It now exits
  2 and writes no fixtures.
- The survey left the package name empty for a Go source without `go.mod`. It now uses the import path of
  the git remote.
- `fixtures diff` on a timings file now says it is not a fixture file.
- `parity reftests` left an empty `[]` in target test names, and PARITY.md had a double space after an
  upstream with no version.

## [0.1.0] - 2026-10-20

### Added

- Claude Code and Codex plugin with ten skills: port, recover, survey, target, deps, contract, strategy,
  implement, verify and status.
- Seven subagents: surveyor, recoverer, scout, contract-extractor, implementer, reviewer and verifier.
- `porter.py` helper CLI, also installable as `agentporter`, with workflow state, preflight and
  postflight checks, gates, registry lookups for nine registries, dependency graphs, usage scanning,
  decomposition, fixture expansion, black-box CLI recording and parity reports.
- Artifact mode: reverse engineering with REA 6.7.0 plus black-box probes, for binaries and bundles
  without source.
- Target language scoring and selection.
- Pair references (full: Python, JavaScript and PHP to TypeScript, Java to Kotlin; stubs for five more),
  a generic method for other pairs, and ten ecosystem references.
- Oracle drivers and parity harness templates, and the oracle contract they share.

[0.1.0]: https://github.com/WebEferen/AgentPorter/releases/tag/v0.1.0
