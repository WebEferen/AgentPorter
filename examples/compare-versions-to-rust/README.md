# compare-versions: TypeScript to Rust

[compare-versions](https://github.com/omichelsen/compare-versions) compares, sorts, validates and
range-matches semver strings. This is version 6.1.1 ported to Rust as the crate `compare-versions-port`
(library `compare_versions_port`), with no runtime dependencies.

- [original/](original/): `src/` and `test/` of compare-versions 6.1.1 (commit `497a7e0`), with its
  `package.json`, README and license.
- [port/](port/): the crate, the ported upstream tests in `tests/`, the parity harness in
  `examples/porter_harness` and the `.porter/` workspace.

## Original and port

```ts
import { compareVersions, compare, satisfies, validate, validateStrict } from "compare-versions";

compareVersions("10.1.8", "10.0.4"); // 1
compare("10.1.8", "10.0.4", ">=");   // true
satisfies("1.1.0", "^1.0.0");        // true
validate("1.0.0-rc.1");              // true
validateStrict("1.0");               // false
["1.5.19", "1.2.3", "1.5.5"].sort(compareVersions); // ["1.2.3", "1.5.5", "1.5.19"]
```

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

Functions that can throw in the original return `Result<_, Error>`, and the error's `Display` text is the
original's message.

## Result

DIVERGENT. Of 4288 recorded cases, 4239 match exactly and 49 differ on purpose, all under one divergence.
None fail. 406 of 422 upstream tests are ported and pass; the other 16 pass numbers, `null`, objects or
JavaScript functions as arguments. Full report: [port/docs/PARITY.md](port/docs/PARITY.md).

- `non-string-arguments` (49 cases): every function takes `&str`, so the original's behavior for
  non-string arguments (returning `false`, or throwing `TypeError`) can't be expressed.

`utils-utils` and `src-index` have no fixtures of their own (internal helpers and the re-exporting entry
point), so their ported tests carry the evidence and they grade as ASSERTED.

## How it was made

One unattended session (see [how the examples were made](../README.md#how-they-were-made)): $19.76,
138 turns, 69 minutes. Pre-approved answers:

```text
- deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the Rust
  standard library; serde_json as a dev-dependency for the parity harness is fine.
- strategy gate: approve the proposed units, order and budgets as written.
- Anything about the package: the crate is named compare-versions-port (library name compare_versions_port),
  Rust stable, edition 2021, an idiomatic Rust API (Result for errors). The fixtures keep the TypeScript call
  ids; the bindings translate.
```

Where the run left the script:

- Node can't run this source unbuilt (it imports types without `import type`), so the contract step
  compiled it with the upstream's own `tsc` settings into `.porter/oracle/build/` and pointed the package
  entry at that build with `.porter/oracle/driver/source-entry-hook.mjs`. The build is git-ignored; the
  contract has the commands.
- porter could not import `cargo test` results yet, so the agent wrote `.porter/tools/cargo_junit.py`.
  `porter parity reftests cargo` does this now.
- After the first implementer and the contract extractor, the agent ran the remaining reviewers,
  verifiers and implementers on Sonnet 5.5 to save budget.
- The doubled unit ids (`utils-utils`, `validate-validate`) come from a naming bug in the decomposer.
  Renaming them mid-run would have meant moving fixtures, so they stayed.
- One fixture whose id the divergence's glob missed was added to `non-string-arguments` with an
  "unattended:" note.

## Check it

```sh
cd port
cargo test
cargo run --example porter_harness -- --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

## License

MIT, from compare-versions (Ole Michelsen). `original/` and `port/` both keep the notice.
