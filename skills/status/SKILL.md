---
name: status
description: Show where an AgentPorter port stands (phase, gates, units by status, parity levels, blocked units and the single next action) and, on request, write the port's "Parity with upstream" README section and a release checklist. Read-only and safe to run at any time. Use when the user asks for the status or progress of a port, what is left, what is blocked, or how to release it.
argument-hint: "[release]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# status

Read-only. It never edits code or state, except the release documents when asked.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state board --units`. If there is no workspace, say so and show how to start one:
   `/agentporter:port <source> [--to <language>]`.
2. If `.porter/parity.json` exists, summarize the levels and any GAP units with their first mismatch.
3. List BLOCKED units with their notes and DEFERRED units with their reasons.
4. End with the next action from `porter state next`.

## Release (argument `release`)

Only when every unit is terminal and the verify phase is DONE:

1. `porter parity report --copy-to <target docs dir>/PARITY.md`.
2. Write a "Parity with upstream" section into the port's README: upstream package, version and commit (or
   artifact SHA-256), evidence date, the per-unit level table, and the divergence list.
3. Write `RELEASE.md` in the target from `${CLAUDE_PLUGIN_ROOT}/knowledge/templates/release-checklist.md`,
   filled in for the target ecosystem.
