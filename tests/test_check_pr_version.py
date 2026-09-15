import unittest

import ci.check_pr_version as check_mod
from ci.check_pr_version import (
    check_claimed_versions,
    claimed_by,
    fetch_builder_version,
    version_from_builder,
)

BASE64_BUILDER = "\
VkVRU0lPTiA9ICIxLjIuNTciClZNZXQ6Cg==\
"


class FakeResult:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class FakeRunner:
    """Scripted runner: maps a gh api command to a canned response."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        for prefix, result in self.responses:
            if argv[: len(prefix)] == prefix:
                return result
        return FakeResult(returncode=1, stderr="unexpected command: " + " ".join(argv))


def _pulls_json(pulls):
    return "\n".join(
        (
            "{"
            f'"number":{pull["number"]},'
            f'"head_ref":"{pull["head_ref"]}",'
            f'"title":"{pull.get("title", "")}",'
            f'"repo":"{pull.get("repo", "grostim/gramps-two-way-fan-chart")}",'
            f'"sha":"{pull["sha"]}"'
            "}"
        )
        for pull in pulls
    )


def _content_json(builder_contents):
    import base64

    # gh api ... --jq .content returns the raw base64 payload, not JSON.
    return base64.b64encode(builder_contents.encode("utf-8")).decode("ascii")


class VersionFromBuilderTests(unittest.TestCase):
    def test_extracts_plain_version_literal(self):
        self.assertEqual(
            version_from_builder('VERSION = "1.2.57"\n'), "1.2.57"
        )

    def test_ignores_other_assignment_shapes(self):
        self.assertIsNone(version_from_builder('VERSION = f"{major}.{minor}"\n'))

    def test_allows_spacing_variants(self):
        self.assertEqual(version_from_builder('VERSION="1.2.57"\n'), "1.2.57")
        self.assertEqual(
            version_from_builder('VERSION = "1.2.57"  # release\n'), "1.2.57"
        )

    def test_returns_none_when_missing(self):
        self.assertIsNone(version_from_builder('ADDON = "TwoWayFanChart"\n'))


class ClaimedByTests(unittest.TestCase):
    def test_finds_the_first_pull_announcing_the_version(self):
        pulls = [
            {"number": 65, "head_ref": "fix/a", "version": "1.2.57"},
            {"number": 66, "head_ref": "fix/b", "version": "1.2.58"},
        ]
        hit = claimed_by("1.2.58", pulls)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["number"], 66)

    def test_returns_none_when_free(self):
        pulls = [{"number": 65, "head_ref": "fix/a", "version": "1.2.57"}]
        self.assertIsNone(claimed_by("1.2.58", pulls))


class FetchBuilderVersionTests(unittest.TestCase):
    def test_fetches_and_decodes_the_remote_builder(self):
        runner = FakeRunner(
            [
                (
                    ["gh", "api", "repos/grostim/gramps-two-way-fan-chart/pulls?state=open&base=main&per_page=100"],
                    FakeResult(stdout=_pulls_json([])),
                ),
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=abc123",
                    ],
                    FakeResult(stdout=_content_json('VERSION = "1.2.58"')),
                ),
            ]
        )
        version = fetch_builder_version(
            "grostim/gramps-two-way-fan-chart",
            {"repo": None, "sha": "abc123"},
            runner=runner,
        )
        self.assertEqual(version, "1.2.58")

    def test_returns_none_when_the_api_fails(self):
        runner = FakeRunner(
            [
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=abc123",
                    ],
                    FakeResult(returncode=1, stderr="Not Found"),
                )
            ]
        )
        version = fetch_builder_version(
            "grostim/gramps-two-way-fan-chart",
            {"repo": None, "sha": "abc123"},
            runner=runner,
        )
        self.assertIsNone(version)


class CheckClaimedVersionsTests(unittest.TestCase):
    def test_raises_when_another_open_pr_claims_the_version(self):
        pulls = [
            {"number": 66, "head_ref": "fix/other", "sha": "sha-other"},
        ]
        runner = FakeRunner(
            [
                (
                    ["gh", "api", "repos/grostim/gramps-two-way-fan-chart/pulls?state=open&base=main&per_page=100"],
                    FakeResult(stdout=_pulls_json(pulls)),
                ),
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=sha-other",
                    ],
                    FakeResult(stdout=_content_json('VERSION = "1.2.58"')),
                ),
            ]
        )
        with self.assertRaisesRegex(ValueError, "already claimed by open PR #66"):
            check_claimed_versions(
                "1.2.58",
                "grostim/gramps-two-way-fan-chart",
                "main",
                current_pr=None,
                runner=runner,
            )

    def test_ignores_the_current_pr(self):
        pulls = [
            {"number": 70, "head_ref": "fix/issue43-symbol-size", "sha": "sha-70"},
            {"number": 71, "head_ref": "fix/other", "sha": "sha-71"},
        ]
        runner = FakeRunner(
            [
                (
                    ["gh", "api", "repos/grostim/gramps-two-way-fan-chart/pulls?state=open&base=main&per_page=100"],
                    FakeResult(stdout=_pulls_json(pulls)),
                ),
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=sha-70",
                    ],
                    FakeResult(stdout=_content_json('VERSION = "1.2.58"')),
                ),
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=sha-71",
                    ],
                    FakeResult(stdout=_content_json('VERSION = "1.2.59"')),
                ),
            ]
        )
        # The current PR (70) announces 1.2.58 and must not collide with
        # itself; the other PR (71) announces a different version.
        check_claimed_versions(
            "1.2.58",
            "grostim/gramps-two-way-fan-chart",
            "main",
            current_pr=70,
            runner=runner,
        )

    def test_skips_unreadable_pulls_with_a_warning(self):
        pulls = [
            {"number": 72, "head_ref": "fork/x", "sha": "fork-sha"},
        ]
        runner = FakeRunner(
            [
                (
                    ["gh", "api", "repos/grostim/gramps-two-way-fan-chart/pulls?state=open&base=main&per_page=100"],
                    FakeResult(stdout=_pulls_json(pulls)),
                ),
                (
                    [
                        "gh",
                        "api",
                        "repos/grostim/gramps-two-way-fan-chart/contents/build_addon.py?ref=fork-sha",
                    ],
                    FakeResult(returncode=1, stderr="Not Found"),
                ),
            ]
        )
        warnings = []
        check_claimed_versions(
            "1.2.60",
            "grostim/gramps-two-way-fan-chart",
            "main",
            current_pr=None,
            runner=runner,
            warn=warnings.append,
        )
        self.assertTrue(any("cannot read version" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
