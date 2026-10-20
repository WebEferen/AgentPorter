# Decisions

Append-only log of human decisions for this port: gates, scope changes, authorizations and overrides.
`porter.py` appends an entry for every gate. Add an entry by hand for anything else a future reader
needs to know, newest last. One heading per decision, then a few lines: what was decided, by whom, why.

## 2026-10-20 strategy gate: approved

approve the proposed units, order and budgets as written.

## 2026-10-20 strategy scope cuts: typed-input and empty-string divergences

unattended: the pre-approved answers cover units, order and budgets ("approve the proposed units, order and
budgets as written.") and the package shape ("a library with an idiomatic Go API. The fixtures keep the
JavaScript call ids; the bindings translate."). They do not name the two divergences in strategy.md's scope
gauntlet. Chosen: keep them, because a typed Go API cannot receive null, booleans, arrays, objects or
non-boolean `long` values (22 fixtures, `typed-input`), and the comma-ok `Parse` reports `ms("")` as "not a
duration" instead of throwing (2 fixtures, `empty-string`). This is the narrowest cut that honors the
explicit "idiomatic Go API" instruction; no other behavior is cut. Reversible later by adding an
error-returning parse variant. Decided by the agent in an unattended run.

## 2026-10-20 correction: typed-input covers 20 fixtures

The strategy scope-cut entry above says 22 fixtures for `typed-input`. Two of the 22 `dynamic-type` cases
(`edge.options.null`, `edge.options.long-null`) stay in scope through the binding and pass, so
`divergences.json` lists 20. Recorded by the agent in the unattended run.

## 2026-10-20 final verify: two adversarial cases added to typed-input

unattended: the final verify pass added `adv2.options.false-options` (options `false`) and
`adv2.invalid.nan-truthy-string-long` (NaN with `{long: "yes"}`). Both hit the binding rule the approved
strategy states for `typed-input` (options must be an object or null; `long` must be true, false, null or
absent) and surface as BindingError; the port's own `Format`/`FormatLong` are not involved. Chosen: list both
ids under the existing `typed-input` divergence rather than widen the binding beyond the strategy's rule.
porter refused `state unit set index GAP` (DONE is terminal), so no new implement attempt was opened; no
target code changed.
