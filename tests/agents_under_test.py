"""What an agent adapter has to be stood in for, and which ones there are.

The conformance suite states what being an agent means and asks it of
everything in `AGENTS_UNDER_TEST`. A second adapter joins by writing one of
these and adding a line here, which is the only edit it makes to the suite.

Each of these stands in below its adapter — the directory it is run out of —
rather than satisfying `Agent` with a fake. That is what makes the suite worth
running: it covers what an adapter writes and reads back as well as what it
promises, and a guard that reads its own configuration wrongly is the half
most likely to be wrong.
"""

from pathlib import Path
from typing import Protocol

import pytest

from offgrid.domain.running.agent import Agent, Passthrough
from tests.claude_code_under_test import ClaudeCodeUnderTest
from tests.opencode_under_test import OpenCodeUnderTest


class AgentUnderTest(Protocol):
    """One adapter, and the arrangements a suite over it needs."""

    @property
    def name(self) -> str:
        """What to call this adapter where a test says which one failed.

        :return: The agent's name, as a profile spells it.
        """
        ...

    @property
    def address(self) -> str:
        """Where the runtime this agent is pointed at listens.

        :return: The address a person would have typed, which the agent has to
            be told one way or another.
        """
        ...

    @property
    def offers_no_hosted_tool(self) -> bool:
        """Whether this agent has no hosted tool to be permitted at all.

        Stated rather than skipped around, and paid for: an adapter saying so
        is asked to answer `NONE_OFFERED` with the evidence for it, and an
        adapter that does offer one and says this goes red instead.

        :return: True where nothing this agent offers runs anywhere but here.
        """
        ...

    def prepare(
        self,
        monkeypatch: pytest.MonkeyPatch,
        home: Path,
        *,
        passthrough: Passthrough = (),
    ) -> Agent:
        """Bind the adapter, run out of a directory under `home`.

        Everything an agent writes for itself lands under `home`, because a
        config directory derives from it. That is what lets the suite say what
        was written without knowing which files any adapter uses.

        :param monkeypatch: The test's patcher.
        :param home: Where offgrid keeps what it writes for this run.
        :param passthrough: Arguments handed to the agent unchanged.

        :return: The adapter under test.
        """
        ...

    def write_a_configuration_permitting_a_hosted_tool(self, home: Path) -> None:
        """Leave a configuration behind that denies no hosted tool.

        The adapter writes it, because permitting one is a key in a JSON file
        for one agent and a table in a TOML file for another.

        :param home: Where offgrid keeps what it writes for this run.
        """
        ...


AGENTS_UNDER_TEST: list[AgentUnderTest] = [ClaudeCodeUnderTest(), OpenCodeUnderTest()]
