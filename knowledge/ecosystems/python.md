# Python ecosystem

| Field | Value |
| --- | --- |
| Registry | PyPI, <https://pypi.org> |
| Registry adapter | `porter.py registry lookup --registry pypi` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -A "$UA" "https://pypi.org/pypi/python-slugify/json"
curl -s -A "$UA" "https://pypi.org/pypi/requests/json"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `GET https://pypi.org/pypi/<name>/json` | `info.summary`, `info.project_urls`, `info.classifiers` |
| Latest version and date | same document | `info.version`, `releases[<info.version>][].upload_time_iso_8601`, `info.yanked` |
| License | same document | `info.license_expression`, `info.license`, `info.classifiers` (entries starting `License ::`) |
| Adoption signal | none | The JSON API has no download counts (see below) |
| Search | none | PyPI has no search API |

What the recorded responses showed:

- `python-slugify`: `info.version` `9.1.3`, `info.license` `null`,
  `info.license_expression` `"MIT"`, no `License ::` classifier, files
  uploaded at `2026-10-07T01:06:18.891997Z`.
- `requests`: `info.version` `2.34.2`, `info.license` `"Apache-2.0"`,
  `info.license_expression` `null`, classifier
  `License :: OSI Approved :: Apache Software License`.
- So read `license_expression` first, then `license`, then classifiers.
- `info.project_urls` is a free-form map (`Homepage`, `Source`, `Changelog`,
  `Issues` and so on). Keys differ per project.
- `releases[<v>]` is a list of files (wheel and sdist). Use the earliest
  `upload_time_iso_8601`. A version can map to an empty list (`0.1.1` of
  python-slugify): no files.
- `info.yanked` and `info.yanked_reason` describe `info.version`. Each file
  in `releases[<v>]` also carries `yanked` and `yanked_reason`.
- Names are normalized: `python_slugify` and `pyyaml` returned the same
  project as `python-slugify` and `PyYAML` (200, no redirect). `info.name`
  holds the display name.
- Downloads: `info.downloads` was `{"last_day": -1, "last_month": -1,
  "last_week": -1}` and every file's `downloads` was `-1`.
- Not found: HTTP 404 with `{"message": "Not Found"}`.
- Also present but not read by the adapter: `info.requires_python`,
  `info.requires_dist`, `info.license_files`, `ownership.roles`, and a
  top-level `vulnerabilities` list (OSV records with `id`, `aliases`,
  `fixed_in`, `link`) for the version in `info.version`.

Search: PyPI has no search API. `https://pypi.org/search/?q=` returned an HTML
page behind a browser challenge. Agents find candidate names with web search,
then confirm each name with the JSON lookup above before naming it.

Downloads, outside the adapter: `https://pypistats.org/api/packages/<name>/recent`
returned `{"data": {"last_day": ..., "last_week": ..., "last_month": ...}}`
(python-slugify: 64,296,908 last month).

## 2. Maturity signals

| Signal | Where | How to read it |
| --- | --- | --- |
| Last release | upload time of `info.version` | Old is fine for small, finished utilities. |
| Release cadence | `releases` map upload times | Count releases in the last 12 months. |
| Status | `Development Status ::` classifier | Self-declared; weak signal. |
| Interpreter support | `info.requires_python`, `Programming Language :: Python :: 3.x` classifiers | Must include the versions the port targets. |
| Yanked | `info.yanked`, file-level `yanked` | A yanked latest version needs the reason read. |
| Vulnerabilities | top-level `vulnerabilities` | OSV records for the latest version. |
| Typed | `Typing :: Typed` classifier, `py.typed` in the wheel, or a `types-<name>` stub package | Untyped packages weaken a typed port's contract. |
| Native code | file `packagetype` (`bdist_wheel`, `sdist`) and `python_version` | sdist-only with C extensions needs a compiler at install. |

Missing: download counts (use pypistats), dependents, and any maintainer
activity signal beyond `ownership.roles`.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `pyproject.toml` | PEP 621 metadata, build system, tool config | Yes |
| `requirements*.txt` | pip requirement lists | Yes; `-r` includes are followed |
| `setup.cfg` | setuptools declarative config | Yes: `install_requires` and `extras_require` |
| `setup.py` | setuptools script | Partly: `install_requires` by regex; computed lists are missed |
| `poetry.lock` | Poetry lockfile | Yes: locked versions |
| `uv.lock` | uv lockfile | Yes: locked versions |
| `Pipfile` | Pipenv manifest | Yes |
| `Pipfile.lock` | Pipenv lockfile | Yes |

Scopes:

| Source | Scope |
| --- | --- |
| `[project].dependencies` | runtime |
| `[project.optional-dependencies]` | optional (extras) |
| `[dependency-groups]` (PEP 735) | dev |
| `[tool.poetry.dependencies]` | runtime (Poetry projects) |
| `[tool.poetry.group.*.dependencies]` | Poetry groups such as dev, test, docs |
| `[build-system].requires` | build |
| `requirements*.txt` whose file name contains `dev`, `test`, `lint` or `doc` | dev |
| other `requirements*.txt` | runtime |

In `[tool.poetry.dependencies]` the `python` key is the interpreter range, not
a package. Pipfile uses `[packages]` and `[dev-packages]`; Pipfile.lock uses
`default` and `develop`. Python has no peer dependencies. Requirement strings
can carry environment markers (`; python_version < "3.11"`,
`; extra == "socks"`) that limit when they apply.

Distribution names often differ from import names: `python-slugify` imports as
`slugify`, `PyYAML` as `yaml`, `beautifulsoup4` as `bs4`, `Pillow` as `PIL`.
`porter.py usage-scan` guesses the import name; pass `--import-name <module>`
to override the guess. To find the real name, read `top_level.txt` or
`RECORD` in the wheel, or call `importlib.metadata.packages_distributions()`
in an environment where the package is installed.

## 4. Package layout

- src layout: `src/<import_name>/__init__.py`, tests in `tests/test_*.py`,
  metadata in `pyproject.toml`. Flat layout (`<import_name>/` at the root) is
  also common in sources.
- `py.typed` (empty file) inside the package marks it typed (PEP 561).
- Console commands: `[project.scripts]`. `python -m <pkg>` runs
  `<pkg>/__main__.py`.
- A directory without `__init__.py` is a namespace package (PEP 420).

```toml
[project]
name = "example-slug"
version = "1.0.0"
description = "Slugify strings"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
dependencies = ["text-unidecode>=1.3"]

[project.optional-dependencies]
unidecode = ["Unidecode>=1.1.1"]

[dependency-groups]
dev = ["pytest>=9", "ruff", "mypy"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

`uv init --lib` scaffolds this shape with the `uv_build` backend instead of
hatchling; either works.

## 5. Test runners

| Tool | Command | Notes |
| --- | --- | --- |
| pytest 9 | `uv run pytest` or `pytest` | Config in `[tool.pytest.ini_options]`. |
| unittest | `python -m unittest discover` | Standard library; common in older sources. |
| Hypothesis | used inside pytest | Property-based tests. |
| tox or nox | `tox`, `nox` | Interpreter matrix. `uv run --python 3.11 pytest` covers quick checks. |

Coverage: `pytest --cov` with pytest-cov, or `coverage run -m pytest`.

## 6. Lint and format

| Tool | Command | Notes |
| --- | --- | --- |
| Ruff | `ruff check .`, `ruff format --check .` | Lint and format; config in `[tool.ruff]`. Replaces flake8, isort, pyupgrade and usually Black. |
| Black | `black --check .` | Still common in existing projects. |

## 7. Type checking

| Tool | Command | Notes |
| --- | --- | --- |
| mypy 2.x | `mypy src` | `[tool.mypy] strict = true` for new code. |
| pyright | `pyright` | Also the engine behind Pylance; basedpyright is a stricter fork. |
| pyrefly 1.x | `pyrefly check` | Rust-based checker from Meta. |
| ty | `ty check` | Rust-based checker from Astral; still 0.0.x, treat as preview. |

Stub packages from typeshed are named `types-<distribution>`. When Python is
the source, annotations may be missing or wrong; the contract comes from the
oracle fixtures, not from the hints.

## 8. Build and publish

- uv: `uv build` writes an sdist and a wheel to `dist/`; `uv publish` uploads
  them. `uv version --bump patch|minor|major` edits the version.
- PyPA tools: `python -m build`, then `twine check dist/*` and
  `twine upload dist/*`.
- From CI, use PyPI trusted publishing: register the workflow on the PyPI
  project, grant `id-token: write`, and publish with
  `pypa/gh-action-pypi-publish` or `uv publish`.
- Test first on TestPyPI:
  `uv publish --publish-url https://test.pypi.org/legacy/`.
- Yanking is done in the PyPI web UI. A yanked version stays installable when
  pinned exactly.

## 9. Runtime version policy

CPython status from `https://peps.python.org/api/release-cycle.json`, read on
2026-10-20:

| Version | Status | End of life |
| --- | --- | --- |
| 3.15 | bugfix (released 2026-10-09) | 2031-10 |
| 3.14 | bugfix | 2030-10 |
| 3.13 | security | 2029-10 |
| 3.12 | security | 2028-10 |
| 3.11 | security | 2027-10 |
| 3.10 | end of life since 2026-10-01 | |

Declare the range with `requires-python = ">=3.11"`. pip and uv skip releases
whose `requires-python` excludes the running interpreter. Do not add an upper
cap such as `<4`. List each tested version as a
`Programming Language :: Python :: 3.x` classifier (informational only). For a
new port, target `>=3.11` and run CI on 3.11 to 3.15.

## 10. License fields

- `pyproject.toml`: `license = "MIT"` is an SPDX expression (PEP 639), with
  `license-files = ["LICENSE"]`. The legacy table forms
  `license = { text = "..." }` and `license = { file = "..." }` still appear
  in sources. PEP 639 deprecates `License ::` classifiers; tools may reject a
  package that sets both.
- Registry: `info.license_expression` (SPDX, PEP 639 metadata),
  `info.license` (legacy free text, sometimes the whole license file),
  `info.license_files`, and `License ::` classifiers.
- If all three are empty, record the license as unknown and read the LICENSE
  file in the sdist or repository.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/python/` (see its README.md).

Fixture harness: `knowledge/harnesses/python/` (see its README.md).
