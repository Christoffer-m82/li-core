# Li OS Memory Storage Policy

**Version:** 0.1
**System:** Li OS
**Primary User:** Christoffer Melldén
**Memory Curator:** Theo
**Primary Coordinator:** Li
**Security Guardian:** Heimdall
**Status:** Foundational

---

## 1. Purpose

Li OS is intended to know Christoffer increasingly well over many years.

That makes personal memory one of the most important assets in the entire system.

Personal memory must therefore be:

* private;
* durable;
* structured;
* portable;
* correctable;
* historically aware;
* searchable;
* recoverable;
* model-independent;
* and owned by Christoffer.

The central principle is:

> **Christoffer's personal memory belongs to Li OS, not to whichever AI model happens to power Li today.**

---

## 2. Canonical Memory

Li OS must have one authoritative source for persistent personal memory.

This is called the:

> **Canonical Personal Memory Store**

The canonical memory store contains the durable records representing what Li OS knows about Christoffer.

Claude, another AI model, chat history, embeddings, summaries, caches, and specialist-agent context must not become the sole source of important personal memory.

---

## 3. Initial Recommended Architecture

The preferred initial architecture is:

```text
Christoffer
     │
     ▼
    Li
     │
     ▼
Memory API
     │
     ├──────────────► Theo
     │                 │
     │                 ▼
     │          Memory validation
     │
     ▼
Private structured database
     │
     ├── canonical memories
     ├── people
     ├── goals
     ├── decisions
     ├── commitments
     ├── open loops
     └── timeline
     │
     ├──────────────► Semantic search index
     │
     ├──────────────► Encrypted document storage
     │
     └──────────────► Encrypted backups
```

The exact technology may change.

The architecture should not depend permanently on one database provider.

---

## 4. Recommended First Database

The preferred first implementation is a private **PostgreSQL-compatible database**.

Reasons include:

* structured records;
* mature access control;
* strong backup tooling;
* portability;
* transactional integrity;
* query flexibility;
* ability to support vector search;
* broad infrastructure support.

A managed PostgreSQL service may be used if security and export requirements are satisfied.

The database provider itself must not become the owner of Li OS memory.

---

## 5. Technology Independence

The memory policy defines behavior rather than permanent vendor choice.

Li OS should be capable of moving from:

```text
Provider A
    ↓
PostgreSQL export
    ↓
Provider B
```

without reconstructing Christoffer from conversations.

---

## 6. Storage Layers

Li OS should separate different types of storage.

### Layer 1 — Canonical Structured Memory

Authoritative persistent personal information.

### Layer 2 — Semantic Index

Derived search representations used to find relevant memories.

### Layer 3 — Document Storage

Files and larger source materials associated with personal memory.

### Layer 4 — Working Context

Temporary information supplied to Li or specialists during a task.

### Layer 5 — Cache

Temporary performance optimization.

### Layer 6 — Backups

Encrypted recoverable copies.

### Layer 7 — Secrets

Credentials and cryptographic material stored separately.

---

## 7. Canonical Structured Memory

Canonical memory should follow:

`memory/schema.yaml`

Each significant memory record should preserve at minimum:

* unique ID;
* memory class;
* domain;
* value;
* source;
* creation date;
* confidence;
* truth status;
* temporal status;
* sensitivity.

Where appropriate it should also retain:

* validity dates;
* related people;
* supporting evidence;
* superseded records;
* tags;
* review date;
* permissions;
* outcomes;
* source references.

---

## 8. Structured Memory Before Free-Form Biography

Li OS should avoid storing Christoffer primarily as one enormous biography or continually rewritten summary.

Prefer structured atomic records such as:

```text
Memory A
Preference:
Prefers smaller boutique hotels.

Memory B
Historical fact:
Lived in location X during period Y.

Memory C
Goal:
Improve cardiovascular fitness.

Memory D
Outcome:
Restaurant X was strongly liked.
```

These can later be assembled into summaries when needed.

---

## 9. Summaries Are Derived

Profile summaries may be useful.

Examples:

* current-life summary;
* health summary;
* professional summary;
* relationship summary;
* travel-preference summary.

But summaries are **derived representations**.

They must not silently replace the underlying records.

---

## 10. Semantic Search

Li OS may use vector embeddings or similar technology to find relevant memories by meaning.

Example:

Christoffer asks:

> "What kind of hotel would I probably like in Barcelona?"

Semantic retrieval may find previous memories relating to:

* hotels;
* travel style;
* noise;
* room size;
* location;
* service;
* atmosphere.

---

## 11. Semantic Index Is Not Source of Truth

Embeddings are a search aid.

They are not the canonical memory.

If the semantic index is lost, it should be possible to rebuild it from the canonical memory store.

```text
Canonical memory
       ↓
Regenerate
       ↓
Semantic index
```

Never:

```text
Semantic index lost
       ↓
Christoffer's memory lost
```

---

## 12. Embeddings Are Sensitive

Embeddings derived from sensitive information should be protected according to the sensitivity of the source material.

They should not be considered harmless merely because they are numerical vectors.

---

## 13. Document Storage

Some information is better stored as a document rather than broken entirely into memory records.

Examples:

* medical report;
* contract;
* financial document;
* travel document;
* important correspondence;
* photograph;
* certificate;
* long report.

Such documents should live in secure object or file storage rather than readable GitHub.

---

## 14. Memory May Reference Documents

Canonical memory may contain references such as:

```text
memory_id:
health-000482

type:
historical_fact

value:
Health examination performed.

source_document:
document-000155
```

The full source document can remain separately protected.

---

## 15. Raw Conversations

Li OS should not automatically treat every conversation as permanent memory.

Conversation history may be useful for temporary continuity, but permanent memory should be selectively curated.

Otherwise the system risks accumulating:

* noise;
* contradictions;
* fleeting emotions;
* jokes;
* temporary opinions;
* incorrect assumptions;
* unnecessary sensitive information.

---

## 16. Conversation-to-Memory Pipeline

A preferred process is:

```text
Conversation
    ↓
Potential memory detected
    ↓
Li evaluates relevance
    ↓
Theo classifies
    ↓
Permission / sensitivity check
    ↓
Canonical memory written
```

Not:

```text
Everything Christoffer says
    ↓
Permanent memory forever
```

---

## 17. Memory Write Authority

Normal specialist agents should not directly modify canonical personal memory.

Preferred flow:

```text
Specialist
    ↓
Memory proposal
    ↓
Li
    ↓
Theo
    ↓
Canonical store
```

Li may directly write limited low-risk explicit information where system policy permits.

---

## 18. Theo's Responsibilities

Theo is responsible for memory quality.

Theo should help determine:

* whether information deserves retention;
* appropriate memory class;
* confidence;
* truth status;
* temporal status;
* sensitivity;
* duplicate detection;
* contradictions;
* relationships between records;
* whether old information should remain current;
* whether information should be reviewed later.

---

## 19. Explicit Facts

When Christoffer directly states a personal fact, provenance should reflect that.

Example:

```text
source_type:
user_explicit

source:
Christoffer Melldén

confidence:
high

truth_status:
confirmed
```

This does not mean every statement must be retained.

Retention still depends on usefulness.

---

## 20. Inferences

An inference should remain visibly an inference.

Example:

```text
class:
inference

value:
Christoffer may prefer quieter hotels.

confidence:
0.65

truth_status:
inferred
```

It must not later become:

```text
Fact:
Christoffer prefers quiet hotels.
```

without additional evidence or confirmation.

---

## 21. Corrections

When Christoffer corrects information, Li OS should update its current understanding.

Where useful, the previous state should remain historically available.

Example:

```text
Old:
Preference X

Status:
outdated

Superseded by:
memory-002918
```

This protects history without continuing to treat the old information as current.

---

## 22. Contradictions

Conflicting memories should not be silently resolved by whichever entry is newest.

Theo should determine whether:

* one is incorrect;
* circumstances changed;
* both apply in different situations;
* either remains uncertain;
* Christoffer should be asked.

---

## 23. Temporal Memory

Memory should understand time.

A fact may be:

* current;
* historical;
* temporary;
* planned;
* unresolved.

Example:

```text
role:
Company X

valid_from:
2025-01-01

valid_until:
2027-06-01

temporal_status:
historical
```

This is better than deleting the old role after a job change.

---

## 24. People Memory

People should have stable IDs where appropriate.

Example:

```text
person_id:
person-000012

name:
Example Person
```

Memories can then refer to the person without duplicating their whole profile.

---

## 25. Third-Party Privacy

Information about other people should be retained only when reasonably useful to Christoffer.

Li OS should avoid accumulating unnecessary:

* intimate details;
* secrets;
* unsupported accusations;
* sensitive personal data;
* psychological profiling.

---

## 26. Separate User Namespaces

The memory architecture should support multiple users eventually.

Initial namespace:

```text
user/christoffer
```

Future possible namespace:

```text
user/elias
```

Shared future family information may use a separate explicitly defined namespace.

For now only:

```text
user/christoffer
```

is active.

---

## 27. No Elias Memory Namespace Yet

Elias Melldén is a future secondary user only.

Do not create:

```text
user/elias
```

as an active user-memory store yet.

Information about Elias that is relevant to Christoffer may exist within Christoffer's family and parenting context.

A separate Elias architecture will be designed only when Christoffer activates it.

---

## 28. Sensitivity Levels

Storage should recognize the sensitivity classes defined in the memory schema:

### Low

Ordinary information with limited privacy impact.

### Personal

Private personal context.

### Sensitive

Information requiring stronger controls.

### Highly Sensitive

Information such as significant health, financial, legal, intimate, or confidential information.

### Secret

Credentials or cryptographic secrets.

---

## 29. Secret Data

Secret values should not be stored in the personal memory database.

Examples:

* passwords;
* API keys;
* private keys;
* recovery codes.

They belong in a dedicated secrets-management system.

---

## 30. Encryption at Rest

Sensitive personal data should be encrypted when stored.

This includes:

* database storage;
* object storage;
* backups;
* local copies where applicable.

---

## 31. Encryption in Transit

Connections carrying private Li OS data should use secure encrypted transport.

Unencrypted transmission of sensitive memory should not be allowed.

---

## 32. Encryption Keys

Encryption keys should be stored separately from encrypted backups where practical.

Avoid:

```text
backup.enc
backup-key.txt
```

in the same repository or storage location.

---

## 33. GitHub

GitHub is the source of truth for the **Li OS system definition**.

GitHub should contain:

* memory schema;
* memory policies;
* migration code;
* database schemas;
* retrieval logic;
* tests;
* backup procedures;
* infrastructure definitions;
* documentation.

Readable GitHub should not become the canonical store for Christoffer's private memory.

---

## 34. What GitHub May Hold About Memory

Allowed examples:

```text
memory/
├── schema.yaml
├── permissions.yaml
├── storage-policy.md
├── migrations/
├── tests/
└── backup-tools/
```

GitHub describes **how memory works**.

The private database contains **what Li remembers**.

---

## 35. Encrypted GitHub Backup

GitHub may eventually hold encrypted memory backups.

Example:

```text
backups/
└── memory/
    └── 2026-08-23.memory.enc
```

The file should be unreadable without the separate decryption key.

---

## 36. GitHub Is Not the Only Backup

GitHub should not necessarily be the sole backup destination.

A robust future design may use:

```text
Production memory
      │
      ├──► encrypted backup location A
      │
      └──► encrypted backup location B
```

At least one recovery copy should ideally be independent of the production provider.

---

## 37. Backup Cadence

Initial target:

### Daily

Encrypted automated backup of canonical memory.

### Weekly

Backup-integrity verification.

### Monthly

Broader export and recovery validation.

### Before Major Updates

Create an additional verified snapshot.

Cadence may later be adjusted based on real system use.

---

## 38. Backup Contents

A complete memory backup should be sufficient to reconstruct:

* canonical memory records;
* people;
* goals;
* decisions;
* commitments;
* open loops;
* timeline;
* permissions;
* provenance;
* memory relationships;
* memory schema version;
* relevant document references.

---

## 39. Derived Data Need Not Be Primary Backup

Rebuildable data may not require the same backup priority.

Examples:

* vector indexes;
* caches;
* temporary summaries.

If rebuilding them is cheap and reliable, canonical data should take priority.

---

## 40. Backup Verification

Backups should be checked for:

* existence;
* expected size;
* integrity;
* encryption;
* schema compatibility;
* successful decryption in controlled tests;
* ability to restore.

A successful backup job does not prove successful recovery.

---

## 41. Restore Testing

Li OS should periodically perform a controlled restore test.

The test should verify:

```text
Backup
   ↓
Decrypt
   ↓
Restore
   ↓
Validate records
   ↓
Run retrieval test
   ↓
Confirm success
```

---

## 42. Recovery Objective

The long-term objective is that even if the main Li OS infrastructure disappears, Christoffer can rebuild Li from:

```text
GitHub configuration
+
Encrypted personal memory backup
+
Encryption / recovery credentials
+
Deployment documentation
```

This is a foundational design goal.

---

## 43. Model Memory

Memory provided directly by an AI platform may be useful as working memory.

It should not be treated as the sole canonical store.

If Claude remembers something, Li OS should still preserve important information independently where appropriate.

---

## 44. Model Migration

Changing from one AI model to another must not require Christoffer to teach his life story again.

Preferred architecture:

```text
Claude
   │
   ▼
Li Memory API
   ▲
   │
Future AI Model
```

Both interact with the same canonical Li OS memory.

---

## 45. Context Assembly

Li should not receive the entire memory database for every conversation.

Instead:

```text
Request
   ↓
Determine relevant domains
   ↓
Permission check
   ↓
Memory retrieval
   ↓
Rank relevant records
   ↓
Build compact context
   ↓
Li
```

---

## 46. Minimum Relevant Context

Retrieval should optimize for relevance rather than maximum recall.

Li should receive enough memory to answer well without unnecessarily exposing unrelated information.

---

## 47. Specialist Context

Specialists should receive an even smaller context set.

Example:

```text
Canonical memory
      ↓
Li retrieval
      ↓
Relevant context
      ↓
Permission filter
      ↓
Specialist context packet
```

---

## 48. Private-to-Li Memory

Records marked:

```text
private_to_li: true
```

should not normally enter specialist context.

Li may ask Christoffer before sharing them where useful.

---

## 49. Retrieval Audit

Highly sensitive retrieval may eventually be auditable.

Possible record:

```text
timestamp:
2026-08-23T16:00:00+02:00

agent:
sofia

domain:
health

purpose:
health consultation

records_accessed:
12
```

Avoid duplicating the sensitive contents themselves in audit logs.

---

## 50. Working Context

Temporary task context should expire.

Examples:

* one-off uploaded document;
* temporary travel search;
* short-lived discussion context;
* specialist task packet.

Temporary context should not automatically become permanent memory.

---

## 51. Cache

Caches may improve performance but must be treated as disposable.

Loss of a cache should not cause permanent information loss.

Sensitive caches should:

* be protected;
* have limited retention;
* be clearable.

---

## 52. Memory Deletion

Christoffer may request deletion.

Deletion should consider:

* canonical record;
* derived indexes;
* summaries;
* caches;
* document references;
* future backups;
* historical integrity.

The system should explain what can and cannot be immediately removed from existing encrypted backups.

---

## 53. Memory Export

Christoffer should be able to export his memory in portable formats.

Supported target formats include:

```text
JSON
YAML
CSV
Markdown
```

A structured JSON export should be considered the principal machine-readable portability format.

---

## 54. Human-Readable Export

Li OS should also be able to generate a readable personal knowledge export.

Possible sections:

```text
Identity
People
Timeline
Preferences
Goals
Health
Fitness
Work
Travel
Decisions
Commitments
Lessons
Open loops
```

This is generated from the structured memory store.

---

## 55. Data Ownership

Christoffer owns his personal Li OS memory.

System providers are infrastructure providers, not owners of his personal history.

---

## 56. Memory Lock-In

Theo and Ada should reject memory systems that create unacceptable vendor lock-in unless reliable export exists.

Before adopting a memory provider, verify:

* export format;
* API access;
* backup options;
* migration path;
* deletion controls;
* security model.

---

## 57. Database Migrations

Schema changes should use versioned migrations.

Example:

```text
memory schema v0.1
        ↓
migration
        ↓
memory schema v0.2
```

Do not manually alter production memory structures without traceable migration history.

---

## 58. Migration Safety

Before a significant migration:

1. create backup;
2. verify backup;
3. test migration on non-production copy;
4. validate record counts;
5. validate permissions;
6. validate relationships;
7. validate retrieval;
8. run Theo integrity review;
9. run Heimdall security review;
10. migrate production.

---

## 59. Rollback

A failed schema or infrastructure migration should be reversible.

Rollback should restore the system without intentionally deleting legitimate new life memories created after the migration began.

---

## 60. Memory Integrity Checks

Theo should eventually perform automated integrity checks.

Examples:

* orphaned person references;
* invalid dates;
* missing sources;
* impossible sensitivity values;
* duplicated records;
* conflicting current facts;
* missing permissions;
* broken document links;
* unclassified inferences.

---

## 61. Memory Quality Review

Memory quality should be evaluated separately from quantity.

More memories are not necessarily better.

Useful memory should be:

* relevant;
* accurate;
* appropriately specific;
* sourced;
* timely;
* retrievable.

---

## 62. Memory Pruning

Some low-value information may eventually be compressed, archived, or removed.

Examples:

* obsolete temporary context;
* duplicate information;
* low-value transient details.

Pruning should not casually destroy meaningful history.

---

## 63. Memory Consolidation

Repeated compatible observations may eventually support a stronger preference.

Example:

```text
Outcome 1:
Loved small boutique hotel.

Outcome 2:
Loved another small boutique hotel.

Outcome 3:
Disliked large resort.

        ↓

Possible preference:
Tends to prefer smaller boutique hotels.
```

Theo may create the preference while preserving evidence links.

---

## 64. Inference Review

Important inferences may have a `review_after` date.

Example:

```text
Inference:
May prefer early flights.

Review after:
5 future travel decisions
```

This allows personalization to improve without prematurely converting assumptions into facts.

---

## 65. Historical Continuity

The memory architecture should allow Li to understand:

> "What was Christoffer's life like in 2026?"

as well as:

> "What is true now?"

This requires preserving historical state.

---

## 66. Event Timeline

Important events should be linkable to related memories.

Example:

```text
Event:
Moved home

Related:
- location change
- new commute
- home preferences
- new local services
```

---

## 67. Memory and Current World Facts

Li OS should avoid permanently storing ordinary world facts as personal memory unless personally relevant.

Example:

Do not store:

> The capital of France is Paris.

Do store when useful:

> Christoffer visited Paris and particularly enjoyed X.

---

## 68. Memory and Professional Knowledge

Medical research belongs primarily to Sofia's professional knowledge system.

Christoffer's reaction to a treatment or health decision belongs to personal memory.

These are separate.

---

## 69. Memory and Lessons

A lesson may combine:

```text
Personal context
+
Recommendation
+
Outcome
+
Interpretation
```

Lessons should explain why something may work for Christoffer rather than pretending it is universally correct.

---

## 70. Source Preservation

Where practical, memory should retain enough provenance to answer:

> "Why do you think that?"

Possible sources:

* Christoffer explicitly said it;
* connected calendar;
* previous outcome;
* imported record;
* document;
* agent observation;
* inference.

---

## 71. Imported Data

Future imports may include:

* contacts;
* calendar history;
* email;
* photos;
* health data;
* financial exports;
* travel history;
* documents.

Imported data must not automatically become canonical memory simply because it was available.

Theo should determine what deserves structured retention.

---

## 72. Bulk Imports

Bulk imports require special care.

Before importing large datasets:

* define purpose;
* define sensitivity;
* define retention;
* identify third-party data;
* verify permissions;
* determine what will become memory;
* review security.

---

## 73. Email Memory

Li may learn meaningful information from email, but should not turn the entire inbox into personal memory.

Examples worth remembering may include:

* important commitments;
* important people;
* significant decisions;
* travel confirmations;
* major life events.

---

## 74. Calendar Memory

Calendar information may provide useful historical evidence.

But a calendar event does not always prove that something actually happened.

Distinguish:

```text
Scheduled:
Dinner with X.

Confirmed outcome:
Dinner occurred.
```

where that distinction matters.

---

## 75. Location Memory

Do not automatically create a permanent history of every location Christoffer visits.

Store location history only when there is meaningful value.

Examples:

* home;
* workplace;
* important travel;
* meaningful places;
* recurring preference.

---

## 76. Health Memory

Health memory receives heightened protection.

Where practical, health information should be logically separable from lower-sensitivity lifestyle memory.

Sofia should receive appropriate health context.

Other agents receive only task-relevant summaries.

---

## 77. Financial Memory

Financial records should be highly protected.

Li may remember useful financial context without storing unnecessary banking secrets or transaction detail.

Raw account credentials must never become memory.

---

## 78. Work-Confidential Memory

Company-confidential information should be separated from ordinary professional profile information.

Access should follow:

`memory/permissions.yaml`

A future company-specific AI environment may require stronger separation from personal Li OS.

---

## 79. Relationship Memory

Relationship memory may be highly personal.

Li should preserve relevant history while avoiding unnecessary intimate detail.

Amelia should receive only relevant relationship context.

---

## 80. Security Controls

Memory infrastructure should follow:

`system/security-policy.md`

Heimdall should review:

* database access;
* backup access;
* encryption;
* keys;
* network exposure;
* agent permissions;
* audit logs;
* third-party services.

---

## 81. Database Access

The production database should not be publicly accessible without appropriate authentication and network controls.

Applications should use dedicated scoped database credentials where possible.

---

## 82. Human Database Access

Direct human access to production memory should be limited.

Administrative access should be auditable where practical.

---

## 83. AI Database Access

Agents should preferably interact through a controlled Memory API rather than receiving unrestricted raw database access.

Preferred:

```text
Li
 ↓
Memory API
 ↓
Permission check
 ↓
Database
```

Not:

```text
Every agent
 ↓
Full database administrator access
```

---

## 84. Memory API

The future Memory API should support capabilities such as:

```text
recall_memory
search_memory
store_memory
propose_memory
correct_memory
get_person
get_goal
get_commitments
get_open_loops
get_timeline
get_memory_source
```

Actual implementation names may change.

---

## 85. Write Validation

Memory writes should be validated against:

* schema;
* user namespace;
* permissions;
* sensitivity;
* required provenance;
* duplication rules.

Malformed or unauthorized writes should fail safely.

---

## 86. Idempotency

Where possible, repeated processing of the same event should not create duplicate memories.

Example:

Reading the same travel confirmation twice should not create two identical trips.

---

## 87. Observability

Memory infrastructure should provide operational visibility.

Monitor:

* API failures;
* database errors;
* backup failures;
* abnormal write volume;
* retrieval latency;
* migration failures;
* unauthorized access attempts.

---

## 88. Memory Availability

Li should degrade gracefully if memory is temporarily unavailable.

Li should not invent remembered information.

She should say that personal memory could not currently be retrieved where that limitation matters.

---

## 89. Memory Failure

If memory infrastructure fails:

```text
Stop risky writes
     ↓
Protect existing data
     ↓
Check backups
     ↓
Restore service
     ↓
Verify integrity
     ↓
Resume writes
```

---

## 90. Corruption Detection

Possible corruption indicators include:

* large unexplained deletion;
* invalid encoding;
* missing relationships;
* unexpected permission changes;
* drastic record-count changes;
* repeated duplicate creation.

Theo and Heimdall should investigate.

---

## 91. No Silent Data Loss

If Li OS discovers meaningful memory loss, Christoffer should be informed.

Do not quietly continue as if nothing happened.

---

## 92. Development vs Production

Development environments should not automatically contain copies of real sensitive personal memory.

Prefer:

* synthetic test data;
* anonymized data;
* minimal test records.

Production data should only be copied when genuinely necessary and securely controlled.

---

## 93. Test User

Li OS may eventually have fictional test profiles for development.

Example:

```text
users/test-user/
```

Testing should not require exposing Christoffer's actual private memory.

---

## 94. Memory Evaluation

Li OS should test whether memory improves responses.

Evaluations should include:

* correct retrieval;
* avoiding irrelevant memory;
* temporal understanding;
* contradiction handling;
* privacy boundaries;
* inference handling;
* specialist disclosure limits;
* correction behavior.

---

## 95. Over-Memory Evaluation

Li should also be tested for remembering too much.

Examples:

* bringing up irrelevant private facts;
* unnecessarily reminding Christoffer of old events;
* over-personalizing simple questions;
* using unrelated sensitive context.

Knowing something does not mean it should always be mentioned.

---

## 96. Personalization Without Surveillance

The goal of memory is:

> Understand Christoffer better.

It is not:

> Record every observable detail about Christoffer.

Memory should remain selective and purposeful.

---

## 97. Future Memory Intelligence

Future improvements may include:

* temporal knowledge graphs;
* better semantic retrieval;
* automatic contradiction detection;
* relationship-aware retrieval;
* event linking;
* confidence calibration;
* memory decay;
* preference-strength estimation;
* personalized outcome learning.

These should be evaluated by Ada and Theo.

---

## 98. Migration to Better Memory Technology

If substantially better memory technology appears:

```text
Ada evaluates capability
       ↓
Theo evaluates memory quality
       ↓
Heimdall evaluates security
       ↓
Migration test
       ↓
Full backup
       ↓
Validation
       ↓
Christoffer approval if material
       ↓
Migration
```

---

## 99. Recovery Package

Li OS should eventually be capable of producing a secure recovery package containing:

```text
Li OS configuration version
Memory schema version
Encrypted memory export
Encrypted document index
Permissions
Agent versions
Backup verification metadata
Restoration instructions
```

Secret decryption material must remain separately protected.

---

## 100. Final Storage Principle

Li OS should always preserve the separation:

> **GitHub defines Li.**

> **The canonical memory store remembers Christoffer.**

> **The semantic index helps Li find what matters.**

> **Secure document storage preserves source material.**

> **The secrets manager protects credentials.**

> **Encrypted backups make the system recoverable.**

And above all:

> **No model, vendor, database provider, system update, or infrastructure migration should be able to erase Christoffer's accumulated relationship and history with Li simply because the technology underneath her changed.**
