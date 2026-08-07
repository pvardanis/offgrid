# The onyx.app coding leaderboard as a source

Primary-source research for issue #20. Everything below was fetched on
2026-08-06 with `curl`, no browser. Every claim carries the URL it came from.
Where a thing could not be established it says so and says what was tried.

There is no research-note convention in this repo — `docs/` held only
`decisions.md` and `models.md` — so this file starts one at `docs/research/`.

## 1. The table is reachable by a plain GET, and there is a cleaner way in

`GET https://onyx.app/best-llm-for-coding` returns 200, 190,835 bytes of
HTML, `content-type: text/html`. The whole model table is in that response.
Nothing is fetched after load.

The payload is carried in 17 `<script>self.__next_f.push([1,"…"])</script>`
tags. Each argument is a two-element JSON array whose second element is a
string; concatenating those strings in document order yields 41,450 characters
of React Server Component flight text. Inside it, the literal `"config":{`
appears once, and brace-matching from that point gives a JSON object with these
top-level keys:

```
lastUpdated  pageFlag  models  benchmarks  tierlist  showPricing
defaultComparisonModels  crossLinks  costVsPerformance
benchmarkTabLabels  benchmarkTabs  copy
```

`lastUpdated` is `"2026-07-20"` and `models` has 27 entries — both unchanged
from what the issue recorded.

**Field names, confirmed and corrected.** Every model object carries ten keys,
not six. The issue's six are all present and correctly named. The two it omits
are cosmetic:

| Key | Type | Note |
| --- | --- | --- |
| `name` | string | |
| `provider` | string | |
| `providerColor` | string | not in the issue; a hex colour |
| `logoPath` | string | not in the issue; a path under `/logos/competitors/` |
| `parameters` | string or null | `"35B"`, `"1.6T"`, `"N/A"` — a string, not a number |
| `activeParameters` | string or null | same encoding |
| `contextWindow` | integer or null | tokens |
| `releaseDate` | string | ISO date |
| `benchmarks` | object | 20 keys, present on all 27 |
| `operational` | object | 8 keys, present on all 27 |

`benchmarks` has exactly these 20 keys on every model, null where unpopulated:
`mmlu_pro`, `gpqa_diamond`, `ifeval`, `chatbot_arena`, `swe_bench_verified`,
`humaneval`, `livecode_bench`, `aime_2025`, `math_500`, `mmlu`, `mmmlu`,
`mmmu_pro`, `hle`, `terminal_bench`, `arc_agi_2`, `tau2_bench`, `osworld`,
`browsecomp`, `swe_bench_pro`, `terminal_bench_21`. The issue names seven of
them and names all seven correctly.

`operational` carries the eight keys the issue lists —
`tokens_per_sec`, `cost_per_1m_input`, `cost_per_1m_output`, `vram_fp16`,
`vram_int4`, `min_gpu`, `license`, `system_ram_gb` — with `system_ram_gb`
absent from 2 of the 27 objects rather than null. A parser must tolerate a
missing key, not just a null one.

**Ground truth, verbatim.** One model object exactly as it appears in the
payload today:

```json
{
  "name": "Qwen3.6-35B-A3B",
  "provider": "Qwen",
  "providerColor": "#6C5CE7",
  "logoPath": "/logos/competitors/qwen.png",
  "parameters": "35B",
  "activeParameters": "3B",
  "contextWindow": 262144,
  "releaseDate": "2026-04-15",
  "benchmarks": {
    "mmlu_pro": 85.2, "gpqa_diamond": 86, "ifeval": null,
    "chatbot_arena": null, "swe_bench_verified": 73.4, "humaneval": null,
    "livecode_bench": 80.4, "aime_2025": null, "math_500": null,
    "mmlu": null, "mmmlu": null, "mmmu_pro": 75.3, "hle": 21.4,
    "terminal_bench": 51.5, "arc_agi_2": null, "tau2_bench": null,
    "osworld": null, "browsecomp": null, "swe_bench_pro": null,
    "terminal_bench_21": null
  },
  "operational": {
    "tokens_per_sec": 153.2, "cost_per_1m_input": null,
    "cost_per_1m_output": null, "vram_fp16": 70, "vram_int4": 18,
    "min_gpu": "1x RTX 4090 24GB", "license": "Apache 2.0",
    "system_ram_gb": 80
  }
}
```

`releaseDate` here is 2026-04-15; `docs/models.md` records 2026-04-16 for the
same model.

**A cleaner target than the HTML.** The same route answers a request carrying
an `RSC: 1` header with `content-type: text/x-component` and 41,112 bytes of
flight text and nothing else — no HTML, no script tags, no unescaping step:

```sh
curl -H 'RSC: 1' https://onyx.app/best-llm-for-coding
```

The `"config":{` locator works identically on that body. This is a Next.js App
Router convention, not a documented interface.

**What fits a 56 GB budget, by their own `vram_int4`.** Seventeen of the 27
models carry a non-null `vram_int4`. Exactly two are at or under 56:

| `vram_int4` | Model | License | `swe_bench_verified` | `tokens_per_sec` |
| --- | --- | --- | --- | --- |
| 14 | Qwen3.6-27B | Apache 2.0 | 77.2 | 56.1 |
| 18 | Qwen3.6-35B-A3B | Apache 2.0 | 73.4 | 153.2 |
| 62 | GPT-oss 120B | Apache 2.0 | 62.4 | null |

The next eight read 99, 102, 135, 142, 159, 206, 207, 214 GB, then 351, 351,
376, 500, 510, 800. The two rows the issue names are the two rows, and the
third-smallest misses by 6 GB.

Note what `tokens_per_sec` is doing there. 153.2 for the 35B-A3B and 56.1 for
the 27B are hosted-inference figures. `docs/models.md` measures 52.0 for the
35B-A3B on this machine and derives 16 for the 27B. The absolute numbers are
about three times too high for this hardware, and the ordering between the two
survives: 2.7× in onyx's figures against 3.3× measured here.

The formula behind those figures does not survive, and it is a different field.
Section 3 covers it: the per-GPU page divides bandwidth by the whole of the
weights, which reads all 35B of a 3B-active model, and that inverts the
ordering.

**Next.js version: unverified.** The `x-powered-by` header says only
`Next.js`. All 28 client chunks referenced by the page were downloaded and
searched for a version literal and none carries one. The flight envelope uses
the short-key schema (`P`, `b`, `p`, `c`, `i`, `f`, `m`, `G`, `s`, `S`), which
is App Router, but that does not pin a release. The build id
`h6RV9KYmOT25YKMj8ccXx` appears as `"b"` in the flight and changes on every
deploy.

Source: `https://onyx.app/best-llm-for-coding`, fetched 2026-08-06.

## 2. The payload is brittle in four named places, and there is no API behind it

A parser has to key off four things, in this order:

1. The literal `self.__next_f.push(` … `)</script>` script-tag shape, and the
   fact that the payload is element 1 of the parsed array. Using the `RSC: 1`
   endpoint removes this step entirely.
2. The literal string `"config":{` — the React prop name the page component is
   called with. This is source-code identifier, not data.
3. `config.models` as an array, and `config.lastUpdated` as the freshness date.
4. The snake_case benchmark and operational key names.

What breaks each: (1) is Next.js's client-payload protocol and moves between
major versions; (2) is one rename away in a file nobody outside Onyx reads;
(3) and (4) are the page's own data schema and move whenever a benchmark is
added or dropped — `terminal_bench` and `terminal_bench_21` already coexist as
separate keys, which is what a schema mid-migration looks like. The build id
changing is harmless and will happen constantly.

There is one further variance already live. The response carries
`x-feature-flags: {"leaderboard_cta_general":"b","leaderboard_cta_coding":"b",…}`
and sets a PostHog cookie, and the payload contains
`"pageFlag":"leaderboard_cta_coding"`. Today those flags select call-to-action
copy, not data. They establish that this page already varies per requester.

**No JSON API exists behind the page.** The HTML contains no `/api/` path, no
`.json` reference, and no `fetch` of a data endpoint —
the table is server-rendered into the flight and never re-fetched.
`https://onyx.app/robots.txt` disallows `/api/` for all user agents. The
`RSC: 1` endpoint is the least brittle target available, and it is still the
same undocumented payload with one layer of escaping removed.

The single sharpest signal about brittleness comes from the sibling page, and
it is in the next section: the per-GPU page used to answer the same question
and does not server-render its data at all.

Sources: `https://onyx.app/best-llm-for-coding` and
`https://onyx.app/robots.txt`, fetched 2026-08-06.

## 3. The per-GPU page returns no data to a plain GET

`GET https://onyx.app/llm-hardware-requirements` returns 200 and 58,689 bytes,
and its flight payload contains no models, no GPUs and no scores. Stripped of
markup, the entire visible body is the site chrome plus the words "LLM Model
Checker / What LLM can I run on my hardware? / Individual / Enterprise /
Share". Everything else is rendered in the browser.

Adding query parameters changes nothing on the server. `?gpu=apple-m1-max&vram=56`
and `?gpu=rtx-4090&vram=24` return payloads that differ from the bare page in
exactly one place — the router segment key, which echoes
`"__PAGE__?{\"gpu\":\"apple-m1-max\",\"vram\":\"56\"}"`. No filtering is
applied server-side.

**The parameters it accepts** are read in a `useEffect` from
`new URLSearchParams(window.location.search)`, in
`/_next/static/chunks/1265-a79672506f1ea1a7.js`:

| Parameter | Meaning | Behaviour |
| --- | --- | --- |
| `gpu` | a slug from the built-in GPU table | ignored unless it is a known slug |
| `vram` | integer GB, overrides the slug's VRAM | falls back to the slug's value |
| `bw` | integer GB/s, overrides the slug's bandwidth | falls back to the slug's value |

Absent a recognised `gpu`, the page falls back to `navigator.deviceMemory` and
`navigator.hardwareConcurrency` — browser properties that do not exist outside
a browser. `defaultProfile` is `"individual"`; the `enterprise` profile skips
the parameter handling entirely.

**The filtering is fully visible and reproducible.** The whole of it is one
predicate:

```js
n.filter(l => l.vramInt4 <= e.vramGb)
```

where `vramInt4` is `operational.vram_int4` straight from the model record and
`vramGb` is the GPU's VRAM. There is no context allowance, no KV cache term and
no runtime overhead term. Speed is estimated as

```js
t = e.bandwidthGbS / vramInt4 * (type === 'apple_silicon' ? 0.65 : 0.7)
low = 0.8t   mid = t   high = 1.15t
```

which is the bandwidth-over-weights arithmetic `docs/models.md` already does,
with a fixed 0.65 efficiency for Apple Silicon against the 0.60 dense / 0.21
MoE constants measured here, and with no distinction between dense and MoE.

**Their M1 Max is not this machine.** The GPU table hard-codes it:

```js
{slug:"m1-max", name:"Apple M1 Max", vramGb:32, bandwidthGbS:400,
 type:"apple_silicon"}
```

32 GB, against the 56 GB wired limit `fit.py` measures here and the 60 GB it
reports usable. Sixteen other Apple entries exist, `m1` through `m5-max`, each
with a single fixed VRAM figure — one number per chip, with no notion that the
same chip ships at several memory sizes. Passing `vram=56` overrides it, which
means offgrid would be supplying the only number that matters anyway.

**Its model catalogue is a different, larger one** than the coding
leaderboard's, embedded as a `JSON.parse('…')` string in the same chunk. It
carries the same record shape and includes rows the coding page omits — Gemma 4
31B, Qwen3-Coder-Next, Devstral-2-123B, Qwen3.5-9B, Qwen3.5-4B, Mistral Small 4
among them. Two pages, two catalogues, no shared source visible from outside.

Sources: `https://onyx.app/llm-hardware-requirements`,
`https://onyx.app/llm-hardware-requirements?gpu=apple-m1-max&vram=56`,
`https://onyx.app/llm-hardware-requirements?gpu=rtx-4090&vram=24`, and
`https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js`, fetched
2026-08-06.

## 3a. Their composite, and the chip table under it, read verbatim

Fetched 2026-08-07 from
`https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js` — the same
chunk hash as on 2026-08-06, so the file has not been rebuilt between the two
fetches. Deminified, their quality score is:

```js
c = round(vramInt4 / vramGb * 100)
p = c <= 70 ? 45 : round(45 * (1 - (c-70)/30) ** 2.5)                        // 45
_ = round((rank ?? 50)/100 * 30 * (0.3 + log2(clamp(activeB,1,70))/log2(70))) // 30
s = mid ? round(log2(clamp(mid,5,200)/5)/log2(40) * 13) : 6                  // 13
x = cw>4096 ? min(12, round(log2(cw/4096)/log2(62.5)*12)) : (cw>0 ? 1 : 4)   // 12
d = min(97, p + _ + s + x)
```

labelled `Excellent` at 85, `Good` at 70, `Decent` at 50, `Weak` at 30, else
`Poor`. The rank term is the one issue #26 describes: `rank` comes from a
percentile that needs six populated benchmarks and five ranked models, and the
fallback map is built from a tier table that is empty for this page, so on a
Mac it is the constant 50 and the term reduces to `0.3 + log2(active)/log2(70)`
— a reward for having more active parameters. Their efficiency figures are
`{consumer: 0.7, datacenter: 0.7, apple_silicon: 0.65}`, one number per class
with no dense-versus-mixture distinction.

Four places offgrid departs from it:

1. **The rank term** becomes the published SWE-bench figure over the same 30
   points, for the reason above. Recorded in `docs/decisions.md`.
2. **A row with no speed figure scores nothing** for speed, where theirs
   scores 6. An unmeasured chip should read as unknown, not as middling.
3. **Headroom is measured at the width being scored.** Theirs divides a fixed
   `vram_int4` by the GPU's total, so every row of a model scores the same
   headroom whatever width it is listed at. offgrid divides that width's own
   weights by what the GPU may use here. This is load-bearing: together with
   the speed term it is what makes a 4-bit build outrank the same model at
   8-bit, which their formula cannot express.
4. **The speed figure is rounded before it is clamped**, so the term is
   computed from the number printed in the table rather than the one behind
   it. Theirs clamps the raw estimate. The two differ by a point in narrow
   bands — an estimate of 5.5 to 5.9 tok/s scores 1 here and 0 there.

**The chip table**, Apple rows only, as `slug: bandwidthGbS`:

```
m1 68, m1-pro 200, m1-max 400, m1-ultra 800, m2 100, m2-pro 200, m2-max 400,
m2-ultra 800, m3 100, m3-pro 150, m3-max 400, m4 120, m4-pro 273, m4-max 546,
m5 150, m5-pro 307, m5-max 614
```

This is the only per-chip bandwidth list found, and `speed.py` carries it. Two
caveats that a measurement would settle and nothing here does. Apple ships the
M3 Max in a 300 GB/s bin as well as the 400 recorded here, and onyx has one row
per chip with no notion that a chip ships at several configurations — the same
flaw that makes their `vramGb` say an M1 Max has 32GB. And the `m5-pro` and
`m5-max` figures were not checked against Apple at all. Their `m1-max` 400 is
the figure `docs/models.md` measures against, which is the one row here that
has been corroborated.

Source: `https://onyx.app/_next/static/chunks/1265-a79672506f1ea1a7.js`,
reached from `https://onyx.app/llm-hardware-requirements`, fetched 2026-08-07.

## 4. Terms of reuse: robots.txt permits fetching; nothing grants reuse

**robots.txt.** `https://onyx.app/robots.txt`, in full for the part that
matters:

```
User-Agent: *
Allow: /
Disallow: /studio/
Disallow: /api/
```

followed by explicit `Allow: /` blocks for `GPTBot`, `OAI-SearchBot`,
`ChatGPT-User`, `PerplexityBot`, `ClaudeBot`, `anthropic-ai`,
`Google-Extended` and `Amazonbot`, and a sitemap line. Both leaderboard paths
are allowed. Automated crawling of them is not excluded, and the file names
eight AI crawlers and permits every one.

**Legal pages.** `https://onyx.app/legal` lists six documents: Cloud Terms of
Service, Self-Host Terms of Service, Privacy Policy, Service Level Agreement,
Discord Bot Terms of Service, Discord Bot Privacy Policy. There is no
site-wide terms-of-use page for visitors. The documents render "Loading…"
server-side and are fetched client-side as Markdown; the raw text is at
`https://onyx.app/legal/cloud.md` and siblings.

The Cloud agreement contains an anti-scraping restriction. From
`https://onyx.app/legal/cloud.md`, under "Restrictions", the customer shall not

> (x) "crawl," "scrape," or "spider" any page, data, or portion of or relating
> to the Services (or any information, data or content made available through
> the Services), whether through use of manual or automated means.

What that document defines itself as, in its own opening sentence:

> This Onyx Cloud Subscription Agreement (this **"Agreement"**) is entered into
> between **DanswerAI, Inc.** […] and the entity or person placing an order via
> the applicable Order Form ("**Customer**" or "**you**").

and "the Services" is defined as "the Onyx service(s) specified in such Order
Form". `https://onyx.app/legal/self-host.md` opens identically and contains no
scraping clause at all — searched, zero matches.

The Privacy Policy pulls in the other direction on scope. From
`https://onyx.app/legal/privacy-policy.md`:

> To offer this website and its software products and services (collectively,
> the **Services**), Danswer collects personal data, including from its
> customers and visitors of the Services. […] Remember that your use of the
> Services is at all times subject to our Terms of Service, which incorporates
> this Privacy Policy.

So one document defines "the Services" as what an Order Form buys, and another
defines it as including the website and refers to a singular "Terms of Service"
that the legal index does not offer to a non-customer.

**Licence on the page or in a repo.** The page states no licence. Neither does
the payload — searching the flight for `license`, `terms`, `copyright`,
`source` and `citation` returns only the per-model `operational.license` field,
which describes each *model's* licence, not the table's. The footer carries
"© 2026 Onyx" and nothing more.

Onyx is an open-source company, and the repository behind the product is
`https://github.com/onyx-dot-app/onyx`. Its `LICENSE` is MIT Expat with an
Enterprise Licence carve-out for `ee/` directories. That governs the product.
The marketing site is not among the org's 13 public repositories
(`https://api.github.com/orgs/onyx-dot-app/repos`), and no public repo carries
this leaderboard data — searched the org listing by name and description. So
the open-source licence does not reach this table.

**Contact route.** `https://onyx.app/contact` reads "Reach us at
hello@onyx.app" and links a Discord at `https://discord.gg/Pk3qzRKAEx`. Both
are open routes for asking.

**What is and is not established.** Established: the page is fetchable by
robots.txt, and robots.txt names AI crawlers and allows them. Established: no
licence, no attribution requirement and no reuse grant is stated anywhere on
the page, in the payload, or in a public repo. Established: the one
anti-scraping clause on the site sits inside a subscription agreement between
Danswer and a paying customer, and the self-host agreement has no such clause.
Not established: whether Onyx considers the marketing site's terms to bind a
non-customer, and whether it would consent to redistribution. Nothing found
answers that, and a mail to hello@onyx.app is the only way to settle it.

Sources: `https://onyx.app/robots.txt`, `https://onyx.app/legal`,
`https://onyx.app/legal/cloud.md`, `https://onyx.app/legal/self-host.md`,
`https://onyx.app/legal/privacy-policy.md`, `https://onyx.app/contact`,
`https://raw.githubusercontent.com/onyx-dot-app/onyx/main/LICENSE`,
`https://api.github.com/orgs/onyx-dot-app/repos`, fetched 2026-08-06.

## 5. The two Qwen numbers are Qwen's, republished without a source field

**onyx cites nothing.** The payload has no `source`, `citation`, `methodology`,
`harness` or `scaffold` field, at any level. Searched the full flight for each
term; the only hits on `source` are the phrase "open source" in marketing copy
and a cross-link labelled "Open Source LLM Leaderboard". The `benchmarks`
metadata object gives each benchmark a `name`, a `description` and a `category`
and no provenance. The rendered page carries no footnote either — stripped of
markup, it contains no occurrence of "methodology", "self-reported" or
"reported by".

**The numbers match Qwen's own to the decimal.**

| | onyx `swe_bench_verified` | Qwen model card | `docs/models.md` |
| --- | --- | --- | --- |
| Qwen3.6-27B | 77.2 | 77.2 | 77.2 |
| Qwen3.6-35B-A3B | 73.4 | 73.4 | 73.4 |

The `terminal_bench` values match too — 59.3 and 51.5 — as do `livecode_bench`
83.9 and 80.4 and `mmlu_pro` 86.2 and 85.2.

`https://huggingface.co/Qwen/Qwen3.6-27B/raw/main/README.md` carries a
comparison table whose SWE-bench Verified row reads: Qwen3.5-27B 75.0,
Qwen3.5-397B-A17B 76.2, Gemma4-31B 52.0, Claude 4.5 Opus 80.9,
Qwen3.6-35B-A3B 73.4, Qwen3.6-27B 77.2. Qwen measured the baselines as well as
its own models. Below the table, verbatim:

> \* SWE-Bench Series: Internal agent scaffold (bash + file-edit tools);
> temp=1.0, top_p=0.95, 200K context window. We correct some problematic tasks
> in the public set of SWE-bench Pro and evaluate all baselines on the refined
> benchmark.

The same footnote appears on
`https://huggingface.co/Qwen/Qwen3.6-35B-A3B/raw/main/README.md`. Neither card
uses the words "self-reported"; the footnote naming an internal scaffold is
what marks it, and onyx drops the footnote.

**The official SWE-bench leaderboard does not list either model.** The
leaderboard data is embedded in `https://www.swebench.com/` as JSON, split by
benchmark. The Verified split has 180 entries; none contains "Qwen3.6".
`https://api.github.com/repos/SWE-bench/experiments/contents/evaluation/verified`
lists 134 submission directories, the most recent dated 2025-12-15, and its six
Qwen entries are all Qwen2.5 or Qwen3-Coder. The highest open-weight-model
score on Verified is 71.2 (Lingxi v1.5 × Kimi K2, 2025-10-14), and
OpenHands + Qwen3-Coder-480B-A35B-Instruct sits at 69.6. Both Qwen3.6 figures
sit above every open-weight score the leaderboard has ever recorded, with no
entry of their own.

**Terminal-Bench 2.0 does have an independent Qwen3.6 run, and it is less than
half Qwen's figure.** `https://www.tbench.ai/leaderboard/terminal-bench/2.0`
carries 142 rows in its flight payload, each with `agent`, `model`, `accuracy`,
`stderr`, `verified`, `agentVersion` and `modelProviders`. Two are Qwen3.6:

| Accuracy | Agent | Version | Served by | `verified` | Date |
| --- | --- | --- | --- | --- | --- |
| 24.6 | little-coder | 0.1.14 | llamacpp | false | 2026-05-14 |
| 23.0 | little-coder | 0.1.13 | llamacpp | false | 2026-05-14 |

Both are Qwen3.6-35B-A3B, submitted by Itay Inbar
(`https://github.com/itayinbarr/little-coder`). Qwen self-reports 51.5 for that
model under the Harbor/Terminus-2 harness. The gap is not a clean refutation —
`little-coder` is a third-party agent at version 0.1.x, the run is marked
unverified, and the scaffold is not Terminus 2 — but it is an independent
counterpart where `docs/models.md` records that none exists. There is no
Qwen3.6-27B row.

`docs/models.md` states that the Terminal-Bench 2.0 leaderboard "has no Qwen3.6
entry at all". That is true of its Terminus-2 rows, which is what that
paragraph is comparing, and false of the leaderboard as fetched today.

**Verdict on onyx's numbers.** For the two models that matter here, onyx's
figures have no independent counterpart on the benchmark's own leaderboard,
match the vendor's published figures exactly, and are presented with no
indication of either fact. The one independent measurement that exists for
Qwen3.6-35B-A3B, on a different benchmark, comes in at less than half the
vendor's figure.

Sources: `https://onyx.app/best-llm-for-coding`,
`https://huggingface.co/Qwen/Qwen3.6-27B/raw/main/README.md`,
`https://huggingface.co/Qwen/Qwen3.6-35B-A3B/raw/main/README.md`,
`https://www.swebench.com/`,
`https://api.github.com/repos/SWE-bench/experiments/contents/evaluation/verified`,
`https://www.tbench.ai/leaderboard/terminal-bench/2.0`, fetched 2026-08-06.

## 6. Alternatives with cleaner provenance

Three sources publish independently-run results in machine-readable form. None
of them covers Qwen3.6.

**SWE-bench Verified.** The leaderboard data is a JSON array embedded in
`https://www.swebench.com/`, keyed by split, with fields `name`, `resolved`,
`date`, `folder`, `os_model`, `os_system`, `checked`, `logs`, `trajs`, `tags`,
`cost`. Every entry points at a directory in
`https://github.com/SWE-bench/experiments` holding the predictions, execution
logs and trajectories. Results are produced by running the harness, not by the
model vendor. Two caveats. The `experiments` repo has no `LICENSE` file — a
request for `.../main/LICENSE` returns 404, and the GitHub API reports the
repo's licence as null — so the results carry no stated reuse terms; the
benchmark code at `https://github.com/SWE-bench/SWE-bench` is MIT and that is a
different artefact. And since 2025-11-18 the repo's README restricts Verified
submissions to teams with "an arXiv preprint or technical report" and an
academic or established-research-lab affiliation, naming Augment Code, Solver
AI and Honeycomb.sh as no longer eligible. Coverage of open-weight models will
narrow, not widen.

**Aider polyglot.** `https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml`
is a 45,725-byte YAML file with 69 entries, one per run, carrying
`pass_rate_2`, `percent_cases_well_formed`, `num_malformed_responses`,
`exhausted_context_windows`, `total_cost`, `seconds_per_case`, `commit_hash`
and the exact `aider --model …` command. It lives in a repository the GitHub
API reports as Apache-2.0, which settles reuse. Runs are Aider's own, on 225
Exercism exercises across six languages. `https://aider.chat/robots.txt`
contains a sitemap line and no disallow. No Qwen3.6 entry — searched the file,
zero matches. The malformed-response and well-formed-edit columns are the
closest published proxy to the tool-calling failure mode `docs/models.md` names
as the one that costs whole turns.

**Terminal-Bench 2.0.** 142 rows in the flight payload at
`https://www.tbench.ai/leaderboard/terminal-bench/2.0`, each with `accuracy`,
`stderr`, `verified`, `agentName`, `agentVersion`, `modelProviders` and
`integrationMethod`, reachable the same way as onyx's and with the same
brittleness. The `verified` flag distinguishes runs the maintainers checked
from ones they did not, which is a provenance field onyx has no equivalent of.
`https://www.tbench.ai/robots.txt` returns the site's 404 page rather than a
robots file. The harness at `https://github.com/harbor-framework/harbor` and
the task set at `https://github.com/laude-institute/terminal-bench-datasets`
are both Apache-2.0; the leaderboard data itself states no licence. This is the
only one of the three carrying any Qwen3.6 result.

Nothing found publishes an independently-run agentic coding score for a model
that fits 56 GB, at 4-bit, on Apple Silicon. That gap is the same one
`docs/models.md` records under "What is not known", and none of these three
closes it.

## What this settles for #20

**Settled.**

- The leaderboard is reachable by a plain GET, the field names in the issue are
  correct, and the record shape is now written down with a verbatim sample. The
  `RSC: 1` endpoint is a strictly better fetch target than parsing script tags
  out of HTML.
- The two rows that survive a 56 GB budget are the two the issue names, and the
  third-smallest misses by 6 GB. The issue's arithmetic holds.
- `parameters` and `activeParameters` are strings, not numbers, and
  `system_ram_gb` can be absent rather than null. A parser has to handle both.
- No JSON API exists behind either page. `robots.txt` disallows `/api/`, and
  the HTML references no `/api/` path and fetches no `.json`.
- The per-GPU page is not a data source. It server-renders nothing, reads
  `gpu`, `vram` and `bw` in the browser, and falls back to `navigator`
  properties that do not exist outside one. Its filter is
  `vram_int4 <= vramGb` with no cache or overhead term, and offgrid can
  reproduce it in one line — which means there is nothing to trust them for.
- Their M1 Max is hard-coded at 32 GB and 400 GB/s, against the 56 GB this
  machine measures. The issue's "their memory model is not this machine's"
  is understated: it is not even the right chip's memory.
- `robots.txt` allows both pages and names eight AI crawlers with `Allow: /`.
  No licence or reuse grant is stated anywhere — page, payload, or public repo.
  The one anti-scraping clause on the site sits inside a paid subscription
  agreement. The leaderboard data is not in any public Onyx repository, so the
  MIT licence on the product does not reach it. `hello@onyx.app` is an open
  route for asking.
- The issue's core worry is confirmed and is worse than stated. onyx carries no
  provenance field of any kind, its two Qwen figures match Qwen's own to the
  decimal, and Qwen's card footnotes them to an internal agent scaffold that
  onyx drops. The official SWE-bench Verified leaderboard has never listed
  either model, and both figures sit above every open-weight score it has ever
  recorded.
- One independent measurement of Qwen3.6-35B-A3B does exist: 24.6 and 23.0 on
  Terminal-Bench 2.0 under a third-party agent, against Qwen's self-reported
  51.5. `docs/models.md` states no independent run exists, which is true of that
  leaderboard's Terminus-2 rows and false of the leaderboard as a whole.
- Aider's polyglot leaderboard is the one alternative with unambiguous reuse
  terms: a YAML file in an Apache-2.0 repository, with per-run malformed-edit
  counts. It has no Qwen3.6 entry.

**Still open.**

- Whether Onyx treats the marketing site as covered by the Cloud agreement's
  scraping clause, and whether they would consent. Only they can answer.
- Whether this is a new command or part of `setup`, whether the recommendation
  is printed or stored, and what to say when one row or no rows fit. Nothing
  found here bears on any of them.
- Whether "best" means top score or top bearable speed. The evidence sharpens
  the question rather than answering it: onyx's `tokens_per_sec` is 153.2 for
  the 35B-A3B and 56.1 for the 27B, which inverts the ordering measured on this
  machine, so a recommendation that used their speed column would be wrong in
  exactly the way the issue warns about.
- Whether a leaderboard is worth consuming at all when the two rows that fit
  are the two `docs/models.md` already covers, from the same underlying vendor
  numbers, with the harness footnote intact.
