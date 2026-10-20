# Release checklist: compare-versions-port

- [ ] Package metadata: name `compare-versions-port` and description ("Rust port of the compare-versions npm
      package ...") are set; license `MIT` matches upstream; `rust-version = "1.81"`. Still missing:
      `repository`, `keywords` (`semver`, `version`, `compare`), `categories`, and a `readme` field.
- [ ] Version policy relative to upstream: currently `0.1.0`. Decide between mirroring upstream (`6.1.1` plus a
      port patch number) and an independent semver line; record the choice in the README.
- [x] README section "Parity with upstream" generated from `.porter/PARITY.md`, evidence date 2026-10-20.
- [x] Attribution: LICENSE keeps "Copyright (c) 2015-2021 Ole Michelsen" with the MIT text.
- [ ] CHANGELOG entry for the first release (no CHANGELOG.md yet).
- [ ] CI green on the supported toolchains: no workflow yet. Add jobs for `cargo fmt --all -- --check`,
      `cargo clippy --all-targets -- -D warnings`, `cargo test`, `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps`
      and the parity harness, on stable and on 1.81. Locally green on rustc 1.93.1.
- [ ] Publish: `cargo package --list` (check that `.porter/` is excluded, add `exclude = [".porter/", "docs/"]` or an
      `include` list to Cargo.toml), `cargo publish --dry-run`, then `cargo publish`.
- [x] Divergences listed in the README with a one-line rationale (`non-string-arguments`).
