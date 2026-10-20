"""Decompose a port into units (plan section 5): roots, reachability clusters, foundation, layers,
cycle collapse, size budgets, waves, risk, tracer bullet and order. Proposes plan.json + decomposition.md."""
from __future__ import annotations

import argparse
import heapq
import re
from collections import defaultdict
from pathlib import Path

from .common import PorterError, find_workspace, now_iso, read_json, write_json, write_text
from .graph import tarjan_scc, waves as compute_waves
from .signals import risk_score

NATIVE_SIGNALS = {"ffi", "cgo", "jni", "pinvoke"}
WELDED_SIGNALS = {"dynamic-attrs", "metaclass", "frame-introspection", "eval", "framework", "proxy-reflect",
                  "prototype-mutation", "dom", "reflect", "unsafe", "magic", "dynamic", "metaprogramming"}
BUDGET_KINDS = {"function", "class", "method", "interface", "trait", "struct", "enum", "module"}
LAYER_RANK = {"foundation": 0, "boundary": 1, "native": 1, "runtime-welded": 1, "core": 2, "entry": 3}
DEFAULT_ACCEPTANCE = [
    "every fixture passes, or the mismatch is a documented DIVERGENCE",
    "every mapped reference test resolves to PASS, OUT-OF-SCOPE or DIVERGENCE",
    "format, lint, typecheck and tests are green",
    "the code follows the idiom map in strategy.md",
]


class Sym:
    __slots__ = ("id", "module", "name", "kind", "loc", "public", "refs", "coupling", "risk", "external", "path", "file", "line", "end")

    def __init__(self, module: dict, s: dict):
        self.id = f"{module['id']}:{s['name']}"
        self.module = module["id"]
        self.name = s["name"]
        self.kind = s.get("kind", "function")
        self.loc = int(s.get("loc", 0))
        self.public = bool(s.get("public"))
        self.refs = list(s.get("refs", []))
        sig = set(s.get("io", []))
        self.coupling = ("native" if sig & NATIVE_SIGNALS else "runtime-welded" if sig & WELDED_SIGNALS
                         else "io" if sig else "pure")
        self.risk = set(s.get("risk", []))
        self.external = list(s.get("external", []))
        self.path = module["path"]
        self.file = s.get("file") or module["path"]
        self.line = s.get("line", 1)
        self.end = s.get("endLine", self.line)


class Cluster:
    def __init__(self, cid: str, symbols: set[str], module: str | None, layer: str | None = None):
        self.id = cid
        self.symbols = set(symbols)
        self.module = module
        self.layer = layer
        self.notes: list[str] = []
        self.over_budget = False


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "unit"


def _is_error(sym: Sym) -> bool:
    return sym.kind == "class" and bool(re.search(r"(Error|Exception|Failure)$", sym.name))


def decompose(survey: dict, api: dict | None, deps: dict | None, usage: dict | None, budgets: dict,
              draft: bool) -> tuple[dict, str]:
    log: list[str] = []
    entry_modules = set()
    for e in survey.get("entryPoints", []):
        if e["kind"] == "cli":
            target = str(e.get("target") or "")
            for m in survey["modules"]:
                if m["role"] == "source" and (m["path"] == target or target.startswith(m["id"] + ":")
                                              or m["path"].rsplit(".", 1)[0] == target.rsplit(".", 1)[0].lstrip("./")):
                    entry_modules.add(m["id"])
    for m in survey["modules"]:
        if m["role"] == "source" and (m["id"].endswith("__main__") or m["id"].endswith(".cli") or m["id"] in ("cli", "main")):
            entry_modules.add(m["id"])

    syms: dict[str, Sym] = {}
    for m in survey["modules"]:
        if m["role"] != "source":
            continue
        for s in m["symbols"]:
            sym = Sym(m, s)
            syms.setdefault(sym.id, sym)
    for sym in syms.values():
        sym.refs = [r for r in sym.refs if r in syms and r != sym.id]

    # roots
    roots: list[str] = []
    unknown_roots: list[str] = []
    out_of_scope: set[str] = set()
    if api:
        for a in api["symbols"]:
            sid = a["id"]
            node = sid if sid in syms else f"{sid.split(':')[0]}:{sid.split(':', 1)[1].split('.')[0]}" if ":" in sid else sid
            if not a["inScope"]:
                if node in syms:
                    out_of_scope.add(node)
                continue
            if node in syms:
                if node not in roots:
                    roots.append(node)
            else:
                unknown_roots.append(sid)
        out_of_scope -= set(roots)
    else:
        roots = [sid for sid, s in syms.items() if s.public and s.module not in entry_modules]
        roots += [sid for sid, s in syms.items() if s.module in entry_modules and s.public]
    if not roots:
        raise PorterError("no roots: the survey found no public symbols and api.json lists none in scope", code=1)
    root_set = set(roots)

    # reachability that stops at other roots
    reach: dict[str, set[str]] = {}
    for r in roots:
        seen = {r}
        stack = [r]
        while stack:
            cur = stack.pop()
            for nxt in syms[cur].refs:
                if nxt in seen or nxt in root_set or nxt in out_of_scope:
                    continue
                seen.add(nxt)
                stack.append(nxt)
        reach[r] = seen
    owners: dict[str, set[str]] = defaultdict(set)
    for r, members in reach.items():
        for s in members:
            owners[s].add(r)

    # initial clusters: roots grouped by module
    clusters: dict[str, Cluster] = {}
    root_cluster: dict[str, str] = {}
    for r in roots:
        mod = syms[r].module
        cid = f"m:{mod}"
        clusters.setdefault(cid, Cluster(cid, set(), mod))
        clusters[cid].symbols.add(r)
        root_cluster[r] = cid
    shared: dict[str, set[str]] = defaultdict(set)
    orphans = []
    for sid, sym in syms.items():
        if sid in root_set or sid in out_of_scope:
            continue
        own = {root_cluster[o] for o in owners.get(sid, ())}
        if len(own) == 1:
            clusters[next(iter(own))].symbols.add(sid)
        elif len(own) > 1:
            shared[sym.module].add(sid)
        else:
            home = f"m:{sym.module}"
            if home in clusters and not draft:
                clusters[home].symbols.add(sid)
                orphans.append((sid, f"unreachable from any root; kept with its module cluster {sym.module}"))
            elif home in clusters:
                clusters[home].symbols.add(sid)
            else:
                orphans.append((sid, "unreachable from any in-scope root; not assigned"))
    for mod, members in shared.items():
        cid = f"f:{mod}"
        clusters[cid] = Cluster(cid, members, mod, "foundation")
        log.append(f"shared helpers in {mod} ({', '.join(sorted(syms[s].name for s in members))}) are used by several "
                   f"clusters: moved to the foundation layer")
    for sid, sym in syms.items():
        if sid in root_set and _is_error(sym):
            src = clusters[root_cluster[sid]]
            if len(src.symbols) > 1:
                src.symbols.discard(sid)
                cid = f"f:errors:{sym.module}"
                clusters.setdefault(cid, Cluster(cid, set(), sym.module, "foundation")).symbols.add(sid)
                root_cluster[sid] = cid
                log.append(f"error type {sym.name} moved to the foundation layer")

    def symbol_owner() -> dict[str, str]:
        return {s: cid for cid, c in clusters.items() for s in c.symbols}

    def cluster_edges() -> dict[str, set[str]]:
        owner = symbol_owner()
        edges: dict[str, set[str]] = defaultdict(set)
        for cid, c in clusters.items():
            for s in c.symbols:
                for r in syms[s].refs:
                    o = owner.get(r)
                    if o and o != cid:
                        edges[cid].add(o)
        return edges

    def loc(c: Cluster) -> int:
        return sum(syms[s].loc for s in c.symbols)

    def budget_root(s: str) -> bool:
        return s in root_set and syms[s].kind in BUDGET_KINDS

    def public_count(c: Cluster) -> int:
        return sum(1 for s in c.symbols if budget_root(s))

    def merge(ids: list[str], new_id: str, layer: str | None) -> Cluster:
        members = set().union(*(clusters[i].symbols for i in ids))
        mods = sorted({clusters[i].module for i in ids if clusters[i].module})
        notes = [n for i in ids for n in clusters[i].notes]
        for i in ids:
            del clusters[i]
        c = Cluster(new_id, members, mods[0] if len(mods) == 1 else None, layer)
        c.notes = notes
        clusters[new_id] = c
        return c

    # foundation consolidation: types/constants/errors used by two or more clusters
    edges = cluster_edges()
    indeg: dict[str, int] = defaultdict(int)
    for cid, outs in edges.items():
        for o in outs:
            indeg[o] += 1
    for cid, c in list(clusters.items()):
        if c.layer == "foundation":
            continue
        kinds = {syms[s].kind for s in c.symbols}
        if indeg[cid] >= 2 and kinds <= {"type", "constant"} | ({"class"} if all(_is_error(syms[s]) or syms[s].kind != "class" for s in c.symbols) else set()):
            c.layer = "foundation"
            log.append(f"{c.module} holds only types, constants or errors used by {indeg[cid]} clusters: foundation layer")
    found = [cid for cid, c in clusters.items() if c.layer == "foundation"]
    if len(found) > 1 and sum(loc(clusters[f]) for f in found) <= budgets["unitMaxLoc"]:
        merge(found, "f:foundation", "foundation")
        log.append(f"merged {len(found)} foundation clusters into one unit (fits the {budgets['unitMaxLoc']} LOC budget)")

    # collapse cycles between clusters
    def collapse_cycles(reason: str) -> list[dict]:
        found_cycles = []
        while True:
            edges = cluster_edges()
            comps = [c for c in tarjan_scc(list(clusters), edges) if len(c) > 1]
            if not comps:
                return found_cycles
            for comp in comps:
                cut = []
                owner = symbol_owner()
                for a in comp:
                    for s in clusters[a].symbols:
                        for r in syms[s].refs:
                            if owner.get(r) in comp and owner.get(r) != a:
                                cut.append(f"{syms[s].id} -> {r}")
                layer = min((clusters[i].layer for i in comp if clusters[i].layer), key=lambda l: LAYER_RANK.get(l, 2), default=None)
                merged = merge(sorted(comp), "c:" + "+".join(sorted(comp)), layer if layer == "foundation" else None)
                total = loc(merged)
                entry = {"clusters": sorted(comp), "edges": sorted(set(cut))[:20], "loc": total, "reason": reason}
                if total > budgets["unitMaxLoc"]:
                    merged.over_budget = True
                    merged.notes.append(f"cycle needs a seam: {total} LOC over the {budgets['unitMaxLoc']} budget; "
                                        f"cutting one of these edges would split it: {'; '.join(entry['edges'][:5])}")
                found_cycles.append(entry)
                log.append(f"cycle between {', '.join(sorted(comp))} collapsed into one unit ({total} LOC, {reason})")

    cycles_found = collapse_cycles("import or call cycle")

    # layers and the pure/io split
    for cid, c in list(clusters.items()):
        if c.layer == "foundation":
            continue
        mods = {syms[s].module for s in c.symbols}
        if mods & entry_modules:
            c.layer = "entry"
            continue
        couplings = {syms[s].coupling for s in c.symbols}
        if "native" in couplings:
            c.layer = "native"
        elif "runtime-welded" in couplings:
            c.layer = "runtime-welded"
        elif couplings == {"io"}:
            c.layer = "boundary"
        elif "io" in couplings:
            io_part = {s for s in c.symbols if syms[s].coupling == "io"}
            pure_part = c.symbols - io_part
            io_refs_pure = any(r in pure_part for s in io_part for r in syms[s].refs)
            pure_refs_io = any(r in io_part for s in pure_part for r in syms[s].refs)
            if pure_part & root_set and not (io_refs_pure and pure_refs_io):
                c.symbols = pure_part
                c.layer = "core"
                bid = cid + ":io"
                clusters[bid] = Cluster(bid, io_part, c.module, "boundary")
                log.append(f"{c.module}: split I/O symbols ({', '.join(sorted(syms[s].name for s in io_part))}) into a "
                           f"boundary unit; port them behind an interface so core fixtures stay deterministic")
            else:
                c.layer = "boundary"
                c.notes.append("pure and I/O code call each other here; keep one unit and inject the I/O at the call site")
        else:
            c.layer = "core"

    # size budgets: split by roots
    for cid, c in list(clusters.items()):
        c_roots = [s for s in c.symbols if s in root_set]
        if loc(c) <= budgets["unitMaxLoc"] and public_count(c) <= budgets["unitMaxSymbols"]:
            continue
        if len(c_roots) < 2:
            c.over_budget = True
            c.notes.append(f"{loc(c)} LOC in a single root: over budget; implement it in several tasks inside the unit")
            continue
        exclusive = {r: {s for s in c.symbols if owners.get(s) == {r} or s == r} for r in c_roots}
        bins: list[set[str]] = []
        for r in sorted(c_roots, key=lambda r: -sum(syms[s].loc for s in exclusive[r])):
            best, best_overlap = None, -1
            for b in bins:
                broots = [x for x in b if x in root_set]
                size = sum(syms[s].loc for s in b | exclusive[r])
                counted = sum(1 for x in broots if budget_root(x)) + (1 if budget_root(r) else 0)
                if size > budgets["unitMaxLoc"] or counted > budgets["unitMaxSymbols"]:
                    continue
                overlap = sum(1 for s in c.symbols if owners.get(s, set()) & set(broots) and r in owners.get(s, set()))
                if overlap > best_overlap:
                    best, best_overlap = b, overlap
            if best is None:
                bins.append(set(exclusive[r]))
            else:
                best |= exclusive[r]
        assigned = set().union(*bins)
        rest = c.symbols - assigned
        if len(bins) < 2:
            c.over_budget = True
            c.notes.append(f"{loc(c)} LOC over budget but its roots could not be separated")
            continue
        layer = c.layer
        del clusters[cid]
        for i, b in enumerate(bins):
            if i == 0:
                b |= rest
            first_root = sorted((s for s in b if s in root_set), key=lambda s: -syms[s].loc)[0]
            nid = f"{cid}/{syms[first_root].name}"
            clusters[nid] = Cluster(nid, b, c.module, layer)
        log.append(f"{c.module}: {loc(Cluster('x', c.symbols, None))} LOC or {public_count(c)} public functions/classes over budget; "
                   f"split into {len(bins)} units by root reachability")
    cycles_found += collapse_cycles("created by a budget split")

    # merges: small leaf clusters with exactly one consumer
    changed = True
    while changed:
        changed = False
        edges = cluster_edges()
        consumers: dict[str, set[str]] = defaultdict(set)
        for cid, outs in edges.items():
            for o in outs:
                consumers[o].add(cid)
        for cid, c in sorted(clusters.items()):
            if c.layer in ("foundation", "entry", "boundary", "native") or loc(c) >= budgets["unitMinLoc"]:
                continue
            cons = consumers.get(cid, set())
            if len(cons) == 1:
                target = next(iter(cons))
                t = clusters[target]
                fits = loc(t) + loc(c) <= budgets["unitMaxLoc"] and public_count(t) + public_count(c) <= budgets["unitMaxSymbols"]
                if fits and t.layer in ("core", "runtime-welded", c.layer):
                    t.symbols |= c.symbols
                    t.notes += c.notes
                    del clusters[cid]
                    log.append(f"{cid} ({loc(c)} LOC, under the {budgets['unitMinLoc']} LOC floor) merged into its only consumer {target}")
                    changed = True
                    break

    # a foundation below the LOC floor folds into the consumer that every other consumer already depends on
    for cid, c in list(clusters.items()):
        if c.layer != "foundation" or loc(c) >= budgets["unitMinLoc"]:
            continue
        edges = cluster_edges()
        cons = {k for k, outs in edges.items() if cid in outs}

        def reaches(a: str, b: str) -> bool:
            seen, stack = {a}, [a]
            while stack:
                for n in edges.get(stack.pop(), ()):
                    if n == b:
                        return True
                    if n not in seen and n != cid:
                        seen.add(n)
                        stack.append(n)
            return False

        hosts = [h for h in sorted(cons) if all(o == h or reaches(o, h) for o in cons)]
        if hosts:
            host = clusters[hosts[0]]
            host.symbols |= c.symbols
            del clusters[cid]
            log.append(f"foundation {cid} ({loc(c)} LOC, under the {budgets['unitMinLoc']} LOC floor) folded into "
                       f"{hosts[0]}, which every other consumer already depends on")

    # unknown roots from api.json
    for sid in unknown_roots:
        mod = sid.split(":")[0]
        home = next((cid for cid, c in clusters.items() if c.module == mod), None)
        if home:
            clusters[home].notes.append(f"also owns {sid} (declared in api.json, not found by the survey)")
        else:
            clusters[f"x:{sid}"] = Cluster(f"x:{sid}", set(), mod, "core")
            clusters[f"x:{sid}"].notes.append(f"owns {sid} (declared in api.json, not found by the survey)")

    # ids
    names: dict[str, str] = {}
    taken: set[str] = set()
    for cid, c in sorted(clusters.items(), key=lambda kv: kv[0]):
        if c.layer == "foundation" and cid == "f:foundation":
            base = "foundation"
        elif cid.startswith("f:errors:"):
            base = "errors"
        elif cid.startswith("f:"):
            base = "foundation" if len([x for x in clusters if x.startswith("f:")]) == 1 else "shared-" + (c.module or "x").split(".")[-1]
        else:
            mod = c.module or cid.split(":", 1)[-1]
            parts = re.split(r"[./]", mod)
            base = parts[-1] if parts[-1] not in ("index", "__init__", "main", "lib", "src", "mod") or len(parts) == 1 else parts[-2]
            if "/" in cid.split(":", 1)[-1] and cid.startswith("m:"):
                base += "-" + cid.rsplit("/", 1)[-1]
            if cid.endswith(":io"):
                base += "-io"
            if cid.startswith("c:"):
                base = "cycle-" + base
        base = _slug(base.replace("__", ""))
        uid, n = base, 2
        while uid in taken:
            uid, n = f"{base}-{n}", n + 1
        taken.add(uid)
        names[cid] = uid

    # unit graph, waves, order
    edges = cluster_edges()
    deps_of = {names[c]: sorted({names[o] for o in edges.get(c, ())}) for c in clusters}
    try:
        wave = compute_waves(list(deps_of), deps_of)
    except ValueError as exc:
        raise PorterError(f"internal error, unit graph still cyclic: {exc}")

    import_to_dep: dict[str, str] = {}
    for name, u in ((usage or {}).get("usage") or {}).items():
        for imp in u.get("importNames", []):
            import_to_dep[imp] = name
    decisions = {d["name"]: d["decision"] for d in (deps or {}).get("dependencies", [])}

    units = []
    for cid, c in clusters.items():
        uid = names[cid]
        members = sorted(c.symbols, key=lambda s: (syms[s].file, syms[s].line))
        risk = set().union(*(syms[s].risk for s in members)) if members else set()
        ext = set()
        for s in members:
            for e in syms[s].external:
                ext.add(import_to_dep.get(e) or import_to_dep.get(e.split(".")[0]) or e)
        sources: dict[str, list[list[int]]] = defaultdict(list)
        for s in members:
            rng = sources[syms[s].file]
            if rng and syms[s].line <= rng[-1][1] + 2:
                rng[-1][1] = max(rng[-1][1], syms[s].end)
            else:
                rng.append([syms[s].line, syms[s].end])
        test_refs = sorted({t["path"] for t in survey.get("tests", {}).get("modules", [])
                            if set(t.get("imports", [])) & {syms[s].module for s in members}})
        units.append({
            "id": uid,
            "name": uid.replace("-", " "),
            "layer": c.layer or "core",
            "wave": wave[uid],
            "symbols": [s for s in members if s in root_set] + [s for s in members if s not in root_set],
            "publicSymbols": [s for s in members if s in root_set],
            "sources": [{"path": p, "lines": r} for p, rs in sources.items() for r in rs],
            "loc": sum(syms[s].loc for s in members),
            "dependsOn": deps_of[uid],
            "externalDeps": sorted(f"{e} ({decisions[e]})" if e in decisions else e for e in ext),
            "fixtures": {"path": f"fixtures/{uid}/", "expected": None},
            "noFixturesReason": None,
            "referenceTests": test_refs,
            "riskTags": sorted(risk),
            "riskScore": risk_score(risk),
            "strategy": None,
            "acceptance": list(DEFAULT_ACCEPTANCE),
            "deferred": None,
            "discovered": False,
            "tracer": False,
            "overBudget": c.over_budget,
            "notes": "; ".join(c.notes) or None,
        })
    ported = [d for d in (deps or {}).get("dependencies", []) if d["decision"] == "PORT" and d.get("scope") == "runtime"]
    for d in ported:
        uid = "dep-" + _slug(d["name"])
        users = [u["id"] for u in units if any(x == d["name"] or x.startswith(d["name"] + " (") for x in u["externalDeps"])]
        for u in units:
            if u["id"] in users:
                u["dependsOn"] = sorted(set(u["dependsOn"]) | {uid})
        surface = ", ".join((d.get("usedSurface") or {}).get("symbols") or []) or "see deps.json"
        units.append({
            "id": uid, "name": f"port of {d['name']}", "layer": "foundation", "wave": 0, "symbols": [],
            "publicSymbols": [], "sources": [], "loc": 0, "dependsOn": [], "externalDeps": [f"{d['name']} (PORT)"],
            "fixtures": {"path": f"fixtures/{uid}/", "expected": None},
            "noFixturesReason": "ported dependency: the fixtures of the units that use it exercise it",
            "referenceTests": [], "riskTags": [], "riskScore": 0, "strategy": None,
            "acceptance": list(DEFAULT_ACCEPTANCE), "deferred": None, "discovered": False, "tracer": False,
            "overBudget": False, "notes": f"deps.json decision PORT; used surface: {surface}",
        })
        log.append(f"{uid}: unit for the PORT decision on {d['name']}, needed by {', '.join(users) or 'no unit'}")
    if ported:
        new_wave = compute_waves([u["id"] for u in units], {u["id"]: u["dependsOn"] for u in units})
        for u in units:
            u["wave"] = new_wave[u["id"]]
    by_id = {u["id"]: u for u in units}

    def closure(uid: str) -> set[str]:
        out, stack = {uid}, [uid]
        while stack:
            for d in by_id[stack.pop()]["dependsOn"]:
                if d not in out:
                    out.add(d)
                    stack.append(d)
        return out

    depended = {d for u in units for d in u["dependsOn"]}
    tops = [u for u in units if u["layer"] not in ("foundation", "entry")] or \
        [u for u in units if u["id"] not in depended and u["layer"] != "foundation"]
    tracer = None
    if tops:
        def tracer_key(u: dict) -> tuple:
            cl = closure(u["id"])
            return (0 if len(cl) > 1 else 1, sum(by_id[x]["riskScore"] for x in cl), sum(by_id[x]["loc"] for x in cl), u["id"])
        pick = min(tops, key=tracer_key)
        tracer = pick["id"]
        tracer_set = closure(tracer)
        for x in tracer_set:
            by_id[x]["tracer"] = x == tracer
        log.append(f"tracer bullet: {tracer} (closure {', '.join(sorted(tracer_set))}), the lowest-risk vertical slice")
    else:
        tracer_set = set()

    def prio(u: dict) -> tuple:
        group = 0 if u["layer"] == "foundation" else 1 if u["id"] in tracer_set else 2
        return (group, u["wave"], -u["riskScore"], u["id"])
    indeg2 = {u["id"]: len(u["dependsOn"]) for u in units}
    users: dict[str, list[str]] = defaultdict(list)
    for u in units:
        for d in u["dependsOn"]:
            users[d].append(u["id"])
    heap = [(prio(by_id[u]), u) for u, n in indeg2.items() if n == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, uid = heapq.heappop(heap)
        order.append(uid)
        for v in users[uid]:
            indeg2[v] -= 1
            if indeg2[v] == 0:
                heapq.heappush(heap, (prio(by_id[v]), v))
    units.sort(key=lambda u: order.index(u["id"]))
    layers: dict[str, list[str]] = defaultdict(list)
    for u in units:
        layers[u["layer"]].append(u["id"])

    plan = {
        "schema": 1,
        "draft": draft,
        "generatedBy": "porter.py decompose",
        "generatedAt": now_iso(),
        "budgets": {k: budgets[k] for k in ("unitMaxLoc", "unitMaxSymbols", "unitMinLoc")},
        "tracer": tracer,
        "order": order,
        "layers": dict(layers),
        "cycles": cycles_found,
        "orphans": [{"symbol": s, "note": n} for s, n in orphans],
        "unknownRoots": unknown_roots,
        "adjustments": [],
        "units": units,
    }
    return plan, render_markdown(plan, log, survey)


def render_markdown(plan: dict, log: list[str], survey: dict) -> str:
    lines = [
        "# Decomposition",
        "",
        f"Proposed by `porter.py decompose` on {plan['generatedAt'][:10]}"
        + (" (draft, used to group fixtures in the contract phase)." if plan["draft"] else "."),
        f"Budgets: at most {plan['budgets']['unitMaxLoc']} LOC and {plan['budgets']['unitMaxSymbols']} public functions, classes and types with members per unit (constants and aliases do not count), "
        f"merge below {plan['budgets']['unitMinLoc']} LOC.",
        "",
        "## Layer map",
        "",
    ]
    for layer in ("foundation", "boundary", "native", "runtime-welded", "core", "entry"):
        if plan["layers"].get(layer):
            lines.append(f"- {layer}: {', '.join(plan['layers'][layer])}")
    lines += ["", "## Units in order", "",
              "| # | Unit | Layer | Wave | LOC | Public symbols | Depends on | Risk | Notes |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, u in enumerate(plan["units"], 1):
        pub = ", ".join(s.split(":", 1)[1] for s in u["publicSymbols"]) or "(internal)"
        flag = " (tracer)" if u["tracer"] else ""
        notes = (u["notes"] or "") + (" OVER BUDGET" if u.get("overBudget") else "")
        lines.append(f"| {i} | {u['id']}{flag} | {u['layer']} | {u['wave']} | {u['loc']} | {pub} | "
                     f"{', '.join(u['dependsOn']) or '-'} | {', '.join(u['riskTags']) or '-'} | {notes} |")
    lines += ["", "## Why the cuts are where they are", ""]
    lines += [f"- {entry}" for entry in log] or ["- No splits, merges or cycles: each module cluster became one unit."]
    if plan["cycles"]:
        lines += ["", "## Cycles", ""]
        for c in plan["cycles"]:
            lines.append(f"- {', '.join(c['clusters'])}: {c['loc']} LOC ({c['reason']}). Edges: {'; '.join(c['edges'][:6])}")
    if plan["orphans"]:
        lines += ["", "## Orphans", ""]
        lines += [f"- `{o['symbol']}`: {o['note']}" for o in plan["orphans"]]
    if plan["unknownRoots"]:
        lines += ["", "## Symbols in api.json the survey did not find", ""]
        lines += [f"- `{s}`" for s in plan["unknownRoots"]]
    lines += ["", "## Adjustments", "",
              "The agent records every change it makes to the proposal here, one line each: what changed and why.",
              "", "- (none yet)", ""]
    return "\n".join(lines)


CARRY = ("strategy", "noFixturesReason", "deferred", "acceptance", "fixtures", "referenceTests", "notes", "discovered")


def cmd_decompose(args: argparse.Namespace) -> int:
    ws = find_workspace(args.workspace)
    cfg = read_json(ws / "config.json")
    budgets = dict(cfg["options"]["budgets"])
    for key in ("max_loc", "max_symbols", "min_loc"):
        val = getattr(args, key)
        if val is not None:
            budgets[{"max_loc": "unitMaxLoc", "max_symbols": "unitMaxSymbols", "min_loc": "unitMinLoc"}[key]] = val
    survey = read_json(ws / "survey.json")
    api = read_json(ws / "contract" / "api.json") if (ws / "contract" / "api.json").exists() and not args.draft else None
    deps = read_json(ws / "deps.json") if (ws / "deps.json").exists() else None
    usage = read_json(ws / "cache" / "usage.json") if (ws / "cache" / "usage.json").exists() else None
    plan, md = decompose(survey, api, deps, usage, budgets, args.draft)
    write_json(ws / "decomposition.proposed.json", plan)
    existing = ws / "plan.json"
    if existing.exists() and not args.force:
        old = read_json(existing)
        if not old.get("draft") and not args.draft:
            print(md)
            print(f"\nplan.json already exists and is final; proposal written to {ws / 'decomposition.proposed.json'}. "
                  "Pass --force to replace plan.json.")
            return 0
    if existing.exists():
        old_units = {u["id"]: u for u in read_json(existing).get("units", [])}
        for u in plan["units"]:
            prev = old_units.get(u["id"])
            if prev:
                for key in CARRY:
                    if prev.get(key) not in (None, [], {}):
                        u[key] = prev[key]
    write_json(existing, plan)
    write_text(ws / "decomposition.md", md)
    print(md)
    print(f"\nWrote {existing} ({'draft' if args.draft else 'final'}) and {ws / 'decomposition.md'}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("decompose", help="propose units, layers, waves and order (writes plan.json and decomposition.md)")
    p.add_argument("--draft", action="store_true", help="contract phase: group by public symbols, ignore api.json")
    p.add_argument("--force", action="store_true", help="replace an existing final plan.json")
    p.add_argument("--max-loc", type=int)
    p.add_argument("--max-symbols", type=int)
    p.add_argument("--min-loc", type=int)
    p.add_argument("--workspace")
    p.set_defaults(func=cmd_decompose)
