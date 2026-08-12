import json
import pathlib

import pytest

from offgrid.dialect import Dialect
from offgrid.runtimes.lmstudio import connect
from offgrid.runtimes.lmstudio.catalogue import loaded, parse_models

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "lmstudio_models.json"


@pytest.fixture(scope="session")
def payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_embeddings_are_not_offered_as_chat_models(payload: dict):
    identifiers = [model.identifier for model in parse_models(payload)]
    assert "text-embedding-nomic-embed-text-v1.5" not in identifiers
    assert len(identifiers) == 3


def test_the_maximum_context_is_used_when_nothing_is_loaded(payload: dict):
    by_id = {model.identifier: model for model in parse_models(payload)}
    assert by_id["google/gemma-4-e4b"].context_limit == 131072


def test_the_loaded_context_wins_over_the_maximum():
    # A model is served at the context it was loaded with, not its ceiling.
    # The captured fixture cannot show this: a server loaded at its maximum
    # reports the same number twice.
    loaded_below_ceiling = {
        "data": [
            {
                "id": "a/model-7b",
                "type": "llm",
                "state": "loaded",
                "max_context_length": 262144,
                "loaded_context_length": 32768,
            }
        ]
    }
    (model,) = parse_models(loaded_below_ceiling)
    assert model.context_limit == 32768


def test_the_model_held_is_the_loaded_one(payload: dict):
    (found,) = loaded(payload)
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
    assert [model.identifier for model in loaded(two_of_three)] == [
        "a/first-7b",
        "a/second-7b",
    ]


def test_no_model_is_in_memory_when_none_is_loaded():
    cold = {"data": [{"id": "a/b-7b", "type": "llm", "state": "not-loaded"}]}
    assert loaded(cold) == []


def test_a_model_the_api_describes_sparsely_still_parses():
    sparse = {"data": [{"id": "a/mystery", "type": "llm", "state": "not-loaded"}]}
    (model,) = parse_models(sparse)
    assert model.identifier == "a/mystery"
    assert model.context_limit == 0


def test_lm_studio_serves_the_anthropic_dialect():
    assert connect("127.0.0.1:1234").dialect is Dialect.ANTHROPIC
