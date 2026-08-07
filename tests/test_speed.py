import pytest

from offgrid.listing import Fit, Listing, widths_that_fit
from offgrid.machine import Machine
from offgrid.speed import tokens_per_second

GIB = 1024**3
BILLION = 1e9


def machine(chip: str = "Apple M1 Max") -> Machine:
    return Machine(chip=chip, memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB)


def listing(parameters: float, active: float | None = None) -> Listing:
    return Listing(
        name="A-Model",
        parameters=parameters,
        active_parameters=active,
        context_window=262144,
        license="Apache 2.0",
    )


def at(bits: int, listed: Listing) -> Fit:
    return next(
        fit
        for fit in widths_that_fit(listed, machine())
        if fit.quantization_bits == bits
    )


def test_a_dense_model_is_read_whole_for_every_token():
    # An M1 Max reads 400GB/s and reaches 60% of that on a dense model, so a
    # 27B build storing 13.5GB is read about 18 times a second.
    speed = tokens_per_second(at(4, listing(27 * BILLION)), machine())

    assert speed == pytest.approx(17.8, abs=0.1)


def test_a_mixture_is_read_only_where_it_is_active():
    # 35B with 3B active at 4-bit holds 17.5GB and reads 1.5GB of it per
    # token, and reaches a fifth of the bandwidth rather than three fifths.
    speed = tokens_per_second(
        at(4, listing(35 * BILLION, active=3 * BILLION)), machine()
    )

    assert speed == pytest.approx(56, abs=0.5)


def test_a_mixture_and_a_dense_model_of_one_size_are_not_one_speed():
    # A regression guard rather than a slice: the two tests above already
    # pin the arithmetic. This is the claim the ranking rests on, said the
    # way the machine meets it — two rows the same size, ordered apart.
    dense = tokens_per_second(at(4, listing(35 * BILLION)), machine())
    mixture = tokens_per_second(
        at(4, listing(35 * BILLION, active=3 * BILLION)), machine()
    )

    assert dense == pytest.approx(13.7, abs=0.1)
    assert mixture == pytest.approx(56, abs=0.5)


def test_a_chip_nobody_measured_gets_no_figure_rather_than_a_wrong_one():
    # An unknown chip means an unknown bandwidth, and every figure downstream
    # is that number divided by something. A default would be invented.
    speed = tokens_per_second(
        at(4, listing(27 * BILLION)), machine(chip="Apple M9 Extreme")
    )

    assert speed is None
