"""OpenCode, stood in for well enough to ask it what an agent must do.

What it is configured with is a file in a directory it is told to use, so
standing it in is pointing that directory somewhere a test owns. What it writes
there is then read back as written, never as documented.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from offgrid.agents.opencode import prepare
from offgrid.agents.opencode.config import OpenCodeConfig
from offgrid.domain.running.agent import Agent, Passthrough

HOST = "127.0.0.1:1234"


@dataclass(frozen=True)
class OpenCodeUnderTest:
    """A copy of OpenCode the suite can put into whatever state it asks about."""

    @property
    def name(self) -> str:
        """What to call this adapter where a test says which one failed.

        :return: The agent's name, as a profile spells it.
        """
        return "opencode"

    @property
    def address(self) -> str:
        """Where the runtime this agent is pointed at listens.

        :return: The address a person would have typed.
        """
        return HOST

    @property
    def offers_no_hosted_tool(self) -> bool:
        """Whether this agent has no hosted tool to be permitted at all.

        Measured against opencode 1.18.20: every tool it offers runs on this
        machine, and it talks to whatever provider it is pointed at rather than
        to one vendor's servers, so there is nothing server-side to deny.

        :return: True.
        """
        return True

    def prepare(
        self,
        monkeypatch: pytest.MonkeyPatch,
        home: Path,
        *,
        passthrough: Passthrough = (),
    ) -> Agent:
        """Bind the adapter, run out of a directory under `home`.

        :param monkeypatch: The test's patcher.
        :param home: Where offgrid keeps what it writes for this run.
        :param passthrough: Arguments handed to the agent unchanged.

        :return: The adapter under test.
        """
        monkeypatch.setattr("offgrid.domain.running.agent.OFFGRID_HOME", home)

        return prepare(OpenCodeConfig(runtime_host=HOST), passthrough)

    def write_a_configuration_permitting_a_hosted_tool(self, home: Path) -> None:
        """Leave behind a configuration permitting a hosted tool, which is none.

        There is no such state to write: nothing OpenCode offers runs anywhere
        but here, which is what `offers_no_hosted_tool` says and what the two
        tests asking for this state skip on.

        :param home: Where offgrid keeps what it writes for this run.

        :raise NotImplementedError: Whenever it is called, so that a suite
            reaching for this state against an agent that has none says so
            rather than passing on a file that means nothing.
        """
        raise NotImplementedError(
            f"{self.name} offers no hosted tool, so no configuration permits one. "
            "The tests that ask for this state skip on `offers_no_hosted_tool`."
        )
