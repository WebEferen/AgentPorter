# Dependencies: ms -> go

ms 2.1.3 has no runtime dependencies (`cache/deps-graph.json`: 6 direct, 0 runtime). The six direct
dependencies are dev tools: a test runner, an assertion library, a linter, a formatter and two git hook
helpers. None is ported; each maps to Go's own tooling. The 184 transitive packages all sit under these dev
tools. The port uses only the Go standard library (`strconv`, `math`, `strings`, `time` at most), so there
are no MAP or SHIM candidates and nothing to verify against the Go module proxy. There are no gate items.

## Runtime dependencies

| Dependency | Version | Role | Used surface | Decision | Candidate | Confidence | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| (none) | | | | | | | `cache/deps-graph.json` counts.directRuntime = 0 |

## API deltas for MAP and SHIM

None: there are no MAP or SHIM decisions.

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| mocha 4.0.1 | `go test` | Table-driven tests with `t.Run`; run `go test ./... -count=1`. |
| expect.js 0.3.1 | `testing` (standard library) | Used only in `tests.js` (87 call sites, `cache/usage.json`). Plain `t.Errorf` comparisons. |
| eslint 4.18.2 | `go vet` | `go vet ./...`; staticcheck is optional. |
| prettier 2.0.5 | `gofmt` | `gofmt -l .` must print nothing. |
| husky 0.14.3 | none | Git hook installer; CI runs the same checks. |
| lint-staged 5.0.0 | none | Pre-commit runner; gofmt and go vet replace it. |

## Gate items

- None. Every decision is DROP for a dev-only tool with HIGH confidence.
