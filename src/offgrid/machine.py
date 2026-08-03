"""The host the model has to run on."""

from dataclasses import dataclass

# macOS reserves part of unified memory for the CPU until iogpu.wired_limit_mb
# is raised, leaving the GPU roughly three quarters of the machine.
DEFAULT_GPU_SHARE = 0.75


@dataclass(frozen=True)
class Machine:
    """An Apple Silicon Mac and the memory a model may use on it.

    :param chip: Marketing name of the SoC, e.g. ``Apple M1 Max``.
    :param memory_bytes: Total unified memory.
    :param wired_limit_bytes: Value of ``iogpu.wired_limit_mb``, or ``None``
        when it has not been raised from its default.
    """

    chip: str
    memory_bytes: int
    wired_limit_bytes: int | None

    @property
    def usable_bytes(self) -> float:
        """Memory a model's weights and cache may occupy.

        :return: The wired limit when one is set, else the default GPU share.
        """
        if self.wired_limit_bytes is not None:
            return float(self.wired_limit_bytes)
        return self.memory_bytes * DEFAULT_GPU_SHARE
