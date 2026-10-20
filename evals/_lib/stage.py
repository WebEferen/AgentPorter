#!/usr/bin/env python3
"""Build an AgentPorter workspace at a given stage in the current directory, for eval scaffolds.

Usage: python3 evals/_lib/stage.py <stage> [--license SPDX]
Stages run the real porter.py commands where they can, and only shortcut the parts an agent normally
writes (reports, deps decisions, state transitions)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTER = [sys.executable, str(ROOT / "scripts" / "porter.py")]
ORACLE = ROOT / "knowledge" / "oracles" / "python" / "oracle.py"
CWD = Path.cwd()
WS = CWD / ".porter"

CORE_PY = '''import re
import unicodedata

_SPACE = re.compile(r"\\s+")
_NON_WORD = re.compile(r"[^\\w\\s-]")


class TextkitError(ValueError):
    pass


def _clean(text):
    if not isinstance(text, str):
        raise TextkitError(f"expected str, got {type(text).__name__}")
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def slug(text, separator="-", max_length=0):
    """Lower-case, drop punctuation, join words with the separator."""
    cleaned = _NON_WORD.sub("", _clean(text).lower())
    out = _SPACE.sub(separator, cleaned)
    if max_length and len(out) > max_length:
        out = out[:max_length].rstrip(separator)
    return out


def ratio_label(part, whole):
    """Format part/whole as a percentage with one decimal."""
    if whole == 0:
        raise TextkitError("whole must not be zero")
    return f"{part / whole:.1%}"


def ascii_fold(text):
    from text_unidecode import unidecode
    return unidecode(_clean(text))


class Tokenizer:
    def __init__(self, lowercase=True):
        self.lowercase = lowercase

    def tokens(self, text):
        words = _clean(text).split(" ")
        return [w.lower() if self.lowercase else w for w in words if w]
'''

TESTS_PY = '''from textkit import slug, ratio_label, Tokenizer


def test_slug():
    assert slug("Hello, World!") == "hello-world"
    assert slug("a  b", separator="_") == "a_b"


def test_ratio():
    assert ratio_label(1, 3) == "33.3%"


def test_tokens():
    assert Tokenizer(lowercase=False).tokens(" A b ") == ["A", "b"]
'''

WC2_C = r'''#include <stdio.h>
#include <string.h>

static const char *USAGE =
    "Usage: wc2 [OPTIONS] [FILE]\n\n"
    "Count lines, words and characters.\n\n"
    "Options:\n"
    "  -l, --lines     print only the line count\n"
    "  -w, --words     print only the word count\n"
    "  -h, --help      show this help\n"
    "      --version   print the version\n\n"
    "Exit codes:\n"
    "  0  OK\n"
    "  1  file not found\n"
    "  2  bad option\n";

int main(int argc, char **argv) {
    int mode = 0;
    const char *file = NULL;
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "-l") || !strcmp(a, "--lines")) mode = 1;
        else if (!strcmp(a, "-w") || !strcmp(a, "--words")) mode = 2;
        else if (!strcmp(a, "-h") || !strcmp(a, "--help")) { fputs(USAGE, stdout); return 0; }
        else if (!strcmp(a, "--version")) { puts("wc2 0.3.1"); return 0; }
        else if (a[0] == '-' && a[1]) { fprintf(stderr, "wc2: unknown option %s\n", a); return 2; }
        else file = a;
    }
    FILE *in = stdin;
    if (file && !(in = fopen(file, "rb"))) { fprintf(stderr, "wc2: %s: no such file\n", file); return 1; }
    long lines = 0, words = 0, chars = 0;
    int c, inword = 0;
    while ((c = fgetc(in)) != EOF) {
        chars++;
        if (c == '\n') lines++;
        if (c == ' ' || c == '\n' || c == '\t' || c == '\r' || c == '\v' || c == '\f') inword = 0;
        else if (!inword) { inword = 1; words++; }
    }
    if (mode == 1) printf("%ld\n", lines);
    else if (mode == 2) printf("%ld\n", words);
    else printf("%ld %ld %ld\n", lines, words, chars);
    return 0;
}
'''


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(list(args), cwd=CWD, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(f"stage: {' '.join(args)} failed ({r.returncode})\n{r.stdout}\n{r.stderr}\n")
        sys.exit(1)
    return r


def porter(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(*PORTER, *args, check=check)


def write(rel: str, text: str) -> Path:
    p = CWD / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def read_json(rel: str):
    return json.loads((CWD / rel).read_text(encoding="utf-8"))


def write_json(rel: str, data) -> None:
    write(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def edit_state(fn) -> None:
    state = read_json(".porter/state.json")
    fn(state)
    write_json(".porter/state.json", state)


def git_init() -> None:
    if not (CWD / ".git").exists():
        run("git", "init", "-q", "-b", "main")
        run("git", "config", "user.email", "eval@example.invalid")
        run("git", "config", "user.name", "eval")


# ---------------------------------------------------------------- stages

def s_src(lic: str) -> None:
    git_init()
    write("upstream/textkit/pyproject.toml",
          f'[project]\nname = "textkit"\nversion = "1.4.0"\nlicense = "{lic}"\nrequires-python = ">=3.9"\n'
          'dependencies = ["text-unidecode>=1.3"]\n')
    write("upstream/textkit/textkit/__init__.py",
          'from .core import Tokenizer, TextkitError, ascii_fold, ratio_label, slug\n\n__version__ = "1.4.0"\n')
    write("upstream/textkit/textkit/core.py", CORE_PY)
    write("upstream/textkit/tests/test_core.py", TESTS_PY)
    write("upstream/textkit/LICENSE", f"{lic} license text placeholder for the eval fixture\n")


def s_init(lic: str, target: bool = True) -> None:
    s_src(lic)
    args = ["init", "--source", "upstream/textkit", "--name", "textkit-ts"]
    if target:
        args += ["--to", "typescript"]
    porter(*args)


def s_surveyed(lic: str, target: bool = True) -> None:
    s_init(lic, target)
    porter("state", "preflight", "survey")
    porter("survey", "--write")
    write(".porter/survey.md", "# Survey\n\ntextkit 1.4.0: one module (`textkit.core`), a slug function, a "
          "percentage formatter, an ASCII folder backed by text-unidecode and a tokenizer class. "
          "Risk: regex, unicode normalization, float formatting.\n")
    porter("state", "postflight", "survey")


DEPS = {
    "schema": 1,
    "source": {"language": "python", "manifest": "pyproject.toml", "lockfile": None},
    "target": {"language": "typescript", "registry": "npm"},
    "dependencies": [{
        "name": "text-unidecode", "version": ">=1.3", "scope": "runtime", "direct": True,
        "role": "runtime-library",
        "usedSurface": {"symbols": ["unidecode"], "callSites": 1, "modules": ["textkit/core.py"]},
        "decision": "MAP",
        "candidate": {"name": "any-ascii", "registry": "npm", "license": "ISC",
                      "coverage": "unidecode() maps to anyAscii(); transliteration tables differ for some scripts"},
        "confidence": "MEDIUM",
        "notes": "only ascii_fold uses it",
        "verified": {"status": "VERIFIED", "registryLookup": True, "fetchedAt": "2026-10-20T10:00:00Z"},
    }],
}


def s_deps_done(lic: str) -> None:
    s_surveyed(lic)
    write_json(".porter/deps.json", DEPS)
    write(".porter/deps.md", "# Dependencies\n\n| Dependency | Decision | Candidate | Confidence |\n| --- | --- | --- | --- |\n"
          "| text-unidecode | MAP | any-ascii (npm, ISC) | MEDIUM |\n")

    def f(st):
        st["phases"]["deps"].update(status="DONE", gate="approved", at="2026-10-20T10:05:00Z")
    edit_state(f)
    with (WS / "decisions.md").open("a", encoding="utf-8") as fh:
        fh.write("\n## 2026-10-20 deps gate approved\n\napproved as proposed\n")


CASES = {
    "schema": 1, "unit": "core", "call": "textkit.core:slug",
    "cases": [
        {"case": "slug-basic", "input": {"args": ["Hello, World!"], "kwargs": {}}},
        {"case": "slug-separator", "input": {"args": ["a  b c"], "kwargs": {"separator": "_"}}},
        {"case": "slug-unicode", "input": {"args": ["Zoë Ünïcode"], "kwargs": {}}},
        {"case": "slug-max", "input": {"args": ["one two three"], "kwargs": {"max_length": 7}}},
        {"case": "slug-type-error", "input": {"args": [42], "kwargs": {}}},
        {"case": "ratio-third", "call": "textkit.core:ratio_label", "input": {"args": [1, 3], "kwargs": {}}},
        {"case": "ratio-zero", "call": "textkit.core:ratio_label", "input": {"args": [1, 0], "kwargs": {}}},
        {"case": "tokens-lower", "call": "textkit.core:Tokenizer.tokens",
         "input": {"init": {"args": [], "kwargs": {}}, "args": [" A b  C "], "kwargs": {}}},
    ],
}


def s_contract_done(lic: str) -> None:
    s_deps_done(lic)
    porter("decompose", "--draft")
    plan = read_json(".porter/plan.json")
    unit_of = {s: u["id"] for u in plan["units"] for s in u["symbols"]}
    survey = read_json(".porter/survey.json")
    symbols = []
    for m in survey["modules"]:
        if m["role"] != "source":
            continue
        for s in m["symbols"]:
            if not s.get("public"):
                continue
            sid = f"{m['id']}:{s['name']}"
            entry = {"id": sid, "name": s["name"], "module": m["id"], "kind": s.get("kind", "function"),
                     "inScope": s["name"] != "ascii_fold", "unit": unit_of.get(sid)}
            if s["name"] == "ascii_fold":
                entry["reason"] = "needs the text-unidecode tables; covered by the any-ascii mapping and its own tests"
                entry["unit"] = None
            symbols.append(entry)
    units = sorted({s["unit"] for s in symbols if s["inScope"] and s["unit"]})
    write_json(".porter/contract/api.json", {"schema": 1, "source": {"language": "python", "package": "textkit",
                                                                     "version": "1.4.0"}, "symbols": symbols})
    write(".porter/contract/contract.md", "# Contract\n\nPublic surface of textkit 1.4.0: `slug`, `ratio_label`, "
          "`Tokenizer.tokens`, `TextkitError`. Errors: `TextkitError` (a ValueError) for non-string input and a "
          "zero denominator.\n")
    write_json(".porter/contract/error-map.json", {"schema": 1, "map": {"TextkitError": "TextkitError"}})
    for u in units:
        spec = dict(CASES, unit=u)
        write_json(f".porter/oracle/cases/{u}.json", spec)
    porter("fixtures", "expand")
    for u in units:
        run(sys.executable, str(ORACLE), "--workspace", ".porter", "--unit", u)

    def f(st):
        st["phases"]["contract"].update(status="DONE", at="2026-10-20T10:20:00Z")
    edit_state(f)


def s_strategy_done(lic: str) -> None:
    s_contract_done(lic)
    porter("decompose", "--force")
    write(".porter/strategy.md", "# Strategy\n\nContract port of every unit. Idiom map: Python `re` to "
          "`RegExp` with the `u` flag, `unicodedata.normalize` to `String.prototype.normalize`, f-string "
          "percent formatting to a helper that matches Python's rounding.\n")

    def f(st):
        st["phases"]["strategy"].update(status="IN_PROGRESS")
    edit_state(f)
    porter("state", "plan-sync")

    def g(st):
        st["phases"]["strategy"].update(status="DONE", gate="approved", at="2026-10-20T10:30:00Z")
    edit_state(g)


def first_unit() -> str:
    return read_json(".porter/plan.json")["order"][0]


def s_implement_mid(lic: str) -> None:
    s_strategy_done(lic)
    porter("state", "preflight", "implement")
    u = first_unit()
    porter("state", "unit", "set", u, "IN_PROGRESS")
    for task in ("scaffold", "implement", "mark-divergences", "port-tests"):
        porter("state", "unit", "task", u, task)
    write("package.json", json.dumps({"name": "textkit-ts", "version": "0.0.0", "type": "module",
                                      "scripts": {"test": "vitest run"}}, indent=2) + "\n")
    write(f"src/{u}.ts", 'export class TextkitError extends Error {\n  constructor(message: string) {\n'
          '    super(message);\n    this.name = "TextkitError";\n  }\n}\n\n'
          'export function slug(text: string, separator = "-", maxLength = 0): string {\n'
          '  const cleaned = text.normalize("NFKC").replace(/\\s+/gu, " ").trim().toLowerCase()\n'
          '    .replace(/[^\\p{L}\\p{N}_\\s-]/gu, "");\n'
          '  let out = cleaned.replace(/\\s+/gu, separator);\n'
          '  if (maxLength && out.length > maxLength) out = out.slice(0, maxLength).replace(new RegExp(`${separator}+$`), "");\n'
          '  return out;\n}\n\n'
          'export function ratioLabel(part: number, whole: number): string {\n'
          '  if (whole === 0) throw new TextkitError("whole must not be zero");\n'
          '  return `${((part / whole) * 100).toFixed(1)}%`;\n}\n\n'
          'export class Tokenizer {\n  constructor(readonly lowercase = true) {}\n\n'
          '  tokens(text: string): string[] {\n'
          '    const words = text.normalize("NFKC").replace(/\\s+/gu, " ").trim().split(" ");\n'
          '    return words.filter((w) => w).map((w) => (this.lowercase ? w.toLowerCase() : w));\n  }\n}\n')
    write(f"test/{u}.test.ts", 'import { describe, expect, it } from "vitest";\nimport { slug } from "../src/' + u + '.js";\n\n'
          'describe("slug", () => {\n  it("joins words [ref: tests/test_core.py::test_slug]", () => {\n'
          '    expect(slug("Hello, World!")).toBe("hello-world");\n    expect(slug("a  b", "_")).toBe("a_b");\n  });\n});\n')
    write(f".porter/reports/units/{u}.md", f"# Unit {u}\n\n- [x] read-contract\n- [x] scaffold\n- [x] implement\n"
          "- [x] mark-divergences\n- [ ] port-tests (in progress: slug tests ported, ratio and tokens pending)\n")


def s_implement_stale(lic: str) -> None:
    s_strategy_done(lic)

    def f(st):
        st["phases"]["strategy"]["status"] = "STALE"
        st["stale"] = ["strategy"]
    edit_state(f)


def s_implement_reviewed(lic: str) -> None:
    s_implement_mid(lic)
    u = first_unit()
    for task in ("wire-fixtures", "green"):
        porter("state", "unit", "task", u, task)
    porter("state", "unit", "set", u, "IMPLEMENTED")
    for task in ("review", "apply-findings"):
        porter("state", "unit", "task", u, task)
    porter("state", "unit", "set", u, "REVIEWED")


def _actuals(u: str, broken: set[str]) -> None:
    fx = read_json(f".porter/fixtures/{u}/oracle.json")
    results = []
    for c in fx["cases"]:
        actual = dict(c["expect"])
        if c["case"] in broken:
            actual = {"kind": "value", "value": "33.4%"} if actual.get("kind") == "value" else actual
        results.append({"case": c["case"], "actual": actual, "durationMs": 0.05})
    write_json(f".porter/runs/r1/{u}.json", {"schema": 1, "unit": u, "runner": {"language": "typescript"},
                                             "startedAt": "2026-10-20T11:00:00Z", "results": results})


def s_verify_gap(lic: str) -> None:
    s_implement_reviewed(lic)
    _actuals(first_unit(), {"ratio-third"})


def s_verify_divergence(lic: str) -> None:
    s_verify_gap(lic)
    u = first_unit()
    write_json(".porter/divergences.json", {"schema": 1, "divergences": [{
        "id": "ratio-rounding", "unit": u, "summary": "ratio_label rounds half up instead of half to even",
        "rationale": "matches the JavaScript toFixed behavior the consumers already rely on",
        "cases": ["ratio-third"], "approvedBy": None}]})


def s_artifact_src(lic: str) -> None:
    git_init()
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if not cc:
        sys.exit("stage: artifact stages need a C compiler (cc, clang or gcc)")
    (CWD / "bin").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "wc2.c"
        src.write_text(WC2_C, encoding="utf-8")
        run(cc, "-O2", "-o", str(CWD / "bin" / "wc2"), str(src))


def s_artifact(lic: str, authorized: bool = False) -> None:
    s_artifact_src(lic)
    args = ["init", "--source", "bin/wc2", "--to", "go", "--name", "wc2-go"]
    if authorized:
        args += ["--authorization", "The user wrote wc2 and owns it."]
    porter(*args)


STAGES = {
    "empty": lambda lic: None,
    "src": s_src,
    "init": s_init,
    "init-notarget": lambda lic: s_init(lic, target=False),
    "surveyed": s_surveyed,
    "surveyed-notarget": lambda lic: s_surveyed(lic, target=False),
    "deps-done": s_deps_done,
    "contract-done": s_contract_done,
    "strategy-done": s_strategy_done,
    "implement-mid": s_implement_mid,
    "implement-stale": s_implement_stale,
    "implement-reviewed": s_implement_reviewed,
    "verify-gap": s_verify_gap,
    "verify-divergence": s_verify_divergence,
    "artifact-src": s_artifact_src,
    "artifact": s_artifact,
    "artifact-authorized": lambda lic: s_artifact(lic, authorized=True),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=sorted(STAGES))
    ap.add_argument("--license", default="MIT")
    args = ap.parse_args()
    STAGES[args.stage](args.license)
    return 0


if __name__ == "__main__":
    sys.exit(main())
