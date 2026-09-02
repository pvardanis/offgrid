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
from dataclasses import astuple, dataclass
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Footer,
    OptionList,
    Select,
    Static,
)

from offgrid.domain.assembling import (
    Pairing,
    WhatCouldBeRun,
    assemble_a_profile,
    find_what_would_answer,
    name_the_model_columns,
    open_on_what_the_profile_holds,
    read_the_highlight,
)
from offgrid.domain.costing import (
    SignalLine,
    Tone,
    describe_the_detail,
    describe_the_signal,
)
from offgrid.domain.profile import DEFAULT_THEME, Profile, Theme
from offgrid.domain.sizing.recommendation import PANEL_COLUMNS, Recommendation
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.wording import REACHING_THE_NETWORK
from offgrid.tui.choices import Choices, agent_choices, model_options, runtime_choices
from offgrid.tui.dropdown import Dropdown
from offgrid.tui.header import HeaderBand

type ReadWhatCouldBeRun = Callable[[], WhatCouldBeRun]
type SaveWhatWasAssembled = Callable[[Profile], None]
type MeasureThisMachine = Callable[[], tuple[str, ...]]
type ReadWhatAListRecommends = Callable[[], Recommendation]


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

RIGHT = "right"
"""The column beside the lists, split into the machine panel over the run one."""

MACHINE = "machine"
"""The upper right panel: what this machine holds, at each quantization width."""

FITS = "fits"
"""Where the machine panel says what fits, which a test reads it back from."""

RECOMMEND = "recommend"
"""The link-style control that reveals the ranked table, in place, below fits."""

RANKED = "ranked"
"""The ranked table itself, revealed by the control and read back by a test."""

RANKED_CAPTION = "ranked-caption"
"""Under the table: which list the figures came from, and what was dropped."""

RECOMMENDING = "recommending"
"""Above the table: the network sentence while it fetches, then the subtitle.

The one place in the picker that reaches the network says so before it does,
and this is where. It carries the sentence while the fetch runs, then either
the subtitle naming the table on success or what stopped the fetch on failure.
"""

RANKED_FOR_THIS_MACHINE = "ranked for this machine"
"""The subtitle above the revealed table, saying what it is rather than how it
was read: how old the figures are is the caption's read date, not a line here."""

RECOMMEND_CLOSED = "[ ▶ recommend models ]"
"""What the control reads as with the table folded away: a right-pointing mark.

A disclosure triangle, the run panel's `details` collapsible uses the same, so
the mark that turns down as the table unfolds is the one a person already knows.
"""

RECOMMEND_OPEN = "[ ▼ recommend models ]"
"""What the control reads as with the table unfolded: the mark turned to point
down, so the triangle says whether the table is open the way a collapsible's does.
"""

RUN = "run"
"""The lower right panel: what the highlighted pairing would do."""

SIGNAL = "signal"
"""Where the run panel's few colour-coded lines are, read back by a test."""

DETAIL = "detail"
"""The collapsible the curated detail waits behind, closed by default."""

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

_TONE_STYLES = {
    Tone.OK: "$text-success",
    Tone.BLOCKED: "$text-error",
    Tone.COST: "$text-warning",
    Tone.INFO: "$text-muted",
}
"""How each verdict is painted: a run that is fine, barred, costed, or a fact.

Theme variables, so the colours move with the theme rather than being fixed
against one palette.
"""


class Picker(App[Departure | None]):
    """Two dropdowns and a models list, and the report for what is picked.

    Three keys end a session, keyed to match Claude Code's model picker: `enter`
    runs with what is assembled and saves it, `s` runs with it once, `q` leaves
    having changed nothing. `r` reveals the ranked table in the machine panel,
    which is the one thing the picker does that reaches the network, and does
    not end the session.
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
        Binding("t", "cycle_theme", "theme"),
        Binding("d", "toggle_detail", "details"),
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

    #{RIGHT} {{
        width: 1fr;
    }}

    /* The two panels share the height, with nothing between them: what this
       machine holds, over what the highlighted run would do. */
    #{MACHINE}, #{RUN} {{
        height: 1fr;
    }}

    #{FITS} {{
        padding: 0 1;
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

    /* Nothing of the recommendation is on screen until the control is used:
       the table, its caption and the network line all wait. */
    #{RANKED}, #{RANKED_CAPTION}, #{RECOMMENDING} {{
        display: none;
    }}

    #{SIGNAL} {{
        padding: 0 1;
    }}

    /* The curated detail scrolls inside the collapsible, so a summary taller
       than the panel is still read to the end once the detail is opened. */
    #{DETAIL} #{PANE} {{
        height: 1fr;
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
        self._theme = DEFAULT_THEME
        self._recommendation: Recommendation | None = None
        self._table_open = False
        self._fetching = False

    def compose(self) -> ComposeResult:
        """Build the screen: the dropdowns, the models list, the report beside.

        :yield: Each widget, in the order they are read across the screen.
        """
        # The band above the lists: which offgrid this is, where a run would
        # operate, and the theme. What it shows was handed in, so it reaches
        # nothing.
        yield HeaderBand(sha=self._sha, cwd=self._cwd, theme=self._theme)

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
            Vertical(
                Vertical(
                    Static(id=FITS, markup=False),
                    # The one control here that reaches the network. It reveals
                    # the table in place below the fits summary, which stays; a
                    # button, so a click and `enter` on it toggle it as `r`
                    # does.
                    Button(RECOMMEND_CLOSED, id=RECOMMEND),
                    Static(id=RECOMMENDING, markup=False),
                    DataTable(id=RANKED, cursor_type="row", zebra_stripes=True),
                    Static(id=RANKED_CAPTION, markup=False),
                    id=MACHINE,
                    classes="box",
                ),
                Vertical(
                    Static(id=SIGNAL),
                    Collapsible(
                        VerticalScroll(Static(id=REPORT, markup=False), id=PANE),
                        title="details",
                        collapsed=True,
                        id=DETAIL,
                    ),
                    id=RUN,
                    classes="box",
                ),
                id=RIGHT,
            ),
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
        # the one the screen is actually drawn in. The default holds until the
        # profile is read, so an error screen is still drawn in a theme.
        self.theme = self._theme

        self.query_one(f"#{RUNTIME_BOX}", Vertical).border_title = "runtime"
        self.query_one(f"#{AGENT_BOX}", Vertical).border_title = "agent"
        self.query_one(f"#{MODEL_BOX}", Vertical).border_title = MODELS
        self.query_one(f"#{MACHINE}", Vertical).border_title = "machine"
        self.query_one(f"#{RUN}", Vertical).border_title = "run"

        # Measured first and kept, so the machine panel is filled whatever the
        # report turns out to be — the machine's budget survives a runtime that
        # did not answer, which is exactly the machine a stranger opened to size.
        self._measurement = self._measure()
        self._show_the_machine()

        try:
            report = self._read_report_func()
        except OffgridError as error:
            self._say(str(error))

            return

        self._report = report
        self._apply_theme(report.profile.theme)
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Toggle the ranked table where the control is clicked or entered.

        The control is a button, so a mouse click and `enter` while it has the
        focus both reach it, as the `r` key does. A press of any other button
        is left to whoever owns it.

        :param event: Which button was pressed.
        """
        if event.button.id == RECOMMEND:
            self.action_recommend()

    def action_recommend(self) -> None:
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
    def _fetch_recommendation(self, read: ReadWhatAListRecommends) -> None:
        """Read the recommendation off the event loop, and reveal what it said.

        On a thread because the read blocks on the network, which would freeze
        the screen the sentence was just painted on. What comes back — a table
        or what stopped it — is shown from the event loop, since a worker may
        not touch the screen itself.

        :param read: The reader, handed in already known to be there so the
            worker does not carry a branch for the case the caller ruled out.
        """
        try:
            recommendation = read()
        except OffgridError as error:
            self.call_from_thread(self._recommendation_failed, str(error))

            return

        self.call_from_thread(self._keep_and_reveal, recommendation)

    def _keep_and_reveal(self, recommendation: Recommendation) -> None:
        """Keep what was read, so the network is reached but the once, then show.

        :param recommendation: What the reader answered.
        """
        self._recommendation = recommendation
        self._fetching = False

        self._reveal_recommendation(recommendation)

    def _reveal_recommendation(self, recommendation: Recommendation) -> None:
        """Fill the ranked table and reveal it, with its caption.

        The network sentence gives way to the subtitle naming the table, so
        what stays above it says what the table is rather than a fetch already
        finished. Reached both by the fetch and by opening from what was kept,
        since the table reads the same either way.

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
        self._show_recommending(RANKED_FOR_THIS_MACHINE)
        self._reveal(RANKED, RANKED_CAPTION)
        self._mark_the_control(open=True)
        self._table_open = True

    def _hide_recommendation(self) -> None:
        """Close the table, keeping what was read so it opens again for free.

        Everything the control revealed goes back to waiting — the table, its
        caption and the subtitle above it — but what was read stays kept, so
        opening it again reaches nothing.
        """
        for one in (RANKED, RANKED_CAPTION, RECOMMENDING):
            self.query_one(f"#{one}").display = False

        self._mark_the_control(open=False)
        self._table_open = False

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

        :param said: The network sentence, the subtitle, or a refusal — or
            nothing, which leaves the line hidden while nothing needs saying
            above the table.
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

    def action_cycle_theme(self) -> None:
        """Move the palette on one, and name the theme now drawn in the header.

        The one control cycled live: what moves is the palette, never the
        banner's glyphs or the screen's labels, so nothing a person picks can
        make it unreadable. The chosen theme rides in what a save writes, so a
        later run opens on it.
        """
        themes = list(Theme)
        after = themes[(themes.index(self._theme) + 1) % len(themes)]

        self._apply_theme(after)
        self._say_what_would_run()

    def _apply_theme(self, name: Theme) -> None:
        """Draw the screen in a theme, and name it in the header's third line.

        :param name: The theme to draw in, which is one offgrid offers.
        """
        # `self.theme` is Textual's live theme *name* — the reactive it resolves
        # to a palette; `self._theme` is what a save writes and what the next
        # cycle steps on from. Assigning a name Textual does not have raises;
        # that `name` is always one it has is held by
        # test_every_offered_theme_is_a_palette_the_screen_can_draw.
        self._theme = name
        self.theme = name
        self.query_one(HeaderBand).show_theme(name)

    def _assemble(self) -> Profile | None:
        """Write what the highlights are on into the profile a run is made from.

        :return: The assembled profile, or ``None`` where nothing was read for
            the screen to assemble — a runtime that did not answer, or a profile
            that would not load.
        """
        report = self._report

        if report is None:
            return None

        return self._assemble_with_theme(report, self._read_the_highlights(report))

    def _assemble_with_theme(self, report: WhatCouldBeRun, pairing: Pairing) -> Profile:
        """Assemble the profile a save writes, carrying the cycled theme.

        The theme is not one of the highlights, so it is stated over the
        assembled profile rather than read out of the pairing: what a save
        writes is the run a person picked drawn in the theme they cycled to.

        :param report: Everything that was read.
        :param pairing: What the highlights are on.

        :return: The profile a save would write.
        """
        return assemble_a_profile(report, pairing).model_copy(
            update={"theme": self._theme}
        )

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
        """Show the run panel for whatever is picked, and whether it differs.

        The signal a person decides on goes in the run panel; the curated detail
        goes into the collapsible under it, closed until a key opens it.
        """
        report = self._report

        if report is None:
            return

        pairing = self._read_the_highlights(report)

        self._show_the_signal(describe_the_signal(report, pairing))
        self.query_one(f"#{REPORT}", Static).update(
            "\n".join(describe_the_detail(report, pairing))
        )
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
        assembled = self._assemble_with_theme(report, pairing)
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

    def action_toggle_detail(self) -> None:
        """Open or close the collapsible the curated detail waits behind.

        Closed on open so the screen a person first meets is the signal rather
        than the summary; a key opens it where they are debugging.
        """
        detail = self.query_one(f"#{DETAIL}", Collapsible)

        detail.collapsed = not detail.collapsed

    def _show_the_machine(self) -> None:
        """Put what this machine holds into the machine panel.

        The measurement does not move as a highlight does, so it is shown once
        rather than recomputed beside every report.
        """
        self.query_one(f"#{FITS}", Static).update("\n".join(self._measurement))

    def _show_the_signal(self, lines: tuple[SignalLine, ...]) -> None:
        """Paint the run panel's signal lines by the verdict each carries.

        :param lines: The signal, each line tagged with how it reads.
        """
        painted = Content("\n".join(line.text for line in lines))
        at = 0

        for line in lines:
            painted = painted.stylize(_TONE_STYLES[line.tone], at, at + len(line.text))
            at += len(line.text) + 1

        self.query_one(f"#{SIGNAL}", Static).update(painted)

    def _say(self, said: str) -> None:
        """Put a message where the signal reads, painted as a thing barring a run.

        The read that failed, or the write that did: a runtime nothing answered
        for, or a profile that would not save. It sits where the signal is,
        which is the panel a person is looking at, rather than behind the toggle.

        :param said: What to show there.
        """
        self._show_the_signal((SignalLine(said, Tone.BLOCKED),))
