"""Parameter counts read from a model's identifier.

Runtimes report quantization and context length but not how large a model is,
so the only available source is the name its publisher gave it. The convention
is widespread but not a specification, which is why an unreadable name yields
no answer rather than a guess.
"""

import re

BILLION = 1e9

# A size is a number followed by "b". Two guards keep other numbers out. The
# leading separator means a digit fused to the name is a version rather than a
# size, so qwen3.6b states no size and Mixtral-8x7B states a number of experts.
# The trailing lookahead means a quantization label is not a size either, so
# mlx-4bit is not a four billion parameter model. Publishers write fractions
# with either a dot or an underscore: 1.5b and 1_6b are both sizes.
_SIZE = r"(\d+(?:[._]\d+)?)b"
_TOTAL = re.compile(rf"[-_/]{_SIZE}(?![a-z0-9])", re.IGNORECASE)
_ACTIVE = re.compile(rf"[-_/]a{_SIZE}(?![a-z0-9])", re.IGNORECASE)
# Gemma reports the parameters actually held in memory as "e4b".
_EFFECTIVE = re.compile(rf"[-_/]e{_SIZE}(?![a-z0-9])", re.IGNORECASE)


def _first(pattern: re.Pattern[str], identifier: str) -> float | None:
    """Read the first size a pattern finds.

    :param pattern: A pattern whose first group is a number of billions.
    :param identifier: The model identifier to read.

    :return: The count in parameters, or ``None`` when the pattern misses.
    """
    found = pattern.search(identifier)
    if found is None:
        return None

    return float(found.group(1).replace("_", ".")) * BILLION


def parameter_counts(identifier: str) -> tuple[float | None, float | None]:
    """Total and active parameter counts named in a model identifier.

    Gemma names the parameters it holds in memory rather than the parameters
    it has, as ``e4b``. That figure is the one memory sizing needs, so it
    stands in for the total.

    :param identifier: The identifier a runtime reports, e.g.
        ``qwen/qwen3.6-35b-a3b``.

    :return: ``(total, active)``. Both are ``None`` when the name states no
        total, including when it names an active count alone: a model that
        cannot be sized must not report a speed either. ``active`` is ``None``
        for dense models, where every parameter is read for every token.
    """
    total = _first(_TOTAL, identifier)
    if total is None:
        total = _first(_EFFECTIVE, identifier)

    if total is None:
        return None, None

    return total, _first(_ACTIVE, identifier)
