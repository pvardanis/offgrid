"""What running one pairing would report, and what it would cost to start.

Everything down to the conversations is the report `doctor` prints, asked for
part by part from the same place, so that two surfaces cannot word one fact
differently. It is composed against a profile the pairing was written into
rather than against the file, which is what makes it follow a highlight.

Under it, the block this owns: whether the pair can talk at all, whether the
agent is on this machine, and whether starting it costs a load. `doctor` has
never had to say any of it, because it reports the model the runtime is already
holding — there is no load in front of it to price.

Apart from `assembling.py` because the two are read by different questions —
what there is to pick from, and what one pick would do — and because the
dependency runs one way: this reaches for those values and they know nothing
about this.
"""

from offgrid.domain.assembling import (
    AgentOnThisMachine,
    Assembly,
    WhatCouldBeRun,
    WouldNotAnswer,
    find_agent,
    find_what_would_answer,
)
from offgrid.domain.checkup import (
    Checkup,
    describe_a_discarded_window,
    describe_the_agent,
    describe_the_model,
    describe_the_runtime,
    describe_what_is_requested,
)
from offgrid.domain.profile import Profile
from offgrid.domain.running.agent import AgentName
from offgrid.domain.running.dialect import Dialect, require_compatible
from offgrid.domain.running.model import Model, ModelRequest
from offgrid.shared.exceptions import DialectMismatchError
from offgrid.shared.wording import REMEDY, say_in_columns, say_indented

RUNNING = "running"
"""What the lines about the cost of a pairing are labelled.

Its own heading rather than more lines under `model`, because it is the one
part of the report that is about a keystroke nobody has pressed yet.
"""


def describe_what_would_run(
    what: WhatCouldBeRun, assembly: Assembly
) -> tuple[str, ...]:
    """Put what running a pairing would do into the lines it is read as.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The lines to say, in the order they are read.
    """
    agent = find_agent(what, assembly.agent)
    answered = agent.answered

    if isinstance(answered, WouldNotAnswer):
        return _describe_an_agent_that_would_not_answer(what, agent.name, answered)

    checkup = Checkup(
        profile=_as_assembled(what.profile, agent, assembly),
        runtime=what.runtime,
        agent=answered,
    )
    model = _find_the_model_that_would_answer(what, assembly)

    # The same lines `doctor` prints, from the same place, with the model block
    # asked for the pairing's model rather than for the one the runtime is
    # holding — the two are the same until somebody moves the highlight.
    return (
        *describe_the_runtime(checkup.profile, what.runtime),
        *describe_the_model(
            model,
            checkup.profile.model,
            held=model is not None and model.identifier in what.held,
        ),
        *describe_what_is_requested(checkup),
        *describe_the_agent(checkup),
        *describe_a_discarded_window(what.runtime),
        *_describe_what_running_would_cost(
            what, assembly, agent, answered.terms.dialect
        ),
    )


def _describe_an_agent_that_would_not_answer(
    what: WhatCouldBeRun, name: AgentName, refusal: WouldNotAnswer
) -> tuple[str, ...]:
    """Say that an agent's own settings stopped it answering at all.

    Everything read off the agent goes — the model it would run against, its
    floor, what could leave, where conversations land — because saying any of
    it would describe a pairing that cannot be assembled. What the runtime
    answered stays, because none of it was read off the agent, and a person
    whose settings file has a stray brace is still owed the finding about the
    second broken file on their machine.

    :param what: Everything that was read.
    :param name: The agent that would not answer.
    :param refusal: What stopped it.

    :return: The lines to say.
    """
    return (
        *describe_the_runtime(what.profile, what.runtime),
        say_in_columns("agent", f"{name.value}, which did not answer"),
        *say_indented(REMEDY, refusal.why),
        *describe_a_discarded_window(what.runtime),
    )


def _as_assembled(
    profile: Profile, agent: AgentOnThisMachine, assembly: Assembly
) -> Profile:
    """Write the pairing into a profile, so the report is about that pairing.

    A copy rather than the file, because nothing here is written down: this is
    what the file would say if somebody pressed the key that saves.

    :param profile: What is written down.
    :param agent: The agent the highlight is on, and its section.
    :param assembly: What the highlight is on.

    :return: The profile the report is computed against.
    """
    # The window is carried through rather than settled: a pairing that asks
    # for no number is one the runtime answers with whatever it remembers, and
    # putting a number there would be a request nobody made.
    return profile.model_copy(
        update={
            "agent": agent.config,
            "model": ModelRequest(
                identifier=assembly.model,
                context_window=profile.model.context_window,
            ),
        }
    )


def _find_the_model_that_would_answer(
    what: WhatCouldBeRun, assembly: Assembly
) -> Model | None:
    """Find the model the report's own lines are about.

    The runtime's own answer for it, so that a held model states the window it
    is served at and a cold one states only its ceiling.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.

    :return: The model, or ``None`` where the pairing would run against none.
    """
    identifier = find_what_would_answer(what, assembly)

    for model in what.downloaded_models:
        if model.identifier == identifier:
            return model

    return None


def _describe_what_running_would_cost(
    what: WhatCouldBeRun,
    assembly: Assembly,
    agent: AgentOnThisMachine,
    speaks: Dialect,
) -> tuple[str, ...]:
    """Say what pressing a key against this pairing would do.

    One answer, most disqualifying first: a pairing whose agent is not here
    cannot be started whatever the runtime serves, and a pair that cannot talk
    is refused whether or not a load would be paid for. Saying the load beside
    a refusal would price a run that is not going to happen.

    :param what: Everything that was read.
    :param assembly: What the highlight is on.
    :param agent: The agent the highlight is on.
    :param speaks: The shape that agent expects, read where it was known to
        have answered at all.

    :return: The lines to say.
    """
    if not agent.is_on_this_machine:
        return (
            say_in_columns(
                RUNNING,
                f"nothing here starts {agent.name.value}, so this pair cannot run",
            ),
        )

    refusal = _refuse_a_pair_that_cannot_talk(what, speaks)

    if refusal is not None:
        return refusal

    if not what.downloaded_models:
        return _describe_a_runtime_with_nothing_downloaded(what)

    identifier = find_what_would_answer(what, assembly)

    if identifier is None:
        return (
            say_in_columns(
                RUNNING, "no model would answer, so there is nothing to run"
            ),
        )

    if _find_the_model_that_would_answer(what, assembly) is None:
        return _refuse_a_model_the_runtime_has_not_got(what, identifier)

    return _price_the_load(what, identifier)


def _refuse_a_pair_that_cannot_talk(
    what: WhatCouldBeRun, speaks: Dialect
) -> tuple[str, ...] | None:
    """Say that the runtime serves nothing this agent speaks, if so.

    The refusal a run would meet, in the words a run meets it in, so that what
    is read here and what is read after committing are the same sentence — and
    it names every dialect the runtime serves, which is what says which end to
    change.

    :param what: Everything that was read.
    :param speaks: The shape the agent the highlight is on expects.

    :return: The lines to say, or ``None`` where the pair can talk.
    """
    try:
        require_compatible(what.runtime.served, speaks)
    except DialectMismatchError as refusal:
        return (
            say_in_columns(RUNNING, "refused, and a load would not be reached"),
            *say_indented(REMEDY, str(refusal)),
        )

    return None


def _describe_a_runtime_with_nothing_downloaded(
    what: WhatCouldBeRun,
) -> tuple[str, ...]:
    """Say that the runtime has no models at all, and what to do about it.

    Its own state and its own words: an empty list is otherwise read as offgrid
    having failed to ask, and the next step is a command rather than a search.

    :param what: Everything that was read.

    :return: The lines to say.
    """
    return (
        say_in_columns(
            RUNNING,
            f"the runtime at {what.profile.runtime.host} has nothing downloaded",
        ),
        *say_indented(
            REMEDY,
            "Run `offgrid recommend` to see what this machine can hold, and how "
            "to download it.",
        ),
    )


def _refuse_a_model_the_runtime_has_not_got(
    what: WhatCouldBeRun, identifier: str
) -> tuple[str, ...]:
    """Say that the model a run would ask for is not one the runtime has.

    The refusal `run` meets, met here for nothing. A profile can name a model
    that has since been deleted or renamed, and the list has no row for it —
    so this is the one thing a screen showing rows could otherwise never say.

    :param what: Everything that was read.
    :param identifier: The model that would be asked for.

    :return: The lines to say.
    """
    return (
        say_in_columns(
            RUNNING,
            f"the runtime at {what.profile.runtime.host} has not got {identifier}",
        ),
        *say_indented(
            REMEDY,
            "Pick one of the models listed, or name a downloaded one under "
            "`model:` in the profile.",
        ),
    )


def _price_the_load(what: WhatCouldBeRun, identifier: str) -> tuple[str, ...]:
    """Say whether starting this pairing would cost a load.

    The one thing a person cannot read anywhere else before committing: a model
    already in memory answers at once, and one that is not is minutes of
    weights moving, with whatever else is held let go of first.

    :param what: Everything that was read.
    :param identifier: The model that would answer, which the runtime has.

    :return: The line to say.
    """
    if identifier in what.held:
        return (
            say_in_columns(RUNNING, f"{identifier} is held, so this costs no load"),
        )

    return (say_in_columns(RUNNING, f"{identifier} is not held, so this costs a load"),)
