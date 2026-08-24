"""What every file asking an adapter what it owes works from.

The suite states what being an agent means and asks it of every adapter in
`AGENTS_UNDER_TEST`. What it asks is in two files — what an agent says about
hosted tools, and everything else it owes — and both ask it of the same list,
against a directory the test owns.
"""

from pathlib import Path

import pytest

from offgrid.domain.running.agent import Agent
from offgrid.domain.running.launch import Launch
from offgrid.domain.running.model import Model
from tests.agents_under_test import AGENTS_UNDER_TEST

WANTED = "a/wanted-7b"
WINDOW = 32768
CEILING = 262144

EVERY_AGENT = pytest.mark.parametrize(
    "agent_under_test", AGENTS_UNDER_TEST, ids=lambda under_test: under_test.name
)
"""Ask what follows of every adapter there is, saying which one failed."""


def read_everything_under(home: Path) -> dict[str, bytes]:
    """Say what is on disk, so that two readings of it can be compared.

    Every file rather than the ones an adapter is known to write: a `configure`
    that leaves something extra behind is as much a change as one that rewrites
    a file, and no assertion naming files could see it.

    :param home: Where offgrid keeps what it writes for this run.

    :return: Each file under it, against what it holds.
    """
    return {
        str(path.relative_to(home)): path.read_bytes()
        for path in sorted(home.rglob("*"))
        if path.is_file()
    }


def plan_for_a_model(agent: Agent) -> Launch:
    """Ask an agent how it would start against the model that will answer.

    :param agent: The adapter under test.

    :return: The environment and command it answered with.
    """
    return agent.plan(
        Model(identifier=WANTED, context_ceiling=CEILING, context_window=WINDOW)
    )
