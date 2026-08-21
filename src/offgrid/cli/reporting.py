"""What offgrid's own errors look like at the terminal.

Every command that reaches past the profile can fail in offgrid's own words,
so the sentence they are said as lives here rather than in whichever command
was written first.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import typer

from offgrid.shared.exceptions import OffgridError
from offgrid.shared.say import tell


@contextmanager
def reporting() -> Iterator[None]:
    """Say what went wrong and stop, rather than raising at the terminal.

    offgrid's own errors carry the operation, the input and what to do next,
    which a traceback buries.

    :yield: To the operation being run.
    """
    try:
        yield
    except OffgridError as error:
        tell(f"{error}")
        raise typer.Exit(1) from error
