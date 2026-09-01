"""What this machine is, in the lines setup prints and the screen shows.

The seam is a machine's sizing: what fits, at each quantization width. These
are the sentences both surfaces take, so that neither words the machine
differently from the other.
"""

from offgrid.domain.sizing.machine import Machine
from offgrid.domain.sizing.measuring import (
    describe_the_machine,
    describe_the_machine_and_how_to_fit_more,
)

GIB = 1024**3


def test_it_names_the_chip_and_the_memory():
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )

    shown = "\n".join(describe_the_machine(machine))

    assert "Apple M1 Max" in shown
    assert "64GB unified memory" in shown


def test_it_says_what_size_of_model_fits_at_each_width():
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )

    widths = [line for line in describe_the_machine(machine) if "bit" in line]

    assert [line.split("-", 1)[0].strip() for line in widths] == ["4", "8", "16"]
    assert all("parameters" in line for line in widths)


def test_the_measurement_names_no_command_to_run():
    # The measurement is the same words setup prints and the picker panel
    # shows, and the panel now recommends in place. So it names no command —
    # neither a prerequisite before it nor a pointer after it — leaving each
    # surface to add what belongs to it.
    machine = Machine(chip="Apple M1", memory_bytes=16 * GIB, wired_limit_bytes=None)

    shown = "\n".join(describe_the_machine(machine))

    assert "offgrid" not in shown


def test_it_says_how_to_raise_a_gpu_limit_still_at_its_default():
    # The one thing offgrid can suggest that changes what fits, which is why the
    # screen shows it beside the budget.
    machine = Machine(chip="Apple M1", memory_bytes=16 * GIB, wired_limit_bytes=None)

    shown = "\n".join(describe_the_machine_and_how_to_fit_more(machine))

    assert "sudo sysctl iogpu.wired_limit_mb=14336" in shown


def test_it_suggests_nothing_where_the_gpu_limit_is_already_raised():
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )

    shown = "\n".join(describe_the_machine_and_how_to_fit_more(machine))

    assert "iogpu.wired_limit_mb" not in shown
