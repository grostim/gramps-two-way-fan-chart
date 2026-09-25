import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
OPTIONS_PATH = ROOT / "TwoWayFanChart" / "options.py"
DOCS = {
    "en": ROOT / "TwoWayFanChart" / "OPTIONS.md",
    "fr": ROOT / "TwoWayFanChart" / "OPTIONS.fr.md",
}

STANDARD_OPTION_KEYS = {"incl_private", "living_people", "years_past_death"}


def _menu_keys() -> set[str]:
    """Extract every stable menu key registered through ``add_option``."""
    tree = ast.parse(OPTIONS_PATH.read_text(encoding="utf-8"))
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_name_format_option"
        ):
            keys.add("name_format")
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_option":
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            if isinstance(node.args[1].value, str):
                keys.add(node.args[1].value)
    return keys


def _doc_sections(path: Path) -> set[str]:
    """Extract the ``### <key>`` option sections of one documentation file."""
    sections = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("### "):
            sections.add(line[4:].strip())
    return sections


class OptionsDocumentationTests(unittest.TestCase):
    def test_every_option_has_a_section_in_both_languages(self):
        expected = _menu_keys() | STANDARD_OPTION_KEYS
        for lang, path in DOCS.items():
            missing = sorted(expected - _doc_sections(path))
            self.assertEqual(
                missing,
                [],
                f"{lang}: menu options undocumented in {path.name}: {missing}",
            )

    def test_doc_sections_correspond_to_existing_options(self):
        expected = _menu_keys() | STANDARD_OPTION_KEYS
        for lang, path in DOCS.items():
            stale = sorted(_doc_sections(path) - expected)
            self.assertEqual(
                stale,
                [],
                f"{lang}: stale sections in {path.name} (option removed?): {stale}",
            )

    def test_french_and_english_sections_are_aligned(self):
        en = _doc_sections(DOCS["en"])
        fr = _doc_sections(DOCS["fr"])
        self.assertEqual(en, fr, "English and French docs drifted apart")


if __name__ == "__main__":
    unittest.main()
