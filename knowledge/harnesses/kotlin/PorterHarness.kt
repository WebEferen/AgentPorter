// AgentPorter parity harness for Kotlin (JVM) ports, see knowledge/oracles/CONTRACT.md. No dependencies.
// Compile with Bindings.kt and the port, then: java -jar harness.jar --workspace .porter --run <run> [--unit <unit>]

package porter

import java.lang.reflect.Modifier
import java.math.BigDecimal
import java.math.BigInteger
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit
import java.time.temporal.TemporalAccessor
import java.util.Base64
import java.util.SortedMap
import java.util.concurrent.ExecutionException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import kotlin.system.exitProcess

/** One binding: (decoded args, decoded kwargs, decoded input including "init") -> the port's result. */
typealias Binding = (args: List<Any?>, kwargs: Map<String, Any?>, input: Map<String, Any?>) -> Any?

/** Return this when the source returned JavaScript undefined; it serializes as {"$undefined": true}. */
object Undefined

/** Thrown by bindings when the case input does not fit the port's signature. */
class BindingError(message: String) : RuntimeException(message)

private const val DRIVER = "agentporter/knowledge/harnesses/kotlin/PorterHarness.kt"
private const val SAFE_INT = 1L shl 53
private const val MAX_DEPTH = 64
private const val MAX_ITEMS = 10000

private class HarnessError(message: String) : RuntimeException(message)

private class Json(private val s: String) {
    private var i = 0

    companion object {
        fun parse(text: String): Any? {
            val j = Json(text)
            val v = j.value()
            j.ws()
            if (j.i != text.length) throw HarnessError("trailing data in JSON at ${j.i}")
            return v
        }

        fun write(v: Any?): String = StringBuilder().also { write(it, v, 0) }.append('\n').toString()

        private fun indent(b: StringBuilder, n: Int) {
            b.append('\n')
            repeat(n) { b.append("  ") }
        }

        fun write(b: StringBuilder, v: Any?, depth: Int) {
            when (v) {
                null -> b.append("null")
                is String -> quote(b, v)
                is Boolean, is Long, is Int, is BigInteger -> b.append(v)
                is Double -> b.append(if (v == Math.rint(v) && Math.abs(v) < 1e16) "${v.toLong()}.0" else v.toString())
                is Map<*, *> -> {
                    if (v.isEmpty()) { b.append("{}"); return }
                    b.append('{')
                    var first = true
                    for ((k, x) in v) {
                        if (!first) b.append(',')
                        first = false
                        indent(b, depth + 1)
                        quote(b, k as String)
                        b.append(": ")
                        write(b, x, depth + 1)
                    }
                    indent(b, depth)
                    b.append('}')
                }
                is List<*> -> {
                    if (v.isEmpty()) { b.append("[]"); return }
                    b.append('[')
                    v.forEachIndexed { k, x ->
                        if (k > 0) b.append(',')
                        indent(b, depth + 1)
                        write(b, x, depth + 1)
                    }
                    indent(b, depth)
                    b.append(']')
                }
                else -> quote(b, v.toString())
            }
        }

        fun quote(b: StringBuilder, str: String) {
            b.append('"')
            for (c in str) {
                when (c) {
                    '"' -> b.append("\\\"")
                    '\\' -> b.append("\\\\")
                    '\n' -> b.append("\\n")
                    '\r' -> b.append("\\r")
                    '\t' -> b.append("\\t")
                    else -> if (c < ' ') b.append(String.format("\\u%04x", c.code)) else b.append(c)
                }
            }
            b.append('"')
        }

        fun canonical(v: Any?): String = when (v) {
            is Map<*, *> -> v.entries.sortedBy { it.key as String }
                .joinToString(",", "{", "}") { StringBuilder().also { b -> quote(b, it.key as String) }.toString() + ":" + canonical(it.value) }
            is List<*> -> v.joinToString(",", "[", "]") { canonical(it) }
            else -> StringBuilder().also { write(it, v, 0) }.toString()
        }
    }

    fun ws() {
        while (i < s.length && s[i].isWhitespace()) i++
    }

    private fun expect(c: Char) {
        if (s[i] != c) throw HarnessError("expected '$c' in JSON at $i")
        i++
    }

    fun value(): Any? {
        ws()
        when (s[i]) {
            '{' -> {
                i++
                val m = LinkedHashMap<String, Any?>()
                ws()
                if (s[i] == '}') { i++; return m }
                while (true) {
                    ws()
                    val k = string()
                    ws()
                    expect(':')
                    m[k] = value()
                    ws()
                    if (s[i] == ',') { i++; continue }
                    expect('}')
                    return m
                }
            }
            '[' -> {
                i++
                val a = ArrayList<Any?>()
                ws()
                if (s[i] == ']') { i++; return a }
                while (true) {
                    a.add(value())
                    ws()
                    if (s[i] == ',') { i++; continue }
                    expect(']')
                    return a
                }
            }
            '"' -> return string()
        }
        if (s.startsWith("true", i)) { i += 4; return true }
        if (s.startsWith("false", i)) { i += 5; return false }
        if (s.startsWith("null", i)) { i += 4; return null }
        val start = i
        while (i < s.length && s[i] in "+-0123456789.eE") i++
        val num = s.substring(start, i)
        if (num.isEmpty()) throw HarnessError("bad JSON at $start")
        if (num.any { it == '.' || it == 'e' || it == 'E' }) return num.toDouble()
        val big = BigInteger(num)
        return if (big.bitLength() < 64) big.toLong() else big
    }

    private fun string(): String {
        expect('"')
        val b = StringBuilder()
        while (true) {
            val c = s[i++]
            if (c == '"') return b.toString()
            if (c != '\\') { b.append(c); continue }
            when (val e = s[i++]) {
                'n' -> b.append('\n')
                't' -> b.append('\t')
                'r' -> b.append('\r')
                'b' -> b.append('\b')
                'f' -> b.append('\u000c')
                'u' -> { b.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4 }
                else -> b.append(e)
            }
        }
    }
}

private fun tag(k: String, v: Any?): Map<String, Any?> = linkedMapOf(k to v)

private fun number(d: Double): Any = when {
    d.isNaN() -> tag("\$float", "nan")
    d.isInfinite() -> tag("\$float", if (d > 0) "inf" else "-inf")
    d == 0.0 && 1.0 / d < 0 -> tag("\$float", "-0")
    else -> d
}

fun serialize(v: Any?, depth: Int = 0): Any? {
    if (v == null || v == Unit) return null
    if (depth > MAX_DEPTH) return linkedMapOf("\$type" to v.javaClass.simpleName, "truncated" to true)
    val d = depth + 1
    return when (v) {
        Undefined -> tag("\$undefined", true)
        is Boolean, is String -> v
        is Char, is CharSequence -> v.toString()
        is Byte, is Short, is Int -> (v as Number).toLong()
        is Long -> if (v > SAFE_INT || v < -SAFE_INT) tag("\$int", v.toString()) else v
        is BigInteger -> tag("\$int", v.toString())
        is Float -> number(v.toString().toDouble())
        is Double -> number(v)
        is BigDecimal -> tag("\$decimal", v.toString())
        is ByteArray -> tag("\$bytes", Base64.getEncoder().encodeToString(v))
        is Pair<*, *> -> listOf(serialize(v.first, d), serialize(v.second, d))
        is Triple<*, *, *> -> listOf(serialize(v.first, d), serialize(v.second, d), serialize(v.third, d))
        is Enum<*> -> tag("\$enum", "${v.declaringJavaClass.simpleName}.${v.name}")
        is java.util.Date -> tag("\$datetime", v.toInstant().toString())
        is TemporalAccessor -> tag("\$datetime", v.toString())
        is Set<*> -> tag("\$set", v.map { serialize(it, d) }.sortedBy { Json.canonical(it) })
        is Map<*, *> -> {
            if (v.keys.all { it is String }) {
                v.entries.associateTo(LinkedHashMap()) { (k, x) -> k as String to serialize(x, d) }
            } else {
                val entries = v.entries.map { (k, x) -> listOf(serialize(k, d), serialize(x, d)) }
                val ordered = v is LinkedHashMap<*, *> || v is SortedMap<*, *>
                tag("\$map", if (ordered) entries else entries.sortedBy { Json.canonical(it[0]) })
            }
        }
        is Iterable<*> -> v.map { serialize(it, d) }
        is Sequence<*> -> v.take(MAX_ITEMS).map { serialize(it, d) }.toList()
        is Throwable -> linkedMapOf("\$type" to v.javaClass.simpleName, "message" to v.message)
        else -> {
            if (v.javaClass.isArray) {
                (0 until java.lang.reflect.Array.getLength(v)).map { serialize(java.lang.reflect.Array.get(v, it), d) }
            } else {
                serializeObject(v, d)
            }
        }
    }
}

private fun serializeObject(v: Any, d: Int): Map<String, Any?> {
    val c = v.javaClass
    val fields = sortedMapOf<String, Any?>()
    for (f in c.fields) if (!Modifier.isStatic(f.modifiers)) fields[f.name] = f.get(v)
    for (m in c.methods) {
        if (Modifier.isStatic(m.modifiers) || m.parameterCount != 0 || m.declaringClass == Any::class.java) continue
        val n = m.name
        val prop = when {
            n.startsWith("get") && n.length > 3 && n != "getClass" -> n.substring(3)
            n.startsWith("is") && n.length > 2 && (m.returnType == java.lang.Boolean.TYPE || m.returnType == java.lang.Boolean::class.java) -> n.substring(2)
            else -> continue
        }
        val key = prop.replaceFirstChar { it.lowercaseChar() }
        if (key !in fields) fields[key] = m.invoke(v)
    }
    val out = linkedMapOf<String, Any?>("\$type" to c.simpleName)
    for ((k, x) in fields) out[k] = serialize(x, d)
    return out
}

@Suppress("UNCHECKED_CAST")
fun decode(v: Any?): Any? {
    if (v is List<*>) return v.map { decode(it) }
    if (v !is Map<*, *>) return v
    if (v.size == 1) {
        val (k, raw) = v.entries.first()
        when (k) {
            "\$float" -> return when (raw) { "nan" -> Double.NaN; "inf" -> Double.POSITIVE_INFINITY; "-inf" -> Double.NEGATIVE_INFINITY; else -> -0.0 }
            "\$int" -> return BigInteger(raw as String).let { if (it.bitLength() < 64) it.toLong() else it }
            "\$bytes" -> return Base64.getDecoder().decode(raw as String)
            "\$decimal" -> return BigDecimal(raw as String)
            "\$datetime" -> return parseDate(raw as String)
            "\$set" -> return (raw as List<*>).mapTo(LinkedHashSet()) { decode(it) }
            "\$map" -> return (raw as List<*>).associateTo(LinkedHashMap()) { e -> (e as List<*>).let { decode(it[0]) to decode(it[1]) } }
            "\$undefined" -> return null
        }
    }
    return (v as Map<String, Any?>).mapValuesTo(LinkedHashMap()) { decode(it.value) }
}

private fun parseDate(s: String): Any =
    runCatching<Any> { OffsetDateTime.parse(s) }
        .recoverCatching { LocalDateTime.parse(s) }
        .recoverCatching { LocalDate.parse(s) }
        .getOrDefault(s)

private var executor: ExecutorService = newExecutor()

private fun newExecutor(): ExecutorService = Executors.newSingleThreadExecutor { r -> Thread(r, "porter-case").apply { isDaemon = true } }

private fun errorOutcome(category: String, message: String?) = linkedMapOf<String, Any?>("kind" to "error", "category" to category, "message" to (message ?: ""))

@Suppress("UNCHECKED_CAST")
private fun runCase(binding: Binding, input: Map<String, Any?>, timeout: Double): Map<String, Any?> {
    val decoded = decode(input) as Map<String, Any?>
    val args = decoded["args"] as? List<Any?> ?: emptyList()
    val kwargs = decoded["kwargs"] as? Map<String, Any?> ?: emptyMap()
    val future = executor.submit<Any?> { binding(args, kwargs, decoded) }
    return try {
        linkedMapOf("kind" to "value", "value" to serialize(future.get((timeout * 1000).toLong(), TimeUnit.MILLISECONDS)))
    } catch (e: TimeoutException) {
        future.cancel(true)
        executor = newExecutor()
        errorOutcome("timeout", "timed out after ${timeout}s")
    } catch (e: ExecutionException) {
        val cause = e.cause ?: e
        errorOutcome(cause.javaClass.simpleName, cause.message)
    }
}

private fun writeJson(path: Path, v: Any?) {
    Files.createDirectories(path.parent)
    val tmp = path.resolveSibling("${path.fileName}.tmp")
    Files.writeString(tmp, Json.write(v))
    Files.move(tmp, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
}

@Suppress("UNCHECKED_CAST")
fun main(argv: Array<String>) {
    var workspace = ".porter"
    var run = Instant.now().truncatedTo(ChronoUnit.SECONDS).toString().replace("-", "").replace(":", "")
    var timeout = 10.0
    val units = ArrayList<String>()
    try {
        var k = 0
        fun next(): String = argv.getOrNull(++k) ?: throw HarnessError("${argv[k - 1]} needs a value")
        while (k < argv.size) {
            when (argv[k]) {
                "--workspace" -> workspace = next()
                "--run" -> run = next()
                "--unit" -> units.add(next())
                "--timeout" -> timeout = next().toDouble()
                else -> throw HarnessError("unknown argument ${argv[k]}")
            }
            k++
        }
        val fixtures = Paths.get(workspace, "fixtures")
        if (units.isEmpty()) {
            if (!Files.isDirectory(fixtures)) throw HarnessError("no fixtures under $fixtures")
            Files.list(fixtures).use { s -> s.filter { Files.isDirectory(it) }.map { it.fileName.toString() }.sorted().forEach { units.add(it) } }
        }
        if (units.isEmpty()) throw HarnessError("no fixtures under $fixtures")
        var missing = 0
        for (unit in units) {
            val dir = fixtures.resolve(unit)
            if (!Files.isDirectory(dir)) throw HarnessError("no fixtures for unit $unit")
            val files = Files.list(dir).use { s -> s.filter { it.toString().endsWith(".json") }.sorted().toList() }
            val startedAt = Instant.now().truncatedTo(ChronoUnit.SECONDS).toString()
            val results = ArrayList<Any?>()
            var errors = 0
            for (f in files) {
                val fixture = Json.parse(Files.readString(f)) as Map<String, Any?>
                for (raw in fixture["cases"] as List<*>) {
                    val c = raw as Map<String, Any?>
                    if ((c["expect"] as Map<String, Any?>)["kind"] == "cli") continue
                    val call = c["call"] as String
                    val binding = bindings[call]
                    val started = System.nanoTime()
                    val actual = if (binding == null) {
                        missing++
                        errorOutcome("MissingBinding", "no binding for $call")
                    } else {
                        runCase(binding, c["input"] as? Map<String, Any?> ?: emptyMap(), timeout)
                    }
                    if (actual["kind"] == "error") errors++
                    val ms = Math.round((System.nanoTime() - started) / 1e6 * 10000) / 10000.0
                    results.add(linkedMapOf("case" to c["case"], "actual" to actual, "durationMs" to ms))
                }
            }
            writeJson(
                Paths.get(workspace, "runs", run, "$unit.json"),
                linkedMapOf(
                    "schema" to 1L,
                    "unit" to unit,
                    "runner" to linkedMapOf("language" to "kotlin", "driver" to DRIVER, "runtime" to "kotlin ${KotlinVersion.CURRENT} on java ${System.getProperty("java.version")}"),
                    "startedAt" to startedAt,
                    "results" to results,
                ),
            )
            println("$unit: ran ${results.size} cases ($errors errors) -> runs/$run/$unit.json")
        }
        if (missing > 0) System.err.println("harness: $missing case(s) have no binding (recorded as MissingBinding)")
    } catch (e: HarnessError) {
        System.err.println("harness: ${e.message}")
        exitProcess(2)
    } catch (e: Exception) {
        System.err.println("harness: $e")
        exitProcess(2)
    }
    exitProcess(0)
}
