import tempfile
import unittest
from pathlib import Path

from ci.update_portainer_rollout import update_compose


_COMPOSE = """services:
  grampsweb_addon:
    configs:
      - source: twfc_addon_sync
    environment:
      - TWFC_ADDON_VERSION=1.2.39
      - TWFC_ADDON_ROLLOUT=1.2.39-code1
  grampsweb:
    depends_on:
      grampsweb_addon:
        condition: service_completed_successfully
    volumes:
      - '${APPDATA_PATH}/grampsweb/addons/TwoWayFanChart:/root/gramps/gramps60/plugins/TwoWayFanChart:ro'
    environment:
      - TWFC_ADDON_VERSION=1.2.39
      - TWFC_ADDON_ROLLOUT=1.2.39-code1
configs:
  twfc_addon_sync:
    file: ./scripts/sync_grampsweb_addon.sh
"""


class PortainerRolloutTests(unittest.TestCase):
    def _write_compose(self, text=_COMPOSE):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "docker-compose.yml"
        path.write_text(text, encoding="utf-8")
        self.addCleanup(directory.cleanup)
        return path

    def test_updates_all_marker_copies_and_preserves_stack_content(self):
        path = self._write_compose()
        release_sha = "a" * 40

        rollout = update_compose(path, "1.2.40", release_sha)

        self.assertEqual(rollout, "1.2.40-release-aaaaaaaaaaaa")
        updated = path.read_text(encoding="utf-8")
        self.assertEqual(updated.count("TWFC_ADDON_VERSION=1.2.40"), 2)
        self.assertEqual(updated.count("TWFC_ADDON_ROLLOUT=1.2.40-release-aaaaaaaaaaaa"), 2)
        self.assertNotIn("TWFC_ADDON_VERSION=1.2.39", updated)
        self.assertNotIn("TWFC_ADDON_ROLLOUT=1.2.39-code1", updated)
        self.assertIn("services:\n  grampsweb_addon:", updated)

    def test_same_release_is_idempotent(self):
        same_release = _COMPOSE.replace(
            "TWFC_ADDON_VERSION=1.2.39", "TWFC_ADDON_VERSION=1.2.40"
        ).replace(
            "TWFC_ADDON_ROLLOUT=1.2.39-code1",
            "TWFC_ADDON_ROLLOUT=1.2.40-release-aaaaaaaaaaaa",
        )
        path = self._write_compose(same_release)
        before = path.read_bytes()

        rollout = update_compose(path, "1.2.40", "a" * 40)

        self.assertEqual(rollout, "1.2.40-release-aaaaaaaaaaaa")
        self.assertEqual(path.read_bytes(), before)

    def test_refuses_downgrade_and_structural_mismatch(self):
        path = self._write_compose(_COMPOSE.replace("1.2.39", "1.2.40"))
        with self.assertRaisesRegex(ValueError, "downgrade"):
            update_compose(path, "1.2.39", "a" * 40)

        malformed = self._write_compose(_COMPOSE.replace("grampsweb_addon:", "other_service:"))
        with self.assertRaisesRegex(ValueError, "not ready"):
            update_compose(malformed, "1.2.40", "a" * 40, expected_occurrences=1)

    def test_rejects_invalid_release_sha(self):
        path = self._write_compose()

        with self.assertRaisesRegex(ValueError, "40-character"):
            update_compose(path, "1.2.40", "not-a-sha")


if __name__ == "__main__":
    unittest.main()
