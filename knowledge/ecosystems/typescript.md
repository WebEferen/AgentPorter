# TypeScript ecosystem

| Field | Value |
| --- | --- |
| Registry | npm, <https://www.npmjs.com> (API at <https://registry.npmjs.org>) |
| Registry adapter | `porter.py registry lookup --registry npm` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

This file also covers JavaScript sources. JavaScript and TypeScript share the
registry, the manifests and the lockfiles.

## 1. Registry API

Each endpoint the registry adapter calls, with a recorded request and the
fields AgentPorter reads. Every endpoint below was called on the date above.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -A "$UA" "https://registry.npmjs.org/zod"
curl -s -A "$UA" "https://registry.npmjs.org/@types%2Fnode"
curl -s -A "$UA" "https://api.npmjs.org/downloads/point/last-month/zod"
curl -s -A "$UA" "https://registry.npmjs.org/-/v1/search?text=slugify&size=10"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `GET https://registry.npmjs.org/<name>` (scoped: `@scope%2Fname`) | `description`, `repository` (object with `type`, `url`, sometimes `directory`), `versions` (count of keys), `versions[<v>].deprecated` |
| Latest version and date | same document | `dist-tags.latest`, `time[<version>]`, `time.created` |
| License | same document | `license` (top level; each version object also has `license`) |
| Adoption signal | `GET https://api.npmjs.org/downloads/point/last-month/<name>` | `downloads`, `start`, `end`, `package` |
| Search | `GET https://registry.npmjs.org/-/v1/search?text=<q>&size=10` | `total`, `objects[].package` (`name`, `version`, `date`, `description`, `license`, `links.repository`), `objects[].downloads.monthly`, `objects[].downloads.weekly`, `objects[].dependents` |

What the recorded responses showed:

- `zod`: `dist-tags.latest` `4.6.7`, `time["4.6.7"]` `2026-10-12T16:29:37.778Z`,
  `time.created` `2020-03-07T21:19:15.387Z`, `license` `MIT`, 1013 versions.
- `deprecated` is a string on a version object and is absent when the version
  is not deprecated. On `request`, all 126 versions carry
  `"request has been deprecated, see https://github.com/request/request/issues/3142"`.
- The full document is large (4.2 MB for `zod`, 11 MB for `@types/node`).
  The adapter caches it; do not fetch it in a loop.
- `dist-tags` can hold many tags (`@types/node` has `ts5.9`, `ts7.0` and
  more). Only `latest` counts as the current release.
- `time.modified` moves on any metadata change (dist-tag, deprecation), so
  use `time[dist-tags.latest]` as the release date.
- Scoped names: `@types%2Fnode` and `@types/node` both returned 200 from the
  registry and from the downloads API.
- Not found: HTTP 404 with `{"error":"Not found"}` (registry) and
  `{"error":"package <name> not found"}` (downloads).
- Search: `dependents` is a string (`"2870"`), parse it as an integer.
  `score.detail.popularity`, `quality` and `maintenance` were `1` for every
  result, so they carry no signal. `flags.insecure` was `0` for every result.
  Search objects have no deprecation flag; look up each candidate.

## 2. Maturity signals

| Signal | Where | How to read it |
| --- | --- | --- |
| Last release | `time[dist-tags.latest]` | Older than two years on an active topic needs a reason (finished, small scope). |
| Release cadence | `time` map, one timestamp per version | Count releases in the last 12 months; ignore pre-release tags. |
| Downloads | downloads API, last month | CI and mirrors inflate counts. Compare candidates with each other, not with a fixed bar. |
| Dependents | search result `dependents` only | Not in the package document. |
| Deprecation | `versions[<latest>].deprecated` | A deprecated latest version rules the package out. Deprecated old ranges alone are normal. |
| Types | version object `types` or `typings`, or a `@types/<name>` package | No bundled types and no `@types` package means writing declarations. |
| Module format | version object `type`, `exports`, `main`, `module` | ESM-only is fine on supported Node lines (`require()` of ESM works from Node 22.12). |
| Runtime range | version object `engines.node` | Seen on `request`: `>= 6`. Often absent. |

Missing from these responses: security advisories (use `npm audit` inside a
project, or OSV and the GitHub Advisory Database), maintainer activity beyond
the `maintainers` list, and any usable quality score.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `package.json` | Declared dependencies and version ranges | Yes |
| `package-lock.json` (lockfileVersion 2 or 3) | npm lockfile | Yes: the `packages` map gives locked versions and transitive dependencies |
| `yarn.lock` (Yarn v1 format) | Yarn classic lockfile | Yes: locked versions |
| `pnpm-lock.yaml` | pnpm lockfile | No: ranges from `package.json` are used and the report says so |

Scopes in `package.json`:

| Field | Scope |
| --- | --- |
| `dependencies` | runtime |
| `devDependencies` | dev |
| `peerDependencies` | peer (the host project installs it; `peerDependenciesMeta.<name>.optional` marks optional peers) |
| `optionalDependencies` | optional (install failures are tolerated) |

A `package-lock.json` with lockfileVersion 1 has no `packages` map. If the
report shows only ranges for a project with a lockfile, the lockfile format was
not one of the parsed ones.

Reading JavaScript and TypeScript imports: `x/sub/path` belongs to package
`x`, and `@scope/name/sub` belongs to `@scope/name`. `node:fs` and other
`node:` imports are built-ins, not dependencies.

## 4. Package layout

- `src/` holds TypeScript source; `dist/` holds build output and is the only
  published directory (`"files": ["dist"]`).
- Tests sit in `test/` or next to the source as `*.test.ts`.
- `package.json` declares entry points through `exports`. Put the `types`
  condition first. Keep `main` and `types` for older resolvers if needed.
- `bin` maps command names to scripts for CLIs.

```json
{
  "name": "example-slug",
  "version": "1.0.0",
  "type": "module",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "default": "./dist/index.js" }
  },
  "files": ["dist"],
  "engines": { "node": ">=22" },
  "license": "MIT"
}
```

New packages can ship ESM only. Every supported Node line loads ESM from
`require()`, so dual CJS and ESM builds are only needed for older consumers.

## 5. Test runners

| Tool | When | Command |
| --- | --- | --- |
| Vitest 5 | Default for new TypeScript packages; runs TS and ESM directly | `npx vitest run` |
| `node:test` | Zero dependencies; Node 22.18 and later strip TS types natively | `node --test` |
| Jest 30 | Common in existing code; ESM needs extra configuration | `npx jest` |

Vitest 5 requires Node `^22.12.0 || ^24.0.0 || >=26.0.0`. Coverage:
`npx vitest run --coverage` with `@vitest/coverage-v8`. Type-level tests:
`expectTypeOf` in Vitest.

## 6. Lint and format

| Tool | Command | Notes |
| --- | --- | --- |
| ESLint 10 | `npx eslint .` | Flat config only (`eslint.config.js`). TS rules come from `typescript-eslint` 8.x. |
| Prettier 3 | `npx prettier --check .` | Formatter only. |
| Biome 2 | `npx biome check .` (`npx biome ci .` in CI) | Lint and format in one binary; replaces ESLint plus Prettier for many projects. |
| oxlint 1.x | `npx oxlint` | Fast linter, often run before ESLint. |

`typescript-eslint` 8.72.0 declares the peer range `typescript >=4.8.4 <6.1.0`.
A project that uses type-aware lint rules must keep TypeScript 6.0.x installed
until that range includes 7.

## 7. Type checking

- `npx tsc --noEmit`. The `typescript` package's `latest` tag is 7.0.2, the
  native compiler. TypeScript 6.0 is the last JavaScript-based compiler, and
  tools that load the compiler API may still require it; check their peer
  ranges.
- Library tsconfig baseline: `"strict": true`, `"module": "nodenext"`,
  `"declaration": true`, `"verbatimModuleSyntax": true`,
  `"noUncheckedIndexedAccess": true`. Set them explicitly.
- `"erasableSyntaxOnly": true` keeps the code runnable by Node's type
  stripping (no enums, namespaces or parameter properties).
- Check the published types resolve: `npx publint` and
  `npx @arethetypeswrong/cli --pack`.
- JavaScript sources: types may come from JSDoc (`checkJs`) or a
  `@types/<name>` package. Treat JSDoc types as hints, not as a contract.

## 8. Build and publish

- Build with `tsc -p tsconfig.build.json` for plain ESM plus `.d.ts`. Use a
  bundler only when needed: tsdown (Rolldown) or tsup (esbuild).
- Inspect the tarball: `npm pack --dry-run`.
- Version: `npm version patch|minor|major`, or Changesets
  (`npx changeset`, `npx changeset version`, `npx changeset publish`).
- Publish: `npm publish` (add `--access public` the first time for a scoped
  package). From CI, use npm trusted publishing (OIDC from GitHub Actions or
  GitLab CI), which also records provenance. Classic tokens were retired in
  late 2025; outside CI, use a short-lived granular token.
- Deprecate: `npm deprecate <name>@<range> "<message>"` sets the `deprecated`
  string read in section 1.

## 9. Runtime version policy

Node.js schedule from `nodejs/Release` `schedule.json`, read on 2026-10-20:

| Line | Status on 2026-10-20 | End of life |
| --- | --- | --- |
| 26 | Current; LTS from 2026-10-28 | 2029-04-30 |
| 24 | LTS; maintenance from 2026-10-20 | 2028-04-30 |
| 22 | Maintenance LTS | 2027-04-30 |
| 20 | End of life since 2026-04-30 | |
| 27 | Alpha from 2026-10-28, release 2027-04-22 | 2030-04-30 |

Declare the range in `package.json` with `"engines": { "node": ">=22" }`.
npm only warns on a mismatch unless `engine-strict` is set. For a new port,
target `>=22` and run CI on 22, 24 and 26. Deno and Bun also install npm
packages; state support for them in the README, since `engines` has no
standard key for them.

## 10. License fields

- `package.json` `license`: an SPDX expression (`"MIT"`,
  `"(MIT OR Apache-2.0)"`), `"UNLICENSED"` for no grant, or
  `"SEE LICENSE IN <file>"`. Old packages may use a `licenses` array or an
  object; read the LICENSE file in that case.
- Registry: top-level `license` in the package document, `license` on each
  version object, and `objects[].package.license` in search. Values seen:
  `MIT`, `Apache-2.0`, `ISC`.
- Read the license of the version you will install; it can change between
  versions. A missing license means unknown, not permissive.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/javascript/` (see its README.md).

Fixture harness: `knowledge/harnesses/typescript/` (see its README.md).

TypeScript and JavaScript sources both use the JavaScript oracle.
