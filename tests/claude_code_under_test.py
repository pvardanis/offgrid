"""Claude Code, stood in for well enough to ask it what an agent must do.

Its whole conversation with this machine is files in a directory it is told to
use, so standing it in is pointing that directory somewhere a test owns. What
it writes there is then read back as written, never as documented.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from offgrid.agents.claude_code import prepare
from offgrid.agents.claude_code.config import ClaudeCodeConfig
from offgrid.domain.running.agent import Agent, Passthrough

HOST = "127.0.0.1:1234"

# Settings a person could plausibly have written: a theme they wanted and no
# mention of the deny offgrid puts there, which is all it takes to leave
# WebSearch reachable again.
PERMITTING = '{"theme": "mine"}\n'

# An argument a person could plausibly type, which sends the whole session to
# Anthropic's servers whatever model the profile names. Spelled here rather
# than reached for out of the adapter, so that a rename in the adapter is
# caught by a test failing rather than by a test still agreeing with itself.
PUBLISHING = "--cloud"


@dataclass(frozen=True)
class ClaudeCodeUnderTest:
    """A copy of Claude Code the suite can put into whatever state it asks about."""

    @property
    def name(self) -> str:
        """What to call this adapter where a test says which one failed.

        :return: The agent's name, as a profile spells it.
        """
        return "claude-code"

    @property
    def address(self) -> str:
        """Where the runtime this agent is pointed at listens.

        :return: The address a person would have typed.
        """
        return HOST

    @property
    def offers_no_hosted_tool(self) -> bool:
        """Whether this agent has no hosted tool to be permitted at all.

        WebSearch runs on Anthropic's servers, which is the whole reason this
        adapter has a guard.

        :return: False.
        """
        return False

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

        return prepare(ClaudeCodeConfig(runtime_host=HOST), passthrough)

    def edit_the_configuration(self, home: Path) -> None:
        """Change both files the way a person plausibly would.

        Each edit takes out what offgrid wrote rather than adding beside it,
        because a key that is still there is kept by anything — including a
        `configure` that merged what was missing back in, which is the reading
        this promise is worth having against.

        :param home: Where offgrid keeps what it writes for this run.
        """
        self.write_a_configuration_permitting_a_hosted_tool(home)

        (home / self.name / "CLAUDE.md").write_text("# Mine\n\nAnswer briefly.\n")

    def arrange_a_transcript_that_leaves(self, home: Path) -> Passthrough:
        """Ask for a session that runs on Anthropic's servers.

        Nothing on disk, because there is nothing on disk to write: Claude
        Code has no setting for this, and the whole of the answer is an
        argument a person types.

        :param home: Where offgrid keeps what it writes for this run.

        :return: The argument that opens a cloud session.
        """
        return (PUBLISHING,)

    def write_a_configuration_permitting_a_hosted_tool(self, home: Path) -> None:
        """Leave settings behind that no longer deny WebSearch.

        A key in a JSON file for this agent, and a table in a TOML file for
        the next, which is why the suite asks rather than writes it itself.

        :param home: Where offgrid keeps what it writes for this run.
        """
        settings = home / self.name / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)

        settings.write_text(PERMITTING)
