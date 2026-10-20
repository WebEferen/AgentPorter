# Contract: <package> <version>

<One paragraph: what the port must preserve, at which observation boundary, and the confidence of the
contract (high when the source has a strong test suite, lower when fixtures come from docs and generators).>

## Public surface

| Symbol | Kind | Signature | Unit | In scope | Notes |
| --- | --- | --- | --- | --- | --- |
| <module:name> | <function / class / method / constant / command / flag / config> | <signature> | <unit> | <yes / no: reason> | <nullability, side effects> |

## Semantics the tests promise and the docs omit

- <ordering, identity, idempotence, precision, locale, timezone, encoding, error types and messages>

## Error model

| Source error | When | Target category (error-map.json) |
| --- | --- | --- |
| <ValueError> | <condition> | <RangeError> |

## Leak list

Internals that leak into observable behavior and must be preserved or consciously diverged from:

- <dict iteration order, float formatting, exception hierarchy, ...>

Free to differ:

- <internal caches, helper names, module layout, ...>

## Observation boundary per unit

| Unit | Observed | Normalization |
| --- | --- | --- |
| <unit> | <return values / errors / trace / stdout, stderr, exit code / files> | <none, or float:1e-9, unordered, trim, ...> |

## Fixtures

<Paste `porter.py fixtures summary`. Say where cases came from: harvested tests, hand-written edge cases,
seeded generators.>
