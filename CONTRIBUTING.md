# Contributing to AgentPorter

Thanks for helping. The most useful contributions, roughly in order:

1. Bug reports from real ports, with the stage card (`porter.py state board --units`) and the command
   that misbehaved.
2. Language pair references. See [docs/adding-a-language-pair.md](docs/adding-a-language-pair.md).
3. Ecosystem references, oracle drivers and parity harnesses for more languages.
4. Evals for the skills, under `evals/`.
5. Fixes and features in `scripts/porterlib/`.

## Local setup

You need Python 3.11 or newer. Nothing else is required for the tests.

```text
git clone https://github.com/WebEferen/AgentPorter
cd AgentPorter
python3 -m unittest discover -s tests
```

To try your checkout inside Claude Code without installing it:

```text
claude --plugin-dir .
claude plugin validate . --strict
```

## Rules for changes

- `porter.py` stays standard library only. A new dependency needs a very good reason.
- Keep a change to one purpose. Refactors, renames and formatting go in their own pull request.
- Every new command or rule in `porterlib` comes with a test in `tests/`.
- A skill change keeps its frontmatter valid. `tests/test_repo.py` checks the manifests, the
  frontmatter and every plugin path a skill refers to.
- Write plainly: short sentences, no filler. Em dashes and en dashes are not used anywhere in the repo,
  and a test enforces it.
- Comments explain constraints the code cannot show. Do not narrate what the next line does.

## Commits and pull requests

Commit messages follow `type(scope): summary`, for example `fix(parity): count mapped error categories
as EQUIVALENT`. Do not add AI attribution trailers or footers to commits or pull requests.

A pull request description says what changed and why in a few sentences, plus anything a reviewer
needs: breaking changes, gotchas, how you tested it.

## Releases

Maintainers tag `vX.Y.Z`, bump the version in `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` and
`pyproject.toml`, and add a section to `CHANGELOG.md`.
