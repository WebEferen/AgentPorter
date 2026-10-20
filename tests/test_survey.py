import json
import unittest

from util import TempDir, porter, write


class SurveyTest(unittest.TestCase):
    def test_dynamic_setuptools_version(self):
        with TempDir() as tmp:
            src = tmp / "pkg"
            write(src / "pyproject.toml", '[project]\nname = "demo"\ndynamic = ["version"]\n\n'
                  '[tool.setuptools.dynamic]\nversion = {attr = "demo.__version__.__version__"}\n')
            write(src / "demo" / "__init__.py", "def hello():\n    return 'hi'\n")
            write(src / "demo" / "__version__.py", "__title__ = 'demo'\n__version__ = '2.4.1'\n")
            out = porter("survey", str(src), "--json", cwd=tmp).stdout
            self.assertEqual(json.loads(out)["package"]["version"], "2.4.1")


if __name__ == "__main__":
    unittest.main()
