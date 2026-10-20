# Decisions

Append-only log of human decisions for this port: gates, scope changes, authorizations and overrides.
`porter.py` appends an entry for every gate. Add an entry by hand for anything else a future reader
needs to know, newest last. One heading per decision, then a few lines: what was decided, by whom, why.

## 2026-10-20 deps gate: approved

deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the regex crate and rewrite lookarounds by hand; use fancy-regex only for a pattern that cannot be rewritten, and say which. serde_json as a dev-dependency for the parity harness is fine. (Package answer: Dict and list inputs map to serde_json::Value.) Both MAP candidates (regex 1.13.1, serde_json 1.0.154) are VERIFIED; no pattern needs fancy-regex.

## 2026-10-20 strategy gate: approved

strategy gate: approve the proposed units, order and budgets as written. (Package: the crate is named humps (library name humps), Rust stable, edition 2021, an idiomatic Rust API. Dict and list inputs map to serde_json::Value. The fixtures keep the Python call ids; the bindings translate.)
