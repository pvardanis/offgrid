"""Which of a published list's models this machine can hold, best first.

Three rules take a row off the list, and each is counted rather than left
silent: no parameter count, so it cannot be sized; no coding score, so it
cannot be ranked; too large at every width. What survives is ordered by what
it is worth here.

Nothing here is said to anybody. `recommendation.py` is where that happens.
"""

from dataclasses import dataclass

from offgrid.listing import Fit, Listing, Table, get_listing_with_feasible_widths
from offgrid.machine import Machine
from offgrid.quality import Quality, get_quality_for_fit


@dataclass(frozen=True)
class Dropped:
    """How many rows one rule took off the published list.

    :param count: How many it took. Never nought: a rule that took nothing
        explains no absence and is not carried.
    :param rule: Why they went, as a person reads it, e.g. ``published no
        size``.
    """

    count: int
    rule: str


@dataclass(frozen=True)
class Shortlist:
    """What a machine makes of a published list.

    :param ranked: Each model at each width the machine holds it at, with
        what it is worth there, best first. Empty when nothing survived.
    :param dropped: One entry per rule that took a row, so that a model
        someone expected and did not find is explainable.
    """

    ranked: list[tuple[Quality, Fit]]
    dropped: list[Dropped]


def shortlist(table: Table, machine: Machine) -> Shortlist:
    """Narrow a published list to what this machine holds, and order it.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: What survived, best first, and what each rule took.
    """
    fits, dropped = _apply_the_rules(table, machine)

    return Shortlist(ranked=_rank_fits(fits, machine), dropped=dropped)


def get_listings_with_coding_score(table: Table) -> list[Listing]:
    """Keep the rows carrying the score the listings_with_coding_score sorts on.

    A row the table scores at nothing is dropped whatever its size, so it is
    not one of these however small it is. Scored nought is scored.

    :param table: The published list, as it was read.

    :return: The listings that survive every rule but the one about room.
    """
    return [one for one in table.listings if one.coding_score is not None]


def _rank_fits(fits: list[Fit], machine: Machine) -> list[tuple[Quality, Fit]]:
    """Put the best of what fits first, judging each one once.

    What a fit costs in memory and what it decodes at are already two of the
    four terms the composite is built from, so a dead heat means those were
    equal too. It is still reachable, because the composite is rounded to a
    whole number — so the order is settled here rather than left to the order
    the table happened to publish its rows in.

    :param fits: Every model at every width this machine holds it at.
    :param machine: The host they would run on.

    :return: Each fit with what it was judged to be worth, best first. Where
        two are judged the same, the leaner width comes first, then the one
        costing less memory to hold, then the name — the cheaper build is the
        one to read as the default, and the name makes the order the same on
        two machines reading one table.
    """
    judged = [(get_quality_for_fit(fit, machine), fit) for fit in fits]

    return sorted(
        judged,
        key=lambda pair: (
            -pair[0].score,
            pair[1].quantization_bits,
            pair[1].weights_bytes,
            pair[1].listing.name,
        ),
    )


def _apply_the_rules(table: Table, machine: Machine) -> tuple[list[Fit], list[Dropped]]:
    """Drop the rows that cannot be sized, cannot be ranked, or will not fit.

    The rules run in order and no row is counted twice: one published with
    no size never reaches the rule about scores.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: Every model at every width that survived, ready to be ranked,
        and how many rows each rule took.
    """
    listings_with_coding_score = get_listings_with_coding_score(table)
    listings_with_feasible_widths = [
        (one, get_listing_with_feasible_widths(one, machine))
        for one in listings_with_coding_score
    ]
    listings_not_fit = [
        one for one, found in listings_with_feasible_widths if not found
    ]

    taken = (
        Dropped(table.unsized_rows, "published no size"),
        Dropped(
            len(table.listings) - len(listings_with_coding_score),
            "published no coding score",
        ),
        Dropped(len(listings_not_fit), "too large for this machine at every width"),
    )

    return [fit for _, found in listings_with_feasible_widths for fit in found], [
        one for one in taken if one.count
    ]
