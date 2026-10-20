# Choosing the target language

`porter.py target score` ranks candidate languages on six criteria, each scored 0 to 5. The total is the
weighted mean of the criteria that have a score, so a ranking is usable before the user answers and gets
sharper after. The user always makes the final call at the target gate (`porter.py target choose`).

| Criterion | Weight | Source | How it is scored |
| --- | --- | --- | --- |
| ecosystem | 3 | user | 5 when the consumers of the port use this language, 4 for a compatible runtime (JVM family, JS and TS), 1 otherwise. Empty until the user answers. |
| dependencies | 3 | computed | 5 with no runtime dependencies or the same registry as the source. Otherwise each dependency named in the pair reference's dependency table counts 1, an undocumented one counts 0.5. |
| team | 2 | user | 5 when the maintainers know the language, 2 otherwise. Empty until the user answers. |
| semantics | 2 | computed | 5 minus the semantic distance between the languages (typing, memory model, error model, concurrency, absence; a near match counts half), minus 0.25 per survey risk tag the pair reference has no trap for (at most 1.5). |
| runtime | 2 | computed | Fit for the project kind. CLIs favor a single static binary with fast startup (Go, Rust 5). Services favor mature server runtimes. Libraries score 3 everywhere because the consumers decide. |
| support | 1 | computed | How much AgentPorter knows: ecosystem reference (1), parity harness template (1.5), full pair reference (2.5) or stub (1.25) or the GENERIC method (0.5). |

## Questions to ask the user

Ask only what the scores are missing, in one message:

1. Where will the port be used? Name the languages or runtimes of the code that will call it, or the
   platform it ships to.
2. Which of the candidate languages do the maintainers know well?
3. Any hard constraints? For example "must run in the browser", "single binary", "must be on the JVM",
   "no garbage collector". A hard constraint removes candidates; record it as the reason.

Re-score with the answers:

```text
porter.py target score --consumers typescript,python --team typescript --write
porter.py target score --set rust.ecosystem=0 --write     # a hard constraint, recorded as a user override
```

## Reading the result

- A blocker (for example the source language itself) sorts a candidate last regardless of its total.
- A low dependencies score is a research cost, not a veto: the deps phase does the real registry work.
- Prefer the recommended language unless the user names a reason. Record the reason in the user's words
  with `porter.py target choose <language> --note "..."`.
- When two candidates are within 0.3 of each other, present both with the one criterion that separates
  them, and let the user pick.
