# scule: TypeScript to Go

[scule](https://github.com/unjs/scule) splits strings by case and converts them between naming
conventions (camelCase, kebab-case, Title Case and others). This is version 1.3.0 ported to Go.

- [original/](original/): `src/` and `test/` of scule 1.3.0 (commit `90d2859`), with its `package.json`,
  README and license.
- [port/](port/): the module `github.com/agentporter-examples/scule`, its tests, the parity harness in
  `cmd/porter-harness` and the `.porter/` workspace.

## Original and port

```ts
import { splitByCase, pascalCase, camelCase, kebabCase, titleCase } from "scule";

splitByCase("fooBar-baz");                 // ["foo", "Bar", "baz"]
pascalCase("foo-bar");                     // "FooBar"
camelCase("FOO_BAR", { normalize: true }); // "fooBar"
kebabCase(["Foo", "Bar"]);                 // "foo-bar"
titleCase("this-IS-aTitle");               // "This is a Title"
```

```go
import "github.com/agentporter-examples/scule"

scule.SplitByCase("fooBar-baz")                                // ["foo" "Bar" "baz"]
scule.PascalCase("foo-bar")                                    // "FooBar"
scule.CamelCase("FOO_BAR", scule.CaseOptions{Normalize: true}) // "fooBar"
scule.KebabCase([]string{"Foo", "Bar"})                        // "foo-bar"
scule.TitleCase("this-IS-aTitle")                              // "This is a Title"
```

The port cases text the way JavaScript does ("ß" uppercases to "SS") and measures in UTF-16 code units like
the original. The type-level helpers (`PascalCase<T>` and the rest) have no runtime behavior and were not
ported.

## Result

EXACT: 2984 of 2984 recorded cases match (987 in `split`, 1997 in `cases`), and 63 of 63 upstream tests
are ported and pass. Full report: [port/docs/PARITY.md](port/docs/PARITY.md).

Three divergences are declared for inputs no fixture holds:

- `d1`, `d1-cases`: where JavaScript returns a string holding a lone UTF-16 surrogate, Go returns U+FFFD
  in its place, because Go strings are UTF-8.
- `d2`: case mappings come from Go's Unicode 15 tables while Node 24 uses Unicode 17, so about 110 code
  points (such as "ƛ") case differently.

## How it was made

One unattended session (see [how the examples were made](../README.md#how-they-were-made)): $21.19,
104 turns, 66 minutes. Pre-approved answers:

```text
- deps gate: approve the proposed decisions when every MAP and SHIM candidate is registry-verified. Prefer the Go
  standard library.
- strategy gate: approve the proposed units, order and budgets as written.
- Anything about the package: the Go module path is github.com/agentporter-examples/scule, Go 1.22 or newer, a
  library with an idiomatic Go API. Type-level helpers in src/types.ts have no runtime behavior and are out of
  scope. The fixtures keep the TypeScript call ids; the bindings translate.
```

Where the run left the script:

- 21 inputs make the original return lone surrogates. porter crashed on them while hashing the fixtures,
  so the agent removed them from the cases, listed each one in the contract and declared `d1` and
  `d1-cases` for them. porter keeps lone surrogates now, so a rerun would record those cases and grade
  them as divergent.
- To stay under the cap, the agent ran verify for both units, the review of `cases` and the final verify
  inline instead of in fresh verifier and reviewer agents.

## Check it

```sh
cd port
go test ./...
go run ./cmd/porter-harness --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

## License

MIT, from scule (Pooya Parsa). `original/` and `port/` both keep the notice.
