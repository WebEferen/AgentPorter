---
name: strategy
description: Decide how a port is built: per-unit strategy (contract port, code port, wrap, drop), the idiom translation map between the two languages, the decomposition into units with layers, waves, a tracer bullet and an order, acceptance criteria, budgets, scope cuts, a risk register and the target scaffold. Writes plan.json, strategy.md and decomposition.md and ends at the user's approval gate. Use as the strategy phase of /agentporter:port, or when the user asks for a porting plan they can review before any code is written.
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# strategy

Where this sits: after contract, before any target code. It produces the final `plan.json`,
`decomposition.md` and `strategy.md`, syncs the units into state, and ends at the strategy gate. Map:
`${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`. Method: section "Decomposition methodology" in
`${CLAUDE_PLUGIN_ROOT}/docs/decomposition.md`.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight strategy`. Stop and report if it fails.
2. Load `${CLAUDE_PLUGIN_ROOT}/knowledge/pairs/<source>-to-<target>.md` (or `GENERIC.md`) and
   `${CLAUDE_PLUGIN_ROOT}/knowledge/ecosystems/<target>.md`.
3. `porter decompose` (final, uses `contract/api.json`). It proposes units, layers, waves, the tracer
   bullet and the order, and explains every split, merge and cycle in `decomposition.md`. It always writes
   `decomposition.proposed.json`, and replaces `plan.json` unless that is already final (`--force` replaces
   a final plan).
4. Review the proposal against the contract. Adjust `plan.json` only for a reason you can state: a unit
   whose symbols do not belong together, a seam that cuts a cycle more cleanly, a unit to defer. Record
   each change as one line under "Adjustments" in `decomposition.md` and in `plan.json.adjustments`.
5. Per unit set `strategy`: `contract-port` (reimplement natively from the contract, the default),
   `code-port` (adapt the source logic, for intricate algorithms), `wrap` (a mapped dependency almost
   directly), `drop`. Units welded to the source runtime are contract ports with a listed divergence, or
   deferred, never code ports.
6. Write `strategy.md` from `${CLAUDE_PLUGIN_ROOT}/knowledge/templates/strategy.md`: idiom map
   specialized to this codebase, dropped workarounds and new substrate, scope gauntlet (now, out of scope,
   seam for later), risk register with signals, scaffold (layout, toolchain, harness from
   `${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/<target>/`, CI), and budgets.
7. Acceptance criteria per unit stay as `decompose` wrote them unless the contract needs more.
8. `porter state postflight strategy`. It validates the plan, syncs units into state and sets GATE_WAIT.
9. Present the gate: the unit table in order with the tracer marked, scope cuts, budgets and the top
   three risks. Stop for the user. Approve with `porter state gate strategy approve --note "..."`.

## Rules

- A plan that exceeds a budget is presented with a cut-down scope for the user to choose. Never trim
  scope silently.
- Every in-scope symbol is owned by exactly one unit. Postflight checks this.
- Nothing is written to the target source tree in this phase.
