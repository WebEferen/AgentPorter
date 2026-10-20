# Dependencies: scule -> go

scule has no runtime dependencies (`cache/deps-graph.json`: 9 direct, 0 runtime, 0 transitive). All nine
are dev, build, lint or test tools, so each one is DROP and maps to the Go toolchain below. The library's
runtime code uses only JavaScript built-ins (`String.prototype.toUpperCase`, `toLowerCase`, `slice`, `at`,
`Array.prototype.includes`, `join`, `filter`, two regexes: `/\d/` and the title-case exception list), which
the Go standard library absorbs (`strings`, `unicode`, `unicode/utf8`, `unicode/utf16`, `regexp`). There are
no gate items.

## Runtime dependencies

None. `package.json` has no `dependencies` or `peerDependencies`.

## API deltas for MAP and SHIM

None: no MAP or SHIM decisions.

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| vitest | `go test ./...` | Used only by `test/` (usage.json: tests-only). The runtime cases in `test/scule.test.ts` become oracle case specs. |
| @vitest/coverage-v8 | `go test -cover ./...` | Ships with Go. |
| eslint, eslint-config-unjs | `go vet ./...`, staticcheck (`honnef.co/go/tools` v0.8.2, `cache/registry` record) | No lint config to port. |
| prettier | `gofmt -l .` | Ships with Go. |
| typescript | `go build ./...` | The compiler is the type checker. The type tests in `test/types.test-d.ts` are out of scope. |
| unbuild | none | Go modules publish source; no bundling. |
| changelogen | none | Go releases are git tags. deps-graph hinted `test-tool`; it is release tooling. |
| @types/node | none | Type stubs only. |

## Gate items

None.
