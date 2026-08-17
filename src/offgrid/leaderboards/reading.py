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

from offgrid.domain.sizing.listing import Table
from offgrid.leaderboards import LEADERBOARDS, cache
from offgrid.shared.exceptions import (
    LeaderboardUnavailableError,
    LeaderboardUnreadableError,
)


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
    """Read a published list, falling back on the last table that was read.

    The lists are asked in the order the registry holds them, and the first
    with a table answers. A current table from a list further down beats a
    stale one from the list above it, so what was kept is the last resort
    rather than the first.

    A payload is kept only once it has parsed. Keeping one that did not would
    take the fall back away at the moment it is all the command has left.

    :param file_path: Where the last table read is kept.

    :return: The table to recommend from, and what to say about it.

    :raise LeaderboardUnavailableError: When no list answered and there is no
        table kept from a run that reached one.
    """
    refusals: list[LeaderboardUnavailableError] = []

    for leaderboard in LEADERBOARDS:
        try:
            payload = leaderboard.fetch()
            table = leaderboard.parse(payload)
        except LeaderboardUnavailableError as error:
            refusals.append(error)
            continue

        return Reading(
            table=table,
            caveats=_why_this_one(refusals, table) + _cache_payload(payload, file_path),
        )

    return _get_cached_reading(refusals, file_path)


def _why_this_one(
    refusals: list[LeaderboardUnavailableError], table: Table
) -> list[str]:
    """Say what the lists above this one did, and name the one answering.

    Every list above the one that answered was asked and failed, and each
    failure is worth the same sentence it would get if it were the only one:
    a site that has been down for a month and a page that has been rewritten
    are both things somebody has to go and look at.

    :param refusals: What each list above this one did instead of answering.
    :param table: The table this run is recommending from.

    :return: The lines to say, or none where the first list answered — which
        is the ordinary case and needs no words.
    """
    if not refusals:
        return []

    return [f"  {refusal}" for refusal in refusals] + [
        f"  Recommending from {table.source} instead.",
        "",
    ]


def _cache_payload(payload: str, file_path: Path) -> list[str]:
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
    refusals: list[LeaderboardUnavailableError], file_path: Path
) -> Reading:
    """Read back the last table offgrid fetched, and say how old it is.

    What stopped this run is said either way. A page that has been rewritten
    has to be loud even where a kept table saves the answer, and a network
    that is not there has to be named so that nobody goes looking for a fault
    on this machine.

    :param refusals: What each list did instead of answering, in the order
        they were asked. Never empty: every list there is has been asked by
        the time this is reached.
    :param file_path: Where the last table read is kept.

    :return: The table as it stood when it was last read, and the lines
        saying what happened and how old it is.

    :raise LeaderboardUnavailableError: When there is no kept table to fall
        back on. Nothing was read and nothing was kept, so what is left to
        say is where numbers measured on this machine already are.
    """
    cached_payload = cache.load(file_path)
    table = _reparsed(cached_payload)

    # Nothing kept and nothing readable are the same answer here. Both halves
    # are stated because the date below is read off the record itself.
    if cached_payload is None or table is None:
        raise LeaderboardUnavailableError(
            f"{' '.join(str(refusal) for refusal in refusals)} No table was "
            "kept by an earlier run either, so there is none to fall back on. "
            "docs/models.md holds what has been measured on this machine by "
            "hand."
        ) from refusals[-1]

    read_on = cached_payload.dated

    return Reading(
        table=table,
        caveats=[
            *(f"  {refusal}" for refusal in refusals),
            f"  This is the table offgrid read on {read_on}, not a current one.",
            "",
        ],
    )


def _reparsed(cached_payload: cache.Cached | None) -> Table | None:
    """Read a kept payload back with whichever list can read it.

    One file holds whatever was kept last and any of the lists may have
    written it, so each is offered the payload in turn. A parser refuses one
    that is not its own, and the table it answers with names its own source.

    :param cached_payload: What was kept, if anything was.

    :return: The table it holds, or ``None`` where no list can read it. A
        payload kept before the parser knew what it knows now is no table,
        and this run already has a failure to report.
    """
    if cached_payload is None:
        return None

    for leaderboard in LEADERBOARDS:
        try:
            return leaderboard.parse(cached_payload.payload)
        except LeaderboardUnreadableError:
            continue

    return None
