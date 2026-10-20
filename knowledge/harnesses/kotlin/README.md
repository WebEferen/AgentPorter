# Kotlin parity harness

`PorterHarness.kt` runs every recorded case in `.porter/fixtures/<unit>/*.json` through a Kotlin (JVM) port
and writes `.porter/runs/<run>/<unit>.json` (see [CONTRACT.md](../../oracles/CONTRACT.md)). It never compares;
`porter parity collect` does. A single file with its own JSON reader and writer, no dependencies beyond the
Kotlin standard library. Tested with kotlinc 2.2.20 on Java 21.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Copy it into the port

With Gradle, put both files in the test source set so they never ship:

```sh
mkdir -p src/test/kotlin/porter
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/kotlin/PorterHarness.kt src/test/kotlin/porter/
cp ${CLAUDE_PLUGIN_ROOT}/knowledge/harnesses/kotlin/Bindings.example.kt src/test/kotlin/porter/Bindings.kt
```

and register a task in `build.gradle.kts`:

```kotlin
tasks.register<JavaExec>("porterHarness") {
    classpath = sourceSets["test"].runtimeClasspath
    mainClass.set("porter.PorterHarnessKt")
}
```

## Run it

```sh
./gradlew porterHarness --args="--workspace .porter --run <run>"
porter parity collect --run <run>
```

Without Gradle, compile the harness, the bindings and the port into one jar:

```sh
kotlinc porter/PorterHarness.kt porter/Bindings.kt src/ -include-runtime -d build/porter-harness.jar
java -jar build/porter-harness.jar --workspace .porter --run <run> [--unit <unit>]... [--timeout <seconds>]
```

The default run id is the UTC time. Exit code 0 when runs were written, 2 when the harness cannot run.

## Bindings

`Bindings.kt` declares `val bindings: Map<String, Binding>` in package `porter`, one entry per source call id.
A `Binding` is `(args, kwargs, input) -> Any?` over decoded values: JSON integers are `Long`, other numbers
`Double`, `$int` is `Long` or `BigInteger`, `$float` is `Double`, `$bytes` is `ByteArray`, `$decimal` is
`BigDecimal`, `$datetime` is `OffsetDateTime`, `LocalDateTime` or `LocalDate`, `$set` is a `Set`, `$map` and
JSON objects are `Map`s, `$undefined` is `null`. `input["init"]` holds constructor arguments for
`Class.method` calls.

Bindings translate calling conventions only (casts such as `(args[0] as Long).toInt()`, named arguments, a
receiver built from `init`) and never patch a result. Return `Undefined` where the JavaScript source returned
`undefined` and the port returns `null`. A call id without a binding becomes the outcome category
`MissingBinding`.

## Serialization

The same rules as the Java oracle (`knowledge/oracles/java/README.md`), plus: `Unit` is `null`, `Pair` and
`Triple` are arrays, a `Sequence` is an array capped at 10000 items, and `Undefined` is `{"$undefined": true}`.
Data classes and other objects become `$type` with public fields and getters, sorted. A Boolean property
named `isActive` comes out as `active`, because the harness reads JVM getters, not Kotlin metadata.

## Errors and timeouts

The category is the exception's simple name: `require` throws `IllegalArgumentException`, `check` and `error`
throw `IllegalStateException`. A port exception class named after the source category (`class Error :
Exception`) matches without an error map.

Each case runs on a worker thread for `--timeout` seconds (default 10). On timeout the thread is interrupted
and abandoned; the JVM exits when the harness finishes.

## Limitations

- `java.time` values print with `toString()`, which drops zero seconds (`2024-02-29T10:00Z`).
- Getters run during serialization.
