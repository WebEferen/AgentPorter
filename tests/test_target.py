import unittest

import util  # noqa: F401
from porterlib import target


class TargetScoreTest(unittest.TestCase):
    def test_semantic_distance(self):
        self.assertEqual(target.semantic_distance("python", "python"), 0)
        self.assertLess(target.semantic_distance("javascript", "typescript"), target.semantic_distance("python", "rust"))
        self.assertIsNone(target.semantic_distance("cobol", "go"))

    def test_runtime_fit_and_user_inputs(self):
        cli_go = target.score_candidate("python", "go", "cli", [], set(), {})
        cli_py = target.score_candidate("ruby", "python", "cli", [], set(), {})
        self.assertGreater(cli_go["scores"]["runtime"], cli_py["scores"]["runtime"])
        self.assertIsNone(cli_go["scores"]["ecosystem"])
        jvm = target.score_candidate("java", "kotlin", "library", [], set(), {"consumers": ["java"], "team": ["kotlin"]})
        self.assertEqual(jvm["scores"]["ecosystem"], 4.0)
        self.assertEqual(jvm["scores"]["team"], 5.0)

    def test_same_language_is_a_blocker_and_same_registry_covers_deps(self):
        deps = [{"name": "left-pad", "direct": True, "scope": "runtime"}]
        c = target.score_candidate("javascript", "typescript", "library", deps, set(), {})
        self.assertEqual(c["scores"]["dependencies"], 5.0)
        self.assertEqual(target.score_candidate("go", "go", "cli", [], set(), {})["blockers"][0][:13], "same language")

    def test_total_ignores_unscored(self):
        c = {"scores": {"ecosystem": None, "dependencies": 4, "team": None, "semantics": 2, "runtime": 3, "support": 1}}
        self.assertAlmostEqual(target.total(c, target.DEFAULT_WEIGHTS), round((12 + 4 + 6 + 1) / 8, 2))


if __name__ == "__main__":
    unittest.main()
