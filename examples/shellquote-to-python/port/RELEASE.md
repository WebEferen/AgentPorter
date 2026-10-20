# Release checklist: shellquote

- [x] Package metadata in `pyproject.toml`: name `shellquote`, description ("Join and split strings using
      sh's word-splitting rules (a port of go-shellquote)"), license `MIT` with `license-files = ["LICENSE"]`
      (same as upstream), `requires-python = ">=3.11"`, `Typing :: Typed`.
- [ ] Add `[project.urls]` (repository, issues) and keywords (`shell`, `quote`, `split`, `sh`) once the
      repository URL exists. Check that the name `shellquote` is free on PyPI before the first upload.
- [ ] Version policy: upstream is untagged, so the port uses its own semver starting at `0.1.0`; record the
      upstream commit (`95032a8`) in the changelog for each release.
- [x] README section "Parity with upstream" generated from `.porter/PARITY.md`, evidence date 2026-10-20.
- [x] Attribution: `LICENSE` keeps the upstream MIT text and "Copyright (C) 2014 Kevin Ballard".
- [ ] Trim the sdist: hatchling's default sdist ships all of `.porter/` (runs, cache, the Go upstream copy),
      `porter/harness.py`, `uv.lock` and `PORTING.md`. Add
      `[tool.hatch.build.targets.sdist] only-include = ["src", "tests", "porter/bindings.py", ".porter/fixtures", "README.md", "LICENSE"]`
      and check `uv build` output. The wheel is already clean.
- [ ] CHANGELOG entry for the first release (0.1.0: initial port, parity EXACT on 1083 fixtures).
- [ ] CI green on Python 3.11 to 3.15: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`,
      `uv run pytest`. No workflow file exists yet.
- [ ] Publish: `uv build`, test on TestPyPI with `uv publish --publish-url https://test.pypi.org/legacy/`,
      then `uv publish` (trusted publishing from CI preferred).
- [x] Divergences listed in the README: none; the two scope cuts (invalid UTF-8, lone surrogates) are listed
      with their reason.
