"""What each downloaded model weighs, which the REST catalogue does not say.

The catalogue at ``/api/v0/models`` names a model, its ceiling and its state,
and no byte count anywhere. LM Studio answers the weight over its SDK's socket
namespace instead, keyed on the same id the catalogue lists as ``id`` and the
socket lists as ``modelKey``. This reads that answer and joins it onto the
models the catalogue parsed.

The join is the whole point of keeping this apart from the catalogue: a weight
is a second fact from a second surface, and a socket that does not answer
leaves the weight ``None`` rather than failing the catalogue the run depends on.

The socket is the one LM Studio's own SDK speaks, and not the REST server's
port: LM Studio runs its SDK server on a port it assigns at launch and records
in an internal file, which is what the SDK reads to find it and what is read
here. On that port it is a websocket on the ``system`` namespace, authenticated
with a cooperative two-part client id, then a single ``listDownloadedModels``
RPC. That whole exchange lives here so "what a download weighs" is one file, the
way the REST catalogue's fetch and parse are.
"""

import json
import logging
import pathlib
import uuid
from dataclasses import replace

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from offgrid.domain.running.model import Model

log = logging.getLogger(__name__)

type WeightsByModelId = dict[str, int]
"""What each download weighs, keyed on the id the catalogue and socket share.

The join is the whole point: the REST catalogue lists a model as ``id`` and the
socket lists it as ``modelKey``, and these are the same string. Naming the dict
says that the key the socket answers on is the key a model is joined by, rather
than leaving two docstrings to describe one key space in two words.
"""

# Where LM Studio records the address of the SDK server it started, which is a
# different port from the REST catalogue and reassigned each launch.
SERVER_RECORD = pathlib.Path.home() / ".lmstudio" / ".internal" / "http-server.json"

# The namespace the download listing answers on, and no other.
NAMESPACE = "system"

# The one call that says what each download weighs.
ENDPOINT = "listDownloadedModels"

# A single call on a fresh socket, so its id never has to vary.
CALL_ID = 0

# The auth the server understands: a version and a two-part client id, which
# is a cooperative resource tag rather than a secret.
AUTH_VERSION = 1

TIMEOUT_SECONDS = 5


def read_weights() -> WeightsByModelId:
    """Ask LM Studio what each downloaded model weighs, keyed by id.

    A weight is not what a run depends on — the catalogue is, and that is read
    over REST — so a server record that is not there, a socket that will not
    open or authenticate, or a frame that is not the answer all leave the
    weights empty rather than failing. A blank size column is what that costs,
    and the debug log says why.

    Only the socket exchange is guarded: the parse that follows is pure, so a
    fault in it is a fault in offgrid to surface rather than a socket that did
    not answer to swallow. A listing that parsed to nothing is logged too, so a
    renamed field — the socket answering downloads none of which carry a weight
    — leaves a fingerprint rather than an unexplained column of blanks.

    :return: ``sizeBytes`` by ``modelKey`` for every download, or empty when
        the socket did not answer.
    """
    try:
        entries = _list_downloaded(_socket_host())
    except (OSError, WebSocketException, ValueError, KeyError) as error:
        log.debug("No weights from LM Studio's SDK socket: %s", error)

        return {}

    weights = parse_weights(entries)

    if entries and not weights:
        log.debug(
            "LM Studio's SDK socket listed %d downloads, none carrying a "
            "modelKey and an integer sizeBytes",
            len(entries),
        )

    return weights


def _socket_host() -> str:
    """Read the address of the SDK server LM Studio started this launch.

    :return: The ``host:port`` the socket is reached on.

    :raise OSError: When the record is not there to read.
    :raise ValueError: When it is there but not the JSON expected.
    :raise KeyError: When it names neither a host nor a port.
    """
    record = json.loads(SERVER_RECORD.read_text())

    return f"{record['host']}:{record['port']}"


def _list_downloaded(host: str) -> list[dict]:
    """Speak the SDK's socket exchange and hand back the download listing.

    :param host: Address the runtime listens on.

    :return: The ``listDownloadedModels`` result, one dict per download.

    :raise OSError: When the socket will not open.
    :raise WebSocketException: When the exchange fails partway.
    :raise ValueError: When auth is refused or a frame is not what was asked
        for, so the caller degrades to empty rather than trusting it.
    """
    url = f"ws://{host}/{NAMESPACE}"

    with connect(url, open_timeout=TIMEOUT_SECONDS) as socket:
        socket.send(json.dumps(_auth_message()))
        _read_auth_reply(socket.recv(timeout=TIMEOUT_SECONDS))

        socket.send(json.dumps(_call_message()))

        return _read_call_result(socket.recv(timeout=TIMEOUT_SECONDS))


def _auth_message() -> dict:
    """Name offgrid to the server so it can scope this client's resources.

    :return: The auth frame the server expects first.
    """
    return {
        "authVersion": AUTH_VERSION,
        "clientIdentifier": "offgrid",
        "clientPasskey": str(uuid.uuid4()),
    }


def _read_auth_reply(frame: str | bytes) -> None:
    """Refuse the exchange where the server did not accept the client.

    :param frame: The server's answer to the auth frame.

    :raise ValueError: When it did not report success.
    """
    reply = json.loads(frame)

    if not reply.get("success"):
        raise ValueError(f"the server refused the client: {reply.get('error')}")


def _call_message() -> dict:
    """Ask for the download listing over the one RPC that answers it.

    :return: The ``rpcCall`` frame for ``listDownloadedModels``.
    """
    return {"type": "rpcCall", "endpoint": ENDPOINT, "callId": CALL_ID}


def _read_call_result(frame: str | bytes) -> list[dict]:
    """Read the call's result, refusing anything that is not one.

    :param frame: The server's answer to the call frame.

    :return: The listing the result carried, one dict per download.

    :raise ValueError: When the frame is not this call's result, or its result
        is not a listing of downloads — so the caller degrades to empty rather
        than reading `.get()` off a shape that is not a dict.
    """
    reply = json.loads(frame)

    if reply.get("type") != "rpcResult" or reply.get("callId") != CALL_ID:
        raise ValueError(f"the socket answered something other than the call: {reply}")

    result = reply["result"]

    if not isinstance(result, list) or not all(
        isinstance(entry, dict) for entry in result
    ):
        raise ValueError(
            f"the socket's result was not a listing of downloads: {result}"
        )

    return result


def parse_weights(entries: list[dict]) -> WeightsByModelId:
    """Read what each downloaded model weighs, keyed on the id it is joined by.

    An entry with no ``modelKey``, or a ``sizeBytes`` that is not a whole number
    of bytes, is left out rather than guessed at or carried: the join tolerates
    a model the socket did not weigh, a weight nobody can be joined to is a
    weight about nothing, and a size that is not an integer is schema drift that
    must not reach the fit comparison, which would raise on it. A stated zero is
    a whole number and stays.

    :param entries: The socket's ``listDownloadedModels`` result, one dict per
        model it has on disk.

    :return: ``sizeBytes`` by ``modelKey``, for every entry stating both.
    """
    return {
        entry["modelKey"]: entry["sizeBytes"]
        for entry in entries
        if entry.get("modelKey") and isinstance(entry.get("sizeBytes"), int)
    }


def attach_weights(models: list[Model], weights: WeightsByModelId) -> list[Model]:
    """Join each model to what the socket said it weighs, where it said anything.

    A model the socket did not weigh keeps the ``None`` the catalogue parsed it
    with, so a weight that never arrived and a weight of zero stay told apart by
    which surface said them.

    :param models: The models the catalogue parsed, each weighing ``None``.
    :param weights: What each model weighs, keyed on its identifier.

    :return: The same models, each carrying its weight where one was joined.
    """
    return [
        replace(model, weight_bytes=weights.get(model.identifier)) for model in models
    ]
