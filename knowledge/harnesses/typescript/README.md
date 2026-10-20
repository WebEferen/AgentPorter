# TypeScript parity harness

`harness.ts` runs every recorded case in `.porter/fixtures/<unit>/*.json` through your port and writes
`.porter/runs/<run>/<unit>.json` (see [CONTRACT.md](../../oracles/CONTRACT.md)). It never compares;
`porter parity collect` does. It works for JavaScript ports too. No dependencies.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Copy it into the port

```sh
mkdir -p porter
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/typescript/harness.ts porter/
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/typescript/bindings.example.ts porter/bindings.ts
```

The files are ES modules: the port's `package.json` needs `"type": "module"` (or rename them to `.mts`).
`bindings.ts` imports only types from `./harness.ts`, so keep `import type`. If `tsc` checks the `porter/`
folder, enable `allowImportingTsExtensions` with `noEmit`, or exclude the folder from the build. The harness
passes `tsc --strict` with `erasableSyntaxOnly`.

## Run it

Node 22.18+, 23.6+ and 24 strip types natively. On Node 22.6 to 22.17 add `--experimental-strip-types`.

```sh
node porter/harness.ts --workspace .porter --run <run> [--unit <unit>]... [--bindings porter/bindings.ts] [--timeout <seconds>]
porter parity collect --run <run>
```

The default run id is the UTC time. Exit code 0 when runs were written, 2 when the harness cannot run (no
fixtures, no bindings file).

## Bindings

`bindings.ts` exports `bindings: Bindings`, one entry per source call id and nothing else. Each entry is
`(args, kwargs, input) => unknown` and may return a promise. Tagged inputs arrive decoded: `$float` as a
number, `$int` as a `bigint`, `$bytes` as a `Uint8Array`, `$set` as a `Set`, `$map` as a `Map`, `$datetime`
as a `Date`, `$decimal` as a string, `$undefined` as `undefined`. `input` is the whole decoded input, so
`input.init` holds the constructor arguments for `Class.method` calls.

Bindings translate calling conventions only: positional to named arguments, Python kwargs to an options
object, a receiver built from `init`. They never convert or patch a result. A call id without a binding
gets the outcome category `MissingBinding`, so it fails in parity instead of disappearing.

Bindings can import TypeScript sources (`../src/index.ts`) or the compiled build (`../dist/index.js`).

## Serialization

The same rules as the JavaScript oracle: `NaN`, `Infinity` and `-0` become `$float`, a `bigint` beyond 2^53
becomes `$int`, `Uint8Array` becomes `$bytes`, `Set` becomes a sorted `$set`, a `Map` becomes an object or a
`$map`, `Date` becomes `$datetime`, and class instances become `$type` objects with their own enumerable keys,
sorted. A top-level `undefined` result becomes `{"$undefined": true}` only when the fixture was recorded
from JavaScript or TypeScript; for other source languages it is `null`, matching Python's `None` or Go's `nil`.

## Errors and timeouts

The category is the thrown error's constructor name, falling back to `error.name`. A port that throws its own
subclass (`class InvalidValueError extends Error`) reports that name, which fails against a source category
`Error` unless `.porter/contract/error-map.json` maps it (then the unit is EQUIVALENT, not EXACT). A thrown
non-error value gets category `NonError`.

Synchronous calls run through `vm.runInNewContext` with `--timeout` seconds (default 10), which interrupts
infinite loops. Promises race against a timer.

## Limitations

- Only erasable TypeScript syntax runs under type stripping: no `enum`, `namespace` or parameter properties
  in the harness or bindings (the port itself may use them if bindings import its compiled build).
- Getters and `#private` fields are not serialized.
