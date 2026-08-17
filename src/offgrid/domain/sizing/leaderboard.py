"""What offgrid needs of a published list, and which ones there are.

Not a Protocol, and the difference is the point. A published list holds no
state and answers two questions, so it is two typed callables kept together
rather than an object with methods.

Why it is shaped this way is in `docs/architecture.md` under "The leaderboard
seam".
"""

from collections.abc import Callable
from dataclasses import dataclass

from offgrid.domain.sizing.listing import Table

Fetch = Callable[[], str]
Parse = Callable[[str], Table]


@dataclass(frozen=True)
class Leaderboard:
    """One published list, as the thing that reads it asks for.

    The two are paired rather than registered apart, because parsing one
    list's payload with another list's parser is nonsense and nothing else
    would stop it.

    :param fetch: Ask the site for whatever the table is published in. Raises
        ``LeaderboardUnreachableError`` where nothing answers.
    :param parse: Read a table out of what came back. Raises
        ``LeaderboardUnreadableError`` where it holds no table this list can
        read — a page that has been redesigned, and equally a payload that is
        another list's altogether. Refusing that second one is what makes a
        kept payload safe to offer to every parser there is, so a parser that
        answered with an empty table instead would break the one file the
        lists share.
    """

    fetch: Fetch
    parse: Parse
