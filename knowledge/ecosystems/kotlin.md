# Kotlin ecosystem

| Field | Value |
| --- | --- |
| Registry | Maven Central (<https://central.sonatype.com>, files at <https://repo1.maven.org/maven2/>) |
| Registry adapter | `porter.py registry lookup --registry maven` |
| Last verified | 2026-10-20 |

How to use this file: `deps` reads it when this language is the source (to
read manifests) or the target (to find and judge candidates); `strategy` and
`implement` read it to scaffold the target package and toolchain.

Kotlin libraries are Maven artifacts. Registry endpoints, prerelease handling,
license resolution and maturity signals are shared with Java and documented
once in `java.md` sections 1 and 2. This file covers what differs for Kotlin.

## 1. Registry API

The adapter calls the same endpoints as for Java: `maven-metadata.xml`, the
POM, the two deps.dev endpoints and Maven Central search. See the endpoint
table, field list and observed response shapes in `java.md` section 1.

Kotlin-specific observations, recorded on 2026-10-20:

```bash
UA="agentporter/0.1 (+https://github.com/WebEferen/AgentPorter)"
curl -s -m 30 -A "$UA" "https://repo1.maven.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core/maven-metadata.xml"
curl -s -m 30 -A "$UA" "https://repo1.maven.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core/1.11.0/kotlinx-coroutines-core-1.11.0.pom"
curl -s -m 30 -A "$UA" "https://repo1.maven.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core/1.11.0/kotlinx-coroutines-core-1.11.0.module"
curl -s -m 30 -A "$UA" "https://api.deps.dev/v3/systems/maven/packages/org.jetbrains.kotlinx%3Akotlinx-coroutines-core/versions/1.11.0"
```

- `maven-metadata.xml` for kotlinx-coroutines-core: `release` `1.11.0`,
  `lastUpdated` `20260508122950`. deps.dev: `publishedAt`
  `2026-05-07T14:02:59Z`, `licenses: ["Apache-2.0"]`, `advisoryKeys: []`.
- `org.jetbrains.kotlin:kotlin-stdlib` had `release` `2.5.0-Beta1`. The newest
  stable entry in its version list was `2.4.21`. Filter qualifiers as described
  in `java.md` before reporting a version.
- Multiplatform (KMP) libraries publish a root artifact plus one artifact per
  target. The root POM for kotlinx-coroutines-core carries the comment
  `published-with-gradle-metadata` and depends on `kotlinx-coroutines-core-jvm`,
  so Maven consumers get the JVM variant.
- The Gradle module metadata file (`<a>-<v>.module`, `formatVersion` `1.1`)
  lists `variants[]`. Their `attributes["org.jetbrains.kotlin.platform.type"]`
  values were `common`, `jvm`, `js`, `wasm` and `native`, and
  `available-at.module` names the per-target artifact (for example
  `kotlinx-coroutines-core-iosarm64`). The adapter does not fetch this file;
  fetch it by hand when the port targets Kotlin/JS, Wasm or Native.

## 2. Maturity signals

Same as `java.md` section 2: no download counts, deps.dev for release dates,
advisories and dependents. Kotlin-specific checks:

- Platform coverage: a JVM-only library cannot serve a multiplatform port.
  Check the `.module` variants (section 1).
- Kotlin version lag: libraries built with a newer Kotlin than the target
  project may not load. Compare the `kotlin-stdlib` version in the library's
  POM with the project's Kotlin version. For KMP libraries it is in the `-jvm`
  POM, not the root one (kotlinx-coroutines-core-jvm 1.11.0: `2.2.20`).
- Android libraries (`androidx.*`) live on Google's Maven repository and are
  not found on Maven Central (HTTP 404).

## 3. Manifests and lockfiles

| File | Role | Parsed by `porter.py deps-graph` |
| --- | --- | --- |
| `build.gradle.kts` | Gradle build, Kotlin DSL | Yes, by regex |
| `build.gradle` | Gradle build, Groovy DSL | Yes, by regex |
| `gradle/libs.versions.toml` | Gradle version catalog | Yes |
| `pom.xml` | Maven build (less common for Kotlin) | Yes |
| `gradle.lockfile` | Gradle dependency locking | No |
| `settings.gradle.kts` | Projects, repositories, included builds | No |

Scopes as `deps-graph` reports them:

- Gradle: `implementation`, `api` and `runtimeOnly` are runtime;
  `compileOnly`, `kapt`, `ksp` and `annotationProcessor` are build;
  `testImplementation` and `testRuntimeOnly` are dev.
- `pom.xml`: `compile` and `runtime` are runtime, `test` is dev, `provided` is
  build, with `${property}` substitution from `<properties>`.
- KMP builds declare dependencies inside
  `kotlin { sourceSets { commonTest.dependencies { implementation(...) } } }`.
  The configuration name says `implementation` even in a test source set, so
  confirm by hand which source set a dependency belongs to before trusting its
  scope.
- Kotlin DSL shorthands: `kotlin("test")` means
  `org.jetbrains.kotlin:kotlin-test`; `libs.<alias>` refers to the version
  catalog; `platform(...)` imports a BOM.
- Optional and peer dependencies: same as Java (`compileOnly` is the closest
  to a peer dependency).

Import names: the Kotlin package cannot be derived from `group:artifact`. Pass
`porter.py usage-scan --import-name <namespace prefix>`, for example
`kotlinx.coroutines` for `org.jetbrains.kotlinx:kotlinx-coroutines-core`.

## 4. Package layout

- JVM-only: `src/main/kotlin`, `src/test/kotlin` (Java files may sit in
  `src/main/java` next to them).
- Multiplatform: `src/commonMain/kotlin`, `src/commonTest/kotlin`, plus one
  pair per target or shared group (`jvmMain`, `jsMain`, `iosMain`,
  `nativeMain`).
- Gradle Kotlin DSL: `settings.gradle.kts`, `build.gradle.kts`,
  `gradle/libs.versions.toml`, shared build logic in an included build such as
  `build-logic/`.
- The coding conventions allow omitting the common package root from the
  directory path, but mirroring the full package is the safe default.
- Libraries should enable explicit API mode (`kotlin { explicitApi() }`) so
  every public declaration needs a visibility modifier and return type.

## 5. Test runners

- `kotlin.test` (`kotlin("test")`) works on every target. On the JVM it runs
  on JUnit 5 or 6 through `tasks.test { useJUnitPlatform() }`.
- Kotest 6.2.6 (`io.kotest:kotest-runner-junit5` on the JVM, Gradle plugin
  `io.kotest` for multiplatform) adds spec styles and property testing.
- MockK 1.14.x for mocks (JVM). `kotlinx-coroutines-test` provides `runTest`
  for suspending code.
- Commands: `./gradlew test` (JVM), `./gradlew allTests` (all KMP targets),
  `./gradlew jvmTest --tests 'com.example.SlugTest'`.

## 6. Lint and format

- ktlint 1.8.0 (`com.pinterest.ktlint:ktlint-cli`), configured through
  `.editorconfig`. Run it from Spotless (`kotlin { ktlint() }`,
  `kotlinGradle { ktlint() }`) or the `org.jlleitschuh.gradle.ktlint` plugin
  (14.2.0): `./gradlew ktlintCheck`.
- detekt: 1.23.8 (`io.gitlab.arturbosch.detekt`) is the stable line and was
  built against Kotlin 2.0, so it can clash with newer Kotlin Gradle plugins.
  detekt 2.0 is in alpha under the new id `dev.detekt` (2.0.0-alpha.6).
- `kotlin.code.style=official` in `gradle.properties`, and
  `compilerOptions { allWarningsAsErrors.set(true) }` in CI.

## 7. Type checking

- `kotlinc` checks types, including null safety. K2 has been the default
  compiler since Kotlin 2.0.
- Java types without nullness annotations appear as platform types (`T!`) and
  are not null-checked. Kotlin reads JSpecify annotations on Java code.
- API stability: the binary-compatibility-validator plugin (0.18.2) keeps an
  `api/` dump checked by `./gradlew apiCheck` and updated by
  `./gradlew apiDump`. The Kotlin Gradle plugin also has an experimental
  built-in ABI validation block.

## 8. Build and publish

- `./gradlew build` compiles every target; JVM jars land in `build/libs/`.
  Gradle 9.8.2 is current.
- Publish to Maven Central with the `com.vanniktech.maven.publish` plugin
  (0.37.0), which handles KMP publications, signing and the Central Publisher
  Portal: `./gradlew publishToMavenCentral` or
  `./gradlew publishAndReleaseToMavenCentral`. Central's requirements are in
  `java.md` section 8.
- A KMP publication uploads the root artifact with its `.module` file and one
  artifact per target. Apple targets need a macOS host to build.
- Docs: Dokka 2.x (`./gradlew dokkaGenerate`) can also produce the
  `-javadoc.jar` Central requires.
- Gradle plugins are published to the Gradle Plugin Portal with
  `com.gradle.plugin-publish` and `./gradlew publishPlugins`.

## 9. Runtime version policy

- Kotlin 2.4 is current (2.4.0 on 2026-06-03, 2.4.21 latest patch); 2.5.0 is
  in beta. Language releases come every six months (2.x.0), with a tooling
  release (2.x.20) and bugfix releases in between.
- JVM target: `kotlin { jvmToolchain(17) }`, or
  `compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }` together with Java's
  `targetCompatibility`. JVM version floors follow `java.md` section 9.
- Consumers on older Kotlin compilers: set `compilerOptions.apiVersion` and
  `languageVersion` to the oldest Kotlin version you support. The Kotlin Gradle
  plugin adds `kotlin-stdlib` at its own version, and that version becomes a
  floor for consumers.
- Platforms: a KMP library declares its targets in the `kotlin {}` block
  (`jvm()`, `js { browser(); nodejs() }`, `wasmJs()`, `iosArm64()`,
  `linuxX64()`). Published targets show up as `.module` variants.
- Android targets also declare `minSdk`.

## 10. License fields

Same as `java.md` section 10. In `build.gradle.kts` the license goes in
`mavenPublishing { pom { licenses { license { name.set("Apache-2.0"); url.set("...") } } } }`.
deps.dev `licenses[]` returned `["Apache-2.0"]` for kotlinx-coroutines-core,
whose POM declares `<name>Apache-2.0</name>` directly.

## 11. AgentPorter templates

Oracle template: none for Kotlin. When the source library's API can be called
from the JVM, reuse the Java oracle: `knowledge/oracles/java/` (see its
README.md).

Fixture harness: `knowledge/harnesses/kotlin/` (see its README.md).
