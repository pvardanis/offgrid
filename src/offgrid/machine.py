"""The host the model has to run on."""

import platform
import subprocess
from dataclasses import dataclass

from offgrid.exceptions import UnsupportedMachineError

# macOS reserves part of unified memory for the CPU until iogpu.wired_limit_mb
# is raised, leaving the GPU roughly three quarters of the machine.
DEFAULT_GPU_SHARE = 0.75

BYTES_PER_MB = 1024 * 1024


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


def require_apple_silicon(system: str, architecture: str) -> None:
    """Refuse hosts offgrid has no tuning knowledge for.

    :param system: Value of ``platform.system()``.
    :param architecture: Value of ``platform.machine()``.

    :raise UnsupportedMachineError: On anything but an Apple Silicon Mac.
    """
    if system != "Darwin":
        raise UnsupportedMachineError(
            f"offgrid runs on macOS, and this is {system}. "
            "Unified memory and Metal are what its sizing assumes."
        )
    if architecture != "arm64":
        raise UnsupportedMachineError(
            f"offgrid runs on Apple Silicon, and this is {architecture}. "
            "Intel Macs have separate GPU memory, which the sizing does not model."
        )


def parse(brand: str, memsize: str, wired_limit_mb: str | None) -> Machine:
    """Build a machine from raw sysctl values.

    :param brand: ``machdep.cpu.brand_string``.
    :param memsize: ``hw.memsize``, in bytes.
    :param wired_limit_mb: ``iogpu.wired_limit_mb``, or ``None`` when the key
        is absent. macOS reports ``0`` while the limit is at its default.

    :return: The described machine.
    """
    wired = int(wired_limit_mb) if wired_limit_mb else 0
    return Machine(
        chip=brand.strip(),
        memory_bytes=int(memsize),
        wired_limit_bytes=wired * BYTES_PER_MB if wired else None,
    )


def _sysctl(key: str) -> str | None:
    """Read one sysctl key.

    :param key: The key to read.

    :return: Its value, or ``None`` when the key does not exist.
    """
    result = subprocess.run(
        ["sysctl", "-n", key], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def detect() -> Machine:
    """Read this host's chip and memory.

    :return: The machine offgrid is running on.

    :raise UnsupportedMachineError: When the host is not an Apple Silicon Mac.
    """
    require_apple_silicon(platform.system(), platform.machine())
    brand = _sysctl("machdep.cpu.brand_string") or "Apple Silicon"
    memsize = _sysctl("hw.memsize") or "0"
    return parse(brand, memsize, _sysctl("iogpu.wired_limit_mb"))
