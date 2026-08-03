"""A model as the runtime describes it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g. ``qwen/qwen3.6-35b-a3b``.
    :param parameters: Total parameter count.
    :param active_parameters: Parameters used per token, for mixture-of-experts
        models. ``None`` for dense models, where every parameter is active.
    :param quantization_bits: Bits per stored parameter.
    :param context_limit: Largest context the runtime will serve for this model.
    """

    identifier: str
    parameters: float
    active_parameters: float | None
    quantization_bits: int
    context_limit: int

    @property
    def parameters_per_token(self) -> float:
        """Parameters read for each generated token.

        :return: Active parameters for a mixture of experts, total otherwise.
        """
        return self.active_parameters or self.parameters
