# Dependencies: <package> -> <target language>

<One paragraph: how many runtime dependencies, how many need work, and the gate items if any.>

## Runtime dependencies

| Dependency | Version | Role | Used surface | Decision | Candidate | Confidence | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <name> | <locked version> | <runtime-library / framework / platform binding> | <symbols and call sites, from usage.json> | <ABSORB / MAP / SHIM / PORT / VENDOR / DROP / DEFER> | <target package@version or stdlib API> | <HIGH / MEDIUM / LOW> | <cache/registry/... record, docs URL> |

## API deltas for MAP and SHIM

### <dependency> -> <candidate>

- <source call> -> <target call>: <difference that matters to the contract, or "same">.
- Shim contract (SHIM only): <what the adapter guarantees>.

## Dev, build and test tools

| Source tool | Target tool | Note |
| --- | --- | --- |
| <pytest> | <vitest> | <from the ecosystem reference> |

## Gate items

- <item from `porter.py state postflight deps`, with a recommendation>
