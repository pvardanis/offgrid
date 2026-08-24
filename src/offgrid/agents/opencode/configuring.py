"""What offgrid writes into a fresh OpenCode directory.

Only what offgrid never revises is here. `configure` writes this where there is
no file at all and never touches one that is there, because it cannot tell
offgrid's own earlier write from a person's deliberate edit — so anything
derived from the profile would be written once and then be wrong, silently, the
moment the profile changed. Everything offgrid derives travels in the launch
instead.

That the check is the file rather than each key is issue #155: a file that is
there but says none of this gets nothing added.
"""

SETTINGS = "opencode.json"

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
# disabled and no default for it, so what applies unset is unknown. It goes in
# the durable half because it is a standing choice about this machine, so
# somebody who wants sharing back keeps the edit.
SHARING = "disabled"

# The file is meant to be edited, and this is what gives an editor the
# completion and validation a person would otherwise be reading OpenCode's
# provider documentation for. It is a fact about the file's shape rather than
# anything offgrid derives, so it belongs on this side of the split.
SCHEMA = "https://opencode.ai/config.json"

DURABLE = {
    "$schema": SCHEMA,
    "share": SHARING,
    "provider": {PROVIDER: {"npm": PACKAGE, "name": LABEL}},
}
