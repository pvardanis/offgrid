"""What the README claims about this project, checked against the project.

A badge is a claim, and a stale one is a lie that looks maintained. The
versions in them are pinned by hand, because shields.io cannot filter a TOML
array by name, so this is what keeps them honest when a dependency moves.
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
LOCK = ROOT / "uv.lock"

BADGED = ("ruff", "ty")


def _locked() -> dict[str, str]:
    """Read what the lockfile pins each tool to."""
    packages = tomllib.loads(LOCK.read_text())["package"]

    return {entry["name"]: entry["version"] for entry in packages}


def _badged(tool: str) -> str | None:
    """Read the version the README shows for a tool."""
    found = re.search(rf"img\.shields\.io/badge/{tool}-([^-]+)-", README.read_text())

    return found.group(1) if found else None


@pytest.mark.parametrize("tool", BADGED)
def test_the_badge_shows_the_version_that_is_locked(tool: str):
    assert _badged(tool) == _locked()[tool]


def test_the_coverage_badge_shows_what_is_enforced():
    # It states the floor rather than the figure of the day: the floor is the
    # number a run can fail on, and the only one that stays true between runs.
    shown = re.search(
        r"img\.shields\.io/badge/coverage-(?:%E2%89%A5)?(\d+)%25", README.read_text()
    )
    floor = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["coverage"][
        "report"
    ]["fail_under"]

    assert shown is not None
    assert int(shown.group(1)) == floor
