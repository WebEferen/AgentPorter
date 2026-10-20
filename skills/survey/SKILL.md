---
name: survey
description: Survey a project before porting it to another language. Pins the source revision, detects languages, build, test and lint tooling, measures size, maps the internal module graph, classifies each module's runtime coupling (pure, I/O, runtime-welded, native) and flags license and test-coverage risks, then writes .porter/survey.md. Works from source code, or from recover's evidence when only a binary exists. Use when a user asks what porting a project would take, or as the survey phase of /agentporter:port.
argument-hint: "[--subpath <dir>]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# survey

Where this sits: after recover (or first, in code mode). It produces `survey.json` and `survey.md`, which
the target, deps, contract and strategy phases read. It never edits the source.
Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight survey`. Stop and report if it fails.
2. `porter survey --write` (add `--subpath <dir>` for a package inside a monorepo; if the repo holds several
   packages and the user did not say which, list them from the output and ask). It sets the source
   language, package, license and commit in `config.json`. In artifact mode it builds the survey from
   `recover/recovery.json` instead of reading code.
3. Read the printed facts. If the survey says it sampled, state which areas were not read.
4. Code mode: if an Agent tool is available, spawn `agentporter:surveyor` with the workspace path, the plugin root (`${CLAUDE_PLUGIN_ROOT}`) and the
   brief "Write .porter/survey.md from survey.json and the source, following your checklist." Otherwise
   read `${CLAUDE_PLUGIN_ROOT}/agents/surveyor.md` and do its checklist inline. Artifact mode: write
   `survey.md` yourself from `recover/recovery.md` and the facts table; there is no code to read.
5. `survey.md` follows `${CLAUDE_PLUGIN_ROOT}/knowledge/templates/survey.md`. It must let the user answer
   "how big is this port and where is the risk" without opening anything else.
6. `porter state postflight survey`. Fix every reported error and run it again.

## Flags the survey must raise

- Strong copyleft license (GPL, AGPL): the port inherits the terms. In artifact mode the license is not
  recoverable from the binary: ask the user and record the answer with
  `porter state source --license <spdx> --note "<the user's words>"` before `survey --write`.
- Few or no tests: the contract will lean on docs and generated fixtures, with lower confidence.
- Service or app kind: the pipeline covers its library parts; list what falls outside.
- Native code, FFI, subprocess calls, OS-specific paths.
- Sampling on a large repository: never imply full coverage.
