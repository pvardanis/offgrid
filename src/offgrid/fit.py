"""Whether a model runs on a machine, and which of several runs best."""

from offgrid.machine import Machine
from offgrid.model import Model

BITS_PER_BYTE = 8


def weights_bytes(model: Model) -> float:
    """Memory the model's weights occupy once loaded.

    :param model: The model to size.

    :return: Bytes of weights.
    """
    return model.parameters * model.quantization_bits / BITS_PER_BYTE


def will_load(model: Model, machine: Machine) -> bool:
    """Whether the model's weights fit in the memory the GPU may use.

    :param model: The model to load.
    :param machine: The host it would load on.

    :return: ``True`` when the weights fit, leaving the cache aside.
    """
    return weights_bytes(model) <= machine.usable_bytes


def ranked(models: list[Model], machine: Machine) -> list[Model]:
    """Models that fit, fastest first.

    Decode is bound by the memory read per token, so a mixture of experts with
    few active parameters outruns a dense model several times smaller on disk.

    :param models: Candidates, in any order.
    :param machine: The host they would run on.

    :return: The subset that loads, ordered by bytes read per token.
    """
    loadable = [model for model in models if will_load(model, machine)]
    return sorted(
        loadable,
        key=lambda model: model.parameters_per_token * model.quantization_bits,
    )
