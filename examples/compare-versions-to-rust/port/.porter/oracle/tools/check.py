import json, re, sys, functools, collections
ws = sys.argv[1]; exp = json.load(open(sys.argv[2]))
fx = {}
for u in ("satisfies-satisfies", "validate-validate"):
    for c in json.load(open(f"{ws}/fixtures/{u}/oracle.json"))["cases"]:
        fx[c["case"]] = c
bad = 0
for name, e in exp["cases"].items():
    got = fx[name]["expect"]
    if e["kind"] == "value":
        ok = got["kind"] == "value" and got["value"] == e["value"] and type(got["value"]) == type(e["value"])
    else:
        ok = got["kind"] == "error" and re.search(re.escape(e["pattern"]), got["message"]) is not None
    if not ok:
        bad += 1; print("MISMATCH", name, e, got)
print(f"harvested assertions checked: {len(exp['cases'])}, mismatches: {bad}")
for test, m in exp["sort"].items():
    inp = m["input"]
    def cmp(a, b):
        i, j = inp.index(a), inp.index(b)
        return fx[m["pairs"][f"{i},{j}"]]["expect"]["value"]
    out = sorted(inp, key=functools.cmp_to_key(cmp))
    print(test, "OK" if out == m["expected"] else f"FAIL {out}")
cats = collections.Counter((c["expect"].get("category"), re.sub(r"\('.*' received\)", "('<v>' received)", c["expect"].get("message", ""), flags=re.S)) for c in fx.values() if c["expect"]["kind"] == "error")
for k, v in cats.most_common(): print(v, k)
vals = collections.Counter(json.dumps(c["expect"]["value"]) for c in fx.values() if c["expect"]["kind"] == "value")
print(vals)
