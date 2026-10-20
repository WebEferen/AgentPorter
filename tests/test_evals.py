import json
import re
import subprocess
import sys
import unittest

import util
from util import ROOT, TempDir, read_json

STAGE = ROOT / "evals" / "_lib" / "stage.py"


def build(stage: str, cwd, *extra: str) -> None:
    r = subprocess.run([sys.executable, str(STAGE), stage, *extra], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"stage {stage} failed:\n{r.stdout}\n{r.stderr}")


class EvalCaseTest(unittest.TestCase):
    def test_every_case_is_complete(self):
        cases = [d for d in (ROOT / "evals").iterdir() if (d / "prompt.md").exists()]
        self.assertGreaterEqual(len(cases), 30)
        known = set(re.findall(r'^    "([a-z-]+)":', STAGE.read_text(), re.M))
        for d in cases:
            self.assertTrue(list((d / "graders").glob("*.md")), f"{d.name} has no graders")
            stage = re.search(r"stage\.py\" (\S+)", (d / "scaffold.sh").read_text()).group(1)
            self.assertIn(stage, known, f"{d.name} uses unknown stage {stage}")

    def test_deep_stages_build(self):
        for stage, extra in (("verify-divergence", ()), ("implement-stale", ()), ("surveyed-notarget", ()),
                             ("artifact-authorized", ()), ("surveyed", ("--license", "GPL-3.0-only"))):
            with self.subTest(stage=stage), TempDir() as tmp:
                build(stage, tmp, *extra)
                self.assertTrue((tmp / ".porter" / "state.json").exists())
        with TempDir() as tmp:
            build("verify-gap", tmp)
            r = util.porter("parity", "collect", cwd=tmp, check=False)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(read_json(tmp / ".porter" / "parity.json")["units"][0]["level"], "GAP")

    def test_contract_needs_a_fixture_per_callable_symbol(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from porterlib.state import Workspace, validate_phase
        with TempDir() as tmp:
            build("contract-done", tmp)
            ws = Workspace(tmp / ".porter")
            self.assertEqual(validate_phase(ws, "contract"), [])
            api_path = tmp / ".porter" / "contract" / "api.json"
            api = read_json(api_path)
            for s in api["symbols"]:
                if s["name"] == "ascii_fold":
                    s.update(inScope=True, unit="core", reason=None)
            api_path.write_text(json.dumps(api))
            self.assertTrue(any("ascii_fold" in e for e in validate_phase(ws, "contract")))


if __name__ == "__main__":
    unittest.main()
