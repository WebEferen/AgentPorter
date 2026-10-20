"""Build .porter/oracle/cases/*.json for compare-versions 6.1.1.

Harvests every table row of the pinned test suite (by source line), adds hand-written edge cases and seeded
generator blocks. Also writes expectations.json (scratch) with what each harvested test asserts, so the
recorded fixtures can be cross-checked against the suite.
"""
import json
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
WS = Path(sys.argv[2])
OUT_EXPECT = Path(sys.argv[3])

CV = "compare-versions:compareVersions"
CMP = "compare-versions:compare"
SAT = "compare-versions:satisfies"
VAL = "compare-versions:validate"
STRICT = "compare-versions:validateStrict"
UNDEF = {"$undefined": True}

expectations = {}  # case name -> {"kind": "value"|"error"|"sort", ...}
unrepresentable = []


def lines(rel):
    return (SRC / rel).read_text(encoding="utf-8").split("\n")


def case(name, call, args, origin=None, tags=None, normalize=None):
    c = {"case": name, "call": call, "input": {"args": args}}
    if origin:
        c["origin"] = origin
    if tags:
        c["tags"] = tags
    if normalize:
        c["normalize"] = normalize
    return c


def ref(file, line):
    return f"reference-test:{file}::L{line}"


# ------------------------------------------------------------------ harvest test/compare.ts
sat_cases, val_cases = [], []
cmp_lines = lines("test/compare.ts")
row3 = re.compile(r"^\s*\['([^']*)', '([^']*)', (-?\d)\],?\s*$")
row4 = re.compile(r"^\s*\['([^']*)', '([^']*)', '([^']*)', (true|false)\],?\s*$")
n_cv = n_cmp = 0
for i, text in enumerate(cmp_lines, start=1):
    m = row3.match(text)
    if m:
        name = f"ref-compare-L{i:03d}"
        sat_cases.append(case(name, CV, [m[1], m[2]], ref("test/compare.ts", i), ["harvested"]))
        expectations[name] = {"kind": "value", "value": int(m[3])}
        n_cv += 1
        continue
    m = row4.match(text)
    if m:
        name = f"ref-compare-L{i:03d}"
        sat_cases.append(case(name, CMP, [m[1], m[2], m[3]], ref("test/compare.ts", i), ["harvested"]))
        expectations[name] = {"kind": "value", "value": m[4] == "true"}
        n_cmp += 1
assert n_cv == 112 and n_cmp == 16, (n_cv, n_cmp)

# describe('invalid input'): compareVersions(v1, v1) throws (test/compare.ts:157-163)
invalid_rows = [
    (157, 42, "Invalid argument expected string"),
    (158, {}, "Invalid argument expected string"),
    (159, [], "Invalid argument expected string"),
    (160, None, None),  # () => undefined
    (161, "6.3.", "Invalid argument not valid semver"),
    (162, "1.2.3a", "Invalid argument not valid semver"),
    (163, "1.2.-3a", "Invalid argument not valid semver"),
]
for line, v, pattern in invalid_rows:
    assert cmp_lines[line - 1].strip().startswith("["), line
    if pattern is None:
        unrepresentable.append(f"test/compare.ts::L{line} compareVersions(() => undefined, () => undefined): function value")
        continue
    ns = not isinstance(v, str)
    name = f"ref-compare-L{line:03d}" + ("-nonstring" if ns else "")
    sat_cases.append(case(name, CV, [v, v], ref("test/compare.ts", line), ["harvested"] + (["nonstring"] if ns else [])))
    expectations[name] = {"kind": "error", "pattern": pattern}

# runThrows (test/compare.ts:232-267)
throw_rows = [
    (233, None, "Invalid operator type, expected string but got "),
    (234, UNDEF, "Invalid operator type, expected string but got "),
    (240, True, "Invalid operator type, expected string but got boolean"),
    (246, 1, "Invalid operator type, expected string but got number"),
    (252, {"foo": "bar"}, "Invalid operator type, expected string but got object"),
    (258, "FUNCTION", None),
    (264, "", "Invalid operator, expected one of "),
    (265, "foo", "Invalid operator, expected one of "),
    (266, "> ", "Invalid operator, expected one of "),
]
for line, op, pattern in throw_rows:
    if pattern is None:
        unrepresentable.append(f"test/compare.ts::L{line} compare('3.2.1', '3.2.0', () => {{}}): function value")
        continue
    ns = not isinstance(op, str)
    name = f"ref-compare-L{line:03d}" + ("-nonstring" if ns else "")
    sat_cases.append(case(name, CMP, ["3.2.1", "3.2.0", op], ref("test/compare.ts", line), ["harvested"] + (["nonstring"] if ns else [])))
    expectations[name] = {"kind": "error", "pattern": pattern}

# it('should throw the same Errors thrown by the main function') loops 7 rows (test/compare.ts:269-285)
loop_rows = [(272, 42, "Invalid argument expected string"), (273, {}, "Invalid argument expected string"),
             (274, [], "Invalid argument expected string"), (275, None, None),
             (276, "6.3.", "Invalid argument not valid semver"), (277, "1.2.3a", "Invalid argument not valid semver"),
             (278, "1.2.-3a", "Invalid argument not valid semver")]
for line, v, pattern in loop_rows:
    if pattern is None:
        unrepresentable.append(f"test/compare.ts::L269 row {line} compare(() => undefined, () => undefined, '>'): function value")
        continue
    ns = not isinstance(v, str)
    name = f"ref-compare-L269-r{line}" + ("-nonstring" if ns else "")
    sat_cases.append(case(name, CMP, [v, v, ">"], ref("test/compare.ts", 269), ["harvested"] + (["nonstring"] if ns else [])))
    expectations[name] = {"kind": "error", "pattern": pattern}

# ------------------------------------------------------------------ harvest test/satisfies.ts
sat_row = re.compile(r"^\s*\['([^']*)', '([^']*)', (true|false)\],?\s*(//.*)?$")
n_sat = 0
for i, text in enumerate(lines("test/satisfies.ts"), start=1):
    m = sat_row.match(text)
    if m:
        name = f"ref-satisfies-L{i:03d}"
        sat_cases.append(case(name, SAT, [m[1], m[2]], ref("test/satisfies.ts", i), ["harvested"]))
        expectations[name] = {"kind": "value", "value": m[3] == "true"}
        n_sat += 1
assert n_sat == 98, n_sat

# ------------------------------------------------------------------ harvest test/sort.ts
sort_tests = [
    (5, ["1.2.3", "4.11.6", "4.2.0", "1.5.19", "1.5.5", "4.1.3", "2.3.1", "10.5.5", "11.3.0"],
     ["1.2.3", "1.5.5", "1.5.19", "2.3.1", "4.1.3", "4.2.0", "4.11.6", "10.5.5", "11.3.0"]),
    (31, ["1.0", "1.0.0", "1.0.1"], ["1.0", "1.0.0", "1.0.1"]),
    (37, ["1.0.0", "1.0.1", "1.0.1-gamma", "1.0.1-alpha"], ["1.0.0", "1.0.1-alpha", "1.0.1-gamma", "1.0.1"]),
]
sort_meta = {}
for line, inp, out in sort_tests:
    names = {}
    for a in range(len(inp)):
        for b in range(len(inp)):
            if a == b:
                continue
            name = f"ref-sort-L{line:03d}-p{a}-{b}"
            sat_cases.append(case(name, CV, [inp[a], inp[b]], ref("test/sort.ts", line), ["harvested", "sort-comparator"]))
            names[f"{a},{b}"] = name
    sort_meta[f"test/sort.ts::L{line}"] = {"input": inp, "expected": out, "pairs": names}

# ------------------------------------------------------------------ harvest test/validate.ts
vl = lines("test/validate.ts")
js_literals = {"undefined": UNDEF, "null": None, "42": 42, "{}": {}, "[]": []}
for i in range(7, 28):
    text = vl[i - 1].strip()
    m = re.match(r"^\[(.*), (true|false)\],?$", text)
    assert m, (i, text)
    lit = m[1]
    if lit.startswith("'"):
        v, ns = lit.strip("'"), False
    elif lit in js_literals:
        v, ns = js_literals[lit], True
    else:
        unrepresentable.append(f"test/validate.ts::L{i} validate({lit}): function value")
        continue
    name = f"ref-validate-L{i:03d}" + ("-nonstring" if ns else "")
    val_cases.append(case(name, VAL, [v], ref("test/validate.ts", i), ["harvested"] + (["nonstring"] if ns else [])))
    expectations[name] = {"kind": "value", "value": m[2] == "true"}
n_strict = 0
for lo, hi, expected in ((39, 69, True), (79, 119, False)):
    for i in range(lo, hi + 1):
        m = re.match(r"^\s*'([^']*)',\s*$", vl[i - 1])
        assert m, (i, vl[i - 1])
        name = f"ref-validate-L{i:03d}"
        val_cases.append(case(name, STRICT, [m[1]], ref("test/validate.ts", i), ["harvested"]))
        expectations[name] = {"kind": "value", "value": expected}
        n_strict += 1
assert n_strict == 72, n_strict

# ------------------------------------------------------------------ hand-written edge cases
D400 = "9" * 400
edge_sat = []


def e(name, call, args, tags, normalize=None):
    edge_sat.append(case(name, call, args, "hand-written", tags, normalize))


# compareVersions: empty, whitespace, malformed, error precedence
e("edge-cv-empty-v1", CV, ["", "1.0.0"], ["empty", "error"])
e("edge-cv-empty-v2", CV, ["1.0.0", ""], ["empty", "error"])
e("edge-cv-leading-space", CV, [" 1.0.0", "1.0.0"], ["whitespace", "error"])
e("edge-cv-trailing-space", CV, ["1.0.0 ", "1.0.0"], ["whitespace", "error"])
e("edge-cv-trailing-newline", CV, ["1.0.0\n", "1.0.0"], ["regex-dollar", "error"])
e("edge-cv-both-invalid-v1-first", CV, ["foo", "bar"], ["error-precedence", "error"])
e("edge-cv-v2-invalid", CV, ["1.0.0", "bar"], ["error-precedence", "error"])
e("edge-cv-invalid-v1-nonstring-v2", CV, ["bar", 42], ["error-precedence", "nonstring", "error"])
e("edge-cv-nonstring-v2", CV, ["1.0.0", 42], ["nonstring", "error"])
e("edge-cv-nonstring-null", CV, [None, "1.0.0"], ["nonstring", "error"])
e("edge-cv-nonstring-undefined", CV, [UNDEF, "1.0.0"], ["nonstring", "error"])
e("edge-cv-nonstring-bool", CV, [True, "1.0.0"], ["nonstring", "error"])
e("edge-cv-nonstring-array-of-string", CV, [["1.0.0"], "1.0.0"], ["nonstring", "error"])
e("edge-cv-nonstring-missing-v2", CV, ["1.0.0"], ["nonstring", "arity", "error"])
e("edge-cv-five-segments", CV, ["1.0.0.0.0", "1"], ["malformed", "error"])
e("edge-cv-prerelease-needs-three-segments", CV, ["1.0-alpha", "1.0"], ["malformed", "error"])
e("edge-cv-prerelease-one-segment", CV, ["1-alpha", "1"], ["malformed", "error"])
e("edge-cv-build-needs-three-segments", CV, ["1.0+build", "1.0"], ["malformed", "error"])
e("edge-cv-empty-prerelease", CV, ["1.0.0-", "1.0.0"], ["malformed", "error"])
e("edge-cv-empty-build", CV, ["1.0.0+", "1.0.0"], ["malformed", "error"])
e("edge-cv-empty-identifier", CV, ["1.0.0-a..b", "1.0.0"], ["malformed", "error"])
e("edge-cv-star-in-prerelease", CV, ["1.0.0-*", "1.0.0"], ["malformed", "error"])
e("edge-cv-wildcard-first-x", CV, ["x", "1"], ["wildcard", "error"])
e("edge-cv-wildcard-first-star", CV, ["*", "1"], ["wildcard", "error"])
e("edge-cv-wildcard-first-segment", CV, ["x.1.0", "1.1.0"], ["wildcard", "error"])
e("edge-cv-message-quote", CV, ["1.0.0'x", "1.0.0"], ["error", "message"])
e("edge-cv-message-unicode", CV, ["ü", "1"], ["error", "message", "unicode"])
e("edge-cv-message-newline", CV, ["a\nb", "1"], ["error", "message"])
# prefixes accepted by the semver regex
e("edge-cv-prefix-gte", CV, [">=1.0.0", "1.0.0"], ["prefix"])
e("edge-cv-prefix-tilde", CV, ["~1.2.3", "1.2.3"], ["prefix"])
e("edge-cv-prefix-caret", CV, ["^1.2.3", "1.2.4"], ["prefix"])
e("edge-cv-prefix-lt", CV, ["<1", "1"], ["prefix"])
e("edge-cv-prefix-eq-v", CV, ["=v1.0.0", "1.0.0"], ["prefix"])
e("edge-cv-prefix-vv", CV, ["vv1", "1"], ["prefix"])
e("edge-cv-prefix-upper-v", CV, ["V1.0.0", "1.0.0"], ["prefix", "case-insensitive"])
e("edge-cv-prefix-mixed-run", CV, ["v^~<>=1.0.0", "1.0.0"], ["prefix"])
e("edge-cv-prefix-bang", CV, ["!1.0.0", "1.0.0"], ["prefix", "error"])
e("edge-cv-prefix-word", CV, ["ver1.0.0", "1.0.0"], ["prefix", "error"])
e("edge-cv-prefix-space", CV, ["v 1.0.0", "1.0.0"], ["prefix", "error"])
# case sensitivity and string order
e("edge-cv-upper-wildcard", CV, ["1.X.0", "1.5.0"], ["wildcard", "case-insensitive"])
e("edge-cv-prerelease-case-order", CV, ["1.0.0-RC.1", "1.0.0-rc.1"], ["string-order"])
e("edge-cv-prerelease-upper-before-lower", CV, ["1.0.0-Beta", "1.0.0-alpha"], ["string-order"])
e("edge-cv-build-upper", CV, ["1.0.0+BUILD.5", "1.0.0"], ["build"])
e("edge-cv-build-differs", CV, ["1.0.0+a", "1.0.0+b"], ["build"])
# wildcards
e("edge-cv-wildcard-fourth", CV, ["1.0.0.x", "1.0.0.5"], ["wildcard"])
e("edge-cv-wildcard-prerelease-x", CV, ["1.0.0-x", "1.0.0-alpha"], ["wildcard", "quirk:wildcard"])
e("edge-cv-wildcard-prerelease-upper-x", CV, ["1.0.0-X", "1.0.0-beta"], ["wildcard", "quirk:wildcard"])
e("edge-cv-wildcard-prerelease-vs-release", CV, ["1.0.0-x", "1.0.0"], ["wildcard"])
e("edge-cv-nontransitive-a", CV, ["1.x", "1.5"], ["wildcard", "quirk:nontransitive"])
e("edge-cv-nontransitive-b", CV, ["1.x", "1.7"], ["wildcard", "quirk:nontransitive"])
e("edge-cv-nontransitive-c", CV, ["1.5", "1.7"], ["wildcard", "quirk:nontransitive"])
e("edge-cv-nontransitive-star-a", CV, ["2.*.*", "2.0.9"], ["wildcard", "quirk:nontransitive"])
e("edge-cv-nontransitive-star-b", CV, ["2.*.*", "2.9.0"], ["wildcard", "quirk:nontransitive"])
e("edge-cv-wildcard-then-missing", CV, ["1.2.3", "1.x"], ["wildcard", "quirk:missing-zero"])
e("edge-cv-wildcard-then-missing-eq", CV, ["1.2.0", "1.x"], ["wildcard", "quirk:missing-zero"])
# missing identifiers count as '0'
e("edge-cv-missing-identifier-zero", CV, ["1.0.0-alpha", "1.0.0-alpha.0"], ["quirk:missing-zero"])
e("edge-cv-missing-identifier-00", CV, ["1.0.0-alpha", "1.0.0-alpha.00"], ["quirk:missing-zero"])
e("edge-cv-identifier-0-vs-00", CV, ["1.0.0-0", "1.0.0-00"], ["quirk:parseint"])
e("edge-cv-prerelease-0-vs-release", CV, ["1.0.0-0", "1.0.0"], ["prerelease"])
e("edge-cv-release-vs-prerelease-0", CV, ["1.0.0", "1.0.0-0"], ["prerelease"])
e("edge-cv-identifier-alpha-vs-missing", CV, ["1.0.0-alpha.beta", "1.0.0-alpha"], ["quirk:missing-zero", "mixed-type"])
# parseInt prefix parsing
e("edge-cv-parseint-prefix-equal", CV, ["1.0.0-10a", "1.0.0-10b"], ["quirk:parseint"])
e("edge-cv-parseint-prefix-gt", CV, ["1.0.0-10a", "1.0.0-9"], ["quirk:parseint"])
e("edge-cv-parseint-numeric-vs-alnum", CV, ["1.0.0-11", "1.0.0-10a"], ["quirk:parseint"])
e("edge-cv-parseint-numeric-vs-alnum-semver", CV, ["1.0.0-11", "1.0.0-1a"], ["quirk:parseint", "semver-divergence"])
e("edge-cv-parseint-hyphenated", CV, ["1.0.0-1-2", "1.0.0-1-3"], ["quirk:parseint"])
e("edge-cv-parseint-hex-like", CV, ["1.0.0-0x10", "1.0.0-0"], ["quirk:parseint"])
e("edge-cv-parseint-exponent-like", CV, ["1.0.0-1e3", "1.0.0-2"], ["quirk:parseint"])
e("edge-cv-mixed-alpha-vs-number", CV, ["1.0.0-alpha", "1.0.0-10"], ["mixed-type"])
e("edge-cv-mixed-number-vs-alpha", CV, ["1.0.0-10", "1.0.0-alpha"], ["mixed-type"])
e("edge-cv-negative-identifier", CV, ["1.0.0--5", "1.0.0-0"], ["quirk:parseint", "negative"])
e("edge-cv-negative-identifiers-order", CV, ["1.0.0--5", "1.0.0--10"], ["quirk:parseint", "negative"])
e("edge-cv-negative-subidentifier", CV, ["1.0.0-alpha.-1", "1.0.0-alpha"], ["quirk:parseint", "negative", "quirk:missing-zero"])
e("edge-cv-hyphen-string-vs-letter", CV, ["1.0.0--a", "1.0.0-a"], ["string-order"])
# JS Number -> String in mixed comparisons
e("edge-cv-tostring-negative-zero", CV, ["1.0.0--0", "1.0.0--a"], ["leak:number-to-string"])
e("edge-cv-tostring-zero-vs-hyphen", CV, ["1.0.0-0", "1.0.0--a"], ["leak:number-to-string"])
e("edge-cv-tostring-infinity-vs-upper", CV, ["1.0.0-" + D400, "1.0.0-Alpha"], ["leak:number-to-string", "quirk:float64", "large"])
e("edge-cv-tostring-infinity-vs-lower", CV, ["1.0.0-" + D400, "1.0.0-alpha"], ["leak:number-to-string", "quirk:float64", "large"])
e("edge-cv-tostring-finite-vs-upper", CV, ["1.0.0-" + "9" * 20, "1.0.0-Alpha"], ["leak:number-to-string"])
e("edge-cv-tostring-neg-infinity-vs-upper", CV, ["1.0.0--" + D400, "1.0.0--A"], ["leak:number-to-string", "quirk:float64", "large"])
e("edge-cv-tostring-exponent-vs-letter", CV, ["1.0.0-1" + "0" * 21, "1.0.0-e"], ["leak:number-to-string"])
# float64 precision
e("edge-cv-2pow53-major", CV, ["9007199254740993", "9007199254740992"], ["quirk:float64", "boundary"])
e("edge-cv-2pow53-major-full", CV, ["9007199254740993.0.0", "9007199254740992.0.0"], ["quirk:float64", "boundary"])
e("edge-cv-2pow53-minor", CV, ["1.9007199254740993", "1.9007199254740992"], ["quirk:float64", "boundary"])
e("edge-cv-2pow53-prerelease", CV, ["1.0.0-9007199254740993", "1.0.0-9007199254740992"], ["quirk:float64", "boundary"])
e("edge-cv-2pow53-exact-step", CV, ["9007199254740994", "9007199254740992"], ["quirk:float64", "boundary"])
e("edge-cv-2pow53-below", CV, ["9007199254740991", "9007199254740990"], ["quirk:float64", "boundary"])
e("edge-cv-u64-overflow", CV, ["18446744073709551616", "18446744073709551615"], ["quirk:float64", "boundary"])
e("edge-cv-u64-max-vs-small", CV, ["18446744073709551615", "1"], ["quirk:float64", "boundary"])
e("edge-cv-infinity-equal", CV, [D400, "9" * 399 + "8"], ["quirk:float64", "large"])
e("edge-cv-infinity-vs-one", CV, [D400, "1"], ["quirk:float64", "large"])
e("edge-cv-1e308-vs-infinity", CV, ["1" + "0" * 308, "1" + "0" * 309], ["quirk:float64", "boundary"])
e("edge-cv-leading-zeros-long", CV, ["00000000000000000000001", "1"], ["leading-zero"])
e("edge-cv-long-prerelease", CV, ["1.0.0-" + ".".join(["a"] * 1000), "1.0.0-" + ".".join(["a"] * 1000)], ["large"])
e("edge-cv-long-prerelease-last-differs", CV, ["1.0.0-" + ".".join(["a"] * 999 + ["b"]), "1.0.0-" + ".".join(["a"] * 1000)], ["large"])
e("edge-cv-huge-segment", CV, ["1." + "7" * 10000, "1.1"], ["large", "quirk:float64"])
# unicode and JS regex dialect
e("edge-cv-unicode-arabic-indic-digits", CV, ["١.٠.٠", "1.0.0"], ["leak:regex-unicode-digit", "unicode", "error"])
e("edge-cv-unicode-fullwidth-digits", CV, ["１.２.３", "1.2.3"], ["leak:regex-unicode-digit", "unicode", "error"])
e("edge-cv-unicode-mixed-digit", CV, ["1١.0.0", "1.0.0"], ["leak:regex-unicode-digit", "unicode", "error"])
e("edge-cv-unicode-prerelease-letter", CV, ["1.0.0-é", "1.0.0"], ["unicode", "error"])
e("edge-cv-unicode-kelvin-sign", CV, ["1.0.0-K", "1.0.0-k"], ["leak:regex-case-fold", "unicode", "error"])
e("edge-cv-unicode-long-s", CV, ["1.0.0-ſ", "1.0.0-s"], ["leak:regex-case-fold", "unicode", "error"])
e("edge-cv-unicode-dotless-i", CV, ["1.0.0-ı", "1.0.0-i"], ["leak:regex-case-fold", "unicode", "error"])
e("edge-cv-unicode-fullwidth-v", CV, ["ｖ1.0.0", "1.0.0"], ["unicode", "error"])
e("edge-cv-unicode-build", CV, ["1.0.0+é", "1.0.0"], ["unicode", "error"])

# compare: every operator on less, equal, greater
for (a, b, tag) in (("1.0.0", "2.0.0", "lt"), ("1.0.0", "1.0.0", "eq"), ("2.0.0", "1.0.0", "gt")):
    for op, opname in ((">", "gt"), (">=", "gte"), ("=", "eq"), ("<=", "lte"), ("<", "lt"), ("!=", "ne")):
        e(f"edge-cmp-{tag}-{opname}", CMP, [a, b, op], ["operator-table"])
for op, slug in (("==", "eqeq"), ("===", "eqeqeq"), ("<>", "ltgt"), ("!", "bang"), ("=>", "eqgt"), ("=<", "eqlt"),
                 ("gt", "word"), (" >", "leading-space"), (">= ", "trailing-space"), ("^", "caret"), ("~", "tilde"),
                 ("GT", "upper-word"), ("＞", "fullwidth-gt")):
    e(f"edge-cmp-invalid-op-{slug}", CMP, ["1.0.0", "1.0.0", op], ["invalid-operator", "error"])
e("edge-cmp-op-type-zero-nonstring", CMP, ["1.0.0", "1.0.0", 0], ["nonstring", "typeof", "error"])
e("edge-cmp-op-type-array-nonstring", CMP, ["1.0.0", "1.0.0", [">"]], ["nonstring", "typeof", "error"])
e("edge-cmp-op-type-nan-nonstring", CMP, ["1.0.0", "1.0.0", {"$float": "nan"}], ["nonstring", "typeof", "error"])
e("edge-cmp-op-type-bigint-nonstring", CMP, ["1.0.0", "1.0.0", {"$int": "1"}], ["nonstring", "typeof", "error"])
e("edge-cmp-op-missing-nonstring", CMP, ["1.0.0", "1.0.0"], ["nonstring", "arity", "typeof", "error"])
e("edge-cmp-precedence-op-before-versions", CMP, ["foo", "bar", "nope"], ["error-precedence", "error"])
e("edge-cmp-precedence-op-type-before-version-type-nonstring", CMP, [42, "1.0.0", None], ["error-precedence", "nonstring", "error"])
e("edge-cmp-precedence-version-type-nonstring", CMP, [42, "1.0.0", ">"], ["error-precedence", "nonstring", "error"])
e("edge-cmp-precedence-v1-before-v2", CMP, ["foo", 42, ">"], ["error-precedence", "nonstring", "error"])
e("edge-cmp-wildcard-ne", CMP, ["3.3.3", "3.x.x", "!="], ["wildcard"])
e("edge-cmp-wildcard-missing-eq", CMP, ["1.2.3", "1.x", "="], ["wildcard", "quirk:missing-zero"])
e("edge-cmp-prefix-gte-eq", CMP, [">=1.0.0", "1.0.0", "="], ["prefix"])
e("edge-cmp-precision-eq", CMP, ["9007199254740993.0.0", "9007199254740992.0.0", "="], ["quirk:float64"])

# satisfies
S = SAT
for name, args, tags in [
    ("edge-sat-npm-caret-prerelease-above", ["1.2.4-beta", "^1.2.3"], ["quirk:prerelease-range", "npm-divergence"]),
    ("edge-sat-npm-caret-prerelease-same", ["1.2.3-beta", "^1.2.3"], ["quirk:prerelease-range", "npm-divergence"]),
    ("edge-sat-npm-tilde-prerelease-same", ["1.2.3-beta", "~1.2.3"], ["quirk:prerelease-range", "npm-divergence"]),
    ("edge-sat-prerelease-gte", ["1.2.3-beta", ">=1.2.3"], ["prerelease"]),
    ("edge-sat-prerelease-eq", ["1.2.3-beta", "1.2.3"], ["prerelease"]),
    ("edge-sat-prerelease-next-major", ["2.0.0-alpha", "^1.2.3"], ["prerelease"]),
    ("edge-sat-prerelease-next-minor-tilde", ["1.3.0-alpha", "~1.2.3"], ["prerelease"]),
    ("edge-sat-release-vs-prerelease-range", ["1.2.3", "^1.2.3-beta"], ["quirk:prerelease-range", "npm-divergence"]),
    ("edge-sat-release-above-prerelease-range", ["1.2.4", "^1.2.3-beta"], ["quirk:prerelease-range", "npm-divergence"]),
    ("edge-sat-prerelease-lower-than-range", ["1.2.3-alpha", "^1.2.3-beta"], ["prerelease"]),
    ("edge-sat-prerelease-equal-range", ["1.2.3-beta", "^1.2.3-beta"], ["prerelease"]),
    ("edge-sat-prerelease-missing-identifier", ["1.2.3-beta", "~1.2.3-beta.2"], ["prerelease", "quirk:missing-zero"]),
    ("edge-sat-prerelease-comparator", ["1.2.3-beta", ">=1.2.3-alpha"], ["prerelease"]),
    ("edge-sat-fourth-segment-tilde", ["1.2.3.4", "~1.2.3.5"], ["quirk:fourth-segment"]),
    ("edge-sat-fourth-segment-caret", ["1.2.3.4", "^1.2.3.5"], ["quirk:fourth-segment"]),
    ("edge-sat-fourth-segment-eq", ["1.2.3.4", "1.2.3.5"], ["quirk:fourth-segment"]),
    ("edge-sat-fourth-segment-lte", ["1.2.3.9", "<=1.2.3.5"], ["quirk:fourth-segment"]),
    ("edge-sat-range-v-prefix", ["1.2.3", "v1.2.3"], ["prefix"]),
    ("edge-sat-range-eq-v-prefix", ["1.2.3", "=v1.2.3"], ["prefix"]),
    ("edge-sat-range-caret-v-prefix", ["1.2.3", "^v1.2.0"], ["prefix"]),
    ("edge-sat-range-upper-v-prefix", ["1.2.3", "V1.2.3"], ["prefix", "case-insensitive"]),
    ("edge-sat-op-eqgt", ["1.2.3", "=>1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-tilde-gt", ["1.2.3", "~>1.2"], ["invalid-operator", "error"]),
    ("edge-sat-op-eqeq", ["1.2.3", "==1.2.3"], ["invalid-operator", "error"]),
    ("edge-sat-op-ltgt", ["1.2.3", "<>1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-caret-tilde", ["1.2.3", "^~1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-caret-caret", ["1.2.3", "^^1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-gtgt", ["1.2.3", ">>1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-eqlt", ["1.2.3", "=<1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-bang-eq", ["1.2.3", "!=1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-op-gte-lt", ["1.2.3", ">=<1.0.0"], ["invalid-operator", "error"]),
    ("edge-sat-empty-range", ["1.2.3", ""], ["empty", "error"]),
    ("edge-sat-space-range", ["1.2.3", " "], ["empty", "whitespace", "error"]),
    ("edge-sat-star-range", ["1.2.3", "*"], ["wildcard", "error"]),
    ("edge-sat-x-range", ["1.2.3", "x"], ["wildcard", "error"]),
    ("edge-sat-xxx-range", ["1.2.3", "x.x.x"], ["wildcard", "error"]),
    ("edge-sat-one-x-nonzero-patch", ["1.2.3", "1.x"], ["wildcard", "quirk:missing-zero"]),
    ("edge-sat-one-x-zero-patch", ["1.2.0", "1.x"], ["wildcard", "quirk:missing-zero"]),
    ("edge-sat-one-star-star", ["1.2.3", "1.*.*"], ["wildcard"]),
    ("edge-sat-caret-00-in", ["0.0.5", "^0.0"], ["caret-zero"]),
    ("edge-sat-caret-00-out", ["0.1.0", "^0.0"], ["caret-zero"]),
    ("edge-sat-caret-0-in", ["0.5.0", "^0"], ["caret-zero"]),
    ("edge-sat-caret-0-out", ["1.0.0", "^0"], ["caret-zero"]),
    ("edge-sat-caret-003-exact", ["0.0.3", "^0.0.3"], ["caret-zero"]),
    ("edge-sat-caret-003-prerelease", ["0.0.3-beta", "^0.0.3"], ["caret-zero", "quirk:prerelease-range"]),
    ("edge-sat-caret-023-in", ["0.2.9", "^0.2.3"], ["caret-zero"]),
    ("edge-sat-caret-023-below", ["0.2.2", "^0.2.3"], ["caret-zero"]),
    ("edge-sat-caret-000-major-differs", ["1.0.0", "^0.0.0"], ["caret-zero"]),
    ("edge-sat-caret-000-minor-above", ["0.5.0", "^0.0.0"], ["caret-zero", "npm-divergence"]),
    ("edge-sat-caret-1x", ["1.5.0", "^1.x"], ["wildcard"]),
    ("edge-sat-caret-1-upper-x", ["1.5.0", "^1.X"], ["wildcard"]),
    ("edge-sat-tilde-12x", ["1.2.9", "~1.2.x"], ["wildcard"]),
    ("edge-sat-tilde-major-only", ["1.9.9", "~1"], ["tilde"]),
    ("edge-sat-ws-after-op-double", ["1.2.4", ">  1.2.3"], ["whitespace"]),
    ("edge-sat-ws-after-op-tab", ["1.2.4", ">\t1.2.3"], ["whitespace"]),
    ("edge-sat-ws-after-op-nbsp", ["1.2.4", ">= 1.2.3"], ["whitespace", "leak:regex-whitespace"]),
    ("edge-sat-ws-after-op-bom", ["1.2.4", ">=﻿1.2.3"], ["whitespace", "leak:regex-whitespace"]),
    ("edge-sat-ws-after-op-line-separator", ["1.2.4", ">= 1.2.3"], ["whitespace", "leak:regex-whitespace"]),
    ("edge-sat-ws-tab-between", ["1.2.4", ">=1.2.3\t<1.2.5"], ["whitespace", "error"]),
    ("edge-sat-ws-nbsp-between", ["1.2.4", ">=1.2.3 <1.2.5"], ["whitespace", "error"]),
    ("edge-sat-ws-newline-between", ["1.2.4", ">=1.2.3\n<1.2.5"], ["whitespace", "error"]),
    ("edge-sat-ws-space-newline-space", ["1.2.4", ">=1.2.3 \n <1.2.5"], ["whitespace"]),
    ("edge-sat-ws-space-newline", ["1.2.4", ">=1.2.3 \n<1.2.5"], ["whitespace"]),
    ("edge-sat-ws-newline-space", ["1.2.4", ">=1.2.3\n <1.2.5"], ["whitespace"]),
    ("edge-sat-ws-space-tab", ["1.2.4", ">=1.2.3 \t<1.2.5"], ["whitespace"]),
    ("edge-sat-ws-trim-bom", ["1.2.4", "﻿^1.2.0 "], ["whitespace", "leak:trim"]),
    ("edge-sat-ws-trim-nbsp", ["1.2.4", " ^1.2.0 "], ["whitespace", "leak:trim"]),
    ("edge-sat-ws-bom-no-space", ["1.2.4", "﻿^1.2.0"], ["whitespace", "error"]),
    ("edge-sat-ws-trailing-space", ["1.2.7", "1.2.7 "], ["whitespace"]),
    ("edge-sat-or-empty-both", ["1.0.0", "||"], ["or", "error"]),
    ("edge-sat-or-trailing-short-circuit", ["1.0.0", "1.0.0||"], ["or", "lazy"]),
    ("edge-sat-or-trailing-evaluated", ["2.0.0", "1.0.0||"], ["or", "lazy", "error"]),
    ("edge-sat-or-leading-empty", ["1.0.0", "|| 1.0.0"], ["or", "error"]),
    ("edge-sat-single-pipe", ["1.0.0", "1.0.0 | 2.0.0"], ["or", "error"]),
    ("edge-sat-triple-pipe-first", ["1.0.0", "1.0.0|||2.0.0"], ["or", "lazy"]),
    ("edge-sat-triple-pipe-second", ["2.0.0", "1.0.0|||2.0.0"], ["or", "error"]),
    ("edge-sat-lazy-or-skips-invalid", ["1.0.0", "1.0.0 || foo"], ["lazy"]),
    ("edge-sat-lazy-or-reaches-invalid", ["2.0.0", "1.0.0 || foo"], ["lazy", "error"]),
    ("edge-sat-lazy-and-skips-invalid", ["0.5.0", ">=1.0.0 foo"], ["lazy"]),
    ("edge-sat-lazy-and-reaches-invalid", ["1.5.0", ">=1.0.0 foo"], ["lazy", "error"]),
    ("edge-sat-hyphen-split-limit-out", ["2.5.0", "1.0.0 - 2.0.0 - 3.0.0"], ["quirk:split-limit"]),
    ("edge-sat-hyphen-split-limit-in", ["1.5.0", "1.0.0 - 2.0.0 - 3.0.0"], ["quirk:split-limit"]),
    ("edge-sat-hyphen-extra-spaces", ["1.5.0", "1.0.0  -  2.0.0"], ["hyphen", "whitespace"]),
    ("edge-sat-hyphen-missing-lower", ["1.5.0", " - 2.0.0"], ["hyphen", "error"]),
    ("edge-sat-hyphen-missing-upper", ["1.5.0", "1.0.0 - "], ["hyphen", "error"]),
    ("edge-sat-hyphen-partial-in", ["1.5.0", "1.0 - 2"], ["hyphen"]),
    ("edge-sat-hyphen-partial-upper-npm", ["2.5.0", "1.0 - 2"], ["hyphen", "npm-divergence"]),
    ("edge-sat-hyphen-caret-lower", ["1.5.0", "^1.0.0 - 2.0.0"], ["hyphen", "invalid-operator", "error"]),
    ("edge-sat-hyphen-prerelease-lower", ["1.5.0", "1.0.0-alpha - 2.0.0"], ["hyphen", "prerelease"]),
    ("edge-sat-hyphen-with-or", ["2.0.0", "1.0.0 - 1.5.0 || 2.0.0"], ["hyphen", "or"]),
    ("edge-sat-no-space-hyphen", ["1.5.0", "1.0.0-1.0.0"], ["hyphen", "prerelease"]),
    ("edge-sat-lt-2x-below", ["1.9.0", "<2.x"], ["wildcard"]),
    ("edge-sat-lt-2x-inside", ["2.5.0", "<2.x"], ["wildcard"]),
    ("edge-sat-invalid-version-caret", ["foo", "^1.0.0"], ["error"]),
    ("edge-sat-invalid-version-gt", ["foo", ">1.0.0"], ["error"]),
    ("edge-sat-invalid-range-caret", ["1.0.0", "^foo"], ["error"]),
    ("edge-sat-invalid-range-gt", ["1.0.0", ">foo"], ["error"]),
    ("edge-sat-unicode-version", ["١.٢.٣", "^1.0.0"], ["unicode", "leak:regex-unicode-digit", "error"]),
    ("edge-sat-unicode-range", ["1.2.3", "^١.٠.٠"], ["unicode", "leak:regex-unicode-digit", "error"]),
    ("edge-sat-nonstring-version-number", [42, "1.0.0"], ["nonstring", "error"]),
    ("edge-sat-nonstring-version-null-caret", [None, "^1.0.0"], ["nonstring", "error"]),
    ("edge-sat-nonstring-version-undefined-or", [UNDEF, "1.0.0 || 2.0.0"], ["nonstring", "error"]),
]:
    e(name, S, args, tags)
v8 = ["ignore-message"]
e("edge-sat-nonstring-range-number", S, ["1.0.0", 42], ["nonstring", "leak:v8-message", "error"], v8)
e("edge-sat-nonstring-range-null", S, ["1.0.0", None], ["nonstring", "leak:v8-message", "error"], v8)
e("edge-sat-nonstring-range-undefined", S, ["1.0.0", UNDEF], ["nonstring", "leak:v8-message", "error"], v8)
e("edge-sat-nonstring-range-array", S, ["1.0.0", ["^1.0.0"]], ["nonstring", "leak:v8-message", "error"], v8)

edge_val = []


def ev(name, call, args, tags):
    edge_val.append(case(name, call, args, "hand-written", tags))


for name, v, tags in [
    ("empty", "", ["empty"]), ("v-only", "v", ["malformed"]), ("v1", "v1", ["prefix"]),
    ("vv-prefix", "vv1.0.0", ["prefix"]), ("v-eq-prefix", "v=1.0.0", ["prefix"]), ("v-gte-prefix", "v>=1", ["prefix"]),
    ("upper-v", "V1.0.0", ["prefix", "case-sensitive"]), ("caret-prefix", "^1.0.0", ["prefix"]),
    ("tilde-prefix", "~1.0.0", ["prefix"]), ("one", "1", ["partial"]), ("one-zero", "1.0", ["partial"]),
    ("four-segments", "1.0.0.0", ["chromium"]), ("five-segments", "1.0.0.0.0", ["malformed"]),
    ("one-x", "1.x", ["wildcard"]), ("upper-x-star", "1.X.*", ["wildcard"]), ("x-first", "x.1", ["wildcard"]),
    ("empty-prerelease", "1.0.0-", ["malformed"]), ("prerelease-x", "1.0.0-x", ["wildcard"]),
    ("prerelease-dot", "1.0.0-.", ["malformed"]), ("prerelease-empty-identifier", "1.0.0-a..b", ["malformed"]),
    ("empty-build", "1.0.0+", ["malformed"]), ("build", "1.0.0+build.1", ["build"]),
    ("build-two-segments", "1.0+build", ["malformed"]), ("prerelease-two-segments", "1.0-rc.1", ["readme"]),
    ("underscore", "1.0.0-rc_1", ["malformed"]), ("upper-prerelease", "1.0.0-RC.1", ["case-insensitive"]),
    ("trailing-newline", "1.0.0\n", ["regex-dollar"]), ("leading-space", " 1.0.0", ["whitespace"]),
    ("trailing-space", "1.0.0 ", ["whitespace"]), ("fullwidth-digits", "１.２.３", ["leak:regex-unicode-digit", "unicode"]),
    ("arabic-indic-digits", "١.٢.٣", ["leak:regex-unicode-digit", "unicode"]),
    ("mixed-unicode-digit", "1١.0.0", ["leak:regex-unicode-digit", "unicode"]),
    ("kelvin-sign", "1.0.0-K", ["leak:regex-case-fold", "unicode"]),
    ("long-s", "1.0.0-ſ", ["leak:regex-case-fold", "unicode"]),
    ("e-acute", "1.0.0-é", ["unicode"]), ("huge-number", D400, ["large"]),
    ("leading-zeros", "01.02.03", ["leading-zero"]), ("readme-1-0", "1.0", ["readme"]), ("readme-1-x", "1.x", ["readme"]),
    ("readme-v1-02", "v1.02", ["readme"]), ("prerelease-and-build", "1.0.0-alpha+001", ["build"]),
    ("prerelease-zero", "1.0.0-0", ["prerelease"]), ("long-input", "1.0.0-" + "a" * 10000, ["large"]),
]:
    ev(f"edge-val-{name}", VAL, [v], tags)
for name, v in [("bool-nonstring", True), ("zero-nonstring", 0), ("nan-nonstring", {"$float": "nan"}),
                ("array-of-string-nonstring", ["1.0.0"]), ("object-nonstring", {"version": "1.0.0"})]:
    ev(f"edge-val-{name}", VAL, [v], ["nonstring"])
ev("edge-val-missing-arg-nonstring", VAL, [], ["nonstring", "arity"])
for name, v, tags in [
    ("empty", "", ["empty"]), ("zeros", "0.0.0", ["boundary"]), ("leading-zero-major", "00.0.0", ["leading-zero"]),
    ("prerelease-0", "1.2.3-0", ["prerelease"]), ("prerelease-00", "1.2.3-00", ["leading-zero"]),
    ("prerelease-0a", "1.2.3-0a", ["prerelease"]), ("prerelease-a-0", "1.2.3-a.0", ["prerelease"]),
    ("prerelease-a-00", "1.2.3-a.00", ["leading-zero"]), ("build-00", "1.2.3+00", ["build"]),
    ("v-prefix", "v1.2.3", ["prefix"]), ("trailing-newline", "1.2.3\n", ["regex-dollar"]),
    ("leading-space", " 1.2.3", ["whitespace"]), ("trailing-space", "1.2.3 ", ["whitespace"]),
    ("fullwidth-digits", "１.２.３", ["leak:regex-unicode-digit", "unicode"]),
    ("unicode-digit-in-major", "1١.2.3", ["leak:regex-unicode-digit", "unicode"]),
    ("unicode-digit-in-prerelease", "1.2.3-1١", ["leak:regex-unicode-digit", "unicode"]),
    ("unicode-digit-identifier", "1.2.3-١", ["leak:regex-unicode-digit", "unicode"]),
    ("e-acute", "1.2.3-é", ["unicode"]), ("kelvin-sign", "1.2.3-K", ["unicode"]),
    ("double-build", "1.2.3-alpha+build+x", ["malformed"]), ("hyphen-identifier", "1.2.3--", ["prerelease"]),
    ("empty-prerelease", "1.2.3-", ["malformed"]), ("empty-build", "1.2.3+", ["malformed"]),
    ("empty-prerelease-and-build", "1.2.3-+", ["malformed"]), ("u64-overflow", "18446744073709551616.0.0", ["large"]),
    ("wildcard", "1.2.x", ["wildcard"]), ("four-segments", "1.2.3.4", ["chromium"]),
    ("long-input", "1.2.3-" + "a" * 10000, ["large"]),
]:
    ev(f"edge-strict-{name}", STRICT, [v], tags)
for name, v in [("undefined-nonstring", UNDEF), ("null-nonstring", None), ("number-nonstring", 42),
                ("object-nonstring", {}), ("bool-nonstring", True)]:
    ev(f"edge-strict-{name}", STRICT, [v], ["nonstring"])

# ------------------------------------------------------------------ seeded generators
def gint(lo, hi):
    return {"$gen": "int", "min": lo, "max": hi}


def gstr(alpha, lo, hi):
    return {"$gen": "string", "alphabet": alpha, "min": lo, "max": hi}


def choice(*opts):
    return {"$gen": "choice", "of": list(opts)}


def concat(*parts):
    return {"$gen": "concat", "parts": list(parts)}


PREFIX = choice("", "", "", "", "v", "V", "=", ">=", "^", "~", "vv")
NUM = choice(gint(0, 3), gint(0, 3), gint(0, 12), gstr("digits", 1, 3))
SEG = choice(NUM, NUM, NUM, "x", "X", "*")
IDENT = choice(gint(0, 12), gstr("lower", 1, 5), gstr("0123456789abx-", 1, 4), "alpha", "beta", "rc", "x")
PRE = choice("", "", concat("-", IDENT), concat("-", IDENT, ".", IDENT), concat("-", IDENT, ".", IDENT, ".", IDENT))
BUILD = choice("", "", "", concat("+", gstr("0123456789abcdef", 1, 6)))
VERSION = choice(
    concat(PREFIX, NUM),
    concat(PREFIX, NUM, ".", SEG),
    concat(PREFIX, NUM, ".", SEG, ".", SEG, PRE, BUILD),
    concat(PREFIX, NUM, ".", SEG, ".", SEG, PRE, BUILD),
    concat(PREFIX, NUM, ".", SEG, ".", SEG, ".", SEG, PRE, BUILD),
)
PLAIN = choice(concat(gint(0, 3), ".", gint(0, 3), ".", gint(0, 3)),
               concat(gint(0, 3), ".", gint(0, 3), ".", gint(0, 3), "-", IDENT),
               concat(gint(0, 3), ".", gint(0, 3)), concat(gint(0, 3)))
PARTIAL = choice(concat(gint(0, 3)), concat(gint(0, 3), ".", choice(gint(0, 3), "x")),
                 concat(gint(0, 3), ".", gint(0, 3), ".", choice(gint(0, 3), "x", "*")),
                 concat(gint(0, 3), ".", gint(0, 3), ".", gint(0, 3), "-", IDENT))
OP = choice("", "", "^", "~", ">", ">=", "<", "<=", "=", "> ", ">= ", "<  ")
COMPARATOR = concat(OP, PARTIAL)
RANGE = choice(
    COMPARATOR, COMPARATOR,
    concat(COMPARATOR, " ", COMPARATOR),
    concat(PARTIAL, " - ", PARTIAL),
    concat(COMPARATOR, " || ", COMPARATOR),
    concat(COMPARATOR, " ", COMPARATOR, " || ", COMPARATOR),
)
PRE_IDENTS = concat(gstr("0123456789-abxAB", 1, 4), choice("", concat(".", gstr("0123456789-abxAB", 1, 4))))
JUNK = "0123456789.vVxX*-+abz^~<>= "
STRICT_NUM = choice(gint(0, 20), gstr("digits", 1, 3))
STRICT_IDENT = choice(gint(0, 20), gstr("digits", 1, 3), gstr("abzAZ-09", 1, 5), gstr("ab_.", 1, 3))
STRICT_VERSION = choice(
    concat(STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM),
    concat(STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM, "-", STRICT_IDENT),
    concat(STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM, "-", STRICT_IDENT, ".", STRICT_IDENT),
    concat(STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM, "+", gstr("abc019-.", 1, 6)),
    concat(STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM, "-", STRICT_IDENT, "+", gstr("abc019-", 1, 6)),
    concat(STRICT_NUM, ".", STRICT_NUM),
    concat(choice("v", " ", "", "="), STRICT_NUM, ".", STRICT_NUM, ".", STRICT_NUM),
)
UNICODE_JUNK = "0123456789.-+vxa١٢３K \n"
UD = gstr("1234567890123456789١٢３", 1, 2)
UI = gstr("0123456789abzAZ-١Kſé", 1, 3)
UVERSION = choice(concat(UD, ".", UD, ".", UD), concat(UD, ".", UD, ".", UD, "-", UI),
                  concat(UD, ".", UD, ".", UD, "+", UI), concat("v", UD, ".", UD), gstr(UNICODE_JUNK, 0, 10))

gen_sat = [
    {"name": "gen-cv-grammar", "call": CV, "seed": 61101, "count": 400, "args": [VERSION, VERSION]},
    {"name": "gen-cv-prerelease", "call": CV, "seed": 61102, "count": 400,
     "args": [concat("1.0.0-", PRE_IDENTS), concat("1.0.0-", PRE_IDENTS)]},
    {"name": "gen-cv-bignum", "call": CV, "seed": 61103, "count": 100,
     "args": [gstr("digits", 15, 22), gstr("digits", 15, 22)]},
    {"name": "gen-cv-2pow53", "call": CV, "seed": 61108, "count": 100,
     "args": [concat("900719925474099", gstr("digits", 1, 1), ".0"), concat("900719925474099", gstr("digits", 1, 1), ".0")]},
    {"name": "gen-cv-2pow53-prerelease", "call": CV, "seed": 61109, "count": 50,
     "args": [concat("1.0.0-900719925474099", gstr("digits", 1, 1)), concat("1.0.0-900719925474099", gstr("digits", 1, 1))]},
    {"name": "gen-cv-junk", "call": CV, "seed": 61104, "count": 200, "args": [gstr(JUNK, 0, 12), "1.0.0"]},
    {"name": "gen-compare-ops", "call": CMP, "seed": 61105, "count": 300,
     "args": [VERSION, VERSION, choice(">", ">=", "=", "<=", "<", "!=", ">", ">=", "=", "<=", "<", "!=", "==", "=>", "", " >")]},
    {"name": "gen-sat-ranges", "call": SAT, "seed": 61106, "count": 600, "args": [PLAIN, RANGE]},
    {"name": "gen-sat-junk", "call": SAT, "seed": 61107, "count": 300,
     "args": ["1.2.3", gstr("0123456789.xX*^~<>=|- v", 0, 15)]},
]
gen_val = [
    {"name": "gen-validate-grammar", "call": VAL, "seed": 61201, "count": 300,
     "args": [choice(VERSION, VERSION, gstr(JUNK, 0, 12))]},
    {"name": "gen-strict-grammar", "call": STRICT, "seed": 61202, "count": 300, "args": [STRICT_VERSION]},
    {"name": "gen-validate-unicode", "call": VAL, "seed": 61203, "count": 200, "args": [UVERSION]},
    {"name": "gen-strict-unicode", "call": STRICT, "seed": 61204, "count": 200, "args": [UVERSION]},
]

specs = {
    "satisfies-satisfies": {"schema": 1, "unit": "satisfies-satisfies", "kind": "value",
                            "cases": sat_cases + edge_sat, "generate": gen_sat},
    "validate-validate": {"schema": 1, "unit": "validate-validate", "kind": "value",
                          "cases": val_cases + edge_val, "generate": gen_val},
}
for unit, spec in specs.items():
    names = [c["case"] for c in spec["cases"]]
    assert len(names) == len(set(names)), [n for n in names if names.count(n) > 1]
    path = WS / "oracle" / "cases" / f"{unit}.json"
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    harvested = sum(1 for c in spec["cases"] if c.get("origin", "").startswith("reference-test:"))
    print(f"{unit}: {len(spec['cases'])} explicit cases ({harvested} harvested, {len(spec['cases']) - harvested} hand-written), "
          f"{sum(g['count'] for g in spec['generate'])} generated")

OUT_EXPECT.write_text(json.dumps({"cases": expectations, "sort": sort_meta, "unrepresentable": unrepresentable},
                                 indent=1, ensure_ascii=False), encoding="utf-8")
print("unrepresentable:", *unrepresentable, sep="\n  ")
