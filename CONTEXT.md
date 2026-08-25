# Context

offgrid runs a coding agent against a model held on this machine. macOS on
Apple Silicon only.

This is the language. The modules, the layers and the flows are in
`docs/architecture.md`.

## Language

Use these words in code, tests, commits and issues. They are what the modules
are named after, and drift makes the code stop describing itself.

**runtime** — the server that holds models in memory and answers requests. LM
Studio today; Ollama is a candidate. Not "backend", not "server".

**agent** — the coding tool being launched. Claude Code and OpenCode, one of
which a profile names. Not "client".

**hosted tool** — a tool whose work happens on the vendor's servers rather
than on this machine, and which therefore cannot run at all against a model
held here. WebSearch is one: asked to search, the model emits the call, no
server-side executor answers it, and the agent renders the call as a result.
An invented answer, with no error. An agent is launched with its hosted tools
denied.

**passthrough** — the arguments a person types after offgrid's own, handed to
the agent unchanged. offgrid reads them as well as passing them: one of them
decides whether the agent loads the settings offgrid wrote, so a run is refused
rather than started with its hosted tools reachable.

**dialect** — the HTTP API shape a runtime serves and an agent expects,
`anthropic` or `openai`. A runtime serves a set of them and an agent speaks
one, and the two may only be paired when the agent's is among the runtime's;
offgrid refuses the pair rather than translating between them.

**machine** — this Mac: its chip, its unified memory, and the share of that
memory the GPU may use. One pool, shared with everything else running.

**held**, **resident** — a model the runtime currently has in memory. A held
model answers immediately; anything else costs a load first.

**load**, **let go** — putting a model into memory and taking it out again.
Loading is tens of seconds and evicts whatever prompt prefix was cached.

**instance** — one copy of a model in memory. A runtime may hold the same model
more than once, and each copy costs its own memory and is let go of on its own,
so letting go of a model means letting go of every instance of it.

**hold** — to make a named model the resident one, letting go of whatever else
the runtime has. What it costs is the runtime's business: one machine has one
pool of memory, and how a runtime reaches that state differs enough that it
cannot be directed from outside. Naming no model is asking for whatever is
resident, which costs no load.

**model request** — what a run asks the runtime to hold: a model, and the
window to hold it at. Either may be absent, and absent means inherit — no model
names whichever is resident, no window leaves whatever the runtime is already
serving. It is the asking, and a **model** is the answering: a window here is
wanted and a window there is served, and the two are only usually the same
number.

**context_ceiling** — the most a model could be served at. The model's own
number, true whether or not anything is held, and what every window asked for
is measured against.

**context_window** — what a model is being served at now, and empty when
nothing is held. Everywhere outside this project the phrase names the maximum,
which is what offgrid calls the ceiling; the two together are unambiguous, so a
document quoting either one alone says which it means.

**context_floor** — the smallest window an agent can start in. What the agent
needs rather than what anyone prefers: below it the agent's own prompt does not
fit and it fails at startup, so the agent states it and nobody sets it.

**discarded window** — a window a run asked for that the runtime did not grant,
serving the model at another instead. Named for what happened rather than for
whose fault it is: offgrid asked, read the answer back, and cannot see why. It
is remembered per runtime and model, because asking again costs a release and a
load reaching the same state — and the load throws away whatever prefix the
runtime had cached.

**launch** — an environment and an argument list, built before anything runs,
so it can be shown rather than guessed at. It carries the caution below, where
there is one.

**caution** — what a person is owed before a run starts, because the agent will
otherwise do something they meet mid-session. An agent's own words, since only
it knows what it will do and which of its commands is the way out. Claude Code's
is about compaction, OpenCode's about the project configuration a run does not
read.

**profile** — what offgrid remembers between runs. YAML, hand-editable, one per
machine. A section per adapter, and one holding a **model request**, which the
command line beats key by key.

**bind** — to turn what a profile names into the runtime and agent a run talks
to. A section of the file is a name and whatever that adapter reads; it becomes
a config, and then an adapter, only once something knows which adapters there
are. Which adapters a run uses is bound before it starts; what the run
discovers — the model — is passed to them.

**fits** — whether a model's weights, plus room for the context cache, are
within the memory the GPU may use. offgrid says how much room there is.

**listing** — a model as a published list describes it: a name, a parameter
count, what is active of it, a **context_ceiling** and a benchmark score.
Nothing about this machine, and nothing about whether it has been downloaded. A
**model** is what the runtime describes; a listing is what someone else
published.

**mixture** — a model that holds many experts and routes each token to a few
of them, as against a **dense** model, which reads all of itself for every
token. Its **parameters** are what must be held in memory; its **active
parameters** are what a token actually reads. A 35B model with 3B active
costs the memory of 35B and the reading time of 3B, which is why the two
counts are carried separately and why speed is estimated from the second.

**quality** — what a fit is worth here, as a score out of 97 and a word for
it. Four terms: the room left after the weights, the published coding score,
the speed on this machine, and the **context_ceiling**. A composite, not a
measurement, and what the ranking sorts on.

**shortlist** — what survives the three rules that drop a published row, in
the order they are worth here. A row is dropped for stating no parameter
count, for stating no coding score, or for being too large at every width,
and each rule is counted rather than left silent.

**recommendation** — the shortlist as a person reads it: the table, the count
against each rule that dropped a row, and who stands behind each figure.
offgrid says what is worth trying. Downloading it, and choosing between what
is left, stay a person's.

**published list** — a leaderboard somebody else keeps, which offgrid asks two
things of: fetch whatever the table is published in, and read a **table** out
of it. offgrid holds the ones it knows in the order it asks them, and the
first with a table answers; a list further down is what answers when the site
above it is down or its page has been rewritten. Which one the figures came
from is said whenever it was not the first, because two lists score on
different benchmarks.

**the last table read** — the payload a published list answered with, kept
beside the profile with the day it was read, and answered from when none of
them answers now. A stale table beats none on a machine with no network, and
how old it is is said every time it is used.
