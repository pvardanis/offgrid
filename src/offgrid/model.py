"""A model as the runtime describes it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g. ``qwen/qwen3.6-35b-a3b``.
    :param parameters: Total parameter count, or ``None`` when the identifier
        states no size and the runtime reports none either.
    :param active_parameters: Parameters used per token, for mixture-of-experts
        models. ``None`` for dense models, where every parameter is active.
    :param quantization_bits: Bits per stored parameter.
    :param context_limit: Largest context the runtime will serve for this model.
    """

    identifier: str
    parameters: float | None
    active_parameters: float | None
    quantization_bits: int
    context_limit: int

    @property
    def is_sized(self) -> bool:
        """Whether the model's parameter count is known.

        :return: ``True`` when its memory needs can be computed.
        """
        return self.parameters is not None

    @property
    def parameters_per_token(self) -> float | None:
        """Parameters read for each generated token.

        :return: Active parameters for a mixture of experts, total for a dense
            model, ``None`` when neither is known.
        """
        return self.active_parameters or self.parameters
