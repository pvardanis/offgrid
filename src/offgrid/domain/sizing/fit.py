"""How large a model a machine can hold.

Which model to run is a choice offgrid leaves to whoever runs it. What it can
say is how much room there is, so that the choice is made against a number
rather than a guess.
"""

from offgrid.domain.sizing.machine import Machine

BITS_PER_BYTE = 8

# Sizes are said in the gigabytes a disk is sold in, not the ones memory is
# counted in, because that is what a model card publishes.
BYTES_PER_GB = 1e9

# Weights are not the whole of it: the cache grows with the context, and a
# machine filled to the brim with weights stalls on the first long prompt.
# A fifth is roughly what a long context costs on a hybrid-attention model.
CACHE_SHARE = 0.2

# Bits per parameter, at the widths models are published at. Below four,
# dequantization costs more time than the smaller weights save.
QUANTIZATION_WIDTHS = (4, 8, 16)


def weight_budget_bytes(machine: Machine) -> float:
    """Work out how much memory a model's weights may take.

    What is left of the memory the GPU may use once the cache's share is set
    aside — the one budget the weights of a model, or a parameter count, are
    measured against. Named once so the number a row is greyed by and the
    number a person is told cannot drift apart the day the cache's share moves.

    :param machine: The host the model would run on.

    :return: The bytes left for weights, with room held back for the cache.
    """
    return machine.usable_bytes * (1 - CACHE_SHARE)


def weigh_model(parameters: float, quantization_bits: int) -> float:
    """Work out what a number of parameters weighs at a width.

    :param parameters: How many there are.
    :param quantization_bits: Bits per stored parameter, e.g. ``4``.

    :return: What holding them costs. Weights only, with nothing set aside
        for the cache the context grows into.
    """
    return parameters * quantization_bits / BITS_PER_BYTE


def get_params_that_fit(machine: Machine, quantization_bits: int) -> float:
    """Work out how many parameters a machine holds at a given width.

    :param machine: The host the model would run on.
    :param quantization_bits: Bits per stored parameter, e.g. ``4``.

    :return: A number of parameters, with room left for the context cache.
    """
    return weight_budget_bytes(machine) * BITS_PER_BYTE / quantization_bits


def model_fits(machine: Machine, weight_bytes: int) -> bool:
    """Say whether a model's weights leave room for the context cache.

    The same budget `get_params_that_fit` measures a parameter count against,
    read against a weight the runtime stated rather than one derived from a
    name: what is left of the memory the GPU may use once the cache's share is
    set aside. A model whose weights are exactly the budget fits — the cache
    grows into the share already held back from it.

    :param machine: The host the model would run on.
    :param weight_bytes: What the runtime says the model weighs on disk.

    :return: Whether it fits with room left for the cache.
    """
    return weight_bytes <= weight_budget_bytes(machine)


def get_sizes_that_fit(machine: Machine) -> list[tuple[int, float]]:
    """List what a machine holds at each width models are published at.

    :param machine: The host the model would run on.

    :return: ``(bits, parameters)`` pairs, largest model first.
    """
    return [(bits, get_params_that_fit(machine, bits)) for bits in QUANTIZATION_WIDTHS]
