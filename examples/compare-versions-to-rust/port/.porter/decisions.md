# Decisions

Append-only log of human decisions for this port: gates, scope changes, authorizations and overrides.
`porter.py` appends an entry for every gate. Add an entry by hand for anything else a future reader
needs to know, newest last. One heading per decision, then a few lines: what was decided, by whom, why.

## 2026-10-20 strategy gate: approved

strategy gate: approve the proposed units, order and budgets as written. Package: the crate is named compare-versions-port (library name compare_versions_port), Rust stable, edition 2021, an idiomatic Rust API (Result for errors). The fixtures keep the TypeScript call ids; the bindings translate.
