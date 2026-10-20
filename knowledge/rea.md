# Reverse engineering with REA

AgentPorter starts from source code by default. When there is no source, only a built artifact (a binary,
a .NET assembly, a JAR or APK, a minified JavaScript bundle, an Electron app, a WASM module), the recover
phase rebuilds enough of the original's behavior to port it. It uses
[REA, Reverse Engineer Anything](https://github.com/morluto/rea) for static evidence and runs the artifact
itself as the black-box oracle.

Tested with REA 6.7.0 (`rea-agents` on npm, Node 22.19+, 24.11+ or 26+).

## Before anything runs

1. Authorization. Reverse engineering is legal only with a basis: the user owns the artifact, the license
   permits analysis, or interoperability law applies where the user is. Ask once, record the answer with
   `porter.py state authorize --note "..."`. Preflight refuses the recover phase without it. This is not
   legal advice; when the user is unsure, say so and stop.
2. Clean room. Decompiled or disassembled code is evidence for understanding behavior. It is never copied
   into the port. Implementers work from `contract/` and `fixtures/`. The recover gate repeats this when
   recovered source came from a decompiler. No agent fetches, clones or reads the original's source code,
   even when it is public: the port rests on observed behavior only. If the source turns out to be public,
   tell the user, who can restart in code mode instead.
3. Execution. Probes and the CLI oracle run the artifact with the user's permissions, an empty stdin, a
   temporary working directory and a temporary HOME. That is not a sandbox. If the artifact is untrusted,
   run AgentPorter inside a VM or container.

## Installing REA

Any of these works; AgentPorter finds REA in this order:

1. `AGENTPORTER_REA` environment variable, a command such as `/path/to/rea` or `npx -y rea-agents@6.7.0`.
2. `rea` on PATH (`npm install -g rea-agents`, or `npx rea-agents setup`, which also registers REA's MCP
   server and its own skill with your agent).
3. `npx -y rea-agents@6.7.0` when npx exists.

Deep native analysis (`analyze`, `function`, `decompile`, `xrefs` with `--provider`) needs Ghidra, Hopper
or IDA configured for REA. Go and Rust metadata, .NET metadata, Mach-O inspection, JavaScript application
analysis and process capture need no provider.

## The recover loop

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command.

```text
porter recover detect --write                       # format, arch, original language, runnable here?, REA plan
porter recover rea artifact inspect-artifact <abs path>
porter recover rea <name> <command from the plan> <abs path>   # one call per plan step that applies
porter recover probe                                # CLI: --help, -h, --version, no args; parses flags and exit codes
porter recover import                               # merges evidence into recover/recovery.json, renders recovery.md
```

`recover rea` appends `--json`, strips REA's progress lines, saves the result under
`.porter/recover/evidence/<name>.json` and indexes it. Use absolute artifact paths; REA resolves relative
paths against `.porter/recover/`.

If REA is connected as an MCP server instead, call its tools directly, save each result as JSON and add it
with `porter recover register <name> --file <path> --command "<tool name>" --tool "rea <version> (MCP)"`.

## Which REA command for which artifact

`recover detect` prints this plan for the artifact it found:

| Artifact | REA commands | What they give the port |
| --- | --- | --- |
| any | `inspect-artifact` | identity, observations, REA's own suggested next probes |
| Go binary | `inspect-go-binary` | Go version, main module and version, dependency modules: the deps phase input |
| Rust binary | `inspect-rust-binary` | cargo-auditable dependency list (missing section proves nothing) |
| .NET assembly | `inspect-managed-artifact`, `inspect-managed-members`, `inspect-managed-native-boundaries` | identity, types and member signatures (the public surface), string literals, P/Invoke boundaries |
| JavaScript app, bundle, ASAR | `analyze-javascript-application`, `recover-javascript-sources <path> <new abs dir>` | module graph and exports; readable modules with provenance |
| Android APK | `inspect-android-package`, then `search-android-classes`, `inspect-android-class` | manifest, components, class inventory |
| WASM | `inspect-wasm-artifact` (needs WABT) | imports and exports |
| Mach-O, macOS app | `inspect-macho` | linked libraries, imports, exports |
| other native | `analyze --provider ghidra`, then `search`, `function`, `decompile` | function inventory and strings; read specific behaviors only |

Process capture (`capture-process`, `compare-process-captures`) runs a program under a PTY and compares two
runs. AgentPorter's own `porter.py cli record` and `cli run` are the primary oracle for CLIs because they
pipe stdin and keep stdout and stderr apart. Use REA capture in the verify phase for interactive or
TTY-dependent behavior (colors, prompts, terminal size), on a handful of scenarios, and save both captures
and the comparison as evidence.

## What goes into recovery.json

- `interface`: commands, flags, arguments, exit codes, functions, classes, exports, endpoints. Each item has
  a confidence (HIGH when observed directly, MEDIUM when read from help text or metadata, LOW when inferred)
  and at least one evidence reference like `evidence/probe.json#/runs/0`.
- `behaviors`: statements about what the original does, each backed by evidence, for example
  "sorts object keys in output" backed by a probe run.
- `modules`: embedded dependencies (from Go build info, cargo-auditable, managed references).
- `unknowns`: open questions with the probe that would answer them. Every unknown is a gate item.
- `oracle`: whether the artifact runs on this host and the command that runs it.
- `source`: a recovered source tree, if REA recovered one, with its origin (`sourcemap`, `decompiled`, ...).

`porter.py recover import` keeps your edits: it adds new evidence-derived items and never overwrites an item
you changed. Group interface items with the `group` field; the survey turns each group into a module and the
decomposition turns modules into units.

## From recovery to the rest of the pipeline

- survey: `porter.py survey --write` builds a synthetic survey from `recovery.json` (one module per group).
- deps: `porter.py deps-graph --write` lists the embedded modules; every one needs a decision. Usage is
  unknown without source, so reason from behaviors and probes.
- contract: fixtures come from running the artifact. For CLIs write `oracle/cases/<unit>.json` with
  `input.argv`, `input.stdin`, `input.files`, `input.env`, then `porter.py fixtures expand` and
  `porter.py cli record --unit <unit>`. For libraries, drive the artifact through the oracle for its
  platform (the JVM driver loads a JAR, the JavaScript driver imports a bundle).
- verify: `porter.py cli run --exe "<command that runs the port>"`, then `porter.py parity collect`.
