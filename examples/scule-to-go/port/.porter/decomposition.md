# Decomposition

Proposed by `porter.py decompose` on 2026-10-20.
Budgets: at most 400 LOC and 8 public functions, classes and types with members per unit (constants and aliases do not count), merge below 30 LOC.

## Layer map

- core: src-kebabcase, src-isuppercase, types-types

## Units in order

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | src-kebabcase (tracer) | core | 0 | 3 | pascalCase, kebabCase, titleCase | - | - |  |
| 2 | src-isuppercase | core | 0 | 21 | isUppercase, splitByCase, upperFirst, lowerFirst, camelCase, snakeCase, flatCase, trainCase | - | nullability |  |
| 3 | types-types | core | 0 | 42 | CaseOptions | - | nullability |  |

## Why the cuts are where they are

- src/index: 24 LOC or 11 public functions/classes over budget; split into 2 units by root reachability
- tracer bullet: src-kebabcase (closure src-kebabcase), the lowest-risk vertical slice

## Orphans

- `src/index:STR_SPLITTERS`: unreachable from any root; kept with its module cluster src/index
- `src/index:titleCaseExceptions`: unreachable from any root; kept with its module cluster src/index
- `src/types:Splitter`: unreachable from any root; kept with its module cluster src/types
- `src/types:FirstOfString`: unreachable from any root; kept with its module cluster src/types
- `src/types:RemoveFirstOfString`: unreachable from any root; kept with its module cluster src/types
- `src/types:IsUpper`: unreachable from any root; kept with its module cluster src/types
- `src/types:IsLower`: unreachable from any root; kept with its module cluster src/types
- `src/types:SameLetterCase`: unreachable from any root; kept with its module cluster src/types
- `src/types:CapitalizedWords`: unreachable from any root; kept with its module cluster src/types
- `src/types:JoinLowercaseWords`: unreachable from any root; kept with its module cluster src/types
- `src/types:LastOfArray`: unreachable from any root; kept with its module cluster src/types
- `src/types:RemoveLastOfArray`: unreachable from any root; kept with its module cluster src/types

## Final units (after adjustments)

| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Strategy | Fixtures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | split (tracer) | core | 0 | ~70 | isUppercase, splitByCase, upperFirst, lowerFirst | - | code-port | 966 |
| 2 | cases | core | 1 | ~85 | pascalCase, camelCase, kebabCase, snakeCase, flatCase, trainCase, titleCase, CaseOptions | split | contract-port | 1982 |

## Adjustments

The agent records every change it makes to the proposal here, one line each: what changed and why.

- Replaced the proposed units (src-kebabcase, src-isuppercase, types-types) with `split` and `cases`: the proposal ignored the api.json units the fixtures are filed under, sized each function by one overload line, and missed the call edges (camelCase->pascalCase, flatCase->kebabCase, case functions->splitByCase).
- `split` owns isUppercase, splitByCase, upperFirst, lowerFirst: the leaf layer every converter calls; `cases` depends on it, so the cut is acyclic.
- CaseOptions moved from types-types to `cases`: it is the options struct of four functions there and has nothing to call; types-types is dropped.
- Private helper types in src/types.ts are not owned by any unit: they serve only the out-of-scope type-level helpers.
- `split` is the tracer: it holds the riskiest semantics (UTF-16 split, full case mapping), so the harness and parity path are proven on them first.
