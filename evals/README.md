# Evals

One case per directory, three per skill, run with `claude plugin eval`. Each case seeds a workspace at a
known stage with `scaffold.sh`, which calls `_lib/stage.py`, then grades what the agent did:
`porter.py` calls it made or avoided, files it created, and an LLM rubric on its reply.

Cases tagged `stage-awareness` check that the agent resumes at the stored unit task, refuses to build on
a STALE phase, and cannot mark its own work verified.

## Running

The scaffolds run `porter.py` and the Python oracle, so they need `--scaffold`. The agent needs Bash, Write
and Edit to work on the seeded workspace.

```text
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit
claude plugin eval . --tag smoke --runs 1 --scaffold --trust-plugin --allow-tools Bash Write Edit --ablation none
claude plugin eval . --case verify-reports-gap --scaffold --trust-plugin --allow-tools Bash Write Edit
```

Evals bill against your account. The full suite is 31 cases with 3 runs each. The `smoke` tag selects the
15 short cases. The deps cases that look packages up need network access.

## Stages

`python3 evals/_lib/stage.py <stage>` builds a stage in the current directory, which is handy when writing
a new case. The source project is a small Python library, `textkit`, in `upstream/textkit`. `artifact`
stages compile a small C command-line tool into `bin/wc2` instead, so they need `cc`, `clang` or `gcc`.

| Stage | Workspace |
| --- | --- |
| `empty`, `src`, `artifact-src` | no workspace yet |
| `init`, `init-notarget` | after `porter.py init`, with or without `--to typescript` |
| `surveyed`, `surveyed-notarget` | survey DONE (add `--license GPL-3.0-only` for a copyleft source) |
| `deps-done`, `contract-done`, `strategy-done` | that phase DONE, with real fixtures recorded by the oracle |
| `implement-mid` | unit `core` IN_PROGRESS at task `port-tests`, some target code written |
| `implement-stale` | strategy STALE |
| `implement-reviewed` | unit `core` REVIEWED, not verified |
| `verify-gap`, `verify-divergence` | harness results with one mismatch, optionally covered by an unmarked divergence |
| `artifact`, `artifact-authorized` | artifact mode, with or without a recorded authorization |
