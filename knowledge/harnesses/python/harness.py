#!/usr/bin/env python3
"""AgentPorter parity harness for Python ports (see knowledge/oracles/CONTRACT.md).

Runs every case in .porter/fixtures/<unit>/*.json through the binding table in bindings.py and writes
.porter/runs/<run>/<unit>.json. It never compares: porter.py parity collect does that.
Standard library only, Python 3.9+:
    python porter/harness.py --workspace .porter --run <run> [--unit <unit>] [--bindings porter/bindings.py]"""
from __future__ import annotations

import argparse
import asyncio
import base64
import dataclasses
import datetime as dt
import decimal
import enum
import importlib.util
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

DRIVER = "agentporter/knowledge/harnesses/python/harness.py"
MAX_DEPTH = 64
MAX_ITEMS = 10000
SAFE_INT = 2 ** 53


class HarnessError(Exception):
    pass


class CaseTimeout(BaseException):
    pass


class _Undefined:
    def __repr__(self) -> str:
        return "UNDEFINED"


# Return this from a binding when the source returned JavaScript undefined (serialized as {"$undefined": true}).
UNDEFINED = _Undefined()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def serialize(value, depth: int = 0):
    if depth > MAX_DEPTH:
        return {"$type": type(value).__name__, "truncated": True}
    d = depth + 1
    if value is UNDEFINED:
        return {"$undefined": True}
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


def _await(value):
    return asyncio.run(value) if inspect.iscoroutine(value) else value


def run_case(binding, inp: dict, timeout: float) -> tuple[dict, float]:
    decoded = decode(inp)
    args, kwargs = decoded.get("args", []), decoded.get("kwargs", {})
    started = time.perf_counter()
    try:
        value = run_with_timeout(lambda: _await(binding(args, kwargs, decoded)), timeout)
        return {"kind": "value", "value": serialize(value)}, (time.perf_counter() - started) * 1000
    except CaseTimeout:
        return {"kind": "error", "category": "timeout", "message": f"timed out after {timeout}s"}, timeout * 1000
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return {"kind": "error", "category": type(exc).__name__, "message": str(exc)}, elapsed


def load_bindings(path: Path) -> dict:
    if not path.is_file():
        raise HarnessError(f"no bindings file at {path}")
    # Bindings import UNDEFINED with `from harness import UNDEFINED`; make that resolve to this module.
    sys.modules.setdefault("harness", sys.modules[__name__])
    spec = importlib.util.spec_from_file_location("porter_bindings", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table = getattr(module, "BINDINGS", None)
    if not isinstance(table, dict):
        raise HarnessError(f"{path} must define BINDINGS = {{call id: function}}")
    return table


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="AgentPorter Python parity harness")
    ap.add_argument("--workspace", default=".porter")
    ap.add_argument("--run", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    ap.add_argument("--unit", action="append", help="unit to run (repeatable; default: every fixture unit)")
    ap.add_argument("--bindings", default=str(here / "bindings.py"))
    ap.add_argument("--path", action="append", default=[], help="extra directory to put on sys.path (repeatable)")
    ap.add_argument("--timeout", type=float, default=10.0, help="seconds per case")
    args = ap.parse_args(argv)

    cwd = Path.cwd()
    for root in reversed(args.path + ([str(cwd / "src")] if (cwd / "src").is_dir() else []) + [str(cwd)]):
        if root not in sys.path:
            sys.path.insert(0, root)
    try:
        bindings = load_bindings(Path(args.bindings).resolve())
        ws = Path(args.workspace).resolve()
        fixtures = ws / "fixtures"
        units = args.unit or (sorted(p.name for p in fixtures.iterdir() if p.is_dir()) if fixtures.is_dir() else [])
        if not units:
            raise HarnessError(f"no fixtures under {fixtures}")
        missing = 0
        for unit in units:
            if not (fixtures / unit).is_dir():
                raise HarnessError(f"no fixtures for unit {unit}")
            started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            results = []
            for f in sorted((fixtures / unit).glob("*.json")):
                fixture = json.loads(f.read_text(encoding="utf-8"))
                for case in fixture["cases"]:
                    if case["expect"]["kind"] == "cli":
                        continue
                    binding = bindings.get(case["call"])
                    if binding is None:
                        missing += 1
                        actual, ms = {"kind": "error", "category": "MissingBinding", "message": f"no binding for {case['call']}"}, 0.0
                    else:
                        actual, ms = run_case(binding, case.get("input", {}), args.timeout)
                    results.append({"case": case["case"], "actual": actual, "durationMs": round(ms, 4)})
            _write(ws / "runs" / args.run / f"{unit}.json", {
                "schema": 1,
                "unit": unit,
                "runner": {"language": "python", "driver": DRIVER,
                           "runtime": f"{sys.implementation.name} {sys.version.split()[0]}"},
                "startedAt": started_at,
                "results": results,
            })
            errors = sum(1 for r in results if r["actual"]["kind"] == "error")
            print(f"{unit}: ran {len(results)} cases ({errors} errors) -> runs/{args.run}/{unit}.json")
        if missing:
            sys.stderr.write(f"harness: {missing} case(s) have no binding (recorded as MissingBinding)\n")
    except HarnessError as exc:
        sys.stderr.write(f"harness: {exc}\n")
        return 2
    return 0


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main())
