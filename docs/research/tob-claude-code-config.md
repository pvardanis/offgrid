<!-- Research notes for ticket #262: what Trail of Bits' claude-code-config concretely ships. -->

# Trail of Bits `claude-code-config` — what it actually provides

Research for ticket #262. Primary source, read on 2026-09-08:
<https://github.com/trailofbits/claude-code-config> (repo `main` branch).

## Summary

The repo is a set of opinionated Claude Code defaults for security work: a
`settings.json` template, a global `CLAUDE.md` template plus path-scoped
language rules, two example hook scripts, a statusline script, an MCP server
template, and a few workflow commands. There is no bespoke sandboxing code —
the hardening it ships is (a) a `permissions.deny` list and (b) two inline
`PreToolUse` Bash hooks. Actual isolation is delegated to Claude Code's own
native `/sandbox` (OS primitives), or to a devcontainer / remote droplet.

## Repository layout

All 17 tracked files (from the git tree API):

```
.claude/commands/trailofbits/config.md   # the /trailofbits:config installer
.gitignore
README.md
claude-md-template.md                     # global CLAUDE.md template
mcp-template.json                          # ~/.mcp.json template (Context7, Exa, Granola)
settings.json                              # the settings template
commands/fix-issue.md
commands/merge-dependabot.md
commands/review-pr.md
hooks/enforce-package-manager.sh           # EXAMPLE hook, not wired in settings.json
hooks/log-gam.sh                           # EXAMPLE hook, not wired in settings.json
rules/bash.md
rules/github-actions.md
rules/python.md
rules/rust.md
rules/typescript.md
scripts/statusline.sh
```

Install is `/trailofbits:config`: fetches these from GitHub into `~/.claude/`,
merging into an existing `settings.json` rather than overwriting, prompting
before clobbering a user `CLAUDE.md` or rule file, and rewriting internal path
references to `$CLAUDE_CONFIG_DIR` if non-default.

## 1. `settings.json` — verbatim

Source: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/settings.json>

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "cleanupPeriodDays": 365,
  "env": {
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "3"
  },
  "enableAllProjectMcpServers": false,
  "permissions": {
    "deny": [
      "Bash(rm -rf *)",
      "Bash(rm -fr *)",
      "Bash(sudo *)",
      "Bash(mkfs *)",
      "Bash(dd *)",
      "Bash(wget *|bash*)",
      "Bash(wget *| bash*)",
      "Bash(git push --force*)",
      "Bash(git push *--force*)",
      "Bash(git reset --hard*)",
      "Edit(~/.bashrc)",
      "Edit(~/.zshrc)",
      "Edit(~/.ssh/**)",
      "Read(~/.ssh/**)",
      "Read(~/.gnupg/**)",
      "Read(~/.aws/**)",
      "Read(~/.azure/**)",
      "Read(~/.config/gh/**)",
      "Read(~/.git-credentials)",
      "Read(~/.docker/config.json)",
      "Read(~/.kube/**)",
      "Read(~/.npmrc)",
      "Read(~/.npm/**)",
      "Read(~/.pypirc)",
      "Read(~/.gem/credentials)",
      "Read(~/Library/Keychains/**)",
      "Read(~/Library/Application Support/**/metamask*/**)",
      "Read(~/Library/Application Support/**/electrum*/**)",
      "Read(~/Library/Application Support/**/exodus*/**)",
      "Read(~/Library/Application Support/**/phantom*/**)",
      "Read(~/Library/Application Support/**/solflare*/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "CMD=$(jq -r '.tool_input.command'); if echo \"$CMD\" | grep -qiE '(^|;[[:space:]]*|&&[[:space:]]*|[|][|][[:space:]]*|[|][[:space:]]*)rm[[:space:]]' && echo \"$CMD\" | grep -qiE '(^|[[:space:]])-[a-zA-Z]*[rR]|--recursive' && echo \"$CMD\" | grep -qiE '(^|[[:space:]])-[a-zA-Z]*[fF]|--force'; then echo 'BLOCKED: Use trash instead of rm -rf' >&2; exit 2; fi"
          },
          {
            "type": "command",
            "command": "CMD=$(jq -r '.tool_input.command'); if echo \"$CMD\" | grep -qE 'git[[:space:]]+push.*(main|master)'; then echo 'BLOCKED: Use feature branches, not direct push to main' >&2; exit 2; fi"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

### What each key does

Non-permission keys:

- `cleanupPeriodDays: 365` — keep chat history 365 days instead of the default 30.
- `env.DISABLE_TELEMETRY` / `DISABLE_ERROR_REPORTING` / `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY` — turn off Statsig telemetry, Sentry error reporting, and the feedback survey.
- `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` — enable the experimental multi-agent teams feature.
- `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: "3"` — cap subagent nesting at 3 levels.
- `enableAllProjectMcpServers: false` — do not auto-enable MCP servers declared by a checked-out repo (blocks a malicious repo shipping its own MCP server).
- `statusLine` — run `~/.claude/statusline.sh` as the status bar.

### `permissions.deny` — what each entry blocks

Deny rules are matched by Claude Code against its own tool calls (`Bash`,
`Edit`, `Read`). They are **tool-level**, not OS-level, unless sandbox
auto-allow mode is active (see section 3).

Dangerous Bash commands:

- `Bash(rm -rf *)`, `Bash(rm -fr *)` — recursive force delete.
- `Bash(sudo *)` — privilege escalation.
- `Bash(mkfs *)` — formatting a filesystem.
- `Bash(dd *)` — raw disk writes.
- `Bash(wget *|bash*)`, `Bash(wget *| bash*)` — curl-pipe-to-shell style remote execution (the `wget ... | bash` pattern).
- `Bash(git push --force*)`, `Bash(git push *--force*)` — force push.
- `Bash(git reset --hard*)` — destructive reset.

Shell config editing:

- `Edit(~/.bashrc)`, `Edit(~/.zshrc)` — block editing login shell startup files (a persistence vector).

Credential / secret reads (and SSH edit):

- `Edit(~/.ssh/**)`, `Read(~/.ssh/**)` — SSH keys.
- `Read(~/.gnupg/**)` — GPG keys.
- `Read(~/.aws/**)`, `Read(~/.azure/**)`, `Read(~/.kube/**)` — cloud / cluster creds.
- `Read(~/.config/gh/**)` — GitHub CLI auth.
- `Read(~/.git-credentials)` — stored git credentials.
- `Read(~/.docker/config.json)` — Docker registry auth.
- `Read(~/.npmrc)`, `Read(~/.npm/**)`, `Read(~/.pypirc)`, `Read(~/.gem/credentials)` — package registry tokens.
- `Read(~/Library/Keychains/**)` — macOS keychain.
- `Read(~/Library/Application Support/**/{metamask,electrum,exodus,phantom,solflare}*/**)` — crypto wallet app data.

There is **no `allow` array** — the template only denies.

## 2. Hooks

Two distinct things carry the name "hook" here.

### 2a. Hooks actually wired into `settings.json`

Both are `PreToolUse` hooks matching the `Bash` tool, written as **inline Bash
one-liners** (not files). Each reads `.tool_input.command` via `jq` and
`exit 2` to block (exit 2 = blocking error, stderr is fed back to Claude):

1. **rm -rf guard** — blocks a command that contains an `rm` (at start or after
   `;`, `&&`, `||`, `|`) *and* a recursive flag (`-r`/`-R`/`--recursive`) *and*
   a force flag (`-f`/`-F`/`--force`). Message: `BLOCKED: Use trash instead of
   rm -rf`. Note this is broader than the `permissions.deny` glob because it
   catches `rm` in pipelines/compound commands and flag reordering.
2. **push-to-main guard** — blocks `git push ... (main|master)`. Message:
   `BLOCKED: Use feature branches, not direct push to main`.

### 2b. Example hook scripts in `hooks/` (NOT wired into settings.json)

These ship as adaptable examples; the installer does not reference them in
`settings.json`. Both are Bash (`#!/bin/bash`, `set -euo pipefail`).

- `hooks/enforce-package-manager.sh` — a `PreToolUse` example. Reads
  `.tool_input.command`; if the project has a `pnpm-lock.yaml` and the command
  starts with `npm `, it emits `BLOCKED: This project uses pnpm, not npm. Use
  pnpm instead.` and `exit 2`. Header comment says to adapt it for any
  "use X not Y" convention (yarn/npm, uv/pip).
- `hooks/log-gam.sh` — a `PostToolUse` example, purely observational (never
  blocks). Detects Google Apps Manager (GAM) *write* mutations (create, update,
  delete, suspend, etc.), skips read-only verbs (print/show/list/get), and
  appends an audit record (timestamp, action, command, exit status) to
  `.changelog-raw.jsonl`.

### Hook model (from README)

README frames hooks as "structured prompt injection at opportune times,"
explicitly *not* a security boundary. Events referenced: `PreToolUse` (can
block), `PostToolUse` (logging), `UserPromptSubmit` (can block), `Stop` (can
force continuation). Exit codes: `0` allowed, `1` non-blocking error, `2`
blocking error (stderr returned to Claude).

## 3. The `sandbox` command — the boundary

There is **no sandbox script in this repo.** `/sandbox` is **Claude Code's own
native feature**, and the repo only documents it and layers deny rules on top.
Per the README:

- Native filesystem + network isolation using **OS-level primitives:
  Seatbelt (`sandbox-exec`) on macOS, bubblewrap on Linux.**
- Default policy: writes restricted to the current directory and subdirectories;
  reads unrestricted; network limited to explicitly allowed domains.
- In sandbox **auto-allow mode**: Bash commands that stay within sandbox
  boundaries run without permission prompts, and the `permissions.deny` rules
  become **OS-enforced** (the OS blocks the Bash command, not just Claude's
  built-in tool layer). This is the only path by which the deny list becomes a
  real boundary rather than a cooperative check.
- README recommends pairing `--dangerously-skip-permissions` with sandboxing
  for throughput while keeping an OS boundary.
- Alternative isolation the README points to (not code in this repo):
  **devcontainer** (agent in a container, only project files mounted) and
  **remote droplets** via the `dropkit` tool (disposable cloud instances).

**Boundary for offgrid:** ToB provides no portable sandbox implementation to
lift. The macOS isolation is Claude Code invoking Seatbelt internally; we do
not get a reusable `sandbox-exec` wrapper from this repo. Any offgrid isolation
effort would either shell out to `sandbox-exec` ourselves or reuse an agent's
native sandbox — this repo is a reference for *policy* (what to deny), not a
*mechanism* to adopt. This is context only; do not design it here.

## 4. Claude-Code-specific vs portable

**Claude-Code-specific (not portable as-is to OpenCode/another agent):**

- `settings.json` schema entirely — `permissions.deny` glob syntax
  (`Bash(...)`, `Read(...)`, `Edit(...)`), the `hooks` block shape
  (`PreToolUse`/`matcher`/`type: command`), `statusLine`, `enableAllProjectMcpServers`.
- `CLAUDE_CODE_*` env vars and the telemetry-disable vars.
- The hook JSON payload contract (`jq -r '.tool_input.command'`, exit-code 2
  blocking, stderr fed to the model).
- `/sandbox`, `/trailofbits:config`, and the `commands/*.md` slash commands.
- Install locations (`~/.claude/`, `~/.mcp.json`, `~/.claude/commands/`).

**Portable ideas / assets (the policy, not the wiring):**

- The **deny *policy*** — the concrete list of credential paths and dangerous
  commands worth blocking. The list of secrets to protect and destructive
  commands to refuse transfers to any agent; only the expression differs.
- The **hook *logic*** — the two guard scripts are plain Bash reading a command
  string and returning a block/allow decision. The detection regexes are
  reusable; the plumbing (how the agent invokes the hook and reads its verdict)
  is per-agent.
- `mcp-template.json` — standard MCP server config; MCP is a cross-agent
  protocol, so the server definitions themselves are broadly portable.
- The language `rules/*.md` and `claude-md-template.md` — plain Markdown
  guidance; content is agent-agnostic, only the load mechanism (path-scoped
  frontmatter) is Claude-Code-specific.

## Sources

- Repo: <https://github.com/trailofbits/claude-code-config>
- `settings.json`: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/settings.json>
- `hooks/enforce-package-manager.sh`: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/hooks/enforce-package-manager.sh>
- `hooks/log-gam.sh`: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/hooks/log-gam.sh>
- `README.md`: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/README.md>
- `.claude/commands/trailofbits/config.md`: <https://raw.githubusercontent.com/trailofbits/claude-code-config/main/.claude/commands/trailofbits/config.md>
