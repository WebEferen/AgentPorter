# C# ecosystem

| Field | Value |
| --- | --- |
| Registry | NuGet (<https://www.nuget.org>, API at <https://api.nuget.org/v3/index.json>) |
| Registry adapter | `porter.py registry lookup --registry nuget` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

## 1. Registry API

Package ids are case-insensitive dotted names, for example `Newtonsoft.Json`.
Registration URLs use the lowercase id. The service index
`https://api.nuget.org/v3/index.json` is the documented way to discover the
other URLs; resolve them from it instead of hard-coding them.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -m 30 -A "$UA" "https://api.nuget.org/v3/index.json"
curl -s -m 30 -A "$UA" "https://azuresearch-usnc.nuget.org/query?q=packageid:Newtonsoft.Json&prerelease=false&semVerLevel=2.0.0"
curl -s -m 30 -A "$UA" "https://api.nuget.org/v3/registration5-semver1/newtonsoft.json/index.json"
curl -s -m 30 -A "$UA" --compressed "https://api.nuget.org/v3/registration5-gz-semver2/newtonsoft.json/index.json"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Service discovery | `https://api.nuget.org/v3/index.json` | `resources[].@id`, `resources[].@type` (`SearchQueryService`, `RegistrationsBaseUrl/3.6.0`) |
| Package metadata | `https://azuresearch-usnc.nuget.org/query?q=packageid:<id>&prerelease=false&semVerLevel=2.0.0` | `data[].id`, `.description`, `.projectUrl`, `.owners`, `.registration` |
| Latest version and date | search, then `https://api.nuget.org/v3/registration5-semver1/<lowercase id>/index.json` | `data[].version`, `data[].versions[].version`; `items[].items[].catalogEntry.version`, `.published`, `.listed` |
| License | registration | `catalogEntry.licenseExpression`, `catalogEntry.licenseUrl`; search `data[].licenseUrl` |
| Deprecation and advisories | search; registration (see notes) | `data[].deprecation`, `data[].vulnerabilities`; `catalogEntry.deprecation`, `catalogEntry.vulnerabilities` |
| Adoption signal | search | `data[].totalDownloads`, `data[].versions[].downloads`, `data[].verified` |
| Search | `https://azuresearch-usnc.nuget.org/query?q=<q>&prerelease=false&semVerLevel=2.0.0` | `totalHits`, `data[].id`, `.version`, `.totalDownloads`, `.verified`, `.description` |

Observed on 2026-10-20:

- Service index `version` `3.0.0`. `SearchQueryService` points to
  `azuresearch-usnc` (primary) and `azuresearch-ussc` (secondary).
  `RegistrationsBaseUrl` (plus `/3.0.0-rc`, `/3.0.0-beta`) is
  `registration5-semver1/`; `/3.4.0` is `registration5-gz-semver1/`; `/3.6.0`
  and `/Versioned` are `registration5-gz-semver2/`, the only hive that
  includes SemVer 2.0.0 versions.
- Search for `packageid:Newtonsoft.Json`: `totalHits` 1; `data[0]` had `id`,
  `version` `13.0.4`, `description`, `projectUrl`, `licenseUrl`
  (`https://www.nuget.org/packages/Newtonsoft.Json/13.0.4/license`),
  `totalDownloads` 9325394018, `verified` true, `versions[]` (`version`,
  `downloads`, `@id`), `vulnerabilities` `[]`, and `registration` pointing at
  the `registration5-gz-semver2` hive. The `packageid:` match ignored case.
  An unknown id returned HTTP 200 with `totalHits` 0 and `data` `[]`.
- Search `deprecation` appears only on deprecated packages. WindowsAzure.Storage
  9.3.3: `{"alternatePackage": {"id": "Azure.Storage.Common", "range": "*"},
  "message": "...", "reasons": ["Legacy"]}`. xunit 2.9.3: `reasons`
  `["Legacy"]`, alternate `xunit.v3`.
- Registration index (`registration5-semver1`) for newtonsoft.json: `count` 2
  pages, both inlined, each with `lower`, `upper`, `count` and `items[]`.
  `catalogEntry` keys: `id`, `version`, `published`, `listed`,
  `licenseExpression`, `licenseUrl`, `projectUrl`, `description`,
  `dependencyGroups`, `tags`, `authors` and a few more. Prereleases are
  included (the newest entry was `14.0.1-beta2`), so filter versions with a
  `-` suffix.
- Pages are not always inlined. AWSSDK.Core had 24 pages with no `items`; the
  adapter must fetch each page's `@id` (for example
  `.../awssdk.core/page/4.0.9.6/4.0.102.12.json`), which returns `items`,
  `parent`, `lower` and `upper`. The newest versions are in the last page.
- Advisory data is missing from `registration5-semver1`: its entries had no
  `deprecation` or `vulnerabilities` keys at all (Newtonsoft.Json 12.0.3,
  WindowsAzure.Storage). The same entries in `registration5-gz-semver2` had
  `vulnerabilities: [{"advisoryUrl":
  "https://github.com/advisories/GHSA-5crp-9r3c-p9vr", "severity": "2"}]` and
  the `deprecation` object. The gz hives are gzip-compressed (send
  `Accept-Encoding: gzip`; curl `--compressed`). Use `RegistrationsBaseUrl/3.6.0`
  from the service index when deprecation or advisory data matters.
- `severity` is a string: `0` low, `1` moderate, `2` high, `3` critical.
- Unlisted versions have `listed: false` and `published`
  `1900-01-01T00:00:00+00:00`.
- An unknown id in a registration hive returns HTTP 404 with an XML
  `BlobNotFound` body.

## 2. Maturity signals

- Downloads: `totalDownloads` and per-version `versions[].downloads`.
- `verified`: true when the owner reserved the id prefix. It guards against
  look-alike ids but says nothing about quality; widely used packages such as
  Shouldly and StyleCop.Analyzers had `verified` false.
- Release cadence: `catalogEntry.published`, ignoring the `1900-01-01` dates of
  unlisted versions.
- Deprecation: `reasons` (`Legacy`, `CriticalBugs`, `Other`), `message`, and
  `alternatePackage.id`.
- Advisories: `vulnerabilities[]` with GitHub advisory URLs. Locally,
  `dotnet restore` reports them (NuGet Audit) and
  `dotnet list package --vulnerable` lists them.
- Target frameworks: `catalogEntry.dependencyGroups[].targetFramework`
  (xunit.v3 4.0.2: `.NETFramework4.7.2`, `net8.0`).
- Missing: no dependents count and no repository health data in these
  endpoints.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `*.csproj` | Project file with `PackageReference` items | Yes |
| `Directory.Packages.props` | Central package versions | Yes |
| `packages.lock.json` | Resolved versions per target framework | Yes |
| `Directory.Build.props` | Shared MSBuild properties | No |
| `packages.config` | Legacy (.NET Framework) references | No |
| `global.json` | SDK version pin | No |
| `*.sln`, `*.slnx` | Solution files | No |

Scopes as `deps-graph` reports them:

- `<PackageReference Include="Serilog" Version="4.3.0" />` reads `Include` and
  `Version`. `PrivateAssets="all"` marks build-only references (analyzers,
  source generators, SourceLink) and is reported as build.
- Central Package Management: `Directory.Packages.props` sets
  `<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>` and
  `<PackageVersion Include="..." Version="..." />`; project files then omit
  `Version`.
- `packages.lock.json` exists when `RestorePackagesWithLockFile` is true. It
  lists `Direct` and `Transitive` packages with a `resolved` version per
  target framework.
- No dev scope: test frameworks are plain `PackageReference`s in a separate
  test project (`*.Tests.csproj`, `<IsTestProject>true</IsTestProject>`).
  Judge scope by the project the reference sits in.
- Optional and peer dependencies do not exist. Shared frameworks use
  `<FrameworkReference Include="Microsoft.AspNetCore.App" />`, which is not a
  NuGet package.

Import names: the namespace cannot be derived from the package id. Pass
`porter.py usage-scan --import-name <namespace prefix>`, for example `Xunit`
for `xunit.v3`. Even when they look alike, check the assembly's root
namespace.

## 4. Package layout

- `src/<Name>/<Name>.csproj`, `tests/<Name>.Tests/<Name>.Tests.csproj`, a
  solution file at the root (`.sln` or the newer XML `.slnx`).
- Shared settings in `Directory.Build.props`, versions in
  `Directory.Packages.props`, SDK pin in `global.json`, style in
  `.editorconfig`.
- Namespaces follow folders under `RootNamespace` (defaults to the project
  name). Prefer file-scoped namespaces (`namespace Foo.Bar;`).
- Tests reach internals through `InternalsVisibleTo`.
- Libraries have no entry point. Console apps use `Program.cs` with top-level
  statements and `<OutputType>Exe</OutputType>`; `<PackAsTool>true</PackAsTool>`
  makes a `dotnet tool`.

## 5. Test runners

- xUnit v3 (`xunit.v3` 4.0.2). `xunit` 2.x (2.9.3) is deprecated on NuGet as
  `Legacy` with `xunit.v3` as the alternate.
- NUnit 5.0.0, MSTest 4.5.1, and TUnit 1.75.0 (source generated, runs only on
  Microsoft.Testing.Platform).
- `dotnet test` runs VSTest-based projects through `Microsoft.NET.Test.Sdk`
  (18.11.0). Microsoft.Testing.Platform is the newer runner; the .NET 10 SDK
  can switch `dotnet test` to it in `global.json`.
- One test (VSTest): `dotnet test --filter "FullyQualifiedName~SlugTests"`.
- Assertions: built-in `Assert`, Shouldly 4.3.0, or AwesomeAssertions 9.6.0
  (Apache-2.0). FluentAssertions 8 moved to a commercial license; its 8.11.0
  catalog entry has an empty `licenseExpression`.
- Coverage: coverlet.collector (10.1.0),
  `dotnet test --collect:"XPlat Code Coverage"`.

## 6. Lint and format

- `dotnet format` ships with the SDK: `dotnet format --verify-no-changes` in
  CI; subcommands `whitespace`, `style`, `analyzers`. It reads
  `.editorconfig`.
- The .NET analyzers are built into the SDK. Turn them up with
  `<AnalysisLevel>latest-recommended</AnalysisLevel>`,
  `<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>` and
  `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`.
- Extra analyzers, referenced with `PrivateAssets="all"`: Roslynator.Analyzers
  (5.0.1), SonarAnalyzer.CSharp (10.35), StyleCop.Analyzers (1.1.118 stable).
- Microsoft.CodeAnalysis.PublicApiAnalyzers (5.6.0) tracks the public surface
  in `PublicAPI.Shipped.txt` and `PublicAPI.Unshipped.txt`.
- CSharpier is an opinionated formatter if the project wants one.

## 7. Type checking

- The C# compiler is the type checker. Enable nullable reference types with
  `<Nullable>enable</Nullable>` and fail on them with
  `<WarningsAsErrors>nullable</WarningsAsErrors>`.
- `LangVersion` defaults to the newest the target framework supports (C# 14
  for `net10.0`). Multi-targeted libraries are limited by their oldest target
  unless they add polyfills.
- `<IsAotCompatible>true</IsAotCompatible>` turns on the trimming and Native
  AOT analyzers for a library.
- `<GenerateDocumentationFile>true</GenerateDocumentationFile>` makes missing
  XML docs on public API a warning (CS1591).

## 8. Build and publish

- `dotnet build -c Release`, then `dotnet pack -c Release -o artifacts` for
  the `.nupkg`. Add `<IncludeSymbols>true</IncludeSymbols>` and
  `<SymbolPackageFormat>snupkg</SymbolPackageFormat>` for a symbols package.
- Package metadata in the csproj: `PackageId`, `Version`, `Authors`,
  `Description`, `PackageLicenseExpression`, `PackageProjectUrl`,
  `RepositoryUrl`, `PackageReadmeFile`, `PackageTags`.
- Push: `dotnet nuget push artifacts/*.nupkg --api-key "$NUGET_API_KEY"
  --source https://api.nuget.org/v3/index.json`. nuget.org also supports
  trusted publishing from GitHub Actions (`NuGet/login` action), which
  replaces the long-lived key.
- `<EnablePackageValidation>true</EnablePackageValidation>` with
  `<PackageValidationBaselineVersion>` catches breaking changes during pack.
- SourceLink is built into the SDK since .NET 8; set
  `<ContinuousIntegrationBuild>true</ContinuousIntegrationBuild>` in CI.
- Versions are permanent. On nuget.org a version can only be unlisted or
  marked deprecated.

## 9. Runtime version policy

- .NET 10 is the current LTS (released 2025-11-11, supported until
  2028-11-14). .NET 8 (LTS) and .NET 9 (STS) both reach end of support on
  2026-11-10 (endoflife.date). A new major version ships each November; even
  numbers are LTS (three years), odd numbers are STS (two years).
- Declare targets with `<TargetFramework>net10.0</TargetFramework>` or
  `<TargetFrameworks>net10.0;netstandard2.0</TargetFrameworks>`. Add
  `netstandard2.0` only when .NET Framework or Unity consumers matter.
- The registry exposes targets as `dependencyGroups[].targetFramework`, in
  either short (`net8.0`) or long (`.NETStandard2.0`, `.NETFramework4.7.2`)
  form.
- Pin the SDK in `global.json`:
  `{"sdk": {"version": "10.0.100", "rollForward": "latestFeature"}}`.

## 10. License fields

- csproj: `<PackageLicenseExpression>MIT</PackageLicenseExpression>` (SPDX),
  or `<PackageLicenseFile>LICENSE.txt</PackageLicenseFile>` with the file
  packed. `<PackageLicenseUrl>` is deprecated.
- Registry: `catalogEntry.licenseExpression` (Newtonsoft.Json `MIT`,
  AWSSDK.Core `Apache-2.0`). It is an empty string when the package ships a
  license file (FluentAssertions 8.11.0); read the file through `licenseUrl`
  or from the `.nupkg`.
- Search `licenseUrl` points to a nuget.org page
  (`https://www.nuget.org/packages/<id>/<version>/license`), not to the
  license text itself.

## 11. AgentPorter templates

Oracle template: none for C# yet (wanted).

Fixture harness: none for C# targets yet (wanted).
