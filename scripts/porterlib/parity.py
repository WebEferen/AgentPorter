"""Parity: compare harness actuals with oracle fixtures, assign a parity level per unit, write parity.json
and PARITY.md, import reference-test results, and check DIVERGENCE(id) markers in the target code."""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import math
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from . import jsonschema
from .common import PorterError, iter_files, now_iso, read_json, read_text_safe, write_json, write_text
from .fixtures import load_unit
from .state import Workspace

MARKER = re.compile(r"DIVERGENCE\(([a-z0-9][a-z0-9-]*)\)")
REF_TAG = re.compile(r"\[ref:\s*([^\]]+?)\s*\]")
TARGET_EXTS = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py", ".go", ".rs", ".kt", ".kts", ".java", ".cs", ".rb", ".php",
               ".ex", ".exs", ".swift", ".scala"}


# ---------------------------------------------------------------- comparison

def _float_tol(normalize: list[str]) -> float | None:
    for n in normalize:
        if n.startswith("float:"):
            return float(n.split(":", 1)[1])
    return None


def _norm_str(s: str, normalize: list[str]) -> str:
    if "lf" in normalize:
        s = s.replace("\r\n", "\n")
    if "nfc" in normalize:
        s = unicodedata.normalize("NFC", s)
    if "trim-trailing-ws" in normalize:
        s = "\n".join(line.rstrip() for line in s.split("\n"))
    if "lines-unordered" in normalize:
        body, nl = (s[:-1], "\n") if s.endswith("\n") else (s, "")
        s = "\n".join(sorted(body.split("\n"))) + nl
    if "trim" in normalize:
        s = s.strip()
    return s


def _norm(value: object, normalize: list[str]) -> object:
    if isinstance(value, str):
        return _norm_str(value, normalize)
    if isinstance(value, list):
        items = [_norm(v, normalize) for v in value]
        if "unordered" in normalize:
            items = sorted(items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        return items
    if isinstance(value, dict):
        return {k: _norm(v, normalize) for k, v in value.items()}
    return value


def _num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _instant(v: object) -> dt.datetime | None:
    if isinstance(v, dict) and v.keys() == {"$datetime"} and isinstance(v["$datetime"], str):
        try:
            return dt.datetime.fromisoformat(v["$datetime"])
        except ValueError:
            return None
    return None


def deep_equal(a: object, b: object, tol: float | None) -> bool:
    ia, ib = _instant(a), _instant(b)
    if ia is not None and ib is not None:
        return (ia.tzinfo is None) == (ib.tzinfo is None) and ia == ib
    if _num(a) and _num(b):
        if tol is not None:
            if math.isnan(a) and math.isnan(b):
                return True
            return math.isclose(a, b, rel_tol=tol, abs_tol=tol)
        return a == b
    if type(a) is not type(b) and not (_num(a) and _num(b)):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(deep_equal(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(deep_equal(a[k], b[k], tol) for k in a)
    return a == b


def _equal_both(expect: object, actual: object, normalize: list[str]) -> tuple[bool, bool]:
    """Return (equal, needed_normalization)."""
    if deep_equal(expect, actual, None):
        return True, False
    if normalize and deep_equal(_norm(expect, normalize), _norm(actual, normalize), _float_tol(normalize)):
        return True, True
    return False, False


def compare(expect: dict, actual: dict | None, normalize: list[str], error_map: dict) -> tuple[str, str | None]:
    """Status is pass, normalized, fail or missing."""
    if actual is None:
        return "missing", "no actual result for this case"
    kind = expect["kind"]
    if actual.get("kind") != kind:
        detail = actual.get("message") or actual.get("category") or json.dumps(actual.get("value"), ensure_ascii=False)
        return "fail", f"expected {kind}, got {actual.get('kind')}: {str(detail)[:200]}"
    if kind == "value":
        ok, used = _equal_both(expect.get("value"), actual.get("value"), normalize)
        if ok:
            return ("normalized" if used else "pass"), None
        return "fail", f"value {json.dumps(actual.get('value'), ensure_ascii=False)[:200]} != " \
                       f"{json.dumps(expect.get('value'), ensure_ascii=False)[:200]}"
    if kind == "error":
        want = expect.get("category")
        mapped = error_map.get(want, want) if want else None
        got = actual.get("category")
        if mapped and got not in {want, mapped}:
            return "fail", f"error category {got} != {mapped}" + (f" (mapped from {want})" if mapped != want else "")
        used = bool(mapped and got == mapped and mapped != want)
        if "ignore-message" in normalize:
            return ("normalized" if used or expect.get("message") else "pass"), None
        msg = actual.get("message") or ""
        if expect.get("messagePattern"):
            if not re.search(expect["messagePattern"], msg):
                return "fail", f"message {msg[:160]!r} does not match /{expect['messagePattern']}/"
            return ("normalized" if used else "pass"), None
        if expect.get("message") is not None:
            ok, n = _equal_both(expect["message"], msg, normalize)
            if not ok:
                return "fail", f"message {msg[:160]!r} != {expect['message'][:160]!r}"
            used = used or n
        return ("normalized" if used else "pass"), None
    if kind == "cli":
        used = False
        if expect.get("exitCode") != actual.get("exitCode"):
            return "fail", f"exit code {actual.get('exitCode')} != {expect.get('exitCode')}"
        streams = ["stdout"] + ([] if "ignore-stderr" in normalize else ["stderr"])
        for stream in streams:
            e, a = expect.get(stream, ""), actual.get(stream, "")
            if "json" in normalize and stream == "stdout":
                try:
                    e, a = json.loads(e) if e.strip() else None, json.loads(a) if a.strip() else None
                except json.JSONDecodeError:
                    pass
            ok, n = _equal_both(e, a, normalize)
            if not ok:
                return "fail", f"{stream} differs: {_first_diff(str(e), str(a))}"
            used = used or n or ("json" in normalize and stream == "stdout")
        if "ignore-stderr" in normalize and expect.get("stderr", "") != actual.get("stderr", ""):
            used = True
        if expect.get("files") is not None:
            ok, n = _equal_both(expect["files"], actual.get("files"), normalize)
            if not ok:
                return "fail", "files differ"
            used = used or n
        return ("normalized" if used else "pass"), None
    if kind in ("trace", "files"):
        key = "events" if kind == "trace" else "files"
        ok, used = _equal_both(expect.get(key), actual.get(key), normalize)
        return (("normalized" if used else "pass"), None) if ok else ("fail", f"{key} differ")
    return "fail", f"unknown expect kind {kind}"


def _first_diff(e: str, a: str) -> str:
    for i, (x, y) in enumerate(zip(e, a)):
        if x != y:
            return f"at char {i}: expected {e[max(0, i - 20):i + 40]!r}, got {a[max(0, i - 20):i + 40]!r}"
    return f"length {len(a)} != {len(e)}; tail expected {e[min(len(e), len(a)):][:60]!r}, got {a[min(len(e), len(a)):][:60]!r}"


# ---------------------------------------------------------------- collection

def latest_run(ws: Workspace) -> str | None:
    runs = ws.p("runs")
    if not runs.is_dir():
        return None
    dirs = [d for d in runs.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime).name if dirs else None


def scan_markers(root: Path, exclude: Path | None = None) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for f in iter_files(root):
        if f.suffix not in TARGET_EXTS or (exclude and exclude in f.parents):
            continue
        text = read_text_safe(f)
        if not text or "DIVERGENCE(" not in text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in MARKER.finditer(line):
                found.setdefault(m.group(1), []).append(f"{f.relative_to(root).as_posix()}:{i}")
    return found


def _timings(ws: Workspace, unit: str) -> dict[str, float]:
    path = ws.p(f"oracle/timings/{unit}.json")
    if not path.exists():
        return {}
    data = read_json(path)
    return {k: float(v) for k, v in (data.get("cases") or data).items() if _num(v)}


def unit_parity(ws: Workspace, unit: str, run: str | None, error_map: dict, divergences: list[dict],
                reftests: dict) -> dict:
    fx = ws.p("fixtures")
    cases, oracles = load_unit(fx, unit) if (fx / unit).is_dir() else ([], [])
    actual_path = ws.p(f"runs/{run}/{unit}.json") if run else None
    actuals: dict[str, dict] = {}
    durations: dict[str, float] = {}
    notes: list[str] = []
    if actual_path and actual_path.exists():
        data = read_json(actual_path)
        errs = jsonschema.validate_named(data, "actuals")
        if errs:
            notes.append(f"actuals file has schema errors: {'; '.join(errs[:3])}")
        for r in data.get("results", []):
            actuals[r["case"]] = r["actual"]
            if _num(r.get("durationMs")):
                durations[r["case"]] = float(r["durationMs"])
    elif cases:
        notes.append(f"no actuals at runs/{run}/{unit}.json" if run else "no harness run found under .porter/runs/")
    unit_divs = [d for d in divergences if d["unit"] == unit]
    counts = {"total": len(cases), "passed": 0, "normalized": 0, "divergent": 0, "failed": 0, "missing": 0}
    mismatches, used_divs = [], set()
    for c in cases:
        status, detail = compare(c["expect"], actuals.get(c["case"]), c.get("normalize", []), error_map)
        if status in ("fail", "missing"):
            hit = next((d for d in unit_divs if any(fnmatch.fnmatchcase(c["case"], pat) for pat in d["cases"])), None)
            if hit:
                status = "divergent"
                used_divs.add(hit["id"])
        key = {"pass": "passed", "normalized": "normalized", "divergent": "divergent", "fail": "failed", "missing": "missing"}[status]
        counts[key] += 1
        if status in ("fail", "missing"):
            mismatches.append({"case": c["case"], "status": status, "detail": detail, "file": c["_file"]})
    refs = reftests.get(unit, [])
    ref_counts = {k: sum(1 for r in refs if r["resolution"] == k) for k in ("PASS", "FAIL", "OUT-OF-SCOPE", "DIVERGENCE", "UNRESOLVED")}
    ref_counts["total"] = len(refs)
    state_unit = ws.state["units"].get(unit, {})
    plan_unit = next((u for u in (ws.plan() or {}).get("units", []) if u["id"] == unit), {})
    if state_unit.get("status") == "DEFERRED":
        level = "OUT-OF-SCOPE"
    elif counts["failed"] or counts["missing"] or ref_counts["FAIL"] or ref_counts["UNRESOLVED"]:
        level = "GAP"
    elif counts["total"] == 0:
        if ref_counts["PASS"] and (plan_unit.get("noFixturesReason") or not cases):
            level = "ASSERTED"
        else:
            level = "GAP"
            notes.append("no fixtures and no passing reference tests")
    elif counts["divergent"] or ref_counts["DIVERGENCE"]:
        level = "DIVERGENT"
    elif counts["normalized"]:
        level = "EQUIVALENT"
    else:
        level = "EXACT"
    perf = None
    oracle_t = _timings(ws, unit)
    common = [k for k in durations if k in oracle_t and oracle_t[k] > 0]
    if len(common) >= 5:
        ratio = statistics.median(durations[k] / oracle_t[k] for k in common)
        perf = {"cases": len(common), "medianRatio": round(ratio, 3), "note": "target time / oracle time; above 1 is slower"}
    return {
        "unit": unit,
        "level": level,
        "fixtures": counts,
        "referenceTests": ref_counts,
        "divergences": sorted(used_divs),
        "mismatches": mismatches[:50],
        "perf": perf,
        "notes": notes,
        "oracle": oracles[0] if oracles else None,
    }


def collect(ws: Workspace, unit: str | None, run: str | None) -> dict:
    run = run or latest_run(ws)
    error_map = read_json(ws.p("contract/error-map.json"))["map"] if ws.p("contract/error-map.json").exists() else {}
    divergences = read_json(ws.p("divergences.json"))["divergences"] if ws.p("divergences.json").exists() else []
    reftests = read_json(ws.p("reftests.json"))["units"] if ws.p("reftests.json").exists() else {}
    path = ws.p("parity.json")
    prev = read_json(path) if path.exists() else None
    fx_units = {p.name for p in ws.p("fixtures").iterdir() if p.is_dir()} if ws.p("fixtures").is_dir() else set()
    units = [unit] if unit else sorted(set(ws.state["units"]) | fx_units)
    entries = {e["unit"]: e for e in (prev or {}).get("units", [])}
    for u in units:
        entries[u] = unit_parity(ws, u, run, error_map, divergences, reftests)
    markers = scan_markers(ws.target_root(), ws.path)
    known = {d["id"] for d in divergences}
    marker_errors = [f"{mid} at {', '.join(locs[:3])}: no entry in divergences.json" for mid, locs in markers.items() if mid not in known]
    marker_errors += [f"divergence {d['id']} ({d['unit']}) has no DIVERGENCE({d['id']}) marker in the target code"
                      for d in divergences if d["id"] not in markers]
    src = ws.config["source"]
    tgt = ws.config["target"]
    ordered = [entries[u] for u in sorted(entries, key=lambda x: (x not in ws.state["units"], x))]
    totals = {"units": len(ordered)}
    for key in ("total", "passed", "normalized", "divergent", "failed", "missing"):
        totals[key] = sum(e["fixtures"][key] for e in ordered)
    for lvl in ("EXACT", "EQUIVALENT", "DIVERGENT", "ASSERTED", "GAP", "OUT-OF-SCOPE"):
        totals[lvl] = sum(1 for e in ordered if e["level"] == lvl)
    return {
        "schema": 1,
        "upstream": {"package": (src.get("package") or {}).get("name"), "version": (src.get("package") or {}).get("version"),
                     "commit": src.get("commit"), "language": src.get("language"), "mode": src.get("mode", "code"),
                     "artifactSha256": _artifact_sha(ws)},
        "target": {"language": tgt.get("language"), "package": tgt.get("package"), "path": tgt.get("path")},
        "evidenceDate": now_iso(),
        "run": run,
        "units": ordered,
        "divergences": divergences,
        "markers": markers,
        "markerErrors": marker_errors,
        "totals": totals,
    }


def _artifact_sha(ws: Workspace) -> str | None:
    p = ws.p("recover/artifact.json")
    return read_json(p).get("sha256") if p.exists() else None


def render_parity_md(parity: dict) -> str:
    up, tg, t = parity["upstream"], parity["target"], parity["totals"]
    origin = f"commit {up['commit'][:12]}" if up.get("commit") else (
        f"artifact sha256 {up['artifactSha256'][:16]}" if up.get("artifactSha256") else "unpinned")
    lines = [
        "# Parity report",
        "",
        f"Upstream: {' '.join(filter(None, [up.get('package') or 'unknown', up.get('version')]))} "
        f"({up.get('language')}, {origin}).",
        f"Port: {tg.get('package') or '(unnamed)'} in {tg.get('language')}. Evidence date: {parity['evidenceDate'][:10]}. "
        f"Harness run: {parity.get('run') or 'none'}.",
        f"Fixtures: {t['total']} cases, {t['passed']} exact, {t['normalized']} normalized, {t['divergent']} divergent, "
        f"{t['failed']} failed, {t['missing']} missing.",
        "",
        "| Unit | Level | Fixtures (exact / normalized / divergent / failed of total) | Reference tests (pass / total) | Divergences | Perf (median ratio) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in parity["units"]:
        f, r = e["fixtures"], e["referenceTests"]
        fx = f"{f['passed']} / {f['normalized']} / {f['divergent']} / {f['failed'] + f['missing']} of {f['total']}"
        perf = f"{e['perf']['medianRatio']}x" if e.get("perf") else "-"
        lines.append(f"| {e['unit']} | {e['level']} | {fx} | {r.get('PASS', 0)} / {r.get('total', 0)} | "
                     f"{', '.join(e['divergences']) or '-'} | {perf} |")
    lines += ["", "Levels: EXACT means every fixture matched byte for byte. EQUIVALENT means every fixture matched under",
              "the normalization declared on the fixture. DIVERGENT means some cases differ on purpose (listed below).",
              "ASSERTED means no oracle fixtures exist and ported reference tests carry the evidence. GAP means a known",
              "mismatch remains.", ""]
    if parity["divergences"]:
        lines += ["## Intentional divergences", ""]
        for d in parity["divergences"]:
            lines.append(f"- **{d['id']}** ({d['unit']}): {d['summary']} Why: {d['rationale']}")
        lines.append("")
    gaps = [e for e in parity["units"] if e["mismatches"]]
    if gaps:
        lines += ["## Open mismatches", ""]
        for e in gaps:
            for m in e["mismatches"][:10]:
                lines.append(f"- {e['unit']} / {m['case']}: {m['detail']}")
        lines.append("")
    if parity["markerErrors"]:
        lines += ["## Marker problems", ""] + [f"- {m}" for m in parity["markerErrors"]] + [""]
    return "\n".join(lines)


# ---------------------------------------------------------------- reference tests

def parse_junit(path: Path) -> list[tuple[str, str]]:
    out = []
    for tc in ET.parse(path).getroot().iter("testcase"):
        name = f"{tc.get('classname', '')} {tc.get('name', '')}".strip()
        if tc.find("skipped") is not None:
            status = "skipped"
        elif tc.find("failure") is not None or tc.find("error") is not None:
            status = "failed"
        else:
            status = "passed"
        out.append((name, status))
    return out


def parse_vitest(path: Path) -> list[tuple[str, str]]:
    data = read_json(path)
    out = []
    for file in data.get("testResults", []):
        for t in file.get("assertionResults", []):
            name = t.get("fullName") or " ".join(t.get("ancestorTitles", []) + [t.get("title", "")])
            out.append((name, {"passed": "passed", "failed": "failed"}.get(t.get("status"), "skipped")))
    return out


def parse_gotest(path: Path) -> list[tuple[str, str]]:
    """go test rewrites spaces in subtest names to underscores, so a tag can also come from t.Log("[ref: <id>]")."""
    out, logged = {}, defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not ev.get("Test"):
            continue
        key = f"{ev.get('Package', '')} {ev['Test']}"
        if ev.get("Action") == "output":
            logged[key] += REF_TAG.findall(ev.get("Output") or "")
        elif ev.get("Action") in ("pass", "fail", "skip"):
            out[key] = {"pass": "passed", "fail": "failed", "skip": "skipped"}[ev["Action"]]
    results = []
    for key, status in out.items():
        refs = [] if REF_TAG.search(key) else list(dict.fromkeys(logged.get(key, [])))
        results += [(f"{key} [ref: {r}]", status) for r in refs] or [(key, status)]
    return results


CARGO_RUNNING = re.compile(r"^\s*Running (?:unittests )?(\S+\.rs)\b")
CARGO_RESULT = re.compile(r"^test (\S+) \.\.\. (ok|FAILED|ignored)\b")
RUST_FN = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)")


def rust_test_refs(root: Path) -> dict[str, dict[str, list[str]]]:
    """[ref: id] tags from the comment lines directly above each Rust fn, by file, then fn name."""
    out: dict[str, dict[str, list[str]]] = {}
    for path in sorted(p for d in ("src", "tests") if (root / d).is_dir() for p in (root / d).rglob("*.rs")):
        pending: list[str] = []
        refs: dict[str, list[str]] = {}
        for line in (read_text_safe(path) or "").splitlines():
            s = line.strip()
            if s.startswith("//"):
                pending += REF_TAG.findall(s)
                continue
            if s.startswith("#["):
                continue
            m = RUST_FN.match(line)
            if m and pending:
                refs.setdefault(m.group(1), []).extend(pending)
            pending = []
        if refs:
            out[path.relative_to(root).as_posix()] = refs
    return out


def _rust_refs_for(tags: dict[str, dict[str, list[str]]], target: str, test: str) -> list[str]:
    parts = test.split("::")
    name, mods = parts[-1], parts[:-1]
    if target.startswith("tests/"):
        files = [f for f in tags if f == target or f.startswith(target[:-3] + "/")]
    elif "/" in target:
        files = [f for f in tags if f.startswith(target.rsplit("/", 1)[0] + "/")]
    else:
        files = list(tags)
    hits = [f for f in files if name in tags[f]]
    if len(hits) > 1 and mods:
        hits = [f for f in hits if any(m in Path(f).with_suffix("").parts for m in mods)] or hits
    return [r for f in hits for r in tags[f][name]]


def parse_cargo(path: Path, root: Path) -> list[tuple[str, str]]:
    """Captured `cargo test` output. Rust test names cannot hold [ref: id], so tags come from comments above the fn."""
    tags = rust_test_refs(root)
    target, out = "", []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = CARGO_RUNNING.match(line)
        if m:
            target = m.group(1)
            continue
        m = CARGO_RESULT.match(line)
        if not m:
            continue
        test, status = m.group(1), {"ok": "passed", "FAILED": "failed", "ignored": "skipped"}[m.group(2)]
        refs = list(dict.fromkeys(_rust_refs_for(tags, target, test)))
        out += [(f"{target} {test} [ref: {r}]".strip(), status) for r in refs] or [(f"{target} {test}".strip(), status)]
    return out


def cmd_reftests(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    if args.format == "cargo":
        results = parse_cargo(Path(args.report), ws.target_root())
    else:
        parser = {"junit": parse_junit, "vitest": parse_vitest, "jest": parse_vitest, "gotest": parse_gotest}[args.format]
        results = parser(Path(args.report))
    path = ws.p("reftests.json")
    data = read_json(path) if path.exists() else {"schema": 1, "units": {}}
    if args.replace:
        for unit, entries in data["units"].items():
            if not args.unit or unit == args.unit:
                for e in entries:
                    if e["resolution"] in ("PASS", "FAIL"):
                        e["resolution"] = "UNRESOLVED"
    plan = ws.plan() or {}
    owners: dict[str, str] = {}
    for u in plan.get("units", []):
        for ref in u.get("referenceTests", []):
            owners[Path(ref).name] = u["id"]
    harvested: dict[str, str] = {}
    for f in sorted(ws.p("oracle/cases").glob("*.json")):
        spec = read_json(f)
        for c in spec.get("cases", []):
            if str(c.get("origin") or "").startswith("reference-test:"):
                harvested[c["origin"].split(":", 1)[1]] = spec.get("unit") or f.stem

    def owner_of(ref: str) -> str | None:
        parts = ref.split("::")
        for i in range(len(parts), 0, -1):
            if "::".join(parts[:i]) in harvested:
                return harvested["::".join(parts[:i])]
        return owners.get(Path(parts[0]).name)
    tagged = untagged = 0
    for name, status in results:
        m = REF_TAG.search(name)
        if not m:
            untagged += 1
            continue
        tagged += 1
        ref = m.group(1)
        unit = args.unit or owner_of(ref)
        if not unit:
            unit = "unassigned"
        entries = data["units"].setdefault(unit, [])
        existing = next((e for e in entries if e["ref"] == ref), None)
        resolution = {"passed": "PASS", "failed": "FAIL", "skipped": "UNRESOLVED"}[status]
        if existing and existing["resolution"] in ("OUT-OF-SCOPE", "DIVERGENCE") and status != "failed":
            continue
        target_test = re.sub(r"\[\s*\]", "", REF_TAG.sub("", name)).strip()
        entry = {"ref": ref, "resolution": resolution, "reason": None, "targetTest": target_test}
        if existing:
            existing.update(entry)
        else:
            entries.append(entry)
    errors = jsonschema.validate_named(data, "reftests")
    if errors:
        raise PorterError("reftests.json would be invalid:\n  " + "\n  ".join(errors))
    write_json(path, data)
    print(f"{tagged} tagged tests imported, {untagged} without a [ref: ...] tag ignored. Wrote {path}")
    if "unassigned" in data["units"]:
        print("Some refs could not be mapped to a unit: pass --unit or list the source test file in plan.json referenceTests")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    parity = collect(ws, args.unit, args.run)
    errors = jsonschema.validate_named(parity, "parity")
    if errors:
        raise PorterError("parity.json would be invalid:\n  " + "\n  ".join(errors))
    if not args.dry_run:
        write_json(ws.p("parity.json"), parity)
    print("| Unit | Level | Pass | Normalized | Divergent | Failed | Missing |\n| --- | --- | --- | --- | --- | --- | --- |")
    shown = [e for e in parity["units"] if not args.unit or e["unit"] == args.unit]
    for e in shown:
        f = e["fixtures"]
        print(f"| {e['unit']} | {e['level']} | {f['passed']} | {f['normalized']} | {f['divergent']} | {f['failed']} | {f['missing']} |")
    for e in shown:
        for m in e["mismatches"][:args.show]:
            print(f"  {e['unit']}/{m['case']}: {m['detail']}")
        for n in e["notes"]:
            print(f"  note ({e['unit']}): {n}")
    for m in parity["markerErrors"]:
        print(f"  marker: {m}")
    print(f"Dry run, parity.json unchanged (run {parity['run']})" if args.dry_run
          else f"Wrote {ws.p('parity.json')} (run {parity['run']})")
    bad = [e for e in shown if e["level"] == "GAP"]
    return 1 if bad else 0


def cmd_report(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    parity = read_json(ws.p("parity.json"))
    md = render_parity_md(parity)
    write_text(ws.p("PARITY.md"), md)
    if args.copy_to:
        write_text(Path(args.copy_to), md)
    print(md)
    return 0


def cmd_markers(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    markers = scan_markers(ws.target_root(), ws.path)
    for mid, locs in sorted(markers.items()):
        print(f"{mid}: {', '.join(locs)}")
    if not markers:
        print("no DIVERGENCE(id) markers in the target code")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("parity", help="compare harness actuals with fixtures and report parity levels")
    p.add_argument("--workspace")
    ps = p.add_subparsers(dest="parity_cmd", required=True)
    c = ps.add_parser("collect", help="write parity.json (exit 1 when a unit is GAP)")
    c.add_argument("--unit")
    c.add_argument("--run", help="run id under .porter/runs (default: the newest)")
    c.add_argument("--show", type=int, default=5, help="mismatches to print per unit")
    c.add_argument("--dry-run", action="store_true", help="compare and print only; parity.json belongs to verify")
    c.set_defaults(func=cmd_collect)
    r = ps.add_parser("report", help="render PARITY.md from parity.json")
    r.add_argument("--copy-to", help="also write PARITY.md here, e.g. the port's docs folder")
    r.set_defaults(func=cmd_report)
    t = ps.add_parser("reftests", help="import ported reference-test results ([ref: id] in test names)")
    t.add_argument("format", choices=("junit", "vitest", "jest", "gotest", "cargo"))
    t.add_argument("report")
    t.add_argument("--unit", help="assign every imported ref to this unit")
    t.add_argument("--replace", action="store_true",
                   help="reset earlier PASS and FAIL rows to UNRESOLVED first, so the report is the only evidence")
    t.set_defaults(func=cmd_reftests)
    m = ps.add_parser("markers", help="list DIVERGENCE(id) markers in the target code")
    m.set_defaults(func=cmd_markers)
