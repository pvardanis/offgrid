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

`offgrid run` starts a coding **agent** against a model held in memory by a
**runtime** on this machine. It holds the model you asked for, sizes the
agent's context to the window the runtime is actually serving, and lets the
model go when the agent exits. No prompt, code or file leaves the machine.

```console
$ offgrid run -m qwen/qwen3.6-35b-a3b
  Letting go of google/gemma-4-e4b, whose cached prefix goes with it.
  Loading qwen/qwen3.6-35b-a3b ... ready in 18s
  qwen/qwen3.6-35b-a3b, context 262144
```

## Contents

- [Concepts](#concepts)
- [Why](#why)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [What a run does](#what-a-run-does)
- [Runtimes](#runtimes)
- [Agents](#agents)
- [The profile](#the-profile)
- [What offgrid does not do](#what-offgrid-does-not-do)
- [Measured on an M1 Max](#measured-on-an-m1-max)
- [Development](#development)
- [Layout](#layout)
- [Roadmap](#roadmap)

## Concepts

Five words carry the whole design, and the modules are named after them.

- **runtime** — the server that holds models in memory and answers requests.
  One adapter per runtime, in `runtimes/`.
- **agent** — the coding tool being launched. One adapter per agent, in
  `agents/`.
- **dialect** — the HTTP API shape a runtime serves and an agent expects,
  `anthropic` or `openai`. A runtime and an agent can be paired only when their
  dialects match. offgrid refuses the pair rather than translating between them.
- **held**, **resident** — a model the runtime currently has in memory. A held
  model answers immediately; anything else costs a load first.
- **profile** — what offgrid remembers between runs: one section per adapter,
  saying which runtime and agent to use and whatever each of them reads, plus
  which model to run.

## Why

Pointing an agent at a local server is a dozen environment variables, and
getting one wrong fails quietly rather than loudly.

- **Context.** A model's catalogue entry states its *ceiling* until it is
  loaded, and the window it is *served* at afterwards. Size the agent from the
  ceiling and it never compacts — the runtime truncates the prefix instead,
  which is the failure compacting exists to prevent.
- **Memory.** One machine, one pool. A model left loaded is memory nothing else
  can use, and a runtime's own tooling will happily report success having freed
  nothing.
- **Naming.** A runtime asked for a model it does not have may answer anyway,
  with whatever it does hold — so a typo runs the wrong model without saying so.
- **Search.** An agent's web search may execute on its vendor's servers. Against
  a local model there is nothing to run it, and what comes back is invented
  rather than an error.

offgrid does that plumbing, says what it did, and gets out of the way.

## Requirements

- macOS on Apple Silicon
- Python 3.13+
- A [supported runtime](#runtimes), with its local server running
- A [supported agent](#agents)
- A model downloaded in the runtime

## Install

offgrid is installed with [uv](https://github.com/astral-sh/uv), which is one
command if you do not have it:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh     # or: brew install uv
```

Then:

```sh
uv tool install git+https://github.com/pvardanis/offgrid
```

That puts `offgrid` on your `PATH`. `uv tool upgrade offgrid` later, `uv tool
uninstall offgrid` to remove it.

From a clone, for development:

```sh
git clone https://github.com/pvardanis/offgrid
cd offgrid
just install            # uv sync, and the checks on every commit
```

That puts the virtualenv at `.venv` in the clone, with offgrid and the dev
tools in it. `uv run <command>` uses it without activating anything, which is
what the recipes do. Activate it when you want the tools on your `PATH`
directly — for a shell session, or to point an editor at the interpreter:

```sh
source .venv/bin/activate    # .venv/bin/activate.fish for fish
offgrid --help               # and deactivate when done
```

The recipes need [just](https://github.com/casey/just):

```sh
brew install just                    # or: cargo install just
uvx --from rust-just just --list     # or run it without installing anything
```

Without it, `uv sync && uv run prek install` does the same thing — every recipe
is one line, so the file reads as a list of commands.

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

  `offgrid recommend` names the published models that fit.
  Load one in your runtime, then `offgrid run`. Profile: /Users/you/.offgrid/profile.yaml
```

**2. See which published models that size admits:**

```console
$ offgrid recommend
  Models that fit this machine, from the list at
  https://onyx.app/best-llm-for-coding, table dated 2026-07-20.

    model                     weights  quant   context  license
    Qwen3.6-35B-A3B            17.5GB  4-bit    262144  Apache 2.0
    Qwen3.6-35B-A3B            35.0GB  8-bit    262144  Apache 2.0
    Qwen3.6-27B                13.5GB  4-bit    262144  Apache 2.0
    Qwen3.6-27B                27.0GB  8-bit    262144  Apache 2.0

  Download one in your runtime, then `offgrid run`.
```

Downloading one, and choosing between what is left, stay yours. This is the
one command that reaches the network — see [Commands](#commands).

**3. Check the runtime is reachable and holding something:**

```console
$ offgrid doctor
  runtime   lmstudio at 127.0.0.1:1234, reachable
  model     qwen/qwen3.6-35b-a3b
  context   262144
  agent     claude-code, speaking anthropic
```

**4. Start the agent:**

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
| `offgrid recommend` | Fetches a published coding table, keeps the models this machine can hold, and prints them at each width they fit at. |
| `offgrid doctor` | Reports the runtime, the model that would answer, its context, and the agent's dialect. |
| `offgrid run [-m MODEL] [-- ARGS]` | Starts the agent. Loads `MODEL` when it is not already held, otherwise uses what is. |

`-m/--model` beats the `model:` in the profile, which beats whatever the
runtime already holds.

**`recommend` is the only command that reaches the network.** It is a `GET` of
one public page, `https://onyx.app/best-llm-for-coding`, carrying an `RSC: 1`
header alongside the HTTP client's own defaults — no model name, no memory
figure, nothing about this machine or the work being done on it, and no
cookie, since nothing is kept between runs. What the other end can see is what any
web request shows it: an IP address, a time, and the page asked for. Nothing is
downloaded, and nothing is written.

**Exit codes**, so it composes in scripts:

| Code | Meaning |
|---|---|
| *n* | whatever the agent exited with |
| `1` | offgrid refused: no profile, no runtime, unknown model, unusable settings |
| `127` | the agent could not be started |
| `130` | interrupted |
| `128+n` | the agent was killed by signal *n* |

## What a run does

1. Reads the profile, and refuses early when the runtime and the agent speak
   different dialects — before spending a minute on a load.
2. Writes the agent's profile directory if it is not there, and refuses to
   start when the settings there would undo a guarantee offgrid makes.
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

## Runtimes

| Runtime | Dialect served | Supported |
|---|---|---|
| [LM Studio](https://lmstudio.ai/) | `anthropic` | ✅ |
| [Ollama](https://ollama.com/) | `openai` | ❌ |

Adding one is a module in `runtimes/` exposing a config class and a
`connect(config)`, and one line each in the two registries beside it. The
config declares which keys the runtime section may carry, and offgrid refuses
the rest on the adapter's behalf. Its name is a property of the class rather
than a field, so a config cannot claim to be an adapter it is not. What that answers with satisfies `Runtime`: it
reports a dialect and what it can be asked to do, lists what it has and what it
holds, holds one model alone, and lets one go. How it reaches that state is its
own business, and nothing above knows which runtime is answering.

Ollama serving the `openai` dialect is the interesting part: pairing it with an
agent that expects `anthropic` would be refused rather than translated, so it
needs an agent on the same side or a proxy of your own between them.

<details>
<summary><b>LM Studio</b> — the endpoints used, and two behaviours worth knowing</summary>

<br>

Reached over HTTP at the `host` in your profile, and nowhere else: nothing
offgrid does needs LM Studio's `lms` command on your `PATH`. That wants
**LM Studio 0.4.0 or newer**, which is where the unload endpoint arrived — an
older one answers the release with a 404 at the end of a run, after the agent
has finished. It serves Anthropic's `/v1/messages` alongside OpenAI's, so an
Anthropic-dialect agent needs no translating proxy.

- **Catalogue** — `GET /api/v0/models`, which states each model's
  `max_context_length` and, once loaded, the `loaded_context_length` it is
  actually served at. Embeddings models are filtered out.
- **Loading** — a one-token request to `/v1/messages`. Doing it here rather
  than leaving it to the agent's first message makes the wait visible and
  attributable instead of a silence mid-turn.
- **Unloading** — `POST /api/v1/models/unload`, once per copy held and once
  for the name asked about whether it is listed or not, because a load that
  failed may have left weights the catalogue does not show yet. The catalogue
  is read back afterwards, and it is what says whether the memory came back.

Two behaviours are worth knowing, both reproduced against a live server, and
both the reason for the checks above:

**A name it does not have is answered anyway.** With `google/gemma-4-e4b`
loaded, a request for `totally/made-up-model-9000` came back `200`, body saying
`"model": "google/gemma-4-e4b"`. The model named in the reply is the only thing
that gives it away.

**A model loaded twice is held twice.** The second load does not replace the
first: both copies stay in memory, and the catalogue lists each as its own
entry with the second suffixed `:2`. Those ids are what the release takes, so
letting go of a model means letting go of every one of them.

</details>

## Agents

| Agent | Dialect expected | Supported |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | `anthropic` | ✅ |
| [OpenCode](https://opencode.ai/) | either, per provider | ❌ |

Adding one is a module in `agents/`: a config class declaring which keys your
section carries, then report a dialect, build a launch — an environment and an
argument list — and prepare whatever profile it reads. The config carries where
the runtime listens, filled from the runtime's own section, so an agent that
writes that into a config file of its own can do it while it configures. Where
its files live is derived from its name, so nobody writes that down.
Launches are built rather than exported, so a caller can show one before
anything runs.

<details>
<summary><b>Claude Code</b> — the environment it is given, the profile written for it, and why its search is denied</summary>

<br>

Configured entirely through the environment, so a launch is a set of variables
and a command line:

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

**Its profile lives in `~/.offgrid/claude-code/`**, separate from your own
`~/.claude`, which is what keeps your plugins, servers and hooks out of a
prefix you pay to prefill on every cold request. offgrid writes two files there
and then leaves them alone, since both are meant to be edited:

- `settings.json` — denies `WebSearch`, loads no plugins or project MCP
  servers. offgrid refuses to start if the deny has been removed.
- `CLAUDE.md` — tells the agent that search is unavailable and why, that
  `WebFetch` works when a URL is known, and to say what it could not look up
  rather than answer from memory.

**Why the search is denied:** `WebSearch` executes on Anthropic's servers. Sent
to a local model instead, there is nothing to run it — the model writes what it
imagines the results would look like, and the agent hands that back as a tool
result. Reproduced here: the "results" contained a fabricated header and the
boilerplate reminder from the real tool's output template. Exit code 0, no
error anywhere. `WebFetch` is genuinely local and stays enabled.

</details>

## The profile

`~/.offgrid/profile.yaml`, hand-editable:

```yaml
runtime:
  name: lmstudio
  host: 127.0.0.1:1234
agent:
  name: claude-code
model: qwen/qwen3.6-35b-a3b
```

| Key | Meaning |
|---|---|
| `runtime.name`, `agent.name` | which adapters to use. Both are required: a name offgrid has no adapter for is refused rather than recorded, and a section naming none is refused rather than guessed at |
| `runtime.host` | where the runtime listens. It sits under the runtime because that is the only thing it means anything to |
| `model` | what `run` uses when the command line names nothing |

One section per adapter, so an adapter with settings of its own has somewhere
to put them and the file says what belongs to what. The block above is the
whole of a minimal profile — `model` is the only key you can leave out.

A typo is an error rather than a shrug: `modle:` is reported, not read as "no
model named". So is a key the adapter a section names does not read — that one
is caught a moment later, when the command binds the adapter, and the message
names the section as well as the key.

A profile in the older flat shape — `host:` beside `runtime:` — is refused,
with the shape above in the message. There is no migration.

Nothing measured is kept here. `setup` reads the chip, the memory and the GPU
limit and prints them; every command that needs them reads them again, so a
raised limit counts from the moment it is raised.

## What offgrid does not do

- **Choose a model.** `recommend` names the published models this machine can
  hold. Which of them suits your work, and downloading it, stay yours.
- **Search the web.** See [Agents](#agents). A replacement is planned.
- **Enforce privacy.** Nothing stops you running a hosted agent on private
  work. Whoever wants a local model runs `offgrid`.
- **Fall back to a hosted model.** When the local model cannot do the job, that
  is the answer.
- **Translate between dialects.** A runtime and an agent that disagree are
  refused, with what to do about it.
- **Run anywhere else.** macOS on Apple Silicon, and one adapter each so far.

## Measured on an M1 Max

64GB:

| Model | Architecture | On disk | Decode |
|---|---|---|---|
| `qwen/qwen3.6-35b-a3b` | MoE, 3B active/token | 35G (8-bit) | 41.9 tok/s |
| `prism-ml/bonsai-27b` | dense 27B | 8.0G (2-bit) | 6.9 tok/s |

Decode tracks *active parameters*, not file size — 2-bit shrinks memory without
shrinking the matmul, so the 8GB model is six times slower than the 35GB one.
Pick by architecture.

Prefill runs at ~384 tok/s cold, and prefix caching is worth protecting: a
repeated 22k-token prefix dropped from 57.3s to 1.7s. That is why `run` says
out loud when a swap is about to throw one away. The runtime answers one
request at a time, so parallel subagents queue *and* evict each other's prefix
— fan-out is a net loss locally.

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
`.pre-commit-config.yaml` about what a check is.

The recipes are for working on offgrid. Using it is `offgrid setup`, `offgrid
recommend`, `offgrid doctor` and `offgrid run`, and nothing here wraps those.

The hooks run on every commit once `just install` has been run. CI runs the
same ones on Linux, where the single test that reads real hardware skips
itself.

**Live tests** are opt-in and deselected by default. They start a real agent
against a real model, so they let go of whatever the runtime is holding. They
default to `lfm2.5-1.2b-instruct-mlx` — small on purpose, since they prove the
plumbing rather than the answers — and `--smoke-model` points them elsewhere.

**The suite cannot reach your runtime, or the network, by accident.**
`tests/conftest.py` fails any test that calls a runtime's own tooling, and any
test that opens a socket, with `live` as the single exception. The published
table is parsed from a payload captured on 2026-08-07 and kept in
`tests/fixtures/`; the live check is what notices the page being redesigned.

When mutation-testing by hand, set `PYTHONDONTWRITEBYTECODE=1` — edits made
within the same second as a restore leave stale `.pyc` files, and the suite
then tests code that is no longer on disk.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
with the modules as scopes. What was decided and why lives in
`docs/decisions.md`; the domain language in `CONTEXT.md`.

## Layout

The modules, the layers, the two flows worth drawing, and where a second
runtime or agent attaches are in [`docs/architecture.md`](docs/architecture.md).

Dependencies point inwards: adapters know about the domain, the domain knows
nothing about adapters.

## Roadmap

- A way for local sessions to search the web
- A second runtime, and a second agent
- A model catalogue, and a verified private mode
