# Survey: ms 2.1.3

ms is Vercel's tiny millisecond conversion utility: one CommonJS function that parses strings such as `"2 days"` or `"1.5h"` into milliseconds and formats a millisecond count as `"2d"` or, with `{ long: true }`, `"2 days"`. It is a common transitive dependency in the npm ecosystem (the `debug` package uses it, for example). Verdict: a very small, low-effort port. There is one pure module of 151 LOC with one public function and no runtime dependencies, so it fits in a single unit. All of the risk is in matching JavaScript number and string semantics exactly: `Math.round` on negative halves, Number-to-string output, the regex grammar, and a signature that takes a string or a number and returns a number, a string or `undefined`.

## Facts

| Fact | Value |
| --- | --- |
| Package | ms 2.1.3 |
| Commit | 1c6264b79549 |
| License | MIT (copyleft: none) |
| Kind | library |
| Primary language | javascript |
| Source LOC | 151 |
| Tests | 1 files, 232 LOC, 49 cases, ratio 1.54 |
| Test runners | mocha-style (describe/it) |
| Public symbols | 1 |
| Modules by coupling | pure 1 |
| Runtimes | not declared |
| Sampled | no |

| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |
| --- | --- | --- | --- | --- | --- | --- |
| index | javascript | 151 | pure |  | error-model, float-format, nullability, numeric, reflection, regex | default |

## Scope

- Kind: library. The package publishes one file with one default export (`package.json`: `"main": "./index"`, `"files": ["index.js"]`).
- In scope: `index.js`, all of it: the exported `ms(val, options)` function (index.js:26-38), the private helpers `parse`, `fmtShort`, `fmtLong` and `plural` (index.js:48-162), and the unit constants (index.js:5-10).
- Out of scope:
  - `tests.js`: the test suite. It is input for the contract and is not shipped (`files` lists only `index.js`).
  - `readme.md`: docs. Its examples (readme.md:9-40) are extra contract cases, including the only `1y` example (readme.md:17).
  - `package-lock.json` and the devDependencies, lint, husky and lint-staged config in `package.json`: dev tooling only. All 189 lockfile entries are dev dependencies, and the `lint` script targets `lib/*` and `bin/*`, which do not exist in this tree.
  - `.github/workflows/ci.yml`, `.npmrc`, `.gitignore`: CI and repo config.
  - Nothing is generated, vendored or platform-specific.

## Where the risk is

Coupling for `index` is confirmed pure: the file has no `require` or import, and touches only ECMAScript built-ins (`isFinite` at index.js:31, `JSON.stringify` at index.js:36, `parseFloat` at index.js:59, `Math.abs` and `Math.round` at index.js:114-161). The rows below split the one module by function, because the risks differ.

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| index: exported function (index.js:26-38) | pure | It dispatches on `typeof val` (index.js:28-33): a non-empty string returns a number or `undefined`, a finite number returns a string, anything else throws. `options.long` is a truthiness check (index.js:27, 32). The error message embeds `JSON.stringify(val)` (index.js:34-37), so NaN and Infinity print as `null` and `undefined` prints as `undefined`. Tests only assert that it throws (tests.js:252-298), never the message. | reflection, error-model, numeric |
| index: `parse` (index.js:48-103) | pure | The regex at index.js:53 is the whole input grammar: ASCII digits, an optional leading `-`, a leading `.` allowed but no trailing one, U+0020 spaces only (no tabs), trailing spaces accepted (`"1 "` gives 1), no leading space, no `+` or exponent, case-insensitive units with JS non-unicode `/i` folding (`1ſ` and `1K` do not match), and `$` anchored at the true end of input (`"1m\n"` fails). It returns `undefined` for input over 100 UTF-16 code units or with no match (index.js:50-58), not NaN as the test name at tests.js:56 suggests. Results are doubles from `parseFloat(...) * unit` (index.js:59-99): `.5ms` gives 0.5 (tests.js:66) and `1.15h` gives 4139999.9999999995. The `default` branch at index.js:100-101 is unreachable. | regex, nullability, float-format |
| index: `fmtShort`, `fmtLong`, `plural` (index.js:113-162) | pure | `Math.round` rounds halves toward +infinity, so `ms(1500)` is `"2s"` but `ms(-1500)` is `"-1s"`. `ms(-90000, { long: true })` is `"-1 minutes"`, because pluralisation tests the absolute value (index.js:160) while rounding uses the signed one (index.js:161). Below one second, the value is printed with JS Number-to-string (index.js:127, 152): `0.5ms`, `1e-7ms`, and `-0` prints as `0ms`. Very large inputs print in exponent form (`ms(1e300)` gives `"1.1574074074074075e+292d"`, index.js:116). None of these edges are tested. The survey tagged `fmtLong` as numeric only, but it also carries float-format (implicit Number-to-string at index.js:152, `Math.round` through `plural`). | float-format, numeric |

## Flags for the user

- License: MIT (`license.md`, "Copyright (c) 2020 Vercel, Inc."). There is no copyleft, but the port must keep the copyright and permission notice.
- Tests: 1 file (`tests.js`), 232 LOC, 49 cases, ratio 1.54, mocha with expect.js. Every short unit and both output formats are covered, positive and negative. Untested:
  - year parsing (`y`, `yr`, `yrs`, `year`, `years`)
  - the 100-character limit
  - trailing spaces
  - half-way and fractional formatting
  - the 1.5x plural boundary
  - error message text
  - exponent output

  The contract for these leans on the source's behaviour and generated fixtures. The case at tests.js:56-59 passes only because `isNaN(undefined)` is true, so the contract must pin `undefined`, not NaN.
- Sampling: full scan, 2 of 2 code files read in full. I also read `readme.md`, `package.json`, `license.md` and the CI workflow. I did not read `package-lock.json` beyond confirming that every entry is a dev dependency.
- Native code, FFI, subprocess or OS-specific paths: none found. The README says it works in Node.js and the browser (readme.md:44). `tests.js` guards `require` for browser runs (tests.js:6-9). CI runs Node 6.x and 14.x (.github/workflows/ci.yml:14), and `package.json` declares no `engines`.
