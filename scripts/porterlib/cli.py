"""Black-box CLI oracle and harness. The same runner executes the original program (record) and the port
(run), so both sides see identical argv, stdin, environment and working files."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from . import jsonschema
from .common import PorterError, now_iso, read_json, write_json
from .state import Workspace

TIMEOUT = 30.0


def _decode(raw: bytes) -> tuple[str, bool]:
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace"), True


def execute_case(cmd: list[str], inp: dict, timeout: float) -> tuple[dict, float, list[str]]:
    tags: list[str] = []
    with tempfile.TemporaryDirectory(prefix="porter-cli-") as tmp:
        root = Path(tmp)
        for rel, content in (inp.get("files") or {}).items():
            target = (root / rel).resolve()
            if root.resolve() not in target.parents:
                raise PorterError(f"input file path escapes the case directory: {rel}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = tmp
        env.update({k: str(v) for k, v in (inp.get("env") or {}).items()})
        stdin = inp.get("stdin")
        started = time.perf_counter()
        try:
            p = subprocess.run(cmd + [str(a) for a in inp.get("argv", [])], cwd=tmp, env=env, capture_output=True,
                               input=stdin.encode("utf-8") if isinstance(stdin, str) else b"", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"kind": "error", "category": "timeout", "message": f"timed out after {timeout}s"}, timeout * 1000, ["timeout"]
        except OSError as exc:
            raise PorterError(f"cannot run {' '.join(cmd)}: {exc}")
        ms = (time.perf_counter() - started) * 1000
        out, bad1 = _decode(p.stdout)
        err, bad2 = _decode(p.stderr)
        if bad1 or bad2:
            tags.append("non-utf8-output")
        result: dict = {"kind": "cli", "stdout": out, "stderr": err, "exitCode": p.returncode}
        collect = inp.get("collect") or []
        if collect:
            files = {}
            for rel in collect:
                f = root / rel
                files[rel] = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None
            result["files"] = files
    return result, ms, tags


def _command(ws: Workspace, exe: str | None) -> list[str]:
    if exe:
        return shlex.split(exe)
    rec = ws.p("recover/recovery.json")
    if rec.exists():
        cmd = read_json(rec).get("oracle", {}).get("command") or []
        if cmd:
            return list(cmd)
    raise PorterError("pass --exe with the command to run")


def _expanded(ws: Workspace, unit: str) -> list[dict]:
    path = ws.p(f"oracle/expanded/{unit}.json")
    if not path.exists():
        raise PorterError(f"no {path}; run porter.py fixtures expand --unit {unit}")
    return read_json(path)["cases"]


def cmd_record(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    cmd = _command(ws, args.exe)
    cases = _expanded(ws, args.unit)
    src = ws.config["source"]
    pkg = src.get("package") or {}
    art = ws.p("recover/artifact.json")
    runtime = f"artifact sha256 {read_json(art)['sha256']}" if art.exists() else " ".join(cmd)
    out_cases, timings = [], {}
    for c in cases:
        expect, ms, tags = execute_case(cmd, c["input"], args.timeout)
        case = {"case": c["case"], "origin": c.get("origin", "hand-written"), "call": c["call"], "input": c["input"], "expect": expect}
        for key in ("normalize",):
            if c.get(key):
                case[key] = c[key]
        if tags or c.get("tags"):
            case["tags"] = sorted(set(c.get("tags", [])) | set(tags))
        out_cases.append(case)
        timings[c["case"]] = round(ms, 3)
    fixture = {"schema": 1, "unit": args.unit,
               "oracle": {"language": src.get("language") or "unknown", "package": pkg.get("name") or Path(cmd[0]).name,
                          "version": pkg.get("version") or "unknown", "commit": src.get("commit"), "runtime": runtime,
                          "driver": "porter.py cli record", "recordedAt": now_iso()},
               "cases": out_cases}
    errors = jsonschema.validate_named(fixture, "fixture")
    if errors:
        raise PorterError("recorded fixture is invalid:\n  " + "\n  ".join(errors))
    out = Path(args.out) if args.out else ws.p(f"fixtures/{args.unit}/{args.name}.json")
    write_json(out, fixture)
    if not args.out:
        write_json(ws.p(f"oracle/timings/{args.unit}.json"), {"unit": args.unit, "cases": timings})
    codes: dict[int, int] = {}
    for c in out_cases:
        code = c["expect"].get("exitCode", -1)
        codes[code] = codes.get(code, 0) + 1
    print(f"{args.unit}: recorded {len(out_cases)} cases from {' '.join(cmd)}; exit codes "
          + ", ".join(f"{k}: {v}" for k, v in sorted(codes.items())))
    print(f"Wrote {out}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    cmd = shlex.split(args.exe)
    units = [args.unit] if args.unit else sorted(p.stem for p in ws.p("oracle/expanded").glob("*.json"))
    run = args.run or now_iso().replace(":", "").replace("-", "")
    for unit in units:
        fx_dir = ws.p(f"fixtures/{unit}")
        cases = []
        for f in sorted(fx_dir.glob("*.json")):
            cases += read_json(f)["cases"]
        if not cases:
            raise PorterError(f"no fixtures for {unit}; record them first")
        results = []
        for c in cases:
            actual, ms, _ = execute_case(cmd, c["input"], args.timeout)
            results.append({"case": c["case"], "actual": actual, "durationMs": round(ms, 3)})
        data = {"schema": 1, "unit": unit, "runner": {"language": ws.config["target"].get("language") or "unknown",
                                                      "command": cmd, "driver": "porter.py cli run"},
                "startedAt": now_iso(), "results": results}
        write_json(ws.p(f"runs/{run}/{unit}.json"), data)
        print(f"{unit}: ran {len(results)} cases -> .porter/runs/{run}/{unit}.json")
    print(f"run id: {run}  (next: porter.py parity collect --run {run})")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("cli", help="black-box CLI oracle (record) and harness (run)")
    p.add_argument("--workspace")
    ps = p.add_subparsers(dest="cli_cmd", required=True)
    r = ps.add_parser("record", help="run the original program on oracle/expanded/<unit>.json and write fixtures")
    r.add_argument("--unit", required=True)
    r.add_argument("--exe", help="original command (default: recovery.json oracle.command)")
    r.add_argument("--name", default="cli", help="fixture file name under fixtures/<unit>/")
    r.add_argument("--out", help="write the recording here instead of the corpus (freshness checks)")
    r.add_argument("--timeout", type=float, default=TIMEOUT)
    r.set_defaults(func=cmd_record)
    u = ps.add_parser("run", help="run the port on every recorded fixture and write actuals for parity collect")
    u.add_argument("--exe", required=True, help="command that runs the port, e.g. \"node dist/cli.js\"")
    u.add_argument("--unit")
    u.add_argument("--run", help="run id (default: a timestamp)")
    u.add_argument("--timeout", type=float, default=TIMEOUT)
    u.set_defaults(func=cmd_run)
