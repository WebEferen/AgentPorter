# Go ecosystem

| Field | Value |
| --- | --- |
| Registry | Go module proxy <https://proxy.golang.org>, docs at <https://pkg.go.dev>, metadata from <https://deps.dev> |
| Registry adapter | `porter.py registry lookup --registry go` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -A "$UA" "https://proxy.golang.org/github.com/gosimple/slug/@latest"
curl -s -A "$UA" "https://proxy.golang.org/github.com/gosimple/slug/@v/list"
curl -s -A "$UA" "https://proxy.golang.org/github.com/!burnt!sushi/toml/@latest"
curl -s -A "$UA" "https://api.deps.dev/v3/systems/go/packages/github.com%2Fgosimple%2Fslug"
curl -s -A "$UA" "https://api.deps.dev/v3/systems/go/packages/github.com%2Fgosimple%2Fslug/versions/v1.15.0"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `GET https://proxy.golang.org/<escaped-module>/@latest` | `Origin.URL` (repository), `Origin.VCS`, `Origin.Ref` (tag; not always present) |
| Latest version and date | same | `Version`, `Time` |
| Version list | `GET https://proxy.golang.org/<escaped-module>/@v/list` | Plain text, one tagged version per line |
| Versions with dates | `GET https://api.deps.dev/v3/systems/go/packages/<urlencoded-module>` | `versions[].versionKey.version`, `versions[].publishedAt`, `versions[].isDefault`, `versions[].isDeprecated` |
| License | `GET https://api.deps.dev/v3/systems/go/packages/<urlencoded-module>/versions/<v>` | `licenses` (SPDX list) |
| Advisories and links | same | `advisoryKeys[].id`, `links[]` (`label`, `url`), `isDeprecated`, `deprecatedReason` |
| Adoption signal | none in the adapter | Go has no download counts; see pkg.go.dev below |
| Search | none in the adapter | See pkg.go.dev below |

Module path escaping for the proxy: every uppercase letter becomes `!`
followed by the lowercase letter. `github.com/BurntSushi/toml` is requested as
`github.com/!burnt!sushi/toml`. The unescaped path returned 404 with
`bad request: invalid escaped module path "github.com/BurntSushi/toml"`.
deps.dev takes the original case, URL-encoded as one path segment
(`github.com%2FBurntSushi%2Ftoml`); the `!` form returned 404
`version not found`.

What the recorded responses showed:

- `@latest` for gosimple/slug:
  `{"Version":"v1.15.0","Time":"2024-12-23T19:03:40Z","Origin":{"VCS":"git","URL":"https://github.com/gosimple/slug","Hash":"62efd7f...","Ref":"refs/tags/v1.15.0"}}`.
  The BurntSushi/toml response had no `Ref`.
- `@v/list` returned 24 tags in no particular order. Sort by semver before
  use. It lists tags only, no pseudo-versions.
- The deps.dev package endpoint returned 73 versions for the same module
  because it includes pseudo-versions. `isDefault: true` marks the version
  deps.dev treats as latest.
- The deps.dev version endpoint: `licenses` `["MPL-2.0"]`, `advisoryKeys`
  `[]`, `links` `[{"label": "SOURCE_REPO", "url": "https://github.com/gosimple/slug"}]`.
  gin-gonic/gin v1.6.0 listed GHSA ids such as `GHSA-2c4m-59x9-fr2g`.
  golang/protobuf v1.5.4 had `isDeprecated: true` and `deprecatedReason`
  `Module deprecated: Use the "google.golang.org/protobuf" module instead.`
- Major versions are separate module paths: `github.com/go-chi/chi/v5`
  returned `v5.5.0`, while `github.com/go-chi/chi` returned `v1.5.5`.
- Not found: proxy 404 with a plain-text body starting
  `not found: module ...`; deps.dev 404 with plain text `package not found`
  or `version not found`. Neither is JSON.

pkg.go.dev JSON API (not called by the adapter). It answered on the date
above and is documented at <https://pkg.go.dev/v1/api> (rate limit 45 requests
per second per IP block). Paths use the original case, not the `!` form.

| Endpoint | Fields seen |
| --- | --- |
| `GET https://pkg.go.dev/v1/search?q=<q>&limit=10` | `items[]`: `packagePath`, `modulePath`, `version`, `synopsis`, `importedByCounts.packages`, `importedByCounts.modules` (`-1` when unknown); `total` |
| `GET https://pkg.go.dev/v1/versions/<module>` | `items[]`: `version`, `commitTime`, `latestVersion`, `deprecated`, `deprecationReason`, `retracted`, `retractionReason` |
| `GET https://pkg.go.dev/v1/package/<path>?licenses=true` | `licenses[]`: `types`, `filePath`, `contents` |

Search results are packages, so several can share one module. The adapter has
no Go search: use the pkg.go.dev search above or web search, then confirm
each module with `@latest` before naming it.

## 2. Maturity signals

| Signal | Where | How to read it |
| --- | --- | --- |
| Last release | `@latest` `Time` | Go libraries often go years between tags when finished. |
| Cadence | deps.dev `versions[].publishedAt` | Ignore pseudo-versions when counting releases. |
| Stability | version number | `v0.x` makes no compatibility promise. `v2+` needs a `/vN` path suffix. `+incompatible` tags predate modules. |
| Untagged | only pseudo-versions (`v0.0.0-<date>-<hash>`) | Nothing to pin but a commit; weak candidate. |
| Deprecation | deps.dev `isDeprecated`, pkg.go.dev `deprecated` | From a `// Deprecated:` comment on the go.mod `module` line. |
| Retraction | pkg.go.dev `/v1/versions` `retracted` | From `retract` directives in go.mod. |
| Advisories | deps.dev `advisoryKeys` | GHSA ids; run `govulncheck` in a project for call-level results. |
| Importers | pkg.go.dev `importedByCounts.packages` | The closest thing Go has to an adoption count. |

Missing: download counts (the Go ecosystem does not publish them). Check the
standard library and `golang.org/x/...` modules before taking a third-party
dependency; Go's standard library covers HTTP, JSON, templates, logging
(`log/slog`) and regular expressions (RE2 syntax: no backreferences or
lookaround).

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `go.mod` | Module path, `go` and `toolchain` lines, `require`, `replace`, `exclude`, `retract`, `tool` | Yes: `require` lines and blocks; `// indirect` marks a transitive dependency |
| `go.sum` | Checksums of every module version in the build graph | No |

Scopes: go.mod has no runtime or dev split. Test-only modules sit in
`require` like any other. Go 1.24 added `tool` directives for dev tools; their
modules also appear in `require`, and `deps-graph` does not separate them.
After `go mod tidy`, go.mod records the selected version of every module that
provides a package to the build, so these versions act as locked versions.
`replace` directives can redirect a module to a fork or a local path; read
go.mod for them.

An import path such as `github.com/x/y/sub` belongs to the module whose path
is the longest matching prefix in `require` (`github.com/x/y`).

## 4. Package layout

- `go.mod` at the module root; one package per directory.
- `internal/` packages are importable only from inside the parent tree.
- Binaries live in `cmd/<name>/main.go`.
- Tests sit next to the code in `*_test.go`. Package `foo_test` gives
  black-box tests. `testdata/` is ignored by the go tool and holds fixtures.
- `example_test.go` holds `ExampleXxx` functions, shown on pkg.go.dev and run
  as tests when they end with an `// Output:` comment.
- `doc.go` holds the package comment. Exported names start with an uppercase
  letter.

## 5. Test runners

| Command | Use |
| --- | --- |
| `go test ./...` | All tests; add `-race` in CI and `-count=1` to skip the cache |
| `go test -run 'TestName/sub' ./pkg` | Focus on one test or subtest |
| `go test -fuzz=FuzzName ./pkg` | Native fuzzing |
| `go test -bench=. ./pkg` | Benchmarks |
| `go test -cover ./...` | Coverage |

Table-driven tests with `t.Run` are the norm. `github.com/google/go-cmp`
prints readable diffs; `github.com/stretchr/testify` is common but optional.
`testing/synctest` helps test concurrent code deterministically.

## 6. Lint and format

| Tool | Command | Notes |
| --- | --- | --- |
| gofmt | `gofmt -l .` (lists unformatted files) | Required; `go fmt ./...` rewrites. gofumpt is a stricter superset. |
| go vet | `go vet ./...` | Ships with Go. |
| staticcheck | `staticcheck ./...` | `honnef.co/go/tools`, release 2026.2.x. |
| golangci-lint v2 | `golangci-lint run` | Runs many linters; `.golangci.yml` needs `version: "2"`. |
| govulncheck | `govulncheck ./...` | `golang.org/x/vuln`; reports advisories on reachable code. |

Pin tools in go.mod with `go get -tool honnef.co/go/tools/cmd/staticcheck`
and run them with `go tool staticcheck ./...`.

## 7. Type checking

The compiler is the type checker: `go build ./...` and `go vet ./...`. There
is no separate tool. Generics exist since Go 1.18.

## 8. Build and publish

- There is no upload step. Publishing means pushing a semver tag:
  `git tag v1.2.3 && git push origin v1.2.3`. A module in a subdirectory
  uses a prefixed tag such as `sub/v1.2.3`.
- Make the version visible on the proxy and pkg.go.dev:
  `GOPROXY=proxy.golang.org go list -m example.com/mod@v1.2.3`.
- Run `go mod tidy` before tagging.
- Tags are effectively immutable: the checksum database (sum.golang.org)
  records the first content seen for each version.
- v2 and later: change the module path to `example.com/mod/v2` and tag
  `v2.0.0`.
- Withdraw a version: add `retract v1.2.3 // reason` to go.mod and tag a new
  version. Deprecate a module: put `// Deprecated: use X instead.` directly
  above the `module` line and tag a release.

## 9. Runtime version policy

Each Go major release is supported until two newer major releases exist. On
2026-10-20, `https://go.dev/dl/?mode=json` listed go1.27.3 and go1.26.10 as
the stable, supported releases.

The `go` line in go.mod (`go 1.26`) is the minimum Go version. Go 1.21 and
later toolchains that are older than that line refuse to build the module, or
download a matching toolchain when `GOTOOLCHAIN=auto` (the default). A
library's `go` line forces every consumer to at least that version, so set it
to the oldest version you test and do not raise it without need. The optional
`toolchain` line only suggests a toolchain for work inside the module. For a
new port, use `go 1.26` and run CI on 1.26 and 1.27, unless the user names an
older minimum: then that version goes in the `go` line and CI.

## 10. License fields

- go.mod has no license field. The license is the LICENSE file at the module
  root.
- Registry: deps.dev `licenses` (SPDX list) on the version endpoint;
  pkg.go.dev `licenses[].types` and `isRedistributable` (pkg.go.dev hides
  documentation for modules whose license it cannot accept).
- Values seen: gosimple/slug `MPL-2.0`, BurntSushi/toml `MIT`,
  golang/protobuf `BSD-3-Clause`.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/go/` (see its README.md).

Fixture harness: `knowledge/harnesses/go/` (see its README.md).
