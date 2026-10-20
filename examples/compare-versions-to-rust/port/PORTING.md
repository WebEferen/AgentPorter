# Porting status

This package is being ported with [AgentPorter](https://github.com/WebEferen/AgentPorter).
All analysis, decisions and evidence live in [`.porter/`](.porter).

```text
AgentPorter  compare-versions 6.1.1 -> rust (compare-versions-port)      .porter/ at 2026-10-20 20:20Z
Phase: verify (DONE)   gates: target given, deps no items, strategy approved   stale: none
Units: 4 total  DONE 4
Parity so far: utils-utils ASSERTED, validate-validate DIVERGENT, src-index ASSERTED, satisfies-satisfies DIVERGENT
Next: port complete: publish PARITY.md and follow the release checklist (/agentporter:status release)
```

| Artifact | Purpose |
| --- | --- |
| [survey.md](.porter/survey.md) | what the source is and where the risk is |
| [deps.md](.porter/deps.md) | every dependency and its decision |
| [contract/contract.md](.porter/contract/contract.md) | the behavioral contract being ported |
| [decomposition.md](.porter/decomposition.md) | how the port was cut into units |
| [strategy.md](.porter/strategy.md) | idiom map, order, risks |
| [PARITY.md](.porter/PARITY.md) | parity evidence against the original |
| [decisions.md](.porter/decisions.md) | human decisions |

| Unit | Layer | Wave | Status | Parity |
| --- | --- | --- | --- | --- |
| utils-utils | foundation | 0 | DONE | ASSERTED |
| validate-validate | core | 1 | DONE | DIVERGENT |
| satisfies-satisfies | core | 1 | DONE | DIVERGENT |
| src-index | entry | 2 | DONE | ASSERTED |
