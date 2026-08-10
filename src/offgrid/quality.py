"""How good a fit is, as one number and one word.

Four terms: room left after the weights, what the list says the model is
worth at coding, how fast this machine decodes it, and how long a session
the window holds. The shape is the one onyx.app scores its own table with,
and `docs/decisions.md` records where offgrid's differs from theirs and why.

Speed is scored off the figure a person reads in the table, so the word and
the number agree.
"""

import math
from dataclasses import dataclass

from offgrid.listing import Fit
from offgrid.machine import Machine
from offgrid.speed import tokens_per_second

HEADROOM_POINTS = 45
SCORE_POINTS = 30
SPEED_POINTS = 13
CONTEXT_POINTS = 12

# The four terms reach 100 together, on a model small and fast and good
# enough to take all of them. Nothing is called perfect: a composite of
# published figures is not a measurement, and the top of the scale is where
# that shows most.
BEST = 97

# Below this share of the memory the GPU may use, the weights cost nothing in
# the figure; above it what is left falls away faster than it is spent.
COMFORTABLE_SHARE = 70
CROWDING = 2.5

# Speed and window are both scored by their logarithm, so 5 to 10 tokens a
# second counts for as much as 100 to 200. Full marks at 200 and at 256K.
UNUSABLE_SPEED = 5
AMPLE_SPEED = 200
SHORTEST_CONTEXT = 4096
AMPLE_CONTEXT = 256_000

# A row stating no window is unknown rather than short.
UNSTATED_CONTEXT_POINTS = 4

LABELS = ((85, "excellent"), (70, "good"), (50, "decent"), (30, "weak"))


@dataclass(frozen=True)
class Quality:
    """What a fit is worth on this machine, and what to call it.

    :param score: The composite, at most 97.
    :param label: The word for that score, e.g. ``excellent``.
    """

    score: int
    label: str


def get_quality(fit: Fit, machine: Machine) -> Quality:
    """Judge a fit on room, published score, speed here, and window.

    :param fit: The model, at one of the widths this machine holds it at.
    :param machine: The host it would run on.

    :return: The composite and its label. A term offgrid cannot compute —
        an unmeasured chip, an unpublished score — contributes nothing
        rather than a guess, so the fit reads worse rather than wrong.
    """
    score = min(
        BEST,
        _headroom(fit, machine)
        + _published(fit)
        + _speed(fit, machine)
        + _context(fit.listing.context_window),
    )

    return Quality(score=score, label=_label(score))


def _headroom(fit: Fit, machine: Machine) -> int:
    """Score what the weights leave behind them.

    :return: Points for the room left over.
    """
    used = round(fit.weights_bytes / machine.usable_bytes * 100)
    if used <= COMFORTABLE_SHARE:
        return HEADROOM_POINTS

    spare = (100 - used) / (100 - COMFORTABLE_SHARE)

    return round(HEADROOM_POINTS * spare**CROWDING)


def _published(fit: Fit) -> int:
    """Score what the list says the model is worth at coding.

    :return: Points for the published score, or none where there is none.
    """
    # `recommend` drops a listing with no score before it ranks anything, so
    # this cannot fire today. It stays because the field is optional and the
    # type checker reads it as one.
    published = fit.listing.coding_score
    if published is None:
        return 0

    return round(published / 100 * SCORE_POINTS)


def _speed(fit: Fit, machine: Machine) -> int:
    """Score how fast this machine decodes the fit.

    :return: Points for the speed, or none for a chip nobody measured.
    """
    estimated = tokens_per_second(fit, machine)
    if estimated is None:
        return 0

    shown = min(max(round(estimated), UNUSABLE_SPEED), AMPLE_SPEED)
    reach = math.log2(shown / UNUSABLE_SPEED) / math.log2(AMPLE_SPEED / UNUSABLE_SPEED)

    return round(reach * SPEED_POINTS)


def _context(window: int | None) -> int:
    """Score how long a session the window holds.

    :return: Points for the window.
    """
    if not window:
        return UNSTATED_CONTEXT_POINTS

    if window <= SHORTEST_CONTEXT:
        return 1

    reach = math.log2(window / SHORTEST_CONTEXT) / math.log2(
        AMPLE_CONTEXT / SHORTEST_CONTEXT
    )

    return min(CONTEXT_POINTS, round(reach * CONTEXT_POINTS))


def _label(score: int) -> str:
    """Say in a word what a score amounts to.

    :return: The word for it.
    """
    for floor, label in LABELS:
        if score >= floor:
            return label

    return "poor"
