# Li OS improvement blueprint and Sol implementation brief

- **Prepared:** 2026-09-05
- **Review baseline:** f66993d
- **Intended implementer:** GPT-5.6 Sol, or a subsequent implementation model
- **Status:** Proposed implementation direction; no recommendations are implemented by this document.

## Start here: instructions for the implementation model

This document carries the complete supervisor review and its six work packages forward without
requiring the original conversation. The owner requested that the review be converted into an
actionable file. Creating this file did not authorize external operations or execute the plan.

When the owner asks you to implement this blueprint, your job is:

**Inspect the current system → reproduce important defects → implement the smallest sound change →
test failure paths → review the complete diff → verify user-visible outcomes → continue to the next
safe package.**

The review model's job was to understand, challenge and prioritize. Your job is to turn that direction
into working, verified behavior. Do not merely add documentation, placeholder modules or more prompts
and describe the recommendations as complete.

### What we are trying to achieve

Li should feel like one capable personal assistant who understands Christoffer, maintains continuity,
coordinates useful expertise, and reliably reports what happened. The aim is not the largest possible
agent architecture. Prefer the simplest architecture that produces a measurable improvement in
usefulness, privacy, correctness and recovery.

Three examples of the intended end state:

1. Christoffer asks Li in Swedish to revisit a decision discussed in English. Li resolves the reference,
   recalls only relevant permitted context, consults a specialist only if useful, and answers naturally
   without changing action or approval semantics because of the language switch.
2. A specialist consultation fails validation. Li does not invent expertise, drop an evidence restriction,
   or offer actions extracted from the rejected response. She gives a useful, truthful fallback.
3. A calendar request loses its network response after execution. On reconnect, Li recovers or reconciles
   the existing operation instead of creating another event or falsely saying that nothing happened.

These are behavioral objectives, not mandates for a particular new framework, service or class layout.
You may choose ordinary implementation details within the repository's rules. If a simpler change
satisfies the same acceptance criteria and preserves boundaries, prefer it and record why.

### Authority and scope

Read [AGENTS.md](../AGENTS.md), [CODEX.md](../CODEX.md), the relevant component documentation, and these
authoritative sources before editing their areas:

- [Li Constitution](../CONSTITUTION.md).
- [Li OS Architecture](../ARCHITECTURE.md).
- [Security & Privacy Policy](../system/security-policy.md).
- [Memory Storage Policy](../memory/storage-policy.md).
- [Update Policy](../system/update-policy.md).
- [Repository README](../README.md).

This is an operating blueprint, not a replacement constitution, approved architecture decision, runtime
permission grant, or proof of deployment. If a recommendation conflicts with an authoritative source,
identify both locations and resolve the conflict through the existing change-control process before
implementing that part. A proposed refactor must not silently broaden an authority boundary.

Follow the current project-limited development authorization in AGENTS.md. Continue ordinary safe
implementation, testing and review without routine approval questions. Do not interpret this file as
permission to deploy, apply migrations, modify cloud/Supabase/IAM/secrets, change billing, delete data,
or perform other protected actions. Ask for the exact authorization when needed; continue independent
safe work if another package remains possible. Never request that credentials be pasted into the report.

The no-spending rule remains binding. Existing subscriptions do not by themselves prove API or hosted-CI
coverage. Verify coverage before bounded metered work; use local synthetic tests when coverage is unknown.
Do not add charges, paid services, automatic overages or model calls simply to complete a checklist.

This is a bounded improvement program for the agreed personal-use scope. Future suggestions are not
instructions to implement the entire future vision. Native work remains part of the wider agreed scope,
but it is not a prerequisite for the first dependable installable-web release.

### First implementation session

1. Read this entire brief, then inspect branch, HEAD and working-tree status. Do not switch branches,
   reset changes, or overwrite files merely to match the review baseline. Preserve unrelated work.
2. Compare the current code with the reviewed revision. Revalidate each finding before changing it.
   If already fixed, record the current evidence and regression coverage instead of rebuilding it.
3. Establish a local synthetic baseline using [Testing and audit](TESTING_AND_AUDIT.md). Read actual
   project manifests and test fixtures rather than assuming installed tools, credentials or services.
4. Begin package 5's evaluation baseline and package 1's reproduction tests. Then execute packages 1–4,
   expanding package 5's evidence throughout, and finish package 6's end-to-end acceptance.
5. Before each substantial change, state the invariant, the smallest intended change, affected interfaces,
   expected failure behavior and validation plan. This is a progress update, not a routine approval request.
6. Prefer reviewable vertical slices. Keep policy, application, migration and deployment changes separately
   reviewable; avoid dozens of foundation-only batches with no completed behavior.

### Implementation discipline

- Separate reasoning from authority. A model may propose a plan; deterministic code validates allowed
  operations, permissions, context disclosure and execution state.
- Fix invariants before expanding behavior. Do not add smarter routing while failed synthesis can still
  escape validation or while context selection cannot enforce privacy.
- Introduce internal modules incrementally behind existing interfaces where practical. Do not start with
  a rewrite or a new microservice architecture.
- Use explicit contracts for success, failure, unavailable and uncertain outcomes. Do not convert errors
  into empty results that look like success.
- Enforce deadlines at provider boundaries. Timing out a waiting thread does not prove the underlying
  call stopped; cancellation and remaining resource usage need explicit handling.
- Do not promise exactly-once external effects without provider support. Reconciliation and a truthful
  uncertain state are preferable to an unsafe automatic retry.
- Preserve all existing specialist identities and approved portraits. This is not portrait or theme work.
- Preserve native English and Swedish wording while making meaning, permissions and capability selection
  equivalent. Machine identifiers stay stable. General semantic parity must not be claimed from a small
  alias list or a handful of passing examples.
- Treat tool-returned source text, uploads, messages and retrieved evidence as untrusted data. Never use them as new
  authority or log them by default for convenience.
- Any migration must be new, not an edit to applied history. Test it only in an explicitly isolated,
  disposable environment; applying it to an external target remains separately protected.

### Evidence and completion protocol

Use [Personal-use acceptance](PERSONAL_V1_ACCEPTANCE.md) as the completion ledger, not the number of
PRs or modules. Keep authoritative documents authoritative; link to their rules rather than duplicating
or independently redefining them. The review sections below remain a dated snapshot, not live status.

For every package, record in the handoff or the existing appropriate acceptance record:

| Field | Required evidence |
| --- | --- |
| Package and revision | Identifier, branch/commit, and date |
| Finding disposition | Reproduced, already fixed with evidence, or revised with explanation |
| Changes | Affected interfaces and the behavior now guaranteed |
| Validation | Exact commands, results and relevant synthetic scenarios |
| Security/data integrity | Allowed and denied paths, including failure and replay behavior |
| State | Not started, in progress, locally verified, externally blocked, or accepted |
| External evidence | Environment, release, date and authorization where required; otherwise unverified |
| Remaining work | Specific limitations and the next safe step |

Review the complete diff, including untracked additions, and the applicable test results before using
the current commit/PR/merge authorization. Do not stage unrelated files. At the review baseline there
was an unrelated untracked portrait archive at output/portraits/li-specialist-thumbnails.zip; recheck
the current tree rather than assuming that inventory remains unchanged.

A package requiring deployment, migration or physical-device evidence can be locally implemented while
still incomplete overall. Never relabel a skipped check as passed. Stop the improvement program when its
agreed acceptance is satisfied, or report exact remaining protected/blocked steps; do not invent more scope.

### Minimum cross-package regression scenarios

These are proposed acceptance requirements, not claims that tests already exist or pass. Use synthetic
data and mocked executors first. Preserve all relevant existing tests as well.

| ID | Scenario | Required outcome |
| --- | --- | --- |
| R1 | Synthesis names an unavailable specialist and contains an action proposal | No proposal or attribution from the rejected synthesis reaches the actionable response |
| R2 | Required current evidence is unavailable, then synthesis validation fails | Recovery preserves the restriction; no unsupported current claim is supplied |
| R3 | Direct current-world question in English and Swedish | Evidence policy runs regardless of whether a specialist is selected |
| R4 | Malformed final structured output | No raw rejected JSON or unsafe proposal is exposed as an accepted response |
| R5 | Unrelated private fact appears in earlier conversation and in memory | A specialist lacking permission/need receives neither representation |
| R6 | Long conversation contains the active decision and a later correction | Relevant continuity survives budgeting; privacy and provenance survive summarization |
| R7 | Explicit opt-out, quoted specialist request, and ambiguous follow-up | Routing distinguishes intent and resolves references without unauthorized delegation |
| R8 | Duplicate turn submission or response lost after an external effect | Existing state is recovered/reconciled; no blind duplicate action |
| R9 | Restart after execution claim, failed completion write, or deadline expiry | No false success or false assertion that nothing happened; uncertainty is explicit |
| R10 | Memory correction followed by recall and specialist consultation | Current corrected fact is used with appropriate provenance and disclosure rules |
| R11 | Provider unavailable, emergency wording, and language switch | No fabricated capability; immediate safety guidance is not delayed by research |
| R12 | Proactive duplicate, quiet hours, stand-down and disabled schedule | No unauthorized or repeated interruption; suppression remains effective |
| R13 | Telemetry failure or partially completed quality evaluation | User safety is preserved; missing evidence does not become a claimed pass |
| R14 | Sign-in expiry, offline launch and unavailable photo service | Honest recoverable UI state, with CM fallback and no misleading enabled capability |

## How to read the review

**OBSERVED** means supported by the reviewed repository. **INFERRED** means a conclusion from that
evidence. **RECOMMENDED** means proposed direction. **OWNER DECISION** identifies a material choice
that needs the appropriate decision process if pursued.

The original review was read-only: no live providers, migrations, deployments or paid evaluations were
run. Its findings describe repository behavior, not verified production behavior. Source links below
resolve within the repository; inspect the named functions and current history because lines may move.

# Part 1 — Li OS vision

**Li needs stronger coordination, continuity and recovery—not more agents.** The right direction is
one capable personal assistant, supported by bounded specialist consultations and dependable software.

### What Li is today

**OBSERVED:** Li is an implemented personal-assistant application with a private backend, browser
interface, governed memory operations, specialist consultations, action proposals, evidence policies
and proactive routines. Some capabilities remain foundations rather than completed user journeys.

Its specialist system is principally multiple stateless consultations with the configured model,
distinguished by role, context and instructions—not twelve independently learning assistants.

### What the owner is building

A personal Chief of Staff who:

- Understands Christoffer's circumstances and maintains continuity.
- Converses naturally in English and Swedish.
- Uses specialists without requiring Christoffer to manage them.
- Notices useful opportunities without becoming intrusive.
- Performs supported actions within the owner's permissions.
- Clearly distinguishes what she knows, recommends, attempted and completed.

This matches the [Constitution](../CONSTITUTION.md) and
[personal-use acceptance definition](PERSONAL_V1_ACCEPTANCE.md).

### Governing principles

Keep one conversational identity, one accountable orchestrator and explicit authority boundaries.
Use reasoning for ambiguous judgments; use ordinary software for permissions, persistence, scheduling,
calculations and validation.

Natural conversation should come from understanding and continuity—not fabricated emotions, background
activity or claims of being human.

# Part 2 — Executive assessment

### What is strong

**OBSERVED:**

- The Constitution defines a coherent personal-use product.
- Specialists cannot directly execute tools or mutate memory.
- Consultation is bounded to three specialists, without recursive delegation.
- Structured results preserve assumptions, uncertainty and attribution.
- The browser/backend separation keeps backend credentials out of browser code.
- Durable action proposals, payload-integrity checks and approval gates already exist.
- Proactivity includes approval, quiet hours, suppression and duplicate controls.
- The acceptance checklist correctly distinguishes implemented code from live readiness.

Preserve these decisions.

### The six highest-leverage improvements

**1. Close validation and evidence-policy gaps — P0.**

The specialist-synthesis fallback rebuilds its prompt from only the first two and last two sections.
This removes recent conversation, trusted runtime outcomes and task-specific evidence restrictions.

Furthermore, if synthesis parses successfully but names an unavailable specialist, validation fails
while the parsed synthesis object still exists. Its action proposals can subsequently be returned.
Approval is still required, but a rejected synthesis should not produce actionable proposals.

The direct-answer branch also returns raw generated output when its structured response cannot be
parsed. These paths weaken the guarantees provided by the normal path. Inspect
talk_to_li_with_outcome in [Li runtime](../backend/app/li_runtime.py), particularly its parsing,
fallback_sections construction and final action_intents assignment.

**2. Enforce minimum necessary context across every channel — P0.**

Canonical memories receive some privacy filtering. However, specialists also receive a common
recent-conversation tail and temporary-upload content. Filtering memory records does not prevent
sensitive information from reaching a specialist through conversation history.

That conflicts with the constitutional requirement for task-specific disclosure. This is an observed
exposure path, not evidence that an actual disclosure incident occurred. Compare specialist packet
construction in [Li runtime](../backend/app/li_runtime.py) with section 10 of the
[Constitution](../CONSTITUTION.md).

**3. Make turns and actions recoverable — P0.**

Chat processing combines history writes, memory classification, consultations, response generation and
proposal persistence in one request. A fresh identifier is generated during processing rather than
establishing a replayable turn at ingress.

Action execution has a durable claim, but a crash after an external effect and before recording
completion leaves an uncertain outcome. The SQL resolution function can also expire an executing
intent before accepting its completion. Expired must not imply that nothing happened. Inspect
li_chat_endpoint in [main](../backend/app/main.py), decide_intent in
[action intents](../backend/app/action_intents.py), and resolve_action_intent in the historical
[state transitions](../memory/migrations/029_durable_action_intents.sql). Do not edit that migration.

**4. Replace keyword-led coordination with bounded intent-led coordination — P1.**

Routing examines the latest message, matches keywords and takes matching specialists in registry order.
The variable named ranked is not a relevance score. It cannot reliably resolve “ask her again” or
distinguish a quoted instruction from an actual delegation request.

Freshness checks are downstream of specialist selection. For example, the reviewed simple-prefix
branch sends “What is today's mortgage rate?” directly to Li, without entering the specialist freshness
path. This is a static control-flow finding, not a live response test. Inspect route_specialists in
[specialist runtime](../backend/app/specialist_runtime.py).

**5. Measure complete-turn quality, latency and usage — P1.**

The provider wrapper returns text but discards usage and completion metadata. Specialist statistics
exist, but they do not establish end-to-end reliability or whether consultation improved the answer.

The bilingual evaluation design is good; its documentation explicitly says provider-backed quality
evaluation and owner acceptance remain pending. See the
[provider wrapper](../backend/app/claude.py) and [evaluation status](LI_CONVERSATION_EVALUATION.md).

**6. Finish vertical user journeys before adding more infrastructure — P1.**

The profile-photo work demonstrates substantial implementation effort without yet delivering an
enabled, verified upload feature. Its README still describes a local foundation with production
isolation and activation prerequisites.

**INFERRED:** The project risks optimizing individual building blocks while everyday usefulness remains
unproven. The next delivery unit should be a completed user journey, not another isolated foundation.
See [profile status](../profile-service/README.md).

# Part 3 — Target architecture

Keep the existing services where they protect meaningful boundaries. Inside the backend, evolve toward
a modular application, not a network of autonomous agents.

~~~text
Owner: Home conversation or Specialist Workspace
                     ↓
Authenticated request + durable turn identity
                     ↓
Li orchestration
  ├─ Resolve intent and active task
  ├─ Select permitted context
  ├─ Check risk, evidence, capabilities and budget
  ├─ Answer directly / read tools / consult specialists
  └─ Validate and synthesize
                     ↓
Durable response + supporting activity record
                     ↓
Action proposal → required approval → executor → reconciliation
~~~

Proactive events enter the same orchestration path after their schedule, relevance, privacy and
interruption checks.

| Responsibility | Owner |
| --- | --- |
| Understanding intent, planning and conversational synthesis | Li |
| Focused domain analysis | Selected specialists |
| Context selection and disclosure enforcement | Backend context service |
| Canonical memory and provenance | Governed memory layer, with Theo's review workflow |
| Tool execution, authentication and payload validation | Deterministic executors |
| Turn progress, retries and recovery | Durable application state |
| Approval of protected actions | Existing owner-confirmation mechanisms |
| Security enforcement | Independent application, database and infrastructure controls |
| Explanations and operational statistics | Small, privacy-minimized activity records |

A specialist can request missing evidence or identify another useful perspective. Only Li decides
whether to arrange it. No specialist-to-specialist conversation loop is needed.

# Part 4 — Li improvements

### Intelligence and planning

Li should establish the objective, constraints, relevant facts and success condition before choosing
specialists.

For simple conversation, this should remain lightweight. For meaningful multi-step work, maintain a
small task record containing the objective, current step, unresolved questions, approved actions and
latest outcome. Do not reconstruct the entire plan from the last twelve messages.

### Delegation

Give each specialist a distinct question. For a training decision:

- Sofia assesses medical concerns.
- Marco evaluates training adaptations.
- Elena contributes only if nutrition materially affects the decision.

Sending everyone the same message produces overlapping answers rather than complementary expertise.

### Reviewing results

Schema validity is necessary but insufficient. Li should assess whether the result:

- Answers the delegated question.
- Uses the supplied evidence correctly.
- Relies on unsupported assumptions.
- Conflicts with another specialist's facts or constraints.
- Requires a clarification that would materially change the recommendation.

Do not average confidence scores or treat agreement between instances of the same model as independent
verification.

### User experience

The default experience remains one conversation with Li. Specialist Workspace provides optional
visibility and direct participation.

Show concise operational states such as “Checking your calendar,” “Waiting for your approval” and
“The action's outcome is uncertain.” Do not expose internal reasoning traces or make the owner
interpret infrastructure failures.

For English and Swedish, preserve the same intent, tool selection and approval requirements while
allowing naturally different wording. Keyword aliases alone cannot prove semantic equivalence.

# Part 5 — Specialist system

Names and roles below are from the [registry](../agents/registry.yaml). KEEP means preserve the role;
every specialist still benefits from the shared contract improvements.

| Specialist and existing role | Decision | Focus and boundary |
| --- | --- | --- |
| Sofia — Health & Medical Adviser | IMPROVE | Clinical interpretation and escalation. Use relevant symptoms and medical context; distinguish emergency guidance from research-dependent advice. |
| Marco — Fitness & Performance Coach | KEEP | Training, performance and recovery. Consume health constraints when relevant; do not diagnose injuries. |
| Elena — Nutrition, Cooking, Food & Drink Expert | KEEP | Meals, nutrition and culinary enjoyment. Separate cooking advice from clinical nutrition and allergy risks. |
| Amelia — Relationships, Dating & Social Adviser | KEEP | Interpersonal communication and relationships. Avoid asserting other people's motives as facts. |
| Freja — Parenting & Family Adviser | KEEP | Parenting and family decisions. Coordinate with Amelia on relationships and Oliver on legal questions; minimize children's personal information. |
| Oliver — Legal & Regulatory Adviser | IMPROVE | Require jurisdiction, relevant date and authoritative legal material where needed. Separate legal interpretation from commercial preference. |
| James — Finance & Wealth Adviser | IMPROVE | Financial planning and trade-offs. Use deterministic calculations and dated financial evidence; no transaction authority. |
| Victor — Business, Commercial & CCO Adviser | IMPROVE | Commercial strategy and negotiation. Separate commercial attractiveness from James's financial analysis and Oliver's legal assessment. |
| Nora — Research, Intelligence & Decision Adviser | IMPROVE | Evidence evaluation, uncertainty and independent challenge. Do not make Nora a compulsory intermediary for every search. |
| Milo — Travel, Leisure & Experiences Adviser | KEEP | Experience selection and planning. Prices, availability and bookings belong to verified tools and governed actions. |
| Iris — Home, Interior Design, Plants & Gardening Adviser | KEEP | Home and garden decisions. Escalate structural, electrical or other safety-critical work appropriately. |
| Clara — Wellbeing, Habits & Mental Performance Adviser | IMPROVE | Sustainable habits and wellbeing. Define boundaries with medical care and relationship advice; avoid diagnosis or pressure to optimize everything. |
| Ada — AI Architect & System Evolution Manager | KEEP | Review and propose system changes using evidence. Not an autonomous production editor. |
| Theo — Personal Memory & Knowledge Curator | IMPROVE | Provenance, contradiction handling and memory review. Keep mutation authority in governed software. |
| Heimdall — Security & Privacy Guardian | IMPROVE | Explain and review security findings. Essential protection must work even when no model is available. |

The system-agent profiles are definitions, not proof of continuously running agents. See the
[current UI distinction](../frontend/README.md).

### Overlap and consolidation

Do not merge or remove existing personalities merely to reduce the roster. Their boundaries are
understandable and meaningful to the owner.

Instead, consolidate duplicated implementation: routing definitions, evidence handling, task packets,
result validation and evaluation infrastructure.

No additional permanent specialist is justified by the gaps found. Missing capabilities are primarily
context selection, task continuity, tool coordination and recovery.

### Standard for future specialists

A versioned specialist contract should define:

- Mission, expertise, responsibilities and explicit exclusions.
- Positive routing examples, negative examples and EN/SV equivalents.
- Required inputs, permitted context and memory domains.
- Output schema, evidence requirements and uncertainty representation.
- Tool-request permissions—not credentials or direct authority.
- Collaboration, escalation and failure behavior.
- Success criteria and regression scenarios.
- Lifecycle status and owner-approved creation/change history.

The reviewed runtime also requires hard-coded triggers and exactly twelve specialists. Replace that
count constraint with contract validation before future expansion. Inspect _load_contracts in
[specialist runtime](../backend/app/specialist_runtime.py).

Creation should require demonstrated value over Li alone or an existing specialist—not just a
plausible name and prompt.

# Part 6 — Architecture and system improvements

### Context and memory

Use one context-selection path for direct answers, consultation, synthesis and recovery.

| Information | Storage and lifetime | Recipients |
| --- | --- | --- |
| Conversation messages | Conversation store under its retention policy | Li; selected excerpts for specialists |
| Active task state | Durable task state until completion/expiry | Li; relevant task fields for specialists |
| Confirmed preferences and personal facts | Canonical memory with provenance and corrections | Li; explicitly permitted, relevant specialist fields |
| Inferences | Separate candidate/review state | Never silently treated as confirmed facts |
| Project knowledge | Versioned documents or retained artifacts | Relevant excerpts with source/version |
| Evidence | Source-linked records with freshness/expiry | Specialists and Li working on that claim |
| Temporary uploads | Existing temporary lifecycle | Only participants needing that content |
| Decisions and outcomes | Concise, source-linked decision records | Li; selectively recalled |
| Operational traces | Short, policy-defined retention | Authorized diagnostics; no default content duplication |

**OBSERVED:** The context assembler exists, but chat currently feeds it conversation/history items
rather than the complete final prompt. Whole history can be omitted when its single item exceeds a
class budget. Separately, Li loads over 100 KB of constitutional, identity and operating text before
adding memory and other context. See assemble_context in
[governed systems](../backend/app/governed_systems.py) and build_li_system_prompt in
[Li runtime](../backend/app/li_runtime.py). The size is source text, not a measured provider token count.

**RECOMMENDED:** Budget the complete request, select at message boundaries and reserve output capacity.
Preserve mandatory safety rules. Derive a concise, reviewed runtime instruction set from authoritative
documents with traceable source mappings; do not silently replace those documents.

Retain provenance, privacy and temporal metadata in specialist packets rather than reducing memories
to a value and confidence score.

### Tools and capability truth

Li needs a current, explicit view of which operations are implemented, configured, permitted and
available. A configured provider is not proof that an operation will succeed.

Evaluate freshness and risk before deciding whether a specialist is needed. Read tools should supply
facts directly to orchestration; specialists interpret those facts. A blocked research provider must
not prevent immediate emergency guidance.

Keep state-changing operations in existing typed, approval-governed executors. Never give specialists
direct database or provider credentials.

### Reliability and cost

Establish a bounded turn deadline, model-call budget, output budget and concurrency budget. The provider
wrapper currently does not set an application-specific timeout/retry policy, and specialist futures
are awaited without a consultation deadline.

A thread timeout alone does not cancel an underlying provider call. Deadline design must reach the
actual provider request.

Use included or verified prepaid capacity only. Record usage without claiming that subscription
ownership proves API coverage.

### Testing and observability

Extend the existing bilingual evaluation suite rather than inventing a second framework.

The permanent scenarios should include:

- Equivalent EN/SV requests, paraphrases, negation and quoted instructions.
- Ambiguous follow-ups and mid-task language changes.
- Private facts in history, not only canonical memory.
- Unavailable or contradictory evidence.
- Invalid specialist output and invalid final attribution.
- Slow providers, client disconnects and process restarts.
- Uncertain external writes and repeated approvals.
- Memory corrections followed by recall.
- Proactive usefulness, quiet hours, duplicate suppression and stand-down.

Record turn ID, selected specialists, selection reason, context references and omission reasons,
tool/result status, validation outcome, latency, retries and usage. Record concise decision
explanations—not hidden chain-of-thought or full private prompts.

### Developer experience

Separate orchestration responsibilities inside the backend without changing public contracts
unnecessarily. There should be an obvious place for intent planning, context selection, evidence
policy, consultations, synthesis and action execution.

Update documentation when a state changes from proposed to implemented or verified. The profile README
and acceptance baseline contain historical statements that no longer fully describe the accumulated
repository work. Recheck current facts before updating those statements.

# Part 7 — What not to build

- No autonomous specialist mesh. Avoid circular delegation, shared unrestricted memory and
  agent-to-agent chatter.
- No extra supervisor/reviewer model on every message. Use targeted review only where it earns its
  latency and usage.
- No permanent agent for deterministic work. Scheduling, calculations, deduplication and permission
  checks are software responsibilities.
- No automatic self-modification or specialist creation. Ada can propose; approved development changes
  remain separately governed.
- No vector database merely because this is an AI product. First measure retrieval failures; add
  semantic retrieval only if it improves representative cases.
- No human-imitation training objective. Optimize naturalness, usefulness and continuity while
  preserving honest identity.
- No full event-sourcing platform or general workflow engine yet. Small durable turn/task records can
  address current recovery needs.
- No claim that portraits or activity charts make an agent operational.
- Do not make optional profile-photo infrastructure the critical path for dependable personal use.
  Preserve completed work and its security requirements; finish it as a bounded feature when
  prerequisites are satisfied.
- Delay native-app expansion and broad self-improvement mechanisms until the agreed installable-web
  journeys are dependable. This changes sequencing, not the agreed scope.

**OWNER DECISION, only if pursued later:** changing the separate profile-service architecture requires
an explicit architectural decision and updated authoritative design. Sol should not quietly collapse
its credential or decoder-isolation boundaries. Consult the
[Owner Profile Photo architecture](../system/OWNER_PROFILE_PHOTO_ARCHITECTURE.md).

# Part 8 — Top recommendations

| Priority | Stage | Recommendation | Why | Impact | Complexity | Dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Foundation | Preserve safety and evidence constraints through every response path | Current fallbacks weaken validation | Correctness and trust | Medium | Reproduction tests |
| P0 | Foundation | Unify context selection and privacy enforcement | History/uploads bypass memory-only filtering | Privacy and continuity | High | Context provenance contract |
| P0 | Foundation | Durable turns and recoverable action execution | Retries and partial completion need truthful state | Reliability | High | State design; separate approval to apply schema changes |
| P1 | Near Term | Intent-led, registry-defined delegation | Keywords cannot support coherent multi-turn work | Intelligence and simplicity | Medium | Safe context and capability contracts |
| P1 | Foundation → Near Term | Whole-turn evaluation and usage visibility | Component tests do not prove product improvement | Measurable quality and cost control | Medium | Start with existing tests |
| P1 | Near Term | Complete personal-use journeys | Foundations are not usable features | Everyday usefulness | Medium | P0 fixes; release approvals where required |

Future direction: measured retrieval improvements and outcome-based personalization. Do not build
either before the evaluation suite demonstrates the need.

# Part 9 — Implementation sequence

Use six meaningful work packages. Begin the evaluation baseline immediately, then extend it through
each package.

| Package | Objective and changes | Why now / dependencies | Expected end state and validation |
| --- | --- | --- | --- |
| 1. Response safety | Unify validation, evidence restrictions and fallback behavior | First: closes concrete correctness defects | Rejected outputs cannot create proposals; freshness restrictions survive failures |
| 2. Context continuity | Introduce selective, provenance-aware packets and complete-request budgeting | Before smarter delegation; depends on package 1's response contract | Relevant context survives; unrelated/private content does not reach specialists |
| 3. Recoverable execution | Add stable turn identity, bounded work and uncertain-outcome recovery | Before more autonomous workflows | Disconnect/restart/retry tests show no duplicate effects or false completion |
| 4. Coherent delegation | Resolve intent and task state; generate focused registry-governed consultations | Uses packages 1–3 | EN/SV scenarios select appropriate capabilities with fewer unnecessary calls |
| 5. Evidence of improvement | Extend evaluations, traces, latency and usage measurement | Baseline first; instrument all preceding packages | Reproducible comparison shows safety, quality and performance outcomes |
| 6. Personal-use completion | Finish and verify existing end-to-end journeys | After P0 closure; requires package 5 evidence | Acceptance rows close only with the required local, live and device evidence |

# SOL IMPLEMENTATION HANDOFF

For GPT-5.6 Sol: recheck the working tree and current revision before implementation. Preserve unrelated
work, including any existing untracked portrait ZIP. Follow repository review, testing and release
rules. Do not interpret this blueprint as permission to deploy, apply migrations, change cloud
resources or incur additional charges. The opening execution instructions apply to every package.

## WORK PACKAGE: RESPONSE SAFETY

**Priority:** P0

**Stage:** Foundation

### Objective

Make response validation and evidence requirements invariant across success, partial failure and
fallback paths.

### Why

A failure must not produce a less-protected answer than the normal path.

### Current Problem

Invalid synthesis can discard task-specific restrictions. Rejected attribution can leave proposals
available. Direct parsing failure returns raw output.

### Desired End State

Only validated outcomes reach the response and action-proposal layers.

### Implementation Requirements

Use explicit validation outcomes instead of checking whether a local variable exists. Clear proposals
and attribution on rejection. Preserve mandatory context during any bounded repair attempt. Apply
evidence requirements independently of specialist routing. Provide a safe, non-actionable response when
repair fails.

### Likely Areas Affected

[Li runtime](../backend/app/li_runtime.py), [freshness policy](../backend/app/freshness_policy.py),
[specialist runtime](../backend/app/specialist_runtime.py), and orchestration/conversation tests in
[backend tests](../backend/tests/).

### Dependencies

Add regression tests reproducing the current paths first.

### Preserve

Existing approvals, source requirements, truthful specialist attribution and immediate safety guidance.

### Failure Cases

Malformed JSON, unavailable specialist attribution, missing evidence, failed repair and provider
unavailability.

### Validation

Test invalid attribution containing an action proposal; required-current-evidence failure followed by
synthesis failure; direct current-world questions; equivalent Swedish cases. Cover R1–R4 and R11.

### Definition of Done

All response branches satisfy the same safety invariants, with passing focused and applicable
regression suites.

### Do Not

Return rejected raw output, weaken evidence requirements, or retry generation indefinitely.

## WORK PACKAGE: CONTEXT PRIVACY AND CONTINUITY

**Priority:** P0

**Stage:** Foundation

### Objective

Supply each participant with sufficient, permitted context and no unnecessary personal information.

### Why

Privacy and useful continuity must be enforced together.

### Current Problem

Specialists receive shared history/upload context. The current budget does not cover the complete
final request, and memory metadata is reduced during delegation.

### Desired End State

A unified context layer produces bounded, task-specific packets with provenance and disclosure decisions.

### Implementation Requirements

Preserve privacy labels through history, memory, task state and attachments. Replace substring domain
authorization with explicit permitted identifiers. Select whole relevant messages or reviewed summaries.
Budget core instructions, evidence, history and output together. Trace any condensed runtime policy
back to authoritative documents.

### Likely Areas Affected

[Governed systems](../backend/app/governed_systems.py), [backend main](../backend/app/main.py),
[Li runtime](../backend/app/li_runtime.py), [specialist runtime](../backend/app/specialist_runtime.py),
and [Li operating rules](../li/operating-rules.md).

### Dependencies

Package 1's stable response/validation contract.

### Preserve

Private-to-Li boundaries, temporary-upload retention rules, factual provenance and existing governance
of memory changes.

### Failure Cases

Sensitive facts repeated in chat, unrelated attachments, outdated memory, missing privacy metadata
and oversized conversation history.

### Validation

Synthetic tests must prove both exclusion of forbidden context and retention of necessary context
across EN/SV follow-ups. Cover R5, R6 and R10, plus mandatory-budget overflow.

### Definition of Done

Every model-facing packet uses the context layer; privacy and complete-request budget tests pass.

### Do Not

Solve filtering by sending everything to another model, silently truncate mandatory rules, or introduce
a new retrieval service without evidence of need.

## WORK PACKAGE: RECOVERABLE TURNS AND ACTIONS

**Priority:** P0

**Stage:** Foundation

### Objective

Make retries, interruptions and partial completion safe and understandable.

### Why

An external action can succeed even when Li loses the response.

### Current Problem

Chat lacks a stable ingress-level replay identity. Claimed actions can remain unresolved, and expiration
can obscure an execution attempt.

### Desired End State

Each turn and action has a durable, truthful lifecycle that survives retries and restarts.

### Implementation Requirements

Bind idempotency to owner, operation and payload. Persist stage outcomes. Distinguish failed, completed
and uncertain execution. Use provider reconciliation or supported idempotency before retrying writes.
Propagate deadlines to providers and bound model calls/concurrency. Prepare new migrations where
necessary; do not edit applied history.

### Likely Areas Affected

[Backend main](../backend/app/main.py), [action intents](../backend/app/action_intents.py),
[runtime data](../backend/app/runtime_data.py), [provider wrapper](../backend/app/claude.py),
[specialist runtime](../backend/app/specialist_runtime.py), [migrations](../memory/migrations/), and
frontend request handling in [app.js](../frontend/static/assets/app.js).

### Dependencies

Packages 1–2; exact authorization before applying any migration to an external target.

### Preserve

Approval scope, payload hashes, owner binding and existing executor separation.

### Failure Cases

Duplicate submission, response lost after provider success, database failure during completion,
restart after claim and deadline exhaustion.

### Validation

Fault-injected tests at every boundary; prove no duplicate effects and no false claim that nothing
happened. Cover R8–R9 and repeated/stale approvals. Rehearse new SQL only in isolated disposable storage.

### Definition of Done

Supported operations recover or explicitly expose uncertainty, with tested reconciliation behavior.
Any external migration/deployment remains separately recorded as pending until authorized and verified.

### Do Not

Blindly retry writes, promise universal exactly-once execution, or build a general distributed workflow
platform.

## WORK PACKAGE: COHERENT LI DELEGATION

**Priority:** P1

**Stage:** Near Term

### Objective

Make Li choose capabilities from the actual task rather than isolated keywords.

### Why

A coherent assistant must understand references, constraints and what each specialist adds.

### Current Problem

Routing uses the latest message and registry-order keyword matches. Task packets lack the explicit
objectives and specialist-specific questions required by the operating rules.

### Desired End State

Li answers directly when appropriate and arranges bounded, complementary consultations when useful.

### Implementation Requirements

Resolve intent using permitted conversation/task state. Retain deterministic handling for unambiguous
explicit requests and exclusions. Use bounded model-assisted planning only where needed. Validate
plans against registered capabilities and permissions. Define per-specialist questions, shared facts,
evidence needs and success criteria. Validate contracts rather than an exact roster count.

### Likely Areas Affected

[Registry](../agents/registry.yaml), [specialist runtime](../backend/app/specialist_runtime.py),
[request language](../backend/app/request_language.py), [Li runtime](../backend/app/li_runtime.py),
and routing tests in [backend tests](../backend/tests/).

### Dependencies

Packages 1–3.

### Preserve

Existing names and roles, specialist independence, no direct tool authority and the consultation bound.

### Failure Cases

Quoted names, negation, “ask her again,” language switching, conflicting recommendations and unavailable
specialists.

### Validation

Compare direct and specialist-assisted outcomes on representative bilingual scenarios; measure
unnecessary consultations and missed useful consultations. Cover R3, R7 and R11, and confirm that
equivalent requests have the same permission requirements, not necessarily identical wording.

### Definition of Done

Routing and handoff quality improve without violating permission or latency budgets.

### Do Not

Add another permanent agent, invoke a planner on every greeting, or treat model confidence as verified
correctness.

## WORK PACKAGE: EVALUATION AND OBSERVABILITY

**Priority:** P1

**Stage:** Foundation

### Objective

Make improvements measurable and failures diagnosable.

### Why

Passing mocked component tests does not establish natural conversation or dependable daily use.

### Current Problem

Useful evaluation scaffolding exists, but complete-turn quality and provider usage are not consistently
captured.

### Desired End State

A small permanent benchmark and privacy-minimized trace explain both product quality and operational
failures.

### Implementation Requirements

Start with the existing bilingual scenarios. Add routing, privacy, evidence, recovery and proactive-
usefulness cases. Capture provider usage, stop status, stage timing and validation results through a
structured internal response. Record revisions and evaluation conditions. Keep raw personal content
out of routine diagnostics.

### Likely Areas Affected

[Voice evaluation](../backend/app/voice_evaluation.py), [provider wrapper](../backend/app/claude.py),
[runtime data](../backend/app/runtime_data.py), [backend tests](../backend/tests/),
[conversation evaluation](LI_CONVERSATION_EVALUATION.md), and [Testing and audit](TESTING_AND_AUDIT.md).

### Dependencies

Baseline immediately; integrate results from packages 1–4. This package is cross-cutting, not something
to postpone until all implementation has finished.

### Preserve

Synthetic fixtures, isolated evaluation and existing no-spending restrictions.

### Failure Cases

Missing telemetry, partial evaluations, sensitive data in logs, and mocks that conceal integration
failures.

### Validation

Inject known failures and confirm traces identify their stage. Run paired-language comparisons and
record skipped/live-unverified checks honestly. Cover R13 and instrumentation for R1–R12.

### Definition of Done

Each package has reproducible acceptance evidence; quality, latency and usage changes are visible.
Live-model quality remains unverified if an authorized, covered evaluation has not run.

### Do Not

Use AI-detection scores, log hidden reasoning, or run paid evaluations without verified coverage.

## WORK PACKAGE: COMPLETE PERSONAL-USE JOURNEYS

**Priority:** P1

**Stage:** Near Term

### Objective

Turn existing components into dependable everyday experiences on Android phone/tablet and Windows.

### Why

The completion unit is something Christoffer can reliably do—not another merged foundation.

### Current Problem

Repository implementation, production activation and device acceptance remain uneven.

### Desired End State

The agreed first-release journeys work end to end, with honest capability and recovery states.

### Implementation Requirements

Complete chat/history, specialist group conversation, permitted memory operations, files and one useful
proactive journey. Reuse the same state and permission contracts throughout. Keep optional profile-photo
work bounded and preserve its isolation prerequisites. Update acceptance evidence and distinguish
implemented, configured, deployed and verified states.

### Likely Areas Affected

[Frontend main](../frontend/app/main.py), [app.js](../frontend/static/assets/app.js),
[Specialist Workspace](../frontend/SPECIALIST_VIEW.md), [proactivity](../backend/app/proactivity.py),
[proactive watchers](../backend/app/proactive_watchers.py),
[profile-service README](../profile-service/README.md), and
[personal-use acceptance](PERSONAL_V1_ACCEPTANCE.md).

### Dependencies

P0 packages closed, package 5 evidence, and separately authorized external activation where needed.

### Preserve

The owner's existing design choices, approved portraits, themes, CM fallback, Li's visibility into
Specialist Workspace and quiet-hour controls.

### Failure Cases

Expired sign-in, offline launch, unavailable provider, unsaved history, duplicate briefs, denied
microphone permission and unavailable photo service.

### Validation

Synthetic full-stack journeys first; then authorized live smoke tests and physical-device checks.
Record failures rather than marking incomplete features passed. Cover R10–R14 and the existing
personal-use acceptance rows; one successful proactive journey does not prove every rhythm complete.

### Definition of Done

Applicable acceptance rows contain dated evidence for the reviewed release, with no unresolved critical
findings or misleading readiness claims. Identify any wider agreed scope that remains unfinished.

### Do Not

Declare 100% from green CI, activate chargeable infrastructure, bypass protected approvals, or invent
new scope to avoid finishing existing journeys.
