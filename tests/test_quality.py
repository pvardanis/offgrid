"""What the composite makes of a fit.

The figures asserted here are the ones issue #24 states this machine should
reach, arrived at by hand before any of this was written.
"""

from offgrid.domain.sizing.listing import Fit, Listing, get_listing_with_feasible_widths
from offgrid.domain.sizing.machine import Machine
from offgrid.domain.sizing.quality import get_quality_for_fit

GIB = 1024**3
BILLION = 1e9


def machine(chip: str = "Apple M1 Max") -> Machine:
    return Machine(chip=chip, memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB)


def small_mac() -> Machine:
    return Machine(chip="Apple M1", memory_bytes=16 * GIB, wired_limit_bytes=None)


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
        for fit in get_listing_with_feasible_widths(listed, host or machine())
        if fit.quantization_bits == bits
    )


def test_the_model_this_machine_is_for_reads_as_the_best_of_them():
    # Qwen3.6-35B-A3B at 4-bit: room to spare, 73.4 on the coding benchmark,
    # 56 tokens a second here, and a 256K window.
    judged = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION)), machine()
    )

    assert judged.score == 88
    assert judged.label == "excellent"


def test_the_dense_model_scores_higher_and_is_judged_no_better():
    # Qwen3.6-27B at 4-bit: 77.2 against the mixture's 73.4, and 18 tokens a
    # second against 56. The four points it gains it hands back and more.
    judged = get_quality_for_fit(at(4, listing(27 * BILLION, score=77.2)), machine())

    assert judged.score == 85
    assert judged.label == "excellent"


def test_the_same_model_at_a_wider_width_is_judged_worse():
    # Twice the weights to read, for the same published score and window.
    judged = get_quality_for_fit(
        at(8, listing(35 * BILLION, active=3 * BILLION)), machine()
    )

    assert judged.score == 85


def test_a_dense_model_at_a_wider_width_falls_out_of_the_top_word():
    # Qwen3.6-27B at 8-bit: 9 tokens a second, which docs/models.md describes
    # as eight minutes before the first token.
    judged = get_quality_for_fit(at(8, listing(27 * BILLION, score=77.2)), machine())

    assert judged.score == 82
    assert judged.label == "good"


def test_the_word_changes_where_the_score_crosses_and_not_beside_it():
    # 30B dense at 4-bit reads 16 tokens a second here, so the published
    # score is what moves these two rows either side of the line.
    on = get_quality_for_fit(at(4, listing(30 * BILLION, score=30)), machine())
    under = get_quality_for_fit(at(4, listing(30 * BILLION, score=26)), machine())

    assert (on.score, on.label) == (70, "good")
    assert (under.score, under.label) == (69, "decent")


def test_the_bottom_of_the_scale_is_reached_by_a_machine_that_is_short_of_room():
    # A 16GB M1 running the largest model it holds: 20B at 4-bit fills three
    # quarters of what the GPU may use and decodes below the speed term's
    # floor, so what is left of the figure is the published score.
    def judged(score: float) -> tuple[int, str]:
        listed = listing(20 * BILLION, score=score, context=8192)
        found = get_quality_for_fit(at(4, listed, small_mac()), small_mac())

        return found.score, found.label

    assert judged(90) == (50, "decent")
    assert judged(87) == (49, "weak")
    assert judged(24) == (30, "weak")
    assert judged(20) == (29, "poor")


def test_weights_that_crowd_the_machine_cost_the_room_they_take():
    # 90B at 4-bit fits, and fills three quarters of what the GPU may use.
    judged = get_quality_for_fit(at(4, listing(90 * BILLION)), machine())

    assert judged.score == 63
    assert judged.label == "decent"


def test_a_chip_nobody_measured_is_judged_without_a_speed_term():
    # Worse than the same fit on a known chip, rather than wrong. The other
    # three terms are published figures and stand on their own.
    unknown = machine(chip="Apple M9 Extreme")

    judged = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION), unknown), unknown
    )

    assert judged.score == 79
    assert judged.label == "good"


def test_a_shorter_window_is_worth_less_than_a_long_one():
    # The table publishes windows from 128K to 1M, and the term separates
    # them rather than reading full marks for anything past 4K.
    long = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION)), machine()
    )
    middling = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION, context=65536)), machine()
    )
    shortest = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION, context=4096)), machine()
    )

    assert long.score == 88
    assert middling.score == 84
    assert middling.label == "good"
    assert shortest.score == 77


def test_a_model_stating_no_window_is_judged_as_unknown_not_as_short():
    judged = get_quality_for_fit(
        at(4, listing(35 * BILLION, active=3 * BILLION, context=None)), machine()
    )

    assert judged.score == 80


def test_nothing_is_ever_called_perfect():
    # Four terms that reach 100 together, on a model good and small and fast
    # enough to take all of them. Nothing on the table is this, and the
    # figure is a composite rather than a measurement either way.
    judged = get_quality_for_fit(
        at(4, listing(7 * BILLION, active=0.5 * BILLION, score=100)), machine()
    )

    assert judged.score == 97


def test_a_model_that_only_just_fits_is_judged_as_barely_worth_it():
    # 96B dense fills the machine at 4-bit and fits at no other width. It
    # decodes at 5 tokens a second, which is the floor of the speed term,
    # and what room it leaves is most of what it loses.
    barely = listing(96 * BILLION, score=49.2)

    assert [
        fit.quantization_bits
        for fit in get_listing_with_feasible_widths(barely, machine())
    ] == [4]
    assert get_quality_for_fit(at(4, barely), machine()).score == 43
    assert get_quality_for_fit(at(4, barely), machine()).label == "weak"


def test_a_lean_build_of_a_small_model_beats_its_own_wide_one():
    # A model small enough for every width, judged at the leanest and the
    # widest. Nothing orders these but the terms themselves.
    small = listing(7 * BILLION)

    assert get_quality_for_fit(at(4, small), machine()).score == 88
    assert get_quality_for_fit(at(16, small), machine()).score == 83
