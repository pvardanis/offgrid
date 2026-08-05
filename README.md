# offgrid

Run a coding agent against a local model, tuned to the machine it runs on.

[![checks](https://github.com/pvardanis/offgrid/actions/workflows/checks.yml/badge.svg)](https://github.com/pvardanis/offgrid/actions/workflows/checks.yml)
[![python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/downloads/)
[![coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen)](#development)
[![docstrings](https://img.shields.io/badge/docstrings-100%25-brightgreen)](#development)
[![ruff](https://img.shields.io/badge/ruff-0.16.1-D7FF64?logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/badge/ty-0.0.65-261230)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-lightgrey)](#requirements)

`offgrid run` points Claude Code at a model held in memory by LM Studio on this
machine, sizes the agent's context to what that model is actually serving, and
lets the model go when the agent exits. No prompt, code or file leaves the
machine.

```console
$ offgrid run -m qwen/qwen3.6-35b-a3b
  Letting go of google/gemma-4-e4b, whose cached prefix goes with it.
  Loading qwen/qwen3.6-35b-a3b ... ready in 18s
  qwen/qwen3.6-35b-a3b, context 262144
```

## Contents

- [Why](#why)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [What a run does](#what-a-run-does)
- [The profile](#the-profile)
- [What offgrid does not do](#what-offgrid-does-not-do)
- [What LM Studio does that is worth knowing](#what-lm-studio-does-that-is-worth-knowing)
- [Measured on an M1 Max](#measured-on-an-m1-max)
- [Development](#development)
- [Layout](#layout)
- [Roadmap](#roadmap)

## Why

Pointing Claude Code at a local server is a dozen environment variables, and
getting one wrong fails quietly rather than loudly.

- **Context.** A model's catalogue entry states its *ceiling* until it is
  loaded, and the window it is *served* at afterwards. Size the agent from the
  ceiling and it never compacts — the runtime truncates the prefix instead,
  which is the failure compacting exists to prevent.
- **Memory.** One machine, one pool. A model left loaded is memory nothing else
  can use, and `lms unload` exits 0 whether or not it freed anything.
- **Naming.** Ask LM Studio for a model it does not have and it answers `200`
  with whatever *is* loaded, so a typo runs the wrong model without saying so.
- **Search.** `WebSearch` executes on Anthropic's servers. Against a local
  model there is nothing to run it, and what comes back is invented rather than
  an error.

offgrid does that plumbing, says what it did, and gets out of the way.

## Requirements

- macOS on Apple Silicon
- Python 3.13+
- [LM Studio](https://lmstudio.ai/), its local server running, and `lms` on
  your `PATH`
- [Claude Code](https://claude.com/claude-code) (`claude`)
- A model downloaded in LM Studio

## Install

With [uv](https://github.com/astral-sh/uv):

```sh
uv tool install git+https://github.com/pvardanis/offgrid
```

From a clone, for development:

```sh
git clone https://github.com/pvardanis/offgrid
cd offgrid
uv sync
uv run prek install     # run the checks on every commit
```

## Quick start

**1. Measure the machine.** This writes a profile and says how much room there
is, at each quantization width:

```console
$ offgrid setup
  Apple M1 Max · 64GB unified memory
  GPU limit  56GB
  usable     60GB

  A model of about this size fits, leaving room for context:

     4-bit      96B parameters
     8-bit      48B parameters
    16-bit      24B parameters

  Load one in your runtime, then `offgrid run`. Profile: /Users/you/.offgrid/profile.yaml
```

Which model to run is your choice. offgrid states the budget; it does not
recommend.

**2. Check the runtime is reachable and holding something:**

```console
$ offgrid doctor
  runtime   127.0.0.1:1234 reachable
  model     qwen/qwen3.6-35b-a3b
  context   262144
  agent     claude-code, speaking anthropic
```

**3. Start the agent:**

```console
$ offgrid run
  qwen/qwen3.6-35b-a3b, context 262144
```

Anything after `--` reaches the agent unchanged:

```console
$ offgrid run -- -p "explain what this module does"
```

## Commands

| Command | What it does |
|---|---|
| `offgrid setup [--host HOST]` | Measures this Mac, says what fits, writes the profile. Keeps whatever you edited into it by hand. |
| `offgrid doctor` | Reports the runtime, the model that would answer, its context, and the agent's dialect. |
| `offgrid run [-m MODEL] [-- ARGS]` | Starts the agent. Loads `MODEL` when it is not already held, otherwise uses what is. |

`-m/--model` beats the `model:` in the profile, which beats whatever the
runtime already holds.

**Exit codes**, so it composes in scripts:

| Code | Meaning |
|---|---|
| *n* | whatever the agent exited with |
| `1` | offgrid refused: no profile, no runtime, unknown model, unusable settings |
| `127` | the agent could not be started — `claude` not on `PATH` |
| `130` | interrupted |
| `128+n` | the agent was killed by signal *n* |

## What a run does

1. Reads the profile, and refuses early when the runtime and the agent speak
   different API dialects — before spending a minute on a load.
2. Writes the agent's profile directory if it is not there, and refuses to
   start when the settings there would let it search the web.
3. Lets go of every model held that is not the one being asked for, saying so,
   because the cached prefix goes with it.
4. Loads the model, and checks the reply came from the model that was asked
   for.
5. Reads the catalogue back, so the context comes from what the runtime
   *serves* rather than the ceiling it advertises.
6. Starts the agent and waits, passing on `SIGTERM` and `SIGHUP` so the agent
   never outlives the model it is talking to.
7. Lets the model go, whatever became of the agent, and confirms against the
   catalogue that it is actually gone.

The environment it builds:

| Variable | Why |
|---|---|
| `ANTHROPIC_BASE_URL` | the local runtime |
| `ANTHROPIC_AUTH_TOKEN` | the server ignores it, the agent will not start without one |
| `ANTHROPIC_MODEL`, `..._OPUS_`, `..._SONNET_`, `..._HAIKU_` | every tier resolves to the one model you have |
| `CLAUDE_CONFIG_DIR` | offgrid's own profile, keeping your plugins and servers out of the cached prefix |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | the served context, so it compacts before the runtime truncates |
| `MAX_THINKING_TOKENS=0` | thinking is paid for at decode speed |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | long replies cost wall time directly |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | less chatter to a server that is not the one answering you |

Plus `--strict-mcp-config` with no config, so no MCP servers load at all, and
`--exclude-dynamic-system-prompt-sections`, so the cached prefix stays
identical between turns.

## The profile

`~/.offgrid/profile.yaml`, hand-editable:

```yaml
host: 127.0.0.1:1234
runtime: lmstudio
agent: claude-code
chip: Apple M1 Max
memory_bytes: 68719476736
wired_limit_bytes: 60129542144
model: qwen/qwen3.6-35b-a3b
```

| Key | Meaning |
|---|---|
| `host` | where the runtime listens |
| `runtime`, `agent` | which adapters to use. Only `lmstudio` and `claude-code` exist, and a name offgrid cannot act on is refused rather than recorded |
| `chip`, `memory_bytes`, `wired_limit_bytes` | measured, refreshed by `setup` |
| `model` | what `run` uses when the command line names nothing |

A typo is an error rather than a shrug: `modle:` is reported, not read as "no
model named".

## What offgrid does not do

- **Recommend a model.** It says how much room the machine has. Which model to
  run is a judgement about your work, not about your hardware.
- **Search the web.** `WebSearch` is denied, because against a local model it
  returns invented results with no error. `WebFetch` works and stays enabled,
  so a URL that is known can still be read. A replacement is planned.
- **Enforce privacy.** Nothing stops you running a hosted agent on private
  work. Whoever wants a local model runs `offgrid`.
- **Fall back to a hosted model.** When the local model cannot do the job, that
  is the answer.
- **Run anywhere else.** macOS on Apple Silicon, one runtime, one agent. More
  of each is a later problem, and the adapters are shaped for it.

## What LM Studio does that is worth knowing

Both reproduced against a live server, and both are why the checks above exist.

**A name it does not have is answered anyway.** With `google/gemma-4-e4b`
loaded, a request for `totally/made-up-model-9000` came back `200`, body
saying `"model": "google/gemma-4-e4b"`. The model named in the reply is the
only thing that gives it away.

**`lms unload` exits 0 having freed nothing.** An unknown name prints `Model
Not Found` and still exits 0, so the exit code cannot say whether memory came
back. The catalogue can.

## Measured on an M1 Max

64GB, LM Studio:

| Model | Architecture | On disk | Decode |
|---|---|---|---|
| `qwen/qwen3.6-35b-a3b` | MoE, 3B active/token | 35G (8-bit) | 41.9 tok/s |
| `prism-ml/bonsai-27b` | dense 27B | 8.0G (2-bit) | 6.9 tok/s |

Decode tracks *active parameters*, not file size — 2-bit shrinks memory without
shrinking the matmul, so the 8GB model is six times slower than the 35GB one.
Pick by architecture.

Prefill runs at ~384 tok/s cold, and prefix caching is worth protecting: a
repeated 22k-token prefix dropped from 57.3s to 1.7s. That is why `run` says
out loud when a swap is about to throw one away. The server answers one request
at a time, so parallel subagents queue *and* evict each other's prefix — fan-out
is a net loss locally.

## Development

```sh
just install                       # the project, its tools, the commit hooks
just test                          # the suite
just cov                           # with coverage, floor at 90%
just live                          # against the runtime on this machine
just check                         # everything CI runs
```

`just` on its own lists the rest — `fmt`, `lint`, `types`, `docs` for one
check at a time, and `mutate` for a run that writes no `.pyc` files. Each one
names a hook rather than a tool, so the recipes cannot disagree with
`.pre-commit-config.yaml` about what a check is. Install it with `brew install
just`, or read the file and run the commands by hand.

The hooks run on every commit once `just install` has been run. CI runs the
same ones on Linux, where the single test that reads real hardware skips
itself.

**Live tests** are opt-in and deselected by default. They start a real agent
against a real model, so they let go of whatever the runtime is holding. They
default to `qwen3-0.6b-mlx` — small on purpose, since they prove the plumbing
rather than the answers — and `--smoke-model` points them elsewhere.

**The suite cannot reach your runtime by accident.** `tests/conftest.py` fails
any test that calls LM Studio's tool, with `live` as the single exception.

When mutation-testing by hand, set `PYTHONDONTWRITEBYTECODE=1` — edits made
within the same second as a restore leave stale `.pyc` files, and the suite
then tests code that is no longer on disk.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
with the modules as scopes. What was decided and why lives in
`docs/decisions.md`; the domain language and module shape in `CONTEXT.md`.

## Layout

```
machine.py      what this Mac is
fit.py          how much room it has
model.py        a model the runtime describes
dialect.py      which API shapes can be paired
profile.py      what is remembered between runs
runtimes/       one module per runtime
agents/         one module per agent
cli.py          setup, doctor, run
```

Dependencies point inwards: adapters know about the domain, the domain knows
nothing about adapters.

## Roadmap

- A way for local sessions to search the web, since `WebSearch` cannot work
- A second runtime, and a second agent — the adapters are shaped for it
- A model catalogue, and a verified private mode
