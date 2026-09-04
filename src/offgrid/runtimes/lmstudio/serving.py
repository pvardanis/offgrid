"""What LM Studio serves and what it can be asked, settled without reaching it.

Facts about the application rather than about one connection to it, which is
why they read before anything has answered — and that is what lets a run
refuse an impossible pairing before it pays for a load. How a model is
downloaded into it is the same kind of fact, and is here for the same reason:
nothing is asked, so `recommend` can print it about a model LM Studio has
never been asked about.
"""

from textwrap import fill

from offgrid.domain.running.dialect import Dialect
from offgrid.shared.wording import LINE_WIDTH

# It exposes `POST /v1/messages` beside `POST /v1/chat/completions`, so an
# agent speaking either shape can be pointed at it. `tests/test_live_dialects.py`
# asks both of a running server. Whether it serves either one *completely* is a
# different question, open as issue #43.
DIALECTS = frozenset({Dialect.ANTHROPIC, Dialect.OPENAI})


def say_nothing_answered(host: str) -> str:
    """Say that nothing answered at an address, and name every way that happens.

    Three causes, because each is checked somewhere else and a sentence naming
    one sends a person to look again at what was already true: the local server
    may not be started, LM Studio may not be on this machine at all, or the
    address may belong to a machine that is not serving. The address is said
    because it is the one part of it a person did not necessarily type — it
    comes out of a profile, and this is where a wrong one shows.

    :param host: Where the runtime was expected, as the profile says it.

    :return: What to tell whoever asked something of a runtime that is not
        answering.
    """
    return (
        f"No model server answered at http://{host}. Start LM Studio's local "
        "server, install LM Studio where this machine has not got it, or point "
        "offgrid at the machine that is serving with `offgrid setup --host`."
    )


def describe_model_download(name: str) -> str:
    """Say how a model is downloaded into LM Studio.

    Both ways, application first. The search is what everybody with LM Studio
    has, and `lms get` is what somebody who has bootstrapped the CLI can paste
    — offgrid does not require `lms` on the `PATH`, so the command is offered
    rather than instructed.

    Neither the name of the window the search sits in nor a shortcut to it is
    named. What ships as LM Studio has been a tab reached with ⌘2 and, by 1.0,
    a modal that opens from a button, so a version-specific gesture is one this
    would state wrongly on somebody's machine.
    `docs/research/adapter-surfaces.md` records what was read where.

    The application is named rather than an address: what a person opens is the
    copy in front of them, whichever machine is serving.

    The command carries a placeholder, not the name. The published table spells
    a model as its list does, which is not the identifier LM Studio downloads it
    under, so `lms get` is shown with a `<model-id>` slot rather than handed a
    name that would resolve to nothing — the name is what the search takes, in
    the app or the CLI, and the identifier is what a person fills the slot with.

    :param name: The model it is about, spelt as the published table spells it,
        which is what a person searches on rather than what the runtime answers
        to afterwards.

    :return: What to do to have that model downloaded.
    """
    # A way each, and the one carrying the command is not wrapped, so it reads
    # as the one line a person copies rather than breaking across two.
    return "\n".join(
        [
            f"To download {name}, either:",
            fill(
                "- search that name in LM Studio and download a build of it",
                LINE_WIDTH,
                subsequent_indent="  ",
            ),
            "- or run `lms get <model-id>`, where you have its CLI",
        ]
    )
