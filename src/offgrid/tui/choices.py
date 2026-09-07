"""What each of the picker's three lists offers, out of what was read.

Turning a `WhatCouldBeRun` into the rows the runtimes, agents and models lists
show, and which of them a run cannot start. Pure: it reaches no widget and no
runtime, so it is the same answer whether a screen shows it or a test reads it.

The screen puts what these return onto the widgets and moves the highlight;
this only says what there is to put.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from rich.console import RenderableType
from textual.widgets.option_list import Option

from offgrid.domain.assembling import (
    WhatCouldBeRun,
    describe_a_model_row,
    describe_an_agent_row,
    describe_weight,
    get_requested_model_context,
    order_models_held_first,
)
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeName
from offgrid.domain.sizing.fit import BYTES_PER_GB, model_fits, weight_budget_bytes
from offgrid.domain.sizing.machine import Machine

NOTHING_DOWNLOADED = "the runtime has nothing downloaded"
"""What stands in the models list where a runtime has no models at all.

A list with a row in it saying so, rather than an empty box: an empty box is
read as offgrid having failed to ask. Disabled, because it is a sentence rather
than something to pick.
"""

NOTHING_THAT_FITS = (
    "nothing downloaded fits this machine — press r for what a list says fits"
)
"""What stands in the models list where everything downloaded is too large.

Told apart from nothing being downloaded at all, because the two are different
problems: one is answered by downloading a smaller model, the other by
downloading anything. This one points at the ranked table, which is where a
model small enough to run is named. Disabled, like the row it stands in for.
"""


@dataclass(frozen=True)
class Choices:
    """What one dropdown offers, and which of it a run cannot start.

    :param options: Each choice, as it reads and the value it stands for.
    :param unavailable: The values a run cannot start, greyed and stepped over.
    :param opens_on: The value to open on, or ``None`` where none can be
        reached and there is nothing to open on.
    """

    options: list[tuple[RenderableType, str]]
    unavailable: frozenset[str]
    opens_on: str | None


def unfit_reason(machine: Machine | None, model: Model) -> str | None:
    """Say why a model will not fit this machine, or that it will.

    A machine offgrid could not size and a weight the runtime did not answer
    are both reasons to leave a model reachable rather than mark it: nothing
    here can call it too large, so the person is left to decide. Only a weight
    read against a sized machine and found over its budget marks a row.

    :param machine: The host a run would use, or ``None`` where it could not be
        sized.
    :param model: The model to weigh against it.

    :return: The reason the model will not fit, put under its row, or ``None``
        where it fits or cannot be judged.
    """
    weight = model.weight_bytes

    if machine is None or weight is None or model_fits(machine, weight):
        return None

    budget = weight_budget_bytes(machine) / BYTES_PER_GB

    return (
        f"needs {describe_weight(weight)}, more than the {budget:.0f}GB this "
        "machine holds with room for context"
    )


def describe_the_row(
    report: WhatCouldBeRun,
    context_store: Mapping[str, int],
    edits: Mapping[str, int],
    model: Model,
    *,
    reason: str | None = None,
) -> RenderableType:
    """Render one model's row, its `context` column seeded the way the list is.

    The row the list lays out and the row the picker redraws in place are the
    same row, so both read it from here rather than each knowing what a row
    shows.

    :param report: Everything that was read.
    :param context_store: The window each model was last saved at, seeding the
        window the row's `context` column shows.
    :param edits: The window edited in place this session, keyed on the model,
        beating the store for the row it was edited on.
    :param model: The model whose row to render.
    :param reason: Why the model will not fit this machine, put under the row,
        or ``None`` where it fits and the window is shown instead.

    :return: The row as it reads.
    """
    return describe_a_model_row(
        model,
        held=model.identifier in report.held,
        window=get_requested_model_context(
            report, context_store, model.identifier, edits=edits
        ),
        unfit_reason=reason,
    )


def model_options(
    report: WhatCouldBeRun,
    context_store: Mapping[str, int],
    edits: Mapping[str, int],
    machine: Machine | None,
) -> list[Option]:
    """Lay out a row per model downloaded, held ones first.

    A model too large for this machine is greyed and stepped over, the way an
    absent agent is: it cannot be run, so the cursor never lands on it and a
    run is never assembled from it. Where every model downloaded is too large,
    the one row left says so and points at the ranked table, which is a
    different thing to read than an empty catalogue.

    :param report: Everything that was read.
    :param context_store: The window each model was last saved at, seeding the
        window each row's `context` column shows.
    :param edits: The window edited in place this session, keyed on the model,
        beating the store for the row it was edited on. Empty where nothing
        has been edited.
    :param machine: The host a run would use, against which a model's weight is
        read, or ``None`` where it could not be sized and none is marked.

    :return: The rows, or the one saying there are none, or the one saying none
        of them fit.
    """
    if not report.downloaded_models:
        return [Option(NOTHING_DOWNLOADED, disabled=True)]

    rows = [
        _a_model_option(report, context_store, edits, machine, model)
        for model in order_models_held_first(report)
    ]

    if all(option.disabled for option in rows):
        return [Option(NOTHING_THAT_FITS, disabled=True)]

    return rows


def _a_model_option(
    report: WhatCouldBeRun,
    context_store: Mapping[str, int],
    edits: Mapping[str, int],
    machine: Machine | None,
    model: Model,
) -> Option:
    """Lay out one model's row, greyed where it will not fit this machine.

    :param report: Everything that was read.
    :param context_store: The window each model was last saved at.
    :param edits: The window edited in place this session.
    :param machine: The host a run would use, or ``None`` where it could not be
        sized.
    :param model: The model whose row to build.

    :return: The row, disabled where the model is too large.
    """
    reason = unfit_reason(machine, model)

    return Option(
        describe_the_row(report, context_store, edits, model, reason=reason),
        id=model.identifier,
        disabled=reason is not None,
    )


def runtime_choices(report: WhatCouldBeRun) -> Choices:
    """Offer every runtime offgrid drives, greying all but the profile's.

    Only the profile's runtime has a config to be assembled from, so every
    other one offgrid drives is greyed until that stops being true. It is what
    the dropdown opens on, since it is the one a run would use today.

    :param report: Everything that was read.

    :return: What the runtimes list offers.
    """
    named = report.profile.runtime_name

    return Choices(
        options=[(name.value, name.value) for name in RuntimeName],
        unavailable=frozenset(name.value for name in RuntimeName if name != named),
        opens_on=named.value,
    )


def agent_choices(report: WhatCouldBeRun) -> Choices:
    """Offer every agent offgrid drives, greying the ones this machine has not.

    The dropdown opens on the agent a run would try today: the profile's where
    this machine has it, otherwise the first it can reach, since something has
    to be reported on. Where none can be reached there is nothing to open on,
    and the report falls back on the agent the profile names.

    :param report: Everything that was read.

    :return: What the agents list offers.
    """
    reachable = [
        agent.name.value for agent in report.agents if agent.is_on_this_machine
    ]
    wanted = report.profile.agent_name.value

    return Choices(
        options=[
            (describe_an_agent_row(agent), agent.name.value) for agent in report.agents
        ],
        unavailable=frozenset(
            agent.name.value for agent in report.agents if not agent.is_on_this_machine
        ),
        opens_on=_agent_to_open_on(reachable, wanted),
    )


def _agent_to_open_on(reachable: list[str], wanted: str) -> str | None:
    """Say which agent a dropdown opens on, which the profile's may not be.

    :param reachable: The agents a run could start, in the order listed.
    :param wanted: The agent the profile names.

    :return: The agent to open on, or ``None`` where none can be reached.
    """
    if not reachable:
        return None

    return wanted if wanted in reachable else reachable[0]
