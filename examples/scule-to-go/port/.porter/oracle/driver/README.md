# JavaScript oracle driver

`oracle.mjs` records what the pinned JavaScript (or compiled TypeScript) source does. It reads
`.porter/oracle/expanded/<unit>.json`, loads the source modules, calls each case, and writes
`.porter/fixtures/<unit>/oracle.json` plus `.porter/oracle/timings/<unit>.json` as
[CONTRACT.md](../CONTRACT.md) describes. Node 18 or newer, no dependencies.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Run it

Install the source's dependencies in its checkout first (`npm ci`), and build it if the package entry points
at build output. That adds untracked files (`node_modules/`, build output) and changes no source file, so it
does not break "never edit the source". If the checkout is the user's own working tree, ask before installing
there. Then:

```sh
porter fixtures expand
node ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/javascript/oracle.mjs --workspace .porter \
    [--unit <unit>]... [--package-version <v>] [--commit <sha>] [--timeout <seconds>]
porter fixtures validate
```

The source root is `config.source.path` joined with `config.source.subpath`. Package name and version come
from `config.source.package`, then the nearest `package.json`.

Exit codes: 0 when fixtures were written (throws are outcomes), 2 when the driver cannot run: an unknown
module or export, a case with `kwargs`, a CLI unit.

## How calls resolve

The module part is an import specifier:

- `./src/index.js` and other relative paths resolve against the source root.
- The package's own name (`ms`, `ms/sub`) resolves through its `package.json` `exports` (conditions
  `import`, `node`, `require`, `default`) or `main`.
- Other bare specifiers resolve as dependencies from the source root. `node:` builtins work too.

ES modules load with `import()`. CommonJS modules load with `require`: `module.exports` is `default` and its
own keys are named exports. The qualified name then walks properties, falling back to `prototype`, so
`Class.method` finds instance methods.

| Call | Input | What runs |
| --- | --- | --- |
| `ms:default` | `args` | `ms(...args)` |
| `pkg:Class` | `args` | `new Class(...args)` |
| `pkg:Class.method` | `init`, `args` | `new Class(...init.args).method(...args)` |
| `pkg:Class.staticMethod` | `args` | called with `Class` as `this` |
| `pkg:NAME` | `{}` | reads the export |

JavaScript has no named arguments: a case with non-empty `kwargs` exits 2. Put an options object in `args`.
Returned promises are awaited.

## Serialization

| JavaScript | JSON |
| --- | --- |
| `undefined` returned by a call | `{"$undefined": true}` |
| `undefined` inside arrays | `null`; object properties holding `undefined` are left out, as in `JSON.stringify` |
| `NaN`, `Infinity`, `-Infinity`, `-0` | `{"$float": ...}` |
| `bigint` | number within 2^53, else `{"$int": "..."}` |
| `Uint8Array`, `Buffer`, `ArrayBuffer` | `{"$bytes": "<base64>"}` |
| other typed arrays | array |
| `Set` | `{"$set": [...]}` sorted by canonical JSON |
| `Map` with only string keys | object |
| other `Map` | `{"$map": [[k, v], ...]}` in insertion order |
| `Date` | `{"$datetime": toISOString()}` |
| `RegExp` | `{"$type": "RegExp", "source", "flags"}` |
| `Error` value | `{"$type": "Name", "message"}` |
| plain object | object in key order |
| class instance | `{"$type": "ClassName", ...}` with own enumerable keys, sorted, `_private` keys skipped |
| function | `{"$type": "function", "name"}` |

Tagged values in case inputs are decoded before the call: `$float`, `$int` (to `BigInt`), `$bytes` (to
`Buffer`), `$datetime` (to `Date`), `$set`, `$map` and `$undefined`. This input decoding is an addition to the
contract.

## Errors and timeouts

The category is the error's constructor name, falling back to `error.name` (`TypeError`, `RangeError`,
`Error`). A thrown non-error value gets category `NonError` and `String(value)` as its message.

Synchronous calls run through `vm.runInNewContext` with `--timeout` seconds (default 10), which interrupts
infinite loops. Promises race against a timer; a promise that never settles is abandoned and the process
exits once every unit is written.

## Limitations

- Getters and `#private` fields of class instances are not serialized.
- The synchronous timeout stops at the first `await`; after that only the promise timer applies.
- Browser-only sources need a Node shim before they can be recorded.
