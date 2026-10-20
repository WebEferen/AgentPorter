# Unit report: src-index

Status: DONE. Parity: ASSERTED. Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20T20:16:31Z |
| scaffold | not needed |
| implement | 2026-10-20T20:16:43Z |
| mark-divergences | 2026-10-20T20:16:43Z (none new) |
| port-tests | 2026-10-20T20:16:52Z |
| wire-fixtures | 2026-10-20T20:16:52Z (no fixtures) |
| green | 2026-10-20T20:16:52Z |
| review | 2026-10-20T20:17:05Z |
| apply-findings | 2026-10-20T20:18:02Z |
| verify | 2026-10-20T20:18:52Z |
| report | this file |
| commit | per-unit |

## What was ported

- src/lib.rs: crate docs with a doc-test example for every function, the kept quirks and the non-string
  divergence. Public surface: `compare`, `compare_versions`, `satisfies`, `validate`, `validate_strict`,
  `CompareOperator`, `Error`; every module is private.
- tests/public_api.rs: imports every public name and checks the harness binds all five call ids.

## Decisions and divergences

- None new. `Error` is exported in addition to src/index.ts's names because the Result API needs it (strategy).

## Reference tests

PASS 5 (`src/index.ts::L1` to `L5`, assertion plan of the unit contract), OUT-OF-SCOPE 0, DIVERGENCE 0, FAIL 0.

## Review findings

- Applied: crate doc now says segments and pre-release identifiers compare by their `parseInt` prefix (it said
  "as numbers when both are numeric", narrower than the code).
- Logged, not applied: the docs could mention the accepted `v^~<>=` prefix run.

## Open questions

- "Exactly these names" is not asserted (an extra public item would not fail a test).
