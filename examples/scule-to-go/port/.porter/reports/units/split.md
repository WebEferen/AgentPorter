# Unit report: split

Status: DONE. Parity: EXACT (987/987 fixtures, including 21 adversarial). Attempts: 1.

## Checklist

| Task | Done at |
| --- | --- |
| read-contract | 2026-10-20 (state keeps no task timestamps) |
| scaffold | 2026-10-20: go.mod, doc.go, LICENSE, CI workflow, cmd/porter-harness |
| implement | 2026-10-20 |
| mark-divergences | 2026-10-20: d1 (utf16.go), d2 (casing.go, after review) |
| port-tests | 2026-10-20 |
| wire-fixtures | 2026-10-20 |
| green | 2026-10-20 |
| review | 2026-10-20 |
| apply-findings | 2026-10-20 |
| verify | 2026-10-20 |
| report | 2026-10-20 |
| commit | 2026-10-20 (policy: per-unit) |

## What was ported

- `scule.go`: IsUppercase, SplitByCase, SplitByCaseWith, UpperFirst, LowerFirst.
- `split.go`, `casing.go`, `casing_table.go`, `utf16.go`: UTF-16 part split, full case mapping with a
  generated SpecialCasing table and Final_Sigma. `internal/gencasing` regenerates the table from Node.
- `cmd/porter-harness`: harness and bindings for the four split call ids.

## Decisions and divergences

- DIVERGENCE(d1): a part that holds a lone surrogate decodes with U+FFFD; rationale in `divergences.json`.
- DIVERGENCE(d2): single code point mappings and the Final_Sigma context come from Go's unicode tables
  (Unicode 15) instead of Node's (Unicode 17); no fixture affected; rationale in `divergences.json`.

## Reference tests

PASS 19, OUT-OF-SCOPE 0, DIVERGENCE 0, FAIL 0.

## Review findings

- Applied: Unicode version gap documented (doc.go, d2 entry and markers); invalid UTF-8 input documented in
  doc.go; SplitByCase doc now says a case change after an ASCII digit does not split.
- Logged, not applied: no Example functions yet (style); `//go:build ignore` keeps internal/gencasing out of
  `go vet ./...` (style); making gencasing emit single code point differences would close most of d2 (seam
  for later per strategy.md).

## Open questions

- Should d2 be closed by extending the generated table (strategy seam), or stay documented?
