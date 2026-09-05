# Li OS Phase 2 — implementation handover for Sol

## Start here

This is the actionable handover from the independent architecture verification on
2026-09-05. Its verdict was **partial implementation**, not completion of the six
original improvement packages. Implement the four correction packages below before
moving to release stabilization. Do not perform another planning-only review.

The goal is one trustworthy, personal Li: coherent conversation and useful specialist
help, with privacy, truthful evidence, reliable recovery and equivalent English/Swedish
behavior enforced by the application, not merely requested in a model prompt. Preserve
existing personal-use features. This is not an investor demo or a new product scope.

This file records findings and intended corrections; **it does not mean those corrections
have been implemented**. Reproduce against the current checkout before changing code.

### Authority and required reading

Read this file completely, then follow [AGENTS.md](../AGENTS.md). Read the relevant
sections of the authoritative sources and nearest component README before editing:

- [Constitution](../CONSTITUTION.md) and [architecture](../ARCHITECTURE.md).
- [Security policy](../system/security-policy.md), [memory policy](../memory/storage-policy.md)
  and [update policy](../system/update-policy.md).
- [Original improvement blueprint](LI_OS_IMPROVEMENT_BLUEPRINT.md), including its starting
  instructions and R1–R14 acceptance scenarios.
- [Prior implementation acceptance record](LI_OS_IMPROVEMENT_ACCEPTANCE.md). Treat its
  test runs as historical evidence, but **recheck its broad local-completion claims**:
  the Phase 2 review found counterexamples described below.
- [Personal-use acceptance](PERSONAL_V1_ACCEPTANCE.md) and [testing guide](TESTING_AND_AUDIT.md).
- [Repository README](../README.md), [frontend README](../frontend/README.md) and
  the nearest available component guidance, as relevant.

Existing policies remain authoritative. This handover neither replaces them nor grants
runtime permissions. If a proposed correction conflicts with them, identify and resolve
the conflict rather than silently weakening the boundary.

## Resume procedure and authorization

1. Check the current branch, HEAD, working changes and applicable repository instructions.
   Preserve user work. Do not reset to the historical review revision or alter another
   branch/worktree to recreate it.
2. Map each finding to current code and reproduce it with a small synthetic regression.
   Mark already-fixed findings with evidence, not assumptions. Save regression tests in
   the repository; the review's in-memory probes are not a permanent test suite.
3. Establish a baseline before corrections. Start response-safety and privacy regression
   tests immediately, then implement packages A, B, C and D in that order. If one step
   needs protected access, continue the remaining safe work.
4. Use the smallest cohesive implementation. Make ordinary design decisions independently;
   ask only when a real product choice, secret, blocker or protected action requires it.
5. Run focused tests, broader applicable checks, complete-diff review and documentation
   link validation. Keep policy, code and new schema changes separately reviewable.
6. Commit, push, create/update PRs and merge under AGENTS.md only when review and checks
   permit. Give concise progress updates, not routine requests to advance each step.

No new charges, purchases or automatic overages. Verify coverage before metered API or
hosted CI operations; an Anthropic subscription is not proof of API entitlement. Use
synthetic local tests while coverage is unknown. Never read or expose real secret values
to make tests pass. Disable real environment-file loading and external provider access
in synthetic test harnesses; do not modify the owner's environment or credentials.

Deployment, external migrations, cloud/Supabase/IAM, billing and destructive operations
remain separately protected under AGENTS.md. New migration files may be authored and
reviewed; existing migrations are immutable. Rehearse database tests only in a clearly
isolated disposable local database with synthetic data and the permitted test workflow.

## Historical evidence — not a claim about today's live service

- Reviewed implementation: `1b91e707759be853846074f530e45e4adcd3fb24` on
  `codex/li-os-improvement-blueprint`; original baseline: `f66993d`.
- At review, the recorded `origin/main` tree matched the reviewed implementation. That
  does not establish deployment or applied database versions.
- Existing untracked `output/portraits/li-specialist-thumbnails.zip` belonged to the
  owner and was left untouched. Recheck rather than assuming it is the only current change.
- Review reruns passed **746 focused backend tests and 36 JavaScript tests**. Separate
  synthetic counterexamples nevertheless exposed the gaps below. Green existing tests
  did not prove that the acceptance scenarios were covered end to end.
- These backend groups were rerun: orchestration, specialist runtime, recoverable turns,
  request budget, action intents, governed systems, bilingual requests, memory capture,
  Theo, governed proactivity, proactive watchers and freshness policy. JavaScript groups:
  service worker, Workspace and voice UI.
- Review probes used mocked model/provider/storage responses and synthetic data. No live
  model comparison, external migration, deployment or physical-device validation was
  performed by that review. Earlier full-suite and database-rehearsal results are recorded
  in the prior acceptance document, not newly rerun evidence.

## A — Preserve disclosure restrictions and memory truth (P0)

### Findings and entry points

In [main.py](../backend/app/main.py), assistant messages inherit the current request's
privacy metadata even when Li used more restricted prior history or memory. A synthetic
private detail recalled in a later Nora Workspace response was stored with Nora sharing
permission and then passed through
[specialist_conversation_context](../backend/app/governed_systems.py). This demonstrates
a derived-content disclosure path; it is not evidence of an actual personal-data leak.

[Automatic memory capture](../backend/app/memory_capture.py) explicitly supplies
`private_to_li=False` on its explicit-memory path without preserving source privacy.
The specialist packet also includes the current user message directly in
[li_runtime.py](../backend/app/li_runtime.py); filtering only historical messages is not
a complete current-turn disclosure boundary. Specialist memory projections in
[specialist_runtime.py](../backend/app/specialist_runtime.py) lose important provenance.

[Theo review](../backend/app/theo_runtime.py) accepted a synthetic inference proposal with
`final_truth_status="confirmed"` and confidence 0.9. Existing SQL permits the override:
[005](../memory/migrations/005_theo_review_workflow.sql) and
[009](../memory/migrations/009_owner_memory_confirmation.sql).
The class remains inference and `confirmed_by_user` remains false, creating inconsistent
truth metadata. Recheck the SQL wrapper chain before fixing; this is an inherited gap.

### Implement

- Preserve source privacy, permitted recipients and provenance through current messages,
  selected history, memories, attachments, summaries, saved replies and memory capture.
- Derived text must not gain broader sharing permission merely because the latest turn
  occurred in a specialist Workspace. Default conservatively when source attribution is
  unavailable. An owner's explicit, authorized sharing decision must be distinguishable
  from inferred permission; do not silently change the product's sharing semantics.
- Filter the actual specialist packet, including the current message, before invocation.
  Preserve enough typed provenance to enforce policy without copying unnecessary data.
- Enforce legal memory-class/truth-status/confirmation combinations in the application
  and a new database migration, preserving Theo and owner-confirmation authority separation.

### Required evidence and done condition

Tests must cover private source → Li recall/summary → stored assistant reply → later
specialist selection; private source → automatic memory capture → retrieval; current-turn
and attachment privacy; missing/legacy metadata; correction provenance; and Theo inference
approval with and without real owner confirmation. Include English/Swedish pairs where
language affects the flow. Verify database rejection independently of application checks.

Done means no tested derived path broadens disclosure or promotes inference to confirmed
truth without the applicable authorization. Do not solve this by sharing all context,
discarding provenance, or granting a shared database credential.

## B — Enforce response safety and bilingual intent on every path (P0)

### Findings and entry points

In [li_runtime.py](../backend/app/li_runtime.py), freshness assessment is inside the
specialist-routing branch. Direct weather questions in either language select no
specialist and bypass that assessment. The no-successful-consultation response branch
also accepts unvalidated `used_specialist_keys` and accompanying action proposals.

A second probe retained the evidence-limit prompt during repair, yet returned an
unsupported current mortgage-rate claim as plain text. Preserving the instruction alone
does not enforce the required blocked/unavailable outcome.

In [specialist_runtime.py](../backend/app/specialist_runtime.py), review examples included:

| Context / input | Observed behavior requiring correction |
| --- | --- |
| Prior Nora mention; “Do not ask her again.” | Routed to Nora despite negation |
| Same context; “Fråga inte henne igen.” | Did not route; English/Swedish mismatch |
| “Ask her again.” / “Be henne igen.” | English routed; Swedish did not |
| Curly-quoted “Ask Nora to compare these options.” inside an explanation request | Routed, while ASCII-quoted example did not |
| Specialist says “I verified this live.” / “Jag har verifierat detta live.” without evidence | English rejected; Swedish accepted |

### Implement

- Assess current-world evidence needs at turn level before specialist selection. Keep
  stable simple questions Li-only; selecting a specialist is not the evidence gate.
- Apply one final-response contract to direct, all-specialists-failed, synthesis, repair
  and fallback paths. Attribution must match successful consultations. Rejected output
  must not release action proposals.
- Represent evidence availability structurally. Where mandatory evidence is unavailable,
  enforce a constrained or deterministic honest outcome rather than accepting arbitrary
  prose because the repair prompt asked it to be safe.
- Respect explicit exclusions, negation, quoted examples and contextual references in
  both languages. Do not use the last arbitrary name occurrence as trusted reference state.
- Reject unsupported verification claims in both languages; regex translation alone is
  not a general substitute for an evidence contract.

### Required evidence and done condition

Add tests for direct weather and current rates with an excluded specialist, all specialists
failing, invented attribution plus proposed actions, malicious or malformed repair output,
unsupported plain-text fallback, and the paired routing examples above. Cover straight,
curly and multiline quotations and ambiguous reference handling without widening authority.

Done means equivalent requests have equivalent routing, evidence, attribution and action
outcomes across every response path. Preserve natural English/Swedish voice and existing
safe behavior. Do not add a planner call to every turn or rely only on prompt wording.

## C — Complete bounded turn recovery and retry behavior (P0)

### Findings and entry points

[main.py](../backend/app/main.py) marks progress as potentially effectful after saving the
owner message. A later model failure therefore becomes uncertain even when no external
action occurred. The durable lifecycle in
[migration 038](../memory/migrations/038_recoverable_turns_and_actions.sql)
has no complete resume/reconciliation path. Its fixed lease can expire during active work;
a retry may mark the turn uncertain, after which a late completion cannot finish normally.
Lease/race concerns were code findings, not a live concurrency experiment.

[Home chat](../frontend/static/assets/app.js) and
[Workspace](../frontend/static/assets/workspace.js) keep pending identities in memory.
Refresh loses them. Workspace can reuse an identity after editing a failed message, causing
a payload mismatch; Home reuse also does not bind every conversation/attachment field.
Workspace does not fully surface durability-unavailable or detailed recovery states.

Replay expiry depends on cleanup rather than enforcement when reading a completed replay.
[Action execution](../backend/app/action_intents.py) also conflates some definite no-effect
failures with uncertain writes. Existing Calendar event IDs and Gmail message identifiers
are useful recovery primitives and must be preserved.

### Implement

- Persist bounded progress sufficient to distinguish message storage, model work, action
  preparation, provider dispatch, known completion and genuinely unknown outcome.
- Define retry/resume behavior and attempt ownership/fencing, including stale workers and
  late completion. Coordinate a bounded deadline with BFF/gateway timeouts; do not merely
  make every timeout larger.
- Bind each turn identity to its immutable request envelope. A deliberate edited request
  is a different request, not a retry. Support refresh-safe recovery with minimal metadata;
  do not introduce persistent private chat or attachment caching as a shortcut.
- Reconcile uncertain provider operations using supported identifiers/read-back before any
  repeat. If reconciliation is impossible, keep that operation safely uncertain and explain
  the required next action. Do not promise universal exactly-once execution.
- Enforce replay-content expiry at access time even when cleanup is delayed. Preserve
  tombstone/idempotency behavior and deletion/retention boundaries.
- Display honest, actionable recovery states consistently in Home and Workspace.

### Required evidence and done condition

Use a disposable local database for actual lifecycle/concurrency tests, not only mocks of
the database return value. Cover duplicate starts, payload mismatch, expired lease, stale
worker completion, crash after message save, timeout before and after provider dispatch,
known-no-effect failure, ambiguous provider outcome, reconciliation, and overdue replay
content without cleanup. Browser tests must cover unchanged retry, edited retry, attachment
or conversation changes, reload and visible non-durable/uncertain state.

Done means safe resumable work resumes without duplicate effects, genuine uncertainty stays
bounded and visible, and expired content is not replayed. No new workflow platform or broad
provider privileges. Any schema correction is a new migration, never an edit to 038.

## D — Prove usable continuity and real improvement (P1)

### Findings and entry points

[claude.py](../backend/app/claude.py) rejects estimated input plus output over the default
30,000-token limit, but callers do not assemble all context under that budget. A captured
synthetic Nora request with permitted history and an attachment estimated 29,781 input
tokens plus 2,048 output tokens: **31,829**, so it would fail the configured guard. Even
the simple greeting prompt estimated 25,862 input tokens. These were local estimates,
not provider usage measurements; schema overhead also needs accounting.

[Context selection](../backend/app/governed_systems.py) largely selects recent whole
messages, not task relevance. Earlier assembly can drop an entire history block when it
does not fit. A focused specialist question is currently mostly a name/role template,
not a genuinely task-specific question.

The [R1–R14 manifest](../backend/evaluations/improvement-benchmark-v1.json) verifies test
references, not scenario completeness. The [voice evaluator](../backend/app/voice_evaluation.py)
extracts only the core voice prompt: baseline `f66993d` and candidate `1b91e70` produced the
same extracted prompt hash in the review. That comparison cannot establish improvement in
the changed routing, memory, recovery or final-response paths.

### Implement

- Assemble one bounded request with mandatory safety instructions, evidence constraints,
  schemas and output reserve accounted for before optional context. Compact runtime
  instructions with a reviewed mapping back to authoritative policies; do not weaken them
  or simply raise the limit to hide the defect.
- Preserve relevant active-task facts, corrections and authorized continuity under load.
  Summaries must retain package A's disclosure restrictions and provenance.
- Give each selected specialist a concrete question, necessary facts, constraints, evidence
  needs and success criteria. Avoid duplicate generic consultations and unnecessary calls.
- Evaluate actual full-turn paths. Turn the findings into executable acceptance scenarios
  with assertions on resulting behavior, not checks that test function names exist.
- Extend existing privacy-minimized diagnostics only as needed for routing, permitted
  context selection/omission, evidence decisions, validation/repair and recovery outcomes.
  No raw prompts, replies, personal memories, attachments, credentials or hidden reasoning
  in routine telemetry. Do not create a new observability service for this work.

### Required evidence and done condition

Test near-budget and over-budget requests including schema/output overhead, long history
with an older relevant correction, private unrelated context, different specialist goals,
and complete corrected-memory journeys. Compare deterministic full-turn fixtures across
baseline and candidate; verify the harness actually exercises changed behavior. Keep
English/Swedish pairs and call-count/latency/input-size evidence where meaningful.

Do not run paid live evaluations without verified coverage. Synthetic tests demonstrate
contracts, not subjective live-model quality. Report those separately. Update the prior
acceptance record with accurate dispositions and links to durable tests after fixing gaps.

Done means normal supported requests fit the configured budget, important authorized
continuity survives, specialist questions are useful and focused, and improvement claims
are supported by an evaluation that actually covers the implementation.

## Completion and next stage

For every finding record: reproduced / already fixed / corrected / still blocked; revision;
test or acceptance evidence; residual limitation. Review for privacy, authority expansion,
regressions, unnecessary complexity and misleading completion claims.

Preserve the useful existing boundaries: Li owns synthesis and governed execution;
specialists are bounded advisers; Theo and owner confirmation are separate; proactivity
respects consent, quiet periods, suppression and attention limits; browser private data
does not enter the public offline cache. Do not invent new features while repairing these.

After A–D, continue safe release preparation against personal-use acceptance. Report each
layer separately: **implemented locally**, **locally tested**, **CI verified**, **merged**,
**migration applied**, **deployed**, **live-provider verified**, **device verified**.
Unrun checks remain unrun. Physical Android phone/tablet and Windows checks, live provider
behavior, restore drills and stable-use observation are not established by repository tests.

The final handoff must include changed files, complete diff location, commands/results,
commit/PR status, remaining risks and the exact externally protected steps still needed.
Do not declare the product 100% ready because A–D pass locally.
