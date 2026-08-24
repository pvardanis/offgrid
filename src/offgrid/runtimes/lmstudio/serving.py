"""What LM Studio can be asked, settled without reaching it.

A fact about the application rather than about one connection to it, which is
why it reads before anything has answered.
"""

from offgrid.domain.running.capabilities import Capabilities

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
