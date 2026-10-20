import json
import random
import sys
import unittest

from util import TempDir, porter, read_json, tiny_python_project, write
from porterlib import fixtures, parity


class GeneratorTest(unittest.TestCase):
    def test_generators_are_deterministic(self):
        tpl = {"args": [{"$gen": "string", "alphabet": "unicode", "min": 0, "max": 9}],
               "kwargs": {"n": {"$gen": "int", "min": 0, "max": 5}, "raw": {"$gen": "const", "value": {"$gen": "x"}}},
               "doc": {"$gen": "json", "depth": 2, "text": True}}
        a = fixtures.generate(tpl, random.Random(3))
        b = fixtures.generate(tpl, random.Random(3))
        self.assertEqual(a, b)
        self.assertEqual(a["kwargs"]["raw"], {"$gen": "x"})
        json.loads(a["doc"])

    def test_expand_spec_names_and_duplicates(self):
        spec = {"schema": 1, "unit": "u", "call": "m:f",
                "cases": [{"case": "one", "input": {"args": [1]}}],
                "generate": [{"name": "gen", "seed": 1, "count": 3, "args": [{"$gen": "int"}]}]}
        cases = fixtures.expand_spec(spec)
        self.assertEqual([c["case"] for c in cases], ["one", "gen-0000", "gen-0001", "gen-0002"])
        spec["cases"].append({"case": "gen-0001", "input": {}})
        with self.assertRaises(Exception):
            fixtures.expand_spec(spec)
        spec["cases"][-1] = {"case": "two", "input": {}, "normalize": ["sort-lines"]}
        with self.assertRaisesRegex(Exception, "sort-lines"):
            fixtures.expand_spec(spec)

    def test_write_json_keeps_lone_surrogates_and_refuses_infinity(self):
        from porterlib.common import PorterError, write_json
        with TempDir() as tmp:
            write_json(tmp / "a.json", {"s": "x\ud800"})
            self.assertEqual(read_json(tmp / "a.json")["s"], "x\ud800")
            with self.assertRaisesRegex(PorterError, r"\$float"):
                write_json(tmp / "b.json", {"v": float("inf")})
            self.assertEqual(sorted(x.name for x in tmp.iterdir()), ["a.json"])


class CompareTest(unittest.TestCase):
    def test_numeric_equality_across_int_and_float(self):
        self.assertEqual(parity.compare({"kind": "value", "value": 1}, {"kind": "value", "value": 1.0}, [], {})[0], "pass")
        self.assertEqual(parity.compare({"kind": "value", "value": True}, {"kind": "value", "value": 1}, [], {})[0], "fail")

    def test_datetimes_compare_as_instants(self):
        dt = lambda s: {"$datetime": s}
        self.assertTrue(parity.deep_equal(dt("2024-02-29T10:00Z"), dt("2024-02-29T11:00:00.000+01:00"), None))
        self.assertFalse(parity.deep_equal(dt("2024-02-29T10:00:00"), dt("2024-02-29T10:00:00Z"), None))
        self.assertFalse(parity.deep_equal(dt("2024-02-29T10:00:01Z"), dt("2024-02-29T10:00:00Z"), None))

    def test_float_tolerance_and_unordered(self):
        exp = {"kind": "value", "value": [0.30000000000000004, 2]}
        act = {"kind": "value", "value": [2, 0.3]}
        self.assertEqual(parity.compare(exp, act, [], {})[0], "fail")
        self.assertEqual(parity.compare(exp, act, ["float:1e-9", "unordered"], {})[0], "normalized")

    def test_error_map_and_message_pattern(self):
        exp = {"kind": "error", "category": "ValueError", "message": "bad value 3", "messagePattern": "bad value \\d+"}
        act = {"kind": "error", "category": "RangeError", "message": "bad value 7"}
        self.assertEqual(parity.compare(exp, act, [], {})[0], "fail")
        self.assertEqual(parity.compare(exp, act, [], {"ValueError": "RangeError"})[0], "normalized")

    def test_cli_streams(self):
        exp = {"kind": "cli", "stdout": "a\r\n", "stderr": "warn", "exitCode": 0}
        act = {"kind": "cli", "stdout": "a\n", "stderr": "", "exitCode": 0}
        self.assertEqual(parity.compare(exp, act, ["lf"], {})[0], "fail")
        self.assertEqual(parity.compare(exp, act, ["lf", "ignore-stderr"], {})[0], "normalized")
        self.assertEqual(parity.compare(exp, dict(act, exitCode=1), ["lf", "ignore-stderr"], {})[0], "fail")

    def test_lines_unordered(self):
        exp = {"kind": "cli", "stdout": "b=2\na=1\n", "stderr": "", "exitCode": 0}
        act = {"kind": "cli", "stdout": "a=1\nb=2\n", "stderr": "", "exitCode": 0}
        self.assertEqual(parity.compare(exp, act, [], {})[0], "fail")
        self.assertEqual(parity.compare(exp, act, ["lines-unordered"], {})[0], "normalized")
        self.assertEqual(parity.compare(exp, dict(act, stdout="a=1\nb=2"), ["lines-unordered"], {})[0], "fail")


class CliParityFlowTest(unittest.TestCase):
    def test_record_run_collect_with_divergence(self):
        with TempDir() as tmp:
            orig = write(tmp / "orig.py", "import sys\ndata = sys.stdin.read()\nprint(data.upper(), end='')\n"
                                          "sys.exit(3 if 'FAIL' in data.upper() else 0)\n")
            port = write(tmp / "port.py", "import sys\ndata = sys.stdin.read()\nprint(data.upper().replace('SS', 'ß'), end='')\n"
                                          "sys.exit(3 if 'FAIL' in data.upper() else 0)\n")
            write(tmp / "src" / "x.txt", "x")
            porter("init", "--source", str(tmp / "src"), "--to", "python", cwd=tmp)
            write(tmp / ".porter" / "oracle" / "cases" / "upper.json", json.dumps({
                "schema": 1, "unit": "upper", "call": "upper", "kind": "cli",
                "cases": [{"case": "plain", "input": {"stdin": "abc"}},
                          {"case": "fail-exit", "input": {"stdin": "fail"}},
                          {"case": "sharp-s", "input": {"stdin": "strasse"}}],
                "generate": [{"name": "rand", "seed": 5, "count": 4,
                              "input": {"stdin": {"$gen": "string", "alphabet": "lower", "min": 1, "max": 5}}}]}))
            porter("fixtures", "expand", cwd=tmp)
            porter("cli", "record", "--unit", "upper", "--exe", f"{sys.executable} {orig}", cwd=tmp)
            self.assertEqual(porter("fixtures", "validate", cwd=tmp).returncode, 0)
            porter("cli", "run", "--unit", "upper", "--exe", f"{sys.executable} {orig}", "--run", "same", cwd=tmp)
            porter("parity", "collect", "--run", "same", cwd=tmp)
            self.assertEqual(read_json(tmp / ".porter" / "parity.json")["units"][0]["level"], "EXACT")
            porter("cli", "run", "--unit", "upper", "--exe", f"{sys.executable} {port}", "--run", "port", cwd=tmp)
            gap = porter("parity", "collect", "--run", "port", cwd=tmp, check=False)
            self.assertEqual(gap.returncode, 1)
            self.assertIn("sharp-s", gap.stdout)
            write(tmp / ".porter" / "divergences.json", json.dumps({"schema": 1, "divergences": [
                {"id": "sharp-s", "unit": "upper", "summary": "keeps the German sharp s", "rationale": "test",
                 "cases": ["sharp-s"]}]}))
            write(tmp / "impl.py", "# DIVERGENCE(sharp-s): keep the sharp s\n")
            porter("parity", "collect", "--run", "port", cwd=tmp)
            data = read_json(tmp / ".porter" / "parity.json")
            self.assertEqual(data["units"][0]["level"], "DIVERGENT")
            self.assertEqual(data["markerErrors"], [])
            report = porter("parity", "report", cwd=tmp).stdout
            self.assertIn("sharp-s", report)


class RefTestsTest(unittest.TestCase):
    def test_harvested_cases_decide_the_owner_before_the_file_name(self):
        with TempDir() as tmp:
            porter("init", "--source", str(tiny_python_project(tmp / "src")), "--to", "go", cwd=tmp)
            ws = tmp / ".porter"
            write(ws / "plan.json", json.dumps({"schema": 1, "units": [
                {"id": "a", "layer": "core", "wave": 0, "symbols": [], "dependsOn": [], "referenceTests": []},
                {"id": "b", "layer": "core", "wave": 0, "symbols": [], "dependsOn": [], "referenceTests": ["tests/test_x.py"]}]}))
            write(ws / "oracle" / "cases" / "a.json", json.dumps({"schema": 1, "unit": "a", "cases": [
                {"case": "one", "origin": "reference-test:tests/test_x.py::test_one", "call": "m:f", "input": {}}]}))
            write(tmp / "report.xml", '<testsuite><testcase classname="x" name="one [ref: tests/test_x.py::test_one]"/>'
                                      '<testcase classname="x" name="two [ref: tests/test_x.py::test_two]"/></testsuite>')
            porter("parity", "reftests", "junit", str(tmp / "report.xml"), cwd=tmp)
            units = read_json(ws / "reftests.json")["units"]
            self.assertEqual([e["ref"] for e in units["a"]], ["tests/test_x.py::test_one"])
            self.assertEqual([e["ref"] for e in units["b"]], ["tests/test_x.py::test_two"])
            write(tmp / "report2.xml", '<testsuite><testcase classname="x" name="two [ref: tests/test_x.py::test_two]"/></testsuite>')
            porter("parity", "reftests", "junit", str(tmp / "report2.xml"), "--replace", cwd=tmp)
            units = read_json(ws / "reftests.json")["units"]
            self.assertEqual((units["a"][0]["resolution"], units["b"][0]["resolution"]), ("UNRESOLVED", "PASS"))

    def test_gotest_reads_tags_from_log_output(self):
        with TempDir() as tmp:
            lines = [{"Action": "output", "Package": "p", "Test": "TestMs/short", "Output": "    ms_test.go:9: [ref: tests.js::ms(string) should work]\n"},
                     {"Action": "pass", "Package": "p", "Test": "TestMs/short"},
                     {"Action": "fail", "Package": "p", "Test": "TestMs/plain"}]
            report = write(tmp / "go.json", "\n".join(json.dumps(x) for x in lines))
            self.assertEqual(parity.parse_gotest(report), [("p TestMs/short [ref: tests.js::ms(string) should work]", "passed"),
                                                           ("p TestMs/plain", "failed")])


if __name__ == "__main__":
    unittest.main()
