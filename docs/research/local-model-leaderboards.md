# Sources a second `recommend` adapter could read

Primary-source research into what, besides onyx.app's coding table, publishes
models `offgrid recommend` could size against a 32–128 GB Apple Silicon Mac.
Everything below was fetched on 2026-08-07 with `curl`, no browser and no
search tool. Every claim carries the URL it came from. Where a thing could not
be established it says so and says what was tried.

The bar a source has to clear is set by `src/offgrid/domain/sizing/listing.py`: a `Listing`
needs a `name` and a `parameters` count, and takes a `context_window` and a
`license` if the source has them. `fit.py` sizes from `parameters`, so a row
without one is dropped — which is why a scores-only leaderboard is useless
alone and interesting only paired with something that publishes sizes.

## 1. The cliff on the coding table is still there today

`GET https://onyx.app/best-llm-for-coding` returns 200, 190,829 bytes,
`content-type: text/html`. Concatenating the 17 `self.__next_f.push` payloads
gives 41,444 characters of flight text; `"config":{` decodes to an object whose
`lastUpdated` is `"2026-07-20"` and whose `models` has 27 entries. Eighteen
carry a parseable `parameters` string. The three smallest are 27 B, 35 B and
117 B. The build id is still `h6RV9KYmOT25YKMj8ccXx`, unchanged from the
2026-08-06 fetch recorded in `docs/research/onyx-leaderboard.md`, so nothing on
that page has been redeployed in between.

Source: `https://onyx.app/best-llm-for-coding`, fetched 2026-08-07.

## 2. onyx's own hardware page carries a second, larger catalogue — 77 models, 62 sized

`docs/research/onyx-leaderboard.md` §3 recorded that
`https://onyx.app/llm-hardware-requirements` embeds a different model
catalogue as a `JSON.parse('…')` string inside a JS chunk. That is confirmed,
and the catalogue is bigger than that note implies.

**How it is fetched.** Two requests. First
`GET https://onyx.app/llm-hardware-requirements` → 200, 58,689 bytes,
`content-type: text/html; charset=utf-8`. That HTML references 25 files matching
`/_next/static/chunks/*.js`. Then
`GET https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js` → 200,
127,734 bytes, `content-type: application/javascript; charset=utf-8`.

The `RSC: 1` trick that works on the coding page does not help here.
`curl -H 'RSC: 1' https://onyx.app/llm-hardware-requirements` returns 200 and
15,007 bytes of `text/x-component` containing zero occurrences of `vram_int4`.
The catalogue is not in any server-rendered payload; it is only in the chunk.

**Where inside the chunk.** The chunk contains exactly two `JSON.parse('` calls.
The first, at byte offset 2,468, opens
`let w=JSON.parse('{"J":[{"name":"Claude Fable 5",…`. The single-quoted JS
string literal runs 58,720 characters. Unescaping `\'` and parsing it yields an
object with one key, `J`, holding a 77-element array. The chunk uses it as
`w.J.find(l=>l.name===e)`. The second `JSON.parse` at offset 61,205 is the
tier list (`{"overall":{"S":[…],"A":[…]}}`), not the catalogue.

`J` is a bundler-mangled identifier, not a data field name — every key *inside*
the records (`name`, `parameters`, `operational`, `vram_int4`) is unmangled,
so a parser must not key off `J`. Section 5 sets out what to key off instead.

**The record shape is byte-identical to the coding table's.** Ten keys on all
77 records, except `activeParameters`, present on 76. `parameters` is a string
with a `B`/`T` suffix exactly as on the coding table, so `onyx.py`'s existing
`_parameters` and `_listings` read it unchanged.

| Key | Present | Type |
| --- | --- | --- |
| `name` | 77 | string |
| `provider` | 77 | string |
| `providerColor` | 77 | string |
| `logoPath` | 77 | string |
| `parameters` | 77 | string or null |
| `activeParameters` | 76 | string or null |
| `contextWindow` | 77 | integer |
| `releaseDate` | 77 | ISO date string |
| `benchmarks` | 77 | object, same 20 keys |
| `operational` | 77 | object |

`operational.system_ram_gb` is absent from 5 of the 77 records rather than
null — the same tolerance the coding-table parser already needs, at a higher
rate. `operational.license` is non-null on 71 of 77.

**Ground truth, verbatim.** One record exactly as it appears in the parsed
literal, chosen because it is a size the coding table has no row for at all:

```json
{
 "name": "Qwen3.5-4B",
 "provider": "Qwen",
 "providerColor": "#6C5CE7",
 "logoPath": "/logos/competitors/qwen.png",
 "parameters": "4B",
 "activeParameters": "4B",
 "contextWindow": 262144,
 "releaseDate": "2026-02-01",
 "benchmarks": {
  "mmlu_pro": 79.1, "gpqa_diamond": 76.2, "ifeval": null,
  "chatbot_arena": null, "swe_bench_verified": null, "humaneval": null,
  "livecode_bench": null, "aime_2025": null, "math_500": null,
  "mmlu": null, "mmmlu": null, "mmmu_pro": null, "hle": null,
  "terminal_bench": null, "arc_agi_2": null, "tau2_bench": null,
  "osworld": null, "browsecomp": null, "swe_bench_pro": null,
  "terminal_bench_21": null
 },
 "operational": {
  "tokens_per_sec": null, "cost_per_1m_input": null,
  "cost_per_1m_output": null, "vram_fp16": 8, "vram_int4": 2,
  "min_gpu": "1x RTX 3060 12GB", "license": "Apache 2.0",
  "system_ram_gb": 5
 }
}
```

**Coverage below 35 B.** Twenty-two of the 62 sized rows are under 35 B, against
zero on the coding table. Taking the crude test of 4-bit weights against a
56 GB budget — `parameters × 4 / 8 ≤ 56 GB`, i.e. 112 G parameters, ignoring the
context reserve `fit.py` applies — 30 of the 62 pass, against 2 on the coding
table:

Ministral 3B, Phi-4-mini, Qwen3.5-4B, DeepSeek-R1-0528-Qwen3-8B, Ministral 8B,
GLM-Z1-9B, Qwen3.5-9B, Gemma 3 12B, Gemma 4 12B, DS-R1-Distill-Qwen-14B,
Ministral 14B, Phi-4, GPT-oss 20B, Mistral Small 3.1, Gemma 3 27B, Qwen3.5-27B,
Qwen3.6-27B, Nemotron 3 Nano, Nemotron Nano 30B, Gemma 4 31B,
DS-R1-Distill-Qwen-32B, GLM-Z1-32B, Qwen3.5-35B-A3B, Qwen3.6-35B-A3B,
Kimi-Linear-48B-A3B, Nemotron Super 49B, DS-R1-Distill-Llama-70B, Llama 3.3 70B,
Qwen3-Coder-Next, Llama 4 Scout.

**What those 30 rows do not carry is a coding score.** Only 5 of the 30 have a
non-null `swe_bench_verified`, and only 3 have any terminal-bench figure:

| Model | `swe_bench_verified` | terminal-bench | `livecode_bench` |
| --- | --- | --- | --- |
| Qwen3.6-27B | 77.2 | 59.3 | 83.9 |
| Qwen3.5-27B | 72.4 | — | 80.7 |
| Nemotron 3 Nano | 38.8 | — | 68.3 |
| Qwen3.6-35B-A3B | 73.4 | 51.5 | 80.4 |
| Qwen3-Coder-Next | 70.6 | 36.2 | 74.5 |

Everything under 27 B — Ministral 3B, Phi-4-mini, Qwen3.5-4B, Ministral 8B,
GLM-Z1-9B, Gemma 3/4 12B, Phi-4, GPT-oss 20B, Mistral Small 3.1 — has no
SWE-bench figure and no terminal-bench figure. Across all 77 records,
`swe_bench_verified` is non-null 31 times and `terminal_bench` 19 times.

**There is no freshness date.** Searched the whole chunk for `lastUpdated`,
`last_updated` and `updatedAt`: zero matches. The coding table's `lastUpdated`
has no counterpart here, so a `Table` built from this source has `dated=None`
and offgrid cannot print how old the list is.

Sources: `https://onyx.app/llm-hardware-requirements`,
`https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js`, fetched
2026-08-07.

## 3. The chunk that holds it moves, and it has only held it for a few weeks

The Wayback CDX index shows two builds of the same webpack chunk id:

```
https://onyx.app/_next/static/chunks/1265-89af02de7d15bf13.js 20260624013735
https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js 20260726050203
```

The June build of `1265` is 23,428 bytes and contains no `JSON.parse` at all.
So the numeric prefix is not a stable address for the catalogue.

The 2026-06-24 snapshot of the page itself lists 26 chunk files, of which 12
filenames differ from today's 25. All 25 of them were fetched from the archive
and grepped for `vram_int4` and `bandwidthGbS`: **zero hits in any of them.**
The largest were `1248-6dd6b8245f63102d.js` at 515,710 bytes,
`9da6db1e-e479850123783283.js` at 177,303 and `1255-79156e80ea3d002b.js` at
173,500; the rest ranged from 572 bytes to 173,025.

Two readings are possible and this evidence does not separate them: either the
catalogue was not on the page on 2026-06-24 and arrived some time before the
2026-07-26 capture, or the archive's capture of that page is not what a browser
saw. Either way the catalogue's location is at most about six weeks old at the
address it occupies now, and nothing about that address is documented.

Scanning all 25 chunks the page references today costs 25 requests and
1,549,472 bytes, and exactly one of them — `1265-a79672506f1ea1a7.js` —
contains `vram_int4`.

Sources: `https://web.archive.org/cdx/search/cdx?url=onyx.app/_next/static/chunks/*`,
`https://web.archive.org/web/20260624013735id_/https://onyx.app/llm-hardware-requirements`
and its 25 referenced chunks, fetched 2026-08-07.

## 4. The Hugging Face Hub API publishes a parameter count that is a fact, not a claim

**How it is fetched.** `GET https://huggingface.co/api/models/{namespace}/{repo}`
returns 200, `content-type: application/json; charset=utf-8`. For
`Qwen/Qwen3.6-27B` that is 21,691 bytes across 26 keys. The response can be
narrowed with a repeated `expand[]` query parameter, which cuts
`Qwen/Qwen3-0.6B` to a few hundred bytes:

```sh
curl 'https://huggingface.co/api/models/Qwen/Qwen3.6-27B?expand[]=safetensors&expand[]=cardData'
```

**The two fields that matter, verbatim.** From `Qwen/Qwen3.6-27B`:

```json
"safetensors": {"parameters": {"BF16": 27781427952}, "total": 27781427952}
```

```json
"cardData": {
  "library_name": "transformers",
  "license": "apache-2.0",
  "license_link": "https://huggingface.co/Qwen/Qwen3.6-27B/blob/main/LICENSE",
  "pipeline_tag": "image-text-to-text"
}
```

`safetensors.total` is an integer counted out of the repo's own weight index —
27,781,427,952, not the string `"27B"` onyx publishes. That is the single
strongest primary-source property found anywhere in this survey: it is not a
number a leaderboard asserts about a model, it is the number of tensor
elements in the files offgrid would download.

**It is not a parameter count for a quantized repo.** For `mlx-community` 4-bit
and 8-bit builds, `safetensors.total` counts stored elements, including packed
`U32` words, and different uploaders disagree about what to report:

| Repo | `safetensors` | `total` in B |
| --- | --- | --- |
| `mlx-community/Qwen3.6-27B-4bit` | `{"BF16": 1303792880, "U32": 3361669120}` | 4.67 |
| `mlx-community/Qwen3.6-27B-8bit` | `{"BF16": 1303792880, "U32": 6723338240}` | 8.03 |
| `mlx-community/Qwen3.6-27B-OptiQ-4bit` | `{"BF16": 1303792880, "U32": 4264427520}` | 26.90 |
| `mlx-community/Qwen3.6-35B-A3B-4bit` | `{"BF16": 1530838896, "U32": 4335063040}` | 5.87 |

Three of those four disagree with the 27.78 B / 35.95 B the source repos report,
and the fourth agrees only by coincidence of what its uploader wrote into the
metadata. A sizing adapter must read the original full-precision repo, not the
MLX build. (`usedStorage` — 55,576,522,126 for `Qwen/Qwen3.6-27B` — is a real
byte count and would be a legitimate alternative input, but `Listing` takes a
parameter count, not bytes.)

**What it does not carry.** No context window: the `config` expansion returns
`architectures`, `model_type` and a large `tokenizer_config` with the chat
template, and no `max_position_embeddings`. Reading a context window means
fetching `config.json` from the repo, which is a second request per model. No
coding or agentic score of any kind. No notion of which models are worth
listing — `?limit=1` against the unfiltered endpoint returns
`MiniMaxAI/MiniMax-H3` by trending score, and there is no filter that means
"good at coding".

**Terms.** `https://huggingface.co/robots.txt` is, in full:

```
User-agent: *
Allow: /

Sitemap: https://huggingface.co/sitemap.xml
```

`https://huggingface.co/terms-of-service` renders 31,762 characters of text
after stripping markup. Searched for `scrap`, `crawl`, `spider`, `robot`,
`automated means` and `data mining`: **zero matches on all six.** The document
is dated "Effective Date: September 15, 2022" and binds "You, whether you are a
user … or a customer".

Rate limits are published rather than prohibited, which is the posture of a
service that expects programmatic use.
`https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/rate-limits.md`
gives an anonymous per-IP allowance of **500 Hub API requests per 5-minute
fixed window**, rising to 1,000 for a free account, and says 429 responses carry
`RateLimit` and `RateLimit-Policy` headers.

**Brittleness.** Neither `/api/models` nor `/api/models/{namespace}/{repo}` is
in `https://huggingface.co/.well-known/openapi.json` — that spec has 254 paths,
29 of them containing `model`, and the bare list and detail endpoints are not
among them. The `expand` parameter is documented only in the client library:
`https://raw.githubusercontent.com/huggingface/huggingface_hub/main/src/huggingface_hub/hf_api.py`,
line 2483:

> expand (`list[ExpandModelProperty_T]`, *optional*):
>     List properties to return in the response. When used, only the properties
>     in the list will be returned. This parameter cannot be used if `full`,
>     `cardData` or `fetch_config` are passed.

with `"safetensors"` and `"cardData"` among the listed values. So this is a
stable, widely-consumed, first-party-client-documented endpoint that is
nonetheless absent from the vendor's own OpenAPI description.

Sources: `https://huggingface.co/api/models/Qwen/Qwen3.6-27B`,
`https://huggingface.co/api/models?author=mlx-community&search=Qwen3.6&…`,
`https://huggingface.co/robots.txt`, `https://huggingface.co/terms-of-service`,
`https://huggingface.co/.well-known/openapi.json`,
`https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/api.md`,
`https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/rate-limits.md`,
`https://raw.githubusercontent.com/huggingface/huggingface_hub/main/src/huggingface_hub/hf_api.py`,
fetched 2026-08-07.

## 5. OpenRouter is the best-shaped catalogue found, and its terms forbid using it this way

**How it is fetched.** `GET https://openrouter.ai/api/v1/models` returns 200,
654,110 bytes, `content-type: application/json`, one request, no key, no
pagination (`links.next` is null). It is `{"data": […400 models…],
"total_count": 400, "links": {…}}`.

**The record shape, verbatim.** `qwen/qwen3.6-27b` exactly as it appears,
with the long fields elided where marked:

```json
{
 "id": "qwen/qwen3.6-27b",
 "canonical_slug": "qwen/qwen3.6-27b-20260422",
 "hugging_face_id": "Qwen/Qwen3.6-27B",
 "name": "Qwen: Qwen3.6 27B",
 "created": 1777255064,
 "description": "Qwen3.6 27B is a dense 27-billion-parameter language model …",
 "context_length": 262144,
 "architecture": {
  "modality": "text+image+video->text",
  "input_modalities": ["text", "image", "video"],
  "output_modalities": ["text"],
  "tokenizer": "Qwen3",
  "instruct_type": null
 },
 "pricing": {"prompt": "0.0000006", "completion": "0.0000036",
             "input_cache_read": "0.00000012"},
 "top_provider": {"context_length": 262144, "max_completion_tokens": 262144,
                  "is_moderated": false},
 "per_request_limits": null,
 "supported_parameters": ["frequency_penalty", "…"],
 "default_parameters": {"temperature": null, "…": null},
 "supported_voices": null,
 "knowledge_cutoff": null,
 "expiration_date": null,
 "links": {"details": "/api/v1/models/qwen/qwen3.6-27b-20260422/endpoints"},
 "benchmarks": {
  "design_arena": [],
  "artificial_analysis": {"intelligence_index": 37.7, "coding_index": 53.7,
                          "agentic_index": 27.5}
 },
 "reasoning": {"mandatory": false, "default_enabled": true}
}
```

**No parameter count anywhere.** Field presence over the 400 records: `id`,
`canonical_slug`, `hugging_face_id`, `name`, `created`, `description`,
`context_length`, `architecture`, `pricing`, `top_provider`,
`per_request_limits`, `supported_parameters`, `default_parameters`,
`supported_voices`, `knowledge_cutoff`, `expiration_date`, `links` on all 400;
`reasoning` on 269; `benchmarks` on 217; `alias_target` on 11. No key contains
"param" except `supported_parameters` and `default_parameters`, which are
sampler settings. A size appears only inside the free-text `description`, in
120 of the 400.

**But it carries the join key.** `hugging_face_id` is non-null on 158 of the
400, and it is an exact repo path. Resolving all 158 against
`https://huggingface.co/api/models/{repo}?expand[]=safetensors&expand[]=cardData&expand[]=usedStorage`
took **3.7 seconds wall clock at concurrency 8**: 157 answered 200, one 404,
and 154 returned a non-null `safetensors.total`.

That join produces 63 rows at 35 B or under and **85 rows (80 distinct repos)**
whose 4-bit weights clear 56 GB — against onyx's 2 on the coding table and 30
on the hardware page. Twenty-eight of the 80 carry an Artificial Analysis
`coding_index` and 24 an `agentic_index`. The top of that list:

| `coding_index` | `agentic_index` | Parameters | Repo |
| --- | --- | --- | --- |
| 53.7 | 27.5 | 27.78 B | `Qwen/Qwen3.6-27B` |
| 43.4 | 14.4 | 31.27 B | `google/gemma-4-31B-it` |
| 41.9 | 21.6 | 35.95 B | `Qwen/Qwen3.6-35B-A3B` |
| 39.3 | 11.0 | 26.54 B | `google/gemma-4-26B-A4B-it` |
| 37.0 | 11.8 | 35.95 B | `Qwen/Qwen3.5-35B-A3B` |
| 36.5 | 3.1 | 30.48 B | `CohereLabs/North-Mini-Code-1.0` |
| 36.2 | 8.9 | 79.66 B | `Qwen/Qwen3-Coder-Next` |
| 28.7 | 7.0 | 9.65 B | `Qwen/Qwen3.5-9B` |
| 20.7 | 3.1 | 21.51 B | `openai/gpt-oss-20b` |
| 15.3 | 1.8 | 32.76 B | `Qwen/Qwen3-32B` |

**Its terms forbid this.** `https://openrouter.ai/robots.txt` is permissive:

```
User-Agent: *
Allow: /
Disallow: /seo/

Sitemap: https://openrouter.ai/sitemap.xml
```

`https://openrouter.ai/terms` is not. Section 7, "Prohibited Conduct", opens
"BY USING THE SERVICE, YOU AGREE NOT TO:" and includes, verbatim:

> develop, support or use software, devices, scripts, robots or any other means
> or processes (such as crawlers, browser plugins, add-ons or any other
> automated technology) to scrape or copy any information on the Site or the
> Services; bypass any technical measures implemented by OpenRouter that are
> designed to prevent scraping

The same list also forbids "access the Site or Service for purposes of …
developing a competing service".

This is a materially worse position than onyx's. The one anti-scraping clause
on onyx.app sits inside a subscription agreement between Danswer and a paying
customer (`docs/research/onyx-leaderboard.md` §4); OpenRouter's binds anyone
using the Service, and calling `/api/v1/models` is using the Service. Not
established: whether OpenRouter reads a call to its own public unauthenticated
model-discovery endpoint — the endpoint every client uses to find out what
exists — as "scrape or copy any information on … the Services". Nothing found
answers that; the only route is to ask them.

Sources: `https://openrouter.ai/api/v1/models`, `https://openrouter.ai/robots.txt`,
`https://openrouter.ai/terms`, `https://huggingface.co/api/models/…`, fetched
2026-08-07. `https://openrouter.ai/docs/api-reference/list-available-models`
returns 404 today; the endpoint is listed in `https://openrouter.ai/llms.txt`.

## 6. The benchmark leaderboards: three are stale, two are live, none publishes a size that helps

**Aider polyglot — machine-readable, permissive, no sizes.**
`https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml`
returns 200, 45,725 bytes, `text/plain` — byte-identical in length to the
2026-08-06 fetch. Sixty-nine entries, one per run, with `pass_rate_2`,
`percent_cases_well_formed`, `num_malformed_responses`,
`exhausted_context_windows`, `total_cost`, `seconds_per_case`, `commit_hash`
and the exact `aider --model …` command. `https://api.github.com/repos/Aider-AI/aider`
reports `license.spdx_id: Apache-2.0`, last pushed 2026-05-22. There is no
parameter count, no model size and no HF repo id in the file — the only model
identifier is an API model string. Unusable for sizing, and it still has no
Qwen3.6 entry.

**EvalPlus — publishes a size, but the data stopped in 2025.**
`https://evalplus.github.io/results.json` returns 200, 34,305 bytes,
`application/json`: an object of 125 models keyed by name. One entry verbatim:

```json
"OpenCoder-8B-Instruct": {
  "link": "https://huggingface.co/infly/OpenCoder-8B-Instruct",
  "open-data": "NONE",
  "pass@1": {"humaneval": 81.7, "humaneval+": 77.4,
             "mbpp": 82.0, "mbpp+": 71.4},
  "prompted": true,
  "size": 8.0
}
```

`size` is a number in billions and `link` is an HF repo URL — the two fields a
sizing adapter wants, in one file. 104 of the 125 have a numeric size, 96 of
those at 35 B or under. But the newest models it knows are Qwen2.5-era: zero
entries matching "Qwen3" or "GPT-oss", one matching "Qwen2.5". The site repo
`https://api.github.com/repos/evalplus/evalplus.github.io` is Apache-2.0 and
was last pushed 2024-12-26.

**BigCodeBench — same shape, same problem, and no licence on the data.**
`https://bigcode-bench.github.io/results.json` returns 200, 76,120 bytes,
202 models, with `size`, `act_param`, `moe`, `date`, `prefill` and an HF `link`:

```json
"Magicoder-S-DS-6.7B": {
  "link": "https://huggingface.co/ise-uiuc/Magicoder-S-DS-6.7B",
  "open-data": "Partial",
  "pass@1": {"instruct": 36.2, "complete": 47.6},
  "prompted": true, "moe": false, "size": 6.7, "act_param": 6.7,
  "date": "2024-12-04", "prefill": true
}
```

149 have a numeric size, 110 of them at 35 B or under. The `date` values run
2023-08-25 to **2025-04-14** — sixteen months stale. Zero "Qwen3" or "GPT-oss"
entries. The harness repo `bigcode-project/bigcodebench` is Apache-2.0, but the
site repo that actually holds `results.json`,
`https://api.github.com/repos/bigcode-bench/bigcode-bench.github.io`, reports
`license: null` — the same trap as `SWE-bench/experiments`, whose GitHub API
record also reports a null licence.

**LiveCodeBench — could not establish a data file.**
`https://livecodebench.github.io/leaderboard.html` returns 200 and 36,734 bytes
containing no `.json` or `.csv` reference and no `fetch` of a data endpoint;
`https://livecodebench.github.io/` returns 22,770 bytes with the same result.
Whatever renders that table is not visible in the served HTML. Tried: grepping
both documents for `.json`, `.csv` and `fetch(`. Not established: whether the
data is reachable at some undiscovered path.

**Terminal-Bench 2.0 — live, no sizes.**
`https://www.tbench.ai/leaderboard/terminal-bench/2.0` returns 200, 563,171
bytes of HTML with 16 `__next_f` push tags and 142 `accuracy` values, matching
what `docs/research/onyx-leaderboard.md` §6 recorded. Its records carry
`accuracy`, `stderr`, `verified`, `agentName`, `agentVersion` and
`modelProviders` and no parameter count. `https://www.tbench.ai/robots.txt`
still returns the site's 404 page rather than a robots file.

**SWE-rebench — live, independently run, small models included, no sizes.**
This is the source `docs/research/onyx-leaderboard.md` did not look at, and it
is the best independent counterpart to onyx's numbers found so far.
`https://swe-rebench.com/` returns 200, 7,789,901 bytes of HTML. Its 23
`__next_f` pushes concatenate to 6,548,154 characters, inside which
`"items":[` decodes to 117 leaderboard rows. One verbatim, with `rangeStats`
trimmed from 45 time windows to the widest:

```json
{
 "modelId": "Qwen3.6-27B__tools",
 "modelName": "Qwen3.6-27B",
 "release": {"timestamp": 1774137600000, "date": "2026-03-22"},
 "taskRangeTimestamp": {"from": 1772323200000, "to": 1782864000000},
 "agentVersion": "tools",
 "meta": {"developer": "alibaba", "instance_type": "model"},
 "rangeStats": {"all": {"1772323200000:1782864000000": {
   "resolvedRate": 33.84615384615385,
   "sem": 1.0258628098420488,
   "passN": 54.29864253393665,
   "instanceCosts": 0.5883202418493214,
   "totalTokenUsage": 2480019.1927601807,
   "cachedTokenPercentage": 45.651843673927466
 }}}
}
```

`rangeStats` is keyed by `all`, `go`, `java`, `python`, `rust` and `typescript`,
each holding 45 `from:to` windows. Small open models are present and freshly
run — the site's own news list says "[2026-07-01] Added new models to the
leaderboad: GLM 5.2, DeepSeek-V4 Pro, DeepSeek-V4 Flash, MiMo V2.5 Pro,
Qwen3.6-35B-A3B, Qwen3.6-27B and Gemma 4 31B."

| `resolvedRate` | `sem` | Model | Agent | Release |
| --- | --- | --- | --- | --- |
| 33.85 | 1.03 | Qwen3.6-27B | tools | 2026-03-22 |
| 29.23 | 0.51 | Qwen3.6-35B-A3B | tools | 2026-03-14 |
| 25.06 | 1.04 | Gemma 4 31B | tools | 2026-04-02 |
| 36.36 | 1.17 | Devstral-Small-2-24B-Instruct-2512 | tools | 2025-12-25 |
| 30.10 | 1.33 | GLM-4.7 Flash | tools | 2026-01-19 |
| 21.56 | 0.50 | Qwen3-Coder-30B-A3B-Instruct | tools | 2025-07-31 |
| 10.76 | 0.68 | Qwen3-30B-A3B-Thinking-2507 | tools | 2025-07-25 |
| 8.08 | 1.12 | gpt-oss-20b | tools | 2025-07-13 |

Two cautions on those numbers. `taskRangeTimestamp` differs per model — the
benchmark evaluates each model on tasks drawn after its release — so rows are
not strictly comparable across models; Qwen3.5-27B reads 58.95 on its own
window, above Qwen3.6-27B's 33.85, which is a window artefact rather than a
finding. And `resolvedRate` on decontaminated fresh GitHub PRs is not the same
quantity as SWE-bench Verified, so 33.85 does not refute Qwen's self-reported
77.2 — it is a different measurement, independently run.

It has no parameter count, so it is a scores source only. `modelName` is a free
string (`"Qwen3-235B-A22B no-thinking"`, `"Fable 5 [high]"`) with no HF repo id,
so pairing it with a size source means fuzzy name matching.
`https://swe-rebench.com/robots.txt` returns `User-Agent: * / Allow: /` plus a
sitemap. The page states no licence — searched the stripped text for `license`,
`License`, `Licence`, `Terms`, `CC BY`, `Apache`, `MIT` and `copyright`: zero
matches on all but a coincidental use of "terms of". The related task dataset
`https://huggingface.co/api/datasets/nebius/SWE-rebench` reports
`cardData.license: "cc-by-4.0"`, but that is the tasks, not the results.

Sources: `https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml`,
`https://evalplus.github.io/results.json`, `https://bigcode-bench.github.io/results.json`,
`https://livecodebench.github.io/leaderboard.html`,
`https://www.tbench.ai/leaderboard/terminal-bench/2.0`, `https://swe-rebench.com/`,
`https://swe-rebench.com/robots.txt`,
`https://huggingface.co/api/datasets/nebius/SWE-rebench`,
`https://api.github.com/repos/{Aider-AI/aider,evalplus/evalplus.github.io,bigcode-bench/bigcode-bench.github.io,SWE-bench/experiments}`,
fetched 2026-08-07.

## 7. The runtime catalogues publish sizes but not in a form worth parsing

**Ollama has no library API.** `https://ollama.com/robots.txt` returns 404.
`https://ollama.com/library` returns 200 and 790,637 bytes of HTML in which
sizes appear only as rendered badges —
`<span class="…">8b</span>`, `70b`, `405b`, `1.5b` — with no JSON payload.
`https://ollama.com/api/tags` returns 200 and 4,416 bytes but is the *cloud*
model list, 18 entries, and its `details.parameter_size` is the empty string on
all 18:

```json
{
 "name": "kimi-k2.6", "model": "kimi-k2.6",
 "modified_at": "2026-04-20T00:00:00Z",
 "size": 595148192736, "digest": "4764ecb21f85",
 "details": {"parent_model": "", "format": "", "family": "", "families": null,
             "parameter_size": "", "quantization_level": ""}
}
```

`size` is a real byte count, and three of the 18 report `size: 0`. The
container registry answers —
`https://registry.ollama.ai/v2/library/qwen3/manifests/latest` returns 200 and
859 bytes of an OCI manifest whose model layer is 5,225,374,496 bytes — but
`/v2/library/qwen3/tags/list` returns 404, so there is no way to enumerate.

**LM Studio publishes sizes in HTML title attributes.**
`https://lmstudio.ai/robots.txt` is `User-agent: * / Allow: /` plus a sitemap.
`https://lmstudio.ai/models` returns 200 and 724,779 bytes, server-rendered,
carrying 46 distinct links under `/models/` and size badges of the form
`<div … title="Model size: 27B parameters">27B</div>`, duplicated between the
mobile and desktop layouts. Sizes seen include 270M, 700M, 2B, 3B, 4B, 4.5B,
5.1B, 6.9B, 7B, 7.9B, 8B, 9B, 12B, 14B, 14.7B, 20B, 23.6B, 24B, 26B, 27B, 30B,
31B, 32B, 35B, 70B, 72B, 80B, 120B, 235B, 480B. There is no JSON payload and no
machine-readable endpoint: `https://lmstudio.ai/api/v1/models` returns 500 with
a 64-byte JSON body and `https://lmstudio.ai/api/v0/models` returns 404. The
catalogue is a curated staff list, not a leaderboard: it publishes no coding
score at all.

Sources: `https://ollama.com/library`, `https://ollama.com/robots.txt`,
`https://ollama.com/api/tags`, `https://registry.ollama.ai/v2/library/qwen3/manifests/latest`,
`https://registry.ollama.ai/v2/library/qwen3/tags/list`,
`https://lmstudio.ai/models`, `https://lmstudio.ai/robots.txt`,
`https://lmstudio.ai/api/v1/models`, `https://lmstudio.ai/api/v0/models`,
fetched 2026-08-07.

## 8. The candidates side by side

Rows are counted the same way throughout: a parameter count exists, and
`parameters × 4 / 8 ≤ 56 GB`, ignoring the context reserve `fit.py` applies.

| Source | Fetch | Sized rows | Fitting 56 GB | Under 35 B | Licence field | Context | Coding score | Reuse terms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| onyx coding table | 1 req, RSC | 18 | 2 | 0 | yes | yes | 2 of 2 rows | none stated |
| onyx hardware chunk | 2–26 reqs | 62 | 30 | 22 | yes | yes | 5 of 30 rows | none stated |
| HF Hub API | 1 req/model | exact | — | — | yes | no | none | ToS silent, robots `Allow: /` |
| OpenRouter + HF | 1 + 158 reqs | 154 | 85 | 63 | yes (HF) | yes | 28 of 80 | **forbidden by §7** |
| EvalPlus | 1 req | 104 | — | 96 | no | no | HumanEval+/MBPP+ | Apache-2.0 site repo |
| BigCodeBench | 1 req | 149 | — | 110 | no | no | BigCodeBench | no licence on site repo |
| Aider polyglot | 1 req | 0 | 0 | 0 | no | no | pass rate, malformed edits | Apache-2.0 |
| Terminal-Bench 2.0 | 1 req | 0 | 0 | 0 | no | no | accuracy + `verified` | none stated |
| SWE-rebench | 1 req | 0 | 0 | 0 | no | no | `resolvedRate` + `sem` | none stated, robots `Allow: /` |
| LM Studio | 1 req, HTML | ~46 | — | — | no | no | none | robots `Allow: /` |
| Ollama | — | 0 | 0 | 0 | no | no | none | robots 404 |

## Recommendation

**Build the second adapter against onyx's `llm-hardware-requirements`
catalogue.** It is the only candidate that turns 2 fitting rows into 30 without
writing a new record parser: the shape is byte-identical to the coding table's,
so `onyx.py`'s `_listings` and `_parameters` read it unchanged, `"27B"` and all.
It needs no new dependency, no API key, and it adds no terms question offgrid
has not already answered for the sibling page: the same robots.txt allows it,
and the site's one anti-scraping clause sits in the same Cloud subscription
agreement, whose reach over a non-customer `docs/research/onyx-leaderboard.md`
§4 records as unsettled either way.

What it costs, concretely:

1. A chunk locator. Fetch the page, extract `/_next/static/chunks/*.js`, fetch
   each in turn and stop at the first containing `"vram_int4"`. Worst case 26
   requests and 1.6 MB; today it is the second of 25 in sorted order. **Do not
   key off the chunk filename** (`1265-…` held something else six weeks ago) and
   **do not key off `"J"`** (a bundler-mangled export name). Key off the record
   fields, which are not mangled: take each `JSON.parse('…')` literal, unescape
   `\'`, parse it, and keep the value whose sole array-of-objects has members
   carrying both `parameters` and `operational`.
2. A `dated=None` path. This catalogue publishes no `lastUpdated`, so
   `Table.dated` is `None` and whatever `recommend` prints about freshness has
   to cope with its absence.
3. Nothing else. `Listing` is populated from the same four fields.

**Pair it with the Hugging Face Hub API only if the rounded sizes turn out to
matter.** `safetensors.total` is 27,781,427,952 where onyx writes `"27B"`, and
it is the one number in this entire survey that nobody is asserting — it is
counted out of the weight files offgrid would download. Cost: one
`?expand[]=safetensors&expand[]=cardData` request per model — 158 of them in
3.7 s wall clock at concurrency 8 — inside a 500-per-5-minute anonymous budget,
against a service
whose robots.txt is `Allow: /` and whose Terms of Service contain no
anti-scraping clause. Note it will not give a context window without a second
request per repo.

**Do not build on OpenRouter**, despite it being the best-shaped source here by
a wide margin — one unauthenticated request, 400 models, an exact
`hugging_face_id` join key, a context window, and third-party coding and
agentic indices. Its Terms section 7 forbids using "any other automated
technology to scrape or copy any information on the Site or the Services", and
that clause binds every user of the Service, not just a paying one. It is
worth an email before it is worth a code path.

## What this settles

**Settled.**

- onyx's hardware page carries 77 models, 62 of them sized, 22 under 35 B and 30
  clearing a 56 GB 4-bit budget — fifteen times what the coding table yields
  from the same site. The record shape is identical to the coding table's, down
  to `parameters` being a `"4B"`-style string.
- That catalogue is only in a JS chunk. The `RSC: 1` endpoint returns 15,007
  bytes containing no `vram_int4`, so the trick that simplified the coding
  adapter does not transfer.
- The chunk address is not stable. `1265-89af02de7d15bf13.js` on 2026-06-24 held
  no catalogue; `1265-a79672506f1ea1a7.js` today does. All 25 chunks of the
  June snapshot were fetched and none contains `vram_int4`. A locator must be
  content-based, and `"J"` is a mangled export name, not a field.
- That catalogue publishes no `lastUpdated` of any kind, so offgrid cannot say
  how old it is.
- It gives sizes but not scores for small models: 25 of the 30 fitting rows have
  neither a SWE-bench nor a terminal-bench figure, including everything under
  27 B.
- `safetensors.total` from the HF Hub API is an exact integer parameter count
  for a full-precision repo, and `cardData.license` is the licence the model
  publisher declared. HF's robots.txt allows everything, its ToS contains no
  anti-scraping clause on any of six searched terms, and its published anonymous
  rate limit is 500 API requests per 5 minutes.
- `safetensors.total` is *not* a parameter count for a quantized repo: three of
  four `mlx-community` Qwen3.6 builds report between 4.67 B and 8.03 B for
  27–36 B models. Sizing must read the source repo.
- OpenRouter's `/api/v1/models` carries no parameter count at all, but carries
  `hugging_face_id` on 158 of 400 and Artificial Analysis coding and agentic
  indices on 217. Joined to HF it yields 85 fitting rows in 3.7 seconds. Its
  Terms section 7 forbids automated copying of information on the Service, and
  that prohibition binds anyone using it.
- EvalPlus and BigCodeBench both publish a numeric `size` and an HF `link` in a
  single JSON file, which is the shape a sizing adapter wants — and both stopped
  before Qwen3 and GPT-oss existed. BigCodeBench's newest dated entry is
  2025-04-14. BigCodeBench's site repo carries no licence.
- Aider polyglot, Terminal-Bench 2.0 and SWE-rebench publish no size of any
  kind and cannot be used alone.
- SWE-rebench is live, independently run, and does cover small open models:
  Qwen3.6-27B at 33.85 `resolvedRate` (`sem` 1.03), Gemma 4 31B at 25.06,
  Devstral-Small-2-24B at 36.36. Its per-model `taskRangeTimestamp` means rows
  are not directly comparable across models.
- Neither Ollama nor LM Studio offers a machine-readable catalogue with sizes.
  Ollama's `/api/tags` is 18 cloud models with an empty `parameter_size`;
  LM Studio's sizes live in HTML `title` attributes.
- LiveCodeBench's leaderboard data could not be found in either page served for
  it; both contain no `.json`, no `.csv` and no data `fetch`.

**Still open.**

- Whether OpenRouter reads a call to its own public model-discovery endpoint as
  the "scraping" its Terms forbid. Only they can answer; there is no exception
  in the text and no separate API terms page was found.
- Whether the onyx hardware catalogue predates 2026-06-24 somewhere the archive
  did not capture, or genuinely arrived in July. The evidence rules out its
  presence in any of the 25 chunks the archived page references and does not
  distinguish those two readings.
- What SWE-rebench's results may be reused under. The site states no licence and
  offers no terms page; the `cc-by-4.0` on `nebius/SWE-rebench` covers the task
  dataset, not the leaderboard.
- Whether LiveCodeBench's leaderboard is reachable at some path not discovered
  here.
- What `recommend` should print for a row with a size and no coding score, which
  is 25 of the 30 rows the recommended source would add. Nothing found here
  bears on it.
