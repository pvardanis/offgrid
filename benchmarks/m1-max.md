# Measured on an M1 Max

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
