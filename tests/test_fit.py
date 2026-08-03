import pytest
from hypothesis import given
from hypothesis import strategies as st

from offgrid.fit import ranked, weights_bytes, will_load
from offgrid.machine import Machine
from offgrid.model import Model

GIB = 1024**3


def machine(memory_gib: int = 64, wired_gib: int | None = 56) -> Machine:
    return Machine(
        chip="Apple M1 Max",
        memory_bytes=memory_gib * GIB,
        wired_limit_bytes=None if wired_gib is None else wired_gib * GIB,
    )


def model(
    identifier: str = "qwen",
    params: float = 35e9,
    active: float | None = 3e9,
    bits: int = 8,
    context: int = 262144,
) -> Model:
    return Model(
        identifier=identifier,
        parameters=params,
        active_parameters=active,
        quantization_bits=bits,
        context_limit=context,
    )


def test_weights_bytes_is_one_byte_per_parameter_at_8_bit():
    assert weights_bytes(model(params=1e9, bits=8)) == pytest.approx(1e9)


def test_four_bit_weights_are_half_of_eight_bit():
    assert weights_bytes(model(bits=4)) == pytest.approx(
        weights_bytes(model(bits=8)) / 2
    )


def test_a_model_larger_than_memory_does_not_load():
    assert not will_load(model(params=70e9, bits=8), machine(memory_gib=32))


def test_a_model_that_fits_loads():
    assert will_load(model(params=35e9, bits=8), machine(memory_gib=64))


def test_the_wired_limit_caps_what_loads_when_it_is_set():
    # 35GB of weights fits in 64GB of RAM but not under a 32GB GPU wired limit.
    assert not will_load(model(params=35e9, bits=8), machine(wired_gib=32))


def test_raising_the_wired_limit_is_what_lets_a_large_model_load():
    # macOS caps the GPU near 48GB of 64GB until iogpu.wired_limit_mb is raised.
    large = model(params=52e9, bits=8)
    assert not will_load(large, machine(wired_gib=None))
    assert will_load(large, machine(wired_gib=56))


def test_ranking_prefers_fewer_active_parameters():
    moe = model(identifier="moe", params=35e9, active=3e9, bits=4)
    dense = model(identifier="dense", params=27e9, active=None, bits=4)
    assert [m.identifier for m in ranked([dense, moe], machine())] == ["moe", "dense"]


def test_ranking_drops_models_that_cannot_load():
    too_big = model(identifier="huge", params=200e9, bits=8)
    assert ranked([too_big], machine()) == []


@given(
    params=st.floats(min_value=1e6, max_value=1e12),
    low=st.sampled_from([2, 3, 4]),
    high=st.sampled_from([6, 8, 16]),
)
def test_more_bits_never_shrinks_the_weights(params: float, low: int, high: int):
    assert weights_bytes(model(params=params, bits=high)) >= weights_bytes(
        model(params=params, bits=low)
    )


@given(params=st.floats(min_value=1e6, max_value=1e12), bits=st.sampled_from([4, 8]))
def test_a_model_never_loads_on_a_machine_smaller_than_its_weights(
    params: float, bits: int
):
    weights = weights_bytes(model(params=params, bits=bits))
    tiny = Machine(chip="test", memory_bytes=int(weights) - 1, wired_limit_bytes=None)
    assert not will_load(model(params=params, bits=bits), tiny)
