"""What bare `offgrid` opens, and what a person reads on it.

The seam is the screen: the lists it shows, the report beside them, and what
each key does. No frame snapshots — they break on every cosmetic change and
pass on wrong content, which is the inverse of asserting on the message a
person reads.
"""

import asyncio
from dataclasses import dataclass

import httpx
from textual.containers import VerticalScroll
from textual.widgets import OptionList, Static
from typer.testing import CliRunner

from offgrid.agents.claude_code.launching import CONTEXT_FLOOR
from offgrid.cli import app
from offgrid.cli.binding import read_what_could_be_run
from offgrid.domain.costing import RUNNING
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.model import Model
from offgrid.tui.picker import AGENTS, MODELS, PANE, REPORT, RUNTIMES, Picker
from tests.doubles import serve_get
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.pairing import StandInRuntime, answer_as_a_runtime
from tests.profiles import add_to_section

runner = CliRunner()

# Wide enough for the lists and the report side by side, since a test reads
# both. The narrow one the report was written against is asked for by name.
ROOMY = (120, 30)


@dataclass(frozen=True)
class Driven:
    """What a screen answered after keys were pressed at it."""

    shown: str
    listed: dict[str, list[str]]
    reachable: dict[str, list[str]]
    highlighted: dict[str, str | None]
    still_open: bool
    scrolled_to: int
    could_scroll_to: int


def _read_a_list(listed: OptionList) -> tuple[list[str], list[str], str | None]:
    """Read back one list: every row, the rows a cursor may reach, and where it is.

    :param listed: The list to read.

    :return: What the rows say, which of them can be highlighted, and what the
        highlight is on.
    """
    rows = [str(option.prompt) for option in listed.options]
    reachable = [str(option.prompt) for option in listed.options if not option.disabled]
    index = listed.highlighted
    on = None if index is None else str(listed.get_option_at_index(index).prompt)

    return rows, reachable, on


def drive(picker: Picker, *keys: str, size: tuple[int, int] = ROOMY) -> Driven:
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

            read = {
                which: _read_a_list(picker.query_one(f"#{which}", OptionList))
                for which in (RUNTIMES, AGENTS, MODELS)
            }
            scroller = picker.query_one(f"#{PANE}", VerticalScroll)

            return Driven(
                shown=str(picker.query_one(f"#{REPORT}", Static).content),
                listed={which: rows for which, (rows, _, _) in read.items()},
                reachable={which: free for which, (_, free, _) in read.items()},
                highlighted={which: on for which, (_, _, on) in read.items()},
                still_open=picker.is_running,
                scrolled_to=scroller.scroll_offset.y,
                could_scroll_to=scroller.max_scroll_y,
            )

    return asyncio.run(driven())


def screen(here, *keys: str, size: tuple[int, int] = ROOMY) -> Driven:
    """Open the screen over the profile a test wrote.

    :param here: Where that profile is.
    :param keys: What to press, in order.
    :param size: How much terminal to give it.

    :return: What the screen answered.
    """
    return drive(
        Picker(read=lambda: read_what_could_be_run(here / "profile.yaml")),
        *keys,
        size=size,
    )


def on_this_machine(monkeypatch, *commands: str) -> None:
    """Answer as a machine with these agents installed and no others.

    Presence is a `PATH` lookup, so a suite run on a laptop with Claude Code on
    it and one run in CI would otherwise list different rows.

    :param monkeypatch: The test's patcher.
    :param commands: The commands the `PATH` has.
    """
    monkeypatch.setattr(
        "offgrid.domain.running.agent_presence.shutil.which",
        lambda command: f"/somewhere/{command}" if command in commands else None,
    )


def name_a_model(here, identifier: str) -> None:
    """Name a model in the profile, the way a person hand-edits one.

    :param here: Where the profile is.
    :param identifier: The model to name.
    """
    add_to_section(here, "model", identifier=identifier)


def sit_at_a_terminal(monkeypatch) -> None:
    """Answer as somewhere with a person in front of it.

    What a test drives is a pipe, so the screen is what offgrid would not open
    here. Said once, because every test about the screen needs it.

    :param monkeypatch: The test's patcher.
    """
    monkeypatch.setattr("offgrid.cli.someone_is_at_a_terminal", lambda: True)


def test_the_screen_lists_the_runtimes_the_agents_and_what_is_downloaded(
    here, monkeypatch
):
    # The three things a run is assembled from, all on one screen: what offgrid
    # drives, and what this machine has downloaded into it. Somebody whose
    # runtime is holding nothing has had no way to see the third at all.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude", "opencode")

    driven = screen(here)

    assert driven.listed[RUNTIMES] == ["lmstudio"]
    assert [row.split()[0] for row in driven.listed[AGENTS]] == [
        "claude-code",
        "opencode",
    ]
    assert [row.split()[0] for row in driven.listed[MODELS]] == [
        RESIDENT,
        "google/gemma-4-e4b",
    ]


def test_a_model_row_says_whether_it_is_held_and_the_most_it_could_be_served_at(
    here, monkeypatch
):
    # The ceiling is the most this model could ever answer at, and whether it is
    # held is what says a load has already been paid for. Both are knowable
    # before committing, and neither is anywhere else a person can read.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
        ceilings={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)
    held, cold = driven.listed[MODELS]

    assert held.split() == [RESIDENT, "held", "262144"]
    assert cold.split() == ["google/gemma-4-e4b", "131072"]


def test_the_models_already_held_are_listed_first(here, monkeypatch):
    # A held model costs nothing to start, so it is what somebody in a hurry is
    # looking for. A runtime answering in its own order is free to put it last,
    # which is what this arranges: LM Studio's own catalogue happens to lead
    # with what it holds, so a test driven through that double would pass with
    # the ordering taken out.
    runner.invoke(app, ["setup"])
    held = Model(identifier=RESIDENT, context_ceiling=262144, context_window=SERVED)
    cold = Model(
        identifier="google/gemma-4-e4b", context_ceiling=131072, context_window=None
    )
    answer_as_a_runtime(
        monkeypatch,
        StandInRuntime(
            dialects=frozenset({Dialect.ANTHROPIC, Dialect.OPENAI}),
            downloaded=(cold, held),
            holding=(held,),
        ),
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert [row.split()[0] for row in driven.listed[MODELS]] == [
        RESIDENT,
        "google/gemma-4-e4b",
    ]


def test_moving_the_highlight_recomputes_what_a_run_would_cost(here, monkeypatch):
    # The whole point of the screen: what a keystroke would cost, before it is
    # pressed. A model in memory answers at once; one that is not is minutes of
    # weights moving, with whatever else is held let go of first.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    opened = screen(here)
    moved = screen(here, "tab", "tab", "down")

    assert f"{RESIDENT} is held, so this costs no load" in opened.shown
    assert "google/gemma-4-e4b is not held, so this costs a load" in moved.shown
    assert "model       google/gemma-4-e4b" in moved.shown
    assert "  ceiling   262144" in moved.shown


def test_the_highlight_is_reported_on_even_where_the_profile_names_another_model(
    here, monkeypatch
):
    # A profile naming a model and a runtime holding a different one are two
    # statements, and moving onto the held one is a third. Reporting the file's
    # while the cursor sits elsewhere prices a load nobody is about to pay.
    runner.invoke(app, ["setup"])
    name_a_model(here, "google/gemma-4-e4b")
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here, "tab", "tab", "up")

    assert str(driven.highlighted[MODELS]).startswith(RESIDENT)
    assert f"model       {RESIDENT}" in driven.shown
    assert f"{RESIDENT} is held, so this costs no load" in driven.shown


def test_a_model_that_is_not_held_is_served_at_no_window_rather_than_an_unsaid_one(
    here, monkeypatch
):
    # `unstated` is what a held model says when the runtime answers no number
    # for it. A cold model is not being served at all, so the number does not
    # exist yet — and reading one as the other is what the context split is for.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here, "tab", "tab", "down")

    assert "model       google/gemma-4-e4b" in driven.shown
    assert "  window    unknown" in driven.shown


def test_the_cursor_will_not_land_on_an_agent_this_machine_cannot_start(
    here, monkeypatch
):
    # Driven rather than read off the widget: a list that let the cursor step
    # onto a marked row would answer this the same way an unmarked one does.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "opencode")

    walked = [
        screen(here, "tab", *pressed).highlighted[AGENTS]
        for pressed in ((), ("up",), ("down",), ("home",), ("end",), ("up", "up"))
    ]

    assert walked == ["opencode"] * len(walked), (
        f"the cursor reached {sorted(map(str, set(walked)))} walking the agent list"
    )


def test_an_agent_whose_own_settings_will_not_read_is_a_row_and_not_a_blank_screen(
    here, monkeypatch
):
    # Every agent offgrid drives is asked when the screen opens, so one file
    # nobody has picked can stop all of it being shown. It is a row that says
    # so instead, and the report for it says what stopped it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude", "opencode")
    (here / "opencode").mkdir()
    (here / "opencode" / "opencode.json").write_text("{not json")

    driven = screen(here, "tab", "down")

    assert driven.listed[AGENTS] == ["claude-code", "opencode      did not answer"]
    assert not any(row.startswith("opencode") for row in driven.reachable[AGENTS]), (
        "the cursor can reach an agent that would not answer"
    )
    assert f"model       {RESIDENT}" in driven.shown


def test_an_agent_the_runtime_cannot_talk_to_is_refused_with_every_dialect_named(
    here, monkeypatch
):
    # The refusal a run meets after committing, met here for nothing — and
    # naming everything the runtime does serve, which is what says which end to
    # change rather than sending somebody to guess.
    runner.invoke(app, ["setup"])
    answer_as_a_runtime(
        monkeypatch,
        StandInRuntime(
            dialects=frozenset({Dialect.OPENAI}),
            downloaded=(
                Model(identifier=RESIDENT, context_ceiling=262144, context_window=None),
            ),
        ),
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    # Read with the wrapping taken out, because where the refusal breaks across
    # lines is the terminal's business rather than what it says.
    flowed = " ".join(driven.shown.split())

    assert "running     refused, and a load would not be reached" in driven.shown
    assert "The runtime serves the openai API and the agent expects anthropic" in flowed
    assert "pick a runtime that serves anthropic" in flowed


def test_an_agent_this_machine_has_not_got_is_marked_and_the_cursor_steps_over_it(
    here, monkeypatch
):
    # Visible, because the list is also how somebody learns what offgrid
    # supports. Unreachable, because arming it would re-create the exit 127
    # this screen exists to prevent — discovered after a load and a release.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "opencode")

    driven = screen(here)
    marked = [row for row in driven.listed[AGENTS] if row.startswith("claude-code")]

    assert marked == ["claude-code   not installed"]
    assert not any(row.startswith("claude-code") for row in driven.reachable[AGENTS]), (
        "the cursor can reach an agent this machine cannot start"
    )
    assert driven.highlighted[AGENTS] == "opencode"


def test_the_report_for_an_absent_agent_says_where_to_get_it(here, monkeypatch):
    # A link and never an install command: which package manager and which
    # flags are facts about somebody else's project, wrong the moment they
    # change it and with nothing here to notice.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch)

    driven = screen(here)

    assert "  command   claude, not on PATH" in driven.shown
    assert "https://docs.claude.com/en/docs/claude-code/setup" in driven.shown
    assert "nothing here starts claude-code, so this pair cannot run" in driven.shown


def test_a_runtime_with_nothing_downloaded_says_so_and_where_to_go_next(
    here, monkeypatch
):
    # An empty list reads as offgrid having failed to ask. Its own state, its
    # own wording, and a command to run rather than a search.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch)
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert driven.listed[MODELS] == ["the runtime has nothing downloaded"]
    assert not driven.reachable[MODELS]
    assert "the runtime at 127.0.0.1:1234 has nothing downloaded" in driven.shown
    assert "Run `offgrid recommend`" in driven.shown


def test_moving_the_highlight_writes_nothing(here, monkeypatch):
    # Looking around is free: the profile a person hand-edited is exactly as
    # they left it, and nothing else has appeared beside it.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude", "opencode")
    profile = here / "profile.yaml"
    before = profile.read_text()
    beside = sorted(path.name for path in here.iterdir())

    screen(here, "tab", "down", "tab", "down", "q")

    assert profile.read_text() == before
    assert sorted(path.name for path in here.iterdir()) == beside


def test_bare_offgrid_opens_the_screen_instead_of_printing_help(here, monkeypatch):
    # Help is the least useful thing a stranger can be shown: it lists commands
    # against a machine nothing has yet said anything about.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)
    opened = []
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

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

    assert "runtime     lmstudio at 127.0.0.1:1234, reachable" in shown
    assert "  dialects  anthropic, openai" in shown
    assert f"model       {RESIDENT}" in shown
    assert "  ceiling   262144" in shown
    assert "  window    212224" in shown
    assert "requests    asks for nothing, so a run takes whatever is held" in shown
    assert "agent       claude-code, speaking anthropic" in shown
    assert "  command   claude, not on PATH" in shown
    assert f"  floor     {CONTEXT_FLOOR}" in shown
    assert "might leave this machine" in shown
    assert f"conversations\n  {here / 'claude-code'}" in shown


def test_the_screen_and_doctor_word_one_fact_the_same_way(here):
    # Two surfaces, one report. A sentence either of them held for itself is a
    # sentence the other comes to say differently.
    #
    # Everything up to `running`, which is the one block the screen owns: what a
    # keystroke would cost is a question `doctor` has never had, because it
    # reports the model the runtime is already holding.
    runner.invoke(app, ["setup"])
    said = runner.invoke(app, ["doctor"]).stderr

    driven = screen(here)
    read_off_both, _, priced = driven.shown.partition(f"\n{RUNNING}")

    assert priced, "the screen priced nothing, so this compares the whole report"

    for line in read_off_both.splitlines():
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

    monkeypatch.setattr("offgrid.cli.read_what_could_be_run", lambda path: crash())

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

    # Three lists take the focus before the report does, so reaching it is
    # three tabs — which is the gesture a person makes to read to the bottom.
    cramped = screen(here, size=(80, 8))
    scrolled = screen(here, "tab", "tab", "tab", "end", size=(80, 8))

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
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

    runner.invoke(app, [])

    assert RESIDENT in drive(opened[0]).shown
