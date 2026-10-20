# Parity model

A port is done when it behaves like the original. AgentPorter checks that behavior directly. The
original runs as an oracle, its outputs become fixtures, the port runs the same cases, and `porter.py
parity collect` compares the two. Structural similarity between the codebases never counts as
evidence.

## Where the evidence comes from

| Source | When it applies | How it is recorded |
| --- | --- | --- |
| Oracle fixtures | The original can be run: a library with an oracle driver, or any CLI | `fixtures/<unit>/*.json`, recorded by the original |
| Reference tests | The source has tests that can be ported | Ported tests tagged `[ref: <id>]`, imported with `parity reftests` |
| Divergences | The port differs on purpose | `divergences.json` plus `DIVERGENCE(id)` markers in the code |

Fixtures always come from running the original. The contract skill writes case specs (explicit inputs
plus seeded generators for random strings, numbers, JSON and so on). `fixtures expand` turns them into
concrete inputs. The oracle then records what the original returns, throws or prints.

Libraries use an oracle driver from `knowledge/oracles/<language>/` and a harness from
`knowledge/harnesses/<language>/`. Both follow `knowledge/oracles/CONTRACT.md`, which fixes the call
format (`module:qualname`), tagged JSON values for types JSON cannot carry (sets, bytes, big integers,
NaN, datetimes, enums, structs) and the outcome shape. One fixture corpus can then drive any pair of
languages.

CLI tools skip both. `porter.py cli record` runs the original with each case's arguments, stdin,
environment and input files in a scratch directory, and records exit code, stdout, stderr and output
files. `porter.py cli run` does the same with the port.

## Levels

Each unit gets one level:

| Level | Meaning |
| --- | --- |
| EXACT | Every fixture matched byte for byte. |
| EQUIVALENT | Every fixture matched, some only under the normalization declared on the case. |
| DIVERGENT | Some cases differ on purpose, and each one is covered by a recorded divergence. |
| ASSERTED | There are no oracle fixtures, and passing ported reference tests carry the evidence. |
| GAP | A mismatch, a missing result, a failing reference test, or no evidence at all. |
| OUT-OF-SCOPE | The unit was deferred at the strategy gate. |

`parity collect` exits 1 while any unit is GAP. Only the verify skill moves a unit to VERIFIED, and only
when `parity.json` agrees.

## Normalizations

Normalizations are declared per case, in the fixture, before the port exists. A port cannot loosen its
own test. Any other name fails schema validation in `fixtures expand` and `fixtures validate`.

| Name | Effect |
| --- | --- |
| `float:<tol>` | Numbers compare with this relative and absolute tolerance. |
| `unordered` | Arrays compare as multisets. |
| `lines-unordered` | Lines of a string (CLI stdout, for example) compare in any order. |
| `trim` | Strings are stripped. |
| `trim-trailing-ws` | Trailing whitespace is stripped from each line. |
| `lf` | CRLF becomes LF. |
| `nfc` | Strings are compared in Unicode NFC form. |
| `json` | CLI stdout is parsed as JSON before comparing. |
| `ignore-stderr` | CLI stderr is not compared. |
| `ignore-message` | Only the error category is compared, not the message. |

Error categories are mapped between languages in `contract/error-map.json`. For example, Python's
`ValueError` can map to a `RangeError` in the TypeScript port. A mapped category counts as EQUIVALENT,
not EXACT.

## Divergences

Some differences are improvements or unavoidable: a clearer error message, a runtime limit, a bug the
user chose not to carry over. They are allowed when written down in two places:

```json
{
  "schema": 1,
  "divergences": [
    {
      "id": "no-legacy-flag",
      "unit": "cli",
      "summary": "the deprecated --legacy flag is not ported",
      "rationale": "removed upstream in 3.0; approved at the strategy gate",
      "cases": ["legacy-*"],
      "approvedBy": "strategy gate 2026-10-20"
    }
  ]
}
```

and in the code, next to the behavior:

```ts
// DIVERGENCE(no-legacy-flag)
```

Case names in `cases` are globs. A failing case that matches one counts as divergent. `parity collect`
checks the markers in both directions: a marker without an entry is an error, and so is an entry
without a marker.

## Performance

When the oracle recorded timings and at least five cases ran in both, the report shows the median ratio
of port time to oracle time. It is a sanity check. A ratio far above 1 is worth a look, but it does not
change the level.

## The report

`parity report` renders `PARITY.md` from `parity.json`. It lists the upstream version and commit, the
port, the harness run, one row per unit with fixture and reference test counts, divergences, perf, and
the open mismatches with the first differing characters. `--copy-to docs/PARITY.md` also writes it into
the port's own docs.

## Keeping parity after release

Re-record the fixtures against a new upstream version with `cli record --out` or the oracle driver,
then compare with `fixtures diff old.json new.json`. The diff shows which behaviors changed upstream and
which units of the port need to follow.
