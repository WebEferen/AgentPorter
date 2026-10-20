#!/usr/bin/env python3
"""AgentPorter oracle driver for Python sources (see knowledge/oracles/CONTRACT.md).

Records what the pinned Python package does for every case in .porter/oracle/expanded/<unit>.json and
writes .porter/fixtures/<unit>/oracle.json plus .porter/oracle/timings/<unit>.json.
Standard library only. Runs on Python 3.9+ because it runs under the source project's interpreter."""
from __future__ import annotations

import argparse
import asyncio
import base64
import dataclasses
import datetime as dt
import decimal
import enum
import importlib
import inspect
import json
import math
import os
import signal
import sys
import threading
import time
import types
from pathlib import Path

DRIVER = "agentporter/knowledge/oracles/python/oracle.py"
MAX_DEPTH = 64
MAX_ITEMS = 10000
SAFE_INT = 2 ** 53


class OracleError(Exception):
    pass


class CaseTimeout(BaseException):
    pass


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def serialize(value, depth: int = 0):
    if depth > MAX_DEPTH:
        return {"$type": type(value).__name__, "truncated": True}
    d = depth + 1
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, enum.Enum):
        return {"$enum": f"{type(value).__name__}.{value.name}"}
    if isinstance(value, int):
        return {"$int": str(value)} if abs(value) > SAFE_INT else value
    if isinstance(value, float):
        if math.isnan(value):
            return {"$float": "nan"}
        if math.isinf(value):
            return {"$float": "inf" if value > 0 else "-inf"}
        if value == 0.0 and math.copysign(1.0, value) < 0:
            return {"$float": "-0"}
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$bytes": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, decimal.Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return {"$datetime": value.isoformat()}
    if isinstance(value, (list, tuple)):
        return [serialize(v, d) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [serialize(v, d) for v in value]
        return {"$set": sorted(items, key=canonical)}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: serialize(v, d) for k, v in value.items()}
        return {"$map": [[serialize(k, d), serialize(v, d)] for k, v in value.items()]}
    if isinstance(value, (types.GeneratorType, range, map, filter, zip, enumerate, reversed)) or \
            type(value).__name__ in ("dict_keys", "dict_values", "dict_items"):
        out = []
        for i, item in enumerate(value):
            if i >= MAX_ITEMS:
                out.append({"$truncated": MAX_ITEMS})
                break
            out.append(serialize(item, d))
        return out
    if isinstance(value, (types.FunctionType, types.BuiltinFunctionType, types.MethodType)):
        return {"$type": "function", "name": getattr(value, "__qualname__", repr(value))}
    if isinstance(value, type):
        return {"$type": "class", "name": value.__qualname__}
    if isinstance(value, BaseException):
        return {"$type": type(value).__name__, "message": str(value)}
    out = {"$type": type(value).__name__}
    if dataclasses.is_dataclass(value):
        fields = {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
    elif hasattr(value, "_asdict") and isinstance(value, tuple):
        fields = value._asdict()
    elif hasattr(value, "__dict__"):
        fields = dict(vars(value))
    elif hasattr(type(value), "__slots__"):
        fields = {s: getattr(value, s) for s in type(value).__slots__ if hasattr(value, s)}
    else:
        out["repr"] = repr(value)
        return out
    for key in sorted(k for k in fields if not k.startswith("_")):
        out[key] = serialize(fields[key], d)
    return out


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if len(value) == 1:
        (tag, raw), = value.items()
        if tag == "$float":
            return {"nan": math.nan, "inf": math.inf, "-inf": -math.inf, "-0": -0.0}[raw]
        if tag == "$int":
            return int(raw)
        if tag == "$bytes":
            return base64.b64decode(raw)
        if tag == "$decimal":
            return decimal.Decimal(raw)
        if tag == "$datetime":
            return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if tag == "$set":
            return {_hashable(decode(v)) for v in raw}
        if tag == "$map":
            return {_hashable(decode(k)): decode(v) for k, v in raw}
        if tag == "$undefined":
            return None
    return {k: decode(v) for k, v in value.items()}


def _hashable(value):
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, set):
        return frozenset(value)
    return value


def resolve(call: str):
    if ":" not in call:
        raise OracleError(f"call '{call}' is not <module>:<qualified name>")
    module_name, qual = call.split(":", 1)
    obj = importlib.import_module(module_name)
    parts = qual.split(".") if qual else []
    owner = None
    for part in parts:
        owner = obj
        obj = getattr(obj, part)
    return owner, obj, parts


def invoke(call: str, inp: dict):
    owner, target, parts = resolve(call)
    if "init" in inp:
        if not isinstance(owner, type):
            raise OracleError(f"{call}: input.init needs a <Class>.<method> call")
        init = inp["init"] or {}
        instance = owner(*decode(init.get("args", [])), **decode(init.get("kwargs", {})))
        target = getattr(instance, parts[-1])
    if "args" not in inp and "kwargs" not in inp and "init" not in inp:
        return target
    result = target(*decode(inp.get("args", [])), **decode(inp.get("kwargs", {})))
    return asyncio.run(result) if inspect.iscoroutine(result) else result


def run_with_timeout(fn, timeout: float):
    if hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread():
        def on_alarm(signum, frame):
            raise CaseTimeout()
        previous = signal.signal(signal.SIGALRM, on_alarm)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            return fn()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    box: dict = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:
            box["error"] = exc
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise CaseTimeout()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def record_case(case: dict, timeout: float) -> tuple[dict, float]:
    started = time.perf_counter()
    try:
        value = run_with_timeout(lambda: invoke(case["call"], case.get("input", {})), timeout)
        elapsed = (time.perf_counter() - started) * 1000
        return {"kind": "value", "value": serialize(value)}, elapsed
    except CaseTimeout:
        return {"kind": "error", "category": "timeout", "message": f"timed out after {timeout}s"}, timeout * 1000
    except OracleError:
        raise
    except (ImportError, AttributeError) as exc:
        if _resolvable(case["call"]):
            return _error(exc, case), (time.perf_counter() - started) * 1000
        raise OracleError(f"case {case['case']}: cannot resolve {case['call']}: {exc}") from exc
    except (Exception, SystemExit) as exc:
        return _error(exc, case), (time.perf_counter() - started) * 1000


def _resolvable(call: str) -> bool:
    try:
        resolve(call)
        return True
    except Exception:
        return False


def _error(exc: BaseException, case: dict) -> dict:
    out = {"kind": "error", "category": type(exc).__name__, "message": str(exc)}
    if case.get("messagePattern"):
        out["messagePattern"] = case["messagePattern"]
    return out


def package_version(name: str | None) -> str | None:
    if not name:
        return None
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AgentPorter Python oracle driver")
    ap.add_argument("--workspace", default=".porter")
    ap.add_argument("--unit", action="append", help="unit to record (repeatable; default: every expanded unit)")
    ap.add_argument("--package-version")
    ap.add_argument("--commit")
    ap.add_argument("--path", action="append", default=[], help="extra directory to put on sys.path (repeatable)")
    ap.add_argument("--timeout", type=float, default=10.0, help="seconds per case")
    args = ap.parse_args(argv)

    ws = Path(args.workspace).resolve()
    config = json.loads((ws / "config.json").read_text(encoding="utf-8"))
    src = config.get("source", {})
    roots = list(args.path)
    if src.get("path"):
        base = Path(src["path"])
        if src.get("subpath"):
            base = base / src["subpath"]
        roots += [str(base / "src"), str(base)] if (base / "src").is_dir() else [str(base)]
    for root in reversed(roots):
        if root not in sys.path:
            sys.path.insert(0, root)

    expanded_dir = ws / "oracle" / "expanded"
    units = args.unit or sorted(p.stem for p in expanded_dir.glob("*.json"))
    if not units:
        sys.stderr.write(f"oracle: no expanded cases in {expanded_dir}; run porter.py fixtures expand\n")
        return 2
    pkg = src.get("package") or {}
    name = pkg.get("name")
    version = args.package_version or pkg.get("version") or package_version(name) or "unknown"
    for unit in units:
        spec = json.loads((expanded_dir / f"{unit}.json").read_text(encoding="utf-8"))
        if spec.get("kind") == "cli":
            sys.stderr.write(f"oracle: unit {unit} is a CLI unit; record it with porter.py cli record\n")
            return 2
        cases, timings = [], {}
        try:
            for case in spec["cases"]:
                expect, ms = record_case(case, args.timeout)
                out = {k: v for k, v in case.items() if k != "messagePattern"}
                out["expect"] = expect
                cases.append(out)
                timings[case["case"]] = round(ms, 4)
        except OracleError as exc:
            sys.stderr.write(f"oracle: {exc}\n")
            return 2
        fixture = {
            "schema": 1,
            "unit": unit,
            "oracle": {
                "language": "python",
                "package": name or units[0],
                "version": version,
                "commit": args.commit or src.get("commit"),
                "runtime": f"{sys.implementation.name} {sys.version.split()[0]}",
                "driver": DRIVER,
                "recordedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            },
            "cases": cases,
        }
        _write(ws / "fixtures" / unit / "oracle.json", fixture)
        _write(ws / "oracle" / "timings" / f"{unit}.json", {"unit": unit, "cases": timings})
        errors = sum(1 for c in cases if c["expect"]["kind"] == "error")
        print(f"{unit}: recorded {len(cases)} cases ({errors} errors) -> fixtures/{unit}/oracle.json")
    return 0


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main())
