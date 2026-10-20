# PHP ecosystem

| Field | Value |
| --- | --- |
| Registry | Packagist (<https://packagist.org>) |
| Registry adapter | `porter.py registry lookup --registry packagist` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Package names are `vendor/package`, lowercase, for example `monolog/monolog`.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -m 30 -A "$UA" "https://repo.packagist.org/p2/monolog/monolog.json"
curl -s -m 30 -A "$UA" "https://packagist.org/packages/monolog/monolog.json"
curl -s -m 30 -A "$UA" "https://packagist.org/search.json?q=monolog"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `https://repo.packagist.org/p2/<vendor>/<package>.json` | `packages[<name>][]`: `version`, `description`, `homepage`, `source.url`, `require`, `require-dev`, `autoload`, `abandoned` |
| Latest version and date | same p2 file | `packages[<name>][].version`, `.time` |
| License | same p2 file | `packages[<name>][].license` (array of SPDX ids) |
| Advisories | same p2 file | `security-advisories[].advisoryId`, `.affectedVersions` |
| Adoption signal | `https://packagist.org/packages/<vendor>/<package>.json` | `package.downloads.total`, `.monthly`, `.daily`, `package.dependents`, `package.favers`, `package.abandoned`, `package.repository` |
| Search | `https://packagist.org/search.json?q=<q>` | `results[].name`, `.description`, `.repository`, `.downloads`, `.favers`, `.abandoned`; `total`, `next` |

Observed on 2026-10-20:

- The p2 file has top-level keys `minified` (`"composer/2.0"`), `packages`
  and `security-advisories`. Entries are ordered newest version first (monolog:
  91 entries, first `3.12.1`, `time` `2026-09-29T19:21:12+00:00`, also
  `published-time`).
- Minified format: only the first entry is complete. Each later entry carries
  only the keys that changed from the entry before it (monolog `3.12.0` had
  just `version`, `version_normalized`, `source`, `dist`, `support`, `time`,
  `published-time`), and the string `"__unset"` removes an inherited key.
  Expand entries in order before reading `license`, `require` or even `time`
  (vimeo/psalm `0.2.43` had no `time` key of its own).
- Prereleases are in the same file: vimeo/psalm listed `7.0.0-rc5` first,
  while the newest stable was `6.20.1`. Skip versions with `-alpha`, `-beta`,
  `-RC` or `-dev` suffixes when looking for the latest stable release. Branch
  versions (`dev-main`, `2.x-dev`) live in a separate file,
  `p2/<vendor>/<package>~dev.json`, which the adapter does not need.
- `security-advisories` for monolog: one entry, `advisoryId`
  `PKSA-dmw8-jd8k-q3c6`, `affectedVersions` `>=1.8.0,<1.12.0`.
- Package endpoint keys: `name`, `description`, `time`, `maintainers`,
  `versions`, `type`, `repository`, `github_stars`, `github_watchers`,
  `github_forks`, `github_open_issues`, `language`, `dependents`,
  `suggesters`, `downloads`, `favers`. monolog: `downloads.total` 1092560604,
  `monthly` 25569321, `dependents` 8497. `abandoned` is absent unless set.
- `abandoned` is either `true` (fzaninotto/faker) or the replacement package
  name (swiftmailer/swiftmailer: `"symfony/mailer"`). The p2 entries and search
  results carry it too.
- Search returned 15 results per page, `total` 1172, and `next` as a full URL
  for page 2.
- Unknown packages: the package endpoint returns HTTP 404 with
  `{"status":"error","message":"Package not found"}`; the p2 endpoint returns
  HTTP 404 with a plain-text body.

## 2. Maturity signals

- Downloads: `total`, `monthly` and `daily` from the package endpoint.
  Monthly downloads are the best adoption signal; totals favor old packages.
- Dependents: `package.dependents` counts packages on Packagist that require
  it. `suggesters` counts packages that only suggest it.
- Release cadence: expanded p2 `time` values, newest first.
- Abandonment: `abandoned` is set by the maintainer and often names a
  successor. Treat any truthy value as a stop sign for new adoption.
- Advisories: p2 `security-advisories`. Locally, `composer audit` checks a
  lockfile against the same data.
- Repository health: `github_stars`, `github_open_issues` and `repository`
  from the package endpoint.
- Missing: no yank flag. Versions come from VCS tags, so a deleted tag simply
  disappears and a moved tag changes the `dist.reference` of a version.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `composer.json` | Package manifest, constraints, autoload map | Yes |
| `composer.lock` | Exact resolved versions | Yes |

Scopes as `deps-graph` reports them:

- `composer.json`: `require` is runtime, `require-dev` is dev. The `php` entry
  and `ext-*` entries (for example `ext-mbstring`) are platform requirements,
  not packages.
- `composer.lock`: the `packages` array holds runtime packages and
  `packages-dev` holds dev packages, each with an exact `version`.
- Optional: `suggest` maps a package name to a free-text reason. Nothing is
  installed.
- Peer: no such concept. The closest are virtual packages (a library requires
  `psr/log-implementation` and an implementation `provide`s it) and
  `conflict`.

Import names: the PHP namespace cannot be derived from `vendor/package`. Pass
`porter.py usage-scan --import-name <namespace prefix>`, for example
`Monolog\` for `monolog/monolog`. The prefix is the key of the `autoload.psr-4`
map in the p2 entry (monolog: `"Monolog\\": "src/Monolog"`).

## 4. Package layout

- `composer.json` at the root, code in `src/`, tests in `tests/`, mapped with
  `"autoload": {"psr-4": {"Vendor\\Package\\": "src/"}}` and
  `"autoload-dev"` for the tests namespace. One class per file, path mirrors
  the namespace under the PSR-4 root.
- Executables go in `bin/` and are listed under the `bin` key.
- PHPUnit config: `phpunit.xml.dist`. Static analysis: `phpstan.neon.dist` or
  `psalm.xml`. Style: `.php-cs-fixer.dist.php`.
- `.gitattributes` with `export-ignore` keeps tests and tooling out of the dist
  archive that Composer downloads.
- Libraries usually do not commit `composer.lock`; applications do.

## 5. Test runners

- PHPUnit 13 (latest 13.4.3 when verified, requires PHP >= 8.4.1). PHPUnit
  12 needs PHP 8.3 and PHPUnit 11 needs PHP 8.2, so the runner major follows
  the lowest PHP version you support. PHPUnit 12 dropped doc-comment annotations; use
  attributes such as `#[Test]` and `#[DataProvider('cases')]`.
- Pest 5 (v5.3.3, requires PHP ^8.4) is built on PHPUnit with a functional
  syntax.
- Commands: `vendor/bin/phpunit`, `vendor/bin/phpunit --filter testSlugify`,
  `vendor/bin/pest`.
- Mutation testing: Infection (0.35.8).

## 6. Lint and format

- PHP-CS-Fixer (v3.95.27): `vendor/bin/php-cs-fixer fix --dry-run --diff`,
  with rule sets such as `@PER-CS` (the PER Coding Style that follows PSR-12)
  or `@Symfony`.
- PHP_CodeSniffer 4 (4.0.4): `vendor/bin/phpcs`, `vendor/bin/phpcbf`.
- Laravel Pint (1.32.1) for Laravel-style projects.
- Rector (2.7.0) for automated upgrades and refactors.
- `composer validate --strict` checks the manifest; `php -l` checks syntax.

## 7. Type checking

- PHPStan 2 (2.3.1): `vendor/bin/phpstan analyse`, levels 0 to 10 (`max`).
  New libraries should aim for level 8 or higher.
- Psalm 6 (6.20.1 stable; 7.0 is in release candidates): `vendor/bin/psalm`.
- Native types cover scalars, classes, unions and nullables. Generics, list
  types and array shapes are PHPDoc only (`@template T`, `list<string>`,
  `array{id: int, name: string}`), and both analyzers read them.
- Start every file with `declare(strict_types=1);` to stop scalar coercion.

## 8. Build and publish

- No build step and no upload. Packagist reads the public VCS repository.
- First release: submit the repository URL at
  <https://packagist.org/packages/submit>, then enable the GitHub integration so
  pushes and tags update the package.
- Each release is a git tag (`v1.2.0` or `1.2.0`): run
  `composer validate --strict`, then `git tag v1.2.0 && git push --tags`.
- Abandoning a package is a setting on Packagist (it fills `abandoned`).

## 9. Runtime version policy

- Supported PHP versions on 2026-10-20 (endoflife.date): 8.5 (released
  2025-11-20), 8.4, 8.3, and 8.2 until 2026-12-31. PHP 8.1 reached end of life
  on 2025-12-31. A new minor version ships each November.
- Declare support in `composer.json`: `"require": {"php": "^8.2"}` plus
  required extensions (`"ext-mbstring": "*"`). Packagist exposes this as
  `require.php` per version (monolog 3.12.1: `>=8.1`; psalm 6.20.1:
  `~8.1.31 || ~8.2.27 || ~8.3.16 || ~8.4.3 || ~8.5.0`).
- `config.platform.php` pins the PHP version Composer resolves against, so
  local installs match the lowest supported version.
- Test the range in CI with a PHP matrix, and once with
  `composer update --prefer-lowest`.

## 10. License fields

- `composer.json`: `"license": "MIT"`, or an array such as
  `["MIT", "GPL-3.0-or-later"]` meaning the user may pick one. A conjunctive
  license is a string in parentheses: `"(LGPL-2.1-only and GPL-3.0-or-later)"`.
  Closed source uses `"proprietary"`.
- Registry: p2 `packages[<name>][].license` is always an array (monolog:
  `["MIT"]`). The package endpoint has no top-level license; it appears only
  inside `package.versions[<version>]`.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/php/` (see its README.md).

Fixture harness: none for PHP targets yet (wanted).
