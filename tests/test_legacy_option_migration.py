import unittest

from TwoWayFanChart.config import Orientation, PresetName, PrivacyMode, PaperSize
from TwoWayFanChart.options import (
    TwoWayFanChartOptions,
    _normalize_legacy_value,
)


class _FakeFamily:
    def get_gramps_id(self) -> str:
        return "F0055"


class _FakeDatabase:
    db_name = "fake-tree"

    def get_family_from_gramps_id(self, gramps_id: str):
        return _FakeFamily() if gramps_id == "F0055" else None

    def get_family_from_handle(self, handle):
        return None


class LegacyOptionMigrationTests(unittest.TestCase):
    """Persisted settings from releases before the option cleanup (≤ 1.2.56)
    must map forward to their closest supported equivalents instead of
    blocking generation or silently weakening privacy protection."""

    def test_legacy_value_aliases(self):
        self.assertEqual(_normalize_legacy_value("preset", "family"), "publication")
        self.assertEqual(
            _normalize_legacy_value("orientation", "automatic"), "landscape"
        )
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
        for key in ("preset", "orientation", "privacy_mode"):
            options.options_dict[key] = {
                "preset": "family",
                "orientation": "automatic",
                "privacy_mode": "surname_only",
            }[key]
            menu_option = options.menu.get_option_by_name(key)
            menu_option.set_value(options.options_dict[key])

        options._normalize_loaded_values()

        config = options.build_chart_config()
        self.assertEqual(config.preset, PresetName.PUBLICATION)
        self.assertEqual(config.orientation, Orientation.LANDSCAPE)
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


if __name__ == "__main__":
    unittest.main()
