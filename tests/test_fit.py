import pytest

from offgrid.fit import CACHE_SHARE, parameters_that_fit, sizes_that_fit
from offgrid.machine import Machine

GIB = 1024**3
BILLION = 1e9


def machine(memory_gib: int = 64, wired_gib: int | None = None) -> Machine:
    return Machine(
        chip="Apple M1 Max",
        memory_bytes=memory_gib * GIB,
        wired_limit_bytes=None if wired_gib is None else wired_gib * GIB,
    )


def test_four_bit_holds_twice_the_parameters_of_eight():
    lean = parameters_that_fit(machine(), quantization_bits=4)
    dense = parameters_that_fit(machine(), quantization_bits=8)
    assert lean == pytest.approx(dense * 2)


def test_a_bigger_machine_holds_more():
    assert parameters_that_fit(machine(memory_gib=64), 4) > parameters_that_fit(
        machine(memory_gib=16), 4
    )


def test_raising_the_wired_limit_holds_more():
    assert parameters_that_fit(machine(wired_gib=56), 4) > parameters_that_fit(
        machine(wired_gib=32), 4
    )


def test_room_is_left_for_the_context_cache():
    # Weights that fill the machine leave nothing for the cache the context
    # grows into, so the answer is smaller than the memory divided by the width.
    assert parameters_that_fit(machine(), 8) == pytest.approx(
        machine().usable_bytes * (1 - CACHE_SHARE)
    )


def test_this_mac_holds_a_useful_model():
    # 64GiB with the wired limit raised: about 100 billion parameters at 4-bit.
    fits = parameters_that_fit(machine(wired_gib=56), 4)
    assert 90 * BILLION < fits < 110 * BILLION


def test_a_small_mac_is_told_a_smaller_number():
    # 16GiB, wired limit untouched: a handful of billions at 4-bit.
    fits = parameters_that_fit(machine(memory_gib=16), 4)
    assert 10 * BILLION < fits < 25 * BILLION


def test_sizes_are_offered_for_each_common_width():
    offered = sizes_that_fit(machine())
    assert [bits for bits, _ in offered] == [4, 8, 16]
    assert [size for _, size in offered] == sorted(
        (size for _, size in offered), reverse=True
    )
