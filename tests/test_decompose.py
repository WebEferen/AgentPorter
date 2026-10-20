import unittest

import util  # noqa: F401  (puts scripts/ on sys.path)
from porterlib.decompose import decompose
from porterlib.state import DEFAULT_BUDGETS


def sym(name, loc=10, public=True, refs=(), kind="function", io=(), risk=()):
    return {"name": name, "kind": kind, "line": 1, "endLine": loc, "loc": loc, "public": public,
            "refs": list(refs), "io": list(io), "risk": list(risk), "external": []}


def survey(modules):
    return {"modules": [{"id": mid, "path": f"{mid}.py", "language": "python", "loc": sum(s["loc"] for s in syms),
                         "role": "source", "coupling": "pure", "symbols": syms} for mid, syms in modules.items()],
            "entryPoints": [], "tests": {"modules": []}}


def plan_for(modules, **budget):
    b = dict(DEFAULT_BUDGETS, **budget)
    plan, md = decompose(survey(modules), None, None, None, b, draft=True)
    return plan, md


class DecomposeTest(unittest.TestCase):
    def test_cycle_between_modules_collapses(self):
        plan, md = plan_for({
            "a": [sym("fa", 40, refs=["b:fb"])],
            "b": [sym("fb", 40, refs=["a:fa"])],
        })
        self.assertEqual(len(plan["units"]), 1)
        self.assertEqual(len(plan["cycles"]), 1)
        self.assertIn("cycle", md)

    def test_over_budget_module_splits_by_root(self):
        mods = {"big": [sym(f"f{i}", 120) for i in range(4)]}
        plan, _ = plan_for(mods)
        self.assertGreaterEqual(len(plan["units"]), 2)
        self.assertTrue(all(u["loc"] <= 400 for u in plan["units"]))

    def test_constants_do_not_count_toward_symbol_budget(self):
        mods = {"m": [sym(f"C{i}", 1, kind="constant") for i in range(12)] + [sym("f", 40), sym("g", 40)]}
        plan, _ = plan_for(mods)
        self.assertEqual(len(plan["units"]), 1)

    def test_shared_private_helper_goes_to_foundation(self):
        helper = sym("_helper", 60, public=False)
        plan, md = plan_for({
            "util": [helper],
            "a": [sym("fa", 60, refs=["util:_helper"])],
            "b": [sym("fb", 60, refs=["util:_helper"])],
        })
        layers = {u["id"]: u["layer"] for u in plan["units"]}
        self.assertIn("foundation", layers.values())
        found = [u for u in plan["units"] if u["layer"] == "foundation"][0]
        self.assertEqual(plan["order"][0], found["id"])
        self.assertIn("util:_helper", found["symbols"])

    def test_io_split_into_boundary(self):
        plan, md = plan_for({
            "m": [sym("parse", 60, refs=[]), sym("load", 30, refs=["m:parse"], io=["fs"])],
        })
        layers = sorted(u["layer"] for u in plan["units"])
        self.assertEqual(layers, ["boundary", "core"])
        self.assertIn("boundary", md)

    def test_waves_respect_dependencies_and_tracer_is_core(self):
        plan, _ = plan_for({
            "base": [sym("b", 50)],
            "mid": [sym("m", 50, refs=["base:b"])],
            "cli": [sym("main", 50, refs=["mid:m"])],
        })
        by_id = {u["id"]: u for u in plan["units"]}
        for u in plan["units"]:
            for d in u["dependsOn"]:
                self.assertLess(by_id[d]["wave"], u["wave"])
                self.assertLess(plan["order"].index(d), plan["order"].index(u["id"]))
        self.assertNotEqual(by_id[plan["tracer"]]["layer"], "entry")

    def test_ported_dependency_becomes_a_foundation_unit(self):
        s = sym("slug", 60)
        s["external"] = ["text_unidecode"]
        deps = {"dependencies": [{"name": "text-unidecode", "decision": "PORT", "scope": "runtime",
                                  "usedSurface": {"symbols": ["unidecode"]}}]}
        usage = {"usage": {"text-unidecode": {"importNames": ["text_unidecode"]}}}
        plan, md = decompose(survey({"core": [s]}), None, deps, usage, dict(DEFAULT_BUDGETS), draft=False)
        units = {u["id"]: u for u in plan["units"]}
        self.assertEqual(units["dep-text-unidecode"]["layer"], "foundation")
        self.assertIn("dep-text-unidecode", units["core"]["dependsOn"])
        self.assertEqual((units["dep-text-unidecode"]["wave"], units["core"]["wave"]), (0, 1))
        self.assertLess(plan["order"].index("dep-text-unidecode"), plan["order"].index("core"))


if __name__ == "__main__":
    unittest.main()
