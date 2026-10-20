# Examples

Five small libraries, each ported by AgentPorter in one unattended Claude Code session. Every folder has
the upstream code at the pinned commit in `original/` and the finished port in `port/`. The port keeps its
`.porter/` workspace, so the contract, the recorded fixtures, the plan, the divergence log and the parity
report sit next to the code.

| Example | Original | Port | Level | Fixtures exact | Reference tests | Cost | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [ms-to-go](ms-to-go/) | ms 2.1.3 (JavaScript) | Go | DIVERGENT | 1458 of 1490 | 44 of 49 | $18.48 | 65 min |
| [shellquote-to-python](shellquote-to-python/) | go-shellquote (Go) | Python | EXACT | 1083 of 1083 | 29 of 29 | $14.60 | 48 min |
| [scule-to-go](scule-to-go/) | scule 1.3.0 (TypeScript) | Go | EXACT | 2984 of 2984 | 63 of 63 | $21.19 | 66 min |
| [compare-versions-to-rust](compare-versions-to-rust/) | compare-versions 6.1.1 (TypeScript) | Rust | DIVERGENT | 4239 of 4288 | 406 of 422 | $19.76 | 69 min |
| [humps-to-rust](humps-to-rust/) | pyhumps 3.8.0 (Python) | Rust | DIVERGENT | 4625 of 4627 | 18 of 18 | $22.44 | 81 min |

No case fails in any of them. DIVERGENT means some cases differ on purpose, each written down with a
reason; the example READMEs list them. The remaining ms cases match through the error map (8) or are
divergent (24). Reference tests are the upstream's own tests ported to the target; the ones not counted as
passing are marked out of scope or covered by a divergence, each with a reason.

## How they were made

Each port is one `claude -p` session on Claude Opus 5.5 with the plugin loaded and a $25 spending cap.
Nobody answered questions during the runs. The prompt was the same for all five except for the answers,
which each example README quotes:

```text
You are running AgentPorter unattended, as an end-to-end test of the plugin. Nobody will answer questions.

Rules for this run:
- Run the whole pipeline through verify and implement every unit, as if `--implement` was passed.
- When a phase stops at a gate, use the pre-approved answers below. Record each one with the gate command
  the skill names, using the answer text as the note, then continue.
- If a gate item comes up that the answers do not cover, pick the conservative option, record it with a
  note that starts with "unattended:" and continue.
- Follow the skills exactly. Do not work around a refused porter.py command by editing state.json or
  config.json. If the plugin blocks you and you cannot resolve it within the rules, stop.
- Do not push anything anywhere. Local commits in this directory are fine.
- At the end, write AGENTPORTER_FEEDBACK.md in the current directory: every plugin bug, confusing or wrong
  instruction, refused command, missing template or wasted step you hit, each with the phase, what
  happened and what you did about it. Then print the stage card.

Pre-approved answers:
<per example>

Start the port now:
/agentporter:port <checkout of the original> --to <language> --name <package> --implement
```

What that means for the results:

- The divergences were accepted by those pre-written answers or by the agent's own "unattended:" notes,
  not by a person who looked at them. In a normal run each one is a question for you at a gate.
- Some runs got close to the cap, and the agent then did a review or a verify pass inline instead of
  handing it to a fresh reviewer or verifier agent. Each example README says where.
- The runs were also end-to-end tests of the plugin. The bugs they hit are fixed in this version (see the
  [changelog](../CHANGELOG.md)), so some workarounds in these workspaces are no longer needed.
- Cost and time cover the whole session, subagents included.
- The perf column in each PARITY.md compares the per-case wall time of the original and the port. These
  calls take microseconds, so it mostly measures harness overhead. It is not a benchmark.

Local paths were rewritten when the examples were copied in: the original's checkout reads
`.porter/cache/source` and the plugin reads `agentporter`. The feedback files and harness run directories
were left out.

## Check one yourself

Each example README has its commands. The pattern is the same everywhere: run the port's tests, replay
every recorded case through the port's harness, then compare with what the original returned.

```sh
cd examples/scule-to-go/port
go test ./...
go run ./cmd/porter-harness --workspace .porter --run local
python3 ../../../scripts/porter.py parity collect --run local --dry-run
```

`--dry-run` prints the comparison and leaves the committed `parity.json` alone. With the CLI installed,
`agentporter parity collect --run local --dry-run` does the same. Recording the fixtures again needs the
original checked out at `port/.porter/cache/source` and its runtime.

## Licenses

Each example keeps the license of the project it ports, in both `original/` and `port/`: MIT for ms,
go-shellquote, scule and compare-versions, and the Unlicense for pyhumps. The rest of this repository is MIT.
