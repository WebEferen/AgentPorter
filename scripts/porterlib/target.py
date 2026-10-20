"""Target language selection: score candidate languages on evidence, then record the user's choice.

The script computes what it can measure (dependency coverage, semantic distance, runtime fit, AgentPorter
support). Ecosystem fit and team familiarity come from the user. The rubric is in knowledge/target-selection.md."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .common import KNOWLEDGE, PorterError, read_json, write_json, write_text
from .langs import REGISTRY_OF, normalize_lang
from .state import TARGET_CRITERIA, Workspace, apply_gate, artifact_hashes, stage_card, write_porting_md

DEFAULT_WEIGHTS = {"ecosystem": 3, "dependencies": 3, "team": 2, "semantics": 2, "runtime": 2, "support": 1}
DEFAULT_CANDIDATES = ("typescript", "python", "go", "rust", "kotlin", "java", "csharp", "elixir", "ruby", "php")

# typing, memory, errors, concurrency, absence
FEATURES = {
    "python": ("dynamic", "gc", "exceptions", "async", "none"),
    "javascript": ("dynamic", "gc", "exceptions", "async", "undefined"),
    "typescript": ("gradual", "gc", "exceptions", "async", "undefined"),
    "coffeescript": ("dynamic", "gc", "exceptions", "async", "undefined"),
    "ruby": ("dynamic", "gc", "exceptions", "threads", "nil"),
    "php": ("dynamic", "gc", "exceptions", "sync", "null"),
    "perl": ("dynamic", "gc", "die", "sync", "undef"),
    "go": ("static", "gc", "values", "goroutines", "zero"),
    "rust": ("static", "ownership", "values", "async", "option"),
    "java": ("static", "gc", "exceptions", "threads", "null"),
    "kotlin": ("static", "gc", "exceptions", "coroutines", "option"),
    "scala": ("static", "gc", "exceptions", "futures", "option"),
    "csharp": ("static", "gc", "exceptions", "async", "nullable"),
    "fsharp": ("static", "gc", "exceptions", "async", "option"),
    "elixir": ("dynamic", "gc", "tuples", "actors", "nil"),
    "c": ("static", "manual", "codes", "threads", "null"),
    "cpp": ("static", "manual", "exceptions", "threads", "null"),
    "swift": ("static", "arc", "values", "async", "option"),
}
HALF_STEPS = {frozenset(p) for p in (("dynamic", "gradual"), ("gradual", "static"), ("gc", "arc"), ("manual", "ownership"),
                                     ("async", "coroutines"), ("async", "futures"), ("values", "tuples"), ("values", "codes"),
                                     ("none", "undefined"), ("nil", "none"), ("null", "nullable"), ("option", "nullable"),
                                     ("undefined", "null"), ("nil", "null"), ("threads", "goroutines"))}
RUNTIME_FIT = {
    "cli": {"go": 5, "rust": 5, "csharp": 3.5, "kotlin": 3, "java": 2.5, "typescript": 3, "javascript": 3, "python": 3,
            "ruby": 2.5, "php": 2, "elixir": 2},
    "service": {"go": 5, "kotlin": 4.5, "java": 4.5, "csharp": 4.5, "elixir": 4.5, "typescript": 4, "rust": 4,
                "python": 3.5, "php": 3.5, "ruby": 3},
}
RUNTIME_NOTE = {
    "cli": "CLI tools ship best as one static binary with fast startup",
    "service": "long-running services favor mature server runtimes and concurrency",
}
JVM = {"java", "kotlin", "scala"}
JS = {"javascript", "typescript"}


def _pair_file(src: str, tgt: str) -> Path | None:
    p = KNOWLEDGE / "pairs" / f"{src}-to-{tgt}.md"
    return p if p.exists() else None


def _pair_status(path: Path | None) -> str | None:
    if not path:
        return None
    m = re.search(r"^\|\s*Status\s*\|\s*(\w+)", path.read_text(encoding="utf-8"), re.M)
    return m.group(1).lower() if m else "stub"


def _section(text: str, number: int) -> str:
    m = re.search(rf"^## {number}\..*?(?=^## \d+\.|\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def semantic_distance(src: str, tgt: str) -> float | None:
    a, b = FEATURES.get(src), FEATURES.get(tgt)
    if not a or not b:
        return None
    dist = 0.0
    for x, y in zip(a, b):
        if x != y:
            dist += 0.5 if frozenset((x, y)) in HALF_STEPS else 1.0
    return dist


def _dep_key(name: str) -> list[str]:
    parts = [name.lower()]
    tail = re.split(r"[/:]", name.lower())[-1]
    if tail and tail not in parts:
        parts.append(tail)
    return parts


def runtime_deps(ws: Workspace) -> list[dict]:
    cache = ws.p("cache/deps-graph.json")
    if cache.exists():
        graph = read_json(cache)
    elif ws.config["source"].get("mode") == "artifact":
        from .recover import deps_from_recovery
        graph = deps_from_recovery(ws.path)
    else:
        from .depsgraph import build_graph
        root = ws.config["source"].get("path")
        if not root:
            return []
        graph = build_graph(Path(root), ws.config["source"].get("subpath"))
    return [d for d in graph["dependencies"] if d["direct"] and d["scope"] in ("runtime", "peer", "optional")]


def score_candidate(src: str, tgt: str, kind: str, deps: list[dict], risk: set[str], inputs: dict) -> dict:
    ev: dict[str, list[str]] = {k: [] for k in TARGET_CRITERIA}
    scores: dict[str, float | None] = {}
    blockers: list[str] = []
    pair = _pair_file(src, tgt)
    status = _pair_status(pair)
    pair_text = pair.read_text(encoding="utf-8") if pair else ""

    if src == tgt:
        blockers.append("same language as the source: this is a refactor, not a port")

    # dependencies
    if not deps:
        scores["dependencies"] = 5.0
        ev["dependencies"].append("no runtime dependencies to replace")
    elif REGISTRY_OF.get(src) and REGISTRY_OF.get(src) == REGISTRY_OF.get(tgt):
        scores["dependencies"] = 5.0
        ev["dependencies"].append(f"same registry ({REGISTRY_OF[tgt]}): every dependency can be reused or typed")
    else:
        mapping = _section(pair_text, 13).lower()
        covered, unknown = [], []
        for d in deps:
            (covered if any(k in mapping for k in _dep_key(d["name"])) else unknown).append(d["name"])
        value = 5 * (len(covered) + 0.5 * len(unknown)) / len(deps)
        scores["dependencies"] = round(value, 2)
        if covered:
            ev["dependencies"].append(f"documented in the pair reference: {', '.join(covered)}")
        if unknown:
            ev["dependencies"].append(f"no documented mapping yet, research in the deps phase: {', '.join(unknown)}")

    # semantics
    dist = semantic_distance(src, tgt)
    if dist is None:
        scores["semantics"] = 2.5
        ev["semantics"].append("no feature profile for this pair: neutral score")
    else:
        traps = set(re.findall(r"`([a-z-]+)`", " ".join(re.findall(r"^Tags:.*$", pair_text, re.M))))
        uncovered = sorted(risk - traps)
        penalty = min(1.5, 0.25 * len(uncovered))
        scores["semantics"] = round(max(0.0, 5 - dist - penalty), 2)
        diffs = [f"{x} to {y}" for x, y in zip(FEATURES[src], FEATURES[tgt]) if x != y]
        ev["semantics"].append(f"model changes: {', '.join(diffs) or 'none'} (distance {dist})")
        if uncovered:
            ev["semantics"].append(f"risk tags with no documented trap for this pair: {', '.join(uncovered)}")

    # runtime
    table = RUNTIME_FIT.get(kind)
    if table:
        scores["runtime"] = float(table.get(tgt, 2.5))
        ev["runtime"].append(f"{kind}: {RUNTIME_NOTE[kind]}")
    else:
        scores["runtime"] = 3.0
        ev["runtime"].append(f"{kind}: runtime fit depends on the consumers, neutral score")

    # support
    support = 0.0
    if (KNOWLEDGE / "ecosystems" / f"{tgt}.md").exists():
        support += 1
        ev["support"].append("ecosystem reference present")
    harness = KNOWLEDGE / "harnesses" / tgt
    if harness.is_dir() and any(harness.iterdir()):
        support += 1.5
        ev["support"].append("parity harness template present")
    else:
        ev["support"].append("no harness template: the verify phase writes one from the README contract")
    if status == "full":
        support += 2.5
        ev["support"].append(f"full pair reference {pair.name}")
    elif status:
        support += 1.25
        ev["support"].append(f"stub pair reference {pair.name}")
    else:
        support += 0.5
        ev["support"].append("no pair reference: GENERIC.md method applies")
    scores["support"] = min(5.0, support)

    # user inputs
    consumers = inputs.get("consumers") or []
    if consumers:
        if tgt in consumers:
            scores["ecosystem"] = 5.0
        elif (tgt in JVM and set(consumers) & JVM) or (tgt in JS and set(consumers) & JS):
            scores["ecosystem"] = 4.0
        else:
            scores["ecosystem"] = 1.0
        ev["ecosystem"].append(f"consumers use: {', '.join(consumers)}")
    else:
        scores["ecosystem"] = None
        ev["ecosystem"].append("ask the user where the port will be used")
    team = inputs.get("team") or []
    if team:
        scores["team"] = 5.0 if tgt in team else 2.0
        ev["team"].append(f"team knows: {', '.join(team)}")
    else:
        scores["team"] = None
        ev["team"].append("ask the user which languages the maintainers know")
    for key, value in (inputs.get("set") or {}).items():
        lang, _, crit = key.partition(".")
        if lang == tgt and crit in TARGET_CRITERIA:
            scores[crit] = float(value)
            ev[crit].append(f"set by the user: {value}")
    return {"language": tgt, "registry": REGISTRY_OF.get(tgt), "scores": {k: scores.get(k) for k in TARGET_CRITERIA},
            "total": None, "evidence": ev, "blockers": blockers, "pairStatus": status or "none"}


def total(c: dict, weights: dict) -> float | None:
    num = den = 0.0
    for k, w in weights.items():
        v = c["scores"].get(k)
        if v is not None:
            num += w * v
            den += w
    return round(num / den, 2) if den else None


def render_md(t: dict) -> str:
    crit = list(TARGET_CRITERIA)
    lines = [
        "# Target language",
        "",
        f"Source: {t['context']['sourceLanguage']} {t['context']['kind']}, "
        f"{t['context']['runtimeDeps']} runtime dependencies, risk tags: {', '.join(t['context']['riskTags']) or 'none'}.",
        f"Weights: {', '.join(f'{k} {v}' for k, v in t['weights'].items())}. Scores are 0 to 5; the total is the weighted "
        "mean of the scored criteria.",
        "",
        "| Language | " + " | ".join(crit) + " | Total | Blockers |",
        "| --- | " + " | ".join("---" for _ in crit) + " | --- | --- |",
    ]
    for c in t["candidates"]:
        cells = ["?" if c["scores"][k] is None else f"{c['scores'][k]:g}" for k in crit]
        mark = " (recommended)" if c["language"] == t["recommended"] else ""
        lines.append(f"| {c['language']}{mark} | " + " | ".join(cells) + f" | {c['total'] if c['total'] is not None else '?'} | "
                     f"{'; '.join(c['blockers']) or '-'} |")
    lines += ["", "## Evidence for the top candidates", ""]
    for c in t["candidates"][:3]:
        lines.append(f"### {c['language']}")
        lines.append("")
        for k in crit:
            for e in c["evidence"].get(k, []):
                lines.append(f"- {k}: {e}")
        lines.append("")
    pending = [k for k in ("ecosystem", "team") if all(c["scores"][k] is None for c in t["candidates"])]
    if pending:
        lines += ["## Questions for the user", ""]
        if "ecosystem" in pending:
            lines.append("- Where will the port be used? Name the languages or runtimes of the code that will call it.")
        if "team" in pending:
            lines.append("- Which of these languages do the maintainers know well?")
        lines.append("")
    lines += ["## Decision", "", f"Chosen: {t.get('chosen') or 'pending the user gate'}",
              f"Rationale: {t.get('rationale') or '-'}", ""]
    return "\n".join(lines)


def _parse_list(raw: str | None) -> list[str]:
    return [normalize_lang(x) for x in (raw or "").split(",") if x.strip()]


def cmd_score(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    src = normalize_lang(ws.config["source"].get("language"))
    if not src:
        raise PorterError("source language unknown: finish the survey phase first")
    survey = read_json(ws.p("survey.json")) if ws.p("survey.json").exists() else {}
    kind = survey.get("kind", "unknown")
    risk = set()
    for m in survey.get("modules", []):
        if m.get("role") == "source":
            risk |= set(m.get("risk", []))
    previous = read_json(ws.p("target.json")) if ws.p("target.json").exists() else {}
    inputs = dict(previous.get("userInputs") or {})
    if args.consumers is not None:
        inputs["consumers"] = _parse_list(args.consumers)
    if args.team is not None:
        inputs["team"] = _parse_list(args.team)
    sets = dict(inputs.get("set") or {})
    for item in args.set or []:
        key, _, value = item.partition("=")
        lang, _, crit = key.partition(".")
        if crit not in TARGET_CRITERIA or not value:
            raise PorterError(f"--set expects <language>.<criterion>=<0-5> with criterion in {', '.join(TARGET_CRITERIA)}")
        if not 0 <= float(value) <= 5:
            raise PorterError("--set values are scores from 0 to 5")
        sets[f"{normalize_lang(lang)}.{crit}"] = float(value)
    inputs["set"] = sets
    weights = dict(previous.get("weights") or DEFAULT_WEIGHTS)
    for item in args.weight or []:
        key, _, value = item.partition("=")
        if key not in TARGET_CRITERIA:
            raise PorterError(f"unknown criterion {key}")
        weights[key] = float(value)
    if args.candidates:
        cands = _parse_list(args.candidates)
    elif previous.get("candidates"):
        cands = [c["language"] for c in previous["candidates"]]
    else:
        cands = [c for c in DEFAULT_CANDIDATES if c != src]
        if src == "javascript" and "typescript" not in cands:
            cands.insert(0, "typescript")
    deps = runtime_deps(ws)
    scored = [score_candidate(src, c, kind, deps, risk, inputs) for c in cands]
    for c in scored:
        c["total"] = total(c, weights)
    scored.sort(key=lambda c: (bool(c["blockers"]), -(c["total"] or 0), c["language"]))
    target = {
        "schema": 1,
        "context": {"sourceLanguage": src, "kind": kind, "runtimeDeps": len(deps), "riskTags": sorted(risk),
                    "mode": ws.config["source"].get("mode", "code")},
        "userInputs": inputs,
        "weights": weights,
        "candidates": scored,
        "recommended": scored[0]["language"],
        "chosen": previous.get("chosen"),
        "rationale": previous.get("rationale"),
    }
    md = render_md(target)
    if args.write:
        write_json(ws.p("target.json"), target)
        write_text(ws.p("target.md"), md)
    if args.json:
        print(json.dumps(target, indent=2))
    else:
        print(md)
        if args.write:
            print(f"Wrote {ws.p('target.json')} and {ws.p('target.md')}")
    return 0


def cmd_choose(args: argparse.Namespace) -> int:
    ws = Workspace.open(args.workspace)
    lang = normalize_lang(args.language)
    if not ws.p("target.json").exists():
        raise PorterError("no target.json: run porter.py target score --write first")
    target = read_json(ws.p("target.json"))
    names = [c["language"] for c in target["candidates"]]
    note = args.note.strip()
    if lang not in names:
        note += f" (chosen outside the scored candidates: {', '.join(names)})"
    target["chosen"] = lang
    target["rationale"] = note
    apply_gate(ws, "target", "approve", f"target language: {lang}. {note}")
    write_json(ws.p("target.json"), target)
    write_text(ws.p("target.md"), render_md(target))
    ws.config["target"]["language"] = lang
    write_json(ws.p("config.json"), ws.config)
    ws.state["phases"]["target"]["artifacts"] = artifact_hashes(ws, "target")
    ws.save()
    write_porting_md(ws)
    print(stage_card(ws))
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("target", help="score candidate target languages and record the user's choice")
    ps = p.add_subparsers(dest="target_cmd", required=True)
    s = ps.add_parser("score", help="score candidates (writes target.json and target.md with --write)")
    s.add_argument("--candidates", help="comma-separated languages (default: every supported language except the source)")
    s.add_argument("--consumers", help="languages of the code that will use the port (user answer)")
    s.add_argument("--team", help="languages the maintainers know (user answer)")
    s.add_argument("--set", action="append", help="override one score: <language>.<criterion>=<0-5>; repeatable")
    s.add_argument("--weight", action="append", help="<criterion>=<weight>; repeatable")
    s.add_argument("--write", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--workspace")
    s.set_defaults(func=cmd_score)
    c = ps.add_parser("choose", help="record the user's choice: approves the target gate and sets config.target.language")
    c.add_argument("language")
    c.add_argument("--note", required=True, help="why, in the user's words")
    c.add_argument("--workspace")
    c.set_defaults(func=cmd_choose)
