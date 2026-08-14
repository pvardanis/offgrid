"""What LM Studio is built from, as the profile's runtime section says it.

Where it listens is all of it, and every runtime needs that, so the type adds
nothing to what the port already declares. It is here anyway, so that a key
nobody reads is refused rather than carried, and so that a setting LM Studio
grows later has somewhere to land.
"""

from pydantic import computed_field

from offgrid.domain.running.runtime import RuntimeConfig, RuntimeName


class LMStudioConfig(RuntimeConfig):
    """Everything LM Studio is reached with."""

    @computed_field
    @property
    def name(self) -> RuntimeName:
        """Which runtime this is the config for.

        :return: Always ``lmstudio``.
        """
        return RuntimeName.LMSTUDIO
