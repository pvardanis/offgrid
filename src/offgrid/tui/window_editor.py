"""The slider that floats over a model row to set its context window.

`e` opens it over the highlighted row's `context` cell. A track runs from the
agent's floor at its left edge to the model's ceiling at its right, a handle
resting on the window the cell shows. The handle moves under the mouse or the
arrow keys, and a box beside it holds the same window as a number a person can
type over — an in-range count moves the handle to it, and a value the model
cannot hold is refused in the words a load would fail with rather than reaching
the row. `escape` abandons, `enter` commits and closes.

Where the runtime states no ceiling there is no right edge to run a track to,
so only the box shows, refused against the floor alone.

The widget reaches no runtime and no store: the ceiling, the floor and the
window it opens on are handed in, and what it settles on it posts back for the
picker to keep. So a test drives it the way a person does — through the keys —
and reads the handle where it rests, never a frame.
"""

from typing import ClassVar

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import clamp
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from offgrid.domain.running.context_window import refuse_a_typed_window
from offgrid.shared.exceptions import ContextWindowUnworkableError

WINDOW_EDITOR = "window-editor"
"""The floating box, which a test reads the whole control back from."""

WINDOW_TRACK = "window-track"
"""The slider the handle rides, floor at its left edge and ceiling at its right."""

WINDOW_BOX = "window-box"
"""The number box beside the track, the window as a count to type over."""

WINDOW_CAPTION = "window-caption"
"""The line under the track naming the most the model could be served at."""

WINDOW_MESSAGE = "window-message"
"""Where a typed value the model cannot hold is refused, hidden until one is."""

STEP = 4096
"""How far an arrow moves the handle, in tokens."""

PAGE_STEP = 32768
"""How far a page key moves the handle, eight arrows in one press."""


def fraction_of_value(value: int, floor: int, ceiling: int) -> float:
    """Say how far along the track a window rests, from the left edge.

    :param value: The window to place, clamped into the range it is measured in.
    :param floor: The window at the left edge.
    :param ceiling: The window at the right edge.

    :return: A fraction from 0.0 at the floor to 1.0 at the ceiling. A range of
        no width rests at the left edge, there being one point to rest on rather
        than a width to divide by.
    """
    if ceiling <= floor:
        return 0.0

    return clamp((value - floor) / (ceiling - floor), 0.0, 1.0)


def value_at_fraction(fraction: float, floor: int, ceiling: int) -> int:
    """Say which window rests a fraction along the track from the left edge.

    :param fraction: How far along the track, clamped to the track's own ends.
    :param floor: The window at the left edge.
    :param ceiling: The window at the right edge.

    :return: The window at that fraction, rounded to a whole number of tokens.
    """
    settled = clamp(fraction, 0.0, 1.0)

    return floor + round(settled * (ceiling - floor))


def step_value(value: int, delta: int, floor: int, ceiling: int) -> int:
    """Move a window by a key's step, held inside the track's own ends.

    :param value: The window the handle rests on now.
    :param delta: How far the key moves it, negative to the left.
    :param floor: The window at the left edge, the smallest it can reach.
    :param ceiling: The window at the right edge, the largest it can reach.

    :return: The window the handle moves to, clamped to the range.
    """
    return clamp(value + delta, floor, ceiling)


class WindowTrack(Widget):
    """A horizontal track a handle rides, from a floor to a ceiling.

    The arrow keys move the handle by a step and the page keys by a page, and a
    click or drag places it under the pointer. Every move posts `Moved` for the
    editor to mirror into the number box; the box moves the handle by setting
    `value`, which redraws without posting, so the two never chase each other.
    """

    can_focus = True

    ALLOW_SELECT = False
    """No text to select: a drag moves the handle, it does not sweep a highlight."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "window-track--bar",
        "window-track--handle",
    }

    DEFAULT_CSS = """
    WindowTrack {
        width: 1fr;
        height: 1;
    }

    WindowTrack .window-track--bar {
        color: $panel;
    }

    WindowTrack .window-track--handle {
        color: $accent;
    }
    """

    value = reactive(0)
    """The window the handle rests on, redrawing the track when it changes."""

    class Moved(Message):
        """That the handle moved under a key or the pointer, to the given window.

        :param window: The window the handle now rests on.
        """

        def __init__(self, window: int) -> None:
            """Carry the moved-to window to the editor.

            :param window: The window the handle now rests on.
            """
            self.window = window

            super().__init__()

    def __init__(self, *, value: int, floor: int, ceiling: int) -> None:
        """Take the range the handle rides and the window it opens on.

        :param value: The window the handle opens on.
        :param floor: The window at the left edge.
        :param ceiling: The window at the right edge.
        """
        self._floor = floor
        self._ceiling = ceiling

        super().__init__(id=WINDOW_TRACK)

        self.value = value

    def render(self) -> Text:
        """Draw the track filled up to the handle, the handle on the window.

        :return: The bar as a line of text, the handle a step within it.
        """
        width = max(self.size.width, 1)
        fraction = fraction_of_value(self.value, self._floor, self._ceiling)
        handle = round(fraction * (width - 1))

        bar = self.get_component_rich_style("window-track--bar")
        knob = self.get_component_rich_style("window-track--handle")

        line = Text("━" * width, style=bar)
        line.stylize(knob, handle, handle + 1)
        line.plain = line.plain[:handle] + "●" + line.plain[handle + 1 :]

        return line

    def _move_to(self, window: int) -> None:
        """Rest the handle on a window and tell the editor it moved there.

        :param window: The window to rest on, already inside the range.
        """
        self.value = window

        self.post_message(self.Moved(window))

    def on_key(self, event: events.Key) -> None:
        """Move the handle by a step or a page, held inside the range.

        :param event: The key pressed, read for the arrows and the page keys.
        """
        steps = {
            "left": -STEP,
            "right": STEP,
            "pagedown": -PAGE_STEP,
            "pageup": PAGE_STEP,
        }

        if event.key not in steps:
            return

        event.stop()

        moved = step_value(self.value, steps[event.key], self._floor, self._ceiling)

        self._move_to(moved)

    def _window_under(self, x: int) -> int:
        """Say which window the track holds at a column, its ends its edges.

        :param x: The column the pointer is over, from the track's left.

        :return: The window at that column.
        """
        width = max(self.size.width, 1)
        fraction = x / (width - 1) if width > 1 else 0.0

        return value_at_fraction(fraction, self._floor, self._ceiling)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """Take the pointer and rest the handle where it went down.

        :param event: Where the press landed, its column read as a window.
        """
        self.capture_mouse()

        self._move_to(self._window_under(event.x))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Drag the handle with the pointer while the press is held.

        :param event: Where the pointer moved, read only while it is captured.
        """
        if self.app.mouse_captured is self:
            self._move_to(self._window_under(event.x))

    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Let the pointer go when the press is released.

        :param event: That the press ended.
        """
        self.release_mouse()


class WindowEditor(Vertical):
    """A slider from the floor to the ceiling, floated over the row it edits.

    Opens with the handle on the window the cell shows and the same window in a
    box beside it. The handle moves under the mouse or the arrow keys and the
    box follows it; a window typed into the box moves the handle where it can be
    held and is refused where it cannot. `escape` abandons and `enter` commits.
    What it settles on it posts as `Committed` for the picker to keep; an
    abandoned edit posts `Cancelled`.
    """

    DEFAULT_CSS = f"""
    WindowEditor {{
        layer: overlay;
        width: 40;
        height: auto;
        background: $surface;
        border: round $accent;
        padding: 0 1;
    }}

    WindowEditor > Input {{
        border: none;
        background: $surface;
    }}

    WindowEditor > #{WINDOW_CAPTION} {{
        color: $text-muted;
    }}

    WindowEditor > #{WINDOW_MESSAGE} {{
        color: $text-error;
    }}
    """

    class Committed(Message):
        """A window the editor settled on, to be kept for the model it edits.

        :param window: The window picked, already refused where it could not be
            served, so the picker keeps it without measuring it again.
        """

        def __init__(self, window: int) -> None:
            """Carry the window picked back to the picker.

            :param window: The window the editor settled on.
            """
            self.window = window

            super().__init__()

    class Cancelled(Message):
        """That the edit was abandoned, so the row keeps the window it had."""

    def __init__(
        self,
        *,
        identifier: str,
        current: int | None,
        floor: int | None,
        ceiling: int | None,
    ) -> None:
        """Take what the row states, so the editor reaches nothing to learn it.

        :param identifier: The model the row is for, named in a ceiling refusal.
        :param current: The window the row shows now, which the editor opens on.
        :param floor: The smallest window the agent can start in, or ``None``
            where no agent answered to state one.
        :param ceiling: The most the model could be served at, or ``None``
            where the runtime states none, which leaves only the box.
        """
        self._identifier = identifier
        self._current = current
        self._floor = floor
        self._ceiling = ceiling

        super().__init__(id=WINDOW_EDITOR)

    def compose(self) -> ComposeResult:
        """Build the box: the track where there is a ceiling, the box, the lines.

        Where the runtime states no ceiling there is no right edge for a track,
        so only the box shows; the caption names the ceiling, and the message
        waits hidden until a typed value is refused.

        :yield: Each widget, top to bottom.
        """
        if self._ceiling is not None and self._current is not None:
            yield WindowTrack(
                value=self._current, floor=self._floor or 0, ceiling=self._ceiling
            )

        # Free-text rather than digits-only, so a value that is not a count at
        # all is refused at the box in the same voice a bad number is, rather
        # than swallowed before it can be read back.
        yield Input(id=WINDOW_BOX)
        yield Static(id=WINDOW_CAPTION, markup=False)
        yield Static(id=WINDOW_MESSAGE, markup=False)

    def on_mount(self) -> None:
        """Fill the box, caption the ceiling, and rest the focus on the track.

        The box opens filled with the window the cell shows, so a person types
        over the current value rather than into an empty box. The message waits
        hidden until a typed value is refused. The track takes the keys where
        there is one, the box where there is not.
        """
        box = self.query_one(f"#{WINDOW_BOX}", Input)
        box.value = "" if self._current is None else str(self._current)

        caption = self.query_one(f"#{WINDOW_CAPTION}", Static)
        caption.update(
            "no ceiling stated"
            if self._ceiling is None
            else f"supports up to {self._ceiling} tokens"
        )

        self.query_one(f"#{WINDOW_MESSAGE}", Static).display = False

        tracks = self.query(WindowTrack)
        (tracks.first() if tracks else box).focus()

    def on_window_track_moved(self, event: WindowTrack.Moved) -> None:
        """Mirror a handle move into the box, without moving the handle back.

        Setting the box's value fires its own change, which the change handler
        skips because it already matches the handle — so the two do not chase.

        :param event: The window the handle moved to.
        """
        self.query_one(f"#{WINDOW_BOX}", Input).value = str(event.window)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Move the handle to an in-range window typed into the box.

        A value that is not a whole count, or one outside the range, leaves the
        handle where it is — the box keeps it to be read back or refused on
        `enter`, and nothing out of range reaches the row.

        :param event: What the box holds now.
        """
        tracks = self.query(WindowTrack)

        if not tracks:
            return

        track = tracks.first()

        try:
            typed = int(event.value)
        except ValueError:
            return

        if self._floor is not None and typed < self._floor:
            return

        if self._ceiling is not None and typed > self._ceiling:
            return

        if typed != track.value:
            track.value = typed

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Commit what the box holds, or hold the message that refuses it.

        :param event: What the box holds when `enter` was pressed.
        """
        self._commit_or_refuse(event.value)

    def _commit_or_refuse(self, typed: str) -> None:
        """Commit a workable window, or hold the message that refuses it.

        Both the box and the track settle through here, so a window a load
        could not hold is refused the same way whichever moved it: a value
        below the floor, above the ceiling or not a positive count is refused
        in the words a load would fail with, and the box stays open on it.

        :param typed: The window to commit, as it reads.
        """
        try:
            window = refuse_a_typed_window(
                typed,
                floor=self._floor,
                ceiling=self._ceiling,
                model_identifier=self._identifier,
            )
        except ContextWindowUnworkableError as refused:
            self._say(str(refused))

            return

        self.post_message(self.Committed(window))

    def _say(self, said: str) -> None:
        """Show why a typed window was refused, so the box stays open on it.

        :param said: The refusal, in the words the runtime or the agent gives.
        """
        message = self.query_one(f"#{WINDOW_MESSAGE}", Static)

        message.update(said)
        message.display = True

    def on_key(self, event: events.Key) -> None:
        """Abandon on `escape`, step to the box on `down`, or commit on `enter`.

        `enter` reaches here only with the track focused: the box takes its own
        `enter` as a submit. Either way the window settles through the same
        refusal, so the handle's window is refused where a load could not hold
        it rather than committed unmeasured. `down` on the track moves the focus
        to the box below it, so the window can be typed over from the keyboard.

        :param event: The key pressed, read for `escape`, `down` and `enter`.
        """
        if event.key == "escape":
            event.stop()

            self.post_message(self.Cancelled())

            return

        if event.key == "down":
            tracks = self.query(WindowTrack)

            if tracks and tracks.first().has_focus:
                event.stop()

                self.query_one(f"#{WINDOW_BOX}", Input).focus()

            return

        if event.key == "enter":
            tracks = self.query(WindowTrack)

            if tracks and tracks.first().has_focus:
                event.stop()

                self._commit_or_refuse(str(tracks.first().value))
