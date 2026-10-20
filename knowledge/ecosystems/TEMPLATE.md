# <Language> ecosystem

| Field | Value |
| --- | --- |
| Registry | <name and URL> |
| Registry adapter | `porter.py registry lookup --registry <id>` |
| Last verified | YYYY-MM-DD |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
curl -s -A "agentporter" "<url>"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | | |
| Latest version and date | | |
| License | | |
| Adoption signal | | |
| Search | | |

## 2. Maturity signals

What the registry exposes (release cadence, downloads, dependents,
deprecation, advisories) and how to read each one. Name what is missing.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |

Scopes: how runtime, dev, build, optional and peer dependencies are expressed.

## 4. Package layout

Where source, tests and entry points live by convention.

## 5. Test runners

## 6. Lint and format

## 7. Type checking

## 8. Build and publish

## 9. Runtime version policy

Supported versions and how a package declares the versions it supports.

## 10. License fields

Where the license is declared in the manifest and in the registry response.

## 11. AgentPorter templates

Which oracle template (`knowledge/oracles/<lang>/`) and fixture harness
(`knowledge/harnesses/<lang>/`) apply to this language and how to run them.
