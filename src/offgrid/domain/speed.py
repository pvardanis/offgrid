"""How fast a model reads its own weights on this machine.

Decoding a token means reading every weight the model uses for it, so the
speed a person feels is the chip's memory bandwidth divided by that read,
discounted by what the runtime actually achieves of the bandwidth.

The constants here are the weakest numbers offgrid has. Issue #21 measures
this machine and replaces them.
"""

from offgrid.domain.fit import BYTES_PER_GB
from offgrid.domain.listing import Fit
from offgrid.domain.machine import Machine

# Peak memory bandwidth in GB/s, by the brand string sysctl reports. Read from
# the GPU table onyx.app ships in its own front end, fetched 2026-08-07, which
# is the only per-chip list found; `docs/research/onyx-leaderboard.md` records
# where. Their M3 Max figure is the 40-core bin and Apple also ships a 300 GB/s
# one, and their M5 Pro and M5 Max rows could not be checked against Apple at
# all. A chip missing here is answered with no figure rather than a guess.
BANDWIDTH_GB_PER_SECOND = {
    "Apple M1": 68,
    "Apple M1 Pro": 200,
    "Apple M1 Max": 400,
    "Apple M1 Ultra": 800,
    "Apple M2": 100,
    "Apple M2 Pro": 200,
    "Apple M2 Max": 400,
    "Apple M2 Ultra": 800,
    "Apple M3": 100,
    "Apple M3 Pro": 150,
    "Apple M3 Max": 400,
    "Apple M4": 120,
    "Apple M4 Pro": 273,
    "Apple M4 Max": 546,
    "Apple M5": 150,
    "Apple M5 Pro": 307,
    "Apple M5 Max": 614,
}


# Peak bandwidth is what the chip can read; efficiency is the share of it a
# real decode reaches. There are two figures because the two kinds of model
# spend the bandwidth differently.
#
# A dense model reads every weight it has for every token, in one sweep the
# memory system is built for. A mixture holds many experts and routes each
# token to a few of them, so it reads far less — but it reads a different,
# scattered few each time, and picking and gathering them is time the sweep
# does not pay. The mixture still wins by a wide margin: it hands back most
# of its advantage in efficiency and keeps the rest in how little it reads.
#
# Both measured on an M1 Max and written up in `docs/models.md`: a dense
# model at 191 tok/s over 1.25GB reaches 239 GB/s of 400, and a 3B-active
# mixture at 52 tok/s over 1.63GB reaches 85.
DENSE_EFFICIENCY = 0.60
MIXTURE_EFFICIENCY = 0.21


def tokens_per_second(fit: Fit, machine: Machine) -> float | None:
    """Estimate how many tokens a second a machine decodes a fit at.

    :param fit: The model, at one of the widths this machine holds it at.
    :param machine: The host it would run on.

    :return: Tokens per second, or ``None`` for a chip whose bandwidth is
        not written down here. Every figure that follows is that bandwidth
        divided by something, so a default would be an invented answer.
    """
    peak = BANDWIDTH_GB_PER_SECOND.get(machine.chip)
    if peak is None:
        return None

    bandwidth = peak * BYTES_PER_GB
    efficiency = MIXTURE_EFFICIENCY if fit.is_mixture else DENSE_EFFICIENCY

    return bandwidth * efficiency / fit.active_bytes
