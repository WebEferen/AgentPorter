import json
import unittest

from util import TempDir, porter, read_json, tiny_python_project, write
from porterlib import registry


class LicenseTest(unittest.TestCase):
    def test_copy_license_for_ported_code(self):
        self.assertTrue(registry.copy_license("MIT", "MIT")["compatible"])
        self.assertTrue(registry.copy_license("GPL-3.0-only OR MIT", "MIT")["compatible"])
        self.assertTrue(registry.copy_license("GPL-3.0-only", "GPL-3.0-only")["compatible"])
        self.assertFalse(registry.copy_license("Artistic License OR GNU General Public License (GPL)", "MIT")["compatible"])
        self.assertFalse(registry.copy_license("MPL-2.0", "MIT")["compatible"])
        self.assertIsNone(registry.copy_license(None, "MIT")["compatible"])

    def test_release_age(self):
        self.assertTrue(registry._older_than("2019-08-30T00:00:00Z", days=730))
        self.assertFalse(registry._older_than(registry.now_iso(), days=730))
        self.assertFalse(registry._older_than(None, days=730))


class VerifyDepsTest(unittest.TestCase):
    def test_port_of_a_copyleft_dependency_is_a_gate_item(self):
        with TempDir() as tmp:
            src = tiny_python_project(tmp / "src")
            porter("init", "--source", str(src), "--to", "typescript", cwd=tmp)
            ws = tmp / ".porter"
            cfg = read_json(ws / "config.json")
            cfg["source"].update(language="python", license={"spdx": "MIT", "copyleft": "none"})
            write(ws / "config.json", json.dumps(cfg))
            cache = ws / "cache" / "registry"
            seeds = [registry._result("pypi", "text-unidecode", exists=True, latestVersion="1.3",
                                      license="Artistic License OR GNU General Public License (GPL)"),
                     registry._result("npm", "any-ascii", exists=True, latestVersion="0.3.2", license="ISC",
                                      latestReleaseDate="2023-01-01T00:00:00Z")]
            for s in seeds:
                write(registry.cache_path(cache, s["registry"], s["name"]), json.dumps(s))
            dep = {"scope": "runtime", "direct": True, "role": "runtime-library", "confidence": "MEDIUM"}
            deps = {"schema": 1, "source": {"language": "python"}, "target": {"language": "typescript", "registry": "npm"},
                    "dependencies": [dict(dep, name="text-unidecode", decision="PORT"),
                                     dict(dep, name="unidecode", decision="MAP", candidate={"name": "any-ascii"})]}
            write(ws / "deps.json", json.dumps(deps))
            report = registry.verify_deps(ws, offline=True)
            self.assertTrue(any("text-unidecode: PORT copies code licensed" in line for line in report), report)
            self.assertTrue(any("no release in two years" in line for line in report), report)
            out = read_json(ws / "deps.json")
            self.assertFalse(out["dependencies"][0]["sourceLicense"]["compatible"])
            from porterlib.state import Workspace, deps_gate_items
            items = deps_gate_items(Workspace.open(str(ws)), out)
            self.assertTrue(any("copies code licensed" in i for i in items), items)


if __name__ == "__main__":
    unittest.main()
