# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

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
