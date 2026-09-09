# Security-analysis dev tooling

Where offgrid's security-analysis skills live and how to run them. This is
tooling for hunting vulnerabilities in offgrid's *own* Python — it never
reaches a run offgrid launches. Installation isolation still holds: none of
these plugins are injected into the agent sessions offgrid starts for a person.
The reasoning, and why none of them is a v0.1 product feature, is in
`docs/research/tob-security-skills.md` (ticket #264); the effort that decided to
couple this dev-env work to the security map is #268 under #261.

Written 2026-09-09.

## What is installed

Trail of Bits publishes a Claude Code plugin marketplace, `trailofbits/skills`.
The marketplace and the plugins offgrid uses are declared at **project scope**
in `.claude/settings.json` (`extraKnownMarketplaces` and `enabledPlugins`), so
they travel with the repo and stay out of a contributor's other projects. A
plugin bundles skills; a skill loads its full instructions only when invoked, so
each adds only a small always-on cost to a session (static-analysis is
~700 tokens) and its real cost is paid on use.

The enabled set, scoped to what bites on a macOS Python CLI (the rest of the
marketplace is C/C++/Rust/crypto/smart-contract/malware work that offgrid has no
surface for):

| Plugin | What it does for offgrid |
|---|---|
| `audit-context-building` | Reads the codebase a function at a time to understand it before any bug hunting — ToB's documented starting point. No binary. |
| `static-analysis` | CodeQL + Semgrep over the Python, merged to SARIF — the main source of taint / injection / unsafe-subprocess findings. Skills: `codeql`, `semgrep`, `sarif-parsing`. |
| `supply-chain-risk-auditor` | Risk report on PyPI dependencies — complements pip-audit / Dependabot, which match known CVEs rather than assess risk. |
| `semgrep-rule-creator` | Turns a described vulnerability pattern into a custom Semgrep rule. |
| `variant-analysis` | Sweeps the codebase for further instances of a bug already found. |
| `fp-check` | Filters false positives out of candidate findings. Useful once there are findings to triage. |
| `differential-review` | Security-focused diff review with a blast-radius estimate — fits the per-PR, one-kind-of-change rhythm. |
| `insecure-defaults` | Flags fail-open / insecure-default configuration. |
| `sharp-edges` | Flags error-prone APIs and configs — footguns in a CLI that spawns processes and writes user files. |
| `property-based-testing` | Reviews and triages test properties. Hardens the parsers (profile file, discarded-windows file, adapter payloads). |
| `mutation-testing` | Configures mutation campaigns — aligns with the existing `just mutate`. |
| `modern-python` | Reference only, not a vuln hunter: it codifies almost the same uv / ruff / pytest / detect-secrets toolchain offgrid already mandates, so it is a cross-check on `CLAUDE.md`'s standards, nothing offgrid runs for a user. |

## Prerequisites

Most of these skills teach the agent to drive an external binary; the binary
still has to be on the machine. `static-analysis` needs both:

- **Semgrep**: `uv tool install semgrep` (or `brew install semgrep`).
- **CodeQL**: `brew install --cask codeql`, or
  `gh extension install github/gh-codeql` (then `gh codeql install-stub`), or the
  codeql-bundle from `github/codeql-action` releases put on `PATH`. CodeQL builds
  a database before it queries, which is not free on a large tree; expect the
  first run to be slow. On Apple Silicon, an exit code 137 mid-build is an
  `arm64e`/`arm64` mismatch rather than a build failure — reach for Homebrew
  arm64 tools or Rosetta before falling back to `build-mode=none`.

Every other plugin drives tooling offgrid already carries or the agent itself,
and needs nothing extra beyond what a given run asks for.

## How to run them

They are skills, not `just` recipes: run them from a Claude Code session opened
on this repo by asking for the work in plain language — no security background
needed, the skill drives the tool and explains what it finds. `static-analysis`
presents its scan plan and waits for approval before running anything.

A run in order — the sequence is a suggested pipeline; ToB's one documented
sequencing is "understand before hunting", which is step 0:

| Step | Ask, in plain language | Skill | Needs |
|---|---|---|---|
| 0. Understand first | "Build audit context for this codebase." | `audit-context-building` | — |
| 1. Dependencies | "Audit our PyPI dependencies for supply-chain risk." | `supply-chain-risk-auditor` | — |
| 2. Config and footguns | "Check for insecure defaults and sharp edges." | `insecure-defaults`, `sharp-edges` | — |
| 3. Main scan | "Run a static-analysis scan for injection and unsafe subprocess use." | `static-analysis` | Semgrep + CodeQL |
| 4. Triage | "Triage these findings for false positives." | `fp-check` | — |
| 5. Sweep for siblings | "Write a Semgrep rule for this bug and find other instances." | `semgrep-rule-creator`, `variant-analysis` | Semgrep |
| Per-PR | "Security diff review of this branch against main." | `differential-review` | — |

Steps 0–2 need no binaries; step 3 waits until Semgrep and CodeQL are installed
(above). `property-based-testing`, `mutation-testing` and `modern-python` sit
outside this pipeline — reach for them when hardening the parsers or
cross-checking the project's standards, not as part of an audit pass.

`claude plugin list` shows what is enabled; `claude plugin details <name>@trailofbits`
shows a plugin's skills and its token cost. A plugin is enabled or disabled for
the repo by editing `enabledPlugins` in `.claude/settings.json`, or with
`claude plugin enable|disable <name>@trailofbits --scope project`.
