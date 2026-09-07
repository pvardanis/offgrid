import json
import pathlib

import pytest

from offgrid.domain.running.model import Model
from offgrid.runtimes.lmstudio import weights
from offgrid.runtimes.lmstudio.weights import (
    attach_weights,
    parse_weights,
    read_weights,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
DOWNLOADED = FIXTURES / "lmstudio_downloaded_models.json"


def downloaded() -> list[dict]:
    return json.loads(DOWNLOADED.read_text())


def test_every_downloaded_model_is_weighed_by_its_id():
    weights = parse_weights(downloaded())

    assert weights["qwen/qwen3.6-35b-a3b"] == 20429364306
    assert weights["qwen3-0.6b-mlx"] == 351383582


def test_an_embedding_the_socket_lists_is_weighed_like_any_other():
    # The socket lists every download, embeddings included; the catalogue is
    # what drops those, so the weights are keyed on all of them and the join
    # reaches only the ids a model was parsed for.
    weights = parse_weights(downloaded())

    assert weights["text-embedding-nomic-embed-text-v1.5"] == 84106624


def test_an_entry_stating_no_key_or_no_size_is_left_out():
    weights = parse_weights(
        [
            {"modelKey": "a/model-7b", "sizeBytes": 100},
            {"sizeBytes": 200},
            {"modelKey": "a/unweighed"},
        ]
    )

    assert weights == {"a/model-7b": 100}


def model(identifier: str) -> Model:
    return Model(identifier=identifier, context_ceiling=None, context_window=None)


def test_a_model_the_socket_weighed_carries_its_weight():
    joined = attach_weights([model("a/model-7b")], {"a/model-7b": 4200})

    assert joined[0].weight_bytes == 4200


def test_a_model_the_socket_did_not_weigh_keeps_none():
    joined = attach_weights([model("a/model-7b")], {})

    assert joined[0].weight_bytes is None


def test_a_model_the_catalogue_parsed_maps_onto_its_downloaded_weight():
    models = [model(entry["modelKey"]) for entry in downloaded()]
    weighed = attach_weights(models, parse_weights(downloaded()))

    joined = {m.identifier: m.weight_bytes for m in weighed}

    assert joined["qwen/qwen3.8-27b"] == 16081678492
    assert joined["google/gemma-4-e4b"] == 6861939888


def test_no_server_record_leaves_the_weights_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    # A weight is not what a run depends on, so a launch whose SDK server was
    # never recorded degrades to no weights rather than raising.
    monkeypatch.setattr(weights, "SERVER_RECORD", tmp_path / "not-there.json")

    assert read_weights() == {}


@pytest.mark.live
def test_the_running_runtime_weighs_its_downloads():
    weighed = read_weights()

    assert weighed
    assert all(size > 0 for size in weighed.values())
