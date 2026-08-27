"""How a recommendation reads to whoever asked for one.

What is worth trying is `shortlist.py`'s answer. This is the words for it: the
table of rows, the count against every rule that dropped one, and the line
saying who stands behind each figure. Downloading a model, and choosing
between what is left, stay a person's.

Nothing here says anything; it returns the lines and the command line says
them.
"""

from collections.abc import Callable
from textwrap import fill

from offgrid.domain.sizing.fit import (
    BYTES_PER_GB,
    QUANTIZATION_WIDTHS,
    get_params_that_fit,
    weigh_model,
)
from offgrid.domain.sizing.listing import Fit, Table
from offgrid.domain.sizing.machine import Machine, suggest_raising_the_gpu_limit
from offgrid.domain.sizing.quality import Quality
from offgrid.domain.sizing.shortlist import (
    Dropped,
    Rule,
    get_listings_with_coding_score,
    shortlist,
)
from offgrid.domain.sizing.speed import tokens_per_second
from offgrid.shared.wording import describe_what_was_stated

DescribeDownload = Callable[[str], str]
"""How a runtime says one of its models is downloaded, given the model's name.

The runtime's own words, taken as a function rather than as its port: what
fits and what runs do not know each other, and this is the whole of what a
recommendation needs of a runtime.
"""

# How wide the runtime's own sentence is laid out at, matching the width the
# lines around it are written to by hand.
PROSE_WIDTH = 76

# One layout, so the heading and the models under it cannot drift apart.
COLUMNS = (
    "  {model:<22}{quality:>14}{score:>7}{speed:>7}"
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

# What each rule that drops a row is called where a person reads it. The rules
# themselves are `shortlist.py`'s; only the wording is here.
WHY_DROPPED = {
    Rule.NO_PARAMETER_COUNT: "published no size",
    Rule.NO_CODING_SCORE: "published no coding score",
    Rule.FITS_AT_NO_WIDTH: "too large for this machine at every width",
}


def summarize_findings(
    table: Table, machine: Machine, describe_download: DescribeDownload
) -> list[str]:
    """Say what this machine can hold off a published list, best first.

    :param table: The published list, as it was read.
    :param machine: The host the models would run on.
    :param describe_download: How the runtime says one of its models is
        downloaded, asked for the model ranked first. Nothing is said about
        downloading where nothing was ranked: there is no model to name.

    :return: Every line to say, in order.
    """
    shortlisted = shortlist(table, machine)
    ranked = shortlisted.ranked

    said = _introduce_findings(len(ranked), table)
    dropped = _say_what_was_dropped(table, shortlisted.dropped)

    if not ranked:
        return (
            said
            + _explain_nothing_fits(table, machine)
            + _set_off(suggest_raising_the_gpu_limit(machine))
            + _set_off(dropped)
        )

    return (
        said
        + [HEADING]
        + [_lay_out(fit, worth, machine) for worth, fit in ranked]
        + _set_off(dropped)
        + _set_off(_credit_the_figures(table.dated))
        + _set_off(_say_how_to_download(ranked[0][1], describe_download))
    )


def _say_how_to_download(fit: Fit, describe_download: DescribeDownload) -> list[str]:
    """Say how to have the model ranked first, in the runtime's own words.

    One model rather than every row: the instruction is the same sentence with
    a different name in it, and a table with one under each row is a table
    nobody reads. Which model is worked through is the one the ranking put at
    the top, so the name in it is a name on the screen.

    :param fit: The model ranked first, at the width it was ranked at.
    :param describe_download: How the runtime says one of its models is
        downloaded.

    :return: The lines to say.
    """
    said = fill(describe_download(fit.listing.name), PROSE_WIDTH).splitlines()

    return [*said, "Then `offgrid run`."]


def _introduce_findings(rows: int, table: Table) -> list[str]:
    """Say what is about to be shown, and where it was read.

    A single row is stated rather than ranked: a list filtered down to one
    model is not a ranking, and announcing one would say the rows that are
    missing had been beaten rather than dropped. No row at all promises
    nothing, since what follows is about the list rather than about models.

    :param rows: How many models at a width there are to show.
    :param table: The published list, as it was read.

    :return: The lines to say, ending in a blank one.
    """
    openings = {
        0: "From the list at",
        1: "One model on this list fits this machine. From the list at",
    }
    opening = openings.get(rows, "Models that fit this machine, from the list at")

    return [
        opening,
        f"{table.source}, table dated {table.dated or 'undated'}.",
        "",
    ]


def _say_what_was_dropped(table: Table, dropped: list[Dropped]) -> list[str]:
    """Say how many rows each rule took, so an absence is explainable.

    A rule that took nothing explains no absence, so it is not printed.

    :param table: The published list, as it was read.
    :param dropped: What each rule took.

    :return: The lines to say, or none where nothing was dropped.
    """
    if not dropped:
        return []

    rows = table.unsized_rows + len(table.listings)
    figures = max(len(str(one.count)) for one in dropped)

    return [f"Left out of the {rows} row{'' if rows == 1 else 's'} on the table:"] + [
        f"  {one.count:>{figures}}  {WHY_DROPPED[one.rule]}" for one in dropped
    ]


def _credit_the_figures(dated: str | None) -> list[str]:
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
        f"The swe, context and licence columns are as {source}",
        "published them, and it states no source for any figure of its own.",
        "The weights, tok/s and quality columns are offgrid's arithmetic, the",
        "last two of them for this machine. offgrid has run none of these models.",
    ]


def _explain_nothing_fits(table: Table, machine: Machine) -> list[str]:
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
    # A row the table scores at nothing is dropped at any size, so its size is
    # not where the list starts — naming it sends someone after room that
    # would still show them nothing. With none of them scored there is no size
    # to name at all, and room was never what was missing.
    shown = get_listings_with_coding_score(table)
    if not shown:
        return _explain_nothing_ranks()

    # The leanest width, where the smallest of everything is.
    bits = min(QUANTIZATION_WIDTHS)
    holds = get_params_that_fit(machine, bits)
    smallest = min(one.parameters for one in shown)

    return [
        "Nothing on this list fits this machine.",
        "",
        f"  the smallest model on it needs {_write_size(smallest, bits)} at {bits}-bit",
        f"  this machine has room for {_write_size(holds, bits)}",
        "",
        "That is where this list starts, not where this machine stops.",
        "Models smaller than any it publishes run here.",
    ]


def _explain_nothing_ranks() -> list[str]:
    """Say the list gave nothing to order, which is not about room.

    Every row unscored is what the table's benchmark key migrating looks
    like, and `leaderboards/onyx.py` is written expecting it. Saying nothing
    fits would blame the memory of a machine that may hold all of them.

    :return: The lines to say.
    """
    return [
        "Nothing on this list can be ranked for this machine.",
        "",
        "Not one row it publishes carries the coding score the ranking",
        "sorts on, so there is nothing to rank. That is this list, and it",
        "says nothing about the room here.",
    ]


def _lay_out(fit: Fit, worth: Quality, machine: Machine) -> str:
    """Lay out one model of the recommendation.

    :param fit: The model, at one of the widths this machine holds it at.
    :param worth: What that fit is worth here.
    :param machine: The host it would run on.

    :return: The line to say.
    """
    # Every row reaching here has a score: a listing without one is dropped
    # before anything is ranked, since it cannot be.
    published = fit.listing.coding_score
    speed = tokens_per_second(fit, machine)

    return COLUMNS.format(
        model=fit.listing.name,
        quality=f"{worth.label} {worth.score}",
        score=f"{published:.1f}",
        speed=f"~{speed:.0f}" if speed else NOTHING,
        weights=_write_gigabytes(fit.weights_bytes),
        quant=f"{fit.quantization_bits}-bit",
        context=describe_what_was_stated(fit.listing.context_window),
        # Printed, never read: it is absent on one open-weight row and a
        # date on another, so nothing here can branch on it.
        license=fit.listing.license or "unstated",
    )


def _write_size(parameters: float, bits: int) -> str:
    """Say how much memory a number of parameters takes at a width.

    :param parameters: How many there are.
    :param bits: Bits per stored parameter, e.g. ``4``.

    :return: The size, as a person reads one.
    """
    return _write_gigabytes(weigh_model(parameters, bits))


def _write_gigabytes(byte_count: float) -> str:
    """Say a number of bytes the way the columns and the sentences both do.

    :param byte_count: How many there are.

    :return: The size, as a person reads one.
    """
    return f"{byte_count / BYTES_PER_GB:.1f}GB"


def _set_off(lines: list[str]) -> list[str]:
    """Set a group of lines off from what came before it.

    :param lines: What to say, which may be nothing.

    :return: The lines under a blank one, or none where there are none.
    """
    return ["", *lines] if lines else []
