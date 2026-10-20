# Unit report: utils-utils

Status: DONE. Parity: ASSERTED. Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20T19:51:19Z |
| scaffold | 2026-10-20T19:52:42Z |
| implement | 2026-10-20T19:58:20Z |
| mark-divergences | 2026-10-20T19:58:20Z (marker added after review, 20:01) |
| port-tests | 2026-10-20T19:58:20Z |
| wire-fixtures | 2026-10-20T19:58:37Z (no fixtures; empty bindings list) |
| green | 2026-10-20T19:58:47Z |
| review | 2026-10-20T20:00:13Z |
| apply-findings | 2026-10-20T20:01:51Z |
| verify | 2026-10-20T20:03:09Z |
| report | this file |
| commit | per-unit |

## What was ported

- Scaffold: Cargo.toml (compare-versions-port, lib compare_versions_port, edition 2021, rust-version 1.81, MIT,
  serde_json dev-dependency), LICENSE (keeps Ole Michelsen's notice), .gitignore, src/lib.rs,
  examples/porter_harness/{main.rs,bindings.rs}.
- src/utils.rs: public `Error` (InvalidVersion, InvalidOperator) and `CompareOperator` (FromStr, Display);
  crate-private semver matcher (`match_semver`, `SemverMatch`), `validate_and_parse`, `compare_segments`,
  `parse_int` (JS parseInt to f64), `js_number_to_string`, `is_js_whitespace`.

## Decisions and divergences

- DIVERGENCE(non-string-arguments) at `validate_and_parse`: the `typeof` guard has no counterpart with `&str`.
  Entries in `divergences.json` for validate-validate and satisfies-satisfies, which own the `*nonstring*`
  fixtures.

## Reference tests

PASS 75, OUT-OF-SCOPE 0, DIVERGENCE 0, FAIL 0 (14 Rust unit tests; tags imported through
`.porter/tools/cargo_junit.py`). The tags mix `test/compare.ts::L<n>` ids with fixture case ids that the tests
mirror.

## Review findings

- Applied: DIVERGENCE marker and divergences.json entries; `rust-version = "1.81"` because `#[expect]` needs it.
- Logged, not applied: byte vs UTF-16 string order note (unreachable, the matcher only passes ASCII);
  `compare_segments` could take slices instead of iterators (style); `#[expect(dead_code)]` on
  `validate_and_parse` and `compare_segments` must be removed by the first unit that calls them;
  lib.rs already re-exports `Error` and `CompareOperator` (needed to build, src-index finalizes it).

## Open questions

- None. The comparison core is graded by fixtures only once satisfies-satisfies lands.
