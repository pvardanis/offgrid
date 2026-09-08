# Trail of Bits' security-analysis skills, and where they fit offgrid

Primary-source research, gathered 2026-09-08, for ticket #264. Everything below
records what Trail of Bits documents in its own repositories or blog. Where a
claim rests on a third party (Snyk, press writeups) it is marked as such.
Sources are listed with each claim and collected at the end. This is **not** a
recommendation to adopt anything: it enumerates what exists, says which pieces
could hunt bugs in offgrid's own Python, and flags — without recommending past
the flag — whether any belongs as an offgrid feature, because that collides with
two stated principles (installation isolation, and v0.1 getting out of the way).

## What it is

`trailofbits/skills` is a Claude Code **plugin marketplace**: a curated set of
plugins, each bundling one or more skills, and some also autonomous agents,
slash commands and event hooks. Licensed CC BY-SA 4.0. A separate repo,
`trailofbits/claude-code-config`, holds opinionated Claude Code defaults and is
the subject of ticket #263 / agent R1 — it is out of scope here except where the
two overlap.

The marketplace holds 42 plugins spanning smart-contract security, code
auditing, malware analysis, cryptographic verification, reverse engineering,
mobile security, and general development. Only a subset is security *analysis*;
the rest are workflow or team tooling (`culture-index`, `let-fate-decide`,
`git-cleanup`, `gh-cli`, `claude-in-chrome-troubleshooting`).

Source: <https://github.com/trailofbits/skills>,
<https://github.com/trailofbits/skills/blob/main/README.md>

## Install / enable mechanism

It is a plugin marketplace, installed and enabled entirely through the agent's
plugin system — no MCP server, no manual skill-file copying required (though the
repo is open source and can be vendored). Commands quoted verbatim from the
README:

- Add the marketplace: `/plugin marketplace add trailofbits/skills`
- Browse and install: `/plugin menu`
- Install one plugin: `/plugin install trailofbits/skills/plugins/<name>`
- Local development: `/plugins marketplace add ./skills`

Under the hood a plugin is a directory under `plugins/<name>/` holding skill
files (`SKILL.md` and supporting scripts), agent definitions, commands and
hooks — i.e. the same on-disk shape Claude Code loads from any marketplace.

Source: <https://github.com/trailofbits/skills/blob/main/README.md>

## Claude-Code-only, or portable?

Mixed. The packaging is Claude Code's plugin/marketplace format. Portability
claims found:

- **Codex**: the README states Codex supports Claude plugin marketplaces
  directly, so the repo ships no Codex-specific metadata. Documented commands:
  `codex plugin marketplace add trailofbits/skills`, `codex plugin list`,
  `codex plugin add <plugin-name>@trailofbits`.
- Two individual plugins name cross-agent compatibility in their own docs:
  `goal-prompt` ("Claude Code and Codex compatible") and `second-opinion`
  (drives "OpenAI Codex, Google Antigravity" as external reviewers).
- **OpenCode**: no statement of support found in ToB's own materials. OpenCode
  is not mentioned. A skill is ultimately a Markdown instruction file plus
  scripts, so the *content* is portable in principle to any agent that can load
  system-prompt fragments and run the bundled tools; the *marketplace install
  path* is not. This is inference, labelled as such — treat OpenCode support as
  unestablished, not confirmed.

Note the dependency shape: many analysis plugins are thin orchestration around
external binaries (CodeQL, Semgrep, the Hypothesis/Echidna/Medusa families,
YARA linters). The skill teaches the agent to drive the tool; the tool still
has to be installed. That matters for both portability and for any offgrid use.

Source: <https://github.com/trailofbits/skills/blob/main/README.md>

## The security-analysis plugins

Enumerated from the `plugins/` directory listing and the README inventory. Each
row: what it analyses / what it produces. Coverage strings are ToB's own.

### Code auditing (language-general or multi-language)

| Plugin | Analyses | Produces |
|---|---|---|
| `static-analysis` | source code via CodeQL (interprocedural taint/dataflow) and Semgrep (pattern scan) | SARIF, merged and deduplicated across tools. Sub-skills: `codeql`, `semgrep`, `sarif-parsing`. CodeQL langs incl. **Python**, JS, Go, Java, C/C++ |
| `semgrep-rule-creator` | vulnerability patterns you describe | custom Semgrep rules |
| `semgrep-rule-variant-creator` | existing Semgrep rules | ported rules, multi-language, with test validation |
| `variant-analysis` | a codebase, for further instances of a known bug | pattern-based findings |
| `fp-check` | candidate security findings | verified findings after gate reviews (false-positive filtering) |
| `differential-review` | a code change + git history | security-focused diff review with blast-radius estimate |
| `insecure-defaults` | configuration | fail-open / insecure-default findings |
| `sharp-edges` | error-prone APIs and configs | identified footguns |
| `audit-context-building` | codebase functions | contextual analysis to prime an audit |
| `dimensional-analysis` | formulas in code | annotated comments (unit/dimension checking) |
| `supply-chain-risk-auditor` | npm, **PyPI**, Go dependencies | dependency risk report |
| `vulnerability-triage-brocards` | vulnerability reports | accept / dismiss / need-more-info via 7 "brocards" |
| `agentic-actions-auditor` | GitHub Actions workflows | findings on AI-agent-integration vulns (Claude Code Action, Gemini CLI, Codex, GH AI Inference) |
| `burpsuite-project-parser` | Burp Suite project files | extracted web-security data |

### Verification / testing

| Plugin | Analyses | Produces |
|---|---|---|
| `property-based-testing` | test properties | test reviews + triage; Hypothesis, fast-check, proptest, Solidity invariants (Echidna/Medusa) |
| `mutation-testing` | test targets | mutation campaign configurations |
| `testing-handbook-skills` | code + test suites | fuzzer / static-analysis / sanitizer configs |
| `spec-to-code-compliance` | code vs. its documentation/spec | compliance verification |
| `constant-time-analysis` | crypto code (C/C++, Rust) | timing side-channel findings |
| `zeroize-audit` | secret-handling code (C/C++, Rust) | missing-zeroization findings |
| `writing-lean-proofs` | Lean 4 code | structured proofs |

### Language-specific review (systems / crypto)

| Plugin | Analyses | Produces |
|---|---|---|
| `c-review` | C/C++ | security review with coverage verification |
| `rust-review` | Rust (safe/unsafe boundary, memory, concurrency, panic-DoS, FFI, async) | SARIF |
| `modern-cpp` | C++20/23/26 | best-practice + compiler-hardening recommendations |

### Smart contract / malware / RE / mobile (out of scope for offgrid)

`building-secure-contracts`, `entry-point-analyzer`, `trailmark` (also does code
graphs + mutation-testing triage), `yara-authoring`, `dwarf-expert`,
`firebase-apk-scanner`. None touches a macOS Python CLI.

### Development (adjacent, not security analysis)

`modern-python`, `code-improver`, `open-sourcing`, `devcontainer-setup`,
`second-opinion`, `github-triage`, `goal-prompt`.

`modern-python` is worth naming: it scaffolds/aligns a Python project on uv,
ruff, ty (type checker), pytest with coverage, plus a security layer of
detect-secrets, shellcheck, actionlint, zizmor, pip-audit and Dependabot. This
is close enough to offgrid's own stated toolchain (uv, `just check`, prek,
zizmor, actionlint from CLAUDE.md) to be either a cross-check or a source of
overlap/conflict — it is a quality+security scaffolder, not a vuln hunter.

Source: <https://github.com/trailofbits/skills/tree/main/plugins>,
<https://github.com/trailofbits/skills/blob/main/README.md>,
<https://github.com/trailofbits/skills/tree/main/plugins/static-analysis>,
<https://github.com/trailofbits/skills/blob/main/plugins/modern-python/README.md>

## Which help hunt vulnerabilities in offgrid's OWN Python code (dev-tooling, #268)

offgrid is a macOS/Apple-Silicon Python CLI+TUI that shells out to local runtime
servers and launches coding agents. Its realistic attack surface is: HTTP calls
to localhost runtimes, subprocess launches, filesystem reads/writes of profile
and discarded-windows files, and third-party Python dependencies. Against that,
the plugins that would genuinely pull their weight:

- **`static-analysis`** — the centrepiece. CodeQL and Semgrep both cover
  Python; produces SARIF that can gate CI. Best single fit for finding taint /
  injection / unsafe-subprocess issues in the codebase. Cost: CodeQL and
  Semgrep binaries must be installed; CodeQL DB builds are not free.
- **`supply-chain-risk-auditor`** — explicitly covers PyPI. Directly relevant
  given offgrid pulls runtime/agent client libraries. Overlaps pip-audit /
  Dependabot already implied by CLAUDE.md; complements rather than duplicates
  (it does risk analysis, not just known-CVE matching).
- **`semgrep-rule-creator`** / **`variant-analysis`** — once a bug class is
  found, write a Semgrep rule for it and sweep for siblings. High value for a
  small codebase with recurring patterns (e.g. every subprocess call site,
  every profile-file parse).
- **`fp-check`** — pairs with the above to keep the signal clean; useful only
  once you have findings to triage.
- **`differential-review`** — per-PR security diff with blast radius; fits the
  ≤500-line one-kind-of-change PR rhythm the repo already runs.
- **`insecure-defaults`** / **`sharp-edges`** — cheap passes over config and
  error-prone API use; low setup cost, moderate signal for a CLI that spawns
  processes and writes user files.
- **`property-based-testing`** / **`mutation-testing`** — align with the repo's
  existing Hypothesis-friendly, `just mutate` mutation-testing setup. These are
  test-quality tools more than vuln hunters, but they harden the parsers
  (profile file, discarded-windows file, adapter payloads) that are the fragile
  surfaces.

Not useful for offgrid's own code: everything C/C++/Rust/crypto-specific
(`c-review`, `rust-review`, `constant-time-analysis`, `zeroize-audit`,
`modern-cpp`), all smart-contract/malware/RE/mobile plugins, and Lean proofs.
`agentic-actions-auditor` is a maybe — offgrid's CI is GitHub Actions and this
audits agent-integration workflows specifically, but offgrid does not (yet) run
Claude Code Action or similar in CI, so it has little to bite on today.

## Worth exposing as an offgrid FEATURE? (flag, not recommend)

The tension, stated in CLAUDE.md and the ticket: offgrid's principle is
**installation isolation** — "none of a person's own plugins reach a run" — and
v0.1 "connects one runtime to one agent and gets out of the way." Bundling or
auto-installing ToB security skills into the runs offgrid launches would
directly contradict both: it injects offgrid's chosen third-party plugins into
the user's agent session, which is exactly the leakage the isolation principle
forbids, and it is scope well beyond "one runtime, one agent."

Flags, not recommendations:

- **Against, on principle**: any path where offgrid installs or enables these
  into a launched run breaks installation isolation. If offgrid ever ships a
  curated plugin set, that is a deliberate future decision (a "verified" mode,
  itself listed as later scope), not a v0.1 feature, and it needs its own
  `docs/decisions.md` entry.
- **The one genuinely feature-adjacent candidate is `modern-python`** — not as
  something offgrid *runs for the user*, but because it codifies almost the same
  toolchain offgrid already mandates. If anything crosses over, it is as a
  reference for offgrid's *own* project standards (dev tooling, #268), not as a
  runtime feature. That keeps it on the correct side of the isolation line.
- **Everything else is dev-tooling only**: valuable for hardening offgrid's
  code (see #268), inert or contradictory as a shipped feature.

Net: nothing here earns a place as a v0.1 offgrid feature given the isolation
principle. The value is entirely on the dev-tooling side.

## Sources

- Trail of Bits skills repo: <https://github.com/trailofbits/skills>
- README (inventory + install + Codex compat): <https://github.com/trailofbits/skills/blob/main/README.md>
- Plugins directory: <https://github.com/trailofbits/skills/tree/main/plugins>
- static-analysis plugin: <https://github.com/trailofbits/skills/tree/main/plugins/static-analysis>
- modern-python plugin: <https://github.com/trailofbits/skills/blob/main/plugins/modern-python/README.md>
- claude-code-config repo (adjacent, ticket #263): <https://github.com/trailofbits/claude-code-config>
- Snyk review (third-party, reception + framing): <https://snyk.io/articles/top-claude-skills-cybersecurity-hacking-vulnerability-scanning/>
