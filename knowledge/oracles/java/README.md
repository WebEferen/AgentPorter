# Java oracle driver

`Oracle.java` records what the pinned Java (or other JVM) source does. It reads
`.porter/oracle/expanded/<unit>.json`, calls each case through reflection, and writes
`.porter/fixtures/<unit>/oracle.json` plus `.porter/oracle/timings/<unit>.json` as
[CONTRACT.md](../CONTRACT.md) describes. A single source file for Java 17 or newer, with its own small JSON
reader and writer and no dependencies.

`porter` below is `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/porter.py`.

## Run it

Build the source first and collect its runtime classpath, for example `mvn -q package` plus
`mvn -q dependency:build-classpath -Dmdep.outputFile=cp.txt`, or a Gradle task that prints
`sourceSets.main.runtimeClasspath.asPath`. The source launcher compiles the driver in memory:

```sh
porter fixtures expand
java -cp <source classes and jars> ${CLAUDE_PLUGIN_ROOT}/knowledge/oracles/java/Oracle.java --workspace .porter \
    [--unit <unit>]... [--package-version <v>] [--commit <sha>] [--timeout <seconds>]
porter fixtures validate
```

Exit codes: 0 when fixtures were written (thrown exceptions are outcomes), 2 when the driver cannot run: a
class or member that does not resolve, arguments that fit no overload, `kwargs` in a case, a CLI unit.

## How calls resolve

When the module part is a class, the qualified name is a member of it (nested classes with dots). When it is a
package, the first name is a class in it.

| Call | Input | What runs |
| --- | --- | --- |
| `com.acme.Text:slugify` | `args` | public static method |
| `com.acme.Text:MAX`, `com.acme.Color:RED` | `{}` | public static field or enum constant |
| `com.acme.Text:Options` | `args` | constructor of the nested class `Text.Options` |
| `com.acme:Counter` | `args` | public constructor |
| `com.acme:Counter.inc`, `com.acme.Counter:inc` | `init`, `args` | `new Counter(init.args).inc(args)` |

Overloads are picked by argument count and JSON types; when several fit, the closest one wins (`long` before
`int` before `short`, `double` before `float`, `String` exactly). Varargs work. Java has no named arguments, so
a case with non-empty `kwargs` exits 2.

Kotlin sources work too: top-level functions are static methods of the file facade class
(`ms.MsKt:parse` for `ms/Ms.kt`), `object` members need `@JvmStatic`, and default arguments need
`@JvmOverloads` or every argument in the case.

Arguments convert from JSON by parameter type: integers to `long`, `int`, `short`, `byte` (range checked),
`BigInteger`; numbers to `double`, `float`, `BigDecimal`; strings to `String`, `char`, enum constants;
arrays to Java arrays, `List`, `Collection`, `Set` (generic element types are followed); objects to `Map`;
any value to `Optional`. Tagged inputs decode too: `$int`, `$float`, `$decimal`, `$bytes` (to `byte[]`),
`$enum`, `$set`, `$map`, and `$datetime` (to `Instant`, `LocalDate`, `LocalDateTime`, `LocalTime`,
`OffsetDateTime`, `ZonedDateTime` or `Date`). An `Object` parameter gets the natural value (`Long`, `Double`,
`String`, `Boolean`, `List`, `Map`).

## Serialization

| Java | JSON |
| --- | --- |
| `long` beyond 2^53, `BigInteger` | `{"$int": "..."}` |
| `float` | shortest float text, so `0.1f` stays `0.1` |
| NaN, ±Infinity, -0.0 | `{"$float": ...}` |
| `BigDecimal` | `{"$decimal": toString()}` (may use exponent notation, `1E+3`) |
| `byte[]` | `{"$bytes": "<base64>"}` |
| other arrays, `Iterable` | array |
| `Set` | `{"$set": [...]}` sorted by canonical JSON |
| `Map` with string keys | object |
| other `Map` | `{"$map": [...]}`, in order for `LinkedHashMap` and `SortedMap`, sorted by canonical key otherwise |
| `Optional` | the value or `null` |
| enum | `{"$enum": "Type.NAME"}` |
| `java.time` types, `Date` | `{"$datetime": toString()}` |
| record | `{"$type": "Name", ...}` with its components |
| other objects | `{"$type": "Name", ...}` with public fields and `getX()`/`isX()` getters, sorted |
| `char` | string |

## Errors and timeouts

`InvocationTargetException` is unwrapped. The category is the exception's simple name
(`IllegalArgumentException`, `NumberFormatException`) and the message is `getMessage()`, which may be `null`.

Each case runs on a worker thread for `--timeout` seconds (default 10). On timeout the thread is interrupted
and abandoned, and the next case gets a fresh thread; the JVM exits when the driver finishes.

## Limitations

- Instance methods need `init`. Calling a method on an existing singleton is not supported.
- Getters run during serialization, so getters with side effects show up in the result.
- `java.time` `toString()` drops zero seconds (`2024-02-29T10:00Z`), so the same instant can print
  differently from other languages' oracles.
