# Unit report: satisfies-satisfies

Status: DONE. Parity: DIVERGENT. Attempts: 2 (attempt 2 had no code change; see below).

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20T20:09:39Z |
| scaffold | not needed |
| implement | 2026-10-20T20:09:39Z |
| mark-divergences | 2026-10-20T20:09:39Z |
| port-tests | 2026-10-20T20:10:17Z |
| wire-fixtures | 2026-10-20T20:10:17Z |
| green | 2026-10-20T20:10:35Z |
| review | 2026-10-20T20:11:13Z |
| apply-findings | after review (no code findings) |
| verify | attempt 1 GAP (1 divergence candidate); attempt 2 VERIFIED DIVERGENT |
| report | this file |
| commit | per-unit |

## What was ported

- src/compare_versions.rs (`compare_versions -> Result<Ordering, Error>`), src/compare.rs
  (`compare(v1, v2, operator: &str) -> Result<bool, Error>`), src/satisfies.rs
  (`satisfies -> Result<bool, Error>`), lib.rs re-exports, three harness bindings.
- tests/compare.rs, tests/satisfies.rs, tests/sort.rs: the test/compare.ts, test/satisfies.ts and test/sort.ts tables.
- src/utils.rs: removed the two `expect(dead_code)` attributes now that the helpers have callers.

## Decisions and divergences

- DIVERGENCE(non-string-arguments) markers on `compare` and `satisfies`. 33 fixtures divergent: the 32
  `*nonstring*` cases plus `edge-cmp-precedence-v1-before-v2` (`compare("foo", 42, ">")`, tagged nonstring but
  not named so). That case id was added to the divergence unattended (conservative: it is a non-string input,
  already covered by the approved decision; no behavior change). Recorded in `divergences.json` approvedBy.

## Reference tests

PASS 239, OUT-OF-SCOPE 2 (L160, L258 pass a JS function), DIVERGENCE 8 (non-string rows), FAIL 0.
test/compare.ts::L269 (the looped "same errors" test) was missed by the implementer; its three string rows were
ported after verify (`compare_throws_the_errors_of_compare_versions`); its non-string and function rows fall
under the divergence and the out-of-scope rule.

## Review findings

- Applied: none to code. Divergence bookkeeping for `edge-cmp-precedence-v1-before-v2` handled at verify.
- Logged, not applied: no separate DIVERGENCE marker on `compare_versions` (its guard lives in
  `validate_and_parse`, which carries one); two divergence entries share the id `non-string-arguments`, one per
  fixture-owning unit; mixed `is_ne()` / `== Ordering::Less` style.

## Open questions

- None. Fixtures: 3043 pass, 33 divergent, 0 failed of 3076 (35 adversarial cases added by verify, all pass).
