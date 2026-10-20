# Java ecosystem

| Field | Value |
| --- | --- |
| Registry | Maven Central (<https://central.sonatype.com>, files at <https://repo1.maven.org/maven2/>) |
| Registry adapter | `porter.py registry lookup --registry maven` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

Kotlin uses the same registry; `kotlin.md` points back here for the registry
parts.

## 1. Registry API

Package names are `group:artifact`, for example `com.google.guava:guava`. In
repository URLs the group's dots become slashes (`com/google/guava/guava`). In
deps.dev URLs the colon is encoded as `%3A`. Maven Central has no JSON metadata
API of its own, so the adapter combines repository files with deps.dev.

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -m 30 -A "$UA" "https://repo1.maven.org/maven2/com/google/guava/guava/maven-metadata.xml"
curl -s -m 30 -A "$UA" "https://repo1.maven.org/maven2/com/google/guava/guava/33.7.2-jre/guava-33.7.2-jre.pom"
curl -s -m 30 -A "$UA" "https://api.deps.dev/v3/systems/maven/packages/com.google.guava%3Aguava"
curl -s -m 30 -A "$UA" "https://api.deps.dev/v3/systems/maven/packages/com.google.guava%3Aguava/versions/33.7.2-jre"
curl -s -m 30 -A "$UA" "https://search.maven.org/solrsearch/select?q=guava&rows=10&wt=json"
```

| Purpose | Endpoint | Fields used |
| --- | --- | --- |
| Package metadata | `https://repo1.maven.org/maven2/<g path>/<a>/<v>/<a>-<v>.pom` | `description`, `url`, `scm/url`, `licenses/license/name`, `parent` |
| Latest version and date | `https://repo1.maven.org/maven2/<g path>/<a>/maven-metadata.xml`, then `https://api.deps.dev/v3/systems/maven/packages/<g>%3A<a>` | `versioning/latest`, `versioning/release`, `versioning/versions/version`, `versioning/lastUpdated`; deps.dev `versions[].versionKey.version`, `versions[].publishedAt`, `versions[].isDefault` |
| License | `https://api.deps.dev/v3/systems/maven/packages/<g>%3A<a>/versions/<v>` | `licenses[]` (SPDX), POM `licenses` as fallback |
| Advisories and deprecation | same deps.dev version endpoint | `advisoryKeys[].id`, `isDeprecated`, `deprecatedReason`, `publishedAt`, `links[]` (`SOURCE_REPO`, `HOMEPAGE`) |
| Adoption signal | none | Maven Central publishes no download counts |
| Search | `https://search.maven.org/solrsearch/select?q=<q>&rows=10&wt=json` | `response.numFound`, `response.docs[].id`, `.g`, `.a`, `.latestVersion`, `.versionCount`, `.timestamp` |

Observed on 2026-10-20:

- guava `maven-metadata.xml`: `latest` and `release` both `33.7.2-jre`,
  `lastUpdated` `20260929145258` (UTC, `yyyyMMddHHmmss`). Unknown coordinates
  return HTTP 404.
- `release` is the newest non-SNAPSHOT upload and can be a prerelease. The same
  day, `org.jetbrains.kotlin:kotlin-stdlib` had `release` `2.5.0-Beta1` and
  `org.apache.maven:apache-maven` had `4.0.0-rc-7`. Drop qualifiers such as
  `alpha`, `beta`, `rc`, `cr`, `M<n>`, `milestone`, `preview`, `eap` and
  `SNAPSHOT` before calling a version the latest stable one. Guava's `-jre` and
  `-android` suffixes are variants, not prereleases.
- The guava POM has no `licenses` or `scm`. Both come from its parent,
  `com.google.guava:guava-parent`. commons-lang3 also inherits its license.
  deps.dev resolves the parent chain and returned `licenses: ["Apache-2.0"]`, so
  prefer deps.dev and follow `<parent>` only when deps.dev has nothing.
- deps.dev package endpoint: each `versions[]` entry has `versionKey.version`,
  `publishedAt`, `isDefault`, `isDeprecated`, `deprecatedReason`. The array is
  sorted by version string, not by date (`r09` came last), and one entry has
  `isDefault: true` (guava `33.7.2-jre`, `publishedAt` `2026-09-29T14:47:28Z`).
  Unknown packages return HTTP 404 with the body `package not found`.
- deps.dev version endpoint: `advisoryKeys` was `[]` for guava and listed GHSA
  ids for `org.apache.logging.log4j:log4j-core` 2.14.1, including
  `GHSA-jfh8-c2jp-5v3q` (CVE-2021-44228). Details come from
  `https://api.deps.dev/v3/advisories/<id>` (`title`, `aliases`, `cvss3Score`,
  `url`).
- Search is slow and stale. The first call timed out at 30 s; a retry answered
  in under 1 s. It reported guava `latestVersion` `33.4.8-jre` (`timestamp`
  1744651522422, April 2025) and `versionCount` 150, while the metadata file and
  deps.dev had `33.7.2-jre` and 160 versions. Use search only to discover
  coordinates, then confirm versions with `maven-metadata.xml` and deps.dev.
- Artifacts under `androidx.*` live on Google's Maven repository
  (`https://dl.google.com/android/maven2/`) and return 404 on Maven Central.
  Gradle plugins usually live on `https://plugins.gradle.org/m2/`.

## 2. Maturity signals

- Release cadence: sort deps.dev `versions[].publishedAt` yourself. The
  `lastUpdated` value in `maven-metadata.xml` is when the metadata file last
  changed, which is usually but not always the last release.
- Prereleases: Maven has no prerelease flag. Judge by the version qualifier
  (see section 1).
- Downloads: missing. Central shows download statistics only to namespace
  owners.
- Dependents: deps.dev
  `https://api.deps.dev/v3alpha/systems/maven/packages/<g>%3A<a>/versions/<v>:dependents`
  returns `dependentCount` and `directDependentCount` (guava 33.7.2-jre: 3453
  and 1408). The adapter does not call it.
- Project health: `https://api.deps.dev/v3/projects/github.com%2F<owner>%2F<repo>`
  returns `starsCount`, `forksCount`, `openIssuesCount` and
  `scorecard.overallScore` (guava: 51924 stars, score 8.4). Not called by the
  adapter.
- Deprecation: Central has no deprecation flag, so deps.dev `isDeprecated` is
  almost always false. Look for a `<relocation>` element under
  `distributionManagement` in the POM (coordinates moved), notices in the
  README, and archived source repositories.
- Advisories: deps.dev `advisoryKeys` (OSV data).
- Immutability: released files cannot be deleted or replaced, so there is no
  yank signal. A bad release is fixed by a newer version.

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `pom.xml` | Maven project model and dependencies | Yes |
| `build.gradle` | Gradle build, Groovy DSL | Yes, by regex |
| `build.gradle.kts` | Gradle build, Kotlin DSL | Yes, by regex |
| `gradle/libs.versions.toml` | Gradle version catalog | Yes |
| `gradle.lockfile` | Gradle dependency locking | No |
| `settings.gradle`, `settings.gradle.kts` | Multi-project layout, repositories | No |

Scopes as `deps-graph` reports them:

- `pom.xml`: `compile` (Maven's default when `<scope>` is absent) and `runtime`
  are runtime, `test` is dev, `provided` is build. `${property}` references are
  substituted from `<properties>` in the same file. Versions that come from a
  parent POM or an imported BOM have to be checked by hand.
- Gradle: `implementation`, `api` and `runtimeOnly` are runtime;
  `compileOnly`, `kapt`, `ksp` and `annotationProcessor` are build;
  `testImplementation` and `testRuntimeOnly` are dev.
- Optional: Maven marks them with `<optional>true</optional>`. Gradle has no
  direct equivalent (feature variants or `compileOnly`).
- Peer: no such concept. The closest is `provided` or `compileOnly`, where the
  consumer supplies the library.

Import names: the Java package cannot be derived from `group:artifact`. Pass
`porter.py usage-scan --import-name <namespace prefix>`, for example
`com.google.common` for `com.google.guava:guava`. To find the prefix, list the
jar (`unzip -l <a>-<v>.jar`) or read `module-info.class` or the
`Automatic-Module-Name` manifest entry.

## 4. Package layout

- Maven standard layout, also Gradle's default: `src/main/java`,
  `src/main/resources`, `src/test/java`, `src/test/resources`.
- Directories mirror packages: `package com.example.slug;` lives in
  `src/main/java/com/example/slug/`.
- Group ids are reverse domain names. Central only accepts a group you have
  verified (a domain you control, or `io.github.<user>`).
- JPMS: `src/main/java/module-info.java`, or at least an
  `Automatic-Module-Name` entry in the jar manifest.
- Multi-module builds: `<modules>` in a parent `pom.xml`, or `include(...)` in
  `settings.gradle.kts`.
- Libraries have no entry point. Applications set `Main-Class` in the jar
  manifest. Service implementations are listed in `META-INF/services/`.

## 5. Test runners

- JUnit Jupiter on the JUnit Platform. JUnit 6 (latest 6.1.3 when verified,
  BOM `org.junit:junit-bom`) needs Java 17; JUnit 5.x stays the choice for Java 8
  or 11 baselines.
- Maven: maven-surefire-plugin (3.6.0) runs `mvn test`; maven-failsafe-plugin
  runs integration tests in `mvn verify`. One test:
  `mvn -Dtest=SlugTest#handlesUnicode test`.
- Gradle: `tasks.test { useJUnitPlatform() }` plus
  `testRuntimeOnly("org.junit.platform:junit-platform-launcher")`, then
  `./gradlew test`. One test: `./gradlew test --tests 'com.example.SlugTest'`.
- Assertions and mocks: AssertJ 3.27.x (4.0 is in milestones), Mockito 5.x.
- Property tests: jqwik. Coverage: JaCoCo. Mutation testing: PIT.

## 6. Lint and format

- Spotless (Maven plugin 3.10.4, Gradle plugin 8.10.4) wraps the formatter:
  google-java-format (1.37.0), palantir-java-format or Eclipse.
  `mvn spotless:check` / `mvn spotless:apply`, `./gradlew spotlessCheck` /
  `./gradlew spotlessApply`.
- Checkstyle (14.3.0) with `google_checks.xml` or a project config, through
  maven-checkstyle-plugin or Gradle's `checkstyle` plugin.
- Error Prone (2.50.0) runs as a javac plugin and fails the build on bug
  patterns. PMD (7.28.0) and SpotBugs (4.10.5) are the other common analyzers.
- OpenRewrite automates migrations such as JUnit 4 to JUnit 5.

## 7. Type checking

- `javac` is the type checker. Add `-Xlint:all -Werror` through
  `<compilerArgs>` (Maven) or `options.compilerArgs` (Gradle).
- Nullness is not in the type system. Use JSpecify 1.0 annotations
  (`@NullMarked`, `@Nullable`) and check them with NullAway (0.14.2) under Error
  Prone, or with the Checker Framework.
- Generics are erased at runtime. Records and sealed interfaces (Java 17+)
  model value types and tagged unions from dynamic source languages.

## 8. Build and publish

- Build: `./mvnw -B verify` (jar in `target/`) or `./gradlew build` (jar in
  `build/libs/`). Commit the wrapper. Current stable: Maven 3.9.x and 3.10.0
  (Maven 4.0.0 is in release candidates), Gradle 9.8.2.
- Maven Central publishing goes through the Central Publisher Portal
  (central.sonatype.com). The old OSSRH service shut down on 2025-06-30.
- Central requires a verified namespace, a POM with `name`, `description`,
  `url`, `licenses`, `developers` and `scm`, `-sources.jar` and
  `-javadoc.jar`, and a GPG `.asc` signature for each file.
- Maven: `org.sonatype.central:central-publishing-maven-plugin` (0.12.0) with
  maven-source-plugin, maven-javadoc-plugin and maven-gpg-plugin, a Portal
  user token in `settings.xml`, then `./mvnw -B deploy`.
- Gradle: the `com.vanniktech.maven.publish` plugin (0.37.0):
  `./gradlew publishToMavenCentral`, or
  `./gradlew publishAndReleaseToMavenCentral` to skip the manual release step.
  JReleaser (1.26.0) works for both build tools.
- A published version is permanent. Bump the version to fix a mistake.

## 9. Runtime version policy

- LTS releases: 8, 11, 17, 21 and 25 (Adoptium). Java 25 (September 2025) is
  the newest LTS; Java 27 (September 2026) is the newest feature release and
  is supported only until the next one ships.
- Common library floors in 2026: Java 17 (JUnit 6 and Spring Boot 4 require
  it). Some libraries still ship Java 8 bytecode (guava).
- Declare the target with `<maven.compiler.release>17</maven.compiler.release>`
  in Maven, or in Gradle with
  `java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }` or
  `options.release = 17`. Prefer `--release` over `-source`/`-target`; it also
  checks API use against that JDK.
- In a published artifact, check the class file major version (52 = Java 8,
  55 = 11, 61 = 17, 65 = 21, 69 = 25) with `javap -v`, or the
  `org.gradle.jvm.version` attribute in `<a>-<v>.module` (guava 33.7.2-jre:
  `8`). Multi-release jars add classes under `META-INF/versions/<N>/`.
- Gradle 9 itself needs Java 17 to run but can compile for older targets with
  toolchains.

## 10. License fields

- POM: `<licenses><license><name>`, `<url>`, `<distribution>`. Names are free
  text ("Apache License, Version 2.0" in guava-parent, "Apache-2.0" in
  kotlinx-coroutines-core) and may be inherited from a parent POM.
- Gradle: set inside `pom { licenses { license { ... } } }` of the publication
  or of `mavenPublishing`.
- Registry: deps.dev `licenses[]` holds SPDX identifiers resolved through the
  parent chain. If it is empty, read the POM chain and the LICENSE file in the
  source repository.

## 11. AgentPorter templates

Oracle template: `knowledge/oracles/java/` (see its README.md).

Fixture harness: none for Java targets yet (wanted).
