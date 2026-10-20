# scule (Go)

Go port of [scule](https://github.com/unjs/scule) 1.3.0: split strings by case and convert them between
naming conventions. Standard library only, Go 1.22 or newer.

```go
import "github.com/agentporter-examples/scule"

scule.SplitByCase("fooBar-baz")                                // ["foo" "Bar" "baz"]
scule.PascalCase("foo-bar")                                    // "FooBar"
scule.CamelCase("FOO_BAR", scule.CaseOptions{Normalize: true}) // "fooBar"
scule.KebabCase([]string{"Foo", "Bar"})                        // "foo-bar"
scule.TitleCase("this-IS-aTitle")                              // "This is a Title"
```

Text is cased the way JavaScript does it (full Unicode mapping, so "ß" uppercases to "SS"), and splitting
measures in UTF-16 code units like the original.

## Parity with upstream

Upstream: scule 1.3.0, commit `90d28593c8426d16beb5dadf3af8d341b6fee107`. Evidence recorded on 2026-10-20
by running the original on Node 24.18.0 and the port on the same 2984 fixture cases; full report in
[docs/PARITY.md](docs/PARITY.md).

| Unit | Functions | Level | Cases | Reference tests |
| --- | --- | --- | --- | --- |
| split | IsUppercase, SplitByCase, SplitByCaseWith, UpperFirst, LowerFirst | EXACT | 987/987 | 19/19 |
| cases | PascalCase, CamelCase, KebabCase, SnakeCase, FlatCase, TrainCase, TitleCase | EXACT | 1997/1997 | 44/44 |

Divergences:

- d1, d1-cases: where JavaScript returns a string holding a lone UTF-16 surrogate (for example
  `splitByCase("𐐀a")`), the Go result holds U+FFFD, because Go strings are UTF-8.
- d2: single code point case mappings come from Go's `unicode` tables (Unicode 15), which can differ from
  newer JavaScript engines for characters added or re-cased later (for example "ƛ").

The TypeScript type-level helpers (`PascalCase<T>` and the rest) are not ported: they have no runtime behavior.

## License

MIT, same as upstream. See [LICENSE](LICENSE).
