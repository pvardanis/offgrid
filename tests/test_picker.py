"""What bare `offgrid` opens, and what a person reads on it.

The seam is the screen: the lists it shows, the report beside them, and what
each key does. No frame snapshots — they break on every cosmetic change and
pass on wrong content, which is the inverse of asserting on the message a
person reads.
"""

import asyncio
import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx
import pytest
import typer
from rich.cells import cell_len
from textual.app import App
from textual.containers import VerticalScroll
from textual.content import Content
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    OptionList,
    Select,
    Static,
)
from textual.widgets._footer import FooterKey
from textual.widgets._select import SelectOverlay
from typer.testing import CliRunner

from offgrid.agents.claude_code.launching import CONTEXT_FLOOR
from offgrid.cli import app, read_this_build
from offgrid.cli.binding import read_profile, read_what_could_be_run
from offgrid.cli.run import launch_the_assembled_profile
from offgrid.domain.assembling import IN_MEMORY
from offgrid.domain.profile import Theme, save_profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import save_discarded_window
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeName
from offgrid.domain.sizing.measuring import describe_the_machine_and_how_to_fit_more
from offgrid.domain.sizing.recommendation import (
    PANEL_COLUMNS,
    Recommendation,
    RecommendedModel,
)
from offgrid.shared.exceptions import LeaderboardUnavailableError, ProfileError
from offgrid.shared.say import LOGGER
from offgrid.shared.wording import REACHING_THE_NETWORK
from offgrid.tui.dropdown import Dropdown
from offgrid.tui.header import BUILD, CWD, INHERITS, THEME
from offgrid.tui.picker import (
    AGENTS,
    CHANGED,
    COLUMNS,
    DEFAULT_THEME,
    DETAIL,
    DOWNLOAD,
    FITS,
    MODELS,
    PANE,
    RANKED,
    RANKED_CAPTION,
    RECOMMEND,
    RECOMMEND_CLOSED,
    RECOMMEND_OPEN,
    RECOMMENDING,
    REPORT,
    RUNTIMES,
    SIGNAL,
    STATUS,
    UNCHANGED,
    WRITES,
    Departure,
    Picker,
)
from tests.commands import MACHINE
from tests.doubles import serve_get
from tests.launches import record_launch
from tests.lmstudio_server import RESIDENT, SERVED, answer_as_lm_studio
from tests.pairing import StandInRuntime, answer_as_a_runtime
from tests.profiles import add_to_section

runner = CliRunner()

# Wide enough for the lists and the report side by side, since a test reads
# both. The narrow one the report was written against is asked for by name.
ROOMY = (120, 30)

# What the command line reads and hands the screen for the header band: which
# offgrid this is, and the directory a run would inherit. Fakes here, because
# the screen only displays them and reads for neither.
BUILD_SHA = "abc1234"
WORKDIR = "/somewhere/a-project"


@dataclass(frozen=True)
class Driven:
    """What a screen answered after keys were pressed at it."""

    shown: str
    fits: str
    signal: str
    signal_colours: dict[str, str]
    detail_open: bool
    columns: str
    status: str
    build: str
    cwd: str
    theme: str
    applied_theme: str
    footer: list[str]
    listed: dict[str, list[str]]
    reachable: dict[str, list[str]]
    highlighted: dict[str, str | None]
    left_with: Departure | None
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


def _read_a_dropdown(dropdown: Dropdown) -> tuple[list[str], list[str], str | None]:
    """Read back one dropdown: every choice, the reachable ones, and the pick.

    The choices are read off the overlay, where they carry the disabled flag
    the cursor steps over; the pick is the value, which greying keeps off the
    ones a run cannot start.

    :param dropdown: The dropdown to read.

    :return: What the choices say, which of them can be picked, and which is.
    """
    overlay = dropdown.query_one(SelectOverlay)
    # A dropdown that may hold no value carries a blank row for clearing it,
    # which is not one of the choices offgrid offers.
    choices = [option for option in overlay.options if str(option.prompt)]
    rows = [str(option.prompt) for option in choices]
    reachable = [str(option.prompt) for option in choices if not option.disabled]
    on = None if dropdown.value is Select.NULL else str(dropdown.value)

    return rows, reachable, on


def _colours_on(signal: Static) -> dict[str, str]:
    """Read which colour paints each line of the signal panel.

    The panel styles a line by covering its whole run with one span, so the
    span starting where a line starts carries that line's verdict. A line left
    unpainted maps to the empty string.

    :param signal: The signal panel to read.

    :return: Each line's text against the theme variable painting it.
    """
    painted = cast(Content, signal.content)
    spans = {span.start: str(span.style) for span in painted.spans}

    colours = {}
    at = 0
    for line in painted.plain.split("\n"):
        colours[line] = spans.get(at, "")
        at += len(line) + 1

    return colours


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
                RUNTIMES: _read_a_dropdown(picker.query_one(f"#{RUNTIMES}", Dropdown)),
                AGENTS: _read_a_dropdown(picker.query_one(f"#{AGENTS}", Dropdown)),
                MODELS: _read_a_list(picker.query_one(f"#{MODELS}", OptionList)),
            }
            scroller = picker.query_one(f"#{PANE}", VerticalScroll)

            return Driven(
                shown=str(picker.query_one(f"#{REPORT}", Static).content),
                fits=str(picker.query_one(f"#{FITS}", Static).content),
                signal=str(picker.query_one(f"#{SIGNAL}", Static).content),
                signal_colours=_colours_on(picker.query_one(f"#{SIGNAL}", Static)),
                detail_open=not picker.query_one(f"#{DETAIL}", Collapsible).collapsed,
                columns=str(picker.query_one(f"#{COLUMNS}", Static).content),
                status=str(picker.query_one(f"#{STATUS}", Static).content),
                build=str(picker.query_one(f"#{BUILD}", Static).content),
                cwd=str(picker.query_one(f"#{CWD}", Static).content),
                theme=str(picker.query_one(f"#{THEME}", Static).content),
                applied_theme=str(picker.theme),
                footer=[key.description for key in picker.query(FooterKey)],
                listed={which: rows for which, (rows, _, _) in read.items()},
                reachable={which: free for which, (_, free, _) in read.items()},
                highlighted={which: on for which, (_, _, on) in read.items()},
                left_with=picker.return_value,
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
        Picker(
            read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
            save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
            sha=BUILD_SHA,
            cwd=WORKDIR,
        ),
        *keys,
        size=size,
    )


def fresh_screen(here, *keys: str, size: tuple[int, int] = ROOMY) -> Driven:
    """Open the screen the way bare `offgrid` does where there is no profile.

    The measurement is handed in, as the command line hands it in when the file
    is absent: a stranger following the README meets the machine measured
    rather than an error naming another command.

    :param here: Where the profile would be, which no test wrote here.
    :param keys: What to press, in order.
    :param size: How much terminal to give it.

    :return: What the screen answered.
    """
    return drive(
        Picker(
            read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
            save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
            sha=BUILD_SHA,
            cwd=WORKDIR,
            measure_func=lambda: describe_the_machine_and_how_to_fit_more(MACHINE),
        ),
        *keys,
        size=size,
    )


def starts_at(row: str, part: str) -> int:
    """Say which terminal cell a piece of a row starts in.

    Cells rather than characters, and measured by Rich rather than by the code
    under test: the mark for a held model is one character and two cells wide,
    so a row counted by characters lines up in the file and not on the screen.
    Rich is what Textual lays the screen out with, which makes it the answer a
    person actually sees.

    :param row: The line to look in.
    :param part: What to find in it.

    :return: How many cells precede it.
    """
    return cell_len(row[: row.index(part)])


def centre_of(row: str, part: str) -> int:
    """Say which terminal cell the middle of a piece of a row falls in.

    Cells rather than characters, and doubled so that a mark centred with an
    odd cell of slack still compares equal to the heading centred over it.

    :param row: The line to look in.
    :param part: What to find in it.

    :return: Twice the cell its centre sits at, so a half-cell is exact.
    """
    return 2 * starts_at(row, part) + cell_len(part)


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


def record_a_discarded_window(here) -> None:
    """Keep that the runtime did not grant a window it was asked for.

    Written where the suite's own guard points `DEFAULT_PATH`, which is where
    the reader looks: the picker reads the record through the same call
    `doctor` does.

    :param here: Where offgrid keeps its files.
    """
    save_discarded_window(
        runtime=RuntimeName.LMSTUDIO,
        host="127.0.0.1:1234",
        model_identifier=RESIDENT,
        asked_for=131072,
        served=SERVED,
        file_path=discarded_windows.DEFAULT_PATH,
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

    assert held.split() == [RESIDENT, IN_MEMORY, "262144"]
    assert cold.split() == ["google/gemma-4-e4b", "131072"]


def test_the_model_list_names_the_column_its_bare_number_is(here, monkeypatch):
    # 262144 against 40960 is two numbers about nothing until something says
    # which of a model's context figures they are — and the ceiling is here
    # precisely because the other one does not exist until a load.
    #
    # Where each name sits is asserted against the row under it, because a
    # heading over the wrong column is worse than no heading at all.
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

    assert driven.columns.split() == ["model", "held", "context"]
    # The mark and the `held` heading are centred in one column, so they share a
    # centre rather than a left edge — a narrower mark starts a cell in from a
    # wider heading and reads as being under it all the same.
    assert centre_of(driven.columns, "held") == centre_of(held, IN_MEMORY)
    assert starts_at(driven.columns, "context") == starts_at(held, "262144")
    assert starts_at(driven.columns, "context") == starts_at(cold, "131072")


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

    a_load = "google/gemma-4-e4b is not held by lmstudio, so this costs a load"

    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in opened.signal
    assert a_load in moved.signal


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
    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in driven.signal


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

    a_load = "google/gemma-4-e4b is not held by lmstudio, so this costs a load"

    # A cold model is served at no window, so the context line says what a run
    # would request rather than a ceiling the detail's model line already gives.
    # That it is not served is the first line's "not held", said once.
    assert a_load in driven.signal
    assert "requested context inherit served" in driven.signal
    assert "context ceiling" not in driven.signal
    assert "not served yet" not in driven.signal


def test_the_cursor_will_not_land_on_an_agent_this_machine_cannot_start(
    here, monkeypatch
):
    # Driven rather than read off the widget: a dropdown that let the cursor
    # commit a marked row would answer this the same way an unmarked one does.
    # Each gesture opens the dropdown, walks it, and presses enter to pick
    # wherever it landed — claude-code among the choices and greyed, opencode
    # the one a run could start.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "opencode")

    walked = [
        screen(here, "tab", "enter", *pressed, "enter").highlighted[AGENTS]
        for pressed in ((), ("up",), ("down",), ("home",), ("end",), ("up", "up"))
    ]

    assert walked == ["opencode"] * len(walked), (
        f"the cursor committed {sorted(map(str, set(walked)))} walking the agent list"
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

    marked = next(row for row in driven.listed[AGENTS] if row.startswith("opencode"))

    # What stopped it rides on the row for the same reason the install link
    # does: the cursor cannot land here, so nothing else would ever show it.
    assert driven.listed[AGENTS][0] == "claude-code"
    assert marked.splitlines()[0] == "opencode      did not answer"
    assert "opencode.json" in marked
    assert not any(row.startswith("opencode") for row in driven.reachable[AGENTS]), (
        "the cursor can reach an agent that would not answer"
    )
    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in driven.signal


def test_moving_the_agent_highlight_recomputes_the_report(here, monkeypatch):
    # The other half of "the report follows the highlight", and the half that
    # nothing held: a report reading the profile's agent rather than the
    # highlighted one answers every question about the pair a person is on with
    # a fact about the pair they left.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude", "opencode")

    opened = screen(here)
    moved = screen(here, "tab", "enter", "down", "enter")

    assert moved.highlighted[AGENTS] == "opencode"
    assert "claude-code · pair can talk (anthropic)" in opened.signal
    assert "opencode · pair can talk (openai)" in moved.signal

    # Where its conversations land is read off the highlighted agent's own
    # config, so it says the signal was computed for that agent rather than
    # from the one the profile names.
    assert str(here / "claude-code") in opened.signal
    assert str(here / "opencode") in moved.signal


def test_moving_inside_the_open_agent_dropdown_leaves_the_report_alone(
    here, monkeypatch
):
    # The report follows the committed pick, not the open popup. Opening the
    # agent dropdown and moving onto opencode without pressing enter to choose
    # it reports nothing new — a person reads the pair they are on, not the one
    # they are hovering. A regression guard: wiring the report to the overlay's
    # own highlight, to match the always-open models list, would break it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude", "opencode")

    hovered = screen(here, "tab", "enter", "down")

    assert hovered.highlighted[AGENTS] == "claude-code"
    assert "claude-code · pair can talk (anthropic)" in hovered.signal
    assert "opencode · pair can talk (openai)" not in hovered.signal


def test_moving_onto_an_agent_the_runtime_cannot_talk_to_is_what_refuses_it(
    here, monkeypatch
):
    # The refusal has to be produced by the move rather than by the profile,
    # or a report that never reads the highlighted agent passes the same
    # assertion.
    runner.invoke(app, ["setup"])
    answer_as_a_runtime(
        monkeypatch,
        StandInRuntime(
            dialects=frozenset({Dialect.ANTHROPIC}),
            downloaded=(
                Model(identifier=RESIDENT, context_ceiling=262144, context_window=None),
            ),
        ),
    )
    on_this_machine(monkeypatch, "claude", "opencode")

    opened = screen(here)
    moved = screen(here, "tab", "enter", "down", "enter")

    assert "refused, and a load would not be reached" not in opened.signal
    assert "refused, and a load would not be reached" in moved.signal
    assert "the anthropic API and the agent expects openai" in " ".join(
        moved.signal.split()
    )


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
    flowed = " ".join(driven.signal.split())

    assert "refused, and a load would not be reached" in driven.signal
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
    marked = next(row for row in driven.listed[AGENTS] if row.startswith("claude-code"))

    # The reason rides on the row, because the cursor steps over it and the
    # report is only ever computed for the row the cursor is on: said anywhere
    # else, the one sentence that helps is the one nobody can reach.
    assert marked.splitlines()[0] == "claude-code   not installed"
    assert "https://docs.claude.com/en/docs/claude-code/setup" in marked
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
    marked = next(row for row in driven.listed[AGENTS] if row.startswith("claude-code"))

    # The run panel bars the pair; where to get the agent rides on its greyed
    # row, since the cursor cannot land there to compute a report for it.
    assert "nothing here starts claude-code, so this pair cannot run" in driven.signal
    assert "https://docs.claude.com/en/docs/claude-code/setup" in marked


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
    assert "the runtime at 127.0.0.1:1234 has nothing downloaded" in driven.signal
    assert "Run `offgrid recommend`" in driven.signal


def test_a_runtime_with_nothing_downloaded_still_reports_the_model_named(
    here, monkeypatch
):
    # An empty list gives the highlight nowhere to sit, and nowhere to sit is
    # not the same statement as asking for nothing: a profile naming a model
    # asks for it whether or not the runtime has anything to show.
    runner.invoke(app, ["setup"])
    name_a_model(here, "google/gemma-4-e4b")
    answer_as_lm_studio(monkeypatch)
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert "google/gemma-4-e4b, context ceiling" in driven.shown
    assert "name one under `model:` in the profile" not in driven.shown


def test_the_agent_a_run_would_try_is_reported_on_even_where_it_would_not_answer(
    here, monkeypatch
):
    # Reached when the profile names the broken agent and nothing else can be
    # highlighted, which is where the whole-report branch is read. What the
    # runtime said stays, because none of it was read off the agent.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch)
    (here / "claude-code").mkdir(exist_ok=True)
    (here / "claude-code" / "settings.json").write_text("{not json")

    driven = screen(here)

    assert "claude-code, which did not answer, so this pair cannot run" in driven.signal
    assert "settings.json" in driven.signal
    assert "lmstudio at 127.0.0.1:1234, serves anthropic + openai" in driven.shown


def test_a_window_offgrid_stopped_asking_for_is_said_on_the_screen(here, monkeypatch):
    # The remedy is a file to delete, and the screen is where somebody looks
    # when a run is not the size they asked for.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")
    record_a_discarded_window(here)

    driven = screen(here)

    assert "discarded" in driven.shown
    assert "context 131072 refused" in driven.shown


def test_a_profile_asking_for_nothing_says_so_where_the_held_model_is_highlighted(
    here, monkeypatch
):
    # Sitting on the model the runtime is holding is not the same statement as
    # having written its name down, and the `requests` line is the only place
    # the difference shows.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    opened = screen(here)
    moved = screen(here, "tab", "tab", "down")

    asks_for_nothing = "no model, so a run takes whatever is held"

    assert str(opened.highlighted[MODELS]).startswith(RESIDENT)
    assert asks_for_nothing in opened.shown
    assert "google/gemma-4-e4b, context ceiling" in moved.shown


def test_a_model_the_runtime_has_not_got_is_named_rather_than_swapped(
    here, monkeypatch
):
    # A profile can name a model that has since been deleted or renamed. The
    # list has no row for it, and quietly moving the highlight onto another
    # model would answer with a clean report about a run nobody asked for —
    # while `run` refuses and `doctor` says the real request.
    runner.invoke(app, ["setup"])
    name_a_model(here, "someone/a-model-that-was-deleted")
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert driven.highlighted[MODELS] is None
    assert "someone/a-model-that-was-deleted, context ceiling unknown" in driven.shown
    assert "has not got someone/a-model-that-was-deleted" in driven.signal
    assert f"{RESIDENT} is held" not in driven.signal


def test_a_window_the_profile_asks_for_is_carried_into_what_would_run(
    here, monkeypatch
):
    # A number somebody wrote down is a request, and a report that dropped it
    # would price a run at a window nobody asked for.
    runner.invoke(app, ["setup"])
    add_to_section(here, "model", context_window=65536)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert "requested context 65536" in driven.shown


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


def test_bare_offgrid_names_the_build_unknown_where_git_is_not_on_the_path(
    here, monkeypatch
):
    # The SHA is a line the header only displays, so git not being reachable —
    # no git on the PATH — is a word rather than the FileNotFoundError that
    # would otherwise escape the callback and keep the screen from opening.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)

    def no_git(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr("offgrid.cli.subprocess.run", no_git)
    opened = []
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

    result = runner.invoke(app, [])
    driven = drive(opened[0])

    assert result.exit_code == 0
    assert "offgrid @ unknown" in driven.build
    # The cwd is wired through the same callback: what the screen shows is the
    # directory a run would inherit, read off this process rather than faked.
    assert str(Path.cwd()) in driven.cwd


def test_bare_offgrid_names_the_build_unknown_where_git_answers_nothing(
    here, monkeypatch
):
    # A git that runs but names no commit — a checkout with no HEAD — answers
    # empty, which is the other way the SHA can be missing. It reads as the same
    # word rather than a blank where the commit would be.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)

    def names_nothing(*args, **kwargs):
        return subprocess.CompletedProcess(args, 128, stdout="\n", stderr="")

    monkeypatch.setattr("offgrid.cli.subprocess.run", names_nothing)
    opened = []
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "offgrid @ unknown" in drive(opened[0]).build


def test_the_build_reads_the_short_commit_git_names(monkeypatch):
    # A regression guard, not a slice: where git answers, the build is the
    # short commit it named, with the trailing newline stripped rather than
    # carried into the header. Nothing else in the suite proves the happy path
    # — every screen test hands the header a fake SHA — so a `read_this_build`
    # that returned `unknown` regardless would otherwise go unnoticed.
    def names_a_commit(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="abc1234\n", stderr="")

    monkeypatch.setattr("offgrid.cli.subprocess.run", names_a_commit)

    assert read_this_build() == "abc1234"


def test_the_build_warns_where_a_checkout_refuses_to_name_its_commit(
    monkeypatch, caplog
):
    # A directory that is a checkout but where git exits non-zero with something
    # to say is the surprising miss. It reads as `unknown` like the benign ones,
    # but leaves a line saying what git refused, so an `unknown` on a real
    # checkout is not silent.
    def refuses(*args, **kwargs):
        return subprocess.CompletedProcess(
            args, 128, stdout="", stderr="fatal: not a git repository"
        )

    monkeypatch.setattr("offgrid.cli.subprocess.run", refuses)

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        build = read_this_build()

    assert build == "unknown"
    assert "fatal: not a git repository" in caplog.text
    assert "128" in caplog.text


def test_the_screen_shows_what_a_run_would_report(here, monkeypatch):
    # Everything knowable before a load, which is what somebody who has just
    # installed offgrid has no other way to see: the signal it decides on, and
    # the curated detail behind the toggle — each in the screen's own voice
    # rather than doctor's column report.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)
    signal = driven.signal
    detail = driven.shown

    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in signal
    assert "served at context 212224 (requested context inherit served)" in signal
    assert "claude-code · pair can talk (anthropic)" in signal
    assert f"conversations → {here / 'claude-code'}" in signal

    assert "lmstudio at 127.0.0.1:1234, serves anthropic + openai" in detail
    assert "no model, so a run takes whatever is held" in detail
    assert "context ceiling 262144" in detail
    assert "requested context inherit served" in detail
    assert f"minimum required context {CONTEXT_FLOOR}" in detail
    assert "claude, at /somewhere/claude" in detail
    assert "leaving" in detail
    assert "hosted tools" in detail
    assert "transcript sharing" in detail
    assert "agent speaks anthropic ∈ {anthropic, openai}" in detail


def test_a_nested_detail_lines_value_aligns_with_a_top_lines(here, monkeypatch):
    # A line nested under the agent puts its value in the same column a top line
    # does, so the detail reads down one column and the indent alone shows the
    # nesting. Widen the sub-label back into a second column and this fails.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    lines = screen(here).shown.splitlines()

    runtime = next(line for line in lines if line.startswith("runtime"))
    command = next(line for line in lines if line.lstrip().startswith("command"))

    assert runtime.index("lmstudio") == command.index("claude")


def test_the_run_panel_signals_what_the_pairing_would_do(here, monkeypatch):
    # The few lines a person decides on before committing: whether it costs a
    # load, the window it is served at and what a run would request, and where a
    # conversation it starts would be kept. Not the fuller dump — that waits
    # behind a key — so the runtime and the agent's command are not in it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    signal = screen(here).signal

    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in signal
    assert "served at context 212224 (requested context inherit served)" in signal
    assert f"conversations → {here / 'claude-code'}" in signal
    # The way back rides in the signal; the provenance and the finding stay in
    # the detail's fuller telling. Swap `resume_with` for `said` and this fails.
    assert "offgrid run -- --resume" in signal
    # One space between the directory and the parenthetical, not the gap two
    # left. Double the space and this fails.
    assert f"{here / 'claude-code'} (offgrid's own" in signal
    assert "measured against" not in signal
    assert "dialect" not in signal


def test_the_signal_recomputes_the_load_cost_as_the_highlight_moves(here, monkeypatch):
    # The signal follows the highlight the way the dump does: a model in memory
    # costs no load, one that is not costs a load, said in the panel a person
    # reads rather than only in the dump behind the toggle.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    opened = screen(here)
    moved = screen(here, "tab", "tab", "down")

    a_load = "google/gemma-4-e4b is not held by lmstudio, so this costs a load"

    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in opened.signal
    assert a_load in moved.signal
    # A load is a cost, not a bar: the line is painted warning, not error.
    costs = next(text for text in moved.signal_colours if "costs a load" in text)
    assert moved.signal_colours[costs] == "$text-warning"


def test_the_signal_bars_a_pair_whose_agent_is_not_here(here, monkeypatch):
    # Viability is a signal, not a footnote: a pair whose agent nothing here
    # starts cannot run, and the panel a person reads says so before they
    # commit to a run that would be refused.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch)

    signal = screen(here).signal

    assert "nothing here starts claude-code, so this pair cannot run" in signal


def test_the_signal_paints_each_verdict_its_own_colour(here, monkeypatch):
    # Colour is the verdict a glance reads before the words are. A free run and
    # a plain fact are painted apart — success against muted — so the panel does
    # not read as one flat block. Repaint every line one colour and this fails.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    colours = screen(here).signal_colours

    held = next(text for text in colours if "costs no load" in text)
    served = next(text for text in colours if "served at context" in text)
    assert colours[held] == "$text-success"
    assert colours[served] == "$text-muted"


def test_the_signal_paints_a_barred_pair_in_error(here, monkeypatch):
    # A pair that cannot run is the one verdict a person must not miss, so the
    # bar line is painted error rather than left the colour of a fact.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch)

    colours = screen(here).signal_colours

    barred = next(text for text in colours if "cannot run" in text)
    assert colours[barred] == "$text-error"


def test_the_diagnostics_wait_behind_a_collapsible_closed_by_default(here):
    # The screen a person first meets is the signal rather than the log. The
    # fuller dump — the runtime, the request, the discarded-window internals —
    # is in the collapsible whether it is open or shut, and a key opens it.
    runner.invoke(app, ["setup"])

    closed = screen(here)
    opened = screen(here, "d")

    assert not closed.detail_open
    assert opened.detail_open
    assert "request" in closed.shown
    assert "request" not in closed.signal


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
    shown = driven.signal

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

    assert "theme" in driven.signal
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

    # The dump waits behind the diagnostics toggle, so it is opened first, and
    # the scroller inside it is what reads to the bottom.
    def scroll(*keys: str) -> tuple[int, int]:
        picker = Picker(
            read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
            save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
            sha=BUILD_SHA,
            cwd=WORKDIR,
        )

        async def driven() -> tuple[int, int]:
            async with picker.run_test(size=(80, 8)) as pilot:
                await pilot.press("d")
                picker.query_one(f"#{PANE}", VerticalScroll).focus()
                await pilot.pause()

                if keys:
                    await pilot.press(*keys)
                    await pilot.pause()

                scroller = picker.query_one(f"#{PANE}", VerticalScroll)

                return scroller.scroll_offset.y, scroller.max_scroll_y

        return asyncio.run(driven())

    at_the_top, could_scroll_to = scroll()
    at_the_end, could_scroll_to_end = scroll("end")

    assert could_scroll_to > 0, "the report fits, so nothing is proven"
    assert at_the_top == 0
    assert at_the_end == could_scroll_to_end


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

    assert any(RESIDENT in row for row in drive(opened[0]).listed[MODELS])


def test_s_runs_with_what_is_assembled_and_writes_nothing(here, monkeypatch):
    # `s` runs for this run only: what it leaves with is what a run is made
    # from, and the file a person hand-edited is exactly as they left it.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude")
    profile = here / "profile.yaml"
    before = profile.read_text()

    driven = screen(here, "s")

    assert isinstance(driven.left_with, Departure)
    assert driven.left_with.saved is False
    assert not driven.still_open
    assert profile.read_text() == before


def test_enter_runs_with_what_is_assembled_and_saves_it(here, monkeypatch):
    # `enter` runs and saves: it leaves with the model the highlight is on, and
    # the file a later run reads now names it. Moving onto the cold model and
    # choosing it is the gesture, and the profile named nothing before.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    driven = screen(here, "tab", "tab", "down", "enter")

    assert isinstance(driven.left_with, Departure)
    assert driven.left_with.saved is True
    saved = read_profile(here / "profile.yaml").model

    assert driven.left_with.profile.model.identifier == "google/gemma-4-e4b"
    assert saved.identifier == "google/gemma-4-e4b"
    # The window nobody chose stays unwritten: the picker offers no way to pick
    # one, so materialising the runtime's served window into a saved number
    # would be a request nobody made and a behaviour change disguised as a save.
    assert saved.context_window is None
    assert driven.left_with.profile.model.context_window is None


def test_enter_saves_the_agent_that_was_picked_and_not_only_the_model(
    here, monkeypatch
):
    # A save here writes runtime and agent as well as the model, so trying the
    # other agent once and pressing the key that writes rewrites the agent. The
    # file names it afterwards, which is what says the write was wider than one
    # field.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude", "opencode")

    driven = screen(here, "tab", "enter", "down", "enter", "tab", "enter")

    assert driven.left_with is not None
    assert driven.left_with.profile.agent_name.value == "opencode"
    assert read_profile(here / "profile.yaml").agent_name.value == "opencode"


def test_a_save_keeps_a_comment_a_person_wrote_by_hand(here, monkeypatch):
    # The file is advertised as hand-editable, so the key that writes must not
    # take a comment with it. Choosing the cold model is what makes the save
    # change the file, so a comment left standing is one a round-tripping write
    # kept rather than one nothing touched.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")
    profile = here / "profile.yaml"
    profile.write_text("# a note I wrote\n" + profile.read_text())

    screen(here, "tab", "tab", "down", "enter")

    assert read_profile(profile).model.identifier == "google/gemma-4-e4b"
    assert "# a note I wrote" in profile.read_text()


def test_the_status_says_which_key_writes_before_either_is_pressed(here, monkeypatch):
    # The consequence is on screen rather than remembered: `enter` writes, `s`
    # runs once. Said above the footer, because Textual's own footer will not
    # carry the `enter` hint while a list or a dropdown has the keys — which is
    # always. `s` and `q` are keys the footer does show.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert WRITES in driven.status
    assert "enter" in driven.status
    assert "saves" in driven.status
    assert "run once" in driven.footer
    assert "leave" in driven.footer
    # The whole reason it is said on the status line: the footer cannot carry a
    # hint for `enter` while a list or a dropdown has the keys.
    assert "run and save" not in driven.footer


def test_the_status_says_when_what_is_assembled_differs_from_the_file(
    here, monkeypatch
):
    # A person about to press the key that writes can see whether the write
    # would change anything. Opened, the screen holds the file; moving onto the
    # cold model is a change the file does not hold.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(
        monkeypatch,
        holding={RESIDENT: SERVED},
        cold={"google/gemma-4-e4b": 131072},
    )
    on_this_machine(monkeypatch, "claude")

    opened = screen(here)
    moved = screen(here, "tab", "tab", "down")

    assert UNCHANGED in opened.status
    assert CHANGED not in opened.status
    assert CHANGED in moved.status


def test_the_status_changes_when_the_agent_alone_is_moved(here, monkeypatch):
    # `differs` is over the whole assembled profile, not the model alone:
    # switching to the other agent and leaving the model where it is still
    # differs from the file, because a save would write the agent too.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude", "opencode")

    moved = screen(here, "tab", "enter", "down", "enter")

    assert moved.highlighted[AGENTS] == "opencode"
    assert CHANGED in moved.status


def test_the_picker_launches_the_run_and_reports_a_save(here, monkeypatch, capsys):
    # `enter` saves and then runs, and the save says what it wrote — runtime,
    # agent and model, not the model alone — in the plain lines a run is read in
    # after the screen is gone. This profile names no model, so the model clause
    # is the "whatever is held" one; the named-model clause is below.
    runner.invoke(app, ["setup"])
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    started = record_launch(monkeypatch)
    profile = read_profile(here / "profile.yaml")

    with pytest.raises(typer.Exit) as left:
        launch_the_assembled_profile(profile, saved=True)

    said = capsys.readouterr().err

    assert left.value.exit_code == 0
    assert started["argv"][0] == "claude"
    assert "Saved to your profile" in said
    assert "runtime lmstudio" in said
    assert "agent claude-code" in said
    assert "model no model, so a run takes whatever is held" in said
    # The picker path lets go of the model afterwards exactly as `run` does.
    assert asked["let_go"] == [RESIDENT]


def test_the_save_report_names_the_model_where_the_profile_names_one(
    here, monkeypatch, capsys
):
    # The other model clause: a profile that names a model reports that name,
    # so a save is never reported as wider or narrower than it was.
    runner.invoke(app, ["setup"])
    name_a_model(here, RESIDENT)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    record_launch(monkeypatch)
    profile = read_profile(here / "profile.yaml")

    with pytest.raises(typer.Exit):
        launch_the_assembled_profile(profile, saved=True)

    assert f"model {RESIDENT}" in capsys.readouterr().err


def test_running_once_launches_the_run_and_reports_no_save(here, monkeypatch, capsys):
    # `s` runs the same sequence and writes nothing, so nothing is reported as
    # written: a save it did not make is not one a person is told about.
    runner.invoke(app, ["setup"])
    asked = answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    started = record_launch(monkeypatch)
    profile = read_profile(here / "profile.yaml")

    with pytest.raises(typer.Exit) as left:
        launch_the_assembled_profile(profile, saved=False)

    said = capsys.readouterr().err

    assert left.value.exit_code == 0
    assert started["argv"][0] == "claude"
    assert "Saved to your profile" not in said
    assert asked["let_go"] == [RESIDENT]


def test_bare_offgrid_launches_what_the_screen_hands_back(here, monkeypatch):
    # The glue between the screen and the run: bare offgrid opens the picker,
    # and when a key ends it with something to run, the callback carries it out
    # after the screen is gone. `Picker.run` stands in to hand back a Departure
    # without a real keypress, since driving a real one needs a terminal a pipe
    # is not. Delete the launch in the callback and this is what fails.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    started = record_launch(monkeypatch)
    profile = read_profile(here / "profile.yaml")
    monkeypatch.setattr(
        Picker, "run", lambda self: Departure(profile=profile, saved=False)
    )

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert started["argv"][0] == "claude"


def test_a_run_key_does_nothing_where_the_runtime_did_not_answer(here, monkeypatch):
    # Nothing was read, so there is nothing to assemble: pressing a run key on
    # the error screen leaves it open and hands nothing back, rather than arming
    # a run against a machine that did not answer.
    runner.invoke(app, ["setup"])

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)

    driven = screen(here, "s")

    assert driven.still_open
    assert driven.left_with is None


def test_a_save_that_cannot_be_written_is_shown_and_the_screen_stays(here, monkeypatch):
    # A write that failed — no room, no permission — is painted where it
    # happened and the screen stays open, mirroring the read path, rather than
    # escaping into the event loop as a traceback. Nothing leaves the screen,
    # so no run is launched against a profile that was not saved.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude")

    def refuse_to_save(profile) -> None:
        raise ProfileError("Could not write the profile to /nope: it is read-only.")

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=refuse_to_save,
        sha=BUILD_SHA,
        cwd=WORKDIR,
    )
    driven = drive(picker, "tab", "tab", "enter")

    assert driven.still_open
    assert driven.left_with is None
    assert "Could not write the profile" in driven.signal


def test_where_there_is_no_profile_the_screen_measures_rather_than_refusing(
    here, monkeypatch
):
    # A stranger following the README has run no `setup`, so there is no
    # profile. What they meet is the machine measured, not an error sending them
    # to another command before they have seen anything.
    on_this_machine(monkeypatch, "claude")

    driven = fresh_screen(here)

    assert "Apple M1 Max" in driven.fits
    assert "No profile at" not in driven.fits
    assert "offgrid setup" not in driven.fits
    # The report is assembled onto what `setup` would have written, so the run
    # panel works rather than standing empty beside the measurement: the runtime
    # the default names answers, and the model it holds is priced in the signal.
    assert f"{RESIDENT} is held by lmstudio, so this costs no load" in driven.signal
    # The machine panel is its own panel above the run one, so what fits is read
    # before the run it is assembled into without either crowding the other.
    assert "Apple M1 Max" not in driven.shown


def test_where_there_is_no_profile_the_screen_says_what_fits_at_each_width(
    here, monkeypatch
):
    # The point of measuring for a stranger: what to go and download. Each width
    # a model is published at, and the budget at it.
    on_this_machine(monkeypatch, "claude")

    driven = fresh_screen(here)
    widths = [line for line in driven.fits.splitlines() if "bit" in line]

    assert [line.split("-", 1)[0].strip() for line in widths] == ["4", "8", "16"]
    assert all("parameters" in line for line in widths)


def test_the_measurement_survives_a_runtime_that_did_not_answer(here, monkeypatch):
    # Someone who has not started their runtime is exactly who wants to know
    # what fits before downloading. The budget is read off this machine, not the
    # runtime, so it stands beside the causes rather than being lost with them.
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    serve_get(monkeypatch, refuse)

    driven = fresh_screen(here)

    assert "Apple M1 Max" in driven.fits
    # Not the chip alone: what fits at each width is the payload someone without
    # a runtime came for, and it survives the runtime not answering in full.
    assert "4-bit" in driven.fits
    assert "parameters" in driven.fits
    assert "http://127.0.0.1:1234" in driven.signal
    assert driven.still_open


def test_measuring_the_machine_writes_no_profile(here, monkeypatch):
    # Nothing measured is kept: opening the screen on a fresh machine and
    # leaving writes no profile, so the measurement never quietly becomes a
    # file. Only the key that saves writes, as everywhere else.
    on_this_machine(monkeypatch, "claude")

    fresh_screen(here, "q")

    assert not (here / "profile.yaml").exists()


def test_bare_offgrid_with_no_profile_hands_the_screen_a_measurement(here, monkeypatch):
    # The wiring: the command line measures the machine and hands it in only
    # where no profile is there, so the screen a stranger opens sizes their Mac.
    sit_at_a_terminal(monkeypatch)
    on_this_machine(monkeypatch, "claude")
    opened = []
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

    runner.invoke(app, [])

    assert "Apple M1 Max" in drive(opened[0]).fits


def test_bare_offgrid_with_a_profile_still_hands_the_screen_a_measurement(
    here, monkeypatch
):
    # The machine panel shows what fits whether or not a profile is there: its
    # owner reads the same budget beside a run already assembled, so the wiring
    # measures for a file that is there as much as for one that is not.
    runner.invoke(app, ["setup"])
    sit_at_a_terminal(monkeypatch)
    opened = []
    monkeypatch.setattr(Picker, "run", lambda self: opened.append(self))

    runner.invoke(app, [])

    assert "Apple M1 Max" in drive(opened[0]).fits


def test_the_header_names_the_build_the_cwd_and_the_theme(here, monkeypatch):
    # The band above the lists says which offgrid this is, where a run would
    # operate, and how the screen looks — the three things a person arriving
    # from the README has no other way to read. The SHA and the cwd are handed
    # in, so the screen displays them without reaching a command for either.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    driven = screen(here)

    assert BUILD_SHA in driven.build
    assert WORKDIR in driven.cwd
    # The cwd line says the directory is inherited, not one offgrid sets — the
    # note a privacy-minded person reads to know offgrid does not move them.
    assert INHERITS in driven.cwd
    assert DEFAULT_THEME in driven.theme
    # The default theme is applied, not only named, so the palette a person
    # meets is the one the third line reports.
    assert driven.applied_theme == DEFAULT_THEME


def test_pressing_t_cycles_the_theme_live_and_names_it_in_the_header(here, monkeypatch):
    # The one control a person cycles live: a key moves the palette on and the
    # header's third line says which theme the screen is now drawn in. What
    # cycles is the colour, read back off the app and off the line together so
    # the name shown is the palette applied.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    opened = screen(here)
    cycled = screen(here, "t")

    assert opened.applied_theme == DEFAULT_THEME
    assert DEFAULT_THEME in opened.theme
    assert cycled.applied_theme == Theme.CATPPUCCIN_LATTE
    assert Theme.CATPPUCCIN_LATTE in cycled.theme
    assert DEFAULT_THEME not in cycled.theme


def test_cycling_past_the_last_theme_wraps_to_the_first(here, monkeypatch):
    # The cycle is a ring: stepping off the end returns to the default rather
    # than off the list. Pressing `t` once per theme lands back where it began,
    # which the `% len(Theme)` in the step is what holds — drop it and this
    # goes red on the last press.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    wrapped = screen(here, *["t"] * len(Theme))

    assert wrapped.applied_theme == DEFAULT_THEME
    assert DEFAULT_THEME in wrapped.theme


def test_cycling_from_a_loaded_theme_steps_from_where_it_opened(here, monkeypatch):
    # Cycling begins where a person left off, not at the default: a profile on
    # the third theme, then `t`, reaches the fourth. This holds that the applied
    # theme is what the step reads, so a later cycle does not jump back to the
    # first on every press.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")
    profile = here / "profile.yaml"
    profile.write_text(
        profile.read_text().replace(f"theme: {DEFAULT_THEME}", f"theme: {Theme.NORD}")
    )

    cycled = screen(here, "t")

    assert cycled.applied_theme == Theme.GRUVBOX
    assert Theme.GRUVBOX in cycled.theme


def test_the_cycled_theme_is_written_to_the_profile_when_the_run_is_saved(
    here, monkeypatch
):
    # Kept means the next open starts on it: cycling the theme and pressing the
    # key that saves writes the chosen theme, so a later run opens on it. The
    # file named the default before, so the theme it names afterwards is the
    # cycle's doing rather than what was already there.
    runner.invoke(app, ["setup"])
    answer_as_lm_studio(monkeypatch, holding={RESIDENT: SERVED})
    on_this_machine(monkeypatch, "claude")

    driven = screen(here, "t", "tab", "tab", "enter")

    assert isinstance(driven.left_with, Departure)
    assert driven.left_with.saved is True
    assert driven.left_with.profile.theme == Theme.CATPPUCCIN_LATTE
    assert read_profile(here / "profile.yaml").theme == Theme.CATPPUCCIN_LATTE


def test_the_header_opens_on_the_theme_the_profile_holds(here, monkeypatch):
    # A theme kept last time is the theme this time: the header opens naming the
    # profile's theme rather than the default, and the palette applied is that
    # one, so cycling begins where a person left off.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")
    profile = here / "profile.yaml"
    profile.write_text(
        profile.read_text().replace(f"theme: {DEFAULT_THEME}", f"theme: {Theme.NORD}")
    )

    driven = screen(here)

    assert Theme.NORD in driven.theme
    assert driven.applied_theme == Theme.NORD


def test_every_offered_theme_is_a_palette_the_screen_can_draw():
    # Theme is a profile field's vocabulary and lives in the domain, but every
    # name in it has to be one the screen can actually apply — a theme the
    # profile accepts and the screen then cannot draw is worse than no theme.
    # Held apart here, where reaching Textual is what the layer is for.
    available = set(App().available_themes)
    offered = {theme.value for theme in Theme}

    assert offered <= available, (
        f"offgrid offers themes Textual does not have: {offered - available}"
    )


A_RECOMMENDATION = Recommendation(
    models=(
        RecommendedModel(
            name="qwen3-coder-30b-a3b",
            params="30B (3B active)",
            quant="4-bit",
            quality="excellent · 92",
            context="262144",
        ),
        RecommendedModel(
            name="glm-4.6-32b",
            params="32B",
            quant="4-bit",
            quality="excellent · 90",
            context="200000",
        ),
    ),
    caption="onyx · swe_bench_verified · read today · dropped 3: 2 no size, 1 no score",
)
"""A recommendation handed to the panel as rows, so no network is reached.

Built by hand — `Quality` and `Fit` are the domain's, and the leaderboard
adapter's parse is its own seam — so the picker seam reads what it reveals
without a page being fetched or an adapter imported.
"""


@dataclass
class Revealed:
    """What the machine panel shows once the recommendation is revealed.

    :param headers: The label over each column, read from the table itself.
    :param rows: Each row of the ranked table, cell by cell.
    :param caption: The line under the table.
    :param recommending: What is shown above the table — the network sentence
        or a refusal.
    :param recommending_shown: Whether that line is on screen at all.
    :param table_shown: Whether the table itself is revealed.
    :param control_label: What the control reads as, whose triangle says
        whether the table is unfolded.
    :param fits: What the fits summary still says above the control.
    :param download: The per-runtime download instruction shown below the
        table for the highlighted row.
    :param download_shown: Whether that instruction is on screen at all.
    :param running: Whether the picker is still the screen — no modal opened.
    """

    headers: list[str]
    rows: list[list[str]]
    caption: str
    recommending: str
    recommending_shown: bool
    table_shown: bool
    control_label: str
    fits: str
    download: str
    download_shown: bool
    running: bool


def reveal(
    here, recommend_func, *after, measure=None, size=ROOMY, describe_download=None
):
    """Open the picker, press the control that recommends, and read the panel.

    The worker is waited on before the panel is read, because the fetch runs
    off the event loop so the network sentence is painted before it: a test
    reading the instant the control was used would read the sentence and call
    the table missing.

    :param here: Where the profile is.
    :param recommend_func: What the control is handed to read.
    :param after: Keys to press once the table has answered.
    :param measure: What the machine panel is handed to size this machine with,
        for the tests that read the fits summary staying above the table.
    :param size: How much terminal to give it.
    :param describe_download: What the screen is handed to say how a highlighted
        model is downloaded, for the tests that read the instruction below the
        table.

    :return: What the panel shows once the control has answered.
    """
    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        measure_func=measure,
        recommend_func=recommend_func,
        describe_download_func=describe_download,
    )

    async def driven() -> Revealed:
        async with picker.run_test(size=size) as pilot:
            await pilot.press("r")
            await picker.workers.wait_for_complete()
            await pilot.pause()

            if after:
                await pilot.press(*after)
                await picker.workers.wait_for_complete()
                await pilot.pause()

            table = picker.query_one(f"#{RANKED}", DataTable)
            recommending = picker.query_one(f"#{RECOMMENDING}", Static)
            download = picker.query_one(f"#{DOWNLOAD}", Static)

            return Revealed(
                headers=[str(column.label) for column in table.columns.values()],
                rows=[
                    [str(cell) for cell in table.get_row_at(index)]
                    for index in range(table.row_count)
                ],
                caption=str(picker.query_one(f"#{RANKED_CAPTION}", Static).content),
                recommending=str(recommending.content),
                recommending_shown=recommending.display,
                table_shown=table.display,
                control_label=str(picker.query_one(f"#{RECOMMEND}", Button).label),
                fits=str(picker.query_one(f"#{FITS}", Static).content),
                download=str(download.content),
                download_shown=download.display,
                running=picker.is_running,
            )

    return asyncio.run(driven())


def test_r_reveals_the_ranked_table_in_place_with_the_fits_summary_kept(
    here, monkeypatch
):
    # The control reveals the table on the screen a person is already on: no
    # modal, no second view. The fits summary stays above it, because the table
    # is worth most read against the machine's budget sitting over it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(
        here,
        lambda: A_RECOMMENDATION,
        measure=lambda: describe_the_machine_and_how_to_fit_more(MACHINE),
    )

    assert revealed.running
    assert revealed.table_shown
    assert "Apple M1 Max" in revealed.fits
    assert [row[0] for row in revealed.rows] == [
        "qwen3-coder-30b-a3b",
        "glm-4.6-32b",
    ]


def test_the_ranked_table_shows_the_columns_the_spec_names(here, monkeypatch):
    # model, params, quant, quality, context — with the active count named for
    # a mixture, and the listing's ceiling in the context column.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(here, lambda: A_RECOMMENDATION)

    # The headers are read from the table, not assumed, so a column reordered
    # out of step with a row's cells is caught here rather than mislabelled in
    # silence.
    assert revealed.headers == list(PANEL_COLUMNS)
    assert revealed.rows[0] == [
        "qwen3-coder-30b-a3b",
        "30B (3B active)",
        "4-bit",
        "excellent · 92",
        "262144",
    ]


def test_the_caption_names_the_list_and_what_was_dropped(here, monkeypatch):
    # Under the table, and the only words about it there: which list the figures
    # came from, the benchmark it ranks by, when it was read, and how many rows
    # each rule dropped, so a model someone expected and did not find is
    # explainable.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(here, lambda: A_RECOMMENDATION)

    assert revealed.caption == A_RECOMMENDATION.caption


def test_the_network_sentence_is_shown_before_the_fetch_not_with_its_result(
    here, monkeypatch
):
    # The headline of this control: told before it happens. The reader is held
    # on an event the test releases, so the line read while the fetch is still
    # waited on is the one painted before it. On success the sentence gives way
    # to the table, which is what says a fresh list needs no words above it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    reached = threading.Event()

    def recommend_func():
        reached.wait(timeout=5)

        return A_RECOMMENDATION

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=recommend_func,
    )

    async def driven():
        async with picker.run_test(size=ROOMY) as pilot:
            await pilot.press("r")
            await pilot.pause()

            line = picker.query_one(f"#{RECOMMENDING}", Static)
            table = picker.query_one(f"#{RANKED}", DataTable)
            before = str(line.content)
            before_rows = table.row_count

            reached.set()
            await picker.workers.wait_for_complete()
            await pilot.pause()

            return before, before_rows, table.row_count, line.display

    before, before_rows, after_rows, line_shown = asyncio.run(driven())

    assert REACHING_THE_NETWORK in before
    assert before_rows == 0
    assert after_rows == 2
    assert not line_shown


def test_a_second_press_while_the_fetch_is_in_flight_reaches_nothing(here, monkeypatch):
    # The control promises the network but once. A person pressing again before
    # the first read has answered must not start a second: the reader is held on
    # an event so both presses land while a fetch is outstanding, and only one
    # read is counted once the event is released.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    reached = threading.Event()
    calls = []

    def recommend_func():
        calls.append(1)
        reached.wait(timeout=5)

        return A_RECOMMENDATION

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=recommend_func,
    )

    async def driven():
        async with picker.run_test(size=ROOMY) as pilot:
            await pilot.press("r")
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            reached.set()
            await picker.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(driven())

    assert len(calls) == 1


def test_a_failed_fetch_keeps_the_panel_open_and_says_what_failed(here, monkeypatch):
    # A network that is not there is what a person most wants the panel to
    # survive: the sentence stays, what stopped the table is shown under it, the
    # table stays hidden, and the picker stays open so a person can start a
    # network and use the control again.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    def refuse():
        raise LeaderboardUnavailableError("Could not reach the table: no route")

    revealed = reveal(here, refuse)

    assert revealed.running
    assert not revealed.table_shown
    said = revealed.recommending
    assert REACHING_THE_NETWORK in said
    assert "Could not reach the table: no route" in said
    assert said.index(REACHING_THE_NETWORK) < said.index("Could not reach the table")


def test_nothing_is_shown_above_a_fresh_table(here, monkeypatch):
    # The network sentence gives way to the table itself, with no line left
    # above it: what the table is and how old its figures are is the caption
    # below, not a subtitle over it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(here, lambda: A_RECOMMENDATION)

    assert revealed.table_shown
    assert not revealed.recommending_shown


def test_a_failed_fetch_can_be_used_again(here, monkeypatch):
    # The refusal lifts the once-only guard, so a person who started a network
    # after the first failure reaches the table on the second press.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    calls = []

    def recommend_func():
        calls.append(1)

        if len(calls) == 1:
            raise LeaderboardUnavailableError("no route")

        return A_RECOMMENDATION

    revealed = reveal(here, recommend_func, "r")

    assert len(calls) == 2
    assert revealed.table_shown


def test_clicking_the_recommend_control_reveals_the_table(here, monkeypatch):
    # The control is a button as well as a key, so a mouse reaches it. Clicking
    # it reveals the same table the key does.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=lambda: A_RECOMMENDATION,
    )

    async def driven():
        async with picker.run_test(size=ROOMY) as pilot:
            await pilot.click(f"#{RECOMMEND}")
            await picker.workers.wait_for_complete()
            await pilot.pause()

            table = picker.query_one(f"#{RANKED}", DataTable)

            return table.display, table.row_count

    shown, rows = asyncio.run(driven())

    assert shown
    assert rows == 2


def test_a_table_taller_or_wider_than_its_box_scrolls_inside_it(here, monkeypatch):
    # A published list runs to more rows than the panel is tall and wider than
    # it is wide. The table keeps its box and scrolls within it, so a long list
    # neither pushes the caption off the screen nor is clipped without a way to
    # reach the rest.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    many = Recommendation(
        models=tuple(
            RecommendedModel(
                name=f"a-fairly-long-published-model-name-{index}",
                params="30B (3B active)",
                quant="4-bit",
                quality="excellent · 92",
                context="262144",
            )
            for index in range(15)
        ),
        caption="onyx · swe_bench_verified · read today · dropped 0",
    )

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=lambda: many,
    )

    async def driven():
        async with picker.run_test(size=ROOMY) as pilot:
            await pilot.press("r")
            await picker.workers.wait_for_complete()
            await pilot.pause()

            table = picker.query_one(f"#{RANKED}", DataTable)

            return table.show_vertical_scrollbar, table.show_horizontal_scrollbar

    down, across = asyncio.run(driven())

    assert down
    assert across


def test_opening_the_picker_and_moving_reaches_no_recommendation(here, monkeypatch):
    # Opening the picker reaches nothing, and neither does moving around it: the
    # fetch happens only when the control is used, so browsing never touches the
    # network. What proves it is that nothing but the control calls the reader.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude", "opencode")
    reached = []

    def recommend_func():
        reached.append(1)

        return A_RECOMMENDATION

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=recommend_func,
    )
    drive(picker, "tab", "down", "tab", "down", "q")

    assert reached == [], "opening the picker or moving in it reached the network"


def test_using_the_control_again_closes_the_table(here, monkeypatch):
    # The control toggles: a second use, once the table is up, closes it rather
    # than opening a second copy or reaching the network again.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(here, lambda: A_RECOMMENDATION, "r")

    assert not revealed.table_shown


def test_the_controls_triangle_turns_down_as_the_table_unfolds(here, monkeypatch):
    # The mark on the control is a disclosure triangle: it points right with the
    # table folded away and turns down as it unfolds, so the control says
    # whether the table is open the way the run panel's collapsible does.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    opened = reveal(here, lambda: A_RECOMMENDATION)
    closed = reveal(here, lambda: A_RECOMMENDATION, "r")

    assert opened.control_label == RECOMMEND_OPEN
    assert closed.control_label == RECOMMEND_CLOSED


def test_reopening_the_table_reads_from_what_was_kept(here, monkeypatch):
    # The read is kept, so showing and hiding the table costs one fetch: opening
    # it again after closing it reads from what was kept, not the wire. The
    # reader is called the once across open, close, open.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")
    reached = []

    def recommend_func():
        reached.append(1)

        return A_RECOMMENDATION

    revealed = reveal(here, recommend_func, "r", "r")

    assert reached == [1]
    assert revealed.table_shown


def test_highlighting_a_ranked_row_shows_that_models_download_instruction(
    here, monkeypatch
):
    # Revealing the table lands the highlight on the best row, and its
    # per-runtime download instruction is shown below the table. The instruction
    # is handed in, so the screen reaches no runtime adapter to say how.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(
        here,
        lambda: A_RECOMMENDATION,
        describe_download=lambda name: f"To download {name}, run `get {name}`.",
    )

    name = "qwen3-coder-30b-a3b"

    assert revealed.download_shown
    assert revealed.download == f"To download {name}, run `get {name}`."


def test_moving_the_ranked_highlight_shows_the_new_models_instruction(
    here, monkeypatch
):
    # The instruction follows the highlight: arrow keys move down the table and
    # the instruction is the next model's, which is what surfacing on highlight
    # means — a mouse click, the arrows and enter all move the highlight alike.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(
        here,
        lambda: A_RECOMMENDATION,
        "down",
        describe_download=lambda name: f"how to get {name}",
    )

    assert revealed.download == "how to get glm-4.6-32b"


def test_the_download_instruction_is_on_screen_and_not_below_the_panel(
    here, monkeypatch
):
    # Showing it in the DOM is not showing it to a person: the panel stands
    # taller than its half-column, so without scrolling the instruction into
    # view it is drawn past the panel's foot and off the screen. A short
    # terminal is where that bites, so it is where this reads the region.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        measure_func=lambda: tuple(f"fits line {index}" for index in range(6)),
        recommend_func=lambda: A_RECOMMENDATION,
        describe_download_func=lambda name: f"To download {name}:\n- search\n- get it",
    )

    async def driven() -> tuple[bool, bool, str]:
        async with picker.run_test(size=(100, 24)) as pilot:
            await pilot.press("r")
            await picker.workers.wait_for_complete()
            await pilot.pause()

            panel = picker.query_one(f"#{DOWNLOAD}", Static)

            return (
                picker.screen.region.contains_region(panel.region),
                panel.display,
                str(panel.content),
            )

    on_screen, shown, content = asyncio.run(driven())

    # A hidden panel has a zero-size region the screen trivially contains, so
    # reading the region alone would pass while the instruction shows nothing.
    # It has to be displayed and say something for its position to mean it.
    assert shown, "the download panel is not displayed"
    assert content, "the download panel says nothing"
    assert on_screen, "the download instruction is off the screen"


def test_clicking_a_ranked_row_shows_that_models_download_instruction(
    here, monkeypatch
):
    # The other arm the criterion names: a mouse click on a row surfaces the
    # instruction as the arrow keys do, since both move the highlight the one
    # handler answers to.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    picker = Picker(
        read_report_func=lambda: read_what_could_be_run(here / "profile.yaml"),
        save_func=lambda profile: save_profile(profile, here / "profile.yaml"),
        sha=BUILD_SHA,
        cwd=WORKDIR,
        recommend_func=lambda: A_RECOMMENDATION,
        describe_download_func=lambda name: f"how to get {name}",
    )

    async def driven() -> tuple[str, str]:
        async with picker.run_test(size=ROOMY) as pilot:
            await pilot.press("r")
            await picker.workers.wait_for_complete()
            await pilot.pause()

            # Click into the table rather than at a row the layout might have
            # moved: whichever row the click lands on, the instruction shown is
            # that row's, which is what the mouse arm has to guarantee.
            await pilot.click(f"#{RANKED}", offset=(5, 2))
            await pilot.pause()

            table = picker.query_one(f"#{RANKED}", DataTable)
            landed = str(table.get_row_at(table.cursor_row)[0])
            shown = str(picker.query_one(f"#{DOWNLOAD}", Static).content)

            return landed, shown

    landed, shown = asyncio.run(driven())

    assert shown == f"how to get {landed}"


def test_the_download_instruction_is_the_runtimes_own_words(here, monkeypatch):
    # What the runtime said is shown as it wrote it, line for line: a command a
    # person copies must survive being shown, so the screen does not reflow it.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    said = (
        "To download qwen3-coder-30b-a3b, either:\n"
        "- search it\n"
        "- run `lms get qwen3-coder-30b-a3b`"
    )

    revealed = reveal(here, lambda: A_RECOMMENDATION, describe_download=lambda _: said)

    assert revealed.download == said


def test_collapsing_the_table_clears_the_download_instruction(here, monkeypatch):
    # The instruction belongs to the open table: closing the table with a second
    # press clears the instruction along with it, so nothing about a model is
    # left below a table that is no longer on the screen.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")

    revealed = reveal(
        here,
        lambda: A_RECOMMENDATION,
        "r",
        describe_download=lambda name: f"how to get {name}",
    )

    assert not revealed.download_shown
    assert revealed.download == ""
