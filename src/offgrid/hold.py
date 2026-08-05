"""Holding the model that will answer, and letting it go afterwards.

One machine, one pool of memory: what is held is memory the rest of the
machine cannot use, so every model but the one being asked for is let go, and
that one goes when the agent is done with it.

Progress is said at info and nothing is configured here. Whoever runs this
decides where it goes.
"""

import logging
import time

from offgrid.exceptions import ModelUnavailableError, RuntimeUnreachableError
from offgrid.model import Model
from offgrid.profile import Profile
from offgrid.runtimes.lmstudio import catalogue, loaded, parse_models, resident, unload
from offgrid.runtimes.lmstudio import load as load_model

log = logging.getLogger(__name__)


def held(profile: Profile) -> Model:
    """Find the model the runtime is already holding.

    :param profile: Where to reach the runtime.

    :return: The model that would answer.

    :raise ModelUnavailableError: When the runtime holds none.
    :raise RuntimeUnreachableError: When it cannot be reached.
    """
    resident_model = resident(catalogue(profile.host))

    if resident_model is None:
        raise ModelUnavailableError(
            f"The runtime at {profile.host} is holding no model. "
            "Load a model in it, then try again."
        )

    return resident_model


def hold(profile: Profile, identifier: str) -> Model:
    """Hold the named model, whatever the runtime is holding now.

    :param profile: Where to reach the runtime.
    :param identifier: The model asked for.

    :return: The model that will answer, described by the context the runtime
        serves it at.

    :raise ModelUnavailableError: When the runtime does not have it.
    :raise RuntimeUnreachableError: When the load fails, when another model
        answers, or when the runtime is not holding it afterwards.
    """
    payload = catalogue(profile.host)
    known = {model.identifier: model for model in parse_models(payload)}

    if identifier not in known:
        raise ModelUnavailableError(
            f"The runtime at {profile.host} does not have {identifier}. "
            "`offgrid doctor` lists what it holds."
        )

    already = resident(payload)
    if already is not None and already.identifier == identifier:
        return already

    stuck = _let_go_of_the_rest(profile.host, payload, identifier)
    if stuck:
        raise RuntimeUnreachableError(
            f"The runtime at {profile.host} is still holding {', '.join(stuck)}, so "
            f"{identifier} is not being loaded on top of it. Let go of it in the "
            "runtime directly, or restart the runtime."
        )

    log.info("  Loading %s ...", identifier)
    started = time.monotonic()

    try:
        load_model(profile.host, identifier)
        log.info("  ready in %.0fs", time.monotonic() - started)

        return _now_holding(profile, identifier)
    except BaseException:
        # However this ended, the runtime may have taken the weights, and
        # nobody downstream of here knows to let them go.
        let_go(profile.host, identifier)
        raise


def let_go(host: str, identifier: str) -> bool:
    """Unload a model, saying so if the runtime will not.

    Memory that stays held is worth saying out loud, and worth answering
    for: the log record is for whoever is watching, the answer is for
    whoever has to decide what to do next.

    :param host: Address the runtime listens on.
    :param identifier: The model to unload.

    :return: Whether the memory came back.
    """
    try:
        unload(host, identifier)
    except RuntimeUnreachableError as error:
        log.warning("  The runtime is still holding %s: %s", identifier, error)
        return False

    return True


def _now_holding(profile: Profile, identifier: str) -> Model:
    """Read back a model from the runtime that has just loaded it.

    A catalogue entry states a model's ceiling until it is loaded, and the
    window it is served at once it is. Sizing an agent's context from the
    ceiling means never compacting, and the runtime truncates the prefix
    instead — which is the failure compacting exists to avoid.

    :param profile: Where to reach the runtime.
    :param identifier: The model that was loaded.

    :return: The model as the runtime now serves it.

    :raise RuntimeUnreachableError: When it is not being held.
    """
    in_memory = {model.identifier: model for model in loaded(catalogue(profile.host))}

    if identifier not in in_memory:
        raise RuntimeUnreachableError(
            f"The runtime at {profile.host} accepted {identifier} but is not "
            "holding it. Load it in the runtime directly to see what it says."
        )

    return in_memory[identifier]


def _let_go_of_the_rest(host: str, payload: dict, wanted: str) -> list[str]:
    """Let go of every model held that is not the one being asked for.

    :param host: Address the runtime listens on.
    :param payload: The runtime's catalogue.
    :param wanted: The model that will answer.

    :return: The models whose memory did not come back.
    """
    stuck = []

    for model in loaded(payload):
        if model.identifier == wanted:
            continue

        log.info(
            "  Letting go of %s, whose cached prefix goes with it.", model.identifier
        )
        if not let_go(host, model.identifier):
            stuck.append(model.identifier)

    return stuck
