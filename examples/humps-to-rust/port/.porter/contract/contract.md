# Contract: pyhumps 3.8.0

The port must reproduce the return values of the ten exported functions of pyhumps 3.8.0 (commit
`dc56af8dff5c`): six converters between snake_case, camelCase, PascalCase and kebab-case, and four
`is_*case` predicates, on strings and on JSON-shaped nested dicts and lists (`serde_json::Value` in the
crate, per the user's decision). The observation boundary is the return value; nothing else is observable
(no I/O, no global state, no errors on JSON input). The confidence is high for ASCII identifiers and
JSON payloads: 133 harvested reference-test cases all reproduce, and 4454 hand-written and seeded cases
cover what the tests leave out (whitespace, Unicode case rules, numbers, scalars, collisions, large and
deep input). Unicode behavior is pinned to CPython 3.14.6 with Unicode 16.0.0.

## Public surface

The package root `humps` re-exports the ten functions from `humps.main` (`humps/__init__.py` `__all__`).
Fixture call ids keep the Python ids `humps.main:<name>`; the Rust bindings translate them to the crate's
names. The crate should expose all ten at its root.

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| humps.main:camelize | function | `camelize(str_or_iter)` | cycle-humps | yes | returns str, list, dict or the input unchanged |
| humps.main:pascalize | function | `pascalize(str_or_iter)` | cycle-humps | yes | goes through camelize, so `pascalize("a_b") == "A_B"` |
| humps.main:kebabize | function | `kebabize(str_or_iter)` | cycle-humps | yes | two paths: lowercased split, or separator rewrite keeping case |
| humps.main:decamelize | function | `decamelize(str_or_iter)` | cycle-humps | yes | acronyms first, then split before ASCII capitals, lowercase |
| humps.main:depascalize | function | `depascalize(str_or_iter)` | cycle-humps | yes | alias of decamelize |
| humps.main:dekebabize | function | `dekebabize(str_or_iter)` | cycle-humps | yes | `-` to `_`, no case change |
| humps.main:is_camelcase | function | `is_camelcase(str_or_iter) -> bool` | cycle-humps | yes | `x == camelize(x)` |
| humps.main:is_pascalcase | function | `is_pascalcase(str_or_iter) -> bool` | cycle-humps | yes | `x == pascalize(x)` |
| humps.main:is_kebabcase | function | `is_kebabcase(str_or_iter) -> bool` | cycle-humps | yes | `x == kebabize(x)` |
| humps.main:is_snakecase | function | `is_snakecase(str_or_iter) -> bool` | cycle-humps | yes | False if kebab and not camel, else `x == decamelize(x)` |
| humps.main:ACRONYM_RE | constant | `re.compile(r"([A-Z\d]+)(?=[A-Z\d]\|$)")` | - | no: not exported or documented; lookahead cannot be a `regex::Regex`; ported as private code | |
| humps.main:PASCAL_RE | constant | `re.compile(r"([^\-_]+)")` | - | no: not exported; private in the port | |
| humps.main:SPLIT_RE | constant | `re.compile(r"([\-_]*[A-Z][^A-Z]*[\-_]*)")` | - | no: not exported; private in the port | |
| humps.main:UNDERSCORE_RE | constant | `re.compile(r"(?<=[^\-_])[\-_]+[^\-_]")` | - | no: not exported; lookbehind cannot be a `regex::Regex`; private in the port | |
| humps.main:StrOrIter | type | `TypeVar(bound=Union[str, Mapping, list])` | - | no: exists only in `humps/main.pyi`, not at runtime | |
| humps:`__title__`, `__version__`, `__author__`, `__license__`, `__copyright__` | constant | `str` | - | no: package metadata; Cargo.toml carries it | |

The four regex constants are out of scope for the crate's public API only. Their patterns are the core of
the implementation (`humps/main.py:8-11`) and must be ported as private code. In final mode,
`porter decompose` drops out-of-scope symbols from unit closures, so the strategy phase will not see them
listed under the unit.

The private helpers `_is_none`, `_process_keys`, `_fix_abbreviations` and `_separate_words` are not public
surface and are not in api.json. `tests/test_separate_words.py` tests `_separate_words` directly (20 cases).
Its exact output is part of the tested contract, but no fixture can call it, because the Rust harness only
reaches the crate's public API (see the unit contract).

## Semantics the tests promise and the docs omit

Promised by the reference tests:

- Acronyms: `decamelize("APIResponse") == "api_response"`, `"PERatio" -> "pe_ratio"`, `"BIP72b" -> "bip72b"`,
  `"B52Thing" -> "b52_thing"`, `"memMB" -> "mem_mb"`, `"_itemID" -> "_item_id"`. `ACRONYM_RE` matches are
  title-cased first, and `str.title` restarts after a digit (`"MB2X" -> "Mb2X"`).
- Edge separators survive and inner runs collapse: `camelize("__scrubber_media___url_") == "__scrubberMediaUrl_"`,
  `camelize("_url__") == "_url__"`.
- All-uppercase input comes back unchanged from every converter (`"API"`, `"_API_"`, `"BIP73"`).
- Digits after separators: `camelize("whatever_10") == "whatever10"`, `camelize("test-1-2-3-4-5-6") == "test123456"`.
- `None` gives `""` (camelize, pascalize). Non-negative ints come back unchanged (`camelize(1234) == 1234`).
- Containers: only dict keys change. Values are never converted (`"test_upper"` stays), lists and dicts
  nested in values are walked, and float values pass through.
- kebabize keeps case on the separator path (`"scrubber_Media_Url" -> "scrubber-Media-Url"`) and
  lowercases on the camel/pascal path (`"APIResponse" -> "api-response"`). dekebabize never changes case.
- Predicates: `"API"` satisfies all four, and `"whatever_10"` is snake only.

Not tested, but observable and recorded:

- Ordering: output dicts keep input key order. On a key collision, the first position is kept and the last
  value wins (`{"a_b": 1, "x": 0, "aB": 2} -> {"aB": 2, "x": 0}`).
- The early return gives back the original input with its whitespace: `camelize("HELLO WORLD") == "HELLO WORLD"`,
  but `kebabize("HELLO WORLD") == "HELLOWORLD"` (kebabize has no isupper early return).
- Strings inside lists are not converted: `camelize(["a_b"]) == ["a_b"]`.
- Odd but real: `pascalize("a_b") == "A_B"`, `decamelize("a_B") == "a__b"`, `kebabize("HELLO world") == "hell-oworld"`,
  `camelize("A_b") == "AB"`.
- Scalars go through `str()`: `camelize(True) == "true"`, `camelize(-5) == "-5"`, `dekebabize(-5) == "_5"`,
  `camelize(1e-05) == "1e05"`.
- Idempotence: on all 2499 distinct strings in the corpus, each converter is idempotent (`f(f(s)) == f(s)`).
  Round trips are not: `decamelize(camelize(s)) != s` for 86 corpus strings that satisfy `is_snakecase`.
- Identity: the input is never mutated. The early return hands back the same object (free to clone in Rust).
- Locale, timezone, encoding: none apply. Case mapping is locale-independent full Unicode mapping.
- Error types and messages: none. No input that JSON can carry makes any function raise.

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| (none on JSON input) | every fixture outcome is a value | not applicable |
| RecursionError | lists/dicts nested deeper than about 990 levels; not recorded | strategy decision (leak `recursion-depth`) |

No `error-map.json` is written: the source raises nothing that a fixture records, so there is no category to
map. If the strategy makes the Rust API reject top-level scalars, those cases become declared divergences:
their oracle outcome is a value, so an error map cannot make them equivalent.

## Leak list

Internals that leak into observable behavior and must be preserved or consciously diverged from. The full
text, with examples, is in `api.json` `leaks`.

- `dict-order-and-collisions` (preserve): insertion order, first position and last value on collision. Parity
  does not check object key order (parity.py:93), so a Rust unit test must cover it.
- `string-path-for-scalars` (strategy decision): None, bool, int and float at top level go through `str()`.
  Non-negative ints come back as ints, negative ints and floats as strings. Fixtures are tagged
  `strategy-decision` (94 hand-written plus 6 harvested).
- `float-repr` (strategy decision): Python `repr` of floats (`1e-05`, `1e+16`, `1.0`) is visible on the
  string path (pair trap T4).
- `early-return-original` (preserve): the `isupper`/`isnumeric` early returns use Python's Unicode
  definitions. `isnumeric` includes 91 Han numerals (`三`) that `char::is_numeric` misses, and `isupper`
  rejects titlecase letters (`ǅ`).
- `whitespace-stripping` (preserve): every Python `\s` character is deleted, including U+001C..U+001F
  (outside Unicode White_Space). Dict keys can collide as a result.
- `unicode-case-mapping` (preserve): full mappings change length (`ß -> SS`, `İ -> i̇`). Whole-string
  lowercasing applies Final_Sigma. Indexing is by code point (pair trap T3).
- `ascii-split-unicode-predicates` (preserve): `[A-Z]` is ASCII-only while `\d` is Unicode Nd and the string
  predicates are Unicode-aware.
- `unicode-version` (preserve): recorded on Unicode 16.0.0; other versions can flip generated cases.
- `strings-in-lists-untouched` (preserve): only keys convert.
- `unrepresentable-inputs` (known divergence, excluded from fixtures): non-str dict keys, tuples, sets,
  bytes, Mapping subclasses, ints beyond 64 bits, NaN/Infinity and lone surrogates. I chose to keep these out
  of the fixtures and to record their probed Python behavior in `api.json` as known divergences.
- `recursion-depth` (strategy decision): Python fails at about 990 levels with a catchable error. A
  recursive Rust walker aborts on stack overflow.

Free to differ:

- helper names and structure, and whether regexes are used at all
- the regex constants (private, compiled once or not at all)
- module layout and function names (bindings translate the call ids)
- object identity and cloning, provided the input is not mutated
- argument and return types (`&str` and `serde_json::Value` entry points), and the type stubs
- performance and allocation

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| cycle-humps | return values (strings, bools, ints, JSON objects and arrays) | none. Parity compares objects order-insensitively by design, so key order is checked by a unit test instead |

## Fixtures

```text
| Unit | Files | Cases | Kinds | Origins |
| --- | --- | --- | --- | --- |
| cycle-humps | 1 | 4587 | value 4587 | generated 2720, hand-written 1734, reference-test 133 |
```

Recorded by `.porter/oracle/driver/oracle.py` (a copy of the plugin's Python driver) under CPython 3.14.6
(Unicode 16.0.0) on 2026-10-20, from the source checkout at `dc56af8dff5c` with no local changes. 0 error
outcomes. `porter fixtures validate`: 0 errors.

- Harvested (133): every assertion and parametrized row in `tests/test_camelize.py`, `test_decamelize.py`,
  `test_dekebabize.py`, `test_humps.py`, `test_kebabize.py` and `test_pascalize.py`, extracted by AST. All 133
  recorded values equal the values the tests assert. Origins are function-level pytest ids
  (`reference-test:tests/test_camelize.py::test_camelize`), because the `[ref: ...]` tag used by
  `porter parity reftests` cannot contain the `]` of a parametrized id. The parameter index is in the case
  name. The 20 rows of `tests/test_separate_words.py` call a private helper and are not recordable.
- Hand-written (1734), tagged by family: `scalar` (94), `whitespace` (180 plus 30 container cases),
  `unicode` (370 plus 10), `numeric` (270 plus 10), `separators` (580), `container` (200, including 50
  `collision` cases and a depth-40 nest), and `large` (40: 2000-character strings and a 300-key dict). Each
  string family runs through all ten functions.
- Generated (2720), fixed seeds: `gen-chars.<fn>` (seeds 1000-1009, random strings of length 0 to 16 over
  ASCII letters, digits, `-`, `_`, space, tab, U+001C, U+00A0 and `éÉßǅİΣσςжЖ中٣５²½ⅻ😀`, U+200B, U+0301),
  `gen-words.<fn>` (seeds 2000-2009, three-word identifiers mixing lower, Capitalized, UPPER, digit and
  non-ASCII words with `_`, `-`, `__`, `_-`, `--`, space and empty separators) and `gen-payload.<fn>` (seeds
  3000-3009, dicts and lists of dicts with generated identifier keys and JSON values). Each block has 150,
  150 and 40 cases per converter and 75, 75 and 20 per predicate.
