---
name: target
description: Recommend the target language for a port. Scores candidate languages on dependency coverage, semantic distance from the source, runtime fit for the project kind, AgentPorter support, where the port will be used and what the team knows, then asks the user to choose and records the decision. Use when the user wants to port or rewrite something but has not picked a language, asks which language to port to, or wants to compare candidate languages for a migration.
argument-hint: "[--candidates <a,b,c>]"
allowed-tools: Read, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py *)
---

# target

Where this sits: after survey, before deps. It runs only when the user did not name a language with
`--to`. It produces `target.json` and `target.md` and ends at a user gate: the user picks the language.
Map: `${CLAUDE_PLUGIN_ROOT}/skills/port/reference/workflow.md`. Rubric:
`${CLAUDE_PLUGIN_ROOT}/knowledge/target-selection.md` (read it first).

`porter` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/porter.py"`, written in full in every command (in
Codex, the `scripts/porter.py` two directories above this file).

## Steps

1. `porter state preflight target`. Stop and report if it fails.
2. `porter target score --write` (add `--candidates a,b,c` when the user named a shortlist). Read
   `target.md`: the table, the evidence for the top candidates, and the open questions.
3. Ask the user, in one message, only the questions `target.md` lists: where the port will be used, what
   the maintainers know, and any hard constraint. Skip a question the user already answered in the
   conversation and use their words instead.
4. Re-score with the answers: `porter target score --consumers <langs> --team <langs> --write`. A hard
   constraint becomes `--set <language>.<criterion>=0` for the excluded languages, with the reason kept
   for the gate note.
5. `porter state postflight target`. The phase is now GATE_WAIT.
6. Present the top three rows of the table, the recommended language and the one or two criteria that
   decide it. When two candidates are within 0.3, say so and name what separates them.
7. When the user picks: `porter target choose <language> --note "<their reason, in their words>"`.
   If the user had already named the language in this conversation, use that as the pick.

## Rules

- The recommendation is evidence for the user, not the decision. Never call `target choose` without the
  user's pick.
- Do not research registries here beyond what the score reports: the deps phase does the real lookup.
- If the user picks a language outside the candidates, accept it; `target choose` records that.
