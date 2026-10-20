# Strategy: scule -> go (github.com/agentporter-examples/scule)

One Go package, `scule`, standard library only, `go 1.22`. Two units: `split` (isUppercase, splitByCase,
upperFirst, lowerFirst plus the internal UTF-16 and full case-mapping helpers) is the tracer and proves the
scaffold, harness, bindings and parity path on the hardest semantics; `cases` (the seven converters and
`CaseOptions`) builds on it. JavaScript string semantics are reproduced exactly where the fixtures observe
them: parts are kept as UTF-16 code units internally and case mapping follows JavaScript's full Unicode
mapping, not Go's simple `unicode.ToUpper`. At the gate you approve the two units and their order, the
public Go API below, the one documented divergence (lone surrogates), and the budgets.

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| split | core | code port | splitByCase is a small state machine whose exact edge behavior (UTF-16 length check, last-unit move, digit neutrality, separator reset) is the contract; follow the source logic step by step. |
| cases | core | contract port | Thin compositions over split; write them natively from the unit contract. |

## Public Go API

```go
package scule

type CaseOptions struct{ Normalize bool }

// Words is a string to split by case, or parts that are used as is.
type Words interface{ ~string | ~[]string }

func IsUppercase(s string) (upper, ok bool)            // ok == false where JS returns undefined (an ASCII digit in s)
func SplitByCase(s string) []string                     // default separators - _ / .
func SplitByCaseWith(s string, separators []string) []string // separators used as given; empty means none
func UpperFirst(s string) string
func LowerFirst(s string) string

func PascalCase[W Words](w W, opts ...CaseOptions) string
func CamelCase[W Words](w W, opts ...CaseOptions) string
func KebabCase[W Words](w W, joiner ...string) string   // no joiner: "-"; "" is a real joiner
func SnakeCase[W Words](w W) string
func FlatCase[W Words](w W) string
func TrainCase[W Words](w W, opts ...CaseOptions) string
func TitleCase[W Words](w W, opts ...CaseOptions) string
```

Only the first `opts` or `joiner` value is read. Bindings (`cmd/porter-harness/bindings.go`) translate the
TypeScript call ids (`./src/index.ts:<name>`) to these functions: a missing or `$undefined` string argument
becomes `""`, a JSON array becomes `[]string`, `{normalize: x}` becomes `CaseOptions{Normalize: truthy(x)}`,
omitted separators call `SplitByCase`, an array calls `SplitByCaseWith`, and `IsUppercase` with `ok == false`
returns the harness `Undefined`. Bindings never patch results.

## Idiom map

Seeded from `knowledge/pairs/GENERIC.md` (no typescript-to-go pair file exists) and specialized to this code.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | none thrown inside the signatures | no error returns | No function returns an error. Inputs outside the TS signatures (null, numbers) are out of scope. |
| Absence | `undefined` args, `?? "-"`, `opts?.normalize`, `boolean \| undefined` | variadic optional args, `(value, ok)` | Missing string -> `""`; missing joiner -> `"-"`; missing opts -> zero `CaseOptions`; `isUppercase` tri-state -> `(upper, ok)`. |
| Overloads and unions | `T extends string \| readonly string[]` | generic `Words` constraint, type switch inside | One function per source function; `[]string` parts are never re-split. |
| Strings | UTF-16 strings, `for...of` by code point, `.length`, `.at(-1)`, `.slice`, `str[0]` | `string` in and out, `[]uint16` parts inside (`unicode/utf16`) | splitByCase iterates code points but measures and cuts in UTF-16 units; upperFirst/lowerFirst re-case only the first UTF-16 unit (a leading astral character is unchanged). Converters work on the UTF-16 parts and decode once at the end, so halves split by the falling edge re-join exactly as in JS (`flatCase("𐐀a")` = `"𐐀a"`). |
| Case mapping | `toUpperCase`/`toLowerCase`: full Unicode mapping, final sigma, no locale | `unicode.ToUpper`/`ToLower` plus a SpecialCasing table and a final-sigma rule | Never use `strings.ToUpper`/`ToLower`/`strings.Title`. Unconditional SpecialCasing entries (`ß`->`SS`, `ŉ`->`ʼN`, `ǰ`->`J̌`, `ΐ`, `ﬀ`, `İ`->`i̇`, Greek iota-subscript forms, Armenian ligatures, ...) live in one table in `casing.go`; Final_Sigma uses Cased and Case_Ignorable as Unicode defines them. A lone surrogate maps to itself. |
| Upper test | `char !== char.toLowerCase()` | the same comparison on the full lowercase mapping | Do not use `unicode.IsUpper` (it disagrees on `Ⅻ`, `Ⓐ`, `ǅ`, `𝐀`). |
| Regex | `/\d/`, `/^(a\|an\|...)$/i` without `u` | no `regexp` | `/\d/` is ASCII `0-9` only. Minor-word match is ASCII-only case-insensitive (`ſ`, Kelvin sign never match); do not use `(?i)` or `strings.EqualFold`. |
| Numbers, dates, async | none | none | Not used. |
| Module layout and naming | one ESM module, camelCase exports | one package at the module root, exported PascalCase names | `scule.go` (API), `split.go`, `casing.go`, `utf16.go` (internal helpers), `doc.go`, tests next to code. |

## Dropped workarounds and new substrate

- Dropped: the TypeScript overloads and the type-level result types (`PascalCase<T>` and the rest): Go has no
  literal result types, and the user put them out of scope.
- Dropped: `export * from "./types"`: only `CaseOptions` has a runtime shape.
- New substrate (unit split): full case mapping (SpecialCasing table, Final_Sigma) and UTF-16 part helpers,
  which the Go standard library does not provide. `golang.org/x/text/cases` was not chosen: the deps gate
  recorded no runtime dependencies and the user prefers the standard library.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| 11 runtime functions and CaseOptions | now | The whole runtime API. |
| Type-level helpers in src/types.ts and test/types.test-d.ts | out of scope | User: "Type-level helpers in src/types.ts have no runtime behavior and are out of scope." |
| Inputs outside the TS signatures (null, numbers, objects, non-string array elements) | out of scope | Go's types rule them out. |
| Lone-surrogate outputs (21 removed cases in the unit contracts) | now, as DIVERGENCE D1 | Go strings are UTF-8. The port's internal UTF-16 parts produce the same code units; decoding turns each lone surrogate into U+FFFD. Mark with a `DIVERGENCE` comment at the decode site. |
| Unicode version (Node 24: Unicode 17, Go 1.22+: Unicode 15) | seam for later | The corpus only uses mappings from Unicode 11 or earlier. A regenerated SpecialCasing table is the seam. |
| Custom multi-character separators | now | They never match (a separator must equal one code point); keep that. |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| Full case mapping or Final_Sigma differs from JS for some code point | One table and one rule in `casing.go`; the unicode generators (seeds 102, 104, 105, 109, 201-204, 206, 209, 212, 217, 219) hit `ß`, `ŉ`, `ǰ`, `ΐ`, `İ`, Greek sigma | Mismatches in cases tagged `full-case-mapping`, `final-sigma` or generated `chars-unicode`. |
| UTF-16 semantics lost by working on runes | `[]uint16` parts inside; upperFirst/lowerFirst look at the first unit only | Mismatches in tags `astral-upper`, `utf16-falling-edge`, `utf16-first-unit-casing`. |
| Go's `unicode.IsUpper`/`EqualFold`/`regexp (?i)` creeping in | Idiom map rules above; reviewer checks | Mismatches in `is-uppercase-definition` and `regex-i-ascii-only` cases. |
| Separators nil vs empty, joiner `""` vs missing | Two split functions; variadic joiner | Mismatches in `separators-nil-vs-empty`, `joiner-nullish` cases. |

## Scaffold

- Package layout:

  ```text
  go.mod                      module github.com/agentporter-examples/scule, go 1.22
  doc.go  scule.go  split.go  casing.go  utf16.go
  *_test.go                   ported reference tests (test/scule.test.ts tables) and examples
  cmd/porter-harness/         harness.go, value.go (copied), bindings.go (call id -> function)
  LICENSE                     MIT, from the original (scule authors)
  ```

- Toolchain: build `go build ./...`, test `go test ./...`, lint `go vet ./...` and
  `go run honnef.co/go/tools/cmd/staticcheck@v0.8.2 ./...` (if it cannot run offline, `go vet` alone and say
  so), format `gofmt -l .`, typecheck `go build ./...`.
- Harness: `knowledge/harnesses/go/{harness.go,value.go}` copied to `cmd/porter-harness/`; bindings in
  `cmd/porter-harness/bindings.go`. Run `go run ./cmd/porter-harness --workspace .porter --run <run> --unit <unit>`
  then `porter parity collect --run <run>`.
- CI: `.github/workflows/ci.yml` with `go test ./...`, `go vet ./...`, `gofmt -l .` on Go 1.22 and the current
  stable. Not pushed anywhere in this run.

## Budgets

Attempts per unit: 3. Discovered units before returning to the user: 5. PORT depth and LOC: 1, 2000 (no PORT
dependencies). Unit size: at most 400 LOC and 8 public symbols; split has 4, cases has 8.
