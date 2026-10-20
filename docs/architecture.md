# Architecture

AgentPorter splits a port between two kinds of worker. The agent does what needs judgment: reading
code, choosing packages, writing the port, reviewing it. A deterministic Python tool does everything
that must give the same answer every time: workflow state, registry checks, dependency graphs,
decomposition, fixtures and parity scoring. The agent can only advance the port through that tool, and
the tool refuses steps that skip evidence.

## Components

| Part | Where | Role |
| --- | --- | --- |
| Router skill | `skills/port/` | Starts or resumes a port, runs phases in order, stops at gates. |
| Phase skills | `skills/<phase>/` | One per phase: recover, survey, target, deps, contract, strategy, implement, verify, plus status. |
| Subagents | `agents/` | Focused workers with their own context: surveyor, recoverer, scout, contract-extractor, implementer, reviewer, verifier. |
| Helper CLI | `scripts/porter.py`, `scripts/porterlib/` | Standard library Python 3.11. The only writer of `state.json` and `config.json`. |
| Knowledge | `knowledge/` | Pair references, ecosystem references, oracle and harness templates, JSON Schemas, artifact templates. |
| Workspace | `.porter/` in the port's repository | Every artifact of the port, so any session can resume it. |

The skills are plain Markdown and follow the open agent skills layout, so Claude Code and Codex load
the same files. Skills reach the helper through `${CLAUDE_PLUGIN_ROOT}/scripts/porter.py` in Claude
Code, and through the `scripts/porter.py` two directories above their `SKILL.md` elsewhere.

## Phases and gates

```text
recover -> survey -> target -> deps -> contract -> strategy -> implement -> verify
```

- `recover` runs only in artifact mode and is SKIPPED in code mode.
- `target` is DONE from the start when the user passed `--to`.
- Gated phases (recover, target, deps, strategy) end in GATE_WAIT. The user's decision is recorded with
  `state gate` or `target choose`, in the user's words, in `decisions.md`.

Phase states are PENDING, IN_PROGRESS, GATE_WAIT, DONE, SKIPPED and STALE. Postflight stores a content
hash of every artifact a phase produced. Re-running a finished phase needs `--rerun` and marks every
downstream phase STALE, so later phases cannot quietly build on outdated inputs. The contract's fixture
hash leaves out cases whose origin marks them adversarial (`adversarial:<topic>`) and the recording
timestamp, so the cases verify adds do not make the contract look changed.

## Stage awareness

The agent has to know where it is after any interruption: which phase, which unit, which step inside
the unit, and what evidence exists. Four mechanisms keep that true.

1. **One state file.** `.porter/state.json` holds phases, units, budgets and an append-only history.
   Only `porter.py` writes it, and `state validate` checks it against its schema.
2. **Preflight and postflight.** Every phase skill starts with `state preflight <phase>`, which refuses
   to run before all upstream phases are DONE or SKIPPED, not STALE, and approved where gated. Every
   phase skill ends with `state postflight <phase>`, which validates the artifacts and moves the phase on.
3. **The stage card.** Every skill prints it at start and stop, and `/agentporter:status` prints it on
   demand:

   ```text
   AgentPorter  ms unpinned -> go      .porter/ at 2026-10-20 16:05Z
   Phase: none   gates: target given, deps pending, strategy pending   stale: none
   Next: run the survey phase (/agentporter:survey)
   ```

4. **`PORTING.md`.** Written to the port's root after every postflight and gate, so a reader on
   GitHub sees the state without tools.

`state next --json` gives the single next action. The router uses it to resume.

## Units

The strategy phase cuts the port into units (see [decomposition.md](decomposition.md)). Each unit goes
through a fixed checklist, and the current step is stored in state:

```text
read-contract -> scaffold -> implement -> mark-divergences -> port-tests -> wire-fixtures ->
green -> review -> apply-findings -> verify -> report -> commit
```

Unit statuses and the rules `porter.py` enforces on them:

| Status | Allowed when |
| --- | --- |
| IN_PROGRESS | All dependencies are DONE and the attempt budget is not exhausted. |
| IMPLEMENTED | The `green` step was reached: build, lint, typecheck and tests pass. |
| REVIEWED | Review findings were applied. |
| VERIFIED | `parity.json` has an entry for the unit with a passing level that matches the claimed one. |
| GAP | `parity.json` records GAP. The unit goes back to IN_PROGRESS, or to VERIFIED with `--note` once the user accepts the remaining cases as a divergence. |
| DONE | The unit was VERIFIED and its report written. |
| BLOCKED | A note says what blocked it and what was tried. |
| DEFERRED | A note says why it is out of scope. |

The implementer cannot mark its own work verified. The verifier runs as a separate subagent that sees
the code, the contract and the fixtures, never the implementer's reasoning.

## Evidence rules

- A package is a candidate only after a live registry lookup. `registry verify-deps` re-checks every
  MAP and SHIM decision before the deps phase can finish.
- Fixtures come from running the original. Normalizations are declared per case before the port exists.
- Every intended difference has a `divergences.json` entry and a `DIVERGENCE(id)` marker in the code.
- In artifact mode, every recovered interface item points at an evidence file, and decompiled code is
  never copied.

## Schemas

Every workspace artifact has a JSON Schema in `knowledge/schemas/`: config, state, survey, artifact,
recovery, target, deps, api, plan, cases, fixture, actuals, reftests, parity, divergences and error-map.
`porter.py` validates against them with a small built-in validator, so no package needs installing.
