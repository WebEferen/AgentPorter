# Oracle and harness contract

Every oracle driver (source side, `knowledge/oracles/<language>/`) and every parity harness (target side,
`knowledge/harnesses/<language>/`) follows this contract, so one fixture corpus drives any pair of languages.
Black-box CLI programs skip both and use `porter.py cli record` and `porter.py cli run` instead.

## Files

| Path | Written by | Read by |
| --- | --- | --- |
| `.porter/oracle/cases/<unit>.json` | contract skill | `porter.py fixtures expand` |
| `.porter/oracle/expanded/<unit>.json` | `porter.py fixtures expand` | oracle driver |
| `.porter/fixtures/<unit>/oracle.json` | oracle driver | harness, `porter.py parity collect` |
| `.porter/oracle/timings/<unit>.json` | oracle driver | `porter.py parity collect` (perf ratio) |
| `.porter/runs/<run>/<unit>.json` | harness | `porter.py parity collect` |

Schemas: `knowledge/schemas/cases.schema.json`, `fixture.schema.json`, `actuals.schema.json`.

## Calls

`call` names what to invoke, as `<module>:<qualified name>`, the same id `contract/api.json` uses. When the
driver needs a different module name than api.json's (a JavaScript import specifier such as `ms` for the
file module `index`, a Go import path), set the symbol's `callId` in api.json to the id fixtures use.

| Form | Meaning |
| --- | --- |
| `pkg.mod:func` | call a module-level function with `input.args` and `input.kwargs` |
| `pkg.mod:Class` | construct the class with `input.args` and `input.kwargs`, result is the instance |
| `pkg.mod:Class.method` | construct with `input.init.args` and `input.init.kwargs`, then call the method with `input.args` and `input.kwargs` |
| `pkg.mod:CONST` | read a module attribute (`input` is `{}`) |

JavaScript modules use the import specifier (`ms`, `lodash/fp`, `./src/index.js`); `default` is the default
export (`ms:default`). Go uses the import path (`github.com/x/y:Func`). Java and Kotlin use the fully
qualified class (`com.acme.Text:slugify` for a static method). PHP uses the class or function name with
namespace (`App\Text:slugify`).

`kwargs` is for languages with named arguments. A target without them maps kwargs in its binding (below).

## Values

Values are JSON. Types JSON cannot carry use tagged objects, identical on both sides:

| Source value | JSON form |
| --- | --- |
| tuple, list, array, slice | array |
| set, frozenset | `{"$set": [sorted elements]}` (sorted by canonical JSON text) |
| map with non-string keys | `{"$map": [[key, value], ...]}` in insertion order when the source keeps one (Python dict, JS Map), otherwise sorted by canonical JSON text of the key (Go, Java, Kotlin and Rust hash maps) |
| bytes, byte array, Buffer | `{"$bytes": "<base64>"}` |
| NaN, Infinity, -Infinity | `{"$float": "nan"}`, `{"$float": "inf"}`, `{"$float": "-inf"}` |
| -0.0 | `{"$float": "-0"}` |
| integers beyond 2^53 | `{"$int": "<decimal digits>"}` |
| decimal, BigDecimal | `{"$decimal": "<string form>"}` |
| date, datetime, instant | `{"$datetime": "<ISO 8601>"}`, with an offset when the value has one (prefer UTC `Z`). Parity compares these as instants, so `10:00Z` equals `11:00:00.000+01:00`; a value without an offset never equals one with an offset |
| enum member | `{"$enum": "<Type>.<MEMBER>"}` |
| object, struct, dataclass, record | `{"$type": "<TypeName>", "<field>": value, ...}` public fields only, sorted by name, under the source's field names |
| null, None, nil, undefined | `null`, except `{"$undefined": true}` for a JavaScript or TypeScript value that is `undefined` (see below) |

Strings stay strings (UTF-8). Do not normalize them: normalization is declared per case, in its
`normalize` list. The names are `float:<tol>`, `unordered`, `lines-unordered`, `trim`, `trim-trailing-ws`,
`lf`, `nfc`, `json`, `ignore-stderr` and `ignore-message`; any other name fails validation.

A JavaScript, Java or C# string can hold a lone UTF-16 surrogate. Record it as is (JSON writes it as a
`\ud801` escape) and porter keeps it. A target whose strings must be valid UTF-8, such as Go or Rust,
cannot return one, so plan a divergence for those cases instead of dropping them.

Drivers stop serializing at 64 levels of nesting: a deeper value is written as
`{"$type": "<TypeName>", "truncated": true}`. The Python and PHP drivers also cut a collection at 10,000
items and end it with `{"$truncated": 10000}`. Parity has no rule for these markers, so a case whose result
crosses a limit cannot pass. Keep generated cases inside the limits; a recorded case that already crosses
one is a divergence, not a port bug.

The tags apply to case inputs too. Drivers and harnesses decode them in `input.args`, `input.kwargs` and
`input.init`, so a case can pass NaN, bytes, a set or a big integer.

`undefined`: an oracle emits `{"$undefined": true}` only when a JavaScript or TypeScript call returns
`undefined`. A harness emits it only when the fixture's oracle language is JavaScript or TypeScript, or
when a binding returns the harness's explicit undefined marker. Everywhere else absence is `null`.

Field names: `$type` objects carry the source's field names. When the port's naming style differs
(`is_active` against `isActive`), the harness's value conversion for that type writes the source names.
Kotlin and Java property getters (`isActive` read as `active`) need the same care. If the names cannot
match, record a divergence.

## Outcomes

A call either returns or throws.

- Return: `{"kind": "value", "value": <serialized>}`.
- Throw: `{"kind": "error", "category": "<error type name>", "message": "<message text>"}`. The category is the
  short type name (`ValueError`, `TypeError`, `IllegalArgumentException`). The harness reports the target's own
  type name; `.porter/contract/error-map.json` maps source categories to target categories. A mapped category
  grades as EQUIVALENT. A port that names its error types after the source categories can reach EXACT.
- Timeout (default 10 s per case): `{"kind": "error", "category": "timeout", "message": "..."}`.
- A Go function can return a result next to its error. The Go driver keeps a non-zero one as `value` on the
  error outcome. Parity does not compare it; the port should still expose it, for example on the exception.

## Oracle driver behavior

1. Read `.porter/oracle/expanded/<unit>.json`.
2. Import the pinned source package (from the checkout in `config.source.path`, or the installed pinned version).
3. For each case: resolve `call`, invoke it, serialize the outcome, time it in milliseconds.
4. Write `.porter/fixtures/<unit>/oracle.json`:
   `{"schema": 1, "unit", "oracle": {"language", "package", "version", "commit", "runtime", "driver", "recordedAt"}, "cases": [...]}`
   where each case is the expanded case plus `"expect": <outcome>`.
5. Write `.porter/oracle/timings/<unit>.json`: `{"unit": "<unit>", "cases": {"<case>": <ms>}}`.
6. Exit 0 even when cases throw (throwing is an outcome). Exit 2 only when the driver itself cannot run.

Command line, same in every language:

```text
<runner> <driver> --workspace .porter --unit <unit> [--package-version <v>] [--commit <sha>]
```

## Harness behavior

1. Read every `.porter/fixtures/<unit>/*.json`.
2. For each case, look up `call` in the binding table and invoke it with the case input.
3. Serialize the outcome with the same rules, and time it.
4. Write `.porter/runs/<run>/<unit>.json`:
   `{"schema": 1, "unit", "runner": {"language", "driver"}, "startedAt", "results": [{"case", "actual", "durationMs"}]}`.
5. Never compare. `porter.py parity collect` owns comparison, normalization and divergences.
6. Exit 0 when the results were written, 2 when the harness itself cannot run (no fixtures, no bindings).

Command line, same in every language (the default run id is the current UTC time):

```text
<runner> <harness> --workspace .porter --run <run> [--unit <unit>]... [--bindings <file>] [--timeout <seconds>]
```

Error categories the drivers and harnesses produce themselves. `MissingBinding` and `BindingError` never
appear in fixtures, so they always fail in parity. `timeout` and `panic` match only when the original
timed out or panicked on the same case.

| Category | Meaning |
| --- | --- |
| `MissingBinding` | The fixture's call id has no entry in the binding table. |
| `BindingError` | The binding could not read the case input in the shape it expected. |
| `timeout` | The call ran longer than `--timeout` (default 10 seconds). |
| `panic` | Go and Rust: the call panicked instead of returning an error. |

## Bindings

The binding table maps each source call id to a target function, written by the implementer next to the
harness (for example `harness/bindings.ts`). One entry per call id, nothing else:

```ts
export const bindings: Bindings = {
  "slugify.slugify:slugify": (args, kwargs) => slugify(args[0], { lowercase: kwargs.lowercase, separator: kwargs.separator }),
};
```

Bindings translate calling conventions only (positional and named arguments, option objects, receivers).
They must not fix up results: a binding that converts or patches a return value hides a parity gap.
