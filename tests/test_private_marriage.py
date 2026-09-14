import unittest

try:
    from gramps.gen.lib import EventType
    from TwoWayFanChart.facts import extract_union
except ModuleNotFoundError:  # pragma: no cover - exercised in CI with Gramps
    EventType = None
    extract_union = None


class FakeDate:
    def is_valid(self):
        return True

    def get_year(self):
        return 1899


class FakeEventRef:
    def __init__(self, handle):
        self.handle = handle

    def get_reference_handle(self):
        return self.handle


class FakeEvent:
    def __init__(self, handle, private):
        self.handle = handle
        self.private = private

    def get_type(self):
        return EventType.MARRIAGE

    def get_handle(self):
        return self.handle

    def get_privacy(self):
        return self.private

    def get_date_object(self):
        return FakeDate()

    def get_place_handle(self):
        return None

    def get_description(self):
        return ""


class FakeFamily:
    def __init__(self, event):
        self.event = event

    def get_event_ref_list(self):
        return [FakeEventRef(self.event.handle)]


class FakeDatabase:
    def __init__(self, event):
        self.event = event

    def get_event_from_handle(self, handle):
        return self.event if handle == self.event.handle else None


class PrivateMarriageTests(unittest.TestCase):
    @unittest.skipUnless(EventType is not None, "Gramps is not installed")
    def test_private_marriage_is_filtered_when_private_facts_are_disabled(self):
        event = FakeEvent("marriage-1", private=True)
        family = FakeFamily(event)
        database = FakeDatabase(event)
        displayer = type(
            "Displayer",
            (),
            {"display_event": lambda _self, _database, _event: "Lyon"},
        )()

        self.assertIsNone(
            extract_union(
                database,
                family,
                "years",
                "gramps",
                displayer=displayer,
                include_private=False,
            )
        )
        self.assertIsNotNone(
            extract_union(
                database,
                family,
                "years",
                "gramps",
                displayer=displayer,
                include_private=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
