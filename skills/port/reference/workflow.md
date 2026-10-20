# AgentPorter workflow

The canonical map of phases, gates, artifacts and transitions. Every phase skill follows it, and
`porter.py state` enforces it. All state lives in `.porter/` at the root of the target repository.

## Phases

| # | Phase | Skill | Runs when | Needs | Produces | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | recover | `/agentporter:recover` | artifact mode only (no source code) | authorization recorded | `recover/artifact.json`, `recover/recovery.json`, `recover/recovery.md`, `recover/evidence/` | when unknowns, LOW confidence items, or no runnable oracle |
| 2 | survey | `/agentporter:survey` | always | recover DONE or SKIPPED | `survey.json`, `survey.md` | none |
| 3 | target | `/agentporter:target` | when `--to` was not given | survey | `target.json`, `target.md` | always: the user picks the language |
| 4 | deps | `/agentporter:deps` | always | target | `deps.json`, `deps.md`, `cache/registry/` | when gate items exist |
| 5 | contract | `/agentporter:contract` | always | deps | `contract/api.json`, `contract/contract.md`, `contract/units/`, `oracle/`, `fixtures/` | none |
| 6 | strategy | `/agentporter:strategy` | always | contract | `plan.json`, `strategy.md`, `decomposition.md` | always: scope, order, budgets |
| 7 | implement | `/agentporter:implement` | per unit | strategy | target code and tests, `reports/units/` | a unit becomes BLOCKED |
| 8 | verify | `/agentporter:verify` | per unit, then once at the end | strategy, fixtures | `parity.json`, `PARITY.md` | none |
| - | status | `/agentporter:status` | any time, read-only | nothing | the stage card | none |

`/agentporter:port` is the router: it creates the workspace, runs the phases in order, stops at gates,
and resumes from `state.json` when called with no arguments.

## Phase states

`PENDING -> IN_PROGRESS -> DONE`, with `GATE_WAIT` before `DONE` for gated phases, `SKIPPED` for
`recover` in code mode and `STALE` when an upstream artifact changed after the phase finished.
Re-running a DONE phase needs `--rerun` and makes every downstream phase STALE. A target language given
with `--to` marks `target` DONE with gate `given`.

## Unit states

```text
PENDING -> (READY, computed) -> IN_PROGRESS -> IMPLEMENTED -> REVIEWED -> VERIFIED -> DONE
                                     |                                      |
                                     +-> BLOCKED (attempts exhausted)       +-> GAP (verify found mismatches) -> IN_PROGRESS
PENDING -> DEFERRED (strategy decision, with a reason)
```

Only the verify skill sets VERIFIED or GAP, and only when `parity.json` agrees. A DONE unit goes back to
GAP when a later pass finds a mismatch; `state postflight verify` refuses to finish while any unit is GAP.
A GAP made only of divergence candidates goes straight to VERIFIED once the user accepts the divergence and
parity is collected again (`--note` records the decision); it does not spend an attempt.

## Unit task checklist

`read-contract -> scaffold -> implement -> mark-divergences -> port-tests -> wire-fixtures -> green ->
review -> apply-findings -> verify -> report -> commit`. The current task is stored in state, so a
resume lands on the right step.

## Commands every skill uses

```text
porter state preflight <phase>      # refuses out-of-order work, prints the stage card
porter state postflight <phase>     # validates artifacts, records hashes, sets DONE or GATE_WAIT
porter state gate <phase> approve|reject --note "<the user's words>"
porter target choose <language> --note "<the user's words>"
porter state next [--json]          # the single next action
porter state board --units          # stage card plus the unit table
```

Here `porter` stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`. There is no `porter` executable,
and shell variables do not survive between tool calls (an unquoted `$P` also breaks under zsh), so write the
full command every time. In Codex or a plain skills install, `${CLAUDE_PLUGIN_ROOT}` is not substituted: use
the `scripts/porter.py` that sits two directories above the skill's `SKILL.md`.

## Rules that hold in every phase

1. Run preflight first and postflight last. If preflight fails, stop and report its message. Never work
   around a missing artifact.
2. Only `porter.py` writes `state.json` and `config.json`. Edit the other artifacts directly.
3. Decisions the user makes go through a gate command, which appends them to `decisions.md`.
4. Every claim about a package, a registry or the original's behavior cites evidence: a registry cache
   record, a fixture, a REA evidence file or a source line.
5. Never invent a package name. A candidate exists only after `porter.py registry lookup` says so.
6. Print the stage card (`state board`) when you start and when you stop.
