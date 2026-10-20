# compare-versions-port

A Rust port of the [compare-versions](https://www.npmjs.com/package/compare-versions) npm package (6.1.1):
compare, sort, validate and range-match semver strings with exactly the rules of the original, quirks
included. No runtime dependencies.

```rust
use compare_versions_port::{compare, compare_versions, satisfies, validate, validate_strict};
use std::cmp::Ordering;

assert_eq!(compare_versions("10.1.8", "10.0.4"), Ok(Ordering::Greater));
assert_eq!(compare("10.1.8", "10.0.4", ">="), Ok(true));
assert_eq!(satisfies("1.1.0", "^1.0.0"), Ok(true));
assert!(validate("1.0.0-rc.1"));
assert!(!validate_strict("1.0"));

let mut versions = vec!["1.5.19", "1.2.3", "1.5.5"];
versions.sort_by(|a, b| compare_versions(a, b).unwrap());
assert_eq!(versions, ["1.2.3", "1.5.5", "1.5.19"]);
```

Functions that can fail return `Result<_, compare_versions_port::Error>`. Its `Display` text is the original's
error message (`Invalid argument not valid semver ('<input>' received)`,
`Invalid operator, expected one of >|>=|=|<=|<|!=`).

## Parity with upstream

- Upstream: compare-versions 6.1.1, commit 497a7e0c5fc0 (github.com/omichelsen/compare-versions).
- Evidence date: 2026-10-20. Fixtures were recorded from the pinned original on Node 24.18.0 and replayed through
  the Rust harness (`examples/porter_harness`). Full report: [docs/PARITY.md](docs/PARITY.md).
- Fixtures: 4288 cases, 4239 exact, 49 divergent (all one documented divergence), 0 failed.

| Unit | What it covers | Level | Fixtures exact / divergent of total | Reference tests pass / total |
| --- | --- | --- | --- | --- |
| satisfies-satisfies | `compare_versions`, `compare`, `satisfies` | DIVERGENT | 3051 / 33 of 3084 | 239 / 249 |
| validate-validate | `validate`, `validate_strict` | DIVERGENT | 1188 / 16 of 1204 | 87 / 93 |
| utils-utils | comparison core, `Error`, `CompareOperator` | ASSERTED | no fixtures of its own | 75 / 75 |
| src-index | crate root and public surface | ASSERTED | no fixtures of its own | 5 / 5 |

Reference tests that do not pass are non-string or JavaScript-function inputs from the upstream suite, resolved
as DIVERGENCE or OUT-OF-SCOPE.

Divergences:

- `non-string-arguments`: every function takes `&str`, so the original's behavior for numbers, `null`, objects,
  arrays and functions (returning `false` or throwing `TypeError`) cannot be expressed. This covers all 49
  divergent fixtures.

## License

MIT. Keeps the original copyright notice of compare-versions (Ole Michelsen); see [LICENSE](LICENSE).
