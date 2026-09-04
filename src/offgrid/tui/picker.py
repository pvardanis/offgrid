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

This is the screen's composition root: it wires the widgets, routes the keys,
and recomputes the report. The shell it lays them out in — the ids they answer
to and the CSS — is `shell`; the panels that carry an idea of their own (the
signal, the recommendation, the window slider) are widgets beside it. It runs
past 200 lines by that role rather than by holding a second idea.
"""

from collections.abc import Callable
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Collapsible,
    Footer,
    OptionList,
    Select,
    Static,
)

from offgrid.domain.assembling import (
    HELD_COLUMN,
    MODEL_COLUMN,
    Pairing,
    WhatCouldBeRun,
    assemble_a_profile,
    find_what_would_answer,
    get_requested_model_context,
    name_the_model_columns,
    open_on_what_the_profile_holds,
    read_the_highlight,
)
from offgrid.domain.costing import describe_the_detail, describe_the_signal
from offgrid.domain.profile import DEFAULT_THEME, Profile, Theme
from offgrid.shared.exceptions import OffgridError
from offgrid.shared.wording import DescribeModelDownload
from offgrid.tui.choices import (
    Choices,
    agent_choices,
    describe_the_row,
    model_options,
    runtime_choices,
)
from offgrid.tui.context_window_editor import WINDOW_EDITOR, ContextWindowEditor
from offgrid.tui.departure import Departure
from offgrid.tui.dropdown import Dropdown
from offgrid.tui.header_band import HeaderBand
from offgrid.tui.reckoning import find_downloaded_model, floor_for_agent
from offgrid.tui.recommend_panel import ReadWhatAListRecommends, RecommendPanel
from offgrid.tui.shell import (
    AGENT_BOX,
    AGENTS,
    COLUMNS,
    DETAIL,
    FITS,
    LISTS,
    MACHINE,
    MODEL_BOX,
    MODELS,
    PANE,
    REPORT,
    RIGHT,
    RUN,
    RUNTIME_BOX,
    RUNTIMES,
    SHELL_CSS,
    SIGNAL,
    SIGNAL_PANE,
    STATUS,
)
from offgrid.tui.signal_view import SignalView

type ReadWhatCouldBeRun = Callable[[], WhatCouldBeRun]
type SaveWhatWasAssembled = Callable[[Profile], None]
type ReadLastSavedWindows = Callable[[], dict[str, int]]
type MeasureThisMachine = Callable[[], tuple[str, ...]]


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
        Binding("e", "edit_window", "edit window"),
        Binding("r", "recommend", "recommend"),
        Binding("t", "cycle_theme", "theme"),
        Binding("d", "toggle_detail", "details"),
        Binding("q", "quit", "leave"),
    ]

    CSS = SHELL_CSS

    def __init__(
        self,
        read_report_func: ReadWhatCouldBeRun,
        save_func: SaveWhatWasAssembled,
        *,
        sha: str,
        cwd: str,
        read_store_func: ReadLastSavedWindows | None = None,
        measure_func: MeasureThisMachine | None = None,
        recommend_func: ReadWhatAListRecommends | None = None,
        describe_download_func: DescribeModelDownload | None = None,
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
        :param read_store_func: What each model was last saved at, keyed on the
            model, seeding the window every row shows and a run is priced at.
            ``None`` where a test hands in no store, which reads as no model
            having a remembered window and every one falling back to its
            ceiling.
        :param measure_func: What this machine and what fits it read as, handed
            in where there is no profile so that a stranger meets the machine
            measured rather than an error naming another command. ``None`` where
            a profile is there, since the machine's budget is not what somebody
            with a run already assembled came to read.
        :param recommend_func: What reads a published list and lays it out, for
            the key that reaches the network. ``None`` leaves that key with
            nothing to fetch, which is what a test that is not about it hands in.
        :param describe_download_func: How the runtime a profile names says one
            of its models is downloaded, asked for the model a ranked row is
            highlighted on. Handed in already bound to the runtime, so the
            screen reaches no adapter to learn it. ``None`` where the ranked
            table is not in play — the highlight has nothing to say about
            downloading.
        """
        super().__init__()

        self._read_report_func = read_report_func
        self._save_func = save_func
        self._sha = sha
        self._cwd = cwd
        self._read_store_func = read_store_func
        self._measure_func = measure_func
        self._recommend_func = recommend_func
        self._describe_download_func = describe_download_func
        self._report: WhatCouldBeRun | None = None
        self._context_store: dict[str, int] = {}
        self._session_windows: dict[str, int] = {}
        self._editing_model: str | None = None
        self._measurement: tuple[str, ...] = ()
        self._theme = DEFAULT_THEME

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
                # Scrolls, because the fits summary, the revealed table, its
                # caption and the download instruction together stand taller
                # than the half-column the panel is given: without it the
                # instruction below the table is drawn past the panel's foot and
                # off the screen. The highlight scrolls its instruction into
                # view, so a row picked is a row read.
                VerticalScroll(
                    Static(id=FITS, markup=False),
                    # The one control here that reaches the network, and the
                    # ranked table it reveals in place below the fits summary,
                    # which stays. It carries the reader and the describer, so
                    # the screen reaches no adapter of either.
                    RecommendPanel(
                        recommend_func=self._recommend_func,
                        describe_download_func=self._describe_download_func,
                    ),
                    id=MACHINE,
                    classes="box",
                ),
                Vertical(
                    VerticalScroll(SignalView(id=SIGNAL), id=SIGNAL_PANE),
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
        self.query_one(f"#{MACHINE}", VerticalScroll).border_title = "machine"
        self.query_one(f"#{RUN}", Vertical).border_title = "run"

        # Measured first and kept, so the machine panel is filled whatever the
        # report turns out to be — the machine's budget survives a runtime that
        # did not answer, which is exactly the machine a stranger opened to size.
        self._measurement = self._measure()
        self._show_the_machine()

        try:
            report = self._read_report_func()
            store = self._read_store_func() if self._read_store_func else {}
        except OffgridError as error:
            self.query_one(SignalView).bar(str(error))

            return

        self._report = report
        self._context_store = store
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

        The runtime and agent dropdowns carry their own lists, and moving
        inside one is about that choice rather than the run, so the report is
        left alone until the highlight that moved is the models list's own.

        :param event: That a list moved, which is what wakes this.
        """
        if event.option_list.id == MODELS:
            self._say_what_would_run()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Run and save when a model row is chosen, which `enter` on it is.

        The models list has the focus and consumes `enter` before the app is
        reached, so selecting a row is where `enter` runs. A disabled row emits
        nothing, so the row that says nothing is downloaded cannot arm a run.
        The runtime and agent dropdowns carry lists too; a choice made on one
        is that dropdown's to answer, not the key that ends the session, so
        only the models list's own selection runs.

        :param event: That a row was chosen, which wakes this.
        """
        if event.option_list.id == MODELS:
            self.action_run_and_save()

    def action_run_and_save(self) -> None:
        """Leave to run with what is assembled, having saved it as remembered.

        A no-op while the window slider is open, so an `enter` committing a
        window is not also read as the key that ends the session.
        """
        if self._slider_is_open():
            return

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
            self.query_one(SignalView).bar(str(error))

            return

        self.exit(Departure(profile=assembled, saved=True))

    def action_run_once(self) -> None:
        """Leave to run with what is assembled, writing nothing.

        A no-op while the window slider is open, for the same reason the key
        that saves is: the keys belong to the editor until it closes.
        """
        if self._slider_is_open():
            return

        assembled = self._assemble()

        if assembled is None:
            return

        self.exit(Departure(profile=assembled, saved=False))

    def _slider_is_open(self) -> bool:
        """Say whether the window slider is floated over a row.

        :return: Whether a slider is on the screen, so the keys that end the
            session and the key that opens another are left to it until it closes.
        """
        return bool(self.query(f"#{WINDOW_EDITOR}"))

    async def action_edit_window(self) -> None:
        """Float the window slider over the highlighted row, where there is one.

        Opens only where the models list holds the focus: `e` edits a model's
        window, so a press while another panel has the focus is a no-op rather
        than floating a control over a row a person is not on. Empty list or
        nothing highlighted is a no-op too, and a press while the slider is
        already open is left to it — it owns the keys until it closes.
        """
        report = self._report

        if report is None or self._slider_is_open():
            return

        if not self._get_list().has_focus:
            return

        identifier = self._get_highlighted_model()

        if identifier is None:
            return

        model = find_downloaded_model(report, identifier)

        editor = ContextWindowEditor(
            identifier=identifier,
            current=get_requested_model_context(
                report, self._context_store, identifier, edits=self._session_windows
            ),
            floor=floor_for_agent(report, self._get_picked_agent()),
            ceiling=None if model is None else model.context_ceiling,
        )

        self._editing_model = identifier

        await self.mount(editor)

        self._float_over_the_row(editor)

    def on_context_window_editor_committed(
        self, event: ContextWindowEditor.Committed
    ) -> None:
        """Keep the picked window in memory, and redraw the row to show it.

        The window is kept per model for the session, so arrowing away and
        back finds it, and it rides into the assembled profile and the store
        the way the cycled theme does.

        :param event: The window the editor settled on.
        """
        identifier = self._editing_model

        self._close_the_editor()

        if identifier is None:
            return

        self._session_windows[identifier] = event.window
        self._redraw_the_row(identifier)
        self._say_what_would_run()

    def on_context_window_editor_cancelled(
        self, event: ContextWindowEditor.Cancelled
    ) -> None:
        """Drop the slider, leaving the row on the window it already showed.

        :param event: That the edit was abandoned.
        """
        self._close_the_editor()

    def _close_the_editor(self) -> None:
        """Take the slider off the screen and give the models list the keys."""
        for editor in self.query(ContextWindowEditor):
            editor.remove()

        self._editing_model = None
        self._get_list().focus()

    def _redraw_the_row(self, identifier: str) -> None:
        """Redraw one model's row so its `context` cell shows the picked window.

        :param identifier: The model whose row to redraw.
        """
        report = self._report

        if report is None:
            return

        model = find_downloaded_model(report, identifier)

        if model is None:
            return

        self._get_list().replace_option_prompt(
            identifier,
            describe_the_row(report, self._context_store, self._session_windows, model),
        )

    def _float_over_the_row(self, editor: ContextWindowEditor) -> None:
        """Place the slider over the highlighted row's `context` cell.

        :param editor: The slider to place.
        """
        listed = self._get_list()
        region = listed.region
        index = listed.highlighted or 0

        row = region.y + index - listed.scroll_offset.y

        editor.styles.offset = (
            region.x + MODEL_COLUMN + HELD_COLUMN,
            max(region.y, row),
        )

    def action_recommend(self) -> None:
        """Toggle the ranked table, which the recommend panel owns.

        The `r` key reaches the app from wherever the focus is, so the toggle is
        routed to the panel that holds the table, the reader and the fetch — the
        panel answers the button on it the same way.
        """
        self.query_one(RecommendPanel).toggle()

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
        self._get_list().add_options(
            model_options(report, self._context_store, self._session_windows)
        )
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
        wanted = find_what_would_answer(
            report, open_on_what_the_profile_holds(report, self._context_store)
        )
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

        self.query_one(SignalView).show(describe_the_signal(report, pairing))
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
            self._context_store,
            agent=self._get_picked_agent(),
            model=self._get_highlighted_model(),
            edits=self._session_windows,
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
