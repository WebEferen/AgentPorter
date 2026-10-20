# Decomposition

Proposed by `porter.py decompose` on 2026-10-20.
Budgets: at most 400 LOC and 8 public functions, classes and types with members per unit (constants and aliases do not count), merge below 30 LOC.

## Layer map

- core: cycle-humps

## Units in order

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | cycle-humps (tracer) | core | 0 | 191 | pascalize, camelize, kebabize, decamelize, depascalize, dekebabize, is_camelcase, is_pascalcase, is_kebabcase, is_snakecase | - | nullability, regex |  |

## Why the cuts are where they are

- humps.main: 191 LOC or 10 public functions/classes over budget; split into 2 units by root reachability
- cycle between m:humps.main/is_pascalcase, m:humps.main/kebabize collapsed into one unit (191 LOC, created by a budget split)
- tracer bullet: cycle-humps (closure cycle-humps), the lowest-risk vertical slice

## Cycles

- m:humps.main/is_pascalcase, m:humps.main/kebabize: 191 LOC (created by a budget split). Edges: humps.main:depascalize -> humps.main:decamelize; humps.main:is_pascalcase -> humps.main:pascalize; humps.main:kebabize -> humps.main:is_pascalcase

## Adjustments

The agent records every change it makes to the proposal here, one line each: what changed and why.

- cycle-humps: strategy code-port; the behavior is defined by regex quirks (`kebabize("HELLO world") == "hell-oworld"`), so the port follows the source pipeline with lookarounds rewritten by hand.
- cycle-humps: referenceTests extended from test_separate_words.py to all 7 test files; decompose maps tests by imported module and 6 of 7 files import the package root `humps`.
- cycle-humps: two acceptance criteria added from the unit contract (key-order tests, `_separate_words` rows).
- Not changed: the unit holds 10 public symbols, over the 8-symbol budget. kebabize calls is_camelcase and is_pascalcase, and is_kebabcase and is_snakecase call kebabize, so the cycle cannot be cut without splitting the fixtures; the id stays `cycle-humps` because fixtures, cases and the unit contract are filed under it.
