"""Packaging invariants, not a substitute for independent behavioral evaluation."""
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_contract", ROOT / "scripts/build_release.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


class SkillContracts(unittest.TestCase):
    def test_shared_policy_is_present_and_identical(self):
        B.validate_confirmation_gate()
        B.validate_execution_guidance()

    def test_each_skill_has_self_contained_markdown_links(self):
        for name in B.ALL_SKILLS:
            skill = ROOT / "skills" / name
            for source in skill.rglob("*.md"):
                for value in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                    if value.startswith(("https://", "http://", "#", "mailto:")):
                        continue
                    target = (source.parent / value.split("#")[0]).resolve()
                    self.assertTrue(target.is_relative_to(skill.resolve()), f"{source}: external local dependency {value}")
                    self.assertTrue(target.exists(), f"{source}: missing {value}")

    def test_stale_policy_prevents_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sample"
            (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("[policy](references/14-task-execution.md)", encoding="utf-8")
            (root / "references/14-task-execution.md").write_text("outdated", encoding="utf-8")
            with patch.object(B, "ALL_SKILLS", ("sample",)), patch.object(B, "SKILLS_ROOT", root.parent):
                with self.assertRaisesRegex(ValueError, "stale"):
                    B.validate_execution_guidance()

    def test_all_skills_keep_automatic_discovery(self):
        for name in B.ALL_SKILLS:
            B.validate_openai_yaml(ROOT / "skills" / name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
