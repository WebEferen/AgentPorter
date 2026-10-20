---
name: verify
description: Prove parity between a port and the original independently of whoever wrote the port. Runs every recorded oracle fixture through the target harness, resolves every mapped reference test, adds adversarial cases recorded from the original, checks DIVERGENCE markers, assigns a parity level per unit (EXACT, EQUIVALENT, DIVERGENT, ASSERTED, GAP, OUT-OF-SCOPE) and publishes parity.json and PARITY.md. Use after a unit is implemented and reviewed, for the final verification of /agentporter:port, or when the user asks whether a port behaves like the original.
argument-hint: "[<unit id>]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# verify

Where this sits: per unit after review, then once at the end. It writes `parity.json`, `PARITY.md` and
`runs/`, and is the only skill that sets a unit VERIFIED or GAP. Map:
`${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`. Fixture contract:
`${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/CONTRACT.md`.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

Unit: `$ARGUMENTS` (empty means the final pass over every unit).

## Steps

1. `porter state preflight verify`.
2. If an Agent tool is available, spawn `agentporter:verifier` with the unit id (or "all"), the workspace
   path and the target root. Give it nothing else: no unit reports, no implementer notes. Otherwise read
   `${CLAUDE_PLUGIN_ROOT}/agents/verifier.md` and do its checklist inline without reading
   `reports/units/` or the implementer's reasoning.
3. The verifier:
   - confirms fixtures match the pinned original (re-record a sample; a difference means the source moved),
   - runs the harness: `porter cli run --exe "<port command>" [--unit <unit>]` for CLIs, or the target
     harness from `knowledge/harnesses/<target>/` for libraries, writing `.porter/runs/<run>/<unit>.json`,
   - imports reference test results with `porter parity reftests <junit|vitest|jest|gotest> <report>`,
   - adds adversarial cases (boundary, empty, unicode, large, malformed) to `oracle/cases/<unit>.json`
     with `"origin": "adversarial:<topic>"`, expands and records them from the original, and runs them
     through the port (without that origin, the new cases change the contract's hash and mark later phases STALE),
   - runs `porter parity collect [--unit <unit>] --run <run>`.
4. Per unit result:
   - Passing level (EXACT, EQUIVALENT, DIVERGENT, ASSERTED):
     `porter state unit set <unit> VERIFIED --level <level>` after `porter state unit task <unit> verify`.
   - GAP: `porter state unit set <unit> GAP` and return the mismatches to the implement skill. When the
     verifier classed every mismatch as a divergence candidate, there is nothing for the implementer to
     fix: stop and ask the user whether to add those case ids to the divergence (`approvedBy` names their
     answer) or to fix the behavior. Sending such a unit back to implement only spends its attempts.
5. Final pass (no unit argument, all units terminal): `porter parity collect`, `porter parity report
   --copy-to <target docs dir>/PARITY.md`, then `porter state postflight verify`. A unit the final pass
   finds GAP is set GAP even when it is DONE (`porter state preflight implement --rerun` reopens the
   phase), and postflight refuses to finish until no unit is GAP.
6. Artifact mode with a TTY-dependent CLI: also capture three to five scenarios with REA
   `capture-process` for the original and the port, compare them with `compare-process-captures`, and
   register both captures and the comparison as evidence (`porter recover register`). See
   `${CLAUDE_PLUGIN_ROOT}/knowledge/rea.md`.

## Rules

- Parity comes from running fixtures. Reading code never makes a case pass.
- A unit with zero fixtures can only be ASSERTED (reference tests pass and the plan gives a reason) or GAP.
- Every divergence in `divergences.json` has a `DIVERGENCE(<id>)` marker in the target, and every marker
  has an entry. `parity collect` reports both directions.
- Adversarial mismatches become fixtures, so the next run keeps checking them.
