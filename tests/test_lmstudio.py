import json
import pathlib

import pytest

from offgrid.runtimes.lmstudio import Dialect, dialect, parse_models, resident

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "lmstudio_models.json"


@pytest.fixture(scope="session")
def payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_embeddings_are_not_offered_as_chat_models(payload: dict):
    identifiers = [model.identifier for model in parse_models(payload)]
    assert "text-embedding-nomic-embed-text-v1.5" not in identifiers
    assert len(identifiers) == 3


def test_quantization_is_read_as_a_bit_width(payload: dict):
    by_id = {model.identifier: model for model in parse_models(payload)}
    assert by_id["qwen/qwen3.6-35b-a3b"].quantization_bits == 4


@pytest.mark.parametrize(
    ("label", "bits"),
    [
        # MLX labels state the width alone.
        ("4bit", 4),
        ("8bit", 8),
        # GGUF labels carry a variant after it, which is not part of the width.
        ("Q4_K_M", 4),
        ("Q8_0", 8),
        ("Q4_0", 4),
        ("Q5_1", 5),
        ("IQ2_XXS", 2),
        # Unquantized weights.
        ("BF16", 16),
        ("F16", 16),
        ("F32", 32),
    ],
)
def test_every_quantization_label_reads_as_its_own_width(label: str, bits: int):
    payload = {"data": [{"id": "a/model-7b", "type": "llm", "quantization": label}]}
    (model,) = parse_models(payload)
    assert model.quantization_bits == bits


def test_sizes_come_from_the_identifier_because_the_api_omits_them(payload: dict):
    by_id = {model.identifier: model for model in parse_models(payload)}
    moe = by_id["qwen/qwen3.6-35b-a3b"]
    assert moe.parameters == pytest.approx(35e9)
    assert moe.active_parameters == pytest.approx(3e9)
    assert by_id["qwen/qwen3.6-27b"].active_parameters is None


def test_the_loaded_context_wins_over_the_maximum(payload: dict):
    # A model is served at the context it was loaded with, not its ceiling.
    by_id = {model.identifier: model for model in parse_models(payload)}
    assert by_id["qwen/qwen3.6-35b-a3b"].context_limit == 262144
    assert by_id["google/gemma-4-e4b"].context_limit == 131072


def test_the_resident_model_is_the_loaded_one(payload: dict):
    found = resident(payload)
    assert found is not None
    assert found.identifier == "qwen/qwen3.6-35b-a3b"


def test_nothing_is_resident_when_nothing_is_loaded():
    cold = {"data": [{"id": "a/b-7b", "type": "llm", "state": "not-loaded"}]}
    assert resident(cold) is None


def test_a_model_the_api_describes_sparsely_still_parses():
    sparse = {"data": [{"id": "a/mystery", "type": "llm", "state": "not-loaded"}]}
    (model,) = parse_models(sparse)
    assert model.parameters is None
    assert model.quantization_bits == 16
    assert model.context_limit == 0


def test_lm_studio_serves_the_anthropic_dialect():
    assert dialect() is Dialect.ANTHROPIC
