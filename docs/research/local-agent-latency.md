# Why a turn is slow, and which of the two owns it

Primary-source research, gathered 2026-08-21, into why Claude Code against a
model held by LM Studio on this machine is slow where OpenCode against the same
model is not. Sources are the vendors' own documentation, their repositories,
their release notes and their issue trackers, plus measurements taken on this
machine from files that were already there. Where a claim rests on reading
source, the repository and path are named. Where a thing could not be
established, it says so and says what would settle it. Inference is labelled as
inference. No benchmark was run, and nothing was loaded, unloaded or
reconfigured to write this.

## The answer

**It is the agent, and the mechanism is payload size rather than cache thrash.**
Claude Code's first request to LM Studio on this machine carries **24,213 to
26,916 input tokens** — measured from 278 distinct requests in transcripts Claude
Code itself wrote under `~/.offgrid/claude-code/projects`. OpenCode's system prompt
and always-loaded tool descriptions come to **23,601 bytes of source text**,
which at roughly four bytes per token is around 6,000 tokens. That is a factor
of four in prefill on the very first turn, before either agent has read a file,
and prefill is what a local runtime is slow at. The runtime is not blameless —
its prefix reuse is real but partial, covering 20,480 of about 27,000 tokens on
the second turn of every session recorded since 2026-08-18 — but the reuse
mechanism works, and a four-fold payload difference is present on turn one where
no cache exists for either agent.

Confidence: **medium-high on the payload gap, medium on it being the dominant
term.** The payload figures for Claude Code are measured on this machine; the
OpenCode figure is a byte count converted with an assumed ratio, and the two
agents were never timed against each other under controlled conditions. What
would raise it: sending one identical trivial prompt to each agent against the
same held model and reading `prompt_tokens` and time-to-first-token off LM
Studio's own server log. That is section 6's experiment 1, and it is an hour of
work that would move this from medium to settled.

Two things this research found that are worth more than the verdict. First, the
model held right now defaults to reasoning **on** — `GET /api/v1/models` reports
`"reasoning": {"allowed_options": ["off", "on"], "default": "on"}` for
`qwen/qwen3.6-35b-a3b` — and offgrid has no established way to turn that off
over `/v1/messages`, which is #40. Decode runs at tens of tokens a second here,
so every reasoning token is wall-clock the person watches. Second, it is being
served at a **262,144-token window** while the profile asks for 131,072, so
whatever is holding it was not `offgrid run`.

## What was read, and at which version

| Thing | Version | How that was determined |
| --- | --- | --- |
| Claude Code | `2.1.238` | `claude --version` on this machine. Docs read from `code.claude.com/docs/en/*`, which version-stamps behaviours inline |
| LM Studio server | reachable at `127.0.0.1:1234`, holding `qwen/qwen3.6-35b-a3b` | `GET /api/v0/models` and `GET /api/v1/models` |
| LM Studio MLX engine | `mlx-llm-mac-arm64-apple-metal-advsimd@1.11.0`, selected | `lms runtime ls` |
| LM Studio llama.cpp engine | `llama.cpp-mac-arm64-apple-metal-advsimd@2.28.2`, selected | `lms runtime ls`. Not in play: every text model here is MLX |
| OpenCode | `v1.18.20`, released 2026-08-21 | `gh api repos/sst/opencode/releases/latest`. Source read from `main` |
| llama.cpp `llama-server` | `tools/server/README.md` from `master` | `curl` of the raw file, 2,132 lines |
| mlx-lm | issue 980, open, filed 2026-03-11 | the issue page |
| offgrid | working tree at `3ab408c` | `git log` |

`docs/research/adapter-surfaces.md` is treated as a primary source for what each
runtime and agent exposes; this note does not repeat its findings, only builds
on them. Issue 19 on `pvardanis/offgrid` is likewise treated as primary for what
was measured on this machine.

## 1. What offgrid actually puts between them: nothing

`ClaudeCode.plan` in `src/offgrid/agents/claude_code/claude_code.py` builds an
environment and an argument list, and `ANTHROPIC_BASE_URL` is set to
`http://{runtime_host}` — the LM Studio address straight out of the profile.
`Launch` is handed to `launch.start`, which runs `claude` as a subprocess.
Nothing in `src/offgrid/` opens a socket during a run, translates a request
body, or sits in the request path. There is no proxy, no Anthropic-to-OpenAI
shim, and no place a `cache_control` block could be dropped.

The translation from Anthropic's Messages shape to whatever the MLX engine
wants happens **inside LM Studio**, on the `/v1/messages` endpoint it added in
0.4.1 with the stated purpose "Use Claude code models with LM Studio"
([api-changelog](https://github.com/lmstudio-ai/docs/blob/main/1_developer/api-changelog.md)).
That endpoint is LM Studio's newest surface and its most reported-against; the
four open regressions on it are listed in `docs/research/adapter-surfaces.md`
section 1.

What offgrid already sets, and what each is worth, from
`claude_code.py` and `launching.py`:

| Set | Why it is there | Latency effect |
| --- | --- | --- |
| `MAX_THINKING_TOKENS=0` | disable extended thinking | see section 5 — probably not doing what it looks like here |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192` | decode is tens of tokens a second | real: the documented default for an unrecognised model ID is `32000` |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | privacy, and no Anthropic round-trips | real but small: this traffic never went to the runtime |
| `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` | no 1M beta header | avoids a beta the runtime cannot honour |
| `--strict-mcp-config` with no `--mcp-config` | no MCP servers load | large, and it is the right call — see section 3 |
| `--exclude-dynamic-system-prompt-sections` | "volatile sections move into the first message, leaving the cached prefix identical between turns" | present since `d008fda`, 2026-08-04, so every measurement below already has it |
| `permissions.deny: ["WebSearch"]` | a hosted tool invents answers here | removes one tool definition from the prefix |
| all four of `ANTHROPIC_MODEL`, `..._OPUS_`, `..._SONNET_`, `..._HAIKU_MODEL` | one model answers everything | **this is what makes background calls expensive — section 3** |

`CLAUDE_CODE_MAX_OUTPUT_TOKENS` is documented as: "Claude Code defaults to
32000 for model IDs it doesn't recognize, such as gateway-specific names, and
lowers values above a model's cap to the cap"
([env-vars](https://code.claude.com/docs/en/env-vars)). `qwen/qwen3.6-35b-a3b`
is exactly an unrecognised name, so 8192 is a real four-fold reduction in the
worst case a turn can cost.

## 2. What this machine already measured

Claude Code writes a transcript per session, and every assistant message carries
the `usage` object the server returned. `~/.offgrid/claude-code/projects` holds
278 distinct requests across sessions from 2026-08-04 to 2026-08-21, all of them
launched by offgrid, all against LM Studio.

**Payload.** Against `qwen/qwen3.6-35b-a3b`, a session's first request carries
25,231, 25,254, 26,505, 26,867, 26,911 or 26,916 input tokens. Against
`qwen3-0.6b-mlx` and `lfm2.5-1.2b-instruct-mlx` — smaller models, same agent —
the first requests are 24,322 to 25,787. The spread is the working directory and
the project's own `CLAUDE.md`; the floor is Claude Code's system prompt plus its
tool definitions. `CONTEXT_FLOOR = 25_000` in `launching.py` was set to this
number and the transcripts say it was set correctly.

**Prefix reuse.** LM Studio reports `cache_read_input_tokens` on `/v1/messages`,
and every nonzero value recorded is an exact multiple of 256:

| Session start | Turn 1 in / cache read | Turn 2 in / cache read |
| --- | --- | --- |
| 2026-08-06 09:24 | 26,505 / 0 | 26,535 / **26,368** |
| 2026-08-06 09:53 | 25,254 / 0 | 25,429 / **25,088** |
| 2026-08-18 10:26 | 26,867 / 0 | 26,917 / **20,480** |
| 2026-08-20 15:03 | 26,911 / 0 | 27,020 / **20,480** |
| 2026-08-21 11:06 | 26,916 / 0 | 26,975 / **20,480** |

256 tokens is the block size LM Studio's own engineering blog gives for its
disk-backed KV cache: it computes "a key for each block of 256 tokens" and
"restores the longest available cached prefix for follow-up requests", the
boundary chosen as "small enough to avoid wasting much work on recomputation,
while large enough to keep the disk cache efficient"
([MLX engine blog](https://lmstudio.ai/blog/mlx-engine-agentic-workloads)). That
work shipped in MLX Engine v1.8.5 on 2026-06-05; the engine selected here is
**1.11.0**, so it is present.

Three things follow, and the third is the interesting one.

Turn one always misses. There is no cache for a 27,000-token prefix that has
never been sent, so every session pays a full cold prefill of the whole system
prompt and tool set before the first token of the answer. That is the cost
section 3 argues is the dominant one.

The mechanism works. On 2026-08-06 it covered 26,368 of a 26,535-token prefix —
99%, leaving 167 tokens to prefill.

**Since 2026-08-18 it covers only 20,480, three times in a row, on three
different days.** About 6,500 tokens are reprocessed on the second turn of every
session. Something in the request now differs between turn one and turn two at
roughly the 20,480-token mark, where on 2026-08-06 nothing differed until the
very end. What that something is **could not be established** — the transcripts
record token counts, not request bodies. Claude Code's own layer table puts the
system prompt and tool definitions first, project context (`CLAUDE.md`, auto
memory) second, and the conversation third
([prompt-caching](https://code.claude.com/docs/en/prompt-caching)), and a break
at 20,480 out of 27,000 falls plausibly at the end of the first layer — but that
is inference from an arithmetic coincidence and nothing more. Section 6's
experiment 2 settles it.

**Memory and the window.** LM Studio is holding the model at
`context_length: 262144` with `parallel: 4`, while `~/.offgrid/profile.yaml`
asks for `context_window: 131072`. `LMStudio.ensure_only` would have let go and
reloaded at 131,072, so this instance was not put there by `offgrid run`.
`lms load --estimate-only`, which does not load anything, reports
**26.64 GiB at 32,768, at 131,072 and at 262,144 alike**, with
`Confidence: LOW` — so that estimator prices weights and not the KV cache, and
cannot be used to argue what the window costs. What the window costs here is
therefore **unmeasured**, not zero.

## 3. The hypotheses, decided

### H1 — prefix cache thrash. **Refuted as the primary cause; partially confirmed as a secondary one.**

Claude Code's request is deliberately shaped for prefix reuse and offgrid
already takes the two extra steps that matter.

The design is documented: "Claude Code orders each request so content that
rarely changes between turns comes first", with the system prompt and tool
definitions first, project context second and the conversation third; and "A
change to the conversation layer leaves the system prompt and project context
cached"
([prompt-caching](https://code.claude.com/docs/en/prompt-caching)). The volatile
content H1 names is explicitly appended rather than injected early: file-change
notices arrive as a `<system-reminder>` at the end ("Editing a file Claude
previously read does not retroactively change the earlier read in history");
skills and commands "inject their instructions as user messages at the point of
invocation"; plan mode "append[s] their instructions as conversation messages,
so the cached prefix stays intact"; `CLAUDE.md` "read once at session start and
held in memory", so editing it mid-session does not invalidate anything.

The attribution block — the one thing Claude Code really does prepend — has been
stable per conversation since v2.1.181: "From Claude Code v2.1.181, the block is
stable for the lifetime of a conversation when requests route through a custom
base URL, so a gateway-side prompt cache keyed on the full request body works
without disabling it"
([llm-gateway-protocol](https://code.claude.com/docs/en/llm-gateway-protocol)).
This machine runs 2.1.238.

And the measurements in section 2 show reuse actually happening — 25,088 and
26,368 tokens of it — which a thrashing prefix would not produce.

What survives of H1 is the 20,480 plateau, worth about 6,500 reprocessed tokens
a turn, cause unknown. And one documented invalidation trap that offgrid has
already closed: behind a custom base URL, MCP tool definitions load **into** the
prefix rather than being deferred — "`ANTHROPIC_BASE_URL` ... When set to a
non-first-party host, MCP tool search is disabled by default"
([env-vars](https://code.claude.com/docs/en/env-vars)) — and then "any change to
them invalidates the cache", including "a stdio server's process exits, an HTTP
session expires, or a server reconnects automatically after a transient failure"
([prompt-caching](https://code.claude.com/docs/en/prompt-caching)). A person
running Claude Code by hand against LM Studio with MCP servers configured would
have a prefix that a flapping server voids at random. `--strict-mcp-config` with
no `--mcp-config` means offgrid's runs cannot hit this, and that is worth
knowing about the hand-run comparison rather than about offgrid.

### H2 — payload size. **Confirmed.**

Claude Code: 24,213–26,916 input tokens on a first request, measured (section
2).

OpenCode: the system prompt selected for a model whose ID contains none of
`gpt`, `gemini`, `claude`, `trinity`, `kimi` or `muse` is `default.txt`
(`packages/opencode/src/session/system.ts`, the `provider` function), which is
**8,528 bytes**. Its tool descriptions are separate `.txt` files in
`packages/opencode/src/tool/`, totalling **15,073 bytes** across all fifteen —
and three of those (`plan-enter`, `plan-exit`, `plan-mode`) are mode-specific, so
15,073 is an upper bound on what is always loaded. Sizes from
`gh api repos/sst/opencode/contents/...`. Total 23,601 bytes.

**The token figure is an estimate, not a measurement.** At roughly four bytes
per token that is about 5,900 tokens, plus JSON schema overhead for the tool
parameters and whatever `AGENTS.md` the project carries. Call it 6,000–9,000
against Claude Code's measured 25,000–27,000. Section 6's experiment 1 replaces
the estimate with a number.

The reason this dominates is that prefill is the expensive half locally. Issue
19 records a 33,880-token cold prefill at 100.9 seconds on this machine. That
figure was measured on a different pairing and cannot be transferred as a rate,
but the shape of it is the point: a cold prefill of tens of thousands of tokens
on this hardware is measured in tens of seconds, and Claude Code pays four times
as many of those tokens as OpenCode before either says a word.

### H3 — extra round-trips. **Refuted for the documented background calls; confirmed for one that offgrid causes itself.**

The documented background traffic is small. "Claude Code uses tokens for some
background functionality even when idle: **Conversation summarization**:
Background jobs that summarize previous conversations for the `claude --resume`
feature. **Command processing**: Some commands like `/usage` may generate
requests to check status. These background processes consume a small amount of
tokens (typically under \$0.04 per session)"
([costs](https://code.claude.com/docs/en/costs)). Everything else that leaves the
machine — telemetry, error reporting, release notes, model-discovery refreshes,
the fast-mode availability check — goes to Anthropic and not to the runtime, and
offgrid already sets `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, documented as
covering exactly that list ([env-vars](https://code.claude.com/docs/en/env-vars)).

What is confirmed is narrower and is offgrid's own doing.
`ANTHROPIC_DEFAULT_HAIKU_MODEL` is documented as "Model ID that the `haiku`
alias resolves to, **also used for background functionality**"
([env-vars](https://code.claude.com/docs/en/env-vars)), and `claude_code.py`
points it at the same 35B model as everything else. There is no smaller model to
point it at without a second model in memory, which one pool of memory forbids —
so this is a consequence of the one-model rule rather than a mistake. It means
any background call that would have been cheap is a full 35B turn, serialised
behind whatever the person is waiting for.

Two documented single-request costs are worth naming. Token counting: LM Studio
does not serve `/v1/messages/count_tokens` (`adapter-surfaces.md` section 1),
and the symptom is "Claude Code falls back to counting context usage through the
messages endpoint", the remediation being "Expose the endpoint so token counts
don't consume inference requests"
([llm-gateway-protocol](https://code.claude.com/docs/en/llm-gateway-protocol)).
That is `Capabilities.counts_tokens=False` in `runtimes/lmstudio/lmstudio.py`,
already recorded, and #43 is where a caller for it would go. And session titles:
`CLAUDE_CODE_DISABLE_TERMINAL_TITLE` "also skips the background small/fast-model
request that generates the session title" — but only "In Agent SDK and
`claude -p` sessions", so it buys nothing for an interactive run.

Subagents are the one place where the round-trip count really does multiply:
"A subagent starts its own conversation with its own system prompt and tool set
... Its first request doesn't read the parent's cache"
([prompt-caching](https://code.claude.com/docs/en/prompt-caching)). Every
subagent is another cold 25,000-token prefill. `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`
defaults to 10 and `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` to 20, and a
single-model local runtime serialises all of them.

### H4 — translation-layer cost. **Refuted for offgrid; unresolved for LM Studio's own `/v1/messages`.**

offgrid adds no layer at all (section 1). Whether LM Studio's Anthropic surface
costs more than its OpenAI one — for the same prompt, on the same engine — could
not be established. Neither its OpenAI-compat page nor its REST page says
anything about prompt caching or per-dialect behaviour, and LM Studio is closed
source, so there is nothing to read. The 256-aligned cache reads in section 2
prove the engine's block cache is reachable through `/v1/messages`; whether it
is reachable equally well through `/v1/chat/completions`, which is the path
OpenCode uses, is exactly what the comparison would need and is experiment 1.

One asymmetry is documented and cuts the other way from what H4 assumes. Behind
`ANTHROPIC_BASE_URL`, Claude Code "sends the full set" of Anthropic capabilities
"even if your gateway forwards to an Amazon Bedrock or Google Cloud's Agent
Platform upstream", including `thinking: {"type": "adaptive"}` which it sends
for "model names it doesn't recognize, such as gateway aliases"
([llm-gateway-protocol](https://code.claude.com/docs/en/llm-gateway-protocol)).
OpenCode against LM Studio uses `@ai-sdk/openai-compatible` (`adapter-surfaces.md`
section 5) and sends a plain chat-completions body. So the Anthropic path
carries fields the OpenAI path does not, and how LM Studio handles them is
unread.

### H5 — server config. **Confirmed as a real difference, with two specific settings.**

The model is held at **262,144** tokens where the profile asks for 131,072
(section 2), and with **`parallel: 4`**. `lms load --parallel` is documented as
"Maximum number of predictions the model can run at a given time. **The speed of
each individual prediction may decrease with concurrency**, but each prediction
will start faster and higher total throughput can be achieved"
(`lms load --help`). One person at one terminal gets none of the throughput and
pays whatever the per-prediction cost is.

offgrid cannot reach either setting cleanly. `parallel` is **not** among the
documented fields of `POST /api/v1/models/load` — that body carries `model`,
`context_length`, `eval_batch_size`, `flash_attention`, `num_experts`,
`offload_kv_cache_to_gpu` and `echo_load_config` and nothing else
([load](https://lmstudio.ai/docs/developer/rest/load)) — and offgrid loads over
HTTP rather than through `lms`, by design (`holding.py`). `flash_attention` and
`offload_kv_cache_to_gpu` are documented, and every text model on this machine
is MLX rather than GGUF (`compatibility_type: "mlx"` on all five LLMs in
`/api/v0/models`; `lms runtime ls` selects both an MLX and a llama.cpp engine).
Whether those two fields apply to an MLX load **could not be established from
LM Studio's own documentation**; the only signal found is a search-result
summary of the REST page describing each as present only for llama.cpp-engine
loads, which is low-trust corroboration rather than evidence. The instance's
reported config carries neither key, only `context_length`, `parallel` and
`reasoning_budget_message`, which is consistent with them not applying.

Whether a smaller window would be faster here is **unmeasured**. The context
length is settled at load and nothing afterwards changes it (`holding.py`), the
window has no effect on `lms load --estimate-only`'s figure, and no LM Studio
document found says how MLX allocates the KV cache against it.

## 4. The levers

| Change | Where | Expected effect | Source |
| --- | --- | --- | --- |
| Load at the window the profile asks for, not 262,144 | `offgrid run` — it already does this; the current instance was not loaded by it | frees whatever the extra 128k of KV allocation costs, which is unmeasured | `ensure_only` in `runtimes/lmstudio/lmstudio.py`; `/api/v1/models` shows the mismatch |
| `parallel: 1` instead of 4 | LM Studio only, via `lms load --parallel 1` — unreachable from offgrid | "the speed of each individual prediction may decrease with concurrency" | `lms load --help`; the field is absent from the [documented REST load body](https://lmstudio.ai/docs/developer/rest/load) |
| Turn the model's reasoning default off | LM Studio's per-model setting; `allowed_options: ["off","on"]`, `default: "on"` | decode is tens of tokens a second, so every reasoning token is wall-clock. Likely the single largest per-turn win | `GET /api/v1/models`. **Whether the app setting binds `/v1/messages` is unverified** — `adapter-surfaces.md` open question 1 |
| `CLAUDE_CODE_DISABLE_THINKING=1` | Claude Code env; offgrid `plan()` | "omit the `thinking` parameter from API requests entirely ... a compatibility option for proxies and gateways". More reliable here than `MAX_THINKING_TOKENS=0`, whose documented `0` behaviour splits between the Anthropic API and "third-party providers" and does not say which branch a plain `ANTHROPIC_BASE_URL` gateway takes | [env-vars](https://code.claude.com/docs/en/env-vars) |
| `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` | Claude Code env | "strip Anthropic-specific `anthropic-beta` request headers and beta tool-schema fields (such as `defer_loading` and `eager_input_streaming`)". Smaller tool schemas, and no `400` from fields LM Studio does not know | [env-vars](https://code.claude.com/docs/en/env-vars) |
| `DISABLE_INTERLEAVED_THINKING=1` | Claude Code env | "prevent sending the interleaved-thinking beta header. Useful when your LLM gateway or provider does not support interleaved thinking" | [env-vars](https://code.claude.com/docs/en/env-vars) |
| `API_FORCE_IDLE_TIMEOUT=0` | Claude Code env | not speed — survival. "Override the 5-minute body idle timeout ... for example when a slow gateway or **local model** pauses longer than 5 minutes between chunks". This is #45's answer for the body timeout specifically; the stream watchdogs "run independently of it" | [env-vars](https://code.claude.com/docs/en/env-vars) |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` set to the served window | Claude Code env | stops Claude Code compacting against a window it guessed for an unrecognised model ID. A wrong guess means either premature compaction or a truncated prefix, and both void the cache | [env-vars](https://code.claude.com/docs/en/env-vars); pairs with `compacting.py`'s existing 100,000 floor |
| Keep `--strict-mcp-config` and add no MCP servers | offgrid already does | behind a custom base URL tool search is off, so MCP tools sit **in** the cached prefix and a server reconnecting voids it | [env-vars](https://code.claude.com/docs/en/env-vars) on `ANTHROPIC_BASE_URL`; [prompt-caching](https://code.claude.com/docs/en/prompt-caching) |
| Deny more hosted or unused tools | offgrid `configuring.py` `SLIM_SETTINGS` | "Adding a bare tool name ... removes that tool from Claude's context entirely". Each denied tool is schema out of a 25,000-token prefix, permanently | [prompt-caching](https://code.claude.com/docs/en/prompt-caching) |
| `/clear` between tasks rather than letting the session grow | the person, and `CLAUDE.md` guidance offgrid writes | every turn re-sends the whole conversation; only the cached part is cheap, and section 2 says about 6,500 tokens of it currently is not | [costs](https://code.claude.com/docs/en/costs) |
| Do **not** set `ENABLE_TOOL_SEARCH=true` | — | "requests fail on proxies that don't support `tool_reference`" | [env-vars](https://code.claude.com/docs/en/env-vars) |

The tool-denial lever is the one with the most headroom and the least risk, and
it is the only one in the table that attacks H2 directly. Claude Code's built-in
tool definitions are the bulk of a 25,000-token floor that is paid cold on every
session start and on every subagent spawn. Nothing measured here says how much
each tool costs, which is experiment 3.

## 5. What offgrid could add, and what each costs

**Config-only changes to the Claude Code adapter. Do this first.** Three or four
environment variables in `plan()` and possibly more entries in `SLIM_SETTINGS`.
It is one commit, it touches one adapter, it needs no new seam, and the agent
conformance suite already states what `plan` must answer with. `CLAUDE_CODE_DISABLE_THINKING`
and `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` are the two with the clearest
documented effect. Cost: near zero. Risk: `MAX_THINKING_TOKENS=0` may already be
doing the job, in which case one of them is redundant — which experiment 4
settles before the commit rather than after.

**An OpenCode agent adapter. Do this second, and only once there is a
measurement.** `docs/architecture.md` already designs for it: the agent seam
exists, `AgentConfig` carries `runtime_host` "precisely so that an agent writing
it into a file of its own has it before `configure` runs", and
`tests/test_agent_conformance.py` states the twelve things any agent owes. The
work is a `configure` that writes a `provider.<id>.options.baseURL` block, a
`plan` that names the model, a `context_floor`, a `read_hosted_tools` that reads
OpenCode's own configuration, and one stand-in in `tests/agents_under_test.py`.
That is a real adapter, several hundred lines with tests, and it would be the
second agent — which is a scope decision, not a performance fix. `CONTEXT.md`
already names OpenCode as the candidate, so it is not out of scope, but v0.1's
"one runtime, one agent" says it is not this week's work either. What makes it
tempting is that if experiment 1 confirms the four-fold payload gap, an OpenCode
adapter is the fix rather than a workaround: no amount of denying tools gets
Claude Code down to 6,000 tokens.

**A llama.cpp or MLX runtime adapter. Do this last, or not at all.** It is the
wrong lever for this problem. `llama-server` has `--cache-prompt` "enabled by
default" and `--cache-reuse N`, "min chunk size to attempt reusing from the
cache via KV shifting", **default 0, disabled**
([server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)),
plus `--ctx-checkpoints` and slot save/restore endpoints — a richer and more
inspectable cache surface than LM Studio's. But it runs GGUF, every text model
on this machine is MLX safetensors, and `adapter-surfaces.md` section 2 records
that a single-model `llama-server` cannot be told to let go at all, which
`ensure_only` requires. Its README also hedges the Anthropic surface: "While no
strong claims of compatibility with the Anthropic API spec are made, in our
experience it suffices to support many apps", and tool use "requires `--jinja`
flag". Cost: a full runtime adapter plus a model re-download in another format,
to fix a problem section 2 says is not primarily the runtime's.

There is one runtime-side risk worth watching that no adapter fixes. mlx-lm
issue [980](https://github.com/ml-explore/mlx-lm/issues/980), open since
2026-03-11, states: "Prompt prefix caching only works for pure full-attention
models. Any model using sliding window attention, Mamba/SSM layers, or mixed
attention types silently falls back to full prompt recomputation on every
request", and names **Qwen 3.5 (all sizes)** among the affected. The model held
here reports `"arch": "qwen3_5_moe"`. LM Studio's blog says its own engine work
"specifically address[es] models using cache-reduction techniques: Qwen 3.5
(hybrid architecture) and Gemma 4", and the section-2 measurements show reuse
actually happening on this model — so LM Studio appears to be ahead of upstream
mlx-lm here. But the partial reuse in section 2 is consistent with an
architecture the block cache handles imperfectly, and that is a second candidate
explanation for the 20,480 plateau alongside the layer-boundary one.

**oMLX reopens the runtime-adapter option this section closed — for one feature
this machine cannot use.** The two grounds above dismiss a runtime adapter: GGUF
format, and mlx-lm's issue 980. oMLX escapes both. It is MLX-native, so there is
no re-download, and it ships its own block-aware prefix cache with explicit
rotating and hybrid handling for Qwen3.5 rather than mlx-lm's, so 980 is
upstream's problem and not necessarily its (`omlx/cache/prefix_cache.py`,
`omlx/custom_kernels/qwen35_prefill/`). It also serves `/v1/messages` with a
real reasoning-off knob and a working `count_tokens` — the two gaps section 3
and open question 5 name in LM Studio. But the one feature that would actually
cut the cold prefill — SpecPrefill's sparse prefill, which scores tokens with a
draft model and prefills only the important ones — loads that draft as a second
set of weights beside the target (`omlx/model_settings.py:255` is a path to a
separate model; the validation pairs are a 4B draft against a 27B or 35B
target), and its load bypasses the engine pool's memory admission, so enabling
it on one pool of memory courts the crash rather than a caught error. The static
system and tool prefix reuse that would attack Claude Code's 25,000-token floor
without a draft is single-model by its own signature but wired to run only inside
that same draft-bearing branch, so it is unreachable here without forking oMLX.
What is left single-model is incremental over LM Studio, not the 30x the README
reports for GLM-5.2, which does not transfer to `qwen3_5_moe`. The full read is
`docs/research/omlx-runtime.md`; the one measurement that would decide a swap —
single-model Qwen3.5 cold prefill on oMLX against LM Studio's MLX engine, one
model at a time — is not taken.

**Recommendation: config-only first, then experiment 1, then decide about
OpenCode on the number it gives.** Building an agent adapter before measuring
would be building the expensive thing on an estimate.

## 6. What could not be determined

1. **How many tokens OpenCode actually sends.** Section 3's figure is a byte
   count with an assumed bytes-per-token ratio and no accounting for JSON schema
   overhead. *Experiment 1:* with one model held and `parallel: 1`, send the same
   trivial prompt ("say hello and stop") through Claude Code and through
   OpenCode, and read `prompt_tokens` and time-to-first-token off LM Studio's
   server log for each. `~/.lmstudio/.internal/http-server-config.json` already
   has `verbose: true` and `fileLoggingMode: "succinct"`, so the log is being
   written. This is the one experiment that decides the whole question, and it
   costs two prompts.

2. **What changed at 20,480 tokens between 2026-08-06 and 2026-08-18.** Three
   sessions on three days all plateau there; the 2026-08-06 sessions did not.
   *Experiment 2:* run Claude Code against LM Studio through a logging reverse
   proxy on a spare port, capture two consecutive request bodies, and diff them.
   The diff's byte offset against a tokeniser says which layer moved. A proxy is
   the only way — the transcripts record counts, not bodies, and LM Studio's log
   does not echo the prompt unless `logSensitiveData` is on and `logIncomingTokens`
   is set, which it is not.

3. **What each of Claude Code's built-in tools costs in the prefix.** Denying
   tools is the highest-headroom lever in section 4 and nothing measured says
   how much each one buys. *Experiment 3:* add one bare tool name at a time to
   `permissions.deny`, start a session, read the first request's `input_tokens`
   from the transcript. One session per tool, no proxy needed.

4. **Whether `MAX_THINKING_TOKENS=0` omits the `thinking` field behind a plain
   `ANTHROPIC_BASE_URL` gateway.** The documentation splits its behaviour
   between "the Anthropic API" and "third-party providers" and never says which
   a custom base URL is. *Experiment 4:* the proxy from experiment 2, reading
   whether the body carries `thinking` with the variable set and unset.

5. **Whether LM Studio's per-model reasoning default binds `/v1/messages`.**
   `GET /api/v1/models` publishes `reasoning.default: "on"` for this model, and
   `adapter-surfaces.md` open question 1 already records that LM Studio
   documents no reasoning knob on its Anthropic surface. *Experiment 5:* issue
   2195's method — ask the model to echo its own system message with the app
   setting `on` and then `off`, and check whether `prompt_tokens` and the
   content blocks differ. This is #40, and the answer changes what offgrid can
   promise about a turn's cost.

6. **What the served context window costs in memory and in prefill on MLX.**
   `lms load --estimate-only` reports the same 26.64 GiB at 32,768 and at
   262,144, so it prices weights only. *Experiment 6:* load the model at 32,768,
   record the LM Studio process's resident memory and one cold prefill's
   time-to-first-token; let go, load at 262,144, repeat. Two loads, tens of
   seconds each, and it would tell `sizing/fit.py` something it currently
   assumes.

7. **Whether LM Studio's block cache serves `/v1/chat/completions` as well as it
   serves `/v1/messages`.** Nothing in its documentation mentions prompt caching
   on either path; the 256-aligned reads in section 2 establish it only for the
   Anthropic one. Experiment 1 answers this as a side effect, since OpenCode
   uses the OpenAI path.

8. **Whether `parallel: 4` costs a single caller anything measurable.**
   `lms load --help` says per-prediction speed "may decrease with concurrency"
   and gives no figure. *Experiment 7:* load at `--parallel 1` and at
   `--parallel 4`, same window, same prompt, compare time-to-first-token. Note
   that offgrid could not act on the answer today without reaching for `lms`,
   which `holding.py` deliberately does not do.
