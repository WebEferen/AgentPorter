// AgentPorter oracle driver for Java (and other JVM) sources, see knowledge/oracles/CONTRACT.md.
// Single-file source, Java 17+, no dependencies: java -cp <source classpath> Oracle.java --workspace .porter
import java.lang.reflect.Array;
import java.lang.reflect.Constructor;
import java.lang.reflect.Executable;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.RecordComponent;
import java.lang.reflect.Type;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZonedDateTime;
import java.time.temporal.TemporalAccessor;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

public class Oracle {
    static final String DRIVER = "agentporter/knowledge/oracles/java/Oracle.java";
    static final long SAFE_INT = 1L << 53;

    static class OracleError extends RuntimeException {
        OracleError(String m) { super(m); }
    }

    static class NoFit extends Exception {
        NoFit() { super(null, null, false, false); }
    }

    static final class Json {
        final String s;
        int i;

        Json(String s) { this.s = s; }

        static Object parse(String text) {
            Json j = new Json(text);
            Object v = j.value();
            j.ws();
            if (j.i != j.s.length()) throw new OracleError("trailing data in JSON at " + j.i);
            return v;
        }

        void ws() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }

        Object value() {
            ws();
            char c = s.charAt(i);
            if (c == '{') {
                i++;
                Map<String, Object> m = new LinkedHashMap<>();
                ws();
                if (s.charAt(i) == '}') { i++; return m; }
                for (;;) {
                    ws();
                    String k = string();
                    ws();
                    expect(':');
                    m.put(k, value());
                    ws();
                    if (s.charAt(i) == ',') { i++; continue; }
                    expect('}');
                    return m;
                }
            }
            if (c == '[') {
                i++;
                List<Object> a = new ArrayList<>();
                ws();
                if (s.charAt(i) == ']') { i++; return a; }
                for (;;) {
                    a.add(value());
                    ws();
                    if (s.charAt(i) == ',') { i++; continue; }
                    expect(']');
                    return a;
                }
            }
            if (c == '"') return string();
            if (s.startsWith("true", i)) { i += 4; return Boolean.TRUE; }
            if (s.startsWith("false", i)) { i += 5; return Boolean.FALSE; }
            if (s.startsWith("null", i)) { i += 4; return null; }
            int start = i;
            while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
            String num = s.substring(start, i);
            if (num.isEmpty()) throw new OracleError("bad JSON at " + start);
            if (num.contains(".") || num.contains("e") || num.contains("E")) return Double.parseDouble(num);
            BigInteger big = new BigInteger(num);
            return big.bitLength() < 64 ? (Object) big.longValue() : big;
        }

        void expect(char c) {
            if (s.charAt(i) != c) throw new OracleError("expected '" + c + "' in JSON at " + i);
            i++;
        }

        String string() {
            expect('"');
            StringBuilder b = new StringBuilder();
            for (;;) {
                char c = s.charAt(i++);
                if (c == '"') return b.toString();
                if (c != '\\') { b.append(c); continue; }
                char e = s.charAt(i++);
                switch (e) {
                    case 'n' -> b.append('\n');
                    case 't' -> b.append('\t');
                    case 'r' -> b.append('\r');
                    case 'b' -> b.append('\b');
                    case 'f' -> b.append('\f');
                    case 'u' -> { b.append((char) Integer.parseInt(s.substring(i, i + 4), 16)); i += 4; }
                    default -> b.append(e);
                }
            }
        }

        static String write(Object v) {
            StringBuilder b = new StringBuilder();
            write(b, v, 0);
            return b.append('\n').toString();
        }

        static void indent(StringBuilder b, int n) {
            b.append('\n');
            for (int k = 0; k < n; k++) b.append("  ");
        }

        @SuppressWarnings("unchecked")
        static void write(StringBuilder b, Object v, int depth) {
            if (v == null) b.append("null");
            else if (v instanceof String str) quote(b, str);
            else if (v instanceof Boolean || v instanceof Long || v instanceof Integer || v instanceof BigInteger) b.append(v);
            else if (v instanceof Double d) b.append(d == Math.rint(d) && Math.abs(d) < 1e16 ? String.valueOf(d.longValue()) + ".0" : String.valueOf(d));
            else if (v instanceof Map<?, ?> m) {
                if (m.isEmpty()) { b.append("{}"); return; }
                b.append('{');
                boolean first = true;
                for (Map.Entry<?, ?> e : m.entrySet()) {
                    if (!first) b.append(',');
                    first = false;
                    indent(b, depth + 1);
                    quote(b, (String) e.getKey());
                    b.append(": ");
                    write(b, e.getValue(), depth + 1);
                }
                indent(b, depth);
                b.append('}');
            } else if (v instanceof List<?> l) {
                if (l.isEmpty()) { b.append("[]"); return; }
                b.append('[');
                for (int k = 0; k < l.size(); k++) {
                    if (k > 0) b.append(',');
                    indent(b, depth + 1);
                    write(b, l.get(k), depth + 1);
                }
                indent(b, depth);
                b.append(']');
            } else quote(b, String.valueOf(v));
        }

        static void quote(StringBuilder b, String str) {
            b.append('"');
            for (int k = 0; k < str.length(); k++) {
                char c = str.charAt(k);
                switch (c) {
                    case '"' -> b.append("\\\"");
                    case '\\' -> b.append("\\\\");
                    case '\n' -> b.append("\\n");
                    case '\r' -> b.append("\\r");
                    case '\t' -> b.append("\\t");
                    default -> {
                        if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                        else b.append(c);
                    }
                }
            }
            b.append('"');
        }

        static String canonical(Object v) {
            if (v instanceof Map<?, ?> m) {
                TreeMap<String, Object> t = new TreeMap<>();
                for (Map.Entry<?, ?> e : m.entrySet()) t.put((String) e.getKey(), e.getValue());
                StringBuilder b = new StringBuilder("{");
                boolean first = true;
                for (Map.Entry<String, Object> e : t.entrySet()) {
                    if (!first) b.append(',');
                    first = false;
                    quote(b, e.getKey());
                    b.append(':').append(canonical(e.getValue()));
                }
                return b.append('}').toString();
            }
            if (v instanceof List<?> l) {
                StringBuilder b = new StringBuilder("[");
                for (int k = 0; k < l.size(); k++) {
                    if (k > 0) b.append(',');
                    b.append(canonical(l.get(k)));
                }
                return b.append(']').toString();
            }
            StringBuilder b = new StringBuilder();
            write(b, v, 0);
            return b.toString();
        }
    }

    static Map<String, Object> tag(String k, Object v) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k, v);
        return m;
    }

    static Object number(double d) {
        if (Double.isNaN(d)) return tag("$float", "nan");
        if (Double.isInfinite(d)) return tag("$float", d > 0 ? "inf" : "-inf");
        if (d == 0.0 && 1.0 / d < 0) return tag("$float", "-0");
        return d;
    }

    static Object serialize(Object v, int depth) {
        if (v == null) return null;
        if (depth > 64) {
            Map<String, Object> m = tag("$type", v.getClass().getSimpleName());
            m.put("truncated", true);
            return m;
        }
        int d = depth + 1;
        if (v instanceof Boolean || v instanceof String) return v;
        if (v instanceof Character || v instanceof CharSequence) return v.toString();
        if (v instanceof Byte || v instanceof Short || v instanceof Integer) return ((Number) v).longValue();
        if (v instanceof Long l) return l > SAFE_INT || l < -SAFE_INT ? tag("$int", l.toString()) : l;
        if (v instanceof BigInteger bi) return tag("$int", bi.toString());
        if (v instanceof Float f) return number(Double.parseDouble(Float.toString(f)));
        if (v instanceof Double dbl) return number(dbl);
        if (v instanceof BigDecimal bd) return tag("$decimal", bd.toString());
        if (v instanceof byte[] bytes) return tag("$bytes", Base64.getEncoder().encodeToString(bytes));
        if (v instanceof Optional<?> o) return o.isPresent() ? serialize(o.get(), d) : null;
        if (v instanceof Enum<?> e) return tag("$enum", e.getDeclaringClass().getSimpleName() + "." + e.name());
        if (v instanceof java.util.Date date) return tag("$datetime", date.toInstant().toString());
        if (v instanceof TemporalAccessor t) return tag("$datetime", t.toString());
        if (v.getClass().isArray()) {
            List<Object> out = new ArrayList<>();
            for (int k = 0; k < Array.getLength(v); k++) out.add(serialize(Array.get(v, k), d));
            return out;
        }
        if (v instanceof Set<?> set) {
            List<Object> out = new ArrayList<>();
            for (Object x : set) out.add(serialize(x, d));
            out.sort(Comparator.comparing(Json::canonical));
            return tag("$set", out);
        }
        if (v instanceof Map<?, ?> map) {
            boolean ordered = map instanceof LinkedHashMap || map instanceof SortedMap;
            boolean stringKeys = map.keySet().stream().allMatch(k -> k instanceof String);
            if (stringKeys) {
                Map<String, Object> out = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : map.entrySet()) out.put((String) e.getKey(), serialize(e.getValue(), d));
                return out;
            }
            List<Object> entries = new ArrayList<>();
            for (Map.Entry<?, ?> e : map.entrySet()) entries.add(java.util.Arrays.asList(serialize(e.getKey(), d), serialize(e.getValue(), d)));
            if (!ordered) entries.sort(Comparator.comparing(x -> Json.canonical(((List<?>) x).get(0))));
            return tag("$map", entries);
        }
        if (v instanceof Iterable<?> it) {
            List<Object> out = new ArrayList<>();
            for (Object x : it) out.add(serialize(x, d));
            return out;
        }
        if (v instanceof Throwable t) {
            Map<String, Object> m = tag("$type", t.getClass().getSimpleName());
            m.put("message", t.getMessage());
            return m;
        }
        TreeMap<String, Object> fields = new TreeMap<>();
        Class<?> c = v.getClass();
        try {
            if (c.isRecord()) {
                for (RecordComponent rc : c.getRecordComponents()) fields.put(rc.getName(), rc.getAccessor().invoke(v));
            } else {
                for (Field f : c.getFields()) {
                    if (!Modifier.isStatic(f.getModifiers())) fields.put(f.getName(), f.get(v));
                }
                for (Method m : c.getMethods()) {
                    if (Modifier.isStatic(m.getModifiers()) || m.getParameterCount() != 0 || m.getDeclaringClass() == Object.class) continue;
                    String n = m.getName();
                    String prop = null;
                    if (n.startsWith("get") && n.length() > 3) prop = n.substring(3);
                    else if (n.startsWith("is") && n.length() > 2 && (m.getReturnType() == boolean.class || m.getReturnType() == Boolean.class)) prop = n.substring(2);
                    if (prop == null) continue;
                    prop = Character.toLowerCase(prop.charAt(0)) + prop.substring(1);
                    if (!fields.containsKey(prop)) fields.put(prop, m.invoke(v));
                }
            }
        } catch (ReflectiveOperationException e) {
            throw new OracleError("cannot read fields of " + c.getName() + ": " + e);
        }
        Map<String, Object> out = tag("$type", c.getSimpleName());
        for (Map.Entry<String, Object> e : fields.entrySet()) out.put(e.getKey(), serialize(e.getValue(), d));
        return out;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    static Object convert(Object json, Class<?> t, Type generic, int[] cost) throws NoFit {
        if (json == null) {
            if (t.isPrimitive()) throw new NoFit();
            return null;
        }
        Map<String, Object> tagged = json instanceof Map<?, ?> m && m.size() == 1 ? (Map<String, Object>) m : null;
        if (t == Object.class) { cost[0] += 3; return natural(json); }
        if (t == String.class || t == CharSequence.class) { if (json instanceof String) return json; throw new NoFit(); }
        if (t == char.class || t == Character.class) {
            if (json instanceof String str && str.length() == 1) return str.charAt(0);
            throw new NoFit();
        }
        if (t == boolean.class || t == Boolean.class) { if (json instanceof Boolean) return json; throw new NoFit(); }
        if (t == long.class || t == Long.class) return integral(json, tagged, Long.MIN_VALUE, Long.MAX_VALUE).longValue();
        if (t == int.class || t == Integer.class) { cost[0] += 1; return integral(json, tagged, Integer.MIN_VALUE, Integer.MAX_VALUE).intValue(); }
        if (t == short.class || t == Short.class) { cost[0] += 2; return integral(json, tagged, Short.MIN_VALUE, Short.MAX_VALUE).shortValue(); }
        if (t == byte.class || t == Byte.class) { cost[0] += 2; return integral(json, tagged, Byte.MIN_VALUE, Byte.MAX_VALUE).byteValue(); }
        if (t == double.class || t == Double.class || t == float.class || t == Float.class) {
            double dv;
            if (json instanceof Double x) dv = x;
            else if (json instanceof Long l) { dv = l; cost[0] += 2; }
            else if (tagged != null && tagged.get("$float") instanceof String f) {
                dv = switch (f) { case "nan" -> Double.NaN; case "inf" -> Double.POSITIVE_INFINITY; case "-inf" -> Double.NEGATIVE_INFINITY; default -> -0.0; };
            } else throw new NoFit();
            if (t == float.class || t == Float.class) { cost[0] += 1; return (float) dv; }
            return dv;
        }
        if (t == BigInteger.class) {
            if (json instanceof Long l) return BigInteger.valueOf(l);
            if (json instanceof BigInteger) return json;
            if (tagged != null && tagged.get("$int") instanceof String str) return new BigInteger(str);
            throw new NoFit();
        }
        if (t == BigDecimal.class) {
            if (json instanceof Long l) return BigDecimal.valueOf(l);
            if (json instanceof Double x) return BigDecimal.valueOf(x);
            if (tagged != null && tagged.get("$decimal") instanceof String str) return new BigDecimal(str);
            throw new NoFit();
        }
        if (t == byte[].class) {
            if (tagged != null && tagged.get("$bytes") instanceof String str) return Base64.getDecoder().decode(str);
            throw new NoFit();
        }
        if (t.isEnum()) {
            if (json instanceof String str) {
                for (Object c : t.getEnumConstants()) if (((Enum<?>) c).name().equals(str)) return c;
            }
            if (tagged != null && tagged.get("$enum") instanceof String str) {
                String name = str.substring(str.lastIndexOf('.') + 1);
                for (Object c : t.getEnumConstants()) if (((Enum<?>) c).name().equals(name)) return c;
            }
            throw new NoFit();
        }
        if (t == Optional.class) return Optional.ofNullable(convert(json, Object.class, typeArg(generic, 0), cost));
        if (TemporalAccessor.class.isAssignableFrom(t) || t == java.util.Date.class) {
            if (tagged == null || !(tagged.get("$datetime") instanceof String str)) throw new NoFit();
            if (t == Instant.class) return Instant.parse(str);
            if (t == LocalDate.class) return LocalDate.parse(str);
            if (t == LocalDateTime.class) return LocalDateTime.parse(str);
            if (t == LocalTime.class) return LocalTime.parse(str);
            if (t == OffsetDateTime.class) return OffsetDateTime.parse(str);
            if (t == ZonedDateTime.class) return ZonedDateTime.parse(str);
            if (t == java.util.Date.class) return java.util.Date.from(Instant.parse(str));
            throw new NoFit();
        }
        if (t.isArray()) {
            if (!(json instanceof List<?> l)) throw new NoFit();
            Object arr = Array.newInstance(t.getComponentType(), l.size());
            for (int k = 0; k < l.size(); k++) Array.set(arr, k, convert(l.get(k), t.getComponentType(), t.getComponentType(), cost));
            return arr;
        }
        if (Set.class.isAssignableFrom(t)) {
            List<?> items = json instanceof List<?> l ? l : tagged != null && tagged.get("$set") instanceof List<?> l2 ? l2 : null;
            if (items == null) throw new NoFit();
            Set out = new LinkedHashSet();
            Type et = typeArg(generic, 0);
            for (Object x : items) out.add(convert(x, rawClass(et), et, cost));
            return out;
        }
        if (Collection.class.isAssignableFrom(t) || t == Iterable.class) {
            if (!(json instanceof List<?> l)) throw new NoFit();
            List out = new ArrayList();
            Type et = typeArg(generic, 0);
            for (Object x : l) out.add(convert(x, rawClass(et), et, cost));
            return out;
        }
        if (Map.class.isAssignableFrom(t)) {
            Type kt = typeArg(generic, 0), vt = typeArg(generic, 1);
            Map out = new LinkedHashMap();
            if (tagged != null && tagged.get("$map") instanceof List<?> entries) {
                for (Object e : entries) {
                    List<?> pair = (List<?>) e;
                    out.put(convert(pair.get(0), rawClass(kt), kt, cost), convert(pair.get(1), rawClass(vt), vt, cost));
                }
                return out;
            }
            if (!(json instanceof Map<?, ?> m)) throw new NoFit();
            for (Map.Entry<?, ?> e : m.entrySet()) out.put(convert(e.getKey(), rawClass(kt), kt, cost), convert(e.getValue(), rawClass(vt), vt, cost));
            return out;
        }
        throw new NoFit();
    }

    static BigInteger integral(Object json, Map<String, Object> tagged, long min, long max) throws NoFit {
        BigInteger n = json instanceof Long l ? BigInteger.valueOf(l) : json instanceof BigInteger b ? b
            : tagged != null && tagged.get("$int") instanceof String str ? new BigInteger(str) : null;
        if (n == null || n.compareTo(BigInteger.valueOf(min)) < 0 || n.compareTo(BigInteger.valueOf(max)) > 0) throw new NoFit();
        return n;
    }

    @SuppressWarnings("unchecked")
    static Object natural(Object json) {
        if (json instanceof List<?> l) {
            List<Object> out = new ArrayList<>();
            for (Object x : l) out.add(natural(x));
            return out;
        }
        if (json instanceof Map<?, ?> m) {
            if (m.size() == 1) {
                Map<String, Object> t = (Map<String, Object>) m;
                if (t.get("$bytes") instanceof String s) return Base64.getDecoder().decode(s);
                if (t.get("$int") instanceof String s) return new BigInteger(s);
                if (t.get("$decimal") instanceof String s) return new BigDecimal(s);
                if (t.get("$float") instanceof String s) return switch (s) { case "nan" -> Double.NaN; case "inf" -> Double.POSITIVE_INFINITY; case "-inf" -> Double.NEGATIVE_INFINITY; default -> -0.0; };
                if (t.get("$set") instanceof List<?> l) {
                    Set<Object> out = new LinkedHashSet<>();
                    for (Object x : l) out.add(natural(x));
                    return out;
                }
                if (t.get("$map") instanceof List<?> l) {
                    Map<Object, Object> out = new LinkedHashMap<>();
                    for (Object e : l) out.put(natural(((List<?>) e).get(0)), natural(((List<?>) e).get(1)));
                    return out;
                }
            }
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : m.entrySet()) out.put((String) e.getKey(), natural(e.getValue()));
            return out;
        }
        return json;
    }

    static Type typeArg(Type t, int i) {
        if (t instanceof ParameterizedType p && p.getActualTypeArguments().length > i) return p.getActualTypeArguments()[i];
        return Object.class;
    }

    static Class<?> rawClass(Type t) {
        if (t instanceof Class<?> c) return c;
        if (t instanceof ParameterizedType p) return (Class<?>) p.getRawType();
        return Object.class;
    }

    static Object[] fit(Executable ex, List<?> args, int[] cost) throws NoFit {
        Class<?>[] types = ex.getParameterTypes();
        Type[] generics = ex.getGenericParameterTypes();
        if (ex.isVarArgs() && args.size() >= types.length - 1) {
            Object[] out = new Object[types.length];
            for (int k = 0; k < types.length - 1; k++) out[k] = convert(args.get(k), types[k], generics[k], cost);
            Class<?> comp = types[types.length - 1].getComponentType();
            Object rest = Array.newInstance(comp, args.size() - types.length + 1);
            for (int k = types.length - 1; k < args.size(); k++) Array.set(rest, k - types.length + 1, convert(args.get(k), comp, comp, cost));
            out[types.length - 1] = rest;
            cost[0] += 2;
            return out;
        }
        if (types.length != args.size()) throw new NoFit();
        Object[] out = new Object[types.length];
        for (int k = 0; k < types.length; k++) out[k] = convert(args.get(k), types[k], generics[k], cost);
        return out;
    }

    record Choice(Executable ex, Object[] args) {}

    static Choice choose(List<? extends Executable> candidates, List<?> args, String what) {
        Choice best = null;
        int bestCost = Integer.MAX_VALUE;
        for (Executable ex : candidates) {
            int[] cost = {0};
            try {
                Object[] converted = fit(ex, args, cost);
                if (cost[0] < bestCost) { best = new Choice(ex, converted); bestCost = cost[0]; }
            } catch (NoFit ignored) {
            }
        }
        if (best == null) throw new OracleError(what + ": no overload accepts " + args.size() + " argument(s) with these JSON types");
        best.ex().setAccessible(true);
        return best;
    }

    static Class<?> load(String name) {
        try {
            return Class.forName(name, true, Oracle.class.getClassLoader());
        } catch (ClassNotFoundException | NoClassDefFoundError e) {
            return null;
        }
    }

    static Class<?> nested(Class<?> c, String name) {
        Class<?> n = load(c.getName() + "$" + name);
        if (n == null) throw new OracleError("no nested class " + name + " in " + c.getName());
        return n;
    }

    @SuppressWarnings("unchecked")
    static Object invoke(String call, Map<String, Object> input) throws Throwable {
        int idx = call.lastIndexOf(':');
        if (idx <= 0) throw new OracleError("call '" + call + "' is not <module>:<qualified name>");
        String module = call.substring(0, idx);
        String[] parts = call.substring(idx + 1).split("\\.");
        Class<?> cls = load(module);
        String member;
        if (cls != null) {
            for (int k = 0; k < parts.length - 1; k++) cls = nested(cls, parts[k]);
            member = parts[parts.length - 1];
            Class<?> inner = load(cls.getName() + "$" + member);
            if (inner != null) {
                cls = inner;
                member = null;
            }
        } else {
            cls = load(module + "." + parts[0]);
            if (cls == null) throw new OracleError("cannot resolve " + call + ": no class " + module + " or " + module + "." + parts[0]);
            for (int k = 1; k < parts.length - 1; k++) cls = nested(cls, parts[k]);
            member = parts.length == 1 ? null : parts[parts.length - 1];
        }
        Object kwargs = input.get("kwargs");
        if (kwargs instanceof Map<?, ?> km && !km.isEmpty()) throw new OracleError(call + ": Java has no named arguments; use args");
        List<Object> args = input.get("args") instanceof List<?> l ? (List<Object>) l : List.of();
        boolean hasCall = input.containsKey("args") || input.containsKey("kwargs") || input.containsKey("init");
        try {
            if (member == null) {
                if (!hasCall) return cls;
                Choice c = choose(List.of(cls.getConstructors()), args, call);
                return ((Constructor<?>) c.ex()).newInstance(c.args());
            }
            if (!hasCall) {
                Field f = cls.getField(member);
                return f.get(null);
            }
            Object target = null;
            if (input.containsKey("init")) {
                Map<String, Object> init = input.get("init") instanceof Map<?, ?> m ? (Map<String, Object>) m : Map.of();
                List<Object> initArgs = init.get("args") instanceof List<?> l ? (List<Object>) l : List.of();
                Choice c = choose(List.of(cls.getConstructors()), initArgs, call + " (init)");
                target = ((Constructor<?>) c.ex()).newInstance(c.args());
            }
            List<Method> methods = new ArrayList<>();
            for (Method m : cls.getMethods()) {
                if (!m.getName().equals(member)) continue;
                if (target == null && !Modifier.isStatic(m.getModifiers())) continue;
                methods.add(m);
            }
            if (methods.isEmpty()) throw new OracleError("cannot resolve " + call + ": no public " + (target == null ? "static " : "") + "method " + member);
            Choice c = choose(methods, args, call);
            return ((Method) c.ex()).invoke(target, c.args());
        } catch (InvocationTargetException e) {
            throw e.getCause();
        } catch (NoSuchFieldException e) {
            throw new OracleError("cannot resolve " + call + ": no public static field " + member);
        } catch (IllegalAccessException | InstantiationException e) {
            throw new OracleError("cannot call " + call + ": " + e);
        }
    }

    static ExecutorService executor = newExecutor();

    static ExecutorService newExecutor() {
        return Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "oracle-case");
            t.setDaemon(true);
            return t;
        });
    }

    static Map<String, Object> outcome(String call, Map<String, Object> input, double timeout, String pattern, double[] ms) {
        long start = System.nanoTime();
        Future<Object> f = executor.submit(() -> {
            try {
                return invoke(call, input);
            } catch (Exception | Error e) {
                throw e;
            } catch (Throwable t) {
                throw new java.util.concurrent.CompletionException(t);
            }
        });
        try {
            Object v = f.get((long) (timeout * 1000), TimeUnit.MILLISECONDS);
            ms[0] = (System.nanoTime() - start) / 1e6;
            Map<String, Object> out = tag("kind", "value");
            out.put("value", serialize(v, 0));
            return out;
        } catch (TimeoutException e) {
            f.cancel(true);
            executor = newExecutor();
            ms[0] = timeout * 1000;
            Map<String, Object> out = tag("kind", "error");
            out.put("category", "timeout");
            out.put("message", "timed out after " + timeout + "s");
            return out;
        } catch (InterruptedException e) {
            throw new OracleError("interrupted");
        } catch (java.util.concurrent.ExecutionException e) {
            ms[0] = (System.nanoTime() - start) / 1e6;
            Throwable cause = e.getCause();
            if (cause instanceof java.util.concurrent.CompletionException ce && ce.getCause() != null) cause = ce.getCause();
            if (cause instanceof OracleError oe) throw oe;
            Map<String, Object> out = tag("kind", "error");
            out.put("category", cause.getClass().getSimpleName());
            out.put("message", cause.getMessage());
            if (pattern != null) out.put("messagePattern", pattern);
            return out;
        }
    }

    static Object read(Path p) throws Exception {
        return Json.parse(Files.readString(p, StandardCharsets.UTF_8));
    }

    static void writeFile(Path p, Object v) throws Exception {
        Files.createDirectories(p.getParent());
        Path tmp = p.resolveSibling(p.getFileName() + ".tmp");
        Files.writeString(tmp, Json.write(v), StandardCharsets.UTF_8);
        Files.move(tmp, p, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] argv) throws Exception {
        String workspace = ".porter", version = null, commit = null;
        double timeout = 10;
        List<String> units = new ArrayList<>();
        for (int k = 0; k < argv.length; k++) {
            switch (argv[k]) {
                case "--workspace" -> workspace = argv[++k];
                case "--unit" -> units.add(argv[++k]);
                case "--package-version" -> version = argv[++k];
                case "--commit" -> commit = argv[++k];
                case "--timeout" -> timeout = Double.parseDouble(argv[++k]);
                default -> { System.err.println("oracle: unknown argument " + argv[k]); System.exit(2); }
            }
        }
        try {
            Path ws = Path.of(workspace);
            Map<String, Object> config = (Map<String, Object>) read(ws.resolve("config.json"));
            Map<String, Object> src = (Map<String, Object>) config.getOrDefault("source", Map.of());
            Map<String, Object> pkg = src.get("package") instanceof Map<?, ?> m ? (Map<String, Object>) m : Map.of();
            Path expanded = ws.resolve("oracle").resolve("expanded");
            if (units.isEmpty()) {
                try (var s = Files.list(expanded)) {
                    s.map(p -> p.getFileName().toString()).filter(n -> n.endsWith(".json")).map(n -> n.substring(0, n.length() - 5)).sorted().forEach(units::add);
                }
            }
            if (units.isEmpty()) throw new OracleError("no expanded cases in " + expanded + "; run porter.py fixtures expand");
            String name = pkg.get("name") instanceof String s ? s : units.get(0);
            if (version == null) version = pkg.get("version") instanceof String s ? s : "unknown";
            if (commit == null) commit = src.get("commit") instanceof String s ? s : null;
            for (String unit : units) {
                Map<String, Object> spec = (Map<String, Object>) read(expanded.resolve(unit + ".json"));
                if ("cli".equals(spec.get("kind"))) throw new OracleError("unit " + unit + " is a CLI unit; record it with porter.py cli record");
                List<Object> cases = new ArrayList<>();
                Map<String, Object> timings = new LinkedHashMap<>();
                int errors = 0;
                for (Object raw : (List<Object>) spec.get("cases")) {
                    Map<String, Object> c = (Map<String, Object>) raw;
                    String id = (String) c.get("case");
                    Map<String, Object> input = c.get("input") instanceof Map<?, ?> m ? (Map<String, Object>) m : Map.of();
                    double[] ms = {0};
                    Map<String, Object> expect;
                    try {
                        expect = outcome((String) c.get("call"), input, timeout, (String) c.get("messagePattern"), ms);
                    } catch (OracleError e) {
                        throw new OracleError("case " + id + ": " + e.getMessage());
                    }
                    if ("error".equals(expect.get("kind"))) errors++;
                    Map<String, Object> out = new LinkedHashMap<>(c);
                    out.remove("messagePattern");
                    out.put("expect", expect);
                    cases.add(out);
                    timings.put(id, Math.round(ms[0] * 10000) / 10000.0);
                }
                Map<String, Object> oracle = new LinkedHashMap<>();
                oracle.put("language", "java");
                oracle.put("package", name);
                oracle.put("version", version);
                oracle.put("commit", commit);
                oracle.put("runtime", "java " + System.getProperty("java.version"));
                oracle.put("driver", DRIVER);
                oracle.put("recordedAt", Instant.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS).toString());
                Map<String, Object> fixture = new LinkedHashMap<>();
                fixture.put("schema", 1L);
                fixture.put("unit", unit);
                fixture.put("oracle", oracle);
                fixture.put("cases", cases);
                writeFile(ws.resolve("fixtures").resolve(unit).resolve("oracle.json"), fixture);
                Map<String, Object> t = new LinkedHashMap<>();
                t.put("unit", unit);
                t.put("cases", timings);
                writeFile(ws.resolve("oracle").resolve("timings").resolve(unit + ".json"), t);
                System.out.println(unit + ": recorded " + cases.size() + " cases (" + errors + " errors) -> fixtures/" + unit + "/oracle.json");
            }
        } catch (OracleError e) {
            System.err.println("oracle: " + e.getMessage());
            System.exit(2);
        } catch (Exception e) {
            System.err.println("oracle: " + e);
            System.exit(2);
        }
        System.exit(0);
    }
}
