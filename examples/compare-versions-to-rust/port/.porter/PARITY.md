# Parity report

Upstream: compare-versions 6.1.1 (typescript, commit 497a7e0c5fc0).
Port: compare-versions-port in rust. Evidence date: 2026-10-20. Harness run: final.
Fixtures: 4288 cases, 4239 exact, 0 normalized, 49 divergent, 0 failed, 0 missing.

| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |
| --- | --- | --- | --- | --- | --- |
| satisfies-satisfies | DIVERGENT | 3051 / 0 / 33 / 0 of 3084 | 239 / 249 | non-string-arguments | 0.102x |
| src-index | ASSERTED | 0 / 0 / 0 / 0 of 0 | 5 / 5 | - | - |
| utils-utils | ASSERTED | 0 / 0 / 0 / 0 of 0 | 75 / 75 | - | - |
| validate-validate | DIVERGENT | 1188 / 0 / 16 / 0 of 1204 | 87 / 93 | non-string-arguments | 0.077x |

Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under
the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).
ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known
mismatch remains.

## Intentional divergences

- **non-string-arguments** (validate-validate): validate and validateStrict take &str; the source's runtime checks for non-string arguments (which return false) cannot be expressed. Why: Idiomatic Rust API decided at the strategy gate: string parameters are &str, so a number, null, object or array cannot be passed. The cases exist only because JavaScript is dynamically typed.
- **non-string-arguments** (satisfies-satisfies): compareVersions, compare and satisfies take &str; the source's TypeError paths for non-string versions, operators and ranges (including four V8-generated messages) cannot be reached. Why: Idiomatic Rust API decided at the strategy gate: string parameters are &str, so non-string values cannot be passed. The cases exist only because JavaScript is dynamically typed.
