"""How offgrid words what it prints, where more than one layer prints it.

A runtime and a published list are both free to answer nothing for a number,
and nothing is not zero: the types those are read into validate neither, so
falsiness reports a number that arrived as one that never came. Numbers only —
where a string is absent or empty, a reader is owed the same word for both,
and each place that prints one has its own.

Here rather than beside the output channel, so that the sizing domain, which
composes lines it does not say, need not reach the module that configures
logging. The width an adapter writes its own lines to is here for the same
reason: what a runtime says about downloading is written in one layer, printed
by another, and checked by a third.

The columns a report is read in are here for the third reason: two reports are
laid out in them — what a run was told, and what arming a pairing would cost —
and a column width written twice is two reports that come to lay the same fact
out differently.
"""

from collections.abc import Callable
from re import sub
from textwrap import fill
from unicodedata import east_asian_width

# The widest a line may be where offgrid prints what somebody else wrote, so
# that it reads beside offgrid's own lines rather than wrapping under them. It
# is the width the reports either side of it are written to by hand.
LINE_WIDTH = 76

COLUMN = 19
"""How wide a label is, so every value in a report starts at one column.

Wide enough that the longest label still has a gap after it once the indent an
indented one carries is taken off. A word too long for it names what is
indented under it instead, and stands on its own line.
"""

UNDER = "  "
"""Where a fact about the line above it goes."""

REMEDY = "    "
"""Where what to do about the line above it goes, deeper than a fact."""

NBSP = "\u00a0"
"""What a space inside a command is while a sentence is being broken up.

Written as its escape rather than as the character, which is invisible in a
file and reads as an ordinary space to whoever opens it next.
"""


DescribeModelDownload = Callable[[str], str]
"""How a runtime says one of its models is downloaded, given the model's name.

The answer names that model, and arrives in lines no wider than `LINE_WIDTH` —
nothing reflows it, since a command in it has to survive being copied. It
answers rather than raises: the picker calls it as the highlight moves, with no
handler around it, so a describer that reached a server and failed would escape
onto the event loop. `tests/test_runtime_downloading.py` holds every adapter to
all three.

Here because the registry that holds one per runtime and the report that
prints it are in layers that may not import each other, and both need to say
what it is.
"""


REACHING_THE_NETWORK = (
    "Reaching the published list now. This is the only time offgrid uses\n"
    "the network: nothing about this machine is sent, and no cookie is kept."
)
"""What is said before a published list is fetched, on both surfaces.

`recommend` and the picker each reach the same page, and neither reaches it
until asked. Said before the fetch rather than after it, so a person is told
that this one thing touches the network before it happens rather than once it
already has. Here because two layers say it and a fact worded twice is two
surfaces that come to word it differently.
"""


def describe_what_was_stated(value: int | None) -> str:
    """Say what number was stated, or that none was.

    :param value: The number stated, or ``None`` where none was.

    :return: The text to read it as.
    """
    return "unstated" if value is None else str(value)


def say_indented(
    indent: str, sentence: str, width: int = LINE_WIDTH
) -> tuple[str, ...]:
    """Break a sentence into lines that all start where the first one does.

    A sentence long enough to wrap is one a terminal wraps at the left margin,
    which puts the rest of it under the labels rather than under the line it
    belongs to. Broken here, every line of it reads as the one thing it is.

    What is inside backticks is held together, because a command broken across
    two lines is one somebody pastes and watches fail. One too long for the
    width overflows rather than breaking, for the same reason — and a hyphen
    is not a place to break either, since the sentences here carry paths and
    flags, and half of one at the end of a line is a path to nothing.

    :param indent: Where the sentence starts, and where it carries on.
    :param sentence: What is being said.
    :param width: How wide it may run before it breaks. The reports are
        written by hand to the default; a list beside them has its own.

    :return: The lines of it, in order.
    """
    held = sub(r"`[^`]*`", lambda command: command.group().replace(" ", NBSP), sentence)

    return tuple(
        fill(
            held,
            width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        .replace(NBSP, " ")
        .splitlines()
    )


def count_cells(text: str) -> int:
    """Count how much room a piece of text takes on a terminal.

    Not its length: an emoji is one character and two cells wide, so a column
    padded by counting characters is a column that lines up in the file and
    not on the screen.

    :param text: What is being measured.

    :return: How many cells it occupies.
    """
    return sum(2 if east_asian_width(one) in "WF" else 1 for one in text)


def pad_to_cells(text: str, cells: int) -> str:
    """Fill a piece of text out to a fixed width on a terminal.

    :param text: What goes in the column.
    :param cells: How wide the column is.

    :return: The text, followed by enough spaces to fill the column, and
        unpadded where it is already wider.
    """
    return text + " " * max(0, cells - count_cells(text))


def center_in_cells(text: str, cells: int) -> str:
    """Centre a piece of text in a fixed width on a terminal.

    So that a column and the mark filling it share a centre rather than a left
    edge: a two-cell mark and its wider heading start in different cells but
    read as one column when both sit in the middle of it.

    :param text: What goes in the column.
    :param cells: How wide the column is.

    :return: The text with spaces either side, split as evenly as an odd
        remainder allows, and unpadded where it is already wider.
    """
    room = max(0, cells - count_cells(text))

    return " " * (room // 2) + text + " " * (room - room // 2)


def say_in_columns(label: str, value: str, *, under: bool = False) -> str:
    """Lay one fact out in the columns a report is read in.

    A fact about the line above is indented and its label narrowed by as much,
    so that every value in the report still starts at the same column however
    deep the thing it is about sits.

    :param label: What the fact is about.
    :param value: What is said about it.
    :param under: Whether it is a fact about the line above rather than one
        of the things the report is a list of.

    :return: The line, as it is read.
    """
    lead = UNDER if under else ""

    return f"{lead}{label:<{COLUMN - len(lead)}}{value}"
