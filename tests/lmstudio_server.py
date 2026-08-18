"""LM Studio's server, answered for as what it holds changes.

Its catalogue, its loads and its releases all come over HTTP, so all three are
answered for here. Every payload is shaped as the captures in
`tests/fixtures/` shape them — a live server's answers, never a transcription
of the documentation.

Apart from `tests/doubles.py` because that file stands in for what any run
talks to — a Mac, an agent, the transport underneath — and this stands in for
one runtime. A second runtime adapter answers for its own server beside this,
and neither file grows the other's.
"""

import json

import httpx
import pytest

from offgrid.runtimes.lmstudio.holding import UNLOAD
from tests.doubles import CEILING, serve_get, serve_post


def answer_as_lm_studio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    holding: dict[str, int] | None = None,
    cold: dict[str, int] | None = None,
    ceiling: int = CEILING,
    stuck: set[str] | None = None,
    serves: int | None = None,
) -> dict:
    """Answer for LM Studio, as what it holds changes.

    Each mapping is a model against the context it is served at; a cold model
    states only its ceiling until something loads it, which is what makes the
    two numbers differ.

    :param monkeypatch: The test's patcher.
    :param holding: Models in memory, against the context each is served at.
    :param cold: Models it has and is not holding.
    :param ceiling: The context every model states before it is loaded.
    :param stuck: Instances the runtime will not free, which stay held and
        answer the release with a complaint. Named per instance rather than
        for the whole server, so that a pool with one immovable model in it
        can be arranged beside models that go.
    :param serves: What every load is served at whatever it asked for, or
        ``None`` to serve what was asked. A runtime is free to honour a window
        it was given with a different one, and a double that always agrees
        cannot tell a readback from an echo.

    :return: What it was asked to load, at what window, what it was asked to
        let go of, and in what order.
    """
    served = {**(holding or {}), **(cold or {})}
    in_memory = dict.fromkeys(holding or {}, True) | dict.fromkeys(cold or {}, False)
    immovable = stuck or set()
    asked: dict = {"loaded": None, "window": None, "let_go": [], "order": []}

    def catalogue(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    _entry(name, served=served[name], ceiling=ceiling, in_memory=state)
                    for name, state in in_memory.items()
                ]
            },
        )

    def load(identifier: str, window: int | None) -> httpx.Response:
        # A load does not replace what is held: LM Studio serves a second copy
        # beside the first, at the new window, and ids it with a suffix.
        instance = f"{identifier}:2" if in_memory.get(identifier) else identifier

        in_memory[instance] = True
        served[instance] = serves or window or served[identifier]
        asked["loaded"] = identifier
        asked["window"] = window
        asked["order"].append(("loaded", identifier))

        return httpx.Response(200, json={"instance_id": instance})

    def let_go(instance: str) -> httpx.Response:
        asked["let_go"].append(instance)
        asked["order"].append(("let_go", instance))

        if instance in immovable:
            return httpx.Response(
                500, json={"error": {"message": f"{instance} would not go"}}
            )

        if not in_memory.get(instance):
            return httpx.Response(
                404,
                json={
                    "error": {
                        "type": "model_not_found",
                        "message": f"Model with instance identifier "
                        f"'{instance}' is not loaded.",
                    }
                },
            )

        in_memory[instance] = False

        return httpx.Response(200, json={"instance_id": instance})

    def posted(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)

        if request.url.path == UNLOAD:
            return let_go(body["instance_id"])

        return load(body["model"], body.get("context_length"))

    serve_get(monkeypatch, catalogue)
    serve_post(monkeypatch, posted)

    return asked


def _entry(identifier: str, *, served: int, ceiling: int, in_memory: bool) -> dict:
    """Describe one model the way LM Studio's catalogue does.

    :param identifier: The model's id.
    :param served: The context it is served at once it is loaded.
    :param ceiling: The context it states before anything loads it.
    :param in_memory: Whether it is held.

    :return: One catalogue entry.
    """
    entry = {
        "id": identifier,
        "type": "llm",
        "state": "loaded" if in_memory else "not-loaded",
        "max_context_length": ceiling,
    }
    if in_memory:
        entry["loaded_context_length"] = served

    return entry
