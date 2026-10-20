# Ruby ecosystem

| Field | Value |
| --- | --- |
| Registry | RubyGems (<https://rubygems.org>) |
| Registry adapter | `porter.py registry lookup --registry rubygems` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Gem names are flat strings, usually lowercase, for example `nokogiri` or
`rest-client`.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -m 30 -A "$UA" "https://rubygems.org/api/v1/gems/nokogiri.json"
curl -s -m 30 -A "$UA" "https://rubygems.org/api/v1/versions/nokogiri.json"
curl -s -m 30 -A "$UA" "https://rubygems.org/api/v1/search.json?query=nokogiri"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `https://rubygems.org/api/v1/gems/<name>.json` | `name`, `info`, `homepage_uri`, `source_code_uri`, `metadata`, `dependencies.runtime[]`, `dependencies.development[]` |
| Latest version and date | same | `version`, `version_created_at`, `yanked`, `platform` |
| Version history | `https://rubygems.org/api/v1/versions/<name>.json` | `[].number`, `.created_at`, `.prerelease`, `.platform`, `.ruby_version`, `.licenses` |
| License | gems endpoint, versions endpoint | `licenses` |
| Adoption signal | gems endpoint | `downloads`, `version_downloads` |
| Search | `https://rubygems.org/api/v1/search.json?query=<q>` | `[].name`, `.version`, `.info`, `.downloads`, `.licenses`, `.source_code_uri`, `.homepage_uri` |

Observed on 2026-10-20:

- gems endpoint for nokogiri: `version` `1.19.4`, `version_created_at`
  `2026-06-18T15:18:58.041Z`, `downloads` 1281905378, `version_downloads`
  1693615, `licenses` `["MIT"]`, `platform` `ruby`, `yanked` false. The URIs
  appear both at top level and inside `metadata`. `dependencies` is
  `{"development": [], "runtime": [{"name", "requirements"}]}`.
- The gems endpoint reports the latest stable version. For rspec-core it
  returned `3.13.6` while the versions list started with `4.0.0.beta1`
  (`prerelease: true`).
- versions endpoint: a JSON array, newest first, with one entry per version
  and platform (nokogiri: 1185 entries; `1.19.4` appears for `ruby`, `java`,
  `x86_64-linux-gnu`, `arm64-darwin` and more). Each entry has `number`,
  `platform`, `created_at`, `prerelease`, `ruby_version` (`">= 3.2"`),
  `rubygems_version`, `licenses`, `downloads_count`, `sha`, `metadata`,
  `summary`, `description`, `authors` and `built_at`. `built_at` was
  `1980-01-02T00:00:00.000Z` (reproducible builds), so use `created_at` for
  release dates. Deduplicate by `number` before counting releases.
- Yanked versions are left out of the versions list, and entries have no
  `yanked` key: rest-client `1.6.10` to `1.6.13` (yanked in 2019) were absent.
  The gems endpoint's `yanked` field only describes the version it reports.
- Unknown gems return HTTP 404 with the plain-text body
  `This rubygem could not be found.`, not JSON.
- Search returned a JSON array of 30 gems per page (`&page=2` gave the next
  30). Entries have the gems endpoint fields minus `version_created_at`,
  `yanked`, `dependencies`, `ruby_abi` and `spec_sha`.
- Old gems may have `licenses: null` (hpricot 0.8.6).

## 2. Maturity signals

- Downloads: `downloads` (all versions) and `version_downloads` (latest).
- Release cadence: `created_at` from the versions list, one per `number`.
- Prereleases: `prerelease: true` in the versions list. Versions with a letter
  segment (`4.0.0.beta1`) are prereleases.
- Dependents:
  `https://rubygems.org/api/v1/gems/<name>/reverse_dependencies.json` returns
  an array of gem names (nokogiri: 7873). The adapter does not call it.
- Yanks: a version pinned in a `Gemfile.lock` but missing from the versions
  list was yanked. Treat that as a security or breakage signal.
- MFA: `metadata.rubygems_mfa_required` set to `"true"` (nokogiri) means
  pushes need multi-factor authentication.
- Native extensions: many platform entries per version (nokogiri) mean
  compiled code. Pure Ruby gems have only `platform: "ruby"`.
- Missing: no advisories and no deprecation flag in the RubyGems API. Use
  `bundle exec bundler-audit check --update` (ruby-advisory-db) locally, and
  check the README, `changelog_uri` and the source repository for
  deprecation notices.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `Gemfile` | Bundler dependency list | Yes, by regex |
| `Gemfile.lock` | Resolved versions | Yes |
| `*.gemspec` | Gem metadata and dependencies | Yes |
| `gems.rb`, `gems.locked` | Alternate Bundler file names | No |
| `.ruby-version` | Local Ruby version for version managers | No |

Scopes as `deps-graph` reports them:

- `Gemfile`: `gem "name", "~> 1.2"` lines. Gems inside a `group :test` or
  `group :development` block are dev; the rest are runtime. A `gemspec` line
  pulls the gemspec's dependencies into the bundle.
- `Gemfile.lock`: exact versions from the `specs` lists, and direct
  dependencies from the `DEPENDENCIES` section. The file also records
  `PLATFORMS`, `RUBY VERSION` and `BUNDLED WITH`.
- `*.gemspec`: `add_dependency` and `add_runtime_dependency` are runtime,
  `add_development_dependency` is dev.
- Optional: gemspecs have no optional dependencies. Libraries document
  optional gems and `require` them inside `begin ... rescue LoadError`.
- Peer: no such concept. Plugins depend on the host gem with a version range.

Import names: the `require` path usually matches the gem name, with dashes
becoming slashes (`net-http` is `require "net/http"`). Exceptions exist, such
as `activesupport` (`require "active_support"`). When they differ, pass the
require path with `porter.py usage-scan --import-name`.

## 4. Package layout

`bundle gem <name>` produces the standard layout:

- `lib/<name>.rb` is the entry point; `lib/<name>/version.rb` defines
  `VERSION`. A dashed name maps to nested modules: `foo-bar` is
  `lib/foo/bar.rb` and `Foo::Bar`; `foo_bar` is `lib/foo_bar.rb` and `FooBar`.
- `<name>.gemspec`, `Gemfile`, `Rakefile` at the root.
- Tests in `spec/` (RSpec) or `test/` (Minitest).
- RBS signatures in `sig/<name>.rbs`.
- Executables in `exe/` (`spec.bindir = "exe"`); `bin/setup` and
  `bin/console` are development scripts.

## 5. Test runners

- RSpec 3.13 (`rspec` 3.13.2; 4.0 is in beta): `bundle exec rspec`, one
  example with `bundle exec rspec spec/slug_spec.rb:12`.
- Minitest (6.0.6 on RubyGems) and test-unit (3.7.8) are bundled gems that
  ship with Ruby: `bundle exec rake test`, or
  `ruby -Ilib:test test/slug_test.rb -n test_unicode` for one test.
- Coverage: SimpleCov.

## 6. Lint and format

- RuboCop (1.92.0) with `.rubocop.yml`: `bundle exec rubocop`, `-a` for safe
  autocorrect, `-A` for all. Plugins: rubocop-rspec, rubocop-minitest,
  rubocop-performance.
- Standard (1.57.0) is RuboCop with a fixed config: `bundle exec standardrb`,
  `bundle exec standardrb --fix`.

## 7. Type checking

- RBS (4.2.0) is the official signature language. Signatures live in
  `sig/*.rbs`; Steep (2.1.0) checks code against them: `bundle exec steep
  check` with a `Steepfile`.
- Sorbet (0.6.x, gems `sorbet` and `sorbet-runtime`) uses inline `sig { ... }`
  blocks and `# typed:` sigils per file: `bundle exec srb tc`. Tapioca
  generates RBI files for dependencies.
- Pick one system per project. New libraries without a Sorbet codebase around
  them usually ship RBS.

## 8. Build and publish

- Build: `gem build <name>.gemspec` produces `<name>-<version>.gem`.
- Publish: `gem push <name>-<version>.gem`, or Bundler's `bundle exec rake
  release` (from `bundler/gem_tasks`), which builds, tags `v<version>`, and
  pushes the tag and the gem.
- Trusted publishing from GitHub Actions uses the `rubygems/release-gem`
  action with OIDC, so CI needs no API key.
- Set `spec.metadata["rubygems_mfa_required"] = "true"` to require MFA for
  pushes.
- `gem yank <name> -v <version>` removes a version from the index. The version
  number cannot be reused.
- Native extensions need one gem per platform (rake-compiler and
  rake-compiler-dock build them).

## 9. Runtime version policy

- Maintained Ruby versions on 2026-10-20 (endoflife.date): 4.0 (released
  2025-12-25), 3.4 and 3.3. Ruby 3.2 reached end of life on 2026-03-31. A new
  version ships each December 25.
- Gems declare support with `spec.required_ruby_version = ">= 3.3"`. The
  registry exposes it as `ruby_version` in the versions list (nokogiri 1.19.4:
  `>= 3.2`), and `rubygems_version` for the RubyGems requirement.
- Applications pin with `ruby "~> 3.4"` in the Gemfile or a `.ruby-version`
  file.
- JRuby is served by `java` platform gems where native code is involved
  (nokogiri publishes one).

## 10. License fields

- gemspec: `spec.license = "MIT"` or `spec.licenses = ["MIT", "Apache-2.0"]`,
  using SPDX identifiers. `gem build` warns about unknown identifiers.
- Registry: `licenses` array in the gems, versions and search responses
  (nokogiri: `["MIT"]`). It can be `null` for old gems (hpricot 0.8.6); read
  the LICENSE file in the gem or source repository then.

## 11. AgentPorter templates

Oracle template: none for Ruby yet (wanted).

Fixture harness: none for Ruby targets yet (wanted).
