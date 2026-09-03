# Open milestones

## How to read this file

This is an evidence-based index of work that tracked documents describe as incomplete, gated,
paused, proof-of-concept, or future. It is not a product roadmap and does not prove live external
state. Close an item only with a repository change or dated operator evidence, and link that evidence
rather than rewriting the authoritative design.

| ID | Milestone | Repository evidence | Exit evidence |
| --- | --- | --- | --- |
| OM-001 | Complete the native mobile product beyond coarse-place proof of concept | Android and iOS documents identify their code as proof of concept; the gateway ADR defines an acceptance gate. See [Android](../native/android/README.md), [iOS](../native/ios/README.md), and [Native Gateway ADR](../system/NATIVE_GATEWAY_ARCHITECTURE.md#deployment-prerequisites-and-acceptance-gate). | Platform integration tests, security/privacy review, revocation tests, and operator-verified staged deployment evidence. |
| OM-002 | Configure native attestation or formally accept the residual risk | The [Native Gateway deployment guide](../deployment/cloud-run/native-gateway.md) sets attestation status to `not_configured`. | Approved design decision plus implementation and denial-path tests, or a dated explicit risk acceptance. |
| OM-003 | Progress voice from foundation to production interaction | [Voice Interaction Foundation](../VOICE_ARCHITECTURE.md) describes a web milestone and typed provider boundary rather than a complete voice service. | End-to-end browser/native validation, privacy review for microphone/audio handling, interruption/error tests, and deployment evidence. |
| OM-004 | Activate governed proactivity selectively | The [proactivity guide](../deployment/cloud-run/governed-proactivity.md) provisions five jobs paused and keeps rhythms `preview_only` until owner approval. | Per-rhythm owner approval, matching scheduler resume evidence, quiet-hour/idempotency tests, and a documented stand-down test. |
| OM-005 | Resolve the annual rhythm schedule from approved owner context | The [proactivity guide](../deployment/cloud-run/governed-proactivity.md) defaults the annual job to January 2 until a birthday-derived schedule is approved. | Owner-approved schedule stored without sensitive date leakage in public metadata, plus scheduler verification. |
| OM-006 | Strengthen authentication beyond shared Li tokens | The [README](../README.md#rotation-and-rollback) names per-device OIDC/WebAuthn, short-lived access tokens, refresh revocation, inventory, and endpoint scopes as the longer-term upgrade. | Approved ADR, migration/deployment plan, revocation and recovery tests, and removal plan for shared-token dependencies. |
| OM-007 | Add distributed abuse protection if usage expands | The [README](../README.md#one-time-google-cloud-setup) states that the in-memory limiter is not a distributed quota and names a gateway/Cloud Armor as a later upgrade for multiple users. | Threat/usage threshold, approved design, staged enforcement tests, and false-positive/rollback plan. |
| OM-009 | Operationalize backup verification and restore testing | [Memory Storage Policy](../memory/storage-policy.md#40-backup-verification) and [Security & Privacy Policy](../system/security-policy.md#71-backup-verification) require verification and recovery controls, which cannot be proven by repository contents. | Dated operator evidence for backup checks and a successful non-production restore drill, with RPO/RTO findings. |

## Maintenance rule

When closing or changing a milestone, update the authoritative source first when the underlying
decision or design changed. In this index, record only the new status and evidence link. Move durable
accepted design decisions to [Decisions](DECISIONS.md) and residual issues to
[Known risks](KNOWN_RISKS.md).
