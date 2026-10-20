import json
import unittest

from util import TempDir, porter, read_json, tiny_python_project, write
from porterlib.state import fixtures_digest


class StateFlowTest(unittest.TestCase):
    def test_code_mode_with_target_given(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            ws = tmp / "port"
            ws.mkdir()
            porter("init", "--source", str(src), "--to", "ts", cwd=ws)
            state = read_json(ws / ".porter" / "state.json")
            self.assertEqual(state["phases"]["recover"]["status"], "SKIPPED")
            self.assertEqual(state["phases"]["target"]["status"], "DONE")
            self.assertEqual(state["phases"]["target"]["gate"], "given")
            self.assertEqual(read_json(ws / ".porter" / "config.json")["target"]["language"], "typescript")
            out = porter("state", "next", cwd=ws).stdout
            self.assertIn("survey", out)

    def test_workspace_flag_after_the_subcommand(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            (tmp / "port").mkdir()
            porter("init", "--source", str(src), "--to", "go", cwd=tmp / "port")
            out = porter("state", "next", "--workspace", str(tmp / "port" / ".porter"), cwd=tmp).stdout
            self.assertIn("survey", out)

    def test_out_of_order_preflight_is_refused(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            porter("init", "--source", str(src), "--to", "go", cwd=tmp)
            proc = porter("state", "preflight", "deps", cwd=tmp, check=False)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("survey must be DONE first", proc.stdout)

    def test_survey_then_target_gate(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            porter("init", "--source", str(src), cwd=tmp)
            porter("state", "preflight", "survey", cwd=tmp)
            porter("survey", "--write", cwd=tmp)
            write(tmp / ".porter" / "survey.md", "# Survey\n\nTiny.\n")
            porter("state", "postflight", "survey", cwd=tmp)
            porter("state", "preflight", "target", cwd=tmp)
            porter("target", "score", "--write", "--candidates", "typescript,go,rust", cwd=tmp)
            proc = porter("state", "postflight", "target", cwd=tmp)
            self.assertIn("GATE_WAIT", proc.stdout)
            refused = porter("state", "gate", "target", "approve", "--note", "x", cwd=tmp, check=False)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("target choose", refused.stderr)
            porter("target", "choose", "go", "--note", "team knows Go", cwd=tmp)
            cfg = read_json(tmp / ".porter" / "config.json")
            self.assertEqual(cfg["target"]["language"], "go")
            self.assertIn("team knows Go", (tmp / ".porter" / "decisions.md").read_text())
            self.assertEqual(read_json(tmp / ".porter" / "target.json")["chosen"], "go")

    def test_rerun_marks_downstream_stale(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            porter("init", "--source", str(src), "--to", "typescript", cwd=tmp)
            porter("state", "preflight", "survey", cwd=tmp)
            porter("survey", "--write", cwd=tmp)
            write(tmp / ".porter" / "survey.md", "# Survey\n")
            porter("state", "postflight", "survey", cwd=tmp)
            write(tmp / ".porter" / "survey.md", "# Survey\n\nchanged after the phase finished\n")
            porter("state", "preflight", "deps", cwd=tmp)
            state = read_json(tmp / ".porter" / "state.json")
            self.assertEqual(state["phases"]["target"]["status"], "DONE", "a given target never goes stale")
            self.assertEqual(state["phases"]["deps"]["status"], "IN_PROGRESS")

    def test_artifact_mode_needs_authorization(self):
        with TempDir() as tmp:
            exe = write(tmp / "tool.sh", "#!/bin/sh\necho hi\n")
            exe.chmod(0o755)
            porter("init", "--source", str(exe), cwd=tmp)
            cfg = read_json(tmp / ".porter" / "config.json")
            self.assertEqual(cfg["source"]["mode"], "artifact")
            proc = porter("state", "preflight", "recover", cwd=tmp, check=False)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("authorization", proc.stdout)
            porter("state", "authorize", "--note", "I wrote this script", cwd=tmp)
            porter("state", "preflight", "recover", cwd=tmp)

    def test_unit_transitions_are_enforced(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            porter("init", "--source", str(src), "--to", "typescript", cwd=tmp)
            ws = tmp / ".porter"
            state = read_json(ws / "state.json")
            for phase in ("survey", "deps", "contract", "strategy"):
                state["phases"][phase]["status"] = "DONE"
            state["phases"]["implement"]["status"] = "IN_PROGRESS"
            state["units"] = {
                "core": {"status": "PENDING", "wave": 0, "attempts": 0, "task": None, "verifiedLevel": None, "note": None},
                "cli": {"status": "PENDING", "wave": 1, "attempts": 0, "task": None, "verifiedLevel": None, "note": None},
            }
            (ws / "state.json").write_text(json.dumps(state))
            plan = {"schema": 1, "draft": False, "order": ["core", "cli"], "units": [
                {"id": "core", "layer": "core", "wave": 0, "symbols": [], "dependsOn": []},
                {"id": "cli", "layer": "entry", "wave": 1, "symbols": [], "dependsOn": ["core"]}]}
            (ws / "plan.json").write_text(json.dumps(plan))
            blocked = porter("state", "unit", "set", "cli", "IN_PROGRESS", cwd=tmp, check=False)
            self.assertIn("dependencies not DONE", blocked.stderr)
            porter("state", "unit", "set", "core", "IN_PROGRESS", cwd=tmp)
            early = porter("state", "unit", "set", "core", "IMPLEMENTED", cwd=tmp, check=False)
            self.assertIn("green", early.stderr)
            porter("state", "unit", "task", "core", "green", cwd=tmp)
            porter("state", "unit", "set", "core", "IMPLEMENTED", cwd=tmp)
            porter("state", "unit", "task", "core", "apply-findings", cwd=tmp)
            porter("state", "unit", "set", "core", "REVIEWED", cwd=tmp)
            no_parity = porter("state", "unit", "set", "core", "VERIFIED", "--level", "EXACT", cwd=tmp, check=False)
            self.assertIn("parity.json", no_parity.stderr)
            (ws / "parity.json").write_text(json.dumps({"units": [{"unit": "core", "level": "EXACT"}]}))
            porter("state", "unit", "set", "core", "VERIFIED", "--level", "EXACT", cwd=tmp)
            porter("state", "unit", "task", "core", "report", cwd=tmp)
            porter("state", "unit", "set", "core", "DONE", cwd=tmp)
            (ws / "parity.json").write_text(json.dumps({"units": [{"unit": "core", "level": "GAP"}]}))
            porter("state", "unit", "set", "core", "GAP", cwd=tmp)
            self.assertEqual(read_json(ws / "state.json")["units"]["core"]["status"], "GAP")
            (ws / "parity.json").write_text(json.dumps({"units": [{"unit": "core", "level": "DIVERGENT"}]}))
            silent = porter("state", "unit", "set", "core", "VERIFIED", "--level", "DIVERGENT", cwd=tmp, check=False)
            self.assertIn("--note", silent.stderr)
            porter("state", "unit", "set", "core", "VERIFIED", "--level", "DIVERGENT", "--note", "user accepted d1", cwd=tmp)
            self.assertEqual(read_json(ws / "state.json")["units"]["core"]["attempts"], 1)

    def test_verify_added_cases_leave_the_fixtures_hash_alone(self):
        with TempDir() as tmp:
            fx = tmp / "fixtures" / "core" / "oracle.json"
            case = {"case": "a", "origin": "hand-written", "call": "m:f", "input": {}, "expect": {"kind": "value", "value": 1}}
            doc = {"schema": 1, "unit": "core", "oracle": {"version": "1.0", "recordedAt": "2026-01-01T00:00:00Z"}, "cases": [case]}
            write(fx, json.dumps(doc))
            before = fixtures_digest(tmp / "fixtures")
            doc["oracle"]["recordedAt"] = "2026-02-01T00:00:00Z"
            doc["cases"] += [dict(case, case="b", origin="adversarial:empty"), dict(case, case="e", origin="verify-adversarial:x"),
                             dict(case, case="c", origin="generated:adversarial-unicode:seed=1")]
            write(fx, json.dumps(doc, indent=2))
            self.assertEqual(fixtures_digest(tmp / "fixtures"), before)
            doc["cases"].append(dict(case, case="d"))
            write(fx, json.dumps(doc))
            self.assertNotEqual(fixtures_digest(tmp / "fixtures"), before)


if __name__ == "__main__":
    unittest.main()
