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
    get_requested_model_context,
    order_models_held_first,
)
from offgrid.domain.running.model import Model
from offgrid.domain.running.runtime import RuntimeName

NOTHING_DOWNLOADED = "the runtime has nothing downloaded"
"""What stands in the models list where a runtime has no models at all.

A list with a row in it saying so, rather than an empty box: an empty box is
read as offgrid having failed to ask. Disabled, because it is a sentence rather
than something to pick.
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


def describe_the_row(
    report: WhatCouldBeRun,
    context_store: Mapping[str, int],
    edits: Mapping[str, int],
    model: Model,
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

    :return: The row as it reads.
    """
    return describe_a_model_row(
        model,
        held=model.identifier in report.held,
        window=get_requested_model_context(
            report, context_store, model.identifier, edits=edits
        ),
    )


def model_options(
    report: WhatCouldBeRun,
    context_store: Mapping[str, int],
    edits: Mapping[str, int],
) -> list[Option]:
    """Lay out a row per model downloaded, held ones first.

    :param report: Everything that was read.
    :param context_store: The window each model was last saved at, seeding the
        window each row's `context` column shows.
    :param edits: The window edited in place this session, keyed on the model,
        beating the store for the row it was edited on. Empty where nothing
        has been edited.

    :return: The rows, or the one saying there are none.
    """
    if not report.downloaded_models:
        return [Option(NOTHING_DOWNLOADED, disabled=True)]

    return [
        Option(
            describe_the_row(report, context_store, edits, model),
            id=model.identifier,
        )
        for model in order_models_held_first(report)
    ]


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
