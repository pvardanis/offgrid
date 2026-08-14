import pytest

from offgrid.domain.running.dialect import Dialect, require_compatible
from offgrid.shared.exceptions import DialectMismatchError


def test_matching_dialects_are_allowed():
    require_compatible(Dialect.ANTHROPIC, Dialect.ANTHROPIC)


def test_a_mismatch_names_both_sides_and_the_way_out():
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(Dialect.OPENAI, Dialect.ANTHROPIC)

    message = str(raised.value)
    assert "openai" in message
    assert "anthropic" in message
    assert "translat" in message


def test_a_mismatch_carries_both_dialects_for_a_caller_to_read():
    with pytest.raises(DialectMismatchError) as raised:
        require_compatible(Dialect.OPENAI, Dialect.ANTHROPIC)

    assert raised.value.served is Dialect.OPENAI
    assert raised.value.expected is Dialect.ANTHROPIC
