"""A model: the one a run asks for, and the one the runtime describes.

Two types rather than one, because the same two numbers mean different things
in each direction. A window a run states is the one being asked for; a window
the runtime states is the one being served. They can differ, and reading
either as the other is the failure the whole context split exists to prevent.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True, kw_only=True)
class Model:
    """One model available on a runtime.

    :param identifier: The id the runtime answers to, e.g.
        ``qwen/qwen3.6-35b-a3b``.
    :param context_ceiling: The most this model could be served at, and
        ``None`` when the runtime states none.
    :param context_window: What it is being served at now, and ``None`` when
        nothing is holding it — a stopped model is not being served at its
        ceiling, it is not being served.
    """

    identifier: str
    context_ceiling: int | None
    context_window: int | None


class ModelRequest(BaseModel):
    """The model a run asked the runtime to hold, and at what window.

    Naming neither is how a run says it wants whatever is already there, at
    whatever it is already served at, which costs no load.

    Validated rather than trusted, and a `BaseModel` rather than a dataclass
    for it, because it is the one of these two a person writes: `Model` is
    parsed from what a runtime answered, and this is stated on a command line
    or in a hand-edited file. Keys it does not name are refused, so a typo is
    reported rather than read as "nothing wanted".

    :param identifier: The model to hold, or ``None`` for whichever the
        runtime is already holding. Never empty: a name nobody typed is not
        the same statement as no name at all, and reading one as the other
        answers with the resident model where the runtime should have said it
        does not have that.
    :param context_window: The context to hold it at, or ``None`` to inherit
        whatever the runtime serves it at. Above zero, because zero is not a
        small window, it is not a window. It is a request, not a reading:
        what the runtime settles on is on the `Model` that comes back, and
        the two are only usually the same number.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier: str | None = Field(default=None, min_length=1)
    context_window: int | None = Field(default=None, gt=0)
