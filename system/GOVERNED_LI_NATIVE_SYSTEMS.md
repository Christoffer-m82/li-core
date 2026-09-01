# ADR-0035: Governed Li-native capability platform

**Status:** Accepted for migration-ready implementation  
**Date:** 2026-09-01  
**Decider:** Owner review before migration or deployment

## Context and decision

Li needs nine coherent systems covering twelve recommendations without changing Identity v0.2,
canonical personal memory, permanent-agent governance, ActionIntent approval, freshness/evidence,
Place privacy, or paused rhythms. We use one shared typed contract layer and nine narrow services.
Postgres remains the durable source; provider adapters remain replaceable.

```text
identity + hard governance + action policy (mandatory, unchanged)
                         |
    registries: skills / models / tools / delivery
                         |
 deterministic context selection -- bounded historical recall
                         |
      Li runtime -- compression -- temporary specialists
                         |
     no-LLM watcher events (only on grounded conditions)
                         |
 experimental isolated heavy worker (disabled, untrusted)
```

## Dependency order

1. Skills, context contracts, historical-search persistence.
2. Compression built on full searchable history.
3. Watchers emitting idempotent events into existing governed proactivity.
4. Temporary specialists using minimized context and the model router.
5. Model, tool, and delivery registries.
6. Heavy-work adapter at the outer trust boundary, disabled by default.

## Twelve recommendations covered by nine systems

System 1 includes governed procedural skills, an open Markdown-plus-manifest shape, outcome
measurement, and promote/improve/retire lifecycle (original recommendations 1, 10, and 12).
Systems 2–7 map directly to progressive context, conversation search, deterministic watchers,
temporary specialists, compression, and model routing. System 8 combines the typed tool registry
and delivery adapter recommendations (8 and 9). System 9 supplies the isolated heavy-work boundary
(11). Thus all twelve recommendations are represented without broadening authority.

## Trust boundaries

- Skills are procedures, never personal memory. Community imports enter `untrusted`; promotion
  requires validation and review. New versions are immutable.
- Context selection records concise reasons and token estimates, never hidden reasoning.
- Historical snippets do not become canonical memory candidates.
- Watchers execute deterministic predicates and do not activate rhythms.
- Temporary workers have no DB, memory-write, action, or registry authority.
- Claude remains primary. High-stakes synthesis cannot silently downgrade.
- Delivery transports messages and approval decisions through existing APIs; it grants no authority.
- Heavy work receives only task-scoped tools and credentials, has no owner DB/private memory, and
  cannot use Gmail/Calendar except through normal Li-governed APIs.

## Hermes reference patterns

Nous Research's public Hermes Agent architecture and documentation were reviewed for conceptual
patterns only: metadata-first skill discovery with bodies loaded on demand, FTS session search,
fresh delegated sessions with bounded concurrency, no-agent cron prechecks, central provider/tool
registries, session compression, and swappable terminal backends. Li adapts metadata-first loading,
deterministic prechecks, isolated delegation, bounded snippets, and adapter separation. No Hermes
code is vendored or copied; Li adds stricter trust lifecycle, owner approval, canonical-memory
separation, caller authority, privacy, and disabled-by-default heavy execution.

References:

- https://github.com/NousResearch/hermes-agent
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/architecture.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/cron.md

## Consequences and later review

Schema 0.35 must be applied before durable skill/search/watcher analytics are enabled. Semantic
search is intentionally deferred until an approved embedding provider or local vector strategy is
configured; Postgres full-text search is the zero-new-cost baseline. Heavy execution needs a real
sandbox adapter, egress policy, and temporary credential broker before its feature flag can be used.
