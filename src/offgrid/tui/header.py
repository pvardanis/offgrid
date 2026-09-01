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
    "█▀█ █▀▀ █▀▀ █▀▀ █▀▄ █ █▀▄",
    "█ █ █▀▀ █▀▀ █▄█ █▀▄ █ █ █",
    "▀▀▀ ▀   ▀   ▀▀▀ ▀ ▀ ▀ ▀▀▀",
)
"""The emboss block spelling offgrid, fixed rather than cycled with the theme."""

INHERITS = "the directory the agent inherits"
"""What the cwd line says the working directory is: inherited, not set here.

offgrid shows where a run would operate; the agent takes the shell's cwd, and
offgrid does not set it. The note says so beside the path.
"""


class HeaderBand(Vertical):
    """The logo and three lines: the build, the working directory, the theme."""

    DEFAULT_CSS = """
    HeaderBand {
        height: auto;
        padding: 0 1;
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
        color: $accent;
        text-style: bold;
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
                yield Static(f"offgrid @ {self._sha}", id=BUILD, markup=False)
                yield Static(f"{self._cwd}  ·  {INHERITS}", id=CWD, markup=False)
                yield Static(f"theme: {self._theme}", id=THEME, markup=False)
