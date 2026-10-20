# JavaScript to TypeScript

| Field | Value |
| --- | --- |
| Source | JavaScript ES5 to ES2022 (CommonJS, AMD/UMD, browser globals, prototype classes, callbacks, jQuery-era code) and CoffeeScript 1.x/2.x |
| Target | TypeScript 5.x, ESM, on Node 20+ |
| Status | full |
| Last reviewed | 2026-10-20 |

How to use this file: the `strategy` skill loads it to seed the idiom map for a
port, and the `implement` skill reads the sections a unit's risk tags point at.
Every trap carries risk tags from this vocabulary, which `porter.py decompose`
also emits for units:

`regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`,
`unicode`, `encoding`, `io`, `locale`, `mutability`, `nullability`,
`error-model`, `ordering`.

Source and target run on the same engine family, so most runtime semantics
carry over unchanged. Behavior changes come from four places:

1. The module switch. ESM is always strict mode, has no `__dirname` or
   `require`, orders `process.nextTick` differently at top level, and turns
   circular-import reads into errors.
2. Rewrites that a linter or the type checker pushes you toward: `===` for
   `==`, `Number()` for `parseInt`, `class` for prototypes, `let` for `var`,
   `Map` for objects, arrow functions for `function`. Each one is a behavior
   change until a fixture proves otherwise.
3. Library replacements: moment, bluebird, Q, async, jQuery, underscore and
   lodash all have semantics that native APIs do not copy.
4. CoffeeScript, where the operators and the return rules differ from
   JavaScript even when the syntax looks the same.

CoffeeScript sources: compile every file once with the exact compiler version
the project pinned (`coffee -c -b file.coffee`) and keep the output under
`.porter/reference/`. Port intent from the `.coffee` file, and check semantics
against the compiled JavaScript, which is what the fixtures actually exercised.

## 1. Type system mapping

| JavaScript value or pattern | TypeScript | Notes |
| --- | --- | --- |
| number | `number` | No integer type. Use `bigint` only where the source used a bignum library or did 64-bit math by hand. |
| string | `string` | UTF-16 code units in both. |
| boolean | `boolean` | |
| `null`, `undefined` | `null`, `undefined` with `strictNullChecks` | Keep whichever one the source returns. JSON output differs (section 3). |
| Array | `T[]` or `readonly T[]` | Holes in sparse arrays survive only if the port avoids `Array.from` rewrites. |
| object used as a record with known keys | interface or type alias | |
| object used as a dictionary | `Record<string, T>` plus `noUncheckedIndexedAccess` | Keep a plain object when key order or JSON output is part of the contract (T10). |
| dictionary keyed by untrusted input | `Map<string, T>` or `Object.create(null)` | A plain object silently drops the key `__proto__`. Check JSON output before switching to `Map` (T10). |
| constructor function plus prototype | `class` | T6, T7, T8. |
| function with properties (`module.exports = fn; fn.version = '1'`) | `Object.assign(fn, { version: '1' })` | Keeps the callable export shape (T11). |
| frozen object used as an enum | `as const` object plus a union type | TS `enum` changes the runtime shape (numeric enums add reverse mappings) and cannot run under Node type stripping. |
| options object | interface with optional members | |
| error-first callback | `(err: Error \| null, value?: T) => void` | Keep the callback if it is in the public contract (section 4). |
| `arguments` | rest parameter `...args: unknown[]` | Sloppy-mode aliasing is gone (T4). |
| Q, bluebird or jQuery Deferred | `Promise<T>` | Section 4. |
| jQuery collection | `JQuery<HTMLElement>` from `@types/jquery` | |
| Buffer | `Buffer` | Do not switch to `Uint8Array` without checking `slice` (T24). |
| CoffeeScript class with `@prop` arguments and `=>` methods | class with constructor assignments and arrow-function fields | T43, T44. |

Rules that do not fit the table:

- Types are erased. Never let an annotation replace a runtime check the source
  had, and never add a runtime check the source lacked: a new `throw` changes
  which inputs fail. Validation libraries (zod, valibot) belong only where the
  source validated.
- Use `unknown` for parsed JSON, `catch` variables and external input, then
  narrow. `any` is acceptable only at a boundary the contract marks as
  untyped, with a comment.
- `typeof x === 'object'` narrows to `object | null`, because
  `typeof null === 'object'`. A source check written as
  `x && typeof x === 'object'` must keep the truthiness guard.
- Turn on `strict` and `noUncheckedIndexedAccess`. Type the public boundary
  first from `.porter/contract/api.json`, then the internals.
- Functions that switch on `typeof` of their arguments become overload
  signatures with one implementation. Keep the source's fallbacks exactly,
  including `||`:

```js
// source: lib/get.js
function get(key, opts, cb) {
  if (typeof opts === 'function') { cb = opts; opts = {}; }
  opts = opts || {};
  // ...
}
module.exports = get;
```

```ts
// target: src/get.ts
export interface GetOptions { timeout?: number }
export type Callback<T> = (err: Error | null, value?: T) => void;

export function get(key: string, cb: Callback<string>): void;
export function get(key: string, opts: GetOptions | null | undefined, cb: Callback<string>): void;
export function get(
  key: string,
  optsOrCb: GetOptions | null | undefined | Callback<string>,
  maybeCb?: Callback<string>,
): void {
  const cb = typeof optsOrCb === 'function' ? optsOrCb : maybeCb!;
  const opts = (typeof optsOrCb === 'function' ? undefined : optsOrCb) || {};
  // ...
}
```

## 2. Error model

JavaScript can throw any value. Legacy code throws strings, plain objects and
errors built by hand, and callers may depend on that (`catch (e) { if (e ===
'timeout') ... }`).

| Source pattern | Target default | Notes |
| --- | --- | --- |
| `throw new Error(msg)` | same | |
| `throw 'message'` or `throw { code: 1 }` | keep the thrown value if callers inspect it; otherwise an `Error` subclass and a divergence entry | `e.message` on a thrown string is `undefined`. |
| ES5 custom error (`function MyError(m) { this.message = m } util.inherits(MyError, Error)`) | `class MyError extends Error` with `name` set | Preserve `name`, `code` and any extra fields. `instanceof` works with native `extends Error` at ES2022 targets. |
| `cb(err)` | same callback, or a rejected promise with the same error object | Do not wrap the error unless the contract says so. |
| `emitter.emit('error', err)` | keep `EventEmitter` | T17. |
| bluebird or Q rejection | native rejection | T16 for unhandled rejections. |
| jQuery 1.x/2.x Deferred `reject` | rejected promise | Pre-3.0 Deferreds ran handlers synchronously and did not catch exceptions thrown in them. jQuery 3 Deferreds follow Promises/A+. |
| `verror` / `new VError(cause, msg)` | `new Error(msg, { cause })` | `cause` is ES2022. VError message concatenation (`msg: cause.message`) must be rebuilt by hand if fixtures record messages. |
| `process.exit(code)` in a CLI | same | Libraries should not exit. Keep it only in entry units. |

`catch (e)` variables are `unknown` under `strict`. Narrow with
`e instanceof Error` before reading `message`, and keep a fallback path for
non-Error values when the source could receive them.

## 3. Null and absence

- Two absent values. JSON drops properties whose value is `undefined` and
  turns `undefined` array slots into `null`:
  `JSON.stringify({ a: undefined, b: [undefined] })` gives `{"b":[null]}`.
  If a fixture records JSON, `null` versus `undefined` is observable.
- `x == null` is true for both `null` and `undefined`. Keep it, or write
  `x === null || x === undefined`. Configure `eqeqeq` with
  `{ "null": "ignore" }` so autofix does not break it (T1).
- `x || d` replaces every falsy value (`0`, `''`, `false`, `NaN`); `x ?? d`
  and default parameters replace only `null`/`undefined`, and default
  parameters replace only `undefined`. Port the operator the source used (T3).
- `'k' in o` is true for inherited properties and for properties set to
  `undefined`. `o.k !== undefined` is false for the second case.
  `Object.hasOwn(o, k)` checks own properties and works on
  `Object.create(null)` objects, where `o.hasOwnProperty` does not exist.
- A missing argument and an explicit `undefined` look the same to default
  parameters but not to `arguments.length`. Overloads that count arguments
  must keep counting (rest parameters plus `args.length`).
- CoffeeScript existential operators map to `!= null` checks, not to
  truthiness (T38, T39).

## 4. Concurrency and async

Single thread, one event loop, in source and target. What changes is the
async style, and the rule is: keep the public async contract. If the source
exports a callback API, the port exports a callback API. A promise API can be
added beside it, never silently swapped in.

```ts
// Keep the callback contract, add a promise form when no callback is passed.
export function load(path: string): Promise<Config>;
export function load(path: string, cb: Callback<Config>): void;
export function load(path: string, cb?: Callback<Config>): Promise<Config> | void {
  const p = loadAsync(path);
  if (!cb) return p;
  p.then((v) => cb(null, v), (e) => cb(e as Error));
}
```

That wrapper defers the callback to a microtask. If the source called the
callback synchronously in some paths, it is not equivalent (T14).

Library mapping:

| Source | Target | Notes |
| --- | --- | --- |
| bluebird `Promise.map(xs, fn, { concurrency: n })` | `p-map` or a small worker pool | |
| bluebird `.spread((a, b) => ...)` | `.then(([a, b]) => ...)` | |
| bluebird `.catch(TypeError, fn)` | `catch (e) { if (!(e instanceof TypeError)) throw e; ... }` | Filtered catch. |
| bluebird `.tap(fn)` | `.then((v) => { fn(v); return v; })` | |
| bluebird `Promise.delay(ms)` | `setTimeout` from `node:timers/promises` | |
| bluebird `Promise.promisifyAll(obj)` | `util.promisify` per method | `promisifyAll` adds `fooAsync` methods. If callers use those names, keep them (T15). |
| bluebird `Promise.props(obj)` | `Object.fromEntries` over `Promise.all` of entries | |
| bluebird cancellation | `AbortSignal` | No native promise cancellation. |
| `Q.defer()` | an explicit `new Promise` executor | `Promise.withResolvers` is ES2024 and missing on Node 20. |
| `Q.nfcall(fn, ...args)` | `util.promisify(fn)(...args)` | |
| `async.series`, `async.waterfall` | sequential `await` | `async.parallel` with an object returns an object of results; keep the shape. |
| `async.eachLimit`, `async.mapLimit` | `p-limit` or `p-map` with `concurrency` | Results of `mapLimit` keep input order. |
| `async.queue` | `p-queue` or a hand-written queue | |
| `co` plus generators | `async` functions | |
| old streams (`through`, `event-stream`, streams1 `data` events) | `node:stream` with `pipeline` from `node:stream/promises` | Readables are async iterable. |
| `setTimeout` id stored as number | `ReturnType<typeof setTimeout>` | Node returns a `Timeout` object, not a number. |

Ordering rules that matter for fixtures:

- In CommonJS, the `process.nextTick` queue drains before promise
  microtasks. At the top level of an ES module it is the other way around
  (T12).
- `setImmediate` runs after I/O callbacks; `setTimeout(fn, 0)` is clamped to
  1 ms. Keep the exact scheduling primitive the source used.
- Node 15+ terminates on an unhandled rejection (T16).

## 5. Iteration, generators, laziness

- `for...in` over an array yields string indexes, skips holes, and includes
  enumerable properties added to the array or to `Array.prototype` by old
  polyfills. `for...of` yields values and visits holes as `undefined`.
  Pick the form that reproduces the source's visit set.
- Object key order: integer-like keys ascending first, then string keys in
  insertion order, then symbols. This applies to `Object.keys`,
  `for...in`, `JSON.stringify` and spread (T10).
- `Array.prototype.forEach` ignores return values. `_.each`, `_.forEach` and
  `$.each` stop when the callback returns `false` (T32), which CoffeeScript
  implicit returns trigger by accident (T37).
- `$.each(obj, function (key, value) {})` passes key first;
  `Array.prototype.forEach` passes value first.
- lodash chains (`_(xs).map(f).take(n).value()`) are lazy: `f` runs only for
  the elements needed (T31). Native array methods are eager.
- `Array(3).map(fn)` skips the holes and returns `[ <3 empty items> ]`; the
  idiomatic `Array.from({ length: 3 }, fn)` calls `fn` three times.
- CoffeeScript comprehensions (`x * 2 for x in xs when x > 0`) are
  expressions that build arrays. `for own k, v of obj` adds a
  `hasOwnProperty` check; `for k, v of obj` does not (T42).
  `for x in xs by 2` steps by 2.
- Generators are unchanged. Node 20 has no Iterator helpers
  (`iterator.map`); they arrive in Node 22.

## 6. Numeric semantics

One numeric type: IEEE 754 double. Integers are exact up to
`Number.MAX_SAFE_INTEGER` (2^53 - 1).

- Bitwise operators convert to signed 32-bit: `x | 0`, `~~x` and `x >> 0`
  truncate and wrap; `x >>> 0` converts to unsigned 32-bit (T22).
- `/` is always float division; `%` takes the sign of the dividend
  (`-7 % 2` is `-1`); division by zero gives `Infinity` or `NaN`.
- `parseInt('12px')` is `12`; `Number('12px')` and `+'12px'` are `NaN`;
  `Number('')` and `Number(null)` are `0`; `Number(undefined)` is `NaN`
  (T20). Always pass a radix to `parseInt`.
- Global `isNaN` and `isFinite` coerce their argument; the `Number.` versions
  do not (T21).
- `Math.round(-2.5)` is `-2` (rounds half toward positive infinity).
  `toFixed` rounds the exact binary value: `(1.005).toFixed(2)` is `'1.00'`.
  `Intl.NumberFormat` and `_.round` give `1.01` for the same input (T23).
- `String(n)` switches to exponent form at `1e21` and below `1e-6`:
  `String(1e21)` is `'1e+21'`, `String(1e-7)` is `'1e-7'`.
- `JSON.stringify` throws `TypeError` on a `bigint`. If the port moves ids to
  `bigint`, serialize them explicitly as strings or numbers to match the
  source output.
- Sloppy-mode octal literals (`010` is 8) are a syntax error in ESM. Replace
  with `0o10` and check the value is what the source meant.

## 7. Strings, bytes, unicode, encodings

- Strings are UTF-16 in both. `length`, `charAt`, `slice` and indexing work
  on code units; `'😀'.length` is 2. Use `[...s]` or `Intl.Segmenter` only
  where the source did something equivalent.
- `toUpperCase` and `toLowerCase` use Unicode default case mapping
  (`'ß'.toUpperCase()` is `'SS'`) and ignore locale; `toLocaleUpperCase`
  depends on the ICU data bundled with Node. `localeCompare` and
  `Intl.Collator` output can change between Node versions. Fixtures that
  record locale-formatted output should pin the Node major.
- `substr(start, length)` is deprecated but still works.
  `substring(start, end)` swaps its arguments when `start > end`
  (`'abcdef'.substring(4, 1)` is `'bcd'`); `slice(4, 1)` returns `''`.
- `escape('é')` is `'%E9'` (Latin-1); `encodeURIComponent('é')` is
  `'%C3%A9'`. The old idiom `unescape(encodeURIComponent(s))` builds a
  "binary string" of UTF-8 bytes; replace it with
  `new TextEncoder().encode(s)` or `Buffer.from(s, 'utf8')`, and keep any
  downstream code that expects one char per byte working.
- `new Buffer(x)` is deprecated: `Buffer.from(string, enc)`,
  `Buffer.from(array)`, `Buffer.alloc(n)`. `Buffer.allocUnsafe` matches the
  old uninitialized `new Buffer(n)` and should not be used for parity.
- `buf.toString('binary')` is Latin-1. `buf.toString('utf8')` replaces
  invalid sequences with U+FFFD.
- `JSON.stringify(buffer)` gives `{"type":"Buffer","data":[...]}`. A port to
  `Uint8Array` serializes as `{"0":104,"1":105}`.
- `atob` and `btoa` exist as globals since Node 16 and throw on characters
  above U+00FF.
- CoffeeScript block strings (`"""`) strip the common leading indentation
  and the first and last newline: a three-line block indented by four
  spaces with one inner line indented by six gives `'a\n  b'`. A template
  literal with the same lines keeps all the whitespace. Heregexes (`///`)
  ignore whitespace and `#` comments.

## 8. Dates, times, timezones

`Date` parsing rules (Node, V8):

| Input | Parsed as |
| --- | --- |
| `'2024-01-15'` (ISO date only) | UTC midnight |
| `'2024-01-15T00:00:00'` (ISO date-time, no offset) | local time |
| `'2024-01-15T00:00:00Z'` or with `+01:00` | that offset |
| `'2024/01/15'`, `'Jan 15 2024'` | local time (V8 heuristics, not standardized) |
| `new Date(2024, 0, 15)` | local time, month is 0-based |

- The process timezone comes from `TZ` or the OS. Fixture recording and
  verification must set the same `TZ`.
- moment parses ISO date-only strings as local time (T25), mutates in place
  (T27), and clamps month arithmetic (T28). moment format tokens are not
  date-fns tokens (T26).

| moment token | date-fns token | Luxon token | Meaning |
| --- | --- | --- | --- |
| `YYYY` | `yyyy` | `yyyy` | calendar year |
| `MM` | `MM` | `LL` or `MM` | month 01-12 |
| `DD` | `dd` | `dd` | day of month |
| `ddd` | `EEE` | `ccc` | weekday short name |
| `HH:mm:ss` | `HH:mm:ss` | `HH:mm:ss` | time |
| `A` | `a` | `a` | AM/PM |
| `X` | `t` | `X` | Unix seconds |
| `GGGG` / `WW` | `RRRR` / `II` | `kkkk` / `WW` | ISO week year / week |

- `getTimezoneOffset()` is in minutes and positive west of UTC.
- `toISOString()` throws `RangeError` on an invalid date;
  `JSON.stringify(new Date(NaN))` gives `null`.
- `getYear()` returns year minus 1900. Port it as written if fixtures show it.
- Temporal is not available on Node 20 or 22. Do not introduce it.

## 9. Regex dialect

Same engine, so patterns carry over unchanged unless the port changes flags,
object lifetime or the API used.

- A regex literal creates a new object each time it is evaluated. Hoisting a
  `/g` or `/y` regex to module scope makes `test` and `exec` stateful through
  `lastIndex` (T18).
- Adding `u` changes `.` and character classes to code points and makes
  invalid escapes (`\-` outside a class, `\a`) syntax errors (T19). The `v`
  flag is available on Node 20.
- `str.replace('a', 'b')` with a string pattern replaces the first match
  only. `replaceAll` with a regex requires the `g` flag or throws
  `TypeError`.
- Replacement patterns: `$&` whole match, `$1`, `$<name>`, `$$` literal
  dollar. `\1` in a replacement string is literal text.
- `split` with a capturing regex includes the captures in the result:
  `'a-b'.split(/(-)/)` is `['a', '-', 'b']`.
- Legacy static properties `RegExp.$1` to `RegExp.$9` still work in V8 and
  hold the last successful match globally. Replace them with the match
  result of the specific call.
- Lookbehind, named groups, `s` and `d` flags exist on Node 20. Inline
  modifiers such as `(?i:...)` do not.

## 10. I/O, paths, process, environment

| CommonJS | ESM on Node 20+ |
| --- | --- |
| `__dirname`, `__filename` | `import.meta.dirname`, `import.meta.filename` (Node 20.11+), or `fileURLToPath(new URL('.', import.meta.url))` |
| `require('./data.json')` | `import data from './data.json' with { type: 'json' }`, or `JSON.parse(readFileSync(...))` |
| `require.resolve('pkg')` | `import.meta.resolve('pkg')` (returns a URL string) or `createRequire(import.meta.url).resolve` |
| `require.main === module` | `import.meta.url === pathToFileURL(process.argv[1]).href` (breaks on symlinks and extensionless bins; test it) |
| conditional `require` inside a function | `createRequire(import.meta.url)` for sync loading, or `await import()` which makes the caller async |
| `require.cache` manipulation | no ESM equivalent; keep that unit CommonJS or redesign |

The `assert { type: 'json' }` form is a syntax error on Node 22+; use `with`.
JSON modules are cached and shared like `require`d JSON, so mutations are
visible to every importer in both.

- `fs.exists` is deprecated and its callback has no error argument. Use
  `fs.existsSync` or `fs.promises.access`.
- Keep sync file APIs sync. Converting `readFileSync` to `await readFile`
  changes the function's signature and its callers.
- `process.env.X` is always a string or `undefined`. Source code that does
  `if (process.env.DEBUG)` treats `'0'` and `'false'` as true; keep that.
- `url.parse` is lenient and accepts relative URLs; `new URL('/a')` throws
  `ERR_INVALID_URL` without a base. `querystring` and `URLSearchParams`
  encode differently (T29).

## 11. Module layout, packaging, naming, visibility

- Set `"type": "module"` and an `exports` map in `package.json`. Under
  `moduleResolution: NodeNext`, relative imports need the `.js` extension in
  the TypeScript source (`import { x } from './util.js'` for `util.ts`).
- `exports` blocks deep imports. If consumers did `require('lib/lib/util')`,
  list that subpath in `exports` or record the break in the contract.
- `module.exports = fn` (callable module) is the trickiest shape. ESM
  importers of the old package got `fn` as the default import. CommonJS
  consumers that `require()` an ES module (Node 20.19+, 22.12+) get the
  namespace object unless the module exports the name `'module.exports'`
  (T11). TypeScript 5.6+ accepts string export names:

```ts
// src/index.ts: keeps require('lib')(input) and import lib from 'lib' working
function parse(input: string): Ast { /* ... */ }
const api = Object.assign(parse, { version: '2.3.0', parse });
export default api;
export { api as 'module.exports' };
```

- If CommonJS consumers on Node versions without `require(esm)` matter, ship
  a dual build (`exports` with `import` and `require` conditions) and test
  both entry points.
- AMD `define([...], factory)` and UMD wrappers: drop the wrapper, turn the
  factory's parameters into imports and its return value into exports. If
  browser `<script>` consumers exist, add an IIFE build with a bundler and
  keep the same global name.
- Browser globals (`window.MyLib = ...`) become named exports.
- CommonJS returns partially filled `exports` during circular loads; ESM
  throws `ReferenceError` for `let`, `const` and `class` bindings read
  before initialization (T13).
- Visibility: `_name` properties are a convention. TS `private` is
  compile-time only. `#name` is runtime-private and changes enumeration,
  JSON output and Proxy behavior (T36).

Baseline `tsconfig.json` for Node 20:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "verbatimModuleSyntax": true,
    "declaration": true,
    "rootDir": "src",
    "outDir": "dist"
  }
}
```

`lib: ES2023` keeps out APIs that Node 20 lacks (`Promise.withResolvers`,
`Object.groupBy`, Set methods). `target: ES2022` turns on
`useDefineForClassFields` (T8).

## 12. Standard library equivalence

| Source | Target | Notes |
| --- | --- | --- |
| `require(x)`, `module.exports` | `import`, `export` | T11, T12, T13. |
| `util.inherits(Child, Parent)` | `class Child extends Parent` | Statics are inherited through the prototype chain; `Parent.call(this)` must become `super()` (T7). |
| `Array.prototype.slice.call(arguments)` | `...args` | |
| `fn.apply(null, args)` | `fn(...args)` | Same unless `this` matters. |
| `obj.hasOwnProperty(k)` | `Object.hasOwn(obj, k)` | |
| `_.extend`, `$.extend(target, src)` | `Object.assign` or spread | `_.extend` copies inherited enumerable properties (T34). |
| `$.extend(true, ...)`, `_.merge` | keep lodash `merge`, or a custom deep merge | Arrays merge by index: `$.extend(true, {}, {a: [1,2,3]}, {a: [9]})` gives `{a: [9,2,3]}`. |
| `JSON.parse(JSON.stringify(x))` | keep it, or `structuredClone(x)` only if no Date, Map or undefined is involved | T45. |
| `new Buffer(...)` | `Buffer.from`, `Buffer.alloc` | |
| `fs.exists` | `fs.existsSync`, `fs.promises.access` | |
| `url.parse` | `new URL` | Different leniency (section 10). |
| `querystring` | `URLSearchParams`, or keep `qs` for nested keys | T29. `querystring.parse('a=1&a=2')` gives an array; `Object.fromEntries` over `URLSearchParams` keeps the last value. |
| `escape`, `unescape` | `encodeURIComponent`, `TextEncoder` | Section 7. |
| `arguments.callee` | a named function expression | Not allowed in strict mode. |
| `indexOf(x) !== -1` | `includes(x)` | `[NaN].includes(NaN)` is true; `indexOf` returns -1. |
| `$.trim(s)` | `s.trim()` | `$.trim(null)` returns `''`; `null.trim()` throws. |
| `$.isArray`, `$.inArray` | `Array.isArray`, `indexOf` | `$.inArray` returns an index, 0 when found first. |
| `$.map(xs, fn)` | `xs.flatMap` plus a null filter | T35. |
| `$.each(obj, (k, v) => ...)` | `for (const [k, v] of Object.entries(obj))` | Argument order and early exit (T32). |
| `$.ajax`, `$.getJSON` | `fetch` | `fetch` resolves on HTTP 4xx and 5xx; jQuery calls the error handler. jQuery also parses JSON by content type. |
| `Date.parse` with custom strings | explicit parsing | Section 8. |
| `setTimeout(fn, 0)` for deferral | same | Do not swap for `queueMicrotask` (section 4). |

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |
| request, request-promise | HTTP client | global `fetch` (Node 18+), undici, got, ky | replace | request is deprecated since 2020. Its `(err, response, body)` callback, automatic redirects, `json: true` and non-2xx handling all differ from `fetch`. |
| q | promises | native `Promise` | replace | `Q.defer`, `nfcall`, `.done()` have no native names (section 4). |
| bluebird | promises and helpers | native `Promise`, p-map, p-limit | replace | Check `promisifyAll` suffixes, filtered catch, and unhandled rejection behavior (T16). |
| async | control flow | `async`/`await`, p-limit, p-map, p-queue | replace | Keep result shapes and short-circuit-on-error behavior. |
| underscore | utilities | native methods, lodash-es, es-toolkit | replace per call | `_.extend` and array-like handling differ from natives (T33, T34). |
| lodash | utilities | keep lodash (or lodash-es), es-toolkit/compat, native methods | keep or replace per call | Keep it where semantics are subtle: `_.round`, `_.merge`, `_.get` paths, lazy chains (T31). |
| moment | dates | date-fns, Luxon, Day.js | replace, test every format string | moment is in maintenance mode. Day.js has the closest API and tokens; date-fns and Luxon differ (T25 to T28). |
| moment-timezone | timezone conversion | Luxon, `@date-fns/tz` (date-fns 4), `Intl.DateTimeFormat` with `timeZone` | replace | |
| jquery | DOM, ajax, utilities | native DOM APIs and `fetch`; keep jQuery 3 in browser code that is not being rewritten | decide per use | `$.map`, `$.each`, `$.extend`, `return false` in handlers have semantics native code lacks. |
| coffee-script, coffeescript | source language | none | drop | Compile once for the reference output (top of file). |
| mkdirp | recursive mkdir | `fs.mkdir(p, { recursive: true })` (Node 10.12+) | replace | |
| rimraf | recursive delete | `fs.rm(p, { recursive: true, force: true })` (Node 14.14+) | replace | |
| glob | file globbing | glob 10+, fast-glob, tinyglobby, `fs.glob` (Node 22+ only) | replace or upgrade | glob 9+ is promise-based; the glob 7 callback API is gone. Check dotfile and ordering options against fixtures. |
| minimist, optimist | argv parsing | `util.parseArgs` (Node 18.3+), commander, yargs 17 | replace | optimist is deprecated. minimist coerces numeric-looking values to numbers; `parseArgs` returns strings. |
| yargs | CLI parsing | yargs 17+, commander | keep or upgrade | yargs 17 supports ESM. Help text output is often in fixtures; compare it. |
| commander | CLI parsing | commander 12+ | keep | Major versions changed option-to-property mapping; pin and compare help output. |
| chalk | terminal colors | chalk 5 (ESM-only), picocolors, `util.styleText` (Node 20.12+) | keep or replace | Color output depends on TTY detection and `FORCE_COLOR`; set them in fixtures. |
| colors | terminal colors | picocolors, chalk | replace | colors 1.4.1+ was sabotaged by its author in 2022; it also extends `String.prototype`. |
| debug | debug logging | debug 4, `util.debuglog` | keep | Works from ESM. |
| uuid, node-uuid | UUIDs | `crypto.randomUUID()` for v4; uuid for v1, v5, v7 | replace for v4 | node-uuid is the deprecated old name of uuid. |
| node-fetch | HTTP client | global `fetch` | replace | node-fetch 3 is ESM-only. Streams in bodies differ (Node streams versus web streams). |
| xmldom | XML DOM | @xmldom/xmldom, fast-xml-parser | replace | xmldom was renamed to @xmldom/xmldom after security fixes. |
| xml2js | XML to object | keep xml2js, fast-xml-parser | keep | Output object shapes differ between the two; keep xml2js if fixtures record its shape. |
| js-yaml | YAML | js-yaml 4, yaml | keep and upgrade | js-yaml 4 removed `safeLoad`; `load` is safe by default. |
| event-stream, through, through2 | stream helpers | `node:stream` `Transform`, `pipeline` | replace | event-stream 3.3.6 shipped a malicious dependency in 2018. |
| shelljs | shell commands | `node:fs`, `node:child_process`, execa | replace | |
| inherits | prototype inheritance | `class extends` | drop | |
| es6-promise, core-js, babel-polyfill | polyfills | none | drop | Check whether the source relied on polyfill quirks. |
| mocha, chai, sinon | tests | vitest, or `node:test` with `node:assert` | replace or keep | chai 5 is ESM-only. Section 14. |

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | mocha, jasmine, tape, nodeunit, karma, QUnit | vitest, or `node:test`; mocha still works with TypeScript through tsx |
| Assertions and fixtures | chai, should.js, `assert`, sinon, nock, proxyquire, rewire | vitest `expect`, `vi.fn`, `vi.mock`, `vi.useFakeTimers`; msw for HTTP; `vi.mock` replaces proxyquire and rewire |
| Lint | jshint, jslint, old eslint, coffeelint | eslint 9 flat config with typescript-eslint |
| Format | none, js-beautify | prettier |
| Type check | none, or JSDoc with Closure | `tsc --noEmit` with `strict` |
| Coverage | istanbul, nyc, blanket | vitest coverage (v8) or c8 |

- Node 20 cannot run `.ts` files directly. Use `tsc` for builds and tsx for
  running scripts and tests during development.
- mocha tests that use `this.timeout()` or `this.retries()` must keep
  `function` callbacks (T5). In vitest, pass the timeout as an argument.
- Fake timers: sinon and vitest both fake `Date` and timers, but
  `process.nextTick` faking is opt-in in vitest (`toFake`). Check tests that
  depend on tick order.

## 15. Known traps

### T1. `== null` checks rewritten to `=== null`

- Tags: `nullability`
- Source behavior: `x == null` is true for both `null` and `undefined`.
- Target behavior: an `eqeqeq` autofix produces `x === null`, which is false for `undefined`.
- Detect: with `x = undefined`, `x == null` gives `true` in the source and `x === null` gives `false` in the naive port.
- Port rule: keep `x == null` (configure `eqeqeq` with `{ "null": "ignore" }`) or write both comparisons explicitly.

### T2. Loose equality between strings and numbers

- Tags: `numeric`
- Source behavior: `==` converts strings to numbers, so a query parameter `'1'` equals `1`.
- Target behavior: switching to `===` makes the comparison false whenever one side is a string.
- Detect: `'1' == 1` gives `true` in the source; `'1' === 1` gives `false` in the naive port.
- Port rule: find where the values come from (query strings, env vars, DOM values, JSON). Convert explicitly at that boundary with the same rule `==` used (`Number(x)`), then compare with `===`.

### T3. `||` defaults versus default parameters and `??`

- Tags: `nullability`
- Source behavior: `x = x || 1` replaces `0`, `''`, `false` and `NaN` as well as `null` and `undefined`.
- Target behavior: a default parameter `(x = 1)` replaces only `undefined`; `x ?? 1` replaces only `null` and `undefined`.
- Detect: `f(0)` returns `1` with `x = x || 1` and `0` with `function f(x = 1)`.
- Port rule: keep `||` where the source used it. Change to `??` only with a fixture covering falsy inputs or a recorded divergence.

### T4. ESM and class bodies run in strict mode

- Tags: `mutability`, `error-model`
- Source behavior: sloppy-mode scripts alias named parameters with `arguments`, set `this` to the global object in plain calls, and create globals on assignment to undeclared names.
- Target behavior: ES modules and class bodies are strict: no aliasing, `this` is `undefined` in plain calls, and assigning an undeclared name throws `ReferenceError`.
- Detect: `function f(a) { arguments[0] = 2; return a }` then `f(1)` returns `2` in a sloppy CommonJS file and `1` in the ESM port.
- Port rule: grep the source for `arguments[`, bare assignments to undeclared names, `this` in non-method functions, `with`, and octal literals. Rewrite each to explicit code that reproduces the sloppy-mode result.

### T5. Arrow functions change `this` in callbacks

- Tags: `reflection`
- Source behavior: libraries call callbacks with a receiver: EventEmitter listeners get the emitter, jQuery handlers get the element, mocha tests get the test context.
- Target behavior: an arrow function ignores the receiver and uses the enclosing `this`, which is `undefined` at ESM module scope.
- Detect: `ee.on('x', function () { r = this === ee })` sets `r` to `true`; the arrow-function version sees `this` as `undefined`.
- Port rule: keep `function` for any callback that reads `this`, and type it with a `this` parameter (`function (this: EventEmitter) { ... }`).

### T6. Class methods are not enumerable

- Tags: `reflection`
- Source behavior: methods assigned to `Foo.prototype` are enumerable, so `for...in`, `Object.keys(Foo.prototype)`, `_.functions` and mixin helpers see them.
- Target behavior: methods declared in a `class` body are non-enumerable.
- Detect: with `A.prototype.m = function () {}`, `Object.keys(A.prototype)` gives `['m']`; with `class A { m() {} }` it gives `[]`.
- Port rule: search for reflection over prototypes or instances (`for...in`, `_.extend(target, instance)`, mixins, serializers). Where found, define those methods with `Object.defineProperty(..., { enumerable: true })` or keep the prototype assignment.

### T7. Class constructors cannot be called without `new`

- Tags: `error-model`, `reflection`
- Source behavior: ES5 constructors are plain functions: factories use `if (!(this instanceof Foo)) return new Foo(x)`, and subclasses call `Parent.call(this, ...)`.
- Target behavior: calling a class without `new`, including through `Parent.call(this)`, throws `TypeError`.
- Detect: `Foo(1)` returns an instance in the source; with `class Foo` it throws `TypeError: Class constructor Foo cannot be invoked without 'new'`.
- Port rule: if the contract allows calls without `new`, export a factory function with the class name and keep the class internal, or keep the ES5 function form for that export.

### T8. ES2022 class fields overwrite values set during the base constructor

- Tags: `mutability`
- Source behavior: in prototype code, or TS compiled below ES2022, a declared-only field emits nothing, so a value assigned by a method the base constructor called survives.
- Target behavior: with `target: ES2022`, `useDefineForClassFields` is on, and `x: number | undefined;` emits a field definition that runs after `super()` returns and resets `x` to `undefined`.
- Detect: a base constructor calls `this.init()`, and the child's `init` sets `this.x = 1`. With prototype code (`Child.prototype.init = ...`, `Base.call(this)`), `new Child().x` is `1`; the TS class that declares `x: number | undefined;` compiled with `target: ES2022` gives `undefined`.
- Port rule: declare such fields with `declare x: number;` (emits nothing), or move the initialization out of the base constructor path.

### T9. `var` to `let` changes closures in loops

- Tags: `mutability`
- Source behavior: `var` is function-scoped, so closures created in a loop share one variable.
- Target behavior: `let` creates one binding per iteration.
- Detect: pushing `function () { return i }` in `for (var i = 0; i < 3; i++)` and calling each gives `[3, 3, 3]`; with `let` it gives `[0, 1, 2]`.
- Port rule: keep the shared-variable result when fixtures show it (declare the variable once outside the loop). Also check `var` used after its block: `let` turns that into a `ReferenceError`.

### T10. Integer-like object keys come first; Map keeps insertion order and serializes to `{}`

- Tags: `ordering`
- Source behavior: plain objects list integer-like keys in ascending order before string keys, in `Object.keys`, `for...in` and `JSON.stringify`.
- Target behavior: a `Map` keeps pure insertion order, and `JSON.stringify(map)` gives `{}`.
- Detect: inserting keys `'b'`, `'2'`, `'1'`: `Object.keys(obj)` gives `['1', '2', 'b']`; `[...map.keys()]` gives `['b', '2', '1']`.
- Port rule: keep a plain object where order or JSON output is observable. If a `Map` is needed for safety, serialize through `Object.fromEntries` and sort keys the way the object did.

### T11. `module.exports = fn` behind `export default`

- Tags: `reflection`
- Source behavior: CommonJS consumers call the module directly: `require('lib')(opts)`.
- Target behavior: `require()` of an ES module (Node 20.19+, 22.12+) returns the namespace object, so the default export sits on `.default`.
- Detect: `require('lib')('x')` works on the source; against `export default fn` it throws `TypeError: ... is not a function`, because `typeof require('lib')` is `'object'`.
- Port rule: also export the callable as `'module.exports'` (`export { api as 'module.exports' }`, section 11), or ship a dual build with a CommonJS entry that assigns `module.exports`.

### T12. `process.nextTick` and promise order flips at ESM top level

- Tags: `async`, `ordering`
- Source behavior: in a CommonJS module, `process.nextTick` callbacks queued at top level run before promise callbacks.
- Target behavior: an ES module body runs inside a promise job, so promise callbacks queued at top level run first.
- Detect: `Promise.resolve().then(() => o.push('promise')); process.nextTick(() => o.push('nextTick'))` gives `nextTick,promise` in a `.cjs` file and `promise,nextTick` in a `.mjs` file.
- Port rule: if a fixture records ordering from module initialization, move the scheduling into a function called after load, or use one scheduling primitive for both.

### T13. Circular imports: partial exports become TDZ errors

- Tags: `error-model`, `ordering`
- Source behavior: in a CommonJS cycle, the second module sees the first module's `exports` as filled so far; missing properties read as `undefined`.
- Target behavior: in an ESM cycle, reading a `const`, `let` or `class` binding before its module has run throws.
- Detect: `a` requires `b`, and `b` reads `a.y` at load time before `a` sets it: CommonJS gives `undefined`; ESM throws `ReferenceError: Cannot access 'y' before initialization`.
- Port rule: list cycles from `survey.json`. Break each with a third module, or defer the read into a function called after all modules load.

### T14. Synchronous callbacks turned into promises

- Tags: `async`
- Source behavior: some callback APIs call back synchronously on some paths (cache hits, validation errors), so code after the call already sees the result.
- Target behavior: a promise always settles in a later microtask.
- Detect: `let r; parse('x', (e, v) => { r = v }); r` is `'X'` when `parse` calls back synchronously, and `undefined` after the port awaits a promise inside `parse`.
- Port rule: keep the callback API and its timing if callers can observe it. Record any change to sync or async timing as a contract change.

### T15. `util.promisify` keeps only the first result

- Tags: `async`
- Source behavior: callbacks can pass several results, such as request's `(err, response, body)`.
- Target behavior: `util.promisify` resolves with the first result after `err` and drops the rest.
- Detect: `util.promisify((cb) => cb(null, 1, 2))()` resolves to `1`; the source callback received `1` and `2`.
- Port rule: write the promise wrapper by hand and resolve with an object or tuple holding every value the callers use.

### T16. Unhandled rejections terminate the process

- Tags: `async`, `error-model`
- Source behavior: bluebird prints `Unhandled rejection ...` to stderr and keeps running; Node before 15 only warned for native promises.
- Target behavior: Node 15+ exits with code 1 on an unhandled native rejection.
- Detect: `P.reject(new Error('x'))` with bluebird logs and lets a later timer run; `Promise.reject(new Error('x'))` with no handler exits before the timer.
- Port rule: find fire-and-forget promise chains and attach handlers that reproduce the source behavior (log and continue). Do not install a global `unhandledRejection` handler in a library.

### T17. EventEmitter `error` with no listener throws

- Tags: `error-model`, `async`
- Source behavior: `emitter.emit('error', err)` throws `err` when no `error` listener is attached.
- Target behavior: replacing EventEmitter with `EventTarget` or a small typed emitter silently drops the event.
- Detect: `new EventEmitter().emit('error', new Error('x'))` throws `x`; `new EventTarget().dispatchEvent(new Event('error'))` returns `true`.
- Port rule: keep `node:events` `EventEmitter`. Type it with the generic form from `@types/node` (`EventEmitter<{ data: [Buffer]; error: [Error] }>`).

### T18. A hoisted `/g` regex keeps `lastIndex`

- Tags: `regex`, `mutability`
- Source behavior: a regex literal inside a function is a new object on every call, so `lastIndex` starts at 0.
- Target behavior: hoisting it to a module constant (a common cleanup) shares one object, and `test` with `g` resumes from the last match.
- Detect: `const f = (s) => /a/g.test(s)` gives `true, true` for two calls with `'a'`; `const RE = /a/g; const f = (s) => RE.test(s)` gives `true, false`.
- Port rule: do not hoist regexes that carry `g` or `y`, or reset `RE.lastIndex = 0` before each use.

### T19. Adding the `u` flag changes matching and syntax

- Tags: `regex`, `unicode`
- Source behavior: without `u`, `.` and classes match UTF-16 code units, and unknown escapes such as `\-` are literal.
- Target behavior: with `u`, `.` matches a whole code point and unknown escapes are syntax errors.
- Detect: `/^.$/.test('😀')` is `false`; `/^.$/u.test('😀')` is `true`. `new RegExp('\\-', 'u')` throws `SyntaxError: Invalid regular expression: /\-/u: Invalid escape`.
- Port rule: copy flags exactly. Add `u` only with a recorded reason and fixtures that cover astral characters.

### T20. `parseInt` versus `Number`

- Tags: `numeric`
- Source behavior: `parseInt` reads a leading integer and ignores the rest.
- Target behavior: `Number()` and unary `+` reject trailing junk and map `''` and `null` to `0`.
- Detect: `parseInt('12px')` is `12`; `Number('12px')` is `NaN`.
- Port rule: keep the parser the source used, with an explicit radix. Do not replace it because a lint rule prefers `Number`.

### T21. Global `isNaN` coerces; `Number.isNaN` does not

- Tags: `numeric`
- Source behavior: `isNaN(x)` converts `x` to a number first.
- Target behavior: `Number.isNaN(x)` is true only for the value `NaN`.
- Detect: `isNaN('abc')` is `true`; `Number.isNaN('abc')` is `false`.
- Port rule: if the argument can be a non-number, write `Number.isNaN(Number(x))` to keep the source result.

### T22. `x | 0` truncates to signed 32-bit

- Tags: `numeric`
- Source behavior: `x | 0`, `~~x` and `x >> 0` truncate toward zero and wrap into the int32 range.
- Target behavior: rewriting to `Math.trunc(x)` keeps values above 2^31 - 1.
- Detect: `(2 ** 31) | 0` is `-2147483648`; `Math.trunc(2 ** 31)` is `2147483648`.
- Port rule: keep the bitwise form where inputs can exceed the int32 range, or document the range that makes the two equal.

### T23. `toFixed`, `Math.round` and `_.round` disagree

- Tags: `float-format`
- Source behavior: `_.round(1.005, 2)` uses exponent shifting through strings and gives `1.01`.
- Target behavior: `Math.round(1.005 * 100) / 100` gives `1` and `(1.005).toFixed(2)` gives `'1.00'`, because `1.005` is stored as slightly less than 1.005.
- Detect: `_.round(1.005, 2)` is `1.01`; `Math.round(1.005 * 100) / 100` is `1`.
- Port rule: keep the rounding function the source used. For formatted output, `Intl.NumberFormat` with fixed fraction digits matched `_.round` on these inputs; confirm with fixtures.

### T24. `Buffer#slice` shares memory; `Uint8Array#slice` copies

- Tags: `mutability`, `encoding`
- Source behavior: `buf.slice()` returns a view on the same memory, so writes go through to the parent.
- Target behavior: moving to `Uint8Array` makes `slice` return a copy.
- Detect: `const b = Buffer.from([1, 2, 3]); b.slice(0, 1)[0] = 9; b[0]` is `9`; the same with `Uint8Array.from` gives `1`.
- Port rule: use `subarray` wherever the source relied on view semantics (it is a view on both types), and `Uint8Array.prototype.slice.call` or `Buffer.from(view)` where a copy is wanted.

### T25. Date-only strings: `Date` parses UTC, moment parses local

- Tags: `datetime`
- Source behavior: `moment('2024-01-15')` is local midnight.
- Target behavior: `new Date('2024-01-15')` is UTC midnight.
- Detect: with `TZ=America/New_York`, `moment('2024-01-15').toISOString()` is `'2024-01-15T05:00:00.000Z'` and `new Date('2024-01-15').toISOString()` is `'2024-01-15T00:00:00.000Z'`.
- Port rule: parse date-only strings as local explicitly (`new Date(y, m - 1, d)`, date-fns `parse`, or Luxon `DateTime.fromISO(s)`, which uses local zone by default). Pin `TZ` in fixtures.

### T26. moment format tokens are not date-fns tokens

- Tags: `datetime`
- Source behavior: moment `YYYY-MM-DD` is calendar year, month, day of month.
- Target behavior: in date-fns, `YYYY` is the week-numbering year and `DD` is day of year; date-fns 2 and later throw unless `useAdditionalWeekYearTokens` and `useAdditionalDayOfYearTokens` are set.
- Detect: `moment(new Date(2024, 0, 15)).format('YYYY-MM-DD')` is `'2024-01-15'`; date-fns `format(new Date(2024, 0, 15), 'YYYY-MM-DD')` throws `RangeError`.
- Port rule: translate every format string with the table in section 8 and add a fixture per format string.

### T27. moment objects mutate in place

- Tags: `datetime`, `mutability`
- Source behavior: `m.add(1, 'day')` changes `m` and returns the same object.
- Target behavior: date-fns, Luxon and Day.js return a new value and leave the input unchanged.
- Detect: `const a = moment('2024-01-01'); a.add(1, 'day'); a.format('D')` is `'2'`; `const a = new Date(2024, 0, 1); addDays(a, 1); format(a, 'd')` is `'1'`.
- Port rule: find every moment call whose return value is ignored or that is called on a shared instance, and assign the new value back where the source relied on mutation.

### T28. Month arithmetic: `setMonth` overflows, libraries clamp

- Tags: `datetime`
- Source behavior: `d.setMonth(d.getMonth() + 1)` on January 31, 2024 rolls over to March 2.
- Target behavior: date-fns `addMonths`, moment `add(1, 'month')` and Luxon `plus({ months: 1 })` clamp to February 29.
- Detect: from `new Date(2024, 0, 31)`, native `setMonth` gives 2024-03-02; `addMonths` gives 2024-02-29.
- Port rule: keep the arithmetic family the source used. When replacing native math with a library, or moment with native math, write an end-of-month fixture first.

### T29. `querystring` and `URLSearchParams` encode differently

- Tags: `encoding`
- Source behavior: `querystring.stringify` encodes a space as `%20` and leaves `*` and `!` alone.
- Target behavior: `URLSearchParams` encodes a space as `+` and `!` as `%21`.
- Detect: `querystring.stringify({ a: 'b c' })` is `'a=b%20c'`; `new URLSearchParams({ a: 'b c' }).toString()` is `'a=b+c'`.
- Port rule: keep `node:querystring` (still supported) or the `qs` package where the encoded string is observable (signatures, cache keys, fixtures).

### T30. Boolean sort comparators

- Tags: `ordering`
- Source behavior: legacy code sorts with `(a, b) => a > b`. Modern V8 treats `true` as 1 and `false` as 0 (equal), so the result is not sorted.
- Target behavior: TypeScript rejects a boolean comparator, and the natural fix `(a, b) => a - b` sorts correctly.
- Detect: `[3, 1, 2].sort((a, b) => a > b)` gives `[3, 1, 2]` on Node 11+; `[3, 1, 2].sort((a, b) => a - b)` gives `[1, 2, 3]`.
- Port rule: fixtures recorded on current Node show the unsorted output. Either reproduce it (`(a, b) => Number(a > b)`) or record the fix as a divergence.

### T31. lodash chains are lazy

- Tags: `ordering`
- Source behavior: `_(xs).map(f).take(n).value()` calls `f` only for the elements it needs.
- Target behavior: `xs.map(f).slice(0, n)` calls `f` for every element.
- Detect: `_([1, 2, 3]).map(f).take(1).value()` calls `f` once; `[1, 2, 3].map(f).slice(0, 1)` calls it 3 times.
- Port rule: if `f` has side effects or is expensive, use a loop with early exit or a generator.

### T32. `_.each` and `$.each` stop when the callback returns `false`

- Tags: `ordering`
- Source behavior: lodash, underscore and jQuery iteration helpers exit early on an explicit `false` return.
- Target behavior: `Array.prototype.forEach` ignores return values.
- Detect: `_.each([1, 2, 3], (x) => { seen.push(x); return false })` leaves `seen` as `[1]`; `forEach` leaves `[1, 2, 3]`.
- Port rule: when a callback can return `false` (watch CoffeeScript implicit returns, T37), port to a `for...of` loop with `break` at the same point.

### T33. lodash and underscore treat `{ length: n }` as array-like

- Tags: `reflection`
- Source behavior: collection functions iterate any object with a non-negative integer `length` by index.
- Target behavior: `Object.values` and `Object.entries` iterate own properties.
- Detect: `_.map({ length: 1, x: 'y' }, (v) => v)` gives `[undefined]`; `Object.values({ length: 1, x: 'y' })` gives `[1, 'y']`.
- Port rule: check whether user-supplied objects can carry a `length` key. If so, keep the lodash call or reproduce the array-like check.

### T34. `_.extend` copies inherited properties

- Tags: `reflection`, `mutability`
- Source behavior: underscore `_.extend` and lodash `_.assignIn` copy own and inherited enumerable properties.
- Target behavior: `Object.assign` and spread copy own properties only.
- Detect: `_.extend({}, Object.create({ a: 1 }))` gives `{ a: 1 }`; `Object.assign({}, Object.create({ a: 1 }))` gives `{}`.
- Port rule: use `Object.assign` only when the sources are plain objects. For class instances or prototype-based defaults, copy with a `for...in` loop.

### T35. `$.map` flattens arrays and drops `null`

- Tags: `nullability`
- Source behavior: `$.map` flattens one level of returned arrays and removes `null` and `undefined` results.
- Target behavior: `Array.prototype.map` keeps one output per input.
- Detect: `$.map([1, 2], (x) => [x, x])` gives `[1, 1, 2, 2]`; `[1, 2].map(...)` gives `[[1, 1], [2, 2]]`.
- Port rule: port as `xs.flatMap((x, i) => { const r = fn(x, i); return r == null ? [] : r })`.

### T36. `_name` to `#name` changes JSON and enumeration

- Tags: `reflection`
- Source behavior: underscore-prefixed properties are ordinary properties: enumerable, serialized, and readable by consumers.
- Target behavior: `#private` fields are invisible to `JSON.stringify`, `Object.keys`, spread and outside code.
- Detect: `JSON.stringify` of an instance with `this._hits = 0` gives `{"_hits":0}`; with `#hits` it gives `{}`.
- Port rule: keep `_name` properties (TS `private` if you want compile-time checks) unless the contract shows nobody reads or serializes them.

### T37. CoffeeScript implicit returns

- Tags: `nullability`
- Source behavior: every CoffeeScript function returns its last expression; a trailing loop returns an array of its body values.
- Target behavior: a TypeScript port without `return` returns `undefined`, and a `void` callback no longer returns `false` to lodash, jQuery or DOM handlers.
- Detect: `f = (xs) -> for x in xs then x * 2` makes `f([1, 2])` return `[2, 4]`; the TS port with a `for` statement returns `undefined`.
- Port rule: read the compiled JavaScript for every function and port its return value. Pay attention to handlers whose last expression can be `false`: lodash `_.each` stops early (T32), and jQuery treats `return false` as `preventDefault` plus `stopPropagation`.

### T38. CoffeeScript `a ? b` is `??`, not `||`

- Tags: `nullability`
- Source behavior: `a ? b` compiles to `a != null ? a : b`, and `a ?= b` assigns only when `a` is null or undefined.
- Target behavior: porting by eye to `a || b` replaces falsy values too.
- Detect: with `x = 0`, CoffeeScript `x ? 5` gives `0`; `x || 5` gives `5`.
- Port rule: map `a ? b` to `a ?? b`, `a ?= b` to `a ??= b`, postfix `a?` to `a != null`, and `a?.b` to `a?.b`.

### T39. CoffeeScript soak calls check for a function

- Tags: `nullability`, `error-model`
- Source behavior: `a?()` compiles to `if (typeof a === "function") a()`.
- Target behavior: TS `a?.()` checks only for `null` and `undefined` and throws on any other non-function.
- Detect: with `a = 5`, CoffeeScript `a?()` gives `undefined`; TS `a?.()` throws `TypeError: a is not a function`.
- Port rule: port `a?()` as `typeof a === 'function' ? a() : undefined`.

### T40. CoffeeScript `==`, `is`, `in` and `of`

- Tags: `numeric`, `reflection`
- Source behavior: CoffeeScript `==` and `is` compile to `===`; `x in arr` is array membership; `k of obj` is the JavaScript `in` operator.
- Target behavior: copying the operators into TypeScript gives loose equality and key lookup.
- Detect: CoffeeScript `'a' in ['a', 'b']` is `true`; JavaScript `'a' in ['a', 'b']` is `false` (it checks keys `0` and `1`).
- Port rule: map `==`/`is` to `===`, `!=`/`isnt` to `!==`, `x in arr` to `arr.indexOf(x) >= 0` (not `includes`, which matches `NaN`), and `k of obj` to `k in obj`.

### T41. CoffeeScript ranges pick their direction at runtime

- Tags: `ordering`, `numeric`
- Source behavior: `[a..b]` counts down when `a > b`, so `for i in [0..n-1]` with `n = 0` iterates over `0` and `-1`.
- Target behavior: `for (let i = 0; i <= n - 1; i++)` runs zero times.
- Detect: with `n = 0`, CoffeeScript `(i for i in [0..n-1])` gives `[0, -1]`; the TS loop gives `[]`.
- Port rule: for ranges with non-literal bounds, reproduce the direction check, or record the fix as a divergence. `[a...b]` excludes `b`; `arr[1..2]` is `arr.slice(1, 3)`.

### T42. CoffeeScript `for k of obj` includes inherited properties

- Tags: `reflection`
- Source behavior: `for k, v of obj` compiles to `for...in`; only `for own` adds a `hasOwnProperty` check.
- Target behavior: `Object.entries(obj)` lists own properties only.
- Detect: with `o = Object.create({ inherited: 1 }); o.own = 2`, CoffeeScript `(k for k of o)` gives `['own', 'inherited']`; `Object.keys(o)` gives `['own']`.
- Port rule: port `for own` to `Object.keys`/`Object.entries`, and plain `for ... of` to `for...in`.

### T43. CoffeeScript 1 copies static properties at `extends` time

- Tags: `reflection`, `mutability`
- Source behavior: CoffeeScript 1 `__extends` copies the parent's own static properties onto the child once, when the class is defined.
- Target behavior: ES classes (and CoffeeScript 2) inherit statics through the prototype chain, so later changes to the parent show through.
- Detect: `class A then @x: 1`, `class B extends A`, then `A.x = 2`: `B.x` is `1` in CoffeeScript 1 and `2` in a TS class.
- Port rule: check for static properties written after class definition. Where found in CoffeeScript 1 code, give the child its own static copy.

### T44. CoffeeScript `=>` methods are bound per instance

- Tags: `reflection`
- Source behavior: a class method defined with `=>` is bound to its instance in the constructor, so it can be passed around detached.
- Target behavior: a TS prototype method loses `this` when detached.
- Detect: `g = new C('z').greet; g()` returns `'hi z'` in CoffeeScript; the TS port throws `TypeError: Cannot read properties of undefined (reading 'name')`.
- Port rule: port `=>` methods as arrow-function class fields (`greet = () => ...`). They become own properties, so tests that spy on `C.prototype.greet` must spy on the instance instead.

### T45. JSON round-trip clone versus `structuredClone`

- Tags: `mutability`
- Source behavior: `JSON.parse(JSON.stringify(x))` turns Dates into strings, drops `undefined` and functions, and turns Maps into `{}`.
- Target behavior: `structuredClone(x)` keeps Dates, `undefined` and Maps, and throws on functions.
- Detect: cloning `{ d: new Date(0), u: undefined }` gives `{ d: '1970-01-01T00:00:00.000Z' }` with JSON and `{ d: Date, u: undefined }` with `structuredClone`.
- Port rule: keep the JSON round trip where its lossy output is observed downstream.
