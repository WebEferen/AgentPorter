import json
import unittest

from util import TempDir, porter, write


class DepsGraphTest(unittest.TestCase):
    def test_requirements_file_name_variants(self):
        with TempDir() as tmp:
            src = tmp / "pkg"
            write(src / "requirements.txt", "requests>=2\n")
            write(src / "dev.requirements.txt", "pytest\n")
            write(src / "requirements-lint.txt", "ruff\n")
            out = json.loads(porter("deps-graph", str(src), "--json", cwd=tmp).stdout)
            scopes = {d["name"]: d["scope"] for d in out["dependencies"]}
            self.assertEqual(scopes, {"requests": "runtime", "pytest": "dev", "ruff": "dev"})


class UsageScanTest(unittest.TestCase):
    def test_computed_imports_are_reported(self):
        from porterlib.usage import scan
        with TempDir() as tmp:
            write(tmp / "pkg" / "a.py", "import importlib\nimport text_unidecode\n"
                                        "mod = importlib.import_module(name.replace('-', '_'))\n")
            result = scan(tmp, [{"name": "anyascii", "ecosystem": "pypi"}, {"name": "text-unidecode", "ecosystem": "pypi"}], {})
            self.assertEqual(result["usage"]["anyascii"]["usedIn"], "unused")
            self.assertEqual(result["usage"]["text-unidecode"]["usedIn"], "source")
            self.assertEqual(result["dynamicImports"], ["pkg/a.py:3"])


if __name__ == "__main__":
    unittest.main()
