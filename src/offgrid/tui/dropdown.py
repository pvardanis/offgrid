"""A dropdown that greys the choices a machine cannot use.

Textual's `Select` cannot mark an option, so its cursor would land on one a run
could not start. This is the one screen widget offgrid adds to it: a `Select`
whose overlay disables the choices it is told are out, which is what makes the
cursor step over them the way a list of models does.
"""

from rich.console import RenderableType
from textual.widgets import Select
from textual.widgets._select import SelectOverlay
from textual.widgets.option_list import Option


class Dropdown(Select[str]):
    """A dropdown whose overlay greys the choices this machine cannot start.

    Textual's `Select` cannot mark an option, so its cursor would land on one
    a run could not use — the exit 127 the screen exists to prevent. This
    disables those rows in the overlay, which is what makes the cursor step
    over them, and keeps the value on one it can reach.
    """

    def __init__(self, *, id: str | None = None) -> None:
        """Start empty, since what there is to pick is read once the screen is up.

        Blank is allowed so that the agents can hold no value on a machine that
        has none of them installed, and so that either dropdown is valid while
        it stands empty before what there is to pick has been read.

        :param id: What the screen reaches this dropdown by.
        """
        self._unavailable: frozenset[str] = frozenset()

        super().__init__([], allow_blank=True, compact=True, id=id)

    def offer(
        self, options: list[tuple[RenderableType, str]], *, unavailable: frozenset[str]
    ) -> None:
        """Put what there is to pick into the dropdown, greying what is out.

        :param options: Each choice, as it reads and the value it stands for.
        :param unavailable: The values a run cannot start, greyed and stepped
            over.
        """
        self._unavailable = unavailable

        self.set_options(options)

    def _setup_options_renderables(self) -> None:
        """Lay the overlay out, greying the values this machine cannot start.

        The one method `Select` leaves between its options and the list they are
        shown in, so that a disabled row is what the cursor steps over.
        """
        overlay = self.query_one(SelectOverlay)

        overlay.clear_options()
        overlay.add_options(
            [
                Option(
                    prompt,
                    disabled=value is Select.NULL or value in self._unavailable,
                )
                for prompt, value in self._options
            ]
        )
