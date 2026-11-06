import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".agents" / "skills"
LOCAL_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class AgentSkillMetadataTests(unittest.TestCase):
    def test_repository_skills_have_valid_metadata_and_links(self):
        skill_dirs = sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir())
        self.assertTrue(skill_dirs, "No repository skills were found")

        names = set()
        for skill_dir in skill_dirs:
            skill_file = skill_dir / "SKILL.md"
            self.assertTrue(skill_file.is_file(), f"Missing {skill_file.relative_to(ROOT)}")
            source = skill_file.read_text(encoding="utf-8")
            self.assertTrue(source.startswith("---\n"), f"Missing YAML frontmatter: {skill_file}")

            parts = source.split("---", 2)
            self.assertEqual(len(parts), 3, f"Malformed frontmatter: {skill_file}")
            frontmatter, body = parts[1], parts[2]
            name_match = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", frontmatter)
            description_match = re.search(r"(?m)^description:\s*(.+?)\s*$", frontmatter)
            self.assertIsNotNone(name_match, f"Missing or invalid name: {skill_file}")
            self.assertIsNotNone(description_match, f"Missing description: {skill_file}")
            name = name_match.group(1)
            self.assertEqual(name, skill_dir.name, f"Directory/name mismatch: {skill_file}")
            self.assertNotIn(name, names, f"Duplicate skill name: {name}")
            names.add(name)
            self.assertGreater(len(description_match.group(1).strip().strip('"')), 20)
            self.assertTrue(body.strip(), f"Empty skill instructions: {skill_file}")

            for target in LOCAL_LINK_RE.findall(body):
                if target.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                target_path = (skill_file.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(
                    target_path.is_file(),
                    f"Broken local reference in {skill_file.relative_to(ROOT)}: {target}",
                )


if __name__ == "__main__":
    unittest.main()
