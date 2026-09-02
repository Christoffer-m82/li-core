# Decision index

## Purpose

This is an index of existing durable decisions, not a new source of architecture authority. Read the
linked document before relying on a row. Status descriptions reflect the tracked source and do not
prove deployment or operational state.

| Decision | Tracked source | Repository status or scope |
| --- | --- | --- |
| Li is the persistent personal AI hub; providers and specialists remain replaceable components | [Li Constitution](../CONSTITUTION.md), [Li OS Architecture](../ARCHITECTURE.md) | Foundational governing decision |
| Git holds Li's definition; canonical memory, secrets, documents, and backups occupy separate controlled layers | [Memory Storage Policy](../memory/storage-policy.md#100-final-storage-principle) | Storage and portability principle |
| Security defaults to zero implicit trust, least privilege, default deny, and independent review | [Security & Privacy Policy](../system/security-policy.md) | Governing security decision |
| Updates preserve memory, permission integrity, auditability, regression coverage, and rollback | [Update Policy](../system/update-policy.md) | Governing change-control decision |
| Browser access uses a server-side BFF so backend invocation and Li credentials do not enter the browser | [Frontend README](../frontend/README.md#security-architecture) | Implemented repository boundary |
| Production backend target is IAM-private Cloud Run with separate Cloud Run and Li authentication layers | [README](../README.md#secure-remote-deployment) | Recommended deployment architecture |
| Private artifact bytes live in private object storage with governed retention; PostgreSQL stores bounded metadata | [README](../README.md#phase-2-private-data-retention), [artifact retention](../deployment/cloud-run/artifact-retention.md) | Implemented repository design; live state requires verification |
| ADR-007: native devices provide coarse place through a bounded, privacy-minimizing contract | [Mobile Location Architecture](../system/MOBILE_LOCATION_ARCHITECTURE.md) | Accepted ADR in tracked source |
| ADR-008: native apps authenticate through a dedicated gateway with bounded bearer/refresh lifecycle | [Native Gateway Architecture](../system/NATIVE_GATEWAY_ARCHITECTURE.md) | Accepted ADR in tracked source; deployment gated |
| ADR-0035: nine governed Li-native systems cover the twelve platform recommendations | [Governed Li-native Systems](../system/GOVERNED_LI_NATIVE_SYSTEMS.md) | Accepted ADR in tracked source |
| Proactivity uses paused scheduler jobs and owner-approved rhythm activation with durable idempotency | [Governed proactivity](../deployment/cloud-run/governed-proactivity.md) | Deployment/activation gate |

## Adding a decision

For a material, cross-component, security, data, provider, or irreversible decision, add or update an
authoritative ADR/policy first. Record context, options, decision, consequences, security/privacy
impact, migration/rollback, and review triggers. Then add a concise link here. Do not use this index
to retroactively declare a disputed implementation detail “decided.”
