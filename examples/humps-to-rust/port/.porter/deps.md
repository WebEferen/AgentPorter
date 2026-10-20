# Dependencies: pyhumps -> rust

pyhumps 3.8.0 has no third-party runtime dependencies. Two standard library areas it uses have no Rust std
equivalent and need crates: `re` (MAP to `regex`) and the dict/list handling of `collections.abc.Mapping`
(MAP to `serde_json`, because the user decided dict and list inputs become `serde_json::Value`). Both
candidates are registry-verified. The 12 direct dev, build and lint dependencies are dropped and map to
cargo tooling. Both MAP decisions are flagged for the gate so the user sees the regex rewrite plan and the
serde_json feature choice.

## Runtime dependencies

| Dependency | Version | Role | Used surface | Decision | Candidate | Confidence | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| re (stdlib) | CPython 3.x | runtime-library | `re.compile` x4, `Pattern.sub` with callback (main.py:38, :65, :93, :240), `Pattern.split` keeping the group (:252), `re.sub(r"\s+")` (:216) | MAP | regex@1.13.1 (`default-features = false`, `features = ["std", "unicode-perl"]`) | HIGH | `cache/registry/crates/regex.json`; docs.rs regex 1.13.1; scout probe, 45,559 inputs, 0 mismatches against CPython 3.14.6 |
| collections.abc.Mapping, dict, list (stdlib) | CPython 3.x | runtime-library | `isinstance(x, (list, Mapping))` in every public function, `_process_keys` (main.py:219-224): ordered dict comprehension, list comprehension | MAP | serde_json@1.0.154 (`features = ["preserve_order"]`) | HIGH | `cache/registry/crates/serde_json.json`, `indexmap.json`; scout probes on order, collisions and equality |

## API deltas for MAP and SHIM

### re -> regex

- `ACRONYM_RE` `([A-Z\d]+)(?=[A-Z\d]|$)` -> compile `[A-Z\d]+`; for each maximal run keep the whole run at end
  of string (or before a final `\n`), else drop its last char (by `len_utf8`), skip when empty. Lookahead
  removed by hand.
- `UNDERSCORE_RE` `(?<=[^\-_])[\-_]+[^\-_]` -> compile `[\-_]+[^\-_]` and skip a match that starts at 0 or
  whose preceding char is `-` or `_`. Must not become a consuming group: `"a_b_c"` would give `aB_c`, not `aBC`.
- `PASCAL_RE.sub(fn)` -> `replace_all` with a closure: same.
- `SPLIT_RE.split()` keeps captured groups; `Regex::split` drops them -> `find_iter` helper that pushes gaps and
  matches. The pattern never matches empty.
- `re.sub(r"\s+", "")` -> `[\s\x1C-\x1F]+`: Python `\s` is White_Space plus U+001C..U+001F; the crate's `\s` is
  White_Space only.
- `\d`: the crate's `\p{Nd}` equals Python 3.14's `\d` (Unicode 16). Python 3.9 to 3.13 ship older tables.
- Callbacks: `m.group(0)[-1]` -> last `char`, not last byte.
- `fancy-regex` is not used for any pattern.

### collections.abc.Mapping -> serde_json::Value

- `dict` -> `Value::Object` with `preserve_order` (IndexMap); without it keys come out sorted.
- Key collision after conversion: Python keeps the first position and the later value; `Map::insert` does the
  same. Build fresh maps; never `Map::remove` in place (it is `swap_remove`).
- `dict ==` and `Map` equality both ignore order, so `is_*case` on objects matches.
- Not representable (contract divergences): non-str keys, tuples (Python does not walk them; every JSON array
  is walked), Mapping subclasses (result is always a plain dict anyway), ints beyond 64 bits, NaN/Infinity.
- Top-level `None`/bool/number go through the string path in Python (`camelize(None) == ""`,
  `camelize(True) == "true"`); the Rust API must reproduce or exclude this. Floats need Python repr (trap T4).

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| pytest | cargo test | parametrized cases become table tests and fixtures |
| flake8, pylint | cargo clippy, cargo fmt | |
| pytest-cov, coveralls | none | coverage not ported |
| sphinx | rustdoc | |
| poetry-core, twine, bumpversion | cargo | no publishing in this run |
| ipython, pathlib2, scandir | none | unused or polyfills |
| (parity harness) | serde_json dev-dependency, `preserve_order` + `float_roundtrip` | user approved serde_json for the harness |

## Gate items

- re: MAP to regex 1.13.1 with lookarounds rewritten by hand; recommendation: approve (no pattern needs fancy-regex).
- collections.abc.Mapping: MAP to serde_json 1.0.154 with `preserve_order` as a runtime dependency; recommendation: approve.
