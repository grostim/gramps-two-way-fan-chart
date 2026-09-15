import tempfile
import unittest
from pathlib import Path

from ci.release_metadata import (
    read_release_metadata,
    validate_version,
    validate_version_is_newer,
    write_github_output,
)


class ReleaseMetadataTests(unittest.TestCase):
    def test_repository_metadata_is_ready_for_the_next_release(self):
        metadata = read_release_metadata(Path(__file__).resolve().parents[1])

        self.assertEqual(metadata.addon, "TwoWayFanChart")
        self.assertEqual(metadata.version, "1.2.67")
        self.assertEqual(metadata.gramps_version, "6.0")
        self.assertEqual(metadata.tag, "v1.2.67")
        self.assertEqual(metadata.archive_name, "TwoWayFanChart.addon.tgz")

    def test_version_must_be_a_plain_semver_patch_version(self):
        validate_version("1.2.47")

        with self.assertRaisesRegex(ValueError, "semantic version"):
            validate_version("1.2")

        with self.assertRaisesRegex(ValueError, "semantic version"):
            validate_version("v1.2.47")

    def test_version_must_be_newer_than_existing_release_tags(self):
        validate_version_is_newer("1.2.47", ["1.2.39", "1.2.4"])

        with self.assertRaisesRegex(ValueError, "newer than existing release"):
            validate_version_is_newer("1.2.39", ["1.2.39"])

        with self.assertRaisesRegex(ValueError, "newer than existing release"):
            validate_version_is_newer("1.2.4", ["1.2.47"])

    def test_github_output_contains_only_single_line_values(self):
        metadata = read_release_metadata(Path(__file__).resolve().parents[1])

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "github-output"
            write_github_output(metadata, output_path)
            output = output_path.read_text(encoding="utf-8")

        self.assertEqual(
            output,
            "version=1.2.67\n"
            "tag=v1.2.67\n"
            "archive_name=TwoWayFanChart.addon.tgz\n",
        )


if __name__ == "__main__":
    unittest.main()
