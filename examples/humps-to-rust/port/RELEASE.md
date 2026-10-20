# Release checklist: humps

- [ ] Package metadata: name `humps`, description "Rust port of pyhumps 3.8.0", license (upstream is
      Unlicense; `Cargo.toml` has no `license` field yet), repository, keywords.
- [ ] Version policy relative to upstream: currently `0.1.0`; decide between mirroring 3.8 with a port patch
      number or semver of its own.
- [x] README section "Parity with upstream" generated from `.porter/PARITY.md`, evidence date 2026-10-20.
- [ ] Attribution: keep the upstream Unlicense notice (no requirement, but courteous).
- [ ] CHANGELOG entry for the first release.
- [ ] CI green on stable and on the declared `rust-version` (1.85).
- [ ] `publish = false` removed from `Cargo.toml`, then `cargo publish --dry-run` and `cargo publish`.
- [x] Divergences listed in the README, each with a one-line rationale.
