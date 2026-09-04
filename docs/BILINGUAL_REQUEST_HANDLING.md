# English and Swedish request handling

## Implemented scope

Li should choose the same runtime path for equivalent English and Swedish requests.
The owner requested this correction on 2026-09-04 after local tests exposed English-only
trigger phrases. The [shared alias vocabulary](../backend/app/request_language.py) maps
reviewed Swedish words and common inflections onto existing English trigger concepts.
Matching uses Unicode normalisation and word boundaries, without translating or rewriting
messages sent to models, saved as conversation history, or used for memory lookup.

This change is distinct from [Li's conversational voice](../li/identity.md) and its
[bilingual quality evaluation](LI_CONVERSATION_EVALUATION.md). Neither local code nor tests
establish the state of a deployed service.

| Area | Implemented equivalence | Boundary preserved |
| --- | --- | --- |
| Named specialists | Ask/consult and be/fråga/rådfråga; English/Swedish possessive requests; all 12 specialists | Existing registry only; maximum three specialists; no new permissions |
| Domain routing | Training/träning, recipe/recept, and reviewed aliases across every specialist | Simple questions can stay with Li; original messages remain intact |
| Multi-specialist selection | Decision/comparison words in both languages | Translation word count no longer changes the number of specialists |
| Current evidence | Reviewed aliases for every current-information and high-stakes policy trigger | Same evidence ages, source classes, minimum source counts and failure behaviour |
| Provider selection | Swedish market-quote terms and names for already supported jurisdictions | Unconfigured quote providers and unsupported jurisdictions still fail closed |
| Personal context | My/me and min/mitt/mina/mig; Swedish query words retain å/ä/ö | Same retrieval limits and private-to-Li specialist exclusions |
| History recall | Do you remember/minns du/kommer du ihåg and other reviewed recall phrases | Six-result bounded lookup; historical text remains untrusted, not canonical memory |
| Memory changes | Glöm det and contextual Swedish corrections receive the existing guards | No guessing a missing target; sensitive targets retain existing protection |
| Place relevance | Reviewed Swedish local/weather/law/travel phrases | Country/town minimisation and existing place consent/storage rules unchanged |
| Text artifacts | Create a text file/skapa en textfil | Existing file-generation/retention path; not permission for arbitrary filesystem writes |
| Action proposals | Runtime and memory-classifier instructions explicitly cover EN/SV requests | Same typed action identifiers and confirmation flow; chat yes/ja is not execution approval |

Freshness policy and provider coverage versions are 1.1; their schema versions remain 1.0.
No provider, dependency, schema, migration, cloud resource or secret is added or changed.
Original English paths also now use whole-word domain matching to avoid incidental
substrings; long requests without decision language no longer gain extra specialists
solely by crossing an 18-word threshold. Explicit multi-specialist requests remain supported.

## Regression checks

From `backend`, using the existing development environment:

```text
python -m pytest tests/test_bilingual_requests.py tests/test_li_conversation_voice.py tests/test_specialist_runtime.py tests/test_freshness_policy.py tests/test_provider_coverage.py tests/test_memory_capture.py tests/test_conversation_history.py tests/test_action_intents.py -q
python -m ruff check app tests
python -m pytest -q
python -m compileall -q app
```

[Paired request tests](../backend/tests/test_bilingual_requests.py) check the same routing
outcome, actual evidence/source/age requirements, provider decisions, memory/context gates,
and language-independent approval schema. They exercise every registered freshness alias,
all specialist names, representative natural requests and negative substring cases.
Endpoint tests use fake storage/providers to verify the history trigger receives the
original text and Swedish ambiguous forgetting reaches the same blocked outcome.
[Synthesis tests](../backend/tests/test_li_conversation_voice.py) cover both languages
through the real router, including the independent-answer fallback.

No test applies migrations, accesses production memories, calls live providers or executes
real external actions. Follow [Testing and audit](TESTING_AND_AUDIT.md) for broader checks.

## Limits and acceptance

This is a bounded lexical implementation, not a proof of semantic equivalence for every
possible translation. The reviewed aliases cover common Swedish forms, not all compounds,
dialects, misspellings, indirect requests, quoted requests or negations. Language homographs
can still be ambiguous. Add a paired regression whenever an unsupported phrasing is found;
avoid global string replacement or loosely matching fragments inside unrelated words.

Model-generated action proposals and memory classifications still need provider-backed
bilingual acceptance testing. Passing a fake provider response through the runtime does
not establish that the live model interprets every request equally.

Memory/history search still uses the original request. Recognising a Swedish recall request
does not guarantee it retrieves an English-only stored record; cross-language semantic
retrieval is not implemented here. Research evidence validation also remains strict and
does not gain a translation-based bypass. A Swedish query with English-only evidence may
need better source retrieval rather than relaxing verification.

Jurisdiction coverage is not expanded: an unsupported country fails the same way regardless
of the language used to name it. Automated proactivity rules use structured events; this
update does not create or schedule routines merely because a chat mentions them.

Before release, run the authorised synthetic EN/SV acceptance cases against the configured
model, review the diff, and follow the existing [deployment workflow](DEPLOYMENT_WORKFLOW.md).
Deployment requires separate explicit authorisation. Rollback is a reviewed application
revert or prior approved backend revision; never revert or delete personal memory for this.
