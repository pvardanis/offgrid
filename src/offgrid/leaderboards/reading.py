"""Which table a recommendation is made from, and what to say about it.

A published list is somebody else's site, and the machine reading it may have
no network at all. So there are two ways to arrive at a table — fetched now,
or kept from the last run that managed to fetch one — and which of the two it
was is something whoever asked has to be told.

Nothing here says anything; it returns the lines and the command line says
them.
"""

from dataclasses import dataclass
from pathlib import Path

from offgrid.exceptions import (
    LeaderboardUnavailableError,
    LeaderboardUnreachableError,
    LeaderboardUnreadableError,
)
from offgrid.leaderboards import cache
from offgrid.leaderboards.onyx import fetch, parse
from offgrid.listing import Table


@dataclass(frozen=True)
class Reading:
    """A table to recommend from, and what is not straightforward about it.

    :param table: The published list, as it was read.
    :param caveats: Lines to say above the table where something about it
        needs saying: that it is not a current one and how old it is, or that
        this one could not be kept for next time. Empty where a fetch worked
        and was kept, which is the ordinary case and needs no words.
    """

    table: Table
    caveats: list[str]


def get_reading(file_path: Path) -> Reading:
    """Read the published list, falling back on the last one that was read.

    A payload is kept only once it has parsed. Keeping one that did not would
    take the fall back away at the moment it is all the command has left.

    :param file_path: Where the last table read is kept.

    :return: The table to recommend from, and what to say about it.

    :raise LeaderboardUnavailableError: When nothing answered and there is no
        table kept from a run that reached one.
    """
    try:
        payload = fetch()
    except LeaderboardUnreachableError as error:
        return _get_cached_reading(error, file_path)

    try:
        table = parse(payload)
    except LeaderboardUnreadableError as error:
        return _get_cached_reading(error, file_path)

    return Reading(table=table, caveats=_keep(payload, file_path))


def _keep(payload: str, file_path: Path) -> list[str]:
    """Keep the payload that parsed, and say so where it cannot be kept.

    Nowhere to write is not a reason to throw away a table this run already
    has in hand. It is a reason to say so, because the run that finds no
    network is the one that will find nothing kept for it either.

    :param payload: What the source answered.
    :param file_path: Where to keep it.

    :return: The lines to say, or none where it was kept.
    """
    try:
        cache.save(payload, file_path)
    except OSError as error:
        return [
            f"  This table could not be kept at {file_path}: {error}.",
            "  A run that reaches nothing will have none to fall back on until",
            "  that is fixed.",
            "",
        ]

    return []


def _get_cached_reading(
    reason: LeaderboardUnavailableError, file_path: Path
) -> Reading:
    """Read back the last table offgrid fetched, and say how old it is.

    What stopped this run is said either way. A page that has been rewritten
    has to be loud even where a kept table saves the answer, and a network
    that is not there has to be named so that nobody goes looking for a fault
    on this machine.

    :param reason: What stopped this run reading a current one.
    :param file_path: Where the last table read is kept.

    :return: The table as it stood when it was last read, and the lines
        saying what happened and how old it is.

    :raise LeaderboardUnavailableError: When there is no kept table to fall
        back on. Nothing was read and nothing was kept, so what is left to
        say is where numbers measured on this machine already are.
    """
    kept = cache.load(file_path)
    table = _reparsed(kept)

    # Nothing kept and nothing readable are the same answer here. Both halves
    # are stated because the date below is read off `kept`.
    if kept is None or table is None:
        raise LeaderboardUnavailableError(
            f"{reason} No table was kept by an earlier run either, so there "
            "is none to fall back on. docs/models.md holds what has been "
            "measured on this machine by hand."
        ) from reason

    return Reading(
        table=table,
        caveats=[
            f"  {reason}",
            f"  This is the table offgrid read on {kept.dated}, not a current one.",
            "",
        ],
    )


def _reparsed(kept: cache.Cached | None) -> Table | None:
    """Read a kept payload the way the one it was kept from was read.

    :param kept: What was kept, if anything was.

    :return: The table it holds, or ``None`` where it holds none. A payload
        kept before the parser knew what it knows now is no table, and this
        run already has a failure to report.
    """
    if kept is None:
        return None

    try:
        return parse(kept.payload)
    except LeaderboardUnreadableError:
        return None
