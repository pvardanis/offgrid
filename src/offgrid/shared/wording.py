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
"""

from collections.abc import Callable

# The widest a line may be where offgrid prints what somebody else wrote, so
# that it reads beside offgrid's own lines rather than wrapping under them. It
# is the width the reports either side of it are written to by hand.
LINE_WIDTH = 76


DescribeModelDownload = Callable[[str], str]
"""How a runtime says one of its models is downloaded, given the model's name.

The answer names that model, and arrives in lines no wider than `LINE_WIDTH` —
nothing reflows it, since a command in it has to survive being copied.
`tests/test_runtime_downloading.py` holds every adapter to both.

Here because the registry that holds one per runtime and the report that
prints it are in layers that may not import each other, and both need to say
what it is.
"""


def describe_what_was_stated(value: int | None) -> str:
    """Say what number was stated, or that none was.

    :param value: The number stated, or ``None`` where none was.

    :return: The text to read it as.
    """
    return "unstated" if value is None else str(value)
