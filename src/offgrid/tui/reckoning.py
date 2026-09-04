"""Facts the picker shows but does not itself compute, read off the report.

Neither reaches the screen: each answers a question about what was read — which
downloaded model a row is, and the floor a picked agent would start in — so the
screen is left holding the widgets and these hold the arithmetic.
"""

from offgrid.domain.assembling import WhatCouldBeRun, find_agent
from offgrid.domain.checkup import WhatTheAgentAnswered
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.model import Model


def find_downloaded_model(report: WhatCouldBeRun, identifier: str) -> Model | None:
    """Find one downloaded model by its identifier.

    :param report: Everything that was read.
    :param identifier: The model to find.

    :return: The model, or ``None`` where the runtime has no such one.
    """
    return next(
        (model for model in report.downloaded_models if model.identifier == identifier),
        None,
    )


def floor_for_agent(report: WhatCouldBeRun, agent: str | None) -> int | None:
    """Say the smallest window the picked agent starts in, where it answered.

    The window box measures against the agent a run would start, so a value
    below its floor is refused in the same words a load would fail with.

    :param report: Everything that was read.
    :param agent: Which agent is picked, or ``None`` where none is.

    :return: The agent's floor, or ``None`` where none is picked or the picked
        one's settings would not read.
    """
    if agent is None:
        return None

    answered = find_agent(report, AgentName(agent)).answered

    if isinstance(answered, WhatTheAgentAnswered):
        return answered.terms.context_floor

    return None
