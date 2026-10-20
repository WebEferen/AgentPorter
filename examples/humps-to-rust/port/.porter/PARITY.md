# Parity report

Upstream: pyhumps 3.8.0 (python, commit dc56af8dff5c).
Port: humps in rust. Evidence date: 2026-10-20. Harness run: verify-3.
Fixtures: 4627 cases, 4625 exact, 0 normalized, 2 divergent, 0 failed, 0 missing.

| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |
| --- | --- | --- | --- | --- | --- |
| cycle-humps | DIVERGENT | 4625 / 0 / 2 / 0 of 4627 | 18 / 18 | oracle-depth-cap | 7.485x |

Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under
the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).
ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known
mismatch remains.

## Intentional divergences

- **recursion-depth** (cycle-humps): the *_value walker has no nesting limit; Python raises RecursionError at about 990 levels Why: a runtime limit, not behavior callers rely on (leak recursion-depth); deep input is bounded by the caller's stack and by serde_json's 128-level parse limit. Planned in strategy.md (idiom map, Recursion row, and the scope gauntlet). No fixture records it.
- **unicode-version** (cycle-humps): Final_Sigma context in py_lower uses std's Unicode 17 Cased/Case_Ignorable sets; a sigma next to U+0295 or a character newly cased in Unicode 17 can lower differently from CPython 3.14 (decamelize("ʕΣ") is "ʕς" in Python, "ʕσ" here) Why: Review finding 2 residual. Per-character case mappings and the str predicates are matched to CPython 3.14 with generated tables; reproducing Final_Sigma would need CPython's Cased and Case_Ignorable sets, which unicodedata does not expose. No fixture input contains these characters.
- **oracle-depth-cap** (cycle-humps): two adversarial fixtures nested 100 levels deep record the oracle driver's truncation marker ({"$type": ..., "truncated": true} past MAX_DEPTH 64); the port returns the full result, which equals what humps returns when called directly Why: The mismatch is in the recorded expectation, not the port: knowledge/oracles/python/oracle.py caps serialization at 64 levels and the Rust harness does not. No normalization covers it and the verifier keeps mismatching adversarial cases as fixtures.
