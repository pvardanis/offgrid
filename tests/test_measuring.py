"""What this machine is, in the lines setup prints and the screen shows.

The seam is a machine's sizing: what fits, at each quantization width. These
are the sentences both surfaces take, so that neither words the machine
differently from the other.
"""

from offgrid.domain.sizing.machine import Machine
from offgrid.domain.sizing.measuring import (
    describe_the_machine,
    describe_this_machine,
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


def test_it_points_at_recommend_and_names_no_command_a_stranger_must_run_first():
    # A stranger meets the measurement having run nothing, so it names no
    # prerequisite. `recommend` is a pointer, not a step before this one.
    machine = Machine(chip="Apple M1", memory_bytes=16 * GIB, wired_limit_bytes=None)

    shown = "\n".join(describe_the_machine(machine))

    assert "`offgrid recommend`" in shown
    assert "offgrid setup" not in shown


def test_describe_this_machine_says_how_to_raise_a_gpu_limit_still_at_its_default():
    # The one thing offgrid can suggest that changes what fits, which is why the
    # screen shows it beside the budget.
    machine = Machine(chip="Apple M1", memory_bytes=16 * GIB, wired_limit_bytes=None)

    shown = "\n".join(describe_this_machine(machine))

    assert "sudo sysctl iogpu.wired_limit_mb=14336" in shown


def test_describe_this_machine_suggests_nothing_where_the_limit_is_raised():
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )

    shown = "\n".join(describe_this_machine(machine))

    assert "iogpu.wired_limit_mb" not in shown
