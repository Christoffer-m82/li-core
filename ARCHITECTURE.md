# Li OS Architecture

**Version:** 0.1
**Status:** Foundational
**Purpose:** Define the technical and organizational architecture of Li OS.

---

## 1. System Objective

Li OS is Christoffer's personal AI operating system.

Its purpose is to provide one primary AI relationship — Li — supported by a network of specialist agents, tools, persistent memory, current professional knowledge, automations, and external services.

Christoffer should normally interact with Li rather than needing to choose which AI, model, agent, or tool to use.

The underlying system should remain modular, portable, secure, version-controlled, and capable of improving over time without losing Christoffer's accumulated personal information or system history.

---

## 2. High-Level Architecture

The system should follow this structure:

```text
                         CHRISTOFFER
                              │
                    Voice / Text / Phone
                              │
                              ▼
                    ┌─────────────────┐
                    │       LI        │
                    │ Personal AI Hub │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      PERSONAL            SPECIALIST          TOOLS &
       MEMORY               AGENTS          AUTOMATIONS
          │                  │                  │
          │          ┌───────┼────────┐         │
          │          │       │        │         │
          │        Sofia   Marco    Elena       │
          │        Amelia  Freja    Oliver      │
          │        James   Victor   Nora        │
          │        Milo    Iris     Clara       │
          │                                   │
          └─────────────────┬─────────────────┘
                            │
                            ▼
                     SYSTEM SERVICES
                            │
                   ┌────────┼────────┐
                   │        │        │
                  Theo     Ada    Heimdall
                 Memory  Evolution Security
```

Li is the center.

Specialist agents support Li.

System agents maintain Li OS itself.

---

## 3. Core Design Principle

Li is not Claude.

Claude is one possible intelligence provider used by Li OS.

Li's identity exists independently through:

* her constitution;
* her memory;
* her agent configuration;
* her history;
* her permissions;
* her tools;
* her relationships;
* her accumulated experience;
* and the architecture defined in GitHub.

This allows Li OS to change underlying AI technologies without losing continuity.

---

## 4. Primary User Interface

The initial primary interface should be Claude Mobile.

Christoffer should be able to communicate with Li through:

* voice;
* text;
* mobile;
* desktop;
* and eventually additional interfaces.

The preferred normal experience is:

```text
Christoffer
     │
     ▼
   "Li..."
     │
     ▼
     Li
```

Christoffer should not normally need to think about:

* which model to use;
* which agent to contact;
* which database to search;
* which tool to call;
* or which workflow to trigger.

Li handles routing.

---

## 5. Li Core

Li Core contains the enduring operating logic of Li.

It includes:

* Li's constitution;
* identity;
* personality;
* objectives;
* reasoning principles;
* delegation policy;
* memory rules;
* permissions;
* proactivity rules;
* specialist routing;
* action approval logic;
* communication style;
* and system-level behavior.

Li Core should remain version-controlled in GitHub.

Changes to Li Core should be deliberate and reviewable.

---

## 6. Agent Architecture

Li OS contains two broad categories of agents.

### 6.1 Life and Professional Specialist Agents

These agents advise Christoffer or Li within specialist domains.

Initial agent registry:

| Agent  | Role                                              |
| ------ | ------------------------------------------------- |
| Li     | Personal Chief of Staff & Life Orchestrator       |
| Sofia  | Health & Medical Adviser                          |
| Marco  | Fitness & Performance Coach                       |
| Elena  | Nutrition, Cooking, Food & Drink Expert           |
| Amelia | Relationships, Dating & Social Adviser            |
| Freja  | Parenting & Family Adviser                        |
| Oliver | Legal & Regulatory Adviser                        |
| James  | Finance & Wealth Adviser                          |
| Victor | Business, Commercial & CCO Adviser                |
| Nora   | Research, Intelligence & Decision Adviser         |
| Milo   | Travel, Leisure & Experiences Adviser             |
| Iris   | Home, Interior Design, Plants & Gardening Adviser |
| Clara  | Wellbeing, Habits & Mental Performance Adviser    |

### 6.2 System Agents

These agents maintain Li OS itself.

| Agent    | Role                                    |
| -------- | --------------------------------------- |
| Ada      | AI Architect & System Evolution Manager |
| Theo     | Personal Memory & Knowledge Curator     |
| Heimdall | Security & Privacy Guardian             |

System agents normally operate behind Li.

Christoffer may communicate with any agent directly if desired.

---

## 7. Agent Definition

Every permanent agent should have its own configuration.

Each agent should define:

```text
Name
Role
Purpose
Areas of expertise
Areas outside expertise
Personality
Professional standards
Knowledge sources
Tools
Memory access
Write permissions
Delegation permissions
Update frequency
Evaluation tests
Escalation rules
Human-professional boundaries
Version
```

Each agent should be independently updateable and version-controlled.

---

## 8. Agent Registry

Li should have access to a central registry describing every available agent.

The registry should allow Li to determine:

* what each agent knows;
* what each agent is responsible for;
* what tools each agent has;
* what information each agent may access;
* when the agent should be consulted;
* and when it should not be consulted.

Li should be able to discover new agents through the registry without requiring changes to her core identity.

---

## 9. Agent Delegation

Li determines whether a request should be:

* answered directly;
* delegated to one specialist;
* delegated to multiple specialists;
* researched externally;
* handled with tools;
* or escalated to a human professional.

Example:

```text
Christoffer:
"My shoulder hurts. Should I train tonight?"

             Li
              │
       ┌──────┴──────┐
       ▼             ▼
     Sofia         Marco
     Health         Fitness
       │             │
       └──────┬──────┘
              ▼
             Li
              │
              ▼
     Synthesized answer
```

The specialists should return their analysis to Li.

Li then produces the final response.

---

## 10. Parallel Agent Work

Li should be capable of consulting multiple agents simultaneously.

Example:

```text
Christoffer:
"Help me evaluate this business agreement."

                    Li
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Victor       Oliver       Nora
    Commercial      Legal      Research
        │            │            │
        └────────────┼────────────┘
                     ▼
                    Li
                     │
              Final synthesis
```

For significant decisions, Li should preserve specialist disagreement rather than forcing consensus.

---

## 11. Personal Memory Architecture

Personal memory must remain independent from the AI model.

The canonical personal memory system should contain structured information about Christoffer's life.

Primary domains:

```text
Identity
People
Family
Relationships
Preferences
Goals
Values
Health
Fitness
Nutrition
Work
Finance
Legal
Travel
Home
Interests
Experiences
Important dates
Commitments
Decisions
Timeline
Documents
Lessons learned
Open loops
```

Memory should be queryable by Li and authorized agents.

---

## 12. Memory Types

The system should distinguish at least four categories.

### Explicit Memory

Information Christoffer directly provided.

### Observed Memory

Information supported by repeated behavior or recorded outcomes.

### Inferred Memory

A hypothesis made by the system.

Inferred memories should retain lower confidence until confirmed.

### Historical Memory

Information that was previously true but may no longer reflect Christoffer's present situation.

The system should preserve useful history rather than simply overwriting it.

---

## 13. Memory Metadata

Important memory records should support metadata such as:

```text
value
category
source
created_at
last_confirmed
confidence
sensitivity
status
access_permissions
agent_visibility
historical_versions
```

Example:

```text
Preference:
Prefers smaller boutique hotels.

Source:
Observed across several travel decisions.

Confidence:
0.82

Status:
Likely

Visible to:
Li
Milo

Sensitive:
No
```

---

## 14. Theo — Memory Curator

Theo is responsible for memory quality.

Theo should:

* identify information worth remembering;
* structure memories;
* avoid unnecessary duplication;
* preserve provenance;
* distinguish fact from inference;
* identify contradictions;
* maintain timelines;
* archive outdated information;
* protect continuity;
* and improve memory retrieval.

Theo should never blindly convert every conversation into permanent memory.

---

## 15. Memory Preservation

System upgrades must never intentionally erase personal memory.

The system should separate:

```text
SYSTEM VERSION
Li v4.2

from

MEMORY STATE
Christoffer's accumulated life knowledge
```

Rolling back an agent update should not automatically roll back newer personal memories.

Software changes and life history must remain separate.

---

## 16. Professional Knowledge

Each specialist agent should maintain its own domain knowledge independently from Christoffer's personal memory.

Examples:

Sofia:

* medicine;
* clinical guidelines;
* research;
* preventive health.

Oliver:

* Malta law;
* UK law;
* family law;
* company law;
* iGaming regulation.

Victor:

* commercial strategy;
* iGaming;
* sales;
* leadership;
* negotiation;
* market developments.

Professional knowledge should be updateable without altering personal memory.

---

## 17. Live Information

Some information should not be stored as permanent knowledge because it changes quickly.

Examples:

* restaurant availability;
* flight prices;
* weather;
* news;
* event availability;
* opening hours;
* hotel prices;
* current regulations;
* market developments.

This information should normally be retrieved when needed.

---

## 18. Experience Layer

Li OS should accumulate lessons from previous outcomes.

Examples:

```text
Milo recommended hotel X.
Christoffer loved it.
→ positive preference signal

Elena proposed recipe Y.
Christoffer found it too complicated.
→ reduce weekday recipe complexity

Li suggested approach Z in a negotiation.
Outcome was positive.
→ experience signal
```

Experience should improve personalization.

Experience should not be mistaken for universal truth.

---

## 19. Knowledge Update Engine

Every agent should have an update policy suited to its field.

Examples:

### Sofia

Medical research and guideline monitoring.

### Marco

Sports science and training evidence.

### Elena

Nutrition science and culinary knowledge.

### Oliver

Legal and regulatory monitoring.

### Victor

Business and iGaming developments.

### Milo

Current travel, restaurants, experiences, and events.

### Ada

AI models, tools, architecture, MCP, automation, and technology.

The system should evaluate information quality before incorporating it.

---

## 20. Update Commands

Li OS should support at least three update concepts.

### Check System Updates

```text
"Li, check for system updates."
```

Reviews:

* AI models;
* tools;
* integrations;
* infrastructure;
* security;
* architecture.

No automatic consequential changes.

### Refresh Knowledge

```text
"Li, refresh everyone's knowledge."
```

Updates professional and world knowledge according to each agent's domain.

### Full Update

```text
"Li, update everything."
```

Triggers:

* system review;
* agent knowledge review;
* professional developments;
* AI technology review;
* tool review;
* security review;
* agent-performance review;
* memory integrity check;
* experience review;
* and missing-agent review.

---

## 21. Ada — System Evolution

Ada is responsible for evolving Li OS.

Ada should:

* monitor AI developments;
* monitor relevant tools;
* evaluate new models;
* evaluate new integrations;
* improve agent architecture;
* propose agent updates;
* maintain evaluation benchmarks;
* identify outdated components;
* propose new agents;
* and maintain technical documentation.

Ada should propose important changes rather than silently applying them.

---

## 22. Heimdall — Security and Privacy

Heimdall protects Li OS.

Responsibilities include:

* access control;
* permission monitoring;
* secret management;
* privacy;
* prompt-injection defenses;
* suspicious activity detection;
* backup verification;
* authentication;
* security reviews;
* agent permission audits;
* and information-sharing boundaries.

Heimdall should operate independently enough to challenge Ada or Li when a proposed convenience creates unacceptable security risk.

---

## 23. Permission Architecture

Actions should follow four broad levels.

### Level 0 — Think

Examples:

* research;
* reasoning;
* planning;
* agent consultation;
* memory retrieval.

Generally automatic.

### Level 1 — Read

Examples:

* calendar;
* email;
* documents;
* reservations;
* contacts.

Generally allowed once access is authorized.

### Level 2 — Reversible Action

Examples:

* draft email;
* create reminder;
* create tentative calendar event;
* organize files.

Can eventually be automated according to user preference.

### Level 3 — Consequential Action

Examples:

* purchases;
* travel bookings;
* important messages;
* cancellations;
* financial actions;
* legal submissions;
* sensitive disclosures.

Normally requires explicit approval.

---

## 24. Tools and Integrations

Li OS should expose external capabilities through modular integrations.

Initial priorities:

```text
Calendar
Email
Contacts
Tasks / Reminders
Web Search
Maps
Files / Documents
Notifications
```

Later:

```text
Travel
Restaurants
Ticketing
Finance
Wearables
Health data
Smart home
Work systems
Entertainment
Additional communication services
```

Whenever practical, integrations should use open or portable interfaces.

MCP should be preferred where appropriate.

---

## 25. Li OS Backend

A private cloud backend should provide functionality such as:

```text
recall_memory()
store_memory()
search_people()
get_goals()

consult_agent()
consult_agents_parallel()
get_agent_registry()

create_task()
get_tasks()

request_action()
approve_action()

check_updates()
refresh_agent_knowledge()

get_system_status()
```

The mobile AI interface should not contain all Li OS logic itself.

The backend should remain independently deployable.

---

## 26. GitHub Architecture

GitHub is the primary source of truth for Li OS configuration and source code.

Initial repository:

```text
li-core
```

Future repositories may include:

```text
li-agents
li-memory
li-integrations
li-infrastructure
li-evaluations
li-docs
```

The exact repository structure may evolve as the project grows.

---

## 27. What Belongs in GitHub

GitHub may contain:

* source code;
* constitution;
* architecture;
* agent definitions;
* prompts;
* schemas;
* policies;
* tests;
* workflows;
* infrastructure definitions;
* documentation;
* changelogs;
* encrypted backups;
* deployment configuration without secrets.

---

## 28. What Must Not Be Stored Readably in GitHub

The following must never be committed in readable form:

* passwords;
* API keys;
* authentication tokens;
* encryption keys;
* private keys;
* health records;
* highly sensitive personal records;
* private legal documents;
* financial records;
* confidential third-party information;
* private relationship records;
* or other high-sensitivity personal information.

Sensitive material may be backed up to GitHub only if appropriately encrypted before upload.

Encryption keys should not be stored beside the encrypted data.

---

## 29. Version Control

Important Li OS changes should use Git.

A typical change should follow:

```text
Proposed change
      ↓
Git branch
      ↓
Implementation
      ↓
Automated tests
      ↓
Security checks
      ↓
Pull request
      ↓
Review
      ↓
Approval
      ↓
Merge
      ↓
Deployment
```

Major releases should receive version tags.

Example:

```text
Li-OS-v1.0
Li-OS-v1.1
Li-OS-v2.0
```

---

## 30. Evaluation Architecture

Every important agent should have tests.

Tests should evaluate:

* factual accuracy;
* domain competence;
* memory retrieval;
* delegation;
* privacy;
* security;
* personality consistency;
* uncertainty handling;
* refusal behavior;
* challenge behavior;
* tool selection;
* and outcome quality.

Li should additionally have personality-regression tests.

The system should test whether Li still behaves like Li after model or prompt changes.

---

## 31. Rollback

Agent and system changes should be reversible where practical.

Example:

```text
Li v4.7
   ↓
Regression detected
   ↓
Rollback
   ↓
Li v4.6
```

Personal memories accumulated during v4.7 should normally remain.

Rollback applies to system configuration, not to Christoffer's life history.

---

## 32. Proactive System

Li OS should eventually operate both reactively and proactively.

Reactive:

```text
Christoffer asks
        ↓
Li responds
```

Proactive:

```text
Li OS detects something meaningful
        ↓
Evaluates importance
        ↓
Li decides whether interruption is justified
        ↓
Christoffer is informed
```

Examples:

* forgotten commitment;
* upcoming travel preparation;
* important family date;
* meaningful professional development;
* health trend;
* unanswered important message;
* opportunity;
* risk;
* useful social suggestion.

---

## 33. Agent Creation Process

New permanent agents should follow a controlled process.

```text
Need identified
      ↓
Li analyzes gap
      ↓
Ada designs agent proposal
      ↓
Heimdall reviews permissions
      ↓
Christoffer approves
      ↓
Agent created
      ↓
Tests run
      ↓
Agent added to registry
```

Agents should not multiply unnecessarily.

---

## 34. Human Professionals

Li OS should improve access to human expertise rather than pretend to replace it in high-stakes situations.

Agents such as Sofia, Oliver, and James should be able to help:

* analyze;
* research;
* organize information;
* identify questions;
* prepare documents;
* explain professional advice;
* and help Christoffer prepare for meetings.

When qualified human involvement is appropriate, the agents should say so clearly.

---

## 35. Separation of Personal and Company Data

Personal Li OS information and confidential company information should remain appropriately separated.

Li may understand Christoffer's professional role and goals.

However, company-confidential information should have its own access controls, storage, and authorization.

Specialist agents should not automatically gain access to confidential work information simply because they exist inside Li OS.

---

## 36. Backup and Recovery

Li OS must be designed so that it can be restored if a provider becomes unavailable.

The recovery plan should preserve:

* Li's constitution;
* agent definitions;
* memory;
* system configuration;
* documents;
* permissions;
* update history;
* infrastructure definitions;
* and evaluation tests.

The goal is:

```text
AI provider changes?
Li survives.

Database provider changes?
Li survives.

Automation provider changes?
Li survives.

Hosting provider changes?
Li survives.
```

---

## 37. Long-Term Architecture Principle

Li OS should optimize for continuity rather than dependence on any single technology.

Over time:

* models will change;
* tools will change;
* interfaces will change;
* databases may change;
* agent technologies will change;
* voice systems will improve.

What should remain is:

```text
Li
Christoffer's memory
Agent identities
Accumulated experience
Permissions
History
Values
Constitution
System ownership
```

---

## 38. End-State Experience

The desired experience is:

Christoffer communicates primarily with Li.

Li understands Christoffer deeply.

Li remembers important information across years.

Li knows when to listen, when to advise, when to challenge, and when to act.

Li can behave as:

* Chief of Staff;
* personal assistant;
* adviser;
* organizer;
* thinking partner;
* companion;
* and friend-like presence when needed.

Li automatically determines when specialist expertise is required.

Specialists can work independently or in parallel.

Li synthesises their conclusions.

Agents remain professionally current.

The system learns from experience.

Personal memory survives every system update.

Ada continually improves the system.

Theo maintains memory quality.

Heimdall protects privacy and security.

Christoffer retains authority.

The entire system remains owned, version-controlled, recoverable, and portable through the Li OS architecture.

The final experience should feel less like managing a collection of AI tools and more like having one trusted personal AI — Li — supported by an invisible organisation of specialists working on Christoffer's behalf.
