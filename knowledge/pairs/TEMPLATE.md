# <Source> to <Target>

| Field | Value |
| --- | --- |
| Source | <language and versions covered, for example Python 3.9 to 3.13> |
| Target | <language, versions and runtime, for example TypeScript 5.x on Node 20+> |
| Status | full / stub |
| Last reviewed | YYYY-MM-DD |

How to use this file: the `strategy` skill loads it to seed the idiom map for a
port, and the `implement` skill reads the sections a unit's risk tags point at.
Every trap carries risk tags from this vocabulary, which `porter.py decompose`
also emits for units:

`regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`,
`unicode`, `encoding`, `io`, `locale`, `mutability`, `nullability`,
`error-model`, `ordering`.

## 1. Type system mapping

Primitives, collections, optional values, unions, generics, structural versus
nominal typing. A table of source type to target type, then the rules that do
not fit a table.

## 2. Error model

Exceptions versus results, hierarchy, chaining, stack traces, and how a source
error category maps to a target error category. The port records the final
mapping in `.porter/contract/error-map.json`; this section gives the default.

## 3. Null and absence

## 4. Concurrency and async

Threads, event loops, promises, cancellation, blocking calls.

## 5. Iteration, generators, laziness

## 6. Numeric semantics

Integer width and overflow, float formatting, division and modulo, big
integers, decimals, NaN and infinity, rounding modes.

## 7. Strings, bytes, unicode, encodings

String model (code points, UTF-16 units, bytes), normalization forms, case
mapping, slicing and length, byte buffers.

## 8. Dates, times, timezones

## 9. Regex dialect

Syntax and semantic differences, flags, unicode classes, lookbehind, named
groups, replacement string syntax.

## 10. I/O, paths, process, environment

## 11. Module layout, packaging, naming, visibility

## 12. Standard library equivalence

| Source | Target | Notes |
| --- | --- | --- |

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | | |
| Assertions and fixtures | | |
| Lint | | |
| Format | | |
| Type check | | |
| Coverage | | |

## 15. Known traps

One entry per trap, in this shape:

### T1. <short title>

- Tags: `unicode`, `regex`
- Source behavior: <what the source does>
- Target behavior: <what a naive port does>
- Detect: <one input and the output that distinguishes the two>
- Port rule: <what the port must do instead>
