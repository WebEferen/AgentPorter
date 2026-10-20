# Unit report: cases

Status: DONE. Parity: EXACT (1997/1997 fixtures, including 15 adversarial). Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20 (state keeps no task timestamps) |
| scaffold | not needed (split scaffolded the module) |
| implement | 2026-10-20 |
| mark-divergences | 2026-10-20: d1-cases (scule.go decodeCase) |
| port-tests | 2026-10-20 |
| wire-fixtures | 2026-10-20 |
| green | 2026-10-20 |
| review | 2026-10-20 (inline pass, budget) |
| apply-findings | 2026-10-20 (none to apply) |
| verify | 2026-10-20 |
| report | 2026-10-20 |
| commit | 2026-10-20 (policy: per-unit) |

## What was ported

- `scule.go`: CaseOptions, Words, PascalCase, CamelCase, KebabCase, SnakeCase, FlatCase, TrainCase, TitleCase.
- `cmd/porter-harness/bindings.go`: the 7 converter call ids. `cases_test.go`: reference rows and edge tests.

## Decisions and divergences

- DIVERGENCE(d1-cases): a lone surrogate left next to a joiner decodes as U+FFFD; rationale in `divergences.json`.

## Reference tests

PASS 44, OUT-OF-SCOPE 0 imported (test/types.test-d.ts is out of scope by user decision), DIVERGENCE 0, FAIL 0.

## Review findings

- Applied: none needed.
- Logged, not applied: `wordParts` falls back to reflect for named string and slice types (style; a type
  parameter conversion cannot express it under a union constraint); `minorWords` is a slice scan (fine at 18
  entries).

## Open questions

- None.
