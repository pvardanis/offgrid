"""What holding a model raises, and what it says while it works.

The command line covers what a person sees. These cover the two things it
cannot reach cleanly: which error a caller importing offgrid gets, and the
progress that travels by logging rather than by return value.
"""

import logging
from collections.abc import Sequence

import pytest

from offgrid.exceptions import ModelUnavailableError, RuntimeUnreachableError
from offgrid.hold import held, hold, let_go
from offgrid.machine import Machine
from offgrid.profile import Profile

GIB = 1024**3
RESIDENT = "a/held-7b"


@pytest.fixture
def profile() -> Profile:
    """A profile pointing at a runtime that the fakes stand in for."""
    machine = Machine(
        chip="Apple M1 Max", memory_bytes=64 * GIB, wired_limit_bytes=56 * GIB
    )

    return Profile.describing(machine, host="127.0.0.1:1234")


def _entry(identifier: str, *, in_memory: bool) -> dict:
    """Describe one model the way a catalogue does."""
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": 262144,
    }
    if in_memory:
        entry["loaded_context_length"] = 8192

    return entry


def _catalogue(
    monkeypatch, *, holding: Sequence[str] = (), cold: Sequence[str] = ()
) -> dict:
    """Stand in for the runtime, answering as what it holds changes."""
    in_memory = dict.fromkeys(holding, True) | dict.fromkeys(cold, False)
    asked: dict = {"loaded": None, "let_go": []}

    monkeypatch.setattr(
        "offgrid.hold.catalogue",
        lambda host: {
            "data": [_entry(name, in_memory=state) for name, state in in_memory.items()]
        },
    )

    def load(host: str, identifier: str) -> None:
        in_memory[identifier] = True
        asked["loaded"] = identifier

    def unload(host: str, identifier: str) -> None:
        in_memory[identifier] = False
        asked["let_go"].append(identifier)

    monkeypatch.setattr("offgrid.hold.load_model", load)
    monkeypatch.setattr("offgrid.hold.unload", unload)

    return asked


def test_a_runtime_holding_nothing_is_not_a_runtime_that_is_unreachable(
    profile, monkeypatch
):
    # The difference decides where someone looks next, so it is carried by
    # the type and not only by the wording.
    _catalogue(monkeypatch, cold=["a/cold-7b"])

    with pytest.raises(ModelUnavailableError, match="holding no model"):
        held(profile)


def test_a_model_the_runtime_does_not_have_names_what_lists_them(profile, monkeypatch):
    _catalogue(monkeypatch, holding=[RESIDENT])

    with pytest.raises(ModelUnavailableError, match="offgrid doctor"):
        hold(profile, "a/absent-7b")


def test_a_model_that_will_not_stay_held_is_reported(profile, monkeypatch):
    # The runtime took the load and is holding nothing, which the catalogue
    # is the only way to find out.
    _catalogue(monkeypatch, cold=["a/other-7b"])
    monkeypatch.setattr("offgrid.hold.load_model", lambda host, identifier: None)

    with pytest.raises(RuntimeUnreachableError, match="accepted"):
        hold(profile, "a/other-7b")


def test_a_model_that_did_not_stay_held_is_let_go_of_before_the_error(
    profile, monkeypatch
):
    # The runtime may have taken the weights even though the catalogue does
    # not say so, and nothing downstream knows to let them go.
    asked = _catalogue(monkeypatch, cold=["a/other-7b"])
    monkeypatch.setattr("offgrid.hold.load_model", lambda host, identifier: None)

    with pytest.raises(RuntimeUnreachableError):
        hold(profile, "a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_a_load_that_is_interrupted_lets_go_of_what_it_started(profile, monkeypatch):
    asked = _catalogue(monkeypatch, cold=["a/other-7b"])

    def interrupted(host: str, identifier: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("offgrid.hold.load_model", interrupted)

    with pytest.raises(KeyboardInterrupt):
        hold(profile, "a/other-7b")

    assert "a/other-7b" in asked["let_go"]


def test_the_wait_for_a_load_is_said_while_it_is_waited_for(
    profile, monkeypatch, caplog
):
    _catalogue(monkeypatch, holding=[RESIDENT], cold=["a/other-7b"])

    with caplog.at_level(logging.INFO, logger="offgrid.hold"):
        hold(profile, "a/other-7b")

    said = [record.getMessage() for record in caplog.records]
    assert any("Loading a/other-7b" in line for line in said)
    assert any("ready in" in line for line in said)


def test_what_a_swap_costs_is_said_before_it_is_paid(profile, monkeypatch, caplog):
    _catalogue(monkeypatch, holding=[RESIDENT], cold=["a/other-7b"])

    with caplog.at_level(logging.INFO, logger="offgrid.hold"):
        hold(profile, "a/other-7b")

    assert any(
        f"Letting go of {RESIDENT}" in record.getMessage()
        and "cached prefix" in record.getMessage()
        for record in caplog.records
    )


def test_a_swap_that_freed_nothing_does_not_load_on_top_of_it(profile, monkeypatch):
    # The model that would not go is still holding its memory. Asking the
    # runtime for another one either fails the load or starts the machine
    # swapping, and the wait for both is paid before either is found out.
    asked = _catalogue(monkeypatch, holding=[RESIDENT], cold=["a/other-7b"])

    def refuse(host: str, identifier: str) -> None:
        raise RuntimeUnreachableError("lms exited 0 and freed nothing")

    monkeypatch.setattr("offgrid.hold.unload", refuse)

    with pytest.raises(RuntimeUnreachableError, match="still holding"):
        hold(profile, "a/other-7b")

    assert asked["loaded"] is None


def test_letting_go_says_whether_the_memory_came_back(profile, monkeypatch):
    # A log record is for a person. A caller embedding offgrid needs an
    # answer it can branch on.
    _catalogue(monkeypatch, holding=[RESIDENT])

    assert let_go("127.0.0.1:1234", RESIDENT) is True


def test_letting_go_says_when_the_memory_did_not_come_back(profile, monkeypatch):
    def refuse(host: str, identifier: str) -> None:
        raise RuntimeUnreachableError("lms exited 0 and freed nothing")

    monkeypatch.setattr("offgrid.hold.unload", refuse)

    assert let_go("127.0.0.1:1234", RESIDENT) is False


def test_a_runtime_that_will_not_let_go_is_said_rather_than_raised(
    profile, monkeypatch, caplog
):
    # A run that has already finished is not worth failing over, but memory
    # still held is worth saying out loud.
    def refuse(host: str, identifier: str) -> None:
        raise RuntimeUnreachableError("lms would not unload it")

    monkeypatch.setattr("offgrid.hold.unload", refuse)

    with caplog.at_level(logging.WARNING, logger="offgrid.hold"):
        let_go("127.0.0.1:1234", RESIDENT)

    assert any("still holding" in record.getMessage() for record in caplog.records)


def test_nothing_is_logged_by_a_caller_that_configured_nothing(profile, monkeypatch):
    # A library that prints without being asked is a library that cannot be
    # embedded.
    _catalogue(monkeypatch, holding=[RESIDENT])

    assert logging.getLogger("offgrid.hold").handlers == []
