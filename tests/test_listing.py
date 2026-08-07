from offgrid.listing import Listing, widths_that_fit
from offgrid.machine import Machine

GIB = 1024**3
BILLION = 1e9


def machine(memory_gib: int = 64, wired_gib: int | None = None) -> Machine:
    return Machine(
        chip="Apple M1 Max",
        memory_bytes=memory_gib * GIB,
        wired_limit_bytes=None if wired_gib is None else wired_gib * GIB,
    )


def listing(parameters: float = 27 * BILLION) -> Listing:
    return Listing(
        name="A-Model-27B",
        parameters=parameters,
        context_window=262144,
        license="Apache 2.0",
    )


def test_a_listing_fits_at_the_widths_its_weights_are_small_enough_for():
    # 56GiB wired holds about 96B parameters at 4-bit, 48B at 8-bit and 24B
    # at 16-bit, so a 35B model fits at the two lean widths and not the wide.
    fits = widths_that_fit(listing(parameters=35 * BILLION), machine(wired_gib=56))

    assert [fit.quantization_bits for fit in fits] == [4, 8]


def test_the_weights_are_the_parameter_count_at_the_width_they_are_stored_at():
    # 35 billion parameters at four bits apiece is 17.5GB of weights.
    fits = {
        fit.quantization_bits: fit.weights_bytes
        for fit in widths_that_fit(
            listing(parameters=35 * BILLION), machine(wired_gib=56)
        )
    }

    assert fits[4] == 17.5e9
    assert fits[8] == 35e9


def test_a_model_larger_than_the_machine_fits_at_no_width():
    assert (
        widths_that_fit(listing(parameters=400 * BILLION), machine(wired_gib=56)) == []
    )


def test_a_small_model_fits_at_every_width():
    fits = widths_that_fit(listing(parameters=7 * BILLION), machine(wired_gib=56))

    assert [fit.quantization_bits for fit in fits] == [4, 8, 16]


def test_a_model_that_fits_a_large_mac_does_not_fit_a_small_one():
    # The same list read on two machines is two different shortlists.
    big = widths_that_fit(listing(parameters=27 * BILLION), machine(wired_gib=56))
    small = widths_that_fit(listing(parameters=27 * BILLION), machine(memory_gib=16))

    assert [fit.quantization_bits for fit in big] == [4, 8]
    assert small == []
