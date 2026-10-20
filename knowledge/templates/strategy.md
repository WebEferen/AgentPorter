# Strategy: <package> -> <target language> (<target package name>)

<One paragraph: the overall approach, the tracer bullet, and what the user is approving at the gate.>

## Per-unit strategy

| Unit | Layer | Strategy | Why |
| --- | --- | --- | --- |
| <unit> | <layer> | <contract port / code port / wrap / drop> | <one line> |

## Idiom map

Seeded from `knowledge/pairs/<pair>.md` and specialized to this codebase.

| Concern | Source idiom | Target idiom | Rule for this port |
| --- | --- | --- | --- |
| Errors | <raise ValueError> | <throw RangeError> | <...> |
| Absence | <None> | <undefined> | <...> |
| Async | <...> | <...> | <...> |
| Numbers | <...> | <...> | <...> |
| Strings and bytes | <...> | <...> | <...> |
| Regex | <...> | <...> | <...> |
| Dates | <...> | <...> | <...> |
| Module layout and naming | <...> | <...> | <...> |

## Dropped workarounds and new substrate

- Dropped: <source workaround the target makes unnecessary>.
- New substrate: <what the target lacks and which unit builds it>.

## Scope gauntlet

| Item | Decision | Reason |
| --- | --- | --- |
| <symbol or feature> | <now / out of scope / seam for later> | <...> |

## Risk register

| Risk | Mitigation | Signal that it is happening |
| --- | --- | --- |
| <...> | <...> | <...> |

## Scaffold

- Package layout: <tree>.
- Toolchain: build <...>, test <...>, lint <...>, format <...>, typecheck <...>.
- Harness: `knowledge/harnesses/<target>/` copied to <path>; bindings in <path>.
- CI: <workflow file and jobs>.

## Budgets

Attempts per unit: <n>. Discovered units before returning to the user: <n>. PORT depth and LOC: <n>, <n>.
