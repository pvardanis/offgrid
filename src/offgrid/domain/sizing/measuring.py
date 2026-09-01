"""This machine, in the lines setup prints and the screen shows.

Both surfaces measure the machine and say what fits at each quantization
width, so the sentences they say it in come from here rather than from
whichever was written first. What decides the numbers lives in ``fit.py`` and
``machine.py``; this is only how they read.
"""

from offgrid.domain.sizing.fit import BYTES_PER_GB, get_sizes_that_fit
from offgrid.domain.sizing.machine import Machine, suggest_raising_the_gpu_limit

GIB = 1024**3
"""Bytes in a gibibyte, which is the unit the system reports memory in."""

BILLION = 1e9
"""Parameters in a billion, which is the unit a model card counts them in."""


def describe_the_machine(machine: Machine) -> tuple[str, ...]:
    """Say what this machine is, and the size of model that fits it.

    Memory in the gibibytes the system reports it in, and the model budget in
    the gigabytes a model card is published in: the two units a person reads
    each figure in, kept apart so neither figure is read in the other's.

    :param machine: What was measured.

    :return: The lines to show, in the order they are read.
    """
    limit = machine.wired_limit_bytes
    gpu = f"GPU limit {limit / GIB:.0f}GB" if limit else "GPU limit at its default"

    return (
        f"{machine.chip} · {machine.memory_bytes / GIB:.0f}GB unified memory · "
        f"{gpu} · usable {machine.usable_bytes / BYTES_PER_GB:.0f}GB",
        "",
        "A model of about this size fits, leaving room for context:",
        "",
        *(
            f"  {bits:>2}-bit   {parameters / BILLION:>5.0f}B parameters"
            for bits, parameters in get_sizes_that_fit(machine)
        ),
    )


def describe_the_machine_and_how_to_fit_more(machine: Machine) -> tuple[str, ...]:
    """Say what the machine is and what fits, then how to make more fit.

    What the screen shows a stranger on a fresh machine: the measurement, and
    the one thing offgrid can suggest that changes it — raising the GPU limit,
    where there is room to. It names no command a person must run first, since
    somebody meeting the screen has run none.

    :param machine: What was measured.

    :return: The lines to show, in the order they are read.
    """
    advice = suggest_raising_the_gpu_limit(machine)

    return (*describe_the_machine(machine), *(("", *advice) if advice else ()))
