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
from offgrid.domain.running.runtime import RuntimeName
from offgrid.shared.exceptions import DiscardedWindowsUnreadableError

# Whether a model was refused a window before, asked of what is already read.
IsWindowRefused = Callable[[str, int], bool]


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


def refuse_to_ask_again(
    discarded_windows: tuple[DiscardedWindow, ...],
) -> IsWindowRefused:
    """Say which windows this runtime has already refused.

    Every model and window it discarded, read once: the answer to each
    question is a membership test rather than another pass over the records.

    :param discarded_windows: What was kept about this runtime.
    :return: Whether a model was refused exactly this window before.
    """
    refused = {(record.identifier, record.asked_for) for record in discarded_windows}

    return lambda identifier, window: (identifier, window) in refused


def read_what_became_of_the_window(
    discarded_windows: tuple[DiscardedWindow, ...], request: ModelRequest, model: Model
) -> WhatBecameOfTheWindow | None:
    """Say what happened to the window a run asked for, where it did not get it.

    Two sentences, because two different things are known. Where offgrid put
    the window to the runtime and read the answer back, it says the runtime
    did not grant it. Where it asked for nothing because that same window was
    already refused, it says so and dates the refusal it is repeating — the
    model may have been loaded this run, so a sentence about what is "already
    held" would be a claim about state that offgrid did not check.

    :param discarded_windows: What was kept about this runtime.
    :param request: What the run asked for, before anything was held.
    :param model: The model as the runtime now serves it.
    :return: What became of the window, or ``None`` where the runtime serves
        the one asked for, none was asked for, or it states no window.
    """
    asked_for, served = request.context_window, model.context_window

    if asked_for is None or served is None or served == asked_for:
        return None

    question = (model.identifier, asked_for)
    record = next(
        (r for r in discarded_windows if (r.identifier, r.asked_for) == question), None
    )

    if record is not None:
        return WhatBecameOfTheWindow(
            said=(
                f"offgrid did not ask for {asked_for}: the runtime discarded "
                f"that window on {record.dated}, and is serving "
                f"{model.identifier} at {served}."
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


def save_discarded_window_if_new(
    became: WhatBecameOfTheWindow,
    model: Model,
    *,
    runtime: RuntimeName,
    host: str,
    file_path: Path,
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
    :param runtime: Which runtime discarded it.
    :param host: Address it listens on.
    :param file_path: Where the records are kept.
    :return: The complaint to say where it could not be written, or ``None``
        where there was nothing to write or writing it worked.
    """
    if not became.is_news:
        return None

    try:
        save_discarded_window(
            runtime=runtime,
            host=host,
            identifier=model.identifier,
            asked_for=became.asked_for,
            served=became.served,
            file_path=file_path,
        )
    except (OSError, DiscardedWindowsUnreadableError) as error:
        return (
            f"{file_path} could not be written: {error}. The run goes on, and "
            "the next one asks for the window again."
        )

    return None
