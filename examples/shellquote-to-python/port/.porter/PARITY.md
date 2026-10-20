# Parity report

Upstream: github.com/kballard/go-shellquote (go, commit 95032a82bc51).
Port: shellquote in python. Evidence date: 2026-10-20. Harness run: verify-final-v1.
Fixtures: 1083 cases, 1083 exact, 0 normalized, 0 divergent, 0 failed, 0 missing.

| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |
| --- | --- | --- | --- | --- | --- |
| root | EXACT | 1083 / 0 / 0 / 0 of 1083 | 29 / 29 | - | 3.1x |

Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under
the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).
ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known
mismatch remains.
