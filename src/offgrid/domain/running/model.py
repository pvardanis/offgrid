"""A model as the runtime describes it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g.
        ``qwen/qwen3.6-35b-a3b``.
    :param context_limit: Context the runtime will serve for this model, which
        is what it was loaded with rather than its ceiling. ``0`` when the
        runtime states neither.
    """

    identifier: str
    context_limit: int
