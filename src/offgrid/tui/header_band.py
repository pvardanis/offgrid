"""The band above the picker: the logo, and which build, where, and how it looks.

Three things a person arriving from the README has no other way to read: which
offgrid this is — a git SHA, since there is no published version to name — the
working directory a run would inherit, and the theme the screen is drawn in.
The SHA and the cwd are a string and a path the screen only displays, handed in
from the command line so the layer rule holds: `offgrid.tui` reaches no command
to learn them.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

BANNER = "banner"
"""What the three-row block logo is stacked in."""

BUILD = "build"
"""Where the git SHA is shown, which is what a test reads it back from."""

CWD = "cwd"
"""Where the directory a run inherits is shown."""

THEME = "theme-name"
"""Where the theme the screen is drawn in is named."""

BANNER_ROWS = (
    "█▀█ █▀▀ █▀▀ █▀█ █▀▄ ▀ █▀▄",
    "█ █ █▀▀ █▀▀ █▄█ █▀▄ █ █ █",
    "█▄█ █   █   ▄▄█ █ █ █ █▄█",
)
"""The emboss block spelling offgrid, fixed rather than cycled with the theme."""


def get_theme_line(name: str) -> str:
    """Give the header's third line, naming the theme the screen is drawn in.

    Shared by the band's first draw and its restatement so the two cannot drift.

    :param name: The theme now applied.

    :return: The line naming it.
    """
    return f"theme: {name}"


class HeaderBand(Vertical):
    """The logo and three lines: the build, the working directory, the theme."""

    DEFAULT_CSS = """
    HeaderBand {
        height: auto;
        /* A symmetric margin so the band floats off the window's edges and off
           the panels below it, rather than the logo sitting hard against the
           left rule — which reads as unfinished on a light theme, where the
           block has nowhere to fade into. */
        margin: 1 2;
        border-bottom: solid $panel;
    }

    HeaderBand > #header-row {
        height: auto;
    }

    /* The block logo is bold, and each row a shade of the accent so the three
       read as one embossed mark rather than three separate lines. */
    HeaderBand #banner {
        text-style: bold;
        height: auto;
        width: auto;
    }

    HeaderBand #banner > Static {
        height: 1;
        width: auto;
    }

    HeaderBand #banner-1 {
        color: $accent-lighten-2;
    }

    HeaderBand #banner-2 {
        color: $accent;
    }

    HeaderBand #banner-3 {
        color: $accent-darken-2;
    }

    HeaderBand #meta {
        height: auto;
        width: 1fr;
        padding: 0 0 0 3;
    }

    HeaderBand #build {
        color: $text-muted;
        height: 1;
    }

    HeaderBand #cwd {
        color: $text-muted;
        height: 1;
    }

    HeaderBand #theme-name {
        color: $text-muted;
        height: 1;
    }
    """

    def __init__(self, *, sha: str, cwd: str, theme: str) -> None:
        """Take what to display, which the screen was handed and only shows.

        Keyword-only, because the three are display strings a positional call
        could transpose without the types noticing.

        :param sha: The git SHA naming which offgrid checkout this is.
        :param cwd: The working directory a run would inherit.
        :param theme: The name of the theme the screen is drawn in.
        """
        super().__init__()

        self._sha = sha
        self._cwd = cwd
        self._theme = theme

    def compose(self) -> ComposeResult:
        """Build the band: the logo, and the three lines beside it.

        :yield: The logo rows, then the build, the cwd and the theme lines.
        """
        with Horizontal(id="header-row"):
            with Vertical(id=BANNER):
                yield Static(BANNER_ROWS[0], id="banner-1", markup=False)
                yield Static(BANNER_ROWS[1], id="banner-2", markup=False)
                yield Static(BANNER_ROWS[2], id="banner-3", markup=False)

            with Vertical(id="meta"):
                yield Static(f"@ {self._sha}", id=BUILD, markup=False)
                yield Static(self._cwd, id=CWD, markup=False)
                yield Static(get_theme_line(self._theme), id=THEME, markup=False)

    def show_theme(self, name: str) -> None:
        """Name the theme the screen is now drawn in, on the band's third line.

        The theme is the one thing the header reports that changes while the
        screen is open — a person cycles it live — so the line is restated
        rather than composed once, both draws going through `get_theme_line`.

        :param name: The theme now applied.
        """
        self._theme = name
        self.query_one(f"#{THEME}", Static).update(get_theme_line(name))
