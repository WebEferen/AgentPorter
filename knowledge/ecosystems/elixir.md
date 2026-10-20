# Elixir ecosystem

| Field | Value |
| --- | --- |
| Registry | Hex, <https://hex.pm> |
| Registry adapter | `porter.py registry lookup --registry hex` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -A "$UA" "https://hex.pm/api/packages/jason"
curl -s -A "$UA" "https://hex.pm/api/packages/slugify"
curl -s -A "$UA" "https://hex.pm/api/packages?search=slug&sort=downloads"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `GET https://hex.pm/api/packages/<name>` | `meta.description`, `meta.links` (map of label to URL) |
| Latest version and date | same | `latest_stable_version`, `updated_at` |
| License | same | `meta.licenses` (list of strings) |
| Adoption signal | same | `downloads.all`, `downloads.recent` (last 90 days) |
| Retirements | same | `retirements` (map of version to `reason` and `message`) |
| Search | `GET https://hex.pm/api/packages?search=<q>&sort=downloads` | JSON array of package objects: `name`, `latest_stable_version`, `meta.description`, `meta.licenses`, `downloads`, `updated_at`, `retirements` |

What the recorded responses showed:

- `jason`: `latest_version` `1.5.0-alpha.2`, `latest_stable_version` `1.4.5`,
  `updated_at` `2026-05-05T14:34:54.953586Z`,
  `downloads` `{"all": 214152375, "day": 137989, "recent": 10058284, "week": 970521}`,
  `meta.licenses` `["Apache-2.0"]`, `retirements` `{}`. Use
  `latest_stable_version`; `latest_version` can be a pre-release.
- `downloads.recent` covers the last 90 days (hexpm's `package_downloads`
  view). `day` was missing for some packages in search results.
- `retirements` example from `plug`:
  `{"1.13.0": {"message": "Package has an incompatible breaking change", "reason": "invalid"}}`.
  `message` can be `null`. Reasons seen: `invalid`, `security`.
- `releases[]` (`version`, `inserted_at`, `has_docs`, `url`) is ordered by
  version, not date: jason lists `1.5.0-alpha.2` (2023-07-07) before `1.4.5`
  (2026-05-05). Take release dates from `inserted_at`.
- The package endpoint also returns `security_advisories` (not in search
  results): `id`, `aliases`, `summary`, `affected` (ranges such as
  `">= 1.16.0 and < 1.16.4"`), `cvss_score`, `cvss_rating`, `published_at`,
  `withdrawn_at`. The adapter does not read them yet; check them by hand.
- `configs["mix.exs"]` gives the dependency line, for example
  `{:jason, "~> 1.4"}`.
- `docs_html_url` is per package: `https://jason.hexdocs.pm/`.
- Search returned a bare array of 17 packages with no total count.
- Rate limit headers: `x-ratelimit-limit: 100`, `x-ratelimit-remaining`,
  `x-ratelimit-reset`.
- Not found: HTTP 404 with `{"message":"Page not found","status":404}`.

## 2. Maturity signals

| Signal | Where | How to read it |
| --- | --- | --- |
| Downloads | `downloads.recent`, `downloads.all` | The 90-day figure shows current use. |
| Release cadence | `releases[].inserted_at` | Small Elixir libraries are often finished; old is not bad by itself. |
| Retirements | `retirements` | A retired latest stable version rules the package out unless the message says otherwise. |
| Advisories | `security_advisories` | Compare `affected` ranges with the version you would pin. |
| Docs | `releases[].has_docs`, `docs_html_url` | Missing docs on recent releases is a warning sign. |
| Owners | `owners[]` (package endpoint only) | Single-owner packages carry more bus-factor risk. |

Missing: a dependents count. Inside a project, `mix hex.audit` lists retired
dependencies and dependencies with advisories and exits non-zero when it
finds any. Erlang packages are on Hex too and work from Elixir.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `mix.exs` | Project config and the `deps/0` list | Yes, by regex over `{:name, ...}` tuples; `only: :test` or `only: :dev` marks a dev dependency |
| `mix.lock` | Locked versions of the whole graph | Yes: locked versions |

Scopes in `deps/0` tuples:

| Option | Meaning |
| --- | --- |
| no `only:` | runtime |
| `only: :dev`, `only: :test`, `only: [:dev, :test]` | dev or test only |
| `runtime: false` | compile-time tool, not started at runtime (ex_doc, credo, dialyxir) |
| `optional: true` | the consumer must add it to use the related feature |
| `github:`, `git:`, `path:` | non-Hex sources; Hex does not list them as package dependencies |

The regex parse misses dependencies built dynamically (helper functions,
module attributes). Confirm list forms such as `only: [:dev, :test]` and
`optional: true` by reading mix.exs. In umbrella projects each app under
`apps/` has its own mix.exs.

## 4. Package layout

- `lib/<app>.ex` and `lib/<app>/*.ex` hold modules (`MyApp`, `MyApp.Sub`).
- `test/*_test.exs` holds tests; `test/test_helper.exs` calls
  `ExUnit.start()`.
- `.formatter.exs` configures `mix format`. `priv/` holds non-code assets.
- Libraries avoid application config in `config/`; pass options as arguments.

```elixir
defmodule ExampleSlug.MixProject do
  use Mix.Project

  def project do
    [
      app: :example_slug,
      version: "1.0.0",
      elixir: "~> 1.18",
      deps: deps(),
      description: "Slugify strings",
      package: [
        licenses: ["MIT"],
        links: %{"GitHub" => "https://github.com/org/example_slug"}
      ]
    ]
  end

  def application, do: [extra_applications: [:logger]]

  defp deps do
    [
      {:ex_doc, "~> 0.40", only: :dev, runtime: false},
      {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
      {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false}
    ]
  end
end
```

## 5. Test runners

| Command | Use |
| --- | --- |
| `mix test` | ExUnit; `use ExUnit.Case, async: true` runs a module's tests concurrently |
| `mix test test/path_test.exs:42` | One test by file and line |
| `mix test --cover` | Coverage |

`doctest MyModule` inside a test module runs the `iex>` examples from
`@doc`. StreamData (`use ExUnitProperties`) adds property-based tests.

## 6. Lint and format

| Tool | Command | Notes |
| --- | --- | --- |
| mix format | `mix format --check-formatted` | Built in. Styler is a common formatter plugin. |
| Credo | `mix credo --strict` | Style and consistency checks. |
| Compiler | `mix compile --warnings-as-errors` | Also surfaces type-checker warnings. |
| mix hex.audit | `mix hex.audit` | Retired and vulnerable dependencies. |

## 7. Type checking

- Elixir 1.17 and later type-check code during compilation with inferred
  set-theoretic types, and each minor release widens what is checked.
  Findings appear as compiler warnings, so CI should run
  `mix compile --warnings-as-errors`.
- Dialyzer through dialyxir: `mix dialyzer`. It uses `@spec` and `@type`
  annotations; cache the PLT files in CI.
- Write `@spec` for every public function in a port; they document the
  contract and feed Dialyzer.

## 8. Build and publish

- Authenticate with `mix hex.user auth`, or set `HEX_API_KEY` in CI.
- `mix hex.build --unpack` shows the package contents.
  `mix hex.publish --dry-run` runs local checks without publishing.
- `mix hex.publish` uploads the package and the docs built by `mix docs`
  (ex_doc). Docs land at `https://<name>.hexdocs.pm/`.
- Required: `:app` and `:version`. Strongly recommended: `:description`,
  `package: [licenses: ..., links: ...]`.
- `mix hex.publish --revert VERSION` works within 24 hours of a package's
  first publish and within one hour for a new version of an existing package.
  After that, retire instead:
  `mix hex.retire <package> <version> <reason> --message "<text>"`, with reason
  `renamed`, `deprecated`, `security`, `invalid` or `other`.

## 9. Runtime version policy

From the Elixir compatibility page, read on 2026-10-20 (latest release
1.20.4):

| Elixir | Support | Erlang/OTP |
| --- | --- | --- |
| 1.20 | Bug fixes and security patches | 27 to 29 |
| 1.19 | Security patches only | 26 to 28 |
| 1.18 | Security patches only | 25 to 27 |
| 1.17 | Security patches only | 25 to 27 |
| 1.16 | Security patches only | 24 to 26 |

OTP 29.1.2, 28.5.0.8 and 27.3.4.19 were all released on 2026-10-14.

Declare the Elixir range with `elixir: "~> 1.18"` in `project/0`; Mix checks
it at compile time. There is no manifest field for the OTP version; state it
in the README and in the CI matrix. For a new port, use `~> 1.18` and test
1.18 with OTP 27, and 1.20 with OTP 29.

## 10. License fields

- mix.exs: `package: [licenses: ["MIT"]]`. Hex docs ask for SPDX identifiers
  or `LicenseRef-<id>` for custom licenses.
- Registry: `meta.licenses` on the package and in search results. It is free
  text on older packages; search returned `"Apache 2.0"`, `"MIT License"`,
  `"GPL-v3"` and `"BSD"`.
- Normalize to SPDX before comparing. Treat ambiguous values such as `BSD`
  (no clause count) as unknown until the LICENSE file is read.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/elixir/` does not exist yet (wanted).

Fixture harness: `knowledge/harnesses/elixir/` does not exist yet (wanted).
