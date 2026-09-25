import unittest
from unittest.mock import patch

from gramps.cli.plug import _convert_str_to_match_type
from gramps.gen.const import GRAMPS_LOCALE
from gramps.gen.display.name import NameDisplay, displayer as global_name_displayer
from gramps.gen.lib import Name, Surname

from TwoWayFanChart import pipeline
from TwoWayFanChart.config import CURRENT_REPORT_NAME_FORMAT, ChartConfig, PresetName
from TwoWayFanChart.facts import simple_name
from TwoWayFanChart.names import NameFormatter, create_name_displayer
from TwoWayFanChart.model import (
    AncestorSlot,
    ChartGraph,
    DescendantBranch,
    PersonNode,
    ScenePathText,
    SceneText,
    UnionBranch,
)
from TwoWayFanChart.options import (
    CURRENT_REPORT_NAME_FORMAT_OPTION_ID,
    TwoWayFanChartOptions,
)
from TwoWayFanChart.privacy import PersonPrivacyFacts


class FakePerson:
    def __init__(self, name):
        self.name = name

    def get_primary_name(self):
        return self.name


class FakeDatabase:
    db_name = "fake-tree"

    def __init__(self, people):
        self.people = people

    def get_person_from_handle(self, handle):
        return self.people.get(handle)

    def get_family_from_gramps_id(self, gramps_id):
        return FakeFamily() if gramps_id == "F0055" else None

    def get_family_from_handle(self, handle):
        return FakeFamily() if handle == "family" else None


class FakeFamily:
    def get_gramps_id(self):
        return "F0055"


def gramps_name():
    name = Name()
    name.set_first_name("Alexandre Théodore")
    name.set_call_name("Alexandre")
    name.set_nick_name("Toto")
    name.set_suffix("Jr.")
    surname = Surname()
    surname.set_surname("Roche")
    name.add_surname(surname)
    return name


def synthetic_graph():
    center = PersonNode("center", "I0001")
    ancestor = PersonNode("ancestor", "I0002")
    descendant = PersonNode("descendant", "I0003")
    return ChartGraph(
        center_family_handle="family",
        center_people=(center, None),
        ancestor_slots=(
            AncestorSlot("ancestor-a-1-0", 1, 0, "a", ancestor),
        ),
        descendant_branches=(
            DescendantBranch(
                "descendant-child",
                descendant,
                1,
                (UnionBranch("descendant-family", "spouse", (), ()),),
                (),
            ),
        ),
        diagnostics=(),
    )


def scene_texts(root):
    texts = []
    stack = [root]
    while stack:
        node = stack.pop()
        if isinstance(node, (ScenePathText, SceneText)):
            texts.append(node.content)
        stack.extend(getattr(node, "children", ()))
    return texts


class NameDisplayOptionTests(unittest.TestCase):
    def test_runtime_option_lists_default_and_report_formats_and_builds_config(self):
        options = TwoWayFanChartOptions("name-format-test", FakeDatabase({}))
        name_option = options.menu.get_option_by_name("name_format")
        assert name_option is not None
        items = name_option.get_items()
        values = {value for value, _description in items}

        self.assertEqual(name_option.get_value(), CURRENT_REPORT_NAME_FORMAT_OPTION_ID)
        self.assertEqual(
            options.build_chart_config().name_format,
            CURRENT_REPORT_NAME_FORMAT,
            "saved configurations without the new key keep the legacy report format",
        )
        self.assertIn(CURRENT_REPORT_NAME_FORMAT_OPTION_ID, values)
        self.assertIn(0, values)
        self.assertTrue(
            set(number for number, _label, _format, _active in global_name_displayer.get_name_format())
            <= values
        )

        name_option.set_value(1)
        self.assertEqual(options.build_chart_config().name_format, 1)

    def test_all_web_name_format_strings_convert_to_supported_menu_ids(self):
        options = TwoWayFanChartOptions("web-name-format-test", FakeDatabase({}))
        name_option = options.menu.get_option_by_name("name_format")
        assert name_option is not None
        default_type_value = name_option.get_value()

        for format_id, _label in name_option.get_items():
            with self.subTest(format_id=format_id):
                parsed = _convert_str_to_match_type(str(format_id), default_type_value)
                self.assertIsInstance(parsed, int)
                name_option.set_value(parsed)
                options.options_dict["name_format"] = parsed
                expected = (
                    CURRENT_REPORT_NAME_FORMAT
                    if format_id == CURRENT_REPORT_NAME_FORMAT_OPTION_ID
                    else format_id
                )
                self.assertEqual(options.build_chart_config().name_format, expected)

    def test_legacy_persisted_name_format_sentinel_is_migrated(self):
        options = TwoWayFanChartOptions("legacy-name-format-test", FakeDatabase({}))
        name_option = options.menu.get_option_by_name("name_format")
        assert name_option is not None
        options.options_dict["name_format"] = CURRENT_REPORT_NAME_FORMAT

        options._normalize_loaded_values()

        self.assertEqual(
            options.options_dict["name_format"],
            CURRENT_REPORT_NAME_FORMAT_OPTION_ID,
        )
        self.assertEqual(name_option.get_value(), CURRENT_REPORT_NAME_FORMAT_OPTION_ID)
        self.assertEqual(
            options.build_chart_config().name_format,
            CURRENT_REPORT_NAME_FORMAT,
        )

    def test_gramps_default_sentinel_resolves_to_current_global_format(self):
        with patch.object(global_name_displayer, "get_default_format", return_value=2):
            formatter = NameFormatter.from_config(ChartConfig(name_format=0))

        self.assertEqual(formatter.local_display.get_default_format(), 2)

    def test_new_configuration_preserves_the_current_report_default(self):
        self.assertEqual(
            getattr(ChartConfig(), "name_format", None),
            "current_report",
        )

    def test_gramp_name_displayer_uses_the_selected_or_global_format_without_mutation(self):
        create_displayer = create_name_displayer
        name = gramps_name()
        default_before = global_name_displayer.get_default_format()

        selected = create_displayer(2)
        with patch.object(global_name_displayer, "get_default_format", return_value=2):
            default = create_displayer(0)
        assert selected is not None
        assert default is not None
        short_format_id = next(
            number
            for number, _name, format_string, active
            in global_name_displayer.get_name_format()
            if active and format_string == "%f"
        )
        short_format = create_displayer(short_format_id)
        assert short_format is not None

        self.assertEqual(selected.display_name(name), "Alexandre Théodore Roche Jr.")
        self.assertEqual(default.display_name(name), selected.display_name(name))
        self.assertEqual(short_format.display_name(name), "Alexandre Théodore")
        self.assertEqual(global_name_displayer.get_default_format(), default_before)
        self.assertIsNone(create_displayer("current_report"))

    def test_simple_name_keeps_legacy_output_by_default_and_honors_an_override(self):
        database = FakeDatabase({"person-1": FakePerson(gramps_name())})
        local = NameDisplay(GRAMPS_LOCALE)
        local.set_name_format(global_name_displayer.get_name_format())
        local.set_default_format(2)

        self.assertEqual(simple_name(database, "person-1"), 'Roche, Alexandre "Toto"')
        self.assertEqual(
            simple_name(database, "person-1", name_displayer=local),
            "Alexandre Théodore Roche Jr.",
        )

    def test_selected_format_is_consistent_for_center_ancestor_and_descendant(self):
        database = FakeDatabase(
            {
                handle: FakePerson(gramps_name())
                for handle in ("center", "ancestor", "descendant", "spouse")
            }
        )
        options = TwoWayFanChartOptions("web-name-format-test", database)
        options.load_previous_values()
        self.assertIs(options.options_dict, options.handler.options_dict)
        menu = options.menu
        menu.get_option_by_name("preset").set_value("custom")
        menu.get_option_by_name("ancestor_generations").set_value(1)
        menu.get_option_by_name("descendant_generations").set_value(1)
        menu.get_option_by_name("show_portraits").set_value(False)
        menu.get_option_by_name("show_ancestor_marriages").set_value(False)
        menu.get_option_by_name("show_descendant_marriages").set_value(False)

        name_option = menu.get_option_by_name("name_format")
        assert name_option is not None
        parsed_value = _convert_str_to_match_type("1", name_option.get_value())
        options.options_dict["name_format"] = parsed_value
        name_option.set_value(parsed_value)
        config = options.build_chart_config()
        self.assertEqual(name_option.get_value(), 1)
        self.assertEqual(options.options_dict["name_format"], 1)
        self.assertEqual(options.handler.options_dict["name_format"], 1)
        self.assertEqual(config.name_format, 1)

        with (
            patch.object(pipeline, "extract_chart_graph", return_value=synthetic_graph()),
            patch.object(
                pipeline,
                "privacy_facts_from_gramps",
                return_value=PersonPrivacyFacts(is_private=False, is_living=False),
            ),
            patch.object(pipeline, "simple_dates", return_value=""),
            patch.object(pipeline, "_marriage_label", return_value=""),
        ):
            _page, scene = pipeline._build_scene(config, database, "family")

        texts = scene_texts(scene)
        expected = "Roche, Alexandre Théodore Jr."
        self.assertEqual(texts.count(expected), 3, texts)
        self.assertIn(f"× {expected}", texts)

    def test_default_scene_keeps_the_existing_call_name_and_nickname_output(self):
        database = FakeDatabase(
            {
                handle: FakePerson(gramps_name())
                for handle in ("center", "ancestor", "descendant", "spouse")
            }
        )
        config = ChartConfig(
            preset=PresetName.CUSTOM,
            ancestor_generations=1,
            descendant_generations=1,
            show_portraits=False,
            show_ancestor_marriages=False,
            show_descendant_marriages=False,
        )

        with (
            patch.object(pipeline, "extract_chart_graph", return_value=synthetic_graph()),
            patch.object(
                pipeline,
                "privacy_facts_from_gramps",
                return_value=PersonPrivacyFacts(is_private=False, is_living=False),
            ),
            patch.object(pipeline, "simple_dates", return_value=""),
            patch.object(pipeline, "_marriage_label", return_value=""),
        ):
            _page, scene = pipeline._build_scene(config, database, "family")

        texts = scene_texts(scene)
        expected = 'Alexandre "Toto" Roche'
        self.assertEqual(texts.count(expected), 3, texts)
        self.assertIn(f"× {expected}", texts)
        self.assertNotIn("Alexandre Théodore Roche Jr.", texts)


if __name__ == "__main__":
    unittest.main()
