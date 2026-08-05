# Context

offgrid runs a coding agent against a model held on this machine. macOS on
Apple Silicon only.

## Language

Use these words in code, tests, commits and issues. They are what the modules
are named after, and drift makes the code stop describing itself.

**runtime** — the server that holds models in memory and answers requests. LM
Studio today; Ollama is a candidate. Not "backend", not "server".

**agent** — the coding tool being launched. Claude Code today; OpenCode is a
candidate. Not "client".

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
within the memory the GPU may use. offgrid says how much room there is. It does
not say which model to run.

## Shape

```
machine.py     what this Mac is
fit.py         how much room it has
model.py       a model the runtime describes
dialect.py     which API shapes can be paired
profile.py     what is remembered between runs
launch.py      an environment and an argument list, and running one
hold.py        holding the model that answers, and letting it go
runtimes/      one module per runtime
agents/        one module per agent
cli.py         setup, doctor, run
```

Dependencies point inwards: adapters know about the domain, the domain knows
nothing about adapters.
