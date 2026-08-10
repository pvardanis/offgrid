"""What the README claims about this project, checked against the project.

A badge is a claim, and a stale one is a lie that looks maintained. The
versions in them are pinned by hand, because shields.io cannot filter a TOML
array by name, so this is what keeps them honest when a dependency moves.

Which command reaches the network is the same kind of claim, and the one a
person weighs before running anything. So it is read out of the README and
checked against what the commands actually ask for.
"""

import re
import tomllib
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from offgrid.cli import DEFAULT_HOST, app
from offgrid.machine import Machine

ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
LOCK = ROOT / "uv.lock"

BADGED = ("ruff", "ty")

COMMANDS = ("setup", "doctor", "recommend", "run")
LOCAL = DEFAULT_HOST.split(":")[0]
MACHINE = Machine(
    chip="Apple M1 Max", memory_bytes=64 * 1024**3, wired_limit_bytes=56 * 1024**3
)


def _locked() -> dict[str, str]:
    """Read what the lockfile pins each tool to."""
    packages = tomllib.loads(LOCK.read_text())["package"]

    return {entry["name"]: entry["version"] for entry in packages}


def _badged(tool: str) -> str | None:
    """Read the version the README shows for a tool."""
    found = re.search(rf"img\.shields\.io/badge/{tool}-([^-]+)-", README.read_text())

    return found.group(1) if found else None


def _named_as_reaching_the_network() -> str | None:
    """Read which command the README says is the one that reaches out."""
    found = re.search(
        r"`(\w+)` is the only command that reaches the network", README.read_text()
    )

    return found.group(1) if found else None


def _hosts_asked(command: str, monkeypatch, tmp_path) -> set[str]:
    """Every host a command asks for, with nothing answering any of them.

    The profile is written first, since three of the four commands refuse
    before asking anything without one.
    """
    asked: set[str] = set()

    def record(self: httpx.HTTPTransport, sent: httpx.Request) -> httpx.Response:
        asked.add(sent.url.host)
        raise httpx.ConnectError("nothing is listening", request=sent)

    monkeypatch.setattr("offgrid.cli.detect", lambda: MACHINE)
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.cli.CONFIG_DIR", tmp_path / "claude-code")
    CliRunner().invoke(app, ["setup"])

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", record)
    CliRunner().invoke(app, [command])

    return asked


@pytest.mark.parametrize("command", COMMANDS)
def test_only_the_command_the_readme_names_reaches_the_network(
    command, monkeypatch, tmp_path
):
    # The claim a person reads before running anything, so it is worth more
    # than a maintainer's memory of which module holds a URL.
    named = _named_as_reaching_the_network()
    assert named in COMMANDS, "The README names no command as the one that reaches out"

    beyond = {
        host for host in _hosts_asked(command, monkeypatch, tmp_path) if host != LOCAL
    }

    if command == named:
        assert beyond, f"`offgrid {command}` asked for nothing beyond {LOCAL}"
    else:
        assert not beyond, (
            f"`offgrid {command}` reached {sorted(beyond)}, and the README says "
            f"`{named}` is the only command that does."
        )


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
