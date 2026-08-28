"""What a run would report, on a screen that leaves everything as it is.

Two dropdowns — the runtimes offgrid drives and the agents it drives — and a
list of the models the runtime has downloaded, with the report `doctor` prints
beside them, taken from the same place so that two surfaces cannot word one
fact differently. It is recomputed as the pick changes, out of what was read
when the screen opened: moving reaches nothing and writes nothing.

What offgrid supports is offered whether or not this machine has it. A choice
it cannot start is greyed and the cursor steps over it, which is the widget's
guarantee rather than a refusal somebody has to remember to write.

The screen reads; nothing on it writes.
"""

from collections.abc import Callable
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, OptionList, Select, Static
from textual.widgets.option_list import Option

from offgrid.domain.assembling import (
    WhatCouldBeRun,
    describe_a_model_row,
    describe_an_agent_row,
    find_what_would_answer,
    name_the_model_columns,
    open_on_what_the_profile_holds,
    order_models_held_first,
    read_the_highlight,
)
from offgrid.domain.costing import describe_what_would_run
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import OffgridError
from offgrid.tui.dropdown import Dropdown

type ReadWhatCouldBeRun = Callable[[], WhatCouldBeRun]

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

RUNTIMES = "runtimes"
AGENTS = "agents"
MODELS = "models"

NOTHING_DOWNLOADED = "the runtime has nothing downloaded"
"""What stands in the models list where a runtime has no models at all.

A list with a row in it saying so, rather than an empty box: an empty box is
read as offgrid having failed to ask. Disabled, because it is a sentence rather
than something to pick.
"""


class Picker(App[None]):
    """Two dropdowns and a models list, and the report for what is picked.

    Textual's own bindings are left as they are — `ctrl+q` leaves, `ctrl+c`
    does not and says which key does, `ctrl+p` opens the command palette — so
    that the only thing to learn here is the one key this adds. It is the only
    binding of its own the `Footer` shows; `ctrl+p` appears beside it, which
    Textual puts there itself rather than reading off a binding.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("q", "quit", "leave")]

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
    """

    def __init__(self, read_report_func: ReadWhatCouldBeRun) -> None:
        """Take what the screen will show, rather than reaching for it.

        The profile, the runtime and the agents are read by whoever opened the
        screen, which is what keeps the picker clear of every registry.

        :param read_report_func: What the profile, the runtime and the agents answer.
        """
        super().__init__()

        self._read_report_func = read_report_func
        self._report: WhatCouldBeRun | None = None

    def compose(self) -> ComposeResult:
        """Build the screen: the dropdowns, the models list, the report beside.

        :yield: Each widget, in the order they are read across the screen.
        """
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
        yield Footer()

    def on_mount(self) -> None:
        """Read once the screen is up, so that a refusal is shown on it.

        Reading in the constructor would raise before there is anywhere to say
        so, and a runtime nothing answered for is exactly what somebody opened
        this to find out about.
        """
        self.query_one(f"#{RUNTIME_BOX}", Vertical).border_title = "runtime"
        self.query_one(f"#{AGENT_BOX}", Vertical).border_title = "agent"
        self.query_one(f"#{MODEL_BOX}", Vertical).border_title = MODELS

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

    def _fill_the_lists(self, report: WhatCouldBeRun) -> None:
        """Put what offgrid drives, and what this machine has, into the screen.

        The models highlight is left where the profile points, and each dropdown
        opens on what a run would do today rather than on whatever sorts first.

        :param report: Everything that was read.
        """
        self._get_list().add_options(self._get_model_options(report))
        self._highlight_model(report)

        # Only the profile's runtime has a config to be assembled from, so every
        # other one offgrid drives is greyed until that stops being true.
        runtime = report.profile.runtime_name

        self._get_dropdown(RUNTIMES).offer(
            [(name.value, name.value) for name in RuntimeName],
            unavailable=frozenset(
                name.value for name in RuntimeName if name != runtime
            ),
        )
        self._get_dropdown(RUNTIMES).value = report.profile.runtime_name.value

        self._get_dropdown(AGENTS).offer(
            [
                (describe_an_agent_row(agent), agent.name.value)
                for agent in report.agents
            ],
            unavailable=frozenset(
                agent.name.value
                for agent in report.agents
                if not agent.is_on_this_machine
            ),
        )

        opens_on = self._agent_to_open_on(report)

        if opens_on is not None:
            self._get_dropdown(AGENTS).value = opens_on

    def _agent_to_open_on(self, report: WhatCouldBeRun) -> str | None:
        """Say which agent a dropdown opens on, which the profile's may not be.

        An agent this machine has not got is greyed and cannot be the value, so
        the dropdown opens on the first one it can reach — something has to be
        reported on, and the rest of the list is what there is. Where none can
        be reached there is nothing to open on, and the report falls back on the
        agent the profile names.

        :param report: Everything that was read.

        :return: The agent to open on, or ``None`` where none can be reached.
        """
        reachable = [
            agent.name.value for agent in report.agents if agent.is_on_this_machine
        ]

        if not reachable:
            return None

        wanted = report.profile.agent_name.value

        return wanted if wanted in reachable else reachable[0]

    def _get_model_options(self, report: WhatCouldBeRun) -> list[Option]:
        """Lay out a row per model downloaded, held ones first.

        :param report: Everything that was read.

        :return: The rows, or the one saying there are none.
        """
        if not report.downloaded_models:
            return [Option(NOTHING_DOWNLOADED, disabled=True)]

        return [
            Option(
                describe_a_model_row(model, held=model.identifier in report.held),
                id=model.identifier,
            )
            for model in order_models_held_first(report)
        ]

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
        """Show the report for whatever is picked."""
        report = self._report

        if report is None:
            return

        pairing = read_the_highlight(
            report,
            agent=self._get_picked_agent(),
            model=self._get_highlighted_model(),
        )

        self._say("\n".join(describe_what_would_run(report, pairing)))

    def _say(self, said: str) -> None:
        """Put text in the report pane.

        :param said: What to show there.
        """
        self.query_one(f"#{REPORT}", Static).update(said)
