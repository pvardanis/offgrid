"""What a run would report, on a screen that leaves everything as it is.

Three lists — the runtimes offgrid drives, the agents it drives, and the models
the runtime has downloaded — and beside them the report `doctor` prints, taken
from the same place, so that two surfaces cannot word one fact differently. It
is recomputed as the highlight moves, out of what was read when the screen
opened: moving reaches nothing and writes nothing.

What offgrid supports is listed whether or not this machine has it. A row it
cannot start is marked and the cursor steps over it, which is the widget's
guarantee rather than a refusal somebody has to remember to write.

Nothing here can be run or saved yet.
"""

from collections.abc import Callable
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from offgrid.domain.assembling import (
    WhatCouldBeRun,
    describe_a_model_row,
    describe_an_agent_row,
    describe_what_would_run,
    find_what_would_answer,
    open_on_what_the_profile_holds,
    order_models_held_first,
    read_the_highlight,
)
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import OffgridError

type ReadWhatCouldBeRun = Callable[[], WhatCouldBeRun]

REPORT = "report"
"""Where the report is shown, which is what a test reads it back from."""

PANE = "pane"
"""What the report scrolls inside, since it is as long as the machine makes it."""

LISTS = "lists"
"""What the three lists are stacked in."""

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
    """Three lists and the report for whatever the highlight is on.

    Textual's own bindings are left as they are — `ctrl+q` leaves, `ctrl+c`
    does not and says which key does, `ctrl+p` opens the command palette — so
    that the only thing to learn here is the one key this adds. It is also the
    only one the `Footer` shows, since the rest declare themselves hidden.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("q", "quit", "leave")]

    CSS = f"""
    #{LISTS} {{
        width: 34;
    }}

    #{LISTS} OptionList {{
        height: 1fr;
        border: round $panel;
    }}

    #{PANE} {{
        width: 1fr;
    }}
    """

    def __init__(self, read: ReadWhatCouldBeRun) -> None:
        """Take what the screen will show, rather than reaching for it.

        The profile, the runtime and the agents are read by whoever opened the
        screen, which is what keeps the picker clear of every registry.

        :param read: What the profile, the runtime and the agents answer.
        """
        super().__init__()

        self._read = read
        self._what: WhatCouldBeRun | None = None

    def compose(self) -> ComposeResult:
        """Build the screen: the lists, the report beside them, the keys under.

        :yield: Each widget, in the order they are read across the screen.
        """
        # The report is inside something that scrolls, because it is as long as
        # the machine makes it: a discarded window, a long path to the agent, or
        # a narrow terminal each push the last lines past the bottom. Those
        # lines are the remedies, which is what a person opened this to read.
        # A bare `Static` cannot take focus, so no key would reach them.
        #
        # Read as plain text, because what it shows is columns and refusals.
        # A refusal carries the key it refused the way pydantic writes one,
        # in square brackets, which a screen reading markup takes for markup
        # and stops on — leaving nowhere to say what was wrong with the file.
        yield Horizontal(
            Vertical(
                OptionList(id=RUNTIMES),
                OptionList(id=AGENTS),
                OptionList(id=MODELS),
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
        for which in (RUNTIMES, AGENTS, MODELS):
            self._list(which).border_title = which

        try:
            what = self._read()
        except OffgridError as error:
            self._say(str(error))

            return

        self._fill_the_lists(what)
        self._what = what
        self._say_what_would_run()

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Report on whatever the highlight has landed on.

        :param event: Which list moved, and onto what.
        """
        self._say_what_would_run()

    def _fill_the_lists(self, what: WhatCouldBeRun) -> None:
        """Put what offgrid drives, and what this machine has, into the lists.

        The highlight is left where the profile points: the first thing shown
        is what a run would do today, rather than whatever happens to sort
        first.

        :param what: Everything that was read.
        """
        # Every runtime offgrid has an adapter for. Only the profile's has a
        # config to be assembled from, and there is one, so nothing else can be
        # highlighted for as long as that stays true.
        self._list(RUNTIMES).add_options(
            [Option(name.value, id=name.value) for name in RuntimeName]
        )
        self._list(AGENTS).add_options(
            [
                Option(
                    describe_an_agent_row(agent),
                    id=agent.name.value,
                    disabled=not agent.is_on_this_machine,
                )
                for agent in what.agents
            ]
        )
        self._list(MODELS).add_options(self._model_options(what))

        self._highlight(RUNTIMES, what.profile.runtime.name.value)
        self._highlight(AGENTS, what.profile.agent.name.value)
        self._highlight(
            MODELS, find_what_would_answer(what, open_on_what_the_profile_holds(what))
        )

    def _model_options(self, what: WhatCouldBeRun) -> list[Option]:
        """Lay out a row per model downloaded, held ones first.

        :param what: Everything that was read.

        :return: The rows, or the one saying there are none.
        """
        if not what.downloaded:
            return [Option(NOTHING_DOWNLOADED, disabled=True)]

        return [
            Option(
                describe_a_model_row(model, held=model.identifier in what.held),
                id=model.identifier,
            )
            for model in order_models_held_first(what)
        ]

    def _highlight(self, which: str, value: str | None) -> None:
        """Put a list's highlight on one row, where the cursor may reach it.

        A row the cursor steps over is left alone, so the highlight stays where
        the widget put it — the first row a person could pick. The report says
        which pairing that is, and a profile naming an agent this machine has
        not got is still reported on, because nothing else is reachable to
        report on instead.

        :param which: The list to move.
        :param value: What the row is identified by, or ``None`` for no row.
        """
        listed = self._list(which)
        reachable = [
            index for index, option in enumerate(listed.options) if not option.disabled
        ]

        if not reachable:
            return

        wanted = [
            index
            for index in reachable
            if listed.get_option_at_index(index).id == value
        ]

        listed.highlighted = wanted[0] if wanted else reachable[0]

    def _highlighted(self, which: str) -> str | None:
        """Say what a list's highlight is on.

        :param which: The list to read.

        :return: What that row is identified by, or ``None`` where the list has
            no reachable row at all — every agent absent, or nothing
            downloaded.
        """
        listed = self._list(which)
        index = listed.highlighted

        if index is None:
            return None

        return listed.get_option_at_index(index).id

    def _list(self, which: str) -> OptionList:
        """Reach one of the three lists.

        :param which: Which one.

        :return: The widget.
        """
        return self.query_one(f"#{which}", OptionList)

    def _say_what_would_run(self) -> None:
        """Show the report for whatever the highlight is on."""
        what = self._what

        if what is None:
            return

        assembly = read_the_highlight(
            what,
            agent=self._highlighted(AGENTS),
            model=self._highlighted(MODELS),
        )

        self._say("\n".join(describe_what_would_run(what, assembly)))

    def _say(self, said: str) -> None:
        """Put text in the report pane.

        :param said: What to show there.
        """
        self.query_one(f"#{REPORT}", Static).update(said)


__all__ = ["AGENTS", "MODELS", "PANE", "REPORT", "RUNTIMES", "AgentName", "Picker"]
