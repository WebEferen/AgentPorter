"""Oracle drivers against tiny sources. Skipped when the driver's runtime is missing."""
import json
import shutil
import subprocess
import unittest

from util import ROOT, TempDir, porter, read_json, write

JS_ORACLE = ROOT / "knowledge" / "oracles" / "javascript" / "oracle.mjs"


def node_strips_types() -> bool:
    if not shutil.which("node"):
        return False
    probe = subprocess.run(["node", "-p", "Boolean(process.features.typescript)"], capture_output=True, text=True)
    return probe.stdout.strip() == "true"


@unittest.skipUnless(node_strips_types(), "needs Node with TypeScript type stripping (22.18 or newer)")
class JavaScriptOracleTest(unittest.TestCase):
    def test_unbuilt_typescript_with_extensionless_and_js_suffixed_imports(self):
        with TempDir() as tmp:
            write(tmp / "src" / "package.json", '{"name": "tslib", "version": "1.0.0"}\n')
            write(tmp / "src" / "src" / "types.ts", 'export const SEP: string = "-";\nexport type Pair = [string, string];\n')
            write(tmp / "src" / "src" / "index.ts",
                  'export * from "./types";\nimport { SEP } from "./types.js";\n'
                  'export function joinUp(a: string, b: string): string { return a.toUpperCase() + SEP + b; }\n')
            porter("init", "--source", str(tmp / "src"), "--to", "go", cwd=tmp)
            write(tmp / ".porter" / "oracle" / "cases" / "core.json", json.dumps({"schema": 1, "unit": "core", "cases": [
                {"case": "j", "call": "./src/index.ts:joinUp", "input": {"args": ["ab", "c"]}},
                {"case": "sep", "call": "./src/index.ts:SEP", "input": {}}]}))
            porter("fixtures", "expand", cwd=tmp)
            proc = subprocess.run(["node", str(JS_ORACLE), "--workspace", ".porter"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = read_json(tmp / ".porter" / "fixtures" / "core" / "oracle.json")
            self.assertEqual(data["oracle"]["language"], "typescript")
            self.assertEqual([c["expect"]["value"] for c in data["cases"]], ["AB-c", "-"])

    def test_a_module_that_does_not_load_is_not_recorded(self):
        with TempDir() as tmp:
            write(tmp / "src" / "package.json", '{"name": "x", "version": "1.0.0"}\n')
            porter("init", "--source", str(tmp / "src"), "--to", "go", cwd=tmp)
            write(tmp / ".porter" / "oracle" / "cases" / "core.json", json.dumps({"schema": 1, "unit": "core", "cases": [
                {"case": "a", "call": "./lib/missing.js:f", "input": {"args": []}}]}))
            porter("fixtures", "expand", cwd=tmp)
            proc = subprocess.run(["node", str(JS_ORACLE), "--workspace", ".porter"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("cannot load", proc.stderr)
            self.assertFalse((tmp / ".porter" / "fixtures" / "core" / "oracle.json").exists())


if __name__ == "__main__":
    unittest.main()
