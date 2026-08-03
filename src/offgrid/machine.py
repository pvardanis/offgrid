"""The host the model has to run on."""

import platform
import subprocess
from dataclasses import dataclass

from offgrid.exceptions import UnsupportedMachineError

# macOS reserves part of unified memory for the CPU until iogpu.wired_limit_mb
# is raised, leaving the GPU roughly three quarters of the machine.
DEFAULT_GPU_SHARE = 0.75

BYTES_PER_MB = 1024 * 1024

# Absolute, so a trimmed PATH under launchd or cron is a clear failure rather
# than a missing command.
SYSCTL = "/usr/sbin/sysctl"


@dataclass(frozen=True)
class Machine:
    """An Apple Silicon Mac and the memory a model may use on it.

    :param chip: Marketing name of the SoC, e.g. ``Apple M1 Max``.
    :param memory_bytes: Total unified memory.
    :param wired_limit_bytes: ``iogpu.wired_limit_mb`` converted to bytes, or
        ``None`` when it has not been raised from its default.
    """

    chip: str
    memory_bytes: int
    wired_limit_bytes: int | None

    @property
    def usable_bytes(self) -> float:
        """Memory the GPU may use, which the weights and cache share.

        :return: The wired limit when one is set, else the default GPU share.
            Never more than the machine physically has: the wired limit takes
            whatever value was typed at it, including a mistyped one.
        """
        if self.wired_limit_bytes is not None:
            return float(min(self.wired_limit_bytes, self.memory_bytes))
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

    :raise UnsupportedMachineError: When the memory size is unreadable or not
        a positive number of bytes. There is no sensible default for how much
        memory a machine has, and a wrong one silently refuses every model.
    """
    try:
        memory = int(memsize)
    except ValueError as error:
        raise UnsupportedMachineError(
            f"sysctl reported hw.memsize as {memsize!r}, which is not a number "
            "of bytes. Run `sysctl -n hw.memsize` to see what your shell reports."
        ) from error
    if memory <= 0:
        raise UnsupportedMachineError(
            f"sysctl reported {memory} bytes of memory, which cannot be right. "
            "offgrid cannot size a model for a machine it cannot measure."
        )
    wired = int(wired_limit_mb) if wired_limit_mb else 0
    return Machine(
        chip=brand.strip(),
        memory_bytes=memory,
        wired_limit_bytes=wired * BYTES_PER_MB if wired else None,
    )


def _sysctl(key: str) -> str | None:
    """Read one sysctl key.

    :param key: The key to read.

    :return: Its value, or ``None`` when the key does not exist. An unset
        ``iogpu.wired_limit_mb`` is a real absence; an unreadable
        ``hw.memsize`` is not, which is why the caller decides what a missing
        value means.

    :raise UnsupportedMachineError: When sysctl cannot be run at all, or
        answers successfully with nothing.
    """
    try:
        result = subprocess.run(
            [SYSCTL, "-n", key], capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise UnsupportedMachineError(
            f"Could not run {SYSCTL} to read {key}: {error}. "
            "offgrid reads this machine's memory through sysctl."
        ) from error
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if not value:
        raise UnsupportedMachineError(
            f"sysctl answered for {key} but said nothing. "
            f"Its complaint was: {result.stderr.strip() or 'none'}."
        )
    return value


def detect() -> Machine:
    """Read this host's chip and memory.

    :return: The machine offgrid is running on.

    :raise UnsupportedMachineError: When the host is not an Apple Silicon Mac,
        or its memory cannot be read.
    """
    require_apple_silicon(platform.system(), platform.machine())
    memsize = _sysctl("hw.memsize")
    if memsize is None:
        raise UnsupportedMachineError(
            "sysctl does not know hw.memsize, so offgrid cannot size a model "
            "for this machine. Run `sysctl -n hw.memsize` to see for yourself."
        )
    brand = _sysctl("machdep.cpu.brand_string") or "Apple Silicon"
    return parse(brand, memsize, _sysctl("iogpu.wired_limit_mb"))
