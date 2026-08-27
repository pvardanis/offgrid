"""What LM Studio serves and what it can be asked, settled without reaching it.

Facts about the application rather than about one connection to it, which is
why they read before anything has answered — and that is what lets a run
refuse an impossible pairing before it pays for a load. How a model is
downloaded into it is the same kind of fact, and is here for the same reason:
nothing is asked, so `recommend` can print it about a model LM Studio has
never been asked about.
"""

from textwrap import fill

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect
from offgrid.shared.wording import LINE_WIDTH

# It exposes `POST /v1/messages` beside `POST /v1/chat/completions`, so an
# agent speaking either shape can be pointed at it. `tests/test_live_dialects.py`
# asks both of a running server. Whether it serves either one *completely* is a
# different question, open as issue #43 — the token count `CAPABILITIES` reads
# on is one of the endpoints that answers while doing nothing.
DIALECTS = frozenset({Dialect.ANTHROPIC, Dialect.OPENAI})

# `/v1/messages/count_tokens` answers 200 while the server logs `Unexpected
# endpoint or method`, so a caller cannot tell a count of zero from an endpoint
# that is not there.
#
# Memory it may manage itself, and which is unsettled. The TTL and the
# Auto-Evict that `docs/research/adapter-surfaces.md` records both belong to a
# JIT load — one the runtime does on its own initiative to answer a request —
# and the load endpoint offgrid asks is not that. Whether a model it loads is
# ever dropped underneath it needs an hour against a live server to answer, so
# the claim is left at the reading that costs a caller a wasted check rather
# than a promise offgrid cannot keep. Issue #109.
CAPABILITIES = Capabilities(
    counts_tokens=False,
    release_can_be_commanded=True,
    manages_its_own_memory=True,
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

    :param name: The model it is about, spelt as the published table spells it.
        Both the search and `lms get` take a name rather than the identifier
        the runtime answers to afterwards.

    :return: What to do to have that model downloaded.
    """
    # The prose is wrapped and the command is not: a line broken through `lms
    # get` is one that no longer runs where it is pasted.
    return "\n".join(
        [
            fill(
                f"To download {name}: search that name in LM Studio and "
                "download a build of it, or where you have its CLI:",
                LINE_WIDTH,
            ),
            f"`lms get {name}`",
        ]
    )
