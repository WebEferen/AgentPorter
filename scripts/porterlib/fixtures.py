"""Fixture corpus tools: expand oracle case specs (with seeded generators), validate, summarize, dedupe,
merge and diff the language-neutral fixture files under .porter/fixtures/<unit>/."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import string
from pathlib import Path

from . import jsonschema
from .common import PorterError, find_workspace, read_json, write_json

UNICODE_SAMPLE = (
    "àáâãäåæçèéêëìíîïñòóôõöøùúûüýÿßÆØÅœŒĀāĂăĄąĆćČčĐđĒēĘęĚěĞğĪīİıŁłŃńŇňŌōŐőŘřŚśŠšŞşŤťŪūŮůŰűŸŹźŻżŽž"
    "ΑΒΓΔαβγδАБВГДабвгд中文字日本語한국어עבריתالعربية😀🎉👍🏽́̈​‍ -_."
)
ALPHABETS = {
    "ascii": string.ascii_letters + string.digits + string.punctuation + " ",
    "letters": string.ascii_letters,
    "lower": string.ascii_lowercase,
    "printable": string.printable,
    "unicode": UNICODE_SAMPLE + string.ascii_letters + " ",
    "whitespace": " \t\n\r  ",
    "digits": string.digits,
}


def _alphabet(spec: object) -> str:
    if isinstance(spec, list):
        return "".join(_alphabet(s) for s in spec)
    if not isinstance(spec, str) or not spec:
        return ALPHABETS["ascii"]
    return ALPHABETS.get(spec, spec)


def _json_value(rng: random.Random, depth: int, alphabet: str) -> object:
    kinds = ["null", "bool", "int", "float", "string"] + (["array", "object"] * 2 if depth > 0 else [])
    kind = rng.choice(kinds)
    if kind == "null":
        return None
    if kind == "bool":
        return rng.random() < 0.5
    if kind == "int":
        return rng.choice([0, 1, -1, rng.randint(-1000, 1000), rng.randint(-2**53, 2**53)])
    if kind == "float":
        return rng.choice([0.5, -0.25, 1e21, 1.5e-7, round(rng.uniform(-1e6, 1e6), rng.randint(0, 6)), 0.1 + 0.2])
    if kind == "string":
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
    if kind == "array":
        return [_json_value(rng, depth - 1, alphabet) for _ in range(rng.randint(0, 4))]
    keys = ALPHABETS["letters"] + "_-. " + "é中"
    return {"".join(rng.choice(keys) for _ in range(rng.randint(1, 8))): _json_value(rng, depth - 1, alphabet)
            for _ in range(rng.randint(0, 4))}


def generate(tpl: object, rng: random.Random) -> object:
    """Expand a template: dicts with a "$gen" key are generators, everything else is literal (recursively)."""
    if isinstance(tpl, list):
        return [generate(x, rng) for x in tpl]
    if not isinstance(tpl, dict):
        return tpl
    if "$gen" not in tpl:
        return {k: generate(v, rng) for k, v in tpl.items()}
    g = tpl["$gen"]
    if g == "const":
        return tpl.get("value")
    if g == "string":
        alpha = _alphabet(tpl.get("alphabet"))
        n = rng.randint(int(tpl.get("min", 0)), int(tpl.get("max", 20)))
        return "".join(rng.choice(alpha) for _ in range(n))
    if g == "int":
        return rng.randint(int(tpl.get("min", -1000)), int(tpl.get("max", 1000)))
    if g == "float":
        value = rng.uniform(float(tpl.get("min", -1e6)), float(tpl.get("max", 1e6)))
        return round(value, int(tpl["digits"])) if tpl.get("digits") is not None else value
    if g == "bool":
        return rng.random() < float(tpl.get("p", 0.5))
    if g == "choice":
        options = tpl.get("of") or []
        if not options:
            raise PorterError("choice generator needs a non-empty 'of' list")
        return generate(rng.choice(options), rng)
    if g == "list":
        n = rng.randint(int(tpl.get("min", 0)), int(tpl.get("max", 5)))
        return [generate(tpl.get("of"), rng) for _ in range(n)]
    if g == "dict":
        n = rng.randint(int(tpl.get("min", 0)), int(tpl.get("max", 4)))
        out = {}
        for _ in range(n):
            out[str(generate(tpl.get("keys", {"$gen": "string", "alphabet": "lower", "min": 1, "max": 8}), rng))] = \
                generate(tpl.get("values"), rng)
        return out
    if g == "json":
        value = _json_value(rng, int(tpl.get("depth", 3)), _alphabet(tpl.get("alphabet", "ascii")))
        if tpl.get("text"):
            return json.dumps(value, ensure_ascii=bool(tpl.get("ascii", False)), indent=tpl.get("indent"))
        return value
    if g == "concat":
        return "".join(str(generate(p, rng)) for p in tpl.get("parts", []))
    raise PorterError(f"unknown generator '{g}'. Known: const, string, int, float, bool, choice, list, dict, json, concat")


def _case_seed(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:12], 16)


def expand_spec(spec: dict) -> list[dict]:
    errors = jsonschema.validate_named(spec, "cases")
    if errors:
        raise PorterError("invalid case spec:\n  " + "\n  ".join(errors))
    default_call = spec.get("call")
    out, names = [], set()

    def push(case: dict) -> None:
        if case["case"] in names:
            raise PorterError(f"duplicate case name {case['case']} in spec for {spec['unit']}")
        if not case.get("call"):
            raise PorterError(f"case {case['case']} has no call (set it on the case or the spec)")
        names.add(case["case"])
        out.append(case)

    for c in spec.get("cases", []):
        case = {k: v for k, v in c.items() if k != "input"}
        case["call"] = c.get("call") or default_call
        case["input"] = generate(c["input"], random.Random(_case_seed(c["case"])))
        case.setdefault("origin", "hand-written")
        push(case)
    for block in spec.get("generate", []):
        rng = random.Random(block["seed"])
        for i in range(block["count"]):
            if "input" in block:
                inp = generate(block["input"], rng)
            else:
                inp = {"args": generate(block.get("args", []), rng), "kwargs": generate(block.get("kwargs", {}), rng)}
            case = {"case": f"{block['name']}-{i:04d}", "call": block.get("call") or default_call, "input": inp,
                    "origin": f"generated:{block['name']}:seed={block['seed']}"}
            if block.get("normalize"):
                case["normalize"] = list(block["normalize"])
            push(case)
    return out


def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def validate_dir(fixtures: Path) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    summary: dict[str, int] = {}
    if not fixtures.is_dir():
        return [f"missing directory: {fixtures}"], summary
    for unit_dir in sorted(p for p in fixtures.iterdir() if p.is_dir()):
        unit = unit_dir.name
        seen: dict[str, str] = {}
        count = 0
        for f in sorted(unit_dir.glob("*.json")):
            rel = f"fixtures/{unit}/{f.name}"
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{rel}: unreadable ({exc})")
                continue
            errors.extend(f"{rel} {e}" for e in jsonschema.validate_named(data, "fixture"))
            if data.get("unit") != unit:
                errors.append(f"{rel}: unit is '{data.get('unit')}' but the file lives under fixtures/{unit}/")
            for case in data.get("cases", []):
                name = case.get("case")
                if name in seen:
                    errors.append(f"{rel}: case '{name}' also defined in {seen[name]}")
                seen[name] = f.name
                count += 1
        summary[unit] = count
    return errors, summary


def load_unit(fixtures: Path, unit: str) -> tuple[list[dict], list[dict]]:
    """Return (cases, oracles) for one unit, each case annotated with its file."""
    cases, oracles = [], []
    for f in sorted((fixtures / unit).glob("*.json")):
        data = read_json(f)
        oracles.append(data["oracle"])
        for c in data["cases"]:
            cases.append(dict(c, _file=f.name))
    return cases, oracles


def cmd_expand(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    cases_dir = ws / "oracle" / "cases"
    units = [args.unit] if args.unit else sorted(p.stem for p in cases_dir.glob("*.json"))
    if not units:
        raise PorterError(f"no case specs in {cases_dir}")
    for unit in units:
        spec_path = cases_dir / f"{unit}.json"
        spec = read_json(spec_path)
        if spec["unit"] != unit:
            raise PorterError(f"{spec_path}: unit field is '{spec['unit']}', file name says '{unit}'")
        expanded = expand_spec(spec)
        write_json(ws / "oracle" / "expanded" / f"{unit}.json",
                   {"schema": 1, "unit": unit, "kind": spec.get("kind", "value"), "cases": expanded})
        gen = sum(1 for c in expanded if c["origin"].startswith("generated:"))
        print(f"{unit}: {len(expanded)} cases ({len(expanded) - gen} written, {gen} generated) -> oracle/expanded/{unit}.json")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    errors, summary = validate_dir(ws / "fixtures")
    for e in errors:
        print(f"  - {e}")
    print(f"{sum(summary.values())} cases in {len(summary)} units; {len(errors)} errors")
    return 1 if errors else 0


def cmd_summary(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    fx = ws / "fixtures"
    errors, summary = validate_dir(fx)
    print("| Unit | Files | Cases | Kinds | Origins |\n| --- | --- | --- | --- | --- |")
    for unit in sorted(summary):
        cases, _ = load_unit(fx, unit)
        kinds: dict[str, int] = {}
        origins: dict[str, int] = {}
        for c in cases:
            kinds[c["expect"]["kind"]] = kinds.get(c["expect"]["kind"], 0) + 1
            o = (c.get("origin") or "unknown").split(":")[0]
            origins[o] = origins.get(o, 0) + 1
        files = len(list((fx / unit).glob("*.json")))
        print(f"| {unit} | {files} | {len(cases)} | {', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))} | "
              f"{', '.join(f'{k} {v}' for k, v in sorted(origins.items()))} |")
    if errors:
        print(f"\n{len(errors)} validation errors; run porter.py fixtures validate")
    return 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    removed_total = 0
    for f in sorted((ws / "fixtures" / args.unit).glob("*.json")):
        data = read_json(f)
        seen, keep, removed = set(), [], []
        for c in data["cases"]:
            key = (c["call"], _canon(c["input"]))
            if key in seen:
                removed.append(c["case"])
                continue
            seen.add(key)
            keep.append(c)
        if removed:
            data["cases"] = keep
            if not args.dry_run:
                write_json(f, data)
            print(f"{f.name}: {'would remove' if args.dry_run else 'removed'} {len(removed)} duplicate inputs: {', '.join(removed[:10])}")
        removed_total += len(removed)
    print(f"{removed_total} duplicates")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    out = Path(args.into)
    base = read_json(out) if out.exists() else None
    merged: dict[str, dict] = {c["case"]: c for c in (base or {}).get("cases", [])}
    conflicts = []
    for src in args.sources:
        data = read_json(src)
        if base is None:
            base = {k: v for k, v in data.items() if k != "cases"}
        elif data["unit"] != base["unit"]:
            raise PorterError(f"{src} is for unit {data['unit']}, not {base['unit']}")
        for c in data["cases"]:
            prev = merged.get(c["case"])
            if prev and _canon(prev) != _canon(c):
                conflicts.append(c["case"])
                if not args.prefer_new:
                    continue
            merged[c["case"]] = c
    if base is None:
        raise PorterError("nothing to merge")
    base["cases"] = list(merged.values())
    errors = jsonschema.validate_named(base, "fixture")
    if errors:
        raise PorterError("merged file is invalid:\n  " + "\n  ".join(errors))
    write_json(out, base)
    print(f"{out}: {len(base['cases'])} cases; {len(conflicts)} conflicting names "
          f"({'took the new case' if args.prefer_new else 'kept the existing case'}): {', '.join(conflicts[:10])}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    a, b = read_json(args.old), read_json(args.new)
    for path, doc in ((args.old, a), (args.new, b)):
        if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list) or not isinstance(doc.get("oracle"), dict):
            raise PorterError(f"{path} is not a fixture file (no oracle and cases list); timings files are not compared")
    ca = {c["case"]: c for c in a["cases"]}
    cb = {c["case"]: c for c in b["cases"]}
    added = sorted(set(cb) - set(ca))
    removed = sorted(set(ca) - set(cb))
    changed = sorted(n for n in set(ca) & set(cb) if _canon(ca[n]["expect"]) != _canon(cb[n]["expect"])
                     or _canon(ca[n]["input"]) != _canon(cb[n]["input"]))
    print(f"oracle {a['oracle'].get('version')} -> {b['oracle'].get('version')}: "
          f"{len(added)} added, {len(removed)} removed, {len(changed)} changed")
    for n in changed[:args.limit]:
        print(f"- {n}\n    old: {_canon(ca[n]['expect'])[:200]}\n    new: {_canon(cb[n]['expect'])[:200]}")
    return 1 if (added or removed or changed) else 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("fixtures", help="expand case specs, validate and maintain the fixture corpus")
    p.add_argument("--workspace")
    ps = p.add_subparsers(dest="fixtures_cmd", required=True)
    e = ps.add_parser("expand", help="oracle/cases/<unit>.json -> oracle/expanded/<unit>.json (concrete inputs)")
    e.add_argument("--unit")
    e.set_defaults(func=cmd_expand)
    v = ps.add_parser("validate", help="check every fixture file against the schema and for duplicate case names")
    v.set_defaults(func=cmd_validate)
    s = ps.add_parser("summary", help="files, cases, outcome kinds and case origins per unit")
    s.set_defaults(func=cmd_summary)
    d = ps.add_parser("dedupe", help="drop cases whose call and input repeat an earlier case")
    d.add_argument("unit")
    d.add_argument("--dry-run", action="store_true")
    d.set_defaults(func=cmd_dedupe)
    m = ps.add_parser("merge", help="merge fixture files for one unit into one file")
    m.add_argument("sources", nargs="+")
    m.add_argument("--into", required=True)
    m.add_argument("--prefer-new", action="store_true")
    m.set_defaults(func=cmd_merge)
    df = ps.add_parser("diff", help="compare two recordings of the same fixture file (e.g. a new upstream version); exit 1 on any difference")
    df.add_argument("old")
    df.add_argument("new")
    df.add_argument("--limit", type=int, default=20)
    df.set_defaults(func=cmd_diff)
