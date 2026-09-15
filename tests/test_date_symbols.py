import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gramps.gen.lib import Date, EventType

from TwoWayFanChart.facts import (
    VitalDates,
    VitalFact,
    build_person_view,
    extract_union,
    format_event_date,
    format_date,
    simple_dates,
)
from TwoWayFanChart.model import PersonViewSeed, VisibilityState


class FakeEvent:
    def __init__(self, handle, date):
        self.handle = handle
        self.date = date

    def get_handle(self):
        return self.handle

    def get_date_object(self):
        return self.date

    def get_type(self):
        return EventType.MARRIAGE

    def get_description(self):
        return ""

    def get_place_handle(self):
        return None


class FakeReference:
    def __init__(self, handle):
        self.handle = handle

    def get_reference_handle(self):
        return self.handle


class FakePerson:
    def __init__(self, birth=None, death=None):
        self.birth = birth
        self.death = death

    def get_birth_ref(self):
        return None

    def get_death_ref(self):
        return None


class FakeFamily:
    def __init__(self, events):
        self.events = events

    def get_event_ref_list(self):
        return tuple(FakeReference(event.handle) for event in self.events)


class FakeDatabase:
    def __init__(self, events, person=None):
        self.events = {event.handle: event for event in events}
        self.person = person

    def get_event_from_handle(self, handle):
        return self.events[handle]

    def get_person_from_handle(self, handle):
        return self.person if handle == "person" else None


class DateSymbolTests(unittest.TestCase):
    def test_year_format_preserves_gramps_date_precision(self):
        about = Date(1820)
        about.set_modifier(Date.MOD_ABOUT)
        before = Date(1820)
        before.set_modifier(Date.MOD_BEFORE)
        after = Date(1820)
        after.set_modifier(Date.MOD_AFTER)

        self.assertEqual(format_date(about, "years"), "ca 1820")
        self.assertEqual(format_date(before, "years"), "/1820")
        self.assertEqual(format_date(after, "years"), "1820/")

    def test_event_symbols_distinguish_vital_and_successive_marriages(self):
        date = Date(1820)

        self.assertEqual(format_event_date(date, "years", EventType.BIRTH), "° 1820")
        self.assertEqual(format_event_date(date, "years", EventType.DEATH), "† 1820")
        self.assertEqual(format_event_date(date, "years", EventType.MARRIAGE), "⚭ 1820")
        self.assertEqual(
            format_event_date(date, "years", EventType.MARRIAGE, occurrence=2),
            "⚭2 1820",
        )
        self.assertEqual(
            format_event_date(date, "years", EventType.MARRIAGE, occurrence=3),
            "⚭3 1820",
        )

    def test_simple_dates_prefixes_each_vital_date(self):
        birth = FakeEvent("birth", Date(1820))
        death = FakeEvent("death", Date(1880))
        person = FakePerson(birth, death)
        database = FakeDatabase([birth, death], person)

        with patch("TwoWayFanChart.facts.get_birth_or_fallback", return_value=birth), patch(
            "TwoWayFanChart.facts.get_death_or_fallback", return_value=death
        ):
            self.assertEqual(simple_dates(database, "person"), "° 1820 – † 1880")

    def test_extract_union_prefixes_marriage_date(self):
        marriage = FakeEvent("marriage", Date(1820))
        database = FakeDatabase([marriage])
        family = FakeFamily([marriage])

        with patch("TwoWayFanChart.facts.format_event_place", return_value=""):
            fact = extract_union(database, family, "years", "gramps")

        self.assertIsNotNone(fact)
        self.assertEqual(fact.date_text, "⚭ 1820")

    def test_person_view_passes_marriage_occurrence_to_union_extraction(self):
        seed = PersonViewSeed(
            position_id="person-position",
            visibility=VisibilityState.VISIBLE,
            given_name="Person",
            surname="Example",
            details=(),
            media_reference=None,
        )
        config = SimpleNamespace(
            date_format="years",
            place_strategy="locality",
            show_places=False,
            show_occupation=False,
            show_residence=False,
            show_union=True,
            show_sosa=False,
            show_daboville=False,
        )
        labels = SimpleNamespace(
            short_label="Person Example",
            full_label="Person Example",
            name_case="Person Example",
        )
        vitals = VitalDates(
            VitalFact("", None, False),
            VitalFact("", None, False),
        )

        with patch("TwoWayFanChart.facts.NameFormatter.from_config"), patch(
            "TwoWayFanChart.facts.derive_name_labels", return_value=labels
        ), patch(
            "TwoWayFanChart.facts.extract_vital_dates", return_value=vitals
        ), patch(
            "TwoWayFanChart.facts.extract_union", return_value=None
        ) as extract_union_mock:
            build_person_view(
                seed,
                object(),
                object(),
                config,
                "central_couple",
                family=object(),
                marriage_occurrence=3,
            )

        self.assertEqual(extract_union_mock.call_args.kwargs["occurrence"], 3)


if __name__ == "__main__":
    unittest.main()
