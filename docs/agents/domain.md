# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the domain glossary.
- **`docs/decisions.md`** — this repo records architectural decisions here rather than under `docs/adr/`. Read the entries that touch the area you're about to work in.
- **`docs/architecture.md`** — the module map and import rules.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CONTEXT.md              ← domain glossary
├── docs/
│   ├── architecture.md     ← module map, import rules
│   └── decisions.md        ← architectural decisions (this repo's ADR log)
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts an existing decision in `docs/decisions.md`, surface it explicitly rather than silently overriding:

> _Contradicts the decision on event-sourced orders — but worth reopening because…_
