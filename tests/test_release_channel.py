import unittest

from ci.release_channel import (
    channel_status,
    channel_from_env,
    transform_registration,
)


class ReleaseChannelTests(unittest.TestCase):
    def test_stable_channel_uses_stable_registration_and_listing_status(self):
        self.assertEqual(channel_status("stable"), ("STABLE", 3))

    def test_experimental_channel_uses_experimental_registration_and_listing_status(self):
        self.assertEqual(channel_status("experimental"), ("EXPERIMENTAL", 2))

    def test_channel_name_is_validated(self):
        with self.assertRaisesRegex(ValueError, "must be one of"):
            channel_status("beta")

    def test_experimental_registration_is_transformed_without_touching_source(self):
        source = 'register(REPORT, id="two_way_fan_chart", status=STABLE)\n'
        result = transform_registration(source, "experimental")
        self.assertEqual(
            result,
            'register(REPORT, id="two_way_fan_chart", status=EXPERIMENTAL)\n',
        )
        self.assertIn("status=STABLE", source)

    def test_refuses_ambiguous_registration_status(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            transform_registration("register(REPORT, status=STABLE, status=STABLE)", "experimental")


if __name__ == "__main__":
    unittest.main()
