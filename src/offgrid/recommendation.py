"""The listings that fit this machine, ranked, and what that reads as.

A recommendation is what offgrid says is worth trying: the models a published
list names, kept to the ones this machine can hold, judged and ordered. It
accounts for every row it left out, and says who stands behind every figure
it shows. Downloading one, and choosing between what is left, stay a person's.

Nothing here says anything; it returns the lines and the command line says
them.
"""

from offgrid.fit import QUANTIZATION_WIDTHS, parameters_that_fit, weights_bytes
from offgrid.leaderboards.onyx import URL as LEADERBOARD
from offgrid.listing import Fit, Table, widths_that_fit
from offgrid.machine import Machine, raising_the_gpu_limit
from offgrid.quality import Quality, quality
from offgrid.speed import tokens_per_second

# One layout, so the heading and the models under it cannot drift apart.
COLUMNS = (
    "    {model:<22}{quality:>14}{score:>7}{speed:>7}"
    "{weights:>9}  {quant:<7}{context:>8}  {license}"
)
HEADING = COLUMNS.format(
    model="model",
    quality="quality",
    score="swe",
    speed="tok/s",
    weights="weights",
    quant="quant",
    context="context",
    license="license",
)

# What a column says where offgrid has no figure for it, as against a figure
# it has and prints.
NOTHING = "—"

# Sizes are said in gigabytes of the kind a disk is sold in, as the rest of
# offgrid says them.
BILLION = 1e9


def recommendation(table: Table, machine: Machine) -> list[str]:
    """Say what this machine can hold off a published list, best first.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: Every line to say, in order.
    """
    fits, dropped = _shortlist(table, machine)
    ranked = _ranked(fits, machine)

    said = _preamble(len(ranked), table.dated)

    if not ranked:
        return (
            said
            + _nothing_fits(table, machine)
            + _under(raising_the_gpu_limit(machine))
            + _under(_accounting(table, dropped))
        )

    return (
        said
        + [HEADING]
        + [_row(fit, judged, machine) for judged, fit in ranked]
        + _under(_accounting(table, dropped))
        + _under(_provenance(table.dated))
        + ["", "  Download one in your runtime, then `offgrid run`."]
    )


def _preamble(rows: int, dated: str | None) -> list[str]:
    """Say what is about to be shown, and where it was read.

    A single row is stated rather than ranked: a list filtered down to one
    model is not a ranking, and announcing one would say the rows that are
    missing had been beaten rather than dropped. No row at all promises
    nothing, since what follows is about the list rather than about models.

    :param rows: How many models at a width there are to show.
    :param dated: The date the list gives itself.

    :return: The lines to say, ending in a blank one.
    """
    openings = {
        0: "  From the list at",
        1: "  One model on this list fits this machine. From the list at",
    }
    opening = openings.get(rows, "  Models that fit this machine, from the list at")

    return [opening, f"  {LEADERBOARD}, table dated {dated or 'undated'}.", ""]


def _shortlist(
    table: Table, machine: Machine
) -> tuple[list[Fit], list[tuple[int, str]]]:
    """Keep what this machine can hold, and count what each rule dropped.

    The rules run in order and no row is counted twice: one published with
    no size never reaches the rule about scores.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.

    :return: Every fit there is to rank, and one ``(count, rule)`` pair per
        rule that took something.
    """
    unscored = [one for one in table.listings if one.coding_score is None]
    widths = [
        (one, widths_that_fit(one, machine))
        for one in table.listings
        if one.coding_score is not None
    ]
    too_large = [one for one, found in widths if not found]

    counted = (
        (table.unsized, "published no size"),
        (len(unscored), "published no coding score"),
        (len(too_large), "too large for this machine at every width"),
    )

    return [fit for _, found in widths for fit in found], [
        pair for pair in counted if pair[0]
    ]


def _accounting(table: Table, dropped: list[tuple[int, str]]) -> list[str]:
    """Say how many rows each rule took, so an absence is explainable.

    A rule that took nothing explains no absence, so it is not printed.

    :param table: The published list, as it was read.
    :param dropped: What each rule took.

    :return: The lines to say, or none where nothing was dropped.
    """
    if not dropped:
        return []

    rows = table.unsized + len(table.listings)
    figures = max(len(str(count)) for count, _ in dropped)

    return [f"  Left out of the {rows} row{'' if rows == 1 else 's'} on the table:"] + [
        f"    {count:>{figures}}  {rule}" for count, rule in dropped
    ]


def _provenance(dated: str | None) -> list[str]:
    """Say who stands behind each column, under every row shown.

    Three claims, true of every row: where the figures came from, that the
    source cites nobody for any of its own, and that offgrid measured none of
    them. What it does not claim is that they are the vendors' own numbers —
    that was established for two models by hand and lives in
    `docs/models.md`, and the table says nothing about who measured what.

    :param dated: The date the list gives itself.

    :return: The lines to say.
    """
    source = f"the table dated {dated}" if dated else "the undated table"

    return [
        f"  The swe, context and licence columns are as {source}",
        "  published them, and it states no source for any figure of its own.",
        "  The weights, tok/s and quality columns are offgrid's arithmetic, the",
        "  last two of them for this machine. offgrid has run none of these models.",
    ]


def _nothing_fits(table: Table, machine: Machine) -> list[str]:
    """Put the limit on the list rather than on the machine.

    The smallest model this list publishes needs about 14GB, so a 16GB Mac
    fits none of them while decoding a 1.2B model at 191 tok/s — a figure
    `docs/models.md` measured on this hardware. "Nothing fits your hardware"
    would tell that person the opposite of the truth, and of what offgrid is
    for. So what is named is where the list starts.

    :param table: The published list, as it was read.
    :param machine: The host none of it fits.

    :return: The lines to say.
    """
    # The leanest width, where the smallest of everything is.
    bits = min(QUANTIZATION_WIDTHS)
    holds = parameters_that_fit(machine, bits)

    # A row the table scores at nothing is dropped at any size, so its size is
    # not where the list starts — naming it sends someone after room that
    # would still show them nothing. Scored nought is scored, as it is to the
    # rule that keeps a row, or the two disagree about the same listing.
    showable = [
        one.parameters for one in table.listings if one.coding_score is not None
    ]
    smallest = min(showable or [one.parameters for one in table.listings])

    return [
        "  Nothing on this list fits this machine.",
        "",
        f"    the smallest model on it needs {_memory_for(smallest, bits)}"
        f" at {bits}-bit",
        f"    this machine has room for {_memory_for(holds, bits)}",
        "",
        "  That is where this list starts, not where this machine stops.",
        "  Models smaller than any it publishes run here.",
    ]


def _ranked(fits: list[Fit], machine: Machine) -> list[tuple[Quality, Fit]]:
    """Put the best of what fits first, judging each one once.

    :param fits: Every model at every width this machine holds it at.
    :param machine: The host they would run on.

    :return: Each fit with what it was judged to be worth, best first, and
        the leaner width first where two are judged the same — the cheaper
        build is the one to read as the default.
    """
    judged = [(quality(fit, machine), fit) for fit in fits]

    return sorted(judged, key=lambda pair: (-pair[0].score, pair[1].quantization_bits))


def _row(fit: Fit, judged: Quality, machine: Machine) -> str:
    """Lay out one model of the recommendation.

    :param fit: The model, at one of the widths this machine holds it at.
    :param judged: What that fit is worth here.
    :param machine: The host it would run on.

    :return: The line to say.
    """
    # Every row reaching here has a score: a listing without one is dropped
    # before anything is ranked, since it cannot be.
    published = fit.listing.coding_score
    speed = tokens_per_second(fit, machine)

    return COLUMNS.format(
        model=fit.listing.name,
        quality=f"{judged.label} {judged.score}",
        score=f"{published:.1f}",
        speed=f"~{speed:.0f}" if speed else NOTHING,
        weights=_gigabytes(fit.weights_bytes),
        quant=f"{fit.quantization_bits}-bit",
        context=str(fit.listing.context_window or "unstated"),
        # Printed, never read: it is absent on one open-weight row and a
        # date on another, so nothing here can branch on it.
        license=fit.listing.license or "unstated",
    )


def _memory_for(parameters: float, bits: int) -> str:
    """Say how much memory a number of parameters takes at a width.

    :param parameters: How many there are.
    :param bits: Bits per stored parameter, e.g. ``4``.

    :return: The size, as a person reads one.
    """
    return _gigabytes(weights_bytes(parameters, bits))


def _gigabytes(byte_count: float) -> str:
    """Say a number of bytes the way the columns and the sentences both do.

    :param byte_count: How many there are.

    :return: The size, as a person reads one.
    """
    return f"{byte_count / BILLION:.1f}GB"


def _under(lines: list[str]) -> list[str]:
    """Set a group of lines off from what came before it.

    :param lines: What to say, which may be nothing.

    :return: The lines under a blank one, or none where there are none.
    """
    return ["", *lines] if lines else []
