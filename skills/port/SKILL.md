---
name: port
description: Port a library, package, CLI tool or compiled artifact from one programming language to another with evidence at every step. Dependencies get decisions checked against real package registries, the original's behavior is recorded as oracle fixtures, the work is cut into units and implemented one at a time, and parity is proven against the original. Starts from source code, or from a binary or closed tool by reverse engineering it with REA. Can recommend the target language. Also resumes a port in progress. Use when the user asks to port, migrate, rewrite, translate or reimplement a codebase, package, CLI or binary in another language, to move off a legacy language, or to continue an AgentPorter port.
argument-hint: "[<source path | git url | artifact>] [--to <language>] [--name <package>] [--subpath <dir>] [--ref <ref>] [--implement]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# AgentPorter router

Arguments: `$ARGUMENTS`

This skill creates the `.porter/` workspace, runs the phases in order, stops at user gates, and resumes
from `.porter/state.json`. Read `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md` once per session:
it is the map of phases, gates and artifacts.

In this skill and every phase skill, `porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`.
There is no `porter` executable: write the full command each time. In Codex or a plain skills install,
use the `scripts/porter.py` two directories above this file.

## 1. Start or resume

1. Check `python3 --version` is 3.11 or newer. If not, stop and tell the user AgentPorter needs it.
2. If `porter state board --units` finds a workspace and the arguments name no new source, this is a
   resume: print the board and go to step 3.
3. Otherwise this is a new port. The workspace belongs in the repository that will hold the port, which is
   the current directory. If the current directory is the source project itself, ask where the port should
   live and create that directory first.
4. Decide the mode from the source argument:
   - Source code (a directory with code, or a git URL): code mode.
   - A built artifact (an executable, `.dll`, `.jar`, `.apk`, `.wasm`, `.asar`, `.app`, a minified bundle,
     or the user says there is no source): artifact mode. Ask the user, in one message, who owns the
     artifact or what permits analyzing it, and pass their answer as `--authorization`. Without an answer,
     stop: reverse engineering needs a basis. See `${CLAUDE_PLUGIN_ROOT}/knowledge/rea.md`.
5. Create the workspace:
   `porter init --source <path or url> [--to <language>] [--ref <ref>] [--subpath <dir>] [--name <package>] [--mode artifact --authorization "<user's words>"]`
   In artifact mode, add `--source-name <name> --source-version <version>` when the user says what the
   artifact is; recover fills them in otherwise.
   Leave out `--to` when the user did not name a language: the target phase will recommend one.
6. Code mode only: `porter source fetch` pins the commit (clones a URL into `.porter/cache/source`).
7. Tell the user, in three or four lines: the phases that will run, which gates will need them, that
   nothing is written to the port's source tree before the strategy gate, and that every artifact lands
   in `.porter/`.

## 2. Pre-answered decisions

Users sometimes give gate answers up front ("use TypeScript", "approve the recommended plan", "skip the
CLI"). Keep those words. At a gate, if the user's own words already decide it, apply them and quote them
in the `--note`. Never approve a gate on your own judgment, and never treat a subagent's output as the
user's approval.

## 3. The loop

Repeat until a stop condition:

1. Run `porter state next --json`. It returns `kind` and a `text` instruction.
2. `phase`: run the named phase skill. With a Skill tool, invoke `agentporter:<phase>`. Without one, read
   `${CLAUDE_PLUGIN_ROOT}/skills/<phase>/SKILL.md` and follow it.
3. `gate`: present the gate (section 4) and stop for the user's answer unless it was pre-answered.
4. `unit`: implementation. Stop here and show the plan, unless the arguments include `--implement` or the
   user asked to implement. When implementing, run `agentporter:implement <unit>` then
   `agentporter:verify <unit>`, and loop.
5. `blocked`: report the blocked units with their notes and the options (retry with a changed approach,
   defer, change scope). Stop.
6. `postflight`: run `porter state postflight implement`, then continue.
7. `complete`: run `agentporter:status release`. Stop.

## 4. Gates

| Gate | Show | Approve with |
| --- | --- | --- |
| recover | the summary of `.porter/recover/recovery.md` and each gate item | `porter state gate recover approve --note "..."` |
| target | the table in `.porter/target.md`; ask the missing questions from `${CLAUDE_PLUGIN_ROOT}/knowledge/target-selection.md`, re-score, then ask for the pick | `porter target choose <language> --note "..."` |
| deps | each gate item with your recommendation | `porter state gate deps approve --note "..."` |
| strategy | unit table, order and tracer from `.porter/decomposition.md`, scope cuts, budgets and the top risks from `.porter/strategy.md` | `porter state gate strategy approve --note "..."` |

When the user asks for changes instead, make them in the phase's artifacts, re-run that phase's
postflight, and present the gate again. `porter state gate <phase> reject --note "..."` records a
rejection and reopens the phase.

## 5. Stop conditions

Stop after the strategy gate unless implementation was requested. Stop at any gate without an answer, at
a BLOCKED unit, and when the port is complete. Always end with `porter state board` output and the single
next action, so the user or a later session can resume with `/agentporter:port`.

## Rules

- Run phases only through their skills; they carry the preflight and postflight checks.
- Do not write into the port's source tree before the strategy gate is approved.
- Do not hand-edit `.porter/state.json` or `.porter/config.json`.
- If a command fails, show its message, fix the cause, and run it again. Do not route around it.
