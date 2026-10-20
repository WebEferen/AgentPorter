"""Single writer of .porter/state.json: phases, gates, units, stage card, PORTING.md."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import jsonschema
from .common import (
    KNOWLEDGE, PorterError, find_workspace, now_iso, read_json, sha256_path, write_json, write_text,
)
from .graph import cycles as find_cycles
from .langs import normalize_lang

PHASES = ("recover", "survey", "target", "deps", "contract", "strategy", "implement", "verify")
PREREQ = {
    "recover": (),
    "survey": ("recover",),
    "target": ("survey",),
    "deps": ("target",),
    "contract": ("deps",),
    "strategy": ("contract",),
    "implement": ("strategy",),
    "verify": ("strategy",),
}
OUTPUTS = {
    "recover": ("recover/artifact.json", "recover/recovery.json", "recover/recovery.md"),
    "survey": ("survey.json", "survey.md"),
    "target": ("target.json", "target.md"),
    "deps": ("deps.json", "deps.md"),
    "contract": ("contract/api.json", "contract/contract.md", "fixtures"),
    "strategy": ("plan.json", "strategy.md", "decomposition.md"),
    "implement": (),
    "verify": ("parity.json", "PARITY.md"),
}
HASH_EXCLUDE = ("adversarial*.json",)
TASKS = (
    "read-contract", "scaffold", "implement", "mark-divergences", "port-tests", "wire-fixtures",
    "green", "review", "apply-findings", "verify", "report", "commit",
)
GATED = ("recover", "target", "deps", "strategy")
SATISFIED = ("DONE", "SKIPPED")
TERMINAL = {"DONE", "BLOCKED", "DEFERRED"}
ACTIVE = {"IN_PROGRESS", "IMPLEMENTED", "REVIEWED", "VERIFIED", "GAP"}
CALLABLE_KINDS = {"function", "method", "class"}
PASSING_LEVELS = {"EXACT", "EQUIVALENT", "DIVERGENT", "ASSERTED"}
DEFAULT_BUDGETS = {
    "unitMaxLoc": 400,
    "unitMaxSymbols": 8,
    "unitMinLoc": 30,
    "attemptsPerUnit": 3,
    "discoveredUnits": 5,
    "portMaxDepth": 1,
    "portMaxLoc": 2000,
}
WS_GITIGNORE = "cache/\nruns/\noracle/expanded/\noracle/.venv/\noracle/node_modules/\noracle/build/\n*.tmp\n"


# ---------------------------------------------------------------- workspace

class Workspace:
    def __init__(self, path: Path):
        self.path = path
        self.root = path.parent
        self.config = read_json(path / "config.json")
        self.state = read_json(path / "state.json")

    @classmethod
    def open(cls, explicit: str | None = None) -> "Workspace":
        return cls(find_workspace(explicit))

    def p(self, rel: str) -> Path:
        return self.path / rel

    def save(self) -> None:
        errors = jsonschema.validate_named(self.state, "state")
        if errors:
            raise PorterError("refusing to write invalid state.json:\n  " + "\n  ".join(errors))
        write_json(self.path / "state.json", self.state)

    def log(self, event: str, **fields: Any) -> None:
        entry = {"at": now_iso(), "event": event}
        entry.update({k: v for k, v in fields.items() if v is not None})
        self.state["history"].append(entry)

    def target_root(self) -> Path:
        return (self.root / self.config["target"].get("path", ".")).resolve()

    def plan(self) -> dict | None:
        path = self.p("plan.json")
        return read_json(path) if path.exists() else None


def new_state(budgets: dict, mode: str, target_given: bool) -> dict:
    phases = {p: {"status": "PENDING", "at": None, "gate": None, "artifacts": {}} for p in PHASES}
    if mode != "artifact":
        phases["recover"].update(status="SKIPPED", gate="source code available")
    if target_given:
        phases["target"].update(status="DONE", at=now_iso(), gate="given")
    return {
        "schema": 1,
        "phase": None,
        "phases": phases,
        "units": {},
        "budgets": {
            "attemptsPerUnit": budgets["attemptsPerUnit"],
            "discoveredUnits": budgets["discoveredUnits"],
            "discoveredUsed": 0,
        },
        "stale": [],
        "history": [],
    }


def upstream(phase: str) -> list[str]:
    out, stack = [], list(PREREQ[phase])
    while stack:
        p = stack.pop()
        if p not in out:
            out.append(p)
            stack.extend(PREREQ[p])
    return [p for p in PHASES if p in out]


def downstream(phase: str) -> list[str]:
    out, frontier = [], {phase}
    for p in PHASES:
        if p != phase and any(pre in frontier for pre in PREREQ[p]):
            out.append(p)
            frontier.add(p)
    return out


# ---------------------------------------------------------------- staleness

VERIFY_ORIGIN = re.compile(r"^(generated:)?[\w.-]*adversarial", re.I)


def _verify_added(case: dict) -> bool:
    return bool(VERIFY_ORIGIN.match(str(case.get("origin") or "")))


def fixtures_digest(path: Path) -> str | None:
    """Hash of the contract's fixture corpus. Cases the verifier adds (origin adversarial...) and the recording
    timestamp are left out, so verify can extend the corpus without making the contract and its downstream STALE."""
    if not path.is_dir():
        return None
    h = hashlib.sha256()
    for f in sorted(x for x in path.rglob("*") if x.is_file() and not any(x.match(pat) for pat in HASH_EXCLUDE)):
        h.update(f.relative_to(path).as_posix().encode() + b"\0")
        try:
            data = json.loads(f.read_text(encoding="utf-8")) if f.suffix == ".json" else None
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("cases"), list):
            oracle = {k: v for k, v in (data.get("oracle") or {}).items() if k != "recordedAt"}
            data = {"unit": data.get("unit"), "oracle": oracle,
                    "cases": [c for c in data["cases"] if not _verify_added(c)]}
            h.update(json.dumps(data, sort_keys=True, ensure_ascii=False).encode())
        else:
            h.update(f.read_bytes())
    return "sha256:" + h.hexdigest()


def artifact_hashes(ws: Workspace, phase: str) -> dict[str, str]:
    out = {}
    for rel in OUTPUTS[phase]:
        digest = fixtures_digest(ws.p(rel)) if rel == "fixtures" else sha256_path(ws.p(rel), HASH_EXCLUDE)
        if digest:
            out[rel] = digest
    return out


def refresh_staleness(ws: Workspace) -> list[str]:
    """Mark downstream phases STALE when a completed phase's outputs changed afterwards."""
    changed = []
    for phase in PHASES:
        info = ws.state["phases"][phase]
        if info["status"] not in ("DONE", "GATE_WAIT") or not info.get("artifacts"):
            continue
        current = artifact_hashes(ws, phase)
        if current != info["artifacts"]:
            changed.append(phase)
            info["artifacts"] = current
            hit = []
            for down in downstream(phase):
                if ws.state["phases"][down].get("gate") == "given":
                    continue
                if ws.state["phases"][down]["status"] in ("DONE", "GATE_WAIT", "IN_PROGRESS"):
                    ws.state["phases"][down]["status"] = "STALE"
                    hit.append(down)
            ws.log("phase.changed", phase=phase, stale=hit or None)
    ws.state["stale"] = [p for p in PHASES if ws.state["phases"][p]["status"] == "STALE"]
    return changed


# ---------------------------------------------------------------- units

def unit_ready(ws: Workspace, unit_id: str, plan: dict | None) -> bool:
    if ws.state["units"][unit_id]["status"] != "PENDING":
        return False
    deps = _plan_unit(plan, unit_id).get("dependsOn", []) if plan else []
    return all(ws.state["units"].get(d, {}).get("status") == "DONE" for d in deps)


def _plan_unit(plan: dict | None, unit_id: str) -> dict:
    for unit in (plan or {}).get("units", []):
        if unit["id"] == unit_id:
            return unit
    return {}


def display_status(ws: Workspace, unit_id: str, plan: dict | None) -> str:
    return "READY" if unit_ready(ws, unit_id, plan) else ws.state["units"][unit_id]["status"]


def parity_entry(ws: Workspace, unit_id: str) -> dict | None:
    path = ws.p("parity.json")
    if not path.exists():
        return None
    for entry in read_json(path).get("units", []):
        if entry["unit"] == unit_id:
            return entry
    return None


def set_unit(ws: Workspace, unit_id: str, status: str, task: str | None, level: str | None,
             note: str | None) -> None:
    units = ws.state["units"]
    if unit_id not in units:
        raise PorterError(f"unknown unit '{unit_id}'. Known: {', '.join(sorted(units)) or 'none'}")
    unit = units[unit_id]
    current = unit["status"]
    plan = ws.plan()
    budget = ws.state["budgets"]["attemptsPerUnit"]

    def need(cond: bool, msg: str) -> None:
        if not cond:
            raise PorterError(f"{unit_id}: {current} -> {status} refused: {msg}", code=1)

    if status == current and status != "IN_PROGRESS":
        raise PorterError(f"{unit_id} is already {status}", code=1)
    if status == "IN_PROGRESS":
        if current == "IN_PROGRESS":
            pass
        elif current == "BLOCKED":
            need(bool(note), "retrying a BLOCKED unit needs --note recording the user's decision")
            unit["attempts"] = 0
        else:
            need(current in ("PENDING", "GAP"), "only PENDING, GAP or BLOCKED units can start")
            deps = _plan_unit(plan, unit_id).get("dependsOn", [])
            not_done = [d for d in deps if units.get(d, {}).get("status") != "DONE"]
            need(not not_done, f"dependencies not DONE: {', '.join(not_done)}")
            need(ws.state["phases"]["implement"]["status"] == "IN_PROGRESS",
                 "implement phase is not IN_PROGRESS (run preflight implement)")
        if current != "IN_PROGRESS":
            unit["attempts"] = unit.get("attempts", 0) + 1
            need(unit["attempts"] <= budget,
                 f"attempt budget {budget} exhausted; set BLOCKED with --note and report to the user")
            unit["task"] = task or TASKS[0]
    elif status == "IMPLEMENTED":
        need(current == "IN_PROGRESS", "unit must be IN_PROGRESS")
        need(_task_at_least(unit, "green"), "task 'green' not reached (build, lint, typecheck, tests)")
    elif status == "REVIEWED":
        need(current == "IMPLEMENTED", "unit must be IMPLEMENTED")
        need(_task_at_least(unit, "apply-findings"), "review findings not applied (task 'apply-findings')")
    elif status == "VERIFIED":
        need(current == "REVIEWED", "unit must be REVIEWED")
        need(level in PASSING_LEVELS, f"--level must be one of {sorted(PASSING_LEVELS)}")
        entry = parity_entry(ws, unit_id)
        need(entry is not None, "no parity.json entry; run porter.py parity collect --unit first")
        need(entry["level"] == level, f"parity.json says {entry['level']}, not {level}")
        unit["verifiedLevel"] = level
    elif status == "GAP":
        need(current in ("IMPLEMENTED", "REVIEWED", "VERIFIED", "DONE"), "only verified-stage or DONE units can be GAP")
        entry = parity_entry(ws, unit_id)
        need(entry is not None and entry["level"] == "GAP", "parity.json must record level GAP for this unit")
        unit["verifiedLevel"] = "GAP"
    elif status == "DONE":
        need(current == "VERIFIED", "unit must be VERIFIED (only the verify skill sets that)")
        need(_task_at_least(unit, "report"), "unit report not written (task 'report')")
    elif status == "BLOCKED":
        need(current not in TERMINAL, "unit already terminal")
        need(bool(note), "--note is required: what blocked it and what was tried")
    elif status == "DEFERRED":
        need(current in ("PENDING", "BLOCKED"), "only PENDING or BLOCKED units can be deferred")
        need(bool(note), "--note is required: why it is out of scope")
    elif status == "PENDING":
        need(current == "IN_PROGRESS" and bool(note), "only an IN_PROGRESS unit can be abandoned, with --note")
    else:
        raise PorterError(f"unknown status {status}")

    unit["status"] = status
    if task:
        _set_task(unit, task)
    if note:
        unit["note"] = note
    ws.log("unit.status", unit=unit_id, **{"from": current, "to": status, "level": level, "note": note})


def _task_at_least(unit: dict, task: str) -> bool:
    current = unit.get("task")
    return current in TASKS and TASKS.index(current) >= TASKS.index(task)


def _set_task(unit: dict, task: str) -> None:
    if task not in TASKS:
        raise PorterError(f"unknown task '{task}'. Tasks in order: {', '.join(TASKS)}")
    unit["task"] = task


# ---------------------------------------------------------------- next action

def next_action(ws: Workspace) -> tuple[str, dict]:
    phases = ws.state["phases"]
    plan = ws.plan()
    for phase in PHASES:
        status = phases[phase]["status"]
        if phase in ("implement", "verify") and phases["strategy"]["status"] == "DONE":
            break
        if status == "GATE_WAIT":
            report = OUTPUTS[phase][-1]
            how = (f"porter.py target choose <language> --note \"...\"" if phase == "target"
                   else f"porter.py state gate {phase} approve --note \"...\"")
            return (f"user gate for {phase}: present .porter/{report} and the gate items, then run: {how}",
                    {"kind": "gate", "phase": phase})
        if status not in SATISFIED:
            verb = "re-run" if status == "STALE" else ("continue" if status == "IN_PROGRESS" else "run")
            return f"{verb} the {phase} phase (/agentporter:{_skill(phase)})", {"kind": "phase", "phase": phase}
    units = ws.state["units"]
    if not units:
        return "run the strategy phase to produce plan.json", {"kind": "phase", "phase": "strategy"}
    for uid, unit in units.items():
        status = unit["status"]
        if status in ACTIVE:
            step = {
                "IN_PROGRESS": f"continue {uid} at task '{unit.get('task')}' (attempt {unit.get('attempts', 1)})",
                "IMPLEMENTED": f"review {uid} (reviewer agent), apply findings, then set REVIEWED",
                "REVIEWED": f"verify {uid} (/agentporter:verify {uid})",
                "VERIFIED": f"write the unit report for {uid}, commit if the policy says so, then set DONE",
                "GAP": f"re-implement {uid}: parity found gaps (attempt {unit.get('attempts', 0) + 1})",
            }[status]
            return step, {"kind": "unit", "unit": uid, "status": status}
    order = (plan or {}).get("order") or sorted(units, key=lambda u: units[u].get("wave", 0))
    for uid in order:
        if uid in units and unit_ready(ws, uid, plan):
            pu = _plan_unit(plan, uid)
            risk = ", ".join(pu.get("riskTags", [])) or "none"
            return (f"start {uid} (wave {pu.get('wave', 0)}, risk: {risk}) with /agentporter:implement {uid}",
                    {"kind": "unit", "unit": uid, "status": "READY"})
    waiting = [u for u, x in units.items() if x["status"] == "PENDING"]
    if waiting:
        return (f"no unit is READY; {len(waiting)} PENDING units wait on BLOCKED or DEFERRED dependencies. "
                "Report to the user.", {"kind": "blocked", "units": waiting})
    if phases["implement"]["status"] != "DONE":
        return "all units terminal: run porter.py state postflight implement", {"kind": "postflight", "phase": "implement"}
    if phases["verify"]["status"] != "DONE":
        return "run the final verification pass (/agentporter:verify)", {"kind": "phase", "phase": "verify"}
    return "port complete: publish PARITY.md and follow the release checklist (/agentporter:status release)", {"kind": "complete"}


def _skill(phase: str) -> str:
    return phase


# ---------------------------------------------------------------- stage card

def stage_card(ws: Workspace) -> str:
    cfg, st = ws.config, ws.state
    src = cfg["source"]
    pkg = (src.get("package") or {})
    name = pkg.get("name") or Path(src["location"].rstrip("/")).name
    version = pkg.get("version") or (src.get("commit") or "")[:10] or "unpinned"
    target = cfg["target"]
    tgt = (target.get("language") or "(target not chosen)") + (f" ({target['package']})" if target.get("package") else "")
    if src.get("mode") == "artifact":
        name += " [artifact]"
    lines = [f"AgentPorter  {name} {version} -> {tgt}      .porter/ at {now_iso()[:16].replace('T', ' ')}Z"]
    phase = st.get("phase") or "none"
    pstatus = st["phases"].get(phase, {}).get("status", "") if phase != "none" else ""
    gates = []
    for g in GATED:
        if st["phases"][g]["status"] == "SKIPPED":
            continue
        gate = st["phases"][g].get("gate")
        gates.append(f"{g} {gate or 'pending'}")
    stale = ", ".join(st["stale"]) or "none"
    lines.append(f"Phase: {phase}{f' ({pstatus})' if pstatus else ''}   gates: {', '.join(gates)}   stale: {stale}")
    plan = ws.plan()
    units = st["units"]
    if units:
        counts: dict[str, int] = {}
        active = []
        for uid in units:
            s = display_status(ws, uid, plan)
            counts[s] = counts.get(s, 0) + 1
            u = units[uid]
            if s in ACTIVE:
                active.append(f"{uid}, task: {u.get('task')}, attempt {u.get('attempts', 0)}/{st['budgets']['attemptsPerUnit']}")
        parts = [f"{len(units)} total"]
        for key in ("DONE", "VERIFIED", "REVIEWED", "IMPLEMENTED", "IN_PROGRESS", "GAP", "READY", "PENDING", "BLOCKED", "DEFERRED"):
            if counts.get(key):
                extra = f" ({'; '.join(active)})" if key == "IN_PROGRESS" and active else ""
                parts.append(f"{key} {counts[key]}{extra}")
        lines.append("Units: " + "  ".join(parts))
        levels = [f"{u} {x['verifiedLevel']}" for u, x in units.items() if x.get("verifiedLevel")]
        if levels:
            lines.append("Parity so far: " + ", ".join(levels))
    lines.append("Next: " + next_action(ws)[0])
    return "\n".join(lines)


# ---------------------------------------------------------------- validation per phase

def _exists(ws: Workspace, rel: str, errors: list[str]) -> bool:
    path = ws.p(rel)
    if not path.exists() or (path.is_file() and not path.read_text(encoding="utf-8").strip()):
        errors.append(f"missing or empty: .porter/{rel}")
        return False
    return True


def _schema(ws: Workspace, rel: str, name: str, errors: list[str]) -> Any:
    if not _exists(ws, rel, errors):
        return None
    data = read_json(ws.p(rel))
    errors.extend(f".porter/{rel} {e}" for e in jsonschema.validate_named(data, name))
    return data


def deps_gate_items(ws: Workspace, deps: dict) -> list[str]:
    items = []
    lic = (ws.config["source"].get("license") or {})
    if lic.get("copyleft") == "strong":
        items.append(f"source license {lic.get('spdx')} is strong copyleft: the port inherits its terms")
    for d in deps.get("dependencies", []):
        name = d["name"]
        if d.get("gate"):
            note = (d.get("notes") or "no note").split(". ")[0]
            items.append(f"{name}: flagged for review ({note[:160]})")
        if d["decision"] in ("PORT", "VENDOR"):
            items.append(f"{name}: decision {d['decision']}")
        elif d["confidence"] == "LOW" and d["decision"] not in ("DROP",):
            items.append(f"{name}: LOW confidence {d['decision']}")
        status = (d.get("verified") or {}).get("status")
        if d["decision"] in ("MAP", "SHIM") and status == "UNVERIFIED":
            items.append(f"{name}: candidate could not be verified against the registry")
        dl = d.get("license") or {}
        if dl.get("compatible") is False:
            items.append(f"{name}: candidate license {dl.get('spdx')} may be incompatible")
        sl = d.get("sourceLicense") or {}
        if sl.get("compatible") is False:
            items.append(f"{name}: {d['decision']} copies code licensed {sl.get('spdx')} into the port")
    return items


def recover_gate_items(ws: Workspace, recovery: dict) -> list[str]:
    items = []
    unknowns = recovery.get("unknowns", [])
    if unknowns:
        shown = "; ".join(u["question"] for u in unknowns[:3])
        items.append(f"{len(unknowns)} open unknowns about the original's behavior: {shown}")
    low = [i["id"] for i in recovery.get("interface", []) if i.get("confidence") == "LOW"]
    if low:
        items.append(f"LOW confidence interface items (confirm or drop): {', '.join(low[:8])}")
    oracle = recovery.get("oracle") or {}
    if not oracle.get("runnable"):
        items.append("the artifact cannot run on this host, so fixtures cannot be recorded from it here: "
                     + (oracle.get("note") or "decide where the oracle runs"))
    if recovery.get("source", {}).get("origin") == "decompiled":
        items.append("recovered source is decompiled output: implementers must work from the contract and "
                     "fixtures (clean room), never copy decompiled code")
    return items


def validate_phase(ws: Workspace, phase: str) -> list[str]:
    errors: list[str] = []
    if phase == "recover":
        if not ws.config["source"].get("authorization"):
            errors.append("config.source.authorization is empty (porter.py state authorize --note ...)")
        _schema(ws, "recover/artifact.json", "artifact", errors)
        recovery = _schema(ws, "recover/recovery.json", "recovery", errors)
        _exists(ws, "recover/recovery.md", errors)
        if recovery:
            errors.extend(_recovery_rules(ws, recovery))
    elif phase == "survey":
        _schema(ws, "survey.json", "survey", errors)
        _exists(ws, "survey.md", errors)
        if not ws.config["source"].get("language"):
            errors.append("config.source.language is not set (porter.py survey sets it)")
    elif phase == "target":
        if ws.state["phases"]["target"].get("gate") == "given":
            return errors
        target = _schema(ws, "target.json", "target", errors)
        _exists(ws, "target.md", errors)
        if target:
            errors.extend(_target_rules(target))
    elif phase == "deps":
        deps = _schema(ws, "deps.json", "deps", errors)
        _exists(ws, "deps.md", errors)
        if deps:
            errors.extend(_deps_rules(ws, deps))
    elif phase == "contract":
        api = _schema(ws, "contract/api.json", "api", errors)
        _exists(ws, "contract/contract.md", errors)
        if ws.p("contract/error-map.json").exists():
            _schema(ws, "contract/error-map.json", "error-map", errors)
        from .fixtures import validate_dir
        fx_errors, summary = validate_dir(ws.p("fixtures"))
        errors.extend(fx_errors)
        if api:
            plan = ws.plan()
            no_fx = {u["id"] for u in (plan or {}).get("units", []) if u.get("noFixturesReason")}
            units = {s.get("unit") for s in api["symbols"] if s["inScope"]}
            for s in api["symbols"]:
                if s["inScope"] and not s.get("unit"):
                    errors.append(f"api symbol {s['id']} is in scope but has no unit")
                if not s["inScope"] and not s.get("reason"):
                    errors.append(f"api symbol {s['id']} is out of scope without a reason")
            for u in sorted(x for x in units if x):
                if summary.get(u, 0) == 0 and u not in no_fx:
                    errors.append(f"unit {u} has no fixtures and no noFixturesReason in plan.json")
            from .fixtures import load_unit
            called = {c.get("call") for u in summary for c in load_unit(ws.p("fixtures"), u)[0]}
            for s in api["symbols"]:
                if (not s["inScope"] or s["kind"] not in CALLABLE_KINDS or s.get("unit") in no_fx
                        or s.get("noFixturesReason") or summary.get(s.get("unit"), 0) == 0
                        or re.search(r"(Error|Exception)$", s["name"])):
                    continue
                cid = s.get("callId") or s["id"]
                if not any(c == cid or (c or "").startswith(cid + ".") for c in called):
                    errors.append(f"api symbol {s['id']} is in scope but no fixture calls it "
                                  "(record cases, or set noFixturesReason on the symbol)")
    elif phase == "strategy":
        plan = _schema(ws, "plan.json", "plan", errors)
        _exists(ws, "strategy.md", errors)
        _exists(ws, "decomposition.md", errors)
        if plan:
            errors.extend(plan_rules(ws, plan))
    elif phase == "implement":
        open_units = [u for u, x in ws.state["units"].items() if x["status"] not in TERMINAL]
        if open_units:
            errors.append("units not terminal (DONE, BLOCKED or DEFERRED): " + ", ".join(open_units))
        if not ws.state["units"]:
            errors.append("no units in state; run strategy first")
    elif phase == "verify":
        parity = _schema(ws, "parity.json", "parity", errors)
        _exists(ws, "PARITY.md", errors)
        if parity:
            seen = {u["unit"] for u in parity["units"]}
            missing = [u for u in ws.state["units"] if u not in seen]
            if missing:
                errors.append("units missing from parity.json: " + ", ".join(missing))
            for err in parity.get("markerErrors", []):
                errors.append(f"divergence marker: {err}")
            for entry in parity["units"]:
                if entry["fixtures"]["total"] == 0 and entry["level"] in ("EXACT", "EQUIVALENT", "DIVERGENT"):
                    errors.append(f"{entry['unit']}: level {entry['level']} with zero fixtures")
                if entry["level"] == "GAP":
                    errors.append(f"{entry['unit']}: parity level GAP; set the unit GAP and fix it in implement "
                                  "(a DONE unit can be set GAP too)")
    return errors


def _recovery_rules(ws: Workspace, recovery: dict) -> list[str]:
    errors = []
    base = ws.p("recover")

    def check_refs(kind: str, item: dict) -> None:
        refs = item.get("evidence", [])
        if not refs:
            errors.append(f"{kind} {item['id']} has no evidence reference")
        for ref in refs:
            path = ref.split("#", 1)[0]
            if not (base / path).exists():
                errors.append(f"{kind} {item['id']}: evidence file recover/{path} does not exist")

    ids = [i["id"] for i in recovery.get("interface", [])]
    if len(ids) != len(set(ids)):
        errors.append("duplicate interface ids in recovery.json")
    for item in recovery.get("interface", []):
        check_refs("interface item", item)
    for item in recovery.get("behaviors", []):
        check_refs("behavior", item)
    if not recovery.get("interface") and not recovery.get("source", {}).get("path"):
        errors.append("nothing recovered: no interface items and no recovered source tree")
    src = recovery.get("source", {}).get("path")
    if src and not (ws.path / src).exists():
        errors.append(f"recovered source path .porter/{src} does not exist")
    return errors


TARGET_CRITERIA = ("ecosystem", "dependencies", "semantics", "runtime", "team", "support")


def _target_rules(target: dict) -> list[str]:
    errors = []
    names = [c["language"] for c in target["candidates"]]
    if len(names) != len(set(names)):
        errors.append("target.json lists a candidate language twice")
    for c in target["candidates"]:
        missing = [k for k in TARGET_CRITERIA if k not in c["scores"]]
        if missing:
            errors.append(f"{c['language']}: missing scores for {', '.join(missing)}")
        unscored = [k for k in ("dependencies", "semantics", "runtime", "support") if c["scores"].get(k) is None]
        if unscored:
            errors.append(f"{c['language']}: computed criteria left empty: {', '.join(unscored)} (run porter.py target score)")
    if target.get("recommended") not in names:
        errors.append("target.recommended must be one of the candidates")
    return errors


def _deps_rules(ws: Workspace, deps: dict) -> list[str]:
    errors = []
    cache = ws.p("cache/registry")
    for d in deps["dependencies"]:
        name = d["name"]
        needs_decision = d["direct"] and d["scope"] in ("runtime", "peer", "optional")
        if needs_decision and d["decision"] == "UNDECIDED":
            errors.append(f"{name}: runtime dependency without a decision")
        if d["decision"] in ("MAP", "SHIM"):
            cand = d.get("candidate") or {}
            if not cand.get("name"):
                errors.append(f"{name}: {d['decision']} without a candidate")
                continue
            status = (d.get("verified") or {}).get("status")
            if status == "UNVERIFIED":
                continue
            if status != "VERIFIED" or not (d.get("verified") or {}).get("registryLookup"):
                errors.append(f"{name}: candidate {cand['name']} not verified; run porter.py registry verify-deps")
                continue
            from .registry import cache_path
            record = cache_path(cache, cand.get("registry") or "", cand["name"])
            if not record.exists() or not read_json(record).get("exists"):
                errors.append(f"{name}: no registry record proving {cand['name']} exists ({record})")
        if d["decision"] == "PORT" and not d.get("budget"):
            errors.append(f"{name}: PORT decision without a budget")
    return errors


def plan_rules(ws: Workspace, plan: dict) -> list[str]:
    errors = []
    if plan.get("draft"):
        errors.append("plan.json is still a draft; run porter.py decompose without --draft")
    ids = [u["id"] for u in plan["units"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate unit ids in plan.json")
    known = set(ids)
    deps = {u["id"]: u.get("dependsOn", []) for u in plan["units"]}
    for uid, ds in deps.items():
        for d in ds:
            if d not in known:
                errors.append(f"{uid} depends on unknown unit {d}")
    for cyc in find_cycles(ids, deps):
        errors.append("dependency cycle between units: " + " -> ".join(cyc))
    waves = {u["id"]: u["wave"] for u in plan["units"]}
    for uid, ds in deps.items():
        for d in ds:
            if d in waves and waves[d] >= waves[uid]:
                errors.append(f"{uid} (wave {waves[uid]}) depends on {d} (wave {waves[d]}): waves must increase")
    order = plan.get("order", [])
    if sorted(order) != sorted(ids):
        errors.append("plan.order must list every unit exactly once")
    else:
        pos = {u: i for i, u in enumerate(order)}
        for uid, ds in deps.items():
            for d in ds:
                if d in pos and pos[d] > pos[uid]:
                    errors.append(f"order puts {uid} before its dependency {d}")
    api_path = ws.p("contract/api.json")
    if api_path.exists():
        covered: dict[str, list[str]] = {}
        for u in plan["units"]:
            for sym in u["symbols"]:
                covered.setdefault(sym, []).append(u["id"])
        for s in read_json(api_path)["symbols"]:
            if not s["inScope"]:
                continue
            owners = covered.get(s["id"]) or covered.get(_class_of(s["id"]), [])
            if not owners:
                errors.append(f"in-scope symbol {s['id']} is not owned by any unit")
            elif len(owners) > 1:
                errors.append(f"symbol {s['id']} is owned by several units: {', '.join(owners)}")
    return errors


def _class_of(symbol_id: str) -> str:
    module, _, qual = symbol_id.partition(":")
    return f"{module}:{qual.split('.')[0]}"


# ---------------------------------------------------------------- plan sync

def plan_sync(ws: Workspace) -> list[str]:
    plan = ws.plan()
    if not plan:
        raise PorterError("no plan.json to sync")
    errors = jsonschema.validate_named(plan, "plan") + plan_rules(ws, plan)
    if errors:
        raise PorterError("plan.json is invalid:\n  " + "\n  ".join(errors), code=1)
    units = ws.state["units"]
    plan_ids = {u["id"] for u in plan["units"]}
    removed = [u for u in units if u not in plan_ids]
    bad = [u for u in removed if units[u]["status"] not in ("PENDING",)]
    if bad:
        raise PorterError("cannot drop units that already started: " + ", ".join(bad), code=1)
    added = []
    for u in plan["units"]:
        if u["id"] in units:
            units[u["id"]]["wave"] = u["wave"]
            continue
        entry = {"status": "DEFERRED" if u.get("deferred") else "PENDING", "wave": u["wave"],
                 "attempts": 0, "task": None, "verifiedLevel": None, "note": u.get("deferred")}
        if u.get("discovered"):
            entry["discovered"] = True
            ws.state["budgets"]["discoveredUsed"] += 1
        units[u["id"]] = entry
        added.append(u["id"])
    for u in removed:
        del units[u]
    used, cap = ws.state["budgets"]["discoveredUsed"], ws.state["budgets"]["discoveredUnits"]
    if used > cap:
        raise PorterError(f"discovered-unit budget exceeded ({used}/{cap}): stop and return to the user", code=1)
    ws.state["phases"]["strategy"]["artifacts"] = artifact_hashes(ws, "strategy")
    ws.log("plan.sync", added=added or None, removed=removed or None)
    return added


# ---------------------------------------------------------------- PORTING.md

def write_porting_md(ws: Workspace) -> Path:
    root = ws.target_root()
    rel_ws = Path(ws.path).relative_to(ws.root).as_posix()
    plan = ws.plan()
    lines = [
        "# Porting status",
        "",
        "This package is being ported with [AgentPorter](https://github.com/WebEferen/AgentPorter).",
        f"All analysis, decisions and evidence live in [`{rel_ws}/`]({_rel_link(root, ws.path)}).",
        "",
        "```text",
        stage_card(ws),
        "```",
        "",
        "| Artifact | Purpose |",
        "| --- | --- |",
    ]
    for rel, purpose in (
        ("recover/recovery.md", "what was recovered from the artifact, with evidence"),
        ("survey.md", "what the source is and where the risk is"),
        ("target.md", "why this target language"),
        ("deps.md", "every dependency and its decision"),
        ("contract/contract.md", "the behavioral contract being ported"),
        ("decomposition.md", "how the port was cut into units"),
        ("strategy.md", "idiom map, order, risks"),
        ("PARITY.md", "parity evidence against the original"),
        ("decisions.md", "human decisions"),
    ):
        if ws.p(rel).exists():
            lines.append(f"| [{rel}]({_rel_link(root, ws.p(rel))}) | {purpose} |")
    if ws.state["units"]:
        lines += ["", "| Unit | Layer | Wave | Status | Parity |", "| --- | --- | --- | --- | --- |"]
        order = (plan or {}).get("order") or list(ws.state["units"])
        for uid in order:
            if uid not in ws.state["units"]:
                continue
            pu = _plan_unit(plan, uid)
            u = ws.state["units"][uid]
            lines.append(f"| {uid} | {pu.get('layer', '')} | {u.get('wave', '')} | "
                         f"{display_status(ws, uid, plan)} | {u.get('verifiedLevel') or ''} |")
    path = root / "PORTING.md"
    write_text(path, "\n".join(lines) + "\n")
    return path


def _rel_link(root: Path, target: Path) -> str:
    try:
        return Path(target).resolve().relative_to(root).as_posix()
    except ValueError:
        return Path(target).resolve().as_posix()


# ---------------------------------------------------------------- commands

def cmd_init(args: argparse.Namespace) -> int:
    ws_path = Path.cwd() / ".porter"
    if ws_path.exists() and not args.force:
        raise PorterError(f"{ws_path} already exists. Resume with /agentporter:port, or pass --force to recreate.")
    budgets = dict(DEFAULT_BUDGETS)
    location = args.source
    local = Path(location).expanduser()
    is_local = local.exists()
    mode = args.mode
    if mode == "auto":
        mode = "artifact" if is_local and (local.is_file() or local.suffix in (".app", ".asar")) else "code"
    target_lang = normalize_lang(args.to)
    config = {
        "schema": 1,
        "createdAt": now_iso(),
        "source": {
            "location": location,
            "path": str(local.resolve()) if is_local else None,
            "ref": args.ref,
            "commit": None,
            "dirty": None,
            "subpath": args.subpath,
            "language": None,
            "package": {"name": args.source_name, "version": args.source_version},
            "license": None,
            "mode": mode,
            "authorization": args.authorization,
        },
        "target": {"language": target_lang, "path": args.target_path, "package": args.name},
        "options": {
            "commitPolicy": args.commit_policy,
            "worktree": False,
            "registryTtlHours": 24,
            "budgets": budgets,
        },
    }
    errors = jsonschema.validate_named(config, "config")
    if errors:
        raise PorterError("invalid init arguments:\n  " + "\n  ".join(errors))
    write_json(ws_path / "config.json", config)
    write_json(ws_path / "state.json", new_state(budgets, mode, bool(target_lang)))
    (ws_path / ".gitignore").write_text(WS_GITIGNORE, encoding="utf-8")
    template = KNOWLEDGE / "templates" / "decisions.md"
    if not (ws_path / "decisions.md").exists():
        (ws_path / "decisions.md").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    ws = Workspace(ws_path)
    if args.authorization:
        record_decision(ws, "reverse-engineering authorization", args.authorization)
    ws.log("init", source=location, mode=mode, target=target_lang)
    ws.save()
    print(stage_card(ws))
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    phase = args.phase
    refresh_staleness(ws)
    st = ws.state["phases"]
    errors = []
    for pre in upstream(phase):
        status = st[pre]["status"]
        if status == "GATE_WAIT":
            how = "porter.py target choose <language>" if pre == "target" else f"porter.py state gate {pre} approve"
            errors.append(f"{pre} is waiting for the user gate ({how})")
        elif status not in SATISFIED:
            errors.append(f"{pre} must be DONE first (it is {status})")
    if st[phase]["status"] == "SKIPPED":
        errors.append(f"{phase} is SKIPPED for this workspace ({st[phase].get('gate')})")
    if phase == "recover" and not ws.config["source"].get("authorization"):
        errors.append("reverse engineering needs a recorded authorization: ask the user who owns the artifact "
                      "or what permits analyzing it, then run porter.py state authorize --note \"...\"")
    if phase == "implement":
        plan = ws.plan()
        if not plan or plan.get("draft"):
            errors.append("plan.json missing or still a draft")
        if not ws.state["units"]:
            errors.append("no units synced from plan.json")
    if phase == "verify":
        if not ws.p("fixtures").is_dir():
            errors.append("no .porter/fixtures directory")
        started = [u for u, x in ws.state["units"].items() if x["status"] in ("IMPLEMENTED", "REVIEWED", "VERIFIED", "DONE", "GAP", "BLOCKED")]
        if not started:
            errors.append("no unit has been implemented yet")
    status = st[phase]["status"]
    if status == "DONE" and not args.rerun and phase != "verify":
        errors.append(f"{phase} is already DONE; pass --rerun to redo it (downstream phases become STALE)")
    if errors:
        print(stage_card(ws))
        print(f"\nPreflight FAILED for {phase}:")
        for e in errors:
            print(f"  - {e}")
        if not args.check:
            ws.save()
        return 1
    if not args.check:
        if args.rerun and status in ("DONE", "GATE_WAIT"):
            for down in downstream(phase):
                if st[down].get("gate") == "given":
                    continue
                if st[down]["status"] in ("DONE", "GATE_WAIT", "IN_PROGRESS"):
                    st[down]["status"] = "STALE"
            st[phase]["gate"] = None
        if status != "IN_PROGRESS":
            st[phase]["status"] = "IN_PROGRESS"
            st[phase]["at"] = now_iso()
            ws.log("phase.start", phase=phase, rerun=args.rerun or None)
        ws.state["phase"] = phase
        ws.state["stale"] = [p for p in PHASES if st[p]["status"] == "STALE"]
        ws.save()
    print(stage_card(ws))
    print(f"\nPreflight OK: {phase}")
    return 0


def cmd_postflight(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    phase = args.phase
    st = ws.state["phases"][phase]
    if st["status"] not in ("IN_PROGRESS", "STALE"):
        raise PorterError(f"{phase} is {st['status']}; postflight runs after preflight", code=1)
    errors = validate_phase(ws, phase)
    if errors:
        print(f"Postflight FAILED for {phase}:")
        for e in errors:
            print(f"  - {e}")
        return 1
    st["artifacts"] = artifact_hashes(ws, phase)
    st["at"] = now_iso()
    gate_items: list[str] = []
    if phase == "recover":
        gate_items = recover_gate_items(ws, read_json(ws.p("recover/recovery.json")))
        if gate_items and st.get("gate") != "approved":
            st["status"] = "GATE_WAIT"
        else:
            st["status"] = "DONE"
            st["gate"] = st.get("gate") or "no items"
    elif phase == "target":
        st["status"] = "DONE" if st.get("gate") in ("approved", "given") else "GATE_WAIT"
        if st["status"] == "GATE_WAIT":
            target = read_json(ws.p("target.json"))
            gate_items = [f"choose the target language (recommended: {target['recommended']}); "
                          f"candidates: {', '.join(c['language'] for c in target['candidates'])}"]
    elif phase == "deps":
        gate_items = deps_gate_items(ws, read_json(ws.p("deps.json")))
        if gate_items and st.get("gate") != "approved":
            st["status"] = "GATE_WAIT"
        else:
            st["status"] = "DONE"
            st["gate"] = st.get("gate") or "no items"
    elif phase == "strategy":
        plan_sync(ws)
        st["status"] = "DONE" if st.get("gate") == "approved" else "GATE_WAIT"
    else:
        st["status"] = "DONE"
    if phase == "survey":
        _sync_license(ws)
    ws.log("phase.end", phase=phase, status=st["status"])
    ws.state["stale"] = [p for p in PHASES if ws.state["phases"][p]["status"] == "STALE"]
    ws.save()
    write_porting_md(ws)
    print(stage_card(ws))
    print(f"\nPostflight OK: {phase} is {st['status']}")
    if gate_items:
        print("Gate items for the user:")
        for item in gate_items:
            print(f"  - {item}")
    return 0


def _sync_license(ws: Workspace) -> None:
    survey = read_json(ws.p("survey.json"))
    lic = survey.get("license") or {}
    if lic.get("spdx"):
        ws.config["source"]["license"] = {"spdx": lic.get("spdx"), "copyleft": lic.get("copyleft", "unknown")}
        write_json(ws.p("config.json"), ws.config)


def record_decision(ws: Workspace, title: str, note: str) -> None:
    entry = f"\n## {now_iso()[:10]} {title}\n\n{note.strip()}\n"
    with ws.p("decisions.md").open("a", encoding="utf-8") as fh:
        fh.write(entry)


def apply_gate(ws: Workspace, phase: str, decision: str, note: str) -> None:
    st = ws.state["phases"][phase]
    if st["status"] != "GATE_WAIT":
        raise PorterError(f"{phase} is {st['status']}, not GATE_WAIT", code=1)
    if not note or not note.strip():
        raise PorterError("--note is required: record what the user decided")
    if decision == "approve":
        st["status"] = "DONE"
        st["gate"] = "approved"
    else:
        st["status"] = "IN_PROGRESS"
        st["gate"] = "rejected"
    record_decision(ws, f"{phase} gate: {decision}d", note)
    ws.log("gate", phase=phase, decision=decision, note=note)


def cmd_gate(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    if args.phase == "target" and args.decision == "approve":
        raise PorterError("approve the target gate with: porter.py target choose <language> --note \"...\"")
    apply_gate(ws, args.phase, args.decision, args.note)
    ws.save()
    write_porting_md(ws)
    print(stage_card(ws))
    return 0


def cmd_authorize(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    if not args.note.strip():
        raise PorterError("--note must say who authorized the analysis and on what basis")
    ws.config["source"]["authorization"] = args.note.strip()
    write_json(ws.p("config.json"), ws.config)
    record_decision(ws, "reverse-engineering authorization", args.note)
    ws.log("authorize", note=args.note)
    ws.save()
    print(stage_card(ws))
    return 0


def cmd_source(args: argparse.Namespace) -> int:
    from .survey import copyleft_of
    ws = Workspace.open(args.workspace)
    if not (args.license or args.name or args.version):
        raise PorterError("pass at least one of --license, --name, --version")
    src = ws.config["source"]
    pkg = src.get("package") or {}
    facts = []
    if args.name:
        pkg["name"] = args.name
        facts.append(f"name {args.name}")
    if args.version:
        pkg["version"] = args.version
        facts.append(f"version {args.version}")
    src["package"] = pkg
    if args.license:
        src["license"] = {"spdx": args.license, "copyleft": copyleft_of(args.license)}
        facts.append(f"license {args.license}")
    write_json(ws.p("config.json"), ws.config)
    record_decision(ws, "source facts: " + ", ".join(facts), args.note)
    ws.log("source", facts=facts, note=args.note)
    ws.save()
    print(stage_card(ws))
    return 0


def cmd_unit(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    if args.action == "set":
        set_unit(ws, args.unit, args.status, args.task, args.level, args.note)
    elif args.action == "task":
        unit = ws.state["units"].get(args.unit)
        if unit is None:
            raise PorterError(f"unknown unit '{args.unit}'")
        if unit["status"] not in ACTIVE:
            raise PorterError(f"{args.unit} is {unit['status']}; tasks apply to active units", code=1)
        _set_task(unit, args.status)
        ws.log("unit.task", unit=args.unit, task=args.status)
    ws.save()
    write_porting_md(ws)
    print(stage_card(ws))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    refresh_staleness(ws)
    ws.save()
    text, data = next_action(ws)
    if args.json:
        import json, sys
        json.dump(data | {"text": text}, sys.stdout, indent=2)
        print()
    else:
        print(text)
    return 0


def cmd_board(args: argparse.Namespace) -> int:
    try:
        ws = Workspace.open(args.workspace)
    except PorterError:
        print("No .porter workspace here. Start one with /agentporter:port <source> [--to <language>].")
        return 0
    refresh_staleness(ws)
    ws.save()
    print(stage_card(ws))
    plan = ws.plan()
    if ws.state["units"] and args.units:
        print("\n| Unit | Layer | Wave | Status | Task | Attempts | Parity | Note |")
        print("| --- | --- | --- | --- | --- | --- | --- | --- |")
        order = (plan or {}).get("order") or list(ws.state["units"])
        for uid in order:
            u = ws.state["units"].get(uid)
            if not u:
                continue
            pu = _plan_unit(plan, uid)
            print(f"| {uid} | {pu.get('layer', '')} | {u.get('wave', '')} | {display_status(ws, uid, plan)} | "
                  f"{u.get('task') or ''} | {u.get('attempts', 0)} | {u.get('verifiedLevel') or ''} | {u.get('note') or ''} |")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    errors = []
    for rel, name in (
        ("config.json", "config"), ("state.json", "state"), ("recover/artifact.json", "artifact"),
        ("recover/recovery.json", "recovery"), ("survey.json", "survey"), ("target.json", "target"),
        ("deps.json", "deps"), ("contract/api.json", "api"), ("plan.json", "plan"),
        ("contract/error-map.json", "error-map"), ("divergences.json", "divergences"),
        ("reftests.json", "reftests"), ("parity.json", "parity"),
    ):
        if ws.p(rel).exists():
            errors.extend(f".porter/{rel} {e}" for e in jsonschema.validate_named(read_json(ws.p(rel)), name))
    from .fixtures import validate_dir
    if ws.p("fixtures").is_dir():
        errors.extend(validate_dir(ws.p("fixtures"))[0])
    for phase in PHASES:
        if ws.state["phases"][phase]["status"] == "DONE":
            errors.extend(f"[{phase}] {e}" for e in validate_phase(ws, phase))
    if errors:
        print("Validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Validation OK")
    return 0


def cmd_plan_sync(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    added = plan_sync(ws)
    ws.save()
    write_porting_md(ws)
    print(f"plan synced; added: {', '.join(added) or 'none'}")
    print(stage_card(ws))
    return 0


def cmd_porting_md(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    print(write_porting_md(ws))
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("init", help="create a .porter workspace in the current directory (the target repo)")
    p.add_argument("--source", required=True, help="local path or git URL of the project to port")
    p.add_argument("--to", help="target language, e.g. typescript, go, rust, kotlin, python; "
                                 "omit it to choose in the target phase")
    p.add_argument("--mode", choices=("auto", "code", "artifact"), default="auto",
                   help="artifact = no source code, recover behavior with REA first (auto: a file or .app is an artifact)")
    p.add_argument("--authorization", help="artifact mode: who authorized reverse engineering, and on what basis")
    p.add_argument("--ref", help="git ref (tag, branch or commit) to pin")
    p.add_argument("--subpath", help="package directory inside a monorepo source")
    p.add_argument("--name", help="target package name")
    p.add_argument("--source-name", help="upstream package name, if known")
    p.add_argument("--source-version", help="upstream package version, if known")
    p.add_argument("--target-path", default=".", help="target package dir relative to the repo root")
    p.add_argument("--commit-policy", choices=("per-unit", "never"), default="per-unit")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    s = sub.add_parser("state", help="workflow state: preflight, postflight, gates, units, board")
    s.add_argument("--workspace", help="path to .porter (default: search upward from cwd)")
    ss = s.add_subparsers(dest="state_cmd", required=True)
    for name, func in (("preflight", cmd_preflight), ("postflight", cmd_postflight)):
        x = ss.add_parser(name)
        x.add_argument("phase", choices=PHASES)
        if name == "preflight":
            x.add_argument("--rerun", action="store_true")
            x.add_argument("--check", action="store_true", help="report only, change nothing")
        x.set_defaults(func=func)
    g = ss.add_parser("gate")
    g.add_argument("phase", choices=GATED)
    g.add_argument("decision", choices=("approve", "reject"))
    g.add_argument("--note", required=True)
    g.set_defaults(func=cmd_gate)
    u = ss.add_parser("unit")
    uu = u.add_subparsers(dest="action", required=True)
    us = uu.add_parser("set")
    us.add_argument("unit")
    us.add_argument("status", choices=("IN_PROGRESS", "IMPLEMENTED", "REVIEWED", "VERIFIED", "DONE", "BLOCKED", "DEFERRED", "GAP", "PENDING"))
    us.add_argument("--task", choices=TASKS)
    us.add_argument("--level", choices=sorted(PASSING_LEVELS))
    us.add_argument("--note")
    us.set_defaults(func=cmd_unit)
    ut = uu.add_parser("task")
    ut.add_argument("unit")
    ut.add_argument("status", metavar="task", choices=TASKS)
    ut.set_defaults(func=cmd_unit, task=None, level=None, note=None)
    n = ss.add_parser("next")
    n.add_argument("--json", action="store_true")
    n.set_defaults(func=cmd_next)
    b = ss.add_parser("board")
    b.add_argument("--units", action="store_true", help="also print the unit table")
    b.set_defaults(func=cmd_board)
    v = ss.add_parser("validate")
    v.set_defaults(func=cmd_validate)
    a = ss.add_parser("authorize", help="record who authorized reverse engineering the artifact")
    a.add_argument("--note", required=True)
    a.set_defaults(func=cmd_authorize)
    sf = ss.add_parser("source", help="record source facts the user states (artifact mode has no manifest to read them from)")
    sf.add_argument("--license", help="SPDX id, e.g. MIT")
    sf.add_argument("--name", help="upstream package name")
    sf.add_argument("--version", help="upstream version")
    sf.add_argument("--note", required=True, help="the user's words")
    sf.set_defaults(func=cmd_source)
    ps = ss.add_parser("plan-sync")
    ps.set_defaults(func=cmd_plan_sync)
    pm = ss.add_parser("porting-md")
    pm.set_defaults(func=cmd_porting_md)
