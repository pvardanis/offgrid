"""What LM Studio serves and what it can be asked, settled without reaching it.

Facts about the application rather than about one connection to it, which is
why they read before anything has answered — and that is what lets a run
refuse an impossible pairing before it pays for a load.
"""

from offgrid.domain.running.capabilities import Capabilities
from offgrid.domain.running.dialect import Dialect

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
