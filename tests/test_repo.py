"""Repository hygiene: manifests agree, frontmatter parses, schemas load, no long dashes anywhere."""
import json
import re
import unittest

from util import ROOT
from porterlib import jsonschema

TEXT_EXT = {".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt", ".ts", ".mjs", ".js", ".go", ".rs", ".kt",
            ".java", ".php", ".svg", ".html", ".sh", ""}
SKIP = {".git", "node_modules", "__pycache__", "results", "target", "build", ".venv"}


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep or line.startswith((" ", "\t")):
            raise ValueError(f"{path}: unparsable frontmatter line {line!r}")
        out[key.strip()] = value.strip()
    return out


class ManifestTest(unittest.TestCase):
    def test_names_and_versions_agree(self):
        claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
        codex_market = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
        from porterlib import __version__
        self.assertEqual(claude["name"], "agentporter")
        self.assertEqual(market["plugins"][0]["name"], claude["name"])
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex_market["plugins"][0]["name"], claude["name"])
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual(claude["version"], __version__)
        for key in ("composerIcon", "logo"):
            self.assertTrue((ROOT / codex["interface"][key]).exists(), codex["interface"][key])

    def test_skills_and_agents_frontmatter(self):
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual({p.parent.name for p in skills},
                         {"port", "recover", "survey", "target", "deps", "contract", "strategy", "implement", "verify", "status"})
        for p in skills:
            fm = frontmatter(p)
            self.assertEqual(fm["name"], p.parent.name)
            self.assertTrue(50 < len(fm["description"]) <= 1536, p)
        for p in sorted((ROOT / "agents").glob("*.md")):
            fm = frontmatter(p)
            self.assertEqual(fm["name"], p.stem)
            self.assertNotIn(":", fm["name"])
            self.assertTrue(fm["description"])

    def test_skill_bodies_reference_existing_plugin_files(self):
        for p in sorted((ROOT / "skills").glob("*/SKILL.md")) + sorted((ROOT / "agents").glob("*.md")):
            for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+[\w/])", p.read_text()):
                if "<" in rel:
                    continue
                self.assertTrue((ROOT / rel).exists(), f"{p.relative_to(ROOT)} references missing {rel}")


class SchemaTest(unittest.TestCase):
    def test_every_schema_loads_and_refs_resolve(self):
        for p in sorted((ROOT / "knowledge" / "schemas").glob("*.schema.json")):
            schema = json.loads(p.read_text())
            self.assertIn("$schema", schema, p.name)
            name = p.name.removesuffix(".schema.json")
            jsonschema.validate_named({}, name)


class StyleTest(unittest.TestCase):
    def test_no_em_or_en_dashes(self):
        bad = []
        for path in ROOT.rglob("*"):
            if any(part in SKIP for part in path.parts) or not path.is_file() or path.suffix not in TEXT_EXT:
                continue
            if path.name == "PLAN.md":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if chr(0x2014) in line or chr(0x2013) in line:
                    bad.append(f"{path.relative_to(ROOT)}:{i}")
        self.assertEqual(bad, [], "long dashes found")


if __name__ == "__main__":
    unittest.main()
