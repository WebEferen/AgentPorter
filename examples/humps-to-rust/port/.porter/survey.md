# Survey: pyhumps 3.8.0

pyhumps is a small Python library with no dependencies. It converts strings, and the keys of nested dicts and lists, between snake_case, camelCase, PascalCase and kebab-case, and it has four `is_*case` predicates. People use it to translate JSON or API payload keys between Python naming and JavaScript or AWS-style naming (the cookbook in README.md wraps boto3). Verdict: a small port with concentrated risk. All the logic sits in one module, `humps/main.py` (200 LOC, of which 77 are logic and the rest docstrings), behind 10 public functions and 4 regexes, with no I/O. The risk is in exact behavior: regex semantics (lookahead, lookbehind, `re.split` with a capture group), Python's Unicode-aware string predicates mixed with ASCII-only `[A-Z]` classes, and dynamic input typing (None becomes `""`, numbers come back unchanged, other scalars get stringified). The 117 test cases that pytest collects give a solid fixture base for ASCII input.

## Facts

| Fact | Value |
| --- | --- |
| Package | pyhumps 3.8.0 |
| Commit | dc56af8dff5c |
| License | Unlicense (copyleft: none) |
| Kind | library |
| Primary language | python |
| Source LOC | 270 |
| Tests | 8 files, 752 LOC, 18 cases, ratio 2.79 |
| Test runners | pytest |
| Public symbols | 25 |
| Modules by coupling | pure 4 |
| Runtimes | python classifiers 3.6, 3.7, 3.8, 3.9, 3.10 |
| Sampled | no |

| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |
| --- | --- | --- | --- | --- | --- | --- |
| humps | python | 34 | pure |  |  |  |
| humps | python | 24 | pure |  |  |  |
| humps.main | python | 200 | pure |  | nullability, regex | ACRONYM_RE, PASCAL_RE, SPLIT_RE, UNDERSCORE_RE, pascalize, camelize, kebabize, decamelize, depascalize, dekebabize, is_c |
| humps.main | python | 12 | pure |  |  | StrOrIter, pascalize, camelize, kebabize, decamelize, depascalize, dekebabize, is_camelcase, is_pascalcase, is_kebabcase |

Reading the tables above:

- The duplicate rows are each `.py` file paired with its type stub. The scanner gives a `.pyi` the same module id as its `.py`. The first `humps` row is `humps/__init__.py` (34 LOC) and the second is `humps/__init__.pyi` (24). The first `humps.main` row is `humps/main.py` (200) and the second is `humps/main.pyi` (12). So there are 2 real modules, not 4.
- Source LOC 270 includes 36 lines of stubs. Runtime code is 234 LOC (`humps/__init__.py` plus `humps/main.py`). Of `main.py`'s 252 lines, 77 are logic and 129 are docstrings.
- Public symbols 25 counts the API twice. `main.py` has 14 (10 functions plus 4 regex constants) and `main.pyi` repeats the 10 functions and adds the `StrOrIter` TypeVar (11). The exported API is the 10 functions in `__all__` (`humps/__init__.py:25-36`). The regex constants are public by naming only and are not re-exported.
- The symbol list in the `humps.main` row is cut off at "is_c" by the table printer. The full list ends `is_camelcase, is_pascalcase, is_kebabcase, is_snakecase`.
- "18 cases" counts test functions. Through `@pytest.mark.parametrize`, pytest collects 117 cases: 106 parametrized rows plus 11 plain tests (see Flags). The 2.79 ratio is test LOC over 270. Against the 234 runtime LOC it is 3.21.
- Runtimes: `setup.py` classifiers list 3.6 to 3.10, while `pyproject.toml` says `python = "^3.7"` and CI runs 3.7 to 3.10 (`.github/workflows/ci.yml`).

Coupling check (all confirmed pure):

- `humps/main.py`: pure. Its only imports are `re` and `collections.abc.Mapping` (`humps/main.py:4-6`). There is no file, network, env, clock or mutable global state. The module-level regexes are compiled once and only read.
- `humps/__init__.py`: pure. It re-exports from `humps.main` (`humps/__init__.py:12-23`) and sets metadata strings (`__version__` and others, `humps/__init__.py:6-10`).
- `humps/__init__.pyi`, `humps/main.pyi`: pure. These are type stubs only (`humps/main.pyi:1` imports `typing`).

## Scope

- Kind: library. One import package, `humps`, with no CLI and no entry point other than import.
- In scope:
  - `humps/main.py`: the 10 public functions (`camelize`, `decamelize`, `pascalize`, `depascalize`, `kebabize`, `dekebabize`, `is_camelcase`, `is_pascalcase`, `is_kebabcase`, `is_snakecase`) and the 4 private helpers (`_is_none`, `_process_keys`, `_fix_abbreviations`, `_separate_words`). `tests/test_separate_words.py:6` imports `_separate_words` directly, so its exact output is part of the tested contract.
  - `humps/__init__.py`: the export surface and `__version__`.
- Reference only: `humps/main.pyi` and `humps/__init__.pyi`. They hold the only typed signatures: `StrOrIter = TypeVar(bound=Union[str, Mapping, list])`, and every converter returns the same type it receives (`humps/main.pyi:4-16`). There is nothing to port in them, but they narrow the declared contract (see the risk table).
- Out of scope:
  - `setup.py`, `pyproject.toml`, `setup.cfg`, `Pipfile.lock`, `poetry.lock`, `MANIFEST.in`: packaging.
  - `docs/conf.py`, `docs/Makefile`: Sphinx build. The examples in `docs/*.rst` and `README.md` are still useful as extra fixtures.
  - `humps/py.typed`: empty marker file.
  - `Makefile`, `.github/`, `.pre-commit-config.yaml`, `.pylintrc`, `.readthedocs.yaml`, `.envrc`: tooling.
  - `artwork/`: images.

## Where the risk is

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| humps.main (`humps/main.py:8-11`, `:240`, `:252`) | pure | The conversion logic lives in 4 regexes that must behave identically: `ACRONYM_RE` uses lookahead `(?=[A-Z\d]\|$)` (`:8`), `UNDERSCORE_RE` uses lookbehind `(?<=[^\-_])` (`:11`), and `SPLIT_RE` goes through `re.split` with a capturing group, which keeps the captures, after which empty strings are dropped (`:10`, `:252`). | regex |
| humps.main (`humps/main.py:216`) | pure | `_is_none` maps None to `""`, calls `str()` on every other input, then strips all Unicode whitespace, so `"hello world"` becomes `"helloworld"`. Tests rely on None giving `""` (`tests/test_camelize.py:34`, `tests/test_pascalize.py:26`), but the stubs do not allow None at all (`humps/main.pyi:4`). | nullability, regex |
| humps.main (`humps/main.py:25-30`, `:53-58`, `:78-83`, `:107-112`, `:140-145`) | pure | Input and return types vary at runtime. Input whose `str()` is numeric comes back unchanged as the original object (`camelize(1234) == 1234`, `tests/test_humps.py:71-75`). All-uppercase strings come back unchanged, whitespace included. Other scalars get stringified (`camelize(1.5)` returns `"1.5"`, `camelize(True)` returns `"true"`). Only `list` and `Mapping` are recursed; tuples and sets pass through (`:220`). | not tagged: dynamic typing |
| humps.main (`humps/main.py:29`, `:39`, `:61`, `:114`, `:240`) | pure | Unicode-aware `str` methods are mixed with ASCII-only `[A-Z]` regex classes. `"½".isnumeric()` is True. `"MB2X".title()` is `"Mb2X"` (title-casing restarts after a digit, which `_fix_abbreviations` depends on). `"ß".upper()` is `"SS"`, so the length changes. `"helloÉcole"` is not split at `É`. `\d` and `\s` match Unicode in Python str patterns. No test uses non-ASCII input. | not tagged: unicode |
| humps.main (`humps/main.py:29`, `:57`, `:60-61`, `:82`, `:85-93`, `:144-147`) | pure | The early returns and branches differ per function and are easy to flatten by accident. camelize, pascalize and decamelize return early on `isupper()` or `isnumeric()`; kebabize and dekebabize only on `isnumeric()`. camelize lowercases the first char unless `s[:2].isupper()` (so `"A_b"` becomes `"AB"`). On its non-camel path kebabize keeps case (`"scrubber_Media_Url"` becomes `"scrubber-Media-Url"`, `tests/test_kebabize.py:43,75`). dekebabize is a plain `-` to `_` replace with no case change. | none |
| humps.main (`humps/main.py:38`, `:85`, `:161-204`) | pure | The functions form a call web: pascalize calls camelize, kebabize calls is_camelcase and is_pascalcase, and is_snakecase calls is_kebabcase, is_camelcase and decamelize. Each `is_*` is a fixed-point check (`x == convert(x)`) that also works on dicts and lists by structural equality. For `"API"` all four predicates return True (`tests/test_humps.py:59-62`). | none |
| humps.main (`humps/main.py:219-224`) | pure | `_process_keys` rebuilds every Mapping as a plain dict in insertion order. Converted keys that collide overwrite each other silently, last one wins. Non-string keys go through the same converter (an int key stays an int, a float key becomes a string). Recursion depth is bounded only by Python's recursion limit. | none |
| humps (`humps/__init__.py`) | pure | Re-exports and metadata only. No risk. | none |
| stubs (`humps/__init__.pyi`, `humps/main.pyi`) | pure | The declared types (`str`, `Mapping` or `list` in, same type out) are narrower than the tested behavior, which covers None and int inputs. The contract phase has to decide which one is the contract. | none |

## Flags for the user

- License: Unlicense (`LICENSE`), a public-domain dedication with no copyleft. Packaging metadata disagrees: `setup.py` sets `license="The Unlicense (Unlicense)"` but has the classifier `License :: OSI Approved :: MIT License`. The `LICENSE` file text is the Unlicense.
- Tests: 8 files, 752 LOC, 18 test functions that pytest expands to 117 cases. Ratio 2.79 as measured (3.21 against the 234 runtime LOC). Per file:
  - `test_camelize.py`: 18 + 1
  - `test_decamelize.py`: 19 + 1
  - `test_dekebabize.py`: 15 + 1
  - `test_humps.py`: 8 parametrized + 6 plain, with `test_conditionals` holding 24 asserts on the predicates
  - `test_kebabize.py`: 12 + 1
  - `test_pascalize.py`: 14 + 1
  - `test_separate_words.py`: 20

  Coverage is good for ASCII strings and nested dict/list payloads. Nothing tests:
  - non-ASCII input
  - input containing whitespace
  - floats or bools
  - tuples or Mapping types other than dict
  - non-string keys
  - key collisions after conversion
  - `depascalize` or `dekebabize` on numbers

  Those cases need generated fixtures. `README.md` and `docs/index.rst` add about 20 more documented input/output pairs.
- Sampling: full scan, 14 of 14 code files. I read all of `humps/`, all of `tests/`, `README.md`, `docs/index.rst`, `docs/api.rst`, `docs/user/quickstart.rst`, `setup.py`, `pyproject.toml`, `setup.cfg`, `Makefile` and `.github/workflows/ci.yml`. I did not read `docs/user/install.rst`, `docs/conf.py`, the lockfiles, the `.github` templates or `artwork/`. None of them affects runtime behavior.
- Native code, FFI, subprocess or OS-specific paths: none found. There are no third-party runtime dependencies (`pyproject.toml` `[tool.poetry.dependencies]` lists only `python`). The only stdlib imports are `re` and `collections.abc` (`humps/main.py:4-6`).
