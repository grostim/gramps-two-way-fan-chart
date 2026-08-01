import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
OPTIONS_PATH = ROOT / "TwoWayFanChart" / "options.py"
CONFIG_PATH = ROOT / "TwoWayFanChart" / "config.py"

ACTIVE_CONFIG_FIELDS = {
    "center_family",
    "preset",
    "ancestor_generations",
    "descendant_generations",
    "paper_size",
    "orientation",
    "margin_mm",
    "custom_width_mm",
    "custom_height_mm",
    "output_format",
    "privacy_mode",
    "background_color",
    "parent_family_policy",
    "descendant_family_policy",
    "show_portraits",
    "portrait_source",
    "respect_media_crop",
    "portrait_treatment",
    "include_private",
    "living_people_mode",
    "years_past_death",
}

ACTIVE_MENU_KEYS = {
    "preset",
    "center_family",
    "ancestor_generations",
    "descendant_generations",
    "parent_family_policy",
    "descendant_family_policy",
    "show_portraits",
    "portrait_source",
    "respect_media_crop",
    "portrait_treatment",
    "paper_size",
    "orientation",
    "margin_mm",
    "custom_width_mm",
    "custom_height_mm",
    "background_color",
    "privacy_mode",
    "output_format",
}


class OptionContractTests(unittest.TestCase):
    @staticmethod
    def _chart_config_fields() -> set[str]:
        tree = ast.parse(CONFIG_PATH.read_text(encoding="utf-8"))
        chart_config = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ChartConfig"
        )
        fields = set()
        for node in chart_config.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                fields.add(node.target.id)
        return fields

    @staticmethod
    def _menu_keys() -> set[str]:
        tree = ast.parse(OPTIONS_PATH.read_text(encoding="utf-8"))
        keys = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_option":
                continue
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                if isinstance(node.args[1].value, str):
                    keys.add(node.args[1].value)
        return keys

    def test_chart_config_contains_only_production_fields(self):
        self.assertEqual(self._chart_config_fields(), ACTIVE_CONFIG_FIELDS)

    def test_menu_contains_only_production_options(self):
        self.assertEqual(self._menu_keys(), ACTIVE_MENU_KEYS)

    def test_standard_privacy_options_remain_and_unused_standard_options_are_gone(self):
        source = OPTIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("add_private_data_option", source)
        self.assertIn("add_living_people_option", source)
        self.assertNotIn("add_name_format_option", source)
        self.assertNotIn("add_localization_option", source)


if __name__ == "__main__":
    unittest.main()
