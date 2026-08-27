"""What bare `offgrid` opens, and what a person reads on it.

The seam is the screen: the sentences it shows and the key that leaves it. No
frame snapshots — they break on every cosmetic change and pass on wrong
content, which is the inverse of asserting on the message a person reads.
"""

import asyncio

import httpx
from textual.widgets import Static
from typer.testing import CliRunner

from offgrid.cli import app
from offgrid.cli.binding import read_what_can_be_read
from offgrid.tui.picker import REPORT, Report
from tests.doubles import serve_get
from tests.lmstudio_server import RESIDENT
from tests.profiles import add_to_section

runner = CliRunner()


def screen(here, *keys: str) -> tuple[str, bool]:
    """Open the screen over the profile a test wrote, and press keys at it.

    Both answers are read while the screen is still open, because leaving the
    driver closes it: a test reading `is_running` afterwards would report the
    driver's own tidying up as the key having worked.

    :param here: Where that profile is.
    :param keys: What to press, in order.

    :return: The report it is showing, and whether it is still open.
    """
    picker = Report(read=lambda: read_what_can_be_read(here / "profile.yaml"))

    async def driven() -> tuple[str, bool]:
        async with picker.run_test() as pilot:
            if keys:
                await pilot.press(*keys)

            await pilot.pause()

            shown = str(picker.query_one(f"#{REPORT}", Static).content)

            return shown, picker.is_running

    return asyncio.run(driven())


def test_bare_offgrid_opens_the_screen_instead_of_printing_help(here, monkeypatch):
    # Help is the least useful thing a stranger can be shown: it lists commands
    # against a machine nothing has yet said anything about.
    runner.invoke(app, ["setup"])
    opened = []
    monkeypatch.setattr(Report, "run", lambda self: opened.append(self))

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert opened, "bare `offgrid` opened no screen"
    assert "Usage" not in result.stdout


def test_the_screen_shows_what_a_run_would_report(here):
    # Everything knowable before a load, which is what somebody who has just
    # installed offgrid has no other way to see.
    runner.invoke(app, ["setup"])

    shown, _ = screen(here)

    assert "runtime   lmstudio at 127.0.0.1:1234, reachable" in shown
    assert f"model     {RESIDENT}" in shown
    assert "ceiling   262144" in shown
    assert "window    212224" in shown
    assert "profile   " in shown
    assert "agent     claude-code, speaking anthropic" in shown
    assert "command   claude, not on PATH" in shown
    assert "floor     " in shown


def test_the_screen_and_doctor_word_one_fact_the_same_way(here):
    # Two surfaces, one report. A sentence either of them held for itself is a
    # sentence the other comes to say differently.
    runner.invoke(app, ["setup"])
    said = runner.invoke(app, ["doctor"]).stderr

    shown, _ = screen(here)

    for line in shown.splitlines():
        assert line in said, f"the screen says {line!r} and `doctor` does not"


def test_an_unreachable_runtime_names_every_cause_and_the_screen_stays(
    here, monkeypatch
):
    # The report is what somebody opens when nothing works, so the screen it is
    # on is the last thing that should close. Three causes, because a reading
    # naming one sends a person to check what was already true.
    runner.invoke(app, ["setup"])

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)

    shown, still_open = screen(here)

    assert "http://127.0.0.1:1234" in shown
    assert "Start LM Studio" in shown
    assert "install LM Studio" in shown
    assert "offgrid setup --host" in shown
    assert still_open


def test_q_leaves(here):
    runner.invoke(app, ["setup"])

    _, still_open = screen(here, "q")

    assert not still_open


def test_the_screen_writes_nothing(here):
    # Looking around is free: the profile a person hand-edited is exactly as
    # they left it, and nothing else has appeared beside it.
    runner.invoke(app, ["setup"])
    profile = here / "profile.yaml"
    before = profile.read_text()
    beside = sorted(path.name for path in here.iterdir())

    screen(here, "q")

    assert profile.read_text() == before
    assert sorted(path.name for path in here.iterdir()) == beside


def test_a_profile_offgrid_cannot_read_is_shown_on_the_screen(here):
    # A hand-edited profile is a named seam, and what a refusal says carries
    # the key that was refused — in brackets, which is markup to a screen that
    # is reading markup. The report is columns of plain text and wants none.
    runner.invoke(app, ["setup"])
    add_to_section(here, "agent", theme="dark")

    shown, still_open = screen(here)

    assert "theme" in shown
    assert still_open


def test_a_screen_that_crashed_is_not_reported_as_a_run_that_worked(here, monkeypatch):
    # Textual paints a traceback and returns rather than raising, so the code
    # it set is the only thing saying the screen died. Unread, bare `offgrid`
    # says the same as a report somebody read: nothing went wrong.
    runner.invoke(app, ["setup"])

    def crash():
        raise RuntimeError("something nobody wrapped")

    monkeypatch.setattr("offgrid.cli.read_what_can_be_read", lambda path: crash())

    result = runner.invoke(app, [])

    assert result.exit_code == 1
