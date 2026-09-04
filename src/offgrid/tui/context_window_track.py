"""The track a handle rides to set a context window, floor to ceiling.

A horizontal bar from the agent's floor at its left edge to the model's ceiling
at its right, a handle resting on the window it opens on. The handle moves under
the mouse or the arrow keys, and every move posts `Moved` for the editor above
it to mirror into its number box. The track reaches nothing: the floor, the
ceiling and the window it opens on are handed in, and the arithmetic that places
the handle is the pure part the editor's test drives through `Pilot` without
reading a frame.
"""

from typing import ClassVar

from rich.text import Text
from textual import events
from textual.geometry import clamp
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

WINDOW_TRACK = "window-track"
"""The slider the handle rides, floor at its left edge and ceiling at its right."""

STEP = 4096
"""How far an arrow moves the handle, in tokens."""

PAGE_STEP = 32768
"""How far a page key moves the handle, eight arrows in one press."""


def get_fraction_of_value(value: int, floor: int, ceiling: int) -> float:
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


def get_value_at_fraction(fraction: float, floor: int, ceiling: int) -> int:
    """Say which window rests a fraction along the track from the left edge.

    :param fraction: How far along the track, clamped to the track's own ends.
    :param floor: The window at the left edge.
    :param ceiling: The window at the right edge.

    :return: The window at that fraction, rounded to a whole number of tokens.
    """
    settled = clamp(fraction, 0.0, 1.0)

    return floor + round(settled * (ceiling - floor))


def get_step_value(value: int, delta: int, floor: int, ceiling: int) -> int:
    """Move a window by a key's step, held inside the track's own ends.

    :param value: The window the handle rests on now.
    :param delta: How far the key moves it, negative to the left.
    :param floor: The window at the left edge, the smallest it can reach.
    :param ceiling: The window at the right edge, the largest it can reach.

    :return: The window the handle moves to, clamped to the range.
    """
    return clamp(value + delta, floor, ceiling)


class ContextWindowTrack(Widget):
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
    ContextWindowTrack {
        width: 1fr;
        height: 1;
    }

    ContextWindowTrack .window-track--bar {
        color: $panel;
    }

    ContextWindowTrack .window-track--handle {
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
        fraction = get_fraction_of_value(self.value, self._floor, self._ceiling)
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

        moved = get_step_value(self.value, steps[event.key], self._floor, self._ceiling)

        self._move_to(moved)

    def _window_under(self, x: int) -> int:
        """Say which window the track holds at a column, its ends its edges.

        :param x: The column the pointer is over, from the track's left.

        :return: The window at that column.
        """
        width = max(self.size.width, 1)
        fraction = x / (width - 1) if width > 1 else 0.0

        return get_value_at_fraction(fraction, self._floor, self._ceiling)

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
