# What four runtimes and three agents actually expose

Primary-source research, gathered 2026-08-11. Everything below records what a
vendor documents, what its OpenAPI spec declares, or what its source says when
the documentation is silent. Nothing recorded here has been revised since;
where it points at offgrid's own code it names modules and functions rather
than lines, so that the pointers survive the code moving. It is **not** a recommendation about offgrid's
design: there is no proposed port shape here, no method signatures, and no
union-of-features table saying every capability should be supported. The four
questions are answered so that someone else can decide which operations belong
behind a seam and which are one runtime's private problem.

Sources are official docs, the projects' own repositories, their OpenAPI specs,
their release notes, and their issue trackers. Where a claim rests on reading
source, the repository, path and line are named. Where a thing could not be
established, it says so and says what was tried. Inference is labelled as
inference.

## What was read, and at which version

| Thing | Version | How that was determined |
| --- | --- | --- |
| LM Studio | docs describe up to **0.4.1**; the app in the wild is at **0.4.20** | `1_developer/api-changelog.md` in `lmstudio-ai/docs`, whose newest heading is `LM Studio 0.4.1`; the repo's last commit is `b02d1751`, 2026-07-20. Bug reports filed against `0.4.19+2` and `0.4.20` establish the app is ahead of the docs |
| Ollama | **v0.32.8**, released 2026-08-10 | `gh api repos/ollama/ollama/releases/latest`. Docs and source read from `main` |
| oMLX | source read at **`2450a53c`** on `main`, `__version__ = "0.5.8.dev3"`; newest tag `v0.5.8.dev3`, newest stable `v0.5.7` | `git clone` of `https://github.com/jundot/omlx`, `omlx/_version.py`, `git ls-remote --tags` |
| llama.cpp `llama-server` | **b10357**, released 2026-08-11 | `gh api repos/ggml-org/llama.cpp/releases/latest`; `tools/server/README.md` read from `master` |
| Claude Code | docs current as of the fetch; behaviours pinned to versions **v2.1.181 – v2.1.223** in the prose | `code.claude.com/docs/en/*`, which version-stamps individual behaviours inline |
| Codex CLI | **rust-v0.147.0**, released 2026-08-07 | `gh api repos/openai/codex/releases/latest`; source read from `main` |
| OpenCode | **v1.18.16**, released 2026-08-10 | `gh api repos/sst/opencode/releases/latest`; docs read from `packages/web/src/content/docs/providers.mdx` on `main` |

oMLX's documentation is thin, so nearly every oMLX claim below comes from
`omlx/server.py` — a 6,800-line FastAPI application — rather than from prose.
Issue 19 on `pvardanis/offgrid` is treated as a primary source for oMLX
behaviour measured on this machine.

## 1. Which dialect each runtime serves

| Runtime | `anthropic` | `openai` | Other |
| --- | --- | --- | --- |
| LM Studio | `POST /v1/messages` | `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`, `GET /v1/models` | native REST at `/api/v1/*`, legacy native REST at `/api/v0/*` |
| Ollama | `POST /v1/messages` | `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`, `GET /v1/models`, `GET /v1/models/:model` | native REST at `/api/*` |
| oMLX | `POST /v1/messages`, `POST /v1/messages/count_tokens` | `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/rerank`, `GET /v1/models` | admin UI at `/admin/*`, `GET /api/status` |
| llama.cpp | `POST /v1/messages`, `POST /v1/messages/count_tokens` | `POST /v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`, `GET /v1/models` | native `/completion`, `/props`, `/slots`, `/tokenize`, `/apply-template` |

All four serve both dialects. That is the flat answer, and it is the least
interesting thing in the table, because the four `/v1/messages` implementations
are not the same size.

**LM Studio** added `POST /v1/messages` in 0.4.1, with the stated purpose "Use
Claude code models with LM Studio"
([api-changelog](https://github.com/lmstudio-ai/docs/blob/main/1_developer/api-changelog.md)).
The endpoint page documents streaming (`message_start`, `content_block_start`,
`content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`)
and tool use with Anthropic-style `input_schema` and `tool_choice`
([messages.md](https://github.com/lmstudio-ai/docs/blob/main/1_developer/4_anthropic-compat/messages.md)).
It documents **no** `/v1/messages/count_tokens`, and the sibling endpoint does
not exist: LM Studio's own server log, quoted in
[bug-tracker issue 2055](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2055)
(2026-06-15, still open), reads

> `Unexpected endpoint or method. (POST /v1/messages/count_tokens?beta=true). Returning 200 anyway`

Returning 200 to an unimplemented endpoint is worse than a 404, because a
client cannot tell the difference between "counted zero" and "not implemented".

LM Studio's `/v1/messages` is also the youngest surface it has, and the one
that breaks. Open reports against it: tool calling broken with Qwen models
under Claude Code on 0.4.19 Build 2
([2164](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2164)), a
grammar-parser crash with Claude Code on 0.4.20 that did not happen on 0.4.16
([2236](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2236)), a
500 on image content
([1755](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1755)), and
`system` role rejected in the messages array in the standalone build
([2204](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2204)).

**Ollama** documents its Anthropic compatibility in
[`docs/api/anthropic-compatibility.mdx`](https://github.com/ollama/ollama/blob/main/docs/api/anthropic-compatibility.mdx),
and the route is registered in source at
[`server/routes.go:1908`](https://github.com/ollama/ollama/blob/main/server/routes.go):

```go
r.POST("/v1/messages", s.withInferenceRequestLogging("/v1/messages", cloudPassthroughMiddleware(...), middleware.AnthropicMessagesMiddleware(), s.ChatHandler)...)
```

No `/v1/messages/count_tokens` is registered anywhere in `routes.go`. Ollama's
doc carries a checkbox list of what it supports and — unusually — what it does
not: `tool_choice` and `metadata` are both marked unsupported, and the doc
states plainly that "API key is accepted but not validated", the
`anthropic-version` header is "accepted but not used", and "Token counts are
approximations based on the underlying model's tokenizer". Ollama is the only
one of the four that publishes its own gap list.

**oMLX** serves the largest Anthropic surface of the four. Its request model at
[`omlx/api/anthropic_models.py:185-202`](https://github.com/jundot/omlx/blob/main/omlx/api/anthropic_models.py)
accepts `system`, `stop_sequences`, `stream`, `temperature`, `top_p`, `top_k`,
`metadata`, `tools`, `tool_choice`, `thinking` and `chat_template_kwargs`, and
it implements `POST /v1/messages/count_tokens` at `omlx/server.py:5547` with a
`TokenCountResponse` of `{"input_tokens": int}`. It also understands Anthropic
prompt caching markers: `omlx/server.py:4844` calls
`request_has_cache_control(request)` and changes what `message_start` reports
for `input_tokens` depending on the answer.

**llama.cpp** advertises "[Anthropic Messages API] compatible chat completions"
in the first ten lines of
[`tools/server/README.md`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
and documents both `/v1/messages` and `/v1/messages/count_tokens`. It hedges
the claim: "While no strong claims of compatibility with the Anthropic API spec
are made, in our experience it suffices to support many apps." Its documented
option list for `/v1/messages` is `model`, `messages`, `max_tokens`, `system`,
`temperature`, `top_p`, `top_k`, `stop_sequences`, `stream`, `tools`,
`tool_choice` — no `thinking`, and tool use "requires `--jinja` flag".

So `count_tokens` is present on oMLX and llama.cpp, absent on Ollama and
LM Studio. That single endpoint is the sharpest split in the table, and section
7 explains why it matters to Claude Code.

## 2. Whether a caller can command a release, or only influence one

| Runtime | Can a caller *command* a release? | Mechanism | Can it *influence* one? |
| --- | --- | --- | --- |
| LM Studio | **Yes**, over HTTP | `POST /api/v1/models/unload` with `{"instance_id": ...}`; also `lms unload <model>` | Yes: `ttl` in a JIT request body (seconds), `lms load --ttl`, app-default 60 min, Auto-Evict |
| Ollama | **Yes**, over HTTP | `POST /api/generate` or `/api/chat` with an empty prompt and `keep_alive: 0` — the handler calls `expireRunner` synchronously | Yes: `keep_alive` per request, `OLLAMA_KEEP_ALIVE` per server |
| oMLX | **Yes**, over HTTP | `POST /v1/models/{model_id}/unload` | Yes: per-model and global `idle_timeout_seconds`; and it evicts on its own against a memory ceiling |
| llama.cpp | **Only in router mode** | `POST /models/unload` with `{"model": ...}`; unavailable when the server was started with a model | Yes: `--sleep-idle-seconds N`, which works in single-model mode too |

**LM Studio has an HTTP unload, and has since 0.4.0.** The 0.4.0 changelog
entry lists "Model [download], [load] and [unload] endpoints" as part of the
native `/api/v1/*` REST API, and
[`1_developer/2_rest/unload.md`](https://github.com/lmstudio-ai/docs/blob/main/1_developer/2_rest/unload.md)
gives it in full:

```bash
curl http://localhost:1234/api/v1/models/unload \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"instance_id": "openai/gpt-oss-20b"}'
```

It takes an `instance_id`, not a model key — the distinction matters because
`GET /api/v1/models` returns a `loaded_instances` array per model, each entry
with its own `id`. The response echoes the `instance_id` back.

**The `/api/v0` catalogue carries the same ids**, which is what lets this
adapter release over HTTP without moving to `/api/v1` first. Loading
`qwen3-0.6b-mlx` three times against a live server and reading both endpoints
gave `qwen3-0.6b-mlx`, `qwen3-0.6b-mlx:2` and `qwen3-0.6b-mlx:3` from each:
`/api/v1` as `loaded_instances[].id` under one model, `/api/v0` as three
entries of its own, all `"state": "loaded"`. The release accepted an id taken
straight from `/api/v0`, and answered `404 model_not_found` for one it was not
holding — which `lms unload` could not, exiting 0 for a name it did not know.

The companion
`POST /api/v1/models/load` documents `model`, `context_length`,
`eval_batch_size`, `flash_attention`, `num_experts`, `offload_kv_cache_to_gpu`
and `echo_load_config` — and notably **no `ttl` field**, so a model loaded
through the REST API takes the app default rather than a per-call TTL.

**Four things about that endpoint were captured live** on 2026-08-18, against
LM Studio on this machine, while #98 was written.

It answers a name it does not have with `404` and a reason, unlike the
messages endpoint, which answers `200` as whatever is loaded:

```
POST /api/v1/models/load  {"model": "totally/made-up-9000", "context_length": 8000}
→ 404  {"error": {"type": "model_not_found",
                  "message": "Model totally/made-up-9000 not found in downloaded models"}}
```

A success names the instance, and **does not echo the configuration** unless
`echo_load_config` is asked for — the readback offgrid needs comes from the
catalogue, not from here:

```
→ 200  {"type": "llm", "instance_id": "lfm2.5-1.2b-instruct-mlx",
        "load_time_seconds": 3.768, "status": "loaded"}
```

`context_length` is honoured and reported: loaded at 8000, the `/api/v0`
catalogue then gave `loaded_context_length: 8000` against a
`max_context_length` of 128000.

A window **above** the model's own maximum is accepted without complaint:
`qwen3-0.6b-mlx` states 40960 and was loaded at 50000, answering `200` and
reporting `loaded_context_length: 50000`. Nothing clamps it, which is why
refusing it is offgrid's job.

**GPU offload rides alongside the context length in setup guidance for local
models, and there is nothing here to offer.** `lms load` takes
`--gpu <off|max|0..1>` beside `-c/--context-length`, so pairing the two is the
obvious suggestion, and it does not transfer to this adapter for three
separate reasons.

The REST load endpoint has no field for it. The documented body above carries
`offload_kv_cache_to_gpu`, which is where the KV cache lives rather than how
much of the model does; there is no offload ratio to send. offgrid loads over
HTTP and never over `lms`, so the flag is not reachable from where it stands.

The ratio does not change what a load costs. Measured on this machine on
2026-08-20 with `lms load --estimate-only`, `--gpu off` and `--gpu max` return
the same figure to the hundredth of a unit, differing only in the `GPU Offload`
percentage echoed back:

```
lms load qwen3-0.6b-mlx --gpu off  → GPU Offload: 0%    Estimated GPU Memory: 469.15 MiB
lms load qwen3-0.6b-mlx --gpu max  → GPU Offload: 100%  Estimated GPU Memory: 469.15 MiB
lms load qwen/qwen3.6-35b-a3b --gpu off  → GPU Offload: 0%    Estimated GPU Memory: 26.64 GiB
lms load qwen/qwen3.6-35b-a3b --gpu max  → GPU Offload: 100%  Estimated GPU Memory: 26.64 GiB
```

Both models are MLX, which is what every text model on this machine is: `lms
ls --json` reports `"format": "safetensors"` for all five LLMs downloaded here
and `gguf` only for the embedding model. Inference, not measurement: an offload
ratio splits weights between a GPU's own memory and the host's, and Apple
Silicon has one pool, so on MLX there is no second place for the weights to
sit — which is consistent with an estimate that reports GPU memory and total
memory as the same number at 0%.

The memory question the flag gestures at is answered elsewhere. How much the
GPU may hold is the macOS wired limit, `iogpu.wired_limit_mb`, which
`sizing/machine` reads and `offgrid setup` prints — a number the machine
states rather than one a load is asked to respect.

The TTL story is documented separately in
[`ttl-and-auto-evict.md`](https://github.com/lmstudio-ai/docs/blob/main/1_developer/0_core/ttl-and-auto-evict.md).
Three facts from it: JIT-loaded models default to a 60-minute TTL; a `ttl` in
seconds can ride along in a chat request body (`"ttl": 300`); and models loaded
with `lms load` have **no** TTL by default and "will remain loaded in memory
until you manually unload them". Auto-Evict, on by default, means "at most `1`
model is kept loaded in memory at a time (when loaded via JIT)" and explicitly
does not affect non-JIT loads. So on LM Studio, how a model got into memory
determines whether it leaves on its own.

**Ollama's `keep_alive` is the interesting case, and it settles cleanly.** The
value is a duration string or a number of seconds; the OpenAPI spec at
[`docs/openapi.yaml:107-111`](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)
describes it as "Model keep-alive duration (for example `5m` or `0` to unload
immediately)". The negative case is not in the spec but is in the source
comment at
[`envconfig/config.go:126-128`](https://github.com/ollama/ollama/blob/main/envconfig/config.go):

> KeepAlive returns the duration that models stay loaded in memory. KeepAlive
> can be configured via the OLLAMA_KEEP_ALIVE environment variable.
> **Negative values are treated as infinite. Zero is treated as no keep alive.**
> Default is 5 minutes.

and the implementation matches: `if keepAlive < 0 { return time.Duration(math.MaxInt64) }`.

An immediate release **is commandable**, not merely influenced. The generate
handler at
[`server/routes.go:408-420`](https://github.com/ollama/ollama/blob/main/server/routes.go)
has a dedicated branch:

```go
// expire the runner if unload is requested (empty prompt, keep alive is 0)
if req.Prompt == "" && req.KeepAlive != nil && req.KeepAlive.Duration == 0 {
    s.sched.expireRunner(m)
    c.JSON(http.StatusOK, api.GenerateResponse{..., DoneReason: "unload"})
    return
}
```

with the same branch on the chat handler at `routes.go:2482-2492` keyed on
`len(req.Messages) == 0`. So the caller commands a release by posting an empty
request with `keep_alive: 0` and gets `"done_reason": "unload"` back as
confirmation. `keep_alive: 0` on a *non-empty* request is a different thing —
it lets go after the request completes, which is influence rather than command,
because the model stays resident for the duration of the generation.

**oMLX** exposes `POST /v1/models/{model_id}/unload` at
[`omlx/server.py:2672`](https://github.com/jundot/omlx/blob/main/omlx/server.py).
It distinguishes three cases by status code: 503 if the pool is not
initialised, 404 `Model not found`, 400 `Model not loaded`, and otherwise
awaits `engine_pool._unload_engine(model_id)` and returns
`{"status": "ok", "model_id": ...}`. Because it awaits the unload rather than
scheduling it, the 200 means the memory has gone.

oMLX is also the only one of the four that manages memory against a ceiling on
its own initiative. `engine_pool.check_ttl_expirations` (`engine_pool.py:2200`)
unloads models past their TTL, skipping pinned ones and ones with active
requests; the TTL comes from a per-model setting with a global
`idle_timeout_seconds` fallback (`omlx/settings.py:448`), and a separate
`process_memory_enforcer` runs a ceiling check on a one-second interval. Issue
19 records what that looks like on this machine at startup:

```
Metal wired limit raised: 0.0GB -> 56.0GB (target=58.0GB, iogpu sysctl cap=56.0GB)
Process memory enforcer started (tier=balanced, ceiling=48.9GB, interval=1.0s)
```

**llama.cpp splits the answer by launch mode.** A `llama-server` started with a
model has no unload endpoint at all — the model is the process's reason for
existing, and the way to release it is to kill the process. Started *without* a
model it comes up in **router mode** and exposes `GET /models`,
`POST /models/load`, `POST /models/unload` and `GET /models/sse`; the README
introduces this as "a **router mode** that exposes an API for dynamically
loading and unloading models". Both load and unload take `{"model": "<id>"}`
and answer `{"success": true}`. A `stop-timeout` preset key, default 10
seconds, controls how long the router waits after a requested unload "before
forcing termination".

The influence knob is `--sleep-idle-seconds SECONDS`, default `-1` (disabled),
and it is **not** router-only. The README's "Sleeping on Idle" section says
"It works seamlessly in both single-model and multi-model configurations" and
that when the server sleeps, "the model and its associated memory (including
the KV cache) are unloaded from RAM to conserve resources. Any new incoming
task will automatically trigger the model to reload." That is the closest thing
a single-model `llama-server` has to letting go, and it is a timer rather than
a command. It was introduced in
[PR #18228](https://github.com/ggml-org/llama.cpp/pull/18228).

## 3. How each runtime is told not to reason before answering

| Runtime | Knob | Same in both dialects? | Where reasoning goes when not suppressed |
| --- | --- | --- | --- |
| LM Studio | `reasoning: "off"` on `/api/v1/chat`; `reasoning_effort` on `/v1/chat/completions` is undocumented and unreliable | **No** — nothing documented on `/v1/messages` | a separate `reasoning` field on `/v1/chat/completions` (gpt-oss), a `reasoning` output item on `/api/v1/chat`, `reasoning_content` for DeepSeek R1 |
| Ollama | `think: false` (also `"low"`, `"medium"`, `"high"`, `"max"`) on `/api/chat` and `/api/generate`; `thinking: {"type": "disabled"}` on `/v1/messages` | Different spelling per dialect, both exist | a separate thinking output on the native API; `thinking` content blocks and `thinking_delta` events on `/v1/messages` |
| oMLX | `chat_template_kwargs: {"enable_thinking": false}` on **both**; `thinking: {"type": "disabled"}` additionally on `/v1/messages` | **Yes**, `chat_template_kwargs` is on all three request models | `thinking` content blocks — but only when the emitted text is wrapped in `<think>` tags |
| llama.cpp | `reasoning_effort: "none"`, or `chat_template_kwargs: {"enable_thinking": false}`, or `reasoning_format: "none"` | documented only for `/v1/chat/completions` | parsed out per `reasoning_format`; `"none"` returns "the raw generated text" |

This is the question where the four runtimes agree least, and where the
documentation is thinnest relative to how much it matters.

**LM Studio has three different spellings across three of its own APIs, and the
Anthropic one is undocumented.** On the native REST API,
[`1_developer/2_rest/chat.md`](https://github.com/lmstudio-ai/docs/blob/main/1_developer/2_rest/chat.md)
documents a `reasoning` field typed `'"off" | "low" | "medium" | "high" | "on"'`
whose description reads "Reasoning setting. Will error if the model being used
does not support the reasoning setting using. Defaults to the automatically
chosen setting for the model." The same file's response schema has a
`Reasoning` output item of `{type: "reasoning", content: string}`, and a
`reasoning_output_tokens` field in stats — so on `/api/v1/chat`, reasoning is a
structurally separate thing, not text. `GET /api/v1/models` advertises the
per-model options in `capabilities.reasoning.allowed_options`, typed
`("off" | "on" | "low" | "medium" | "high")[]`, with a `default`.

On the OpenAI-compatible path, `reasoning_effort` is **not in the documented
payload list**:
[`3_openai-compat/chat-completions.md`](https://github.com/lmstudio-ai/docs/blob/main/1_developer/3_openai-compat/chat-completions.md)
enumerates `model`, `top_p`, `top_k`, `messages`, `temperature`, `max_tokens`,
`stream`, `stop`, `presence_penalty`, `frequency_penalty`, `logit_bias`,
`repeat_penalty`, `seed` and nothing else. `reasoning.effort` appears only in
the 0.3.29 changelog entry, scoped to `/v1/responses` and to one model:
"Reasoning support with `reasoning.effort` for `openai/gpt-oss-20b`."

Issue 19 records that LM Studio takes `reasoning_effort: "none"` and this
research does not contradict that — but it does bound it. Open bug report
[2195](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2195)
(2026-07-23, against 0.4.19+2, on an M5 Max) reports `reasoning_effort` on
`/v1/chat/completions` being "silently dropped before it ever reaches
`apply_chat_template`" for a model whose published chat template reads it, with
`prompt_tokens` byte-identical across `low`, `high`, and the field being
absent. The reporter's reading of `mlx_engine`'s source is that LM Studio has
"explicit, hand-wired reasoning support for **Gemma 4** and **Qwen 3.5**
specifically" and nothing generic. Report
[988](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/988), "Setting
reasoning_effort through the API does not work", is also open, and
[2057](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2057), "REST
API and lms CLI ignore thinking_enable settings", was closed. Whether
`/v1/messages` accepts any reasoning knob at all could not be established: the
Anthropic-compat docs do not mention one, and LM Studio is closed source, so
there is nothing to read.

**Ollama's knob is `think`, and it is a first-class field.** The OpenAPI spec
types it as a boolean or one of `high`, `medium`, `low`, `max`, described as
"When true, returns separate thinking output in addition to content"
(`docs/openapi.yaml:103`, and again at `:292-295` for the chat request). On the
Anthropic path the spelling changes: the compatibility doc's supported-fields
list marks `thinking` supported, marks `thinking` blocks supported in message
content, and marks `thinking_delta` among the streaming
`content_block_delta` variants. Ollama also normalises across the two: source
at `server/routes.go:435-437` maps a `think` of `"max"` down to `"high"` for
Harmony models, with the comment "harmony's Reasoning field only understands
low/medium/high".

**oMLX takes both knobs on the Anthropic path, which settles issue 19's open
question.** Issue 19 records: "Whether the Anthropic path accepts either knob
was not established." The source settles it two ways.

First, `chat_template_kwargs` is a declared field on the Anthropic request
model itself —
[`omlx/api/anthropic_models.py:201-202`](https://github.com/jundot/omlx/blob/main/omlx/api/anthropic_models.py):

```python
    # Chat template kwargs (e.g. enable_thinking, reasoning_effort)
    chat_template_kwargs: dict[str, Any] | None = None
```

with byte-identical lines in `omlx/api/openai_models.py:299` and
`omlx/api/responses_models.py:126`. The same knob, on all three dialects.

Second, `/v1/messages` translates Anthropic's own `thinking` config into it —
[`omlx/server.py:5217-5224`](https://github.com/jundot/omlx/blob/main/omlx/server.py):

```python
        # Pass Anthropic thinking config to chat template (except forced keys)
        if hasattr(request, "thinking") and request.thinking:
            if "enable_thinking" not in forced_keys:
                thinking_type = getattr(request.thinking, "type", None)
                if thinking_type in ("enabled", "adaptive"):
                    merged_ct_kwargs["enable_thinking"] = True
                elif thinking_type == "disabled":
                    merged_ct_kwargs["enable_thinking"] = False
```

`ThinkingConfig.type` is `Literal["enabled", "disabled", "adaptive"]`
(`anthropic_models.py:176`), so oMLX accepts Anthropic's `adaptive` tag — the
one the Claude Code gateway docs warn produces a `400` on upstreams that do not
know it. A per-model `forced_ct_kwargs` setting can pin `enable_thinking` so a
request cannot override it (`omlx/model_settings.py:97`), which is a way for a
runtime-side configuration to silently win over the caller.

On where the reasoning *goes*: oMLX's `/v1/messages` streaming path constructs
a `ThinkingParser` unconditionally (`omlx/server.py:4822`) and emits proper
Anthropic `thinking` content blocks via `create_thinking_delta_event`
(`server.py:4899-4903`). Issue 19 observed the opposite — reasoning arriving as
visible text reading "Thinking Process: 1. Analyze the request..." — and the
parser's docstring explains why without contradicting either observation.
`ThinkingParser` is "a stateful streaming parser for separating
`<think>...</think>` from content" (`omlx/api/thinking.py:215-217`) and matches
those literal tags only. Prose that announces itself as thinking without
wrapping itself in a tag is, to that parser, an answer. **This is inference**
from the parser's implementation matched against issue 19's transcript; sending
the same prompt again and inspecting the raw stream for `<think>` would confirm
it.

**llama.cpp documents three knobs and is explicit about what each does.** From
`tools/server/README.md`, verbatim:

- `chat_template_kwargs`: "Allows sending additional parameters to the json
  templating system. For example: `{"enable_thinking": false}`"
- `reasoning_effort`: "If set to `none`, reasoning will be disabled for this
  request. Other values (e.g., `low`, `max`) have no effect on reasoning."
- `reasoning_format`: "The reasoning format to be parsed. If set to `none`, it
  will output the raw generated text."

There is also `--chat-template-kwargs STRING` as a server flag
(`LLAMA_ARG_CHAT_TEMPLATE_KWARGS`), which sets the default for every request,
and a `reasoning_control` field plus a `/v1/chat/completions/control` endpoint
for "ending reasoning blocks mid-generation" — a capability none of the other
three has. All of this is documented under `/v1/chat/completions`; the
`/v1/messages` section's option list does not repeat it, and nothing found says
whether the Anthropic path honours the same fields.

So on the narrow question offgrid's issue 19 raises — two runtimes spelling "do
not think" differently, each ignoring the other's — the wider survey says it is
worse than two spellings. `reasoning_effort` is llama.cpp's documented knob and
LM Studio's undocumented and unreliable one; `chat_template_kwargs.enable_thinking`
works on llama.cpp and oMLX and is not documented for either of the others;
`think` is Ollama's and nobody else's; Anthropic's own `thinking: {"type": ...}`
is honoured by oMLX and Ollama, undocumented on LM Studio, and absent from
llama.cpp's documented field list.

## 4. Whether each runtime says what is held right now

| Runtime | Endpoint | Are "available" and "held" distinguishable? |
| --- | --- | --- |
| LM Studio | `GET /api/v1/models`, `GET /api/v0/models`, `lms ps` | **Yes.** `/api/v1` gives every model a `loaded_instances` array; `/api/v0` gives each a `state` |
| Ollama | `GET /api/ps` (held) vs `GET /api/tags` (available) | **Yes**, by using two different endpoints |
| oMLX | `GET /v1/models/status` (held) vs `GET /v1/models` (available) | **Yes**, but not on `/v1/models`, whose docstring says otherwise |
| llama.cpp | router mode: `GET /models`; single-model: `GET /props` | **Router mode yes; single-model mode the question barely applies** |

**LM Studio distinguishes them within one response, twice over.** The native
`GET /api/v1/models` returns per model a `loaded_instances` array — "List of
currently loaded instances of this model" — where each entry carries an `id`
and a `config` with the `context_length`, `eval_batch_size`, `parallel`,
`flash_attention`, `num_experts` and `offload_kv_cache_to_gpu` that instance
was loaded with. An empty array means downloaded but not held. Alongside it
each model carries `max_context_length`, so the ceiling and the served window
are both present and separately named — which is the distinction
`lmstudio.LMStudio._now_holding` exists to make. The older `/api/v0/models`
instead
carries a flat `"state"` field per model, documented as taking `"not-loaded"`
and, implicitly, `"loaded"`
([rest endpoints](https://lmstudio.ai/docs/developer/rest/endpoints)). That is
the field `lmstudio.loaded` reads.

**Ollama splits them across two endpoints.** `GET /api/ps` is summarised as
"Retrieve a list of models that are currently running" and its documented
response carries, per model, `name`, `model`, `size`, `digest`, a `details`
object with `parameter_size` and `quantization_level`, an `expires_at`
timestamp, `size_vram`, and `context_length`
(`docs/openapi.yaml:1169-1204`). `expires_at` is the notable one: it exposes
the keep-alive deadline, so a caller can see not only that a model is held but
when it is due to be released. `GET /api/tags` lists what is on disk. Nothing
in the `/api/tags` response marks a model as running, so a caller wanting both
facts fetches twice.

**oMLX has the same split, and one of its two endpoints lies in its
docstring.** `GET /v1/models` is documented in source as "List all available
models with load status" (`omlx/server.py:2537`) but constructs `ModelInfo`
objects carrying only `id`, `owned_by` and `max_model_len` — no load status
reaches the response
([`server.py:2536-2620`](https://github.com/jundot/omlx/blob/main/omlx/server.py)).
The endpoint that does is `GET /v1/models/status`, "Extended endpoint that
provides more information than /v1/models" (`server.py:2629`). It returns
`engine_pool.get_status()` (`omlx/engine_pool.py:2159-2198`) enriched with
`max_context_window` and `max_tokens` per model. The pool status is the richest
"what is held" payload of the four:

```python
"final_ceiling": ..., "current_model_memory": ..., "model_count": ...,
"loaded_count": sum(1 for e in self._entries.values() if e.engine is not None),
"models": [{
    "id": mid, "model_path": ..., "loaded": e.engine is not None,
    "is_loading": e.is_loading, "loading_started_at": ...,
    "estimated_size": ..., "actual_size": ..., "pinned": e.is_pinned,
    "model_context_length": ..., "thinking_default": e.thinking_default,
    "last_access": ...,
}]
```

`loaded`, `is_loading` and `pinned` are three separate booleans, and
`estimated_size` against `actual_size` is the only place in this survey where a
runtime publishes both what it thought a model would cost and what it did.
`/v1/models` also hides models: a per-model `is_hidden` setting and a global
`hide_helper_models` toggle both drop entries from the list entirely
(`server.py:2570-2580`), so its catalogue is not a complete inventory.

**llama.cpp answers the question only in router mode.** There, `GET /models`
returns per model a `status` object whose `value` is one of `unloaded`,
`loading`, `loaded`, `sleeping` or `downloading`, with `args` recording the
command line the instance was launched with, and `failed`/`exit_code` on a
crash. `sleeping` is a state none of the other three names: the weights are out
of RAM but the instance is still tracked and will reload on the next request.
Adding `?reload=1` refreshes the list from the source directory. A single-model
`llama-server` has one model by construction, so `GET /v1/models` naming it is
the whole answer, and `GET /props` reports `is_sleeping` for the sleep case.

## 5. Which dialect each agent expects, and how it is pointed elsewhere

| Agent | Dialect | Pointed by |
| --- | --- | --- |
| Claude Code | `anthropic` (`/v1/messages`) | `ANTHROPIC_BASE_URL` environment variable, or the `env` block of a settings file |
| OpenCode | `openai` in practice; `anthropic` is expressible | `opencode.json`: `provider.<id>.npm` + `provider.<id>.options.baseURL` |
| Codex CLI | `openai`, but **only the Responses API** | `~/.codex/config.toml`: `[model_providers.<id>] base_url`, selected with `model_provider` or `--profile` |

**Claude Code** takes `ANTHROPIC_BASE_URL`, documented as "Override the API
endpoint to route requests through a proxy or gateway"
([env-vars](https://code.claude.com/docs/en/env-vars)). The
[gateway protocol reference](https://code.claude.com/docs/en/llm-gateway-protocol)
states the format-to-variable mapping directly: the Anthropic Messages format
is "Selected by `ANTHROPIC_BASE_URL`" and its endpoints are "`/v1/messages`,
`/v1/messages/count_tokens` (optional)". The other rows in that table —
`ANTHROPIC_BEDROCK_BASE_URL`, `ANTHROPIC_VERTEX_BASE_URL`,
`ANTHROPIC_FOUNDRY_BASE_URL`, `ANTHROPIC_AWS_BASE_URL` — select provider
dialects and are irrelevant to a local runtime.

Setting it in the environment and setting it in a settings file are not
equivalent: "When both a shell export and a settings-file `env` block set the
same variable, the settings-file value applies", and a shell export "doesn't
reliably reach background agents hosted by the supervisor"
([llm-gateway-connect](https://code.claude.com/docs/en/llm-gateway-connect)).

**OpenCode** points at a server through `opencode.json`. Its
[providers doc](https://github.com/sst/opencode/blob/main/packages/web/src/content/docs/providers.mdx)
carries worked examples for LM Studio (line 1418) and llama.cpp (line 1351),
both of the same shape:

```json
{
  "provider": {
    "lmstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LM Studio (local)",
      "options": { "baseURL": "http://127.0.0.1:1234/v1" },
      "models": { "google/gemma-3n-e4b": { "name": "Gemma 3n-e4b (local)" } }
    }
  }
}
```

The doc annotates each key: the provider ID "can be any string you want", `npm`
"specifies the package to use for this provider. Here,
`@ai-sdk/openai-compatible` is used for any OpenAI-compatible API", and
`options.baseURL` "is the endpoint for the local server". Separately, at line
34: "You can customize the base URL for any provider by setting the `baseURL`
option", with an `anthropic` example — so an `anthropic`-dialect local server
is expressible by overriding the built-in `anthropic` provider's `baseURL`
rather than declaring an `openai-compatible` one. The doc does not show that
being done against a local runtime, and none of its three local-server examples
(llama.cpp, LM Studio, Ollama) uses it. Whether the Anthropic AI SDK provider
tolerates a server that omits `count_tokens` was not established.

**Codex CLI expects the Responses API and nothing else, as of rust-v0.147.0.**
This is the sharpest constraint found in the whole survey, and it is recent.
The `WireApi` enum in
[`codex-rs/model-provider-info/src/lib.rs:53-83`](https://github.com/openai/codex/blob/main/codex-rs/model-provider-info/src/lib.rs)
has exactly one variant:

```rust
/// Wire protocol that the provider speaks.
pub enum WireApi {
    /// The Responses API exposed by OpenAI at `/v1/responses`.
    #[default]
    Responses,
}
```

and its hand-written `Deserialize` rejects the old value with a named error
(`lib.rs:49`):

```rust
const CHAT_WIRE_API_REMOVED_ERROR: &str = "`wire_api = \"chat\"` is no longer supported.\nHow to fix: set `wire_api = \"responses\"` in your provider config.\nMore info: https://github.com/openai/codex/discussions/7782";
```

A sibling constant removes the `ollama-chat` provider ID the same way. So a
runtime that serves only `/v1/chat/completions` cannot be used with current
Codex at all. All four runtimes here do serve `/v1/responses` — LM Studio since
0.3.29, Ollama at `routes.go:1903`, oMLX at `server.py:5673`, llama.cpp per its
README — so the constraint is satisfiable, but it is a hard gate rather than a
preference, and it is newer than most of the third-party instructions on the
internet.

The provider table keys, read from `ModelProviderInfo`
(`codex-rs/model-provider-info/src/lib.rs:86-145`), are `name`, `base_url`,
`env_key`, `env_key_instructions`, `experimental_bearer_token`, `auth`, `aws`,
`wire_api`, `query_params`, `http_headers`, `env_http_headers`,
`request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`,
`websocket_connect_timeout_ms`, `requires_openai_auth`, `supports_websockets`
and `supports_standalone_web_search`. The struct is `#[schemars(deny_unknown_fields)]`,
so a typo in a provider block is an error rather than a silent no-op. Ollama's
own integration doc shows the resulting config
([`docs/integrations/codex.mdx`](https://github.com/ollama/ollama/blob/main/docs/integrations/codex.mdx)):

```toml
model = "gpt-oss:120b"
model_provider = "ollama-launch"

[model_providers.ollama-launch]
name = "Ollama"
base_url = "http://localhost:11434/v1/"
wire_api = "responses"
```

## 6. What must be configured for each agent to talk to a local server

| | Claude Code | OpenCode | Codex CLI |
| --- | --- | --- | --- |
| Base URL | `ANTHROPIC_BASE_URL` | `provider.<id>.options.baseURL` | `model_providers.<id>.base_url` |
| Auth with no real key | `ANTHROPIC_AUTH_TOKEN` (→ `Authorization: Bearer`) or `ANTHROPIC_API_KEY` (→ `x-api-key`); **one is required** | provider-dependent; the local examples set none | `env_key` naming a variable, or `experimental_bearer_token`; `requires_openai_auth = false` is the default |
| Model name | `--model`, `ANTHROPIC_MODEL`, or the `model` setting | keys of `provider.<id>.models` | top-level `model` |
| Max output tokens | `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | not established | not found in the reference |
| Context window | `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, 100,000–1,000,000 | not established | `model_context_window` |
| Custom headers | `ANTHROPIC_CUSTOM_HEADERS`, `Name: Value` per line | `options.headers` | `http_headers`, `env_http_headers` |

**Claude Code needs a credential even though the server does not.** The
troubleshooting table is explicit that a reachable base URL is not enough: the
row "Claude Code asks you to log in even though the curl test succeeds" gives
the cause as "The CLI has no credential of its own: a reachable base URL isn't
one", and the fix as "Set `ANTHROPIC_AUTH_TOKEN` somewhere Claude Code reads
before first-run setup". Which variable decides which header carries it —
"`ANTHROPIC_AUTH_TOKEN` in `Authorization: Bearer`, `ANTHROPIC_API_KEY` in
`x-api-key`, and `apiKeyHelper` in both" — and the docs recommend
`ANTHROPIC_AUTH_TOKEN` when you do not know. `ANTHROPIC_API_KEY` additionally
"needs a one-time approval in interactive sessions", which is a prompt an
automated launch would hang on. Both LM Studio's and Ollama's own integration
docs use `ANTHROPIC_AUTH_TOKEN` with a dummy value; Ollama's comment on it is
`# required but ignored`.

The model name is separate from the base URL and is not discovered by default.
"`ANTHROPIC_BASE_URL` changes where requests are sent, not which model answers
them" ([model-config](https://code.claude.com/docs/en/model-config)), and
behind a custom base URL "your provider or gateway defines the model names, so
Claude Code passes any string through without checking it" — a mistyped model
name surfaces as an error on the first request, not at launch. Optional
discovery exists: `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` makes Claude
Code issue `GET /v1/models?limit=1000` at startup with a 3-second timeout,
treating any redirect as failure, and it **keeps only entries whose `id`
contains `claude` or `anthropic`, matched case-insensitively**. A local
runtime's catalogue of `qwen3.6-35b-a3b` and the like survives none of that
filter. Discovery is also silently off when
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is set.

Two limits are worth setting explicitly against a local server, and the docs
say so in the same troubleshooting row: for a server enforcing a smaller
context than the model's native window, "set `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
to the gateway's limit; the value is clamped to at least 100,000 tokens and at
most the model's context window", and "Also set `CLAUDE_CODE_MAX_OUTPUT_TOKENS`
below the gateway model's output limit". The 100,000 floor is the load-bearing
detail: a runtime serving a model at, say, 32k cannot have that matched, and
the docs say so — "a gateway limit below 100,000 can't be matched and
`/compact` remains the recovery there."

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` is the documented way to stop the
traffic that does not go to the base URL at all. Its documented side effects
are that it "disables auto-updates, so plan for another update path", it
suppresses the fast-mode availability check, it turns off model discovery, and
it does **not** stop the WebFetch domain safety check, which "still calls
`api.anthropic.com`" and needs `skipWebFetchPreflight: true` separately.

**OpenCode's local examples configure a base URL, a package and a model list,
and nothing else** — no auth key appears in the LM Studio, Ollama or llama.cpp
blocks. Model entries are keyed by the ID the server uses and carry a
human-readable `name`. What OpenCode assumes about output-token limits or
context windows was not established from the providers doc; it may live in
`models.mdx` or in models.dev metadata, neither of which was read.

**Codex** takes its key from a named environment variable rather than a literal:
`env_key` is "Environment variable that stores the user's API key for this
provider", and `experimental_bearer_token` exists but its own doc comment says
"Use of this config is discouraged in favor of `env_key` for security reasons".
`requires_openai_auth` defaults to `false`, and its comment says that when
false "login screen is skipped, and API key (if needed) comes from the
`env_key` environment variable" — so a local server needing no key is the
default-shaped case. `model_context_window` is a documented top-level key;
`model_max_output_tokens` appears in the reference's structure but not among
the actual entries, so **it could not be established** whether that key exists
at rust-v0.147.0. `stream_idle_timeout_ms` defaults to 300,000 — five minutes —
which is the same order as a cold prefill on a large local model.

## 7. What each agent assumes the server provides

This is the question with the most concrete answers, because Claude Code
publishes a contract for it and the other two do not.

**Claude Code's contract is the
[gateway protocol reference](https://code.claude.com/docs/en/llm-gateway-protocol),
and five of its requirements are things a local runtime may not meet.**

*Streaming is mandatory, and silence is fatal.* "Inference responses must
stream. Claude Code consumes server-sent events as they arrive, so a gateway
that buffers complete responses before relaying them stalls the client." Worse
for a local runtime: "Claude Code counts every byte your gateway relays,
including SSE `ping` events and comment lines, and aborts a stream that goes
silent for 300 seconds by default." A runtime that goes quiet during a long
prefill — and issue 19 measures a 33,880-token cold prefill at 100.9 seconds on
this machine, with ~145s projected at 50k — is inside a factor of three of that
watchdog. The default event-level watchdog is tighter still:
`CLAUDE_CODE_STREAM_IDLE_TIMEOUT_MS` defaults to `60000`, one minute, "which
abort a streaming model response when there is no progress", clamped between
10 seconds and 30 minutes. **Whether a first-token delay counts as "no
progress" for that watchdog was not established** — the docs describe the byte
watchdog's counting rule precisely and the event watchdog's not at all.

*Token counting is optional but its absence costs inference calls.* From the
feature pass-through table: token counting has "No beta pairing; uses the
`count_tokens` endpoint"; the symptom when absent is "Claude Code falls back to
counting context usage through the messages endpoint"; the remediation is
"Expose the endpoint so token counts don't consume inference requests". LM
Studio and Ollama do not serve it (section 1). On a local runtime, "consume
inference requests" means occupying the one model the machine is holding.

*Requests carry the full Anthropic capability set, not a subset.* "When the
client speaks the Anthropic Messages format, Claude Code sends the full set,
even if your gateway forwards to an Amazon Bedrock or Google Cloud's Agent
Platform upstream." Concretely: `thinking: {"type": "adaptive"}` is sent "for
Claude 4.6 and later, and treats model names it doesn't recognize, such as
gateway aliases, as current models that receive the field", with the symptom
"`400` naming the `thinking` field or the `adaptive` tag when the upstream
model build doesn't accept it". A local model named `qwen3.6-35b-a3b` is
exactly an unrecognised name. oMLX accepts `adaptive`
(`anthropic_models.py:176`); Ollama's supported-field list marks `thinking`
supported without enumerating its tags; llama.cpp does not list `thinking`
among `/v1/messages` options at all. The escape hatch is
`CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1`, documented as: "When disabled, the
`think` parameter is not sent."

Alongside it, `context_management` and `output_config` body fields pair with
beta headers and produce "`400` with `Extra inputs are not permitted`" on an
upstream that does not know them; `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` is
the documented suppressor, though the `env-vars` page's own description of that
variable is narrower ("Currently disables the `/` command namespace system")
than the gateway page's use of it, which is a contradiction between two
first-party pages and is listed as an open question below.

*Error wording is load-bearing.* "Claude Code retries automatically after some
upstream rejections and disables the rejected capability for the rest of the
conversation. Rejections of the `thinking` field, of thinking signatures, and
of mid-conversation system messages all recover this way… The retry logic
matches on the upstream's error wording, so forward error response bodies
unmodified." And separately, the compact-and-retry path "matches Anthropic's
`prompt is too long` wording", so a runtime whose context error says anything
else does not trigger it. llama.cpp's `n_keep > n_ctx` handling is reported as
"an unrecoverable predict error instead of graceful truncation" in LM Studio's
tracker for a Qwen model at 8192 context
([2256](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2256)).

*Prompt caching interacts with a system-prompt block.* Claude Code "prepends a
short attribution block to the system prompt containing the client version and
a fingerprint derived from the conversation", which `api.anthropic.com` strips
positionally and any other upstream "receives as part of the prompt". From
v2.1.181 the block is stable for the lifetime of a conversation behind a custom
base URL, so a prefix cache keyed on it still works; before that it changed per
request. `CLAUDE_CODE_ATTRIBUTION_HEADER=0` omits it. Of the four runtimes,
only oMLX was found to read Anthropic cache markers at all
(`request_has_cache_control`, `server.py:4844`).

Two smaller assumptions: an Anthropic-format base URL "receives a
`HEAD /api/hello` connection-warming probe", which a gateway "can reject
without breaking anything"; and `anthropic-version: 2023-06-01` and
`anthropic-beta` headers arrive on every request. Ollama documents accepting
and ignoring the version header; the other three say nothing about it.

**OpenCode's assumptions were not established.** Its providers doc configures a
base URL and a package and stops; it makes no statement about streaming, tool
use, context windows or output limits, and the AI SDK package it names
(`@ai-sdk/openai-compatible`) documents its own expectations elsewhere, which
was not read. What is visible is that its three local examples all use the
OpenAI-compatible package, so tool use goes over `/v1/chat/completions`
function calling rather than the Anthropic tool schema.

**Codex assumes the Responses API, and that is the whole story.** Beyond the
`wire_api` gate in section 5, Ollama's integration note adds one operational
assumption worth recording: "Codex requires a larger context window. It is
recommended to use a context window of at least 64k tokens." That is Ollama's
statement about Codex, not OpenAI's. `model_supports_reasoning_summaries` is a
documented boolean to "Force Codex to send or not send reasoning metadata",
which implies Codex sends reasoning metadata by default and that a server not
understanding it is a foreseen case. `supports_websockets` defaults to false,
so the WebSocket transport is opt-in rather than assumed.

## 8. Open questions

These could not be settled from primary sources, with what was tried.

1. **Does LM Studio's `/v1/messages` accept any reasoning knob?** The
   Anthropic-compat docs do not mention one; the OpenAI-compat payload list
   does not include `reasoning_effort`; the native `/api/v1/chat` uses a
   differently-named `reasoning` field. LM Studio is closed source, so there is
   nothing to read. Only a request against a running instance settles it —
   send `/v1/messages` with `thinking: {"type": "disabled"}`, then with
   `reasoning_effort: "none"`, then with neither, and compare `prompt_tokens`
   and the content blocks. Issue 2195's method (asking the model to echo its
   own system message, and checking `prompt_tokens` is byte-identical) is the
   one that catches a silently-dropped field.

2. **Does llama.cpp's `/v1/messages` honour `reasoning_effort`,
   `chat_template_kwargs` or `reasoning_format`?** All three are documented
   under `/v1/chat/completions` and none is repeated in the `/v1/messages`
   option list. The server source at `tools/server/` would settle it; only the
   README was read.

3. **Does Claude Code's event-level idle watchdog fire during a long cold
   prefill?** The byte-level watchdog's rule is documented precisely — every
   byte counts, 300s default — and `CLAUDE_CODE_STREAM_IDLE_TIMEOUT_MS`
   defaults to 60s for watchdogs that "abort a streaming model response when
   there is no progress", without defining progress. Issue 19's measurements
   put a 50k-token cold prefill near 145 seconds on this machine. A run against
   a real cold prefill is what answers it.

4. **Do LM Studio, Ollama or llama.cpp emit SSE keep-alive pings during
   prefill?** This is the other half of question 3 and is the thing that would
   make the byte watchdog harmless. Nothing in any of the three documents says.
   oMLX's `/v1/messages` sends `message_start` before generation begins
   (`server.py:4864`), which is at least one byte early, but whether anything
   follows during a long prefill was not read.

5. **Whether oMLX's visible-reasoning behaviour in issue 19 was untagged prose
   or a parser miss.** Section 3 argues from `ThinkingParser`'s source that it
   matches only literal `<think>`/`</think>`, and that "Thinking Process: 1.
   Analyze the request…" carries no tag. That is inference. Capturing the raw
   SSE stream for the same prompt and grepping for `<think>` confirms or kills
   it.

6. **Whether `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` suppresses body fields
   or only a slash-command namespace.** The gateway pages use it repeatedly as
   the remedy for `400`s naming `context_management` and beta tool fields; the
   `env-vars` page describes it as "Currently disables the `/` command
   namespace system. This variable is for testing purposes and is not
   user-facing." Two first-party pages, two descriptions. Only observation of
   the request body settles which is current.

7. **Whether Codex CLI has a `model_max_output_tokens` key.** The config
   reference's structure mentions it; its table of entries does not carry it.
   The `Config` struct in `codex-rs/config/` would settle it; only
   `model-provider-info/src/lib.rs` was read.

8. **What OpenCode assumes of a server.** Its providers doc states nothing
   about streaming, tool-call format, context limits or output limits. Its
   `models.mdx`, its `@ai-sdk/openai-compatible` dependency, and the models.dev
   metadata it reads were all unread, and any of them could carry the answer.

9. **Whether OpenCode's built-in `anthropic` provider works against a local
   `/v1/messages`.** The doc shows `baseURL` being overridable "for any
   provider" with an `anthropic` example, but every local-server example uses
   the OpenAI-compatible package instead. Whether the Anthropic AI SDK provider
   tolerates a server with no `count_tokens` and no `anthropic-beta` handling
   is unaddressed anywhere found.

10. **What LM Studio versions past 0.4.1 changed in these surfaces.** The docs
    repo's last commit is 2026-07-20 and its changelog stops at 0.4.1, while
    bug reports name 0.4.19 and 0.4.20. Everything asserted here about LM
    Studio describes documented 0.4.1 behaviour, and three open regressions on
    the `/v1/messages` path (2164, 2204, 2236) say the surface has moved since.
