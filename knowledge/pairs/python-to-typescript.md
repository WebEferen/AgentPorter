# Python to TypeScript

| Field | Value |
| --- | --- |
| Source | Python 3.9 to 3.13 (CPython) |
| Target | TypeScript 5.x on Node 20+, ES2022 or later, ESM |
| Status | full |
| Last reviewed | 2026-10-20 |

How to use this file: the `strategy` skill loads it to seed the idiom map for a
port, and the `implement` skill reads the sections a unit's risk tags point at.
Every trap carries risk tags from this vocabulary, which `porter.py decompose`
also emits for units:

`regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`,
`unicode`, `encoding`, `io`, `locale`, `mutability`, `nullability`,
`error-model`, `ordering`.

Conventions in this file:

- "TS" in a Detect line means the naive port, run on Node. Every Detect line
  was run on CPython 3.14 and Node 24. Results that depend on the Python
  version were also run on 3.9, 3.12 and 3.13, and the trap says so.
- Helpers named `pyXxx` are defined in this file. Put the ones a port needs in
  one internal module (for example `src/internal/py.ts`), unexported from the
  package entry, with their own tests. The helper bodies here were tested
  against CPython on random inputs; keep them as written.
- Version facts about Node were checked on Node 22.15 and 24.18. For anything
  newer than Node 20, check the runtime the port targets before relying on it.

## 1. Type system mapping

| Python | TypeScript | Notes |
| --- | --- | --- |
| `int` | `number` or `bigint` | Decide per value domain, rule 1 below. |
| `float` | `number` | Same IEEE 754 double. Printing differs (T5). |
| `bool` | `boolean` | Python `bool` is an `int` subclass: `True + 1 == 2`, `sum(flags)` counts. |
| `complex` | small class `{ re: number; im: number }` | No built-in. |
| `str` | `string` | Code points versus UTF-16 code units (section 7). |
| `bytes`, `bytearray` | `Uint8Array` | `Buffer` only inside Node-specific modules (section 7). |
| `memoryview` | `Uint8Array` view (`subarray`) or `DataView` | |
| `list[T]` | `T[]` | |
| `tuple[A, B]` | `readonly [A, B]` | Comparison and hashing differ (T44, T51). |
| `tuple[T, ...]` | `readonly T[]` | |
| `dict[str, V]` | `Map<string, V>` | `Record<string, V>` only for fixed, non-numeric keys (T40). |
| `dict[K, V]`, tuple or object `K` | `Map<string, V>` with an encoded key | T51. |
| `set[T]`, `frozenset[T]` | `Set<T>`, `ReadonlySet<T>` | Members compare by identity for objects and arrays. |
| `None` | `null` or `undefined` | Section 3. |
| `Optional[T]`, `T \| None` | `T \| null` for values, `x?: T` for parameters and properties | Section 3. |
| `Union[A, B]` | `A \| B` | Narrow with `typeof`, `instanceof`, or a `kind` field. |
| `Any`, `object` | `unknown` | Never `any` in ported code. |
| `Callable[[A, B], R]` | `(a: A, b: B) => R` | |
| `Iterable[T]`, `Iterator[T]` | `Iterable<T>`, `Iterator<T>` | |
| `Generator[Y, S, R]` | `Generator<Y, R, S>` | Parameter order differs. |
| `AsyncIterator[T]`, `AsyncGenerator[Y, S]` | `AsyncIterator<T>`, `AsyncGenerator<Y, void, S>` | |
| `Awaitable[T]`, `Coroutine[Any, Any, T]` | `Promise<T>` | Coroutines are lazy, promises are not (T87). |
| `TypeVar("T", bound=X)` | `<T extends X>` | Constrained TypeVars become overloads. |
| `Literal["a", "b"]` | `"a" \| "b"` | |
| `Final`, `ClassVar[T]` | `const` or `readonly`, `static` | |
| `type[C]` | `typeof C` or `new (...args: any[]) => C` | |
| `TypedDict` | `interface` | `total=False` and `NotRequired` become `?`. |
| `Protocol` | `interface` | Structural in both. |
| `NamedTuple` | class with `readonly` fields, or a `readonly` tuple type | A NamedTuple is also indexable, iterable and ordered. |
| `@dataclass` | `class` | Rule 2 below. |
| `Enum`, `IntEnum`, `StrEnum` | `as const` object plus a union type | T57. |
| `NewType("UserId", int)` | `number & { readonly __brand: "UserId" }` | |
| `TypeGuard[T]` | `x is T` | |
| `decimal.Decimal` | `Decimal` from decimal.js | T13. |
| `fractions.Fraction` | fraction.js or a small class | |
| `datetime`, `date`, `timedelta` | section 8 | |
| `re.Pattern` | `RegExp` | Section 9. |
| `pathlib.Path` | `string` | Section 10. |

Rules that do not fit the table:

1. `int` to `number` or `bigint`. Use `number` when every value is provably
   within `Number.MAX_SAFE_INTEGER` (`2**53 - 1`): counts, lengths, indexes,
   sizes, ports, small arithmetic. Use `bigint` when values can exceed it:
   64-bit ids, hashes, checksums, nanosecond timestamps, factorials, bit masks
   wider than 32 bits, `pow(a, b, m)`, or any place the source relies on exact
   unbounded arithmetic. `bigint` does not mix with `number` (TypeError), has
   no `JSON` support (T66) and no `Math.*`. Record the choice per public
   symbol in the idiom map.
2. Dataclasses generate behavior that TS classes do not have: field-wise
   `__eq__`, `__repr__`, tuple-style ordering with `order=True`, and
   `__hash__` with `frozen=True`. Write each one the source relies on.
   `frozen=True` maps to `readonly` fields plus `Object.freeze(this)`, but only
   in classes that are never subclassed (a frozen base blocks subclass field
   assignment).

   ```python
   @dataclass(frozen=True, order=True)
   class Version:
       major: int
       minor: int = 0
   ```

   ```ts
   export class Version {
     readonly major: number;
     readonly minor: number;

     constructor(major: number, minor = 0) {
       this.major = major;
       this.minor = minor;
       Object.freeze(this);
     }

     equals(other: Version): boolean {
       return this.major === other.major && this.minor === other.minor;
     }

     compare(other: Version): number {
       return this.major - other.major || this.minor - other.minor;
     }

     toString(): string {
       return `Version(major=${this.major}, minor=${this.minor})`;
     }
   }
   ```

   Do not use constructor parameter properties
   (`constructor(readonly x: number)`): Node's built-in type stripping and
   TS 5.8 `--erasableSyntaxOnly` reject them.
3. TS typing is structural; Python `isinstance` is nominal. Where the source
   dispatches with `isinstance` between classes of the same shape, keep real
   classes and `instanceof`, or add a `kind` discriminant. Interfaces do not
   exist at runtime.
4. Class attributes are shared. `class A: items = []` is one list for every
   instance, and `self.items.append(x)` mutates it. A TS field initializer
   (`items: string[] = []`) creates one per instance. If the source relies on
   sharing, use `static items: string[] = []`.
5. Dunder methods have no operator hook in TS. Map them to methods:
   `__eq__` to `equals`, `__lt__` and `functools.total_ordering` to `compare`,
   `__hash__` to a `key(): string` used for `Map` keys, `__str__` to
   `toString`, `__repr__` to `[util.inspect.custom]` or a `repr()` method,
   `__len__` to a `length` or `size` getter, `__iter__` to
   `[Symbol.iterator]`, `__contains__` to `has`, `__getitem__` to `get` or
   `at`, `__call__` to a plain function, `__enter__`/`__exit__` to
   `[Symbol.dispose]` (section 4). Avoid `Proxy` for `__getattr__`; list the
   dynamic names explicitly.
6. `@property` maps to `get`, `@x.setter` to `set`, `@staticmethod` to
   `static`, `@classmethod` to `static` using `this` for the class.
   `@functools.cached_property` maps to a getter that stores into a private
   field. `__slots__` has no equivalent and needs none.
7. Multiple inheritance and mixins: use composition, or mixin functions that
   take a base class and return `class extends Base { ... }`. Do not
   reproduce Python MRO.
8. Function decorators become higher-order functions. TS 5.x standard
   decorators exist but have different semantics; use them only when the
   strategy says so.

## 2. Error model

Python and TS both use exceptions, so keep exceptions. Do not convert to
result types unless the strategy records that decision.

Default mapping for `.porter/contract/error-map.json`. Every exception type
that appears in a fixture or in the source's documented API gets a named TS
class with the same name, exported from one `errors.ts`, except where the row
says otherwise. Same names keep fixture comparison mechanical.

| Python | TS default | Notes |
| --- | --- | --- |
| Library base `FooError(Exception)` | `class FooError extends Error` | Set `name` explicitly; minifiers rename classes. |
| Library subclasses | same names, extending the mapped parent | Keep the hierarchy; callers catch parents. |
| `ValueError` | exported `class ValueError extends Error` | No JS equivalent. Do not extend the library base: Python's `except FooError` does not catch `ValueError`. |
| `KeyError`, `IndexError` | exported classes, under `LookupError` only if the source catches `LookupError` | `str(KeyError(k))` is `repr(k)` (T59). |
| `TypeError` | built-in `TypeError` | |
| `NotImplementedError` | exported class, or `abstract` methods | |
| `FileNotFoundError`, `PermissionError`, `OSError` | Node system error; branch on `err.code` (`"ENOENT"`, `"EACCES"`) | Wrap only if the contract exposes the class. |
| `TimeoutError`, `asyncio.TimeoutError` | `DOMException` with `name === "TimeoutError"` from `AbortSignal.timeout`, or an exported class | `asyncio.TimeoutError` is a separate class before 3.11. |
| `asyncio.CancelledError` | abort reason, `DOMException` with `name === "AbortError"` | |
| `StopIteration` | iterator result `{ done: true }` | Never thrown. |
| `ExceptionGroup` (3.11+) | `AggregateError` | |
| `json.JSONDecodeError` | `SyntaxError` from `JSON.parse` | Messages differ completely. |
| `re.error` (`re.PatternError` in 3.13+) | `SyntaxError` from `new RegExp` | Build patterns at module load. |
| `UnicodeDecodeError` | `TypeError` from `TextDecoder` with `fatal: true` | T69. |
| `ZeroDivisionError`, `OverflowError` | exported classes thrown by explicit checks | JS arithmetic never throws (T8). |
| `RecursionError` | `RangeError` (stack overflow) | Depth limits differ; never test them. |
| `AssertionError` from `assert` | not part of the contract | `python -O` strips asserts. |
| `KeyboardInterrupt`, `SystemExit` | signal handlers, `process.exitCode` | Not exceptions in TS. |

Error class shape:

```ts
export class FooError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "FooError";
  }
}

export class NotFoundError extends FooError {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "NotFoundError";
  }
}
```

Rules:

- `raise X(msg) from e` becomes `throw new X(msg, { cause: e })`.
  `raise X from None` has no cause. Implicit chaining (`__context__`) has no
  equivalent; add `cause` only when tests or messages use it.
- `except A:` catches `A` and subclasses only. A TS `catch` catches
  everything, including non-`Error` values, so filter and rethrow (T62):

  ```ts
  try {
    parse(text);
  } catch (e) {
    if (!(e instanceof ValueError)) throw e;
    return fallback;
  }
  ```

- `try/except/else/finally`: the `else` body runs only when the `try` body did
  not raise, and its own exceptions are not caught by the `except` clauses.

  ```ts
  let ok = false;
  try {
    risky();
    ok = true;
  } catch (e) {
    if (!(e instanceof ValueError)) throw e;
    handle(e);
  } finally {
    cleanup();
  }
  if (ok) elseBody();
  ```

  This runs `elseBody` after `cleanup`; Python runs `else` before `finally`.
  If the order is observable, put the `else` body inside the `try` after
  `ok = true` and rethrow its errors past the filter.
- `str(e)` is the message for one argument and `str(e.args)` for several:
  `str(ValueError("a", 1))` is `"('a', 1)"`. Copy the exact text fixtures
  record. Built-in messages change between Python versions (T60).
- Never compare stack traces or `repr(e)` text in fixtures.
- `warnings.warn` maps to `process.emitWarning`, which prints to stderr and is
  not an error.
- `instanceof` fails across two copies of a module (T61). Ship one module
  format and add a brand check for errors other packages catch:

  ```ts
  const BRAND: unique symbol = Symbol.for("foo-lib/FooError");

  export class FooError extends Error {
    readonly [BRAND] = true;
    constructor(message: string, options?: ErrorOptions) {
      super(message, options);
      this.name = "FooError";
    }
  }

  export function isFooError(e: unknown): e is FooError {
    return typeof e === "object" && e !== null && BRAND in e;
  }
  ```

## 3. Null and absence

Python has one absent value, `None`. TS has `null` and `undefined`. Default:

- Values that a Python function returns or stores as `None`, and anything that
  crosses JSON or fixtures: `null`. `JSON.stringify` drops `undefined`
  properties (T67), Python writes `null`.
- Optional parameters and optional object properties: `?` (`undefined`).
- A function with no `return` returns `None` in Python and `undefined` in TS.
  Type it `void`; if a fixture records `None` for it, the harness must treat
  `undefined` as `None`.

Rules:

- `x is None` becomes `x === null` (or `x == null` when both `null` and
  `undefined` can arrive; pick one convention per module and record it).
- `if x:` and `x or y` use Python truthiness: `None`, `False`, `0`, `0.0`,
  `""`, empty list, dict, set and tuple, and objects with `__bool__` or
  `__len__` returning false. In TS `[]` and `{}` are truthy (T52). Port the
  condition the source means: `x !== null`, `x.length > 0`, `x.size > 0`.
- `x or default` is not `x ?? default`: `0 or 5` is `5`, `0 ?? 5` is `0`.
  `x || default` matches for numbers and strings but not for containers.
- `d.get(k, default)` returns a stored `None` when the key exists.
  `m.get(k) ?? dflt` replaces it (T53). Use `m.has(k) ? m.get(k) : dflt`.
- JS default parameter values apply when the argument is `undefined`, not
  `null`. Python defaults apply only when the argument is omitted. A Python
  caller passing `None` explicitly gets `None`; a TS caller passing `null` gets
  `null`. The common idiom `def f(x=None): if x is None: x = []` becomes
  `function f(x: T[] | null = null) { const xs = x ?? []; ... }`.
- `getattr(obj, "name", None)` becomes `obj.name ?? null` for known optional
  fields. For dynamic names, see section 1 rule 5.
- A key that is missing differs from a key whose value is `None`. Turn on
  `exactOptionalPropertyTypes` so `{ a?: T }` (may be missing) and
  `{ a: T | undefined }` are different types.
- Turn on `noUncheckedIndexedAccess` so `xs[i]` and `rec[k]` are
  `T | undefined`, which mirrors where Python would raise `IndexError` or
  `KeyError` (T49).
- Sentinels (`_MISSING = object()`) become `const MISSING = Symbol("MISSING")`.

## 4. Concurrency and async

| Python | TS | Notes |
| --- | --- | --- |
| `async def f()` | `async function f()` | The JS body runs at call time up to the first `await`; a Python coroutine runs only when awaited or scheduled (T87). |
| `await x` | `await x` | |
| `asyncio.run(main())` | top-level `await main()` in the ESM entry | |
| `asyncio.create_task(c)` | call the async function and keep the promise | Attach a rejection handler or await it later (T89). |
| `asyncio.gather(*cs)` | `Promise.all(ps)` | Neither cancels the others on failure. |
| `gather(..., return_exceptions=True)` | `Promise.allSettled(ps)` | Map `{ status, value, reason }` back to values or errors. |
| `asyncio.wait_for(c, t)` | pass `AbortSignal.timeout(ms)` to a signal-aware API | `Promise.race` leaves the loser running (T88). |
| `task.cancel()`, `CancelledError` | `AbortController.abort()`, `AbortError` | Cancellation is cooperative: only code that checks the signal stops. |
| `asyncio.sleep(s)` | `await setTimeout(ms)` from `node:timers/promises` | Seconds to milliseconds. |
| `asyncio.sleep(0)` | `await setImmediate()` from `node:timers/promises` | Yields to other tasks. |
| `asyncio.Lock`, `Semaphore` | small mutex, or `p-limit` | Only needed when the critical section awaits. |
| `asyncio.Queue` | small queue class, or `p-queue` | |
| `async with` | `await using` or `try/finally` | |
| `async for` | `for await` | |
| `contextvars.ContextVar` | `AsyncLocalStorage` from `node:async_hooks` | |
| `threading.Thread`, `ThreadPoolExecutor` for I/O | async Node APIs | No threads needed for I/O. |
| `ProcessPoolExecutor`, CPU-bound threads | `worker_threads`, or `piscina` | Data crosses by structured clone. |
| `threading.Lock` around plain state | nothing | One thread per isolate; code between two `await`s runs without interruption. |
| `time.sleep(s)` in sync code | restructure as async | Blocking the event loop stalls everything. |

Patterns:

```python
async def fetch_all(urls):
    return await asyncio.gather(*(fetch_one(u) for u in urls))

result = await asyncio.wait_for(fetch_one(url), timeout=5)
```

```ts
export async function fetchOne(
  url: string,
  opts: { signal?: AbortSignal } = {},
): Promise<string> {
  const res = await fetch(url, { signal: opts.signal ?? null });
  return res.text();
}

export async function fetchAll(urls: string[]): Promise<string[]> {
  return Promise.all(urls.map((u) => fetchOne(u)));
}

const result = await fetchOne(url, { signal: AbortSignal.timeout(5_000) });
```

```ts
export class Mutex {
  #tail: Promise<void> = Promise.resolve();

  async run<T>(fn: () => Promise<T>): Promise<T> {
    const prev = this.#tail;
    let release!: () => void;
    this.#tail = new Promise<void>((r) => (release = r));
    await prev;
    try {
      return await fn();
    } finally {
      release();
    }
  }
}
```

Context managers:

- `with x as y:` maps to `using y = x;` when `x` has `[Symbol.dispose]()`, and
  `async with` to `await using`. Syntax needs TS 5.2+ and the
  `esnext.disposable` lib. Node 24 runs `using` natively (checked); Node 22
  does not parse it (checked), so TS must downlevel it, which needs
  `Symbol.dispose` at runtime (present on Node 22, checked). On Node 20,
  check `typeof Symbol.dispose` and polyfill if missing. Without any of this,
  use `try/finally`.
- `@contextlib.contextmanager` generators become a function that returns
  `{ [Symbol.dispose]() { ... } }`.
- `__exit__` returning `True` suppresses the exception. `Symbol.dispose`
  cannot; use `try/catch` for those.

Rules:

- A sync Python API that does blocking I/O (`requests`, `open`) either stays
  sync in TS with `*Sync` fs calls, or becomes async. Becoming async changes
  the public contract; record it in `decisions.md`.
- Node exits with code 1 on an unhandled rejection (checked on Node 24);
  Python logs "Task exception was never retrieved" and continues (T89).
- Interleaving order between concurrent tasks is not part of the contract.
  Fixtures must not depend on it; sort or key results instead.

## 5. Iteration, generators, laziness

| Python | TS |
| --- | --- |
| `def g(): yield x` | `function* g() { yield x; }` |
| `yield from h()` | `yield* h()` (the return value of `h` comes back in both) |
| `x = yield y` with `g.send(v)` | `const x = yield y;` with `g.next(v)` |
| `g.throw(e)`, `g.close()` | `g.throw(e)`, `g.return(undefined)` |
| `next(it)` | `it.next()`, check `done` |
| `next(it, default)` | `const r = it.next(); r.done ? dflt : r.value` |
| `__iter__` / `__next__` raising `StopIteration` | `[Symbol.iterator]()` returning `{ next() }` |
| `range(a, b, step)` | `for (let i = a; i < b; i += step)` for a positive `step`, or the `range` helper below |
| `enumerate(xs, start)` | `xs.entries()` or an index loop |
| `zip(a, b)` | `zip` helper below (stops at the shortest) |
| `zip(a, b, strict=True)` (3.10+) | `zip` that throws on a length mismatch |
| `map(f, xs)`, `filter(p, xs)` | lazy: a generator, or `Iterator.prototype.map` and `filter` (Node 22+). `Array.prototype.map` is eager (T46). |
| `reversed(xs)` | `xs.toReversed()` (Node 20+) or a reverse loop |
| `sorted(xs)` | `xs.toSorted(cmp)` (Node 20+); always pass a comparator (T42) |
| `any`, `all` | `some`, `every` |
| `sum`, `min`, `max` | `reduce`; `max([])` raises, `Math.max()` returns `-Infinity`, and `Math.max(...xs)` throws `RangeError` for very large arrays (1e6 elements, checked) |
| list comprehension | `map`/`filter` or a loop |
| dict comprehension | `new Map(...)` or `Object.fromEntries(...)` |
| set comprehension | `new Set(...)` |
| `[x for row in rows for x in row]` | `rows.flatMap((row) => row)` |
| `for ... else` | a `found` flag, or a labeled block |
| `itertools.chain(a, b)` | `function*` with `yield* a; yield* b;` |
| `itertools.islice(it, n)` | `Iterator.prototype.take(n)` (Node 22+) or a helper |
| `itertools.groupby` | `groupby` helper below; not `Object.groupBy` (T45) |
| `itertools.accumulate`, `pairwise` (3.10), `batched` (3.12), `product`, `permutations`, `combinations`, `zip_longest`, `takewhile`, `dropwhile`, `count`, `cycle`, `repeat`, `starmap`, `compress`, `filterfalse` | small generator helpers; keep Python's output order |
| `itertools.tee` | avoid; materialize to an array |
| `collections.Counter(xs).most_common()` | `Map` counts, then a stable descending sort by count; ties keep first-seen order in both |

Helpers:

```ts
export function* range(start: number, stop?: number, step = 1): Generator<number> {
  if (stop === undefined) [start, stop] = [0, start];
  if (step === 0) throw new ValueError("range() arg 3 must not be zero");
  for (let i = start; step > 0 ? i < stop : i > stop; i += step) yield i;
}

export function* zip<A, B>(a: Iterable<A>, b: Iterable<B>): Generator<[A, B]> {
  const ia = a[Symbol.iterator]();
  const ib = b[Symbol.iterator]();
  for (;;) {
    const x = ia.next();
    if (x.done) return;
    const y = ib.next();
    if (y.done) return;
    yield [x.value, y.value];
  }
}

// itertools.groupby: groups consecutive runs only. Groups are arrays here;
// in Python they are lazy and invalidated when the outer iterator advances.
export function* groupby<T, K>(xs: Iterable<T>, key: (x: T) => K): Generator<[K, T[]]> {
  let first = true;
  let cur!: K;
  let group: T[] = [];
  for (const x of xs) {
    const k = key(x);
    if (!first && k === cur) {
      group.push(x);
      continue;
    }
    if (!first) yield [cur, group];
    cur = k;
    group = [x];
    first = false;
  }
  if (!first) yield [cur, group];
}
```

`groupby` compares keys with `===`; Python uses `==`. If keys are tuples or
other compound values, compare encoded keys.

Generators with `send`:

```python
def running_total():
    total = 0
    while True:
        x = yield total
        total += x
```

```ts
function* runningTotal(): Generator<number, never, number> {
  let total = 0;
  for (;;) {
    const x = yield total;
    total += x;
  }
}
const g = runningTotal();
g.next(); // primes the generator, like next(g)
g.next(5); // { value: 5, done: false }
```

Rules:

- Iterators and generators are single-use in both languages.
- Python dict views (`d.keys()`) are live. `[...m.keys()]` is a snapshot,
  which matches `list(d.keys())`.
- Changing a dict's size while iterating it raises `RuntimeError` in Python.
  JS `Map` iteration tolerates mutation and visits added keys (T47).

## 6. Numeric semantics

| Python | TS | Notes |
| --- | --- | --- |
| `a / b` | `a / b` | Python raises on zero (T8). |
| `a // b`, `a % b` (ints) | `intFloorDiv`, `intMod` | `%` in JS takes the sign of the dividend (T1). Exact for safe integers. |
| `a // b`, `a % b` (floats) | `pyDivmod` | `Math.floor(a / b)` is wrong for some floats (T2). |
| `//`, `%` on big ints | `bigFloorDiv`, `bigMod` | BigInt `/` truncates. |
| `divmod(a, b)` | `pyDivmod` or the int helpers | |
| `int(x)` for a float | `Math.trunc(x)` | Not `Math.floor`. `int(inf)` raises `OverflowError`, `int(nan)` raises `ValueError`; `Math.trunc` returns them. |
| `round(x)` | `pyRoundInt` | Ties to even (T3). |
| `round(x, n)` | `pyRound` | Exact binary value, ties to even (T4). |
| `math.floor`, `math.ceil` | `Math.floor`, `Math.ceil` | Python returns `int`. |
| `x ** y` | `x ** y` | `(-8) ** (1/3)` is a complex number in Python and `NaN` in JS. |
| `pow(a, b, m)` | `powMod` with `bigint` | |
| `abs`, `math.fabs` | `Math.abs` | |
| `math.isclose(a, b)` | `isClose` | Default `rel_tol=1e-9`, `abs_tol=0`. |
| `math.fsum` | port CPython `math_fsum` (Shewchuk plus final half-even correction) | Test against fixtures. |
| `sum(floats)` | `pySum` (Neumaier) when the source runs on 3.12+ | T9. |
| `math.isnan`, `math.isinf` | `Number.isNaN`, `!Number.isFinite(x) && !Number.isNaN(x)` | Global `isNaN` coerces strings. |
| `float("inf")`, `math.inf`, `math.nan` | `Infinity`, `NaN` | |
| `sys.float_info.epsilon` | `Number.EPSILON` | |
| `int(s)` | `pyInt` | `parseInt` and `Number` accept other inputs (T10). |
| `float(s)` | a strict regex check, then `Number(s)` | Python accepts `"inf"`, `"nan"`, `"1_0.5"`, surrounding whitespace; `Number("")` is `0`. |
| `hex(n)`, `oct(n)`, `bin(n)` | `(n < 0 ? "-0x" : "0x") + Math.abs(n).toString(16)` | |
| `int(s, 16)` | strict check, then `parseInt(s, 16)` or `BigInt("0x" + s)` | `parseInt` stops at the first bad digit. |
| `n.bit_length()` | `n === 0n ? 0 : (n < 0n ? -n : n).toString(2).length` | |
| `int.to_bytes`, `int.from_bytes` | `DataView` for 8 to 64 bits; a bigint loop beyond | |
| `<<`, `>>`, `&`, `\|`, `^`, `~` | the same on `bigint`, or on `number` within 32 bits | JS number bit ops are 32-bit signed (T7). |
| `decimal.Decimal` | decimal.js configured to Python's context | T13. |
| `random.seed(n)` sequences | port MT19937 and CPython's `random` algorithms | Only if fixtures depend on seeds (T12). |

Helpers (each tested against CPython on thousands of random inputs):

```ts
// Python float // and %, ported from CPython float divmod.
export function pyDivmod(a: number, b: number): [number, number] {
  if (b === 0) throw new ZeroDivisionError("float divmod()");
  let mod = a % b;
  let div = (a - mod) / b;
  if (mod !== 0) {
    if ((b < 0) !== (mod < 0)) {
      mod += b;
      div -= 1;
    }
  } else {
    mod = b < 0 ? -0 : 0;
  }
  let floordiv: number;
  if (div !== 0) {
    floordiv = Math.floor(div);
    if (div - floordiv > 0.5) floordiv += 1;
  } else {
    const q = a / b;
    floordiv = q < 0 || Object.is(q, -0) ? -0 : 0;
  }
  return [floordiv, mod];
}

// Python int // and % for integers within Number.MAX_SAFE_INTEGER.
export const intFloorDiv = (a: number, b: number): number => Math.floor(a / b);

export function intMod(a: number, b: number): number {
  const m = a % b;
  if (m === 0) return 0;
  return (m < 0) !== (b < 0) ? m + b : m;
}

export function bigFloorDiv(a: bigint, b: bigint): bigint {
  const q = a / b;
  return a % b !== 0n && (a < 0n) !== (b < 0n) ? q - 1n : q;
}

export function bigMod(a: bigint, b: bigint): bigint {
  const m = a % b;
  return m !== 0n && (m < 0n) !== (b < 0n) ? m + b : m;
}

// Python round(x) for |x| < 2**53: ties to even.
export function pyRoundInt(x: number): number {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

// Python round(x, n) for n >= 0: rounds the exact binary value, ties to even.
export function pyRound(x: number, n: number): number {
  if (!Number.isFinite(x) || Math.abs(x) >= 1e21) return x;
  const ax = Math.abs(x);
  const exact = ax.toFixed(Math.min(100, n + 30));
  const cut = exact.indexOf(".") + 1 + n;
  let r: number;
  if (/^50*$/.test(exact.slice(cut))) {
    const kept = exact.slice(0, n === 0 ? cut - 1 : cut);
    r = Number(kept.at(-1)) % 2 === 0 ? Number(kept) : Number(ax.toFixed(n));
  } else {
    r = Number(ax.toFixed(n));
  }
  return x < 0 || Object.is(x, -0) ? -r : r;
}

// Python f"{x:.{n}f}" and "%.nf" % x, for |x| < 1e21 and n <= 70. Returns the
// string directly: converting back to a number can lose the half-even choice.
export function pyFormatFixed(x: number, n: number): string {
  if (Number.isNaN(x)) return "nan";
  if (!Number.isFinite(x)) return x > 0 ? "inf" : "-inf";
  const ax = Math.abs(x);
  const exact = ax.toFixed(Math.min(100, n + 30));
  const cut = exact.indexOf(".") + 1 + n;
  let s: string;
  if (/^50*$/.test(exact.slice(cut))) {
    const kept = exact.slice(0, n === 0 ? cut - 1 : cut);
    s = Number(kept.at(-1)) % 2 === 0 ? kept : ax.toFixed(n);
  } else {
    s = ax.toFixed(n);
  }
  return x < 0 || Object.is(x, -0) ? `-${s}` : s;
}

// Python repr(float), str(float), f"{x}", and json.dumps for finite floats.
export function pyFloatRepr(x: number): string {
  if (Number.isNaN(x)) return "nan";
  if (!Number.isFinite(x)) return x > 0 ? "inf" : "-inf";
  if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
  const [mant, e] = x.toExponential().split("e") as [string, string];
  const exp = Number(e);
  if (exp < -4 || exp >= 16) {
    return `${mant}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
  }
  const s = String(x);
  return s.includes(".") ? s : `${s}.0`;
}

// math.isclose, same algorithm as CPython.
export function isClose(a: number, b: number, relTol = 1e-9, absTol = 0): boolean {
  if (a === b) return true;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
  const diff = Math.abs(b - a);
  return diff <= Math.abs(relTol * b) || diff <= Math.abs(relTol * a) || diff <= absTol;
}

// pow(base, exp, mod) for exp >= 0n and mod > 0n.
export function powMod(base: bigint, exp: bigint, mod: bigint): bigint {
  let result = 1n % mod;
  base = ((base % mod) + mod) % mod;
  while (exp > 0n) {
    if (exp & 1n) result = (result * base) % mod;
    base = (base * base) % mod;
    exp >>= 1n;
  }
  return result;
}

// int(s) for base 10, ASCII digits. Python also accepts non-ASCII decimal
// digits (int("٣") == 3); add them only if the contract needs it.
const INT_WS = "\\t-\\r \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const INT_RE = new RegExp(`^[${INT_WS}]*([+-]?[0-9]+(?:_[0-9]+)*)[${INT_WS}]*$`, "u");

export function pyInt(s: string): number {
  const m = INT_RE.exec(s);
  if (m === null) throw new ValueError(`invalid literal for int() with base 10: '${s}'`);
  return Number(m[1]!.replaceAll("_", ""));
}
```

`ZeroDivisionError` and `ValueError` are the exported error classes from
section 2. `pyInt` returns a `number`; switch to `BigInt(...)` when the value
domain needs it. Its message matches Python only when `s` has no characters
that `repr` escapes. `INT_WS` is not `str.isspace()`: `int()` rejects
U+001C to U+001F (`int("\x1c5")` raises) although `"\x1c".isspace()` is true.

Python 3.12+ `sum()` of floats uses compensated summation. A port of a 3.12+
source that sums floats needs:

```ts
// Neumaier summation; matches sum() of floats on CPython 3.12+ for finite inputs.
export function pySum(xs: Iterable<number>): number {
  let sum = 0;
  let c = 0;
  for (const x of xs) {
    const t = sum + x;
    c += Math.abs(sum) >= Math.abs(x) ? sum - t + x : x - t + sum;
    sum = t;
  }
  return c !== 0 && Number.isFinite(c) ? sum + c : sum;
}
```

Number formatting:

| Python | TS | Difference |
| --- | --- | --- |
| `str(x)`, `repr(x)`, `f"{x}"` for floats | `pyFloatRepr(x)` | `String(1.0)` is `"1"` (T5). |
| `f"{x:.2f}"`, `"%.2f" % x` | `pyFormatFixed(x, 2)` | `toFixed` breaks exact ties upward (T4), drops the sign of `-0.0`, and switches to exponent form at 1e21. |
| `f"{x:e}"` | `x.toExponential(6)` | Python pads the exponent to two digits: `1.500000e+00` against `1.500000e+0`. |
| `f"{x:g}"` | helper from `toPrecision` | Different exponent thresholds and zero stripping. |
| `f"{n:,}"`, `f"{x:,.2f}"` | insert commas into the `pyFormatFixed` output | Python's `,` is not locale-aware; the JS default locale is (T96). `Intl.NumberFormat` rounds the shortest decimal form, so `2.675` gives `2.68` and `1.005` gives `1.01`; Python gives `2.67` and `1.00` (checked). |
| `f"{n:x}"`, `f"{n:08b}"` | `n.toString(16)`, `n.toString(2).padStart(8, "0")` | Negative numbers: Python puts the sign first (`-0000101`). |
| `f"{s:>10}"`, `ljust`, `rjust`, `center` | pad by code points | `padStart` counts UTF-16 units (T23). |
| `f"{x!r}"` | a `pyRepr` helper | Only if the text is observable. |
| `f"{x:%}"` | `(x * 100).toFixed(6) + "%"` | The multiplication can round differently; prefer exact decimal math if it matters. |

## 7. Strings, bytes, unicode, encodings

Python `str` is a sequence of code points (it can hold lone surrogates). A JS
string is a sequence of UTF-16 code units: characters above U+FFFF (emoji,
CJK extension B, mathematical letters) take two units. `len`, indexing,
slicing and every offset differ for those characters (T14, T15). A port may
keep UTF-16 offsets internally as long as no code point offset or length is
observable at the API boundary (returned, stored, or used to cut text that is
returned).

| Python | TS | Notes |
| --- | --- | --- |
| `len(s)` | `[...s].length` when `s` can hold astral characters, else `s.length` | T14 |
| `s[i]`, `s[a:b]` | `Array.from(s)` once, then index or `slice(a, b).join("")` | Build the array outside loops. |
| `s[::-1]` | `Array.from(s).reverse().join("")` | T15 |
| `ord(c)`, `chr(n)` | `c.codePointAt(0)`, `String.fromCodePoint(n)` | Not `charCodeAt`, `fromCharCode`. |
| `s.find(t)`, `s.rfind(t)` | `indexOf`, `lastIndexOf` | UTF-16 offsets. `s.index` raises `ValueError` on a miss. |
| `s.count(t)` | `s.split(t).length - 1` for non-empty `t` | Both count non-overlapping matches. |
| `s.startswith(("a", "b"))` | `["a", "b"].some((p) => s.startsWith(p))` | |
| `s.replace(a, b)` | `s.split(a).join(b)` for non-empty `a`, or `replaceAll` with `$` escaped in `b` | `String.prototype.replace` with a string replaces the first match only (T21). |
| `s.split()` | `pySplit` | T20 |
| `s.split(sep, maxsplit)` | `pySplitSep` | JS `limit` drops the remainder. |
| `s.splitlines()` | `pySplitlines` | T22 |
| `s.strip()` | `pyStrip` | `trim()` uses a different whitespace set (T19). |
| `s.strip(chars)` | loop over code points in a `Set` of `chars` | `chars` is a set, not a prefix. |
| `s.removeprefix(p)` (3.9+) | `s.startsWith(p) ? s.slice(p.length) : s` | |
| `s.upper()`, `s.lower()` | `toUpperCase()`, `toLowerCase()` | Same full mappings, final sigma included. Never the `toLocale*` forms. |
| `s.casefold()` | table-driven helper | T16 |
| `s.capitalize()`, `s.title()` | `pyCapitalize`, `pyTitle` | T17 |
| `s.zfill(n)` | `pyZfill` | T23 |
| `s.ljust(n)`, `s.rjust(n)`, `s.center(n)` | pad by code point count | `padStart` counts UTF-16 units. |
| `s.translate(table)` | `Map<number, string>` over code points | |
| `"".join(xs)` | `xs.join("")` | Python raises on non-`str` items; JS stringifies anything (T25). |
| `s * n` | `s.repeat(n)` | `repeat` throws `RangeError` for negative `n`; Python returns `""`. |
| `unicodedata.normalize(form, s)` | `s.normalize(form)` | |
| `unicodedata.category(c)` | test `/\p{Lu}/u` and friends | |
| `unicodedata.name(c)` | no built-in | |
| grapheme clusters | `Intl.Segmenter` with `granularity: "grapheme"` | Python's stdlib has none. |
| `s < t`, `sorted(strs)` | `compareCodePoints` | T24 |

`str` predicates as JS regexes. Exact on every assigned code point (checked
CPython 3.14 against Node 24). Python returns `False` for the empty string,
which `+` reproduces:

| Python | JS |
| --- | --- |
| `s.isalpha()` | `/^\p{L}+$/u` |
| `s.isalnum()` | `/^[\p{L}\p{N}]+$/u` |
| `s.isdecimal()` | `/^\p{Nd}+$/u` |
| `s.isspace()` | `` new RegExp(`^[${PY_WS}]+$`, "u") `` |
| `s.isascii()` (3.7+) | `/^[\x00-\x7f]*$/` (true for `""`) |
| `s.isdigit()` | no class: `\p{Nd}` plus 128 more such as `²` |
| `s.isnumeric()` | no class: `\p{N}` plus 91 CJK ideographs such as `一` |
| `s.isupper()`, `s.islower()`, `s.istitle()` | no class; write a helper on `\p{Cased}`, `\p{Lu}`, `\p{Ll}`, `\p{Lt}` and test it |

Unicode versions: Python 3.9 uses Unicode 13.0, 3.12 uses 15.0, 3.13 uses
15.1 (`unicodedata.unidata_version`). Node reports its version in
`process.versions.unicode` (16.0 on Node 22.15, 17.0 on Node 24.18).
Characters assigned in between can classify, normalize and case-map
differently. Record both versions in the strategy.

Helpers (tested against CPython on random strings):

```ts
// Python str.isspace(); also str.split(), str.strip() and re \s for str patterns.
export const PY_WS =
  "\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const WS_RUN = new RegExp(`[${PY_WS}]+`, "u");
const WS_EDGES = new RegExp(`^[${PY_WS}]+|[${PY_WS}]+$`, "gu");

export const pySplit = (s: string): string[] => s.split(WS_RUN).filter((p) => p !== "");
export const pyStrip = (s: string): string => s.replace(WS_EDGES, "");

export function pySplitSep(s: string, sep: string, maxsplit = -1): string[] {
  if (sep === "") throw new ValueError("empty separator");
  if (maxsplit < 0) return s.split(sep);
  const out: string[] = [];
  let start = 0;
  while (out.length < maxsplit) {
    const i = s.indexOf(sep, start);
    if (i === -1) break;
    out.push(s.slice(start, i));
    start = i + sep.length;
  }
  out.push(s.slice(start));
  return out;
}

export function pySplitlines(s: string): string[] {
  const parts = s.split(/\r\n|[\n\v\f\r\x1c-\x1e\x85\u2028\u2029]/);
  if (parts.at(-1) === "") parts.pop();
  return parts;
}

// Python str ordering: by code point, not by UTF-16 code unit.
export function compareCodePoints(a: string, b: string): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a.codePointAt(i)!;
    const y = b.codePointAt(i)!;
    if (x !== y) return x < y ? -1 : 1;
    if (x > 0xffff) i++;
  }
  return a.length === b.length ? 0 : a.length < b.length ? -1 : 1;
}

export function pyZfill(s: string, width: number): string {
  const cps = Array.from(s);
  const fill = width - cps.length;
  if (fill <= 0) return s;
  const sign = cps[0] === "+" || cps[0] === "-" ? cps[0] : "";
  return sign + "0".repeat(fill) + cps.slice(sign ? 1 : 0).join("");
}

// capitalize() and title() use uppercase where Python uses titlecase. They
// differ only on the 135 code points whose titlecase is not their uppercase,
// such as "ß" (title "Ss"), "ǆ" (title "ǅ") and the ligature "ﬁ" (title "Fi").
export function pyCapitalize(s: string): string {
  if (s === "") return "";
  const first = String.fromCodePoint(s.codePointAt(0)!);
  return first.toUpperCase() + s.toLowerCase().slice(first.toLowerCase().length);
}

const CASED_BEFORE = /(?!\p{Case_Ignorable})\p{Cased}\p{Case_Ignorable}*$/u;
const CASED_AFTER = /^\p{Case_Ignorable}*(?!\p{Case_Ignorable})\p{Cased}/u;

export function pyTitle(s: string): string {
  let out = "";
  let prevCased = false;
  let i = 0;
  for (const c of s) {
    if (!prevCased) {
      out += c.toUpperCase();
    } else if (c === "\u03a3") {
      const final = CASED_BEFORE.test(s.slice(0, i)) && !CASED_AFTER.test(s.slice(i + 1));
      out += final ? "\u03c2" : "\u03c3";
    } else {
      out += c.toLowerCase();
    }
    prevCased = /\p{Cased}/u.test(c);
    i += c.length;
  }
  return out;
}
```

`casefold()`: no JS equivalent. `s.toUpperCase().toLowerCase()` differs from
`casefold()` on 174 code points (Cherokee letters, dotless `ı`, and others) and
`s.toLowerCase()` on 297 (checked CPython 3.14 against Node 24). For parity,
generate a fold table from Unicode `CaseFolding.txt` (statuses C and F) at the
source's Unicode version.

Bytes:

| Python | TS | Notes |
| --- | --- | --- |
| `bytes`, `bytearray` | `Uint8Array` | |
| `b"abc"` | `Uint8Array.of(0x61, 0x62, 0x63)` or `new TextEncoder().encode("abc")` | |
| `bytes(n)` | `new Uint8Array(n)` | |
| `b[i]` | `b[i]` | A number in both. |
| `b[a:c]` | `b.slice(a, c)` | Copies. `subarray` and `Buffer.prototype.slice` return views (T72). |
| `b1 + b2` | `Buffer.concat([b1, b2])`, or allocate and `set` | |
| `b1 == b2` | `Buffer.compare(b1, b2) === 0` | `===` compares identity. |
| `b.hex()` | `Buffer.from(b).toString("hex")` | |
| `bytes.fromhex(s)` | validate, then `Buffer.from(s.replace(/[ \t\n\v\f\r]/g, ""), "hex")` | `Buffer` stops at the first bad digit (T74). Python allows whitespace only between bytes. |
| `base64.b64encode`, `b64decode` | `Buffer.from(b).toString("base64")`, validate then `Buffer.from(s, "base64")` | T75 |
| `base64.urlsafe_b64encode` | `toString("base64url")` plus `=` padding | T75 |
| `struct.pack`, `struct.unpack` | `DataView` with an explicit endianness flag | T73 |
| `memoryview(b)[a:c]` | `b.subarray(a, c)` | A view on purpose. |
| `io.BytesIO` | array of chunks, then `Buffer.concat` | |

Text encodings:

| Python | TS | Notes |
| --- | --- | --- |
| `s.encode()`, `s.encode("utf-8")` | `new TextEncoder().encode(s)` | Lone surrogates become `EF BF BD`; Python raises `UnicodeEncodeError`. Check `s.isWellFormed()` first when the contract raises. |
| `b.decode()`, `b.decode("utf-8")` | `new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(b)` | The default `TextDecoder` replaces errors and strips a BOM (T69, T70). |
| `b.decode("utf-8", "replace")` | `new TextDecoder("utf-8", { ignoreBOM: true }).decode(b)` | Same replacement count on truncated, overlong and surrogate sequences (checked). |
| `b.decode("utf-8-sig")` | `new TextDecoder("utf-8", { fatal: true }).decode(b)` | Strips one BOM. |
| `b.decode("latin-1")` | `Buffer.from(b).toString("latin1")` | `TextDecoder("latin1")` is windows-1252 (T71). |
| `s.encode("latin-1")` | check every code point is at most 0xFF, then `Buffer.from(s, "latin1")` | `Buffer` keeps the low byte silently: `"€"` becomes `0xAC`. |
| `b.decode("ascii")` | check every byte is below 0x80, then decode as latin1 | `Buffer` `"ascii"` decoding never throws (0xE9 decodes to `"i"`). |
| `b.decode("cp1252")`, `"shift_jis"`, `"gbk"`, other codecs | `new TextDecoder(label, { fatal: true })` | WHATWG labels and tables differ from Python codecs in places; test each one used. Encoding to them needs `iconv-lite`. |
| `"utf-16"` | detect the BOM, then `TextDecoder("utf-16le")` or `"utf-16be"` | Python's `"utf-16"` encoder writes a BOM. |
| `errors="surrogateescape"` | keep the bytes | No equivalent. |

## 8. Dates, times, timezones

Temporal: Node 22.15 and 24.18 do not expose it (`typeof Temporal` is
`"undefined"`, checked). Before using it, check `typeof globalThis.Temporal`
on the exact runtime the port targets. If it is absent, use
`temporal-polyfill` or `@js-temporal/polyfill` (same API, so the code can move
to the native one later), or Luxon for zone-aware work. Pick one model per
port and record it; do not mix `Date` and Temporal types in one public API.

| Python | With Temporal | Without Temporal | Notes |
| --- | --- | --- | --- |
| naive `datetime` | `Temporal.PlainDateTime` | `Date` used only through `getUTC*`/`setUTC*`, holding wall time | Naive arithmetic ignores DST, and so does UTC arithmetic. |
| aware `datetime` in UTC | `Temporal.Instant`, or `ZonedDateTime` in `"UTC"` | `Date` | |
| aware `datetime` with `ZoneInfo` | `Temporal.ZonedDateTime` | Luxon `DateTime` with a zone | `Date` cannot carry a zone. |
| `date` | `Temporal.PlainDate` | `"YYYY-MM-DD"` string or UTC-midnight `Date` | |
| `time` | `Temporal.PlainTime` | small record | |
| `timedelta` | `Temporal.Duration` | integer microseconds or milliseconds | `str(timedelta(hours=-1))` is `"-1 day, 23:00:00"`; write a formatter. |
| `datetime.now()` | `Temporal.Now.plainDateTimeISO()` | `new Date()` with local getters | Naive local time. |
| `datetime.now(timezone.utc)` | `Temporal.Now.instant()` | `new Date()` | |
| `datetime.utcnow()` | as above | as above | Naive UTC, deprecated in 3.12. |
| `time.time()` | `Temporal.Now.instant().epochMilliseconds / 1000` | `Date.now() / 1000` | Seconds against milliseconds. |
| `datetime.fromtimestamp(ts, tz=timezone.utc)` | `Temporal.Instant.fromEpochMilliseconds(Math.trunc(ts * 1000))` | `new Date(ts * 1000)` | Python keeps microseconds; `Date` truncates to milliseconds. |
| `dt.isoformat()` | helper | helper | T82 |
| `datetime.fromisoformat(s)` | `Temporal.PlainDateTime.from(s)` and friends | explicit regex parser | Never `new Date(s)` for strings without an offset (T81). Accepted formats depend on the Python version (T86). |
| `dt.strftime(fmt)` | helper for the formats used | helper | `%a`, `%b` are English under the C locale. `Intl.DateTimeFormat` output depends on locale and ICU version. |
| `datetime.strptime(s, fmt)` | explicit parser | explicit parser | |
| `dt.month` | `dt.month` (1 to 12) | `d.getUTCMonth() + 1` | T79 |
| `dt.weekday()` | `dt.dayOfWeek - 1` | `(d.getUTCDay() + 6) % 7` | T83 |
| `dt.isoweekday()` | `dt.dayOfWeek` | `d.getUTCDay() \|\| 7` | |
| `calendar.timegm(t)` | `pdt.toZonedDateTime("UTC").epochMilliseconds / 1000` | `Date.UTC(y, m - 1, d, hh, mm, ss) / 1000` | |
| `zoneinfo.ZoneInfo(name)` | `timeZone` argument | Luxon zone; `Intl.DateTimeFormat` with `timeZone` for display only | Python reads system tzdata or the `tzdata` package; Node uses ICU's copy. Recent rule changes can differ. |

Rules:

- Pin `TZ=UTC` when recording fixtures and in the TS test run, then run the TS
  suite once more with a zone that has DST (for example
  `TZ=America/New_York`) to catch local-time leaks.
- Python months are 1 to 12 and invalid dates raise. `Date` months are 0 to
  11 and out-of-range fields roll over (T79, T80).
- Keep naive and aware values as different TS types. Python raises when they
  are compared or subtracted (T85).
- Python adds a `timedelta` to an aware datetime on its wall-clock fields, in
  any unit, then re-attaches the zone (T84). With Temporal, mirror that with
  `zdt.toPlainDateTime().add(d).toZonedDateTime(zone)`; `zdt.add({ days: 1 })`
  also keeps wall time, but `zdt.add({ hours: 24 })` is exact elapsed time
  (checked with `temporal-polyfill`). Times that fall in a DST gap print
  differently: Python keeps the nonexistent wall time, Temporal moves it
  forward. Add a fixture if the domain can hit a gap.

## 9. Regex dialect

Translate every pattern by hand when porting; do not translate at runtime.
Always use the `u` flag (or `v`) for `str` patterns. The `u` flag gives code
point semantics and `\p{...}`, and makes the syntax strict: escapes such as
`\-`, `\:`, `\'` outside a class and a bare `{` become `SyntaxError` (T35).
The `v` flag is stricter still inside classes (`[(]` and `[a-]` are errors).
`bytes` patterns and `re.ASCII` patterns are ASCII.

Classes and anchors (each translation was compared with Python on random
strings):

| Python `str` pattern | JS, `u` flag | Notes |
| --- | --- | --- |
| `\w`, `\W` | `[\p{L}\p{N}_]`, `[^\p{L}\p{N}_]` | JS `\w` is ASCII even with `u` (T26). |
| `\d`, `\D` | `\p{Nd}`, `\P{Nd}` | Python `\d` matches `٣`. |
| `\s`, `\S` | `[${PY_WS}]`, `[^${PY_WS}]` | JS `\s` adds U+FEFF and lacks U+001C to U+001F and U+0085. |
| `\b`, `\B` | `PY_B`, `PY_NB` below | JS `\b` is ASCII (T27). |
| `\A` | `^` without the `m` flag | JS has no `\A` (T31). |
| `\Z` | `$` without the `m` flag | JS has no `\Z` (T31). |
| `$` without MULTILINE | `(?=\n?$)` | Python `$` also matches before a final `\n` (T30). |
| `^` with MULTILINE | `(?<![^\n])` | JS `m` also breaks lines at `\r`, U+2028, U+2029. |
| `$` with MULTILINE | `(?![^\n])` | |
| `.` | `[^\n]` | JS `.` also excludes `\r`, U+2028, U+2029 (T33). |
| `.` with DOTALL | `[\s\S]`, or `.` with the `s` flag | |
| `\w`, `\d`, `\s`, `\b` under `re.ASCII` | `\w`, `\d`, `[\t-\r ]`, `\b` | JS `\s` is not ASCII-only. |
| `(?P<name>...)` | `(?<name>...)` | |
| `(?P=name)` | `\k<name>` | |
| `{,n}` | `{0,n}` | JS reads `{,n}` as literal text (T35). |
| literal `{` | `\{` | |
| `(?>X)` (3.11+) | `(?=(X))\1` | Adds a capture group; renumber the others. |
| `X*+`, `X++`, `X?+` (3.11+) | `(?=(X*))\1` and the like | |
| `(?(1)yes\|no)` | rewrite with alternation | No conditionals in JS. |
| `\U0001F600`, `\N{name}` | `\u{1F600}`, the literal character | |
| octal `\012` | `\x0a` | |
| lookbehind | same | Python needs fixed width; JS allows any. Safe direction. |

```ts
export const PY_W = "[\\p{L}\\p{N}_]";
export const PY_B = `(?:(?<!${PY_W})(?=${PY_W})|(?<=${PY_W})(?!${PY_W}))`;
export const PY_NB = `(?:(?<=${PY_W})(?=${PY_W})|(?<!${PY_W})(?!${PY_W}))`;

// Python r"\bfoo\b" for a str pattern:
const FOO = new RegExp(`${PY_B}foo${PY_B}`, "u");
```

Flags:

| Python | JS |
| --- | --- |
| `re.I`, `(?i)` at the start | `i`, always with `u` (T34) |
| `re.S`, `(?s)` | `s` |
| `re.M`, `(?m)` | the lookaround forms above; `m` only if the input never contains `\r`, U+2028 or U+2029 |
| `re.X`, `(?x)` | remove whitespace and comments while porting; for long patterns build the source with `String.raw` pieces joined |
| `re.A`, `(?a)` | keep the ASCII escapes, map `\s` to `[\t-\r ]` |
| `(?i:...)` scoped | modifiers parse on Node 24 and fail on Node 22 (checked); otherwise expand by hand (`[aA]`) |
| inline flags after the start | an error since 3.11 and a `DeprecationWarning` before |

API:

| Python | JS | Notes |
| --- | --- | --- |
| `re.compile(p)` | a module-level `RegExp` constant | Without `g` or `y` unless needed (T38). |
| `re.search(p, s)` | `p.exec(s)` | |
| `re.match(p, s)` | `^(?:...)` without `m`, or a sticky copy with `lastIndex = 0` | `test` searches the whole string (T32). |
| `re.fullmatch(p, s)` | `^(?:...)$` without `m` | |
| `re.findall(p, s)` | `pyFindall` | Returns groups, not matches (T37). |
| `re.finditer(p, s)` | `s.matchAll(gp)` | `matchAll` throws without `g`. |
| `re.sub(p, r, s)` | `s.replace(gp, r2)` with `r` translated | Replaces all in Python (T28). `count=1` uses a non-global regex; other counts need a counting callback. |
| `re.subn` | callback that counts | |
| `re.split(p, s, maxsplit)` | `pyReSplit` | T36 |
| `re.escape(s)` | escape by hand while porting | `RegExp.escape` exists on Node 24 and not on Node 22 (checked). |
| `m.group(0)`, `m.group(n)` | `m[0]`, `m[n]` | `undefined` where Python gives `None` (T39). |
| `m.group("x")`, `m.groupdict()` | `m.groups?.x`, `{ ...m.groups }` | |
| `m.groups()` | `m.slice(1)` | |
| `m.start()`, `m.end()`, `m.span(n)` | `m.index`, `m.index + m[0].length`, `d` flag then `m.indices[n]` | UTF-16 offsets. |
| `m.lastindex`, `m.expand(t)` | none | |

Replacement templates (Python `repl` string to JS replacement string):

| Python | JS |
| --- | --- |
| `\1`, `\g<1>` | `$1` |
| `\g<name>` | `$<name>` |
| `\g<0>` | `$&` |
| `$` | `$$` |
| `\n`, `\t` (even in a raw string) | the character itself; Python processes escapes in templates |
| `\\` | `\` |

When `repl` is a function, Python passes a `Match`; JS passes
`(match, p1, ..., pN, offset, string, groups)` where `groups` is present only
when the pattern has named groups. Use a rest parameter and convert
`undefined` to the source's `None` handling.

Helpers (tested against CPython):

```ts
export function pyFindall(re: RegExp, s: string): (string | string[])[] {
  const g = new RegExp(re.source, re.flags.replace(/[gy]/g, "") + "g");
  return Array.from(s.matchAll(g), (m) =>
    m.length === 1 ? m[0] : m.length === 2 ? (m[1] ?? "") : m.slice(1).map((x) => x ?? ""),
  );
}

export function pyReSplit(re: RegExp, s: string, maxsplit = 0): (string | undefined)[] {
  const g = new RegExp(re.source, re.flags.replace(/[gy]/g, "") + "g");
  const out: (string | undefined)[] = [];
  let last = 0;
  let n = 0;
  for (const m of s.matchAll(g)) {
    if (maxsplit > 0 && n >= maxsplit) break;
    out.push(s.slice(last, m.index), ...m.slice(1));
    last = m.index + m[0].length;
    n++;
  }
  out.push(s.slice(last));
  return out;
}
```

Patterns from the third-party `regex` module: `\p{...}` and set operations
map to the `v` flag (`[\p{L}--\p{Lu}]`), `\X` maps to `Intl.Segmenter`, and
fuzzy matching, recursion and timeouts have no JS equivalent.

## 10. I/O, paths, process, environment

| Python | TS | Notes |
| --- | --- | --- |
| `open(p).read()` | `readFileSync(p, "utf8")`, then `.replace(/\r\n?/g, "\n")` | Text mode translates newlines (T90) and uses the locale encoding unless `encoding=` is given (T91). Skip the replace if the source passed `newline=""`. |
| `open(p, "rb").read()` | `readFileSync(p)` | |
| `open(p, "w").write(s)` | `writeFileSync(p, s)` | Python on Windows writes `\r\n` for `\n` in text mode. |
| `for line in f:` | `readline.createInterface({ input: createReadStream(p), crlfDelay: Infinity })` with `for await` | Python lines keep their `\n`; `readline` strips it. |
| `print(a, b)` | `process.stdout.write([a, b].map(pyStr).join(" ") + "\n")` | `pyStr` is the `str()` helper from T25. `console.log` applies `%s`-style format specifiers to its first argument (T94). |
| `print(x, file=sys.stderr)` | `process.stderr.write(pyStr(x) + "\n")` | |
| `sys.stdin.read()` | `readFileSync(0, "utf8")` | |
| `sys.argv[1:]` | `process.argv.slice(2)` | `process.argv[0]` is the node binary. |
| `sys.exit(n)` | `process.exitCode = n`, then return | `process.exit()` can drop pending output on pipes. |
| `os.environ["X"]` | `process.env.X` plus an explicit missing check | T95 |
| `os.environ.get("X", d)` | `process.env.X ?? d` | Values are strings. `process.env.X = 1` stores `"1"`; Python raises `TypeError`. |
| `os.getcwd()`, `os.chdir(p)` | `process.cwd()`, `process.chdir(p)` | |
| `os.path.join(a, b)` | `path.join(a, b)` only when `b` is relative | An absolute `b` resets the result in Python (T92). |
| `os.path.basename`, `os.path.dirname` | `path.basename`, `path.dirname` plus the edge cases | T93 |
| `os.path.splitext(p)` | `const ext = path.extname(p); [p.slice(0, p.length - ext.length), ext]` | Same results for `.bashrc`, `a/.b` and `a.tar.gz` (checked). |
| `os.path.normpath(p)` | `path.normalize(p)` | `normpath("a/")` is `"a"`; `path.normalize("a/")` is `"a/"`. |
| `os.path.abspath(p)` | `path.resolve(p)` | |
| `os.path.exists`, `isfile`, `isdir` | `existsSync`, `statSync(p, { throwIfNoEntry: false })?.isFile()` | |
| `os.path.getmtime(p)` | `statSync(p).mtimeMs / 1000` | Seconds against milliseconds. |
| `os.listdir(p)` | `readdirSync(p)` | Order is filesystem-dependent in both; sort when order is observable. |
| `os.walk(p)` | `readdirSync(p, { recursive: true, withFileTypes: true })` (Node 20.1+) or a manual walk | Write a helper for the `(dirpath, dirnames, filenames)` shape and order. |
| `os.makedirs(p, exist_ok=True)` | `mkdirSync(p, { recursive: true })` | |
| `os.remove(p)` | `unlinkSync(p)`; `rmSync(p, { force: true })` for "missing is fine" | |
| `shutil.rmtree(p)` | `rmSync(p, { recursive: true, force: true })` | |
| `shutil.copy`, `shutil.copytree` | `copyFileSync`, `cpSync(src, dst, { recursive: true })` | |
| `tempfile.mkdtemp()` | `mkdtempSync(path.join(os.tmpdir(), "prefix-"))` | |
| `tempfile.TemporaryDirectory()` | `mkdtempSync` plus `rmSync` in `finally`, or a `Symbol.dispose` wrapper | |
| `glob.glob(pattern)` | `fs.glob` (Node 22+, check its stability on the target), `tinyglobby`, `fast-glob` | Hidden files, `**` and order differ; sort results. |
| `fnmatch.fnmatch(name, pat)` | `picomatch` or a translated regex | In `fnmatch`, `*` also matches `/`. |
| `subprocess.run(args, check=True, capture_output=True, text=True)` | `execFileSync(args[0], args.slice(1), { encoding: "utf8" })` | `execFileSync` throws on non-zero exit; `spawnSync` does not. No shell unless the source used `shell=True`. |
| `subprocess.Popen` | `spawn` | |
| `signal.signal(signal.SIGINT, h)` | `process.on("SIGINT", h)` | |
| `atexit.register(f)` | `process.on("exit", f)` | Synchronous work only. |
| `platform.system()` | `process.platform` | `"Darwin"` against `"darwin"`. `sys.platform` values `"darwin"`, `"linux"`, `"win32"` match `process.platform`. |
| `os.cpu_count()` | `os.availableParallelism()` | |
| `os.sep`, `os.linesep` | `path.sep`, `os.EOL` | |

pathlib:

| Python | TS | Notes |
| --- | --- | --- |
| `Path(a) / b` | `path.join(a, b)` | `Path("a") / "/b"` is `/b`, as in T92. |
| `p.name`, `p.stem`, `p.suffix` | `path.basename(p)`, `path.parse(p).name`, `path.extname(p)` | `Path("a/").name` is `"a"`: pathlib drops the trailing slash, `os.path.basename` does not. |
| `p.parent` | `path.dirname(p)` | `Path("a").parent` is `.`, like `path.dirname("a")`. |
| `p.resolve()` | `realpathSync(path.resolve(p))` when the path exists | `resolve` follows symlinks; `path.resolve` does not. |
| `p.read_text()`, `p.write_text(s)` | `readFileSync`, `writeFileSync` | Same text-mode rules as `open`. |
| `p.exists()`, `p.is_file()`, `p.is_dir()` | `existsSync`, `statSync` | |
| `p.iterdir()` | `readdirSync(p).map((n) => path.join(p, n))` | |
| `p.mkdir(parents=True, exist_ok=True)` | `mkdirSync(p, { recursive: true })` | |
| `Path.home()`, `Path.cwd()` | `os.homedir()`, `process.cwd()` | |
| `PurePosixPath`, `PureWindowsPath` | `path.posix`, `path.win32` | |

## 11. Module layout, packaging, naming, visibility

| Python | TS |
| --- | --- |
| `pkg/__init__.py` with re-exports and `__all__` | `src/index.ts` with explicit `export { ... } from "./mod.js"` |
| `pkg/mod.py` | `src/mod.ts` |
| `pkg/sub/__init__.py` | `src/sub/index.ts` |
| `pkg/_private.py`, names starting with `_` | modules and names not re-exported from `src/index.ts` |
| `tests/test_mod.py` | `test/mod.test.ts` |
| `if __name__ == "__main__":` | a separate `src/cli.ts` referenced from `bin`, starting with `#!/usr/bin/env node` |
| `pyproject.toml` `[project]` | `package.json` |
| `requires-python = ">=3.9"` | `"engines": { "node": ">=20" }` |
| `dependencies` | `dependencies` |
| `optional-dependencies` (extras) | `peerDependencies` with `peerDependenciesMeta` optional, or separate entry points |
| `[project.scripts]` | `bin` |
| `[project.entry-points]` plugin groups | explicit registration; no equivalent |
| `py.typed` | `types` condition in `exports` |
| `__version__` | a generated `version.ts` |
| PEP 440 versions (`1.0.0rc1`) | semver (`1.0.0-rc.1`) |

Naming:

- Functions, methods, variables, parameters: `snake_case` to `camelCase`.
  Classes stay `PascalCase`, constants stay `UPPER_SNAKE_CASE`.
- Module files: `snake_case.py` to `kebab-case.ts` or `camelCase.ts`; pick one
  and record it.
- Keyword argument names become option property names in `camelCase`
  (`max_retries` to `maxRetries`). Keys that cross a wire (JSON fields, HTTP
  parameters, config file keys) keep their exact spelling.
- `_name` (convention-private) maps to TS `private` or `protected`, which
  subclasses and tests can still reach through type assertions. `__name`
  (name-mangled) maps to `#name`. `#name` is invisible to subclasses and
  breaks `Proxy` wrappers; do not use it for `_name`.

ESM layout:

```json
{
  "name": "foo",
  "version": "1.2.0",
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
  },
  "bin": { "foo": "./dist/cli.js" },
  "files": ["dist"],
  "engines": { "node": ">=20" },
  "sideEffects": false
}
```

```json
{
  "compilerOptions": {
    "target": "es2022",
    "lib": ["es2023"],
    "module": "nodenext",
    "types": ["node"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "declaration": true,
    "sourceMap": true,
    "rootDir": "src",
    "outDir": "dist"
  },
  "include": ["src"]
}
```

Rules:

- With `module: "nodenext"`, relative imports carry the emitted extension:
  `import { x } from "./mod.js"` imports `mod.ts`. TS 5.7+ can rewrite
  `.ts` specifiers with `rewriteRelativeImportExtensions`.
- Ship ESM only. Node 20.19+ and 22.12+ can `require()` an ESM package that
  has no top-level `await`. Dual ESM and CJS builds create two copies of every
  class (T61).
- Raise `lib` when the minimum Node allows (`es2024` features such as
  `Object.groupBy` need Node 21+).
- Avoid TS `enum`, `namespace` and constructor parameter properties. Node's
  type stripping rejects them (`enum` fails with
  `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` on Node 24, checked), and so does
  TS 5.8 `--erasableSyntaxOnly`.
- Circular imports: Python tolerates them when names are read late. In ESM a
  `class` or `const` read before its module finished evaluating throws
  `ReferenceError`. Break cycles with a seam (the decomposition already
  reports strongly connected components).
- Optional imports (`try: import ujson except ImportError: import json`)
  become a static choice, or a dynamic `import()` inside `try/catch`.
- Monkeypatching module attributes is impossible on ESM namespaces. Replace
  it with parameters, setters, or dependency injection.

## 12. Standard library equivalence

| Source | Target | Notes |
| --- | --- | --- |
| `re` | `RegExp` | Section 9. |
| `json` | `JSON` plus helpers | T63 to T68. |
| `math` | `Math` plus helpers | Section 6. |
| `decimal` | decimal.js | T13. |
| `fractions` | fraction.js or a small class | |
| `random` | `Math.random`, `crypto.getRandomValues` | Not seedable (T12). |
| `secrets` | `crypto.randomBytes`, `crypto.randomInt` | |
| `statistics` | small helpers, or `simple-statistics` | `statistics.mean` sums exactly with fractions; a naive sum can differ in the last digit. |
| `datetime`, `zoneinfo`, `calendar` | Temporal or `Date` plus Luxon | Section 8. |
| `time.time`, `time.monotonic`, `time.perf_counter_ns` | `Date.now() / 1000`, `performance.now() / 1000`, `process.hrtime.bigint()` | Seconds against milliseconds. |
| `time.sleep` | `setTimeout` from `node:timers/promises` | Async only. |
| `string` constants | literal strings | |
| `textwrap` | small helper | `textwrap.wrap` rules (break on hyphens, drop whitespace) need care. |
| `unicodedata` | `String.prototype.normalize`, `\p{...}` | Section 7. |
| `codecs` | `TextEncoder`, `TextDecoder`, `Buffer` | Section 7. |
| `struct` | `DataView`, `Buffer` read and write methods | T73. |
| `array` | typed arrays | |
| `base64`, `binascii` | `Buffer` `"base64"`, `"base64url"`, `"hex"` | T74, T75. |
| `hashlib` | `crypto.createHash` | |
| `hmac` | `crypto.createHmac`; `hmac.compare_digest` to `crypto.timingSafeEqual` | `timingSafeEqual` throws `RangeError` on different lengths; check lengths first. |
| `uuid` | `crypto.randomUUID()` for v4; `uuid` package for v1, v5, v7 | |
| `collections.OrderedDict` | `Map` | `move_to_end` is `delete` then `set`. |
| `collections.defaultdict` | `Map` plus a get-or-insert helper | |
| `collections.Counter` | `Map<K, number>` plus helpers | Section 5. |
| `collections.deque` | a ring buffer, or `denque` | `Array.prototype.shift` is O(n). |
| `collections.namedtuple` | class or readonly tuple | Section 1. |
| `heapq` | small binary heap helper | Python's heap is a min-heap on a list. |
| `bisect` | binary search helper | |
| `itertools` | generator helpers, iterator helpers on Node 22+ | Section 5. |
| `functools.reduce` | `Array.prototype.reduce` | Both throw on an empty input without an initial value. |
| `functools.partial` | arrow function | |
| `functools.lru_cache`, `cache` | `Map` memo, or `lru-cache` | Python keys on argument equality; `Map` keys on identity. |
| `operator.itemgetter`, `attrgetter` | arrow functions | |
| `copy.copy`, `copy.deepcopy` | spread, `structuredClone` | T56. |
| `dataclasses`, `typing`, `abc`, `enum` | classes, types, abstract classes, `as const` objects | Section 1. |
| `contextlib` | `try/finally`, `using` | Section 4. |
| `weakref` | `WeakRef`, `WeakMap`, `FinalizationRegistry` | |
| `pickle`, `shelve`, `marshal` | none | Never port; choose JSON and record the format change. |
| `io.StringIO`, `io.BytesIO` | string array plus `join`, chunk array plus `Buffer.concat` | |
| `os`, `os.path`, `pathlib`, `shutil`, `tempfile`, `glob`, `fnmatch` | `node:fs`, `node:path`, `node:os` | Section 10. |
| `sys` | `process` | Section 10. |
| `subprocess` | `node:child_process` | |
| `threading`, `concurrent.futures`, `multiprocessing` | async APIs, `worker_threads` | Section 4. |
| `asyncio` | promises, `node:timers/promises`, `AbortController` | Section 4. |
| `logging` | injected logger or `console` | |
| `warnings` | `process.emitWarning` | |
| `argparse` | `util.parseArgs` | No help generation or subcommands; use `commander` if the CLI needs them. |
| `configparser` | `ini` package | Interpolation and key case rules differ. |
| `csv` | `csv-parse` and `csv-stringify` | `csv.writer` ends rows with `\r\n` by default. |
| `sqlite3` | `node:sqlite` (Node 22+, check stability), `better-sqlite3` | |
| `gzip`, `zlib`, `bz2` | `node:zlib` (gzip, deflate, brotli; no bz2) | Compressed bytes differ (header fields); compare decompressed data. |
| `zipfile`, `tarfile` | `yauzl`/`yazl`, `fflate`, `tar` | |
| `urllib.parse` | `URL`, `URLSearchParams`, helpers | T76, T77. |
| `urllib.request`, `http.client` | `fetch` | |
| `http.server`, `socketserver` | `node:http`, `node:net` | |
| `socket`, `ssl` | `node:net`, `node:dgram`, `node:tls` | |
| `email`, `smtplib` | `nodemailer`, `mailparser` | |
| `html` | small `escape` helper | `html.escape` escapes `'` as `&#x27;` with `quote=True`. |
| `html.parser`, `xml.etree.ElementTree` | `parse5`, `htmlparser2`, `fast-xml-parser`, `@xmldom/xmldom` | |
| `shlex` | `shell-quote` | Quoting rules differ in details; test the inputs used. |
| `difflib` | `diff` package | Output formats differ from `unified_diff`. |
| `pprint`, `reprlib` | `util.inspect` | Different text. |
| `traceback` | `err.stack` | Never compare text. |
| `inspect`, `ast`, `dis`, `importlib` internals | none | Redesign; dynamic `import()` covers simple plugin loading. |
| `importlib.resources` | `new URL("./data.json", import.meta.url)` plus `readFileSync` | |
| `locale`, `gettext` | `Intl`, an i18n library | |
| `unittest`, `doctest` | vitest | Section 14. |

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |
| requests | sync HTTP client | `fetch`, `undici`, `ky` | use the platform | `fetch` is async, so the API changes (section 4). `fetch` resolves on 4xx and 5xx; `requests` too, until `raise_for_status()`. `response.text()` always decodes UTF-8; `requests` uses the declared charset or a guess. |
| httpx | sync and async HTTP | `fetch`, `undici`, `ky` | use the platform | httpx times out after 5 seconds by default; Node's `fetch` waits up to 300 seconds for response headers (undici default). Add `AbortSignal.timeout(5_000)`. |
| aiohttp | async HTTP client and server | `fetch`, `undici`; `node:http`, `fastify` | map | |
| pydantic | parsing and validation models | `zod`, `valibot`, `@sinclair/typebox` with `ajv` | map | Pydantic v2 lax mode turns `"1"` into `1` for `int` fields; `zod` does not unless `z.coerce` is used. Error shapes and messages differ. |
| attrs | class boilerplate | plain classes | drop | As dataclasses (section 1). |
| marshmallow | serialization schemas | `zod`, `valibot` | map | |
| jsonschema | JSON Schema validation | `ajv` with `ajv-formats` | map | Use the same draft (`ajv/dist/2020` for 2020-12). Python `jsonschema` checks `format` only when a format checker is passed; align both sides. |
| click | CLI framework | `commander`, `yargs`, `citty` | map | Click exits with code 2 on usage errors; set the same code explicitly. Help text differs. |
| typer | CLI from type hints | `commander`, `clipanion`, `citty` | map | |
| rich | terminal styling, tables, progress | `picocolors`, `util.styleText`, `cli-table3`, `ora` | rewrite narrowly | No single equivalent. |
| tqdm | progress bars | `cli-progress` | map | |
| colorama | ANSI colors on Windows | none | drop | Modern Windows terminals handle ANSI. |
| python-dateutil | parsing, `relativedelta`, `rrule` | `date-fns`, Luxon, `rrule` | map | `dateutil.parser.parse` guesses formats; write an explicit parser for the formats fixtures contain. |
| pytz | time zones | Temporal, Luxon, `Intl` | use the platform | `datetime(..., tzinfo=pytz.timezone("Europe/Warsaw"))` gets the LMT offset `+01:24`; `localize()` gets `+01:00` (checked). Port the result, not the bug, unless fixtures record it. |
| arrow, pendulum | datetime convenience | Luxon, `dayjs`, `date-fns` | map | |
| PyYAML | YAML | `yaml` with `{ version: "1.1" }`, `js-yaml` | map | PyYAML is YAML 1.1 (T78). |
| ruamel.yaml | round-trip YAML with comments | `yaml` Document API | map | |
| toml, tomli, tomllib | TOML | `smol-toml` | map | `tomllib` (3.11+) and `tomli` are TOML 1.0; the old `toml` package is not. |
| jinja2 | templates | `nunjucks` | map | Close syntax, not identical. Nunjucks autoescapes by default; a Jinja2 `Environment` does not unless `autoescape` is set. |
| regex | extended regex engine | `RegExp` with the `v` flag | rewrite narrowly | Section 9. |
| Unidecode, text-unidecode | ASCII transliteration | `any-ascii`, `transliteration` | map | Per-character tables differ; diff outputs over the fixture alphabet. Check licenses. |
| chardet, charset-normalizer | encoding detection | `jschardet`, `chardet` (npm) | map | Guesses and confidences differ; never treat a guess as a fixture value without review. |
| beautifulsoup4 | HTML parsing and queries | `cheerio`, `linkedom`, `parse5` | map | The tree depends on the parser. `cheerio` (parse5, HTML5 algorithm) is closest to bs4 with `html5lib`, not with `html.parser` or `lxml`. |
| lxml | XML, HTML, XPath, XSLT | `fast-xml-parser`, `@xmldom/xmldom` with `xpath`, `saxes` | rewrite narrowly | No fair equivalent for the full API (XSLT, schema validation). |
| numpy | n-dimensional arrays | typed arrays and loops, `@stdlib/*`, `ndarray` | no fair equivalent | Port the few operations used over `Float64Array`. numpy fixed-width integers wrap and `float32` rounds differently from JS doubles; fixtures must record dtypes. |
| pandas | dataframes | `nodejs-polars`, `arquero`, `danfojs` | no fair equivalent | Rewrite the specific transformations and test each column type. |
| scipy | scientific algorithms | `@stdlib/*` | no fair equivalent | |
| sqlalchemy | SQL toolkit and ORM | `kysely`, `knex` (Core); `drizzle-orm`, `mikro-orm`, `typeorm` (ORM) | map by layer | Session and unit-of-work semantics differ. |
| psycopg2, psycopg | PostgreSQL driver | `pg`, `postgres` | map | |
| tenacity | retries | `p-retry`, `cockatiel` | map | A bare tenacity `@retry` retries forever with no wait (checked); `p-retry` defaults to 10 retries with backoff. Set both explicitly. |
| cachetools | LRU and TTL caches | `lru-cache`, `quick-lru`, `@isaacs/ttlcache` | map | |
| more-itertools | iterator helpers | local helpers, `iter-tools` | rewrite narrowly | Prefer local helpers for the few functions used. |
| python-dotenv | `.env` loading | `dotenv`, `node --env-file` (20.6+), `process.loadEnvFile` (20.12+) | use the platform | Quoting, `export` and multiline rules differ. |
| PyJWT | JWT | `jose` | map | |
| cryptography | crypto primitives | `node:crypto`, `@noble/*` | use the platform | |
| Pillow | images | `sharp` | map | Native dependency. |
| Markdown, mistune | Markdown to HTML | `markdown-it`, `marked`, `micromark` | map | HTML output differs between libraries; compare on fixtures. |
| Pygments | syntax highlighting | `shiki`, `highlight.js` | map | Token names and CSS classes differ. |
| packaging | PEP 440 versions | `semver` | map | PEP 440 and semver differ in syntax and pre-release ordering. |
| python-slugify | slugs | `@sindresorhus/slugify`, `slugify` | map | |
| orjson, ujson | fast JSON | `JSON` | use the platform | orjson output is compact, unlike `json.dumps` defaults. |
| boto3 | AWS | `@aws-sdk/client-*` | map | |
| websockets | WebSocket | `ws`; global `WebSocket` client on Node 22+ | map | |
| six, typing_extensions, future | compatibility shims | none | drop | |

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | pytest, unittest | vitest (`node:test` if no dependencies are allowed) |
| Assertions and fixtures | `assert`, pytest fixtures, `conftest.py` | `expect`, `beforeEach`/`afterEach` or `test.extend` fixtures, `setupFiles` |
| Parametrize | `@pytest.mark.parametrize` | `it.each` / `test.each` |
| Exceptions | `pytest.raises(E, match="re")` | `expect(() => f()).toThrow(E)` plus `.toThrow(/re/)` (`match` uses `re.search`, so no anchors) |
| Approximate floats | `pytest.approx(x)` (rel 1e-6, abs 1e-12) | `isClose(a, b, 1e-6, 1e-12)`; `toBeCloseTo` uses a different rule (decimal digits) |
| Property tests | hypothesis | fast-check |
| Mocks | `unittest.mock`, `monkeypatch`, `mocker` | `vi.fn`, `vi.spyOn`, `vi.mock` (hoisted, per module), `vi.stubEnv`, `vi.stubGlobal` |
| Temp dirs | `tmp_path` | `mkdtempSync` in `beforeEach`, `rmSync` in `afterEach` |
| Output capture | `capsys`, `caplog` | `vi.spyOn(process.stdout, "write")`, spy on the injected logger |
| Time | freezegun | `vi.useFakeTimers()`, `vi.setSystemTime(...)` |
| Async tests | pytest-asyncio | `async` test functions |
| Snapshots | syrupy, snapshottest | `toMatchSnapshot`, `toMatchFileSnapshot` |
| Doctests | doctest | convert to ordinary tests |
| Skips | `pytest.mark.skip`, `skipif`, `xfail` | `it.skip`, `it.skipIf`, `it.fails` |
| Lint | ruff, flake8, pylint | eslint with typescript-eslint, or biome |
| Format | black, ruff format | prettier, or biome |
| Type check | mypy, pyright | `tsc --noEmit` with `strict` |
| Coverage | coverage.py, pytest-cov | `@vitest/coverage-v8` |
| Environments | tox, nox | npm scripts plus a CI matrix over Node 20, 22, 24 |
| Hooks | pre-commit | lefthook, or husky with lint-staged |

hypothesis to fast-check:

```python
@given(st.text(), st.integers())
def test_roundtrip(s, n):
    assert decode(encode(s, n)) == (s, n)
```

```ts
it("round-trips", () => {
  fc.assert(
    fc.property(fc.string({ unit: "binary" }), fc.bigInt(), (s, n) => {
      expect(decode(encode(s, n))).toEqual([s, n]);
    }),
  );
});
```

- `st.text()` draws any code point. `fc.string()` defaults to printable ASCII
  (checked on fast-check 4.10: no code point above 126 in 2,000 samples); use
  `fc.string({ unit: "binary" })` (fast-check 3.22+).
- `st.integers()` is unbounded; `fc.integer()` is 32-bit. Use `fc.bigInt()`
  or `fc.maxSafeInteger()` to match the domain.
- `st.floats()` and `fc.double()` both include NaN and infinities unless told
  not to; set the same options on both sides.
- `@example(...)` becomes an explicit test case; `assume(x)` becomes
  `fc.pre(x)`.

Run the TS tests with the same pinned environment used to record fixtures
(`TZ=UTC`, `LANG=C.UTF-8` or another fixed locale), plus one extra run with a
non-UTC zone and a non-English locale to catch leaks (T81, T96).

## 15. Known traps

### T1. Modulo takes the sign of the divisor

- Tags: `numeric`
- Source behavior: `%` and `//` floor, so `%` has the sign of the divisor: `-7 % 3 == 2`, `-7 // 2 == -4`.
- Target behavior: `%` truncates and takes the sign of the dividend. BigInt `/` also truncates.
- Detect: Python `-7 % 3` is `2`; TS `-7 % 3` is `-1`.
- Port rule: use `intMod` and `intFloorDiv` for numbers, `bigMod` and `bigFloorDiv` for `bigint` (section 6).

### T2. Float floor division is not `Math.floor(a / b)`

- Tags: `numeric`
- Source behavior: float `//` and `%` come from `fmod` plus a correction, so `1 // 0.1 == 9.0` and `1 % 0.1 == 0.09999999999999995`.
- Target behavior: `1 / 0.1` rounds to exactly `10`, so `Math.floor` gives `10`.
- Detect: Python `1 // 0.1` is `9.0`; TS `Math.floor(1 / 0.1)` is `10`.
- Port rule: use `pyDivmod` for float operands. `Math.floor(a / b)` is exact only for integers within `Number.MAX_SAFE_INTEGER`.

### T3. `round()` rounds ties to even

- Tags: `numeric`, `float-format`
- Source behavior: `round(0.5) == 0`, `round(1.5) == 2`, `round(2.5) == 2`, `round(-2.5) == -2`.
- Target behavior: `Math.round` rounds ties toward positive infinity: `0.5` to `1`, `2.5` to `3`.
- Detect: Python `round(2.5)` is `2`; TS `Math.round(2.5)` is `3`.
- Port rule: use `pyRoundInt`.

### T4. `round(x, n)` and `.nf` formatting at exact ties

- Tags: `numeric`, `float-format`
- Source behavior: rounds the exact binary value, ties to even. `round(0.125, 2) == 0.12` (an exact tie), `round(2.675, 2) == 2.67` (2.675 is stored as 2.67499...). `f"{0.125:.2f}"` is `'0.12'`.
- Target behavior: `toFixed` also uses the exact value but breaks ties upward. `Math.round(x * 100) / 100` rounds the product: `Math.round(2.675 * 100) / 100` is `2.68`. `new Decimal(2.675)` from decimal.js starts from the shortest string `"2.675"` and also gets `2.68`.
- Detect: Python `round(0.125, 2)` is `0.12`; TS `Number((0.125).toFixed(2))` is `0.13`.
- Port rule: use `pyRound` for `round(x, n)` and `pyFormatFixed` for `.nf` formatting (section 6). `pyRound(x, n).toFixed(n)` is not enough: it loses the sign of `-0.0` and can round a tie the other way for large `n`.

### T5. Float to string

- Tags: `float-format`
- Source behavior: `str` and `repr` print the shortest round-trip digits, always with a `.0` or an exponent, and switch to exponent form below 1e-4 and from 1e16: `str(1.0) == '1.0'`, `repr(1e16) == '1e+16'`, `repr(1e-5) == '1e-05'`, `str(-0.0) == '-0.0'`, `str(float("inf")) == 'inf'`, `str(float("nan")) == 'nan'`.
- Target behavior: `String(1.0)` is `"1"`, `String(1e16)` is `"10000000000000000"`, `String(1e-5)` is `"0.00001"`, `String(-0)` is `"0"`, and `"Infinity"`, `"NaN"`. The digits themselves match.
- Detect: Python `str(1.0)` is `'1.0'`; TS `String(1.0)` is `"1"`.
- Port rule: use `pyFloatRepr` wherever a float becomes text: string building, logging that tests read, JSON (T63), error messages.

### T6. Integers above `2**53` lose precision

- Tags: `numeric`
- Source behavior: `int` is arbitrary precision.
- Target behavior: `number` is a double; integers above `2**53` round.
- Detect: Python `2**53 + 1` is `9007199254740993`; TS `2 ** 53 + 1` is `9007199254740992`.
- Port rule: choose `bigint` for every value that can exceed `Number.MAX_SAFE_INTEGER` (section 1 rule 1), including intermediate products.

### T7. Bitwise operators work on 32 bits

- Tags: `numeric`
- Source behavior: `<<`, `>>`, `&`, `|`, `^`, `~` work on unbounded integers.
- Target behavior: on `number`, operands are cut to signed 32-bit integers first.
- Detect: Python `1 << 31` is `2147483648`; TS `1 << 31` is `-2147483648`.
- Port rule: use `bigint` for masks, shifts and hashes wider than 31 bits; use `>>> 0` only when the source masks to 32 bits explicitly.

### T8. Division by zero does not throw

- Tags: `numeric`, `error-model`
- Source behavior: `1 / 0`, `1.0 / 0`, `1 // 0` and `1 % 0` raise `ZeroDivisionError`. `math.sqrt(-1)` raises `ValueError`.
- Target behavior: `1 / 0` is `Infinity`, `1 % 0` is `NaN`, `Math.sqrt(-1)` is `NaN`.
- Detect: Python `1 / 0` raises `ZeroDivisionError`; TS `1 / 0` is `Infinity`.
- Port rule: add explicit checks that throw the mapped error class wherever the source can divide by zero or call `math` outside the domain.

### T9. `sum()` of floats is compensated on 3.12+

- Tags: `numeric`
- Source behavior: CPython 3.12+ sums floats with Neumaier compensation; 3.9 to 3.11 add naively.
- Target behavior: `reduce((a, b) => a + b, 0)` adds naively.
- Detect: Python `sum([0.1] * 10)` is `1.0` on 3.12 and 3.13, `0.9999999999999999` on 3.9; TS `Array(10).fill(0.1).reduce((a, b) => a + b, 0)` is `0.9999999999999999`.
- Port rule: record the Python version that produced the fixtures. For 3.12+ use `pySum`; for older versions use plain addition.

### T10. `int()` and `float()` parsing is strict

- Tags: `numeric`, `error-model`
- Source behavior: `int("12abc")`, `int("")`, `int("1.0")` raise `ValueError`; `int(" 12 ")`, `int("1_000")` and `int("٣")` succeed.
- Target behavior: `parseInt("12abc")` is `12`, `Number("")` is `0`, `Number("1_000")` is `NaN`.
- Detect: Python `int("12abc")` raises `ValueError`; TS `parseInt("12abc")` is `12`.
- Port rule: use `pyInt` (section 6) and a strict regex before `Number` for floats. Never `parseInt` or `Number` alone on external input.

### T11. `int` and `float` are one type in TS

- Tags: `numeric`, `reflection`
- Source behavior: `1` and `1.0` are different types; code branches on `isinstance(x, float)`, and output differs (`json.dumps(1.0) == '1.0'`).
- Target behavior: there is one `number`; `1.0` is an integer value.
- Detect: Python `isinstance(1.0, int)` is `False`; TS `Number.isInteger(1.0)` is `true`.
- Port rule: when behavior or output depends on int versus float, carry the distinction explicitly (separate parameters, a wrapper type, or schema knowledge of which fields are floats) and format floats with `pyFloatRepr`.

### T12. Seeded random sequences

- Tags: `numeric`
- Source behavior: `random.seed(n)` gives a reproducible Mersenne Twister sequence.
- Target behavior: `Math.random` cannot be seeded.
- Detect: Python `random.seed(1); random.random()` is `0.13436424411240122`; TS has no seeded equivalent.
- Port rule: if fixtures depend on seeded values, port MT19937 together with CPython's `random()`, `getrandbits`, `randrange` and `shuffle` algorithms and test against the fixtures. Otherwise mark the outputs nondeterministic in the contract.

### T13. decimal.js defaults differ from Python's decimal context

- Tags: `numeric`
- Source behavior: the default context has 28 significant digits and `ROUND_HALF_EVEN`. `Decimal(0.1)` keeps the exact binary value (`0.1000000000000000055511151231257827021181583404541015625`). `str(Decimal("1E+2"))` is `'1E+2'`.
- Target behavior: decimal.js defaults to 20 digits and `ROUND_HALF_UP`; `new Decimal(0.1)` is `0.1`; `new Decimal("1E+2").toString()` is `"100"`.
- Detect: Python `Decimal(1) / Decimal(3)` is `Decimal('0.3333333333333333333333333333')`; TS `new Decimal(1).div(3).toString()` is `"0.33333333333333333333"`.
- Port rule: create one configured constructor, `Decimal.clone({ precision: 28, rounding: Decimal.ROUND_HALF_EVEN })`, build values from strings, and write a `toString` helper that follows Python's exponent rules when text is observable.

### T14. Length and indexing count code units

- Tags: `unicode`
- Source behavior: `len`, indexes and slices count code points.
- Target behavior: they count UTF-16 code units; astral characters count twice.
- Detect: Python `len("😀")` is `1`; TS `"😀".length` is `2`.
- Port rule: when a length or offset is observable, work on `Array.from(s)`. Keep UTF-16 offsets only when they never leave the module.

### T15. Reversing or slicing splits surrogate pairs

- Tags: `unicode`
- Source behavior: `"😀a"[::-1] == 'a😀'`.
- Target behavior: `split("")` and index-based slicing cut between the two halves of a surrogate pair, producing invalid strings.
- Detect: Python `"😀a"[::-1]` is `'a😀'`; TS `"😀a".split("").reverse().join("")` is `"a\ude00\ud83d"`.
- Port rule: use `Array.from(s)` (code points) for reversing and slicing; use `Intl.Segmenter` if the source cut by grapheme with a library.

### T16. `casefold()` has no JS equivalent

- Tags: `unicode`
- Source behavior: `casefold()` applies full Unicode case folding: `"ß".casefold() == "ss"`.
- Target behavior: `toLowerCase()` leaves `ß` alone.
- Detect: Python `"Straße".casefold() == "STRASSE".casefold()` is `True`; TS `"Straße".toLowerCase() === "STRASSE".toLowerCase()` is `false`.
- Port rule: use a fold table generated from `CaseFolding.txt` (section 7). `toUpperCase().toLowerCase()` is wrong on 174 code points.

### T17. `capitalize()` and `title()` lowercase the rest

- Tags: `unicode`
- Source behavior: `"hELLO".capitalize() == 'Hello'`; `"they're".title() == "They'Re"`; both use titlecase for the first letter.
- Target behavior: the usual JS idiom only uppercases the first character.
- Detect: Python `"hELLO".capitalize()` is `'Hello'`; TS `s[0].toUpperCase() + s.slice(1)` is `"HELLO"`.
- Port rule: use `pyCapitalize` and `pyTitle` (section 7); add an override map if the domain contains titlecase digraphs or ligatures.

### T18. `str` predicates are Unicode-aware

- Tags: `unicode`
- Source behavior: `isdigit`, `isdecimal`, `isalpha`, `isalnum`, `isnumeric` accept non-ASCII characters: `"٣".isdigit()` and `"é".isalpha()` are `True`.
- Target behavior: `/^\d+$/` and `/^[a-z]+$/i` are ASCII.
- Detect: Python `"٣".isdigit()` is `True`; TS `/^\d+$/.test("٣")` is `false`.
- Port rule: use the `\p{...}` regexes from section 7, and record which predicate the source used, since `isdigit`, `isdecimal` and `isnumeric` differ.

### T19. Whitespace sets differ

- Tags: `unicode`
- Source behavior: `strip()`, `split()`, `isspace()` and `re` `\s` treat U+001C to U+001F and U+0085 as whitespace, and not U+FEFF.
- Target behavior: `trim()` and `\s` treat U+FEFF as whitespace, and not U+001C to U+001F or U+0085.
- Detect: Python `"\x1ca\x1c".strip()` is `'a'`; TS `"\x1ca\x1c".trim()` is `"\x1ca\x1c"`.
- Port rule: use `PY_WS`, `pyStrip`, `pySplit` (section 7).

### T20. `str.split()` without a separator

- Tags: `unicode`
- Source behavior: `split()` splits on runs of whitespace and drops empty strings: `"".split() == []`. `split(sep, maxsplit)` keeps the remainder in the last item.
- Target behavior: `split(" ")` keeps empty strings; `split(/\s+/)` keeps leading and trailing empties; `split(sep, limit)` drops the remainder.
- Detect: Python `"  a  b ".split()` is `['a', 'b']`; TS `"  a  b ".split(" ")` is `["", "", "a", "", "b", ""]`.
- Port rule: use `pySplit` and `pySplitSep`.

### T21. `str.replace` replaces every occurrence

- Tags: `unicode`, `regex`
- Source behavior: `s.replace(a, b)` replaces all occurrences, and `b` is literal.
- Target behavior: `s.replace(a, b)` with a string `a` replaces only the first occurrence, and `$&`, `$1` and friends in `b` are expanded even for a string pattern.
- Detect: Python `"aa".replace("a", "b")` is `'bb'`; TS `"aa".replace("a", "b")` is `"ba"`.
- Port rule: use `s.split(a).join(b)` for non-empty `a`, or `replaceAll(a, () => b)` to keep `b` literal.

### T22. `splitlines()` is not `split("\n")`

- Tags: `unicode`, `io`
- Source behavior: `splitlines()` breaks on `\r\n`, `\r`, `\n`, `\v`, `\f`, U+001C to U+001E, U+0085, U+2028, U+2029, and drops the trailing empty line.
- Target behavior: `split("\n")` breaks on `\n` only and keeps a trailing `""`.
- Detect: Python `"a\n".splitlines()` is `['a']`; TS `"a\n".split("\n")` is `["a", ""]`.
- Port rule: use `pySplitlines`.

### T23. `zfill` and padding

- Tags: `float-format`, `unicode`
- Source behavior: `zfill` keeps a leading sign first; all padding (`zfill`, `rjust`, format widths) counts code points.
- Target behavior: `padStart` pads before the sign and counts UTF-16 units: `"😀".padStart(3)` adds one space, Python's `f"{'😀':>3}"` adds two.
- Detect: Python `"-5".zfill(3)` is `'-05'`; TS `"-5".padStart(3, "0")` is `"0-5"`.
- Port rule: use `pyZfill`, and pad with `width - Array.from(s).length`.

### T24. String comparison by UTF-16 unit

- Tags: `ordering`, `unicode`
- Source behavior: `<` and `sorted` compare code points.
- Target behavior: `<` and the default `sort` compare UTF-16 units, so astral characters sort before U+E000 to U+FFFF.
- Detect: Python `sorted(["\uff5e", "😀"])` is `['～', '😀']`; TS `["\uff5e", "😀"].sort()` is `["😀", "～"]`.
- Port rule: sort and compare strings with `compareCodePoints`; never `localeCompare` for this (T97).

### T25. Implicit `str()` of None, bools and containers

- Tags: `reflection`, `nullability`
- Source behavior: f-strings and `str()` call `__str__`: `None` gives `'None'`, `True` gives `'True'`, `[1, 2]` gives `'[1, 2]'`, `{'a': 1}` gives `"{'a': 1}"`.
- Target behavior: template literals give `"null"`, `"true"`, `"1,2"`, `"[object Object]"`.
- Detect: Python `f"{True}"` is `'True'`; TS `` `${true}` `` is `"true"`.
- Port rule: when such text is observable, write a `pyStr` helper for the types involved and use it in every interpolation; never interpolate containers directly.

### T26. `\w`, `\d`, `\s` are Unicode in Python

- Tags: `regex`, `unicode`
- Source behavior: in `str` patterns `\w` matches letters and digits of every script, `\d` matches every decimal digit, `\s` matches Python's whitespace set.
- Target behavior: `\w` and `\d` are ASCII even with the `u` or `v` flag; `\s` uses JS whitespace.
- Detect: Python `re.match(r"\w+", "café").group()` is `'café'`; TS `/\w+/u.exec("café")[0]` is `"caf"`.
- Port rule: translate with the class table in section 9 unless the source used `re.ASCII`.

### T27. `\b` is ASCII in JS

- Tags: `regex`, `unicode`
- Source behavior: `\b` uses Unicode `\w`.
- Target behavior: `\b` uses ASCII `\w`, so it fires inside words with accents.
- Detect: Python `re.sub(r"\b", "|", "naïve")` is `'|naïve|'`; TS `"naïve".replace(/\b/gu, "|")` is `"|na|ï|ve|"`.
- Port rule: use `PY_B` and `PY_NB` (section 9).

### T28. `re.sub` replaces every match

- Tags: `regex`
- Source behavior: `re.sub` replaces all matches unless `count` is given.
- Target behavior: `replace` with a non-global regex replaces the first match only.
- Detect: Python `re.sub("a", "b", "aa")` is `'bb'`; TS `"aa".replace(/a/, "b")` is `"ba"`.
- Port rule: use a `g` regex (or `replaceAll`) for `re.sub` without `count`.

### T29. Replacement template syntax

- Tags: `regex`
- Source behavior: `\1`, `\g<1>`, `\g<name>` are group references; `$` is literal; escapes such as `\n` are processed.
- Target behavior: `$1`, `$<name>`, `$&` are references; backslashes are literal.
- Detect: Python `re.sub(r"(\d+)", r"$1!", "a1")` is `'a$1!'`; TS `"a1".replace(/(\d+)/, "$1!")` is `"a1!"`.
- Port rule: translate templates with the table in section 9, or use a replacement function.

### T30. `$` matches before a trailing newline

- Tags: `regex`
- Source behavior: without MULTILINE, `$` matches at the end and just before a final `\n`.
- Target behavior: without `m`, `$` matches only at the end.
- Detect: Python `re.match(r"^abc$", "abc\n")` is a match; TS `/^abc$/.test("abc\n")` is `false`.
- Port rule: translate `$` to `(?=\n?$)`; translate `\Z` to `$`.

### T31. `\A` and `\Z` do not exist in JS

- Tags: `regex`
- Source behavior: `\A` and `\Z` anchor at the start and the very end.
- Target behavior: without `u`, `\A` and `\Z` match the letters `A` and `Z`; with `u` they are a `SyntaxError`.
- Detect: Python `re.search(r"\Afoo\Z", "AfooZ")` is `None`; TS `/\Afoo\Z/.test("AfooZ")` is `true`.
- Port rule: `\A` becomes `^` and `\Z` becomes `$`, both without the `m` flag.

### T32. `re.match` anchors; `fullmatch` needs a group

- Tags: `regex`
- Source behavior: `re.match` anchors at the start only; `re.fullmatch` requires the whole string, across alternatives.
- Target behavior: `test` and `exec` search anywhere; `^a|ab$` anchors each alternative separately.
- Detect: Python `re.fullmatch(r"a|ab", "xab")` is `None`; TS `/^a|ab$/.test("xab")` is `true`.
- Port rule: `re.match` becomes `^(?:...)`, `re.fullmatch` becomes `^(?:...)$`, both without `m`.

### T33. `.` matches `\r` and line separators

- Tags: `regex`
- Source behavior: without DOTALL, `.` excludes only `\n`.
- Target behavior: `.` also excludes `\r`, U+2028 and U+2029.
- Detect: Python `re.fullmatch(r".", "\r")` is a match; TS `/^.$/.test("\r")` is `false`.
- Port rule: translate `.` to `[^\n]`.

### T34. Case-insensitive matching needs the `u` flag

- Tags: `regex`, `unicode`
- Source behavior: `re.IGNORECASE` on `str` patterns uses Unicode case folding: `k` matches the Kelvin sign U+212A, `s` matches `ſ`.
- Target behavior: `i` without `u` folds only simple cases.
- Detect: Python `re.match(r"(?i)k", "\u212a")` is a match; TS `/k/i.test("\u212a")` is `false` (`/k/iu` gives `true`).
- Port rule: always pair `i` with `u`; add fixtures for the non-ASCII letters the domain uses, since the two folding tables are close but not proven identical.

### T35. Syntax that JS reads differently or rejects

- Tags: `regex`
- Source behavior: `a{,2}` means `a{0,2}`; `a{` and `\-` are literals; `(?P<n>...)`, `(?P=n)`, atomic groups `(?>...)` and possessive quantifiers (3.11+) are valid.
- Target behavior: without `u`, `a{,2}` is literal text; with `u`, `a{` and `\-` are `SyntaxError`; `(?P<`, `(?>` and `*+` are always `SyntaxError`.
- Detect: Python `re.match(r"a{,2}", "aaa").group()` is `'aa'`; TS `/a{,2}/.exec("aaa")` is `null`.
- Port rule: translate with the tables in section 9 and construct every pattern at module load so syntax errors fail the first test run.

### T36. `re.split` with empty matches and `maxsplit`

- Tags: `regex`
- Source behavior: empty matches split (3.7+); `maxsplit` keeps the remainder; captured groups are included, with `None` for groups that did not take part.
- Target behavior: `split` skips empty matches at the edges, its `limit` truncates, and unmatched groups are `undefined`.
- Detect: Python `re.split(r"x*", "ab")` is `['', 'a', 'b', '']`; TS `"ab".split(/x*/)` is `["a", "b"]`.
- Port rule: use `pyReSplit`.

### T37. `re.findall` returns groups

- Tags: `regex`
- Source behavior: with one group, `findall` returns that group per match; with several, tuples (unmatched groups as `''`); with none, whole matches.
- Target behavior: `match` with `g` returns whole matches.
- Detect: Python `re.findall(r"a(b)", "abab")` is `['b', 'b']`; TS `"abab".match(/a(b)/g)` is `["ab", "ab"]`.
- Port rule: use `pyFindall`.

### T38. Global regexes keep state

- Tags: `regex`, `mutability`
- Source behavior: compiled patterns are stateless.
- Target behavior: a regex with `g` or `y` stores `lastIndex`; `test` and `exec` continue from it.
- Detect: Python `p = re.compile("a")` then `p.search("a")` twice matches both times; TS `const p = /a/g; [p.test("a"), p.test("a")]` is `[true, false]`.
- Port rule: module-level regexes carry no `g` or `y`; derive a global copy inside the function that needs one (as `pyFindall` does).

### T39. Unmatched groups are `undefined`, not `None`

- Tags: `regex`, `nullability`
- Source behavior: `m.group(n)` for a group that did not take part is `None`.
- Target behavior: `m[n]` and replacement callback arguments are `undefined`.
- Detect: Python `re.sub(r"(a)|b", lambda m: str(m.group(1)), "ab")` is `'aNone'`; TS `"ab".replace(/(a)|b/g, (m, p1) => String(p1))` is `"aundefined"`.
- Port rule: normalize with `?? null` where the value is stored or compared, and handle the absent case explicitly where it is printed.

### T40. Object key order puts integer-like keys first

- Tags: `ordering`
- Source behavior: dicts keep insertion order for every key.
- Target behavior: plain objects list integer-like keys first, in numeric order, then string keys in insertion order.
- Detect: Python `list({"b": 1, "1": 2})` is `['b', '1']`; TS `Object.keys({ b: 1, "1": 2 })` is `["1", "b"]`.
- Port rule: use `Map` for every dict whose keys come from data.

### T41. Set iteration order

- Tags: `ordering`
- Source behavior: sets iterate in hash order. Small ints come out sorted by value modulo the table size; strings vary between runs because of hash randomization.
- Target behavior: `Set` iterates in insertion order.
- Detect: Python `list({3, 1, 2})` is `[1, 2, 3]`; TS `[...new Set([3, 1, 2])]` is `[3, 1, 2]`.
- Port rule: if output order comes from a set, it is not a contract; the contract step should have normalized it (sorted). If fixtures recorded it, sort in both places and record the normalization.

### T42. Default sort is lexicographic

- Tags: `ordering`
- Source behavior: `sorted` compares values by type: numbers numerically, strings by code point, tuples element-wise. Mixed types raise `TypeError`.
- Target behavior: `sort()` without a comparator converts every element to a string.
- Detect: Python `sorted([10, 9, 1])` is `[1, 9, 10]`; TS `[10, 9, 1].sort()` is `[1, 10, 9]`.
- Port rule: always pass a comparator; use `toSorted` (Node 20+) where the source used `sorted` (which copies).

### T43. `reverse=True` keeps equal elements in order

- Tags: `ordering`
- Source behavior: `sorted(xs, key=k, reverse=True)` is stable: equal keys keep their original order.
- Target behavior: sorting ascending then calling `reverse()` flips equal elements.
- Detect: Python `sorted([("a", 1), ("b", 1)], key=lambda t: t[1], reverse=True)` is `[('a', 1), ('b', 1)]`; TS `[["a", 1], ["b", 1]].sort((x, y) => x[1] - y[1]).reverse()` is `[["b", 1], ["a", 1]]`.
- Port rule: invert the comparator (`(x, y) => k(y) - k(x)`) instead of reversing.

### T44. Tuples compare element-wise

- Tags: `ordering`
- Source behavior: `(1, 10) < (1, 9)` compares 10 with 9.
- Target behavior: `<` on arrays compares their string forms, `"1,10" < "1,9"`.
- Detect: Python `(1, 10) < (1, 9)` is `False`; TS `[1, 10] < [1, 9]` is `true`.
- Port rule: write a comparator that compares element by element (strings with `compareCodePoints`); use it for `sorted` keys that return tuples.

### T45. `itertools.groupby` groups consecutive runs

- Tags: `ordering`
- Source behavior: `groupby` starts a new group whenever the key changes.
- Target behavior: `Object.groupBy` (Node 21+) and lodash `groupBy` collect all equal keys into one group.
- Detect: Python `[k for k, _ in groupby("aaba")]` is `['a', 'b', 'a']`; TS `Object.keys(Object.groupBy("aaba", (c) => c))` is `["a", "b"]`.
- Port rule: use the `groupby` helper (section 5).

### T46. `map` and `filter` are lazy

- Tags: `ordering`
- Source behavior: `map(f, xs)` calls `f` only as items are consumed, possibly never.
- Target behavior: `Array.prototype.map` calls `f` on every item immediately.
- Detect: Python `log = []; m = map(log.append, [1])` leaves `log == []`; TS `[1].map((x) => log.push(x))` leaves `log` as `[1]`.
- Port rule: when `f` has side effects or the iterator may be partly consumed, use a generator or iterator helpers (Node 22+).

### T47. Mutating a dict while iterating it

- Tags: `ordering`, `mutability`
- Source behavior: changing a dict's size during iteration raises `RuntimeError`.
- Target behavior: `Map` iteration tolerates deletes and visits added keys.
- Detect: Python `for k in d: del d[k]` with `d = {"a": 1, "b": 2}` raises `RuntimeError`; TS `for (const k of m.keys()) m.delete(k)` empties the map.
- Port rule: iterate over a snapshot (`[...m.keys()]`) when the source iterated over `list(d)`; if the source relied on the error, throw it explicitly.

### T48. `in` checks keys, not values

- Tags: `reflection`
- Source behavior: `x in xs` tests membership for lists, tuples, strings, sets and dict keys.
- Target behavior: `x in arr` tests whether the array has a property named `x` (an index).
- Detect: Python `"a" in ["a"]` is `True`; TS `"a" in ["a"]` is `false`.
- Port rule: `includes` for arrays and strings, `has` for `Set` and `Map`. `in` is only for property checks.

### T49. Negative indexes and missing keys

- Tags: `nullability`, `error-model`
- Source behavior: `xs[-1]` is the last item; out-of-range indexes and missing keys raise `IndexError` and `KeyError`.
- Target behavior: `xs[-1]` and missing keys give `undefined`.
- Detect: Python `[1, 2, 3][-1]` is `3`; TS `[1, 2, 3][-1]` is `undefined`.
- Port rule: use `at(-1)` for negative indexes; where the source relies on the exception, check bounds and throw the mapped error. Turn on `noUncheckedIndexedAccess`.

### T50. `==` compares values

- Tags: `reflection`
- Source behavior: `==` on lists, dicts, tuples, sets and dataclasses compares contents.
- Target behavior: `===` on arrays and objects compares identity.
- Detect: Python `[1, 2] == [1, 2]` is `True`; TS `[1, 2] === [1, 2]` is `false`.
- Port rule: use `util.isDeepStrictEqual` for plain data and `equals` methods for classes (section 1 rule 2).

### T51. Map and Set keys compare by identity

- Tags: `mutability`, `reflection`
- Source behavior: dict keys and set members compare with `__eq__` and `__hash__`, so tuples work as keys; `1`, `1.0` and `True` are the same key.
- Target behavior: arrays and objects are keys by identity; `1` and `true` are different keys.
- Detect: Python `{(1, 2): "x"}[(1, 2)]` is `'x'`; TS `new Map([[[1, 2], "x"]]).get([1, 2])` is `undefined`.
- Port rule: encode compound keys to a string (for example `JSON.stringify` of the tuple) or nest maps; normalize `True`/`1` collisions only if the source relied on them.

### T52. Empty containers are truthy in JS

- Tags: `nullability`
- Source behavior: empty lists, dicts, sets, tuples and strings, `0`, `0.0` and `None` are false.
- Target behavior: `[]` and `{}` are truthy; `0`, `""`, `NaN`, `null` and `undefined` are falsy.
- Detect: Python `bool([])` is `False`; TS `Boolean([])` is `true`.
- Port rule: port the intent: `xs.length > 0`, `m.size > 0`, `x !== null`. Do not replace `x or y` with `x ?? y` (section 3).

### T53. `dict.get(k, default)` keeps a stored `None`

- Tags: `nullability`
- Source behavior: the default applies only when the key is missing.
- Target behavior: `??` also replaces a stored `null`.
- Detect: Python `{"a": None}.get("a", 5)` is `None`; TS `new Map([["a", null]]).get("a") ?? 5` is `5`.
- Port rule: `m.has(k) ? m.get(k) : dflt`.

### T54. Mutable default arguments are shared

- Tags: `mutability`
- Source behavior: a default value is evaluated once; a mutated default list persists across calls.
- Target behavior: default parameter expressions are evaluated on every call.
- Detect: Python `def f(x, acc=[]): acc.append(x); return acc` then `f(1); f(2)` is `[1, 2]`; TS `function f(x: number, acc: number[] = []) { acc.push(x); return acc; }` gives `[2]`.
- Port rule: if fixtures depend on the sharing (usually a bug or a hidden cache), hoist a module-level variable and record it; otherwise keep the fresh default and record the divergence.

### T55. `+=` on a list mutates it in place

- Tags: `mutability`
- Source behavior: `a += [2]` extends the same list, so aliases see the change; `a = a + [2]` creates a new list.
- Target behavior: the common ports `a = [...a, 2]` and `a = a.concat([2])` create a new array.
- Detect: Python `a = [1]; b = a; a += [2]` leaves `b == [1, 2]`; TS `let a = [1]; const b = a; a = [...a, 2];` leaves `b` as `[1]`.
- Port rule: `a += xs` becomes `a.push(...xs)` (or a loop for large `xs`); `a = a + xs` becomes a new array.

### T56. `structuredClone` is not `deepcopy`

- Tags: `mutability`, `reflection`
- Source behavior: `copy.deepcopy` keeps classes, handles cycles, and honors `__deepcopy__`.
- Target behavior: `structuredClone` returns plain objects for class instances and throws on functions.
- Detect: Python `isinstance(copy.deepcopy(P(1)), P)` is `True`; TS `structuredClone(new P(1)) instanceof P` is `false`.
- Port rule: give classes a `clone()` method; use `structuredClone` only for plain data.

### T57. Enums

- Tags: `reflection`
- Source behavior: members are singletons with `.name` and `.value`; `list(Color)` yields members in definition order; `Color(1)` looks up by value; `str(Color.RED)` is `'Color.RED'`. `str()` of an `IntEnum` member is `'IE.A'` on 3.9 and `'1'` on 3.11+.
- Target behavior: a numeric TS `enum` adds reverse mappings, so `Object.keys` lists values too; `String(Color.RED)` is `"1"`. Node's type stripping rejects `enum`.
- Detect: Python `[m.name for m in Color]` is `['RED']`; TS `Object.keys(Color)` for `enum Color { RED = 1 }` is `["1", "RED"]`.
- Port rule: use an `as const` object plus a union type, with explicit `names`, `fromValue` and `toString` helpers that reproduce what fixtures record.

### T58. Unknown keyword arguments

- Tags: `reflection`, `error-model`
- Source behavior: an unexpected keyword argument raises `TypeError`.
- Target behavior: an options object accepts extra properties at runtime; TS checks them only for object literals.
- Detect: Python `f(1, colour="red")` for `def f(x, *, color="red")` raises `TypeError`; TS `f(1, JSON.parse('{"colour": "red"}'))` runs with the default color.
- Port rule: if the contract includes the error, validate option keys at runtime against a known list.

### T59. `str(KeyError)` is quoted

- Tags: `error-model`
- Source behavior: `str(KeyError(k))` is `repr(k)`.
- Target behavior: `new KeyError(k).message` is the raw text.
- Detect: Python `str(KeyError("a"))` is `"'a'"`; TS `new KeyError("a").message` is `"a"`.
- Port rule: build the message as Python's `repr` of the key when fixtures record `str(e)`.

### T60. Built-in error messages change between Python versions

- Tags: `error-model`
- Source behavior: messages of built-in exceptions are not stable. `max([])`, `datetime(2024, 2, 30)` and `math.sqrt(-1)` also changed wording across these versions.
- Target behavior: the port copies whichever text the agent remembers.
- Detect: Python `1 % 0` raises with `'integer division or modulo by zero'` on 3.9 and `'integer modulo by zero'` on 3.12 and 3.13; TS `1 % 0` is `NaN` with no error.
- Port rule: copy messages from the fixtures, which were recorded on one pinned Python version, and record that version in the strategy.

### T61. `instanceof` fails across module copies

- Tags: `error-model`, `reflection`
- Source behavior: one module object per process, so `except NotFound` catches every `NotFound`.
- Target behavior: an ESM and a CJS build, or two installed versions, give two different classes.
- Detect: TS `new NotFound() instanceof NotFound` across two copies of the same module file is `false` (checked); Python `except NotFound` catches it.
- Port rule: ship one module format, and export an `isFooError` brand check (section 2) for errors that callers catch.

### T62. `catch` catches everything

- Tags: `error-model`
- Source behavior: `except KeyError:` lets other exceptions propagate.
- Target behavior: `catch (e)` catches every thrown value, including bugs.
- Detect: Python `try: int("x") except KeyError: pass` raises `ValueError`; TS `try { pyInt("x"); } catch { }` swallows it.
- Port rule: test the type in every `catch` and rethrow the rest (section 2).

### T63. `json.dumps` default separators

- Tags: `encoding`
- Source behavior: `json.dumps` puts a space after `,` and `:` unless `separators=(",", ":")` is passed.
- Target behavior: `JSON.stringify` emits no spaces.
- Detect: Python `json.dumps({"a": 1, "b": [1, 2]})` is `'{"a": 1, "b": [1, 2]}'`; TS `JSON.stringify({ a: 1, b: [1, 2] })` is `'{"a":1,"b":[1,2]}'`.
- Port rule: when JSON text is observable, write a `pyJsonDumps` helper that reproduces the separators, `ensure_ascii`, `sort_keys` (by code point) and float formatting the source used. With `indent`, Python's output matches `JSON.stringify(x, null, indent)` layout apart from those points.

### T64. `ensure_ascii` is on by default

- Tags: `encoding`, `unicode`
- Source behavior: non-ASCII characters are written as `\uXXXX` escapes, astral ones as surrogate pairs.
- Target behavior: `JSON.stringify` writes them as is.
- Detect: Python `json.dumps("é")` is `'"\\u00e9"'`; TS `JSON.stringify("é")` is `'"é"'`.
- Port rule: in `pyJsonDumps`, escape every UTF-16 unit from 0x7F up (Python escapes DEL too; `JSON.stringify` does not) as a `\u` escape with four lowercase hex digits, unless the source passed `ensure_ascii=False`.

### T65. NaN and Infinity in JSON

- Tags: `encoding`, `float-format`
- Source behavior: `json.dumps` writes `NaN`, `Infinity`, `-Infinity` (invalid JSON) and `json.loads` reads them.
- Target behavior: `JSON.stringify` writes `null`; `JSON.parse("NaN")` throws `SyntaxError`.
- Detect: Python `json.dumps(float("nan"))` is `'NaN'`; TS `JSON.stringify(NaN)` is `'null'`.
- Port rule: reproduce the tokens in `pyJsonDumps`; for parsing, preprocess or use a tolerant parser only if the source accepted them.

### T66. Big integers in JSON

- Tags: `encoding`, `numeric`
- Source behavior: `json.loads` returns exact `int` values of any size; `json.dumps` writes them exactly.
- Target behavior: `JSON.parse` rounds integers above `2**53`; `JSON.stringify` throws on `bigint`.
- Detect: Python `json.loads("12345678901234567890")` is `12345678901234567890`; TS `JSON.parse("12345678901234567890")` is `12345678901234567000`.
- Port rule: use `lossless-json` or `json-bigint` where large integers can occur, or carry them as strings if the contract allows.

### T67. `None` versus `undefined` in JSON

- Tags: `encoding`, `nullability`
- Source behavior: `None` values are written as `null`; keys are kept.
- Target behavior: `undefined` properties are dropped, `undefined` array items become `null`, and `JSON.stringify(undefined)` returns `undefined`.
- Detect: Python `json.dumps({"a": None})` is `'{"a": null}'`; TS `JSON.stringify({ a: undefined })` is `'{}'`.
- Port rule: use `null` for values that are serialized (section 3).

### T68. Sets and Maps in JSON

- Tags: `encoding`, `error-model`
- Source behavior: `json.dumps` raises `TypeError` for sets and other non-JSON types.
- Target behavior: `JSON.stringify` writes `Set` and `Map` as `{}`.
- Detect: Python `json.dumps({1, 2})` raises `TypeError`; TS `JSON.stringify(new Set([1, 2]))` is `'{}'`.
- Port rule: convert explicitly before serializing, and throw the mapped error where the source raised.

### T69. Invalid UTF-8 is replaced silently

- Tags: `encoding`, `error-model`
- Source behavior: `bytes.decode("utf-8")` raises `UnicodeDecodeError`; `str.encode("utf-8")` raises on lone surrogates.
- Target behavior: `TextDecoder` and `Buffer.toString` replace invalid bytes with U+FFFD; `TextEncoder` replaces lone surrogates.
- Detect: Python `b"\xff".decode("utf-8")` raises `UnicodeDecodeError`; TS `new TextDecoder().decode(Uint8Array.of(0xff))` is `"\ufffd"`.
- Port rule: decode with `{ fatal: true }`; check `isWellFormed()` before encoding when the source would raise.

### T70. `TextDecoder` strips the BOM

- Tags: `encoding`
- Source behavior: the `"utf-8"` codec keeps a leading BOM as U+FEFF; `"utf-8-sig"` strips it.
- Target behavior: `TextDecoder` strips it unless `ignoreBOM: true`.
- Detect: Python `b"\xef\xbb\xbfa".decode("utf-8")` is `'\ufeffa'` (length 2); TS `new TextDecoder().decode(Uint8Array.of(0xef, 0xbb, 0xbf, 0x61))` is `"a"`.
- Port rule: `ignoreBOM: true` for `"utf-8"`, the default for `"utf-8-sig"`.

### T71. The `latin1` label means windows-1252

- Tags: `encoding`
- Source behavior: `"latin-1"` is ISO-8859-1: every byte maps to the code point with the same value.
- Target behavior: WHATWG maps the labels `latin1`, `iso-8859-1` and `ascii` to windows-1252.
- Detect: Python `b"\x80".decode("latin-1")` is `'\x80'`; TS `new TextDecoder("latin1").decode(Uint8Array.of(0x80))` is `"€"`.
- Port rule: decode with `Buffer.from(b).toString("latin1")`; encode after checking every code point is at most 0xFF.

### T72. Byte slices are views

- Tags: `mutability`, `encoding`
- Source behavior: slicing `bytes` or `bytearray` copies.
- Target behavior: `Buffer.prototype.slice` and `subarray` share memory; `Uint8Array.prototype.slice` copies.
- Detect: Python `b = bytearray(b"ab"); c = b[0:1]; c[0] = 120` leaves `b == bytearray(b'ab')`; TS `const b = Buffer.from("ab"); const c = b.slice(0, 1); c[0] = 120;` makes `b.toString()` `"xb"`.
- Port rule: copy with `Uint8Array.prototype.slice.call(b, a, c)` or `Uint8Array.from(b.subarray(a, c))`; use `subarray` only where the source used `memoryview`.

### T73. `struct` uses native order, `DataView` uses big-endian

- Tags: `encoding`
- Source behavior: `struct` formats without a prefix use native byte order and alignment; `<` and `>` choose little and big endian without padding.
- Target behavior: `DataView` setters and getters default to big-endian.
- Detect: Python `struct.pack("I", 1)` is `b'\x01\x00\x00\x00'` on little-endian hosts; TS `new DataView(buf).setUint32(0, 1)` writes `[0, 0, 0, 1]`.
- Port rule: pass the endianness flag on every `DataView` call, and reproduce native alignment padding (`struct.calcsize("BI") == 8`, `"=BI"` is 5) where the format has no prefix.

### T74. `Buffer` hex decoding is lenient

- Tags: `encoding`, `error-model`
- Source behavior: `bytes.fromhex` raises `ValueError` on any non-hex character other than whitespace between bytes.
- Target behavior: `Buffer.from(s, "hex")` stops at the first invalid pair and returns what it decoded.
- Detect: Python `bytes.fromhex("zz")` raises `ValueError`; TS `Buffer.from("zz", "hex")` is an empty buffer.
- Port rule: validate with a regex before decoding and throw the mapped error.

### T75. base64 padding and strictness

- Tags: `encoding`
- Source behavior: `urlsafe_b64encode` keeps `=` padding; `b64decode` raises `binascii.Error` on bad padding.
- Target behavior: `Buffer` `"base64url"` omits padding, and decoding accepts missing padding.
- Detect: Python `base64.urlsafe_b64encode(b"a")` is `b'YQ=='`; TS `Buffer.from("a").toString("base64url")` is `"YQ"`.
- Port rule: add padding to match the source; validate length and alphabet before decoding when the source would raise.

### T76. `quote` versus `encodeURIComponent`

- Tags: `encoding`
- Source behavior: `urllib.parse.quote` keeps `/` by default and escapes `!`, `*`, `'`, `(`, `)`.
- Target behavior: `encodeURIComponent` escapes `/` and keeps `!`, `*`, `'`, `(`, `)`.
- Detect: Python `quote("a b/c!~*")` is `'a%20b/c%21~%2A'`; TS `encodeURIComponent("a b/c!~*")` is `"a%20b%2Fc!~*"`.
- Port rule: write `pyQuote(s, safe = "/")` on top of `encodeURIComponent` that re-escapes `!*'()` and un-escapes the `safe` characters.

### T77. `urlencode` versus `URLSearchParams`

- Tags: `encoding`
- Source behavior: `urlencode` uses `quote_plus`: space becomes `+`, `~` stays, `*` is escaped.
- Target behavior: `URLSearchParams` escapes `~` and keeps `*`.
- Detect: Python `urlencode({"a": "~* x"})` is `'a=~%2A+x'`; TS `new URLSearchParams({ a: "~* x" }).toString()` is `"a=%7E*+x"`.
- Port rule: build query strings with a helper on `pyQuote` and `+` for spaces.

### T78. PyYAML implements YAML 1.1

- Tags: `encoding`
- Source behavior: `yaml.safe_load` reads `yes`, `no`, `on`, `off` as booleans, `0777` as octal 511, and `1:30` as the base-60 number 90.
- Target behavior: `yaml` and `js-yaml` default to YAML 1.2: those stay strings or decimal `777`.
- Detect: Python `yaml.safe_load("a: yes")` is `{'a': True}`; TS `YAML.parse("a: yes")` is `{ a: "yes" }`.
- Port rule: use the `yaml` package with `{ version: "1.1" }`, which matched PyYAML on these cases (checked).

### T79. `Date` months start at 0

- Tags: `datetime`
- Source behavior: months are 1 to 12.
- Target behavior: `new Date(y, m, d)` and `getMonth()` use 0 to 11.
- Detect: Python `date(2024, 1, 15).strftime("%b")` is `'Jan'`; TS `new Date(2024, 1, 15).toLocaleString("en-US", { month: "short" })` is `"Feb"`.
- Port rule: convert at every `Date` boundary (`m - 1` in, `+ 1` out), or use Temporal, whose months are 1 to 12.

### T80. Invalid dates roll over

- Tags: `datetime`, `error-model`
- Source behavior: `date(2024, 2, 30)` and `date.fromisoformat("2024-02-30")` raise `ValueError`.
- Target behavior: `Date` rolls out-of-range fields into the next month, including in ISO strings.
- Detect: Python `date.fromisoformat("2024-02-30")` raises `ValueError`; TS `new Date("2024-02-30").toISOString()` is `"2024-03-01T00:00:00.000Z"`.
- Port rule: validate fields before building a `Date`, or use `Temporal.PlainDate.from` (which throws on `"2024-02-30"`; the object form clamps unless `{ overflow: "reject" }`).

### T81. Date-time strings without an offset parse as local time

- Tags: `datetime`
- Source behavior: `fromisoformat` without an offset returns a naive datetime with the same fields.
- Target behavior: `new Date("2024-01-01")` is UTC midnight but `new Date("2024-01-01T00:00")` is local midnight.
- Detect: Python `datetime.fromisoformat("2024-01-01T00:00").isoformat()` is `'2024-01-01T00:00:00'`; TS `new Date("2024-01-01T00:00").toISOString()` under `TZ=Europe/Warsaw` is `"2023-12-31T23:00:00.000Z"`.
- Port rule: parse with an explicit regex into fields (or Temporal `PlainDateTime.from`); never pass offset-less strings to `Date`.

### T82. `isoformat` versus `toISOString`

- Tags: `datetime`
- Source behavior: `isoformat()` writes `+00:00` for UTC, omits the fraction when microseconds are 0, writes 6 fraction digits otherwise, and writes no offset for naive values.
- Target behavior: `toISOString()` always writes milliseconds and `Z`.
- Detect: Python `datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()` is `'2024-01-01T00:00:00+00:00'`; TS `new Date(Date.UTC(2024, 0, 1)).toISOString()` is `"2024-01-01T00:00:00.000Z"`.
- Port rule: write a `pyIsoformat` helper that follows these rules.

### T83. Weekday numbering

- Tags: `datetime`
- Source behavior: `weekday()` is 0 for Monday; `isoweekday()` is 1 for Monday, 7 for Sunday.
- Target behavior: `getDay()` is 0 for Sunday.
- Detect: Python `date(2024, 1, 1).weekday()` is `0`; TS `new Date(2024, 0, 1).getDay()` is `1`.
- Port rule: `(d.getUTCDay() + 6) % 7` for `weekday()`; Temporal `dayOfWeek` is ISO (1 for Monday).

### T84. Aware arithmetic is wall-clock arithmetic

- Tags: `datetime`
- Source behavior: adding a `timedelta` to an aware datetime changes the wall-clock fields and keeps the zone, so across a DST change `+ timedelta(days=1)` (or `hours=24`) keeps the clock time.
- Target behavior: adding milliseconds to a `Date` adds elapsed time.
- Detect: Python `datetime(2024, 3, 30, 12, tzinfo=ZoneInfo("Europe/Warsaw")) + timedelta(days=1)` is `2024-03-31T12:00:00+02:00`; TS `new Date(d.getTime() + 86_400_000)` under `TZ=Europe/Warsaw` is 13:00 local time.
- Port rule: with Temporal, `zdt.toPlainDateTime().add(d).toZonedDateTime(zone)`; without it, do the arithmetic on wall-clock fields and re-attach the zone with Luxon (section 8).

### T85. Naive and aware datetimes do not mix

- Tags: `datetime`, `error-model`
- Source behavior: comparing or subtracting a naive and an aware datetime raises `TypeError`.
- Target behavior: every `Date` is an instant; comparisons always succeed.
- Detect: Python `datetime(2024, 1, 1) < datetime(2024, 1, 1, tzinfo=timezone.utc)` raises `TypeError`; TS `<` on two `Date` values returns a boolean.
- Port rule: give naive and aware values different TS types so mixing fails to compile; throw the mapped error at runtime boundaries where the source would raise.

### T86. `fromisoformat` accepts more on 3.11+

- Tags: `datetime`
- Source behavior: on 3.9 and 3.10, `fromisoformat` accepts only what `isoformat` writes; 3.11+ accepts most ISO 8601, including `Z` and `20240101`.
- Target behavior: `new Date(s)` accepts its own, different set of formats on every Node version.
- Detect: Python `datetime.fromisoformat("2024-01-01T00:00:00Z")` raises `ValueError` on 3.9 and returns an aware datetime on 3.12; TS `new Date("2024-01-01T00:00:00Z")` parses.
- Port rule: implement the accepted grammar of the Python version that recorded the fixtures, with a regex, and reject everything else.

### T87. Coroutines are lazy, async functions are eager

- Tags: `async`
- Source behavior: calling an `async def` returns a coroutine; its body runs only when awaited or wrapped in a task.
- Target behavior: calling an `async function` runs its body synchronously up to the first `await`.
- Detect: Python `c = g()` where `g` prints `start` prints nothing until `await c`; TS `const p = g()` prints `start` immediately.
- Port rule: when side-effect order matters, defer the call (`() => g()`) until the point where Python awaited or scheduled it.

### T88. `Promise.race` does not cancel

- Tags: `async`
- Source behavior: `asyncio.wait_for` cancels the inner task on timeout.
- Target behavior: `Promise.race` with a timer rejects but leaves the operation running.
- Detect: a 50 ms timeout around a 100 ms task that appends to `log`, checked after 200 ms: Python `asyncio.wait_for` leaves `log == []`; TS `Promise.race` leaves `log` as `["done"]`.
- Port rule: pass an `AbortSignal` (`AbortSignal.timeout(ms)`) into the operation and check it at every await point.

### T89. Unhandled rejections exit the process

- Tags: `async`, `error-model`
- Source behavior: a task that raises and is never awaited logs "Task exception was never retrieved"; the program continues.
- Target behavior: Node 15+ exits with code 1 on an unhandled rejection.
- Detect: Python `loop.create_task(boom())` without awaiting it exits with code 0; TS `Promise.reject(new Error("x"))` with no handler exits with code 1.
- Port rule: keep every promise you start and await it, or attach `.catch` that does what the source's handler did.

### T90. Text mode translates newlines

- Tags: `io`
- Source behavior: `open(p)` in text mode turns `\r\n` and `\r` into `\n` on read (unless `newline=""`), and on Windows writes `\n` as `\r\n`.
- Target behavior: `readFileSync(p, "utf8")` returns the bytes as text.
- Detect: for a file containing `a\r\nb`, Python `open(p).read()` is `'a\nb'`; TS `readFileSync(p, "utf8")` is `"a\r\nb"`.
- Port rule: apply `.replace(/\r\n?/g, "\n")` after reading in places where the source used text mode.

### T91. Python's default file encoding depends on the locale

- Tags: `io`, `encoding`, `locale`
- Source behavior: `open(p)` without `encoding=` uses the locale's encoding (cp1252 on many Windows systems, UTF-8 on most Linux and macOS setups).
- Target behavior: the port passes `"utf8"`.
- Detect: the bytes `c3 a9` read with cp1252 are `'Ã©'` in Python (`b"\xc3\xa9".decode("cp1252")`, checked); TS `readFileSync(p, "utf8")` gives `"é"`.
- Port rule: use UTF-8 and record the divergence when the source relied on the locale default; if fixtures came from a non-UTF-8 locale, re-record them under UTF-8.

### T92. `os.path.join` restarts at an absolute component

- Tags: `io`
- Source behavior: an absolute later argument discards everything before it.
- Target behavior: `path.join` concatenates and normalizes.
- Detect: Python `os.path.join("a", "/b")` is `'/b'`; TS `path.join("a", "/b")` is `"a/b"`.
- Port rule: check `path.isAbsolute` on later parts, or use `path.resolve` only when an absolute result is acceptable (it also prepends the cwd).

### T93. `basename` and `dirname` edge cases

- Tags: `io`
- Source behavior: `os.path.basename("a/")` is `''`; `os.path.dirname("a")` is `''`.
- Target behavior: `path.basename("a/")` is `"a"`; `path.dirname("a")` is `"."`.
- Detect: Python `os.path.basename("a/")` is `''`; TS `path.basename("a/")` is `"a"`.
- Port rule: use helpers that reproduce `os.path` (split on the last `/`), or note that pathlib behaves like Node here (`Path("a/").name == 'a'`).

### T94. `console.log` formats its first argument

- Tags: `io`
- Source behavior: `print(a, b)` writes `str(a)`, a space, `str(b)`, and a newline.
- Target behavior: `console.log` treats `%s`, `%d`, `%i`, `%f`, `%j`, `%o`, `%O`, `%c` in a first string argument as format specifiers, and prints objects with `util.inspect`.
- Detect: Python `print("a%sb", "X")` prints `a%sb X`; TS `console.log("a%sb", "X")` prints `aXb`.
- Port rule: write to `process.stdout` with `pyStr` and `" "` joins (section 10).

### T95. Missing environment variables

- Tags: `io`, `nullability`
- Source behavior: `os.environ["X"]` raises `KeyError` when unset.
- Target behavior: `process.env.X` is `undefined`.
- Detect: Python `os.environ["NOPE"]` raises `KeyError`; TS `process.env.NOPE` is `undefined`.
- Port rule: read through a helper that throws the mapped error when the source indexed directly, and returns the default when it used `.get`.

### T96. JS locale-aware APIs read the process locale

- Tags: `locale`, `float-format`
- Source behavior: `format(x, ",")`, `str.upper()`, `str.lower()` and `sorted` ignore the locale. `locale`-module functions and `%a`/`%b` in `strftime` use the C locale unless `setlocale` was called.
- Target behavior: `toLocaleString()`, `toLocaleUpperCase()`, `Intl.*` and `localeCompare` without an explicit locale use the process locale from `LANG`/`LC_ALL`.
- Detect: Python `format(1234.5, ",")` is `'1,234.5'`; TS `(1234.5).toLocaleString()` under `LC_ALL=de_DE.UTF-8` is `"1.234,5"` (checked).
- Port rule: format numbers by hand (`pyFormatFixed` plus separators). Where `Intl` is used anyway, pass an explicit locale and fraction digits and note that it rounds the shortest decimal form (section 6). Never use the `toLocale*` case functions for `upper` and `lower`.

### T97. `localeCompare` is not code point order

- Tags: `locale`, `ordering`
- Source behavior: string ordering is by code point: uppercase ASCII before lowercase.
- Target behavior: `localeCompare` uses ICU collation for the current locale.
- Detect: Python `sorted(["b", "a", "B", "A"])` is `['A', 'B', 'a', 'b']`; TS `["b", "a", "B", "A"].sort((x, y) => x.localeCompare(y))` is `["a", "A", "b", "B"]` (en-US).
- Port rule: use `compareCodePoints`; use `Intl.Collator` with an explicit locale only where the source used `locale.strxfrm` or a collation library.
