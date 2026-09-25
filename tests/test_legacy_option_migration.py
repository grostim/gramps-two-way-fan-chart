import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gramps.gen.plug.docgen import PAPER_LANDSCAPE, PAPER_PORTRAIT
from gramps.gen.plug.report import _options as gramps_report_options

from TwoWayFanChart.config import Orientation, PresetName, PrivacyMode, PaperSize
from TwoWayFanChart.options import (
    TwoWayFanChartOptions,
    _normalize_legacy_value,
)
from TwoWayFanChart.pipeline import _build_paper_region


class _FakeFamily:
    def get_gramps_id(self) -> str:
        return "F0055"


class _FakeDatabase:
    db_name = "fake-tree"

    def get_family_from_gramps_id(self, gramps_id: str):
        return _FakeFamily() if gramps_id == "F0055" else None

    def get_family_from_handle(self, handle):
        return None


class _NativePaper:
    def __init__(self, name, height_cm, width_cm):
        self._name = name
        self._height_cm = height_cm
        self._width_cm = width_cm

    def get_name(self):
        return self._name

    def get_height(self):
        return self._height_cm

    def get_width(self):
        return self._width_cm


class LegacyOptionMigrationTests(unittest.TestCase):
    """Persisted settings from releases before the option cleanup (≤ 1.2.56)
    must map forward to their closest supported equivalents instead of
    blocking generation or silently weakening privacy protection."""

    def test_legacy_value_aliases(self):
        self.assertEqual(_normalize_legacy_value("preset", "family"), "publication")
        self.assertEqual(
            _normalize_legacy_value("privacy_mode", "surname_only"), "full_name_only"
        )

    def test_unknown_and_supported_values_pass_through(self):
        self.assertEqual(_normalize_legacy_value("preset", "compact"), "compact")
        self.assertEqual(
            _normalize_legacy_value("privacy_mode", "include_all"), "include_all"
        )
        self.assertEqual(_normalize_legacy_value("other_key", "family"), "family")
        self.assertEqual(_normalize_legacy_value("preset", "family"), "publication")

    def test_legacy_persisted_values_migrate_on_load_and_build(self):
        options = TwoWayFanChartOptions("legacy-test", _FakeDatabase())
        # Simulate a preferences file written by release 1.2.55 (before the
        # cleanup): the Gramps handler pushes those values into the menu,
        # where the removed enum members are rejected and the widgets keep
        # their defaults. The load-time normalization must win.
        for key in ("preset", "privacy_mode"):
            options.options_dict[key] = {
                "preset": "family",
                "privacy_mode": "surname_only",
            }[key]
        options.load_previous_values()

        config = options.build_chart_config()
        self.assertEqual(config.preset, PresetName.PUBLICATION)
        self.assertEqual(config.privacy_mode, PrivacyMode.FULL_NAME_ONLY)
        # The normalized values are also persisted back for the next run.
        self.assertEqual(options.options_dict["privacy_mode"], "full_name_only")

    def test_without_normalization_privacy_weakens(self):
        # Guard: prove the regression the migration prevents. A stale
        # "surname_only" that the menu rejects leaves the widget on
        # "include_all" — full identity of private people again.
        options = TwoWayFanChartOptions("legacy-test", _FakeDatabase())
        options.options_dict["privacy_mode"] = "surname_only"
        menu_option = options.menu.get_option_by_name("privacy_mode")
        menu_option.set_value("surname_only")  # rejected: kept default

        self.assertEqual(menu_option.get_value(), "include_all")

    def test_new_report_page_setup_defaults_to_a0_landscape(self):
        with tempfile.TemporaryDirectory() as directory:
            report_options_path = Path(directory) / "report-options.xml"
            with patch.object(
                gramps_report_options, "REPORT_OPTIONS", str(report_options_path)
            ):
                options = TwoWayFanChartOptions("new-page-default-test", _FakeDatabase())
                options.load_previous_values()
                handler = options.handler
                assert handler is not None

                self.assertEqual(handler.get_paper_name(), "A0")
                self.assertEqual(handler.get_orientation(), PAPER_LANDSCAPE)
                config = options.build_chart_config()
                self.assertEqual(config.paper_size, PaperSize.A0)
                self.assertEqual(config.orientation, Orientation.LANDSCAPE)

    def test_saved_report_page_setup_is_not_overridden_by_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            report_options_path = Path(directory) / "report-options.xml"
            with patch.object(
                gramps_report_options, "REPORT_OPTIONS", str(report_options_path)
            ):
                options = TwoWayFanChartOptions("saved-page-test", _FakeDatabase())
                options.load_previous_values()
                handler = options.handler
                assert handler is not None
                handler.set_paper_name("A4")
                handler.set_orientation(PAPER_PORTRAIT)
                handler.save_options()

                reloaded = TwoWayFanChartOptions("saved-page-test", _FakeDatabase())
                reloaded.load_previous_values()
                reloaded_handler = reloaded.handler
                assert reloaded_handler is not None

                self.assertEqual(reloaded_handler.get_paper_name(), "A4")
                self.assertEqual(reloaded_handler.get_orientation(), PAPER_PORTRAIT)
                config = reloaded.build_chart_config()
                self.assertEqual(config.paper_size, PaperSize.A4)
                self.assertEqual(config.orientation, Orientation.PORTRAIT)

    def test_chart_page_uses_gramps_standard_paper_and_orientation(self):
        options = TwoWayFanChartOptions("native-page-test", _FakeDatabase())
        options.options_dict["paper_size"] = "A0"
        options.options_dict["orientation"] = "landscape"
        options.load_previous_values()
        handler = options.handler
        assert handler is not None
        handler.set_paper(_NativePaper("A4", 29.7, 21.0))
        handler.options_dict.update({"papers": "A4", "papero": 0})

        config = options.build_chart_config()
        page = _build_paper_region(config)

        self.assertEqual(config.paper_size, PaperSize.A4)
        self.assertEqual(config.orientation, Orientation.PORTRAIT)
        self.assertEqual((page.width_mm, page.height_mm), (210, 297))

    def test_chart_page_preserves_native_paper_sizes_not_in_addon_enum(self):
        options = TwoWayFanChartOptions("native-page-test", _FakeDatabase())
        options.load_previous_values()
        handler = options.handler
        assert handler is not None
        handler.set_paper(_NativePaper("B0", 141.4, 100.0))
        handler.options_dict.update({"papers": "B0", "papero": 1})

        config = options.build_chart_config()
        page = _build_paper_region(config)

        self.assertEqual(config.paper_size, PaperSize.CUSTOM)
        self.assertEqual(config.custom_width_mm, 1414.0)
        self.assertEqual(config.custom_height_mm, 1000.0)
        self.assertEqual((page.width_mm, page.height_mm), (1414.0, 1000.0))

    def test_chart_page_uses_native_custom_paper_dimensions(self):
        options = TwoWayFanChartOptions("native-page-test", _FakeDatabase())
        options.load_previous_values()
        handler = options.handler
        assert handler is not None
        handler.set_paper(_NativePaper("Custom Size", -1, -1))
        handler.set_custom_paper_size([29.7, 21.0])
        handler.options_dict.update({"papers": "Custom Size", "papero": 0})

        config = options.build_chart_config()
        page = _build_paper_region(config)

        self.assertEqual(config.paper_size, PaperSize.CUSTOM)
        self.assertEqual(config.custom_width_mm, 210.0)
        self.assertEqual(config.custom_height_mm, 297.0)
        self.assertEqual((page.width_mm, page.height_mm), (210.0, 297.0))

    def test_chart_preset_does_not_override_gramps_page_setup(self):
        options = TwoWayFanChartOptions("native-page-test", _FakeDatabase())
        options.load_previous_values()
        handler = options.handler
        assert handler is not None
        handler.set_paper(_NativePaper("B0", 141.4, 100.0))
        handler.options_dict.update({"papers": "B0", "papero": 1})

        preset_option = options.menu.get_option_by_name("preset")
        assert preset_option is not None
        preset_option.set_value("compact")
        options.apply_selected_preset()
        config = options.build_chart_config()

        self.assertEqual(config.preset, PresetName.COMPACT)
        self.assertEqual(config.paper_size, PaperSize.CUSTOM)
        self.assertEqual(config.custom_width_mm, 1414.0)
        self.assertEqual(config.custom_height_mm, 1000.0)

    def test_hidden_highlight_controls_stay_disabled_for_saved_values(self):
        options = TwoWayFanChartOptions("hidden-highlight-test", _FakeDatabase())
        saved_values = {"highlight_tag": "Old tag", "show_highlight_markers": True}
        for key, value in saved_values.items():
            options.options_dict[key] = value
            menu_option = options.menu.get_option_by_name(key)
            if menu_option is not None:
                menu_option.set_value(value)

        config = options.build_chart_config()

        self.assertEqual(config.highlight_tag, "")
        self.assertFalse(config.show_highlight_markers)


if __name__ == "__main__":
    unittest.main()
