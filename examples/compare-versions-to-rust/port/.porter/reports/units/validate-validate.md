# Unit report: validate-validate

Status: DONE. Parity: DIVERGENT. Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | not recorded separately (implementer advanced straight to green) |
| scaffold | not needed (utils-utils built it) |
| implement | not recorded separately |
| mark-divergences | not recorded separately |
| port-tests | not recorded separately |
| wire-fixtures | not recorded separately |
| green | 2026-10-20T20:05:31Z |
| review | 2026-10-20T20:05:49Z |
| apply-findings | 2026-10-20T20:06:35Z |
| verify | 2026-10-20T20:07:58Z |
| report | this file |
| commit | per-unit |

## What was ported

- src/validate.rs: `validate` (first byte `v` or ASCII digit, then the shared `match_semver`) and
  `validate_strict` (hand-written std-only matcher for the semver.org 2.0.0 regex).
- src/lib.rs: `pub use validate::{validate, validate_strict}`.
- examples/porter_harness/bindings.rs: `compare-versions:validate`, `compare-versions:validateStrict`.
- tests/validate.rs: the test/validate.ts tables (L13-L27, L39-L69, L79-L119).

## Decisions and divergences

- DIVERGENCE(non-string-arguments): 16 `*nonstring*` fixtures, `&str` cannot carry them. Rationale in
  `divergences.json`.

## Reference tests

PASS 162, OUT-OF-SCOPE 1 (L12, a JS function), DIVERGENCE 5 (L7-L11, non-string), FAIL 0.

## Review findings

- Applied: none needed (no correctness or contract findings).
- Logged, not applied: `take_char`/`take_numeric`/`take_list` partly duplicate scanning helpers in utils.rs; kept
  separate because the strict grammar differs (leading zeros).

## Open questions

- None. Fixtures: 1188 pass, 16 divergent of 1204 (30 adversarial cases added by verify, all pass).
