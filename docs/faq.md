# FAQ

**What can it port?**
Libraries, packages and CLI tools whose behavior shows up as inputs and outputs: parsers, formatters,
validators, data transforms, API clients, SDKs, command-line tools. With REA it can also start from a
compiled binary or bundle.

**What can it not port?**
UI, whole applications with databases and deployment, and code whose correctness depends on timing.
Code welded to its runtime, such as ORMs, metaclass-heavy frameworks or native extensions, gets a
contract port with listed divergences, or is deferred at the strategy gate.

**Does the source need tests?**
No. Fixtures are recorded by running the original. Existing tests help: ported reference tests are a
second line of evidence and are the only evidence for code that cannot be run as an oracle.

**What if I cannot run the original?**
Units without fixtures can still reach ASSERTED when ported reference tests pass. Units with neither
stay GAP, and the report says so.

**Can I stop halfway?**
Yes. Everything lives in `.porter/`. Run `/agentporter:port` with no arguments to resume at the exact
unit and step. Another person or another model can pick it up from the repository alone.

**Which model should run it?**
Any model your agent supports. The parts that must be exact (state, registry checks, decomposition,
parity) are done by `porter.py` and do not depend on the model. Stronger models write better ports and
need fewer attempts per unit.

**Does my code leave my machine?**
`porter.py` sends package names to public registries during the deps phase, clones a source URL if you
gave one, and downloads REA through npx in artifact mode. Nothing else. Your agent itself works under
its own settings.

**Is this a migration tool for Python 2 to 3, or CommonJS to ESM?**
No. Those are upgrades within one language and have dedicated tools. When the target phase ranks
languages, it marks the source language itself as a blocker.

**Is decompiled code copied into the port?**
Never. It is evidence for understanding behavior. Implementers work from the contract and the fixtures.

**Why is the helper written in Python?**
It runs anywhere Python 3.11 is installed, needs no packages, and its own tests run in seconds. The
ports it drives can be in any language.

**My language pair has no reference. Will it work?**
Yes. The agent follows `knowledge/pairs/GENERIC.md`, which asks the right questions for each area and
has it probe both runtimes. A pair reference makes it faster and catches known traps earlier. See
[adding-a-language-pair.md](adding-a-language-pair.md).
