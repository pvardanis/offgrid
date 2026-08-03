"""Parameter counts read from a model's identifier.

Runtimes report quantization and context length but not how large a model is,
so the only available source is the name its publisher gave it. The convention
is widespread but not a specification, which is why an unreadable name yields
no answer rather than a guess.
"""

import re

BILLION = 1e9

# A size is a number followed by "b", introduced by a separator so that a
# version like qwen3.6 or llama-3.1 cannot be read as a parameter count.
_SIZE = r"(\d+(?:\.\d+)?)b"
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
    return float(found.group(1)) * BILLION if found else None


def parameter_counts(identifier: str) -> tuple[float | None, float | None]:
    """Total and active parameter counts named in a model identifier.

    :param identifier: The identifier a runtime reports, e.g.
        ``qwen/qwen3.6-35b-a3b``.

    :return: ``(total, active)``. ``total`` is ``None`` when the name states
        no size; ``active`` is ``None`` for dense models, where every
        parameter is read for every token.
    """
    total = _first(_TOTAL, identifier) or _first(_EFFECTIVE, identifier)
    return total, _first(_ACTIVE, identifier)
