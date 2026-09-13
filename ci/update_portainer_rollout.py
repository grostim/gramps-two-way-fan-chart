#!/usr/bin/env python3
"""Update the versioned rollout markers in the Portainer Compose file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_VERSION_PATTERN = re.compile(r"\A[0-9]+\.[0-9]+\.[0-9]+\Z")
_SHA_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
_MARKER_PATTERNS = {
    "version": re.compile(
        r"^(?P<prefix>[ \t]*-[ \t]*TWFC_ADDON_VERSION=)"
        r"(?P<value>[^#\r\n \t]+)(?P<suffix>[ \t]*(?:#.*)?)$",
        re.MULTILINE,
    ),
    "rollout": re.compile(
        r"^(?P<prefix>[ \t]*-[ \t]*TWFC_ADDON_ROLLOUT=)"
        r"(?P<value>[^#\r\n \t]+)(?P<suffix>[ \t]*(?:#.*)?)$",
        re.MULTILINE,
    ),
}


def _version_tuple(value: str) -> tuple[int, int, int]:
    if _VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"invalid semantic version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def _matches(text: str, marker: str) -> list[re.Match[str]]:
    return list(_MARKER_PATTERNS[marker].finditer(text))


def _replace_markers(text: str, marker: str, value: str) -> str:
    pattern = _MARKER_PATTERNS[marker]

    def replace(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{value}{match.group('suffix')}"

    return pattern.sub(replace, text)


def update_compose(
    compose_path: Path,
    version: str,
    release_sha: str,
    *,
    expected_occurrences: int = 2,
) -> str:
    """Update both marker copies and return the new rollout marker.

    The two copies are intentional: one is used by the downloader service and
    one is inherited by the web/Celery runtime anchor. Requiring the exact
    count prevents silently updating an incomplete or structurally changed
    stack file.
    """
    _version_tuple(version)
    if _SHA_PATTERN.fullmatch(release_sha) is None:
        raise ValueError("release SHA must be a 40-character lowercase hex string")
    if expected_occurrences < 1:
        raise ValueError("expected_occurrences must be positive")

    text = compose_path.read_text(encoding="utf-8")
    required_fragments = (
        "grampsweb_addon:",
        "service_healthy",
        "twfc_addon_sync",
        "addons/TwoWayFanChart:/root/gramps/gramps60/plugins/TwoWayFanChart:ro",
    )
    missing_fragments = [fragment for fragment in required_fragments if fragment not in text]
    if missing_fragments:
        raise ValueError(
            "Portainer stack is not ready for release deployment; missing: "
            + ", ".join(missing_fragments)
        )
    version_matches = _matches(text, "version")
    rollout_matches = _matches(text, "rollout")
    if len(version_matches) != expected_occurrences:
        raise ValueError(
            "expected exactly "
            f"{expected_occurrences} TWFC_ADDON_VERSION markers, found {len(version_matches)}"
        )
    if len(rollout_matches) != expected_occurrences:
        raise ValueError(
            "expected exactly "
            f"{expected_occurrences} TWFC_ADDON_ROLLOUT markers, found {len(rollout_matches)}"
        )

    current_versions = {match.group("value") for match in version_matches}
    if len(current_versions) != 1:
        raise ValueError(f"TWFC_ADDON_VERSION markers disagree: {sorted(current_versions)}")
    current_version = next(iter(current_versions))
    if _version_tuple(current_version) > _version_tuple(version):
        raise ValueError(
            f"refusing to downgrade Portainer marker from {current_version} to {version}"
        )

    current_rollouts = {match.group("value") for match in rollout_matches}
    if len(current_rollouts) != 1:
        raise ValueError(f"TWFC_ADDON_ROLLOUT markers disagree: {sorted(current_rollouts)}")

    rollout = f"{version}-release-{release_sha[:12]}"
    updated = _replace_markers(text, "version", version)
    updated = _replace_markers(updated, "rollout", rollout)
    if updated != text:
        compose_path.write_text(updated, encoding="utf-8", newline="")
    return rollout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("compose_path", type=Path)
    parser.add_argument("version")
    parser.add_argument("release_sha")
    parser.add_argument("--expected-occurrences", type=int, default=2)
    args = parser.parse_args()

    rollout = update_compose(
        args.compose_path,
        args.version,
        args.release_sha,
        expected_occurrences=args.expected_occurrences,
    )
    print(f"portainer_rollout=ok version={args.version} marker={rollout}")


if __name__ == "__main__":
    main()
