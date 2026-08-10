"""Which of a published list's models this machine can hold, best first.

Three rules take a row off the list, and each is counted rather than left
silent: no parameter count, so it cannot be sized; no coding score, so it
cannot be ranked; too large at every width. What survives is ordered by what
it is worth here.

Nothing here is said to anybody. `recommendation.py` is where that happens.
"""

from offgrid.listing import Fit, Listing, Table, widths_that_fit
from offgrid.machine import Machine
from offgrid.quality import Quality, quality


def shortlist(
    table: Table, machine: Machine
) -> tuple[list[tuple[Quality, Fit]], list[tuple[int, str]]]:
    """Keep what this machine can hold, judge it, and count what was dropped.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: Each fit with what it is worth, best first, and one
        ``(count, rule)`` pair per rule that took something.
    """
    kept, dropped = _kept(table, machine)

    return ranked(kept, machine), dropped


def ranked(fits: list[Fit], machine: Machine) -> list[tuple[Quality, Fit]]:
    """Put the best of what fits first, judging each one once.

    :param fits: Every model at every width this machine holds it at.
    :param machine: The host they would run on.

    :return: Each fit with what it was judged to be worth, best first, and
        the leaner width first where two are judged the same — the cheaper
        build is the one to read as the default.
    """
    judged = [(quality(fit, machine), fit) for fit in fits]

    return sorted(judged, key=lambda pair: (-pair[0].score, pair[1].quantization_bits))


def showable(table: Table) -> list[Listing]:
    """Keep the rows that a machine with the room would actually be shown.

    A row the table scores at nothing is dropped whatever its size, so it is
    not one of these however small it is.

    :param table: The published list, as it was read.

    :return: The listings that survive every rule but the one about room.
    """
    return [one for one in table.listings if one.coding_score is not None]


def _kept(table: Table, machine: Machine) -> tuple[list[Fit], list[tuple[int, str]]]:
    """Apply the three rules, keeping what survives and counting the rest.

    The rules run in order and no row is counted twice: one published with
    no size never reaches the rule about scores.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: Every fit there is to rank, and one ``(count, rule)`` pair per
        rule that took something.
    """
    scored = showable(table)
    widths = [(one, widths_that_fit(one, machine)) for one in scored]
    too_large = [one for one, found in widths if not found]

    counted = (
        (table.unsized, "published no size"),
        (len(table.listings) - len(scored), "published no coding score"),
        (len(too_large), "too large for this machine at every width"),
    )

    return [fit for _, found in widths for fit in found], [
        pair for pair in counted if pair[0]
    ]
