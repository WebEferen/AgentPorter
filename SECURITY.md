# Security policy

## Reporting a vulnerability

Please use GitHub private vulnerability reporting: open the repository's Security tab and choose
"Report a vulnerability". Do not open a public issue for a security problem.

Only the latest release is supported.

## What AgentPorter executes

AgentPorter runs code on your machine as part of its normal work. Know what you point it at.

- **Oracles run the original.** The contract phase imports or executes the source project to record
  fixtures. Port only code you would be willing to run.
- **Artifact mode runs the artifact.** Probes and `porter.py cli record` execute the binary with your
  permissions, an empty stdin, a temporary working directory and a temporary HOME. That is not a
  sandbox. Analyze untrusted binaries inside a VM or container.
- **The port is built and tested.** The implement and verify phases run the target toolchain, its
  package manager and its tests.
- **REA is downloaded on demand** with `npx -y rea-agents@<pinned version>` unless you set
  `AGENTPORTER_REA` or have `rea` on the PATH.

## Network access

`porter.py` contacts public package registries during the deps phase and caches the answers in
`.porter/cache/registry/`. It also clones a source URL when given one, and downloads REA in artifact
mode. Use `porter.py registry ... --offline` to work from the cache only.

## Legal basis for reverse engineering

Artifact mode requires a recorded authorization: you own the artifact, its license permits analysis, or
interoperability law applies where you are. AgentPorter records the answer but does not check it, and
this is not legal advice.
