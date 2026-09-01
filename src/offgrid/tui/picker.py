"""What a run would report, and the two keys that end the session.

Two dropdowns — the runtimes offgrid drives and the agents it drives — and a
list of the models the runtime has downloaded, with the report `doctor` prints
beside them, taken from the same place so that two surfaces cannot word one
fact differently. It is recomputed as the pick changes, out of what was read
when the screen opened: moving reaches nothing and writes nothing.

What offgrid supports is offered whether or not this machine has it. A choice
it cannot start is greyed and the cursor steps over it, which is the widget's
guarantee rather than a refusal somebody has to remember to write.

Browsing writes nothing. Only the key that ends the session writes, and only
the one that saves: it hands the assembled profile to the writer it was given,
and exits with what to run. The screen never holds a model itself.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, OptionList, Select, Static

from offgrid.domain.assembling import (
    Pairing,
    WhatCouldBeRun,
    assemble_a_profile,
    find_what_would_answer,
    name_the_model_columns,
    open_on_what_the_profile_holds,
    read_the_highlight,
)
from offgrid.domain.costing import describe_what_would_run
from offgrid.domain.profile import Profile
from offgrid.shared.exceptions import OffgridError
from offgrid.tui.choices import Choices, agent_choices, model_options, runtime_choices
from offgrid.tui.dropdown import Dropdown
from offgrid.tui.header import HeaderBand
from offgrid.tui.published_list import PublishedList, ReadWhatAListRecommends

type ReadWhatCouldBeRun = Callable[[], WhatCouldBeRun]
type SaveWhatWasAssembled = Callable[[Profile], None]
type MeasureThisMachine = Callable[[], tuple[str, ...]]

DEFAULT_THEME = "catppuccin-mocha"
"""The theme the screen opens in, settled against the prototype.

Applied on open and named in the header. There is no key to change it, so the
one theme is both what the screen is drawn in and what the header names.
"""


@dataclass(frozen=True)
class Departure:
    """What a person assembled, and how they chose to leave the screen with it.

    Handed back to whoever opened the screen, which carries out the run in the
    plain lines a run is read in. The screen never holds a model itself; this
    is the wish it exits with.

    :param profile: What was assembled — runtime, agent and model — as a run is
        made from it.
    :param saved: Whether the key that writes was the one pressed, which is what
        the report of the save is about. A past fact rather than a request: the
        file is already written by the time this is handed back, and this says
        whether to say so.
    """

    profile: Profile
    saved: bool


REPORT = "report"
"""Where the report is shown, which is what a test reads it back from."""

PANE = "pane"
"""What the report scrolls inside, since it is as long as the machine makes it."""

LISTS = "lists"
"""What the two dropdowns and the models list are stacked in."""

RUNTIME_BOX = "runtime-box"
"""The titled box the runtime dropdown sits in."""

AGENT_BOX = "agent-box"
"""The titled box the agent dropdown sits in."""

MODEL_BOX = "model-box"
"""What the models list and the names of its columns share a border with."""

COLUMNS = "columns"
"""Where the names of the model list's columns are shown.

Above the list rather than a row in it, so that it stays where it is when a
machine with a shelf full of models scrolls.
"""

STATUS = "status"
"""Where it is said which key writes, and whether a run would change anything.

A line of its own above the footer's key hints. `enter` runs both a `Select`
and an `OptionList` themselves before the app is reached, so Textual's `Footer`
never shows its hint while either has the focus — which is always here. Which
key writes is said here instead, beside the one fact the footer could not carry
anyway: whether what is assembled is still what the file holds, which is
rewritten as the highlight moves.
"""

RUNTIMES = "runtimes"
AGENTS = "agents"
MODELS = "models"

WRITES = "enter runs and saves · s runs once"
"""What the status says about which key writes, before either is pressed.

So that a person coming from Claude Code, where the same keys mean the same
things, sees the consequence on screen rather than trusting the reflex.
"""

CHANGED = "changed from your saved profile"
"""What the status says when what is assembled is not what the file holds.

So that a person about to press the key that writes can see the write would
change something, rather than remember whether they moved anything.
"""

UNCHANGED = "this is your saved profile"
"""What the status says when what is assembled is exactly what the file holds."""


class Picker(App[Departure | None]):
    """Two dropdowns and a models list, and the report for what is picked.

    Three keys end a session, keyed to match Claude Code's model picker: `enter`
    runs with what is assembled and saves it, `s` runs with it once, `q` leaves
    having changed nothing. `r` opens the published list, which is the one thing
    the picker does that reaches the network, and does not end the session.
    Textual's own bindings are left as they are — `ctrl+q` leaves, `ctrl+c` does
    not and says which key does, `ctrl+p` opens the command palette — so that
    the only things to learn are the ones this adds.

    `enter` is answered on the models list rather than reached at the app,
    because a `Select` or an `OptionList` with the focus consumes `enter` itself
    before the app is: selecting a model is what runs when the list has the keys.
    `s` reaches the app from either. Which key writes is said on the status line
    rather than in the `Footer`, since the `Footer` never carries a hint for a
    key the focused widget has taken — `s` and `q` are what it shows.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "run_and_save", "run and save"),
        Binding("s", "run_once", "run once"),
        Binding("r", "recommend", "recommend"),
        Binding("q", "quit", "leave"),
    ]

    CSS = f"""
    #{LISTS} {{
        width: 44;
    }}

    .box {{
        border: round $panel;
        /* On the box rather than on the widget inside it, so that a heading and
           what it is over are one surface: a heading left transparent paints
           the screen behind it and reads as a second box. */
        background: $surface;
        /* A title drawn in the border colour is as faint as the border, and
           these three are what say which box a person is looking at. */
        border-title-color: $text;
        border-title-style: bold;
        border-title-align: left;
    }}

    /* Which box has the keys is worth seeing, with three of them on screen and
       every one of them answering to the same arrows. */
    .box:focus-within {{
        border: round $accent;
        border-title-color: $accent;
    }}

    /* The dropdowns are as tall as their one line; the models list takes the
       rest. */
    .box.pick {{
        height: auto;
    }}

    .box.pick > Select {{
        border: none;
        background: $surface;
    }}

    #{MODEL_BOX} {{
        height: 1fr;
    }}

    #{MODEL_BOX} > OptionList {{
        height: 1fr;
        border: none;
        background: $surface;
    }}

    #{COLUMNS} {{
        color: $text-muted;
        padding: 0 1;
    }}

    #{PANE} {{
        width: 1fr;
    }}

    #{STATUS} {{
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }}
    """

    def __init__(
        self,
        read_report_func: ReadWhatCouldBeRun,
        save_func: SaveWhatWasAssembled,
        *,
        sha: str,
        cwd: str,
        measure_func: MeasureThisMachine | None = None,
        recommend_func: ReadWhatAListRecommends | None = None,
    ) -> None:
        """Take what the screen will show and how it saves, rather than reaching.

        The profile, the runtime and the agents are read by whoever opened the
        screen, and writing the assembled profile back is theirs too, which is
        what keeps the picker clear of every registry and of where the file is
        kept. The SHA and the cwd the header shows are read the same way — a
        string and a path the screen only displays, so it reaches no command,
        registry or adapter to learn them.

        :param read_report_func: What the profile, the runtime and the agents answer.
        :param save_func: What writes an assembled profile where a later run
            finds it.
        :param sha: The git SHA naming which offgrid checkout this is, shown in
            the header.
        :param cwd: The working directory a run would inherit, shown in the
            header. offgrid displays it; the agent inherits the shell's cwd, and
            offgrid does not set it.
        :param measure_func: What this machine and what fits it read as, handed
            in where there is no profile so that a stranger meets the machine
            measured rather than an error naming another command. ``None`` where
            a profile is there, since the machine's budget is not what somebody
            with a run already assembled came to read.
        :param recommend_func: What reads a published list and lays it out, for
            the key that reaches the network. ``None`` leaves that key with
            nothing to fetch, which is what a test that is not about it hands in.
        """
        super().__init__()

        self._read_report_func = read_report_func
        self._save_func = save_func
        self._sha = sha
        self._cwd = cwd
        self._measure_func = measure_func
        self._recommend_func = recommend_func
        self._report: WhatCouldBeRun | None = None
        self._measurement: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        """Build the screen: the dropdowns, the models list, the report beside.

        :yield: Each widget, in the order they are read across the screen.
        """
        # The band above the lists: which offgrid this is, where a run would
        # operate, and the theme. What it shows was handed in, so it reaches
        # nothing.
        yield HeaderBand(sha=self._sha, cwd=self._cwd, theme=DEFAULT_THEME)

        # The report is inside something that scrolls, because it is as long as
        # the machine makes it: a discarded window, a long path to the agent, or
        # a narrow terminal each push the last lines past the bottom. Those
        # lines are the remedies, which is what a person opened this to read.
        #
        # Read as plain text, because what it shows is columns and refusals.
        # A refusal carries the key it refused the way pydantic writes one,
        # in square brackets, which a screen reading markup takes for markup
        # and stops on — leaving nowhere to say what was wrong with the file.
        yield Horizontal(
            Vertical(
                Vertical(Dropdown(id=RUNTIMES), id=RUNTIME_BOX, classes="box pick"),
                Vertical(Dropdown(id=AGENTS), id=AGENT_BOX, classes="box pick"),
                # The models are the one list whose rows carry a column a reader
                # cannot name from what is in it, so they are the one list with
                # its columns named above them.
                Vertical(
                    Static(name_the_model_columns(), id=COLUMNS, markup=False),
                    OptionList(id=MODELS),
                    id=MODEL_BOX,
                    classes="box",
                ),
                id=LISTS,
            ),
            VerticalScroll(Static(id=REPORT, markup=False), id=PANE),
        )
        yield Static(id=STATUS, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Read once the screen is up, so that a refusal is shown on it.

        Reading in the constructor would raise before there is anywhere to say
        so, and a runtime nothing answered for is exactly what somebody opened
        this to find out about.
        """
        # Applied here, once the app is up, so the palette the header names is
        # the one the screen is actually drawn in.
        self.theme = DEFAULT_THEME

        self.query_one(f"#{RUNTIME_BOX}", Vertical).border_title = "runtime"
        self.query_one(f"#{AGENT_BOX}", Vertical).border_title = "agent"
        self.query_one(f"#{MODEL_BOX}", Vertical).border_title = MODELS

        # Measured first and kept, so it is shown above whatever the report turns
        # out to be — the machine's budget survives a runtime that did not
        # answer, which is exactly the machine a stranger opened this to size.
        self._measurement = self._measure()

        try:
            report = self._read_report_func()
        except OffgridError as error:
            self._say(str(error))

            return

        self._report = report
        self._fill_the_lists(report)
        self._say_what_would_run()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Report on whatever is now picked.

        :param event: That a dropdown's value changed. Which one, and to what,
            is read off the dropdowns themselves.
        """
        self._say_what_would_run()

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Report on whatever the model highlight is now on.

        :param event: That the models list moved, which is what wakes this.
        """
        self._say_what_would_run()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Run and save when a model row is chosen, which `enter` on it is.

        The models list has the focus and consumes `enter` before the app is
        reached, so selecting a row is where `enter` runs. A disabled row emits
        nothing, so the row that says nothing is downloaded cannot arm a run.

        :param event: That a model row was chosen, which wakes this.
        """
        self.action_run_and_save()

    def action_run_and_save(self) -> None:
        """Leave to run with what is assembled, having saved it as remembered."""
        assembled = self._assemble()

        if assembled is None:
            return

        try:
            self._save_func(assembled)
        except OffgridError as error:
            # Mirrors the read path in `on_mount`: a write that failed — no room,
            # no permission, a path that is a file — is painted where it happened
            # and the screen stays open, rather than escaping into the event loop
            # as a traceback nothing here would turn into a sentence.
            self._say(str(error))

            return

        self.exit(Departure(profile=assembled, saved=True))

    def action_run_once(self) -> None:
        """Leave to run with what is assembled, writing nothing."""
        assembled = self._assemble()

        if assembled is None:
            return

        self.exit(Departure(profile=assembled, saved=False))

    def action_recommend(self) -> None:
        """Open the published list, which is what reaches the network.

        The one key here that touches the network, and only when it is pressed.
        Nothing happens where no reader was handed in: a screen with nothing to
        fetch is a key that opens onto a blank list, so the key does nothing
        instead.
        """
        if self._recommend_func is None:
            return

        self.push_screen(PublishedList(self._recommend_func))

    def _assemble(self) -> Profile | None:
        """Write what the highlights are on into the profile a run is made from.

        :return: The assembled profile, or ``None`` where nothing was read for
            the screen to assemble — a runtime that did not answer, or a profile
            that would not load.
        """
        report = self._report

        if report is None:
            return None

        return assemble_a_profile(report, self._read_the_highlights(report))

    def _fill_the_lists(self, report: WhatCouldBeRun) -> None:
        """Put what offgrid drives, and what this machine has, into the screen.

        What each list offers is worked out in `choices`; this puts it on the
        widgets. The models highlight is left where the profile points, and each
        dropdown opens on what a run would do today rather than on whatever sorts
        first.

        :param report: Everything that was read.
        """
        self._get_list().add_options(model_options(report))
        self._highlight_model(report)

        self._offer(RUNTIMES, runtime_choices(report))
        self._offer(AGENTS, agent_choices(report))

    def _offer(self, which: str, choices: Choices) -> None:
        """Put what a dropdown offers onto it, and open it on the right value.

        :param which: The dropdown to fill.
        :param choices: What it offers, and what to open on.
        """
        dropdown = self._get_dropdown(which)

        dropdown.offer(choices.options, unavailable=choices.unavailable)

        if choices.opens_on is not None:
            dropdown.value = choices.opens_on

    def _highlight_model(self, report: WhatCouldBeRun) -> None:
        """Put the models highlight on the row the profile points at.

        A value naming no row gets no substitute: a profile naming a model the
        runtime has not got is a thing to say, and moving the highlight quietly
        onto another model would answer with a report about a run nobody asked
        for.

        :param report: Everything that was read.
        """
        listed = self._get_list()
        wanted = find_what_would_answer(report, open_on_what_the_profile_holds(report))
        rows = list(enumerate(listed.options))
        reachable = [index for index, option in rows if not option.disabled]
        found = [index for index, option in rows if option.id == wanted]

        if not reachable or (wanted is not None and not found):
            return

        listed.highlighted = next(
            (index for index in found if index in reachable), reachable[0]
        )

    def _get_highlighted_model(self) -> str | None:
        """Say what the models highlight is on.

        :return: What that row is identified by, or ``None`` where the list has
            no reachable row at all — nothing downloaded.
        """
        listed = self._get_list()
        index = listed.highlighted

        if index is None:
            return None

        return listed.get_option_at_index(index).id

    def _get_picked_agent(self) -> str | None:
        """Say which agent is picked, which may be none where all are greyed.

        :return: The agent's name, or ``None`` where none can be reached.
        """
        value = self._get_dropdown(AGENTS).value

        return None if value is Select.NULL else str(value)

    def _get_dropdown(self, which: str) -> Dropdown:
        """Reach one of the two dropdowns.

        :param which: Which one.

        :return: The widget.
        """
        return self.query_one(f"#{which}", Dropdown)

    def _get_list(self) -> OptionList:
        """Reach the models list, the one list left on the screen.

        :return: The widget.
        """
        return self.query_one(f"#{MODELS}", OptionList)

    def _say_what_would_run(self) -> None:
        """Show the report for whatever is picked, and whether it differs."""
        report = self._report

        if report is None:
            return

        pairing = self._read_the_highlights(report)

        self._say("\n".join(describe_what_would_run(report, pairing)))
        self._say_whether_it_differs(report, pairing)

    def _read_the_highlights(self, report: WhatCouldBeRun) -> Pairing:
        """Read what the two highlights are sitting on as one pairing.

        :param report: Everything that was read.

        :return: The agent and model a run would be assembled from.
        """
        return read_the_highlight(
            report,
            agent=self._get_picked_agent(),
            model=self._get_highlighted_model(),
        )

    def _say_whether_it_differs(self, report: WhatCouldBeRun, pairing: Pairing) -> None:
        """Say whether what is assembled is what the file already holds.

        So that a person can see whether the key that writes would change
        anything, rather than remember what they moved.

        :param report: Everything that was read.
        :param pairing: What the highlights are on.
        """
        assembled = assemble_a_profile(report, pairing)
        differs = assembled != report.profile

        self.query_one(f"#{STATUS}", Static).update(
            f"{WRITES} · {CHANGED if differs else UNCHANGED}"
        )

    def _measure(self) -> tuple[str, ...]:
        """Read this machine, where a fresh one was handed a way to.

        :return: The measurement's lines, or none where a profile was there and
            no measurement was handed in. A machine offgrid cannot size — not an
            Apple Silicon Mac — is the one line saying so rather than a blank
            pane, since that too is worth reading above the report.
        """
        if self._measure_func is None:
            return ()

        try:
            return self._measure_func()
        except OffgridError as error:
            return (str(error),)

    def _say(self, said: str) -> None:
        """Put text in the report pane, under the measurement where there is one.

        :param said: What to show there.
        """
        shown = "\n".join((*self._measurement, "", said)) if self._measurement else said

        self.query_one(f"#{REPORT}", Static).update(shown)
