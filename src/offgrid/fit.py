"""Whether a model runs on a machine, and which of several runs best."""

from offgrid.machine import Machine
from offgrid.model import Model

BITS_PER_BYTE = 8


def weights_bytes(model: Model) -> float | None:
    """Memory the model's weights occupy once loaded.

    :param model: The model to size.

    :return: Bytes of weights, or ``None`` when the parameter count is unknown.
    """
    if model.parameters is None:
        return None
    return model.parameters * model.quantization_bits / BITS_PER_BYTE


def will_load(model: Model, machine: Machine) -> bool:
    """Whether the model's weights fit in the memory the GPU may use.

    A model of unknown size is never promised to load. Report it with
    :func:`unsized` rather than presenting the refusal as a poor fit.

    :param model: The model to load.
    :param machine: The host it would load on.

    :return: ``True`` when the weights are known to fit, leaving the cache aside.
    """
    weights = weights_bytes(model)
    return weights is not None and weights <= machine.usable_bytes


def unsized(models: list[Model]) -> list[Model]:
    """Models whose parameter count could not be established.

    :param models: Candidates, in any order.

    :return: Those that cannot be ranked, so a caller can say so.
    """
    return [model for model in models if not model.is_sized]


def ranked(models: list[Model], machine: Machine) -> list[Model]:
    """Models that fit, fastest first.

    Decode is bound by the memory read per token, so a mixture of experts with
    few active parameters outruns a dense model several times smaller on disk.

    :param models: Candidates, in any order.
    :param machine: The host they would run on.

    :return: The subset that loads, ordered by bytes read per token. Models of
        unknown size are absent.
    """
    loadable = [model for model in models if will_load(model, machine)]
    return sorted(loadable, key=_bytes_per_token)


def _bytes_per_token(model: Model) -> float:
    """Memory read to generate one token.

    :param model: A model whose size is known.

    :return: Bytes read per token.
    """
    per_token = model.parameters_per_token or 0.0
    return per_token * model.quantization_bits / BITS_PER_BYTE
