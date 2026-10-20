# Generic pair reference

| Field | Value |
| --- | --- |
| Source | any language that has no dedicated pair file |
| Target | any language that has no dedicated pair file |
| Status | full |
| Last reviewed | 2026-10-20 |

How to use this file: the `strategy` skill loads it to seed the idiom map for a
port when `knowledge/pairs/<src>-to-<dst>.md` does not exist, and the
`implement` skill reads the sections a unit's risk tags point at. Every trap
carries risk tags from this vocabulary, which `porter.py decompose` also emits
for units:

`regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`,
`unicode`, `encoding`, `io`, `locale`, `mutability`, `nullability`,
`error-model`, `ordering`.

A pair file gives answers. This file gives the questions. Sections 1 to 14
each have three parts:

- Questions: a checklist to answer for the specific pair before writing code.
- Universal traps: the traps from section 15 that apply to almost every pair.
- Record: what to write into the idiom map in the port's `strategy.md`.

## Answering the questions

Answer each question with a probe, not from memory. A probe is the smallest
program that shows the behavior: one input, run on the exact source runtime
and the exact target runtime the port uses. Most traps in section 15 are
version-dependent somewhere, and a remembered answer is often the answer for
another language or another version.

Record every answer as a row of the idiom map in `strategy.md`:

| Area | Source behavior | Target idiom or helper | Probe (input, source result, target result) | Traps |
| --- | --- | --- | --- | --- |
| Integer division | floors: `-7 // 2` is `-4` | `floorDiv` in `internal/num` | `-7, 2`: source `-4`, target `/` gives `-3` | T12 |
| Map iteration | insertion order, observable in output | ordered map type | insert `b`, `a`: source `b, a`, target varies per run | T24 |

Rules for the idiom map:

- One row per decision. "Same in both" is a valid answer when a probe shows
  it; write the probe anyway so the next reader does not redo it.
- Write the runtime versions used for the probes at the top of the map
  (for example "CPython 3.12.4, Go 1.22.5"). Unicode tables, tz data, error
  messages and library defaults change between versions.
- "Unknown" is allowed only with a plan to find out, usually a fixture that
  covers the case. List those fixtures in `strategy.md`.
- When a helper reproduces source behavior, name it in the row and give it
  its own unit with its own tests.
- If a dedicated pair file appears later, it replaces this file, and the
  idiom map rows that disagree with it get reviewed.

Conventions in section 15: a Detect line gives one input and its result in
several languages. Every result shown was produced by running it on CPython
3.14 (and 3.13 where stated), Node 24.18, Go 1.26, Rust 1.93, Ruby 3.4,
.NET 10 (C#), Swift 6.3 or Perl 5.34. Languages without a result shown (for
example Java, Kotlin, PHP, Elixir) were not run; probe them before relying on
a claim about them.

## 1. Type system mapping

Questions:

- [ ] For each source type in the public API, which target type? Cover
  integers (width, signedness, unbounded), floats, decimals, booleans,
  characters, strings, byte strings, lists, tuples, maps, sets, records,
  enums, unions, functions and closures, and the null or unit value.
- [ ] Is the source typed dynamically, gradually or statically? Where the
  source relies on duck typing, what replaces it in the target: interfaces,
  traits, protocols, generics with constraints, or tagged unions?
- [ ] Is the target's typing nominal or structural? Can two unrelated types
  with the same shape be passed for each other on one side and not the other?
- [ ] Does the source check types at runtime (`isinstance`, `instanceof`,
  `is_a?`, type switches)? Do target types exist at runtime, or are generics
  erased (Java, TypeScript) or reified (C#)?
- [ ] Value or reference semantics for each type: does assignment copy or
  share (T38)? Which source objects are shared and mutated by several owners?
- [ ] Are booleans numbers in the source (Python `True + 1 == 2`, C
  truthiness), and does the code depend on that?
- [ ] How are equality and hashing defined for compound values on each side,
  and which types can be map keys (T39)?
- [ ] Which public data must be read-only, and what does the target offer
  (`final`, `readonly`, `val`, immutable collections, ownership)?
- [ ] Does the target support every generic construct the source uses
  (variance, generic methods, higher-kinded types), or does code need to be
  duplicated or generated?
- [ ] Enums: are source enum values integers, strings, or objects? Are they
  open (any integer) or closed? Do they serialize by name or by value?

Universal traps: T10, T11 (integer width), T38 (value against reference),
T39 (equality of compound values).

Record: a table of source type to target type for every type that crosses
the public API, with the reason whenever there was a choice (for example an
unbounded integer mapped to a 64-bit integer because the contract bounds it).
Record the equality and copy semantics of each mapped type.

## 2. Error model

Questions:

- [ ] How does the source signal failure: exceptions, error values, result
  types, sentinel values (`-1`, `nil`, `false`), panics, or process exit? What
  is idiomatic in the target?
- [ ] What error categories can the public API produce (the contract lists
  them)? For each: the target type, how a caller tests for it (`catch` on a
  class, `errors.Is` or `errors.As`, a match on an error enum), and whether its
  message text is part of the contract.
- [ ] Does the source rely on hierarchy, so that catching a base class catches
  subclasses? How is the same grouping expressed in the target?
- [ ] How is a cause attached (`raise ... from`, `cause`, `%w`, `source()`)
  and does any caller read it?
- [ ] Which operations raise in one language and return a special value in
  the other: division by zero, number parsing, out-of-range index, missing map
  key, invalid UTF-8, invalid dates (T17, T30, T33, T40, T44)?
- [ ] Which source errors come from wrong argument types that the target's
  type checker rejects at compile time? Those cases become contract changes,
  not tests.
- [ ] What happens to an unhandled error in a background task or thread on
  each side (T34)?
- [ ] Does any caller or test compare error messages, error codes, or stack
  traces (T35)?
- [ ] Does cleanup run on every path (`finally`, `ensure`, `defer`, `Drop`,
  `using`) in the same order on both sides?

Universal traps: T32 (error identity), T33 (out-of-range access), T34 (errors
in background tasks), T35 (messages change between versions).

Record: the error idiom (exceptions, results, or both, and where each is used)
in the idiom map, and the per-category mapping in
`.porter/contract/error-map.json`: source category, target type, how callers
test for it, and where the message text comes from.

## 3. Null and absence

Questions:

- [ ] How many "nothing" values does each side have? Python `None`; JS `null`
  and `undefined`; Go `nil` plus zero values; Rust `Option`; nullable types in
  Kotlin, Swift and C#; SQL `NULL`; a missing JSON key. Which target value
  stands for each source value?
- [ ] Does the source distinguish "key missing" from "key present with null"
  (JSON input, dictionaries, keyword arguments)? Can the target (T41, T42)?
- [ ] What does a failed lookup return on each side: missing map key,
  out-of-range index, no regex match, no list element found (T33, T40)?
- [ ] Does the target fill in zero values (`0`, `""`, `false`) where the
  source has null, for example when decoding JSON into structs (T41)?
- [ ] How does each absent value print and serialize (T9, T42)?
- [ ] For optional parameters: does passing null explicitly mean "use the
  default" or "set to null"?
- [ ] Which values are falsy on each side, and where does the source branch
  on truthiness (T43)?

Universal traps: T9, T40, T41, T42, T43.

Record: one row per kind of absence with the source value, the target value,
how it is tested, how it prints, and how it serializes.

## 4. Concurrency and async

Questions:

- [ ] What is the source model: OS threads, a global interpreter lock, an
  event loop, coroutines, green threads, processes, actors? And the target's?
- [ ] Do async functions start running when called or when awaited (T52)?
- [ ] Which APIs are synchronous in the source but must be asynchronous in the
  target (I/O in JavaScript), or the reverse? Changed signatures are contract
  changes; record them.
- [ ] How are cancellation and timeouts expressed (task cancel,
  `context.Context`, `AbortSignal`, `CancellationToken`)? Which library calls
  have default timeouts on one side only?
- [ ] What protected shared mutable state in the source (a global lock, a
  single thread, explicit locks), and what protects it in the target? Code
  that was safe under a global lock can race on real threads.
- [ ] What happens to an exception in a task nobody waits for (T34)?
- [ ] Are concurrent results returned in submission order or completion
  order?
- [ ] Which source calls block, and would they stall the target's event loop
  or scheduler?

Universal traps: T34, T52.

Record: the concurrency model, the async boundary (which public functions are
async), the cancellation mechanism, and the locking rule for shared state.

## 5. Iteration, generators, laziness

Questions:

- [ ] Which source sequences are lazy (generators, streams, enumerators), and
  does any caller depend on laziness: infinite sequences, side effects during
  consumption, early exit, memory limits?
- [ ] What is the target's lazy construct (generators, iterator traits,
  channels, `Sequence`, `IEnumerable`)? Does it support values sent back into
  a generator if the source uses that?
- [ ] Are iterators single-use or restartable on each side?
- [ ] What happens when a collection is modified while being iterated: an
  error, undefined behavior, or newly added items being visited?
- [ ] In what order do maps and sets iterate (T24, T25)?
- [ ] Range and slice semantics: is the end inclusive or exclusive? What do
  negative indexes and steps do? Do out-of-range slice bounds clamp (Python
  `[1, 2, 3][1:100]` is `[2, 3]`) or fail (Go panics with `slice bounds out
  of range`)?

Universal traps: T24, T25, T33.

Record: which public functions return lazy sequences and the target type for
each; the slice and range helpers the port needs.

## 6. Numeric semantics

Questions:

- [ ] For each numeric value domain (IDs, counters, sizes, money, hashes,
  timestamps), what is the largest value? Does it fit 32 bits, 53 bits (the
  exact integer range of a double), 64 bits (T10, T11)?
- [ ] What happens on overflow: wrap, panic, trap, or promote to a bigger
  type? Does it depend on the build mode (Rust debug against release)?
- [ ] What do integer division and modulo do with negative operands (T12)?
  Does dividing two integers give an integer or a float (T13)?
- [ ] What mode does the default rounding function use (T14)? What mode does
  fixed-decimal formatting use (T16)?
- [ ] How does a float become text: shortest round-trip digits, a `.0`
  suffix, exponent thresholds, exponent format (T15)?
- [ ] Where does the source raise on bad arithmetic (division by zero, square
  root of a negative, float overflow) and the target return NaN or infinity,
  or the reverse?
- [ ] Is negative zero observable (printed, compared, serialized)?
- [ ] Decimal arithmetic: precision, rounding mode, context, and how values
  print (trailing zeros, exponent form).
- [ ] How lenient is number parsing: whitespace, signs, underscores, leading
  zeros, non-ASCII digits, trailing garbage (T17)? Is any of it
  locale-dependent (T18)?
- [ ] Are seeded random sequences part of any fixture? If so, the port must
  reproduce the source's generator algorithm exactly.
- [ ] What width and sign do bit operations and shifts use?

Universal traps: T10 to T19.

Record: the target type per value domain with its bound, the division,
modulo, rounding and formatting helpers, and the parse rules per input
format.

## 7. Strings, bytes, unicode, encodings

Questions:

- [ ] What is a string on each side: code points (Python, Ruby), UTF-16 code
  units (JS, Java, C#), UTF-8 bytes (Go, Rust), grapheme clusters (Swift
  `count`), or bytes with an encoding tag?
- [ ] Which public functions take or return a length, offset or index into
  text, and in which unit (T1)?
- [ ] Where does code cut text at an offset: truncation, slicing, padding,
  column alignment, wrapping (T2, T3)?
- [ ] Does either side normalize strings before comparing or hashing them
  (T4)?
- [ ] Do case functions use full or simple mappings (T5)? Do they depend on
  the current locale (T6)? What does case-insensitive comparison use?
- [ ] What do character predicates (`isalpha`, `isdigit`, `isspace`) and
  regex classes match: ASCII or which Unicode properties? Which Unicode
  version does each runtime ship?
- [ ] How are byte strings represented, and are they mutable?
- [ ] What happens to invalid input bytes: an error, replacement characters,
  or bytes kept as they are (T44)? Is a byte order mark stripped (T45)?
- [ ] How are strings ordered by default (T7, T8)?
- [ ] How do null, booleans, floats and collections print inside formatted
  strings (T9, T15)?

Universal traps: T1 to T9, T44, T45.

Record: the string model on both sides, the unit used at the API boundary,
the Unicode versions, and the helpers for length, slicing, case mapping,
comparison and decoding.

## 8. Dates, times, timezones

Questions:

- [ ] Which date and time kinds does the source use: naive local date-times,
  zone-aware date-times, UTC instants, dates, times, durations? Which target
  types or libraries represent each kind?
- [ ] What zone does parsing assume when the input has no offset (T28)?
- [ ] Which epoch unit does each API use (seconds, milliseconds,
  microseconds, nanoseconds), and what precision does each type keep (T29)?
- [ ] How are months and weekdays numbered, and what happens to an invalid
  date such as February 30: an error or a rollover (T30)?
- [ ] Does date arithmetic across a DST change add calendar time or elapsed
  time (T31)?
- [ ] Where does each runtime get time zone data, and which version is it?
- [ ] Which format-string dialect does each side use (`strftime`, Go's
  reference time, Java and ICU patterns), and do month and day names depend
  on the locale?
- [ ] Are years before 1970, after 2038 or outside 1 to 9999 possible?

Universal traps: T28 to T31.

Record: one row per date and time kind with the target type, the zone policy
for parsing and printing, the epoch unit, and the arithmetic rule. Pin
`TZ=UTC` for fixture recording and the target tests, and plan one extra test
run under a zone with DST.

## 9. Regex dialect

Questions:

- [ ] Is each engine backtracking (Python `re`, JS, Java, .NET, Ruby Onigmo,
  PCRE in PHP) or linear-time (Go `regexp` and Rust `regex`, which have no
  lookaround and no backreferences) (T22)?
- [ ] What do `\w`, `\d`, `\s` and `\b` match by default, and under the flags
  the source uses (T20)?
- [ ] What do `^` and `$` match with and without multiline mode? Does `$`
  match before a final newline (T21)? What does `.` refuse to match?
- [ ] Does case-insensitive matching use simple or full case folding, and is
  it Unicode-aware?
- [ ] Syntax differences: named groups (`(?P<n>...)` or `(?<n>...)`), inline
  flags and where they may appear, atomic groups and possessive quantifiers,
  Unicode property escapes, `\A`, `\Z` and `\z`.
- [ ] Replacement templates (`\1`, `\g<1>`, `$1`, `${1}`) and what a
  replacement callback receives (T23).
- [ ] Match API: search anywhere, match at the start, or match the whole
  string; does find-all return whole matches or groups; does split keep
  captured groups?
- [ ] In which unit are match offsets reported (T1)?
- [ ] Does the source rely on a timeout or on a backtracking limit for
  pathological patterns?

Universal traps: T20 to T23.

Record: a translation table from each pattern construct the source uses to
its target form, then every source pattern next to its translated pattern
with one test input that exercises the difference.

## 10. I/O, paths, process, environment

Questions:

- [ ] Does text-mode I/O translate newlines on either side (T48)? What
  encoding does it use when none is given (T49)?
- [ ] How do path join and normalization treat absolute components, trailing
  separators, `..`, and drive letters (T50)?
- [ ] Is directory listing order observable? It is unspecified everywhere;
  sort it.
- [ ] Does an unset environment variable differ from an empty one (T51)?
- [ ] Exit codes, buffering of stdout and whether it is flushed on exit,
  what goes to stderr.
- [ ] Command-line parsing: where the program name sits in `argv`, help text,
  and the exit code for usage errors.
- [ ] Subprocesses: through a shell or not, argument quoting, the encoding of
  their output.
- [ ] Are file APIs synchronous or asynchronous in the target, and does that
  change public signatures (section 4)?
- [ ] Which platform differences does the source handle (Windows paths, line
  endings, case-insensitive file systems)?

Universal traps: T48 to T51.

Record: the I/O helper set (read text, write text, join paths, read
environment) with the encoding and newline policy of each.

## 11. Module layout, packaging, naming, visibility

Questions:

- [ ] What is the module unit on each side (file, directory package, crate
  module, namespace), and how does the source layout map onto it?
- [ ] How is "private" marked on each side (`_name`, `private`, lowercase
  names in Go, missing `pub` in Rust), and is it enforced?
- [ ] Naming conventions for identifiers, files and packages on the target.
  Which names cross a wire (JSON keys, CLI flags, environment variables,
  config keys, database columns) and must keep their exact spelling (T53)?
- [ ] Are circular imports allowed? Go rejects import cycles; ES modules throw
  `ReferenceError` when a `class`, `let` or `const` binding is read before its
  module has finished evaluating.
- [ ] What runs at import time on each side, and in what order?
- [ ] Manifest, entry points, command-line binaries, optional features,
  minimum runtime version, version scheme (PEP 440 has `.dev` and `.post`
  releases that semver lacks).
- [ ] What replaces monkeypatching, plugins loaded by name, `eval`, and
  `method_missing`-style dispatch?
- [ ] Which names does the contract mark public, and how does the target
  re-export them?

Universal traps: T53.

Record: the module map (source module to target module), naming rules,
visibility rules, wire names that must not be renamed, and the package
manifest fields.

## 12. Standard library equivalence

In this file the Source column names an area, the Target column lists where
common languages keep it, and Notes lists what to compare. In `strategy.md`,
replace it with a real table: one row per source module the code imports (the
survey lists them), the target module or `none`, and the differences the
fixtures touch.

| Source | Target | Notes |
| --- | --- | --- |
| JSON | Python `json`, JS `JSON`, Go `encoding/json`, Rust `serde_json`, Java Jackson or Gson, C# `System.Text.Json`, Ruby `json`, PHP `json_encode` | Big integers (T46), key order (T27), spacing and escaping (T47), NaN (T19), absent fields (T41, T42). |
| Regex | Python `re`, JS `RegExp`, Go `regexp`, Rust `regex`, Java `java.util.regex`, C# `System.Text.RegularExpressions`, Ruby `Regexp`, PHP `preg_*` | Section 9. |
| Date and time, time zones | Python `datetime` and `zoneinfo`, JS `Date` or Temporal, Go `time`, Rust `chrono` or `jiff`, Java `java.time`, C# `DateTimeOffset` and `TimeZoneInfo`, Ruby `Time`, PHP `DateTimeImmutable` | Section 8. |
| Decimal numbers | Python `decimal`, Java `BigDecimal`, C# `decimal`, Ruby `BigDecimal`, PHP `bcmath`; JS, Go and Rust need a library | Precision, rounding mode, printing of trailing zeros. C# `decimal` holds 28 to 29 significant digits. |
| Big integers | Python and Ruby integers, JS `bigint`, Go `math/big`, Java and C# `BigInteger`, Rust `num-bigint`, PHP `gmp` | Division and modulo signs (T12) apply here too. |
| Random numbers | Python `random` and Ruby `Random` (Mersenne Twister), JS `Math.random` (not seedable), Go `math/rand/v2`, Java `java.util.Random`, C# `System.Random`, Rust `rand` | Seeded sequences differ between generators. Port the source algorithm only if fixtures depend on seeds. |
| Hashing | Python `hashlib`, Node `node:crypto`, Go `crypto/*`, Java `MessageDigest`, C# `System.Security.Cryptography`, Ruby `Digest`, PHP `hash` | Same digests; check the string encoding before hashing and the hex letter case. |
| Base64 and hex | Python `base64`, Node `Buffer`, Go `encoding/base64` and `encoding/hex`, Java `Base64` and `HexFormat`, C# `Convert`, Ruby `pack("m0")`, PHP `base64_encode` | Padding, URL-safe alphabet, line breaks (Ruby `pack("m")` every 60 characters, MIME encoders every 76), strictness on bad input. |
| Compression | Python `zlib` and `gzip`, Node `node:zlib`, Go `compress/*`, Java `java.util.zip`, C# `System.IO.Compression`, Ruby `Zlib` | Compressed bytes differ (levels, header fields); compare decompressed data. |
| CSV | Python `csv`, Go `encoding/csv`, Ruby `csv`, PHP `fgetcsv`; JS, Java, C# and Rust need a library | Line terminator (Python's writer uses `\r\n`), quoting rules, BOM, empty trailing field. |
| URLs | Python `urllib.parse`, JS `URL`, Go `net/url`, Java `URI`, C# `Uri`, Ruby `URI`, PHP `parse_url` | Form encoding writes a space as `+` (Python `quote_plus`, Go `QueryEscape`, Java `URLEncoder`, PHP `urlencode`); path encoding writes `%20`. The set of characters left unescaped differs per function. |
| Paths and files | Python `os.path` and `pathlib`, Node `node:path` and `node:fs`, Go `path/filepath` and `os`, Rust `std::path` and `std::fs`, Java `java.nio.file`, C# `System.IO` | Section 10, T50. |
| Subprocesses | Python `subprocess`, Node `node:child_process`, Go `os/exec`, Rust `std::process`, Java `ProcessBuilder`, C# `System.Diagnostics.Process`, Ruby `Open3` | Shell use, quoting, output encoding, exit status on signals. |
| Command-line parsing | Python `argparse`, Node `util.parseArgs`, Go `flag`, Ruby `OptionParser`; Rust, Java and C# usually use a library | Help text, exit code on usage errors (`argparse` exits with 2), combined short flags, `--opt=value`. |
| Logging | Python `logging`, Go `log/slog`, Java `java.util.logging`, C# `Microsoft.Extensions.Logging`, Ruby `Logger` | Rarely part of the contract; inject a logger. |
| Priority queues | Python `heapq` (min-heap), Java `PriorityQueue` (min), C# `PriorityQueue` (lowest priority first), Rust `BinaryHeap` (max-heap), Go `container/heap` (order from `Less`), PHP `SplPriorityQueue` (highest first) | Direction and tie order differ. |
| Ordered and sorted maps | Python `dict`, Ruby `Hash`, JS `Map` (insertion order); Java `LinkedHashMap` and `TreeMap`, C# `SortedDictionary`, Rust `BTreeMap` | T24. |
| Sorting | Python `sorted`, JS `sort`, Java `List.sort`, Rust `sort`, Go `slices.SortStableFunc`, LINQ `OrderBy`, PHP 8 `sort` (stable); Go `sort.Slice`, Rust `sort_unstable`, C# `List.Sort`, Ruby `sort_by` (not stable) | T26; default string comparison T7, T8. |
| String formatting | Python f-strings and `%`, JS template literals, Go `fmt`, Rust `format!`, Java `String.format`, C# interpolation, Ruby `format`, PHP `sprintf` | T9, T15, T16. Java `String.format` and C# interpolation use the current locale (T18). |
| Unicode data and normalization | Python `unicodedata`, JS `normalize` and `\p{...}`, Go `unicode` and `golang.org/x/text`, Java `Normalizer`, C# `string.Normalize`, Ruby `unicode_normalize` | Unicode versions differ per runtime release. |
| Native object serialization | Python `pickle`, Ruby `Marshal`, Go `encoding/gob`, Java `Serializable`, PHP `serialize` | Never port the format. Choose a documented format and record the change in the contract. |
| Threads and tasks | Python `threading` and `asyncio`, JS promises and `worker_threads`, Go goroutines, Rust `std::thread` and tokio, Java `java.util.concurrent`, C# `Task` | Section 4. |
| Test utilities | see section 14 | |

Questions:

- [ ] Which standard library modules does the source import (the survey lists
  them)? For each: a target built-in, a dependency (section 13), or nothing?
- [ ] For each mapped module, which behaviors do the fixtures touch, and has a
  probe shown that they match? The Notes column lists the usual differences.
- [ ] Which source modules have no target equivalent? Each becomes a helper
  unit in the layer that owns it.
- [ ] Does any target built-in need a newer runtime than the minimum the port
  supports?

Universal traps: T7, T8 and T26 (sorting), T19, T27, T46 and T47 (JSON),
T50 (paths).

Record: the filled table in `strategy.md`, one row per imported source
module, with the probe for every difference the fixtures touch.

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

This file cannot name packages for an unknown target, so each row names a
category, examples from several ecosystems, and how to choose. Decision
hints: "use the platform" (the target's standard library covers it), "map"
(pick the closest maintained package), "rewrite narrowly" (port only the
functions the source uses), "drop" (the target does not need it), "no fair
equivalent" (redesign that part and record it).

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |
| HTTP clients (requests, httpx, axios, Guzzle, Faraday, OkHttp) | outgoing HTTP | the target's built-in client (`fetch`, Go `net/http`, Java `HttpClient`, C# `HttpClient`), else its most used client | use the platform | Default timeouts differ (httpx 5 seconds; Go's default client none; Node `fetch` waits 300 seconds for headers, the undici default), as do redirects, body charset decoding, and whether 4xx and 5xx raise. |
| Data models and validation (pydantic, marshmallow, zod, Joi, dry-validation) | parsing input into typed records | the target's main schema library, or typed decoding (serde, struct tags) | map | Coercion rules (`"1"` to `1`) and error shapes and messages differ. |
| JSON Schema validators | validating documents | a validator for the same draft | map | `format` checking is optional in the spec and off or partial by default in many validators; align both sides. |
| CLI frameworks (click, typer, commander, Thor, cobra, clap, picocli) | command-line interfaces | the target's common framework | map | Exit codes for usage errors, help text, option syntax. |
| Terminal styling and progress (rich, chalk, colorama, tqdm) | output decoration | small libraries or none | rewrite narrowly | Rarely contract. Respect `NO_COLOR` and TTY detection. |
| YAML (PyYAML, Psych, js-yaml, yaml, SnakeYAML, go-yaml) | config files | a parser with the same YAML version | map | YAML 1.1 and 1.2 disagree: Ruby `YAML.load("[010, yes, on]")` is `[8, true, true]`; npm `yaml` and `js-yaml` give `[10, "yes", "on"]` (checked). |
| TOML (tomllib, toml, BurntSushi/toml, toml-rs) | config files | a TOML 1.0 parser | map | Older parsers predate TOML 1.0; date-time types differ. |
| Templating (Jinja2, ERB, Handlebars, Twig, Go `text/template`) | text and HTML generation | the closest syntax family | map or rewrite narrowly | Autoescaping defaults, whitespace control, and undefined variables (error or empty) differ. |
| Date helpers (python-dateutil, moment, Carbon, pytz, arrow) | parsing and zone handling | the platform API or one date library | use the platform | Guessing parsers accept different inputs; write explicit parsers for the formats fixtures contain. |
| HTML parsing (beautifulsoup4, cheerio, Nokogiri, jsoup, goquery) | scraping and queries | an HTML5-algorithm parser | map | The tree depends on the parser; malformed input differs most. |
| XML (lxml, Nokogiri, ElementTree, JAXP) | XML processing | the platform parser or a full library | map | Namespaces, whitespace text nodes, entity expansion (disable for untrusted input). XSLT and schema validation rarely have equivalents. |
| Numeric arrays and dataframes (numpy, pandas) | vectorized math, tables | typed arrays and loops, or a dataframe library | no fair equivalent | Fixed-width dtypes, NaN handling, and float32 rounding must be recorded in fixtures. |
| SQL toolkits and ORMs (SQLAlchemy, ActiveRecord, Hibernate, Eloquent) | database access | a query builder for the core layer, an ORM for the model layer | map by layer | Session, lazy loading and transaction semantics differ; generated SQL differs. |
| Database drivers | database access | the target's main driver | map | Placeholder style (`?`, `$1`, `%s`, `:name`) and conversion of decimals, dates and booleans. |
| Retry libraries (tenacity, retrying, p-retry, retriable) | retries with backoff | a retry library or a small loop | map | Defaults differ: a bare tenacity `@retry` retries forever without waiting. Set limits explicitly on both sides. |
| Caches (cachetools, lru-cache, Caffeine) | memoization | a cache library or a map | map | Key equality (T39), eviction order, TTL clock. |
| Transliteration and slugs (Unidecode, any-ascii, stringex) | ASCII text | a transliteration library | map | Per-character tables differ; diff outputs over the fixture alphabet. Check licenses. |
| Encoding detection (chardet, charset-normalizer) | guessing encodings | a detector port | map | Guesses and confidence values differ; never treat a guess as a fixture value without review. |
| Markdown (Python-Markdown, markdown-it, CommonMarker, goldmark) | Markdown to HTML | a CommonMark implementation | map | HTML output differs between implementations, even CommonMark ones, in edge cases. |
| Dependency injection and plugin frameworks | wiring | constructors and explicit registration | rewrite narrowly | |
| Async runtimes (gevent, eventlet, EventMachine) | concurrency | the target's native model | drop | The concurrency model changes (section 4). |
| Compatibility shims (six, polyfills, backports) | old runtime support | none | drop | |

Questions:

- [ ] For each source dependency, which functions does the code actually use?
  A small used surface favors "rewrite narrowly".
- [ ] Does the target's standard library cover that surface?
- [ ] For each candidate: is it maintained, is its license compatible, does it
  support the target runtime version and module format, and how many
  transitive dependencies does it bring?
- [ ] Do the candidate's defaults (timeouts, coercion, YAML version, escaping,
  autoescaping) match the source library's, or must the port set them?
- [ ] Is any output of the dependency observable in fixtures (rendered HTML,
  parsed YAML, transliterated text)? Each one needs a diff test over the
  fixture inputs.

Universal traps: most problems here are library defaults rather than language
rules (see the Notes column); T46 and T47 apply to every JSON library.

Record: one decision per source dependency in `strategy.md` (decision hint,
candidate packages, defaults the port must set explicitly). The confirmed
choice goes into `deps.json` only after the `scout` agent has checked it.

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | the runner the source suite uses | the target ecosystem's default runner (table below) |
| Assertions and fixtures | source assertion style, setup and teardown, shared fixtures | the target's assertions; setup and teardown hooks; fixture files loaded the same way the fixture harness loads them |
| Parametrized tests | `parametrize`, `each`, data providers, table-driven tests | the target's table-driven form |
| Property tests | the source's property library | the target's property library (table below), with generators covering the same domain |
| Mocks and time | the source's mocks, clock control | injected dependencies first; the target's mocking and fake clock only where injection is impossible |
| Lint | the source linter | the target's standard linter (table below) |
| Format | the source formatter | the target's standard formatter |
| Type check | the source type checker, if any | the compiler or the target's type checker in strict mode |
| Coverage | the source coverage tool | the target coverage tool |

Common tools per language:

| Language | Test runner | Property tests | Lint | Format | Type check | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| Python | pytest | hypothesis | ruff, pylint | ruff format, black | mypy, pyright | coverage.py |
| JavaScript, TypeScript | vitest, jest, `node:test` | fast-check | eslint, biome | prettier, biome | `tsc` | `@vitest/coverage-v8`, c8 |
| Go | `go test` | rapid, gopter | `go vet`, staticcheck, golangci-lint | gofmt | compiler | `go test -cover` |
| Rust | `cargo test` | proptest, quickcheck | clippy | rustfmt | compiler | cargo-llvm-cov, tarpaulin |
| Java | JUnit 5 | jqwik | Error Prone, SpotBugs, PMD, Checkstyle | google-java-format, Spotless | compiler | JaCoCo |
| Kotlin | JUnit 5, Kotest | Kotest property testing | detekt, ktlint | ktlint, ktfmt | compiler | Kover, JaCoCo |
| C# | xUnit, NUnit, MSTest | FsCheck, CsCheck | .NET analyzers | `dotnet format`, CSharpier | compiler | coverlet |
| Ruby | RSpec, minitest | prop_check | RuboCop | RuboCop, standard | Sorbet, Steep | SimpleCov |
| PHP | PHPUnit, Pest | Eris | PHPStan, Psalm, PHP_CodeSniffer | PHP-CS-Fixer | PHPStan, Psalm | Xdebug or PCOV with PHPUnit |
| Elixir | ExUnit | StreamData | Credo | `mix format` | Dialyzer | `mix test --cover` |
| Swift | XCTest, Swift Testing | SwiftCheck | SwiftLint | swift-format, SwiftFormat | compiler | `swift test --enable-code-coverage` |
| C++ | GoogleTest, Catch2 | RapidCheck | clang-tidy | clang-format | compiler | gcov, llvm-cov |
| Perl | Test::More with prove | none common | Perl::Critic | perltidy | none | Devel::Cover |

Questions:

- [ ] Which runner, assertion style and fixture loading does the target use,
  and how does the fixture harness for the target plug into it?
- [ ] Which source tests use property-based generators, and which target
  generators cover the same domain? Default string generators often produce
  only ASCII, and default integer generators are often 32-bit; check both.
- [ ] Do float comparisons in source tests use a tolerance, and with which
  rule (relative, absolute, decimal places)?
- [ ] Do source tests depend on the environment (time zone, locale, current
  directory, environment variables, network)? Pin the same values for the
  target run.
- [ ] Which source tests check things the target's type system now rules out?
  Mark them out of scope with that reason.

Universal traps: T18 and T28 show up first in tests run on a developer machine
with a different locale or zone.

Record: the tool for each concern in the table above, the commands to run
them, and the pinned environment (`TZ`, `LANG` or `LC_ALL`, and anything else
the fixtures need), plus one planned extra run with a non-UTC zone and a
non-English locale.

## 15. Known traps

Each trap below applies to most pairs. One entry per trap, in the template's
shape.

Questions:

- [ ] Does the trap apply to this pair? Run its Detect input on both
  runtimes, translated into the pair's languages if neither appears in the
  line.
- [ ] Which units in the plan carry the trap's tags?

Universal traps: all of the entries below.

Record: the probe result and the port rule, adapted to the pair, in the idiom
map row for that area. Keep traps that do not apply in the map too, with the
probe that showed it, so nobody checks them again.

### T1. String length counts different units

- Tags: `unicode`
- Source behavior: length is counted in code points (Python, Ruby), UTF-16 code units (JS, Java, C#), UTF-8 bytes (Go `len`, Rust `.len()`), or grapheme clusters (Swift `count`).
- Target behavior: a direct translation of `len` or `length` counts in the target's unit and gives a different number for any character outside the source's single-unit range.
- Detect: `"😀"` (U+1F600): Python `len` 1, Ruby `length` 1, Swift `count` 1; JS `length` 2, C# `Length` 2; Go `len` 4, Rust `.len()` 4.
- Port rule: decide which unit every public length, offset and index uses (the source's, unless the contract says otherwise) and count in that unit through a helper. Add a fixture with an astral character such as an emoji.

### T2. Indexing and slicing can split a character

- Tags: `unicode`
- Source behavior: Python slices code points: `"😀"[0:1]` is `"😀"`.
- Target behavior: slicing in UTF-16 or UTF-8 units can cut through a character, producing a lone surrogate, a broken byte sequence, or a panic.
- Detect: the first character of `"😀"`: Python `s[0:1]` is `"😀"`; JS `s.slice(0, 1)` is the lone surrogate `"\ud83d"`; Go `s[0]` is the byte `240`; Rust `&s[0..1]` panics because 1 is not a character boundary.
- Port rule: slice through a helper in the source's unit (code point arrays, `chars()`, `[]rune`, `utf8.DecodeRuneInString`), and add a fixture where a cut falls next to an astral character.

### T3. User-perceived characters are grapheme clusters

- Tags: `unicode`
- Source behavior: most languages count code points or code units, so a flag or an accented letter written with a combining mark counts as two or more.
- Target behavior: Swift `String.count` counts extended grapheme clusters; other languages need a segmenter (`Intl.Segmenter`, ICU break iterators, Python `regex` with `\X`).
- Detect: `"🇵🇱"` (two regional indicator symbols): Python `len` 2, JS `length` 4, Swift `count` 1.
- Port rule: keep the source's unit. Switch to grapheme clusters only if the source counted them, and then use a segmenter on both sides of the fixture recorder.

### T4. String equality may or may not normalize

- Tags: `unicode`
- Source behavior: Python, JS, Go, Rust, Java and C# compare strings by their code units or code points, so precomposed and decomposed forms of the same letter are different strings.
- Target behavior: Swift `==` on `String` uses canonical equivalence.
- Detect: `"\u00e9" == "e\u0301"` (precomposed against decomposed `é`): Python `False`, JS `false`; Swift `"\u{e9}" == "e\u{301}"` is `true`.
- Port rule: normalize explicitly (NFC or NFD) at the boundaries where the source normalized, and when porting from Swift, normalize before every comparison, hash and map lookup that relied on `==`.

### T5. Case mapping is not one-to-one

- Tags: `unicode`
- Source behavior: full case mapping can change the length of a string: `"ß"` uppercases to `"SS"`, the ligature `"ﬁ"` to `"FI"`.
- Target behavior: some APIs use simple one-to-one mappings and leave such characters unchanged.
- Detect: `"ß"` uppercased: Python `upper`, JS `toUpperCase`, Ruby `upcase`, Rust `to_uppercase`, Swift `uppercased` give `"SS"`; Go `strings.ToUpper` and C# `ToUpper` and `ToUpperInvariant` give `"ß"`.
- Port rule: test every case function the port uses on `ß`, `ﬁ`, `İ` and Greek final sigma. For case-insensitive comparison, record which folding each side uses (full in Python `casefold`; simple in Go `strings.EqualFold` and C# `OrdinalIgnoreCase`) and write a helper if they differ.

### T6. The current locale changes case mapping

- Tags: `locale`, `unicode`
- Source behavior: Python `upper` and `lower`, Go `strings.ToUpper` and Rust `to_uppercase` ignore the locale.
- Target behavior: C# `ToUpper()` and `ToLower()` and Java `toUpperCase()` and `toLowerCase()` without arguments use the current culture or default locale; JS `toLocaleUpperCase` takes a locale.
- Detect: `"i"` uppercased with the current culture set to `tr-TR`: Python `"i".upper()` is `"I"`; C# `"i".ToUpper()` is `"İ"`; JS `"i".toLocaleUpperCase("tr-TR")` is `"İ"`.
- Port rule: use invariant or ordinal forms (`ToUpperInvariant`, `Locale.ROOT`, `toUpperCase`) for identifiers, keys and protocol text; use a locale only where the source did, and pin it in fixtures.

### T7. Default string ordering: code units against code points

- Tags: `ordering`, `unicode`
- Source behavior: Python, Go, Rust and Ruby order strings by code point (UTF-8 byte order is the same order).
- Target behavior: JS, Java and C# ordinal comparison order by UTF-16 code unit, which puts characters above U+FFFF before U+E000 to U+FFFF.
- Detect: sorting `["\uff5e", "😀"]` (U+FF5E and U+1F600): Python, Go, Rust and Ruby give `["～", "😀"]`; JS `sort()` gives `["😀", "～"]`.
- Port rule: when the target compares UTF-16 units and the order is observable, sort with a code point comparator helper.

### T8. Default string comparison can be culture-aware

- Tags: `ordering`, `locale`
- Source behavior: Python, JS `sort()`, Go and Rust compare strings ordinally by default.
- Target behavior: C# `List<string>.Sort()` and `string.Compare` use the current culture by default, which orders letters alphabetically before case.
- Detect: sorting `["b", "B", "a"]` with the default comparison: Python and JS give `["B", "a", "b"]`; C# `List<string>.Sort()` gives `["a", "b", "B"]`.
- Port rule: pass an ordinal comparer (`StringComparer.Ordinal`, `CompareOrdinal`) unless the source sorted with a collator, and then use the same locale on both sides.

### T9. Null and booleans inside formatted text

- Tags: `nullability`, `float-format`
- Source behavior: each language prints null and booleans its own way: Python `None`, `True`, `False`.
- Target behavior: JS prints `null` or `undefined` and `true`; Ruby prints `nil` as an empty string; C# prints `null` as an empty string and `true` as `True`; Go prints `<nil>`.
- Detect: interpolating a null value: Python `f"{None}"` is `"None"`; JS `` `${null}` `` is `"null"`; Ruby `"#{nil}"` is `""`; C# `$"{null}"` is `""`; Go `fmt.Sprint(nil)` is `"<nil>"`.
- Port rule: route every value that can reach output text through a helper that prints the way the source does, and add fixtures with null and boolean values inside messages.

### T10. Fixed-width integers overflow

- Tags: `numeric`
- Source behavior: Python and Ruby integers are unbounded.
- Target behavior: fixed-width integers wrap silently (Go, C# by default, Java), panic (Rust debug builds), or wrap (Rust release builds).
- Detect: `2147483647 + 1` in a 32-bit integer: Python `2147483648`; Go `int32` and C# `int` give `-2147483648`; Rust `i32` panics in a debug build and gives `-2147483648` in a release build.
- Port rule: choose a width per value domain that holds every value the source can produce; use checked or big-integer arithmetic where source integers are unbounded; copy wrap-around only where the source wrapped on purpose (hashes, checksums, random generators).

### T11. Integers above 2^53 in doubles

- Tags: `numeric`
- Source behavior: Python, Ruby, Go `int64` and Java `long` hold integers above 2^53 exactly.
- Target behavior: JS `number`, Lua numbers before 5.3, and JSON decoders that produce doubles round them.
- Detect: `2**53 + 1`: Python `9007199254740993`; JS `2 ** 53 + 1` is `9007199254740992`.
- Port rule: use 64-bit or big integers for IDs, counters and money in minor units (`bigint` in JS), and decode JSON integers without going through a double (T46).

### T12. Division and modulo of negative numbers

- Tags: `numeric`
- Source behavior: Python and Ruby floor: the remainder has the sign of the divisor.
- Target behavior: Go, Rust, C, Java, C# and JS truncate: the remainder has the sign of the dividend.
- Detect: `-7 / 2` and `-7 % 3` on integers: Python and Ruby give `-4` and `2`; Go, Rust and C# give `-3` and `-1`, as do JS `Math.trunc(-7 / 2)` and `-7 % 3`.
- Port rule: use floor-division and floor-modulo helpers where the source floors. Rust `div_euclid` and `rem_euclid` match floor semantics only for positive divisors: `7.rem_euclid(-3)` is `1` where Python `7 % -3` is `-2`.

### T13. Dividing two integers

- Tags: `numeric`
- Source behavior: in Python 3, JS and Perl, `/` on two integers gives a float.
- Target behavior: in Go, Rust, C#, Java and Ruby, `/` on two integers gives a truncated integer.
- Detect: `7 / 2`: Python, JS and Perl give `3.5`; Go, Rust, C# and Ruby give `3`.
- Port rule: map each `/` by the types of its operands, not by its spelling. Python `//` becomes floor division (T12), not the target's `/`.

### T14. The default rounding mode

- Tags: `numeric`, `float-format`
- Source behavior: Python `round` and C# `Math.Round` round ties to even.
- Target behavior: JS `Math.round` rounds ties toward positive infinity; Go `math.Round`, Rust `round`, Ruby `round` and Swift `rounded()` round ties away from zero.
- Detect: rounding `2.5` and `-2.5`: Python and C# give `2` and `-2`; JS gives `3` and `-2`; Go, Rust, Ruby and Swift give `3` and `-3`.
- Port rule: name the source's mode in the idiom map and call a target function that implements it (`math.RoundToEven`, `f64::round_ties_even`, `MidpointRounding.ToEven`, Ruby `round(half: :even)`) or a tested helper.

### T15. Float to string

- Tags: `float-format`
- Source behavior: the shortest round-trip digits are the same almost everywhere; the decoration differs. Python, Ruby and Swift keep a `.0` on whole numbers.
- Target behavior: JS, Go, C# and Rust `Display` drop it. Exponent form differs: `1e21` prints as `1e+21` in Python, JS, Go and Swift, `1.0e+21` in Ruby, `1E+21` in C#, and `1000000000000000000000` in Rust. JS prints `-0.0` as `0`; the others keep the sign.
- Detect: `1.0`: Python, Ruby and Swift print `1.0`; JS, Go, C# and Rust print `1`.
- Port rule: write one float-to-text helper that reproduces the source's suffix, exponent threshold and exponent format, and use it wherever a float becomes text, including messages and serialized output.

### T16. Fixed-decimal formatting at ties

- Tags: `float-format`
- Source behavior: `0.125` is exactly representable, so formatting it to two decimals is a true tie. Python `"%.2f"`, Go `%.2f`, Rust `{:.2}` and C# `"F2"` round the exact value half to even and give `"0.12"`.
- Target behavior: JS `toFixed` breaks ties upward. Ruby agrees on `0.125` but its `format("%.2f", 2.675)` is `"2.68"` while Python, Go, Rust and C# give `"2.67"` (2.675 is stored just below the tie), and Ruby `0.125.round(2)` is `0.13`.
- Detect: `0.125` to two decimals: Python, Go, Rust, C# and Ruby give `"0.12"`; JS `(0.125).toFixed(2)` gives `"0.13"`.
- Port rule: do not assume two printf-style formatters agree. Add fixtures for exact ties (`0.125`, `0.375`, `2.5`) and near ties (`2.675`, `1.005`), and use a helper where results differ.

### T17. Lenient number parsing

- Tags: `numeric`, `error-model`
- Source behavior: Python `int` raises on trailing garbage; Go `strconv.Atoi` returns an error; Ruby `Integer()` raises.
- Target behavior: JS `parseInt` and Ruby `to_i` stop at the first bad character and return what they read; JS `Number` returns `NaN`, and `Number("")` is `0`.
- Detect: `"12abc"`: Python `int` raises `ValueError`; Go `strconv.Atoi` returns an error; JS `parseInt` and Ruby `to_i` give `12`; JS `Number` gives `NaN`.
- Port rule: for each parse site, list the syntax the source accepts (sign, whitespace, underscores, leading zeros, non-ASCII digits, prefixes) and validate with an explicit pattern before converting.

### T18. Locale-dependent number formatting and parsing

- Tags: `locale`, `numeric`
- Source behavior: Python `str`, `float` and `int` ignore the locale.
- Target behavior: C# `ToString()` and `double.Parse`, Java `String.format`, and JS `toLocaleString` use the current culture.
- Detect: with the current culture set to `de-DE`: C# `1.5.ToString()` is `"1,5"` and `double.Parse("1.5")` is `15`; Python `str(1.5)` is `"1.5"` under any locale.
- Port rule: use invariant formatting and parsing (`CultureInfo.InvariantCulture`, `Locale.ROOT`) for all machine-readable text; pin the locale in tests and run once more under a non-English locale.

### T19. NaN and infinity in JSON

- Tags: `numeric`, `encoding`
- Source behavior: Python `json.dumps` writes `NaN`, `Infinity` and `-Infinity`, which are not valid JSON.
- Target behavior: JS `JSON.stringify` writes `null`; Go `json.Marshal` returns an error.
- Detect: encoding NaN: Python `json.dumps(float("nan"))` is `NaN`; JS `JSON.stringify(NaN)` is `null`; Go `json.Marshal(math.NaN())` fails with `json: unsupported value: NaN`.
- Port rule: decide in the contract whether NaN and infinity can reach the encoder; either reproduce the source's output with a custom encoder or reject them on both sides.

### T20. `\w`, `\d`, `\s` and `\b` can be ASCII-only

- Tags: `regex`, `unicode`
- Source behavior: Python `str` patterns and .NET use Unicode classes by default.
- Target behavior: JS (even with the `u` flag) and Go use ASCII `\w` and `\b`. Ruby's `\w` is ASCII but its `\b` treats `é` as a word character, so `caf\b` does not match in `"café"`. Java's `\w` is ASCII unless `UNICODE_CHARACTER_CLASS` is set. The Unicode sets differ too: Python `\w` is letters, numbers and underscore; .NET `\w` is letters, nonspacing marks, decimal digits and connector punctuation.
- Detect: `\w+` on `"café"`: Python and C# match `café`; JS, Go and Ruby match `caf`.
- Port rule: never copy `\w`, `\d`, `\s` or `\b` unchanged. Translate each to an explicit class (`[\p{L}\p{N}_]` and the like) after checking the exact set on both sides.

### T21. `$` before a final newline

- Tags: `regex`
- Source behavior: in Python, PCRE, Java and .NET, `$` without multiline mode also matches before a newline at the very end. In Ruby, `^` and `$` always match at every line.
- Target behavior: in JS, Go and Rust, `$` without multiline mode matches only at the end of the input.
- Detect: `^abc$` against `"abc\n"`: Python, Ruby and C# match; JS and Go do not.
- Port rule: translate anchors by meaning. "End of input" is `\Z` in Python, `\z` in Ruby, PCRE, Java, .NET, Go and Rust, and `$` in JS without the `m` flag. "End or before a final newline" needs `(?=\n?$)` in JS.

### T22. Linear-time engines lack lookaround and backreferences

- Tags: `regex`
- Source behavior: backtracking engines support lookahead, lookbehind and backreferences.
- Target behavior: Go `regexp` and Rust `regex` reject them when the pattern is compiled.
- Detect: `(?<=a)b` on `"ab"`: Python finds `"b"`; Go `regexp.Compile` returns an error.
- Port rule: rewrite with capture groups plus code, or use a backtracking library (Go `regexp2`, Rust `fancy-regex`) and record its performance and safety trade-off.

### T23. Replacement template syntax

- Tags: `regex`
- Source behavior: Python uses `\1` and `\g<1>`; JS, Java and .NET use `$1`; Go uses `$1` and `${1}` but reads the longest name after `$`.
- Target behavior: a template copied from another dialect can silently produce wrong text.
- Detect: replacing `(a)` in `"a"` with group 1 followed by `x`: Python `re.sub(r"(a)", r"\1x", "a")` and JS `"a".replace(/(a)/, "$1x")` give `"ax"`; Go `ReplaceAllString("a", "$1x")` gives `""` because it reads `$1x` as a group named `1x`.
- Port rule: translate every template by hand (`${1}x` in Go), and test each one where the group reference is followed by a digit or a letter.

### T24. Map iteration order

- Tags: `ordering`
- Source behavior: Python `dict`, Ruby `Hash` and JS `Map` iterate in insertion order.
- Target behavior: Go `map` and Rust `HashMap` order changes between runs; Java `HashMap` follows hash order; JS plain objects put integer-like keys first.
- Detect: insert `b`, then `a`, then iterate: Python, Ruby and JS `Map` give `b, a`; Go `map` and Rust `HashMap` give a different order from run to run; JS `{ b: 1, 1: 2 }` iterates `1, b`.
- Port rule: use an insertion-ordered structure where order is observable (a key slice in Go, `indexmap` in Rust, `LinkedHashMap` in Java, `Map` in JS), and sort before output where the source sorted.

### T25. Set order and hash randomization

- Tags: `ordering`
- Source behavior: Python sets of strings iterate in hash order, and string hashes are randomized per process unless `PYTHONHASHSEED` is set.
- Target behavior: JS `Set` keeps insertion order, so a port can look deterministic where the source was not.
- Detect: `list({"a", "b", "c", "d", "e", "f"})`: Python prints a different order in each new process; with `PYTHONHASHSEED=0` the order repeats.
- Port rule: if a fixture captured a set's order, that order is accidental. Sort in both the fixture recorder and the port, or record the value as unordered in the contract.

### T26. Sort stability

- Tags: `ordering`
- Source behavior: Python `sorted`, JS `sort` (ES2019 and later), Java object sorts, Rust `sort`, LINQ `OrderBy` and PHP 8 sorts keep equal elements in their original order.
- Target behavior: Go `sort.Slice`, Rust `sort_unstable`, C# `List.Sort` and `Array.Sort`, and Ruby `sort` and `sort_by` do not guarantee it.
- Detect: sorting the 100 pairs `(i % 2, i)` for `i` in 0 to 99 by the first field: Python and JS keep `i` ascending inside each key; Go `sort.Slice`, Rust `sort_unstable_by_key`, C# `List.Sort` and Ruby `sort_by` put a larger `i` before a smaller one.
- Port rule: use the stable variant (`sort.SliceStable`, `slices.SortStableFunc`, `sort_by_key`, `OrderBy`) or add the original index as the last key (Ruby `sort_by.with_index { |x, i| [key(x), i] }`).

### T27. Serialized key order

- Tags: `ordering`, `encoding`
- Source behavior: Python `json.dumps` writes dict keys in insertion order.
- Target behavior: Go `json.Marshal` sorts map keys; struct fields come out in declaration order.
- Detect: encoding `{"b": 1, "a": 2}`: Python gives `{"b": 1, "a": 2}`; Go `json.Marshal` of a `map[string]int` gives `{"a":2,"b":1}`.
- Port rule: when output bytes are compared, reproduce the source's key order (an ordered structure, a struct with fields in order, or an explicit sort) and its spacing (T47).

### T28. Parsing a timestamp without an offset

- Tags: `datetime`
- Source behavior: Python `datetime.fromisoformat` returns a naive datetime that carries no zone.
- Target behavior: JS `new Date` reads a date-time without an offset as local time but a date-only string as UTC; Go `time.Parse` without a zone gives UTC.
- Detect: `"2024-01-01T00:00:00"` with `TZ=America/New_York`: Python gives a naive `datetime(2024, 1, 1, 0, 0)`; JS `new Date(...).toISOString()` is `"2024-01-01T05:00:00.000Z"`; Go gives `2024-01-01 00:00:00 +0000 UTC`.
- Port rule: decide per field whether a value is naive wall time, UTC, or in a named zone, and parse with that zone explicitly. Run the target tests under `TZ=UTC` and once under a zone with DST.

### T29. Epoch units

- Tags: `datetime`
- Source behavior: Python, Ruby, Go `time.Unix` and Unix tools count seconds; Python keeps microseconds.
- Target behavior: JS `Date`, Java `currentTimeMillis` and many JSON APIs count milliseconds; Go `UnixNano` and Java `Instant` go to nanoseconds.
- Detect: `1700000000`: Python `datetime.fromtimestamp(1700000000, timezone.utc)` is 2023-11-14 22:13:20 UTC; JS `new Date(1700000000).toISOString()` is `"1970-01-20T16:13:20.000Z"`.
- Port rule: name the unit in every variable and field that holds epoch time, convert at the boundary, and check that the target type keeps the precision the source keeps.

### T30. Invalid dates roll over

- Tags: `datetime`, `error-model`
- Source behavior: Python `date(2024, 2, 30)` raises `ValueError`.
- Target behavior: Go `time.Date` and JS `Date.UTC` normalize out-of-range fields into the next month. JS months are also numbered 0 to 11.
- Detect: February 30, 2024: Python raises; Go `time.Date(2024, 2, 30, 0, 0, 0, 0, time.UTC)` and JS `new Date(Date.UTC(2024, 1, 30))` both give 2024-03-01.
- Port rule: validate year, month and day ranges before constructing a date wherever the source raised, and convert month numbers at the boundary for JS.

### T31. Adding a day across a DST change

- Tags: `datetime`
- Source behavior: Python adds a `timedelta` to an aware datetime on its wall-clock fields, even for `timedelta(hours=24)`.
- Target behavior: adding milliseconds to a JS `Date` or a `Duration` to an instant adds elapsed time.
- Detect: 2024-03-10 00:00 in America/New_York plus 24 hours: Python gives 2024-03-11 00:00; JS `new Date(d.getTime() + 86400000)` gives 01:00 local time.
- Port rule: for each date operation decide between calendar arithmetic (wall time) and elapsed time, and use the target API for that one (Temporal `add({ days: 1 })` against `add({ hours: 24 })`, `java.time` `plusDays` against `plus(Duration)`). Add a fixture across a DST change.

### T32. Error identity after wrapping

- Tags: `error-model`
- Source behavior: exception languages test the category with `except`, `catch` or `rescue` on a class, which also matches subclasses.
- Target behavior: Go compares error values by identity unless `errors.Is` or `errors.As` unwraps them. In JS, `instanceof` fails when two copies of a package are loaded (duplicate installs, or ESM and CommonJS builds side by side).
- Detect: `err := fmt.Errorf("open x: %w", fs.ErrNotExist)` in Go: `err == fs.ErrNotExist` is `false`; `errors.Is(err, fs.ErrNotExist)` is `true`.
- Port rule: test categories only with the target's category mechanism (`errors.Is` and `errors.As`, one shared error class, a match on an error enum), never with `==` on wrapped values or with message text. Add one test per category in `error-map.json` that passes through a wrapping layer.

### T33. Out-of-range access

- Tags: `error-model`, `nullability`
- Source behavior: Python raises `IndexError`; Go and Rust panic; negative indexes count from the end in Python and Ruby.
- Target behavior: JS returns `undefined` and Ruby returns `nil`; JS `[1, 2][-1]` is `undefined` (`at(-1)` counts from the end).
- Detect: index 5 of a two-element list: Python raises `IndexError`; Go panics with `index out of range [5] with length 2`; JS gives `undefined`; Ruby gives `nil`.
- Port rule: add bounds checks where the source raised, translate negative indexes explicitly, and decide what a missing element becomes in the target.

### T34. Errors in background tasks

- Tags: `error-model`, `async`
- Source behavior: an exception in a Python `asyncio` task that nobody awaits is logged as `Task exception was never retrieved` when the task is collected, and the program continues.
- Target behavior: Node ends the process on an unhandled promise rejection; a panic in any goroutine ends the whole Go program.
- Detect: a background task that raises while nothing waits for it: Python logs the error and exits with status 0; Node exits with status 1; a compiled Go program exits with status 2.
- Port rule: decide per background task whether its error propagates, is logged, or stops the program, attach that handling explicitly (`catch`, `recover` inside the goroutine, checking the join handle), and test it with a failing task.

### T35. Error messages change between versions

- Tags: `error-model`
- Source behavior: messages from the runtime and standard library are not stable across versions, and they differ between languages for the same failure (Python `invalid literal for int() with base 10: '12abc'`; Go `strconv.Atoi: parsing "12abc": invalid syntax`).
- Target behavior: a port that reuses the target's built-in messages, or fixtures recorded on another source version, will not match.
- Detect: `datetime.date(2024, 2, 30)`: Python 3.13 raises `ValueError("day is out of range for month")`; Python 3.14 raises `ValueError("day 30 must be in range 1..29 for month 2 in year 2024")`.
- Port rule: the contract states for each error whether its text is observable. Where it is, build the message in the port's own code with the source's exact text. Otherwise compare only the category in fixtures. Record the source version used to record fixtures.

### T36. Shared mutable default arguments

- Tags: `mutability`
- Source behavior: Python evaluates a default argument once, when the function is defined, so a mutable default is shared by every call. Python class attributes are shared by every instance the same way.
- Target behavior: Ruby, JS, Kotlin and C++ evaluate defaults on each call.
- Detect: `def f(x, acc=[]): acc.append(x); return acc`, called `f(1)` then `f(2)`: Python returns `[1, 2]`; the same function in Ruby (`def f(x, acc = [])`) or JS returns `[2]`.
- Port rule: when the source relies on the sharing (memo tables, registries), make it an explicit module-level value; otherwise create a fresh value per call. Fixtures should call such functions at least twice.

### T37. Slices and views alias their source

- Tags: `mutability`
- Source behavior: Python list slices and JS `Array.prototype.slice` copy.
- Target behavior: Go slices, Rust mutable slices, JS `subarray`, Node `Buffer` slices and numpy slices share memory with the original, and Go `append` can write into the original's spare capacity.
- Detect: `a = [1, 2, 3]; b = a[0:1]; b[0] = 9`: Python leaves `a` as `[1, 2, 3]`; Go `b := a[0:1]; b[0] = 9; b = append(b, 7)` leaves `a` as `[9 7 3]`.
- Port rule: copy explicitly (`slices.Clone`, `to_vec`, `slice()`) wherever the source copied, and in Go use a full slice expression (`a[0:1:1]`) when the result will be appended to.

### T38. Value against reference semantics on assignment

- Tags: `mutability`
- Source behavior: in Python, JS, Ruby and Java, assigning an object shares it.
- Target behavior: Swift arrays, dictionaries, strings and structs, Go arrays and structs, and C# structs are copied on assignment. Go slices and maps are shared.
- Detect: `a = [1]; b = a; b.append(2)`: Python `a` is `[1, 2]`; Swift `var b = a; b.append(2)` leaves `a` as `[1]`.
- Port rule: map each source type deliberately in section 1: objects mutated through several references become reference types (classes, pointers), plain values become value types.

### T39. Equality of compound values

- Tags: `mutability`
- Source behavior: Python and Ruby `==` compare lists, dicts and tuples by content.
- Target behavior: JS `===` and Java `==` compare identity; Go does not allow `==` on slices or maps at all. Map keys and set members follow the same rule, so a compound key can never be found again in a JS `Map`.
- Detect: `[1, 2] == [1, 2]`: Python and Ruby give `true`; JS `[1, 2] === [1, 2]` is `false`; Go `a == b` on two `[]int` fails to compile.
- Port rule: write equality helpers for compound values used in comparisons, `in` tests, `indexOf`, deduplication and map keys; encode compound keys as strings or use value types that compare by content.

### T40. Missing map keys

- Tags: `nullability`, `error-model`
- Source behavior: Python `d[k]` raises `KeyError`; C# throws `KeyNotFoundException`.
- Target behavior: Ruby returns `nil`, JS returns `undefined`, and Go returns the zero value.
- Detect: looking up `"x"` in an empty map: Python raises `KeyError`; C# throws `KeyNotFoundException`; Ruby gives `nil`; JS gives `undefined`; Go `v, ok := m["x"]` gives `0` and `false`.
- Port rule: use the two-result lookup (`v, ok := m[k]`, `TryGetValue`, `has`, `key?`) wherever the source distinguished missing from present, and raise where the source raised.

### T41. Absent fields decode to zero values

- Tags: `nullability`
- Source behavior: Python `json.loads` keeps exactly the keys present.
- Target behavior: Go and C# decoding into a struct or class fills absent fields with zero or default values, so absent, null and zero look the same.
- Detect: decoding `{}` into `struct{ N int }`: Go gives `N == 0`, the same as decoding `{"N": 0}`; Python `json.loads("{}")` has no `"N"` key.
- Port rule: use pointer or optional field types (`*int`, `Option<i32>`, `int?`) where absence matters, or decode into a generic map first. Fixtures need the field missing, null and zero.

### T42. Absent, null and undefined in serialization

- Tags: `nullability`, `encoding`
- Source behavior: Python `json.dumps` writes `None` as `null` and keeps the key.
- Target behavior: JS `JSON.stringify` drops properties whose value is `undefined`; Go `omitempty` drops zero values (`0`, `""`, `false`, nil pointers, empty slices and maps).
- Detect: a record whose field is unset: Python `json.dumps({"a": None})` is `{"a": null}`; JS `JSON.stringify({ a: undefined })` is `{}`.
- Port rule: map each source kind of absence to a target value that encodes the same way, and test missing, null and zero fields in output fixtures.

### T43. Truthiness

- Tags: `nullability`
- Source behavior: Python treats `0`, `""`, empty containers and `None` as false.
- Target behavior: JS treats `[]` and `{}` as true; Ruby treats everything except `nil` and `false` as true, including `0` and `""`; Perl treats `"0"` as false but `"0.0"` as true; Go, Rust, Java and C# require a boolean.
- Detect: `0`, `[]`, `""` and `"0"` as conditions: Python gives false, false, false, true; JS gives false, true, false, true; Ruby gives true for all four.
- Port rule: translate every condition on a non-boolean into an explicit test (`len(x) > 0`, `x != nil`, `x !== ""`) that states what the source checked.

### T44. Invalid UTF-8

- Tags: `encoding`, `unicode`
- Source behavior: Python `bytes.decode` and Rust `str::from_utf8` reject invalid input.
- Target behavior: JS `TextDecoder` replaces bad bytes with U+FFFD by default; Go keeps them in the string and only notices on iteration or with `utf8.Valid`.
- Detect: the single byte `0xFF` decoded as UTF-8: Python raises `UnicodeDecodeError`; Rust returns `Err`; JS `new TextDecoder().decode(Uint8Array.of(0xff))` is `"\ufffd"`; Go `string([]byte{0xff})` has `len` 1, `utf8.ValidString` is `false`, and `range` yields U+FFFD.
- Port rule: decode strictly (`fatal: true`, `from_utf8`, a `utf8.Valid` check) where the source raised and with replacement where it replaced; test truncated, overlong and surrogate sequences.

### T45. Byte order marks

- Tags: `encoding`
- Source behavior: Python `decode("utf-8")` keeps a leading BOM as U+FEFF; `"utf-8-sig"` strips it.
- Target behavior: JS `TextDecoder` strips it by default; Go and Rust keep it.
- Detect: bytes `EF BB BF 61`: Python `decode("utf-8")` gives a 2-character string starting with U+FEFF; JS `new TextDecoder().decode(...)` gives `"a"`.
- Port rule: strip a BOM only where the source did, and in JS pass `ignoreBOM: true` to keep it.

### T46. JSON number fidelity

- Tags: `encoding`, `numeric`
- Source behavior: Python `json.loads` reads integers as unbounded `int`.
- Target behavior: JS `JSON.parse` and Go decoding into `interface{}` read every number as a double.
- Detect: `12345678901234567890`: Python gives `12345678901234567890`; JS `JSON.parse` gives `12345678901234567000`; Go `json.Unmarshal` into `interface{}` gives `1.2345678901234567e+19`.
- Port rule: decode into exact types (typed struct fields, Go `Decoder.UseNumber`, a lossless JSON parser in JS) and add a fixture above 2^53.

### T47. JSON spacing and escaping

- Tags: `encoding`
- Source behavior: Python `json.dumps` writes `", "` and `": "` separators and escapes non-ASCII characters by default.
- Target behavior: JS and Go write compact output and keep non-ASCII characters; Go escapes `<`, `>` and `&` for HTML safety.
- Detect: encoding the string `"<é>"`: Python gives `"<\u00e9>"`; JS gives `"<é>"`; Go `json.Marshal` gives `"\u003cé\u003e"`.
- Port rule: when JSON text is compared byte for byte, configure the target encoder (separators, ASCII escaping, Go `SetEscapeHTML(false)`) or write a small encoder, and add a fixture with non-ASCII and HTML characters.

### T48. Newline translation in text mode

- Tags: `io`
- Source behavior: Python text-mode reads turn `\r\n` and `\r` into `\n`, and text-mode writes on Windows turn `\n` into `\r\n`.
- Target behavior: Node, Go, Rust, Java and C# read files as stored.
- Detect: a file containing `a\r\nb`: Python `open(p).read()` gives `"a\nb"`; Node `readFileSync(p, "utf8")` gives `"a\r\nb"`.
- Port rule: normalize newlines on read wherever the source read in text mode, and on write when the source targets Windows.

### T49. Default text encoding comes from the locale

- Tags: `io`, `encoding`, `locale`
- Source behavior: Python `open()` without `encoding=` uses the locale's encoding unless UTF-8 mode is on (`-X utf8`, `PYTHONUTF8=1`). Older Java versions behave the same way.
- Target behavior: Node, Go and Rust treat file contents as UTF-8 when asked for text.
- Detect: reading a UTF-8 file containing `café` with `LC_ALL=en_US.ISO8859-1`: Python 3.14 `open(p).read()` gives `"cafÃ©"` (5 characters); Node `readFileSync(p, "utf8")` gives `"café"`.
- Port rule: find out which encoding the source used in production, state it in the contract, and pass it explicitly on both sides, including in the fixture recorder.

### T50. Joining a path with an absolute component

- Tags: `io`
- Source behavior: Python `os.path.join`, Rust `Path::join` and C# `Path.Combine` discard everything before an absolute component.
- Target behavior: Node `path.join`, Go `filepath.Join` and Ruby `File.join` concatenate.
- Detect: joining `"a"` and `"/b"`: Python, Rust and C# give `"/b"`; Node, Go and Ruby give `"a/b"`.
- Port rule: check for absolute components explicitly wherever the source's behavior is observable; it is often a security boundary (path traversal), so add a fixture.

### T51. Unset against empty environment variables

- Tags: `io`, `nullability`
- Source behavior: Python `os.environ.get("X")` returns `None` when `X` is unset and `""` when it is empty.
- Target behavior: Go `os.Getenv` returns `""` for both.
- Detect: reading an unset `X`: Python gives `None`; Go `os.Getenv("X")` gives `""`.
- Port rule: use the lookup that tells the two apart (`os.LookupEnv`, Rust `std::env::var` returning `Err`) wherever the source did.

### T52. Eager against lazy start of async work

- Tags: `async`
- Source behavior: calling a Python coroutine function creates a coroutine object; its body does not run until it is awaited or scheduled.
- Target behavior: calling a JS or C# async function runs its body synchronously up to the first `await`.
- Detect: an async function that appends `"body"` to a list, called and then followed by appending `"after call"` before awaiting: Python gives `after call, body`; JS gives `body, after call`.
- Port rule: where the order of side effects is observable, start the work where the source started it (call it later, or wrap it in a function) and add a test that checks the order.

### T53. Reflection-based serialization uses target names

- Tags: `reflection`
- Source behavior: Python serializers that read `vars(obj)` or `__dict__` use attribute names as written and in assignment order.
- Target behavior: Go `encoding/json` uses exported field names (capitalized) in declaration order and skips unexported fields; other reflection-based serializers apply their own naming policies.
- Detect: an object with one field `name` set to `"x"`: Python `json.dumps(vars(obj))` gives `{"name": "x"}`; Go `json.Marshal(struct{ Name string }{"x"})` gives `{"Name":"x"}`.
- Port rule: declare every wire name explicitly (Go struct tags, serde `rename`, `[JsonPropertyName]`, Jackson `@JsonProperty`), keep field order where output bytes are compared, and add a round-trip fixture per serialized type.
