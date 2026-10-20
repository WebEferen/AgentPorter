# Rust ecosystem

| Field | Value |
| --- | --- |
| Registry | crates.io, <https://crates.io> |
| Registry adapter | `porter.py registry lookup --registry crates` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -A "$UA" "https://crates.io/api/v1/crates/serde"
curl -s -A "$UA" "https://crates.io/api/v1/crates/slug"
curl -s -A "$UA" "https://crates.io/api/v1/crates?q=slugify&per_page=10"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `GET https://crates.io/api/v1/crates/<name>` | `crate.description`, `crate.repository` |
| Latest version and date | same | `crate.max_stable_version`, `crate.updated_at` |
| License | same | `versions[].license` (pick the entry whose `num` equals `max_stable_version`) |
| Yanked | same | `versions[].yanked` |
| Adoption signal | same | `crate.downloads` (all time), `crate.recent_downloads` (last 90 days) |
| Search | `GET https://crates.io/api/v1/crates?q=<q>&per_page=10` | `crates[]`: `name`, `max_stable_version`, `description`, `downloads`, `recent_downloads`, `updated_at`, `exact_match`; `meta.total` |

A User-Agent is required. The same request without one returned 403 with a
message asking for a User-Agent that identifies the bot and gives contact
details. Keep to about one request per second (crates.io crawler policy).

What the recorded responses showed:

- `serde`: `max_stable_version` `1.0.229`, `updated_at`
  `2026-07-18T23:05:13.266456Z`, `downloads` 1,558,311,361,
  `recent_downloads` 371,108,586, 316 entries in `versions`, 3 of them yanked.
- `crate.updated_at` matched the newest version's `created_at`. For the date
  of a specific version, use `versions[].created_at`.
- `versions[].license` is an SPDX expression (`MIT OR Apache-2.0`). Older
  releases use the slash form `MIT/Apache-2.0`, which means OR. Some old serde
  releases had `null`.
- `versions[]` came newest first, but match by `num` instead of position.
- `versions[]` also carries `yank_message`, `rust_version` (declared MSRV,
  `"1.56"` for serde, `null` for slug), `edition`, `features`, `has_lib`,
  `bin_names` and `downloads`. The adapter does not read them; they help when
  judging a candidate.
- `crate.max_version` and `crate.newest_version` include pre-releases;
  `max_stable_version` does not.
- `crate.trustpub_only` (boolean) shows whether the crate accepts only
  trusted publishing.
- Search results have `versions: null`, so they carry no license. Look up
  each candidate. `exact_match` is `true` when the name equals the query.
- Not found: HTTP 404 with
  ``{"errors":[{"detail":"crate `<name>` does not exist"}]}``.
- Outside the adapter: `GET https://crates.io/api/v1/crates/<name>/reverse_dependencies`
  returned `meta.total` (157 for slug).

## 2. Maturity signals

| Signal | Where | How to read it |
| --- | --- | --- |
| Downloads | `crate.downloads`, `crate.recent_downloads` | Prefer the 90-day figure; all-time totals favor old crates. |
| Release cadence | `versions[].created_at` | Count releases in the last 12 months. |
| Yanked | `versions[].yanked`, `yank_message` | A yanked latest version needs the message read. |
| Pre-1.0 | version number | Many core crates stay `0.x` for years; Cargo treats a `0.x` minor bump as breaking. Not a negative on its own. |
| MSRV | `versions[].rust_version` | Must be at or below the port's MSRV. |
| Dependents | `reverse_dependencies` `meta.total` | Not read by the adapter. |
| Features | `versions[].features` | Check `default` and whether `std` can be turned off when the port needs `no_std`. |

Missing from crates.io: security advisories. Use the RustSec database through
`cargo audit` or `cargo deny check advisories` inside a project. docs.rs builds
documentation for every release; a missing or failed docs build is worth a
look.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `Cargo.toml` | Package metadata and dependency ranges | Yes: `[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`, `[target.<cfg>.dependencies]` |
| `Cargo.lock` | Locked versions of the whole graph | Yes: locked versions, including transitive ones |

Scopes:

| Table | Scope |
| --- | --- |
| `[dependencies]` | runtime |
| `[dev-dependencies]` | dev (tests, examples, benches) |
| `[build-dependencies]` | build (`build.rs`) |
| `[target.'cfg(...)'.dependencies]` | runtime on matching platforms only |

Optional dependencies are `[dependencies]` entries with `optional = true`;
a feature in `[features]` turns them on. `default-features = false` and
`features = [...]` change what a dependency compiles. In a workspace,
`dep = { workspace = true }` takes its version from
`[workspace.dependencies]` in the root Cargo.toml. A `package = "real-name"`
key renames a dependency. In code, hyphens in crate names become underscores
(`unicode-segmentation` is used as `unicode_segmentation`).

## 4. Package layout

- `src/lib.rs` is the library root; `src/main.rs` is the default binary;
  `src/bin/*.rs` adds more binaries.
- Unit tests live in a `#[cfg(test)] mod tests` block inside each source
  file. `tests/*.rs` are integration tests, each built as its own crate
  against the public API.
- `examples/`, `benches/` and `build.rs` sit at the package root.
- Doc comments (`///`) hold doc tests that `cargo test` runs.
- Visibility: `pub` for the public API, `pub(crate)` for crate-internal.

```toml
[package]
name = "example-slug"
version = "1.0.0"
edition = "2024"
rust-version = "1.85"
description = "Slugify strings"
license = "MIT OR Apache-2.0"
repository = "https://github.com/org/example-slug"

[dependencies]
deunicode = "1"

[dev-dependencies]
proptest = "1"
```

## 5. Test runners

| Command | Use |
| --- | --- |
| `cargo test` | Unit, integration and doc tests |
| `cargo test --all-features` | Include optional features |
| `cargo nextest run` | Faster runner; does not run doc tests, so add `cargo test --doc` |
| `cargo +1.85 test` | Check the declared MSRV with rustup |

Common test crates: proptest (property tests), insta (snapshots), criterion
(benchmarks). cargo-msrv finds the lowest toolchain that builds the crate.

## 6. Lint and format

| Tool | Command | Notes |
| --- | --- | --- |
| rustfmt | `cargo fmt --all -- --check` | Config in `rustfmt.toml`. |
| Clippy | `cargo clippy --all-targets --all-features -- -D warnings` | Lint levels can be set in the `[lints]` table of Cargo.toml. |
| cargo-deny | `cargo deny check` | Licenses, advisories, banned and duplicate crates. |
| cargo-semver-checks | `cargo semver-checks` | Catches breaking API changes before a release. |

## 7. Type checking

The compiler is the type checker. `cargo check --all-targets` is the fast
path. `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps` checks documentation
and intra-doc links.

## 8. Build and publish

- `cargo build --release` builds; `cargo package --list` shows the files that
  will be uploaded.
- `cargo publish --dry-run`, then `cargo publish`. crates.io requires
  `description` and either `license` or `license-file`.
- Authenticate with `cargo login <token>`, or from CI with trusted publishing
  (`rust-lang/crates-io-auth-action` in GitHub Actions exchanges an OIDC token
  for a short-lived publish token).
- Releases cannot be overwritten. `cargo yank --version 1.2.3` stops new
  lockfiles from selecting a version; existing lockfiles still download it.
  `cargo yank --version 1.2.3 --undo` reverses it.
- docs.rs builds and hosts documentation for each published version.

## 9. Runtime version policy

Rust ships a stable release every six weeks, and the Rust project supports
only the latest stable. On 2026-10-20 the stable channel manifest
(`https://static.rust-lang.org/dist/channel-rust-stable.toml`) listed rustc
1.99.1.

A crate declares support in two fields:

- `edition` sets the language edition (`2015`, `2018`, `2021`, `2024`).
  Edition 2024 needs Rust 1.85 or later.
- `rust-version` is the MSRV. Cargo refuses to build the crate with an older
  toolchain. Resolver 3 (the default with edition 2024) prefers dependency
  versions whose `rust-version` fits.

For a new port, use `edition = "2024"`, set `rust-version` to the oldest
toolchain you test (at least `1.85`), and run CI on that version and on
stable.

## 10. License fields

- Cargo.toml `license` holds an SPDX expression; the ecosystem default is
  `MIT OR Apache-2.0`. `license-file` points to a file for licenses without an
  SPDX id.
- Registry: `versions[].license` per version. The `crate` object has no
  license field. Expect `null` when a crate uses `license-file` or on old
  releases.
- Treat the slash form (`MIT/Apache-2.0`) as OR.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/rust/` does not exist yet (wanted). A Rust
source needs a small binary that reads cases as JSON on stdin and prints
results.

Fixture harness: `knowledge/harnesses/rust/` (see its README.md).
