# Java to Kotlin

| Field | Value |
| --- | --- |
| Source | Java 8 to 21 |
| Target | Kotlin 2.x on the JVM |
| Status | full |
| Last reviewed | 2026-10-20 |

How to use this file: the `strategy` skill loads it to seed the idiom map for a
port, and the `implement` skill reads the sections a unit's risk tags point at.
Every trap carries risk tags from this vocabulary, which `porter.py decompose`
also emits for units:

`regex`, `float-format`, `numeric`, `datetime`, `async`, `reflection`,
`unicode`, `encoding`, `io`, `locale`, `mutability`, `nullability`,
`error-model`, `ordering`.

Java and Kotlin share the JVM, the class library and the exception classes,
so arithmetic, `String`, `java.time`, `java.util.regex` and I/O behave the
same. What changes:

- The API shape Java callers see. Kotlin compiles properties, companion
  objects, default arguments, top-level functions and checked exceptions into
  different JVM signatures than the Java original had. For a library with
  Java consumers, binary and source compatibility of the public API is the
  real contract.
- Nullability. Kotlin inserts runtime null checks at the Java boundary that
  the Java code never had.
- Defaults: classes are `final`, nested classes are static, `mutableMapOf`
  is a `LinkedHashMap`, collection operations are eager, and stdlib string
  functions differ from the `String` methods with similar names.

Decide at the start, and record in the strategy, which of these holds:

1. Java callers must keep compiling and running (library with Java users,
   mixed-language codebase). Keep the Java-facing shape with `@JvmStatic`,
   `@JvmOverloads`, `@JvmField`, `@JvmName`, `@Throws` and `@JvmRecord`, and
   diff the public ABI before and after with the Kotlin
   binary-compatibility-validator Gradle plugin or japicmp.
2. Only Kotlin callers remain. Idiomatic Kotlin API is fine, and the change
   is recorded in the contract.

Port class by class inside the same module: Kotlin and Java compile together,
so the existing tests keep running throughout.

## 1. Type system mapping

| Java | Kotlin | Notes |
| --- | --- | --- |
| `int`, `long`, `short`, `byte`, `double`, `float`, `boolean`, `char` | `Int`, `Long`, `Short`, `Byte`, `Double`, `Float`, `Boolean`, `Char` | Primitive on the JVM when non-null and not a type argument. |
| `Integer`, `Long` (boxed) | `Int?`, `Long?` | Boxed. `==` means `equals` (T17). |
| `String` | `String` or `String?` | Section 3 decides which. |
| `Object` | `Any` or `Any?` | `wait`/`notify` need a cast to `java.lang.Object`. |
| `void` | `Unit` | |
| `int[]`, `T[]` | `IntArray`, `Array<T>` | `Array<Int>` is `Integer[]`, not `int[]`. |
| `List<T>`, `Set<T>`, `Map<K, V>` | `List<T>`, `Set<T>`, `Map<K, V>` (read-only views) or the `Mutable` interfaces | Same `java.util` classes at runtime (T15). |
| `List<? extends T>` | `List<out T>`, often plain `List<T>` | Kotlin `List` is already covariant (T36). |
| `List<? super T>` | `MutableList<in T>` | |
| raw types | `List<*>` | |
| `Optional<T>` | `T?` internally; keep `Optional<T>` on Java-facing API | T37. |
| `Function<A, B>`, `Supplier<T>`, `Runnable` | `(A) -> B`, `() -> T`, `() -> Unit` | Keep the Java interfaces in Java-facing signatures; use `fun interface` for Kotlin SAM types. |
| `throws` clauses | `@Throws(...)` | T3. |
| `static` members | top-level declarations, `object`, `companion object` | T4. |
| JavaBean getters and setters | properties | T6. |
| `record` (Java 16) | `@JvmRecord data class` | T10. |
| `enum` | `enum class` | `entries` (Kotlin 1.9+) replaces `values()`, which still exists. |
| `sealed` classes and interfaces (Java 17) | `sealed` classes and interfaces | |
| non-static inner class | `inner class` | Kotlin nested classes are static by default. |
| static nested class | `class` nested | |
| anonymous class | `object : Iface { ... }` or a lambda | T34 for listener identity. |
| unsigned arithmetic helpers (`Integer.toUnsignedLong`) | `UInt`, `ULong` | Keep them out of Java-facing signatures: functions taking inline value classes get mangled JVM names. |

Rules that do not fit the table:

- Keep the JVM signature of every public member that Java code calls. The
  table in section 11 lists the annotation for each Java shape.
- Do not turn a class into a `data class` just because it has fields
  (T8, T9).
- Prefer `val` and read-only collection types internally, but never change
  the runtime collection class handed to Java callers (T12, T15).

## 2. Error model

Same exception classes, no checked exceptions. Every Java `throws` clause on
public API needs `@Throws` (T3).

| Source | Kotlin default | Notes |
| --- | --- | --- |
| `throws IOException` on a public method | `@Throws(IOException::class)` | Needed for Java `catch`, Mockito `thenThrow`, and JDK dynamic proxies. |
| `try (A a = ...; B b = ...) { }` | `a.use { b.use { ... } }` | `use` adds suppressed exceptions like try-with-resources. |
| `Objects.requireNonNull(x, "msg")` | `requireNotNull(x) { "msg" }` | `requireNotNull` throws `IllegalArgumentException`, not `NullPointerException`. Use `x ?: throw NullPointerException("msg")` to keep the type. |
| `Preconditions.checkArgument` (Guava) | `require(cond) { msg }` | Both `IllegalArgumentException`. |
| `Preconditions.checkState` | `check(cond) { msg }` | Both `IllegalStateException`. |
| `list.get(0)` | `list[0]` | `first()` throws a different type (T32). |
| `map.get(k)` | `map[k]` | `getValue(k)` throws `NoSuchElementException`. |
| `throw new UnsupportedOperationException()` | same, or `TODO()` only in unported stubs | `TODO()` throws `NotImplementedError`, an `Error`. |
| `catch (A \| B e)` | `catch (e: Exception) { if (e !is A && e !is B) throw e; ... }` | No multi-catch in Kotlin. |

Exception messages from Kotlin-generated checks differ from Java's. A
non-null parameter that receives `null` throws
`NullPointerException: Parameter specified as non-null is null: method
lib.Svc.take, parameter s` (T2); `!!` throws `NullPointerException` with no
message; Java 14+ helpful NPE messages name the null expression. If fixtures
record exception messages, map them in `.porter/contract/error-map.json`.

## 3. Null and absence

Java types without nullability annotations become platform types (`String!`)
in Kotlin. Kotlin lets you treat them as nullable or non-null, and inserts a
runtime check when you assign one to a non-null type (T1).

Decide nullability per member from, in order: annotations
(`@Nullable`/`@NonNull` from JetBrains, JSpecify, AndroidX, Checker
Framework, JSR-305 with `-Xjsr305=strict`), the contract in
`.porter/contract/api.json`, the Java implementation (does it ever return or
accept `null`?), and the reference tests. When unsure, use the nullable type.

```java
// Java: callers may pass null for suffix; name() may return null.
public String label(String prefix, @Nullable String suffix) {
    String n = repo.name();
    return prefix + n + (suffix == null ? "" : suffix);
}
```

```kotlin
fun label(prefix: String, suffix: String?): String {
    val n: String? = repo.name() // nullable: Java returned null sometimes
    return prefix + n + (suffix ?: "")
}
```

`prefix + n` with a null `n` produces `"null"` in both languages, so the
output matches.

`!!` policy: allow `!!` only where the Java code dereferenced the same value
immediately, so the NPE happens at the same point. Everywhere else, use a
nullable type, `?:` with the source's fallback, or an explicit throw with the
source's exception type.

- `lateinit var` throws `UninitializedPropertyAccessException` when read
  early. A Java field read early is `null` and may never fail. Use a nullable
  property if the source reads fields before initialization.
- `map.getOrDefault(k, d)` returns `null` when the key exists with a `null`
  value; `map[k] ?: d` returns `d`.
- `List.of(...)` (Java 9) rejects `null` elements and throws on
  `contains(null)`; Kotlin `listOf` accepts both.

## 4. Concurrency and async

Keep the concurrency model. Threads, executors, `CompletableFuture`,
`synchronized` and `java.util.concurrent` all work unchanged from Kotlin.
Converting to coroutines changes the public API and threading and is a
contract change, not a port step.

| Java | Kotlin |
| --- | --- |
| `synchronized` method | `@Synchronized fun` |
| `synchronized (lock) { }` | `synchronized(lock) { }` (stdlib function) |
| `volatile` field | `@Volatile var` |
| `transient` field | `@Transient` |
| `lock.wait()`, `lock.notifyAll()` | `(lock as java.lang.Object).wait()`, or switch to `ReentrantLock` and `Condition` |
| `new Thread(r).start()` | `thread { ... }` starts immediately; `Thread(r).start()` keeps the Java form |
| `ExecutorService`, `CompletableFuture` | unchanged |
| virtual threads (Java 21) | unchanged |

If a coroutine API is wanted in addition to the blocking one:

- `suspend` functions are hard to call from Java (they take a
  `Continuation`). Keep the blocking or `CompletableFuture` signature for
  Java callers and add the `suspend` variant beside it. `future { }` from
  kotlinx-coroutines bridges a coroutine to a `CompletableFuture`.
- Avoid `runBlocking` inside library code that may run on a coroutine
  dispatcher thread; it blocks that thread.
- `ThreadLocal` values do not follow a coroutine to another thread (T38).
  Use `threadLocal.asContextElement(value)`, or MDC's `MDCContext`.
- A `synchronized` block cannot contain a suspension point. Use `Mutex`.
- RxJava at a public boundary stays RxJava. kotlinx-coroutines-rx3 converts
  between `Flow` and `Observable` internally.

## 5. Iteration, generators, laziness

Kotlin collection operations are eager and allocate a new collection per
step. Java streams are lazy and process elements one at a time through the
whole pipeline. Use `asSequence()` when the stream short-circuits, has side
effects in lambdas, or is large (T14).

```java
Optional<User> first = users.stream()
    .peek(u -> log.debug("checking {}", u.id()))
    .filter(User::active)
    .findFirst();
```

```kotlin
// Lazy like the stream: logs only until the first active user.
val first: User? = users.asSequence()
    .onEach { log.debug("checking {}", it.id) }
    .firstOrNull { it.active }
```

| Java stream | Kotlin | Notes |
| --- | --- | --- |
| `.map(f).collect(Collectors.toList())` | `.map(f)` | Result is an `ArrayList` in both. |
| `.toList()` (Java 16) | `.map(f)` plus a read-only wrapper if Java callers get it | `Stream.toList()` is unmodifiable (T15). |
| `.filter(p).findFirst()` | `.firstOrNull(p)` | Java returns `Optional`. |
| `.anyMatch`, `.allMatch`, `.noneMatch` | `any`, `all`, `none` | |
| `Collectors.toMap(k, v)` | `associate { k to v }`, `associateBy` | Duplicate keys (T13) and map class (T12). |
| `Collectors.groupingBy(f)` | `groupBy(f)` | `HashMap` versus `LinkedHashMap` (T12). |
| `Collectors.toSet()` | `toSet()` | `HashSet` versus `LinkedHashSet` (T12). |
| `Collectors.joining(", ")` | `joinToString(", ")` | |
| `.sorted(cmp)` | `sortedWith(cmp)` | Both stable. |
| `.reduce(identity, op)` | `fold(identity, op)` | `reduce` without identity: Java returns an empty `Optional`; Kotlin `reduce` throws `UnsupportedOperationException` on an empty collection. |
| `.count()` | `count()` or `size` | Java returns `long`, Kotlin `Int`. |
| `.limit(n)`, `.skip(n)` | `take(n)`, `drop(n)` | |
| `.peek(f)` | `onEach(f)` | Lazy only on a sequence. |
| `IntStream.range(0, n)` | `0 until n` or `0..<n` | |
| `Stream.iterate`, `Stream.generate` | `generateSequence` | |
| `.parallel()` | keep the Java stream | Do not drop parallelism silently. |

- `for (Map.Entry<K, V> e : map.entrySet())` becomes `for ((k, v) in map)`.
- Iterator removal (`it.remove()`) works the same with `iterator()` and
  `MutableIterator`.
- `sequence { yield(x) }` replaces hand-written `Iterator` classes.

## 6. Numeric semantics

Arithmetic is the JVM's in both languages: 32-bit `Int` and 64-bit `Long`
wrap on overflow, integer division truncates toward zero, `%` takes the sign
of the dividend, and division by zero throws `ArithmeticException` for
integers. What differs is conversion and operator spelling.

- No implicit widening. `long x = a * b` with `int` operands overflows in
  Java before widening; the Kotlin equivalent of that exact behavior is
  `(a * b).toLong()`, and the "natural" `a.toLong() * b` does not overflow
  (T19).
- Hex literals that do not fit in `Int` are `Long` in Kotlin:
  `0xFFFFFFFF` is `-1` in Java and `4294967295L` in Kotlin (T20).
- `%` is `rem`; `mod` is floor modulo, like `Math.floorMod` (T21).
- `BigDecimal` operators: `a / b` calls `divide(b, RoundingMode.HALF_EVEN)`
  and keeps `a`'s scale (T22). `==` calls `equals`, which is
  scale-sensitive (`1.0` is not equal to `1.00`); `<` and `>` call
  `compareTo`.
- Double equality depends on the static type: IEEE for `Double`, `equals`
  for `Double?`, `Any` and generics (T18).
- `Char` is not a number: `'a' + 1` is `'b'`, `'a'.code` is `97`,
  `c - '0'` is an `Int` (T23).

| Java | Kotlin |
| --- | --- |
| `a & b`, `a \| b`, `a ^ b`, `~a` | `a and b`, `a or b`, `a xor b`, `a.inv()` |
| `a << n`, `a >> n`, `a >>> n` | `a shl n`, `a shr n`, `a ushr n` |
| `b & 0xFF` with `byte b` | `b.toInt() and 0xFF` |
| `(int) d` | `d.toInt()` (truncates; `NaN` gives 0; saturates at the `Int` bounds, like Java) |
| `(byte) i` | `i.toByte()` |
| `Integer.MAX_VALUE` | `Int.MAX_VALUE` |
| `Math.floorMod(a, b)` | `a.mod(b)` |
| `Integer.parseInt(s)` | `s.toInt()` (same `NumberFormatException`) |
| `Double.compare(a, b)` | `a.compareTo(b)` |

## 7. Strings, bytes, unicode, encodings

Same `java.lang.String` (UTF-16). Kotlin stdlib functions with familiar names
sometimes behave differently from the `String` methods:

| Java | Kotlin with the same behavior | Kotlin look-alike that differs |
| --- | --- | --- |
| `s.split(",")` (regex, drops trailing empties) | `s.split(Regex(","))` then `.dropLastWhile { it.isEmpty() }` | `s.split(",")` (literal, keeps trailing empties) (T24) |
| `s.replaceAll(regex, repl)` | `s.replace(Regex(regex), repl)` | `s.replace(regex, repl)` with a `String` (literal) (T25) |
| `s.trim()` (chars up to U+0020) | `s.trim { it <= ' ' }` | `s.trim()` (Unicode whitespace) (T27) |
| `s.isBlank()` (Java 11) | `s.all { Character.isWhitespace(it) }` | `s.isBlank()` (also counts U+00A0 and other space separators) (T27) |
| `s.toUpperCase()` (default locale) | `s.uppercase(Locale.getDefault())` | `s.uppercase()` (invariant locale) (T28) |
| `s.getBytes()` (default charset) | `s.toByteArray(Charset.defaultCharset())` | `s.toByteArray()` (UTF-8) (T29) |
| `new String(bytes)` | `String(bytes, Charset.defaultCharset())` | `String(bytes)` (UTF-8) (T29) |
| `String.valueOf(chars)` | `String(chars)` or `chars.concatToString()` | `"$chars"`, `chars.toString()` (T30) |
| `s.equalsIgnoreCase(t)` | `s.equals(t, ignoreCase = true)` | |
| `String.join(",", xs)` | `xs.joinToString(",")` | |
| `String.format(fmt, args)` | `fmt.format(*args)` | Both use the default locale. |
| `s.matches(regex)` | `s.matches(Regex(regex))` | Both match the whole string. |

- String templates (`"$x"`) call `toString()`, like Java concatenation.
  `null` becomes `"null"` in both.
- Raw strings (`"""..."""`) avoid regex double escaping, but `$` must be
  written `${'$'}`.
- `String.format` and `"...".format()` use `Locale.getDefault(FORMAT)`:
  `"%.2f".format(1.5)` is `"1,50"` under a German default locale. Pin the
  locale in fixtures or pass `Locale.ROOT` where the source should have.
- Since JDK 18 the default charset is UTF-8 everywhere. Java 8 to 17 sources
  running on Windows used the system code page, so T29 matters most for
  ports of older code.

## 8. Dates, times, timezones

`java.time` works unchanged from Kotlin; keep it. Port `java.util.Date`,
`Calendar` and `SimpleDateFormat` as they are unless the contract allows a
change, and note that `SimpleDateFormat` is not thread-safe (a shared
instance in a `companion object` is a bug in both languages).

- Joda-Time to `java.time`: `DateTime` maps to `ZonedDateTime` (it carries a
  zone), `LocalDate` to `LocalDate`, `Instant` to `Instant`, `Period` and
  `Duration` to their namesakes. Pattern letters differ: Joda `Y` is year of
  era and `x` is week year; in `java.time`, `Y` is week-based year (T43).
- `DateTimeFormatter.ofPattern` without a locale uses the default locale for
  week fields and text. Pass `Locale.ROOT` or the locale the source used.
- With `ResolverStyle.STRICT`, `yyyy` is year of era and needs an era; use
  `uuuu`.
- kotlinx-datetime is for multiplatform code. On the JVM, staying on
  `java.time` avoids a conversion layer.

## 9. Regex dialect

Same engine (`java.util.regex`). `Regex` wraps `Pattern`.

| Java | Kotlin | Notes |
| --- | --- | --- |
| `Pattern.compile(p)` | `Regex(p)` or `p.toRegex()` | `regex.toPattern()` gives the `Pattern` back. |
| `Pattern.CASE_INSENSITIVE` | `RegexOption.IGNORE_CASE` | Kotlin also sets `UNICODE_CASE` (T26). |
| `Pattern.MULTILINE`, `DOTALL`, `COMMENTS`, `LITERAL` | `MULTILINE`, `DOT_MATCHES_ALL`, `COMMENTS`, `LITERAL` | |
| `m.find()` loop | `regex.findAll(s)` | Lazy sequence of `MatchResult`. |
| `m.matches()` | `regex.matches(s)` or `regex.matchEntire(s)` | |
| `m.lookingAt()` | `regex.matchAt(s, 0)` | |
| `m.group(1)` | `match.groupValues[1]` (empty string if unmatched) or `match.groups[1]?.value` (null if unmatched) | Java `group(1)` returns `null` when unmatched. |
| `s.replaceAll(p, r)` | `s.replace(Regex(p), r)` | `$1` and `\` in `r` are special in both; `Regex.escapeReplacement` quotes them. |
| `s.replaceFirst(p, r)` | `s.replaceFirst(Regex(p), r)` | |
| `Pattern.quote(s)` | `Regex.escape(s)` | |

## 10. I/O, paths, process, environment

`java.io`, `java.nio.file`, `ProcessBuilder`, `System.getenv` and
`System.getProperty` work unchanged. The Kotlin extensions are convenient
but default to UTF-8 (T29):

| Java | Kotlin extension | Charset |
| --- | --- | --- |
| `Files.readString(p)` (UTF-8) | `p.readText()` | UTF-8 in both |
| `new String(Files.readAllBytes(p))` | `p.readText()` | Java: default charset; Kotlin: UTF-8 |
| `new FileReader(f)` | `f.reader()`, `f.bufferedReader()` | Java: default charset; Kotlin: UTF-8 |
| `Files.lines(p)` | `p.useLines { ... }` | UTF-8 in both; `useLines` closes the file |
| `Files.walk(p)` | `p.walk()` (`kotlin.io.path`, opt-in on older Kotlin versions) or `f.walkTopDown()` | Iteration order follows the file system in both |

- `use { }` replaces try-with-resources and closes on exceptions.
- `println` is `System.out.println`.
- `System.exit` stays `exitProcess(code)` (returns `Nothing`, which helps
  flow analysis).

## 11. Module layout, packaging, naming, visibility

- Packages and directories stay the same. Kotlin allows several classes per
  file; keep one public class per file in ports to keep diffs reviewable.
- Top-level functions in `Utils.kt` compile to a class `UtilsKt`. Use
  `@file:JvmName("Utils")` to keep a Java class name.
- Visibility: Kotlin has no package-private. `internal` (module-wide) is the
  closest; it compiles to `public` in bytecode, with mangled names for
  functions. Kotlin `protected` does not include same-package access as Java
  `protected` does.
- Classes and members are `final` by default. Add `open` where Java code
  subclasses or overrides them, and use the all-open plugin for frameworks
  (T35).
- For libraries, enable explicit API mode (`kotlin { explicitApi() }`) so
  every public declaration states its visibility and type.

Java-facing API checklist:

| Java shape to keep | Kotlin |
| --- | --- |
| `public static` method | `@JvmStatic` in an `object` or `companion object`, or a top-level function with `@file:JvmName` |
| `public static final` constant (primitive or `String`) | `const val` |
| `public static final` field of another type | `@JvmField val` in a companion or object |
| overloads that drop trailing parameters | default arguments plus `@JvmOverloads` |
| other overload sets | separate functions |
| `getURL()` and other non-standard getter names | `@get:JvmName("getURL") val url` |
| `isActive()` boolean getter | property named `isActive` (T6) |
| `throws` clause | `@Throws` |
| record accessors `x()` | `@JvmRecord data class` |
| interface `default` methods for Java implementers | Kotlin 2.2+, or `-Xjvm-default=all` on older 2.x (T7) |
| `Foo.Companion.bar()` is acceptable | no annotation needed |

```java
public final class Units {
    public static final String DEFAULT_UNIT = "m";
    private Units() {}
    public static double convert(double v, String from) throws IOException { /* ... */ }
    public static double convert(double v) throws IOException { return convert(v, DEFAULT_UNIT); }
}
```

```kotlin
object Units {
    const val DEFAULT_UNIT = "m"

    @JvmStatic
    @JvmOverloads
    @Throws(IOException::class)
    fun convert(v: Double, from: String = DEFAULT_UNIT): Double { /* ... */ }
}
```

Java callers keep `Units.convert(1.0)`, `Units.convert(1.0, "ft")` and
`Units.DEFAULT_UNIT`. The object also gains a public `Units.INSTANCE` field,
which is an addition, not a break.

Build: apply the Kotlin Gradle or Maven plugin to the existing module, set
`jvmToolchain` to the source's Java version, and add the compiler plugins the
frameworks need (`kotlin("plugin.spring")`, `kotlin("plugin.jpa")`,
`kotlin("plugin.serialization")`). Add `-Xjsr305=strict` when dependencies
use JSR-305 annotations.

## 12. Standard library equivalence

| Source | Target | Notes |
| --- | --- | --- |
| `Objects.equals(a, b)` | `a == b` | |
| `Objects.hash(a, b)` | keep `Objects.hash(a, b)` in hand-written `hashCode` | Data class hash values differ (T9). |
| `Objects.requireNonNull(x)` | `x ?: throw NullPointerException()` or `requireNotNull(x)` | Exception type differs (section 2). |
| `Collections.unmodifiableList(l)` | `Collections.unmodifiableList(l)` | `toList()` copies and returns a mutable `ArrayList` at runtime (T15). |
| `Arrays.asList(a, b)` | `listOf(a, b)` | Same runtime class (`Arrays$ArrayList`). |
| `List.of(a, b)` | `listOf(a, b)` | `List.of` rejects nulls (section 3). |
| `new ArrayList<>()` | `ArrayList()` or `mutableListOf()` | Both `ArrayList`. |
| `new HashMap<>()` | `HashMap()` or `hashMapOf()` | Not `mutableMapOf()` (T12). |
| `new HashSet<>()` | `HashSet()` or `hashSetOf()` | Not `mutableSetOf()` (T12). |
| `Collections.sort(l)` | `l.sort()` | `sorted()` returns a copy. |
| `Arrays.equals`, `Arrays.hashCode`, `Arrays.toString` | `contentEquals`, `contentHashCode`, `contentToString` | `==` on arrays is identity in both. |
| `Arrays.fill`, `Arrays.copyOf` | `fill`, `copyOf` | |
| `Math.max(a, b)` | `maxOf(a, b)` | |
| `Character.isDigit(c)`, `Character.isLetter(c)` | `c.isDigit()`, `c.isLetter()` | Same implementation. |
| `Character.isWhitespace(c)` | `Character.isWhitespace(c)` | `c.isWhitespace()` also accepts space separators like U+00A0 (T27). |
| `instanceof` plus cast | `is` with smart cast | |
| ternary `c ? a : b` | `if (c) a else b` | |
| `switch` | `when` | No fall-through; null handling differs (T31). |
| `x != null ? x : d` | `x ?: d` | |
| `Optional.ofNullable(x).map(f).orElse(d)` | `x?.let(f) ?: d` | Same result when `f` returns `null`. |
| `String.valueOf(chars)` | `String(chars)` | T30. |
| `Thread.sleep(ms)` | `Thread.sleep(ms)` | `delay` only inside coroutines. |
| `System.out.println` | `println` | |
| `Math.floorMod` | `mod` | T21. |

## 13. Common dependency equivalence

Seed candidates only. The `scout` agent must confirm every one with
`porter.py registry lookup` before it is used in `deps.json`.

| Source package | Used for | Target candidates | Decision hint | Notes |
| --- | --- | --- | --- | --- |
| Guava | collections, caches, strings, preconditions, hashing | Kotlin stdlib; Caffeine for caches | keep for caches, hashing, `Immutable*` collections, `RateLimiter`; replace small helpers | `ImmutableList` rejects nulls and is truly immutable; `listOf` is neither. |
| Apache Commons Lang 3 | string and object helpers | Kotlin stdlib | replace simple helpers | `StringUtils.isBlank` uses `Character.isWhitespace` (no U+00A0), unlike Kotlin `isBlank` (T27). `StringUtils.split` treats adjacent separators as one; Kotlin `split` does not. |
| Apache Commons IO | file and stream helpers | `java.nio.file.Files`, kotlin.io extensions | replace | Charset defaults (T29). |
| Apache Commons Collections | collection utilities | Kotlin stdlib | replace | |
| Apache Commons CSV | CSV | keep; kotlin-csv | keep | |
| Jackson (databind) | JSON | keep with jackson-module-kotlin; kotlinx.serialization | keep, add the Kotlin module | T40, T41. |
| Gson | JSON | Jackson with the Kotlin module, kotlinx.serialization, Moshi with Kotlin codegen | replace for classes that become Kotlin | Gson ignores Kotlin nullability and defaults (T39). |
| Lombok | boilerplate | Kotlin properties, data classes, default and named arguments | drop (delombok first) | Kotlin cannot see Lombok-generated members of Java classes in the same module unless the experimental kotlin-lombok plugin is on. `@Data` equality differs from data classes (T11). |
| SLF4J, Logback | logging | keep; kotlin-logging (`io.github.oshai:kotlin-logging-jvm`) | keep | |
| JUnit 4 | tests | JUnit 5 (vintage engine during migration), Kotest | migrate or keep | |
| JUnit 5 | tests | keep; Kotest | keep | `@BeforeAll` needs `@JvmStatic` in a companion, or `@TestInstance(PER_CLASS)`. |
| Mockito | mocking | keep with mockito-kotlin; MockK | keep or replace | Mockito 5 mocks final classes by default. Mockito's `any()` returns `null`, which fails Kotlin non-null parameters; mockito-kotlin's `any()` does not. |
| AssertJ | assertions | keep; Kotest assertions, Strikt, kotlin.test | keep | |
| Hamcrest | matchers | keep; Kotest matchers | keep | `is` is a Kotlin keyword: write `` `is`(x) `` or use `equalTo`. |
| OkHttp | HTTP client | keep (OkHttp 4+ is written in Kotlin); Ktor client | keep | |
| Retrofit | HTTP API client | keep (supports `suspend` since 2.6.0); Ktor client | keep | |
| Apache HttpClient | HTTP client | keep; OkHttp; Ktor client | keep | |
| RxJava | reactive streams | keep; kotlinx.coroutines `Flow` with kotlinx-coroutines-rx3 | keep at public boundaries | Switching to `Flow` is a contract change. |
| Joda-Time | dates | `java.time`; kotlinx-datetime for multiplatform | replace | T43. |
| Spring Framework and Boot | DI, web, data | keep | keep | Add kotlin-spring (all-open), jackson-module-kotlin and `-Xjsr305=strict` (T35). |
| Hibernate, JPA | ORM | keep | keep | Add kotlin-jpa (no-arg) and all-open for entities. Avoid data classes for entities: generated `equals`/`hashCode` touch lazy and mutable fields. |
| Dagger | compile-time DI | keep with kapt or KSP (Dagger 2.48+) | keep | Add `@JvmSuppressWildcards` on injected collections of Kotlin types (T36). |
| Guice | runtime DI | keep; Koin as a Kotlin-native alternative | keep | Same wildcard issue for multibindings (T36). |
| Protobuf (protobuf-java) | serialization | keep, optionally add protobuf-kotlin DSL (`--kotlin_out`); Wire | keep | Generated Java builders work from Kotlin. |
| picocli, JCommander | CLI parsing | keep picocli; Clikt | keep | Annotated option fields need `lateinit var` or default values. |
| AutoValue, Immutables | value classes | data classes | replace | Check `equals`, `hashCode` and `toString` formats (T8, T9). |
| Vavr | functional types | Kotlin stdlib, Arrow | replace | |
| Caffeine | caching | keep | keep | |
| java.util.concurrent | concurrency | keep; kotlinx.coroutines | keep | Section 4. |

## 14. Test framework and tooling

| Concern | Source | Target |
| --- | --- | --- |
| Test runner | JUnit 4, JUnit 5, TestNG | JUnit 5 (keep), or Kotest |
| Assertions and fixtures | AssertJ, Hamcrest, Mockito, PowerMock | AssertJ or kotlin.test, Kotest assertions, Strikt; mockito-kotlin or MockK |
| Lint | Checkstyle, PMD, SpotBugs, Error Prone, NullAway | detekt, compiler warnings as errors |
| Format | google-java-format, Spotless | ktlint or ktfmt through Spotless |
| Type check | javac | kotlinc with `allWarningsAsErrors` and `-Xjsr305=strict` |
| Coverage | JaCoCo | JaCoCo (filters some Kotlin-generated code), or Kover |

- Keep the Java test suite running against the Kotlin classes during the
  port. It is the cheapest check of Java-facing compatibility.
- Add an ABI check (binary-compatibility-validator or japicmp) for libraries
  in mode 1 (see the top of this file).
- Backtick test names (`` fun `parses empty input`() ``) are fine in Kotlin
  tests; keep the Java method names if reports are compared.

## 15. Known traps

### T1. Platform types fail at assignment

- Tags: `nullability`
- Source behavior: Java passes a `null` return value along until something dereferences it, which may be never.
- Target behavior: assigning a platform-type value to a non-null Kotlin type inserts a check that throws immediately.
- Detect: with `J.name()` returning `null`, Java `String s = J.name(); return "x" + s;` returns `"xnull"`; Kotlin `val s: String = J.name()` throws `NullPointerException: name(...) must not be null`.
- Port rule: use the nullable type for every Java call result unless an annotation, the contract or the implementation proves non-null.

### T2. Non-null parameters reject `null` from Java callers

- Tags: `nullability`, `error-model`
- Source behavior: a Java method accepts `null` for any reference parameter and decides what to do with it.
- Target behavior: a non-null Kotlin parameter checks on entry and throws.
- Detect: Java caller `svc.take(null)` reaches the method body in the Java original; against Kotlin `fun take(s: String)` it throws `NullPointerException: Parameter specified as non-null is null: method lib.Svc.take, parameter s`.
- Port rule: make parameters nullable wherever Java callers can pass `null` (look for null checks in the Java body, `@Nullable`, and reference tests passing `null`).

### T3. Checked exceptions need `@Throws`

- Tags: `error-model`
- Source behavior: `throws IOException` lets Java callers catch it and lets Mockito stub it.
- Target behavior: without `@Throws`, the JVM method declares no exceptions. Java `catch (IOException e)` around the call stops compiling, and Mockito rejects `thenThrow(IOException())` with "Checked exception is invalid for this method!".
- Detect: Java `try { new Svc().read(); } catch (java.io.IOException e) {}` compiles against the Java class; against Kotlin `fun read()` javac reports `exception IOException is never thrown in body of corresponding try statement`.
- Port rule: copy every `throws` clause of a public or protected member into `@Throws(...)`.

### T4. Statics need `@JvmStatic`, `const` or `@JvmField`

- Tags: `reflection`
- Source behavior: Java callers write `Svc.create()` and `Svc.VERSION`.
- Target behavior: companion members compile to instance members of `Svc.Companion` plus accessor methods.
- Detect: Java `Svc.create()` compiles against the Java class; against a Kotlin companion `fun create()` javac reports `cannot find symbol`.
- Port rule: annotate Java-called companion functions with `@JvmStatic`; use `const val` for primitive and `String` constants and `@JvmField` for other static fields.

### T5. Overloads collapse into default arguments

- Tags: `reflection`
- Source behavior: Java declares `Client(String host)` and `Client(String host, int port)`.
- Target behavior: `class Client(val host: String, val port: Int = 80)` produces one JVM constructor with both parameters (plus a synthetic one), so Java callers lose the short form and already-compiled callers fail with `NoSuchMethodError`.
- Detect: Java `new Client("h")` compiles against the Java class; against the Kotlin class without `@JvmOverloads` javac reports `constructor Client in class Client cannot be applied to given types`.
- Port rule: add `@JvmOverloads` (on the constructor: `class Client @JvmOverloads constructor(...)`) when the Java overloads drop trailing parameters; otherwise declare each overload explicitly.

### T6. Property names decide getter names

- Tags: `reflection`
- Source behavior: Java exposes `isActive()` for a boolean and `getURL()` for a URL.
- Target behavior: `var active: Boolean` compiles to `getActive()`/`setActive()`, and `val url` to `getUrl()`. Only a property named `isActive` keeps `isActive()`.
- Detect: Java `bean.isActive()` compiles against the Java bean; against Kotlin `var active: Boolean` javac reports `cannot find symbol` (the method is `getActive()`).
- Port rule: name boolean properties `isX` when the Java getter was `isX()`, and use `@get:JvmName` / `@set:JvmName` for any other getter or setter name. Check serializers too (T41).

### T7. Interface default methods before Kotlin 2.2

- Tags: `reflection`
- Source behavior: a Java interface with a `default` method can be implemented by Java classes that do not override it.
- Target behavior: before Kotlin 2.2, a Kotlin interface method with a body compiled to an abstract JVM method plus a `DefaultImpls` class unless `-Xjvm-default=all` was set. Kotlin 2.2 emits JVM default methods by default.
- Detect: Java `class Impl implements Shape { public double area() { return 1.0; } }` compiles against a Kotlin `interface Shape { fun area(): Double; fun describe() = "shape" }` built with Kotlin 2.2.20, and fails with Kotlin 2.1.21 defaults: `Impl is not abstract and does not override abstract method describe() in Shape`.
- Port rule: on Kotlin 2.x before 2.2, compile with `-Xjvm-default=all` (or `all-compatibility` when old Kotlin clients exist); on 2.2+ keep the default.

### T8. `data class` changes equality, `toString` and the API

- Tags: `reflection`, `mutability`
- Source behavior: a Java class without `equals` uses identity, and `toString` prints `Point@1b6d3586`.
- Target behavior: a data class compares the primary constructor properties, prints `Point(x=1, y=2)`, and adds public `copy` and `componentN` functions whose signatures change whenever a property is added.
- Detect: `setOf(Point(1, 2), Point(1, 2)).size` is `2` for the Java class without `equals` and `1` for the data class.
- Port rule: use a data class only where the Java class already had value equality on the same fields, and check `toString` output in fixtures. Otherwise write a plain class with the same `equals`, `hashCode` and `toString`.

### T9. `data class` hashCode differs from `Objects.hash`

- Tags: `ordering`
- Source behavior: Java value classes usually implement `hashCode` with `Objects.hash(x, y)`, which starts from 1.
- Target behavior: data class `hashCode` starts from the first property's hash, so values differ, and so does iteration order of `HashMap` and `HashSet` keyed by the class.
- Detect: `Objects.hash(1, 2)` is `994`; `Point(1, 2).hashCode()` for `data class Point(val x: Int, val y: Int)` is `33`.
- Port rule: when hash values or hash-ordered iteration are observable, override `hashCode` with the Java formula.

### T10. Records versus data classes

- Tags: `reflection`
- Source behavior: a Java record has accessors `x()` and prints `Point[x=1, y=2]`.
- Target behavior: a data class has getters `getX()`; `@JvmRecord` restores `x()` and compiles to a real record, but `toString` still prints `Point(x=1, y=2)`.
- Detect: `new Point(1, 2).toString()` is `Point[x=1, y=2]` for the record and `Point(x=1, y=2)` for `@JvmRecord data class Point`.
- Port rule: use `@JvmRecord data class` for records Java code calls, and override `toString` when its output is observable.

### T11. Lombok `@Data` compares arrays by content

- Tags: `reflection`
- Source behavior: Lombok's generated `equals` and `hashCode` use `Arrays.equals` and `Arrays.deepEquals` for array fields, and include every non-static, non-transient field.
- Target behavior: data class `equals` compares array properties by identity and includes only primary constructor properties.
- Detect: two instances holding equal but distinct `byte[]` arrays are equal under Lombok `@Data` and not equal as a data class.
- Port rule: delombok first to see the generated code, then port that `equals`/`hashCode` by hand (`contentEquals`, `contentHashCode`) where arrays or body fields are involved.

### T12. Linked maps and sets by default

- Tags: `ordering`
- Source behavior: `new HashMap<>()`, `new HashSet<>()`, `Collectors.groupingBy` and `Collectors.toSet()` iterate in hash order.
- Target behavior: `mutableMapOf`, `mutableSetOf`, `groupBy`, `associate` and `toSet` create `LinkedHashMap`/`LinkedHashSet`, which iterate in insertion order.
- Detect: inserting `"b"` then `"a"` gives keys `[a, b]` from `HashMap` and `[b, a]` from `mutableMapOf()`.
- Port rule: use `HashMap()`/`hashMapOf()` and `HashSet()`/`hashSetOf()` where the Java code used hash collections and iteration order is observable.

### T13. `associate` keeps the last duplicate

- Tags: `error-model`
- Source behavior: `Collectors.toMap(k, v)` throws `IllegalStateException: Duplicate key` when two elements map to the same key.
- Target behavior: `associate`, `associateBy` and `toMap` keep the last value silently.
- Detect: collecting `["a", "a"]` with `toMap(s -> s, s -> 1)` throws `IllegalStateException: Duplicate key a (attempted merging values 1 and 1)`; `listOf("a" to 1, "a" to 2).associate { it }` returns `{a=2}`.
- Port rule: port `toMap` without a merge function as a loop that throws on duplicates; with a merge function, use `groupingBy { }.reduce { }` or an explicit loop.

### T14. Eager collection operations versus lazy streams

- Tags: `ordering`
- Source behavior: a stream pipeline processes one element at a time and stops at short-circuiting terminals like `findFirst`.
- Target behavior: `list.map { }.first()` maps every element before taking the first.
- Detect: `Stream.of(1, 2, 3).map(x -> { log.add(x); return x; }).findFirst()` logs `[1]`; `listOf(1, 2, 3).map { log.add(it); it }.first()` logs `[1, 2, 3]`.
- Port rule: use `asSequence()` for pipelines with side effects, short-circuiting terminals, or large inputs.

### T15. A read-only `List` is not unmodifiable

- Tags: `mutability`
- Source behavior: Java returns `Collections.unmodifiableList(items)` or `stream.toList()`, so callers that try to modify it get `UnsupportedOperationException`.
- Target behavior: a Kotlin `List<T>` return type is only a compile-time view. Java callers, and Kotlin code that casts, can modify the underlying `ArrayList`.
- Detect: a Java caller doing `k.getItems().add("x")` gets `UnsupportedOperationException` from the Java original; with Kotlin `val items: List<String> get() = _items` (backed by `ArrayList`) the add succeeds and changes internal state.
- Port rule: keep `Collections.unmodifiableList` (or return a copy) wherever the Java code protected internal collections.

### T16. `MutableList<Int>.remove(1)` removes the element

- Tags: `mutability`
- Source behavior: Java `List<Integer>.remove(1)` resolves to `remove(int index)`.
- Target behavior: Kotlin `remove(1)` on `MutableList<Int>` calls `remove(element)`; the index form is `removeAt`.
- Detect: on `[1, 2, 3]`, Java `remove(1)` leaves `[1, 3]`; Kotlin `remove(1)` leaves `[2, 3]`.
- Port rule: port index removal as `removeAt(i)` and element removal of an `Integer` as `remove(element)`.

### T17. `==` calls `equals`

- Tags: `numeric`
- Source behavior: Java `==` on `Integer` objects compares references; it happens to work for values from -128 to 127 because of the box cache.
- Target behavior: Kotlin `==` calls `equals`; `===` compares references.
- Detect: `Integer a = 1000, b = 1000; a == b` is `false` in Java; `val a: Int? = 1000; val b: Int? = 1000; a == b` is `true` in Kotlin.
- Port rule: where the Java code compared boxed values or other objects by reference, decide whether that was intended (identity maps, sentinels) and use `===` there; record any bug fix as a divergence.

### T18. Floating-point equality depends on the static type

- Tags: `numeric`
- Source behavior: Java `double` comparisons are IEEE: `NaN == NaN` is false and `0.0 == -0.0` is true.
- Target behavior: Kotlin uses IEEE only when both sides are statically `Double`/`Float`; for `Double?`, `Any` and generic `T` it calls `equals`, where `NaN` equals `NaN` and `0.0` differs from `-0.0`.
- Detect: `Double.NaN == Double.NaN` is `false`; `val a: Any = Double.NaN; a == Double.NaN` is `true`.
- Port rule: keep primitive comparisons on non-null `Double` types, or compare explicitly with `a.compareTo(b)` / `isNaN()` when values pass through generic or nullable code.

### T19. No implicit widening: `(a * b).toLong()`

- Tags: `numeric`
- Source behavior: `long p = a * b` with `int` operands multiplies in 32 bits, overflows, then widens.
- Target behavior: Kotlin rejects the assignment; the natural fix `a.toLong() * b` multiplies in 64 bits.
- Detect: with `a = b = 100000`, Java `long p = a * b` gives `1410065408`; Kotlin `a.toLong() * b` gives `10000000000`.
- Port rule: port the conversion where Java performed it: `(a * b).toLong()` to keep the overflow, and record a divergence if the overflow was a bug being fixed.

### T20. Hex literals above `Int` range are `Long`

- Tags: `numeric`
- Source behavior: `0xFFFFFFFF` is an `int` literal with value `-1`.
- Target behavior: Kotlin types it as `Long` with value `4294967295`.
- Detect: `System.out.println(0xFFFFFFFF)` prints `-1`; `println(0xFFFFFFFF)` prints `4294967295`.
- Port rule: write `0xFFFFFFFF.toInt()` or `-1` for int masks, and check every hex literal with the high bit set (`0x80000000`, `0xFF000000`).

### T21. `%` versus `mod`

- Tags: `numeric`
- Source behavior: Java `%` is a truncated remainder: `-7 % 3` is `-1`.
- Target behavior: Kotlin `%` is the same, but `mod` (suggested by IDE inspections and by readers expecting math modulo) is floor modulo.
- Detect: `-7 % 3` is `-1`; `(-7).mod(3)` is `2`.
- Port rule: port `%` as `%` and `Math.floorMod` as `mod`. Never swap one for the other.

### T22. `BigDecimal` `/` rounds to the dividend's scale

- Tags: `numeric`
- Source behavior: `a.divide(b)` returns the exact quotient or throws `ArithmeticException` for a non-terminating expansion.
- Target behavior: Kotlin's `a / b` operator calls `divide(b, RoundingMode.HALF_EVEN)`, keeping `a`'s scale.
- Detect: `new BigDecimal("10").divide(new BigDecimal("4"))` is `2.5`; `BigDecimal("10") / BigDecimal("4")` is `2`. `1 / 3` throws in Java and gives `0` in Kotlin.
- Port rule: port `divide` calls as method calls with the same arguments; do not use the `/` operator on `BigDecimal`.

### T23. `Char` arithmetic

- Tags: `numeric`, `unicode`
- Source behavior: `char + int` is an `int` in Java.
- Target behavior: `Char + Int` is a `Char` in Kotlin; the code point is `.code`.
- Detect: `System.out.println('a' + 1)` prints `98`; `println('a' + 1)` prints `b`.
- Port rule: port `c + n` used as a number to `c.code + n`, and as a character to `c + n`. `(char) i` becomes `i.toChar()`.

### T24. `split` treats the delimiter literally and keeps trailing empties

- Tags: `regex`
- Source behavior: Java `String.split` takes a regex and drops trailing empty strings.
- Target behavior: Kotlin `split(String)` splits on the literal text and keeps every empty string.
- Detect: `"a.b".split(".")` is `[]` in Java and `["a", "b"]` in Kotlin; `"a,b,,".split(",")` is `["a", "b"]` in Java and `["a", "b", "", ""]` in Kotlin.
- Port rule: port `s.split(re)` as `s.split(Regex(re)).dropLastWhile { it.isEmpty() }`, and `split(re, limit)` with the Java limit semantics checked by a fixture.

### T25. `replace` is literal; `replaceAll` was a regex

- Tags: `regex`
- Source behavior: Java `replaceAll(".", "-")` treats `.` as a regex.
- Target behavior: Kotlin `replace(".", "-")` with two `String`s replaces the literal dot.
- Detect: `"a.b".replaceAll(".", "-")` is `"---"` in Java; `"a.b".replace(".", "-")` is `"a-b"` in Kotlin.
- Port rule: port `replaceAll(p, r)` as `replace(Regex(p), r)` and `replaceFirst` as `replaceFirst(Regex(p), r)`; Java `replace(CharSequence, CharSequence)` stays `replace`.

### T26. `Regex` with `IGNORE_CASE` is Unicode-aware

- Tags: `regex`, `unicode`
- Source behavior: `Pattern.CASE_INSENSITIVE` alone folds ASCII letters only.
- Target behavior: Kotlin's `Regex` adds `UNICODE_CASE` whenever `IGNORE_CASE` is set.
- Detect: `Pattern.compile("é", Pattern.CASE_INSENSITIVE).matcher("É").matches()` is `false`; `Regex("é", RegexOption.IGNORE_CASE).matches("É")` is `true`.
- Port rule: when the Java pattern lacked `UNICODE_CASE`, keep using `Pattern` directly (`Pattern.compile(p, CASE_INSENSITIVE)`), or record the divergence.

### T27. `trim`, `isBlank` and `isWhitespace` use a different whitespace set

- Tags: `unicode`
- Source behavior: Java `trim()` removes characters up to U+0020 (including control characters); `Character.isWhitespace` and Java 11 `isBlank()` exclude non-breaking spaces.
- Target behavior: Kotlin `trim()`, `isBlank()` and `Char.isWhitespace()` use `Character.isWhitespace(c) || Character.isSpaceChar(c)`: they include U+00A0 and U+2003 and exclude control characters like U+0001.
- Detect: `"\u0001x".trim()` is `"x"` in Java and `"\u0001x"` in Kotlin; `" ".isBlank()` is `false` in Java and `true` in Kotlin.
- Port rule: port Java `trim()` as `trim { it <= ' ' }` and Java `isBlank()`/`strip()` with `Character.isWhitespace` predicates.

### T28. `uppercase()` and `lowercase()` use the invariant locale

- Tags: `locale`
- Source behavior: Java `toUpperCase()` and `toLowerCase()` without arguments use the default locale, so Turkish turns `i` into `İ`.
- Target behavior: Kotlin `uppercase()` and `lowercase()` use `Locale.ROOT`.
- Detect: with default locale `tr_TR`, `"title".toUpperCase()` is `"TİTLE"`; `"title".uppercase()` is `"TITLE"`.
- Port rule: port no-argument Java calls as `uppercase(Locale.getDefault())` where fixtures run under a non-English locale; otherwise record that the port fixes the locale dependence.

### T29. `toByteArray()`, `String(bytes)` and `readText()` default to UTF-8

- Tags: `encoding`, `io`
- Source behavior: `getBytes()`, `new String(bytes)`, `FileReader` and `InputStreamReader` without a charset use the platform default charset (UTF-8 only since JDK 18).
- Target behavior: Kotlin `toByteArray()`, `String(bytes)`, `readText()` and `reader()` use UTF-8.
- Detect: with default charset ISO-8859-1, `"é".getBytes().length` is `1`; `"é".toByteArray().size` is `2`.
- Port rule: pass `Charset.defaultCharset()` explicitly where the Java code relied on the default, or record the switch to UTF-8 as a divergence.

### T30. `"$chars"` is not `String.valueOf(chars)`

- Tags: `encoding`
- Source behavior: `String.valueOf(char[])` builds a string from the characters.
- Target behavior: a string template or `toString()` on a `CharArray` prints the array identity, like `[C@1b6d3586`.
- Detect: `String.valueOf(new char[]{'h', 'i'})` is `"hi"`; `"${charArrayOf('h', 'i')}"` starts with `[C@`.
- Port rule: port as `String(chars)` or `chars.concatToString()`.

### T31. `switch` on `null` throws; `when` takes `else`

- Tags: `nullability`, `error-model`
- Source behavior: a classic Java `switch` on a `null` `String` or enum throws `NullPointerException` (Java 21 pattern switches can add `case null`).
- Target behavior: `when (s)` with a nullable subject falls through to `else`.
- Detect: `switch (s)` with `s = null` throws `NullPointerException`; `when (s) { "a" -> "a"; else -> "other" }` returns `"other"`.
- Port rule: add `null -> throw NullPointerException()` as the first branch when the Java switch could receive `null` and callers rely on the exception.

### T32. `first()` versus `get(0)` exception types

- Tags: `error-model`
- Source behavior: `list.get(0)` on an empty list throws `IndexOutOfBoundsException`.
- Target behavior: the idiomatic `list.first()` throws `NoSuchElementException: List is empty.`.
- Detect: an empty `ArrayList` gives `IndexOutOfBoundsException: Index 0 out of bounds for length 0` from `get(0)` and `NoSuchElementException` from `first()`.
- Port rule: keep `list[0]` where the exception type is observable; use `first()` only where it is not.

### T33. Varargs need the spread operator

- Tags: `reflection`
- Source behavior: Java passes an `Object[]` straight through as the varargs array.
- Target behavior: Kotlin passes an `Array` as a single element unless it is spread with `*`.
- Detect: with `arr = {"a", "b"}`, Java `String.format("%s %s", arr)` returns `"a b"`; Kotlin `String.format("%s %s", arr)` throws `MissingFormatArgumentException: Format specifier '%s'`.
- Port rule: write `*arr` at every call that forwards an array into a vararg parameter.

### T34. SAM conversion creates a new wrapper each time

- Tags: `reflection`, `mutability`
- Source behavior: Java code registers and removes the same listener object.
- Target behavior: passing a Kotlin function value where a Java interface is expected wraps it in a new object at every call site, so removal finds nothing.
- Detect: with Java `add(Runnable r)` and `remove(Runnable r)` backed by a list, Kotlin `val f: () -> Unit = {}; add(f); remove(f)` leaves 1 listener; the Java original leaves 0.
- Port rule: create the interface instance once (`val r = Runnable { ... }`) and pass `r` to both calls.

### T35. Final by default breaks proxies

- Tags: `reflection`
- Source behavior: Spring, Hibernate and older Mockito subclass classes at runtime to add transactions, lazy loading or stubbing.
- Target behavior: Kotlin classes and members are final. Spring refuses a final `@Configuration` class at startup, and calls to a final method on a CGLIB proxy skip the interceptor and run on the proxy instance, whose injected fields are `null`.
- Detect: inside a `@Transactional` method, `TransactionSynchronizationManager.isActualTransactionActive()` is `true` in the Java service and `false` (or an NPE on an injected field) when the Kotlin method is final.
- Port rule: apply the kotlin-spring (all-open) and kotlin-jpa (no-arg) plugins, or mark proxied classes and members `open` explicitly.

### T36. Declaration-site variance adds wildcards to Java signatures

- Tags: `reflection`
- Source behavior: Java `void sum(List<Number> l)` has exactly that generic signature.
- Target behavior: Kotlin `fun sum(l: List<Number>)` compiles to `sum(List<? extends Number>)` because `List` is covariant. DI frameworks that match generic types (Dagger, Guice multibindings) then look up the wrong key.
- Detect: `Svc.class.getMethod("sum", List.class).getGenericParameterTypes()[0]` is `java.util.List<java.lang.Number>` for the Java method and `java.util.List<? extends java.lang.Number>` for the Kotlin one.
- Port rule: add `@JvmSuppressWildcards` on parameters, classes or injection sites where the Java signature must stay exact.

### T37. `Optional` presence collapses into `null`

- Tags: `nullability`
- Source behavior: `Map<String, Optional<String>>` can hold a key whose value is `Optional.empty()`, which differs from a missing key.
- Target behavior: porting to `Map<String, String?>` makes `map["k"]` return `null` in both cases.
- Detect: with `"k"` mapped to `Optional.empty()`, Java `m.get("k")` is `Optional.empty` and `m.get("x")` is `null`; Kotlin `m["k"]` and `m["x"]` are both `null`.
- Port rule: check `containsKey` where presence matters, and keep `Optional` in Java-facing signatures and in nested positions.

### T38. `ThreadLocal` values do not follow coroutines

- Tags: `async`
- Source behavior: Java code sets a `ThreadLocal` (request id, MDC, security context) and reads it later on the same thread.
- Target behavior: after `withContext(Dispatchers.IO)`, the code runs on a pool thread where the value is not set.
- Detect: `tl.set("a"); tl.get()` returns `"a"` in Java; in Kotlin, `tl.set("a"); withContext(Dispatchers.IO) { tl.get() }` returns `null`.
- Port rule: do not introduce dispatcher switches into code that relies on thread-locals; when coroutines are required, pass `tl.asContextElement(value)` (or `MDCContext()`) in the context.

### T39. Gson bypasses constructors

- Tags: `nullability`
- Source behavior: for a Java POJO with field initializers (`String name = "x"`), Gson calls the no-arg constructor, so missing JSON fields keep their defaults.
- Target behavior: for a Kotlin class without a no-arg constructor, Gson allocates the object without running any constructor, so defaults are lost and non-null properties can hold `null`.
- Detect: `{"id":1}` into `data class Foo(val id: Int, val name: String = "x")` gives `name == null` with Gson; the Java POJO gives `"x"`.
- Port rule: move the classes to Jackson with the Kotlin module, Moshi with Kotlin codegen, or kotlinx.serialization. If Gson must stay, give every constructor parameter a default (Kotlin then generates a no-arg constructor).

### T40. Jackson needs the Kotlin module

- Tags: `error-model`, `nullability`
- Source behavior: Jackson builds Java POJOs through a no-arg constructor and setters, keeping field initializers for missing properties.
- Target behavior: without jackson-module-kotlin, a Kotlin class with only a primary constructor cannot be deserialized. With the module, missing properties use Kotlin defaults, and missing or `null` values for non-null parameters without defaults throw `MissingKotlinParameterException`.
- Detect: `{"id":1}` into `data class Foo(val id: Int, val name: String = "x")` with a plain `ObjectMapper` throws `InvalidDefinitionException` ("Cannot construct instance of ... (no Creators, like default constructor, exist)"); the Java POJO deserializes.
- Port rule: build mappers with `jacksonObjectMapper()` or `registerKotlinModule()`, and give properties the nullability and defaults that reproduce the Java POJO's behavior for missing fields.

### T41. jackson-module-kotlin keeps the `is` prefix in JSON names

- Tags: `encoding`, `reflection`
- Source behavior: a Java bean with `boolean enabled` and `isEnabled()` serializes as `"enabled"`.
- Target behavior: a Kotlin property `val isEnabled: Boolean` serializes as `"isEnabled"` once the Kotlin module is registered (plain Jackson still writes `"enabled"`).
- Detect: serializing `data class Flag(val isEnabled: Boolean)` gives `{"enabled":true}` with plain Jackson and `{"isEnabled":true}` with jackson-module-kotlin 2.17.
- Port rule: add `@JsonProperty("enabled")` (or `@get:JsonProperty`) to `is`-prefixed properties, and compare JSON fixtures for every boolean.

### T42. kotlinx.serialization omits default values

- Tags: `encoding`
- Source behavior: Jackson and Gson write every property, including ones equal to their initial value.
- Target behavior: kotlinx.serialization's `Json` skips properties whose value equals the default unless `encodeDefaults = true`.
- Detect: for `data class A(val x: Int = 0, val y: String)`, Jackson writes `{"x":0,"y":"v"}`; `Json.encodeToString(A(y = "v"))` writes `{"y":"v"}`.
- Port rule: configure `Json { encodeDefaults = true }` when replacing Jackson or Gson, and check `explicitNulls` and `ignoreUnknownKeys` against the old behavior too.

### T43. Joda `Y` is year of era; `java.time` `Y` is week-based year

- Tags: `datetime`
- Source behavior: Joda-Time's `DateTimeFormat.forPattern("YYYY-MM-dd")` formats the calendar year (`Y` is year of era, `x` is week year).
- Target behavior: `DateTimeFormatter.ofPattern("YYYY-MM-dd")` formats the week-based year.
- Detect: for December 30, 2024, Joda prints `2024-12-30`; `java.time` prints `2025-12-30`.
- Port rule: translate Joda patterns letter by letter: Joda `Y` becomes `yyyy` (or `uuuu`), Joda `x` becomes `YYYY`, and check every pattern with a fixture at a year boundary.
