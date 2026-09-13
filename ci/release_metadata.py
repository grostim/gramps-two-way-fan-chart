#!/usr/bin/env python3
"""Read the version contract consumed by the release workflow."""

from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


ADDON = "TwoWayFanChart"
_VERSION_PATTERN = re.compile(r"\A[0-9]+\.[0-9]+\.[0-9]+\Z")


@dataclass(frozen=True)
class ReleaseMetadata:
    """Versioned values shared by the build and publication jobs."""

    addon: str
    version: str
    gramps_version: str

    @property
    def tag(self) -> str:
        return f"v{self.version}"

    @property
    def archive_name(self) -> str:
        return f"{self.addon}.addon.tgz"


def _literal_assignment(path: Path, name: str):
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
        except (TypeError, ValueError) as error:
            raise ValueError(f"{path}: {name} is not a literal value") from error
    raise ValueError(f"{path}: missing assignment {name}")


def _registration_value(text: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*\"([^\"]+)\"", text)
    if match is None:
        raise ValueError(f"registration is missing {field}")
    return match.group(1)


def validate_version(version: str) -> None:
    """Reject tags that could produce ambiguous or unsafe release names."""
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(
            f"{version!r} is not a plain semantic version (expected X.Y.Z)"
        )


def _version_tuple(version: str) -> tuple[int, int, int]:
    validate_version(version)
    return tuple(int(part) for part in version.split("."))


def validate_version_is_newer(version: str, existing_versions: Iterable[str]) -> None:
    """Reject a version that reuses or regresses an existing release tag."""
    candidate = _version_tuple(version)
    parsed_existing = [
        (_version_tuple(existing), existing)
        for existing in existing_versions
        if isinstance(existing, str) and _VERSION_PATTERN.fullmatch(existing)
    ]
    if not parsed_existing:
        return

    latest_tuple, latest_version = max(parsed_existing)
    if candidate <= latest_tuple:
        raise ValueError(
            f"{version!r} must be newer than existing release {latest_version!r}"
        )


def read_release_metadata(root: Path) -> ReleaseMetadata:
    """Read and cross-check the builder and Gramps registration versions."""
    builder_path = root / "build_addon.py"
    registration_path = root / ADDON / f"{ADDON}.gpr.py"

    addon = _literal_assignment(builder_path, "ADDON")
    version = _literal_assignment(builder_path, "VERSION")
    gramps_version = _literal_assignment(builder_path, "GRAMPS_VERSION")
    if addon != ADDON:
        raise ValueError(f"builder ADDON={addon!r}; expected {ADDON!r}")
    if not isinstance(version, str):
        raise ValueError("builder VERSION must be a string")
    if not isinstance(gramps_version, str):
        raise ValueError("builder GRAMPS_VERSION must be a string")
    validate_version(version)

    registration = registration_path.read_text(encoding="utf-8")
    registration_version = _registration_value(registration, "version")
    registration_gramps_version = _registration_value(
        registration, "gramps_target_version"
    )
    if registration_version != version:
        raise ValueError(
            "version mismatch between builder and registration: "
            f"{version!r} != {registration_version!r}"
        )
    if registration_gramps_version != gramps_version:
        raise ValueError(
            "Gramps target mismatch between builder and registration: "
            f"{gramps_version!r} != {registration_gramps_version!r}"
        )

    return ReleaseMetadata(
        addon=addon,
        version=version,
        gramps_version=gramps_version,
    )


def write_github_output(metadata: ReleaseMetadata, path: Path) -> None:
    """Append the validated single-line values used by later jobs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"version={metadata.version}\n")
        output.write(f"tag={metadata.tag}\n")
        output.write(f"archive_name={metadata.archive_name}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append validated outputs to a GitHub Actions output file",
    )
    args = parser.parse_args()

    metadata = read_release_metadata(Path(__file__).resolve().parents[1])
    if args.github_output is not None:
        write_github_output(metadata, args.github_output)
    print(
        "release_metadata=ok "
        f"addon={metadata.addon} version={metadata.version} "
        f"tag={metadata.tag} gramps={metadata.gramps_version}"
    )


if __name__ == "__main__":
    main()
