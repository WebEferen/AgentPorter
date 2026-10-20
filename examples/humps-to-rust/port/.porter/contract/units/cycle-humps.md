# Unit contract: cycle-humps

Layer: core. Wave: 0. Depends on: none. Draft unit holding all of `humps/main.py`. The strategy phase
re-cuts it.

## Symbols

`x` is the argument. "String path" means: `s = "" if x is None else str(x)`, with every Python `\s`
character removed. "Walk" means: a list becomes a new list of walked items, a dict becomes a new dict with
every key converted and every value walked, and anything else comes back unchanged.

| Symbol | Signature | Semantics |
| --- | --- | --- |
| humps.main:camelize | `camelize(x)` | Walk containers. On the string path, return `x` when `s.isupper()` or `s.isnumeric()`. Otherwise lowercase `s[0]` unless `s[:2].isupper()`, then replace every separator run that follows a non-separator and precedes one with that next character uppercased. |
| humps.main:pascalize | `pascalize(x)` | Walk containers. Same early return. Uppercase the first character of every run of non-`-`/`_` characters, pass the result through camelize (its early return can fire: `"a_b" -> "A_B"`), then uppercase the first character. |
| humps.main:kebabize | `kebabize(x)` | Walk containers. Early return on `s.isnumeric()` only. If `s` is not all-uppercase and `is_camelcase(s) or is_pascalcase(s)`: title-case the acronyms, split before ASCII capitals, join with `-`, lowercase. Otherwise replace each separator run with `-` plus the next character, keeping case. |
| humps.main:decamelize | `decamelize(x)` | Walk containers. Early return on `isupper` or `isnumeric`. Title-case the acronyms (`[A-Z\d]+` followed by `[A-Z\d]` or end), split before ASCII capitals keeping adjacent separators, join with `_`, lowercase the whole string. |
| humps.main:depascalize | `depascalize(x)` | `decamelize(x)`. |
| humps.main:dekebabize | `dekebabize(x)` | Walk containers. Early return on `s.isnumeric()`. Otherwise `s.replace("-", "_")`. |
| humps.main:is_camelcase | `is_camelcase(x) -> bool` | `x == camelize(x)` under Python equality. An int never equals a str. |
| humps.main:is_pascalcase | `is_pascalcase(x) -> bool` | `x == pascalize(x)`. |
| humps.main:is_kebabcase | `is_kebabcase(x) -> bool` | `x == kebabize(x)`. |
| humps.main:is_snakecase | `is_snakecase(x) -> bool` | `False` if `is_kebabcase(x) and not is_camelcase(x)`, else `x == decamelize(x)`. |

Internal pieces the unit must still port (private in the crate; `porter decompose` in final mode drops
them from the unit's symbol list because api.json marks them out of scope):

- `ACRONYM_RE` `([A-Z\d]+)(?=[A-Z\d]|$)`, `PASCAL_RE` `([^\-_]+)`, `SPLIT_RE` `([\-_]*[A-Z][^A-Z]*[\-_]*)`
  (split keeps the captured group, then empty pieces are dropped), `UNDERSCORE_RE` `(?<=[^\-_])[\-_]+[^\-_]`
  (the lookbehind is not consumed: `"a_b_c" -> "aBC"`). See the rewrite notes in `deps.json`. The `$` before
  a final newline in ACRONYM_RE cannot be observed, because whitespace is stripped first.
- `_is_none`, `_process_keys`, `_fix_abbreviations` (title-case each acronym match; only ASCII capitals and
  Nd digits can occur, and title-casing restarts after a digit), and `_separate_words(string, separator="_")`.

## Errors

- None on any JSON input. Every one of the 4587 recorded outcomes is a value.
- Nesting deeper than about 990 levels raises `RecursionError` in Python. This is not recorded. The strategy
  decides the Rust behavior (leak `recursion-depth`).

## Fixtures

- `fixtures/cycle-humps/oracle.json`: 4587 cases. 133 harvested, 1734 hand-written (tags `scalar`,
  `whitespace`, `unicode`, `numeric`, `separators`, `container`, `collision`, `large`, `deep`), and 2720
  generated (`gen-chars.*`, `gen-words.*`, `gen-payload.*`, seeds 1000-1009, 2000-2009, 3000-3009).
  Per function: camelize 542, pascalize 537, kebabize 534, decamelize 549, depascalize 521, dekebabize 536,
  and each predicate 342.
- Normalization: none. Parity compares objects order-insensitively, so key order and collision position
  are not checked by fixtures. See the assertions below.
- Tag `strategy-decision` (100 cases) marks top-level None, bool, int and float inputs. Their outcome
  depends on whether the Rust API accepts non-container, non-string values. If it does not, declare them
  as a divergence instead of patching them in a binding.

Behavioral assertions that the fixtures cannot express (write them as Rust unit tests):

- Key order: `camelize({"b_x": 1, "a_y": 2, "c_z": 3})` iterates `bX, aY, cZ`.
- Collision position: `camelize({"a_b": 1, "x": 0, "aB": 2})` iterates `aB, x`, with `aB == 2`.
- The input value is not mutated.
- `_separate_words` (or its Rust equivalent), from `tests/test_separate_words.py`:

| Input | `separate_words(input)` |
| --- | --- |
| `HelloWorld` | `Hello_World` |
| `_HelloWorld` | `_Hello_World` |
| `__HelloWorld` | `__Hello_World` |
| `HelloWorld_` | `Hello_World_` |
| `HelloWorld__` | `Hello_World__` |
| `helloWorld` | `hello_World` |
| `_helloWorld` | `_hello_World` |
| `__helloWorld` | `__hello_World` |
| `helloWorld_` | `hello_World_` |
| `helloWorld__` | `hello_World__` |
| `hello_world` | `hello_world` |
| `_hello_world` | `_hello_world` |
| `__hello_world` | `__hello_world` |
| `hello_world_` | `hello_world_` |
| `hello_world__` | `hello_world__` |
| `whatever_hi` | `whatever_hi` |
| `whatever_10` | `whatever_10` |
| `sizeX` | `size_X` |
| `aB` | `a_B` |
| `testNTest` | `test_N_Test` |

## Reference tests mapped here

`plan.json` lists only `tests/test_separate_words.py` under this unit's `referenceTests`, because the other
six files import the package root `humps` and the draft decomposition does not map them. The strategy phase
should add them. Harvested cases carry function-level origins, so `porter parity reftests` can map a
ported test tagged `[ref: tests/test_camelize.py::test_camelize]` to this unit.

- `tests/test_camelize.py::test_camelize` (18 rows) -> PASS. Row 17 (`None`) depends on the scalar
  decision: DIVERGENCE if the Rust API does not accept null.
- `tests/test_camelize.py::test_camelize_dict_list` -> PASS
- `tests/test_decamelize.py::test_decamelize` (19 rows), `::test_decamelize_dict_list` -> PASS (float values
  need `serde_json` `float_roundtrip` in the harness)
- `tests/test_dekebabize.py::test_dekebabize` (15 rows), `::test_dekebabize_dict_list` -> PASS
- `tests/test_humps.py::test_converting_strings` (6), `::test_camelized_acronyms` (8 rows),
  `::test_conditionals` (24), `::test_upper` (6), `::test_pascalize`, `::test_depascalize` -> PASS
- `tests/test_humps.py::test_numeric` (4, ints) -> PASS or DIVERGENCE, per the scalar decision
- `tests/test_kebabize.py::test_kebabize` (12 rows), `::test_kebabize_dict_list` -> PASS
- `tests/test_pascalize.py::test_pascalize` (14 rows), `::test_pascalize_dict_list` -> PASS. Row 13
  (`None`) follows the scalar decision.
- `tests/test_separate_words.py::test_separate_words` (20 rows) -> PASS as an in-crate `#[cfg(test)]` test
  of the private helper, using the table above. There are no fixtures, because the harness only reaches the
  public API. OUT-OF-SCOPE only if the port has no separate-words helper, in which case decamelize and
  kebabize fixtures cover its effect.

## Risk tags and traps to read

- regex: `deps.json` notes for `re` (hand-written lookaround rewrites, `[\s\x1C-\x1F]+` for Python `\s`,
  a `find_iter` split that keeps matches, `\d` = `\p{Nd}`). Section 9 of the pair file is still a stub.
- nullability: leak `string-path-for-scalars` (None becomes `""`, `is_*case(None)` is False).
- unicode: T3 (code-point indexing), plus leaks `early-return-original`, `unicode-case-mapping`,
  `ascii-split-unicode-predicates` and `unicode-version`.
- float-format: T4, leak `float-repr`, only if top-level floats are accepted.
- ordering: T5, leak `dict-order-and-collisions`.
- numeric: T1. Ints beyond 2^53 are not fixture inputs (leak `unrepresentable-inputs`).
