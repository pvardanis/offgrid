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

## What this note got wrong

Everything below was written before the comparison was run under control. It
was: two agents, one warm LM Studio instance, same prompt, same empty
directory. **The verdict below is falsified by it and is kept only as a record
of the reasoning.**

| | cold cache | warm cache |
| --- | --- | --- |
| Claude Code | 60.4s | **2.02s** |
| OpenCode | 52.4s | 13.4s |

Claude Code is roughly **ten times faster than OpenCode once the prefix is
cached**, despite sending 1.9× the tokens — not four times, either: OpenCode
sends 10,596, not the ~6,000 estimated below from a byte count. Cold, the two
are within 15% of each other, which is about what the payload difference
predicts and nothing like what was felt.

So the payload gap is real as a token count and close to irrelevant as a
latency explanation. What was actually being felt is neither agent and neither
payload:

**`offgrid run` reloaded the model on every run, and a reload empties LM
Studio's prompt-prefix cache.** LM Studio silently discards the context length
a load asks for on some models — upstream
[lmstudio-ai/lmstudio-bug-tracker#2250](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2250),
ours [#136](https://github.com/pvardanis/offgrid/issues/136) — so offgrid asked
for 131,072, read back 262,144, called that a mismatch and reloaded to close a
gap that could not close. Every run. So every Claude Code session started in
the cold column, while the hand-run OpenCode sessions, which reloaded nothing,
stayed in the warm one. That is the 60.4s against 13.4s, and it is offgrid's
doing rather than either tool's.

Two smaller corrections while the reasoning below stands uncorrected:

- **Reasoning is not a Claude Code cost here.** `/v1/messages` produces no
  reasoning tokens for this model, with or without a `thinking` field.
  `/v1/chat/completions` spends 149 of 150 on reasoning for "say hello and
  stop". So it is a cost on OpenCode's path, not Claude Code's — the reverse of
  what the levers table below assumes, and it makes the handicap OpenCode
  overcame larger still.
- **`chat_template_kwargs` is ignored** by LM Studio, so there is no
  per-request reasoning knob on either dialect.

What remains sound below: the measured payload figures, the prefix-cache
mechanics, the adapter surfaces, and the reasoning about what would settle each
open question. What does not: the verdict, and the levers table's ranking.

## The answer, as it read before the control run

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
term, and lower than both on the payload gap being what was actually felt** —
the slow runs were measured against a server in a state `offgrid run` would not
have produced, and nothing records what the OpenCode comparison ran against.
That is open item 0, and it is the first thing to fix.

The payload figures for Claude Code are measured on this machine; the
OpenCode figure is a byte count converted with an assumed ratio, and the two
agents were never timed against each other under controlled conditions. What
would raise it: sending one identical trivial prompt to each agent against the
same held model and reading `prompt_tokens` and time-to-first-token off LM
Studio's own server log. That is section 6's experiment 1, and it is an hour of
work that would move this from medium to settled.

Two things this research found that are worth more than the verdict, and the
first of them is a correction to what this note said in its earlier form. The
model advertises reasoning **on** by default, and on the path Claude Code
actually uses **it does not reason at all**: four requests against the live
server on 2026-08-21 (section 3a) put `/v1/chat/completions` at 149 reasoning
tokens for "say hello and stop" and `/v1/messages` at three output tokens and
no reasoning. So the lever this note previously ranked first is not a lever on
Claude Code — it is one on the OpenAI path, which is OpenCode's. That cuts the
other way from the obvious reading, and section 3's H2 gets stronger for it.
Second, the model is served at a **262,144-token window** while the profile asks
for 131,072, so whatever is holding it was not `offgrid run`.

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
| oMLX | source read at `0436bdf` on `main`, `__version__ = "0.6.3rc2"` | shallow `git clone` of `https://github.com/jundot/omlx`, then `omlx/_version.py`. `adapter-surfaces.md` read it at `2450a53c`/`0.5.8.dev3`; every claim of its that section 5 leans on was re-checked at `0436bdf`, and the line numbers below are that revision's |
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
| `MAX_THINKING_TOKENS=0` | disable extended thinking | none, on this pairing: section 3a measures `/v1/messages` producing no reasoning for this model with or without a `thinking` field |
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
reloaded at 131,072, so this instance was not put there by `offgrid run`. Both
halves of that were re-read directly off the running server and the profile on
2026-08-21 and are confirmed, as is `capabilities.reasoning` of
`{"allowed_options": ["off", "on"], "default": "on"}` on
`qwen/qwen3.6-35b-a3b` and on `qwen/qwen3.6-27b` alike. What that advertised
default actually does depends on the dialect, which is section 3a.
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

**Section 3a makes this argument stronger, by removing a rival explanation and
handing OpenCode a handicap.** OpenCode reaches LM Studio through
`@ai-sdk/openai-compatible` (`adapter-surfaces.md` section 5), which is
`/v1/chat/completions` — the path that *does* reason, and reasons hard: 149
tokens to say hello. Claude Code's path produces none. So the faster agent was
the one paying reasoning tokens the slower agent never paid, and it still felt
faster. Whatever accounts for the difference has to overcome that handicap as
well, which leaves less room for anything other than the prefill payload.

It also removes the tidiest alternative story. Before these measurements the
obvious rival explanation was "Claude Code is slow because the model reasons at
it"; on this model, over `/v1/messages`, it does not. Two caveats keep this from
being conclusive: 3a used one trivial prompt with no tools, and nobody recorded
what the OpenCode hand-run was served by — open items 11 and 0.

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

## 3a. Reasoning is a property of the dialect, not of the model

Four requests against the live server on 2026-08-21, same held instance section
2 describes, same prompt `"say hello and stop"`, `max_tokens: 150`,
non-streaming, **no tools in the request**:

| Request | in | out | reasoning | content |
| --- | --- | --- | --- | --- |
| `POST /v1/chat/completions` | 14 | 149 | **149** | `''`, `finish_reason: "length"` |
| the same, plus `"chat_template_kwargs": {"enable_thinking": false}` | 14 | 149 | **149** | `''` — byte-identical, the field is ignored |
| `POST /v1/messages` | 16 | 3 | **0** | `"Hello!"`, `stop_reason: "end_turn"` |
| the same, plus `"thinking": {"type": "disabled"}` | 16 | 3 | **0** | `"Hello!"` — no different from the control |

The OpenAI path burned its entire 150-token budget reasoning and returned an
empty string. The Anthropic path answered in three tokens. Same server, same
weights, same instant.

The reasoning figure is reported directly on the OpenAI path, as
`completion_tokens_details.reasoning_tokens: 149`. The Anthropic usage object
carries no reasoning field at all — it is
`{"input_tokens": 16, "output_tokens": 3, "cache_read_input_tokens": 0}` — so
the zero there is read off `output_tokens: 3`, which is the whole of `"Hello!"`
and leaves no room for anything discarded.

**Two things follow, and both change what this note recommended.**

*There is no per-request reasoning knob on LM Studio at all.*
`chat_template_kwargs` is ignored on `/v1/chat/completions`, and
`thinking: {"type": "disabled"}` changes nothing on `/v1/messages` because
nothing there was reasoning to begin with. That is a harder fact for #40 than
`adapter-surfaces.md` had: not "two runtimes spell it differently" but "this
runtime does not accept it in either dialect".

*Where the toggle actually lives is the model file.* It is a custom field in
`~/.lmstudio/hub/models/qwen/qwen3.6-35b-a3b/model.yaml`, not a server option
and not a load option — `lms load --help` carries no reasoning flag:

```yaml
customFields:
  - key: enableThinking
    displayName: Enable Thinking
    description: Controls whether the model will think before replying
    type: boolean
    defaultValue: true
    effects:
      - type: setJinjaVariable
        variable: enable_thinking
```

and the chat template consumes it as

```jinja
{%- if enable_thinking is defined and enable_thinking is false %}
{{- '<think>\n\n</think>\n\n' }}{%- else %}{{- '<think>\n' }}{%- endif %}
```

Read that template against the measurements and it explains the OpenAI row
exactly: `defaultValue: true` leaves the else branch, which emits a bare
`<think>\n` and hands the model an open reasoning block to fill — which is what
149 tokens of nothing is.

**Why the Anthropic path does not reason could not be established, and one
explanation is ruled out.** It is not stripping: a strip would still have cost
the generation, and `output_tokens: 3` says the tokens were never produced. The
template's false branch pre-closes the block with `<think>\n\n</think>\n\n`,
leaving the model nothing to fill, so the behaviour is what
`enable_thinking = false` looks like — which means LM Studio's `/v1/messages`
implementation is setting it, or building the prompt by another route entirely.
Nothing in LM Studio's documentation mentions either, and it is closed source,
so there is nothing to read. Weak corroboration, marked as inference: the
Anthropic request counted **two more input tokens** for the same prompt, and the
false branch is the longer string — but the two dialects also encode
system and message content differently, so the two tokens cannot be attributed
cleanly and nothing here rests on them.

**Every number in this section carries one caveat.** One trivial prompt, no
tools in the request, non-streaming. The chat template's tool branch is a
different path, and reasoning behaviour with Claude Code's actual tool schemas
present is untested — open item 11.

## 4. The levers

| Change | Where | Expected effect | Source |
| --- | --- | --- | --- |
| Load at the window the profile asks for, not 262,144 | `offgrid run` — it already does this; the current instance was not loaded by it | frees whatever the extra 128k of KV allocation costs, which is unmeasured | `ensure_only` in `runtimes/lmstudio/lmstudio.py`; `/api/v1/models` shows the mismatch |
| `parallel: 1` instead of 4 | LM Studio only, via `lms load --parallel 1` — unreachable from offgrid | "the speed of each individual prediction may decrease with concurrency" | `lms load --help`; the field is absent from the [documented REST load body](https://lmstudio.ai/docs/developer/rest/load) |
| Set `enableThinking` false | the model's own `model.yaml` `customFields`, which is the only place it lives — not a server option, not a load option, and not a request field in either dialect | **On the OpenAI path, large: 149 of 150 tokens went to reasoning for a two-word answer. On the Anthropic path, nothing — that path does not reason for this model.** So this is a lever on OpenCode and not on Claude Code, which is the reverse of what this note claimed before the measurements | section 3a; `lms load --help` has no reasoning flag |
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

Section 3a demoted what used to head this table. With the Anthropic path not
reasoning for this model, the two thinking variables are compatibility measures
rather than speed ones: `CLAUDE_CODE_DISABLE_THINKING=1` keeps a field LM Studio
has no documented handling for out of the body, which is worth doing and is not
worth expecting a speed-up from. That leaves tool denial as the only large
agent-side lever, and it is a payload lever — which is section 3's point.

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

**A llama.cpp runtime adapter. No.** `llama-server` has `--cache-prompt`
"enabled by default" and `--cache-reuse N`, "min chunk size to attempt reusing
from the cache via KV shifting", **default 0, disabled**
([server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)),
plus `--ctx-checkpoints` and slot save/restore endpoints — a richer and more
inspectable cache surface than LM Studio's. But it runs GGUF, every text model
on this machine is MLX safetensors, and `adapter-surfaces.md` section 2 records
that a single-model `llama-server` cannot be told to let go at all, which
`ensure_only` requires. Its README also hedges the Anthropic surface: "While no
strong claims of compatibility with the Anthropic API spec are made, in our
experience it suffices to support many apps", and tool use "requires `--jinja`
flag". Cost: a full runtime adapter plus a model re-download in another format.

**An oMLX runtime adapter. A real candidate, and the format objection above does
not apply to it — but it loses on this note's own question.** oMLX serves MLX
safetensors, so this machine already has the weights; issue 19 records that
symlinking into `~/.lmstudio/models/<publisher>/<model>` was enough to serve the
very model held today. It is the candidate `CONTEXT.md` and issue 19 weigh, and
`docs/architecture.md` already designs around one of its quirks.

*What it buys that LM Studio cannot.* Three things, and they land on three
findings above rather than on generic merit.

Reasoning can be turned off **on the Anthropic path**. `omlx/server.py:5517-5520`
maps Anthropic's own `thinking` config into the chat template — `thinking_type`
of `"enabled"` or `"adaptive"` sets `enable_thinking` true, `"disabled"` sets it
false — and `chat_template_kwargs` is a declared field on the Anthropic request
model itself (`omlx/api/anthropic_models.py`). Section 4 calls turning reasoning
off "likely the single largest per-turn win" and section 4 also records that on
LM Studio there is no established way to reach it over `/v1/messages`. **This
does not close #40; it moves it somewhere it can be answered.** Two reasons it
is not closed. Whether Claude Code sends `thinking` disabled at all behind a
plain `ANTHROPIC_BASE_URL` is open item 4 and is unresolved either way. And
issue 19 *observed* oMLX returning reasoning as visible text in `content` over
`/v1/messages` on this machine — "Thinking Process: 1. Analyze the request..." —
which is the failure the knob exists to prevent.

Section 3a sharpens the contrast rather than softening it. LM Studio honours
**neither** knob: `chat_template_kwargs` is ignored on `/v1/chat/completions`
and `thinking: {"type": "disabled"}` is a no-op on `/v1/messages`, so its only
reasoning control is a field in the model's own `model.yaml`. oMLX accepts
`chat_template_kwargs` on all three dialects and Anthropic's `thinking` config
on `/v1/messages` (`adapter-surfaces.md` section 3). That is a genuine
capability difference and it belongs in the comparison — it does not change the
ranking, because oMLX still loses prefill, and because on this model the
Anthropic path has no reasoning to suppress.

What genuinely changes is where the lever sits. `docs/architecture.md`'s "What
is not decided" states the constraint exactly: "offgrid never sends a request,
so it has no per-request knob; its levers are the agent's environment and
whatever server-side default a runtime takes." oMLX gives a server-side default
that can be **pinned**: `ModelSettings.forced_ct_kwargs` is "Keys that cannot be
overridden by API requests" (`omlx/model_settings.py:199`), and the merge order
is documented as "1. `settings.chat_template_kwargs` 2. the dedicated
`enable_thinking` / `preserve_thinking` toggles 3. per-request kwargs, except
keys listed in `forced_ct_kwargs`" (`omlx/model_settings.py:1374-1378`). So a
runtime-side setting can win over whatever the agent sends, which is a smaller
and more tractable problem than guessing the agent's spelling.

It serves `POST /v1/messages/count_tokens` (`omlx/server.py:5843`). Section 3
records that LM Studio's absence of it makes Claude Code "fall back to counting
context usage through the messages endpoint", which locally means spending the
one model being held. **What that is worth per turn could not be quantified:**
no primary source found states how often Claude Code counts context, only that
the fallback "consume[s] inference requests"
([llm-gateway-protocol](https://code.claude.com/docs/en/llm-gateway-protocol)).

*The cache_control question, which is the sharp one, and it lands against the
easy reading.* `adapter-surfaces.md` records that oMLX reads Anthropic cache
markers and that this changes what `message_start` reports. Reporting a cache
read is not reusing a prefix, and **oMLX's own source says so in as many
words**. `request_has_cache_control` at `omlx/api/anthropic_utils.py:32-42` is
documented as a reporting gate and nothing else:

> Anthropic's three input-side usage fields (`input_tokens`,
> `cache_creation_input_tokens`, `cache_read_input_tokens`) form a *disjoint*
> partition of the prompt only when the client explicitly marks a region with
> `cache_control`. Without that signal the cache fields must stay at 0 and
> `input_tokens` carries the whole prompt count — **independent of whether the
> oMLX engine happens to run automatic prefix caching internally.**

So in oMLX, reporting and reuse are separate subsystems. The consequence for
this note is worth stating plainly: on oMLX the transcript evidence of section 2
would be **unavailable** unless Claude Code marks blocks with `cache_control`,
and a zero there would mean nothing either way.

*Does it actually reuse a prefix?* **Yes, by its own machinery rather than
mlx-lm's, and it is measured on this exact model.** `omlx/cache/` is 17,489
lines across sixteen modules, including `prefix_cache.py` (4,798 lines),
`paged_ssd_cache.py` (5,080), `boundary_snapshot_store.py` (2,000) and
`paged_cache.py` (1,793). Issue 19 measured the result on this machine against
`Qwen3.6-35B-A3B`: a prompt already in cache costs 5.6s, and — the case nothing
else does — the same 33,880-token prompt sent again **after killing and
restarting the server** costs **4.21s against a 100.9s cold prefill**. That is
work genuinely skipped, not an echo of the client's markers.

*Does it inherit mlx-lm's Qwen 3.5 limitation?* **It classified the problem
rather than escaping it, and the measurement says reuse survives anyway.**
`omlx/cache/type_handlers.py` gives each cache type a `supports_block_slicing`
flag: `True` for `KVCache`, and `False` for `RotatingKVCache` ("Cannot safely
slice rotating cache"), `ArraysCache` ("Generic arrays may not be
sequence-indexed") and `CacheList` ("Mixed sub-cache types prevent slicing").
Those three are exactly the sliding-window, Mamba/SSM and mixed-attention cases
mlx-lm issue [980](https://github.com/ml-explore/mlx-lm/issues/980) names when it
says "Prompt prefix caching only works for pure full-attention models. Any model
using sliding window attention, Mamba/SSM layers, or mixed attention types
silently falls back to full prompt recomputation on every request", listing
**Qwen 3.5 (all sizes)**.

But slicing is not the whole cache, and oMLX restores what it cannot slice.
`omlx/cache/_rotating_subclass.py` exists precisely so that **SSD-restored
rotating caches work**, its docstring naming three upstream failures it fixes
(mlx-lm issues 934, 903, 900) where a restored buffer shorter than `max_size`
"exposes zero positions to attention causing softmax dilution that surfaces as
infinite loops or empty content". `hybrid_cache.py` carries a per-layer
`LayerCacheConfig` with its own `supports_block_slicing`, for "models that use
different cache types across layers (e.g., Qwen3-Next with ArraysCache +
KVCache)".

**Which cache class `qwen3_5_moe` instantiates could not be determined from
oMLX's source**: `omlx/cache/type_registry.py` keys on the mlx-lm cache class
name at runtime, not on architecture, so the answer lives in mlx-lm's model
implementation. Issue 19's 4.21s answers it empirically for this model without
answering it in general. The same uncertainty is a second candidate explanation
for section 2's 20,480 plateau on LM Studio, alongside the layer-boundary one —
an architecture whose blocks the cache handles imperfectly would look like this.

*Speed, and why the published figures must not be used.* `docs/models.md:275-283`
carries `local-llm-bench` figures on an M1 Max 64GB running Qwen3.5-35B-A3B
4-bit: oMLX at 47.3 effective / 65.2 generation against LM Studio MLX at 17.0 /
56.6. **Those are not transferable, and this repo has already established why.**
Issue 19 found the harness "counts each SSE delta as one token, and oMLX packs
7.69 tokens into a delta"; reading `usage.completion_tokens` instead reverses the
result. `docs/models.md:389-390` re-measures the same scenario on Qwen3.6 here at
34.1 effective for LM Studio against the published 17.0. The only figures worth
carrying are issue 19's own, measured on this machine on the model held today:

| | LM Studio | oMLX |
| --- | --- | --- |
| decode, short context | 52.0 tok/s | **57.8 tok/s** |
| ops-agent scenario, effective | **33.7 tok/s** | 29.9 tok/s |
| cold prefill at 33.9k tokens | **96.3s** | 111.5s |
| a prompt already in cache | **1.1s** | 5.6s |
| same prompt after a server restart | full cold prefill | **4.21s** |

oMLX wins decode by 11% and wins the restart case outright. **It loses prefill,
which is the term this note says dominates** — 111.5s against 96.3s at 33.9k
tokens — it loses the warm path five-fold, and it loses the agent-shaped
scenario, which is the one that looks like the thing being complained about.

*Cost of building it.* The `Runtime` port is six members and oMLX answers every
one. `GET /v1/models` and `GET /v1/models/status` split catalogue from held
(`adapter-surfaces.md` section 4); `POST /v1/models/{model_id}/unload`
(`omlx/server.py:2943`) is awaited, so a 200 means the memory has gone; it
serves `anthropic`, so `require_compatible` passes against Claude Code. The work
is one adapter package, one stand-in, and a line in
`tests/runtimes_under_test.py`, against the three conformance suites. No model
re-download, which is the whole difference from llama.cpp.

Two things would fight the port, and issue 19 names both.
`Capabilities.manages_its_own_memory` would be true in a way LM Studio's is not:
`process_memory_enforcer` runs a ceiling check every second and evicts
least-recently-used, so `ensure_only`'s promise can be undone a second after it
is made, and `_let_go_of_the_rest` would be doing a job the runtime is already
doing. The second is already handled: oMLX raises the Metal wired limit at
startup, and `docs/architecture.md` records that reading `iogpu.wired_limit_mb`
at the point of use "is right even when a runtime moves it at startup, which
oMLX does" — which is what #42 settled.

**Recommendation, in order: config-only first, then experiment 1, then OpenCode
if experiment 1 confirms the payload gap, and oMLX not for this problem.**

The ordering follows from which term each attacks. OpenCode attacks the four-fold
prefill payload, which is H2 and this note's verdict. oMLX attacks decode speed
and the cross-run cold start. **If H2 is the dominant cost, no runtime change
fixes it** — both runtimes prefill the same 26,000 tokens Claude Code sends, and
on this repo's own measurements LM Studio is currently the faster of the two at
doing exactly that. Swapping the runtime under an unchanged agent would trade a
partial 20,480-token reuse for a warm path five times slower, to gain 11% on
decode.

That is not an argument against oMLX. It is an argument that oMLX answers a
different question, and issue 19 states that question better than this note
could: offgrid lets go of the model when the agent exits, so **every run starts
cold**, and oMLX is the only runtime found whose cache outlives its own process.
If the thing being fixed is "the first turn of every session costs 100 seconds",
oMLX is the candidate and issue 19 is the place that decision belongs. If the
thing being fixed is "every turn is slow", it is not.

## 6. What could not be determined

0. **Whether the observation this research was commissioned to explain is real.**
   It has to come first, because everything after it is conditional on it. The
   slow runs were measured against the instance section 2 describes: a
   **262,144**-token window where the profile asks 131,072, and **`parallel: 4`**
   — both confirmed off the running server on 2026-08-21, and neither the state
   `offgrid run` would have produced. The OpenCode comparison was a separate
   hand-run, and **nothing records what LM Studio was serving at the time**. If
   it differed on either, the observed difference may owe something other than
   payload. Section 3's payload gap is measured and stands on its own; that a
   four-fold prefill difference is what the *person* felt is the part that is
   unestablished.

   Reasoning **no longer belongs on this list** for the Claude Code half.
   Section 3a measured that path producing none for this model, so the
   advertised `default: "on"` cannot have confounded those runs. It remains a
   confound for the OpenCode half, in the opposite direction: that agent was on
   the dialect that reasons, so it was carrying a cost Claude Code was not.

   *The control, which precedes experiment 1 rather than replacing it:* let go
   of everything and load once through `offgrid run`, so the window is the
   profile's and the load path is the real one; then run both agents against
   that same untouched instance. Fix `enableThinking` explicitly rather than
   leaving it at its default, and record which way it was set, because it
   changes the OpenCode half and not the Claude Code half. Every figure below is
   worth more taken against a known server state, and worth little without one.

1. **How many tokens OpenCode actually sends.** Section 3's figure is a byte
   count with an assumed bytes-per-token ratio and no accounting for JSON schema
   overhead. *Experiment 1:* with one model held and `parallel: 1`, send the same
   trivial prompt ("say hello and stop") through Claude Code and through
   OpenCode, and read `prompt_tokens` and time-to-first-token off LM Studio's
   server log for each. `~/.lmstudio/.internal/http-server-config.json` already
   has `verbose: true` and `fileLoggingMode: "succinct"`, so the log is being
   written. This is the one experiment that decides the whole question, and it
   costs two prompts.

   **Section 3a makes its design harder, and the note should not pretend
   otherwise.** Comparing the two agents means comparing two dialects that
   behave differently: OpenCode's `/v1/chat/completions` reasons for this model
   and Claude Code's `/v1/messages` does not, so a single wall-clock number per
   agent silently folds a reasoning difference into a payload comparison. Two
   ways out, and either is acceptable as long as which one was taken is stated.
   Control it — set `enableThinking: false` in the model's `model.yaml` so
   neither path reasons, and compare prefill against prefill. Or report both
   numbers with the asymmetry named, which is the more honest answer to "why
   does this feel slower" and the less useful one for isolating H2. Reporting
   one number without saying which regime it came from would be the one
   unacceptable option.

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

5. **Why `/v1/messages` does not reason.** Section 3a answered the question this
   item used to ask — there is no per-request reasoning knob on LM Studio in
   either dialect, and the Anthropic path produces no reasoning for this model
   whether asked to or not — and replaced it with a narrower one. Stripping is
   ruled out: `output_tokens: 3` for `"Hello!"` says the tokens were never
   generated, and a strip would still have paid for generating them. What
   remains is whether LM Studio's `/v1/messages` implementation sets
   `enable_thinking = false` when it renders the chat template, or builds the
   prompt by a route that never reaches the template's reasoning branch.
   **No primary source settles it:** LM Studio's Anthropic-compat docs do not
   mention reasoning, its OpenAI-compat payload list does not carry
   `reasoning_effort`, and the app is closed source.

   *Experiment 5, rewritten:* set `enableThinking: false` in the model's
   `model.yaml` and send the same two requests again. If the OpenAI path stops
   reasoning and the Anthropic path is unchanged, the Anthropic path is already
   taking the false branch and the model file is the only control — which is
   what section 3a infers. If the Anthropic path changes too, the template is
   being reached and something else suppressed it. Either result is worth more
   than what is recorded today, and neither costs more than four requests. This
   is #40's real form for LM Studio, and it also bears on
   `adapter-surfaces.md` open question 1, which asked a question that now has a
   measured answer for this model.

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

9. **Which mlx-lm cache class `qwen3_5_moe` instantiates.** It decides whether
   this model is one of the architectures mlx-lm issue 980 says falls back to
   full recomputation, and it is a candidate explanation for section 2's 20,480
   plateau. oMLX's registry keys on the class name at runtime rather than on
   architecture (`omlx/cache/type_registry.py`), so its source cannot answer it.
   *Experiment 8:* load the model under `mlx_lm` directly and print
   `type(c).__name__` for each entry of the cache its model builder returns. No
   server involved, and it answers the question for LM Studio and oMLX at once.

10. **Whether oMLX's `forced_ct_kwargs` actually suppresses reasoning on
    `/v1/messages` for this model.** Section 5 establishes that the setting
    exists and that per-request kwargs lose to it
    (`omlx/model_settings.py:1374-1378`), not that the result is a model which
    stops reasoning — and issue 19 observed reasoning arriving as visible text
    on that path. This is #40's real form. *Experiment 9:* serve this model
    under oMLX with `forced_ct_kwargs: ["enable_thinking"]` and
    `chat_template_kwargs: {"enable_thinking": false}`, send one `/v1/messages`
    request, and check the raw stream for both `thinking` content blocks and
    untagged "Thinking Process" prose in `content`. It also settles
    `adapter-surfaces.md` open question 5, which is the same parser.

11. **Whether `/v1/messages` still declines to reason once tools are in the
    request.** Everything in section 3a was measured with **no tools**, one
    trivial prompt, non-streaming. Chat templates commonly branch on whether
    tools are present, and Qwen-family templates render tool schemas in a
    separate block, so the reasoning branch is not guaranteed to be reached the
    same way. This matters more than a caveat usually would, because a real
    Claude Code turn always carries the full tool set — section 2 measures it at
    roughly 25,000 tokens of it — so the tool-present path is the only one that
    describes what a person actually waits for. If reasoning returns with tools
    present, section 3a's demotion of the reasoning lever is wrong for the case
    that counts, and the levers table would have to move it back.

    *Experiment 10:* send the same `"say hello and stop"` prompt to
    `/v1/messages` twice, once bare and once with a handful of tool definitions
    attached, and compare `output_tokens`. Two requests, and it either confirms
    section 3a for the case that matters or overturns it. **This should be run
    before anything in section 3a is acted on.**
