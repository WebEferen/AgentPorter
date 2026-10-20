# Unit contract: split

Layer: core. Wave: 0. Depends on: none. Re-filed during the contract rerun from the draft units
src-titlecase (splitByCase) and src-isuppercase (isUppercase, upperFirst, lowerFirst) to remove the call
cycle between them: everything here calls only code in this unit.

## Symbols

| Symbol | Signature | Semantics |
| --- | --- | --- |
| src/index:isUppercase | `isUppercase(char = ""): boolean \| undefined` | `undefined` if any ASCII digit is present, else `char !== char.toLowerCase()` over the whole argument. |
| src/index:splitByCase | `splitByCase(str: string, separators?: readonly string[]): string[]` | Walks code points. A separator (one whole code point from the list; default `- _ / .`; `[]` means none) ends the part and resets case state. Lower-to-upper starts a part; upper-to-lower after 2+ UTF-16 units moves the last unit into the next part. ASCII digits are neutral. `""` gives `[]`; empty parts are kept. |
| src/index:upperFirst | `upperFirst(str: string): string` | Uppercases the first UTF-16 unit with full mapping (`ß` -> `SS`); a leading astral character is left as is. `""` for `""`. |
| src/index:lowerFirst | `lowerFirst(str: string): string` | Same with `toLowerCase` (`İ` -> `i\u0307`). |

## Errors

- None. No input inside the TypeScript signatures throws; all 966 outcomes are values. `isUppercase`
  returns `undefined` (fixture `{"$undefined": true}`) for digits; that is a value, and the Go binding returns
  the harness `Undefined` marker for it.

## Fixtures

- `fixtures/split/oracle.json`: 966 cases. splitByCase 496 (13 harvested, 1 README, 82 hand-written, 400
  generated), isUppercase 246 (0, 0, 46, 200), upperFirst 110 (3, 1, 26, 80), lowerFirst 114 (3, 1, 30, 80).
- Generators: `gen.splitByCase.chars-ascii` (seed 101, 120), `chars-unicode` (102, 120), `words` (103, 80),
  `separators` (104, 80); `gen.isUppercase.char` (201, 150), `gen.isUppercase.string` (202, 50),
  `gen.upperFirst.chars-unicode` (203, 80), `gen.lowerFirst.chars-unicode` (204, 80).
- Normalization: none. Outputs are exact strings, string arrays and booleans.
- The astral cases whose outputs are valid UTF-8 stay in the fixtures and must pass (tags `astral-upper`,
  `utf16-falling-edge`; for example `splitByCase("a𐐀")` = `["a","𐐀"]`).

## Removed cases: documented divergence

These 3 inputs were recorded from the original and then removed from the fixtures. Their outputs contain lone
UTF-16 surrogates, and fixture strings must be UTF-8 (`knowledge/oracles/CONTRACT.md`: "Strings stay strings
(UTF-8)"). A Go string cannot carry these values, so the port's result for them is a documented divergence
(leaks `utf16-falling-edge-split` and `lone-surrogate-encoding` in `api.json`). The outputs below are the
original's return values as JSON text; `\udXXX` is a lone surrogate.

| Removed case | Call | Original output |
| --- | --- | --- |
| splitByCase.astral-upper-then-lower | `splitByCase("𐐀a")` | `["\ud801","\udc00a"]` |
| splitByCase.astral-upper-mid | `splitByCase("A𐐀a")` | `["A\ud801","\udc00a"]` |
| splitByCase.astral-upper-then-astral-lower | `splitByCase("𐐀𐐨")` | `["\ud801","\udc00𐐨"]` |

`𐐀` is U+10400 (UTF-16 `\ud801\udc00`), `𐐨` is U+10428. The split moves only the low surrogate of the
astral capital into the next part.

## Reference tests mapped here

- `test/scule.test.ts:17-34` (describe splitByCase, 13 rows, cases `splitByCase.ref.L<line>`) -> PASS
- `test/scule.test.ts:93-95` (describe upperFirst, 3 rows) -> PASS
- `test/scule.test.ts:103-105` (describe lowerFirst, 3 rows) -> PASS

Cases are `<fn>.ref.L<line>`.

## Risk tags and traps to read

- unicode: T1 and T2 (UTF-16 length and slicing in the falling edge; `str[0]` in upperFirst/lowerFirst), T5
  (full case mapping: `ß`, `ŉ`, `ﬀ`, `ǰ`, `ΐ`, `İ`), T6 (no locale), T44 (lone surrogates against Go's
  UTF-8). Leaks `utf16-first-unit-casing`, `utf16-falling-edge-split`, `lone-surrogate-encoding`,
  `code-point-iteration`, `full-case-mapping`, `is-uppercase-definition`.
- regex: T20 (`/\d/` is ASCII-only, leak `ascii-digit-tristate`).
- nullability: T41, T42 (omitted against empty separators; `undefined` and zero-argument calls;
  `isUppercase` tri-state).
