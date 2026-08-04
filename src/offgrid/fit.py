"""How large a model a machine can hold.

Which model to run is a choice offgrid leaves to whoever runs it. What it can
say is how much room there is, so that the choice is made against a number
rather than a guess.
"""

from offgrid.machine import Machine

BITS_PER_BYTE = 8

# Weights are not the whole of it: the cache grows with the context, and a
# machine filled to the brim with weights stalls on the first long prompt.
# A fifth is roughly what a long context costs on a hybrid-attention model.
CACHE_SHARE = 0.2

# Bits per parameter, at the widths models are published at. Below four,
# dequantization costs more time than the smaller weights save.
QUANTIZATION_WIDTHS = (4, 8, 16)


def parameters_that_fit(machine: Machine, quantization_bits: int) -> float:
    """Work out how many parameters a machine holds at a given width.

    :param machine: The host the model would run on.
    :param quantization_bits: Bits per stored parameter, e.g. ``4``.

    :return: A number of parameters, with room left for the context cache.
    """
    for_weights = machine.usable_bytes * (1 - CACHE_SHARE)

    return for_weights * BITS_PER_BYTE / quantization_bits


def sizes_that_fit(machine: Machine) -> list[tuple[int, float]]:
    """List what a machine holds at each width models are published at.

    :param machine: The host the model would run on.

    :return: ``(bits, parameters)`` pairs, largest model first.
    """
    return [(bits, parameters_that_fit(machine, bits)) for bits in QUANTIZATION_WIDTHS]
