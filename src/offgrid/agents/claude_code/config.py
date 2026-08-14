"""What Claude Code is built from, as the profile's agent section says it.

Nothing of its own yet: where it is run out of derives from its name, and
where the runtime listens is settled for every agent. The type is here anyway,
so that a key nobody reads is refused rather than carried, and so that a
setting Claude Code grows later has somewhere to land.
"""

from pydantic import computed_field

from offgrid.agent import AgentConfig, AgentName


class ClaudeCodeConfig(AgentConfig):
    """Everything Claude Code is run out of."""

    @computed_field
    @property
    def name(self) -> AgentName:
        """Which agent this is the config for.

        :return: Always ``claude-code``.
        """
        return AgentName.CLAUDE_CODE
