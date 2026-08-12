"""A connection to LM Studio: what a runtime is asked, in its terms."""

import logging
import time
from dataclasses import dataclass, field

from offgrid.dialect import Dialect
from offgrid.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)
from offgrid.model import Model
from offgrid.runtime import Capabilities
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.holding import TOOL, load, unload

# What LM Studio's API can be asked, rather than what this machine can reach:
# a release commanded through `lms` needs the tool on PATH, which `unload`
# reports when it is not.
#
# `/v1/messages/count_tokens` answers 200 while the server logs `Unexpected
# endpoint or method`, so a caller cannot tell a count of zero from an endpoint
# that is not there.
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


@dataclass(frozen=True)
class LMStudio:
    """A running copy of LM Studio, at the address it was reached on.

    `dialect` and `capabilities` are facts about LM Studio rather than about
    one connection to it, so they are settled here and not passed in.

    :param host: Address it listens on.
    """

    host: str
    dialect: Dialect = field(init=False, default=Dialect.ANTHROPIC)
    capabilities: Capabilities = field(init=False, default=CAPABILITIES)

    def read_catalogue(self) -> list[Model]:
        """List every model LM Studio has, held or not.

        :return: The models it can be asked for.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return parse_models_from_payload(get_catalogue_payload(self.host))

    def read_held(self) -> list[Model]:
        """List the models LM Studio has in memory.

        :return: What is held, described by the context each is served at.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return get_loaded_models(get_catalogue_payload(self.host))

    def ensure_only(self, identifier: str) -> Model:
        """Hold the named model, whatever the runtime is holding now.

        A model that will not go is said out loud and this answers anyway
        where the wanted one is already in memory: nothing is being loaded, so
        there is nothing to refuse. Where a load is needed, it is refused
        rather than paid into a pool that is still full.

        :param identifier: The model that will answer.

        :return: The model as LM Studio now serves it.

        :raise ModelUnavailableError: When it does not have it.
        :raise ModelNotHeldError: When it took the load and is not holding it.
        :raise RuntimeUnreachableError: When it cannot be reached, when the
            load fails, when another model answers, or when what is already
            held will not go and this one would be loaded on top of it.
        """
        payload = get_catalogue_payload(self.host)
        known = {
            model.identifier: model for model in parse_models_from_payload(payload)
        }

        if identifier not in known:
            raise ModelUnavailableError(
                f"The runtime at {self.host} does not have {identifier}. "
                "`offgrid doctor` lists what it holds."
            )

        stuck = self._let_go_of_the_rest(payload, identifier)

        # `loaded` answers in catalogue order and LM Studio can hold several:
        # what matters is whether this one is among them, not whether it
        # happens to be first.
        in_memory = {model.identifier: model for model in get_loaded_models(payload)}
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

        The tool exits 0 for a name it does not know, freeing nothing, so
        what it said is not what settles this — the catalogue is. Memory that
        stays held is worth saying out loud, and worth answering for: the log
        record is for whoever is watching, the answer is for whoever has to
        decide what to do next.

        :param identifier: The model to let go of.

        :return: Whether the memory came back.
        """
        try:
            said = unload(identifier)
        except RuntimeUnreachableError as error:
            log.warning("  The runtime is still holding %s: %s", identifier, error)
            return False

        if any(model.identifier == identifier for model in self.read_held()):
            log.warning(
                "  The runtime is still holding %s: %s exited cleanly, but "
                "http://%s has it loaded — it said %s. Let it go in LM Studio "
                "directly.",
                identifier,
                TOOL,
                self.host,
                said or "nothing",
            )
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

        for model in get_loaded_models(payload):
            if model.identifier == wanted:
                continue

            log.info(
                "  Letting go of %s, whose cached prefix goes with it.",
                model.identifier,
            )
            if not self.let_go(model.identifier):
                stuck.append(model.identifier)

        return stuck
