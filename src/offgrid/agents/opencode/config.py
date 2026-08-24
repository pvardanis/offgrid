"""What OpenCode is built from, as the profile's agent section says it.

Nothing of its own: where it is run out of derives from its name, and where the
runtime listens is settled for every agent. The type is here anyway, so that a
key nobody reads is refused rather than carried, and so that a setting OpenCode
grows later has somewhere to land.
"""

from pydantic import computed_field

from offgrid.domain.running.agent import AgentConfig, AgentName


class OpenCodeConfig(AgentConfig):
    """Everything OpenCode is run out of."""

    @computed_field
    @property
    def name(self) -> AgentName:
        """Which agent this is the config for.

        :return: Always ``opencode``.
        """
        return AgentName.OPENCODE
