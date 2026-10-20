# PHP to TypeScript

| Field | Value |
| --- | --- |
| Source | PHP 7.4 to 8.4 |
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

Most PHP-to-TypeScript bugs come from six differences:

1. PHP arrays are ordered hash maps with value semantics. They serve as lists,
   maps and records at once, normalize integer-like keys, and are copied on
   assignment.
2. PHP strings are byte strings. Every non-`mb_` string function counts and
   slices bytes.
3. PHP compares and converts loosely in more places than JavaScript does
   (`==`, `switch`, `in_array`, `sort`, scalar parameter types, `+` on
   strings), with different rules.
4. PHP integers are 64-bit, and floats print with 14 significant digits.
5. Many PHP functions report failure with a warning and a `false` or `null`
   return value instead of throwing.
6. PHP state lives for one request; Node module state lives for the process.

Before porting, record two facts in the strategy:

- The exact PHP version the fixtures were recorded on. 8.0 changed
  string-to-number comparison, numeric string handling, sort stability,
  division by zero and many warnings into `Error`s. 8.1 changed
  `htmlspecialchars` defaults. 8.2 made case conversion ASCII-only.
- Whether the source runs under an error handler that converts warnings into
  `ErrorException` (Laravel, Symfony and many apps install one). With such a
  handler, the "returns false" paths in this file throw instead, and the
  fixtures show exceptions.

## 1. Type system mapping

| PHP | TypeScript | Notes |
| --- | --- | --- |
| `int` (64-bit) | `number` when values stay within 2^53, else `bigint` | T19, T20. |
| `float` | `number` | Formatting differs (section 6). |
| `string` | `string` for text, `Buffer` or `Uint8Array` for binary data | PHP strings are bytes (section 7). |
| `bool` | `boolean` | |
| `null` | `null` | Prefer `null` over `undefined` so JSON output matches. |
| `array` used as a list (keys 0 to n-1 in order) | `T[]` | Stays a list only until a key-preserving function runs (T3). |
| `array` used as a map | `Map<PhpKey, T>` with `phpKey()` on every access | T1, T2. A plain object reorders integer-like keys. |
| `array` used as a record with fixed keys | interface | Check `json_encode` output for empty arrays (T4). |
| `stdClass` | plain object | `json_decode($s)` without `true` returns `stdClass`. |
| `?T`, `T\|null` | `T \| null` | |
| union types (8.0) | union types | |
| `mixed` | `unknown` | |
| `callable`, `Closure` | function type | A PHP callable can also be a string (`'strlen'`) or `[$obj, 'method']`; resolve those at the call site. |
| `iterable`, `Generator` | `Iterable<T>`, `Generator<T>` | Keys matter (T52). |
| `resource` | handle objects (`FileHandle`, sockets) | |
| `enum` (8.1, backed) | `as const` object plus a union type, or a class with static instances | Port `from()` (throws `ValueError`), `tryFrom()` (returns `null`) and `cases()`. |
| `readonly` properties (8.1) | `readonly` | PHP enforces at runtime with `Error`; TypeScript only at compile time. |
| `static` return type | `this` type | |
| `never`, `void` | `never`, `void` | |
| traits | composition, or mixin functions | Port conflict resolution (`insteadof`, `as`) by hand. |
| `ArrayAccess`, `Countable`, `IteratorAggregate` | explicit `get`/`set`/`has` methods, `size` getter, `[Symbol.iterator]` | No operator overloading in TypeScript. |

PHP array key normalization, needed whenever a PHP array becomes a `Map`:

```ts
export type PhpKey = string | number;

// Mirrors PHP's array key cast. Decimal integer strings become ints;
// "01", "-0", " 1" and "1.5" stay strings. Keys between 2^53 and 2^63
// are ints in PHP but stay strings here: use bigint keys if they occur.
export function phpKey(k: string | number | boolean | null): PhpKey {
  if (typeof k === 'number') return Math.trunc(k);
  if (typeof k === 'boolean') return k ? 1 : 0;
  if (k === null) return '';
  if (/^(0|-?[1-9][0-9]*)$/.test(k)) {
    const n = Number(k);
    if (Number.isSafeInteger(n)) return n;
  }
  return k;
}
```

Rules that do not fit the table:

- Decide list or map per variable, from how the source writes and reads it,
  and record the decision in the idiom map. Mixed use (a list that later gets
  `unset`, or `array_filter`) needs a `Map` or an explicit reindex.
- PHP arrays are values, objects are handles. A TypeScript array or `Map` is a
  reference, so every place the source copied an array implicitly needs an
  explicit copy or proof that nobody mutates it (T8).
- Scalar type declarations coerce at runtime unless the file declares
  `strict_types=1` (T18). TypeScript types do not exist at runtime, so public
  entry points that receive untyped data must convert explicitly.

## 2. Error model

PHP has two throwable families under `Throwable`: `Exception` (application
errors) and `Error` (engine errors: `TypeError`, `ValueError`,
`ArgumentCountError`, `ArithmeticError`, `DivisionByZeroError`,
`UnhandledMatchError`). `catch (Exception $e)` does not catch `Error` (T39).
On top of that, many functions emit a warning and return `false` or `null`
(T40).

| Source | Target default | Notes |
| --- | --- | --- |
| `throw new FooException($msg, $code, $prev)` | `throw new FooException(msg, code, { cause: prev })` | Keep class names, `code` and the hierarchy. |
| `$e->getPrevious()` | `e.cause` | |
| `$e->getCode()` | a `code` property | `Error` has no `code` in the TS lib; declare it. |
| engine `Error` subclasses | a separate base class in the port, or plain JS `TypeError`/`RangeError` | Only matters where the source catches `Exception` broadly. |
| warning plus `false`/`null` return | the same return value | If the source ran under an `ErrorException` handler, throw instead. |
| `@` error suppression | nothing | |
| `trigger_error($m, E_USER_WARNING)` | a logger call or `process.emitWarning` | |
| `json_decode` with `JSON_THROW_ON_ERROR` | `JSON.parse` wrapped to throw the port's `JsonException` | Without the flag, `json_decode` returns `null` on error. |
| `exit()`, `die()` in library code | throw an error the entry point maps to the exit code | |
| PHP 8 `match` with no arm | throw an `UnhandledMatchError` equivalent | `match` compares with `===`. |

```php
try {
    $data = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
} catch (JsonException $e) {
    throw new PayloadException('bad payload', 400, $e);
}
```

```ts
export class PayloadException extends Error {
  readonly code: number;
  constructor(message: string, code = 0, previous?: unknown) {
    super(message, previous === undefined ? undefined : { cause: previous });
    this.name = 'PayloadException';
    this.code = code;
  }
}

let data: unknown;
try {
  data = JSON.parse(body); // see T5 for what assoc decoding changes
} catch (e) {
  throw new PayloadException('bad payload', 400, e);
}
```

## 3. Null and absence

| PHP | True when | TypeScript |
| --- | --- | --- |
| `isset($a['k'])` | key exists and value is not `null` | `m.get(k) != null` |
| `array_key_exists('k', $a)` | key exists, even with a `null` value | `m.has(k)` or `Object.hasOwn(o, k)` |
| `empty($x)` | unset or falsy | `!phpTruthy(x)` |
| `$a['k'] ?? $d` | same test as `isset` | `m.get(k) ?? d` |
| `$o?->m()` (8.0) | | `o?.m()` |
| `$x ??= $d` (7.4) | | `x ??= d` |

PHP falsiness differs from JavaScript: `"0"` and `[]` are falsy, `NAN` is
truthy (T14).

```ts
export function phpTruthy(v: unknown): boolean {
  if (v === '0') return false;
  if (typeof v === 'number' && Number.isNaN(v)) return true;
  if (Array.isArray(v)) return v.length > 0;
  if (v instanceof Map) return v.size > 0;
  return Boolean(v); // null, false, 0, 0.0 and '' are falsy in both
}
```

- Reading a missing key or undefined variable gives a warning and `null`.
  `Map.get` gives `undefined`; add `?? null` where the value flows into
  output.
- Passing `null` to a non-nullable parameter of a built-in function is
  deprecated since 8.1 but still coerces (`strlen(null)` is `0`). The port
  must coalesce (`(s ?? '').length`) instead of throwing.
- Accessing an uninitialized typed property throws `Error` ("must not be
  accessed before initialization"). TypeScript reads `undefined`.
- Functions that return `false` as "not found" (`strpos`, `array_search`,
  `file_get_contents`, `fgets`) need the sentinel preserved or every caller
  ported together (T15).

## 4. Concurrency and async

PHP code is synchronous, shared-nothing, and normally runs one request per
process lifetime (PHP-FPM, mod_php) or per CLI run.

- Keep pure functions synchronous. Only the I/O boundary may become `async`,
  and only when Node has no sync API for it (HTTP has none). Record each new
  `async` public function as a contract change.
- File I/O can stay synchronous (`readFileSync`) when the library contract is
  synchronous and the target is a CLI or a batch tool.
- Static properties, function `static` variables, singletons and globals
  reset with every PHP request. In a long-running Node server they persist
  for the whole process (T46).
- `__destruct` runs as soon as the last reference goes away (end of scope,
  `unset`, reassignment). JavaScript has no deterministic destructor (T47).
  Port to explicit `close()` methods, or `using` declarations (TypeScript
  5.2+, with `esnext.disposable` in `lib` and `Symbol.dispose` at runtime,
  which current Node 20 releases provide).
- `register_shutdown_function` maps to `process.on('exit')` for sync work
  only.
- `sleep`/`usleep` become `await setTimeout(ms)` from `node:timers/promises`
  (which makes the caller async) or `Atomics.wait` on a `SharedArrayBuffer`
  for a blocking sleep in CLI code.
- Fibers (8.1), ReactPHP, Amp and Swoole code maps to promises and
  `async`/`await`. Check each library's resolution timing against
  fixtures; do not assume it matches native promises.
- `pcntl_fork` and `pcntl_signal` map to `child_process` and
  `process.on('SIGINT')`.

## 5. Iteration, generators, laziness

- `foreach ($arr as $v)` iterates a snapshot of the array. Appending inside
  the loop does not extend it; in JavaScript `for...of` does (T9).
- `foreach ($arr as &$v)` writes through, and the reference stays alive
  after the loop (T10).
- Key handling of array functions decides whether the result is still a
  list:

| Function | Keys of the result |
| --- | --- |
| `array_filter` | preserved, so gaps appear |
| `array_map` with one array | preserved |
| `array_map` with several arrays | renumbered 0 to n-1 |
| `array_unique` | key of the first occurrence preserved |
| `array_slice`, `array_reverse` | integer keys renumbered unless `preserve_keys` is true; string keys kept |
| `array_splice` | integer keys renumbered |
| `array_merge` | integer keys renumbered and appended; string keys overwritten by later arrays |
| `$a + $b` | left keys win; nothing renumbered |
| `sort`, `rsort`, `usort`, `shuffle` | renumbered |
| `asort`, `arsort`, `uasort`, `ksort`, `krsort`, `uksort` | preserved |
| `array_values` | renumbered |

```php
$active = array_values(array_filter($users, fn($u) => $u->active));
echo json_encode(array_filter([1, 0, 2])); // {"0":1,"2":2}
```

```ts
const active = users.filter((u) => u.active);
// To reproduce PHP's key-preserving result exactly:
const kept = new Map([1, 0, 2].map((v, i) => [i, v] as const).filter(([, v]) => phpTruthy(v)));
```

- `range($a, $b)` counts down when `$a > $b`, and `range('a', 'e')` produces
  letters (T51).
- Generators: `yield $k => $v` produces keys. A JS port yields `[k, v]`
  tuples where keys matter. `yield from` maps to `yield*`, but
  `iterator_to_array` keeps keys and can overwrite values (T52). Generator
  return values (`getReturn()`) map to the `value` of the final
  `{ done: true }` result.
- `array_walk($arr, fn(&$v) => ...)` mutates in place; `array_map` does not.
- `list('a' => $x, 'b' => $y) = $arr` and `['a' => $x] = $arr` map to object
  or `Map` destructuring by key.

## 6. Numeric semantics

- `int` is 64-bit on all common platforms. Arithmetic that overflows turns
  into a `float` silently: `var_export(PHP_INT_MAX + 1)` prints
  `9.2233720368547758E+18`.
  JavaScript numbers lose integer precision above 2^53 (T19).
- Bitwise operators work on 64-bit integers; JavaScript `&`, `|`, `^`, `<<`
  and `>>` work on signed 32-bit (T20). Port hash and checksum code with
  `bigint` or `>>> 0` and test it with values above 2^31.
- `/` returns an `int` when both operands are ints and the division is exact
  (`6 / 2` is `int(3)`), else a `float`. `is_int`, `===` and `var_export`
  can see the difference: `10 / 4 * 2 === 5` is `false` in PHP because the
  left side is `float(5)`.
- `intdiv($a, $b)` truncates toward zero: `Math.trunc(a / b)`, exact only
  below 2^53. `intdiv(PHP_INT_MIN, -1)` throws `ArithmeticError`.
- `%` converts both operands to `int` first and takes the sign of the
  dividend (T21). `fmod` keeps floats and matches JavaScript `%`.
- Division or modulo by zero throws `DivisionByZeroError` in PHP 8. PHP 7.4
  gave a warning and `INF`/`false` for `/` (T22).
- Numeric strings: `"10" + "5"` is `15` (T16). Leading-numeric strings
  (`"10 apples"`) give a warning and use the number; non-numeric strings
  throw `TypeError` in PHP 8 (T17).
- `intval("1e3")` and `(int)"1e3"` are `1000` (PHP 7.1+); `intval("0x1A")` is
  `0`; `intval(" 12")` is `12`; out-of-range numeric strings saturate at
  `PHP_INT_MAX` (T53).
- Float to string (echo, string interpolation, `(string)`, `strval`,
  `implode`, `sprintf('%s')`) uses `precision=14`: `0.1 + 0.2` prints as
  `0.3`, `1/3` as `0.33333333333333`, `1e14` as `1.0E+14`, `0.00001` as
  `1.0E-5`. Exponent form starts at 1e14 and below 1e-4. `var_export`,
  `json_encode` and `serialize` use `serialize_precision=-1` (shortest
  round-trip, like JavaScript) (T23). Since 8.0, float to string ignores the
  locale.

```ts
// PHP float-to-string with the default precision=14 (php_gcvt rules).
// Matches PHP except on exact ties at the 15th significant digit, which PHP
// rounds half to even and toExponential rounds up: 123456789012345.0 prints
// 1.2345678901234E+14 in PHP and 1.2345678901235E+14 here.
export function phpFloatToString(x: number): string {
  if (Number.isNaN(x)) return 'NAN';
  if (!Number.isFinite(x)) return x > 0 ? 'INF' : '-INF';
  if (x === 0) return Object.is(x, -0) ? '-0' : '0';
  const sign = x < 0 ? '-' : '';
  const [m, e] = Math.abs(x).toExponential(13).split('e');
  const digits = m!.replace('.', '').replace(/0+$/, '');
  const decpt = Number(e) + 1; // digits before the decimal point
  if (decpt < -3 || decpt > 14) {
    const mant = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : `${digits}.0`;
    const exp = decpt - 1;
    return `${sign}${mant}E${exp < 0 ? '-' : '+'}${Math.abs(exp)}`;
  }
  if (decpt <= 0) return `${sign}0.${'0'.repeat(-decpt)}${digits}`;
  if (digits.length <= decpt) return sign + digits + '0'.repeat(decpt - digits.length);
  return `${sign}${digits.slice(0, decpt)}.${digits.slice(decpt)}`;
}
```

- `round()` rounds half away from zero and corrects for binary
  representation error: `round(1.005, 2)` is `1.01`, `round(-2.5)` is `-3`.
  `number_format` uses the same rounding. JavaScript `toFixed` and
  `Math.round` do not (T24).
- `sprintf('%.2f')` rounds the exact binary value with ties to even:
  `sprintf('%.0f', 2.5)` is `'2'`, `sprintf('%.2f', 1.005)` is `'1.00'`
  (T25). `%f` uses the current locale's decimal point; `%F` does not.
- `floor` and `ceil` return `float`. `max('apple', 10)` compares across
  types with PHP 8 rules (`'apple'` wins in 8.x, `10` in 7.4).
- bcmath and GMP map to `bigint` for integers and decimal.js or big.js for
  decimals.
- `mt_rand` and `rand` with `mt_srand($seed)` produce a reproducible
  sequence. `Math.random` cannot be seeded; if fixtures depend on seeded
  output, port PHP's Mt19937 and its range scaling.

## 7. Strings, bytes, unicode, encodings

PHP strings are byte arrays; `default_charset` is UTF-8, but only `mb_*`,
`iconv_*`, `/u` regexes and a few others interpret the bytes as UTF-8.

| PHP | Counts | TypeScript for the same result |
| --- | --- | --- |
| `strlen($s)` | bytes | `Buffer.byteLength(s, 'utf8')` |
| `mb_strlen($s)` | code points | `[...s].length` (not `s.length`, which counts UTF-16 units) |
| `substr($s, $i, $n)` | bytes; can cut a UTF-8 sequence | slice a `Buffer`, or `s.slice` if inputs are ASCII |
| `mb_substr($s, $i, $n)` | code points | `[...s].slice(i, i + n).join('')` |
| `strrev`, `str_split`, `str_pad`, `wordwrap`, `chunk_split` | bytes | port on code points only if the fixtures show text-safe results |
| `strtoupper`, `strtolower`, `ucfirst`, `lcfirst`, `ucwords` | ASCII only (8.2+) | ASCII-only helpers (T28) |
| `mb_strtoupper`, `mb_strtolower` | Unicode | `toUpperCase`, `toLowerCase` |
| `strcmp`, `strcasecmp` | byte order | compare `Buffer`s, or `<` on strings (UTF-16 order differs from UTF-8 byte order only for astral versus U+E000 to U+FFFF characters) |
| `trim`, `rtrim`, `ltrim` | the bytes `" \t\n\r\0\x0B"` by default | a regex with the same set (T29) |

- `explode(',', 'a,b,c', 2)` is `['a', 'b,c']`: the last element holds the
  rest. JavaScript `'a,b,c'.split(',', 2)` truncates to `['a', 'b']`.
  Negative limits drop elements from the end.
- `strtr($s, ['a' => 'b', 'b' => 'a'])` replaces in one pass, longest key
  first, never re-replacing output. Chained `replaceAll` calls do re-replace:
  `strtr('ab', [...])` is `'ba'`, chained replaces give `'aa'`.
- `str_replace` with arrays replaces sequentially, left to right, and does
  re-replace. That one maps to chained `replaceAll`.
- `str_contains($s, '')` is `true` (8.0). `substr('abc', 5)` is `''` in 8.0+.
- `implode` converts `true` to `'1'`, `false` and `null` to `''`, floats with
  `precision=14`.
- Heredoc and nowdoc (`<<<EOT`) strip the closing marker's indentation from
  every line since 7.3. A template literal keeps it.
- Interpolation: `"$a[key]"` reads the key `key` (no quotes);
  `"{$a['key']}"` and `"{$obj->x}"` are the explicit forms.
- `iconv` and `mb_convert_encoding`: `TextDecoder` decodes many legacy
  encodings (windows-1252, ISO-8859-x, Shift_JIS) with Node's full ICU, but
  cannot encode to them; use iconv-lite for encoding.
- `md5`, `sha1`, `hash`, `crc32`, `base64_encode` hash or encode the bytes of
  the PHP string. For UTF-8 text, `createHash('md5').update(s, 'utf8')`
  matches. For binary strings built with `pack` or `chr`, port the data as a
  `Buffer`. `crc32()` returns an unsigned value on 64-bit PHP;
  `zlib.crc32` (Node 20.15+, 22.2+) returns the same unsigned number.
- `pack`/`unpack` map to `Buffer` read and write methods
  (`writeUInt32BE`, `readInt16LE`).
- `levenshtein`, `similar_text`, `soundex` and `metaphone` are byte-based and
  ASCII-oriented; npm equivalents work on UTF-16 strings, so non-ASCII
  results differ.

## 8. Dates, times, timezones

- PHP uses the `date.timezone` ini setting, defaulting to UTC when unset. It
  ignores the `TZ` environment variable. Node uses `TZ` or the OS zone (T41).
  Read the source's ini, then make the zone explicit in the port.
- `DateTime` is mutable: `modify`, `add`, `sub`, `setDate` change the object
  and return it (T42). `DateTimeImmutable` returns new objects. Carbon has
  both (`Carbon` and `CarbonImmutable`).
- `modify('+1 month')` and Carbon `addMonth()` overflow into the next month
  (January 31 plus one month is March 2 in 2024); date-fns, Luxon and Day.js
  clamp to the month end (T43). Carbon's `addMonthNoOverflow()` clamps.
- `DateTime` keeps microseconds (format `u`); JavaScript `Date` keeps
  milliseconds.
- `time()` is seconds; `Date.now()` is milliseconds.
- `strtotime` and `new DateTime($s)` accept relative formats ("next monday",
  "last day of next month", "+2 weekdays"). There is no JavaScript
  equivalent. Port only the formats the source passes, each with a fixture.
  `strtotime` returns `false` on failure.
- `DateTime::diff()` returns a `DateInterval` with `y`, `m`, `d`, `h`, `i`,
  `s`, `days` and `invert`. date-fns `intervalToDuration` gives y/m/d parts,
  `differenceInCalendarDays` gives `days`; verify month-end cases.

`date()` and `DateTime::format()` characters versus date-fns tokens:

| PHP | date-fns | Meaning |
| --- | --- | --- |
| `Y` / `y` | `yyyy` / `yy` | year |
| `m` / `n` | `MM` / `M` | month with / without leading zero |
| `d` / `j` | `dd` / `d` | day of month with / without leading zero |
| `H` / `G` | `HH` / `H` | hour 0-23 with / without leading zero |
| `h` / `g` | `hh` / `h` | hour 1-12 with / without leading zero |
| `i` / `s` | `mm` / `ss` | minutes / seconds |
| `v` | `SSS` | milliseconds |
| `u` | none | microseconds |
| `A` / `a` | `a` / `aaa` | `AM` / `am` |
| `D` / `l` | `EEE` / `EEEE` | weekday name |
| `M` / `F` | `MMM` / `MMMM` | month name |
| `N` | `i` | ISO weekday 1-7 |
| `w` | `getDay()` | weekday 0 (Sunday) to 6 |
| `S` with `j` | `do` | `1st`, `2nd` |
| `W` / `o` | `II` / `RRRR` | ISO week / ISO week-numbering year |
| `P` / `O` | `xxx` / `xx` | offset `+02:00` / `+0200` |
| `U` | `t` | Unix seconds |
| `c` | `yyyy-MM-dd'T'HH:mm:ssxxx` | ISO 8601 |
| `\T` (escape) | `'T'` | literal text |

## 9. Regex dialect

`preg_*` uses PCRE2. JavaScript `RegExp` is close but differs in anchors,
Unicode handling, offsets and several constructs.

| PCRE | JavaScript | Notes |
| --- | --- | --- |
| delimiters `/.../`, `#...#`, `~...~`, `{...}` | regex literal or `new RegExp(src, flags)` | Unescape delimiter escapes such as `\#`. |
| `i`, `m`, `s` | same | |
| `x` | remove whitespace and `#` comments by hand | |
| `u` | `u` | In PHP also makes `\w`, `\d`, `\b` Unicode-aware (T34); offsets stay in bytes (T35). |
| `D` | default `$` | |
| `U` (ungreedy) | swap greedy and lazy quantifiers | |
| `A` (anchored) | `^`, or the `y` flag | |
| `$` without `D` or `m` | `(?=\n?$)` | T33. |
| `\A`, `\z` | `^`, `$` without `m` | |
| `\Z` | `(?=\n?$)` | |
| `\h` | `[\t   ᠎ -   　]` | |
| `\R` | `(?:\r\n\|[\n\v\f\r\x85  ])` | |
| `\K` | lookbehind, or capture the prefix and rebuild | |
| `(?P<n>...)`, `(?'n'...)` | `(?<n>...)` | |
| `(?P=n)`, `\g{1}`, `\k{n}` | `\k<n>`, `\1` | |
| `a++`, `(?>...)` | `(?=(a+))\1` | Atomic group emulation. |
| `(?R)`, `(?1)` | none | Rewrite as code. |
| `(?i)` at pattern start | the `i` flag | Mid-pattern inline flags need a rewrite on Node 20. |
| `[[:alpha:]]`, `[[:digit:]]` | `[A-Za-z]`, `[0-9]`, or `\p{L}` with `u` | |
| `\Q...\E` | escape the literal text | |
| `\e`, `\a` | `\x1B`, `\x07` | |

Replacement strings and results:

- `preg_replace` replaces every match unless `$limit` is set (T36).
- Replacement references `$1`, `\1`, `${1}` and `$0` map to `$1`, `$1`, `$1`
  and `$&`. In JavaScript, `\1` in a replacement is literal text.
- `preg_replace_callback` passes one array `$m`; JavaScript passes
  `(match, p1, p2, ..., offset, string, groups)`. Build `$m` from the
  arguments to keep the callback body unchanged.
- `preg_match` returns `1`, `0`, or `false` on error, and fills `$m` by
  reference. Unmatched groups in the middle are `''` and trailing unmatched
  groups are missing, unless `PREG_UNMATCHED_AS_NULL` is set. JavaScript
  gives `undefined` (T38).
- `preg_match_all` defaults to `PREG_PATTERN_ORDER`: `$m[0]` is all full
  matches, `$m[1]` all first groups. `matchAll` yields one entry per match.
  Transpose to keep the shape.
- `preg_split` includes captured delimiters only with
  `PREG_SPLIT_DELIM_CAPTURE` (T37). `PREG_SPLIT_NO_EMPTY` maps to
  `.filter((s) => s !== '')`.
- PCRE stops at `pcre.backtrack_limit` (default 1000000) and returns
  `false`/`null`. JavaScript has no limit and can hang on catastrophic
  patterns. Keep the source's failure handling and add a timeout or a
  pattern rewrite.

## 10. I/O, paths, process, environment

| PHP | Node | Notes |
| --- | --- | --- |
| `__DIR__`, `__FILE__` | `import.meta.dirname`, `import.meta.filename` | Node 20.11+. |
| `file_get_contents($path)` | `readFileSync(path, 'utf8')` or a `Buffer` | PHP returns `false` with a warning on failure; Node throws. PHP also fetches URLs through stream wrappers. |
| `file_put_contents($p, $d, FILE_APPEND)` | `writeFileSync(p, d, { flag: 'a' })` | |
| `fopen`/`fgets`/`fclose` | `readline` over a stream, or `FileHandle` | `fgets` keeps the newline. |
| `realpath($p)` | `fs.realpathSync(p)` | PHP returns `false` for missing paths; Node throws. |
| `basename`, `dirname`, `pathinfo` | `path.basename`, `path.dirname`, `path.parse` | `pathinfo` returns no `extension` key when there is none. |
| `sys_get_temp_dir`, `tempnam` | `os.tmpdir()`, `fs.mkdtempSync` | |
| `getenv('X')` | `process.env.X` | `getenv` returns `false` for unset variables. |
| `$_SERVER['argv']` | `process.argv.slice(1)` | PHP's `argv[0]` is the script. |
| `exec`, `shell_exec`, `proc_open` | `child_process.execFileSync`, `spawn` | Pass arguments as an array instead of porting `escapeshellarg`. |
| `echo`, `printf`, output buffering | return strings or write to a stream | Libraries that echo need an explicit output sink. |
| `PHP_EOL` | `'\n'` on Linux and macOS, `os.EOL` in general | |
| `http_build_query` | `URLSearchParams` for flat data, `qs` for nested arrays | Both encode a space as `+`. |
| `parse_str`, `$_GET` | `qs.parse` plus key rewriting | T32. |
| `urlencode` / `rawurlencode` | `URLSearchParams` / a custom RFC 3986 encoder | T31. |
| `parse_url` | `new URL(s)` | `new URL` throws on relative URLs; `parse_url` returns the parts it finds. |

## 11. Module layout, packaging, naming, visibility

- PSR-4 maps namespaces to directories. Map each namespace to a directory and
  each class to a module: `App\Http\Client` in `src/Http/Client.php` becomes
  `src/http/client.ts` exporting `Client`. Do not use TypeScript
  `namespace`.
- `include` and `require` execute a file at the point of the statement, in
  the caller's scope. ES `import` declarations are hoisted and evaluated
  before the importing module's body (T48). Conditional or late includes
  become dynamic `import()` (async) or explicit init functions.
- Config files that `return [...]` become modules with a default export.
- Composer `autoload.files` (eagerly loaded helper functions) become ordinary
  imports at each use site.
- Function names, class names and method names are case-insensitive in PHP
  (T49). Normalize to the declared casing and fix any dynamic lookups.
- Visibility: `public`, `protected`, `private` map to the TypeScript
  modifiers, which are compile-time only. Use `#private` only when runtime
  privacy matters and nothing serializes or reflects over the object.
  `final` has no TypeScript equivalent; document it.
- Class constants (`const TABLE = 'x'`) become `static readonly`.
- Late static binding: `static::` resolves to the called class, `self::` to
  the defining class, `parent::` to the parent.

```php
class Model {
    const TABLE = '';
    public static function create(array $attrs): static {
        $m = new static();
        $m->fill($attrs);
        return $m;
    }
    public static function table(): string { return static::TABLE; }
}
class User extends Model { const TABLE = 'users'; }
```

```ts
class Model {
  static TABLE = '';
  static create<T extends Model>(this: new () => T, attrs: Record<string, unknown>): T {
    const m = new this(); // `new static()`
    m.fill(attrs);
    return m;
  }
  static table(this: { TABLE: string }): string {
    return this.TABLE; // `static::TABLE`; use `Model.TABLE` for `self::TABLE`
  }
  fill(attrs: Record<string, unknown>): void { /* ... */ }
}
class User extends Model {
  static override TABLE = 'users';
}
```

In instance methods, `static::X` is `(this.constructor as typeof Model).X`.
Static properties need extra care (T45).

Magic methods:

| PHP | TypeScript | Notes |
| --- | --- | --- |
| `__get`, `__set`, `__isset`, `__unset` | `get`/`set` accessors for known names; a `Proxy` (`get`, `set`, `has`, `deleteProperty`) for dynamic names | PHP calls them only for inaccessible or undeclared properties; a Proxy trap runs for every access, including methods. |
| `__call`, `__callStatic` | explicit methods; a `Proxy` as a last resort | |
| `__toString` | `toString()` | PHP also calls it for `==` against strings, `in_array`, `sort` and string functions. |
| `__invoke` | a function with properties (`Object.assign(fn, props)`) | |
| `__clone` | an explicit `clone()` method | PHP `clone` copies array properties by value and object properties by handle. |
| `__destruct` | `close()` or `[Symbol.dispose]()` | T47. |
| `__serialize`, `__sleep`, `__wakeup`, `JsonSerializable` | `toJSON()` and explicit factories | |
| `__debugInfo` | `[util.inspect.custom]` | |

## 12. Standard library equivalence

| Source | Target | Notes |
| --- | --- | --- |
| `count($a)` | `a.length`, `m.size` | `count` on a non-countable throws `TypeError` in 8.0. |
| `in_array($x, $a)` | `a.some((v) => phpLooseEquals(v, x))` | Strict only with `in_array($x, $a, true)` (T13). |
| `array_search($x, $a)` | index or key lookup | Returns `false`, not `-1` (T15). |
| `array_keys`, `array_values` | `[...m.keys()]`, `[...m.values()]` | Keys are ints or strings (T1). |
| `array_merge`, `+` | spread or a merge helper | Section 5 key table. |
| `array_slice`, `array_splice` | `slice`, `splice` | Key renumbering rules (section 5). |
| `array_unique` | `Map` keyed by `String(v)` | Default comparison is string-based (`"1"` and `1` are duplicates; `"01"` is not); keeps first keys. |
| `array_column`, `array_combine`, `array_flip`, `array_fill_keys` | `map`, `Object.fromEntries`, `new Map(...)` | `array_flip` normalizes the new keys (T1). |
| `array_chunk`, `array_fill`, `array_pad` | small helpers | |
| `usort`, `uasort`, `uksort` | `sort` with a comparator | PHP 8 sort is stable, like JavaScript. A bool-returning comparator still sorts in PHP 8 (deprecated); in JavaScript it does not. |
| `sort`, `asort`, `ksort` | `sort` with a PHP-compatible comparator | T44. |
| `implode`, `explode` | `join`, `split` with a limit helper | Section 7. |
| `str_contains`, `str_starts_with`, `str_ends_with` | `includes`, `startsWith`, `endsWith` | |
| `strpos`, `stripos` | `indexOf` returning `false` on miss | Byte offsets for non-ASCII text. |
| `str_replace`, `str_ireplace` | `replaceAll`, regex with `gi` | Arrays replace sequentially. |
| `strtr` | one-pass replacer | Section 7. |
| `sprintf`, `printf`, `vsprintf` | a sprintf port with PHP rules | Padding with `%'05d`, `%u` on negatives gives the 64-bit unsigned value, `%e` prints `1.234568e+4`. |
| `number_format` | `Intl.NumberFormat('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })` with custom separators | Matched PHP on `1.005`, `1.45` and `2.5` in testing; keep a fixture (T24). |
| `json_encode`, `json_decode` | `JSON.stringify`, `JSON.parse` plus adapters | T3 to T7. |
| `serialize`, `unserialize` | a port of the format, or JSON if the data never leaves the process | |
| `var_export`, `print_r`, `var_dump` | custom formatters | Only if their output is in fixtures. |
| `htmlspecialchars` | a small escaper with the same flags | T30. |
| `filter_var` | explicit parsers per filter | Port the accepted grammar of each filter used, with fixtures. |
| `password_hash`, `password_verify` | bcrypt or bcryptjs | PHP writes `$2y$` hashes; `$2y$` and `$2b$` are the same algorithm, so rewrite the prefix if the library rejects `$2y$`. |
| `random_int`, `random_bytes` | `crypto.randomInt`, `crypto.randomBytes` | |
| `uniqid` | `crypto.randomUUID()` if only uniqueness matters | `uniqid` is time-based hex; keep the format only if stored. |
| `hash_hmac` | `crypto.createHmac` | |
| `base64_encode`, `bin2hex` | `Buffer.from(...).toString('base64' or 'hex')` | |
| `date`, `strtotime`, `DateTime` | date-fns or Luxon | Section 8. |
| `file_get_contents`, `file_put_contents` | `node:fs` | Section 10. |
| `glob`, `scandir` | `fs.readdirSync`, a glob library | `scandir` sorts alphabetically and includes `.` and `..`. |
| `call_user_func`, `call_user_func_array` | direct calls | Resolve string callables explicitly (T49). |
| `compact`, `extract` | object literals and destructuring | |
| `is_numeric` | a regex for PHP numeric strings | Accepts leading whitespace, trailing whitespace (8.0+), exponents; rejects hex. |

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |
| guzzlehttp/guzzle | HTTP client | global `fetch`, undici, ky, got | replace | Guzzle throws on 4xx/5xx by default (`http_errors`); `fetch` does not. Middleware, retries and cookie jars need explicit equivalents. |
| symfony/http-client | HTTP client | global `fetch`, undici | replace | Lazy responses: errors surface when the body or status is read. |
| monolog/monolog | logging | pino, winston | replace | If fixtures record log lines, write a formatter for Monolog's line format. |
| psr/log | logger interface | a local `Logger` interface | replace | |
| symfony/console | CLI framework | commander, yargs, clipanion, oclif | replace | Help output, `<info>` style tags and exit codes are often in fixtures. |
| symfony/process | subprocesses | `node:child_process`, execa | replace | |
| symfony/yaml | YAML | yaml, js-yaml | replace | Symfony parses unquoted dates to Unix timestamps by default (`PARSE_DATETIME` gives objects); js-yaml returns `Date`; yaml keeps strings. `!php/const` and `!php/object` tags have no equivalent. |
| symfony/event-dispatcher | events | `EventEmitter` or a typed dispatcher | replace | Port listener priorities and `stopPropagation`. |
| nesbot/carbon | dates | Luxon, date-fns, Day.js | replace | Carbon is mutable and overflows months (T42, T43). `diffForHumans` wording differs from date-fns `formatDistance`. |
| ramsey/uuid | UUIDs | `crypto.randomUUID()` for v4, uuid for v1/v3/v5/v6/v7 | replace | |
| vlucas/phpdotenv | `.env` loading | `process.loadEnvFile` (Node 20.12+), `node --env-file` (20.6+), dotenv plus dotenv-expand | replace | phpdotenv expands `${VAR}`; the usual `Dotenv::createImmutable` setup does not override variables already set. |
| league/flysystem | filesystem abstraction | `node:fs/promises`, @aws-sdk/client-s3, flydrive | replace | |
| twig/twig | templates | nunjucks, twing, twig.js | decide per template set | nunjucks syntax is close but filters, tests and autoescape defaults differ. Compare rendered output byte for byte. |
| phpmailer/phpmailer | email | nodemailer | replace | |
| firebase/php-jwt | JWT | jose, jsonwebtoken | replace | `JWT::$leeway` maps to a clock tolerance option. |
| respect/validation | validation | zod, valibot, ajv | replace | Error messages differ; port them if fixtures record them. |
| egulias/email-validator | email validation | validator (`isEmail`), email-addresses | replace, fixture the edges | No exact RFC 5322 equivalent; acceptance differs on quoted local parts, comments and IP literals. |
| doctrine/dbal | database access | kysely, knex, plus pg or mysql2 | replace | Type conversion differs: pg returns BIGINT as strings, mysql2 returns DECIMAL as strings by default. |
| doctrine/orm | ORM | MikroORM (data mapper, unit of work), TypeORM | replace | MikroORM is the closest model to Doctrine. |
| illuminate/collections | collection helpers | native arrays and `Map`, collect.js | replace | collect.js mirrors the Laravel API but follows JavaScript key semantics. |
| league/commonmark | Markdown | commonmark (commonmark.js), markdown-it, micromark | replace | HTML output whitespace and extensions differ; compare rendered HTML. |
| ezyang/htmlpurifier | HTML sanitizing | DOMPurify with jsdom, sanitize-html | replace | Different allowlists and output; review security behavior, not just fixtures. |
| intervention/image | image processing | sharp, jimp | replace | Encoders differ: compare decoded pixels with a tolerance, not file bytes. |
| league/csv | CSV | csv-parse and csv-stringify, papaparse | replace | PHP's `fputcsv` default escape character `\` produces non-RFC 4180 output; check quoting fixtures. |
| brick/math | big numbers | `bigint` for `BigInteger`, decimal.js or big.js for `BigDecimal` | replace | Map `RoundingMode` names; decimal.js has no `UNNECESSARY` mode, so check exactness by hand. |
| phpunit/phpunit | tests | vitest, `node:test` | replace | Section 14. |
| mockery/mockery | mocks | vitest `vi.fn`/`vi.spyOn`, sinon | replace | |

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | PHPUnit, Pest, Codeception | vitest, or `node:test` |
| Assertions and fixtures | PHPUnit assertions, data providers, Mockery, Prophecy, vfsStream | vitest `expect`, `test.each`, `vi.fn`, `vi.spyOn`, temp directories or memfs |
| Lint | PHPStan, Psalm, PHP_CodeSniffer, PHPMD | eslint 9 with typescript-eslint |
| Format | PHP-CS-Fixer, phpcbf | prettier |
| Type check | PHPStan or Psalm levels | `tsc --noEmit` with `strict` |
| Coverage | Xdebug, PCOV | vitest coverage (v8) or c8 |

- `assertEquals` compares loosely (`'1'` equals `1`) and ignores key order in
  associative arrays; `assertSame` is strict and order-sensitive. When
  porting reference tests, `toEqual` is stricter than `assertEquals` on
  types and as lenient on object key order. Do not "fix" a failing ported
  test by loosening it without checking which PHP assertion it came from.
- Data providers map to `test.each`; keep provider names as test titles so
  the mapping to `.porter/` reference tests stays traceable.
- Mutation testing: Infection maps to StrykerJS.

## 15. Known traps

### T1. Integer-like string keys become integers

- Tags: `numeric`
- Source behavior: `$a["1"] = x` stores the key as `int(1)`; `"01"`, `"1.5"` and `" 1"` stay strings; `true` becomes `1` and `null` becomes `""`.
- Target behavior: JavaScript object keys are always strings, and a `Map` keeps `"1"` and `1` as different keys.
- Detect: `json_encode(array_keys(["1" => "a", "01" => "b"]))` is `[1,"01"]`; `JSON.stringify(Object.keys({ "1": "a", "01": "b" }))` is `["1","01"]`.
- Port rule: run every key through `phpKey()` (section 1) on write and read, and keep the key's type when it flows into output.

### T2. Arrays keep insertion order for integer keys; JS objects do not

- Tags: `ordering`
- Source behavior: PHP arrays iterate in insertion order whatever the key type.
- Target behavior: JavaScript objects list integer-like keys first, ascending, and `JSON.stringify` follows that order.
- Detect: `json_encode(json_decode('{"b":1,"1":2}', true))` is `{"b":1,"1":2}`; `JSON.stringify(JSON.parse('{"b":1,"1":2}'))` is `{"1":2,"b":1}`.
- Port rule: use `Map` for PHP arrays with mixed or integer keys, and serialize maps with a writer that walks entries in order.

### T3. `json_encode` picks list or object from the keys

- Tags: `encoding`
- Source behavior: an array encodes as a JSON list only if its keys are exactly 0 to n-1 in order; otherwise it encodes as an object.
- Target behavior: a JavaScript array always encodes as a list.
- Detect: `json_encode(array_filter([1, 0, 2]))` is `{"0":1,"2":2}`; `JSON.stringify([1, 0, 2].filter(Boolean))` is `[1,2]`.
- Port rule: after every key-preserving operation (`array_filter`, `unset`, `array_unique`), check whether the source reindexed with `array_values`. If not, the port must emit an object with the surviving keys.

### T4. Empty arrays encode as `[]` even when used as maps

- Tags: `encoding`
- Source behavior: `json_encode([])` is `[]`, including for arrays the code treats as maps. Only `new stdClass`, `(object)[]` or `JSON_FORCE_OBJECT` give `{}`.
- Target behavior: an empty object or `Map` port encodes as `{}`.
- Detect: `json_encode(['x' => []])` is `{"x":[]}`; the port with `{ x: {} }` gives `{"x":{}}`.
- Port rule: when serializing a map that may be empty, emit `[]` for the empty case if the source did.

### T5. `json_decode($s, true)` turns `{"0":...}` into a list

- Tags: `encoding`
- Source behavior: decoding to associative arrays normalizes keys, so an object with keys `"0"` to `"n-1"` becomes a list.
- Target behavior: `JSON.parse` keeps an object.
- Detect: `json_encode(json_decode('{"0":"a"}', true))` is `["a"]`; `JSON.stringify(JSON.parse('{"0":"a"}'))` is `{"0":"a"}`.
- Port rule: when the source decodes with `true` and re-encodes, convert decoded objects through `phpKey()` and the list check from T3.

### T6. `json_encode` escapes `/` and non-ASCII by default

- Tags: `encoding`, `unicode`
- Source behavior: without `JSON_UNESCAPED_SLASHES` and `JSON_UNESCAPED_UNICODE`, `/` becomes `\/` and non-ASCII becomes `\uXXXX`.
- Target behavior: `JSON.stringify` escapes neither.
- Detect: `json_encode("é/")` is `"é\/"`; `JSON.stringify("é/")` is `"é/"`.
- Port rule: write a `phpJsonEncode(value, flags)` that post-processes string escapes according to the flags the source passed.

### T7. `json_encode` float format

- Tags: `float-format`, `encoding`
- Source behavior: `json_encode` writes floats in shortest round-trip form but switches to exponent form at 1e17 and below 1e-4, always with a fractional digit and a lowercase `e` (`1.0e+17`, `1.0e-5`). `10.0` prints as `10` unless `JSON_PRESERVE_ZERO_FRACTION` is set.
- Target behavior: `JSON.stringify` switches to exponent form only at 1e21 and below 1e-6.
- Detect: `json_encode(1e17)` is `1.0e+17`; `JSON.stringify(1e17)` is `100000000000000000`.
- Port rule: if fixtures can contain large, small or zero-fraction floats, format numbers in the JSON writer with PHP's rules.

### T8. Arrays are copied on assignment and on calls

- Tags: `mutability`
- Source behavior: `$b = $a` and passing `$a` to a function copy the array (copy-on-write), so changes to the copy never reach the caller.
- Target behavior: arrays and maps are shared references.
- Detect: `function f($a) { $a[] = 1; return count($a); }` with `$x = []; f($x); count($x)` gives `0`; the TS port gives `1`.
- Port rule: copy at every mutation of a received or assigned array (`[...a]`, `new Map(m)`, `structuredClone` for nested arrays), or prove the value is never mutated and mark it `readonly`.

### T9. `foreach` iterates a snapshot

- Tags: `mutability`, `ordering`
- Source behavior: `foreach ($a as $v)` iterates the array as it was when the loop started.
- Target behavior: `for...of` over an array sees elements appended during the loop.
- Detect: iterating `[1, 2]` and appending `99` when `$v == 1` visits `1, 2` in PHP and `1, 2, 99` in the TS port.
- Port rule: iterate over a copy (`for (const v of [...a])`) wherever the loop body can modify the array.

### T10. `foreach` by reference leaves a live reference

- Tags: `mutability`
- Source behavior: after `foreach ($a as &$v) {}`, `$v` still points at the last element, so a later `foreach ($a as $v)` overwrites it.
- Target behavior: a port without references leaves the array intact.
- Detect: `$a = [1, 2, 3]; foreach ($a as &$v) {} foreach ($a as $v) {}` leaves `$a` as `[1, 2, 2]`; the TS port leaves `[1, 2, 3]`.
- Port rule: if fixtures show the corrupted result, reproduce it explicitly and record it; otherwise record the fix as a divergence.

### T11. `==` compares numeric strings as numbers

- Tags: `numeric`
- Source behavior: when both strings are numeric, `==` compares them as numbers: `"1" == "01"`, `"10" == "1e1"`, `100 == "1e2"`.
- Target behavior: JavaScript `==` compares two strings as strings.
- Detect: `"1" == "01"` is `true` in PHP; `'1' == '01'` is `false` in JavaScript.
- Port rule: port `==` on values that can be strings with a `phpLooseEquals(a, b)` helper implementing PHP 8 rules, or prove both sides have the same type and use `===`.

### T12. PHP 7 and PHP 8 disagree on string-to-number comparison

- Tags: `numeric`
- Source behavior: PHP 7.4 converts a non-numeric string to `0` when comparing with a number, so `0 == "a"` is `true`. PHP 8 compares as strings instead.
- Target behavior: JavaScript `0 == 'a'` is `false`, which matches PHP 8 only.
- Detect: `0 == "a"` is `true` on PHP 7.4 and `false` in JavaScript.
- Port rule: check which PHP version recorded the fixtures. For 7.x sources, `phpLooseEquals` must implement the 7.x table.

### T13. `switch`, `in_array` and `array_search` compare loosely

- Tags: `numeric`
- Source behavior: `switch` uses `==`; `in_array` and `array_search` use `==` unless the third argument is `true`.
- Target behavior: JavaScript `switch`, `includes` and `indexOf` use strict comparison.
- Detect: `switch ("1e1") { case "10": ... }` takes the `"10"` branch in PHP; the JavaScript `switch` falls to `default`.
- Port rule: port with `phpLooseEquals` unless the source passed `true` or the operands provably share a type. PHP 8 `match` is strict and maps to `===`.

### T14. `"0"` and `[]` are falsy, `NAN` is truthy

- Tags: `nullability`
- Source behavior: PHP treats `"0"`, `""`, `0`, `0.0`, `[]`, `null` and `false` as false, and `NAN` as true.
- Target behavior: JavaScript treats `"0"` and `[]` as true and `NaN` as false.
- Detect: `if ("0")` skips the branch in PHP and enters it in JavaScript.
- Port rule: use `phpTruthy()` (section 3) for every condition, `empty()` and `!` on values that can be strings, arrays or floats.

### T15. Sentinel `false` from `strpos` and friends

- Tags: `nullability`
- Source behavior: `strpos` returns `0` for a match at the start and `false` for no match; correct code tests `!== false`.
- Target behavior: `indexOf` returns `-1` for no match, which is truthy.
- Detect: `strpos('abc', 'd')` is `false`, so `if (strpos(...))` skips; `if ('abc'.indexOf('d'))` enters because `-1` is truthy.
- Port rule: port `strpos(...) !== false` to `includes` or `indexOf(...) !== -1`, and port bare truthiness checks literally (`indexOf(...) > 0` reproduces `if (strpos(...))`).

### T16. `+` on strings is numeric addition

- Tags: `numeric`
- Source behavior: PHP concatenates with `.`; `+` always converts operands to numbers.
- Target behavior: JavaScript `+` concatenates when either side is a string.
- Detect: `"10" + "5"` is `15` in PHP and `'105'` in JavaScript.
- Port rule: convert explicitly with a PHP numeric-string parser before `+` whenever an operand can be a string.

### T17. Non-numeric strings in arithmetic throw in PHP 8

- Tags: `error-model`, `numeric`
- Source behavior: PHP 8 throws `TypeError: Unsupported operand types: string + int` for `"abc" + 1`; a leading-numeric string like `"10 apples"` gives a warning and uses `10`. PHP 7.4 warned and used `0` for `"abc"`.
- Target behavior: JavaScript concatenates or produces `NaN` and never throws.
- Detect: `"abc" + 1` throws `TypeError` in PHP 8; `'abc' + 1` is `'abc1'` in JavaScript.
- Port rule: the numeric-string parser from T16 must throw the port's `TypeError` equivalent for non-numeric input on 8.x sources.

### T18. Scalar parameter types coerce without `strict_types`

- Tags: `numeric`
- Source behavior: without `declare(strict_types=1)`, `function inc(int $x)` accepts `"5"` and converts it to `5`.
- Target behavior: TypeScript types are erased, so a string from JSON or a query string flows through unchanged.
- Detect: `inc("5")` returns `6` in PHP; the TS `inc(x: number) { return x + 1 }` called with `"5"` from untyped input returns `'51'`.
- Port rule: convert at every public entry point that can receive untyped data, using PHP's coercion rules for the declared type. Check `declare(strict_types=1)` per file; it applies to calls made from that file.

### T19. 64-bit integers

- Tags: `numeric`
- Source behavior: integers are exact up to 2^63 - 1, then overflow to float.
- Target behavior: JavaScript numbers are exact only up to 2^53 - 1.
- Detect: `var_dump(9007199254740993)` prints `int(9007199254740993)`; JavaScript `9007199254740993` is `9007199254740992`.
- Port rule: use `bigint` for ids, counters and hashes that can exceed 2^53, and keep their JSON form (number or string) identical to the source.

### T20. Bitwise operators work on 64 bits

- Tags: `numeric`
- Source behavior: `&`, `|`, `^`, `~`, `<<`, `>>` operate on 64-bit signed integers.
- Target behavior: JavaScript bitwise operators truncate to signed 32-bit.
- Detect: `0xFFFFFFFF & 0xFFFFFFFF` is `4294967295` in PHP and `-1` in JavaScript.
- Port rule: use `bigint` (`BigInt.asIntN(64, ...)`) for 64-bit math, or `>>> 0` when the source masks to 32 bits.

### T21. `%` converts operands to int

- Tags: `numeric`
- Source behavior: `%` truncates both operands to integers before taking the remainder.
- Target behavior: JavaScript `%` works on floats.
- Detect: `7.5 % 2` is `1` in PHP and `1.5` in JavaScript.
- Port rule: port `%` as `Math.trunc(a) % Math.trunc(b)` where operands can be fractional; port `fmod` as `%`.

### T22. Division by zero throws in PHP 8

- Tags: `error-model`, `numeric`
- Source behavior: `1 / 0`, `1 % 0` and `intdiv(1, 0)` throw `DivisionByZeroError` in PHP 8. In 7.4, `/` warned and returned `INF`, `%` threw.
- Target behavior: JavaScript returns `Infinity` or `NaN`.
- Detect: `1 / 0` throws `DivisionByZeroError` in PHP 8; JavaScript gives `Infinity`.
- Port rule: add an explicit zero check that throws the port's `DivisionByZeroError` where the divisor can be zero.

### T23. Float to string uses 14 significant digits

- Tags: `float-format`
- Source behavior: `echo`, interpolation and `(string)` use `precision=14`, and switch to exponent form at 1e14 and below 1e-4.
- Target behavior: `String(x)` prints the shortest round-trip form and switches to exponent form at 1e21.
- Detect: `echo 0.1 + 0.2;` prints `0.3`; `String(0.1 + 0.2)` is `'0.30000000000000004'`.
- Port rule: route every float-to-string conversion through `phpFloatToString()` (section 6), and use shortest round-trip only where the source used `var_export`, `json_encode` or `serialize`.

### T24. `round` and `number_format` versus `toFixed`

- Tags: `float-format`
- Source behavior: `round` and `number_format` round half away from zero and correct for binary representation error.
- Target behavior: `toFixed` rounds the exact binary value, and `Math.round` rounds half toward positive infinity.
- Detect: `number_format(1.005, 2)` is `'1.01'`; `(1.005).toFixed(2)` is `'1.00'`.
- Port rule: use `Intl.NumberFormat` with fixed fraction digits (it matched PHP on `1.005`, `1.45`, `2.5` and `-2.5`) or a decimal library with half-up rounding, and fixture the boundary values.

### T25. `sprintf('%.Nf')` rounds ties to even

- Tags: `float-format`
- Source behavior: `sprintf` rounds the exact binary value, and exact ties go to the even digit.
- Target behavior: `toFixed` resolves exact ties upward in magnitude.
- Detect: `sprintf('%.0f', 2.5)` is `'2'`; `(2.5).toFixed(0)` is `'3'`.
- Port rule: port PHP's `sprintf` float conversion with ties-to-even on the exact value; do not reuse the `number_format` helper.

### T26. `strlen`, `substr` and friends count bytes

- Tags: `unicode`, `encoding`
- Source behavior: non-`mb_` string functions count and slice UTF-8 bytes.
- Target behavior: JavaScript string methods count UTF-16 code units.
- Detect: `strlen("é")` is `2`; `'é'.length` is `1`.
- Port rule: decide per call whether the source wanted bytes or text. For bytes, use `Buffer.byteLength` and `Buffer` slicing; for text, port to the `mb_` behavior, and record the divergence if the source mangled multi-byte text.

### T27. `mb_*` counts code points; JavaScript counts UTF-16 units

- Tags: `unicode`
- Source behavior: `mb_strlen`, `mb_substr` and `mb_strpos` count Unicode code points.
- Target behavior: `length`, `slice` and `indexOf` count UTF-16 code units, so astral characters count twice.
- Detect: `mb_strlen("😀")` is `1`; `'😀'.length` is `2`.
- Port rule: use `[...s]` (code point array) for `mb_` length, slicing and offsets.

### T28. `strtoupper`, `strtolower` and `ucfirst` are ASCII-only

- Tags: `unicode`, `locale`
- Source behavior: since 8.2 these functions change only ASCII letters. Before 8.2 they followed `setlocale(LC_CTYPE)`, which is the ASCII-only "C" locale by default.
- Target behavior: `toUpperCase` and `toLowerCase` apply Unicode case mapping.
- Detect: `strtoupper("é")` is `'é'`; `'é'.toUpperCase()` is `'É'`.
- Port rule: port to an ASCII-only helper (`s.replace(/[a-z]/g, (c) => c.toUpperCase())`). Use `toUpperCase` only for `mb_strtoupper`.

### T29. `trim` strips a fixed byte set

- Tags: `unicode`
- Source behavior: `trim` removes `" \t\n\r\0\x0B"` only; it keeps U+00A0 and other Unicode spaces and does remove NUL.
- Target behavior: JavaScript `trim` removes all Unicode whitespace and line terminators, but not NUL.
- Detect: `trim("x\0")` is `'x'`; `'x\0'.trim()` is `'x\u0000'`.
- Port rule: port `trim($s)` as `s.replace(/^[ \t\n\r\0\x0B]+|[ \t\n\r\0\x0B]+$/g, '')`, and translate custom character lists including `..` ranges.

### T30. `htmlspecialchars` defaults changed in 8.1

- Tags: `encoding`
- Source behavior: since 8.1 the default flags are `ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML401`, so `'` becomes `&#039;`. Before 8.1 single quotes were left alone.
- Target behavior: common JavaScript escapers differ: lodash `_.escape("'")` gives `&#39;`.
- Detect: `htmlspecialchars("'")` is `'` on 7.4 and `&#039;` on 8.1+; lodash gives `&#39;`.
- Port rule: write an escaper with the exact entity set and flags of the source version.

### T31. `rawurlencode` versus `encodeURIComponent`

- Tags: `encoding`
- Source behavior: `rawurlencode` follows RFC 3986 and leaves only `A-Z a-z 0-9 - _ . ~` unencoded; `urlencode` also turns spaces into `+`.
- Target behavior: `encodeURIComponent` leaves `! ' ( ) *` unencoded.
- Detect: `rawurlencode("a!b")` is `'a%21b'`; `encodeURIComponent('a!b')` is `'a!b'`.
- Port rule: port `rawurlencode` as `encodeURIComponent(s).replace(/[!'()*]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase())`. For `urlencode`, also encode `~` as `%7E` and replace `%20` with `+`.

### T32. `parse_str` and `$_GET` rewrite dots and spaces in names

- Tags: `encoding`
- Source behavior: PHP replaces `.` and space in incoming variable names with `_`, and turns `a[]=1&a[]=2` into an array.
- Target behavior: `URLSearchParams` keeps names as sent and has no bracket syntax.
- Detect: `parse_str("a.b=1&c d=2", $o)` gives keys `a_b` and `c_d`; `URLSearchParams` gives `a.b` and `c d`.
- Port rule: use `qs` for brackets and apply PHP's name mangling before lookup.

### T33. PCRE `$` matches before a final newline

- Tags: `regex`
- Source behavior: without the `D` modifier, `$` matches at the very end and before a trailing `\n`.
- Target behavior: JavaScript `$` without `m` matches only at the very end.
- Detect: `preg_match('/^abc$/', "abc\n")` is `1`; `/^abc$/.test('abc\n')` is `false`.
- Port rule: translate `$` to `(?=\n?$)` unless the pattern has `D` or `m`. Validation code that relied on this lets a trailing newline through; keep that or record a divergence.

### T34. `/u` makes `\w`, `\d` and `\b` Unicode-aware

- Tags: `regex`, `unicode`
- Source behavior: PHP's `u` modifier turns on Unicode properties for `\w`, `\d` and `\b`.
- Target behavior: JavaScript `\w`, `\d` and `\b` stay ASCII even with `u`.
- Detect: `preg_match('/^\w$/u', 'é')` is `1`; `/^\w$/u.test('é')` is `false`.
- Port rule: under `/u`, translate `\w` to `[\p{L}\p{N}_]` and `\d` to `\p{Nd}` with the `u` flag, and rewrite `\b` with lookarounds. Newer PCRE2 releases (bundled with recent PHP versions) also count `\p{Mn}` and `\p{Pc}` as word characters; add them if fixtures show it.

### T35. preg offsets are byte offsets

- Tags: `regex`, `unicode`
- Source behavior: `PREG_OFFSET_CAPTURE`, the `$offset` argument and `preg_match_all` offsets count bytes, even with `/u`.
- Target behavior: `match.index` counts UTF-16 code units.
- Detect: `preg_match('/b/u', 'éb', $m, PREG_OFFSET_CAPTURE)` gives offset `2`; `'éb'.search(/b/u)` is `1`.
- Port rule: convert offsets with `Buffer.byteLength(s.slice(0, index))` when they leave the function, and convert incoming byte offsets back before slicing.

### T36. `preg_replace` replaces every match

- Tags: `regex`
- Source behavior: `preg_replace` replaces all matches unless `$limit` is given.
- Target behavior: `String.prototype.replace` with a regex lacking `g` replaces the first match only.
- Detect: `preg_replace('/a/', 'b', 'aa')` is `'bb'`; `'aa'.replace(/a/, 'b')` is `'ba'`.
- Port rule: add the `g` flag for `preg_replace` without a limit; implement `$limit` with a counter in a replacer function.

### T37. `preg_split` drops captures unless asked

- Tags: `regex`
- Source behavior: captured groups in the delimiter are discarded unless `PREG_SPLIT_DELIM_CAPTURE` is set.
- Target behavior: JavaScript `split` includes captured groups in the output.
- Detect: `preg_split('/(-)/', 'a-b')` is `['a', 'b']`; `'a-b'.split(/(-)/)` is `['a', '-', 'b']`.
- Port rule: convert capturing groups in split patterns to non-capturing `(?:...)` unless the flag is set.

### T38. Unmatched groups are `""`

- Tags: `regex`, `nullability`
- Source behavior: an unmatched group before a matched one is `""` in `$m`; trailing unmatched groups are absent.
- Target behavior: JavaScript match arrays hold `undefined` for unmatched groups.
- Detect: `preg_match('/(a)?(b)/', 'b', $m)` gives `$m[1] === ""`; `'b'.match(/(a)?(b)/)[1]` is `undefined`.
- Port rule: map `undefined` to `''` and trim trailing unmatched groups when building `$m`, unless the source used `PREG_UNMATCHED_AS_NULL`.

### T39. `catch (Exception $e)` does not catch engine errors

- Tags: `error-model`
- Source behavior: `TypeError`, `ArgumentCountError`, `ValueError` and other `Error`s are not `Exception`s and pass through `catch (Exception $e)`.
- Target behavior: a JavaScript `catch` catches everything.
- Detect: `try { strlen(); } catch (Exception $e) { echo 'caught'; }` lets `ArgumentCountError` escape in PHP 8; the TS `try/catch` reports `caught`.
- Port rule: in catch blocks ported from `catch (Exception $e)`, rethrow anything that is not an instance of the port's exception base class.

### T40. Warnings return `false` or `null`; JavaScript throws

- Tags: `error-model`
- Source behavior: `json_decode`, `file_get_contents`, `unserialize`, `iconv` and many others return `null` or `false` and emit a warning on bad input.
- Target behavior: the JavaScript equivalents throw.
- Detect: `json_decode('')` returns `null`; `JSON.parse('')` throws `SyntaxError`.
- Port rule: wrap the target call in `try/catch` and return the PHP sentinel, unless the source runs under an `ErrorException` handler (then throw).

### T41. `date.timezone` versus the process timezone

- Tags: `datetime`
- Source behavior: PHP uses `date.timezone` from php.ini (UTC when unset) and ignores the `TZ` environment variable.
- Target behavior: Node uses `TZ` or the operating system zone.
- Detect: with `date.timezone` unset and `TZ=America/New_York`, `date('H:i', 0)` is `'00:00'`; `new Date(0).getHours()` is `19`.
- Port rule: read the source's `date.timezone`, then format and parse with that zone explicitly (date-fns-tz, Luxon `setZone`, or `Intl.DateTimeFormat` with `timeZone`).

### T42. `DateTime` is mutable

- Tags: `datetime`, `mutability`
- Source behavior: `$d->modify('+1 day')` changes `$d` and returns the same object, so `$d2 = $d->modify(...)` aliases.
- Target behavior: date-fns, Luxon and Day.js return new values.
- Detect: `$a = new DateTime('2024-01-01'); $b = $a->modify('+1 day'); echo $a->format('d');` prints `02`; the Luxon port prints `01` for `a`.
- Port rule: for `DateTime` (not `DateTimeImmutable`), assign the result back to every alias the source mutated through.

### T43. `modify('+1 month')` overflows

- Tags: `datetime`
- Source behavior: month arithmetic keeps the day number and rolls over: January 31, 2024 plus one month is March 2.
- Target behavior: date-fns `addMonths` and Luxon `plus({ months: 1 })` clamp to February 29.
- Detect: `(new DateTime('2024-01-31'))->modify('+1 month')->format('Y-m-d')` is `2024-03-02`; `addMonths(new Date(2024, 0, 31), 1)` gives 2024-02-29.
- Port rule: port month and year arithmetic with native `Date.setMonth` (which overflows the same way) or a helper, and fixture the 29th to 31st of each month.

### T44. `sort` compares numeric strings numerically

- Tags: `ordering`
- Source behavior: `sort()` with the default `SORT_REGULAR` compares with PHP 8 comparison rules, so numeric strings sort as numbers.
- Target behavior: `Array.prototype.sort()` without a comparator compares as strings.
- Detect: `sort(["10", "9", "1"])` gives `["1", "9", "10"]`; `['10', '9', '1'].sort()` gives `['1', '10', '9']`.
- Port rule: always pass a comparator built on PHP's `<=>` rules for the flag the source used (`SORT_REGULAR`, `SORT_STRING`, `SORT_NUMERIC`, `SORT_NATURAL`). PHP 7 sort was not stable; PHP 8 and JavaScript are.

### T45. Static properties are shared with subclasses

- Tags: `mutability`, `reflection`
- Source behavior: a static property declared once in a parent is one storage slot for the whole hierarchy, unless a child redeclares it.
- Target behavior: in JavaScript, `this.n++` in a static method called on a subclass reads the parent's value through the prototype chain and writes a new own property on the subclass.
- Detect: `class SA { static $n = 0; static function inc() { static::$n++; } } class SB extends SA {}`, then `SB::inc()`: `SA::$n` is `1`. The TS port with `this.n++` leaves `SA.n` at `0` and creates `SB.n = 1`.
- Port rule: write through the declaring class (`SA.n++`) for properties that subclasses do not redeclare; use `this` only for properties a subclass redeclares.

### T46. Request-scoped static state becomes process-wide

- Tags: `mutability`
- Source behavior: under PHP-FPM, statics, singletons and caches start empty for every request.
- Target behavior: module-level and static state in a Node server persists across requests.
- Detect: `Counter::next()` returning `++self::$n`, called once per HTTP request, gives `1` then `1` under PHP-FPM; the Node port gives `1` then `2`.
- Port rule: list every static property, `static` local variable and singleton in the survey. Move request-scoped ones into an explicit context object, or reset them per request.

### T47. `__destruct` runs deterministically

- Tags: `io`
- Source behavior: an object's destructor runs as soon as its last reference disappears, so locks, files and transactions are released at scope end.
- Target behavior: JavaScript has no destructors; `FinalizationRegistry` callbacks may never run.
- Detect: `function f() { $lock = new FileLock('x'); } f();` releases the lock when `f` returns; the TS port keeps the lock until process exit.
- Port rule: give the class a `close()` or `[Symbol.dispose]()` method and call it in `finally`, or use a `using` declaration.

### T48. Includes run in statement order; ESM imports are hoisted

- Tags: `ordering`
- Source behavior: `require 'b.php'` runs `b.php` when the statement executes.
- Target behavior: `import './b.js'` runs before any statement of the importing module.
- Detect: `echo "a"; require 'b.php';` (where `b.php` echoes `b`) prints `ab`; `console.log('a'); import './b.js';` prints `ba`.
- Port rule: move side effects of included files into exported functions and call them where the source included the file.

### T49. Function and class names are case-insensitive

- Tags: `reflection`
- Source behavior: PHP resolves function, class and method names case-insensitively, including dynamic calls through strings.
- Target behavior: JavaScript lookups are case-sensitive.
- Detect: `$f = 'STRLEN'; $f('ab')` returns `2`; a TS dispatch table lookup `fns['STRLEN']` is `undefined`.
- Port rule: normalize names at every dynamic dispatch site (`call_user_func`, `new $class`, `$obj->$method()`), for example by lowercasing keys of the dispatch table.

### T50. Autovivification

- Tags: `nullability`, `mutability`
- Source behavior: writing to a nested key of a missing or `null` array creates the intermediate arrays.
- Target behavior: writing through `undefined` throws.
- Detect: `$c = []; $c['a']['b'] = 1;` gives `{"a":{"b":1}}`; `const c = {}; c.a.b = 1` throws `TypeError: Cannot set properties of undefined`.
- Port rule: create intermediate containers explicitly (`(c.a ??= {}).b = 1`, or a `setIn` helper for `Map`s).

### T51. `range()` counts down

- Tags: `ordering`
- Source behavior: `range($a, $b)` produces a descending sequence when `$a > $b`, and letters for single-character string bounds.
- Target behavior: a `for (let i = a; i <= b; i++)` loop runs zero times when `a > b`.
- Detect: `range(1, 0)` is `[1, 0]`; the TS loop produces `[]`.
- Port rule: port `range` with a helper that handles direction, step and character bounds.

### T52. `iterator_to_array` keeps keys

- Tags: `ordering`
- Source behavior: `iterator_to_array($gen)` uses the generator's keys. `yield from` passes through the inner keys, which restart at 0, so later values overwrite earlier ones.
- Target behavior: `[...gen]` collects every value.
- Detect: `function g() { yield 1; yield from [2, 3]; yield 4; }`: `iterator_to_array(g())` is `[2, 4]`; `[...g()]` is `[1, 2, 3, 4]`.
- Port rule: port `iterator_to_array($g)` as a keyed `Map` build, and `iterator_to_array($g, false)` as `[...g]`.

### T53. `intval` and `(int)` read exponents

- Tags: `numeric`
- Source behavior: `(int)"1e3"` and `intval("1e3")` are `1000` (PHP 7.1+); `intval("0x1A")` is `0`.
- Target behavior: `parseInt('1e3')` is `1`, and `parseInt('0x1A')` is `26`.
- Detect: `intval("1e3")` is `1000` in PHP; `parseInt('1e3')` is `1`.
- Port rule: port `intval` with a helper that parses the leading numeric string (including exponents), truncates, and saturates at the 64-bit bounds.
