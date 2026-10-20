---
name: recover
description: Recover the behavior and public surface of a program you only have as a built artifact (native binary, .NET assembly, JAR or APK, minified JavaScript bundle, Electron app, WASM) so it can be ported to another language. Uses REA (Reverse Engineer Anything) for static evidence and runs the artifact as a black-box oracle, then writes .porter/recover/recovery.json with every claim tied to evidence. Use as the first AgentPorter phase when there is no source code, or when the user asks what a binary or closed tool does before reimplementing it.
argument-hint: "[<artifact path>]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# recover

Where this sits: first phase, artifact mode only. It needs a recorded authorization. It produces
`recover/artifact.json`, `recover/recovery.json`, `recover/recovery.md` and `recover/evidence/`, which the
survey, deps and contract phases read. Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`.
Reference: `${CLAUDE_PLUGIN_ROOT}/knowledge/rea.md` (read it before step 2).

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight recover`. If it reports a missing authorization, ask the user who owns the
   artifact or what permits analyzing it, record the answer with `porter state authorize --note "..."`,
   and run preflight again. If the user cannot give a basis, stop.
2. `porter recover detect --write`. Read the table: format, architecture, original language and its
   evidence, kind, whether it runs on this host, and the REA plan. If REA is reported missing, tell the
   user `npx -y rea-agents@6.7.0` will be downloaded on first use, or how to install it (knowledge/rea.md).
3. Static evidence: run each REA plan step that applies, one evidence file per step, absolute paths:
   `porter recover rea <name> <rea command> <args>`. Always run `inspect-artifact` first and read its
   `next_probes`. Skip steps marked "needs provider" unless the user has Ghidra, Hopper or IDA set up for
   REA, and use them only for specific unknowns.
4. Black-box surface, when the artifact runs here and is a CLI: `porter recover probe`. Then targeted
   probes for each behavior question, one evidence file each:
   `porter recover probe --name probe-<topic> --probe="<argv>" --stdin="<input>"`. Keep the `=`: argv that
   starts with a dash (`--probe="-m"`) is otherwise read as a new flag.
   Probes execute the artifact. If the user said it is untrusted, ask before running it, and suggest a VM.
5. `porter recover import`. This writes `recover/recovery.json` from the evidence and keeps any edits.
6. Curate `recovery.json`. If an Agent tool is available, spawn `agentporter:recoverer` with the workspace
   path and this brief: "Curate .porter/recover/recovery.json from the evidence under
   .porter/recover/evidence/. Follow your checklist." Otherwise read
   `${CLAUDE_PLUGIN_ROOT}/agents/recoverer.md` and do its checklist inline. The result must have:
   - `summary`: what the artifact is, how it was examined, and how confident the recovery is.
   - `kind` set correctly, and every interface item grouped (`group`) the way the port should be cut.
   - `behaviors`: what the program does, each with evidence references.
   - `unknowns`: every open question, each with the probe that would answer it.
   - `oracle.command`: the exact command that runs the original.
7. `porter recover import --render` to regenerate `recover/recovery.md` from the curated JSON.
8. `porter state postflight recover`. Fix every reported error and run it again.
9. If the phase is GATE_WAIT, show the user the summary and each gate item with your recommendation, then
   stop. The router or the user approves with `porter state gate recover approve --note "..."`.

## Rules

- Every interface item and behavior cites evidence under `recover/evidence/`. No evidence, no claim.
- Decompiled or disassembled code is evidence only. Never copy it into the port, and never paste large
  listings into artifacts the implementer reads.
- REA exit 0 can still mean partial evidence: read `limitations` and `unknowns` in each result and carry
  them into `unknowns` when they matter to the port.
- Version strings: prefer embedded metadata (Go build info, assembly identity) over `--version` output,
  and record both when they disagree.
