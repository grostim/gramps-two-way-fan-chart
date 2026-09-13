import ast
import unittest
from pathlib import Path

from TwoWayFanChart.config import (
    ChartConfig,
    Orientation,
    OutputFormat,
    PaperSize,
    PresetName,
    PrivacyMode,
    build_preset,
)
from TwoWayFanChart.model import VisibilityState
from TwoWayFanChart.privacy import PersonPrivacyFacts, classify_visibility


class DefaultConfigurationTests(unittest.TestCase):
    def test_registration_and_builder_versions_are_aligned(self):
        registration = Path("TwoWayFanChart/TwoWayFanChart.gpr.py").read_text(
            encoding="utf-8"
        )
        builder = Path("build_addon.py").read_text(encoding="utf-8")

        self.assertIn('version="1.2.37"', registration)
        self.assertIn('VERSION = "1.2.37"', builder)

    def test_chart_defaults_match_requested_fan_chart(self):
        config = ChartConfig()

        self.assertEqual(config.center_family, "F0055")
        self.assertEqual(config.output_format, OutputFormat.SVG)
        self.assertEqual(config.paper_size, PaperSize.A0)
        self.assertEqual(config.ancestor_generations, 5)
        self.assertEqual(config.descendant_generations, 4)
        self.assertEqual(config.orientation, Orientation.LANDSCAPE)
        self.assertEqual(config.privacy_mode, PrivacyMode.INCLUDE_ALL)
        self.assertTrue(config.include_private)
        self.assertEqual(config.living_people_mode, 99)
        self.assertFalse(config.show_highlight_markers)

    def test_publication_preset_uses_the_same_requested_defaults(self):
        config = build_preset(PresetName.PUBLICATION)

        self.assertEqual(config, ChartConfig(preset=PresetName.PUBLICATION))

    def test_default_privacy_settings_keep_private_living_person_visible(self):
        config = ChartConfig()

        state = classify_visibility(
            PersonPrivacyFacts(is_private=True, is_living=True),
            privacy_mode=config.privacy_mode,
            include_private=config.include_private,
            living_people_mode=config.living_people_mode,
        )

        self.assertEqual(state, VisibilityState.VISIBLE)

    def test_gramps_menu_definitions_use_the_requested_defaults(self):
        source = Path("TwoWayFanChart/options.py").read_text(encoding="utf-8")
        ast.parse(source)

        for expected in (
            'NumberOption(_("Ancestor generations"), 5, 0, 8)',
            'NumberOption(_("Descendant generations"), 4, 0, 5)',
            'default_center = ChartConfig().center_family',
            '"Orientation",\n                "landscape"',
            '_enum("Output format", "svg"',
            '"Paper size",\n                "A0"',
            '"Privacy mode",\n                "include_all"',
            'add_private_data_option(menu, _(CATEGORY_PRIVACY), default=True)',
            'mode=LivingProxyDb.MODE_INCLUDE_ALL',
            'BooleanOption(_("Show citation markers"), False)',
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
