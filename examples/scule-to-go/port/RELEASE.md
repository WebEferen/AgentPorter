# Release checklist: github.com/agentporter-examples/scule

- [x] Package metadata: module `github.com/agentporter-examples/scule`, package doc in doc.go ("Go port of
      the JavaScript package scule 1.3.0"), MIT license kept from upstream.
- [ ] Version policy relative to upstream: tag `v1.3.0` to mirror upstream; port-only fixes bump the patch.
- [x] README section "Parity with upstream" generated from `.porter/PARITY.md`, evidence date 2026-10-20.
- [x] Attribution: upstream LICENSE (scule authors) kept at the module root.
- [ ] CHANGELOG entry for the first release.
- [ ] CI green on Go 1.22 and the current stable (`.github/workflows/ci.yml`; tests also pass locally on
      go1.26.0 and GOTOOLCHAIN=go1.22.0).
- [ ] Publish: `go mod tidy`, `git tag v1.3.0 && git push origin v1.3.0`, then
      `GOPROXY=proxy.golang.org go list -m github.com/agentporter-examples/scule@v1.3.0`.
- [x] Divergences listed in the README, each with a one-line rationale (d1, d1-cases, d2).
