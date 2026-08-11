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

**agent** — the coding tool being launched. Claude Code today; OpenCode is a
candidate. Not "client".

**hosted tool** — a tool whose work happens on the vendor's servers rather
than on this machine, and which therefore cannot run at all against a model
held here. WebSearch is one: asked to search, the model emits the call, no
server-side executor answers it, and the agent renders the call as a result.
An invented answer, with no error. An agent is launched with its hosted tools
denied.

**dialect** — the HTTP API shape a runtime serves and an agent expects,
`anthropic` or `openai`. A runtime and an agent may only be paired when their
dialects match; offgrid refuses the pair rather than translating between them.

**machine** — this Mac: its chip, its unified memory, and the share of that
memory the GPU may use. One pool, shared with everything else running.

**held**, **resident** — a model the runtime currently has in memory. A held
model answers immediately; anything else costs a load first.

**load**, **let go** — putting a model into memory and taking it out again.
Loading is tens of seconds and evicts whatever prompt prefix was cached.

**launch** — an environment and an argument list, built before anything runs,
so it can be shown rather than guessed at.

**profile** — what offgrid remembers between runs. YAML, hand-editable, one per
machine.

**fits** — whether a model's weights, plus room for the context cache, are
within the memory the GPU may use. offgrid says how much room there is.

**listing** — a model as a published list describes it: a name, a parameter
count, what is active of it, a context window and a benchmark score. Nothing
about this machine, and nothing about whether it has been downloaded. A
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
the speed on this machine, and the context window. A composite, not a
measurement, and what the ranking sorts on.

**shortlist** — what survives the three rules that drop a published row, in
the order they are worth here. A row is dropped for stating no parameter
count, for stating no coding score, or for being too large at every width,
and each rule is counted rather than left silent.

**recommendation** — the shortlist as a person reads it: the table, the count
against each rule that dropped a row, and who stands behind each figure.
offgrid says what is worth trying. Downloading it, and choosing between what
is left, stay a person's.

**the last table read** — the payload a published list answered with, kept
beside the profile with the day it was read, and answered from when nothing
answers now. A stale table beats none on a machine with no network, and how
old it is is said every time it is used.
