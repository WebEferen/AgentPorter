"""Round-trip cases for both_test.go::TestJoinSplit (Split(Join(args...)) == args).

derive: for every generated Join case in fixtures/root/oracle.json, add a Split case whose input is the
        recorded Join output (origin derived:...). Replaces earlier derived cases in oracle/cases/root.json.
check:  after re-recording, confirm each derived Split case returned exactly the Join case's args.

Usage: python3 -I derive_roundtrip.py <.porter dir> derive|check
Re-record order: fixtures expand, driver, derive, fixtures expand, driver, check.
"""
import json
import sys
from pathlib import Path

SPLIT = "github.com/kballard/go-shellquote:Split"


def main() -> int:
    ws, mode = Path(sys.argv[1]), sys.argv[2]
    fx = json.loads((ws / "fixtures" / "root" / "oracle.json").read_text(encoding="utf-8"))
    joins = [c for c in fx["cases"] if c["origin"].startswith("generated:join-")]
    if mode == "derive":
        spec_path = ws / "oracle" / "cases" / "root.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["cases"] = [c for c in spec["cases"] if not c.get("origin", "").startswith("derived:")]
        for j in joins:
            if j["expect"]["kind"] != "value":
                raise SystemExit(f"{j['case']}: Join did not return a value")
            spec["cases"].append({
                "case": f"roundtrip.{j['case']}",
                "origin": f"derived:both_test.go::TestJoinSplit:from={j['case']}",
                "call": SPLIT,
                "input": {"args": [j["expect"]["value"]]},
                "tags": ["roundtrip"],
            })
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"derived {len(joins)} round-trip Split cases into {spec_path}")
        return 0
    by_name = {c["case"]: c for c in fx["cases"]}
    bad = []
    for j in joins:
        s = by_name.get(f"roundtrip.{j['case']}")
        if s is None:
            bad.append(f"{j['case']}: no derived Split case recorded")
        elif s["expect"] != {"kind": "value", "value": j["input"]["args"]}:
            bad.append(f"{j['case']}: Split(Join(x)) = {json.dumps(s['expect'], ensure_ascii=False)[:200]}")
    for b in bad:
        print("  -", b)
    print(f"round-trip property: {len(joins) - len(bad)}/{len(joins)} hold")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
