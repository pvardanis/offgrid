"""What bare `offgrid` opens, and what a person reads on it.

The seam is the screen: the lists it shows, the report beside them, and what
each key does. No frame snapshots — they break on every cosmetic change and
pass on wrong content, which is the inverse of asserting on the message a
person reads.
"""

import asyncio
from dataclasses import dataclass

import httpx
import pytest
import typer
from rich.cells import cell_len
from textual.containers import VerticalScroll
from textual.widgets import OptionList, Select, Static
from textual.widgets._footer import FooterKey
from textual.widgets._select import SelectOverlay
from typer.testing import CliRunner

from offgrid.agents.claude_code.launching import CONTEXT_FLOOR
from offgrid.cli import app
from offgrid.cli.binding import read_profile, read_what_could_be_run
from offgrid.cli.run import launch_the_assembled_profile
from offgrid.domain.assembling import IN_MEMORY
from offgrid.domain.costing import RUNNING
from offgrid.domain.profile import save_profile
from offgrid.domain.running import discarded_windows
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.discarded_windows import save_discarded_window
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import ProfileError
from offgrid.tui.dropdown import Dropdown
from offgrid.tui.picker import (
    AGENTS,
    CHANGED,
    COLUMNS,
    MODELS,
    PANE,
    REPORT,
    RUNTIMES,
    STATUS,
    UNCHANGED,
    WRITES,
    Departure,
    Picker,
)
from tests.doubles import serve_get
from tests.launches import record_launch
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
    columns: str
    status: str
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
                columns=str(picker.query_one(f"#{COLUMNS}", Static).content),
                status=str(picker.query_one(f"#{STATUS}", Static).content),
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
        identifier=RESIDENT,
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

    assert f"{RESIDENT} is held, so this costs no load" in opened.shown
    assert "google/gemma-4-e4b is not held, so this costs a load" in moved.shown
    assert "model              google/gemma-4-e4b" in moved.shown
    assert "  context_ceiling  262144" in moved.shown


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
    assert f"model              {RESIDENT}" in driven.shown
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

    assert "model              google/gemma-4-e4b" in driven.shown
    assert "  context_window   unknown" in driven.shown


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
    assert f"model              {RESIDENT}" in driven.shown


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
    assert "agent              claude-code, speaking anthropic" in opened.shown
    assert "agent              opencode, speaking openai" in moved.shown

    # Where its conversations land is read off the highlighted agent's own
    # config, so it says the report was assembled from that agent rather than
    # from the one the profile names.
    assert str(here / "claude-code") in opened.shown
    assert str(here / "opencode") in moved.shown


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
    assert "agent              claude-code, speaking anthropic" in hovered.shown
    assert "opencode, speaking openai" not in hovered.shown


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

    assert "refused, and a load would not be reached" not in opened.shown
    assert "running            refused, and a load would not be reached" in moved.shown
    assert "the anthropic API and the agent expects openai" in " ".join(
        moved.shown.split()
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
    flowed = " ".join(driven.shown.split())

    assert "running            refused, and a load would not be reached" in driven.shown
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

    assert "  command          claude, not on PATH" in driven.shown
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

    assert "requests           google/gemma-4-e4b" in driven.shown
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

    assert "agent              claude-code, which did not answer" in driven.shown
    assert "settings.json" in driven.shown
    assert "runtime            lmstudio at 127.0.0.1:1234, reachable" in driven.shown
    assert "  dialects         anthropic, openai" in driven.shown


def test_a_window_offgrid_stopped_asking_for_is_said_on_the_screen(here, monkeypatch):
    # The remedy is a file to delete, and the screen is where somebody looks
    # when a run is not the size they asked for.
    runner.invoke(app, ["setup"])
    on_this_machine(monkeypatch, "claude")
    record_a_discarded_window(here)

    driven = screen(here)

    assert "discarded          131072 was asked for on" in driven.shown
    assert "to ask again" in driven.shown


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

    asks_for_nothing = (
        "requests           asks for nothing, so a run takes whatever is held"
    )

    assert str(opened.highlighted[MODELS]).startswith(RESIDENT)
    assert asks_for_nothing in opened.shown
    assert "requests           google/gemma-4-e4b" in moved.shown


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
    assert "requests           someone/a-model-that-was-deleted" in driven.shown
    assert "has not got someone/a-model-that-was-deleted" in driven.shown
    assert f"{RESIDENT} is held" not in driven.shown


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

    assert "at 65536" in driven.shown


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

    assert "runtime            lmstudio at 127.0.0.1:1234, reachable" in shown
    assert "  dialects         anthropic, openai" in shown
    assert f"model              {RESIDENT}" in shown
    assert "  context_ceiling  262144" in shown
    assert "  context_window   212224" in shown
    assert (
        "requests           asks for nothing, so a run takes whatever is held" in shown
    )
    assert "agent              claude-code, speaking anthropic" in shown
    assert "  command          claude, not on PATH" in shown
    assert f"  context_minimum  {CONTEXT_FLOOR}" in shown
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

    monkeypatch.setattr("offgrid.cli.run.read_what_could_be_run", lambda path: crash())

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
    )
    driven = drive(picker, "tab", "tab", "enter")

    assert driven.still_open
    assert driven.left_with is None
    assert "Could not write the profile" in driven.shown
