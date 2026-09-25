import tempfile
import unittest
from pathlib import Path

from ci.update_portainer_rollout import update_compose


_COMPOSE = """services:
  grampsweb_addon:
    command:
      - /bin/sh
      - -ec
      - |
          apk add --no-cache ca-certificates curl
          sha256sum -c archive.sha256
          tail -f /dev/null
    environment:
      - TWFC_ADDON_VERSION=1.2.39
      - TWFC_ADDON_CHANNEL=stable
      - TWFC_ADDON_ROLLOUT=1.2.39-stable-release-aaaaaaaaaaaa
  grampsweb:
    depends_on:
      grampsweb_addon:
        condition: service_healthy
    volumes:
      - '${APPDATA_PATH}/grampsweb/addons/TwoWayFanChart:/root/gramps/gramps60/plugins/TwoWayFanChart:ro'
    environment:
      - TWFC_ADDON_VERSION=1.2.39
      - TWFC_ADDON_CHANNEL=stable
      - TWFC_ADDON_ROLLOUT=1.2.39-stable-release-aaaaaaaaaaaa
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

        self.assertEqual(rollout, "1.2.40-stable-release-aaaaaaaaaaaa")
        updated = path.read_text(encoding="utf-8")
        self.assertEqual(updated.count("TWFC_ADDON_VERSION=1.2.40"), 2)
        self.assertEqual(updated.count("TWFC_ADDON_CHANNEL=stable"), 2)
        self.assertEqual(updated.count("TWFC_ADDON_ROLLOUT=1.2.40-stable-release-aaaaaaaaaaaa"), 2)
        self.assertNotIn("TWFC_ADDON_VERSION=1.2.39", updated)
        self.assertNotIn("1.2.39-stable-release-aaaaaaaaaaaa", updated)
        self.assertIn("services:\n  grampsweb_addon:", updated)

    def test_same_release_is_idempotent(self):
        same_release = (
            _COMPOSE.replace(
                "TWFC_ADDON_VERSION=1.2.39", "TWFC_ADDON_VERSION=1.2.40"
            )
            .replace(
                "TWFC_ADDON_ROLLOUT=1.2.39-stable-release-aaaaaaaaaaaa",
                "TWFC_ADDON_ROLLOUT=1.2.40-stable-release-aaaaaaaaaaaa",
            )
        )
        path = self._write_compose(same_release)
        before = path.read_bytes()

        rollout = update_compose(path, "1.2.40", "a" * 40)

        self.assertEqual(rollout, "1.2.40-stable-release-aaaaaaaaaaaa")
        self.assertEqual(path.read_bytes(), before)

    def test_refuses_downgrade_and_structural_mismatch(self):
        path = self._write_compose(_COMPOSE.replace("1.2.39", "1.2.40"))
        with self.assertRaisesRegex(ValueError, "downgrade"):
            update_compose(path, "1.2.39", "a" * 40)

        malformed = self._write_compose(_COMPOSE.replace("grampsweb_addon:", "other_service:"))
        with self.assertRaisesRegex(ValueError, "not ready"):
            update_compose(malformed, "1.2.40", "a" * 40, expected_occurrences=1)

    def test_experimental_rollout_and_explicit_stable_rollback(self):
        path = self._write_compose()
        beta_marker = update_compose(
            path, "1.2.41", "b" * 40, channel="experimental"
        )
        self.assertEqual(beta_marker, "1.2.41-experimental-release-bbbbbbbbbbbb")
        updated = path.read_text(encoding="utf-8")
        self.assertEqual(updated.count("TWFC_ADDON_CHANNEL=experimental"), 2)

        with self.assertRaisesRegex(ValueError, "downgrade"):
            update_compose(path, "1.2.40", "c" * 40, channel="stable")
        rollback_marker = update_compose(
            path,
            "1.2.40",
            "c" * 40,
            channel="stable",
            allow_rollback=True,
        )
        self.assertEqual(rollback_marker, "1.2.40-stable-rollback-cccccccccccc")
        self.assertEqual(path.read_text(encoding="utf-8").count("TWFC_ADDON_CHANNEL=stable"), 2)

        with self.assertRaisesRegex(ValueError, "only for the stable channel"):
            update_compose(
                path,
                "1.2.41",
                "d" * 40,
                channel="experimental",
                allow_rollback=True,
            )

    def test_rejects_invalid_release_sha(self):
        path = self._write_compose()

        with self.assertRaisesRegex(ValueError, "40-character"):
            update_compose(path, "1.2.40", "not-a-sha")


if __name__ == "__main__":
    unittest.main()
