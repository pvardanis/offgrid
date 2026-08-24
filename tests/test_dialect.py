import pytest

from offgrid.domain.running.dialect import Dialect, require_compatible
from offgrid.shared.exceptions import DialectMismatchError

BOTH = frozenset({Dialect.ANTHROPIC, Dialect.OPENAI})


def test_an_agent_pairs_with_a_runtime_that_serves_what_it_expects():
    require_compatible(frozenset({Dialect.ANTHROPIC}), Dialect.ANTHROPIC)


def test_either_agent_pairs_with_a_runtime_serving_both():
    # The pairing is a membership test, so a runtime serving both shapes is
    # pairable with an agent speaking either one.
    require_compatible(BOTH, Dialect.ANTHROPIC)
    require_compatible(BOTH, Dialect.OPENAI)


def test_a_mismatch_names_both_sides_and_the_way_out():
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(frozenset({Dialect.OPENAI}), Dialect.ANTHROPIC)

    message = str(raised.value)
    assert "openai" in message
    assert "anthropic" in message
    assert "translat" in message


def test_a_runtime_serving_nothing_is_refused_saying_so():
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(frozenset(), Dialect.ANTHROPIC)

    assert "no dialect" in str(raised.value)


def test_a_runtime_serving_nothing_is_not_offered_a_proxy():
    # A proxy goes between two shapes. Offering one to somebody whose runtime
    # serves none sends them to build a translator with one end unattached,
    # when what they have is an adapter that is wrong.
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(frozenset(), Dialect.ANTHROPIC)

    message = str(raised.value)
    assert "translat" not in message
    assert "adapter" in message


def test_a_mismatch_carries_both_sides_for_a_caller_to_read():
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(frozenset({Dialect.OPENAI}), Dialect.ANTHROPIC)

    assert raised.value.served == frozenset({Dialect.OPENAI})
    assert raised.value.expected is Dialect.ANTHROPIC
