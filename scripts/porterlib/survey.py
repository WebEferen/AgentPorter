"""Survey a source project: languages, size, manifests, tooling, license, modules, symbols, graph."""
from __future__ import annotations

import argparse
import ast
import configparser
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import PorterError, emit, find_workspace, iter_files, nonblank_loc, now_iso, read_json, read_text_safe, write_json
from .graph import cycles as find_cycles
from .langs import AUX_DIR_NAMES, CLASS_LANGS, EXT_LANG, NODE_BUILTINS, TEST_DIR_NAMES
from .signals import coupling_of, risk_score, scan_lines

MANIFESTS = {
    "package.json": "npm", "package-lock.json": "npm-lock", "yarn.lock": "yarn-lock",
    "pnpm-lock.yaml": "pnpm-lock", "bower.json": "bower", "deno.json": "deno",
    "pyproject.toml": "pyproject", "setup.py": "setup.py", "setup.cfg": "setup.cfg", "Pipfile": "pipfile",
    "Pipfile.lock": "pipfile-lock", "poetry.lock": "poetry-lock", "uv.lock": "uv-lock",
    "go.mod": "go.mod", "Cargo.toml": "cargo", "Cargo.lock": "cargo-lock", "pom.xml": "maven",
    "build.gradle": "gradle", "build.gradle.kts": "gradle", "libs.versions.toml": "gradle-catalog",
    "composer.json": "composer", "composer.lock": "composer-lock", "Gemfile": "gemfile",
    "Gemfile.lock": "gemfile-lock", "packages.lock.json": "nuget-lock",
    "Directory.Packages.props": "nuget-central", "mix.exs": "mix", "mix.lock": "mix-lock",
}
MANIFEST_PATTERNS = [
    (re.compile(r"^(.*[._-])?requirements([._-].*)?\.txt$"), "requirements"),
    (re.compile(r".*\.gemspec$"), "gemspec"),
    (re.compile(r".*\.csproj$"), "csproj"),
]
PACKAGE_MANIFESTS = {"npm", "pyproject", "setup.py", "go.mod", "cargo", "maven", "gradle", "composer", "gemspec", "csproj", "mix"}
TOOLING = [
    (re.compile(r"^(tox\.ini|noxfile\.py)$"), "test-matrix"),
    (re.compile(r"^(pytest\.ini|conftest\.py)$"), "pytest"),
    (re.compile(r"^(\.flake8|ruff\.toml|\.ruff\.toml|\.pylintrc|pylintrc)$"), "python-lint"),
    (re.compile(r"^(mypy\.ini|pyrightconfig\.json)$"), "python-types"),
    (re.compile(r"^(\.eslintrc.*|eslint\.config\..*|\.jshintrc|\.jscsrc|tslint\.json)$"), "js-lint"),
    (re.compile(r"^(\.prettierrc.*|prettier\.config\..*|biome\.jsonc?)$"), "js-format"),
    (re.compile(r"^tsconfig.*\.json$"), "typescript"),
    (re.compile(r"^(jest|vitest|karma|ava)\.config\..*$|^\.mocharc.*$|^karma\.conf\.js$"), "js-test"),
    (re.compile(r"^(Gruntfile|gulpfile|webpack\.config|rollup\.config|vite\.config|babel\.config)\..*$|^\.babelrc$"), "js-build"),
    (re.compile(r"^(Makefile|Justfile|Taskfile\.ya?ml|Rakefile)$"), "task-runner"),
    (re.compile(r"^(Dockerfile|docker-compose\.ya?ml|compose\.ya?ml)$"), "container"),
    (re.compile(r"^(\.travis\.yml|\.gitlab-ci\.yml|azure-pipelines\.yml|Jenkinsfile|appveyor\.yml|\.drone\.yml)$"), "ci"),
    (re.compile(r"^(phpunit\.xml(\.dist)?|phpstan\.neon(\.dist)?|psalm\.xml|\.php-cs-fixer.*)$"), "php-tooling"),
    (re.compile(r"^(\.rubocop\.yml|\.rspec|\.standard\.yml)$"), "ruby-tooling"),
    (re.compile(r"^(\.golangci\.ya?ml|golangci\.ya?ml)$"), "go-lint"),
    (re.compile(r"^(rustfmt\.toml|\.rustfmt\.toml|clippy\.toml)$"), "rust-tooling"),
    (re.compile(r"^(detekt\.yml|checkstyle\.xml|\.editorconfig|\.pre-commit-config\.yaml)$"), "lint-config"),
]
LICENSE_FILE = re.compile(r"^(LICEN[CS]E|COPYING|UNLICENSE)([.-].*)?$", re.I)

TEST_FILE = re.compile(
    r"(^tests?\.([cm]?[jt]sx?|py|coffee)$|^test_.*\.py$|.*_test\.py$|.*_test\.go$|.*\.(test|spec)\.[cm]?[jt]sx?$|.*(Test|Tests|IT)\.(java|kt|cs)$|"
    r".*_spec\.rb$|.*_test\.rb$|.*Test\.php$|^test.*\.coffee$|.*_test\.exs$|.*\.t$)"
)
TEST_CASE = {
    "python": re.compile(r"^\s*(async\s+)?def\s+test\w*\s*\("),
    "javascript": re.compile(r"\b(it|test)\s*\(\s*['\"`]"),
    "typescript": re.compile(r"\b(it|test)\s*\(\s*['\"`]"),
    "coffeescript": re.compile(r"\b(it|test)\s*\(?\s*['\"]"),
    "go": re.compile(r"^func\s+Test\w*\("),
    "java": re.compile(r"@Test\b"),
    "kotlin": re.compile(r"@Test\b|\btest\(\"|\bshould\(\""),
    "php": re.compile(r"function\s+test\w*\s*\(|@test\b|\bit\(['\"]|\btest\(['\"]"),
    "ruby": re.compile(r"^\s*(it|specify|scenario)\s+['\"]|^\s*def\s+test_"),
    "csharp": re.compile(r"\[(Fact|Test|TestMethod|Theory)\]"),
    "rust": re.compile(r"#\[test\]"),
    "elixir": re.compile(r"^\s*test\s+\""),
}


# ------------------------------------------------------------------ helpers

def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _role(rel: str, name: str) -> str:
    parts = rel.split("/")[:-1]
    if TEST_FILE.match(name) or any(p.lower() in TEST_DIR_NAMES for p in parts):
        return "test"
    if any(p.lower() in AUX_DIR_NAMES for p in parts) or name in ("setup.py", "conftest.py", "noxfile.py", "fabfile.py"):
        return "aux"
    if re.match(r".*\.(config|conf)\.[cm]?[jt]s$", name) or name in ("Gruntfile.js", "gulpfile.js"):
        return "aux"
    return "source"


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def vcs_info(root: Path) -> dict:
    top = _git(root, "rev-parse", "--show-toplevel")
    if not top:
        return {"kind": None, "commit": None, "dirty": None, "remote": None}
    return {
        "kind": "git",
        "commit": _git(root, "rev-parse", "HEAD"),
        "dirty": bool(_git(root, "status", "--porcelain")),
        "remote": _git(root, "config", "--get", "remote.origin.url"),
        "describe": _git(root, "describe", "--tags", "--always"),
    }


def classify_license(text: str) -> str | None:
    t = re.sub(r"\s+", " ", text)
    checks = [
        ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
        ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE.{0,200}Version 3"),
        ("LGPL-2.1", r"GNU LESSER GENERAL PUBLIC LICENSE|GNU LIBRARY GENERAL PUBLIC LICENSE"),
        ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE.{0,200}Version 3"),
        ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE"),
        ("MPL-2.0", r"Mozilla Public License,? (v\. |Version )?2\.0"),
        ("EPL-2.0", r"Eclipse Public License"),
        ("Apache-2.0", r"Apache License,? Version 2\.0|Apache License\s+Version 2\.0"),
        ("Artistic-2.0", r"Artistic License 2\.0|The Artistic License 2\.0"),
        ("Artistic-1.0", r"Artistic License"),
        ("Unlicense", r"This is free and unencumbered software"),
        ("ISC", r"ISC License|Permission to use, copy, modify, and/?or distribute this software for any"),
        ("MIT", r"Permission is hereby granted, free of charge"),
        ("BSD-3-Clause", r"Redistribution and use in source and binary forms.{0,1500}(Neither the name|endorse or promote)"),
        ("BSD-2-Clause", r"Redistribution and use in source and binary forms"),
        ("0BSD", r"Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee"),
    ]
    for spdx, pattern in checks:
        if re.search(pattern, t, re.I):
            return spdx
    return None


def copyleft_of(spdx: str | None) -> str:
    if not spdx:
        return "unknown"
    s = spdx.upper()
    if s.startswith(("GPL", "AGPL")):
        return "strong"
    if s.startswith(("LGPL", "MPL", "EPL", "CDDL")):
        return "weak"
    return "none"


# ------------------------------------------------------------------ python

class PyModuleInfo:
    def __init__(self) -> None:
        self.symbols: list[dict] = []
        self.internal: set[str] = set()
        self.external: set[str] = set()
        self.stdlib: set[str] = set()


def py_module_id(rel: str, src_roots: list[str]) -> str:
    path = rel[:-4] if rel.endswith(".pyi") else rel[:-3]
    for root in src_roots:
        if root and path.startswith(root + "/"):
            path = path[len(root) + 1:]
            break
    parts = path.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or "__init__"


def _chain(node: ast.AST) -> list[str] | None:
    names = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        names.append(node.id)
        return names[::-1]
    return None


def analyze_python(text: str, mod_id: str, is_package: bool, modules: set[str], top_internal: set[str],
                   lines: list[str], want_symbols: bool) -> PyModuleInfo:
    info = PyModuleInfo()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return info
    stdlib = set(sys.stdlib_module_names)
    package = mod_id if is_package else mod_id.rpartition(".")[0]
    mod_alias: dict[str, str] = {}
    sym_alias: dict[str, tuple[str, str]] = {}
    ext_alias: dict[str, str] = {}

    def resolve_rel(level: int, module: str | None) -> str:
        base = package.split(".") if package else []
        if level > 1:
            base = base[: len(base) - (level - 1)]
        return ".".join([*base, *(module.split(".") if module else [])])

    def note_external(name: str) -> None:
        top = name.split(".")[0]
        if top in stdlib or top == "__future__":
            info.stdlib.add(top)
        elif top not in top_internal:
            info.external.add(top)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name
                if full in modules or full.split(".")[0] in top_internal:
                    target = full if full in modules else full.split(".")[0]
                    if alias.asname:
                        mod_alias[alias.asname] = full if full in modules else target
                    else:
                        mod_alias[full.split(".")[0]] = full.split(".")[0]
                    info.internal.add(full if full in modules else target)
                else:
                    note_external(full)
                    ext_alias[alias.asname or full.split(".")[0]] = full.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = resolve_rel(node.level, node.module) if node.level else (node.module or "")
            internal = base in modules or base.split(".")[0] in top_internal
            if not internal:
                note_external(base)
                for alias in node.names:
                    ext_alias[alias.asname or alias.name] = base.split(".")[0]
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                sub = f"{base}.{alias.name}" if base else alias.name
                if sub in modules:
                    mod_alias[local] = sub
                    info.internal.add(sub)
                elif alias.name == "*":
                    if base in modules:
                        info.internal.add(base)
                else:
                    sym_alias[local] = (base, alias.name)
                    if base in modules:
                        info.internal.add(base)
    info.internal.discard(mod_id)
    if not want_symbols:
        return info

    all_names = None
    top_names: dict[str, ast.AST] = {}
    order: list[tuple[str, str, ast.AST]] = []

    def collect(body: list[ast.stmt]) -> None:
        nonlocal all_names
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                order.append((stmt.name, "function", stmt))
            elif isinstance(stmt, ast.ClassDef):
                order.append((stmt.name, "class", stmt))
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        if t.id == "__all__" and isinstance(stmt.value, (ast.List, ast.Tuple)):
                            all_names = {e.value for e in stmt.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                        elif not (t.id.startswith("__") and t.id.endswith("__")):
                            order.append((t.id, "constant", stmt))
            elif isinstance(stmt, (ast.If, ast.Try)):
                collect(stmt.body)
                for handler in getattr(stmt, "handlers", []):
                    collect(handler.body)
                collect(getattr(stmt, "orelse", []))

    collect(tree.body)
    for name, _, node in order:
        top_names.setdefault(name, node)

    seen: set[str] = set()
    for name, kind, node in order:
        if name in seen:
            continue
        seen.add(name)
        start = min([node.lineno, *[d.lineno for d in getattr(node, "decorator_list", [])]])
        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        refs: set[str] = set()
        external: set[str] = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                if sub.id in top_names and sub.id != name:
                    refs.add(f"{mod_id}:{sub.id}")
                elif sub.id in sym_alias:
                    m, n = sym_alias[sub.id]
                    refs.add(f"{m}:{n}")
                elif sub.id in ext_alias:
                    external.add(ext_alias[sub.id])
            elif isinstance(sub, ast.Attribute):
                chain = _chain(sub)
                if chain and chain[0] in mod_alias:
                    mod = mod_alias[chain[0]]
                    rest = chain[1:]
                    while rest and f"{mod}.{rest[0]}" in modules:
                        mod = f"{mod}.{rest[0]}"
                        rest = rest[1:]
                    if rest:
                        refs.add(f"{mod}:{rest[0]}")
        span = lines[start - 1:end]
        sig = scan_lines("python", span)
        public = (name in all_names) if all_names is not None else not name.startswith("_")
        info.symbols.append({
            "name": name,
            "kind": kind if not (kind == "constant" and name[:1].isupper() and not name.isupper()) else "type",
            "line": start,
            "endLine": end,
            "loc": sum(1 for l in span if l.strip()),
            "public": public,
            "refs": sorted(refs),
            "external": sorted(external),
            "io": sorted(sig["io"] | sig["welded"] | sig["native"]),
            "risk": sorted(sig["risk"]),
        })
    return info


# ------------------------------------------------------------------ javascript / typescript / go / class langs

JS_DECL = [
    re.compile(r"^export\s+default\s+(?:async\s+)?function\*?\s*(\w+)?"),
    re.compile(r"^export\s+default\s+(?:abstract\s+)?class\s+(\w+)?"),
    re.compile(r"^(?:export\s+)?(?:declare\s+)?(?:async\s+)?function\*?\s+(\w+)"),
    re.compile(r"^(?:export\s+)?(?:declare\s+)?(?:abstract\s+)?class\s+(\w+)"),
    re.compile(r"^(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+(\w+)"),
    re.compile(r"^(?:export\s+)?(?:declare\s+)?(?:interface|type|enum|const\s+enum)\s+(\w+)"),
    re.compile(r"^(?:module\.)?exports\.(\w+)\s*="),
    re.compile(r"^module\.exports\s*="),
]
JS_PROTO = re.compile(r"^(\w+)\.prototype\.\w+\s*=")
JS_EXPORT_LIST = re.compile(r"^export\s*\{([^}]*)\}")
JS_CJS_OBJECT = re.compile(r"^module\.exports\s*=\s*\{([^}]*)\}")
JS_CJS_NAME = re.compile(r"^module\.exports\s*=\s*(\w+)\s*;?\s*$")
JS_IMPORT = re.compile(r"""^\s*import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\}|\*\s+as\s+(\w+))?\s*(?:from\s*)?['"]([^'"]+)['"]""", re.M)
JS_REQUIRE_NAMED = re.compile(r"""(?:const|let|var)\s*\{([^}]*)\}\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)""")
JS_REQUIRE = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)(?:\.(\w+))?""")
JS_REQUIRE_BARE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
JS_EXPORT_FROM = re.compile(r"""^\s*export\s+(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]""", re.M)
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
JS_STRIP = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`", re.S)
GO_FUNC = re.compile(r"^func\s+(?:\(\s*\w*\s*\*?(\w+)(?:\[[^\]]*\])?\s*\)\s*)?(\w+)")
GO_TYPE = re.compile(r"^type\s+(\w+)")
GO_VAR = re.compile(r"^(?:var|const)\s+(\w+)")
GO_BLOCK = re.compile(r"^(?:var|const|type)\s*\(\s*$")
GO_BLOCK_ITEM = re.compile(r"^\s+(\w+)\b")
GO_IMPORT_SINGLE = re.compile(r'^import\s+(?:(\w+|\.)\s+)?"([^"]+)"', re.M)
GO_IMPORT_BLOCK = re.compile(r"^import\s*\((.*?)\)", re.M | re.S)
GO_IMPORT_LINE = re.compile(r'^\s*(?:(\w+|\.|_)\s+)?"([^"]+)"', re.M)
CLASS_DECL = {
    "java": re.compile(r"^(?:(?:public|protected|private|abstract|final|sealed|non-sealed|static|strictfp)\s+)*(class|interface|enum|record|@interface)\s+(\w+)"),
    "kotlin": re.compile(r"^(?:(?:public|internal|private|protected|data|sealed|abstract|open|enum|annotation|inline|value|inner|expect|actual)\s+)*(class|interface|object|fun|val|var|const\s+val|typealias)\s+(?:<[^>]*>\s*)?(?:\w+\.)?(\w+)"),
    "csharp": re.compile(r"^\s{0,4}(?:(?:public|internal|private|protected|abstract|sealed|static|partial|readonly|record)\s+)*(class|interface|enum|struct|record)\s+(\w+)"),
    "php": re.compile(r"^(?:(?:final|abstract|readonly)\s+)*(class|interface|trait|enum|function)\s+&?(\w+)"),
    "ruby": re.compile(r"^(?:\s{0,2})(class|module)\s+([A-Z]\w*(?:::\w+)*)"),
    "scala": re.compile(r"^(?:(?:final|sealed|abstract|case|private|protected|implicit)\s+)*(class|object|trait|enum)\s+(\w+)"),
    "swift": re.compile(r"^(?:(?:public|open|internal|private|fileprivate|final)\s+)*(class|struct|enum|protocol|extension|func)\s+(\w+)"),
    "dart": re.compile(r"^(?:abstract\s+)?(class|mixin|enum|extension)\s+(\w+)"),
    "groovy": re.compile(r"^(?:(?:public|abstract|final)\s+)*(class|interface|enum|trait)\s+(\w+)"),
}


def _js_kind(line: str) -> str:
    if re.search(r"\bclass\b", line):
        return "class"
    if re.search(r"\bfunction\b", line):
        return "function"
    if re.search(r"\b(interface|type|enum)\b", line):
        return "type"
    return "constant"


def _trim_end(lines: list[str], start: int, end: int, comment=re.compile(r"^\s*(//|/\*|\*|\*/|#)")) -> int:
    while end > start and (not lines[end - 1].strip() or comment.match(lines[end - 1])):
        end -= 1
    return end


def split_decls(lines: list[str], decls: list[tuple[int, str, str, bool]]) -> list[dict]:
    """decls: (line, name, kind, public) sorted by line; spans run to the next declaration."""
    out = []
    for i, (line, name, kind, public) in enumerate(decls):
        nxt = decls[i + 1][0] - 1 if i + 1 < len(decls) else len(lines)
        end = _trim_end(lines, line, nxt)
        out.append({"name": name, "kind": kind, "line": line, "endLine": end, "public": public})
    return out


def js_resolve(spec: str, from_rel: str, known: dict[str, str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = Path(from_rel).parent
    target = (base / spec).as_posix()
    parts: list[str] = []
    for part in target.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    target = "/".join(parts)
    for cand in (target, re.sub(r"\.[cm]?[jt]sx?$|\.coffee$", "", target), target + "/index"):
        if cand in known:
            return known[cand]
    return None


def js_package_name(spec: str) -> str | None:
    if spec.startswith((".", "/")) or spec.startswith("node:"):
        return None
    parts = spec.split("/")
    name = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
    return None if name in NODE_BUILTINS else name


def analyze_js(text: str, rel: str, mod_id: str, language: str, known: dict[str, str],
               lines: list[str], want_symbols: bool) -> dict:
    internal: set[str] = set()
    external: set[str] = set()
    imported: dict[str, tuple[str, str]] = {}
    mod_alias: dict[str, str] = {}
    ext_alias: dict[str, str] = {}

    def link(local: str | None, spec: str, member: str | None) -> None:
        target = js_resolve(spec, rel, known)
        if target:
            internal.add(target)
            if local:
                if member:
                    imported[local] = (target, member)
                else:
                    mod_alias[local] = target
            return
        pkg = js_package_name(spec)
        if pkg:
            external.add(pkg)
            if local:
                ext_alias[local] = pkg

    for m in JS_IMPORT.finditer(text):
        default, named, ns, spec = m.groups()
        if default:
            link(default, spec, "default")
        if ns:
            link(ns, spec, None)
        if named:
            for item in named.split(","):
                item = item.strip().removeprefix("type ").strip()
                if not item:
                    continue
                orig, _, local = item.partition(" as ")
                link(local.strip() or orig.strip(), spec, orig.strip())
        if not (default or ns or named):
            link(None, spec, None)
    for m in JS_REQUIRE_NAMED.finditer(text):
        for item in m.group(1).split(","):
            orig, _, local = item.strip().partition(":")
            if orig.strip():
                link((local or orig).strip(), m.group(2), orig.strip())
    for m in JS_REQUIRE.finditer(text):
        link(m.group(1), m.group(2), m.group(3))
    for m in JS_REQUIRE_BARE.finditer(text):
        link(None, m.group(1), None)
    for m in JS_EXPORT_FROM.finditer(text):
        link(None, m.group(1), None)
    internal.discard(mod_id)
    result = {"internal": internal, "external": external, "symbols": []}
    if not want_symbols:
        return result

    decls: list[tuple[int, str, str, bool]] = []
    exported: set[str] = set()
    for i, line in enumerate(lines, 1):
        m = JS_EXPORT_LIST.match(line)
        if m:
            for item in m.group(1).split(","):
                orig, _, alias = item.strip().partition(" as ")
                if orig.strip():
                    exported.add(orig.strip())
            continue
        m = JS_CJS_OBJECT.match(line)
        if m:
            for item in m.group(1).split(","):
                key, _, value = item.strip().partition(":")
                exported.add((value or key).strip())
        m = JS_CJS_NAME.match(line)
        if m:
            exported.add(m.group(1))
            continue
        if JS_PROTO.match(line):
            continue
        for rx in JS_DECL:
            m = rx.match(line)
            if not m:
                continue
            if rx.pattern.startswith("^module\\.exports\\s*="):
                if JS_CJS_OBJECT.match(line):
                    break
                decls.append((i, "default", "function" if "function" in line else "constant", True))
            else:
                name = m.group(1) or "default"
                public = line.startswith("export") or line.startswith(("exports.", "module.exports."))
                decls.append((i, name, _js_kind(line), public))
            break
    spans = split_decls(lines, decls)
    names = {s["name"] for s in spans}
    for s in spans:
        if s["name"] in exported:
            s["public"] = True
    if not spans:
        spans = [{"name": Path(rel).stem, "kind": "module", "line": 1, "endLine": len(lines), "public": True}]
        names = set()
    for s in spans:
        body = "\n".join(lines[s["line"] - 1: s["endLine"]])
        code = JS_STRIP.sub(" ", body)
        tokens = set(IDENT.findall(code))
        refs: set[str] = set()
        ext: set[str] = set()
        for tok in tokens:
            if tok == "default":
                continue
            if tok in names and tok != s["name"]:
                refs.add(f"{mod_id}:{tok}")
            elif tok in imported:
                refs.add(f"{imported[tok][0]}:{imported[tok][1]}")
            elif tok in ext_alias:
                ext.add(ext_alias[tok])
        for alias, target in mod_alias.items():
            for m in re.finditer(rf"\b{re.escape(alias)}\.(\w+)", code):
                refs.add(f"{target}:{m.group(1)}")
        span_lines = lines[s["line"] - 1: s["endLine"]]
        sig = scan_lines(language, span_lines)
        s.update({
            "loc": sum(1 for l in span_lines if l.strip()),
            "refs": sorted(refs),
            "external": sorted(ext),
            "io": sorted(sig["io"] | sig["welded"] | sig["native"]),
            "risk": sorted(sig["risk"]),
        })
    result["symbols"] = spans
    return result


def analyze_go_package(files: list[tuple[str, str, list[str]]], pkg_id: str, module_path: str | None,
                       pkg_ids: dict[str, str]) -> dict:
    internal: set[str] = set()
    external: set[str] = set()
    alias_pkg: dict[str, str] = {}
    ext_alias: dict[str, str] = {}
    raw: list[tuple[str, list[str], list[tuple[int, str, str, bool]]]] = []
    for rel, text, lines in files:
        imports = []
        for m in GO_IMPORT_SINGLE.finditer(text):
            imports.append((m.group(1), m.group(2)))
        for block in GO_IMPORT_BLOCK.finditer(text):
            for m in GO_IMPORT_LINE.finditer(block.group(1)):
                imports.append((m.group(1), m.group(2)))
        for alias, path in imports:
            last = path.split("/")[-1]
            if re.fullmatch(r"v\d+", last) and "/" in path:
                last = path.split("/")[-2]
            local = alias or last.replace("-", "_")
            if module_path and (path == module_path or path.startswith(module_path + "/")):
                sub = path[len(module_path):].lstrip("/") or "."
                target = pkg_ids.get(sub)
                if target and target != pkg_id:
                    internal.add(target)
                    alias_pkg[local] = target
            elif "." in path.split("/")[0]:
                external.add(path)
                ext_alias[local] = path
        decls: list[tuple[int, str, str, bool]] = []
        in_block = False
        for i, line in enumerate(lines, 1):
            if in_block:
                if line.startswith(")"):
                    in_block = False
                    continue
                m = GO_BLOCK_ITEM.match(line)
                if m and m.group(1) not in ("_",) and not line.strip().startswith("//"):
                    decls.append((i, m.group(1), "constant", m.group(1)[0].isupper()))
                continue
            if GO_BLOCK.match(line):
                in_block = True
                continue
            m = GO_FUNC.match(line)
            if m:
                receiver, name = m.groups()
                if receiver:
                    decls.append((i, f"{receiver}.{name}", "method", name[0].isupper()))
                else:
                    decls.append((i, name, "function", name[0].isupper()))
                continue
            m = GO_TYPE.match(line) or GO_VAR.match(line)
            if m:
                decls.append((i, m.group(1), "type" if line.startswith("type") else "constant", m.group(1)[0].isupper()))
        raw.append((rel, lines, decls))
    spans_all: list[dict] = []
    for rel, lines, decls in raw:
        for s in split_decls(lines, decls):
            s["file"] = rel
            s["_lines"] = lines[s["line"] - 1: s["endLine"]]
            spans_all.append(s)
    merged: dict[str, dict] = {}
    methods = []
    for s in spans_all:
        if s["kind"] == "method":
            methods.append(s)
        else:
            merged.setdefault(s["name"], s)
    for s in methods:
        owner = s["name"].split(".")[0]
        if owner in merged:
            merged[owner].setdefault("extra", []).append(s)
        else:
            merged[s["name"]] = s
    names = set(merged)
    symbols = []
    for name, s in merged.items():
        body_lines = list(s["_lines"])
        for extra in s.get("extra", []):
            body_lines.extend(extra["_lines"])
        code = JS_STRIP.sub(" ", "\n".join(body_lines))
        refs: set[str] = set()
        ext: set[str] = set()
        for tok in set(IDENT.findall(code)):
            if tok in names and tok != name:
                refs.add(f"{pkg_id}:{tok}")
            elif tok in ext_alias:
                ext.add(ext_alias[tok])
        for alias, target in alias_pkg.items():
            for m in re.finditer(rf"\b{re.escape(alias)}\.(\w+)", code):
                refs.add(f"{target}:{m.group(1)}")
        sig = scan_lines("go", body_lines)
        symbols.append({
            "name": name, "kind": s["kind"], "line": s["line"], "endLine": s["endLine"], "file": s["file"],
            "loc": sum(1 for l in body_lines if l.strip()), "public": s["public"], "refs": sorted(refs),
            "external": sorted(ext), "io": sorted(sig["io"] | sig["welded"] | sig["native"]), "risk": sorted(sig["risk"]),
        })
    return {"internal": internal, "external": external, "symbols": symbols}


BRACE_LANGS = {"java", "kotlin", "php", "scala", "groovy", "dart", "csharp", "swift"}


def analyze_class_lang(text: str, language: str, lines: list[str]) -> list[dict]:
    rx = CLASS_DECL[language]
    max_depth = 1 if language == "csharp" else 0
    decls = []
    depth = 0
    for i, line in enumerate(lines, 1):
        m = rx.match(line)
        if m and (language not in BRACE_LANGS or depth <= max_depth):
            kind_word, name = m.group(1), m.group(2)
            kind = {"fun": "function", "function": "function", "func": "function", "val": "constant", "var": "constant",
                    "const val": "constant", "interface": "type", "typealias": "type", "trait": "type",
                    "protocol": "type", "module": "class"}.get(kind_word, "class")
            public = True
            if language == "java":
                public = bool(re.match(r"^\s*(?:\w+\s+)*public\b", line))
            elif language in ("kotlin", "swift"):
                public = not re.match(r"^\s*(?:\w+\s+)*(private|internal|fileprivate)\b", line)
            elif language == "csharp":
                public = bool(re.search(r"\bpublic\b", line))
            decls.append((i, name, kind, public))
        if language in BRACE_LANGS:
            depth += line.count("{") - line.count("}")
    return split_decls(lines, decls)


# ------------------------------------------------------------------ manifests, entry points, runtimes

def _load_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _dynamic_python_version(base: Path, data: dict) -> str | None:
    tool = data.get("tool", {})
    attr = ((tool.get("setuptools", {}).get("dynamic", {}) or {}).get("version") or {}).get("attr")
    candidates = []
    if isinstance(attr, str) and "." in attr:
        mod, _, var = attr.rpartition(".")
        rel = Path(*mod.split("."))
        candidates = [(base / rel).with_suffix(".py"), base / rel / "__init__.py",
                      (base / "src" / rel).with_suffix(".py"), base / "src" / rel / "__init__.py"]
    elif isinstance(tool.get("hatch", {}).get("version", {}).get("path"), str):
        candidates, var = [base / tool["hatch"]["version"]["path"]], "__version__"
    for f in candidates:
        if f.is_file():
            m = re.search(rf"^{re.escape(var)}\s*=\s*['\"]([^'\"]+)['\"]", f.read_text(encoding="utf-8", errors="replace"), re.M)
            if m:
                return m.group(1)
    return None


def entry_points_and_runtimes(root: Path, manifests: list[dict]) -> tuple[list[dict], list[dict], dict]:
    entries: list[dict] = []
    runtimes: list[dict] = []
    package: dict = {}
    for m in manifests:
        path = root / m["path"]
        kind = m["kind"]
        try:
            if kind == "npm":
                data = read_json(path)
                package.setdefault("name", data.get("name"))
                package.setdefault("version", data.get("version"))
                package.setdefault("license", data.get("license") if isinstance(data.get("license"), str) else None)
                bins = data.get("bin")
                if isinstance(bins, str):
                    entries.append({"kind": "cli", "name": data.get("name"), "target": bins, "path": m["path"]})
                elif isinstance(bins, dict):
                    for k, v in bins.items():
                        entries.append({"kind": "cli", "name": k, "target": v, "path": m["path"]})
                for key in ("main", "module", "types", "typings", "browser"):
                    if isinstance(data.get(key), str):
                        entries.append({"kind": "library", "name": key, "target": data[key], "path": m["path"]})
                exports = data.get("exports")
                if isinstance(exports, str):
                    entries.append({"kind": "library", "name": ".", "target": exports, "path": m["path"]})
                elif isinstance(exports, dict):
                    for k in exports:
                        entries.append({"kind": "library", "name": k, "target": str(exports[k])[:120], "path": m["path"]})
                if isinstance(data.get("engines"), dict):
                    for k, v in data["engines"].items():
                        runtimes.append({"runtime": k, "spec": v, "path": m["path"]})
            elif kind == "pyproject":
                data = _load_toml(path)
                proj = data.get("project", {})
                poetry = data.get("tool", {}).get("poetry", {})
                package.setdefault("name", proj.get("name") or poetry.get("name"))
                package.setdefault("version", proj.get("version") or poetry.get("version")
                                   or _dynamic_python_version(path.parent, data))
                lic = proj.get("license")
                if isinstance(lic, dict):
                    lic = lic.get("text")
                package.setdefault("license", lic if isinstance(lic, str) and len(lic) < 60 else None)
                for section in ("scripts", "gui-scripts"):
                    for k, v in proj.get(section, {}).items():
                        entries.append({"kind": "cli", "name": k, "target": v, "path": m["path"]})
                for k, v in poetry.get("scripts", {}).items():
                    entries.append({"kind": "cli", "name": k, "target": str(v), "path": m["path"]})
                if proj.get("requires-python"):
                    runtimes.append({"runtime": "python", "spec": proj["requires-python"], "path": m["path"]})
                classifiers = proj.get("classifiers", [])
                versions = [c.split("::")[-1].strip() for c in classifiers if c.startswith("Programming Language :: Python ::") and re.match(r".*\d\.\d+$", c)]
                if versions:
                    runtimes.append({"runtime": "python", "spec": "classifiers " + ", ".join(versions), "path": m["path"]})
            elif kind == "setup.py":
                text = path.read_text(encoding="utf-8", errors="replace")
                name = re.search(r"\bname\s*=\s*['\"]([^'\"]+)", text)
                version = re.search(r"\bversion\s*=\s*['\"]([^'\"]+)", text)
                package.setdefault("name", name.group(1) if name else None)
                package.setdefault("version", version.group(1) if version else None)
                for em in re.finditer(r"['\"]([\w.-]+)\s*=\s*([\w.]+:[\w.]+)['\"]", text):
                    entries.append({"kind": "cli", "name": em.group(1), "target": em.group(2), "path": m["path"]})
                pr = re.search(r"python_requires\s*=\s*['\"]([^'\"]+)", text)
                if pr:
                    runtimes.append({"runtime": "python", "spec": pr.group(1), "path": m["path"]})
                lic = re.search(r"\blicense\s*=\s*['\"]([^'\"]+)", text)
                if lic:
                    package.setdefault("license", lic.group(1))
                versions = re.findall(r"Programming Language :: Python :: (\d\.\d+)", text)
                if versions:
                    runtimes.append({"runtime": "python", "spec": "classifiers " + ", ".join(versions), "path": m["path"]})
            elif kind == "setup.cfg":
                cp = configparser.ConfigParser()
                cp.read(path, encoding="utf-8")
                if cp.has_section("metadata"):
                    package.setdefault("name", cp.get("metadata", "name", fallback=None))
                    package.setdefault("version", cp.get("metadata", "version", fallback=None))
                if cp.has_option("options", "python_requires"):
                    runtimes.append({"runtime": "python", "spec": cp.get("options", "python_requires"), "path": m["path"]})
                if cp.has_section("options.entry_points"):
                    for line in cp.get("options.entry_points", "console_scripts", fallback="").splitlines():
                        if "=" in line:
                            k, v = line.split("=", 1)
                            entries.append({"kind": "cli", "name": k.strip(), "target": v.strip(), "path": m["path"]})
            elif kind == "go.mod":
                text = path.read_text(encoding="utf-8")
                mod = re.search(r"^module\s+(\S+)", text, re.M)
                package.setdefault("name", mod.group(1) if mod else None)
                go = re.search(r"^go\s+(\S+)", text, re.M)
                if go:
                    runtimes.append({"runtime": "go", "spec": go.group(1), "path": m["path"]})
            elif kind == "cargo":
                data = _load_toml(path)
                pkg = data.get("package", {})
                package.setdefault("name", pkg.get("name"))
                package.setdefault("version", pkg.get("version") if isinstance(pkg.get("version"), str) else None)
                package.setdefault("license", pkg.get("license"))
                for b in data.get("bin", []):
                    entries.append({"kind": "cli", "name": b.get("name"), "target": b.get("path"), "path": m["path"]})
                if pkg.get("rust-version"):
                    runtimes.append({"runtime": "rust", "spec": pkg["rust-version"], "path": m["path"]})
            elif kind == "composer":
                data = read_json(path)
                package.setdefault("name", data.get("name"))
                package.setdefault("version", data.get("version"))
                lic = data.get("license")
                package.setdefault("license", lic if isinstance(lic, str) else (lic[0] if isinstance(lic, list) and lic else None))
                for b in data.get("bin", []) or []:
                    entries.append({"kind": "cli", "name": Path(b).name, "target": b, "path": m["path"]})
                php = (data.get("require") or {}).get("php")
                if php:
                    runtimes.append({"runtime": "php", "spec": php, "path": m["path"]})
            elif kind == "gemspec":
                text = path.read_text(encoding="utf-8", errors="replace")
                name = re.search(r"\.name\s*=\s*['\"]([^'\"]+)", text)
                package.setdefault("name", name.group(1) if name else None)
                rv = re.search(r"required_ruby_version\s*=\s*['\"]([^'\"]+)", text)
                if rv:
                    runtimes.append({"runtime": "ruby", "spec": rv.group(1), "path": m["path"]})
                lic = re.search(r"\.licenses?\s*=\s*\[?\s*['\"]([^'\"]+)", text)
                if lic:
                    package.setdefault("license", lic.group(1))
            elif kind == "maven":
                text = path.read_text(encoding="utf-8", errors="replace")
                aid = re.search(r"<artifactId>([^<]+)</artifactId>", text)
                gid = re.search(r"<groupId>([^<]+)</groupId>", text)
                if aid:
                    package.setdefault("name", f"{gid.group(1)}:{aid.group(1)}" if gid else aid.group(1))
                rel = re.search(r"<maven\.compiler\.(release|source)>([^<]+)<", text)
                if rel:
                    runtimes.append({"runtime": "java", "spec": rel.group(2), "path": m["path"]})
        except (OSError, ValueError, PorterError):
            continue
    return entries, runtimes, {k: v for k, v in package.items() if v}


# ------------------------------------------------------------------ main survey

def run_survey(root: Path, subpath: str | None = None, max_files: int = 4000) -> dict:
    root = root.resolve()
    scan_root = (root / subpath).resolve() if subpath else root
    if not scan_root.is_dir():
        raise PorterError(f"not a directory: {scan_root}")
    all_files = list(iter_files(scan_root))
    manifests: list[dict] = []
    tooling: list[dict] = []
    license_files: list[Path] = []
    code_files: list[tuple[Path, str, str]] = []
    for f in all_files:
        rel = _rel(f, scan_root)
        name = f.name
        kind = MANIFESTS.get(name) or next((k for rx, k in MANIFEST_PATTERNS if rx.match(name)), None)
        if kind:
            manifests.append({"path": rel, "kind": kind})
        for rx, tkind in TOOLING:
            if rx.match(name):
                tooling.append({"path": rel, "kind": tkind})
                break
        if rel.startswith(".github/workflows/") or rel.startswith(".circleci/"):
            tooling.append({"path": rel, "kind": "ci"})
        if LICENSE_FILE.match(name) and rel.count("/") == 0:
            license_files.append(f)
        lang = EXT_LANG.get(f.suffix.lower())
        if lang:
            code_files.append((f, rel, lang))
    sampled = False
    total_code = len(code_files)
    if total_code > max_files:
        step = total_code / max_files
        code_files = [code_files[int(i * step)] for i in range(max_files)]
        sampled = True

    texts: dict[str, tuple[str, list[str]]] = {}
    lang_stats: dict[str, dict] = defaultdict(lambda: {"files": 0, "loc": 0})
    test_stats = {"files": 0, "loc": 0, "cases": 0}
    roles: dict[str, str] = {}
    for f, rel, lang in code_files:
        text = read_text_safe(f)
        if text is None:
            continue
        lines = text.splitlines()
        texts[rel] = (text, lines)
        loc = nonblank_loc(text)
        lang_stats[lang]["files"] += 1
        lang_stats[lang]["loc"] += loc
        role = _role(rel, f.name)
        roles[rel] = role
        if role == "test":
            test_stats["files"] += 1
            test_stats["loc"] += loc
            rx = TEST_CASE.get(lang)
            if rx:
                test_stats["cases"] += sum(1 for line in lines if rx.search(line))

    for rel in list(roles):
        if roles[rel] == "source" and EXT_LANG[Path(rel).suffix.lower()] == "shell" and any(
                EXT_LANG[Path(r).suffix.lower()] != "shell" and roles[r] == "source" for r in roles):
            roles[rel] = "aux"
    source_loc_by_lang = defaultdict(int)
    for rel, (text, lines) in texts.items():
        if roles[rel] == "source":
            source_loc_by_lang[EXT_LANG[Path(rel).suffix.lower()]] += nonblank_loc(text)
    primary = max(source_loc_by_lang, key=source_loc_by_lang.get) if source_loc_by_lang else (
        max(lang_stats, key=lambda k: lang_stats[k]["loc"]) if lang_stats else None)

    modules: list[dict] = []
    module_index: dict[str, dict] = {}

    # python
    py_files = [rel for rel in texts if EXT_LANG[Path(rel).suffix.lower()] == "python"]
    src_roots = ["src"] if any(r.startswith("src/") for r in py_files) else [""]
    py_ids = {rel: py_module_id(rel, src_roots) for rel in py_files}
    py_modules = set(py_ids.values())
    top_internal = {m.split(".")[0] for rel, m in py_ids.items() if roles.get(rel) == "source"}
    for rel in py_files:
        text, lines = texts[rel]
        mod_id = py_ids[rel]
        info = analyze_python(text, mod_id, rel.endswith("__init__.py"), py_modules, top_internal, lines,
                              want_symbols=roles[rel] == "source")
        modules.append(_module(rel, mod_id, "python", text, lines, roles[rel], info.internal, info.external, info.symbols))

    # javascript family
    js_langs = ("javascript", "typescript", "coffeescript")
    js_files = [rel for rel in texts if EXT_LANG[Path(rel).suffix.lower()] in js_langs]
    js_known: dict[str, str] = {}
    for rel in js_files:
        mod_id = re.sub(r"\.[^.]+$", "", rel)
        js_known[rel] = mod_id
        js_known[mod_id] = mod_id
    for rel in js_files:
        text, lines = texts[rel]
        lang = EXT_LANG[Path(rel).suffix.lower()]
        res = analyze_js(text, rel, js_known[rel], lang, js_known, lines, want_symbols=roles[rel] == "source")
        modules.append(_module(rel, js_known[rel], lang, text, lines, roles[rel], res["internal"], res["external"], res["symbols"]))

    # go (module = package directory)
    go_files = [rel for rel in texts if rel.endswith(".go")]
    if go_files:
        go_mod = next((scan_root / m["path"] for m in manifests if m["kind"] == "go.mod" and "/" not in m["path"]), None)
        module_path = None
        if go_mod and go_mod.exists():
            mm = re.search(r"^module\s+(\S+)", go_mod.read_text(encoding="utf-8"), re.M)
            module_path = mm.group(1) if mm else None
        pkgs: dict[str, list[str]] = defaultdict(list)
        for rel in go_files:
            pkgs[str(Path(rel).parent.as_posix())].append(rel)
        base = (module_path or "root").split("/")[-1]
        pkg_ids = {d: (base if d == "." else d) for d in pkgs}
        for d, rels in sorted(pkgs.items()):
            src = [r for r in rels if roles[r] == "source"]
            tests = [r for r in rels if roles[r] != "source"]
            if src:
                res = analyze_go_package([(r, *texts[r]) for r in src], pkg_ids[d], module_path, pkg_ids)
                text = "\n".join(texts[r][0] for r in src)
                lines = text.splitlines()
                modules.append(_module(d if d != "." else ".", pkg_ids[d], "go", text, lines, "source",
                                       res["internal"], res["external"], res["symbols"], files=src))
            for r in tests:
                text, lines = texts[r]
                res = analyze_go_package([(r, text, lines)], pkg_ids[d] + "_test", module_path, pkg_ids)
                modules.append(_module(r, r, "go", text, lines, roles[r], res["internal"], res["external"], []))

    # class-per-file languages and the rest
    handled = set(py_files) | set(js_files) | set(go_files)
    class_names: dict[str, list[str]] = defaultdict(list)
    pending: list[dict] = []
    for rel, (text, lines) in texts.items():
        if rel in handled:
            continue
        lang = EXT_LANG[Path(rel).suffix.lower()]
        mod_id = re.sub(r"\.[^.]+$", "", rel)
        symbols: list[dict] = []
        if roles[rel] == "source":
            if lang in CLASS_LANGS:
                symbols = analyze_class_lang(text, lang, lines)
            if not symbols:
                symbols = [{"name": Path(rel).stem, "kind": "module", "line": 1, "endLine": len(lines), "public": True}]
            for s in symbols:
                class_names[s["name"]].append(f"{mod_id}:{s['name']}")
        mod = _module(rel, mod_id, lang, text, lines, roles[rel], set(), set(), symbols)
        pending.append(mod)
        modules.append(mod)
    for mod in pending:
        text, lines = texts[mod["path"]]
        for s in mod["symbols"]:
            body = lines[s["line"] - 1: s["endLine"]]
            code = JS_STRIP.sub(" ", "\n".join(body))
            refs = set()
            for tok in set(IDENT.findall(code)):
                if tok in class_names and tok != s["name"]:
                    refs.update(class_names[tok])
            refs.discard(f"{mod['id']}:{s['name']}")
            sig = scan_lines(mod["language"], body)
            s.update({"loc": sum(1 for l in body if l.strip()), "refs": sorted(refs), "external": [],
                      "io": sorted(sig["io"] | sig["welded"] | sig["native"]), "risk": sorted(sig["risk"])})
        mod["imports"]["internal"] = sorted({r.split(":")[0] for s in mod["symbols"] for r in s["refs"]} - {mod["id"]})

    for mod in modules:
        module_index[mod["id"]] = mod
    for mod in modules:
        derived = {r.split(":")[0] for s in mod["symbols"] for r in s.get("refs", [])}
        mod["imports"]["internal"] = sorted((set(mod["imports"]["internal"]) | derived) - {mod["id"]})
        mod["imports"]["internal"] = [m for m in mod["imports"]["internal"] if m in module_index]

    src_mods = [m for m in modules if m["role"] == "source"]
    edges = {m["id"]: m["imports"]["internal"] for m in src_mods}
    indeg: dict[str, int] = defaultdict(int)
    for m, deps in edges.items():
        for d in deps:
            indeg[d] += 1
    graph = {
        "leaves": sorted(m for m, deps in edges.items() if not [d for d in deps if d in edges]),
        "hubs": [{"module": m, "importedBy": n} for m, n in sorted(indeg.items(), key=lambda x: (-x[1], x[0]))[:5] if m in edges],
        "cycles": find_cycles(list(edges), edges),
    }

    entries, runtimes, package = entry_points_and_runtimes(scan_root, manifests)
    for rel, mod_id in py_ids.items():
        if roles.get(rel) == "source" and rel.endswith("__init__.py") and "." not in mod_id:
            entries.append({"kind": "library", "name": mod_id, "target": rel, "path": rel})
    for rel in texts:
        if rel.endswith("__main__.py") and roles[rel] == "source":
            entries.append({"kind": "cli", "name": py_ids.get(rel, rel), "target": rel, "path": rel})
    for m in src_mods:
        if m["language"] == "go" and any(re.search(r"^package main\b", texts[f][0], re.M) for f in m.get("files", [])):
            entries.append({"kind": "cli", "name": m["id"], "target": m["path"], "path": m["path"]})
    lic_spdx = None
    lic_source = None
    for lf in license_files:
        text = read_text_safe(lf) or ""
        lic_spdx = classify_license(text)
        lic_source = _rel(lf, scan_root)
        if lic_spdx:
            break
    if not lic_spdx and package.get("license"):
        lic_spdx, lic_source = package["license"], "manifest"
    license = {"spdx": lic_spdx, "source": lic_source, "copyleft": copyleft_of(lic_spdx), "manifest": package.get("license")}

    pkg_manifests = [m for m in manifests if m["kind"] in PACKAGE_MANIFESTS]
    dirs = sorted({str(Path(m["path"]).parent.as_posix()) for m in pkg_manifests})
    packages = [{"path": d, "manifests": [m["path"] for m in pkg_manifests if str(Path(m["path"]).parent.as_posix()) == d]} for d in dirs]

    ext_all = set().union(*(set(m["imports"]["external"]) for m in src_mods)) if src_mods else set()
    signals_all = set().union(*(set(m["signals"]) for m in src_mods)) if src_mods else set()
    kind = _kind(entries, ext_all, signals_all)
    public_symbols = sum(1 for m in src_mods for s in m["symbols"] if s.get("public"))
    tests = dict(test_stats)
    src_loc = sum(m["loc"] for m in src_mods)
    tests["ratio"] = round(test_stats["loc"] / src_loc, 2) if src_loc else None
    tests["runners"] = _test_runners(tooling, manifests, texts, roles)
    tests["modules"] = [{"path": m["path"], "imports": m["imports"]["internal"]} for m in modules if m["role"] == "test"][:200]
    coupling_counts: dict[str, int] = defaultdict(int)
    for m in src_mods:
        coupling_counts[m["coupling"]] += 1
    return {
        "schema": 1,
        "generatedAt": now_iso(),
        "root": str(root),
        "subpath": subpath,
        "sampled": sampled,
        "coverage": {"codeFiles": total_code, "scanned": len(texts)},
        "vcs": vcs_info(root),
        "license": license,
        "package": package,
        "languages": sorted(({"language": k, **v} for k, v in lang_stats.items()), key=lambda x: -x["loc"]),
        "primaryLanguage": primary,
        "tests": tests,
        "manifests": manifests,
        "tooling": tooling,
        "runtimes": runtimes,
        "entryPoints": entries,
        "packages": packages,
        "kind": kind,
        "couplingCounts": dict(coupling_counts),
        "sourceLoc": src_loc,
        "publicSymbols": public_symbols,
        "graph": graph,
        "modules": modules,
    }


def _module(rel: str, mod_id: str, lang: str, text: str, lines: list[str], role: str, internal: set[str],
            external: set[str], symbols: list[dict], files: list[str] | None = None) -> dict:
    sig = scan_lines(lang, lines) if role == "source" else {"io": set(), "welded": set(), "native": set(), "risk": set()}
    out = {
        "id": mod_id,
        "path": rel,
        "language": lang,
        "loc": nonblank_loc(text),
        "role": role,
        "coupling": coupling_of(sig) if role == "source" else "pure",
        "signals": sorted(sig["io"] | sig["welded"] | sig["native"]),
        "risk": sorted(sig["risk"]),
        "riskScore": risk_score(sig["risk"]),
        "imports": {"internal": sorted(internal), "external": sorted(external)},
        "symbols": [{k: v for k, v in s.items() if not k.startswith("_")} for s in symbols],
    }
    if files:
        out["files"] = files
    return out


def _kind(entries: list[dict], external: set[str], signals: set[str]) -> str:
    services = {"flask", "django", "fastapi", "starlette", "tornado", "express", "koa", "fastify", "hapi",
                "@nestjs/core", "github.com/gin-gonic/gin", "github.com/labstack/echo", "rails", "sinatra", "laravel"}
    apps = {"react", "react-dom", "vue", "@angular/core", "svelte", "tkinter", "PyQt5", "PyQt6", "PySide6", "electron"}
    sdk = {"requests", "httpx", "aiohttp", "axios", "node-fetch", "got", "guzzlehttp", "okhttp3", "reqwest"}
    if external & services or "framework" in signals:
        return "service"
    if external & apps or "dom" in signals:
        return "app"
    has_cli = any(e["kind"] == "cli" for e in entries)
    has_lib = any(e["kind"] == "library" for e in entries) or not has_cli
    if has_cli and any(e["kind"] == "library" for e in entries):
        return "mixed"
    if has_cli:
        return "cli"
    if external & sdk:
        return "sdk"
    return "library" if has_lib else "unknown"


def _test_runners(tooling: list[dict], manifests: list[dict], texts: dict, roles: dict) -> list[str]:
    runners = set()
    kinds = {t["kind"] for t in tooling}
    if "pytest" in kinds:
        runners.add("pytest")
    for rel, (text, _) in texts.items():
        if roles.get(rel) != "test":
            continue
        if re.search(r"^\s*import pytest|^\s*from pytest", text, re.M):
            runners.add("pytest")
        if re.search(r"^\s*import unittest|^\s*from unittest", text, re.M):
            runners.add("unittest")
        if re.search(r"""from ['"]vitest['"]""", text):
            runners.add("vitest")
        if re.search(r"""require\(['"](mocha|chai|expect\.js|should)['"]\)|\bdescribe\(""", text):
            runners.add("mocha-style (describe/it)")
        if rel.endswith("_test.go"):
            runners.add("go test")
        if "@Test" in text:
            runners.add("junit")
        if re.search(r"PHPUnit\\|extends TestCase", text):
            runners.add("phpunit")
        if rel.endswith("_spec.rb"):
            runners.add("rspec")
    return sorted(runners)


def markdown_facts(s: dict) -> str:
    lines = ["| Fact | Value |", "| --- | --- |"]
    pkg = s.get("package", {})
    lines.append(f"| Package | {' '.join(x for x in (pkg.get('name') or 'unknown', pkg.get('version')) if x)} |")
    vcs = s.get("vcs", {})
    commit = (vcs.get("commit") or "")[:12]
    shown = (commit + (" (dirty)" if vcs.get("dirty") else "") if commit
             else "git repository with no commits" if vcs.get("kind") == "git" else "not a git checkout")
    lines.append(f"| Commit | {shown} |")
    lic = s["license"]
    lines.append(f"| License | {lic.get('spdx') or 'not detected'} (copyleft: {lic.get('copyleft')}) |")
    lines.append(f"| Kind | {s['kind']} |")
    lines.append(f"| Primary language | {s['primaryLanguage']} |")
    lines.append(f"| Source LOC | {s['sourceLoc']} |")
    t = s["tests"]
    lines.append(f"| Tests | {t['files']} files, {t['loc']} LOC, {t['cases']} cases, ratio {t['ratio']} |")
    lines.append(f"| Test runners | {', '.join(t['runners']) or 'none detected'} |")
    lines.append(f"| Public symbols | {s['publicSymbols']} |")
    cc = s.get("couplingCounts", {})
    lines.append("| Modules by coupling | " + ", ".join(f"{k} {v}" for k, v in sorted(cc.items())) + " |")
    lines.append(f"| Runtimes | {', '.join(r['runtime'] + ' ' + r['spec'] for r in s['runtimes']) or 'not declared'} |")
    lines.append(f"| Sampled | {'yes, ' + str(s['coverage']['scanned']) + ' of ' + str(s['coverage']['codeFiles']) + ' files' if s['sampled'] else 'no'} |")
    lines.append("")
    lines.append("| Module | Language | LOC | Coupling | Signals | Risk tags | Public symbols |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for m in s["modules"]:
        if m["role"] != "source":
            continue
        pub = ", ".join(x["name"] for x in m["symbols"] if x.get("public"))[:120]
        lines.append(f"| {m['id']} | {m['language']} | {m['loc']} | {m['coupling']} | {', '.join(m['signals'])} | "
                     f"{', '.join(m['risk'])} | {pub} |")
    if s["graph"]["cycles"]:
        lines.append("")
        lines.append("Import cycles: " + "; ".join(" <-> ".join(c) for c in s["graph"]["cycles"]))
    return "\n".join(lines)


def cmd_survey(args: argparse.Namespace) -> int:
    if args.facts:
        print(markdown_facts(read_json(find_workspace(args.workspace) / "survey.json")))
        return 0
    ws = None
    root = args.path
    subpath = args.subpath
    if args.write:
        from .state import Workspace
        ws = Workspace(find_workspace(args.workspace))
        root = root or ws.config["source"].get("path")
        subpath = subpath or ws.config["source"].get("subpath")
        if not root and ws.config["source"].get("mode") != "artifact":
            raise PorterError("source path unknown: run porter.py source fetch first, or pass a path")
    if ws is not None and ws.config["source"].get("mode") == "artifact" and not args.path \
            and not ws.p("recover/source").exists():
        from .recover import survey_from_recovery
        result = survey_from_recovery(ws.path)
    elif not root:
        raise PorterError("pass the source path, or --write inside a workspace")
    else:
        result = run_survey(Path(root), subpath, args.max_files)
    if ws is not None:
        src = ws.config["source"]
        src["language"] = result["primaryLanguage"]
        vcs = result["vcs"]
        if vcs.get("commit") and not src.get("commit"):
            src["commit"] = vcs["commit"]
            src["dirty"] = vcs.get("dirty")
        pkg = src.get("package") or {}
        pkg.setdefault("name", None)
        pkg.setdefault("version", None)
        pkg["name"] = pkg.get("name") or result["package"].get("name")
        pkg["version"] = pkg.get("version") or result["package"].get("version")
        src["package"] = pkg
        if result.get("mode") == "artifact" and (src.get("license") or {}).get("spdx"):
            result["license"].update(spdx=src["license"]["spdx"], copyleft=src["license"]["copyleft"],
                                     note="stated by the user (state source)")
        else:
            src["license"] = {"spdx": result["license"]["spdx"], "copyleft": result["license"]["copyleft"]}
        write_json(ws.p("survey.json"), result)
        write_json(ws.p("config.json"), ws.config)
    if args.out:
        write_json(args.out, result)
    if args.json:
        emit(result, True)
    else:
        print(markdown_facts(result))
        if ws is not None:
            print(f"\nWrote {ws.p('survey.json')}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("survey", help="scan a source project and write survey.json")
    p.add_argument("path", nargs="?", help="source root (default: the workspace's source path)")
    p.add_argument("--subpath", help="package directory inside a monorepo")
    p.add_argument("--max-files", type=int, default=4000, help="sample above this many code files")
    p.add_argument("--write", action="store_true", help="write .porter/survey.json and update config")
    p.add_argument("--workspace")
    p.add_argument("--out", help="also write the JSON here")
    p.add_argument("--json", action="store_true", help="print JSON instead of the markdown facts")
    p.add_argument("--facts", action="store_true", help="print the facts table of the workspace's survey.json and exit")
    p.set_defaults(func=cmd_survey)
