"""What a run would report, on a screen that leaves everything as it is.

The sentences are the ones `doctor` prints, taken from the same place, so that
two surfaces cannot word one fact differently. Nothing here writes: the screen
reads once, shows what came back, and `q` leaves.
"""

from collections.abc import Callable
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Footer, Static

from offgrid.domain.checkup import Checkup, describe_what_was_read
from offgrid.shared.exceptions import OffgridError

type ReadCheckup = Callable[[], Checkup]

REPORT = "report"
"""Where the report is shown, which is what a test reads it back from."""


class Report(App[None]):
    """The report `doctor` prints, on a screen a person can sit in front of.

    Textual's own bindings are left as they are — `ctrl+q` leaves, `ctrl+c`
    does not and says which key does, `ctrl+p` opens the command palette — so
    that the only thing to learn here is the one key this adds. It is also the
    only one the `Footer` shows, since the rest declare themselves hidden.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("q", "quit", "leave")]

    def __init__(self, read: ReadCheckup) -> None:
        """Take what the screen will show, rather than reaching for it.

        The profile, the runtime and the agent are read by whoever opened the
        screen, which is what keeps the picker clear of every registry.

        :param read: What the profile, the runtime and the agent answer.
        """
        super().__init__()

        self._read = read

    def compose(self) -> ComposeResult:
        """Build the screen: the report, and the keys under it.

        :yield: Each widget, in the order they are read down the screen.
        """
        # Read as plain text, because what it shows is columns and refusals.
        # A refusal carries the key it refused the way pydantic writes one,
        # in square brackets, which a screen reading markup takes for markup
        # and stops on — leaving nowhere to say what was wrong with the file.
        yield Static(id=REPORT, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Read once the screen is up, so that a refusal is shown on it.

        Reading in the constructor would raise before there is anywhere to say
        so, and a runtime nothing answered for is exactly what somebody opened
        this to find out about.
        """
        self.query_one(f"#{REPORT}", Static).update(self._say_what_was_read())

    def _say_what_was_read(self) -> str:
        """Put what was read into the lines the screen shows.

        :return: The report, or what stopped it being read.
        """
        try:
            checkup = self._read()
        except OffgridError as error:
            return str(error)

        return "\n".join(describe_what_was_read(checkup))
