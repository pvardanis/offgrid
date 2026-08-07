"""A model as a published list describes it, and where it fits.

A listing is what someone else published: a name, a size, a context window
and a licence. Nothing about this machine, and nothing about whether the
model has been downloaded. What this machine makes of one is the fit.
"""

from dataclasses import dataclass

from offgrid.fit import BITS_PER_BYTE, sizes_that_fit
from offgrid.machine import Machine


@dataclass(frozen=True)
class Listing:
    """One model as a published list states it.

    :param name: The model's name as published, e.g. ``Qwen3.6-35B-A3B``.
        Not an identifier any runtime answers to.
    :param parameters: How many parameters it has. A listing without one
        cannot be sized, and is not a listing.
    :param context_window: Tokens it is published as taking, or ``None``
        when the list states none.
    :param license: The licence as published, which offgrid prints and does
        not read: it is absent on some open-weight rows and a date on others.
    """

    name: str
    parameters: float
    context_window: int | None
    license: str | None


@dataclass(frozen=True)
class Table:
    """A published list, as it stood when it was fetched.

    :param dated: The date the list states it was last updated, or ``None``
        when it states none. What it says about itself, not when it was
        fetched.
    :param listings: The models on it that carry enough to be sized.
    """

    dated: str | None
    listings: list[Listing]


@dataclass(frozen=True)
class Fit:
    """A listing at one of the widths a machine has room for it at.

    The same model is a different proposition at each width, which is why a
    fit is a listing and a width together rather than a property of either.

    :param listing: The model as published.
    :param quantization_bits: Bits per stored parameter, e.g. ``4``.
    :param weights_bytes: What holding it costs at that width. Weights only:
        the room for the context cache is what ``fit.py`` set aside before
        deciding this fits at all.
    """

    listing: Listing
    quantization_bits: int
    weights_bytes: float


def widths_that_fit(listing: Listing, machine: Machine) -> list[Fit]:
    """Work out which quantization widths a machine holds a listing at.

    :param listing: The model as published.
    :param machine: The host it would run on.

    :return: One fit per width the machine has room for, leanest first.
        Empty when it fits at none.
    """
    return [
        Fit(
            listing=listing,
            quantization_bits=bits,
            weights_bytes=listing.parameters * bits / BITS_PER_BYTE,
        )
        for bits, parameters in sizes_that_fit(machine)
        if listing.parameters <= parameters
    ]
