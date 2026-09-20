import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gramps.gen.lib import Date, EventType

from TwoWayFanChart.facts import source_ok_vital_dates
from TwoWayFanChart.layout import calculate_canvas, layout_center
from TwoWayFanChart.geometry import PaperRegion, PaperSize, Orientation
from TwoWayFanChart.model import SceneText
from TwoWayFanChart.styles import SOURCE_OK_DATE_FILL, TEXT_GREY


class FakeEvent:
    def __init__(self, handle, event_type, tags=()):
        self.handle = handle
        self.event_type = event_type
        self.tags = tuple(tags)

    def get_handle(self):
        return self.handle

    def get_date_object(self):
        return Date(1900)

    def get_tag_list(self):
        return self.tags


class FakePerson:
    def __init__(self, birth, death):
        self.birth = birth
        self.death = death


class FakeDatabase:
    def __init__(self, events, person):
        self.events = {event.handle: event for event in events}
        self.person = person

    def get_person_from_handle(self, handle):
        return self.person if handle == "person" else None


def _canvas():
    return calculate_canvas(
        PaperRegion(PaperSize.A4, Orientation.LANDSCAPE, margin_mm=8),
        ancestor_generations=1,
        descendant_generations=0,
    )


class SourceOkDateTests(unittest.TestCase):
    def test_only_vital_events_with_source_ok_tag_are_selected(self):
        birth = FakeEvent("birth", EventType.BIRTH, tags=("source-ok",))
        death = FakeEvent("death", EventType.DEATH)
        db = FakeDatabase((birth, death), FakePerson(birth, death))

        with patch(
            "TwoWayFanChart.facts.get_birth_or_fallback", return_value=birth
        ), patch(
            "TwoWayFanChart.facts.get_death_or_fallback", return_value=death
        ):
            self.assertEqual(
                source_ok_vital_dates(db, "person", "source-ok"),
                (True, False),
            )

    def test_center_date_color_is_default_grey_and_opt_in_green(self):
        scene = layout_center(
            _canvas(),
            left_label="Alice",
            left_dates="° 1900",
            left_dates_source_ok=False,
        )
        dates = [node for node in scene.children if isinstance(node, SceneText)]
        self.assertEqual(dates[-1].fill, TEXT_GREY)

        scene = layout_center(
            _canvas(),
            left_label="Alice",
            left_dates="° 1900",
            left_dates_source_ok=True,
        )
        dates = [node for node in scene.children if isinstance(node, SceneText)]
        self.assertEqual(dates[-1].fill, SOURCE_OK_DATE_FILL)


if __name__ == "__main__":
    unittest.main()
