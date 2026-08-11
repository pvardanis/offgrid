"""LM Studio, which serves Anthropic's message API alongside OpenAI's."""

import logging
import subprocess
import time
from dataclasses import dataclass, field

import httpx

from offgrid.dialect import Dialect
from offgrid.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from offgrid.model import Model
from offgrid.runtime import Capabilities, Runtime

CATALOGUE = "/api/v0/models"
MESSAGES = "/v1/messages"
TIMEOUT_SECONDS = 5

# Weights come off disk at gigabytes a second, so a large model takes tens of
# seconds and a cold cache takes longer.
LOAD_TIMEOUT_SECONDS = 300

# Letting go of a model is not part of the HTTP API; LM Studio's own tool is
# what does it, and it talks to the copy running on this machine.
TOOL = "lms"

# `/v1/messages/count_tokens` answers 200 while the server logs `Unexpected
# endpoint or method`, so a caller cannot tell a count of zero from an endpoint
# that is not there. `lms unload` is what lets go.
#
# Memory it manages itself: loading through the messages endpoint is a JIT
# load, and `docs/research/adapter-surfaces.md` records what that carries — the
# app-default 60-minute TTL, and Auto-Evict keeping at most one JIT-loaded
# model. So this runtime lets go of things nobody asked it to.
CAPABILITIES = Capabilities(
    counts_tokens=False,
    release_can_be_commanded=True,
    manages_its_own_memory=True,
)

log = logging.getLogger(__name__)


def connect(host: str) -> Runtime:
    """Bind the address LM Studio listens on.

    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.

    :return: A connection offgrid can ask to hold a model.
    """
    return LMStudio(host=host)


@dataclass(frozen=True)
class LMStudio:
    """A running copy of LM Studio, at the address it was reached on.

    :param host: Address it listens on.
    :param dialect: The API shape it serves, which needs no translation for
        Claude Code.
    :param capabilities: What it can be asked to do.
    """

    host: str
    dialect: Dialect = field(init=False, default=Dialect.ANTHROPIC)
    capabilities: Capabilities = field(init=False, default=CAPABILITIES)

    def read_catalogue(self) -> list[Model]:
        """List every model LM Studio has, held or not.

        :return: The models it can be asked for.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return parse_models(catalogue(self.host))

    def read_held(self) -> list[Model]:
        """List the models LM Studio has in memory.

        :return: What is held, described by the context each is served at.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return loaded(catalogue(self.host))

    def ensure_only(self, identifier: str) -> Model:
        """Hold the named model, whatever the runtime is holding now.

        :param identifier: The model that will answer.

        :return: The model as LM Studio now serves it.

        :raise ModelUnavailableError: When it does not have it.
        :raise ModelNotHeldError: When it took the load and is not holding it.
        :raise RuntimeUnreachableError: When it cannot be reached, when the
            load fails, when another model answers, or when what is already
            held will not go and this one would be loaded on top of it.
        """
        payload = catalogue(self.host)
        known = {model.identifier: model for model in parse_models(payload)}

        if identifier not in known:
            raise ModelUnavailableError(
                f"The runtime at {self.host} does not have {identifier}. "
                "`offgrid doctor` lists what it holds."
            )

        stuck = self._let_go_of_the_rest(payload, identifier)

        # `loaded` answers in catalogue order and LM Studio can hold several:
        # what matters is whether this one is among them, not whether it
        # happens to be first.
        in_memory = {model.identifier: model for model in loaded(payload)}
        if identifier in in_memory:
            return in_memory[identifier]

        if stuck:
            raise RuntimeUnreachableError(
                f"The runtime at {self.host} is still holding {', '.join(stuck)}, "
                f"so {identifier} is not being loaded on top of it. Let go of it "
                "in the runtime directly, or restart the runtime."
            )

        return self._load(identifier)

    def let_go(self, identifier: str) -> bool:
        """Let go of a model, saying so if the runtime will not.

        Memory that stays held is worth saying out loud, and worth answering
        for: the log record is for whoever is watching, the answer is for
        whoever has to decide what to do next.

        :param identifier: The model to let go of.

        :return: Whether the memory came back.
        """
        try:
            unload(self.host, identifier)
        except RuntimeUnreachableError as error:
            log.warning("  The runtime is still holding %s: %s", identifier, error)
            return False

        return True

    def _load(self, identifier: str) -> Model:
        """Wait for a model's weights, and read back what is being served.

        :param identifier: The model to load.

        :return: The model as LM Studio now serves it.

        :raise ModelNotHeldError: When it is not held afterwards.
        :raise RuntimeUnreachableError: When the load fails.
        """
        log.info("  Loading %s ...", identifier)
        started = time.monotonic()

        try:
            load(self.host, identifier)
            log.info("  ready in %.0fs", time.monotonic() - started)

            return self._now_holding(identifier)
        except BaseException:
            # However this ended, the runtime may have taken the weights, and
            # nobody downstream of here knows to let them go.
            self.let_go(identifier)
            raise

    def _now_holding(self, identifier: str) -> Model:
        """Read back a model from the runtime that has just loaded it.

        :param identifier: The model that was loaded.

        :return: The model as the runtime now serves it.

        :raise ModelNotHeldError: When it is not being held.
        """
        in_memory = {model.identifier: model for model in self.read_held()}

        if identifier not in in_memory:
            raise ModelNotHeldError(
                f"The runtime at {self.host} accepted {identifier} but is not "
                "holding it. Load it in the runtime directly to see what it says."
            )

        return in_memory[identifier]

    def _let_go_of_the_rest(self, payload: dict, wanted: str) -> list[str]:
        """Let go of every model held that is not the one being asked for.

        :param payload: The runtime's catalogue.
        :param wanted: The model that will answer.

        :return: The models whose memory did not come back.
        """
        stuck = []

        for model in loaded(payload):
            if model.identifier == wanted:
                continue

            log.info(
                "  Letting go of %s, whose cached prefix goes with it.",
                model.identifier,
            )
            if not self.let_go(model.identifier):
                stuck.append(model.identifier)

        return stuck


def parse_models(payload: dict) -> list[Model]:
    """Read the catalogue into models that can be sized and ranked.

    :param payload: A decoded response from the catalogue endpoint.

    :return: Every model that generates text, embeddings excluded.

    :raise RuntimeUnreachableError: When the body is not a catalogue. A
        server that answers with something else has not told us it holds no
        models, and reporting an empty list would say that it did.
    """
    if "data" not in payload:
        raise RuntimeUnreachableError(
            f"The body at {CATALOGUE} is not a catalogue: it has no 'data', only "
            f"{sorted(payload) or 'nothing'}. Check the address points at LM Studio."
        )

    models = []
    for entry in payload["data"]:
        if entry.get("type") == "embeddings":
            continue

        identifier = entry.get("id")
        if not identifier:
            raise RuntimeUnreachableError(
                f"The catalogue at {CATALOGUE} lists a model with no id. "
                "Update LM Studio, or report the response it gave."
            )

        models.append(
            Model(
                identifier=identifier,
                context_limit=entry.get("loaded_context_length")
                or entry.get("max_context_length")
                or 0,
            )
        )

    return models


def loaded(payload: dict) -> list[Model]:
    """Find every model held in memory.

    The machine has one pool of memory, and LM Studio can hold several models
    in it at once, so what is held is a list rather than a single answer.

    :param payload: A decoded response from the catalogue endpoint.

    :return: Every loaded model, in catalogue order, described by the context
        the runtime serves it at rather than its ceiling.
    """
    in_memory = {
        entry["id"]
        for entry in payload.get("data", [])
        if entry.get("state") == "loaded"
    }

    return [model for model in parse_models(payload) if model.identifier in in_memory]


def catalogue(host: str) -> dict:
    """Fetch the runtime's catalogue.

    :param host: Address the runtime listens on, e.g. ``127.0.0.1:1234``.

    :return: The decoded response.

    :raise RuntimeUnreachableError: When nothing answers, when the answer
        takes too long, or when what comes back is not a catalogue. Each case
        says which it was: a server that answered with a 500 is running, and
        being told to start it sends you looking in the wrong place.
    """
    url = f"http://{host}{CATALOGUE}"

    try:
        response = httpx.get(url, timeout=TIMEOUT_SECONDS)
    except httpx.TimeoutException as error:
        raise RuntimeUnreachableError(
            f"http://{host} did not answer within {TIMEOUT_SECONDS}s. "
            "It may be loading a model; try again once it settles."
        ) from error
    except httpx.TransportError as error:
        raise RuntimeUnreachableError(
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ) from error
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            f"The answer from {url} could not be read: {error}. Something is "
            f"listening at http://{host}; check it is LM Studio's local server."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"{url} answered {response.status_code}. The server is running but "
            "served no catalogue; check its local server is enabled."
        )

    try:
        return response.json()
    except ValueError as error:
        raise RuntimeUnreachableError(
            f"{url} answered with {response.headers.get('content-type', 'no type')}, "
            f"not JSON. Is http://{host} really LM Studio?"
        ) from error


def load(host: str, identifier: str, timeout: float = LOAD_TIMEOUT_SECONDS) -> None:
    """Hold a model in memory, waiting until it is ready to answer.

    Asking for a single token is what makes the runtime load it. Doing that
    here rather than leaving it to the first real request means the wait is
    visible and attributable, instead of a silence in the middle of a turn.

    :param host: Address the runtime listens on.
    :param identifier: The model to load.
    :param timeout: How long to wait before giving up.

    :raise RuntimeUnreachableError: When the load does not finish in time,
        when the runtime refuses it, or when another model answers. A name
        LM Studio does not have is answered 200 by whatever is loaded, and
        the model named in the reply is what gives that away.
    """
    url = f"http://{host}{MESSAGES}"
    body = {
        "model": identifier,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }

    try:
        response = httpx.post(url, json=body, timeout=timeout)
    except httpx.TimeoutException as error:
        raise RuntimeUnreachableError(
            f"{identifier} did not finish loading within {timeout:.0f}s. "
            "Load it in the runtime directly, or allow longer."
        ) from error
    except httpx.TransportError as error:
        raise RuntimeUnreachableError(
            f"No model server answered at http://{host}. "
            "Start LM Studio, or point offgrid elsewhere with --host."
        ) from error
    except httpx.RequestError as error:
        raise RuntimeUnreachableError(
            f"The answer to loading {identifier} could not be read: {error}. "
            f"Check what is listening at http://{host}."
        ) from error

    if response.is_error:
        raise RuntimeUnreachableError(
            f"The runtime answered {response.status_code} loading {identifier}. "
            "Check the name against `offgrid doctor`, and that it has room."
        )

    try:
        answer = response.json()
    except ValueError as error:
        raise RuntimeUnreachableError(
            f"{url} answered {response.status_code} loading {identifier} with "
            f"{response.headers.get('content-type', 'no type')}, not JSON. "
            f"Is http://{host} really LM Studio?"
        ) from error

    answered = answer.get("model") if isinstance(answer, dict) else None
    if answered and answered != identifier:
        raise RuntimeUnreachableError(
            f"{identifier} was asked for and {answered} answered. LM Studio "
            "takes a name it does not have and lets whatever is loaded reply, "
            "so check the name against `offgrid doctor`."
        )


def unload(host: str, identifier: str) -> None:
    """Let go of a model, and confirm the memory it held came back.

    The tool exits 0 for a name it does not know, printing ``Model Not
    Found`` and freeing nothing, so its exit code alone cannot say whether
    anything was let go. The catalogue is what settles it.

    :param host: Address the runtime listens on.
    :param identifier: The model to unload.

    :raise RuntimeUnreachableError: When the runtime's tool is missing, when
        it refuses, or when the model is still held afterwards. Memory that
        stays held is worth saying out loud, since the machine has one pool
        and everything else on it shares it.
    """
    try:
        finished = subprocess.run(
            [TOOL, "unload", identifier],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeUnreachableError(
            f"Could not run {TOOL} to unload {identifier}: {error}. "
            "It ships with LM Studio; check it is on PATH."
        ) from error

    if finished.returncode != 0:
        complaint = (
            finished.stderr.strip() or finished.stdout.strip() or "no reason given"
        )
        raise RuntimeUnreachableError(
            f"{TOOL} would not unload {identifier}: {complaint}"
        )

    if any(model.identifier == identifier for model in loaded(catalogue(host))):
        raise RuntimeUnreachableError(
            f"{TOOL} exited cleanly, but http://{host} is still holding "
            f"{identifier}: {finished.stdout.strip() or 'it said nothing'}. "
            "Let it go in LM Studio directly."
        )
