import json
import pathlib

import pytest

from offgrid.domain.running.dialect import Dialect
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.catalogue import (
    get_held_instances,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.config import LMStudioConfig

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "lmstudio_models.json"
HELD_TWICE = FIXTURES / "lmstudio_models_held_twice.json"
ABOVE_THE_CEILING = FIXTURES / "lmstudio_models_above_the_ceiling.json"


@pytest.fixture(scope="session")
def payload() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="session")
def held_twice() -> dict:
    return json.loads(HELD_TWICE.read_text())


@pytest.fixture(scope="session")
def above_the_ceiling() -> dict:
    return json.loads(ABOVE_THE_CEILING.read_text())


def test_a_window_above_the_ceiling_is_read_as_the_runtime_states_it(
    above_the_ceiling: dict,
):
    # Captured from a live server asked to hold a model whose own maximum is
    # 40960 at 50000: it answered 200, said "loaded", and reported the
    # impossible number back. Reading it down to the ceiling here would leave
    # nothing to refuse, and would say a window is real when it is not.
    parsed = parse_models_from_payload(above_the_ceiling)
    by_id = {model.identifier: model for model in parsed}
    served = by_id["qwen3-0.6b-mlx"]

    assert served.context_ceiling == 40960
    assert served.context_window == 50000


def test_embeddings_are_not_offered_as_chat_models(payload: dict):
    identifiers = [model.identifier for model in parse_models_from_payload(payload)]
    assert "text-embedding-nomic-embed-text-v1.5" not in identifiers
    assert len(identifiers) == 3


def test_a_model_nothing_is_holding_states_a_ceiling_and_no_window(payload: dict):
    # What it could be served at is a capability, and it has one whether or
    # not anything is holding it. What it is being served at is a state, and
    # a model in nothing's memory is not being served at all.
    by_id = {model.identifier: model for model in parse_models_from_payload(payload)}
    gemma = by_id["google/gemma-4-e4b"]

    assert gemma.context_ceiling == 131072
    assert gemma.context_window is None


def test_a_model_being_held_states_the_window_it_is_served_at(held_twice: dict):
    # A model is served at the window it was loaded with, not at its ceiling.
    # This capture is the one that shows the difference: the other was taken
    # from a server holding a model at its maximum, which reports one number
    # twice.
    by_id = {model.identifier: model for model in parse_models_from_payload(held_twice)}
    held = by_id["qwen3-0.6b-mlx"]

    assert held.context_window == 4096
    assert held.context_ceiling == 40960


def test_the_model_held_is_the_loaded_one(payload: dict):
    (found,) = get_loaded_models(payload)
    assert found.identifier == "qwen/qwen3.6-35b-a3b"


def test_every_model_in_memory_is_reported():
    # LM Studio holds several at once, and each one is memory the rest of the
    # machine cannot use.
    two_of_three = {
        "data": [
            {"id": "a/cold-7b", "type": "llm", "state": "not-loaded"},
            {"id": "a/first-7b", "type": "llm", "state": "loaded"},
            {"id": "a/second-7b", "type": "llm", "state": "loaded"},
        ]
    }
    assert [model.identifier for model in get_loaded_models(two_of_three)] == [
        "a/first-7b",
        "a/second-7b",
    ]


def test_a_model_held_twice_is_two_instances_to_let_go_of(held_twice: dict):
    # Loading the same model again does not replace it: LM Studio serves both
    # copies and lists each as its own entry, the second suffixed `:2`. That
    # id is what the release endpoint takes, so it is what has to be found.
    assert get_held_instances(held_twice, "qwen3-0.6b-mlx") == [
        "qwen3-0.6b-mlx",
        "qwen3-0.6b-mlx:2",
    ]


def test_one_instance_of_a_model_is_the_only_one_named_by_its_own_id(
    held_twice: dict,
):
    # Whoever already has an instance id in hand asked about that copy, not
    # about every copy of the model it belongs to.
    assert get_held_instances(held_twice, "qwen3-0.6b-mlx:2") == ["qwen3-0.6b-mlx:2"]


def test_a_model_nothing_is_holding_has_no_instances(held_twice: dict):
    assert get_held_instances(held_twice, "google/gemma-4-e4b") == []


def test_no_model_is_in_memory_when_none_is_loaded():
    cold = {"data": [{"id": "a/b-7b", "type": "llm", "state": "not-loaded"}]}
    assert get_loaded_models(cold) == []


def test_a_model_the_api_describes_sparsely_still_parses():
    sparse = {"data": [{"id": "a/mystery", "type": "llm", "state": "not-loaded"}]}
    (model,) = parse_models_from_payload(sparse)
    assert model.identifier == "a/mystery"
    assert model.context_ceiling is None
    assert model.context_window is None


def test_lm_studio_serves_both_dialects():
    # It exposes `POST /v1/messages` and `POST /v1/chat/completions` both, so
    # an agent speaking either one pairs with it.
    assert connect(LMStudioConfig(host="127.0.0.1:1234")).dialects == frozenset(
        {Dialect.ANTHROPIC, Dialect.OPENAI}
    )


def test_downloading_is_the_application_rather_than_a_tool_on_the_path():
    # `lms get` is LM Studio's download command and `lms` is not on the `PATH`
    # until a person has bootstrapped it, which offgrid neither does nor asks
    # for. Printing the command at somebody who has not names two problems
    # where they had one, so what is printed is the application they already
    # have running.
    said = connect(LMStudioConfig(host="127.0.0.1:1234")).describe_download(
        "Qwen3.6-35B-A3B"
    )

    assert "lms" not in said
    assert "Discover" in said
