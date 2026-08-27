"""A connection to LM Studio: what a runtime is asked, in its terms."""

import logging
import time
from dataclasses import dataclass, field

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.runtimes.lmstudio.catalogue import (
    get_catalogue_payload,
    get_held_instances,
    get_loaded_models,
    parse_models_from_payload,
)
from offgrid.runtimes.lmstudio.config import LMStudioConfig
from offgrid.runtimes.lmstudio.holding import load_model, unload_model
from offgrid.runtimes.lmstudio.serving import CAPABILITIES, DIALECTS
from offgrid.shared.exceptions import (
    ModelNotHeldError,
    ModelUnavailableError,
    RuntimeUnreachableError,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LMStudio:
    """A running copy of LM Studio, at the address it was reached on.

    `dialects` and `capabilities` are facts about LM Studio rather than about
    one connection to it, so `serving.py` settles them and nobody passes them.

    :param config: What the profile settled for this runtime.
    """

    config: LMStudioConfig
    dialects: frozenset[Dialect] = field(init=False, default=DIALECTS)
    capabilities: Capabilities = field(init=False, default=CAPABILITIES)

    def describe_download(self, name: str) -> str:
        """Say how a model is downloaded into LM Studio.

        The application rather than a command, because the command is `lms
        get` and `lms` is not on the `PATH` until a person has bootstrapped
        it, which offgrid does not require of them — printing it at somebody
        who has not names two problems where they had one. The Discover tab
        and its shortcut are LM Studio's own, and
        `docs/research/adapter-surfaces.md` records where they were read.

        The application is named rather than the address this connection
        holds: what a person opens is the copy in front of them, whichever
        machine is serving.

        :param name: The model it is about, spelt as the published table spells
            it. LM Studio's search takes a name rather than the identifier it
            answers to afterwards.

        :return: What to do to have that model downloaded.
        """
        return (
            f"To download {name}: open LM Studio, press ⌘2 for its Discover\n"
            "tab, search that name, and download a build of it."
        )

    def read_catalogue(self) -> list[Model]:
        """List every model LM Studio has, held or not.

        :return: The models it can be asked for.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return parse_models_from_payload(get_catalogue_payload(self.config.host))

    def read_held(self) -> list[Model]:
        """List the models LM Studio has in memory.

        :return: What is held, described by the context each is served at.

        :raise RuntimeUnreachableError: When it cannot be reached.
        """
        return get_loaded_models(get_catalogue_payload(self.config.host))

    def ensure_only(self, model_request: ModelRequest) -> Model:
        """Hold the model a run asked for, whatever the runtime holds now.

        A model that will not go is said out loud and this answers anyway
        where the wanted one is already in memory at the window asked for:
        nothing is being loaded, so there is nothing to refuse. Where a load
        is needed, it is refused rather than paid into a pool that is still
        full.

        :param model_request: The model that will answer, and the window to hold
            it at. Its identifier is settled before it reaches here.

        :return: The model as LM Studio now serves it.

        :raise ModelUnavailableError: When it does not have it.
        :raise ModelNotHeldError: When it took the load and is not holding it.
        :raise RuntimeUnreachableError: When it cannot be reached, when the
            load fails, or when what is already held will not go and the
            wanted one would be loaded on top of it.
        """
        identifier, window = model_request.identifier, model_request.context_window

        if identifier is None:
            raise ModelUnavailableError(
                "No model was named, and which one is resident was not settled "
                "before the runtime was asked. `hold_model` answers that; a "
                "caller reaching the port directly has to name one."
            )

        # One payload read twice, rather than `read_catalogue` and `read_held`,
        # which fetch one each. Two fetches are two moments: a model can be let
        # go of between them, and then what the runtime has and what it holds
        # describe different states of the same machine. What is decided below
        # turns on both at once.
        payload = get_catalogue_payload(self.config.host)
        known = {
            model.identifier: model for model in parse_models_from_payload(payload)
        }

        if identifier not in known:
            raise ModelUnavailableError(
                f"The runtime at {self.config.host} does not have {identifier}. "
                "`offgrid doctor` lists what it holds."
            )

        stuck = self._let_go_of_the_rest(payload, identifier)

        # `loaded` answers in catalogue order and LM Studio can hold several:
        # what matters is whether this one is among them, not whether it
        # happens to be first.
        in_memory = {model.identifier: model for model in get_loaded_models(payload)}
        held = in_memory.get(identifier)

        if held and _is_served_at(held, window):
            return held

        # Settled before the wanted model is touched: a load that is going to
        # be refused anyway must not cost the copy that is answering now.
        if stuck:
            raise RuntimeUnreachableError(
                f"The runtime at {self.config.host} is still holding "
                f"{', '.join(stuck)}, so {identifier} is not being loaded on "
                "top of it. Let go of it in the runtime directly, or restart "
                "the runtime."
            )

        # A second load does not replace the first: LM Studio serves both
        # copies of the model, at both windows. So a window that differs is
        # reached by letting go and loading again.
        if held and not self.let_go(identifier):
            raise RuntimeUnreachableError(
                f"The runtime at {self.config.host} is serving {identifier} at "
                f"{held.context_window} and will not let it go, so it cannot be "
                f"held at {window} instead. Let it go in the runtime directly, "
                "or run at the window it is already serving."
            )

        return self._load(model_request)

    def let_go(self, identifier: str) -> bool:
        """Let go of a model, saying so if the runtime will not.

        Every copy of it, because a release names one instance and LM Studio
        serves a model twice over where it was loaded twice.

        What a release answered is not what settles this — the catalogue is.
        Memory that stays held is worth saying out loud, and worth answering
        for: the log record is for whoever is watching, the answer is for
        whoever has to decide what to do next.

        Reading the catalogue back can fail too, and a release that cannot be
        confirmed is answered for as one that did not happen. Both callers are
        cleanup, so raising here would replace what they were about to report
        with the failure of tidying up after it.

        :param identifier: The model to let go of.

        :return: Whether the memory came back.
        """
        try:
            refusals = self._release_every_instance(identifier)
            still_held = get_held_instances(
                get_catalogue_payload(self.config.host), identifier
            )
        except RuntimeUnreachableError as error:
            log.warning("The runtime is still holding %s: %s", identifier, error)
            return False

        if still_held:
            log.warning(
                "The runtime is still holding %s: http://%s has %s loaded — "
                "%s. Let it go in LM Studio directly.",
                identifier,
                self.config.host,
                ", ".join(still_held),
                "; ".join(refusals) or "it took the release and freed nothing",
            )
            return False

        return True

    def _release_every_instance(self, identifier: str) -> list[str]:
        """Ask the runtime to let go of each copy of a model it is holding.

        The model is named alongside them whether the catalogue lists it or
        not: a load that failed may have left weights behind that the
        catalogue does not show, and nobody downstream of here knows to ask
        again. What that costs where there really is nothing is one request
        answered 404.

        A refusal is collected rather than raised, so that one copy that will
        not go does not leave the others held.

        :param identifier: The model to let go of.

        :return: What the runtime said about the copies it would not free.

        :raise RuntimeUnreachableError: When the catalogue cannot be read, so
            that what is held is unknown rather than empty.
        """
        held = get_held_instances(get_catalogue_payload(self.config.host), identifier)
        refusals = []

        for instance in dict.fromkeys([identifier, *held]):
            try:
                unload_model(self.config.host, instance)
            except RuntimeUnreachableError as error:
                # Only for a copy something saw held. The one asked after on
                # the chance the catalogue was behind answers 404 when it was
                # not, and reporting that beside a real refusal explains
                # memory that is stuck with a non-event.
                if instance in held:
                    refusals.append(str(error))

        return refusals

    def _load(self, model_request: ModelRequest) -> Model:
        """Wait for a model's weights, and read back what is being served.

        What is served is read from the catalogue rather than taken from the
        load's own answer: a load LM Studio accepted is not a model it is
        holding, and only the catalogue says which of the two happened.

        :param model_request: The model to load, and the window to load it at.

        :return: The model as LM Studio now serves it.

        :raise ModelNotHeldError: When it is not held afterwards.
        :raise RuntimeUnreachableError: When the load fails.
        """
        log.info("Loading %s ...", model_request.identifier)
        started = time.monotonic()

        try:
            load_model(self.config.host, model_request)
            log.info("ready in %.0fs", time.monotonic() - started)

            return self._now_holding(str(model_request.identifier))
        except BaseException:
            # However this ended, the runtime may have taken the weights, and
            # nobody downstream of here knows to let them go.
            self.let_go(str(model_request.identifier))
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
                f"The runtime at {self.config.host} accepted {identifier} but is not "
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
                "Letting go of %s, whose cached prefix goes with it.",
                model.identifier,
            )
            if not self.let_go(model.identifier):
                stuck.append(model.identifier)

        return stuck


def _is_served_at(model: Model, window: int | None) -> bool:
    """Say whether a model in memory is already being served at a window.

    Asking for none is asking for whatever it has, so anything held answers
    it: that is how a run that says nothing about a window costs no load.

    :param model: The model the runtime is holding.
    :param window: The context asked for, or ``None`` for whatever it has.

    :return: Whether it is already what was asked for.
    """
    return window is None or model.context_window == window
