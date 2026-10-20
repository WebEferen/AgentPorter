# Decomposition

Proposed by `porter.py decompose` on 2026-10-20.
Budgets: at most 400 LOC and 8 public functions, classes and types with members per unit (constants and aliases do not count), merge below 30 LOC.

## Layer map

- foundation: utils-utils
- core: validate-validate, satisfies-satisfies
- entry: src-index

## Units in order

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | utils-utils | foundation | 0 | 40 | CompareOperator, semver, validateAndParse, compareSegments | - | error-model, numeric, reflection | adjusted: also owns Error |
| 2 | validate-validate (tracer) | core | 1 | 7 | validate, validateStrict | utils-utils | reflection, regex |  |
| 3 | satisfies-satisfies | core | 1 | 90 | compare, compareVersions, satisfies | utils-utils | error-model, nullability, ordering, reflection, regex |  |
| 4 | src-index | entry | 2 | 5 | index | validate-validate, satisfies-satisfies | - | adjusted: entry last |

## Why the cuts are where they are

- src/utils holds only types, constants or errors used by 4 clusters: foundation layer
- m:src/compare (29 LOC, under the 30 LOC floor) merged into its only consumer m:src/satisfies
- m:src/compareVersions (18 LOC, under the 30 LOC floor) merged into its only consumer m:src/satisfies
- tracer bullet: validate-validate (closure utils-utils, validate-validate), the lowest-risk vertical slice

## Adjustments

The agent records every change it makes to the proposal here, one line each: what changed and why.

- src-index: dependsOn [validate-validate, satisfies-satisfies], wave 0 -> 2, moved last in order. Rust `pub use` re-exports need the modules to exist; the survey recorded no refs from src/index (it only re-exports), so decompose saw it as independent. Matches 'entry points last' in the methodology.
- src-index: referenceTests cleared. The four test files exercise functions owned by validate-validate (test/validate.ts) and satisfies-satisfies (test/compare.ts, test/satisfies.ts, test/sort.ts), which already map them; decompose assigned them to src-index too because every test imports the package entry.
- utils-utils also owns the crate's public Error enum and the JS-number helpers (parseInt prefix parse, Number-to-String), per the cross-cutting rule that the error hierarchy belongs to the foundation.
