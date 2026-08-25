"""The pairs a live run proves, and what starting each of them takes.

A run holds a model, starts an agent against it and lets the model go, and
that is the same sentence whichever agent it is — so the check is
parameterised over both rather than written twice. Which agent starts is the
profile's to say and nothing else's, so a pair is arranged by naming it in the
stored profile for the length of one check and putting the profile back.

One record per agent, so a third one is a line here rather than an edit in
four places. What differs is the binary a machine needs on the PATH and the
spelling that asks one question and exits.
"""

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from offgrid.domain.profile import DEFAULT_PATH

PROMPT = "reply with the two letters OK and nothing else"


@dataclass(frozen=True)
class Pair:
    """One agent a live run pairs the runtime with.

    :param agent: The agent, as a profile spells it.
    :param binary: What the machine needs on the PATH to start it.
    :param where_to_get_it: Where a machine without it is sent.
    :param one_shot: What asks one question and has it exit.
    """

    agent: str
    binary: str
    where_to_get_it: str
    one_shot: tuple[str, ...]


PAIRS = {
    pair.agent: pair
    for pair in (
        Pair(
            agent="claude-code",
            binary="claude",
            where_to_get_it="https://docs.claude.com/en/docs/claude-code/setup",
            one_shot=("-p", PROMPT),
        ),
        Pair(
            agent="opencode",
            binary="opencode",
            where_to_get_it="https://opencode.ai/docs/",
            one_shot=("run", PROMPT),
        ),
    )
}
"""Every agent a live run starts, and what starting it takes."""


def get_one_shot_args(agent: str) -> list[str]:
    """Say how to ask this agent one question and have it exit.

    :param agent: The agent, as a profile spells it.

    :return: The arguments handed to the agent unchanged.
    """
    return list(PAIRS[agent].one_shot)


def require_installed(agent: str) -> None:
    """Stop the check with words where the agent is not on the PATH.

    A live run covers both pairs, so it needs both agents installed, and a
    machine without one is owed the binary's name and where to get it rather
    than whatever an agent that is not there fails as.

    :param agent: The agent, as a profile spells it.
    """
    pair = PAIRS[agent]

    if shutil.which(pair.binary) is None:
        pytest.fail(
            f"a live run covers {pair.agent}, and there is no `{pair.binary}` on "
            f"the PATH. Install it from {pair.where_to_get_it}, or leave the pair "
            f"out with `uv run pytest -m live -k 'not {pair.agent}'`."
        )


@contextmanager
def paired_with(agent: str, profile_path: Path) -> Iterator[None]:
    """Name this agent in the stored profile, and put the profile back after.

    What was there is restored whatever the check did, since a profile left
    naming another agent would silently change this person's own next run. A
    run killed outright is the one case nothing can restore, and it leaves the
    profile naming this agent.

    :param agent: The agent, as a profile spells it.
    :param profile_path: Where the stored profile is.

    :yield: Nothing; the profile names the agent inside the block.
    """
    was = profile_path.read_text()
    body = yaml.safe_load(was)
    body["agent"] = {**body["agent"], "name": agent}

    try:
        profile_path.write_text(yaml.safe_dump(body, sort_keys=False))

        yield
    finally:
        profile_path.write_text(was)


@pytest.fixture(params=tuple(PAIRS))
def paired(request: pytest.FixtureRequest) -> Iterator[str]:
    """One pair, named in the stored profile for the length of the check.

    :param request: The running test.

    :yield: The agent a run started now would start.
    """
    agent = str(request.param)

    require_installed(agent)

    with paired_with(agent, DEFAULT_PATH):
        yield agent
