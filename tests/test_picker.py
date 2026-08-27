"""What bare `offgrid` opens, and what a person reads on it.

The seam is the screen: the sentences it shows and the key that leaves it. No
frame snapshots — they break on every cosmetic change and pass on wrong
content, which is the inverse of asserting on the message a person reads.
"""

import asyncio
from dataclasses import dataclass

import httpx
from textual.containers import VerticalScroll
from textual.widgets import Static
from typer.testing import CliRunner

from offgrid.agents.claude_code.launching import CONTEXT_FLOOR
from offgrid.cli import app
from offgrid.cli.binding import read_what_can_be_read
from offgrid.tui.picker import REPORT, Report
from tests.doubles import serve_get
from tests.lmstudio_server import RESIDENT
from tests.profiles import add_to_section

runner = CliRunner()


@dataclass(frozen=True)
class Driven:
    """What a screen answered after keys were pressed at it."""

    shown: str
    still_open: bool
    scrolled_to: int
    could_scroll_to: int


def drive(picker: Report, *keys: str, size: tuple[int, int] = (80, 24)) -> Driven:
    """Open a screen, press keys at it, and read what it is showing.

    Everything is read while the screen is still open, because leaving the
    driver closes it: a test reading `is_running` afterwards would report the
    driver's own tidying up as the key having worked.

    :param picker: The screen to open.
    :param keys: What to press, in order.
    :param size: How much terminal to give it, for a report that is taller.

    :return: What it shows, whether it is still open, and how far the report
        has been scrolled against how far it could be.
    """

    async def driven() -> Driven:
        async with picker.run_test(size=size) as pilot:
            if keys:
                await pilot.press(*keys)

            await pilot.pause()

            shown = str(picker.query_one(f"#{REPORT}", Static).content)
            scroller = picker.query_one(VerticalScroll)

            return Driven(
                shown=shown,
                still_open=picker.is_running,
                scrolled_to=scroller.scroll_offset.y,
                could_scroll_to=scroller.max_scroll_y,
            )

    return asyncio.run(driven())


def screen(here, *keys: str, size: tuple[int, int] = (80, 24)) -> Driven:
    """Open the screen over the profile a test wrote.

    :param here: Where that profile is.
    :param keys: What to press, in order.
    :param size: How much terminal to give it.

    :return: What the screen answered.
    """
    return drive(
        Report(read=lambda: read_what_can_be_read(here / "profile.yaml")),
        *keys,
        size=size,
    )


def sit_at_a_terminal(monkeypatch) -> None:
    """Answer as somewhere with a person in front of it.

    What a test drives is a pipe, so the screen is what offgrid would not open
    here. Said once, because every test about the screen needs it.

    :param monkeypatch: The test's patcher.
    """
    monkeypatch.setattr("offgrid.cli.someone_is_at_a_terminal", lambda: True)


def test_bare_offgrid_opens_the_screen_instead_of_printing_help(here, monkeypatch):
    # Help is the least useful thing a stranger can be shown: it lists commands
    # against a machine nothing has yet said anything about.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)
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

    driven = screen(here)
    shown = driven.shown

    assert "runtime   lmstudio at 127.0.0.1:1234, reachable" in shown
    assert "dialects  anthropic, openai" in shown
    assert f"model     {RESIDENT}" in shown
    assert "ceiling   262144" in shown
    assert "window    212224" in shown
    assert "requests  asks for nothing, so a run takes whatever is held" in shown
    assert "agent     claude-code, speaking anthropic" in shown
    assert "command   claude, not on PATH" in shown
    assert f"floor     {CONTEXT_FLOOR}" in shown
    assert "might leave this machine" in shown
    assert "conversations path" in shown


def test_the_screen_and_doctor_word_one_fact_the_same_way(here):
    # Two surfaces, one report. A sentence either of them held for itself is a
    # sentence the other comes to say differently.
    runner.invoke(app, ["setup"])
    said = runner.invoke(app, ["doctor"]).stderr

    driven = screen(here)
    shown = driven.shown

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

    driven = screen(here)
    shown = driven.shown

    assert "http://127.0.0.1:1234" in shown
    assert "Start LM Studio" in shown
    assert "install LM Studio" in shown
    assert "offgrid setup --host" in shown
    assert driven.still_open


def test_q_leaves(here):
    runner.invoke(app, ["setup"])

    driven = screen(here, "q")

    assert not driven.still_open


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

    driven = screen(here)
    shown = driven.shown

    assert "theme" in shown
    assert driven.still_open


def test_a_screen_that_crashed_is_not_reported_as_a_run_that_worked(here, monkeypatch):
    # Textual paints a traceback and returns rather than raising, so the code
    # it set is the only thing saying the screen died. Unread, bare `offgrid`
    # says the same as a report somebody read: nothing went wrong.
    runner.invoke(app, ["setup"])

    sit_at_a_terminal(monkeypatch)

    def crash():
        raise RuntimeError("something nobody wrapped")

    monkeypatch.setattr("offgrid.cli.read_what_can_be_read", lambda path: crash())

    result = runner.invoke(app, [])

    assert result.exit_code == 1


def test_nothing_at_the_terminal_gets_the_help_rather_than_a_screen(here):
    # A screen takes the terminal and waits for a key. Somewhere with nobody
    # at it — a pipe, a file, a CI step — that wait never ends, and what a
    # person would have read is 13KB of escape codes in a log.
    runner.invoke(app, ["setup"])

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_a_report_taller_than_the_terminal_can_be_read_to_the_end(here):
    # The lines that fall off the bottom are the remedies — where to get the
    # agent, how to open a conversation again, what to delete to be asked
    # about a window again. A report nobody can reach the end of is not the
    # report `doctor` prints.
    runner.invoke(app, ["setup"])

    cramped = screen(here, size=(80, 8))
    scrolled = screen(here, "end", size=(80, 8))

    assert cramped.could_scroll_to > 0, "the report fits, so nothing is proven"
    assert cramped.scrolled_to == 0
    assert scrolled.scrolled_to == scrolled.could_scroll_to


def test_the_screen_bare_offgrid_opens_reads_the_profile_offgrid_keeps(
    here, monkeypatch
):
    # The command line builds the screen's reading around its own DEFAULT_PATH,
    # and nothing else runs that lambda: pointed at a path nobody has, every
    # test about the screen still passes and every person meets a refusal.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)
    opened = []
    monkeypatch.setattr(Report, "run", lambda self: opened.append(self))

    runner.invoke(app, [])

    assert RESIDENT in drive(opened[0]).shown
