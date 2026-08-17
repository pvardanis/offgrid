"""Adapters for the published lists offgrid recommends from.

One module per list, each a fetcher and a parser, and the registry naming
which of them offgrid has. Nothing else is exported: `import-linter` reads
import statements as written, so a re-exported `onyx` would be
indistinguishable from the import `cli.py` legitimately makes — and the rule
that only a registry may import a concrete adapter would stop being checkable.

It is ordered, and the order is preference. What that order means is
`domain/sizing/reading.py`'s, which is handed this and asks each in turn: a
module that chooses between lists is policy rather than an adapter.
"""

from offgrid.domain.sizing.leaderboard import Leaderboard
from offgrid.leaderboards import onyx

LEADERBOARDS: tuple[Leaderboard, ...] = (
    Leaderboard(fetch=onyx.fetch, parse=onyx.parse),
)
