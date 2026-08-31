"""The published list, fetched on the one key in the picker that reaches out.

Every other key in the picker reaches nothing: the lists are read from the
machine and the runtime on this machine, and moving a highlight is arithmetic.
This screen is where a person asks for the published table `recommend` names,
and it is the only place the picker touches the network.

So the sentence saying so is painted the moment the screen opens, before the
fetch runs rather than after it — the fetch is carried out on a thread so the
sentence is on screen while the network is being waited on, and stays there
whether the fetch answers with a table or with what stopped it. The screen
never fetches anything itself: it is handed a reader, as the picker is handed
everything it shows.
"""

from collections.abc import Callable
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Static

from offgrid.shared.exceptions import OffgridError
from offgrid.shared.wording import REACHING_THE_NETWORK

type ReadWhatAListRecommends = Callable[[], list[str]]

TABLE = "table"
"""Where the sentence, and then the table under it, are shown."""

PANE = "published-pane"
"""What the table scrolls inside, since it is as long as the list is."""


class PublishedList(ModalScreen[None]):
    """The published table, said before it is reached and shown once it is.

    Opened over the picker by the key that recommends, and left with `esc` or
    `q`, which returns to the picker with everything still assembled. It is its
    own full screen rather than a panel, because the table is wider than the
    lists it would sit beside and longer than the report it would sit under.

    Modal so that it holds the keyboard while it is up: the picker's keys run
    or recommend, and pressing one of those over the table would launch a run
    and tear the table away mid-read, or open a second copy of this screen.
    Only the keys bound here answer while it is on top.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "back"),
        Binding("q", "back", "back"),
    ]

    CSS = f"""
    #{PANE} {{
        padding: 0 1;
    }}
    """

    def __init__(self, read_func: ReadWhatAListRecommends) -> None:
        """Take the reader the picker was handed, rather than reaching itself.

        :param read_func: What reads a published list and lays it out. Reaching
            the network is its, so a screen that shows the domain and reaches
            nothing stays that.
        """
        super().__init__()

        self._read_func = read_func

    def compose(self) -> ComposeResult:
        """Build the screen: the sentence and the table, above the key hints.

        :yield: Each widget, in the order they are read down the screen.
        """
        yield VerticalScroll(Static(id=TABLE, markup=False), id=PANE)
        yield Footer()

    def on_mount(self) -> None:
        """Say the network is about to be reached, then reach it on a thread.

        The sentence is painted first and the fetch is handed to a worker, so
        that a person reads what is about to happen while it happens rather
        than meeting a frozen screen for as long as the network takes.
        """
        self._show(REACHING_THE_NETWORK)

        self._fetch()

    @work(thread=True)
    def _fetch(self) -> None:
        """Read the published list, off the event loop, and show what it said.

        On a thread because the read blocks on the network, which would freeze
        the screen the sentence was just painted on. What comes back — a table
        or the sentence saying what stopped it — is shown under the sentence,
        from the event loop, since a worker may not touch the screen itself.
        """
        try:
            said = "\n".join(self._read_func())
        except OffgridError as error:
            said = str(error)

        self.app.call_from_thread(self._show_beneath_the_sentence, said)

    def _show_beneath_the_sentence(self, said: str) -> None:
        """Show what was read under the sentence that was said before it.

        The sentence stays whether a table or a refusal follows it, which is
        what says it was said before the fetch rather than as its result.

        :param said: The table, or what stopped it being read.
        """
        self._show("\n".join((REACHING_THE_NETWORK, "", said)))

    def _show(self, said: str) -> None:
        """Put text in the table pane.

        :param said: What to show there.
        """
        self.query_one(f"#{TABLE}", Static).update(said)

    def action_back(self) -> None:
        """Leave the screen, returning to the picker unchanged."""
        self.dismiss(None)
