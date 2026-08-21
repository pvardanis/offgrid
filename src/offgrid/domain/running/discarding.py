"""Whether a window is asked for again, and what became of the one that was.

One question, asked in one place: was this model, on this runtime, refused
this window. `hold_model` asks it to decide what to request and the command
line to decide what to say, reading the same records from the same moment, so
the two cannot disagree.

Only the window that was refused is left unasked. A different one is a
question the runtime has not been put, and a run that dropped it would be
throwing away a number somebody typed on the strength of an answer about
another.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from offgrid.domain.running.discarded_windows import (
    DiscardedWindow,
    save_discarded_window,
)
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError

# Whether a model was refused a window before, asked of what is already read.
Refused = Callable[[str, int], bool]


@dataclass(frozen=True)
class WhatBecameOfTheWindow:
    """What happened to a window a run asked for, and what to say about it.

    :param said: What to tell whoever ran offgrid.
    :param asked_for: The window the run asked to hold the model at.
    :param served: The window the runtime is serving it at instead.
    :param is_news: Whether the runtime refused it this run, which is what
        makes it worth keeping. One already on record was not asked again.
    """

    said: str
    asked_for: int
    served: int
    is_news: bool


def refuse_to_ask_again(kept: dict[str, DiscardedWindow]) -> Refused:
    """Say which windows this runtime has already refused.

    :param kept: What was kept about this runtime, by model.
    :return: Whether a model was refused exactly this window before.
    """

    def was_refused(identifier: str, window: int) -> bool:
        """Say whether this model was refused this window.

        :param identifier: The model about to be asked for.
        :param window: The window about to be asked for.
        :return: Whether that pair is already on record.
        """
        record = kept.get(identifier)

        return record is not None and record.asked_for == window

    return was_refused


def read_what_became_of_the_window(
    kept: dict[str, DiscardedWindow], request: ModelRequest, model: Model
) -> WhatBecameOfTheWindow | None:
    """Say what happened to the window a run asked for, where it did not get it.

    Two sentences, because two different things are known. Where offgrid put
    the window to the runtime and read the answer back, it says the runtime
    did not grant it. Where it asked for nothing because that same window was
    already refused, it says what is held and cites the day it was told, which
    is a claim about state rather than about the runtime.

    :param kept: What was kept about this runtime.
    :param request: What the run asked for, before anything was held.
    :param model: The model as the runtime now serves it.
    :return: What became of the window, or ``None`` where the runtime serves
        the one asked for, none was asked for, or it states no window.
    """
    asked_for, served = request.context_window, model.context_window

    if asked_for is None or served is None or served == asked_for:
        return None

    record = kept.get(model.identifier)

    if record is not None and record.asked_for == asked_for:
        return WhatBecameOfTheWindow(
            said=(
                f"{model.identifier} is already held at {served}, and "
                f"{asked_for} was asked for. The runtime discarded that "
                f"window on {record.dated}, so offgrid is using what is there."
            ),
            asked_for=asked_for,
            served=served,
            is_news=False,
        )

    return WhatBecameOfTheWindow(
        said=(
            f"offgrid asked the runtime to hold {model.identifier} at "
            f"{asked_for} and it is serving {served}. Later runs will use what "
            "it serves rather than asking again."
        ),
        asked_for=asked_for,
        served=served,
        is_news=True,
    )


def keep_what_the_runtime_did(
    became: WhatBecameOfTheWindow, model: Model, *, host: str, kept: Path
) -> str | None:
    """Write down a refusal the runtime gave this run, where it gave one.

    Nothing is written for a refusal already on record: the runtime was not
    asked again, so there is no new answer, and re-stamping it would lose the
    day it was first told. A file that cannot be written is answered for
    rather than raised: the model is held and the agent is about to start, and
    taking that away over a record offgrid keeps for itself costs the load
    twice.

    :param became: What became of the window a run asked for.
    :param model: The model the record is about.
    :param host: Address the runtime listens on.
    :param kept: Where the records are kept.
    :return: What to say about not keeping it, or ``None``.
    """
    if not became.is_news:
        return None

    try:
        save_discarded_window(
            host=host,
            identifier=model.identifier,
            asked_for=became.asked_for,
            served=became.served,
            file_path=kept,
        )
    except (OSError, DiscardedWindowsUnreadableError) as error:
        return (
            f"{kept} could not be written: {error}. The run goes on, and the "
            "next one asks for the window again."
        )

    return None
