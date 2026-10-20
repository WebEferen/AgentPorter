"""Artifact mode: no source code, only a built artifact (binary, assembly, jar, bundle, app).

Fingerprints the artifact, runs REA (Reverse Engineer Anything, github.com/morluto/rea) and black-box
probes, and turns the evidence into recovery.json, a synthetic survey and a dependency list."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from .common import PorterError, find_workspace, now_iso, read_json, sha256_path, write_json, write_text

REA_PACKAGE = "rea-agents"
REA_VERSION = "6.7.0"
SCAN_LIMIT = 128 * 1024 * 1024
OUTPUT_LIMIT = 64 * 1024

ELF_MACHINE = {0x03: "x86", 0x28: "arm", 0x3E: "x86_64", 0xB7: "arm64", 0xF3: "riscv64"}
MACHO_CPU = {7: "x86", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64"}
PE_MACHINE = {0x14C: "x86", 0x8664: "x86_64", 0xAA64: "arm64", 0x1C4: "arm"}
SHEBANG_LANG = {"python": "python", "python3": "python", "node": "javascript", "ruby": "ruby", "perl": "perl",
                "php": "php", "bash": "shell", "sh": "shell", "zsh": "shell"}
NATIVE_MARKERS = (
    (b"\xff Go buildinf:", "go", "Go build-information header"),
    (b".dep-v0", "rust", "cargo-auditable .dep-v0 section"),
    (b"/rustc/", "rust", "rustc source path strings"),
    (b"rust_begin_unwind", "rust", "Rust panic runtime symbol"),
    (b"_MEIPASS", "python", "PyInstaller bootloader strings"),
    (b"__swift5_", "swift", "Swift 5 metadata sections"),
    (b"__gxx_personality", "cpp", "C++ exception personality routine"),
    (b"_ZNSt", "cpp", "Itanium C++ mangled std symbols"),
)
ECOSYSTEM_OF_LANG = {"go": "go", "rust": "crates", "csharp": "nuget", "fsharp": "nuget", "java": "maven",
                     "kotlin": "maven", "javascript": "npm", "typescript": "npm", "python": "pypi"}
CLI_KINDS = {"command", "subcommand", "flag", "argument", "stdin", "stdout", "stderr", "env", "file", "exit-code", "config"}
PUBLIC_KINDS = {"command", "subcommand", "function", "class", "export", "endpoint", "event"}


# ---------------------------------------------------------------- detection

def _host_format() -> str:
    return {"darwin": "macho", "linux": "elf", "win32": "pe"}.get(sys.platform, "unknown")


def _host_arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x86_64", "aarch64": "arm64"}.get(m, m)


def _pe_info(path: Path, head: bytes) -> dict:
    out = {"format": "pe", "platform": "native", "arch": None, "dotnet": False}
    try:
        off = struct.unpack("<I", head[0x3C:0x40])[0]
        if head[off:off + 4] != b"PE\0\0":
            return out
        out["arch"] = PE_MACHINE.get(struct.unpack("<H", head[off + 4:off + 6])[0])
        opt = off + 24
        magic = struct.unpack("<H", head[opt:opt + 2])[0]
        dirs = opt + (96 if magic == 0x10B else 112)
        clr_size = struct.unpack("<I", head[dirs + 14 * 8 + 4:dirs + 14 * 8 + 8])[0]
        out["dotnet"] = clr_size > 0
    except (struct.error, IndexError):
        pass
    return out


def _sniff_file(path: Path) -> dict:
    with path.open("rb") as fh:
        head = fh.read(65536)
    name = path.name.lower()
    info: dict = {"format": "unknown", "arch": None, "platform": "unknown", "language": None, "evidence": [], "kind": "unknown"}
    if head[:4] == b"\x7fELF":
        little = head[5] == 1
        machine = struct.unpack("<H" if little else ">H", head[18:20])[0]
        info.update(format="elf", platform="native", arch=ELF_MACHINE.get(machine, hex(machine)))
    elif head[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
        little = head[:4] in (b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe")
        cpu = struct.unpack("<I" if little else ">I", head[4:8])[0]
        info.update(format="macho", platform="native", arch=MACHO_CPU.get(cpu, hex(cpu)))
    elif head[:4] == b"\xca\xfe\xba\xbe" and struct.unpack(">I", head[4:8])[0] < 30:
        count = struct.unpack(">I", head[4:8])[0]
        arches = [MACHO_CPU.get(struct.unpack(">I", head[8 + 20 * i:12 + 20 * i])[0], "?") for i in range(count)]
        info.update(format="macho-fat", platform="native", arch="+".join(arches))
    elif head[:2] == b"MZ":
        pe = _pe_info(path, head)
        info.update(format="pe", arch=pe["arch"], platform="dotnet" if pe["dotnet"] else "native")
        if pe["dotnet"]:
            info["language"] = "csharp"
            info["evidence"].append("PE file with a CLI (.NET) runtime header")
    elif head[:4] == b"\0asm":
        info.update(format="wasm", platform="wasm")
    elif head[:4] == b"PK\x03\x04":
        _sniff_zip(path, info)
    elif name.endswith(".asar"):
        info.update(format="asar", platform="electron", language="javascript", kind="app")
    elif name.endswith(".pyc"):
        info.update(format="pyc", platform="python", language="python", kind="library")
    elif head[:2] == b"#!":
        interp = head[2:200].split(b"\n", 1)[0].decode("utf-8", "replace").strip().split()
        prog = Path(interp[-1] if interp and interp[0].endswith("env") else (interp[0] if interp else "")).name
        lang = SHEBANG_LANG.get(re.sub(r"[\d.]+$", "", prog), None)
        info.update(format="script", platform={"javascript": "node", "python": "python"}.get(lang or "", "unknown"),
                    language=lang, kind="cli")
        info["evidence"].append(f"shebang interpreter {prog}")
    elif path.suffix in (".js", ".mjs", ".cjs"):
        info.update(format="script", platform="node", language="javascript", kind="library")
    if info["platform"] == "native":
        _native_language(path, info)
        if name.endswith((".so", ".dylib", ".dll")) or ".so." in name:
            info["kind"] = "library"
        else:
            info["kind"] = "cli"
    elif info["platform"] == "dotnet":
        info["kind"] = "library" if name.endswith(".dll") else "cli"
        with path.open("rb") as fh:
            if b"FSharp.Core" in fh.read(SCAN_LIMIT):
                info["language"] = "fsharp"
                info["evidence"].append("references FSharp.Core")
    return info


def _sniff_zip(path: Path, info: dict) -> None:
    info["format"] = "zip"
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            manifest = zf.read("META-INF/MANIFEST.MF").decode("utf-8", "replace") if "META-INF/MANIFEST.MF" in names else ""
    except (zipfile.BadZipFile, OSError, KeyError):
        return
    lower = path.name.lower()
    if "AndroidManifest.xml" in names and any(n.startswith("classes") and n.endswith(".dex") for n in names):
        info.update(format="apk", platform="android", language="java", kind="app")
    elif lower.endswith(".aar"):
        info.update(format="aar", platform="android", language="java", kind="library")
    elif manifest or any(n.endswith(".class") for n in names):
        info.update(format="war" if any(n.startswith("WEB-INF/") for n in names) else "jar", platform="jvm", language="java")
        info["kind"] = "cli" if re.search(r"^Main-Class:", manifest, re.M) else "library"
    elif lower.endswith(".whl"):
        info.update(platform="python", language="python", kind="library")
    elif lower.endswith(".nupkg"):
        info.update(platform="dotnet", language="csharp", kind="library")
    if info["platform"] in ("jvm", "android") and any(n.startswith("kotlin/") or n.endswith(".kotlin_module") for n in names):
        info["language"] = "kotlin"
        info["evidence"].append("bundles Kotlin runtime or module metadata")


def _native_language(path: Path, info: dict) -> None:
    with path.open("rb") as fh:
        blob = fh.read(SCAN_LIMIT)
    for marker, lang, why in NATIVE_MARKERS:
        if marker in blob:
            if info["language"] is None:
                info["language"] = lang
            if lang == info["language"]:
                info["evidence"].append(why)
    if info["language"] is None:
        info["language"] = "c"
        info["evidence"].append("no Go, Rust, Swift, C++ or PyInstaller markers: assumed C (low confidence)")


def _sniff_dir(path: Path) -> dict:
    info: dict = {"format": "directory", "arch": None, "platform": "unknown", "language": None, "evidence": [], "kind": "unknown"}
    if path.suffix == ".app" and (path / "Contents").is_dir():
        info.update(format="app-bundle", platform="native", kind="app")
        if (path / "Contents" / "Resources" / "app.asar").exists():
            info.update(platform="electron", language="javascript")
            info["evidence"].append("Contents/Resources/app.asar (Electron)")
        else:
            exes = sorted((path / "Contents" / "MacOS").glob("*"))
            if exes and exes[0].is_file():
                inner = _sniff_file(exes[0])
                info.update(arch=inner["arch"], language=inner["language"])
                info["evidence"] += inner["evidence"]
        return info
    if (path / "resources" / "app.asar").exists() or (path / "app.asar").exists():
        info.update(platform="electron", language="javascript", kind="app")
        info["evidence"].append("app.asar present (Electron)")
    elif (path / "package.json").exists():
        info.update(platform="node", language="javascript")
        try:
            pkg = json.loads((path / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pkg = {}
        info["kind"] = "cli" if pkg.get("bin") else "library"
        info["evidence"].append("package.json present")
    elif list(path.glob("*.deps.json")):
        info.update(platform="dotnet", language="csharp", kind="app")
        info["evidence"].append("*.deps.json present (.NET application)")
    return info


def _runnable(path: Path, info: dict) -> tuple[bool, str | None]:
    plat, fmt = info["platform"], info["format"]
    if plat == "native" and fmt in ("elf", "macho", "macho-fat", "pe"):
        host = _host_format()
        if fmt.startswith("macho") and host != "macho" or fmt in ("elf", "pe") and fmt != host:
            return False, f"{fmt} binary cannot run on this {sys.platform} host; record fixtures on a matching host or VM"
        arch = info.get("arch") or ""
        if _host_arch() not in arch and not (sys.platform == "darwin" and "x86_64" in arch):
            return False, f"{arch} binary on an {_host_arch()} host"
        if path.is_file() and not os.access(path, os.X_OK):
            return False, "file is not executable (chmod +x after confirming with the user)"
        if info["kind"] == "library":
            return False, "shared library: needs a host program or FFI harness to drive it"
        note = "runs under Rosetta" if sys.platform == "darwin" and "arm64" not in arch else None
        return True, note
    need = {"jvm": "java", "dotnet": "dotnet", "node": "node", "python": "python3", "wasm": "wasmtime"}.get(plat)
    if fmt == "script" and info.get("language") == "shell":
        need = "sh"
    if need:
        found = shutil.which(need)
        return (bool(found), None if found else f"{need} is not installed on this host")
    if plat == "electron":
        return False, "Electron apps need the app runtime; drive scenarios with REA capture-electron-scenario"
    if plat == "android":
        return False, "needs an Android device or emulator (REA adb commands)"
    return False, "unknown platform"


def rea_plan(path: Path, info: dict) -> list[dict]:
    p = str(path)
    plan = [{"command": ["inspect-artifact", p], "why": "identity, observations and REA's suggested next probes"}]
    lang, plat, fmt = info.get("language"), info["platform"], info["format"]
    if lang == "go":
        plan.append({"command": ["inspect-go-binary", p], "why": "Go version, main module, dependency modules and build settings"})
    if lang == "rust":
        plan.append({"command": ["inspect-rust-binary", p], "why": "cargo-auditable dependency list (absent section is not proof of no deps)"})
    if plat == "dotnet":
        plan += [{"command": ["inspect-managed-artifact", p], "why": "assembly identity and deployment form"},
                 {"command": ["inspect-managed-members", p], "why": "types, members, signatures and string literals: the public surface"},
                 {"command": ["inspect-managed-native-boundaries", p], "why": "P/Invoke boundaries that need a native plan"}]
    if plat in ("node", "electron") or fmt == "asar":
        plan.append({"command": ["analyze-javascript-application", p], "why": "module graph, exports and evidence for the JS application"})
    if fmt == "script" and lang == "javascript":
        plan.append({"command": ["recover-javascript-sources", p, "<absolute-new-output-dir>"],
                     "why": "readable modules from a bundle, with provenance"})
    if plat == "android":
        plan.append({"command": ["inspect-android-package", p], "why": "manifest, components and declared surface"})
    if fmt == "wasm":
        plan.append({"command": ["inspect-wasm-artifact", p], "why": "imports and exports", "needsProvider": "wabt"})
    if fmt.startswith("macho") or fmt == "app-bundle":
        plan.append({"command": ["inspect-macho", p], "why": "load commands, linked libraries and symbols"})
    if plat == "native" and lang not in ("go", "rust"):
        plan.append({"command": ["analyze", p, "--provider", "ghidra"], "why": "function inventory and strings for native code",
                     "needsProvider": "ghidra"})
    if plat == "native" and lang in ("go", "rust"):
        plan.append({"command": ["analyze", p, "--provider", "ghidra"],
                     "why": "only if probing leaves unknowns: function-level reading of a specific behavior",
                     "needsProvider": "ghidra"})
    return plan


def detect(path: Path) -> dict:
    path = path.expanduser().resolve()
    if not path.exists():
        raise PorterError(f"artifact not found: {path}")
    info = _sniff_dir(path) if path.is_dir() else _sniff_file(path)
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        sha, size = digest.hexdigest(), path.stat().st_size
    else:
        sha = sha256_path(path, ())
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    runnable, note = _runnable(path, info)
    return {
        "schema": 1,
        "path": str(path),
        "sha256": sha,
        "bytes": size,
        "format": info["format"],
        "arch": info["arch"],
        "platform": info["platform"],
        "language": info["language"],
        "languageEvidence": info["evidence"],
        "kind": info["kind"],
        "runnable": runnable,
        "runnableNote": note,
        "reaPlan": rea_plan(path, info),
        "detectedAt": now_iso(),
    }


# ---------------------------------------------------------------- REA runner

def rea_base(explicit: str | None = None) -> list[str] | None:
    raw = explicit or os.environ.get("AGENTPORTER_REA")
    if raw:
        return shlex.split(raw)
    found = shutil.which("rea")
    if found:
        return [found]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", f"{REA_PACKAGE}@{REA_VERSION}"]
    return None


def parse_rea_output(text: str) -> object | None:
    body = [line for line in text.splitlines() if not line.lstrip().startswith('{"rea_progress"')]
    raw = "\n".join(body).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for line in reversed(body):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _evidence_dir(ws: Path) -> Path:
    d = ws / "recover" / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index(ws: Path) -> dict:
    path = _evidence_dir(ws) / "index.json"
    return read_json(path) if path.exists() else {"schema": 1, "entries": []}


def _add_index(ws: Path, entry: dict) -> None:
    idx = _index(ws)
    idx["entries"] = [e for e in idx["entries"] if e["file"] != entry["file"]] + [entry]
    write_json(_evidence_dir(ws) / "index.json", idx)


def _safe_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    if not s:
        raise PorterError("evidence name is empty")
    return s


def cmd_rea(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    base = rea_base(args.rea)
    if not base:
        raise PorterError("REA not found: install Node 22.19+ and run `npx rea-agents setup`, put `rea` on PATH, "
                          "or set AGENTPORTER_REA to the command")
    rea_args = list(args.rea_args)
    if rea_args and rea_args[0] == "--":
        rea_args = rea_args[1:]
    if not rea_args:
        raise PorterError("pass the REA command after the evidence name, e.g. recover rea go inspect-go-binary /abs/path")
    if "--json" not in rea_args and "--format" not in rea_args:
        rea_args.append("--json")
    name = _safe_name(args.name)
    out_dir = _evidence_dir(ws)
    started = time.monotonic()
    try:
        proc = subprocess.run(base + rea_args, capture_output=True, timeout=args.timeout, cwd=ws / "recover")
    except subprocess.TimeoutExpired:
        raise PorterError(f"REA timed out after {args.timeout}s: {' '.join(rea_args)}", code=1)
    except OSError as exc:
        raise PorterError(f"could not start REA ({' '.join(base)}): {exc}")
    text = proc.stdout.decode("utf-8", "replace")
    data = parse_rea_output(text)
    if data is None:
        rel = f"evidence/{name}.txt"
        write_text(out_dir / f"{name}.txt", text + "\n--- stderr ---\n" + proc.stderr.decode("utf-8", "replace"))
    else:
        rel = f"evidence/{name}.json"
        write_json(out_dir / f"{name}.json", data)
    version = None
    try:
        v = subprocess.run(base + ["--version"], capture_output=True, timeout=120)
        version = v.stdout.decode("utf-8", "replace").strip().splitlines()[-1] if v.stdout else None
    except (subprocess.TimeoutExpired, OSError):
        pass
    _add_index(ws, {"file": rel, "producer": "rea", "command": rea_args, "tool": f"rea {version}" if version else "rea",
                    "exit": proc.returncode, "at": now_iso(), "ms": round((time.monotonic() - started) * 1000)})
    print(f"REA exit {proc.returncode}; saved .porter/recover/{rel}")
    if isinstance(data, dict):
        if data.get("error") or data.get("code"):
            print(f"error: {data.get('code')}: {data.get('message') or data.get('error')}")
            if data.get("details"):
                print("details: " + json.dumps(data["details"])[:800])
        else:
            print(f"operation: {data.get('operation')}  confidence: {data.get('confidence')}  authority: {data.get('authority')}")
            nr = data.get("normalized_result")
            if isinstance(nr, dict):
                print("result keys: " + ", ".join(list(nr)[:20]))
            for lim in (data.get("limitations") or [])[:3]:
                print(f"limitation: {str(lim)[:200]}")
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr.decode("utf-8", "replace")[-1500:], file=sys.stderr)
    return 0 if proc.returncode == 0 else 1


# ---------------------------------------------------------------- black-box probing

PROBES = (["--help"], ["-h"], ["help"], ["--version"], ["-version"], ["version"], [])
FLAG_LINE = re.compile(
    r"^\s{1,10}(?P<short>-[A-Za-z0-9?])?(?:,\s*|\s+)?(?P<long>--[A-Za-z0-9][\w-]*)?"
    r"(?P<arg>(?:[ =](?:<[^>]+>|\[[^\]]+\]|[A-Z][A-Z0-9_]+|string|int|float|duration|value))?)"
    r"(?:\s+(?P<desc>\S.*))?$")
GO_FLAG = re.compile(r"^\s{2}-(?P<name>[\w-]+)(?:\s+(?P<arg>\w+))?\s*$")


def _text(raw: bytes) -> tuple[str, bool]:
    s = raw.decode("utf-8", "replace")
    return (s[:OUTPUT_LIMIT], len(s) > OUTPUT_LIMIT)


def run_probe(cmd: list[str], argv: list[str], timeout: float, cwd: Path, env_extra: dict, stdin: str = "") -> dict:
    env = dict(os.environ)
    env.update(env_extra)
    started = time.monotonic()
    out: dict = {"argv": argv, "stdin": stdin, "env": env_extra}
    try:
        p = subprocess.run(cmd + argv, input=stdin.encode("utf-8"), capture_output=True, timeout=timeout, cwd=cwd, env=env)
        stdout, t1 = _text(p.stdout)
        stderr, t2 = _text(p.stderr)
        out.update(exit=p.returncode, stdout=stdout, stderr=stderr, truncated=t1 or t2, timedOut=False)
    except subprocess.TimeoutExpired as exc:
        stdout, _ = _text(exc.stdout or b"")
        stderr, _ = _text(exc.stderr or b"")
        out.update(exit=None, stdout=stdout, stderr=stderr, truncated=False, timedOut=True)
    except OSError as exc:
        out.update(exit=None, error=str(exc))
    out["ms"] = round((time.monotonic() - started) * 1000)
    return out


def parse_help(text: str) -> dict:
    flags, exits, args, section = [], [], [], ""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[A-Za-z][\w ]*:\s*$", stripped):
            section = stripped[:-1].lower()
            continue
        if re.match(r"^usage:", stripped, re.I) or section == "usage":
            usage = re.sub(r"^usage:\s*", "", stripped, flags=re.I)
            for tok in re.findall(r"\[([^\]]+)\]|<([^>]+)>", usage):
                t = tok[0] or tok[1]
                if not t.startswith("-") and t.upper() not in ("OPTIONS", "OPTION", "FLAGS", "ARGS..."):
                    args.append(t)
            continue
        if "exit" in section:
            m = re.match(r"^\s*(\d{1,3})\s+(.+)$", line)
            if m:
                exits.append({"code": int(m.group(1)), "description": m.group(2).strip()})
            continue
        m = GO_FLAG.match(line)
        if m and i + 1 < len(lines) and lines[i + 1].startswith(("    \t", "    ", "\t")):
            flags.append({"short": None, "long": f"-{m.group('name')}", "arg": m.group("arg"),
                          "description": lines[i + 1].strip()})
            continue
        m = FLAG_LINE.match(line)
        if m and (m.group("short") or m.group("long")):
            flags.append({"short": m.group("short"), "long": m.group("long"),
                          "arg": (m.group("arg") or "").strip(" =") or None, "description": (m.group("desc") or "").strip() or None})
    seen, uniq = set(), []
    for f in flags:
        key = (f["short"], f["long"])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return {"flags": uniq, "exitCodes": exits, "arguments": args, "summary": next((l.strip() for l in lines if l.strip()), None)}


def cmd_probe(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    art_path = ws / "recover" / "artifact.json"
    if args.exe:
        cmd = shlex.split(args.exe)
    elif art_path.exists():
        cmd = [read_json(art_path)["path"]]
    else:
        raise PorterError("run porter.py recover detect --write first, or pass --exe")
    probes = [shlex.split(p) for p in args.probe] if args.probe else [list(p) for p in PROBES]
    env_extra = {"NO_COLOR": "1", "TERM": "dumb"}
    runs = []
    with tempfile.TemporaryDirectory(prefix="porter-probe-") as tmp:
        env_extra_run = dict(env_extra, HOME=tmp)
        for argv in probes:
            runs.append(run_probe(cmd, argv, args.timeout, Path(tmp), env_extra_run, args.stdin or ""))
    for r in runs:
        r["env"] = env_extra | {"HOME": "<temp dir>"}
    help_run = next((i for i, r in enumerate(runs) if r["argv"] and r["argv"][0] in ("--help", "-h", "help")
                     and (r.get("stdout") or r.get("stderr")) and not r.get("timedOut")), None)
    parsed = parse_help((runs[help_run].get("stdout") or runs[help_run].get("stderr")) if help_run is not None else "")
    version_run = next((i for i, r in enumerate(runs) if r["argv"] and "version" in r["argv"][0] and r.get("exit") == 0
                        and (r.get("stdout") or "").strip()), None)
    data = {"schema": 1, "command": cmd, "at": now_iso(), "runs": runs, "helpRun": help_run, "versionRun": version_run,
            "parsed": parsed, "note": "probes ran with the given stdin (empty by default), a temporary cwd and HOME; "
                                      "this is not a sandbox"}
    name = _safe_name(args.name)
    write_json(_evidence_dir(ws) / f"{name}.json", data)
    _add_index(ws, {"file": f"evidence/{name}.json", "producer": "porter-probe", "command": cmd, "tool": "porter.py recover probe",
                    "exit": 0, "at": now_iso()})
    print(f"| argv | exit | stdout bytes | stderr bytes | ms |\n| --- | --- | --- | --- | --- |")
    for r in runs:
        status = "timeout" if r.get("timedOut") else r.get("exit")
        print(f"| {' '.join(r['argv']) or '(none)'} | {status} | {len(r.get('stdout') or '')} | {len(r.get('stderr') or '')} | {r['ms']} |")
    print(f"\nParsed from help: {len(parsed['flags'])} flags, {len(parsed['exitCodes'])} exit codes, "
          f"arguments: {', '.join(parsed['arguments']) or 'none'}")
    if version_run is not None:
        print(f"Version output: {runs[version_run]['stdout'].strip()[:120]}")
    print(f"Saved .porter/recover/evidence/{name}.json")
    return 0


# ---------------------------------------------------------------- import evidence into recovery.json

def _ident(text: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-.") or "x"


def _find_packages(obj: object, out: list[dict], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(obj, dict):
        name, ver = obj.get("name"), obj.get("version")
        if isinstance(name, str) and isinstance(ver, str) and re.match(r"^v?\d", ver):
            out.append({"name": name, "version": ver, "root": bool(obj.get("root"))})
        for v in obj.values():
            _find_packages(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _find_packages(v, out, depth + 1)


def _from_rea(data: dict, rel: str, rec: dict, modules: dict) -> None:
    op = data.get("operation") or ""
    nr = data.get("normalized_result") or {}
    origin = rec.setdefault("origin", {})
    if op == "inspect_go_binary":
        bi = nr.get("build_info") or {}
        mod = bi.get("module") or {}
        main = mod.get("main") or {}
        origin["language"] = "go"
        origin["toolchain"] = bi.get("go_version") or origin.get("toolchain")
        origin["package"] = origin.get("package") or main.get("path") or mod.get("path")
        origin["version"] = origin.get("version") or main.get("version")
        for dep in mod.get("dependencies") or []:
            target = dep.get("replacement") or dep
            modules.setdefault(dep["path"], {"name": dep["path"], "version": target.get("version") or dep.get("version"),
                                             "ecosystem": "go", "from": "go-buildinfo", "main": False})
        return
    if op in ("inspect_rust_binary", "inspect_managed_artifact", "inspect_managed_members"):
        eco, src = ("crates", "cargo-auditable") if op == "inspect_rust_binary" else ("nuget", "managed-reference")
        found: list[dict] = []
        _find_packages(nr, found)
        for f in found:
            if f["root"]:
                origin["package"] = origin.get("package") or f["name"]
                origin["version"] = origin.get("version") or f["version"]
                continue
            modules.setdefault(f["name"], {"name": f["name"], "version": f["version"], "ecosystem": eco, "from": src, "main": False})
        if op == "inspect_rust_binary" and found:
            origin["language"] = "rust"


def _from_probe(data: dict, rel: str, rec: dict, existing_ids: set[str]) -> list[dict]:
    items: list[dict] = []
    cmd_name = Path(data["command"][-1] if len(data["command"]) == 1 else data["command"][0]).name
    parsed = data.get("parsed") or {}
    help_ref = f"{rel}#/runs/{data['helpRun']}" if data.get("helpRun") is not None else rel
    group = _ident(cmd_name)

    def add(item: dict) -> None:
        if item["id"] not in existing_ids and all(i["id"] != item["id"] for i in items):
            items.append(item)

    add({"id": f"cmd:{_ident(cmd_name)}", "kind": "command", "name": cmd_name, "group": group,
         "signature": None, "description": parsed.get("summary"), "confidence": "HIGH" if data.get("helpRun") is not None else "MEDIUM",
         "evidence": [help_ref]})
    for f in parsed.get("flags", []):
        label = (f["long"] or f["short"]).lstrip("-")
        names = ", ".join(x for x in (f["short"], f["long"]) if x)
        add({"id": f"flag:{_ident(label)}", "kind": "flag", "name": names, "group": group,
             "signature": f"{names} {f['arg']}" if f.get("arg") else names, "description": f.get("description"),
             "confidence": "MEDIUM", "evidence": [help_ref]})
    for a in parsed.get("arguments", []):
        add({"id": f"arg:{_ident(a)}", "kind": "argument", "name": a, "group": group, "signature": None,
             "description": None, "confidence": "MEDIUM", "evidence": [help_ref]})
    for e in parsed.get("exitCodes", []):
        add({"id": f"exit:{e['code']}", "kind": "exit-code", "name": str(e["code"]), "group": group, "signature": None,
             "description": e["description"], "confidence": "MEDIUM", "evidence": [help_ref]})
    if data.get("versionRun") is not None:
        out = data["runs"][data["versionRun"]]["stdout"].strip()
        m = re.search(r"\bv?(\d+\.\d+(?:\.\d+)?[\w.+-]*)", out)
        if m:
            rec.setdefault("origin", {})["version"] = rec.get("origin", {}).get("version") or m.group(1)
    return items


def build_recovery(ws: Path) -> dict:
    art = read_json(ws / "recover" / "artifact.json")
    path = ws / "recover" / "recovery.json"
    rec = read_json(path) if path.exists() else {
        "schema": 1, "artifact": {}, "origin": {}, "kind": art["kind"] if art["kind"] != "unknown" else "unknown",
        "interface": [], "behaviors": [], "modules": [], "unknowns": [], "oracle": {}, "source": {"path": None, "origin": "none"},
        "evidence": [],
    }
    rec["artifact"] = {"path": art["path"], "sha256": art["sha256"], "format": art["format"]}
    origin = rec.setdefault("origin", {})
    origin.setdefault("language", art.get("language"))
    origin.setdefault("package", None)
    origin.setdefault("version", None)
    origin.setdefault("toolchain", None)
    if not origin.get("language"):
        origin["language"] = art.get("language")
    oracle = rec.setdefault("oracle", {})
    oracle.setdefault("runnable", art["runnable"])
    oracle.setdefault("command", [art["path"]] if art["runnable"] else [])
    oracle.setdefault("note", art.get("runnableNote"))
    modules = {m["name"]: m for m in rec.get("modules", [])}
    existing = {i["id"] for i in rec.get("interface", [])}
    idx = _index(ws)
    for entry in idx["entries"]:
        f = ws / "recover" / entry["file"]
        if f.suffix != ".json" or not f.exists():
            continue
        data = read_json(f)
        if entry["producer"] == "rea" and isinstance(data, dict):
            _from_rea(data, entry["file"], rec, modules)
        elif entry["producer"] == "porter-probe":
            new = _from_probe(data, entry["file"], rec, existing)
            rec["interface"].extend(new)
            existing |= {i["id"] for i in new}
    if origin.get("package") and origin["package"] not in modules:
        modules[origin["package"]] = {"name": origin["package"], "version": origin.get("version"),
                                      "ecosystem": ECOSYSTEM_OF_LANG.get(origin.get("language") or ""), "from": "observed", "main": True}
    rec["modules"] = sorted(modules.values(), key=lambda m: (not m.get("main"), m["name"]))
    rec["evidence"] = [{k: e[k] for k in ("file", "producer", "command", "tool", "exit", "at") if k in e} for e in idx["entries"]]
    return rec


def render_recovery_md(rec: dict, art: dict) -> str:
    o = rec.get("origin", {})
    lines = [
        "# Recovery report",
        "",
        "What AgentPorter and REA recovered from the artifact. Every row cites evidence under `recover/evidence/`.",
        "It is generated from recovery.json by `porter.py recover import --render`: edit recovery.json, then re-render.",
        "",
        rec.get("summary") or "(Add a `summary` to recovery.json: what the artifact is and how confident the recovery is.)",
        "",
        "| Fact | Value |",
        "| --- | --- |",
        f"| Artifact | `{art['path']}` |",
        f"| SHA-256 | `{art['sha256']}` |",
        f"| Format | {art['format']} ({art.get('arch') or 'arch unknown'}), platform {art['platform']} |",
        f"| Original language | {o.get('language') or 'unknown'} ({'; '.join(art.get('languageEvidence') or []) or 'no markers'}) |",
        f"| Package | {o.get('package') or 'unknown'} {o.get('version') or ''} |",
        f"| Toolchain | {o.get('toolchain') or 'unknown'} |",
        f"| Kind | {rec.get('kind')} |",
        f"| Oracle | {'runnable here' if rec['oracle'].get('runnable') else 'not runnable here'}"
        f"{': ' + rec['oracle']['note'] if rec['oracle'].get('note') else ''} |",
        f"| Recovered source | {rec['source'].get('path') or 'none'} ({rec['source'].get('origin')}) |",
        "",
        "## Interface",
        "",
        "| Id | Kind | Name | Description | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in rec["interface"]:
        lines.append(f"| {i['id']} | {i['kind']} | `{i['name']}` | {(i.get('description') or '').replace('|', '/')} | "
                     f"{i['confidence']} | {', '.join(i['evidence'])} |")
    lines += ["", "## Behaviors", ""]
    lines += [f"- **{b['id']}** ({b['confidence']}): {b['statement']} [{', '.join(b['evidence'])}]" for b in rec["behaviors"]] or \
             ["- (none recorded yet: add observed behaviors with evidence)"]
    lines += ["", "## Embedded dependencies", "", "| Module | Version | Ecosystem | From |", "| --- | --- | --- | --- |"]
    for m in rec["modules"]:
        lines.append(f"| {m['name']}{' (main)' if m.get('main') else ''} | {m.get('version') or ''} | {m.get('ecosystem') or ''} | {m['from']} |")
    lines += ["", "## Unknowns", ""]
    lines += [f"- **{u['id']}**: {u['question']}" + (f" Probe: {u['probe']}" if u.get("probe") else "") for u in rec["unknowns"]] or \
             ["- (none recorded)"]
    lines += ["", "## Evidence", "", "| File | Producer | Command | Exit |", "| --- | --- | --- | --- |"]
    for e in rec["evidence"]:
        lines.append(f"| {e['file']} | {e['producer']} | `{' '.join(e.get('command') or [])[:100]}` | {e.get('exit')} |")
    lines += ["", "## Clean-room rule", "",
              "Implementers port from the contract and the fixtures. Decompiled or disassembled code is evidence for",
              "understanding behavior; it is never copied into the port.", ""]
    return "\n".join(lines)


def cmd_detect(args: argparse.Namespace) -> int:
    ws = None
    target = args.path
    if args.write or not target:
        ws = find_workspace(args.workspace)
        cfg = read_json(ws / "config.json")
        target = target or cfg["source"].get("path") or cfg["source"]["location"]
    art = detect(Path(target))
    if args.write and ws:
        write_json(ws / "recover" / "artifact.json", art)
    if args.json:
        print(json.dumps(art, indent=2))
        return 0
    print(f"| Fact | Value |\n| --- | --- |")
    for key in ("path", "sha256", "bytes", "format", "arch", "platform", "language", "kind", "runnable", "runnableNote"):
        print(f"| {key} | {art[key]} |")
    print(f"| language evidence | {'; '.join(art['languageEvidence']) or 'none'} |")
    print("\nREA plan:")
    for step in art["reaPlan"]:
        need = f" (needs provider: {step['needsProvider']})" if step.get("needsProvider") else ""
        print(f"  rea {' '.join(shlex.quote(c) for c in step['command'])} --json   # {step['why']}{need}")
    base = rea_base()
    print(f"\nREA command: {' '.join(base) if base else 'NOT FOUND (npx rea-agents setup, or set AGENTPORTER_REA)'}")
    if args.write and ws:
        print(f"Wrote {ws / 'recover' / 'artifact.json'}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    if not (ws / "recover" / "artifact.json").exists():
        raise PorterError("run porter.py recover detect --write first")
    rec = build_recovery(ws)
    art = read_json(ws / "recover" / "artifact.json")
    write_json(ws / "recover" / "recovery.json", rec)
    md = ws / "recover" / "recovery.md"
    rendered = args.render or not md.exists()
    if rendered:
        write_text(md, render_recovery_md(rec, art))
    cfg_path = ws / "config.json"
    cfg = read_json(cfg_path)
    src = cfg["source"]
    o = rec.get("origin", {})
    src["language"] = o.get("language") or src.get("language")
    pkg = src.get("package") or {}
    pkg["name"] = pkg.get("name") or o.get("package")
    pkg["version"] = pkg.get("version") or o.get("version")
    src["package"] = pkg
    if rec["source"].get("path"):
        src["path"] = str((ws / rec["source"]["path"]).resolve())
    write_json(cfg_path, cfg)
    print(f"recovery.json: {len(rec['interface'])} interface items, {len(rec['behaviors'])} behaviors, "
          f"{len(rec['modules'])} modules, {len(rec['unknowns'])} unknowns, {len(rec['evidence'])} evidence files")
    print(f"origin: {o.get('language')} {o.get('package') or ''} {o.get('version') or ''}".rstrip())
    print(f"Wrote {ws / 'recover' / 'recovery.json'}" + (f" and {md}" if rendered else " (recovery.md kept)"))
    return 0


# ---------------------------------------------------------------- synthetic survey and deps for artifact mode

def survey_from_recovery(ws: Path) -> dict:
    rec = read_json(ws / "recover" / "recovery.json")
    art = read_json(ws / "recover" / "artifact.json")
    lang = rec.get("origin", {}).get("language") or "unknown"
    groups: dict[str, list[dict]] = {}
    for item in rec["interface"]:
        g = item.get("group")
        if not g:
            if item["kind"] in CLI_KINDS:
                g = "cli"
            elif item["kind"] in ("function", "class", "method", "export") and "." in item["name"]:
                g = item["name"].rsplit(".", 1)[0]
            else:
                g = "api"
        groups.setdefault(_ident(g), []).append(item)
    modules = []
    for gid, items in groups.items():
        publics = [i for i in items if i["kind"] in PUBLIC_KINDS] or items[:1]
        pub_ids = {i["id"] for i in publics}
        symbols = []
        for i in items:
            public = i["id"] in pub_ids
            symbols.append({
                "name": re.sub(r"[^A-Za-z0-9_]", "_", i["id"]),
                "interfaceId": i["id"],
                "kind": {"class": "class", "flag": "constant", "env": "constant", "exit-code": "constant"}.get(i["kind"], "function"),
                "line": 0, "endLine": 0, "loc": 0, "public": public,
                "refs": [f"{gid}:{re.sub(r'[^A-Za-z0-9_]', '_', j['id'])}" for j in items if j["id"] not in pub_ids] if public else [],
                "io": [], "risk": [], "external": [],
            })
        cli_like = any(i["kind"] in CLI_KINDS for i in items)
        modules.append({"id": gid, "path": f"artifact:{gid}", "language": lang, "loc": 0, "role": "source",
                        "coupling": "io" if cli_like else "pure", "signals": ["black-box"], "risk": [],
                        "imports": {"internal": [], "external": []}, "symbols": symbols})
    public_count = sum(1 for m in modules for s in m["symbols"] if s["public"])
    return {
        "schema": 1,
        "generatedAt": now_iso(),
        "mode": "artifact",
        "root": art["path"],
        "subpath": None,
        "sampled": False,
        "coverage": {"codeFiles": 0, "scanned": 0},
        "vcs": {},
        "license": {"spdx": None, "copyleft": "unknown", "files": [],
                    "note": "license is not recoverable from a binary: ask the user and record it with state source"},
        "package": {"name": rec.get("origin", {}).get("package"), "version": rec.get("origin", {}).get("version")},
        "languages": [{"language": lang, "files": 0, "loc": 0}],
        "primaryLanguage": lang,
        "tests": {"files": 0, "loc": 0, "cases": 0, "ratio": None, "runners": [], "modules": []},
        "manifests": [],
        "tooling": [],
        "runtimes": [],
        "entryPoints": [{"kind": "cli", "target": art["path"]}] if rec.get("kind") == "cli" else [],
        "packages": [],
        "kind": rec.get("kind") or "unknown",
        "couplingCounts": {"io": sum(1 for m in modules if m["coupling"] == "io"),
                           "pure": sum(1 for m in modules if m["coupling"] == "pure")},
        "sourceLoc": 0,
        "publicSymbols": public_count,
        "graph": {"leaves": [m["id"] for m in modules], "hubs": [], "cycles": []},
        "modules": modules,
    }


def deps_from_recovery(ws: Path) -> dict:
    rec = read_json(ws / "recover" / "recovery.json")
    deps = []
    for m in rec.get("modules", []):
        if m.get("main"):
            continue
        deps.append({"name": m["name"], "ecosystem": m.get("ecosystem") or "unknown", "scope": "runtime", "direct": True,
                     "versionSpec": None, "version": m.get("version"), "manifests": [f"recover/recovery.json ({m['from']})"],
                     "roleHint": "unknown"})
    return {
        "schema": 1,
        "generatedAt": now_iso(),
        "root": rec["artifact"]["path"],
        "ecosystems": sorted({d["ecosystem"] for d in deps}),
        "manifests": [{"path": "recover/recovery.json", "parsed": True}],
        "counts": {"direct": len(deps), "directRuntime": len(deps), "transitive": 0},
        "dependencies": deps,
        "notes": ["artifact mode: modules embedded in the binary; direct and transitive cannot be told apart, so every one "
                  "needs a decision. Usage is unknown without source: check behaviors and probe evidence instead."],
    }


def cmd_register(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    src = Path(args.file)
    if not src.is_file():
        raise PorterError(f"not a file: {src}")
    name = _safe_name(args.name)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        rel = f"evidence/{name}.json"
        write_json(_evidence_dir(ws) / f"{name}.json", data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        rel = f"evidence/{name}{src.suffix or '.txt'}"
        shutil.copyfile(src, _evidence_dir(ws) / Path(rel).name)
    _add_index(ws, {"file": rel, "producer": args.producer, "command": shlex.split(args.command) if args.command else [],
                    "tool": args.tool, "exit": None, "at": now_iso()})
    print(f"Registered .porter/recover/{rel} ({args.producer})")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("recover", help="artifact mode: fingerprint, run REA, probe and build recovery.json")
    ps = p.add_subparsers(dest="recover_cmd", required=True)
    d = ps.add_parser("detect", help="identify the artifact and print the REA plan")
    d.add_argument("path", nargs="?")
    d.add_argument("--write", action="store_true", help="write .porter/recover/artifact.json")
    d.add_argument("--json", action="store_true")
    d.add_argument("--workspace")
    d.set_defaults(func=cmd_detect)
    r = ps.add_parser("rea", help="run one REA command and save its evidence: recover rea <name> <rea args...>")
    r.add_argument("name", help="evidence file name, e.g. go-buildinfo")
    r.add_argument("rea_args", nargs=argparse.REMAINDER)
    r.add_argument("--rea", help="REA command (default: $AGENTPORTER_REA, rea on PATH, or npx rea-agents@" + REA_VERSION + ")")
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--workspace")
    r.set_defaults(func=cmd_rea)
    pr = ps.add_parser("probe", help="run the artifact with help/version/no-arg probes and parse its CLI surface")
    pr.add_argument("--exe", help="command to run (default: the artifact path)")
    pr.add_argument("--probe", action="append", help="custom argv string; repeatable (replaces the default probes); write --probe=\"-m x\" when it starts with a dash")
    pr.add_argument("--name", default="probe")
    pr.add_argument("--stdin", help="text fed to every probe's stdin (default: empty)")
    pr.add_argument("--timeout", type=float, default=10.0)
    pr.add_argument("--workspace")
    pr.set_defaults(func=cmd_probe)
    g = ps.add_parser("register", help="add an evidence file produced elsewhere (REA MCP tool output, notes, captures)")
    g.add_argument("name")
    g.add_argument("--file", required=True)
    g.add_argument("--producer", choices=("rea", "manual"), default="rea")
    g.add_argument("--command", help="the REA tool or command that produced it")
    g.add_argument("--tool", help="tool and version, e.g. 'rea 6.7.0 (MCP)'")
    g.add_argument("--workspace")
    g.set_defaults(func=cmd_register)
    i = ps.add_parser("import", help="merge evidence into recovery.json (keeps edits) and render recovery.md if missing")
    i.add_argument("--render", action="store_true", help="re-render recovery.md from recovery.json")
    i.add_argument("--workspace")
    i.set_defaults(func=cmd_import)
