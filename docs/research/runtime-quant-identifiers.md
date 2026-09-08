<!-- How local-model runtimes identify a model and its quantization variant. -->

# How runtimes identify a model and its quantization

The question: can quantization live purely inside an opaque model-identifier
string, or must it be a separate field? Crux: is LM Studio the outlier in
overloading one identifier across simultaneously-available quant variants?

Facts below are from primary sources (official API docs, source READMEs, CLI
references). Every claim cites a URL.

## Ollama

- **Q_A — identifier**: `model` field in `model:tag` form, e.g.
  `"orca-mini:3b-q8_0"`, `"llama3:70b"`. Tag defaults to `latest`.
- **Q_B — quant location**: encoded **inside the tag**
  (`orca-mini:3b-q8_0`). A separate `details.quantization_level` (e.g.
  `"Q4_K_M"`) is *also* reported in list responses, but the request identifier
  carries the quant in its tag.
- **Q_C — one-id-to-many**: no. Each installed quant is pulled under its own
  distinct `model:tag` name.
- **Q_D — listing shape**: `/api/tags` and `/api/ps` return a flat array; each
  quant is its own object with its own `name` plus a nested `details` object.
  No variants array.
- Source: <https://github.com/ollama/ollama/blob/main/docs/api.md>

**Verdict**: one identifier per quant; quant lives in the tag string. Not an
LM-Studio-style overload.

## llama.cpp `llama-server`

- **Q_A — identifier**: the loaded model is set at launch by `-m/--model FNAME`
  (file path), or `-hf <user>/<model>[:quant]`. In OpenAI-compatible endpoints
  (`/v1/models`, `/v1/chat/completions`) the `model` `id` defaults to the model
  file path and can be overridden with `--alias STRING`.
- **Q_B — quant location**: part of the identifier — the `-hf` form takes an
  optional quant tag, e.g. `ggml-org/GLM-4.7-Flash-GGUF:Q4_K_M`. No separate
  quant field; the quant is baked into the GGUF file you point at.
- **Q_C — one-id-to-many**: no. Single-model mode (`-m`) serves exactly one
  model/quant. Router mode (`--models-dir` / `--models-preset`) exposes several
  models, but each is a distinct id, not variants under one id.
- **Q_D — listing shape**: `/v1/models` lists each served model as its own `id`
  entry. No nested variants.
- Source:
  <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>

**Verdict**: one id per loaded quant; quant is the GGUF file / `-hf` tag. Not an
LM-Studio-style overload.

## MLX / mlx-lm server

- **Q_A — identifier**: `--model` arg and request `model` field are a
  HuggingFace repo path, e.g. `mlx-community/Llama-3.2-3B-Instruct-4bit`.
- **Q_B — quant location**: encoded **inside the repo name** by convention
  (`-4bit` suffix). Quantization is a separate parameter (`quantize=True`) only
  at *convert* time; once published, the quant is part of the repo identifier.
- **Q_C — one-id-to-many**: no. Each quant is a separate HF repository with its
  own path (thousands in the MLX Community org).
- **Q_D — listing shape**: each model/quant is its own repo id. No variants
  array at the identifier level.
- Source: <https://github.com/ml-explore/mlx-lm/blob/main/README.md>

**oMLX** (`jundot/omlx`): a menu-bar MLX inference server for Apple Silicon,
OpenAI- and Anthropic-compatible, multi-model. It serves "any MLX-format model
from HuggingFace" and reads the HF cache and the LM Studio folder directly, so
it inherits the MLX repo-name convention above (quant in the folder/repo name,
one id per quant). It does *not* re-expose LM Studio's variants array; each
served model is its own entry.
Sources: <https://github.com/jundot/omlx>, <https://omlx.ai/>

**Verdict**: one id per quant; quant lives in the repo/folder name. Not an
LM-Studio-style overload.

## vLLM

- **Q_A — identifier**: `--model` (HF id or local path). The API-facing name is
  `--served-model-name` (an alias); if omitted it defaults to the `--model`
  value. That name is what `/v1/models` and response `model` fields report.
- **Q_B — quant location**: a **separate** flag. `--quantization` names the
  weight-quant method, independent of `--model`; if `None`, vLLM reads the
  model config's `quantization_config`. This is the clearest separate-field
  case of the four.
- **Q_C — one-id-to-many**: no. One `vllm serve` process loads one model with
  one quantization. `--served-model-name` can supply multiple *aliases* for the
  same single loaded model — that is many-names-to-one-model, the inverse of
  one-name-to-many-quants.
- **Q_D — listing shape**: `/v1/models` reports the served name(s); one loaded
  model per server. No variants array.
- Sources:
  <https://docs.vllm.ai/en/stable/cli/serve/>,
  <https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html>

**Verdict**: quant is a fully separate flag; one loaded quant per server. Not an
LM-Studio-style overload.

## Summary

| runtime | quant in identifier? | one-id-many-variants? | verdict |
|---|---|---|---|
| Ollama | yes (in the `:tag`) | no — one `model:tag` per quant | separate ids |
| llama.cpp | yes (GGUF file / `-hf :quant`) | no — one model per `-m`, router = distinct ids | separate ids |
| MLX / mlx-lm | yes (repo name `-4bit`) | no — separate HF repo per quant | separate ids |
| oMLX | yes (repo/folder name) | no — one entry per model | separate ids |
| vLLM | no — separate `--quantization` flag | no — one loaded quant per server | separate field |

**Bottom line**: LM Studio **is the outlier**. Every other runtime surveyed
gives each installed quantization its own distinct identifier — either by baking
the quant into the identifier string (Ollama tag, GGUF file, MLX repo name) or
by keeping it a separate load-time flag (vLLM). None exposes one identifier that
resolves to multiple simultaneously-available quant variants the way LM Studio's
`modelKey` carries `variants: [id@4bit, id@8bit]`.

**Design implication**: quantization can live inside an opaque identifier string
for every runtime except vLLM, where it is a separate load parameter. But for
*listing what is installed*, no runtime except LM Studio groups quants under one
identifier — so a per-quant identifier is the common shape, and LM Studio's
variants array is the case that needs special handling.
