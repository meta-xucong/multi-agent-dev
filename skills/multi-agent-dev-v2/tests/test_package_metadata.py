from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_skill_frontmatter_is_minimal_and_valid(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        _, frontmatter, _ = content.split("---", 2)
        parsed: dict[str, str] = {}
        for line in frontmatter.strip().splitlines():
            key, separator, value = line.partition(":")
            self.assertTrue(separator)
            self.assertIn(key, {"name", "description"})
            scalar = value.strip()
            parsed[key] = json.loads(scalar) if scalar.startswith('"') else scalar
        self.assertEqual(set(parsed), {"name", "description"})
        self.assertRegex(parsed["name"], r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(parsed["name"]), 64)
        self.assertTrue(parsed["description"].strip())
        self.assertLessEqual(len(parsed["description"]), 1024)
        self.assertNotRegex(parsed["description"], r"[<>]")

    def test_openai_yaml_is_a_valid_quoted_metadata_subset(self) -> None:
        lines = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "interface:")
        values: dict[str, str] = {}
        for line in lines[1:]:
            match = re.fullmatch(r'  (display_name|short_description): (".*")', line)
            self.assertIsNotNone(match, line)
            assert match is not None
            values[match.group(1)] = json.loads(match.group(2))
        self.assertEqual(set(values), {"display_name", "short_description"})
        self.assertTrue(all(value.strip() for value in values.values()))

    def test_hook_example_matches_the_expected_events_envelope(self) -> None:
        example = json.loads((ROOT / "hooks" / "hooks.json.example").read_text(encoding="utf-8"))
        hooks = example["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse", "Stop", "Interrupt", "SessionEnd"})
        for event, entries in hooks.items():
            self.assertIsInstance(entries, list)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(set(entry) - {"matcher"}, {"hooks"})
            if event == "PreToolUse":
                self.assertEqual(entry["matcher"], "^Bash$")
            self.assertEqual(len(entry["hooks"]), 1)
            command = entry["hooks"][0]
            self.assertEqual(command["type"], "command")
            self.assertIn("task_terminal_notify.py", command["command"])
            self.assertIn("task_terminal_notify.py", command["commandWindows"])
            self.assertEqual(command["timeout"], 50 if event == "Stop" else 3)

    def test_skill_local_reference_links_exist(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", content):
            self.assertTrue((ROOT / target).resolve().is_file(), target)

    def test_text_files_have_no_trailing_whitespace(self) -> None:
        text_extensions = {".md", ".py", ".toml", ".yaml"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in text_extensions:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    self.assertEqual(line, line.rstrip(), f"{path}:{line_number}")


if __name__ == "__main__":
    unittest.main()
