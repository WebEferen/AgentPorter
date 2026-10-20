# Adding a language pair

A pair reference is one Markdown file that tells the agent how a source language maps onto a target
language and where naive ports break. AgentPorter can port between any two languages without one, using
`knowledge/pairs/GENERIC.md`, but a good pair reference makes the strategy sharper and catches traps
earlier. It is the most useful contribution you can make.

## Where it is used

- The **strategy** skill seeds the idiom map in `strategy.md` from it.
- The **implement** skill reads the traps whose risk tags match the unit it is working on.
- `porter.py target score` reads section 13 to see which dependencies already have a known mapping,
  and the `Status` field to score how much support the pair has.

## Steps

1. Copy `knowledge/pairs/TEMPLATE.md` to `knowledge/pairs/<source>-to-<target>.md`. Use the canonical
   language names: `python`, `javascript`, `typescript`, `go`, `rust`, `java`, `kotlin`, `php`, `ruby`,
   `csharp`, `cpp`, `perl` and so on.
2. Fill the header table. Name the versions you cover. Set `Status` to `full` when every section has
   content, or `stub` when only some sections do. A stub is welcome and falls back to `GENERIC.md` for
   the empty sections.
3. Write the sections. Tables first, prose only for the rules a table cannot hold.
4. Write the traps in section 15. Each trap has this shape:

   ```text
   ### T1. <short title>

   - Tags: `unicode`, `regex`
   - Source behavior: <what the source does>
   - Target behavior: <what a naive port does>
   - Detect: <one input and the output that distinguishes the two>
   - Port rule: <what the port must do instead>
   ```

   Tags come from a fixed vocabulary, the same one `porter.py decompose` assigns to units:
   `regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`, `unicode`, `encoding`, `io`,
   `locale`, `mutability`, `nullability`, `error-model`, `ordering`.
5. Run every Detect line on real runtimes and write the versions you used. A trap that was not
   reproduced does not belong in the file.
6. Section 13 lists seed candidates only. The scout agent confirms every one in the registry before it
   is used, so a wrong name there costs time but never ends up in a port.
7. Run the tests and the dash check:

   ```text
   python3 -m unittest discover -s tests
   ```

8. Open a pull request. Say which runtimes you ran the Detect lines on.

## What makes a good trap

- It changes observable behavior: a different value, error, ordering or output byte.
- It is specific. "Python's `round(2.5)` is 2, `Math.round(2.5)` is 3" helps. "Rounding differs" does
  not.
- The Detect input is the smallest one that shows the difference.
- The Port rule says what to write, not only what to avoid.

## Ecosystem references

An ecosystem reference (`knowledge/ecosystems/<language>.md`) describes a target ecosystem: registry
API, maturity signals, manifests and lockfiles, layout, test runners, lint, type checking, publishing
and license fields. Copy `knowledge/ecosystems/TEMPLATE.md` and fill it the same way.

## Oracle and harness templates

To record fixtures from a new source language as a library (not as a CLI), add an oracle driver under
`knowledge/oracles/<language>/`. To run fixtures against a new target language, add a harness under
`knowledge/harnesses/<language>/`. Both must follow `knowledge/oracles/CONTRACT.md`. Copy an existing
one in a similar language and keep it to the standard library where you can.
