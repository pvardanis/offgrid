"""What offgrid writes into a fresh OpenCode directory, and where it goes.

Only what offgrid never revises is here. `configure` writes this where the file
holds no edit and never touches one that does, because it cannot tell offgrid's
own earlier write from a person's deliberate edit — so anything derived from
the profile would be written once and then be wrong, silently, the moment the
profile changed. Everything offgrid derives travels in the launch instead.

A file that is there and says none of this keeps its own keys and gets none of
these added. `domain/running/config_editing.py` says why that is the answer rather
than merging them in.

The names under that directory are here too, whichever side of the split
writes them: the file above is offgrid's, and the store below is OpenCode's
own, reached through a variable the launch carries.
"""

SETTINGS = "opencode.json"

# Where OpenCode writes what a run leaves behind, rather than reads. The file
# above settles what OpenCode is configured with and nothing about where a
# session lands, and both halves are an installation: the provider a run
# answers through is derived inline and exists only inside one, so a
# conversation kept in a person's own store is one nothing outside a run can
# resolve the model of. `docs/decisions.md` has why that partition is worth
# having, under "A conversation started here is resumed here".
#
# Measured on opencode 1.18.23. Against three directory levels that did not
# exist, this variable creates all of them and then `opencode/` inside; a real
# `offgrid run` left `opencode.db` with `-wal` and `-shm` beside it, `repos/`,
# `snapshot/` and `log/` under that. The write-ahead log is where a session
# reaches first, so the database file alone is not the conversation.
#
# What moves with the conversations is what a person authenticated: the
# database's `credential` table, and the `auth.json` that `opencode auth list`
# names — asked with this variable set, it reports the moved path. Nothing was
# authenticated to watch a key become unreachable, so what was measured is
# where the file is looked for.
#
# What it does not move is `prompt-history.jsonl`, which records what a person
# typed and sits under `XDG_STATE_HOME`. The interactive interface is what
# fills it, so a one-shot run leaves it empty. Issue #184 moves that directory
# too.
#
# Not OpenCode's variable in particular — anything a run spawns sees the moved
# value, which is the price of one variable moving as much as it does.
DATA_HOME = "XDG_DATA_HOME"

# Beside the file above rather than in the directory holding it, because
# OpenCode hangs its own name off this value: pointing it at that directory
# would put a store called `opencode` inside `opencode/`.
STORE = "store"

# What `opencode run --help` and `opencode session --help` offer at the version
# below: `-c, --continue` takes up the last session, `-s, --session <id>` takes
# up one by identifier, and `opencode session list` names what is there.
CONTINUE = "--continue"
SESSION = "--session"
LISTING = "session list"
OFFERS_RESUMING = "opencode 1.18.23"

# What was measured of that store on the version below, and no more than it:
# `session list` with `XDG_DATA_HOME` pointed at a directory nothing had written
# to created the store there and answered with nothing, while the same command
# without the variable listed a person's own sessions. So which store is read is
# settled by what points that variable, which a run is one of.
#
# The listing is named with the variable rather than through `offgrid run`,
# because a run holds a model and lets it go again on its way out: looking a
# session up would cost the load the session is being looked up to avoid.
#
# The two resuming flags were not measured, because measuring one means
# generating against whatever it resolves to — the same reason `sharing.py`
# leaves `--share` unmeasured. What would settle it is a session started under a
# run and taken up again by identifier.
READS_THE_STORE = "opencode 1.18.23"

# OpenCode takes any string as a provider identifier, so nothing requires this
# to be a runtime's name — and making it one would put a fact about runtimes
# inside an agent adapter. It would also deep-merge with a provider entry a
# person wrote for that runtime themselves, where a name of offgrid's own
# cannot collide with anything they wrote.
PROVIDER = "offgrid"

# Which package the entry speaks the OpenAI-compatible protocol through. Named
# rather than relied on: measured on opencode 1.18.20, a provider absent from
# the published registry resolves against this one anyway, so writing it pins
# what offgrid expects rather than supplying something OpenCode would miss.
PACKAGE = "@ai-sdk/openai-compatible"

# What OpenCode displays for the provider, which is a key of its own rather
# than the identifier. It names no runtime for the same reason.
LABEL = "offgrid"

# A transcript leaving this machine is the promise `docs/decisions.md` makes,
# and this is the setting in the file that decides it. Written out rather than
# left to a default: the published schema states an enum of manual, auto and
# disabled and no default for it, and measured on 1.18.23 OpenCode fills none
# in, so what applies unset is unknown. It goes in the durable half because it
# is a standing choice about this machine, so somebody who wants sharing back
# keeps the edit — and `leaving.py` reads the key back, so an edit that leaves
# it unstated is reported rather than written over.
SHARING_KEY = "share"
SHARING = "disabled"

# The file is meant to be edited, and this is what gives an editor the
# completion and validation a person would otherwise be reading OpenCode's
# provider documentation for. It is a fact about the file's shape rather than
# anything offgrid derives, so it belongs on this side of the split.
SCHEMA = "https://opencode.ai/config.json"

DURABLE = {
    "$schema": SCHEMA,
    SHARING_KEY: SHARING,
    "provider": {PROVIDER: {"npm": PACKAGE, "name": LABEL}},
}
