# CLI reference

`scripts/porter.py` is the deterministic half of AgentPorter. The skills call it for everything that
must not depend on a model's memory: workflow state, registry lookups, dependency graphs,
decomposition, fixtures, parity and REA runs. It needs Python 3.11 or newer and nothing else.

There are two ways to run it:

```text
python3 path/to/AgentPorter/scripts/porter.py <command> ...
agentporter <command> ...          # after: pipx install git+https://github.com/WebEferen/AgentPorter
```

Most commands look for `.porter/` in the current directory or its parents. Pass `--workspace <dir>` to
point at another one. Errors exit with code 2, and checks that fail on purpose (a failed postflight, a
parity GAP) exit with code 1.

## Workspace and workflow

| Command | What it does |
| --- | --- |
| `init --source <path or url> [--to <lang>] [--mode auto\|code\|artifact] [--authorization <text>] [--ref <ref>] [--subpath <dir>] [--name <pkg>] [--commit-policy per-unit\|never]` | Creates `.porter/` in the current directory. Without `--to`, the target phase picks the language. A file, `.app` or `.asar` source means artifact mode. |
| `source fetch [--ref <ref>]` | Pins the source commit. A URL is cloned into `.porter/cache/source`. |
| `state preflight <phase> [--rerun] [--check]` | Refuses out-of-order work and prints the stage card. `--rerun` reopens a finished phase and marks everything downstream STALE. |
| `state postflight <phase>` | Validates the phase artifacts, records their hashes, and sets DONE or GATE_WAIT. |
| `state gate <recover\|deps\|strategy> approve\|reject --note <text>` | Records the user's decision in `decisions.md`. The target gate goes through `target choose`. |
| `state authorize --note <text>` | Records who authorized reverse engineering an artifact. |
| `state source [--license <spdx>] [--name <pkg>] [--version <v>] --note <text>` | Records source facts the user states, for artifact mode where no manifest has them. |
| `state unit set <unit> <status> [--task <task>] [--level <level>] [--note <text>]` | Moves a unit through its state machine. Only legal transitions are accepted. |
| `state unit task <unit> <task>` | Records the current step of the unit checklist. |
| `state next [--json]` | Prints the single next action. |
| `state board [--units]` | Prints the stage card, optionally with the unit table. |
| `state validate` | Validates every artifact in the workspace against its schema. |
| `state plan-sync` | Syncs units from `plan.json` into `state.json`. Needed after adding a discovered unit. |
| `state porting-md` | Writes `PORTING.md`, the human summary of the port. |

Phases are `recover`, `survey`, `target`, `deps`, `contract`, `strategy`, `implement` and `verify`.
Unit tasks, in order: `read-contract`, `scaffold`, `implement`, `mark-divergences`, `port-tests`,
`wire-fixtures`, `green`, `review`, `apply-findings`, `verify`, `report`, `commit`.

## Analysis

| Command | What it does |
| --- | --- |
| `survey [<path>] [--subpath <dir>] [--write] [--json]` | Scans the source: languages, modules, symbols, entry points, tests, risk signals. In artifact mode it builds the survey from `recovery.json`. |
| `deps-graph [<path>] [--all] [--write] [--json]` | Parses manifests and lockfiles into a normalized dependency list. |
| `usage-scan [<path>] [--dep <name>] [--all] [--write] [--json]` | Measures the used surface of each dependency: symbols, call sites, modules. |
| `registry lookup <names...> --registry <reg>` | Confirms that a package exists and records version, license, release date and adoption. Exit 1 when any name does not exist or its lookup failed. |
| `registry search <terms...> --registry <reg>` | Searches a registry for candidates. |
| `registry verify-deps` | Re-checks every MAP and SHIM candidate in `deps.json` and fills `verified`. Records the source license of every PORT and VENDOR dependency. Exit 1 when a candidate does not exist. |
| `target score [--candidates <list>] [--consumers <langs>] [--team <langs>] [--set <lang.crit=v>] [--weight <crit=w>] [--write] [--json]` | Scores candidate target languages. `--write` produces `target.json` and `target.md`. |
| `target choose <lang> --note <text>` | Records the user's language choice and approves the target gate. |
| `decompose [--draft] [--force] [--max-loc N] [--max-symbols N] [--min-loc N]` | Proposes units, layers, waves, the tracer bullet and the order. See [decomposition.md](decomposition.md). |

Registries: `npm`, `pypi`, `crates`, `go`, `maven`, `packagist`, `rubygems`, `nuget`, `hex`. Lookups
are cached in `.porter/cache/registry/`. `--offline` uses only the cache, and `--refresh` refetches regardless of cache age.

## Reverse engineering

| Command | What it does |
| --- | --- |
| `recover detect [<path>] [--write] [--json]` | Fingerprints the artifact (format, native language, runnable) and prints the REA commands that fit it. |
| `recover rea <name> <rea args...> [--rea <cmd>] [--timeout <s>]` | Runs one REA command with `--json` and saves its output as evidence. |
| `recover probe [--exe <path>] [--probe=<args>] [--stdin=<text>] [--name <name>]` | Runs the artifact with help, version and no-argument probes and parses flags, arguments and exit codes. Use the `=` form when the argv starts with a dash. |
| `recover register <name> --file <path> [--producer rea\|manual] [--command <text>] [--tool <name>]` | Adds evidence produced elsewhere, such as REA MCP tool output. |
| `recover import [--render]` | Merges all evidence into `recovery.json` (keeping edits) and renders `recovery.md` when missing. |

REA is found through `AGENTPORTER_REA`, then `rea` on the PATH, then `npx -y rea-agents@6.7.0`.

## Fixtures and parity

| Command | What it does |
| --- | --- |
| `fixtures expand [--unit <unit>]` | Turns case specs in `oracle/cases/` into concrete inputs in `oracle/expanded/`. Generated cases are seeded. |
| `fixtures validate` | Checks every fixture file against the schema and counts cases per unit. Exits 1 on errors. |
| `fixtures summary` | Prints a table of cases per unit, by expectation kind and origin. |
| `fixtures dedupe <unit> [--dry-run]` | Drops cases whose call and input repeat an earlier case. |
| `fixtures merge <files...> --into <file> [--prefer-new]` | Merges fixture files for one unit. |
| `fixtures diff <old> <new> [--limit N]` | Compares two recordings, for example before and after an upstream upgrade. |
| `cli record --unit <unit> [--exe <path>] [--out <file>] [--timeout <s>]` | Black-box oracle: runs the original program on the expanded cases and writes fixtures and timings. |
| `cli run --exe <path> --unit <unit> --run <id>` | Black-box harness: runs the port on the same cases and writes actuals. |
| `parity collect [--unit <unit>] [--run <id>] [--show N] [--dry-run]` | Compares actuals with fixtures and writes `parity.json` (not with `--dry-run`). Exits 1 when a unit is GAP. |
| `parity report [--copy-to <path>]` | Renders `PARITY.md`. |
| `parity reftests <junit\|vitest\|jest\|gotest\|cargo> <report> [--unit <unit>] [--replace]` | Imports ported reference test results. Tests are matched by `[ref: id]` in their names (gotest also reads it from `t.Log` output). `cargo` takes the captured output of `cargo test --no-fail-fast 2>&1` and reads the tags from `// [ref: id]` comment lines directly above each `#[test] fn`. |
| `parity markers` | Lists `DIVERGENCE(id)` markers in the target code. `parity collect` checks them against `divergences.json` in both directions. |

The fixture format and the oracle protocol are specified in `knowledge/oracles/CONTRACT.md`.
