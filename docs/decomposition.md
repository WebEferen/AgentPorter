# Decomposition methodology

Ports usually fail on bad cuts, and much less often on bad code. Typical bad cuts are units too large
to verify in one run, hidden cycles, I/O tangled with pure logic, and shared types ported three times
in three dialects. AgentPorter therefore splits a port with a deterministic script (`porter.py
decompose`), lets the agent adjust the proposal with stated reasons, and asks the user to approve the
result at the strategy gate.

## Four levels

| Level | Cut | Produced by | Recorded in |
| --- | --- | --- | --- |
| L0 project | one package, or the packages of a monorepo | survey | `survey.json` |
| L1 layers | foundation, core, boundary, runtime-welded, native, entry | `decompose` from survey signals | `plan.json.layers` |
| L2 units | symbol clusters with one observation boundary, sized to one agent run | `decompose` proposes, the agent adjusts, the user approves | `plan.json.units` |
| L3 tasks | the fixed checklist inside a unit | implement skill | `state.json`, `reports/units/<unit>.md` |

The layers follow a hexagonal reading of the source:

- **Foundation** holds shared types, the error hierarchy, constants and small helpers that several
  clusters use. It sets the dialect every later unit follows.
- **Core** is data in, data out.
- **Boundary** is where the core touches the world: filesystem, network, process, clock, randomness.
- **Runtime-welded** and **native** code depend on the source runtime itself (metaclasses, reflection,
  `eval`, FFI, cgo, JNI). They need a strategy decision (contract port, wrap or defer) more than a
  code port.
- **Entry** is the public API surface and CLI wiring that composes everything below.

## What makes a unit

A unit belongs in `plan.json` when it meets all of these:

1. **One observation boundary.** Fixtures or a trace can drive it, and the verifier can judge it
   without looking inside.
2. **Sized to one run.** The defaults are at most 400 source lines and 8 public symbols, and at least
   30 lines. Only functions, classes, methods, interfaces, traits, structs, enums and modules count
   toward the symbol budget. Constants and type aliases ride along for free. A unit's lines are the lines
   of the symbols it owns, so imports and other top-level code are not counted and a unit can look smaller
   than its module does in the survey.
3. **Closed dependencies.** It depends only on units earlier in the order or on mapped external
   dependencies.
4. **One layer.** Pure logic and I/O never share a unit. The I/O side is split into a boundary unit.
5. **Traceable both ways.** It lists the public symbols it owns and the source files and line ranges
   they came from, and later its fixtures and the reference tests mapped to it.

## The algorithm

`porter.py decompose` reads `survey.json`, `contract/api.json` (skipped with `--draft`), `deps.json`
and the usage cache. It writes `plan.json` and `decomposition.md` and logs a reason for every cut.

1. **Roots.** In-scope public symbols from `api.json` are roots. Without `api.json` (draft mode), every
   public symbol the survey found is a root. Symbols marked out of scope are ignored, and their private
   helpers are not pulled in.
2. **Reachability.** From each root, follow references (calls, imports, inheritance, type use) and
   stop at other roots. A private symbol reached from exactly one root joins that root's cluster.
3. **Foundation.** A private symbol reached from several clusters moves to a foundation cluster. Error
   types move to the foundation too. A module that holds only types, constants or errors and is used by
   two or more clusters becomes foundation. Several small foundation clusters merge into one when they
   fit the line budget.
4. **Cycles.** Tarjan's strongly connected components on the cluster graph. Each cycle collapses into
   one unit. A collapsed cycle over budget is flagged so the agent can choose a seam and record it.
5. **Layers.** Entry modules (CLI targets, `__main__`, `cli`, `main`) become entry. Symbols with FFI
   signals become native, symbols with reflection or metaprogramming signals become runtime-welded. A
   cluster that mixes pure and I/O symbols is split into a core unit and a boundary unit.
6. **Split.** A cluster over the line or symbol budget is split by its roots, packing roots and their
   private helpers into budget-sized groups.
7. **Merge.** A cluster under the line floor with exactly one consumer merges into that consumer, when
   the merged result still fits the symbol budget. Foundation, entry, boundary and native clusters are
   never merged this way.
8. **Tiny foundation.** A foundation below the line floor folds into the one consumer that every other
   consumer already depends on. If there is no such consumer, it stays a separate unit.
9. **Ported dependencies.** Each runtime dependency that `deps.json` decides to PORT becomes a
   foundation unit `dep-<name>`, and every unit that imports it depends on it.
10. **Waves.** A topological sort of the unit graph. A unit's wave is the longest path from a leaf.
   Units in the same wave are independent.
11. **Risk.** Each unit carries the union of its symbols' risk tags (regex, unicode, float formatting,
    datetime, reflection, async and so on) and a weighted score.
12. **Tracer bullet.** The lowest-risk vertical slice: a non-foundation, non-entry unit, preferring one
    with at least one dependency, chosen by total risk and then total size of its dependency closure.
13. **Order.** Foundation first, then the tracer bullet's closure, then wave by wave with the highest
    risk first inside a wave, so surprises arrive early. Entry units land last because they depend on
    everything else.

The script is pure standard library and deterministic, so the same inputs always give the same plan.

## Adjusting the proposal

The script proposes and the agent reviews it with the contract in hand. Allowed changes are merges,
splits, renames, deferrals and a different seam for a cycle. Each one needs a reason and gets one line
under "Adjustments" in `decomposition.md` and in `plan.json.adjustments`. The machine proposal stays in
`decomposition.proposed.json`, so a later reader can see what the agent changed.

Re-running `decompose` after `plan.json` is final writes only the proposal. Pass `--force` to replace
the plan. Per-unit decisions (`strategy`, `deferred`, `acceptance`, `fixtures`, `referenceTests`,
`notes`) carry over to units that keep their id.

Budgets live in `.porter/config.json` under `options.budgets` and can be overridden per run:

```text
porter.py decompose --max-loc 600 --max-symbols 12 --min-loc 20
```

## Order of work

1. **Foundation first.** Types, errors, constants and shared helpers.
2. **Tracer bullet second.** It proves the idiom map, the fixture harness, the review loop and the
   verifier on a thin slice before breadth work starts. If it fails, the strategy is wrong, and the
   implement skill returns to the strategy phase instead of pushing on.
3. **Wave by wave.** Highest risk first inside a wave.
4. **Entry points last.** They are mostly composition.
5. **Discovered units.** A unit found mid-implementation goes into `plan.json` with
   `discovered: true`, followed by `porter.py state plan-sync`. These count against the
   discovered-unit budget (default 5). When it runs out, the agent stops and asks the user.

## Cross-cutting concerns

Some concerns do not follow the symbol graph. `strategy.md` names each one with an owner unit:

- The error hierarchy and the error-to-result mapping belong to the foundation.
- Logging, telemetry and configuration loading become a boundary interface plus one adapter, injected
  and never imported globally by core units.
- Clock, randomness and environment are boundary interfaces, so fixtures stay deterministic.
- Serialization formats and wire compatibility get a dedicated unit with fixtures recorded as bytes.
- Public API packaging (index exports, CLI wiring, docs) is the last entry unit.

## Example

Real output for `python-slugify` 9.1.3 in draft mode:

```text
| # | Unit             | Layer | Wave | LOC | Depends on |
| 1 | legacy           | core  | 0    | 129 | -          |
| 2 | slugify (tracer) | core  | 1    | 196 | legacy     |
| 3 | special          | core  | 0    | 40  | -          |
| 4 | main             | entry | 2    | 86  | slugify    |

- shared helpers in slugify.slugify (DEFAULT_SEPARATOR) are used by several clusters:
  moved to the foundation layer
- foundation f:slugify.slugify (1 LOC, under the 30 LOC floor) folded into
  m:slugify.slugify, which every other consumer already depends on
- tracer bullet: slugify (closure legacy, slugify), the lowest-risk vertical slice
```
