"""What the composite makes of a fit.

The figures asserted here are the ones issue #24 states this machine should
reach, arrived at by hand before any of this was written.
"""

from offgrid.listing import Fit, Listing, widths_that_fit
from offgrid.machine import Machine
from offgrid.quality import quality

GIB = 1024**3
BILLION = 1e9


def machine(chip: str = "Apple M1 Max") -> Machine:
    return Machine(chip=chip, memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB)


def listing(
    parameters: float,
    active: float | None = None,
    score: float | None = 73.4,
    context: int | None = 262144,
) -> Listing:
    return Listing(
        name="A-Model",
        parameters=parameters,
        active_parameters=active,
        coding_score=score,
        context_window=context,
        license="Apache 2.0",
    )


def at(bits: int, listed: Listing, host: Machine | None = None) -> Fit:
    return next(
        fit
        for fit in widths_that_fit(listed, host or machine())
        if fit.quantization_bits == bits
    )


def test_the_model_this_machine_is_for_reads_as_the_best_of_them():
    # Qwen3.6-35B-A3B at 4-bit: room to spare, 73.4 on the coding benchmark,
    # 56 tokens a second here, and a 256K window.
    judged = quality(at(4, listing(35 * BILLION, active=3 * BILLION)), machine())

    assert judged.score == 88
    assert judged.label == "excellent"


def test_the_dense_model_scores_higher_and_is_judged_no_better():
    # Qwen3.6-27B at 4-bit: 77.2 against the mixture's 73.4, and 18 tokens a
    # second against 56. The four points it gains it hands back and more.
    judged = quality(at(4, listing(27 * BILLION, score=77.2)), machine())

    assert judged.score == 85


def test_the_same_model_at_a_wider_width_is_judged_worse():
    # Twice the weights to read, for the same published score and window.
    judged = quality(at(8, listing(35 * BILLION, active=3 * BILLION)), machine())

    assert judged.score == 85


def test_a_dense_model_at_a_wider_width_falls_out_of_the_top_word():
    # Qwen3.6-27B at 8-bit: 9 tokens a second, which docs/models.md describes
    # as eight minutes before the first token.
    judged = quality(at(8, listing(27 * BILLION, score=77.2)), machine())

    assert judged.score == 82
    assert judged.label == "good"


def test_weights_that_crowd_the_machine_cost_the_room_they_take():
    # 90B at 4-bit fits, and fills three quarters of what the GPU may use.
    judged = quality(at(4, listing(90 * BILLION)), machine())

    assert judged.score == 63
    assert judged.label == "decent"


def test_a_chip_nobody_measured_is_judged_without_a_speed_term():
    # Worse than the same fit on a known chip, rather than wrong. The other
    # three terms are published figures and stand on their own.
    unknown = machine(chip="Apple M9 Extreme")

    judged = quality(at(4, listing(35 * BILLION, active=3 * BILLION), unknown), unknown)

    assert judged.score == 79
    assert judged.label == "good"


def test_a_lean_build_of_a_small_model_beats_its_own_wide_one():
    # A model small enough for every width, judged at the leanest and the
    # widest. Nothing orders these but the terms themselves.
    small = listing(7 * BILLION)

    assert quality(at(4, small), machine()).score == 88
    assert quality(at(16, small), machine()).score == 83
