---
name: deps
description: Turn every dependency of a project being ported into an explicit, evidenced decision for the target language (ABSORB into the standard library, MAP to a package, SHIM with an adapter, PORT, VENDOR, DROP or DEFER). Parses manifests and lockfiles, measures the used surface of each dependency, finds candidates in the target registry and confirms each one exists with a live registry lookup, never by memory. Use as the deps phase of /agentporter:port, or when the user asks what replaces each dependency in another language.
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# deps

Where this sits: after target. It produces `deps.json`, `deps.md` and registry records under
`cache/registry/`, which the contract and strategy phases read. It ends at a gate when there are gate
items. Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight deps`. Stop and report if it fails.
2. `porter deps-graph --write`. Direct and transitive dependencies with scope and locked versions. In
   artifact mode the list comes from modules embedded in the binary; every one needs a decision.
3. Code mode: `porter usage-scan --write`. For Maven, Packagist and NuGet dependencies the scan needs the
   import namespace: add `--import-name <dep>=<prefix>` (for example `com.google.guava:guava=com.google.common`).
   If it lists computed imports, read those lines before calling any dependency unused.
   Artifact mode has no usage data: reason from `recover/recovery.json` behaviors and probes, and say so.
4. Read `${CLAUDE_PLUGIN_ROOT}/knowledge/ecosystems/<target>.md` (registry, maturity signals, test, lint
   and build tools) and sections 12 (standard library) and 13 (dependencies) of
   `${CLAUDE_PLUGIN_ROOT}/knowledge/pairs/<source>-to-<target>.md`, or `GENERIC.md` when no pair file exists.
5. Decide each runtime dependency against its used surface, not the whole package:
   - ABSORB: the target's standard library or runtime covers the used surface.
   - MAP: a target package covers it. SHIM: a package covers most of it and a thin adapter bridges the rest.
   - PORT: no acceptable candidate; it becomes work units, within the PORT budget in `config.json`.
   - VENDOR: keep the original behind a binding (wasm, C ABI, subprocess). Last resort.
   - DROP: not needed in the target (polyfills, source-only tooling). DEFER: out of scope for now, with a reason.
   Dev, build, lint and test tools map through the ecosystem reference to `devTools`; they are never ported.
6. Candidates for MAP and SHIM: if an Agent tool is available, spawn `agentporter:scout` once per
   dependency that needs research (in parallel), with the dependency name, its used surface, the target
   registry and the workspace path. In artifact mode, add that it must not fetch or read the original's
   source (`knowledge/rea.md`, clean room). Otherwise read `${CLAUDE_PLUGIN_ROOT}/agents/scout.md` and do its
   checklist inline. A candidate counts only after
   `porter registry lookup --registry <registry> <name>` reports that it exists.
7. Write `deps.json` (schema `${CLAUDE_PLUGIN_ROOT}/knowledge/schemas/deps.schema.json`). Per dependency:
   `name`, `version`, `scope`, `direct`, `role`, `usedSurface`, `decision`, `candidate` (name, registry,
   version, license, coverage, evidence), `confidence` (HIGH, MEDIUM, LOW), `budget` for PORT, `gate: true`
   for anything the user must see, and `notes`.
8. `porter registry verify-deps`. It re-checks every MAP and SHIM candidate, fills `verified`, license
   compatibility, deprecation and advisories, and records the source license of every PORT and VENDOR
   dependency (`sourceLicense`; copyleft code copied into a permissive port is a gate item). Exit code 1
   means a candidate does not exist: fix the decision, never the check. If the registry is unreachable,
   the status is UNVERIFIED: say so, do not guess.
9. Write `deps.md` following `${CLAUDE_PLUGIN_ROOT}/knowledge/templates/deps.md`.
10. `porter state postflight deps`. Fix every reported error and run it again. If the phase is GATE_WAIT,
    present each gate item with a one-line recommendation and stop for the user.

## Rules

- No package name from memory. Every candidate in `deps.json` has a registry record in `cache/registry/`.
- A dependency used only by tests is a test tool, even if it is listed as a runtime dependency.
- Confidence is LOW when the candidate covers the used surface only partly, is unmaintained (no release in
  two years), has an incompatible license, or was not verified. LOW, PORT and VENDOR always reach the gate.
