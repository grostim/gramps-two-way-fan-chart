#!/usr/bin/env python3
"""Reject a pull request whose release version is already claimed by another
open pull request.

The distribution job already rejects versions that are not newer than the
latest release tag. That check cannot see parallel open pull requests: two
PRs merged in quick succession can both bump to the same patch number, and
the collision only surfaces as a merge/squash conflict or a failed push to
main. This script reads the version announced by every other open PR
targeting the base branch and fails when the current PR reuses it.

Best-effort on unreadable PRs (forks whose builder file cannot be fetched):
those PRs are skipped with a warning rather than blocking every fork flow.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

# Make the repository root importable when executed directly as
# `python ci/check_pr_version.py` (sys.path[0] is ci/ then).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci.release_metadata import read_release_metadata

_VERSION_RE = re.compile(r"^VERSION\s*=\s*\"([0-9]+\.[0-9]+\.[0-9]+)\"", re.MULTILINE)


def version_from_builder(contents: str) -> str | None:
    """Extract the VERSION literal from a build_addon.py source string."""
    match = _VERSION_RE.search(contents)
    if match is None:
        return None
    return match.group(1)


def claimed_by(
    version: str,
    other_pulls: list[dict],
) -> dict | None:
    """Return the first open PR announcing *version*, or None."""
    for pull in other_pulls:
        if pull.get("version") == version:
            return pull
    return None


def open_pulls(owner_repo: str, *, runner=subprocess.run) -> list[dict]:
    """List all open pull requests for cross-channel version checks."""
    result = runner(
        [
            "gh",
            "api",
            f"repos/{owner_repo}/pulls?state=open&per_page=100",
            "--jq",
            ".[] | {number, head_ref: .head.ref, title: .title, repo: .head.repo.full_name, sha: .head.sha, base_ref: .base.ref}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cannot list open pull requests: {result.stderr.strip()}"
        )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def fetch_builder_version(
    owner_repo: str,
    pull: dict,
    *,
    runner=subprocess.run,
) -> str | None:
    """Fetch one PR's build_addon.py and return its announced version.

    Returns None when the file cannot be read (fork without access, PR
    touching no version) so the caller can skip it.
    """
    pull_repo = pull.get("repo") or owner_repo
    result = runner(
        [
            "gh",
            "api",
            f"repos/{pull_repo}/contents/build_addon.py?ref={pull.get('sha', '')}",
            "--jq",
            ".content",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        contents = base64.b64decode(result.stdout.strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return version_from_builder(contents)


def check_claimed_versions(
    version: str,
    owner_repo: str,
    base: str,
    current_pr: int | None,
    *,
    runner=subprocess.run,
    warn=sys.stderr.write,
) -> None:
    """Raise when another open PR to a release branch claims the version."""
    release_branches = {"main", "experimental"}
    pulls = [
        pull
        for pull in open_pulls(owner_repo, runner=runner)
        if pull.get("base_ref") in release_branches
    ]
    readable: list[dict] = []
    for pull in pulls:
        if current_pr is not None and pull["number"] == current_pr:
            continue
        announced = fetch_builder_version(owner_repo, pull, runner=runner)
        if announced is None:
            warn(
                f"warning: cannot read version from PR #{pull['number']} "
                f"({pull.get('head_ref')}); skipped\n"
            )
            continue
        readable.append({**pull, "version": announced})

    conflicting = claimed_by(version, readable)
    if conflicting is not None:
        raise ValueError(
            f"release version {version!r} is already claimed by open PR "
            f"#{conflicting['number']} ({conflicting.get('head_ref')}); "
            "bump to a free patch version in build_addon.py, "
            "TwoWayFanChart/TwoWayFanChart.gpr.py, the listing files and "
            "their tests"
        )
    if readable:
        announced = ", ".join(
            f"#{pull['number']}={pull['version']}" for pull in readable
        )
        print(f"open_pr_versions={announced}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-pr", type=int, default=None)
    parser.add_argument("--base", default="main")
    parser.add_argument("--repo", default=None)
    args = parser.parse_args()

    repo = args.repo
    if repo is None:
        repo = __import__("os").environ.get("GITHUB_REPOSITORY")
    if not repo:
        parser.error("--repo is required (or set GITHUB_REPOSITORY)")
    if "/" not in repo:
        parser.error(f"invalid repository {repo!r}: expected owner/name")

    root = Path(__file__).resolve().parents[1]
    version = read_release_metadata(root).version
    check_claimed_versions(
        version,
        repo,
        args.base,
        args.current_pr,
    )
    print(f"version_claim=ok version={version}")


if __name__ == "__main__":
    main()
