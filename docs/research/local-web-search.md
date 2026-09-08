<!-- How a coding session against a locally-held model can search the web with the search run on this machine, and what leaves the machine when it does. -->

# Local web search for a held model

Research ticket #263, context for issue #10.

The question: how can a coding session driving a locally-held model search
the web when the search itself runs on *this* machine — no vendor-hosted
search tool? And, for the domain model: for each option, what actually leaves
this machine when the tool runs, and to whom?

The short answer: "search runs on this machine" is a claim about *where the
tool process runs*, not about *where the query ends up*. Every option below
runs the tool process locally (an MCP server spawned by the agent), but almost
all of them then send the query text off-machine to some search engine. The
only way to keep the query fully on-machine is to point the tool at a
self-hosted index — and even a self-hosted SearXNG forwards the query onward
to Google/Bing/DuckDuckGo/etc. There is no keyless, fully-on-machine web index
in any of these tools. That distinction is the whole point for offgrid's
modelling.

Facts below are from primary sources (project repos, official docs). Every
claim cites a URL.

## The shape of the problem

An agent (Claude Code or OpenCode) can call a *tool*. A local web-search tool
is an MCP server: a process the agent spawns on this machine over stdio. When
the model decides to search, the agent hands the query to that local process.
What the local process does with the query is the variable that matters:

- **Scrape/call a public engine directly** (DuckDuckGo HTML, Brave API) —
  query leaves the machine, straight to that engine's servers.
- **Call a self-hosted metasearch instance** (SearXNG on localhost) — query
  leaves the local *tool* only to reach a local *instance*, which then fans
  the query out to upstream engines. Still leaves the machine, just one hop
  later and to several engines at once.
- **Route through the model provider's own search tool** (Anthropic
  `web_search`, OpenAI `web_search`) — only meaningful when the model is
  remote; irrelevant to a locally-held model.

None of these is a local index. There is no "grep the web offline" option.

## 1. Local MCP search servers — what exists

### DuckDuckGo — `nickclyde/duckduckgo-mcp-server`

- Maintainer: Nick Clyde (community). Python, MIT, on PyPI. The most widely
  adopted keyless search MCP.
- **Needs**: nothing — no API key, no account, no self-hosted index. Plain
  network egress.
- **Runs locally**: the MCP process. **Calls remotely**: it queries
  DuckDuckGo's public HTML endpoint `html.duckduckgo.com`.
- Tools: `search()`, `fetch_content()`, `expand_link()`.
- Reliability caveat that matters for a domain that promises behaviour:
  `html.duckduckgo.com` is a scraped HTML endpoint, not an API. Cloudflare-style
  bot filters key on the TLS/JA3 handshake, so a plain HTTP client can get an
  empty `HTTP 202` and silently return "no results". Some servers work around
  this by impersonating Chrome's TLS handshake (`curl_cffi`). Scraping, not a
  contract — it can break without warning.
- Source: <https://github.com/nickclyde/duckduckgo-mcp-server>

### SearXNG — several servers, all pointing at a SearXNG instance

SearXNG is a self-hostable metasearch engine. An MCP server for it is a thin
client that forwards the query to a SearXNG instance URL.

- `SecretiveShell/MCP-searxng` — Python, `uvx mcp-searxng`. Env var
  `SEARXNG_URL`, **default `http://localhost:8080`**. No API key.
  <https://github.com/SecretiveShell/MCP-searxng>
- `kevinwatt/mcp-server-searxng` — Node, MIT, `npx @kevinwatt/mcp-server-searxng`.
  `SEARXNG_INSTANCES` (comma-separated, default `http://localhost:8080`).
  <https://github.com/kevinwatt/mcp-server-searxng>
- `ninickname/searxng-mcp-server` — Spring Boot/Java, Docker-ready, "no API
  keys, completely local, privacy-first".
  <https://github.com/ninickname/searxng-mcp-server>
- `Pascalrjt/SearXNG-Websearch-MCP` — TypeScript, aimed at local LLMs in LM
  Studio; caching, dedup, domain filtering.
  <https://github.com/Pascalrjt/SearXNG-Websearch-MCP>
- `varlabz/searxng-mcp` — env `SEARX_HOST`, default `http://localhost:8888`.
  <https://github.com/varlabz/searxng-mcp>
- `tisDDM/searxng-mcp` — Node. Note the anti-pattern for our purposes: its
  zero-config mode picks a **random public instance from SearX.space**, i.e.
  it sends your query to a third party you did not choose. Private-instance
  mode is opt-in. <https://github.com/tisDDM/searxng-mcp>

- **Needs**: a running SearXNG instance. If self-hosted on localhost, no API
  key and no third party in the tool→instance hop.
- **Runs locally**: the MCP process, and (if self-hosted) the SearXNG instance.
  **Calls remotely**: SearXNG itself does not have an index — it forwards the
  query to configured upstream engines (Google, Bing, DuckDuckGo, and dozens
  more). The SearXNG docs are explicit: the query "string is passed to
  external search services."
  <https://docs.searxng.org/dev/search_api.html>

So a localhost SearXNG is the *most* private option (you control the instance,
you choose the engines, you can strip identifying params) but it is **not**
on-machine search: the query still fans out to whichever engines the instance
enables.

### Brave Search — `brave/brave-search-mcp-server` (official) and others

- Maintainer: Brave (official). Others: `mikechao/brave-search-mcp`,
  `zed-extensions/mcp-server-brave-search`, plus the reference
  `@modelcontextprotocol/server-brave-search`.
- **Needs**: a `BRAVE_API_KEY` (free tier 2,000 queries/month, 1 req/s).
  Account required.
- **Runs locally**: the MCP process. **Calls remotely**: the Brave Search API
  (`api.search.brave.com`). Brave does run its own independent index, so it is
  a *single* well-defined recipient — but it is still a remote recipient, and
  it is tied to an API key that identifies the account.
- The official server's HTTP transport binds loopback (`127.0.0.1`) by default
  and rejects non-loopback Origins (DNS-rebinding guard); for our use it runs
  as stdio.
- Sources: <https://github.com/brave/brave-search-mcp-server>,
  <https://github.com/mikechao/brave-search-mcp>

### Multi-engine keyless — `sweetcornna/free-search-mcp`

- Maintainer: community. "Local-first, no-API-key" — DuckDuckGo, Mojeek,
  Startpage, with a Playwright fallback and an FTS5 result cache.
- **Needs**: nothing (keyless engines work immediately); `uv`.
- **Runs locally**: the MCP process and its cache. **Calls remotely**: each
  configured engine (DuckDuckGo/Mojeek/Startpage) directly. Multi-engine means
  the query goes to *several* third parties.
- Install: `claude mcp add search -- uvx free-search-mcp`.
- Source: <https://github.com/sweetcornna/free-search-mcp>

### Summary table — what each needs and who gets the query

| Server | Key/account? | Self-hosted index? | Query goes to |
|---|---|---|---|
| nickclyde DuckDuckGo | none | no | `html.duckduckgo.com` (scrape) |
| SearXNG servers (localhost instance) | none | instance is local, index is not | your instance → upstream engines (Google/Bing/DDG/…) |
| SearXNG (public/random instance) | none | no | a third-party instance you may not control → its upstream engines |
| Brave (official) | `BRAVE_API_KEY` | Brave's own index (remote) | `api.search.brave.com` |
| free-search-mcp | none | no | DuckDuckGo + Mojeek + Startpage |

No row keeps the query on the machine. The localhost-SearXNG row keeps the
*first hop* on the machine and lets you choose and strip the rest.

## 2. How each agent registers a local MCP tool

### Claude Code

CLI (`--` separates Claude's flags from the spawned command; everything after
is passed to the server untouched):

```bash
claude mcp add [options] <name> -- <command> [args...]

# DuckDuckGo, keyless:
claude mcp add ddg-search -- uvx duckduckgo-mcp-server

# SearXNG pointed at a localhost instance:
claude mcp add --env SEARXNG_URL=http://localhost:8080 searxng -- uvx mcp-searxng

# Brave, with the key in env:
claude mcp add --env BRAVE_API_KEY=YOUR_KEY --transport stdio brave -- npx -y @modelcontextprotocol/server-brave-search
```

Scopes decide where the entry is stored and who sees it:

| Scope | Loads in | Shared | Stored in | Flag |
|---|---|---|---|---|
| Local | current project only | no | `~/.claude.json` | default / `--scope local` |
| Project | current project only | yes, via VCS | `.mcp.json` at project root | `--scope project` |
| User | all your projects | no | `~/.claude.json` | `--scope user` |

Project-scoped `.mcp.json` shape (verbatim):

```json
{
  "mcpServers": {
    "myserver": {
      "command": "npx",
      "args": ["-y", "my-mcp-server"],
      "env": {
        "API_KEY": "value"
      }
    }
  }
}
```

Source: <https://code.claude.com/docs/en/mcp>

### OpenCode

Config lives in `opencode.json` (or `.jsonc`) at the repo root, or globally at
`~/.config/opencode/opencode.json`; files are merged, project over global. A
local server has `"type": "local"`, a `command` array, optional `environment`
and `enabled`. Shape (verbatim):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "my-local-mcp-server": {
      "type": "local",
      "command": ["npx", "-y", "my-mcp-command"],
      "enabled": true,
      "environment": {
        "MY_ENV_VAR": "my_env_var_value"
      }
    }
  }
}
```

For our servers the `command` array is e.g. `["uvx", "duckduckgo-mcp-server"]`
or `["uvx", "mcp-searxng"]` with `SEARXNG_URL` in `environment`.

Sources: <https://open-code.ai/en/docs/mcp-servers>,
<https://open-code.ai/en/docs/config>

Note on trust that touches offgrid's threat model: OpenCode auto-loads
`opencode.json` from the working directory, and that file can define `local`
MCP servers — i.e. a repo can ship a config that spawns processes on your
machine with your user's rights. Claude Code's project-scoped `.mcp.json` is
the same idea. A web-search tool registered this way runs with full user
privileges; the query egress is only part of the exposure.

## 3. Native (non-MCP) local-search paths

- **Claude Code**: its built-in `WebSearch`/`WebFetch` tools are
  vendor-hosted — the search runs on Anthropic's servers, US-only, tied to the
  API. That is exactly the vendor-hosted path #263 excludes. Claude Code has
  **no** native path that runs the search on this machine; local search must
  come through an MCP server.
- **OpenCode**: ships a built-in `websearch` tool, but it is **Exa-backed** —
  it "connects directly to the backend's hosted MCP service without
  authentication" and is only active on the `opencode` provider or behind
  `OPENCODE_ENABLE_EXA=true` / `OPENCODE_ENABLE_PARALLEL=true`. That is a
  vendor-hosted search (Exa), not on-machine. There is also a community plugin
  `emilsvennesson/opencode-websearch` that routes to the *model provider's* own
  search tool (Anthropic `web_search_20250305`, OpenAI `web_search`) — only
  meaningful for a remote provider, useless for a locally-held model.
  So OpenCode's only route to a search that runs on this machine is, again, a
  local MCP server.
  Sources: <https://opencode.ai/docs/tools/>,
  <https://github.com/emilsvennesson/opencode-websearch>

Conclusion: for a **locally-held** model, neither agent has a native
on-machine search. MCP is the only door.

## 4. What actually leaves this machine — for the domain model

This is the part that feeds "web search as a new *what could leave this
machine* subject." Ranked by how little escapes:

1. **Self-hosted SearXNG on localhost** (via `mcp-searxng` etc.) — leaks the
   *least you can control*. The agent→tool→instance hops are all on-machine.
   The instance then sends the **query text** to the upstream engines *you*
   configured; you choose which engines, and SearXNG can strip client
   identity. No API key, no account tying the query to you. Still: the query
   text does leave the machine, to multiple engines. Cost: you must run and
   maintain SearXNG (a second local service).

2. **DuckDuckGo (`nickclyde`)** — leaks the **query text** to a single,
   well-known recipient (`html.duckduckgo.com`), no account, no key. One hop,
   one recipient, anonymous-ish. Downside is reliability (scraping), not
   exposure. Good "keyless default".

3. **free-search-mcp** — leaks the **query text** to *several* third parties
   at once (DuckDuckGo, Mojeek, Startpage). More recipients than DDG, still
   keyless.

4. **Brave (official)** — leaks the **query text** plus an **API key** that
   identifies your account, to `api.search.brave.com`. Single high-quality
   recipient, but now attributable to you.

5. **Public/random SearXNG instance** (e.g. `tisDDM` zero-config) — leaks the
   query to a **third-party instance you don't control**, which then forwards
   it onward. Worst of both: unknown intermediary *and* fan-out. Avoid for a
   privacy claim.

In every case the subject that leaves is the **query text** (and, for a page
fetch via `fetch_content`, the **URL fetched** and whatever that fetch
returns). The differentiator is the *recipient set* and whether an
account/key makes it attributable:

- query → one anonymous engine (DuckDuckGo)
- query → several anonymous engines (free-search, or SearXNG fan-out)
- query → one attributable engine (Brave, via key)
- query → an untrusted intermediary (public SearXNG)

For offgrid's "what could leave this machine" model, web search is not a
single subject — it is *query text egressing to a recipient set*, where the
recipient set and its attributability are the axes worth naming. "Runs
locally" (the MCP process) and "stays on this machine" (the query) are
different properties, and every option here has the former without the latter.

## Bottom line

- **Least off-machine leak**: a **self-hosted SearXNG on localhost** fronted by
  a SearXNG MCP server — no key, no account, you choose and can strip the
  upstream engines. If running a second service is too much, **DuckDuckGo
  (`nickclyde/duckduckgo-mcp-server`)** is the keyless one-recipient default.
  Neither keeps the query on the machine; nothing does.
- **Registration**: Claude Code via `claude mcp add <name> -- uvx …` (or
  `.mcp.json` `mcpServers` for project scope); OpenCode via `opencode.json`
  `mcp.<name>` with `"type": "local"` and a `command` array.
- **Native path**: none for a locally-held model — Claude Code's WebSearch and
  OpenCode's built-in websearch are both vendor-hosted (Anthropic, Exa). MCP is
  the only on-machine door, and even it only moves the *process* on-machine,
  not the *query*.
