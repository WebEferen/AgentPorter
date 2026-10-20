# Dependencies: compare-versions 6.1.1 -> rust

compare-versions has no runtime dependencies (package.json lists only devDependencies), so nothing needs a
MAP, SHIM or PORT decision. The six direct dev dependencies are a test runner, its type stubs, a coverage
wrapper and three build tools; all are DROPped and replaced by cargo's built-in tooling. The port's only
crate is `serde_json` as a dev-dependency for the parity harness, so the published crate keeps zero
runtime dependencies. There are no gate items from the dependency side.

## Runtime dependencies

None. `porter deps-graph` found 6 direct dependencies, all in scope `dev`, and 135 transitive ones, all
pulled in by those dev tools.

The source does use built-in JavaScript facilities that the Rust standard library does not cover one to
one. They are not npm dependencies, so they are decided in the strategy phase (idiom map), but the
crates involved were looked up here so the decision has evidence:

| Built-in | Used in | Rust option | Evidence |
| --- | --- | --- | --- |
| `RegExp` (`semver` regex, `validateStrict` regex, operator prefix regex) | src/utils.ts:7, src/validate.ts:34, src/satisfies.ts:19,30,36 | Hand-written matcher on `&str` (std only, per the user's preference); the `regex` crate is the verified fallback | cache/registry/crates/regex.json (1.13.1, MIT OR Apache-2.0, released 2026-07-15) |
| `parseInt`, `typeof`, string comparison | src/utils.ts:20-36 | std (`str::parse`, `char::is_ascii_digit`, `Ord for str`) | no crate needed |

## API deltas for MAP and SHIM

None: there are no MAP or SHIM decisions.

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| mocha | `cargo test` | Table-driven suites become `#[test]` functions over case tables in `tests/*.rs`. |
| @types/mocha | none | Type stubs only. |
| c8 | none | Coverage is not part of the contract; `cargo llvm-cov` can be used locally. |
| typescript | rustc (`cargo check --all-targets`) | The compiler is the type checker. |
| ts-node | none | `cargo test` compiles directly. |
| rollup | `cargo build` | The UMD bundle has no Rust counterpart. |
| (parity harness) | `serde_json` dev-dependency | Needed by knowledge/harnesses/rust/main.rs. Evidence: cache/registry/crates/serde_json.json (1.0.154, MIT OR Apache-2.0, released 2026-10-11). |

## Gate items

- None from postflight. For the record: no MAP or SHIM candidates exist, so the "every candidate is
  registry-verified" condition holds trivially; the only crate the port will add (`serde_json`, dev-only)
  was confirmed with `porter registry lookup`.
