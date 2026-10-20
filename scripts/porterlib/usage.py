"""Find which symbols of each dependency the source actually uses (its used surface)."""
from __future__ import annotations

import argparse
import ast
import re
from collections import defaultdict
from pathlib import Path

from .common import PorterError, emit, find_workspace, iter_files, read_json, read_text_safe, write_json
from .langs import EXT_LANG
from .survey import JS_STRIP, _role

PY_ALIASES = {
    "pyyaml": ["yaml"], "beautifulsoup4": ["bs4"], "pillow": ["PIL"], "scikit-learn": ["sklearn"],
    "python-dateutil": ["dateutil"], "msgpack-python": ["msgpack"], "protobuf": ["google.protobuf"],
    "pyjwt": ["jwt"], "python-dotenv": ["dotenv"], "attrs": ["attr", "attrs"], "pycryptodome": ["Crypto"],
    "opencv-python": ["cv2"], "typing-extensions": ["typing_extensions"], "importlib-metadata": ["importlib_metadata"],
    "pymysql": ["pymysql"], "psycopg2-binary": ["psycopg2"], "python-magic": ["magic"], "pyserial": ["serial"],
    "setuptools": ["setuptools", "pkg_resources"], "text-unidecode": ["text_unidecode"],
    "python-slugify": ["slugify"], "ruamel.yaml": ["ruamel.yaml"], "google-cloud-storage": ["google.cloud.storage"],
}


def import_names(name: str, ecosystem: str, override: str | None = None) -> list[str]:
    if override:
        return [x.strip() for x in override.split(",") if x.strip()]
    if ecosystem == "pypi":
        base = name.lower()
        if base in PY_ALIASES:
            return PY_ALIASES[base]
        cands = {base.replace("-", "_"), base.replace("-", "_").replace(".", "_")}
        for prefix in ("python-", "py-", "django-", "flask-"):
            if base.startswith(prefix):
                cands.add(base[len(prefix):].replace("-", "_"))
        if base.endswith("-python"):
            cands.add(base[: -len("-python")].replace("-", "_"))
        return sorted(cands)
    if ecosystem == "crates":
        return [name.replace("-", "_")]
    if ecosystem == "hex":
        return ["".join(part.capitalize() for part in name.split("_"))]
    if ecosystem == "rubygems":
        return sorted({name, name.replace("-", "/")})
    return [name]


def _match(module: str, names: list[str]) -> str | None:
    for n in names:
        if module == n or module.startswith(n + ".") or module.startswith(n + "/"):
            return n
    return None


class Usage:
    def __init__(self) -> None:
        self.symbols: dict[str, int] = defaultdict(int)
        self.files: set[str] = set()
        self.test_files: set[str] = set()
        self.aux_files: set[str] = set()
        self.refs = 0
        self.imports = 0


def scan_python(text: str, deps: dict[str, list[str]], out: dict[str, Usage], rel: str, is_test,
                dynamic: list[str] | None = None) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        fn = node.func
        fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
        if fname not in ("import_module", "__import__"):
            continue
        if not (isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            if dynamic is not None:
                dynamic.append(f"{rel}:{node.lineno}")
            continue
        for dep, names in deps.items():
            if _match(node.args[0].value, names):
                _touch(out[dep], rel, is_test)
                out[dep].imports += 1
                out[dep].symbols["(dynamic import)"] += 1
    mod_alias: dict[str, tuple[str, str]] = {}
    sym_alias: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                for dep, names in deps.items():
                    hit = _match(a.name, names)
                    if hit:
                        local = a.asname or a.name.split(".")[0]
                        mod_alias[local] = (dep, a.name if a.asname else a.name.split(".")[0])
                        _touch(out[dep], rel, is_test)
                        out[dep].imports += 1
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for dep, names in deps.items():
                if _match(node.module, names):
                    _touch(out[dep], rel, is_test)
                    out[dep].imports += 1
                    for a in node.names:
                        if a.name == "*":
                            out[dep].symbols["*"] += 1
                        else:
                            sym_alias[a.asname or a.name] = (dep, a.name)
                            out[dep].symbols.setdefault(a.name, 0)
    if not (mod_alias or sym_alias):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in mod_alias:
            dep, _ = mod_alias[node.value.id]
            out[dep].symbols[node.attr] += 1
            out[dep].refs += 1
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in sym_alias:
            dep, sym = sym_alias[node.id]
            out[dep].symbols[sym] += 1
            out[dep].refs += 1


JS_IMPORT = re.compile(r"""import\s+(?:type\s+)?(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\}|\*\s+as\s+(\w+))?\s*from\s*['"]([^'"]+)['"]""")
JS_SIDE = re.compile(r"""import\s+['"]([^'"]+)['"]""")
JS_REQ_NAMED = re.compile(r"""\{([^}]*)\}\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)""")
JS_REQ = re.compile(r"""(\w+)\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)(?:\.(\w+))?""")
JS_REQ_ANY = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")


def scan_js(text: str, deps: dict[str, list[str]], out: dict[str, Usage], rel: str, is_test: bool) -> None:
    locals_: dict[str, tuple[str, str | None]] = {}
    hit_any = False

    def dep_of(spec: str) -> str | None:
        for dep, names in deps.items():
            if _match(spec, names):
                return dep
        return None
    for m in JS_IMPORT.finditer(text):
        default, named, ns, spec = m.groups()
        dep = dep_of(spec)
        if not dep:
            continue
        hit_any = True
        _touch(out[dep], rel, is_test)
        out[dep].imports += 1
        if default:
            locals_[default] = (dep, "default")
        if ns:
            locals_[ns] = (dep, None)
        for item in (named or "").split(","):
            item = item.strip().removeprefix("type ").strip()
            if item:
                orig, _, local = item.partition(" as ")
                locals_[(local or orig).strip()] = (dep, orig.strip())
    for m in JS_REQ_NAMED.finditer(text):
        dep = dep_of(m.group(2))
        if dep:
            for item in m.group(1).split(","):
                orig, _, local = item.strip().partition(":")
                if orig.strip():
                    locals_[(local or orig).strip()] = (dep, orig.strip())
    for m in JS_REQ.finditer(text):
        dep = dep_of(m.group(2))
        if dep:
            locals_[m.group(1)] = (dep, m.group(3) or None)
    for m in list(JS_REQ_ANY.finditer(text)) + list(JS_SIDE.finditer(text)):
        dep = dep_of(m.group(1))
        if dep:
            hit_any = True
            _touch(out[dep], rel, is_test)
            out[dep].imports += 1
    if not hit_any and not locals_:
        return
    code = JS_STRIP.sub(" ", text)
    for local, (dep, member) in locals_.items():
        _touch(out[dep], rel, is_test)
        if member is None:
            for m in re.finditer(rf"(?<![\w$.]){re.escape(local)}\.(\w+)", code):
                out[dep].symbols[m.group(1)] += 1
                out[dep].refs += 1
            calls = len(re.findall(rf"(?<![\w$.]){re.escape(local)}\s*\(", code))
            if calls:
                out[dep].symbols["(default call)"] += calls
                out[dep].refs += calls
        else:
            n = max(0, len(re.findall(rf"(?<![\w$.]){re.escape(local)}\b", code)) - 1)
            out[dep].symbols[member] += n
            out[dep].refs += n


GO_IMPORT = re.compile(r'(?:^import\s+|^\s+)(?:(\w+|\.|_)\s+)?"([^"]+)"', re.M)


def scan_go(text: str, deps: dict[str, list[str]], out: dict[str, Usage], rel: str, is_test: bool) -> None:
    for m in GO_IMPORT.finditer(text):
        alias, path = m.groups()
        for dep, names in deps.items():
            if _match(path, names):
                _touch(out[dep], rel, is_test)
                out[dep].imports += 1
                last = path.rstrip("/").split("/")[-1]
                if re.fullmatch(r"v\d+", last):
                    last = path.split("/")[-2]
                local = alias or last.replace("-", "_").replace(".", "_")
                if local in (".", "_"):
                    continue
                code = JS_STRIP.sub(" ", text)
                for sm in re.finditer(rf"\b{re.escape(local)}\.(\w+)", code):
                    out[dep].symbols[sm.group(1)] += 1
                    out[dep].refs += 1


IMPORT_LINE = {
    "java": re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)(?:\.\*)?\s*;", re.M),
    "kotlin": re.compile(r"^\s*import\s+([\w.]+)", re.M),
    "scala": re.compile(r"^\s*import\s+([\w.]+)", re.M),
    "php": re.compile(r"^\s*use\s+([\w\\]+)", re.M),
    "csharp": re.compile(r"^\s*using\s+(?:static\s+)?([\w.]+)\s*;", re.M),
    "ruby": re.compile(r"""^\s*require\s+['"]([\w/.-]+)['"]""", re.M),
    "elixir": re.compile(r"^\s*(?:alias|import|use|require)\s+([\w.]+)", re.M),
    "rust": re.compile(r"^\s*(?:pub\s+)?use\s+([\w:]+)", re.M),
}


def scan_generic(text: str, lang: str, deps: dict[str, list[str]], out: dict[str, Usage], rel: str, is_test: bool) -> None:
    rx = IMPORT_LINE.get(lang)
    if not rx:
        return
    code = JS_STRIP.sub(" ", text)
    for m in rx.finditer(text):
        target = m.group(1).replace("::", ".").replace("\\", ".").strip(".")
        for dep, names in deps.items():
            norm = [n.replace("\\", ".").replace("::", ".").strip(".") for n in names]
            if _match(target, norm):
                _touch(out[dep], rel, is_test)
                out[dep].imports += 1
                leaf = target.split(".")[-1]
                if leaf and leaf[0].isupper():
                    n = max(0, len(re.findall(rf"\b{re.escape(leaf)}\b", code)) - 1)
                    out[dep].symbols[leaf] += n
                    out[dep].refs += n
                else:
                    out[dep].symbols[target] += 0


def _touch(u: Usage, rel: str, role) -> None:
    if role is True or role == "test":
        u.test_files.add(rel)
    elif role == "aux":
        u.aux_files.add(rel)
    else:
        u.files.add(rel)


def scan(root: Path, dependencies: list[dict], overrides: dict[str, str]) -> dict:
    deps = {d["name"]: import_names(d["name"], d.get("ecosystem", ""), overrides.get(d["name"])) for d in dependencies}
    needs_override = [d["name"] for d in dependencies if d.get("ecosystem") in ("maven", "packagist", "nuget") and d["name"] not in overrides]
    out: dict[str, Usage] = defaultdict(Usage)
    dynamic: list[str] = []
    for f in iter_files(root):
        lang = EXT_LANG.get(f.suffix.lower())
        if not lang:
            continue
        text = read_text_safe(f)
        if text is None:
            continue
        rel = f.relative_to(root).as_posix()
        is_test = _role(rel, f.name)
        if lang == "python":
            scan_python(text, deps, out, rel, is_test, dynamic)
        elif lang in ("javascript", "typescript", "coffeescript"):
            scan_js(text, deps, out, rel, is_test)
        elif lang == "go":
            scan_go(text, deps, out, rel, is_test)
        else:
            scan_generic(text, lang, deps, out, rel, is_test)
    result = {}
    for d in dependencies:
        u = out.get(d["name"], Usage())
        if u.files:
            where = "source"
        elif u.test_files:
            where = "tests-only"
        elif u.aux_files:
            where = "aux-only"
        else:
            where = "unused"
        result[d["name"]] = {
            "importNames": deps[d["name"]],
            "usedIn": where,
            "symbols": dict(sorted(u.symbols.items(), key=lambda kv: (-kv[1], kv[0]))),
            "callSites": u.refs,
            "imports": u.imports,
            "modules": sorted(u.files),
            "testModules": sorted(u.test_files),
            "auxModules": sorted(u.aux_files),
            "resolved": d["name"] not in needs_override,
        }
    return {"schema": 1, "root": str(root), "usage": result,
            "unresolved": needs_override,
            "dynamicImports": dynamic,
            "note": ("pass --import-name NAME=PREFIX for these; their import namespace cannot be derived from the package name"
                     if needs_override else None)}


def cmd_usage(args: argparse.Namespace) -> int:
    ws = None
    root = args.path
    if args.write or not root or not args.dep:
        ws = find_workspace(args.workspace, must_exist=bool(args.write or not root))
    cfg = read_json(ws / "config.json") if ws and (ws / "config.json").exists() else {}
    if not root:
        root = cfg.get("source", {}).get("path")
        sub = cfg.get("source", {}).get("subpath")
        if root and sub:
            root = str(Path(root) / sub)
    if not root:
        raise PorterError("source path unknown: pass a path or run inside a workspace")
    overrides = dict(x.split("=", 1) for x in (args.import_name or []))
    if args.dep:
        deps = [{"name": n, "ecosystem": args.ecosystem or ""} for n in args.dep]
    else:
        graph_path = ws / "cache" / "deps-graph.json"
        if not graph_path.exists():
            raise PorterError("no .porter/cache/deps-graph.json: run porter.py deps-graph --write first")
        graph = read_json(graph_path)
        deps = [d for d in graph["dependencies"] if d["direct"] or args.all]
    result = scan(Path(root), deps, overrides)
    if args.write and ws:
        write_json(ws / "cache" / "usage.json", result)
    if args.json:
        emit(result, True)
        return 0
    print("| Dependency | Used in | Imports | References | Symbols | Modules |\n| --- | --- | --- | --- | --- | --- |")
    for name, u in result["usage"].items():
        syms = ", ".join(f"{k} ({v})" for k, v in list(u["symbols"].items())[:8])
        mods = ", ".join(u["modules"][:4]) + (" ..." if len(u["modules"]) > 4 else "")
        print(f"| {name} | {u['usedIn']}{'' if u['resolved'] else ' (unresolved)'} | {u['imports']} | {u['callSites']} | {syms} | {mods} |")
    if result["note"]:
        print(f"\nNote: {', '.join(result['unresolved'])}: {result['note']}")
    if result["dynamicImports"]:
        print(f"\nComputed imports the scan cannot resolve: {', '.join(result['dynamicImports'][:10])}. "
              "A dependency marked unused may still be loaded there: read those lines before deciding DROP.")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("usage-scan", help="find the used surface of each dependency in the source")
    p.add_argument("path", nargs="?")
    p.add_argument("--dep", action="append", help="scan one dependency (repeatable); default: all direct deps from deps-graph")
    p.add_argument("--ecosystem", help="ecosystem for --dep (pypi, npm, go, crates, maven, packagist, rubygems, nuget, hex)")
    p.add_argument("--import-name", action="append", metavar="DEP=PREFIX", help="import namespace override, comma-separated prefixes allowed")
    p.add_argument("--all", action="store_true", help="include transitive dependencies")
    p.add_argument("--workspace")
    p.add_argument("--write", action="store_true", help="write .porter/cache/usage.json")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_usage)
