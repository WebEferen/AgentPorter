import struct
import unittest
import zipfile

from util import TempDir, write
from porterlib import recover


class DetectTest(unittest.TestCase):
    def _bin(self, tmp, name, data):
        path = tmp / name
        path.write_bytes(data)
        path.chmod(0o755)
        return path

    def test_elf_go_binary(self):
        with TempDir() as tmp:
            head = b"\x7fELF\x02\x01\x01" + b"\0" * 9 + struct.pack("<HH", 2, 0xB7)
            path = self._bin(tmp, "tool", head + b"\0" * 64 + b"\xff Go buildinf:" + b"\0" * 32)
            art = recover.detect(path)
            self.assertEqual((art["format"], art["arch"], art["language"], art["kind"]), ("elf", "arm64", "go", "cli"))
            self.assertTrue(any(step["command"][0] == "inspect-go-binary" for step in art["reaPlan"]))

    def test_macho_rust_library(self):
        with TempDir() as tmp:
            head = b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C)
            art = recover.detect(self._bin(tmp, "libx.dylib", head + b"\0" * 64 + b"/rustc/abc/library"))
            self.assertEqual((art["format"], art["language"], art["kind"]), ("macho", "rust", "library"))
            self.assertFalse(art["runnable"])

    def test_dotnet_pe(self):
        with TempDir() as tmp:
            pe = bytearray(512)
            pe[0:2] = b"MZ"
            struct.pack_into("<I", pe, 0x3C, 0x80)
            pe[0x80:0x84] = b"PE\0\0"
            struct.pack_into("<H", pe, 0x84, 0x8664)
            opt = 0x80 + 24
            struct.pack_into("<H", pe, opt, 0x20B)
            struct.pack_into("<II", pe, opt + 112 + 14 * 8, 0x2000, 0x48)
            art = recover.detect(self._bin(tmp, "App.dll", bytes(pe)))
            self.assertEqual((art["platform"], art["language"], art["kind"]), ("dotnet", "csharp", "library"))
            self.assertIn("inspect-managed-members", [s["command"][0] for s in art["reaPlan"]])

    def test_jar_with_main_class(self):
        with TempDir() as tmp:
            path = tmp / "app.jar"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: a.Main\n")
                zf.writestr("a/Main.class", b"\xca\xfe\xba\xbe")
                zf.writestr("kotlin/Unit.class", b"\xca\xfe\xba\xbe")
            art = recover.detect(path)
            self.assertEqual((art["format"], art["platform"], art["language"], art["kind"]), ("jar", "jvm", "kotlin", "cli"))

    def test_shebang_script(self):
        with TempDir() as tmp:
            art = recover.detect(self._bin(tmp, "run", b"#!/usr/bin/env python3\nprint(1)\n"))
            self.assertEqual((art["format"], art["language"], art["kind"]), ("script", "python", "cli"))


class HelpParseTest(unittest.TestCase):
    def test_gnu_style_with_single_space_and_exit_codes(self):
        text = """Transform things

Usage:
  tool [OPTIONS] [FILE|URL|-]

Options:
  -u, --ungron     Reverse the operation
  -m, --monochrome Monochrome output
  -o, --output FILE  Write to FILE
      --no-sort    Do not sort

Exit Codes:
  0\tOK
  2\tFailed to read input
"""
        parsed = recover.parse_help(text)
        longs = [f["long"] for f in parsed["flags"]]
        self.assertEqual(longs, ["--ungron", "--monochrome", "--output", "--no-sort"])
        self.assertEqual(parsed["flags"][2]["arg"], "FILE")
        self.assertEqual(parsed["flags"][1]["description"], "Monochrome output")
        self.assertEqual([e["code"] for e in parsed["exitCodes"]], [0, 2])
        self.assertEqual(parsed["arguments"], ["FILE|URL|-"])

    def test_go_flag_package_style(self):
        text = "Usage of tool:\n  -depth int\n    \tmaximum depth (default 3)\n  -v\tverbose\n"
        parsed = recover.parse_help(text)
        self.assertEqual(parsed["flags"][0]["long"], "-depth")
        self.assertEqual(parsed["flags"][0]["arg"], "int")
        self.assertEqual(parsed["flags"][0]["description"], "maximum depth (default 3)")

    def test_parse_rea_output_skips_progress_lines(self):
        out = '{"rea_progress":{"phase":"running"}}\n{"operation":"x","ok":true}\n'
        self.assertEqual(recover.parse_rea_output(out), {"operation": "x", "ok": True})


class RecoveryImportTest(unittest.TestCase):
    def test_import_merges_go_buildinfo_and_probe_and_keeps_edits(self):
        from util import porter, read_json
        with TempDir() as tmp:
            exe = write(tmp / "tool", "#!/bin/sh\nif [ \"$1\" = --help ]; then echo 'Tool does things'; echo; "
                                      "echo 'Options:'; echo '  -x, --extra   Extra mode'; exit 0; fi\n"
                                      "if [ \"$1\" = --version ]; then echo 'tool version 2.0.1'; exit 0; fi\necho ok\n")
            exe.chmod(0o755)
            porter("init", "--source", str(exe), "--authorization", "test fixture", cwd=tmp)
            porter("recover", "detect", "--write", cwd=tmp)
            porter("recover", "probe", cwd=tmp)
            rea = {"operation": "inspect_go_binary", "normalized_result": {"build_info": {"go_version": "go1.22", "module": {
                "main": {"path": "example.com/tool", "version": "v2.0.1"},
                "dependencies": [{"path": "github.com/a/b", "version": "v1.0.0", "replacement": None}]}}}}
            write(tmp / "rea.json", __import__("json").dumps(rea))
            porter("recover", "register", "go", "--file", str(tmp / "rea.json"), "--command", "inspect-go-binary", cwd=tmp)
            porter("recover", "import", cwd=tmp)
            rec_path = tmp / ".porter" / "recover" / "recovery.json"
            rec = read_json(rec_path)
            ids = [i["id"] for i in rec["interface"]]
            self.assertIn("flag:extra", ids)
            self.assertEqual(rec["origin"]["package"], "example.com/tool")
            self.assertEqual([m["name"] for m in rec["modules"]], ["example.com/tool", "github.com/a/b"])
            rec["interface"][0]["description"] = "edited by a person"
            rec_path.write_text(__import__("json").dumps(rec))
            porter("recover", "import", cwd=tmp)
            self.assertEqual(read_json(rec_path)["interface"][0]["description"], "edited by a person")
            porter("state", "source", "--license", "GPL-3.0-only", "--note", "the owner says GPL 3", cwd=tmp)
            survey = porter("survey", "--write", cwd=tmp)
            self.assertIn("Public symbols", survey.stdout)
            self.assertIn("GPL-3.0-only (copyleft: strong)", survey.stdout)
            self.assertEqual(read_json(tmp / ".porter" / "config.json")["source"]["license"]["spdx"], "GPL-3.0-only")
            self.assertIn("the owner says GPL 3", (tmp / ".porter" / "decisions.md").read_text())
            graph = porter("deps-graph", "--write", "--json", cwd=tmp).stdout
            self.assertIn("github.com/a/b", graph)


if __name__ == "__main__":
    unittest.main()
