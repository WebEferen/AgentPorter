---
name: implement
description: Port one unit of an approved AgentPorter plan into the target language, following the unit task checklist (read contract, scaffold, implement in target idioms, mark divergences, port the mapped reference tests, wire the fixtures, get format, lint, typecheck and tests green, review, report, commit). Refuses to start a unit whose dependencies are not done. Use when the user asks to implement or continue implementing a port, or for the next READY unit of /agentporter:port.
argument-hint: "[<unit id>]"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# implement

Where this sits: after the strategy gate. One unit per run. It writes target code and tests and
`reports/units/<unit>.md`, and moves the unit from READY to IMPLEMENTED and REVIEWED. Only the verify skill
sets VERIFIED. Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`.

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

Unit requested: `$ARGUMENTS` (empty means the next READY unit).

## Steps

1. `porter state preflight implement` (once per session; it is fine when it reports IN_PROGRESS).
2. Pick the unit: the argument, or the unit named by `porter state next`. If a unit is already
   IN_PROGRESS, resume it at its recorded task instead of starting another.
3. `porter state unit set <unit> IN_PROGRESS`. It refuses when dependencies are not DONE or the attempt
   budget is spent; report that and stop.
4. If an Agent tool is available, spawn `agentporter:implementer` with: the unit id, the workspace path,
   the target root, and "Implement this unit following your checklist; report the task reached."
   Otherwise read `${CLAUDE_PLUGIN_ROOT}/agents/implementer.md` and do its checklist inline. The
   implementer advances the task with `porter state unit task <unit> <task>` as it goes and stops at
   `green`.
5. `porter state unit set <unit> IMPLEMENTED`.
6. Review: `porter state unit task <unit> review`, then spawn `agentporter:reviewer` with the unit id, the
   diff (`git add -N <files>` first, so new files show in `git diff`) and the paths of
   `contract/units/<unit>.md` and `strategy.md`. Without an Agent tool, read
   `${CLAUDE_PLUGIN_ROOT}/agents/reviewer.md` and do it inline, in a separate pass. Apply findings that are
   correctness or contract issues; log the rest in the unit report. Re-run the checks until green.
7. `porter state unit task <unit> apply-findings`, then `porter state unit set <unit> REVIEWED`.
8. Hand the unit to verify: run `agentporter:verify <unit>` (or tell the router to). After it returns
   VERIFIED, write `reports/units/<unit>.md` from `${CLAUDE_PLUGIN_ROOT}/knowledge/templates/unit-report.md`,
   `porter state unit task <unit> report`. When `config.options.commitPolicy` is `per-unit`, run
   `porter state unit task <unit> commit` and `porter state unit set <unit> DONE`, then commit
   (`port(<unit>): <summary>`) so `.porter/` and `PORTING.md` go into the same commit. Otherwise just
   `porter state unit set <unit> DONE`.
9. If verify returned GAP with port or binding bugs, go back to step 3 for the same unit with the
   mismatches as input. Divergence candidates alone are the user's call (see the verify skill), not a retry.
10. If the attempt budget runs out: `porter state unit set <unit> BLOCKED --note "<what failed, what was tried>"`
    and stop for the user.

## Rules

- Never start a unit whose dependencies are not DONE, and never leave the build red at the end of a run.
- Write target idioms from the idiom map. Do not transliterate the source line by line.
- Every deliberate behavior difference gets a `DIVERGENCE(<id>)` comment at the point of divergence and an
  entry in `.porter/divergences.json` with summary and rationale.
- Port every reference test mapped to the unit, tagged `[ref: <source test id>]` in the test name, asserting
  observable behavior. A test that cannot be ported is OUT-OF-SCOPE with a reason in `reftests.json`, never
  skipped silently.
- In artifact mode, work from `contract/` and `fixtures/` only. Never read decompiled code into the port,
  and never fetch the original's source, even when it is public.
- A new dependency or unit discovered mid-flight goes into `plan.json` with `discovered: true`, then
  `porter state plan-sync`. When the discovered-unit budget is exceeded, stop for the user.
