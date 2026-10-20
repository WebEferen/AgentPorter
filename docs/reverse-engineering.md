# Porting without source code

Sometimes the only thing left of a tool is the binary: the source is lost, owned by a vendor that is
gone, or never published. AgentPorter can still port it. The `recover` phase rebuilds the observable
behavior with [REA (Reverse Engineer Anything)](https://github.com/morluto/rea) and with black-box runs of
the artifact. The rest of the pipeline then works from that evidence.

The agent-facing method is in `knowledge/rea.md`. This page is the user guide.

## Before you start

- **You need a basis to analyze the artifact.** You own it, its license permits analysis, or
  interoperability law applies where you are. AgentPorter asks once and records your answer in
  `decisions.md`. It refuses to start the recover phase without one. This is not legal advice.
- **Decompiled code is evidence only.** It helps the agent understand behavior. It is never copied into
  the port. Implementers work from the contract and the fixtures.
- **The artifact gets executed.** Probes and the CLI oracle run it with your permissions, an empty stdin,
  a temporary working directory and a temporary HOME. That is not a sandbox. Run untrusted artifacts
  inside a VM or container.

## Installing REA

AgentPorter looks for REA in this order:

1. The `AGENTPORTER_REA` environment variable, for example `/opt/rea/bin/rea`.
2. `rea` on the PATH, from `npm install -g rea-agents`.
3. `npx -y rea-agents@6.7.0`, downloaded on first use.

REA needs Node 22.19 or newer. Go and Rust build metadata, .NET metadata, Mach-O inspection,
JavaScript bundle analysis and process capture work out of the box. Function-level analysis of other
native code needs Ghidra, Hopper or IDA configured for REA. WASM inspection needs WABT.

## What gets recovered

| Artifact | Evidence |
| --- | --- |
| Go binary | Go version, main module and version, every dependency module with its version |
| Rust binary | The cargo-auditable dependency list, when the binary has one |
| .NET assembly | Types, member signatures, string literals, P/Invoke boundaries |
| JAR, APK | Manifest, classes, components |
| JavaScript bundle, Electron app, ASAR | Module graph, exports, readable sources with provenance |
| WASM module | Imports and exports |
| Mach-O, ELF, PE | Linked libraries, imports, exports, symbols |
| Any CLI that runs here | Commands, flags, arguments and exit codes parsed from `--help`, `-h`, `--version` and a no-argument run |

Everything lands in `.porter/recover/evidence/` with an index. `recover/recovery.json` merges it into
interface items, behaviors, embedded dependencies and unknowns. Each item has a confidence (HIGH when
observed, MEDIUM when read from help text or metadata, LOW when inferred) and a pointer to its evidence.

## Walkthrough: gron

[gron](https://github.com/tomnomnom/gron) is a small Go CLI that flattens JSON into greppable
assignments. Starting from the release binary only:

```text
mkdir gron-port && cd gron-port && git init
claude
> /agentporter:port ./bin/gron
```

The router asks for the basis of the analysis, records it, and runs `recover detect`:

```text
| format    | macho                       |
| arch      | arm64                       |
| language  | go                          |
| kind      | cli                         |
| runnable  | True                        |
| language evidence | Go build-information header |

REA plan:
  rea inspect-artifact <path> --json     # identity, observations and REA's suggested next probes
  rea inspect-go-binary <path> --json    # Go version, main module, dependency modules and build settings
  rea inspect-macho <path> --json        # load commands, linked libraries and symbols
```

After the REA steps and the black-box probe, `recovery.md` holds what was learned. An excerpt:

```text
| Package   | github.com/tomnomnom/gron v0.7.1 |
| Toolchain | go1.26.0                         |
| Oracle    | runnable here                    |

| flag:ungron | flag      | -u, --ungron | Reverse the operation (turn assignments back into JSON) | MEDIUM |
| flag:stream | flag      | -s, --stream | Treat each line of input as a separate JSON object      | MEDIUM |
| exit:3      | exit-code | 3            | Failed to form statements                               | MEDIUM |

| github.com/fatih/color | v1.7.0 | go | go-buildinfo |
```

The agent adds behaviors it confirmed by running the binary, lists open questions as unknowns, and
stops at the recover gate if anything is weak. From there:

- **survey** builds a synthetic survey from `recovery.json`.
- **target** recommends a language. For a Go CLI with no other input it suggests Rust, since a single
  static binary fits a CLI best. Telling it that the maintainers write TypeScript changes the ranking.
- **deps** decides each embedded Go module, such as `fatih/color`, for the target.
- **contract** records fixtures by running the original binary on generated JSON inputs.
- **verify** runs the port on the same cases and fails on any mismatch in exit code, stdout or stderr.

## Using REA as an MCP server

If REA is already connected to your agent as an MCP server, the agent can call its tools directly. It
saves each result as JSON and registers it:

```text
porter.py recover register go-buildinfo --file result.json --command "inspect_go_binary" --tool "rea 6.7.0 (MCP)"
```

AgentPorter never runs `rea setup` for you, because that command changes your agent configuration.
