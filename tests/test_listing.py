from offgrid.listing import Fit, Listing, get_listing_with_feasible_widths
from offgrid.machine import Machine

GIB = 1024**3
BILLION = 1e9


def machine(memory_gib: int = 64, wired_gib: int | None = None) -> Machine:
    return Machine(
        chip="Apple M1 Max",
        memory_bytes=memory_gib * GIB,
        wired_limit_bytes=None if wired_gib is None else wired_gib * GIB,
    )


def listing(parameters: float = 27 * BILLION, active: float | None = None) -> Listing:
    # Dense by default: every parameter is read for every token, which the
    # table writes by stating no active count. What fits is decided by what
    # is held, so the widths a machine holds it at do not turn on this.
    return Listing(
        name="A-Model-27B",
        parameters=parameters,
        active_parameters=active,
        coding_score=77.2,
        context_window=262144,
        license="Apache 2.0",
    )


def at(bits: int, listed: Listing) -> Fit:
    return next(
        fit
        for fit in get_listing_with_feasible_widths(listed, machine(wired_gib=56))
        if fit.quantization_bits == bits
    )


def test_a_listing_fits_at_the_widths_its_weights_are_small_enough_for():
    # 56GiB wired holds about 96B parameters at 4-bit, 48B at 8-bit and 24B
    # at 16-bit, so a 35B model fits at the two lean widths and not the wide.
    fits = get_listing_with_feasible_widths(
        listing(parameters=35 * BILLION), machine(wired_gib=56)
    )

    assert [fit.quantization_bits for fit in fits] == [4, 8]


def test_the_weights_are_the_parameter_count_at_the_width_they_are_stored_at():
    # 35 billion parameters at four bits apiece is 17.5GB of weights.
    fits = {
        fit.quantization_bits: fit.weights_bytes
        for fit in get_listing_with_feasible_widths(
            listing(parameters=35 * BILLION), machine(wired_gib=56)
        )
    }

    assert fits[4] == 17.5e9
    assert fits[8] == 35e9


def test_a_model_larger_than_the_machine_fits_at_no_width():
    assert (
        get_listing_with_feasible_widths(
            listing(parameters=400 * BILLION), machine(wired_gib=56)
        )
        == []
    )


def test_a_small_model_fits_at_every_width():
    fits = get_listing_with_feasible_widths(
        listing(parameters=7 * BILLION), machine(wired_gib=56)
    )

    assert [fit.quantization_bits for fit in fits] == [4, 8, 16]


def test_a_model_that_fits_a_large_mac_does_not_fit_a_small_one():
    # The same list read on two machines is two different shortlists.
    big = get_listing_with_feasible_widths(
        listing(parameters=27 * BILLION), machine(wired_gib=56)
    )
    small = get_listing_with_feasible_widths(
        listing(parameters=27 * BILLION), machine(memory_gib=16)
    )

    assert [fit.quantization_bits for fit in big] == [4, 8]
    assert small == []


def test_a_dense_model_reads_all_of_itself_for_every_token():
    # What is held and what is read are the same thing here, which is what
    # makes the distinction invisible until a mixture turns up.
    fit = at(4, listing(27 * BILLION))

    assert not fit.is_mixture
    assert fit.active_parameters == 27 * BILLION
    assert fit.active_bytes == fit.weights_bytes


def test_a_mixture_holds_all_of_itself_and_reads_a_fraction():
    # 35B at 4-bit costs 17.5GB of memory whether or not it is a mixture.
    # Only 3B of it is read per token, so only 1.5GB is.
    fit = at(4, listing(35 * BILLION, active=3 * BILLION))

    assert fit.is_mixture
    assert fit.weights_bytes == 17.5e9
    assert fit.active_bytes == 1.5e9


def test_a_model_stating_all_of_itself_as_active_is_not_a_mixture():
    # Two rows on the table write a dense model this way rather than by
    # omitting the count.
    fit = at(4, listing(27 * BILLION, active=27 * BILLION))

    assert not fit.is_mixture
    assert fit.active_bytes == fit.weights_bytes


def test_a_model_cannot_read_more_of_itself_than_it_holds():
    # Nothing on the table states this, and a published count larger than
    # the total would otherwise make a model read weights it does not have.
    fit = at(4, listing(27 * BILLION, active=40 * BILLION))

    assert not fit.is_mixture
    assert fit.active_bytes == fit.weights_bytes
