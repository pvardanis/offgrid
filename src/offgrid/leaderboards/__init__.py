"""Adapters for the published lists offgrid recommends from.

The registry is the one place a module becomes a list offgrid reads. Nothing
else is exported beside it: `import-linter` reads import statements as
written, so a re-exported `onyx` would be indistinguishable from the import
`reading.py` legitimately makes — and the rule that only a registry may import
a concrete adapter would stop being checkable.

It is ordered, and the order is preference: `reading.py` asks each in turn and
answers from the first that has a table. A list added below the one above it
is the one that answers when the site above is down.
"""

from offgrid.domain.sizing.leaderboard import Leaderboard
from offgrid.leaderboards import onyx

LEADERBOARDS: tuple[Leaderboard, ...] = (
    Leaderboard(fetch=onyx.fetch, parse=onyx.parse),
)
