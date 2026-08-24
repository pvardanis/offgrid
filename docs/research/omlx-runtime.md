# oMLX as a runtime: which features fit one pool of memory

Primary-source research, gathered 2026-08-24, into whether the oMLX runtime
(`github.com/jundot/omlx`) could hold the coding model on this machine and help
the cold-start problem `docs/research/local-agent-latency.md` describes. The only
source read is oMLX's own repository — its source and its README — at `main`,
commit `f244ac0`, taken as a shallow clone and read on disk. Every claim is
traced to a file and line in that repo. Nothing was loaded, no model was run, no
benchmark was taken. Inference is labelled as inference.

The machine constraint drives the whole read: **it cannot hold two models in
memory at once — it crashes.** So each oMLX feature is sorted into single-model
(usable here) or two-model (off-limits), and the sort is made from the code that
loads the weights, not from the feature's description.

## The answer

**Yes, oMLX runs single-model, and by default it is single-model — but its one
dramatic cold-prefill accelerator is a two-model feature and is off-limits
here.** Every weight-doubling feature oMLX has — SpecPrefill, DFlash, VLM MTP —
is opt-in, defaults to `False`, and is mutually exclusive with the others
(`omlx/model_settings.py:254`, `:262`, `:309`; the exclusivity guard at
`:339`–`:370`). A plain load holds one model. What oMLX then offers a
single-model caller that LM Studio does not is real but incremental: a reasoning
**off** knob on the Anthropic surface (`thinking.type: "disabled"`), a working
`/v1/messages/count_tokens`, a genuinely cross-session disk prefix cache, and
Qwen3.5-specific prefill kernels. What it cannot offer here is **SpecPrefill**,
the sparse-prefill path that would actually cut the ~25k-token cold prefill —
because its token scoring requires a second resident draft model, and the one
mechanism that would reuse the system/tool prefix across turns (issue #2177) is
wired to run only inside that same draft-bearing flow.

Confidence: **high on the single-vs-two-model sort** (it rests on the load
paths, which are unambiguous) and **low on the size of the single-model win**
(no prefill was timed; whether oMLX's Qwen3.5 kernels beat LM Studio's MLX engine
on this machine's cold prefill is unmeasured and is the question that decides
whether a runtime swap is worth anything).

One caution on reading this repo: oMLX's own primary sources are the only trusted
input, and the sort below turns entirely on which function loads a second set of
weights. Where a feature is only proven by a test that itself loads two models,
that is called out — a passing test is not evidence the feature is reachable on
one pool of memory.

## What was read, and at which version

| Thing | Version | How that was determined |
| --- | --- | --- |
| oMLX repository | `main` at `f244ac0` ("fix(dflash): honor repetition context size (#3011)") | `git clone --depth 1`, `git log -1`, read on 2026-08-24 |
| README (30x DSA claim) | same commit | `README.md`, 439 lines |
| `docs/research/local-agent-latency.md` | working tree | treated as primary for what this machine already measured and for the open questions (#40/#5, #43) |
| `docs/research/adapter-surfaces.md` | working tree | treated as primary for what LM Studio's surface lacks (no reasoning knob, no `count_tokens`) |

oMLX requires "macOS 15.0+ (Sequoia), Python 3.11–3.13, and Apple Silicon"
(`README.md:94`), which matches this machine's platform.

## 1. SpecPrefill needs a second resident model. **Confirmed — off-limits here.**

The sparse-prefill path does not sparsify by itself; it scores every candidate
token with a **separate draft model** and keeps the important ones. The draft is
a distinct checkpoint on disk, loaded as its own set of weights and handed to the
scheduler:

- `omlx/model_settings.py:255` — `specprefill_draft_model: Optional[str] = None
  # Path to draft model (must share tokenizer)`. It is a path, not a mode.
- `omlx/engine/batched.py:600`–`651` — when `specprefill_enabled and
  specprefill_draft`, a loader thread runs `lm_load_compat(specprefill_draft,
  …)` (`:627`) and `set_specprefill_draft_model(draft_model, …)` (`:649`). There
  is **no memory check** on this path.
- `omlx/scheduler.py:8471`–`8479` — `_try_specprefill_scoring` returns
  immediately `if self._specprefill_draft_model is None`. No draft, no scoring.
- `omlx/specprefill/draft.py:42`–`55` — `run_specprefill_draft_scoring` takes
  `draft_model` and calls `score_tokens(draft_model, …)` (`:114`). The draft is
  the thing that produces the importance ranking; the target never scores itself.

There is **no self-draft, shared-weights, or quantized-head option in the code.**
The draft can be smaller and quantized — the validation pairs use a 4B draft
against a 27B/35B target — but it is a second set of weights held alongside the
target. The repo says so in its own words, in the real-model test that guards the
feature:

> "the known validation pairs use a 27B or 35B target plus a 4B draft and
> consequently need substantial Apple Silicon unified memory."
> — `tests/integration/test_specprefill_static_prefix_real_model.py:22`–`24`

**Verdict:** SpecPrefill is a two-model feature. On this machine it cannot be
enabled, and — a sharper point — the draft load at `batched.py:627` bypasses the
engine pool's memory admission (section 5), so turning it on would attempt the
second load with no guard in front of it. *Inference, labelled:* on Apple Silicon
a unified-memory over-commit tends to hard-fault Metal rather than raise a Python
error, so this would present as the crash the constraint names, not as the caught
`except` at `batched.py:655`. That inference is not settled from source and must
never be tested here, because the test is the crash.

## 2. Static system/tool prefix reuse (#2177) is cache-only — but wired behind the draft

This is the mechanism `target.py` describes: the first request stores the
prefetched system state, later requests restore it and skip the target's
system-prefill loop. Read on its own, it **is single-model**: it touches only
`target_model` and an `exact_prefix_cache`, never a draft.

- `omlx/specprefill/target.py:70`–`77` — the opt-in parameters:
  `extract_cache_states`, `exact_prefix_cache`, `static_prefix_tokens`.
- `:117`–`131` — `exact_prefix_cache.restore_exact_prefix(...)` returns a cache
  that replaces the system-prefill loop; on a hit, `static_prefix_cached_tokens`
  is set and the loop at `:135`–`163` is skipped.
- `:169`–`188` — on a miss, the just-computed system KV is stored with
  `store_exact_prefix(...)` for the next turn.

None of that needs a draft. **But it is not reachable single-model as shipped.**
`run_specprefill_target_prefill` has exactly one caller —
`omlx/scheduler.py` (the `from .specprefill.target import …` inside the
specprefill branch) — and that branch runs only when specprefill is active, which
requires the resident draft of section 1. `restore_exact_prefix` /
`store_exact_prefix` are called from nowhere else in `omlx/` (grep: only
`specprefill/target.py`). So the cold-start-relevant lever the task hoped for is
architecturally single-model but operationally chained to the two-model feature.
Using it here would take a code change to invoke the target static-prefix path
outside specprefill — that is a fork of oMLX, not a configuration.

## 3. The tiered prefix cache: single-model, disk-backed, cross-session — and no more drift-robust than LM Studio

This is the general cache the normal (non-specprefill) decode path uses, and it
**is** single-model and genuinely cross-session.

**Single-model, disk-backed.** oMLX "only supports paged SSD-based caching …
When paged SSD cache is disabled, no oMLX caching is performed"
(`omlx/cache/factory.py:8`–`11`). Blocks are isolated per model by name
(`create_paged_ssd_cache` puts each model in its own subdir,
`factory.py:120`–`121`; the block hash also folds in the model name, below).

**Cross-session, survives restart.** `PagedSSDCacheManager` construction
(`__init__` at `omlx/cache/paged_ssd_cache.py:1556`) runs `_scan_existing_files()`
(call at `:1710`, method at `:2200`), which
walks the cache dir's `*.safetensors` blocks and rebuilds the index, indexing
only blocks compatible with the currently loaded model/layout
(`:2200`–`2247`). The module header lists "Startup scan to reuse existing cache
files" as a feature (`:12`). So a prefix stored in one session is available to a
later session after a full restart. LM Studio's disk cache is likewise
cross-session (`local-agent-latency.md` §2); this is the same class of thing, not
a new one.

**How a prefix is keyed.** `compute_block_hash`
(`omlx/cache/paged_cache.py:78`–`119`) is a chained SHA-256, vLLM-style: for each
block it hashes `model_name`, then the parent block's hash, then
`str(tuple(token_ids))`, then any `extra_keys` (LoRA, VLM image). The default
block is 64 tokens (`omlx/cache/factory.py:42`, `CacheConfig.block_size = 64`).
A prefix hits iff its leading token blocks are byte-for-byte the ones stored,
in order.

**Would Claude Code's per-session drift miss here too? Yes, the same way.** The
keying is a content hash of the actual tokens — exactly the property LM Studio's
256-token block cache has (`local-agent-latency.md` §2). It is **not** more
robust to prefix drift. If Claude Code's system/tool prefix varies between
sessions, oMLX's turn-1 misses for the same reason LM Studio's does; if the
prefix is byte-stable (offgrid already takes the two steps that stabilise it —
`--exclude-dynamic-system-prompt-sections` and the per-conversation attribution
block), then turn-1 of a **later** session can hit oMLX's disk cache just as it
can LM Studio's. The first-ever session with a never-seen prefix always pays the
full cold prefill either way. oMLX changes nothing about the turn-1 story on the
keying axis.

**Opt-in, off by default.** `PagedSSDCacheConfig.enabled: bool = False`
(`omlx/config.py:112`). To get any cross-session reuse, offgrid would have to
start the server with the paged SSD cache turned on and a `cache_dir` set
(`config.py:113`–`115`).

## 4. Qwen 3.5 support: first-class in code and unit-tested, but not proven single-model here

Qwen3.5 is not a bolted-on code path in oMLX — it is a first-class family with
its own kernels and its own cache handling, and it uses **oMLX's own cache, not
mlx-lm's** (`factory.py:8`–`11`), which is why the mlx-lm issue-980 failure
(`local-agent-latency.md` §5) is upstream's problem, not necessarily oMLX's.

Evidence it is real, not aspirational:

- Dedicated prefill kernels: `omlx/custom_kernels/qwen35_prefill/` (Metal
  sources: `qwen35_attention.metal`, `qwen35_qmm.metal`, `gdn.py`, `fast.py`).
- Sliding-window (rotating) cache handling in the prefix cache: a
  supersede-on-extend lineage for rotating models
  (`omlx/cache/prefix_cache.py:231`–`236`, `_rotating_tip_lineage`), and rotating
  families explicitly kept off the GDN-sidecar split path
  (`:302`–`328`).
- Hybrid detection: `ModelCacheConfig.from_cache_list` reads each layer's cache
  type, tracks `ROTATING_KVCACHE` window sizes and `CacheList` sub-caches, and
  sets `is_hybrid` when more than one cache type is seen
  (`omlx/cache/hybrid_cache.py:86`–`128`). Qwen3.5's mix of full-attention and
  GDN (gated-delta) layers is exactly this hybrid shape.
- GDN (linear-attention) state is handled through a dedicated split/sidecar path
  with its own tests (`omlx/cache/prefix_cache.py:293`–`413`;
  `tests/test_prefix_cache_gdn_split.py`,
  `tests/test_prefix_cache_rotating_tip_strip.py`, `tests/test_hybrid_cache.py`).

**Code path exists and is unit-tested. Proven-to-work on a real Qwen3.5 through
the normal single-model prefix cache is what I cannot show from source.** The
only real-model proof in the repo that a Qwen3.5 hybrid cache "restore[s] their
recurrent state, rotating-cache metadata, MLX stream ownership, and target
positions correctly" is
`tests/integration/test_specprefill_static_prefix_real_model.py:6`–`9` — and that
test loads a Qwen3.6 target **plus** a Qwen3.5 draft (two models). Whether the
plain, single-model paged-SSD prefix cache round-trips `qwen3_5_moe` GDN state
correctly on this machine is not demonstrated by any single-model test I found;
it is a code claim backed by unit tests with synthetic caches. That distinction
is the honest one: the machinery is there and tested at unit level; the
single-model real-model proof is not in the repo.

## 5. Load and unload: HTTP-reachable, and the pool evicts before it loads

oMLX exposes model management over HTTP on the main server, guarded by the API
key — offgrid loads over HTTP (`holding.py`), so this is the right surface:

- `omlx/server.py:2959` — `POST /v1/models/{model_id}/load` (`verify_api_key`),
  blocks until loaded, and maps `ModelTooLargeError`/`InsufficientMemoryError` to
  HTTP 507 (`:2979`–`2982`).
- `omlx/server.py:2943` — `POST /v1/models/{model_id}/unload` (`verify_api_key`).
- The admin surface duplicates these at `omlx/admin/routes.py:2079` (load) and
  `:2014` (unload), the latter with a 202 "queued" path when the model is busy.

This satisfies offgrid's `ensure_only` shape: hold one, let go. Two nuances:

1. **The pool holds many models, but it evicts before it loads.** The engine pool
   does "Pre-load memory checking (evict before load, not after)" and "LRU
   eviction when memory limit is exceeded" (`omlx/engine_pool.py:249`–`251`;
   the eviction loop at `:1466`–`1534`). So loading model B evicts LRU model A
   rather than over-committing — favourable for the one-pool constraint. offgrid
   should still unload explicitly for determinism rather than lean on LRU.
2. **This guard protects target loads, not draft loads.** The pool's admission is
   in front of `get_engine`; the SpecPrefill draft is loaded *inside* the target
   engine (`batched.py:627`, section 1) and never passes the pool's memory check.
   The pool cannot save you from the two-model features — only from two targets.

*Inference, labelled:* `verify_api_key` means offgrid must present the server's
API key (or run the server in its documented no-auth mode) to reach load/unload
— the same as any authenticated runtime. Not read: whether offgrid's current
`holding.py` carries a key. Flag if the LM Studio path assumed none.

## 6. The Anthropic surface has a reasoning off-knob. **Confirmed — this is the standout single-model win.**

`local-agent-latency.md` §6 open question 5 and adapter-surfaces open question 1
record that LM Studio publishes no reasoning knob on its `/v1/messages`. oMLX
does.

- `omlx/server.py:5480` — `@app.post("/v1/messages")`, the Anthropic Messages
  endpoint.
- `omlx/api/anthropic_models.py:173`–`177` — `ThinkingConfig.type:
  Literal["enabled", "disabled", "adaptive"] = "enabled"`, plus optional
  `budget_tokens`. `MessagesRequest.thinking` carries it (`:200`).
- `omlx/server.py:5535`–`5542` — the request's `thinking.type` is mapped to the
  chat template: `"enabled"`/`"adaptive"` → `enable_thinking=True`; `"disabled"`
  → `enable_thinking=False`. This is the on/off knob (`#40`/`#5`).
- `omlx/server.py:5873` — `@app.post("/v1/messages/count_tokens")` exists and
  uses the loaded model's tokenizer. That closes the gap
  `local-agent-latency.md` §3 names: LM Studio has no `count_tokens`, so Claude
  Code burns inference requests counting context. oMLX's `Capabilities` would set
  `counts_tokens=True`, unlike LM Studio's `False`.
- README confirms the surface and adaptive thinking (`README.md:271`, `:277`).

**Three caveats, all load-bearing:**

1. `enable_thinking` is a **chat-template kwarg** — it only suppresses reasoning
   if the model's chat template honours it. Qwen3.5's does; a model whose
   template ignores it would keep reasoning regardless. So the knob's effect is
   model-conditional, not a hard server-side gate.
2. **Model settings can force it either way.** `forced_ct_keys(ms)` is checked
   before the mapping (`server.py:5533`, `:5537`), so an oMLX per-model setting
   can pin `enable_thinking`. That is the clean place for offgrid to set the
   default **off** — it does not depend on what the agent sends.
3. Claude Code, behind a gateway alias, sends `thinking: {"type": "adaptive"}`
   by default (`local-agent-latency.md` §H4), which oMLX maps to
   `enable_thinking=True` — reasoning **on**. So to get the win, offgrid must
   either force it off in oMLX's model settings (caveat 2) or have the Claude
   Code adapter send `"disabled"`. It is not off for free.

*Inference, labelled:* the caveat-2 path (force off in model settings) is the one
that binds independently of the agent and looks like the largest single-model,
config-only latency lever oMLX offers over LM Studio, given decode here runs at
tens of tokens a second (`local-agent-latency.md`). It is unmeasured.

## 7. The 30x DSA claim is GLM-5.2-specific and does not transfer to Qwen 3.5. **Confirmed.**

The README states the figure against one architecture, in its own words:

> "for GLM-5.2 the fused DSA prefill is roughly 30x faster with the kernels
> (measured 845 vs ~29 tok/s on an M3 Ultra), and the fallback also uses more
> memory (#2137)."
> — `README.md:98`–`100`

DSA is DeepSeek Sparse Attention, a GLM-5.2 architecture feature; its model code
lives at `omlx/patches/mlx_lm_mtp/glm_moe_dsa_model.py`, and the memory monitor
sizes a GLM-5.2-specific indexer/sparse-attention cache (`omlx/memory_monitor.py`,
the GLM-5.2 indexer accounting). Qwen3.5 is a different family: it runs the
`qwen35_prefill` kernels and the GDN hybrid path (section 4), not DSA. **The 30x
does not apply to `qwen3_5_moe`.** Qwen3.5 has its own custom kernels that may
speed its prefill, but the repo gives no comparable multiplier for them, and a
plain `pip install` builds none of these kernels (`README.md:96`–`98`) — the
official DMG or a `--with-custom-kernel` build is required, or the family "silently
fall[s] back to much slower generic paths."

## 8. What could not be determined, and the single-model experiments that would

Every experiment below must load **one model only**. The features that require a
second resident model — SpecPrefill (§1), DFlash, VLM MTP — are **untestable on
this machine** and must not be enabled; the test would be the crash the
constraint names.

1. **Whether oMLX's single-model Qwen3.5 cold prefill beats LM Studio's MLX
   engine on this machine.** This is the number that decides whether a runtime
   swap buys anything, since the dramatic accelerator (SpecPrefill) is
   off-limits. *Experiment:* build oMLX with the Qwen3.5 custom kernels, load one
   Qwen3.5 model, send one ~25k-token cold prompt, read time-to-first-token; do
   the same against LM Studio holding the same model. One model at a time, never
   both. Nothing in the repo settles this — it is a rate on specific hardware.

2. **Whether the normal single-model paged-SSD prefix cache round-trips
   `qwen3_5_moe` GDN/rotating state correctly.** §4 shows unit tests and kernels,
   not a single-model real-model proof. *Experiment:* enable the paged SSD cache
   (`config.py:112`), one Qwen3.5 model, send a prefix twice across a server
   restart, and confirm the second turn reports the prefix as cache-restored and
   produces identical logits/first token. Single model throughout.

3. **How much the reasoning off-knob actually saves here.** §6 establishes the
   knob exists and how to bind it; it does not measure the wall-clock. *Experiment:*
   one model, force `enable_thinking=False` in oMLX model settings, send one
   agentic turn; repeat with it on; compare completion tokens and total time.
   Single model.

4. **Whether offgrid's `holding.py` can authenticate to oMLX's load/unload.** §5
   notes `verify_api_key` guards the endpoints. *Not an experiment so much as a
   read:* confirm offgrid can carry the key, or that oMLX's no-auth mode is
   acceptable, before assuming the `ensure_only` shape drops in.

5. **Whether the #2177 static-prefix reuse could be reached single-model at all.**
   §2 shows it is cache-only in principle but wired behind the draft. *Not
   testable as configuration* — it would need a code change to oMLX to invoke the
   target static-prefix path outside the specprefill flow. That is a fork
   decision, and it should be recorded as one in `docs/decisions.md` if pursued,
   not slipped in as a config toggle.

**Untestable on this machine, stated plainly:** SpecPrefill, DFlash, and VLM MTP
each hold a second model and cannot be exercised here. Any claim about their
latency on this hardware is unreachable by us and must be sourced from oMLX's own
numbers or left open.
