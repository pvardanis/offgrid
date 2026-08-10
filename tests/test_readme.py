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
RUNTIME_COMMANDS = ("doctor", "run")
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


def _requests_made(command: str, monkeypatch, tmp_path) -> list[httpx.Request]:
    """Every request a command makes, with nothing answering any of them.

    A profile is written first, since `doctor` and `run` refuse before asking
    anything without one, and a command that refused asks for nothing at all —
    which is what every claim below would read as kept.

    :param command: The one to run.
    :param monkeypatch: The test's patcher.
    :param tmp_path: Where the profile and the agent's directory go.

    :return: The requests, in the order they were made.
    """
    made: list[httpx.Request] = []

    def record(self: httpx.HTTPTransport, sent: httpx.Request) -> httpx.Response:
        made.append(sent)
        raise httpx.ConnectError("nothing is listening", request=sent)

    monkeypatch.setattr("offgrid.cli.detect", lambda: MACHINE)
    monkeypatch.setattr("offgrid.cli.DEFAULT_PATH", tmp_path / "profile.yaml")
    monkeypatch.setattr("offgrid.cli.CONFIG_DIR", tmp_path / "claude-code")
    written = CliRunner().invoke(app, ["setup"])
    assert written.exit_code == 0, f"The profile was not written: {written.stderr}"

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", record)
    CliRunner().invoke(app, [command])

    return made


@pytest.mark.parametrize("command", COMMANDS)
def test_only_the_command_the_readme_names_reaches_the_network(
    command, monkeypatch, tmp_path
):
    # The claim a person reads before running anything, so it is worth more
    # than a maintainer's memory of which module holds a URL.
    named = _named_as_reaching_the_network()
    assert named in COMMANDS, "The README names no command as the one that reaches out"

    asked = {sent.url.host for sent in _requests_made(command, monkeypatch, tmp_path)}
    beyond = asked - {LOCAL}

    if command == named:
        assert beyond, f"`offgrid {command}` asked for nothing beyond {LOCAL}"
    else:
        assert not beyond, (
            f"`offgrid {command}` reached {sorted(beyond)}, and the README says "
            f"`{named}` is the only command that does."
        )

    # A command that asked for nothing keeps every claim there is, so the two
    # that talk to the runtime have to be seen doing it.
    if command in RUNTIME_COMMANDS:
        assert LOCAL in asked, f"`offgrid {command}` never reached the runtime"


def test_the_request_that_reaches_the_network_carries_nothing_about_this_machine(
    monkeypatch, tmp_path
):
    # The README says what is sent, and "nothing about you" is the half of it
    # a person cannot check for themselves.
    command = _named_as_reaching_the_network()
    assert command is not None

    sent = _requests_made(command, monkeypatch, tmp_path)[0]
    with httpx.Client() as client:
        default = client.build_request("GET", sent.url)

    assert sent.method == "GET"
    assert not sent.url.query
    assert set(sent.headers) - set(default.headers) == {"rsc"}
    assert "cookie" not in sent.headers
    assert not sent.content


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
