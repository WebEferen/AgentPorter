# Survey: <package> <version>

<One paragraph: what the project is, who uses it, and the one-line verdict on port size and risk.>

## Facts

<Paste the facts table printed by `porter.py survey --facts`. Keep it as printed.>

## Scope

- Kind: <library | cli | sdk | service | app | mixed>. <For service or app: which library parts the pipeline covers and what stays out.>
- In scope: <packages, modules or commands>.
- Out of scope: <generated code, vendored code, examples, platform shims>, each with a reason.

## Where the risk is

| Module | Coupling | Why it is risky | Risk tags |
| --- | --- | --- | --- |
| <module> | <pure / io / runtime-welded / native> | <one line> | <tags> |

## Flags for the user

- License: <SPDX>. <Copyleft note if any: the port inherits the terms.>
- Tests: <count and ratio>. <If thin: the contract leans on docs and generated fixtures.>
- Sampling: <"full scan" or "sampled N of M files; these areas were not read">.
- Native code, FFI, subprocess or OS-specific paths: <list or "none found">.
