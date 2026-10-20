"""Line-level signals: runtime coupling (io, runtime-welded, native) and risk tags.

Each entry is (signal name, compiled regex). Coupling severity: native > runtime-welded > io > pure.
Risk tags use the vocabulary in knowledge/pairs/TEMPLATE.md.
"""
from __future__ import annotations

import re

_C = re.compile

IO: dict[str, list[tuple[str, re.Pattern]]] = {
    "python": [
        ("fs", _C(r"\bopen\(|\bos\.(path\.|listdir|remove|unlink|makedirs|mkdir|walk|rename|stat)|\bpathlib\b|\bshutil\.|\bglob\.")),
        ("env", _C(r"\bos\.(environ|getenv)|\bsys\.argv")),
        ("process", _C(r"\bsubprocess\b|\bos\.(system|popen|exec)")),
        ("net", _C(r"\bsocket\b|\burllib\b|\bhttp\.client\b|\brequests\.|\bhttpx\.|\baiohttp\b")),
        ("stdio", _C(r"\bprint\(|\bsys\.(stdin|stdout|stderr)|\binput\(")),
        ("clock", _C(r"\btime\.(time|sleep|monotonic|perf_counter)\(|\b(datetime|date)\.(now|utcnow|today)\(")),
        ("random", _C(r"\brandom\.|\buuid\.uuid[14]|\bsecrets\.|\bos\.urandom")),
        ("db", _C(r"\bsqlite3\b|\bpsycopg|\bpymysql\b|\bsqlalchemy\b")),
    ],
    "javascript": [
        ("fs", _C(r"""require\(\s*['"](node:)?(fs|path|fs/promises)['"]|from\s+['"](node:)?(fs|path|fs/promises)['"]""")),
        ("process", _C(r"""['"](node:)?child_process['"]""")),
        ("net", _C(r"""['"](node:)?(net|http|https|dgram|tls)['"]|\bfetch\(|\bXMLHttpRequest\b|\baxios\b""")),
        ("env", _C(r"\bprocess\.(env|argv|cwd)")),
        ("stdio", _C(r"\bconsole\.(log|error|warn|info)\(|\bprocess\.(stdout|stderr|stdin)")),
        ("clock", _C(r"\bDate\.now\(|\bnew Date\(\s*\)|\bperformance\.now\(|\bsetTimeout\(|\bsetInterval\(")),
        ("random", _C(r"\bMath\.random\(|\bcrypto\.(randomUUID|getRandomValues|randomBytes)")),
    ],
    "go": [
        ("fs", _C(r'"(os|io/ioutil|io/fs|path/filepath)"|\bos\.(Open|Create|ReadFile|WriteFile|Remove|Mkdir)')),
        ("process", _C(r'"os/exec"')),
        ("net", _C(r'"(net|net/http|net/url)"')),
        ("env", _C(r"\bos\.(Getenv|Args|Environ|LookupEnv)")),
        ("stdio", _C(r"\bfmt\.(Print|Println|Printf)\(|\bos\.(Stdout|Stderr|Stdin)")),
        ("clock", _C(r"\btime\.(Now|Sleep|Since|After|Tick)\(")),
        ("random", _C(r'"(math/rand|crypto/rand)"')),
    ],
    "java": [
        ("fs", _C(r"\bjava\.(io|nio)\.|\bnew File\(|\bFiles\.")),
        ("net", _C(r"\bjava\.net\.|\bHttpClient\b|\bURLConnection\b")),
        ("process", _C(r"\bRuntime\.getRuntime\(\)|\bProcessBuilder\b")),
        ("env", _C(r"\bSystem\.(getenv|getProperty)\(")),
        ("stdio", _C(r"\bSystem\.(out|err|in)\b")),
        ("clock", _C(r"\bSystem\.(currentTimeMillis|nanoTime)\(|\bnew Date\(\s*\)|\b(Instant|LocalDateTime|LocalDate|ZonedDateTime)\.now\(")),
        ("random", _C(r"\bnew Random\(|\bMath\.random\(|\bUUID\.randomUUID\(|\bSecureRandom\b")),
    ],
    "php": [
        ("fs", _C(r"\b(fopen|file_get_contents|file_put_contents|unlink|mkdir|scandir|is_file|file_exists)\(")),
        ("net", _C(r"\bcurl_\w+\(|\bfsockopen\(|\bstream_socket_client\(")),
        ("process", _C(r"\b(exec|shell_exec|system|passthru|proc_open|popen)\(")),
        ("env", _C(r"\$_(SERVER|GET|POST|REQUEST|COOKIE|SESSION|ENV)\b|\bgetenv\(")),
        ("stdio", _C(r"^\s*(echo|print)\b|\bprintf\(|\bvar_dump\(")),
        ("clock", _C(r"\b(time|microtime|date|sleep)\(|\bnew \\?DateTime(Immutable)?\(\s*\)")),
        ("random", _C(r"\b(rand|mt_rand|random_int|random_bytes|uniqid)\(")),
        ("db", _C(r"\bnew \\?PDO\(|\bmysqli_")),
    ],
    "ruby": [
        ("fs", _C(r"\b(File|Dir|IO|FileUtils)\.")),
        ("net", _C(r"\bNet::HTTP\b|\bOpen3\b|\bopen-uri\b|\bFaraday\b")),
        ("process", _C(r"\bsystem\(|`[^`]+`|\bspawn\(|%x\{")),
        ("env", _C(r"\bENV\[|\bARGV\b")),
        ("stdio", _C(r"^\s*(puts|print|p)\b|\$stdout|\$stderr|\bSTDIN\b")),
        ("clock", _C(r"\bTime\.now\b|\bDate\.today\b|\bsleep\b")),
        ("random", _C(r"\brand\(|\bRandom\b|\bSecureRandom\b")),
    ],
    "csharp": [
        ("fs", _C(r"\bSystem\.IO\b|\bFile\.|\bDirectory\.")),
        ("net", _C(r"\bSystem\.Net\b|\bHttpClient\b")),
        ("process", _C(r"\bProcess\.Start\(")),
        ("env", _C(r"\bEnvironment\.")),
        ("stdio", _C(r"\bConsole\.")),
        ("clock", _C(r"\bDateTime(Offset)?\.(Now|UtcNow|Today)\b|\bStopwatch\b|\bThread\.Sleep\(")),
        ("random", _C(r"\bnew Random\(|\bGuid\.NewGuid\(")),
    ],
    "rust": [
        ("fs", _C(r"\bstd::fs\b|\bFile::(open|create)\(")),
        ("net", _C(r"\bstd::net\b|\breqwest::|\bhyper::")),
        ("process", _C(r"\bstd::process\b|\bCommand::new\(")),
        ("env", _C(r"\bstd::env\b|\benv::(var|args)\(")),
        ("stdio", _C(r"\b(e?println|e?print)!\(|\bstd::io::(stdin|stdout|stderr)")),
        ("clock", _C(r"\b(SystemTime|Instant)::now\(|\bthread::sleep\(")),
        ("random", _C(r"\brand::")),
    ],
}
IO["typescript"] = IO["javascript"]
IO["coffeescript"] = IO["javascript"]
IO["kotlin"] = IO["java"] + [("stdio", _C(r"\bprintln\(|\breadLine\("))]
IO["scala"] = IO["java"]

WELDED: dict[str, list[tuple[str, re.Pattern]]] = {
    "python": [
        ("dynamic-attrs", _C(r"\bdef __(getattr|getattribute|setattr)__\b")),
        ("metaclass", _C(r"\bmetaclass\s*=")),
        ("frame-introspection", _C(r"\bsys\._getframe\b|\binspect\.(currentframe|stack|getouterframes)")),
        ("eval", _C(r"(?<![\w.])(eval|exec)\(|\b__import__\(|\bimportlib\.import_module\(")),
        ("framework", _C(r"^\s*(from|import)\s+(django|flask|fastapi|starlette|tornado|celery|twisted|gevent|pyramid|kivy|tkinter|PyQt\d|PySide\d)\b")),
    ],
    "javascript": [
        ("eval", _C(r"(?<![\w.])eval\(|\bnew Function\(")),
        ("proxy-reflect", _C(r"\bnew Proxy\(|\bReflect\.")),
        ("prototype-mutation", _C(r"\b__proto__\b|\bObject\.setPrototypeOf\(|\b(Array|String|Object|Function|Number)\.prototype\.\w+\s*=")),
        ("dom", _C(r"\b(document|window)\.|\blocalStorage\b|\bjQuery\b|\$\(\s*['\"]")),
        ("framework", _C(r"""from\s+['"](react|react-dom|vue|@angular/[\w-]+|svelte|express|koa|@nestjs/[\w-]+)['"]|require\(\s*['"](react|vue|express|koa)['"]""")),
    ],
    "go": [
        ("reflect", _C(r'"reflect"')),
        ("unsafe", _C(r'"unsafe"|//go:linkname')),
    ],
    "java": [
        ("reflect", _C(r"\bjava\.lang\.reflect\b|\bClass\.forName\(|\.getDeclared(Method|Field|Constructor)s?\(")),
        ("framework", _C(r"@(Autowired|Component|Service|Repository|Controller|RestController|Entity|Inject)\b|\bjavax?\.persistence\b|\borg\.springframework\b")),
        ("unsafe", _C(r"\bsun\.misc\.Unsafe\b")),
    ],
    "php": [
        ("magic", _C(r"function\s+__(get|set|call|callStatic|isset|unset)\s*\(")),
        ("dynamic", _C(r"\bcall_user_func(_array)?\(|\$\$\w+|(?<![\w>])eval\(")),
        ("framework", _C(r"\b(Illuminate|Symfony\\Component\\HttpKernel|Laminas|Zend)\\|\badd_action\(|\badd_filter\(")),
    ],
    "ruby": [
        ("metaprogramming", _C(r"\bmethod_missing\b|\bdefine_method\b|\b(class|instance)_eval\b|\binstance_variable_(get|set)\b|\.send\(|\brespond_to_missing\?")),
        ("framework", _C(r"\bActiveRecord\b|\bRails\b|\bActionController\b|\bSinatra\b")),
        ("eval", _C(r"(?<![\w.])eval\(")),
    ],
    "csharp": [
        ("reflect", _C(r"\bSystem\.Reflection\b|\bActivator\.CreateInstance\b|\bdynamic\b")),
        ("framework", _C(r"\bMicrosoft\.AspNetCore\b|\bSystem\.Web\b|\bEntityFramework")),
    ],
}
WELDED["typescript"] = WELDED["javascript"]
WELDED["coffeescript"] = WELDED["javascript"]
WELDED["kotlin"] = WELDED["java"]

NATIVE: dict[str, list[tuple[str, re.Pattern]]] = {
    "python": [("ffi", _C(r"\bimport ctypes\b|\bfrom ctypes\b|\bcffi\b|\bcython\b|\bpybind11\b|\bPyO3\b"))],
    "javascript": [("ffi", _C(r"""['"](ffi-napi|node-addon-api|bindings|nan)['"]|\.node['"]\)"""))],
    "go": [("cgo", _C(r'^\s*import\s+"C"'))],
    "java": [("jni", _C(r"\bnative\s+\w+[\w<>\[\]]*\s+\w+\s*\(|\bSystem\.loadLibrary\("))],
    "php": [("ffi", _C(r"\bFFI::"))],
    "ruby": [("ffi", _C(r"\brequire\s+['\"](ffi|fiddle)['\"]|\bextend FFI::Library"))],
    "csharp": [("pinvoke", _C(r"\[DllImport\(|\bextern\s+static\b"))],
    "rust": [("ffi", _C(r'extern\s+"C"|\bbindgen\b'))],
}
NATIVE["typescript"] = NATIVE["javascript"]
NATIVE["kotlin"] = NATIVE["java"]

RISK: dict[str, list[tuple[str, re.Pattern]]] = {
    "python": [
        ("regex", _C(r"\bre\.\w+\(|\bregex\.\w+\(|\bre\.compile\(")),
        ("unicode", _C(r"\bunicodedata\b|\.normalize\(|\.casefold\(|\.isalnum\(|\.isalpha\(|\bunidecode\b")),
        ("encoding", _C(r"\.(encode|decode)\(|\bbytes\(|\bbytearray\(|\bcodecs\.")),
        ("float-format", _C(r"\bround\(|:\.\d+f|%\.\d+f|\bformat\(|\brepr\(|\bfloat\(")),
        ("numeric", _C(r"//|\bdivmod\(|\bDecimal\b|\bFraction\b|<<|>>|\bmath\.")),
        ("datetime", _C(r"\bdatetime\b|\btimedelta\b|\btzinfo\b|\bpytz\b|\bzoneinfo\b|\bstrftime\(|\bstrptime\(")),
        ("async", _C(r"\basync def\b|\bawait\b|\basyncio\b|\bthreading\b|\bmultiprocessing\b|\bconcurrent\.futures\b")),
        ("reflection", _C(r"\bgetattr\(|\bsetattr\(|\bhasattr\(|\b__dict__\b|\btype\(\w+\)\s*(is|==)")),
        ("locale", _C(r"\blocale\.|\bgettext\b")),
        ("mutability", _C(r"def \w+\([^)]*=\s*(\[\]|\{\}|set\(\))")),
        ("ordering", _C(r"\bsorted\(|\.sort\(|\bset\(|\bfrozenset\(")),
        ("error-model", _C(r"\braise\b|\bexcept\b")),
        ("nullability", _C(r"\bNone\b|\bOptional\[")),
    ],
    "javascript": [
        ("regex", _C(r"/[^/\n]+/[gimsuyd]*\.test\(|\.(match|replace|replaceAll|split|search)\(\s*/|\bnew RegExp\(|\.exec\(")),
        ("unicode", _C(r"\.normalize\(|\.codePointAt\(|\bfromCodePoint\(|\\u\{|\.toLocale(Lower|Upper)Case\(")),
        ("encoding", _C(r"\bBuffer\.|\bTextEncoder\b|\bTextDecoder\b|\bUint8Array\b|\batob\(|\bbtoa\(")),
        ("float-format", _C(r"\.toFixed\(|\.toPrecision\(|\bMath\.round\(|\bparseFloat\(|\bNumber\(")),
        ("numeric", _C(r"\bMath\.|\bparseInt\(|\bBigInt\b|>>>|\|\s*0\b|\bNumber\.(MAX|MIN)_SAFE_INTEGER|\bisNaN\(|\bisFinite\(")),
        ("datetime", _C(r"\bnew Date\(|\bDate\.(parse|UTC)\(|\bgetTimezoneOffset\(|\bmoment\b|\bdayjs\b|\bTemporal\.")),
        ("async", _C(r"\basync\b|\bawait\b|\bPromise\b|\.then\(|\bsetImmediate\(|\bprocess\.nextTick\(|\bEventEmitter\b")),
        ("reflection", _C(r"\btypeof\b|\binstanceof\b|\bObject\.(keys|entries|getOwnPropertyNames|defineProperty)\(|\bhasOwnProperty\(")),
        ("locale", _C(r"\bIntl\.|\.toLocale\w*\(|\blocaleCompare\(")),
        ("ordering", _C(r"\.sort\(|\bfor\s*\(\s*(var|let|const)\s+\w+\s+in\b|\bObject\.keys\(")),
        ("error-model", _C(r"\bthrow\b|\bcatch\s*\(|\bnew \w*Error\(")),
        ("nullability", _C(r"\bnull\b|\bundefined\b|\?\?|\?\.")),
    ],
    "go": [
        ("regex", _C(r'"regexp"')),
        ("unicode", _C(r'"unicode(/utf8|/utf16)?"|\brune\b|"golang\.org/x/text')),
        ("float-format", _C(r"\bstrconv\.(FormatFloat|ParseFloat)\(|%[0-9.]*[fgeFGE]\b|\bmath\.Round\(")),
        ("numeric", _C(r"\bint(8|16|32|64)?\(|\buint\w*\(|\bmath\.|\bbig\.|<<|>>")),
        ("datetime", _C(r'"time"')),
        ("async", _C(r"\bgo\s+\w+|\bchan\b|\bsync\.|\bselect\s*\{|\bcontext\.")),
        ("reflection", _C(r'"reflect"|\.\(type\)|interface\{\}|\bany\b')),
        ("error-model", _C(r"\berrors\.(New|Is|As)\(|\bfmt\.Errorf\(|\bpanic\(|\brecover\(")),
        ("ordering", _C(r"\brange\s+\w+|\bsort\.|\bslices\.Sort")),
        ("nullability", _C(r"\bnil\b")),
    ],
    "java": [
        ("regex", _C(r"\bPattern\.|\.matches\(|\.replaceAll\(|\.split\(")),
        ("unicode", _C(r"\bNormalizer\b|\bCharacter\.|\bcodePoint|\.toLowerCase\(\)|\.toUpperCase\(\)")),
        ("encoding", _C(r"\bStandardCharsets\b|\.getBytes\(|\bCharset\b|\bbyte\[\]")),
        ("float-format", _C(r"\bString\.format\(|\bDecimalFormat\b|\bDouble\.(parseDouble|toString)\(|\bMath\.round\(")),
        ("numeric", _C(r"\bBigDecimal\b|\bBigInteger\b|\bMath\.|>>>|\(int\)|\(long\)")),
        ("datetime", _C(r"\bjava\.time\b|\bjava\.util\.Date\b|\bCalendar\b|\bSimpleDateFormat\b|\bTimeZone\b")),
        ("async", _C(r"\bThread\b|\bExecutor|\bCompletableFuture\b|\bsynchronized\b|\bvolatile\b|\bjava\.util\.concurrent\b")),
        ("reflection", _C(r"\bgetClass\(\)|\binstanceof\b|\.class\b")),
        ("locale", _C(r"\bLocale\b")),
        ("ordering", _C(r"\bHashMap\b|\bHashSet\b|\bCollections\.sort\(|\.sort\(")),
        ("error-model", _C(r"\bthrows\b|\bthrow new\b|\bcatch\s*\(")),
        ("nullability", _C(r"\bnull\b|@Nullable|\bOptional\b")),
    ],
    "php": [
        ("regex", _C(r"\bpreg_\w+\(")),
        ("unicode", _C(r"\bmb_\w+\(|\biconv\(|\bNormalizer::|\butf8_(en|de)code\(|\btransliterator_")),
        ("encoding", _C(r"\bbase64_|\bbin2hex\(|\bpack\(|\bunpack\(")),
        ("float-format", _C(r"\bnumber_format\(|\bsprintf\(|\bround\(|\bfloatval\(|\(float\)")),
        ("numeric", _C(r"\bintdiv\(|\bfmod\(|\bPHP_INT_MAX\b|\bbc\w+\(|\bgmp_\w+\(|\(int\)")),
        ("datetime", _C(r"\bDateTime\b|\bstrtotime\(|\bdate\(|\bmktime\(|\bdate_default_timezone")),
        ("reflection", _C(r"\bReflection\w+\b|\bget_class\(|\bmethod_exists\(|\bproperty_exists\(|\binstanceof\b")),
        ("locale", _C(r"\bsetlocale\(|\bstrftime\(")),
        ("ordering", _C(r"\b(sort|usort|uasort|uksort|ksort|krsort|asort|arsort|rsort)\(")),
        ("mutability", _C(r"&\$\w+")),
        ("error-model", _C(r"\bthrow new\b|\bcatch\s*\(|\btrigger_error\(|@\w+\(")),
        ("nullability", _C(r"\bnull\b|\?\?|\?->|\bisset\(|\bempty\(")),
    ],
    "ruby": [
        ("regex", _C(r"=~|\.match\(|\.gsub\(|\.sub\(|\.scan\(|%r\{|/[^/\n]+/[imxo]*")),
        ("unicode", _C(r"\.unicode_normalize\b|\.encode\(|\.force_encoding\(|\.unpack\(")),
        ("float-format", _C(r"\bformat\(|\.round\(|\bsprintf\(|%\.\d+f")),
        ("numeric", _C(r"\.to_i\b|\.to_f\b|\bBigDecimal\b|\bRational\b|\.divmod\(|\.fdiv\(")),
        ("datetime", _C(r"\bTime\b|\bDate\b|\bDateTime\b|\.strftime\(")),
        ("reflection", _C(r"\.is_a\?|\.respond_to\?|\.class\b|\.kind_of\?")),
        ("mutability", _C(r"\.(push|<<|concat|merge!|update|gsub!|sub!|upcase!|downcase!)\b|\bfrozen_string_literal\b")),
        ("error-model", _C(r"\braise\b|\brescue\b|\bensure\b")),
        ("nullability", _C(r"\bnil\b|&\.")),
    ],
}
RISK["typescript"] = RISK["javascript"]
RISK["coffeescript"] = RISK["javascript"]
RISK["kotlin"] = RISK["java"]
RISK["csharp"] = RISK["java"]
RISK["rust"] = RISK["go"]

COUPLING_ORDER = ["pure", "io", "runtime-welded", "native"]


def scan_lines(language: str, lines: list[str]) -> dict[str, set[str]]:
    """Return {"io": {...}, "welded": {...}, "native": {...}, "risk": {...}} for these lines."""
    out: dict[str, set[str]] = {"io": set(), "welded": set(), "native": set(), "risk": set()}
    groups = (("io", IO), ("welded", WELDED), ("native", NATIVE), ("risk", RISK))
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "*", "/*")) and not stripped.startswith("#include"):
            continue
        for key, table in groups:
            for name, rx in table.get(language, ()):
                if name not in out[key] and rx.search(line):
                    out[key].add(name)
    if out["io"]:
        out["risk"].add("io")
    return out


def coupling_of(sig: dict[str, set[str]]) -> str:
    if sig["native"]:
        return "native"
    if sig["welded"]:
        return "runtime-welded"
    if sig["io"]:
        return "io"
    return "pure"

RISK_WEIGHTS = {
    "regex": 3, "unicode": 3, "datetime": 3, "async": 3, "float-format": 2, "numeric": 2,
    "encoding": 2, "locale": 2, "reflection": 2, "io": 2, "mutability": 1, "ordering": 1,
    "error-model": 1, "nullability": 0,
}


def risk_score(tags) -> int:
    return sum(RISK_WEIGHTS.get(t, 1) for t in set(tags))
