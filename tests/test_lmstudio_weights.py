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


def test_a_zero_byte_download_is_kept_apart_from_an_unweighed_one():
    # None means the socket said nothing; zero means it said zero. Filtering on
    # truthiness would collapse them, so a stated zero survives the parse.
    weights = parse_weights([{"modelKey": "a/empty", "sizeBytes": 0}])

    assert weights == {"a/empty": 0}


def test_a_weight_that_is_not_an_integer_is_left_out():
    # A size that arrives as a string is schema drift, not a number to grey a
    # row by; it is dropped so it never reaches the fit comparison, which would
    # otherwise raise on a string against a budget.
    weights = parse_weights([{"modelKey": "a/model-7b", "sizeBytes": "100"}])

    assert weights == {}


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


class StubSocket:
    """A socket that answers with frames a test hands it, in order.

    Stands in for the SDK server's websocket so the handshake and its guards
    run against crafted frames — a refused auth, a result that is not a listing
    — without a live server. What it answers with is stated by the test; the
    parsing it drives is the real code.
    """

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)

    def __enter__(self) -> "StubSocket":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def send(self, _: str) -> None:
        pass

    def recv(self, timeout: float | None = None) -> str:
        return self._frames.pop(0)


def _answer_over_the_socket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    *frames: str,
) -> None:
    """Record a server and answer its socket with the given frames."""
    record = tmp_path / "http-server.json"
    record.write_text(json.dumps({"host": "127.0.0.1", "port": 1234}))
    monkeypatch.setattr(weights, "SERVER_RECORD", record)
    monkeypatch.setattr(
        weights, "connect", lambda url, open_timeout: StubSocket(list(frames))
    )


def test_the_handshake_weighs_each_download_the_result_carries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    # The whole exchange against a captured result: auth accepted, the call
    # answered, and each download in it weighed. The live test proves the same
    # path reaches a real server; this proves the parsing without one.
    _answer_over_the_socket(
        monkeypatch,
        tmp_path,
        json.dumps({"success": True}),
        json.dumps({"type": "rpcResult", "callId": 0, "result": downloaded()}),
    )

    assert read_weights()["qwen/qwen3.6-35b-a3b"] == 20429364306


def test_a_server_that_refuses_the_client_leaves_the_weights_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    # Auth refused is not a weight to trust; it degrades to empty. Delete the
    # success check in `_read_auth_reply` and this stops failing.
    _answer_over_the_socket(
        monkeypatch,
        tmp_path,
        json.dumps({"success": False, "error": "unknown client"}),
    )

    assert read_weights() == {}


def test_a_result_that_is_not_a_listing_leaves_the_weights_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    # A well-formed frame whose result is not a list of entries is schema drift,
    # not the answer. It degrades to empty rather than crashing the catalogue on
    # `.get()` against a non-dict — the contract the whole file rests on.
    _answer_over_the_socket(
        monkeypatch,
        tmp_path,
        json.dumps({"success": True}),
        json.dumps({"type": "rpcResult", "callId": 0, "result": "not-a-listing"}),
    )

    assert read_weights() == {}


@pytest.mark.live
def test_the_running_runtime_weighs_its_downloads():
    weighed = read_weights()

    assert weighed
    assert all(size > 0 for size in weighed.values())
