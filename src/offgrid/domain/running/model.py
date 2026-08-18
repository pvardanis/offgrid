"""A model as the runtime describes it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g.
        ``qwen/qwen3.6-35b-a3b``.
    :param context_ceiling: The most this model could be served at. ``0`` when
        the runtime states none.
    :param context_window: What it is being served at now, and ``None`` when
        nothing is holding it — a stopped model is not being served at its
        ceiling, it is not being served.
    """

    identifier: str
    context_ceiling: int
    context_window: int | None
