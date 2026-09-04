"""The arithmetic of the window slider's track.

A value to a fraction of the range, a fraction back to a value, and a value
stepped by a key — the pure part of the control, so the seam that drives it
through `Pilot` never has to read a frame to know where the handle sits. What
the control does under the keys is proven at the picker seam; this proves the
sums a mouse drag and an arrow both rest on.
"""

from offgrid.tui.context_window_track import (
    get_fraction_of_value,
    get_step_value,
    get_value_at_fraction,
)

FLOOR = 100000
CEILING = 131072


def test_a_value_at_the_floor_is_the_left_edge():
    assert get_fraction_of_value(FLOOR, FLOOR, CEILING) == 0.0


def test_a_value_at_the_ceiling_is_the_right_edge():
    assert get_fraction_of_value(CEILING, FLOOR, CEILING) == 1.0


def test_a_value_midway_is_half_along():
    midpoint = FLOOR + (CEILING - FLOOR) // 2

    assert get_fraction_of_value(midpoint, FLOOR, CEILING) == 0.5


def test_a_value_below_the_floor_pins_to_the_left_edge():
    assert get_fraction_of_value(FLOOR - 5000, FLOOR, CEILING) == 0.0


def test_a_value_above_the_ceiling_pins_to_the_right_edge():
    assert get_fraction_of_value(CEILING + 5000, FLOOR, CEILING) == 1.0


def test_a_range_of_no_width_is_the_left_edge():
    # Floor equal to ceiling leaves nothing to be part-way along, so the handle
    # sits at the one point the range has rather than dividing by its width.
    assert get_fraction_of_value(FLOOR, FLOOR, FLOOR) == 0.0


def test_the_left_edge_is_the_floor():
    assert get_value_at_fraction(0.0, FLOOR, CEILING) == FLOOR


def test_the_right_edge_is_the_ceiling():
    assert get_value_at_fraction(1.0, FLOOR, CEILING) == CEILING


def test_half_along_is_the_midpoint():
    assert get_value_at_fraction(0.5, FLOOR, CEILING) == FLOOR + (CEILING - FLOOR) // 2


def test_a_fraction_past_the_right_edge_is_the_ceiling():
    assert get_value_at_fraction(1.4, FLOOR, CEILING) == CEILING


def test_a_fraction_before_the_left_edge_is_the_floor():
    assert get_value_at_fraction(-0.2, FLOOR, CEILING) == FLOOR


def test_a_step_within_the_range_moves_by_the_delta():
    assert get_step_value(120000, 4096, FLOOR, CEILING) == 124096


def test_a_step_past_the_ceiling_stops_at_it():
    assert get_step_value(130000, 4096, FLOOR, CEILING) == CEILING


def test_a_step_below_the_floor_stops_at_it():
    assert get_step_value(101000, -4096, FLOOR, CEILING) == FLOOR
