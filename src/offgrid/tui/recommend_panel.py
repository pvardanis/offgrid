"""The one control in the picker that reaches the network: a ranked table.

A link-style control reveals a table of what a published list says fits this
machine, ranked, in place below the fits summary — no modal, no second screen.
The read is on a worker thread so the screen never freezes, and it happens but
once: the table is shown and hidden from what was kept, so the network is
reached the first time the control is used and never again.

It runs past 200 lines by holding one idea whole — the control, the table it
reveals, the fetch behind it and the CSS that lays them out — rather than by
holding a second, so the fix is not to split it.
"""

from collections.abc import Callable
from dataclasses import astuple

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Static

from offgrid.domain.sizing.recommendation import PANEL_COLUMNS, Recommendation
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.wording import REACHING_THE_NETWORK, DescribeModelDownload

type ReadWhatAListRecommends = Callable[[], Recommendation]

RECOMMEND = "recommend"
"""The link-style control that reveals the ranked table, in place, below fits."""

RANKED = "ranked"
"""The ranked table itself, revealed by the control and read back by a test."""

RANKED_CAPTION = "ranked-caption"
"""Under the table: which list the figures came from, and what was dropped."""

DOWNLOAD = "download"
"""Below the table: how the highlighted model is downloaded, in the runtime's
own words.

Surfaced on row highlight, so a mouse click, the arrow keys and enter all show
it. offgrid says how; it downloads nothing. The words are handed in, so the
screen reaches no runtime adapter to learn them.
"""

RECOMMENDING = "recommending"
"""Above the table: the network sentence while it fetches, then nothing.

The one place in the picker that reaches the network says so before it does,
and this is where. It carries the sentence while the fetch runs, then clears on
success — the caption below the table is what says what it is — or shows what
stopped the fetch on failure.
"""

RECOMMEND_CLOSED = "[ ▶ recommend models ]"
"""What the control reads as with the table folded away: a right-pointing mark.

A disclosure triangle, the run panel's `details` collapsible uses the same, so
the mark that turns down as the table unfolds is the one a person already knows.
"""

RECOMMEND_OPEN = "[ ▼ recommend models ]"
"""What the control reads as with the table unfolded: the mark turned to point
down, so the triangle says whether the table is open the way a collapsible's does.
"""


class RecommendPanel(Vertical):
    """The control, the ranked table it reveals, and the fetch behind it.

    The control is a button, so a mouse click and `enter` on it toggle the
    table as the picker's `r` key does. Held content-height so the machine
    panel it sits in scrolls it, rather than a fraction of the panel that swallows
    the download instruction below the table.
    """

    DEFAULT_CSS = f"""
    RecommendPanel {{
        height: auto;
    }}

    /* The link-style control, centred over the table it reveals. A button, so
       a click and `enter` reach it, but flattened of a button's chrome to read
       as a link: no border, no fill, its one line the accent it points with. */
    #{RECOMMEND} {{
        border: none;
        background: transparent;
        color: $accent;
        text-style: bold;
        content-align: center middle;
        width: 1fr;
        height: 1;
        min-width: 0;
        margin: 1 0 0 0;
    }}

    #{RECOMMEND}:focus {{
        text-style: bold reverse;
    }}

    /* Fixed-height and scrolling, so a shelf of models does not push the
       caption or the run panel off the screen: the table is read inside itself. */
    #{RANKED} {{
        height: 10;
        margin: 0 1;
    }}

    #{RANKED_CAPTION}, #{RECOMMENDING} {{
        color: $text-muted;
        padding: 0 1;
    }}

    /* The download instruction sits below the caption, drawn in the full text
       colour rather than the caption's muted grey: it is what a person acts on,
       and the caption is the credit under the table. A rule above it sets it
       off from the caption without a border. */
    #{DOWNLOAD} {{
        padding: 0 1;
        margin: 1 0 0 0;
        border-top: dashed $panel;
    }}

    /* Nothing of the recommendation is on screen until the control is used:
       the table, its caption, the download instruction and the network line
       all wait. */
    #{RANKED}, #{RANKED_CAPTION}, #{DOWNLOAD}, #{RECOMMENDING} {{
        display: none;
    }}
    """

    def __init__(
        self,
        *,
        recommend_func: ReadWhatAListRecommends | None,
        describe_download_func: DescribeModelDownload | None,
    ) -> None:
        """Take the reader and the describer, or nothing where neither is in play.

        :param recommend_func: What reads a published list and lays it out.
            ``None`` leaves the control with nothing to fetch.
        :param describe_download_func: How the runtime says one of its models is
            downloaded, already bound to the runtime. ``None`` where the table is
            not in play — the highlight has nothing to say about downloading.
        """
        super().__init__()

        self._recommend_func = recommend_func
        self._describe_download_func = describe_download_func
        self._recommendation: Recommendation | None = None
        self._table_open = False
        self._fetching = False

    def compose(self) -> ComposeResult:
        """Build the control and the widgets it reveals, all waiting hidden.

        :yield: The control, the network line, the table, its caption, and the
            download instruction, in the order they stack.
        """
        yield Button(RECOMMEND_CLOSED, id=RECOMMEND)
        yield Static(id=RECOMMENDING, markup=False)
        yield DataTable(id=RANKED, cursor_type="row", zebra_stripes=True)
        yield Static(id=RANKED_CAPTION, markup=False)
        # How the highlighted model is downloaded, in the runtime's own words.
        # Read as plain text, since the instruction carries a command a person
        # copies — backticks and all — which a screen reading markup would eat.
        yield Static(id=DOWNLOAD, markup=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Toggle the ranked table where the control is clicked or entered.

        :param event: Which button was pressed.
        """
        if event.button.id == RECOMMEND:
            self.toggle()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Say how the model a ranked row was highlighted on is downloaded.

        The highlight moves however a person reaches a row — a mouse click, the
        arrow keys or `enter` — so this is where the download instruction below
        it is kept in step with what is highlighted.

        :param event: That a ranked row is now highlighted, and which one.
        """
        if event.data_table.id == RANKED:
            self._show_the_download(event.cursor_row)

    def toggle(self) -> None:
        """Toggle the ranked table in place, reaching the network but once.

        The one control here that touches the network, and only the first time
        it is used: the fits summary stays and the table is revealed below it —
        no modal, no second screen — with the fetch on a worker thread so the
        screen never freezes and the network sentence painted before it.

        Using it again closes the table, and using it once more opens it from
        what was read, not from the network: the read is kept, so a person may
        show and hide the table as often as they like for the one fetch. A press
        while a fetch is still in flight does nothing, so mashing the control on
        a slow network starts the one read rather than a fan of them. Nothing
        happens where no reader was handed in — the control has nothing to open.
        """
        if self._recommend_func is None:
            return

        if self._fetching:
            return

        if self._table_open:
            self._hide_recommendation()

            return

        if self._recommendation is not None:
            self._reveal_recommendation(self._recommendation)

            return

        self._fetching = True
        self._show_recommending(REACHING_THE_NETWORK)
        self._fetch_recommendation(self._recommend_func)

    @work(thread=True)
    def _fetch_recommendation(
        self, read_recommendation_func: ReadWhatAListRecommends
    ) -> None:
        """Read the recommendation off the event loop, and reveal what it said.

        On a thread because the read blocks on the network, which would freeze
        the screen the sentence was just painted on. What comes back — a table
        or what stopped it — is shown from the event loop, since a worker may
        not touch the screen itself.

        :param read_recommendation_func: The reader, handed in already known to
            be there so the worker does not carry a branch for the case the
            caller ruled out.
        """
        try:
            recommendation = read_recommendation_func()
        except OffgridError as error:
            self.app.call_from_thread(self._recommendation_failed, str(error))

            return

        self.app.call_from_thread(self._keep_and_reveal, recommendation)

    def _keep_and_reveal(self, recommendation: Recommendation) -> None:
        """Keep what was read, so the network is reached but the once, then show.

        :param recommendation: What the reader answered.
        """
        self._recommendation = recommendation
        self._fetching = False

        self._reveal_recommendation(recommendation)

    def _reveal_recommendation(self, recommendation: Recommendation) -> None:
        """Fill the ranked table and reveal it, with its caption.

        The network sentence is cleared, so nothing is left above the table and
        the caption below it is what says what it is. Reached both by the fetch
        and by opening from what was kept, since the table reads the same either
        way.

        :param recommendation: The models that fit and the caption under them.
        """
        table = self.query_one(f"#{RANKED}", DataTable)

        table.clear(columns=True)
        table.add_columns(*PANEL_COLUMNS)
        for model in recommendation.models:
            # A row is the model's own cells, in the order its fields are named
            # — which is the order `PANEL_COLUMNS` heads them — so a column
            # added or moved is one edit beside the other, not a positional
            # list here to keep in step by hand.
            table.add_row(*astuple(model))

        self.query_one(f"#{RANKED_CAPTION}", Static).update(recommendation.caption)
        self._show_recommending("")
        self._reveal(RANKED, RANKED_CAPTION)
        self._mark_the_control(open=True)
        self._table_open = True

        # The table takes the keys as it opens, so the arrows walk its rows and
        # the download instruction below follows the highlight without a person
        # first tabbing onto it.
        table.focus()

        # Reopening from what was kept adds no highlight event, so the download
        # is shown for the top row here rather than waited for: the table opens
        # on its best row, and the instruction below it is that row's.
        self._show_the_download(0)

    def _hide_recommendation(self) -> None:
        """Close the table, keeping what was read so it opens again for free.

        Everything the control revealed goes back to waiting — the table, its
        caption below it and the line above it — but what was read stays kept, so
        opening it again reaches nothing.
        """
        for one in (RANKED, RANKED_CAPTION, RECOMMENDING):
            self.query_one(f"#{one}").display = False

        self._clear_the_download()
        self._mark_the_control(open=False)
        self._table_open = False

    def _show_the_download(self, index: int) -> None:
        """Show how the model a ranked row is highlighted on is downloaded.

        The instruction is the runtime's own words for the highlighted model,
        asked of the describer handed in. Nothing is shown where no describer was
        handed in, or where the index names no row — an empty recommendation
        highlights nothing.

        :param index: Which ranked row is highlighted, counted from the top.
        """
        if self._describe_download_func is None or self._recommendation is None:
            return

        models = self._recommendation.models

        if not 0 <= index < len(models):
            return

        panel = self.query_one(f"#{DOWNLOAD}", Static)

        panel.update(self._describe_download_func(models[index].name))
        panel.display = True

        # The panel stands taller than its half-column and scrolls, so the
        # instruction is brought into view rather than left below the foot of
        # the panel where a row picked would say nothing.
        panel.scroll_visible(animate=False)

    def _clear_the_download(self) -> None:
        """Take the download instruction off the screen and empty it.

        Called as the table is closed: the instruction belongs to the open
        table, so nothing about a model is left below a table that is gone.
        """
        panel = self.query_one(f"#{DOWNLOAD}", Static)

        panel.update("")
        panel.display = False

    def _mark_the_control(self, *, open: bool) -> None:
        """Turn the control's triangle to say whether the table is unfolded.

        :param open: Whether the table is showing, so the mark points down, or
            folded away, so it points right.
        """
        self.query_one(f"#{RECOMMEND}", Button).label = (
            RECOMMEND_OPEN if open else RECOMMEND_CLOSED
        )

    def _recommendation_failed(self, said: str) -> None:
        """Keep the sentence, say what stopped the table, and allow another try.

        The panel stays open and the table stays hidden, so a person can start
        a network and use the control again — which is why the in-flight guard
        is lifted rather than left set.

        :param said: What stopped the fetch.
        """
        self._show_recommending("\n".join((REACHING_THE_NETWORK, "", said)))
        self._fetching = False

    def _show_recommending(self, said: str) -> None:
        """Put a line above the table, showing it only where there is one.

        :param said: The network sentence or a refusal — or nothing, which
            leaves the line hidden so a fresh table needs no words above it.
        """
        line = self.query_one(f"#{RECOMMENDING}", Static)

        line.update(said)
        line.display = bool(said)

    def _reveal(self, *ids: str) -> None:
        """Show widgets that waited hidden until the control was used.

        :param ids: Which widgets to reveal.
        """
        for one in ids:
            self.query_one(f"#{one}").display = True
