# Decomposition

Proposed by `porter.py decompose` on 2026-10-20.
Budgets: at most 400 LOC and 8 public functions, classes and types with members per unit (constants and aliases do not count), merge below 30 LOC.

## Layer map

- core: root

## Units in order

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | root (tracer) | core | 0 | 213 | Join, UnterminatedSingleQuoteError, UnterminatedDoubleQuoteError, UnterminatedEscapeError, Split | - | error-model, nullability, ordering, unicode |  |

## Why the cuts are where they are

- tracer bullet: root (closure root), the lowest-risk vertical slice

## Adjustments

The agent records every change it makes to the proposal here, one line each: what changed and why.

- root: referenceTests set to both_test.go, quote_test.go, unquote_test.go; decompose left it empty because Go same-package tests import nothing, and `parity reftests` needs the files to assign `[ref: ...]` tags.
- root: added risk tag `unicode`; the survey and the contract leak list flag byte versus code-point semantics (`invalid-utf8`).
- root: strategy `code-port`; the `goto` state machines must be reproduced exactly and the contract pins their output character for character.
- root: extra acceptance criterion for `exc.words`, because parity ignores `expect.value` on error outcomes.
