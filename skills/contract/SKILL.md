---
name: contract
description: Capture what the original program promises, independent of any language, so a port can be tested against it. Inventories the public surface into contract/api.json, reads the source tests as the executable spec, records the leak list of internals that are observable, and builds an oracle that runs the original (pinned version or the shipped artifact) to record language-neutral JSON fixtures, including seeded generated inputs. Use as the contract phase of /agentporter:port, or when the user wants a behavioral spec and test corpus recorded from an existing implementation.
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# contract

Where this sits: after deps. It produces `contract/api.json`, `contract/contract.md`,
`contract/units/<unit>.md`, `contract/error-map.json`, `oracle/` and `fixtures/`, plus a draft `plan.json`.
The strategy, implement and verify phases depend on it. It never edits the source.
Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`. Fixture contract:
`${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/CONTRACT.md` (read it before step 5).

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight contract`. Stop and report if it fails.
2. `porter decompose --draft`. This groups the public symbols into draft units so fixtures can be filed per
   unit now; the strategy phase finalizes the cut.
3. If an Agent tool is available, spawn `agentporter:contract-extractor` with the workspace path and the
   brief "Build the contract and record fixtures, following your checklist." Otherwise read
   `${CLAUDE_PLUGIN_ROOT}/agents/contract-extractor.md` and do its checklist inline. It produces:
   - `contract/api.json` (schema `knowledge/schemas/api.schema.json`): every public symbol with id
     `<module>:<name>`, kind, signature, errors, side effects, `inScope`, `unit`, and a `reason` when out of
     scope. In artifact mode the symbols come from `recover/recovery.json` interface items (`interfaceId`).
   - `oracle/cases/<unit>.json`: harvested test cases, hand-written edge cases and seeded generators.
   - fixtures recorded by running the original (step 4).
   - `contract/contract.md` (template `knowledge/templates/contract.md`), one `contract/units/<unit>.md` per
     unit (template `knowledge/templates/unit-contract.md`) and `contract/error-map.json` when error types
     will differ in the target.
4. Recording fixtures, whichever applies:
   - Library with source: copy `${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/<source language>/` into
     `.porter/oracle/driver/` (the copy pins the driver with the workspace), run `porter fixtures expand`,
     then run that copy with the command its README gives, the plugin path replaced by `.porter/oracle/driver/`.
   - CLI, from source or artifact: `porter fixtures expand --unit <unit>` then
     `porter cli record --unit <unit>` (the command comes from `recovery.json` or `--exe`).
   - Then `porter fixtures validate` and `porter fixtures summary`.
5. Units that cannot have fixtures (pure side effects, UI, network) get `noFixturesReason` in `plan.json`
   and a behavioral assertion plan in their unit contract. Postflight also wants at least one fixture per
   in-scope function, method and class; a single symbol that cannot have one gets `noFixturesReason` on
   its `api.json` entry.
6. Keep each in-scope symbol's `unit` in `api.json` equal to the draft unit its fixtures are filed under.
   The strategy phase re-cuts the final units from `api.json`.
7. `porter state postflight contract`. Fix every reported error and run it again.

## Rules

- The oracle runs the pinned original: the source checkout at the recorded commit, or the artifact with the
  recorded SHA-256. Never record from a different version.
- Nondeterministic output (time, randomness, hash order) is either controlled in the case input or
  normalized, and the normalization is written in the unit contract.
- Behavior that depends on the source runtime goes in the leak list and to the strategy phase as a
  decision. It is never silently copied or silently dropped.
- Generated cases use fixed seeds so re-recording gives the same inputs.
