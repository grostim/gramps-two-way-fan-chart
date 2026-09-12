#!/usr/bin/env python3
"""Validate the checked-in Gramps add-on distribution."""

from __future__ import annotations

import ast
import json
import re
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON = "TwoWayFanChart"
ARCHIVE_NAME = f"{ADDON}.addon.tgz"
ARCHIVE_PATH = ROOT / "gramps60" / "download" / ARCHIVE_NAME


def fail(message: str) -> None:
    raise SystemExit(f"distribution validation failed: {message}")


def literal_assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, TypeError) as error:
            fail(f"{path}: {name} is not a literal value ({error})")
    fail(f"{path}: missing assignment {name}")


def registration_value(text: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*\"([^\"]+)\"", text)
    if match is None:
        fail(f"registration is missing {field}")
    return match.group(1)


def expected_archive_files() -> set[str]:
    manifest_path = ROOT / ADDON / "MANIFEST"
    manifest_entries = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    missing_manifest_entries = [
        entry for entry in manifest_entries if not (ROOT / entry).is_file()
    ]
    if missing_manifest_entries:
        fail(
            "MANIFEST references missing files: "
            + ", ".join(sorted(missing_manifest_entries))
        )

    python_files = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / ADDON).glob("*.py")
    }
    return set(manifest_entries) | python_files


def validate_archive(expected_files: set[str]) -> int:
    if not ARCHIVE_PATH.is_file():
        fail(f"missing archive {ARCHIVE_PATH.relative_to(ROOT)}")

    with tarfile.open(ARCHIVE_PATH, mode="r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            fail("archive contains duplicate member names")

        actual_files = set(names)
        if actual_files != expected_files:
            missing = sorted(expected_files - actual_files)
            unexpected = sorted(actual_files - expected_files)
            details = []
            if missing:
                details.append(f"missing={missing}")
            if unexpected:
                details.append(f"unexpected={unexpected}")
            fail("archive member set differs: " + "; ".join(details))

        for member in members:
            if not member.isfile():
                fail(f"archive member is not a regular file: {member.name}")
            extracted = archive.extractfile(member)
            if extracted is None:
                fail(f"cannot read archive member: {member.name}")
            source_bytes = (ROOT / member.name).read_bytes()
            if extracted.read() != source_bytes:
                fail(f"archive content differs from source: {member.name}")

    return len(members)


def validate_listings(version: str, gramps_version: str) -> None:
    for language in ("en", "fr"):
        path = ROOT / "gramps60" / "listings" / f"addons-{language}.json"
        if not path.is_file():
            fail(f"missing listing {path.relative_to(ROOT)}")
        try:
            listing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            fail(f"invalid JSON in {path.relative_to(ROOT)}: {error}")
        if not isinstance(listing, list) or len(listing) != 1:
            fail(f"{path.relative_to(ROOT)} must contain exactly one add-on")
        entry = listing[0]
        if not isinstance(entry, dict):
            fail(f"{path.relative_to(ROOT)} entry must be an object")
        expected = {
            "i": ADDON,
            "v": version,
            "g": gramps_version,
            "z": ARCHIVE_NAME,
        }
        for key, value in expected.items():
            if entry.get(key) != value:
                fail(
                    f"{path.relative_to(ROOT)} has {key}={entry.get(key)!r}; "
                    f"expected {value!r}"
                )


def main() -> None:
    builder_path = ROOT / "build_addon.py"
    registration_path = ROOT / ADDON / f"{ADDON}.gpr.py"
    registration = registration_path.read_text(encoding="utf-8")

    addon = literal_assignment(builder_path, "ADDON")
    version = literal_assignment(builder_path, "VERSION")
    gramps_version = literal_assignment(builder_path, "GRAMPS_VERSION")
    if addon != ADDON:
        fail(f"builder ADDON={addon!r}; expected {ADDON!r}")

    registration_version = registration_value(registration, "version")
    registration_gramps_version = registration_value(
        registration, "gramps_target_version"
    )
    if registration_version != version:
        fail(
            "version mismatch between builder and registration: "
            f"{version!r} != {registration_version!r}"
        )
    if registration_gramps_version != gramps_version:
        fail(
            "Gramps target mismatch between builder and registration: "
            f"{gramps_version!r} != {registration_gramps_version!r}"
        )

    expected_files = expected_archive_files()
    archive_entries = validate_archive(expected_files)
    validate_listings(version, gramps_version)
    print(
        "distribution=ok "
        f"version={version} gramps={gramps_version} "
        f"archive_entries={archive_entries}"
    )


if __name__ == "__main__":
    main()
