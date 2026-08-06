# Models

This is research, not a decision. It records what was measured on this machine,
what the vendors claim, and what follows arithmetically from the two. offgrid
does not choose a model; this is here so that a person choosing one has the
numbers in front of them instead of vendor marketing.

Written 2026-08-06. Every speed figure is labelled **measured**, **claimed** or
**derived**. Derived figures are arithmetic on measured ones and are not
evidence.

## The question

Which currently-released open-weight model gives the most useful work per second
when driving Claude Code against LM Studio on this machine?

Not which model scores highest. The agent sends a ~25,000-token preamble of tool
definitions and skill listings before the user types anything, and sessions reach
50k+ tokens. A model that is three points better on SWE-bench and four times
slower to read the prompt is a worse tool. The question is quality per second,
and the second half of that is decided by this machine's memory bandwidth and
GPU, not by the model's benchmark card.

## The constraints from this machine

Apple M1 Max, 24-core GPU, 64GB unified memory, ~400 GB/s memory bandwidth. GPU
wired limit 56GB; offgrid reports 60GB usable. Runtime is LM Studio with the MLX
engine.

Measured on this machine, through LM Studio's own reported statistics
(`/api/v0/chat/completions` returns `stats.time_to_first_token` and
`stats.tokens_per_second`):

| Model | Quant | Measurement |
| --- | --- | --- |
| `qwen/qwen3.6-35b-a3b` | MLX 4-bit, 19GB | decode 52.0 tok/s @ 370 tokens, 47.5 @ 3.5k, 45.5 @ 14k, 35.8 @ 49k |
| `qwen/qwen3.6-35b-a3b` | MLX 4-bit, 19GB | cold prefill 389 tok/s @ 3.4k, 351 @ 13.6k, 352 @ 33.9k, 251 @ 71.6k |
| `qwen/qwen3.6-35b-a3b` | MLX 4-bit, 19GB | a 49,450-token prompt already in cache: 1.1s. A mid-history edit re-prefills the tail at ~273 tok/s |
| `lfm2.5-1.2b-instruct-mlx` | MLX 8-bit dense | decode 191 tok/s at short context |
| `qwen3-0.6b-mlx` | MLX 4-bit dense | decode 169 tok/s at short context |

Two efficiency constants come out of these, and everything downstream rests on
them.

**Dense: 239 GB/s achieved, 60% of peak.** The 1.2B model at 8-bit reads about
1.25 GB of weights per token. 191 tok/s × 1.25 GB = 239 GB/s. The 0.6B model is
not usable for this: at 169 tok/s over ~0.35 GB it achieves only 59 GB/s, which
says it is bound by kernel dispatch, not bandwidth.

**MoE with 3B active: 85 GB/s achieved, 21% of peak.** The 35B-A3B at 4-bit
stores 19 GB for 35B parameters, so 0.543 bytes per parameter; 3B active
parameters is 1.63 GB read per token. 52.0 tok/s × 1.63 GB = 85 GB/s.

The dense constant survives an independent check. The llama.cpp Apple Silicon
performance table measures LLaMA 7B at Q4_0 on an M1 Max at 61.19 tok/s text
generation ([llama.cpp discussion
#4167](https://github.com/ggml-org/llama.cpp/discussions/4167)). Q4_0 7B is about
3.56 GB, so 61.19 × 3.56 = 218 GB/s, within 9% of 239 across a 6× jump in model
size. That table's machine has a 32-core GPU rather than 24, which matters for
prefill and not for decode.

The MoE constant also survives an independent check, on this exact hardware. The
`local-llm-bench` project publishes measurements taken on an M1 Max, 64GB,
24-core GPU: Qwen3.5-35B-A3B at MLX 4-bit under LM Studio generates at 56.6 tok/s
([famstack-dev/local-llm-bench](https://github.com/famstack-dev/local-llm-bench)).
That is 9% above the 52.0 measured here on the 3.6 version of the same
architecture.

## Candidates

Weights sizes marked *(measured)* were read off this machine or off the model
card's own file listing. The rest are derived at 4.4 bits per weight, which is
the ratio the two measured MLX 4-bit builds actually show (19/35 and 15.0/27).

KV cache is computed from each model's published `config.json`, at fp16, counting
only the layers that keep a growing cache. The arithmetic is in the next section.

| Model | Released | Total / active | Quant | Weights | KV @ 50k | Decode tok/s | Prefill tok/s | Coding benchmark |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.6-35B-A3B | 2026-04-16 | 35B / 3B MoE | MLX 4-bit | 19 GB *(measured)* | 1.02 GB | **52.0 (measured)** | **351 (measured)** | SWE-bench Verified 73.4, Terminal-Bench 2.0 51.5 (self-reported) |
| Qwen3.6-35B-A3B | 2026-04-16 | 35B / 3B MoE | MLX 8-bit | 35 GB *(measured)* | 1.02 GB | 29 *(derived)* | ~351 *(derived)* | same weights, see quantization below |
| Qwen3.6-27B | 2026-04-22 | 27B dense | MLX 4-bit | 15.0 GB *(measured)* | 3.28 GB | 16 *(derived)* | 103 *(derived)* | SWE-bench Verified 77.2, Terminal-Bench 2.0 59.3 (self-reported) |
| Qwen3.6-27B | 2026-04-22 | 27B dense | MLX 8-bit | 29.5 GB *(measured)* | 3.28 GB | 8 *(derived)* | ~103 *(derived)* | as above |
| Qwen3-Coder-Next | 2026-02-03 | 80B / 3B MoE | MLX 4-bit | 44.8 GB *(measured)* | 1.23 GB | ≤52 *(derived)* | ≤351 *(derived)* | SWE-bench Verified 70.6, Terminal-Bench 2.0 36.2 (self-reported) |
| Gemma 4 26B-A4B | 2026-07 | 25.2B / 3.8B MoE | 4-bit | ~13.9 GB *(derived)* | 0.61 GB | 42 *(derived)* | 323 *(derived)* | LiveCodeBench v6 77.1 (self-reported). No SWE-bench published |
| Gemma 4 31B | 2026-07 | 30.7B dense | 4-bit | ~16.9 GB *(derived)* | 2.47 GB | 14 *(derived)* | 90 *(derived)* | LiveCodeBench v6 80.0 (self-reported); SWE-bench Verified 52.0 (third-party) |
| Devstral Small 2 | 2025-12-09 | 24B dense | 4-bit | ~13.2 GB *(derived)* | 8.19 GB | 18 *(derived)* | 116 *(derived)* | SWE-bench Verified 68.0 (self-reported) |
| gpt-oss-120b | 2025-08-05 | 117B / 5.1B MoE | MXFP4 | 63 GB | — | — | — | **Does not fit.** 63 GB exceeds the 56 GB wired limit before any cache |

Sources for the benchmark column, in order: the [Qwen3.6-35B-A3B model
card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) and the comparison table on
the [Qwen3.6-27B model card](https://huggingface.co/Qwen/Qwen3.6-27B), which is
where both Qwen figures and the Gemma4-31B SWE-bench figure come from; the
[Qwen3-Coder-Next model card](https://huggingface.co/Qwen/Qwen3-Coder-Next); the
[Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4); the
[Devstral 2 announcement](https://mistral.ai/news/devstral-2-vibe-cli/); the
[gpt-oss-120b model card](https://huggingface.co/openai/gpt-oss-120b) for the
63 GB MXFP4 footprint.

Every coding number in that table is self-reported by the model's vendor. This is
not a hedge — it is the actual state of the evidence, and the next section says
what happens when you check it against a leaderboard that runs the models itself.

## The benchmark numbers are weaker evidence than they look

The official [Terminal-Bench 2.0
leaderboard](https://www.tbench.ai/leaderboard/terminal-bench/2.0) has no Qwen3.6
entry at all. Its open-weight rows, all under the Terminus 2 scaffold, run: GLM 5
(744B) 52.4%, Kimi K2.5 43.2%, MiniMax M2.5 42.2%, DeepSeek-V3.2 39.6%, GLM 4.7
33.4%, Qwen 3 Coder 480B 23.9%, GPT-OSS-120B 18.7%.

Qwen self-reports 59.3 on Terminal-Bench 2.0 for the 27B and 51.5 for the
35B-A3B. If those held under the leaderboard's own scaffold, a 27B dense model
would sit above a 744B one. That is possible and it is also exactly the shape of
result that a tuned in-house harness produces. Nothing here can distinguish the
two, and no independent run of either Qwen3.6 model exists to check against.

The same applies to SWE-bench Verified. Qwen's 77.2 for the 27B is measured by
Qwen, against a Claude 4.5 Opus figure of 80.9 that Qwen also measured. Treat the
ordering within Qwen's own table as informative — the 27B beats the 35B-A3B by
3.8 points under one harness — and treat the absolute numbers as unverified.

For function calling specifically, which is the failure mode that costs whole
turns, the [Berkeley Function Calling
Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) renders its table
client-side and could not be read here. The one BFCL number found from a primary
source is on the [mlx-community Qwen3.6-27B-OptiQ-4bit
card](https://huggingface.co/mlx-community/Qwen3.6-27B-OptiQ-4bit): BFCL-V3
simple, 200 calls, 93.0% for the uniform 4-bit build. That is a subset of one
version of the benchmark run by a quantizer, not a leaderboard placement, but it
is the only direct evidence that the 27B at 4-bit calls tools reliably.

## The KV cache turned out not to be the constraint

The instruction to compute KV cache per model from its architecture was the right
one, and the answer is that for four of the seven candidates it is nearly free.

**Qwen3.6-35B-A3B.** From its
[config.json](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/blob/main/config.json):
40 layers, of which only 10 are `full_attention` — the other 30 are
`linear_attention` (Gated DeltaNet), whose state is a fixed-size recurrence, not
a growing cache. The full-attention layers have `num_key_value_heads: 2` and
`head_dim: 256`. Per token per layer: 2 tensors × 2 heads × 256 × 2 bytes =
2,048 B. Across 10 layers, 20,480 B/token — 20 KiB per token. At 50k tokens,
**1.02 GB**; at 100k, 2.05 GB. The 30 DeltaNet layers hold
32 × 128 × 128 × 4 bytes = 2.1 MB each, 63 MB total, constant at any context
length.

**Qwen3.6-27B.**
[config.json](https://huggingface.co/Qwen/Qwen3.6-27B/blob/main/config.json): 64
layers, 16 of them full attention, `num_key_value_heads: 4`, `head_dim: 256`.
2 × 4 × 256 × 2 = 4,096 B per layer per token, × 16 = 65,536 B/token — 64 KiB.
At 50k, **3.28 GB**; at 100k, 6.55 GB. Three times the MoE's cache, and still
small next to the weights.

**Qwen3-Coder-Next.**
[config.json](https://huggingface.co/Qwen/Qwen3-Coder-Next/blob/main/config.json):
48 layers, 12 full attention, 2 KV heads, head_dim 256 → 24,576 B/token.
At 50k, **1.23 GB**.

**Gemma 4 26B-A4B.**
[config.json](https://huggingface.co/google/gemma-4-26B-A4B/blob/main/config.json):
30 layers, 5 full and 25 sliding at a 1,024-token window, and
`attention_k_eq_v: true` — K and V are one tensor, halving the cache. Full
layers: 1 × 2 × 512 × 2 = 2,048 B × 5 = 10,240 B/token → **0.51 GB** at 50k. The
sliding layers are capped by their window at 25 × 1,024 × 4,096 = 105 MB,
constant. Gemma 4 31B, by the same method, is 10 full layers at 4 KV heads and
head_dim 512 → 40,960 B/token → **2.05 GB**, plus 419 MB of capped sliding cache.

**Devstral Small 2** is the exception and shows what the others avoid. Its
[config.json](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512/blob/main/config.json)
has `sliding_window: null` — all 40 layers are full GQA attention, 8 KV heads,
head_dim 128. That is 163,840 B/token, **160 KiB per token**: 8.19 GB at 50k and
16.4 GB at 100k. A 13 GB model carrying a 16 GB cache.

The conclusion is that hybrid attention has made the 50k–100k cache requirement
stop mattering. Everything in the table except gpt-oss-120b fits in 56 GB with
room to spare, and the model that comes closest to trouble is the smallest dense
one. Memory is no longer the axis on which to choose.

## MoE versus dense is the whole decision

With memory removed as a constraint, the choice reduces to: pay 3–4× in speed for
Qwen's claimed 3.8 SWE-bench points and 7.8 Terminal-Bench points.

**Decode.** The dense constant of 239 GB/s divided by weights size gives 239/15.0
= **16 tok/s** for the 27B at 4-bit, against 52 tok/s measured for the 35B-A3B.
A 3.3× penalty. At 8-bit the 27B falls to 239/29.5 = 8 tok/s.

**Prefill.** This is compute-bound rather than bandwidth-bound, so it scales with
active parameters. The anchor is llama.cpp's measured 530 tok/s prompt processing
for a 7B dense at Q4_0 on an M1 Max — but on a 32-core GPU, so scaling by core
count gives 530 × 24/32 = 398 tok/s on this machine. Scaling that by parameter
count: 398 × 7/27 = **103 tok/s** for the 27B.

A cold 50,000-token prompt at 103 tok/s takes 485 seconds. Eight minutes before
the first token. The measured figure for the 35B-A3B is 351 tok/s, so the same prompt costs
about 145 seconds.

That prefill arithmetic also produces an independent measurement of the MoE
penalty. Pure compute scaling would predict 398 × 7/3 = 929 tok/s for a 3B-active
model. The measured figure is 351. The MoE gives back 62% of its theoretical
prefill advantage to routing and expert-gather overhead — which is the same story
the 22%-versus-60% decode gap tells, arrived at along a different route. Both say
a MoE with few active parameters wins on paper and hands back roughly half of it
in practice, and still wins by a wide margin.

**What the prefix cache does to this.** A 49,450-token prompt measures 1.1
seconds warm against 122 seconds cold. In a session that stays warm, prefill
disappears and only the 3.3× decode penalty is left. The cold cost is paid once
per session and again whenever the cache is invalidated — which offgrid
guarantees at least once per run, since it lets go of the model when the agent
exits and a load evicts the prefix cache. So the 27B's real cost is eight minutes
at session start plus 3.3× on every turn thereafter.

**Whether the quality buys it back.** The argument for the dense model is that
better tool-calling wastes fewer turns, and a wasted turn costs tens of seconds.
That argument has to clear a high bar: at 3.3× slower per turn, the 27B has to
finish a task in under 30% of the turns to break even. Qwen's own numbers put it
at 59.3 versus 51.5 on Terminal-Bench — a 15% relative improvement in tasks
solved, not a 70% reduction in turns taken. The arithmetic does not come close.

The dense 27B is the better model. On this machine it is the worse tool, unless
there is a specific task the 35B-A3B cannot complete at any number of turns.

Qwen3-Coder-Next is the other MoE that fits, and it is dominated rather than
close: 70.6 SWE-bench Verified and 36.2 Terminal-Bench against the 35B-A3B's 73.4
and 51.5, for 44.8 GB instead of 19 GB. Its 3B active count predicts similar
speed, but with 512 experts spread over 44.8 GB instead of 256 over 19 GB, memory
locality is worse and 52 tok/s should be read as a ceiling. There is no reason to
run it.

Gemma 4 26B-A4B is the one candidate that was not ruled out and was not
investigated far enough. It is a 3.8B-active MoE with the smallest KV cache in the
table, and derives to 42 tok/s decode and 323 tok/s prefill — the same class as
the 35B-A3B. Google publishes no SWE-bench or agentic-coding number for it, only
LiveCodeBench v6 77.1, and LiveCodeBench measures competitive-programming
problems rather than repository work. The already-downloaded `google/gemma-4-e4b`
is a different matter: at LiveCodeBench v6 52.0 and Tau2 42.2 against the
27B's 83.9 and Qwen's agentic scores, it is below the floor for driving an agent.

## Quantization width does not pay for itself

Going from 4-bit to 8-bit on the 35B-A3B costs 16 GB of memory and halves decode
from 52 to 29 tok/s, derived from the same bandwidth constant.

No primary source with a head-to-head MLX 4-bit versus 8-bit perplexity or
benchmark table was found, for any model. That is a genuine gap and it is stated
as one.

The nearest primary evidence points the other way. The [mlx-community
Qwen3.6-27B-OptiQ-4bit
card](https://huggingface.co/mlx-community/Qwen3.6-27B-OptiQ-4bit) publishes a
direct comparison between a mixed 5.24-bits-per-weight build (17.5 GB) and a
uniform 4-bit build (15.0 GB) of the same model:

| Metric | Mixed 5.24 bpw | Uniform 4-bit | Δ |
| --- | --- | --- | --- |
| MMLU (5-shot, 1000 samples) | 87.4% | 87.6% | −0.2 |
| GSM8K (1000 samples, 3-shot CoT) | 92.0% | 92.1% | −0.1 |
| IFEval (full set, strict) | 74.1% | 71.7% | +2.4 |
| BFCL-V3 simple (200 calls) | 92.5% | 93.0% | −0.5 |
| HumanEval (164 problems, pass@1) | 90.2% | 92.1% | −1.8 |
| HashHop (long-context retrieval) | 80.0% | 77.0% | +3.0 |
| Capability score (mean of six) | 86.04 | 85.58 | +0.46 |

Spending 31% more memory to move a six-metric mean by 0.46 points, while
*losing* 1.8 points on HumanEval and 0.5 on function calling, says the returns
above 4 bits are inside the noise on this model. It does not prove 8-bit is
worthless, but it removes the reason to assume otherwise. On the two metrics that
matter here — code and tool calls — the cheaper build won.

## MLX beats GGUF on decode and the runtime beats both

Measured on an M1 Max, 64GB, 24-core GPU — this machine's configuration — by
[local-llm-bench](https://github.com/famstack-dev/local-llm-bench), running
Qwen3.5-35B-A3B at 4-bit through an agent-shaped scenario:

| Backend | Format | Effective tok/s | Generation tok/s |
| --- | --- | --- | --- |
| oMLX | MLX 4-bit fp16 | 47.3 | 65.2 |
| oMLX | MLX 4-bit | 37.5 | 53.3 |
| Rapid-MLX | MLX 4-bit | 35.6 | 59.9 |
| LM Studio | MLX | 17.0 | 56.6 |
| LM Studio | GGUF | 17.6 | 28.2 |

MLX generates at twice GGUF's rate under LM Studio, 56.6 against 28.2. That
settles the format question for decode on this hardware.

It also says something more useful. Effective throughput — the figure that
includes prefill — is 17.0 for LM Studio MLX and 17.6 for LM Studio GGUF. MLX's
2× decode advantage is entirely consumed by prefill. Meanwhile two other MLX
servers on the same machine reach 47.3 and 35.6 effective at similar generation
speeds. The gap is prefill and cache handling, not the model and not the format.

The same repository states that LM Studio's default MLX prefill chunk size is 512
and that raising it to 4096 nearly doubles prefill speed. If that holds here, the
measured 122-second cold prefill is a setting, not a limit — and every prefill
figure derived above moves with it, though the ratio between dense and MoE does
not.

One counter-signal, on different hardware: [mlx-lm issue
#763](https://github.com/ml-explore/mlx-lm/issues/763) reports an M3 Ultra
running MiniMax-M2.1 at 4-bit generating 5.95 tok/s under MLX against 12.12 under
llama.cpp with flash attention, at 146k context; at 30k the gap is 25 against 32.
MLX degrades worse than llama.cpp as context grows. No M1 Max data exists for
this, and the sessions here reach 50k rather than 146k, so it is a flag rather
than a finding.

## What would settle it

Three experiments, in order of what they resolve per hour spent. All of them run
on models already on this machine.

**One: sweep the 27B the way the 35B-A3B was swept.** `qwen/qwen3.6-27b` at
4-bit is already downloaded. Run the same prompt lengths — 370, 3.5k, 14k, 49k —
through `/api/v0/chat/completions`, recording `stats.time_to_first_token` and
`stats.tokens_per_second`, cold and warm. This directly tests the two derived
numbers the whole argument rests on: 16 tok/s decode and 103 tok/s prefill. If
decode comes back above 25 or prefill above 200, the dense model is back in
contention and this document is wrong.

**Two: raise the MLX prefill chunk size from 512 to 4096 and re-run the 49k cold
prefill on the 35B-A3B.** If 122 seconds becomes 65, the largest available
speedup on this machine is a configuration change and no model choice competes
with it. This costs one setting and one request.

**Three: run one real task through both models and count turns.** Same task, same
prompt, `qwen3.6-35b-a3b` 4-bit against `qwen3.6-27b` 4-bit. Record wall-clock to
completion, number of agent turns, and number of malformed or rejected tool
calls. This is the only measurement that tests the actual claim — that the dense
model's higher agentic score buys back its slowness — and no benchmark substitutes
for it. Issue #17 already covers writing down what a long session costs; this is the
same measurement taken twice.

## What is not known

- **No independent evaluation of either Qwen3.6 model exists.** Neither appears
  on the Terminal-Bench 2.0 leaderboard, and no third-party SWE-bench Verified
  run was found. Every quality number for the two leading candidates is measured
  by Qwen.
- **BFCL rankings could not be read.** The leaderboard renders client-side. The
  benchmark that most directly measures the failure mode that costs whole turns
  is the one with the least evidence here.
- **No MLX-specific 4-bit versus 8-bit comparison exists** for any model, from any
  primary source. The OptiQ table above compares 4-bit against 5.24-bit, not
  against 8-bit, and covers one model.
- **Gemma 4 26B-A4B has no published agentic or SWE-bench score.** It derives to
  the same speed class as the 35B-A3B with a smaller cache, and its coding quality
  is unknown. It is the one candidate that could change the answer and cannot be
  ranked from published data.
- **No M1 Max prefill measurement exists for any dense model above 7B.** The
  103 tok/s figure for the 27B is a 3.9× extrapolation from a 7B measurement taken
  on a 32-core GPU, scaled by core count. Core-count scaling for prefill is
  assumed linear and was not verified.
- **The dense bandwidth constant rests on one usable data point.** 239 GB/s comes
  from a 1.2B model; applying it to a 27B model is a 22× extrapolation. The
  llama.cpp 7B figure narrows the gap but does not close it.
- **MoE efficiency at 44.8 GB of expert weights is unmeasured.** The 85 GB/s
  constant was measured on a model whose experts occupy 19 GB. Whether locality
  degrades at 44.8 GB is the reason Qwen3-Coder-Next's 52 tok/s is written as a
  ceiling.
- **Whether the MLX prefill chunk size claim holds on this machine.** It comes
  from a repository that measures on this hardware configuration, but the claim
  itself is stated in prose rather than shown in a measured row.
- **What warm-cache hit rate a real session achieves.** The 1.1-second warm
  figure and the 122-second cold figure bound the range, and nothing here says
  where in that range an actual session sits. Since offgrid lets the model go on
  exit, at least one cold prefill per run is certain; how many more is not known.

## The one benchmark on this hardware was replicated, and it moved

`local-llm-bench` measures on an M1 Max 64GB 24-core — this machine's
configuration — and is the only source found that does. Its harness was run
here on 2026-08-06 against `qwen/qwen3.6-35b-a3b` at MLX 4-bit, with
`reasoning_effort: "none"` sent per request so the model answers rather than
thinks. Its published rows are Qwen3.5-35B-A3B measured 2026-03-20, so this is
a comparison across two model versions and five months of runtime releases, not
a clean replication.

| Scenario | Published, Qwen3.5 | Measured here, Qwen3.6 |
| --- | --- | --- |
| ops-agent | 17.0 eff (56.6 gen) | 34.1 eff (47.9 gen) |
| doc-summary | 13.4 eff (56.8 gen) | 21.8 eff (50.1 gen) |
| creative-writing | 38.3 eff (58.9 gen) | 44.3 eff (46.9 gen) |
| prefill-test | 5.9 eff (54.4 gen) | 7.0 eff (46.3 gen) |

Effective throughput on the agent scenario is twice the published figure while
generation is slower, which is prefill and cache handling improving rather than
the model getting faster. The gap the repository reports between LM Studio and
oMLX — 17.0 against 47.3 — is 34.1 against 47.3 here.

Two corrections to that repository's numbers, both verified on this machine:

**The prefill chunk size claim does not hold.** The README states that raising
LM Studio's MLX prefill chunk from 512 to 4096 nearly doubles prefill speed. The
author's own follow-up measured it and found nothing: fp16 Gemma at 8K took
72.7s with the patch and 68.9s without
([mlx-vs-gguf part 2](https://famstack.dev/guides/mlx-vs-gguf-part-2-isolating-variables/)).
Nothing here should be built on that claim.

**Its prefill rates are understated.** The harness estimates context as
`chars // 4` (`bench.py:629`). The prefill-test scenario's final turn is 34,338
characters, which it reports as 8,584 tokens; the runtime counts 15,826. Rates
derived from that estimate are low by a factor of 1.8. Effective throughput is
unaffected — output tokens and wall clock are both measured.
