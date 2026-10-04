# Work, meeting transcripts and ElevenLabs audio

**Status:** Proposed architecture; owner-requested scope, not implemented or activated.
**Date:** 2026-10-04.
**Decider:** Christoffer; material privacy, retention and external activation decisions remain gated.

## Context and authority

The owner requests a Work menu containing notes/to-dos and meetings, recording for both in-person
and online meetings, speaker-separated transcripts, summaries and follow-ups available to Li.
After transcription completes, ask whether to delete the recording. Renaming Person 1 should
update that person's labels throughout the meeting. The preferred audio provider is ElevenLabs:
Eleven v4 Turbo for Li's speech, and speech-to-text with speaker separation for meetings.

This proposal is subordinate to the [Constitution](../CONSTITUTION.md),
[architecture](../ARCHITECTURE.md), [security policy](security-policy.md),
[storage policy](../memory/storage-policy.md), [permissions](../memory/permissions.yaml) and
[update policy](update-policy.md). It does not expand specialist access, approve cloud resources,
change retention policy, or close KR-011. The [voice foundation](../VOICE_ARCHITECTURE.md) remains
the implemented contract. OM-003's [entry gate](../docs/REALTIME_VOICE_PLAN.md#placement-in-package-6)
still governs enhanced Li voice implementation. Work planning is not evidence that this gate passed.

## Proposed decision

Build Work as a separate operational workspace, with three subordinate views: **Overview**,
**Notes & tasks**, and **Meetings**. Keep typed Work records independent of audio activation.
Use a replaceable server-side batch transcription adapter for recorded meetings. Preserve Li's
existing reasoning and governed-action path; do not introduce a second ElevenLabs reasoning agent.

Use meeting-local speaker IDs, not permanent voice identities. Names are editable annotations,
not facts inferred from voice alone. Store transcripts and summaries as private Work artifacts,
not automatically as canonical personal memory. Proposed tasks require review before becoming
active commitments. Calendar events, outbound messages and specialist sharing retain their own
governed confirmation boundaries.

### Options and tradeoffs

| Option | Assessment |
| --- | --- |
| Batch meeting STT plus existing Li reasoning; separate TTS adapter | Preferred: fits editable transcripts and existing authority boundaries. Medium integration complexity; transcript appears after recording rather than being guaranteed live. STT, summary reasoning and storage each need cost coverage. |
| Real-time meeting agent with autonomous actions | Not selected: adds streaming/session complexity and a second action surface. Low-latency captions are not necessary for the first meeting workflow. |
| Browser recognition only | Keep the existing chat fallback; insufficient evidence for reliable long-meeting diarization. Browser/vendor availability varies. |
| Permanent enrolled speaker library | Not selected: adds biometric enrollment, consent, deletion and cross-meeting linkage obligations beyond meeting-local labeling. |

Consequences: initial delivery is simpler and privacy scopes remain explicit, but server audio
storage/processing, transcription reconciliation and editable provenance require new reviewed
contracts. No guarantee of perfect recognition, speaker separation or capture from another app.
Revisit streaming or enrolled identities only through a separate requested design review.

## Layout and interaction

- Overview shows overdue/today/upcoming tasks, recent notes, and meetings needing review; counts
  come from real records. Empty and unavailable are different states.
- Notes & tasks supports a quick note, checkable tasks, optional due date, priority and status.
  A due date does not silently create a Calendar event or activate a notification schedule.
- Meetings lists date, title and processing state. Open a meeting into Summary, Transcript and
  Tasks sections, with recording state and retention choice clearly visible.
- Desktop can place transcript and summary side by side. Phone uses stacked sections with a
  reachable recording control and no horizontal overflow at 200% text size. State is not color-only.
- Transcript rows show speaker label, timestamp, text and uncertainty. Speaker editor previews
  affected segments before saving a meeting-wide rename. Text correction and speaker reassignment
  remain separate controls. Allow correcting one wrongly attributed segment without renaming others.
- Audio playback is available only while retained. Deleting it disables playback honestly while
  preserving the transcript unless the owner separately requests transcript deletion.
- English and Swedish controls, failures, confirmations and editing behavior must be equivalent.

## Capture and processing flow

```text
Explicit capture/upload + recording authority + retention choice
    -> private bounded audio artifact
    -> durable transcription job + reserved cost ceiling
    -> ElevenLabs STT (audio only; no Li memory/history)
    -> validated transcript + meeting-local speaker IDs
    -> durable transcript saved -> ask delete or keep recording
    -> authorized Li summary/task proposals with source references
    -> owner review -> governed task creation / permitted follow-up
```

In-person capture uses the chosen microphone after permission and a visible Start action. Stop
closes every media track. Denial, device change, interrupted capture and screen lock show accurate
states; do not silently resume recording or promise reliable background capture on Android.

Online capture must detect what the browser actually offers and show the selected source. A mic
alone may miss remote participants. Initially support recording-file import and, where supported
and explicitly selected, browser tab/system audio plus mic. Do not claim mobile capture of another
meeting app or install a meeting bot. Keep channels separate when available, with a tested mapping;
channel identity still is not proof of a person's name. Unsupported capture offers upload instead.

Before capture or upload, explain participant notice/permission, company restrictions, external
processing and retention. Owner permission to build this feature is not consent from all future
participants. Denied or unestablished recording/processing authority blocks that operation. Do not
automatically join calls, record in the background, capture video, or send invitations.

## Speaker and transcript semantics

- Assign stable opaque speaker IDs scoped to one meeting. Render Person 1 / Person 2 (Person 1 /
  Person 2 in Swedish where appropriate); unknown, overlap and unintelligible speech remain explicit.
- Provider diarization is an estimate. Two similar voices, crosstalk, noise and a person changing
  microphones can split or merge speakers incorrectly. Permit bounded owner merge/split/reassignment
  with version checks and provenance; never represent a guessed assignment as verified identity.
- A clear spoken self-introduction or supplied participant list may support a **suggested** name
  with a source timestamp. Mentioning someone is not evidence that they are speaking. Require owner
  confirmation before applying a suggested personal name; preserve rejected/unknown states.
- Store the confirmed display name in a speaker mapping and resolve it in transcript, summary
  attributions and task-source views. Do not use global string replacement in the spoken text.
- Editing transcript text increments its revision. Existing summaries/task proposals become stale
  and must not appear regenerated until an explicitly requested, cost-covered regeneration completes.
  Confirmed tasks are not silently rewritten by a transcript edit or new model response.
- No voiceprints, voice cloning, speaker-library enrollment, emotion inference, cross-meeting identity
  matching or authentication from voice in this design.

## Provider contract and evidence

First-party documentation reviewed on 2026-10-04, not a quality benchmark or activated integration:

- [Models](https://elevenlabs.io/docs/overview/models) identifies `eleven_v4_turbo` for speech
  generation and `scribe_v2` for batch transcription. The latter is the proposed meeting model;
  model ID, entitlement and Swedish/English quality must be reverified before live evaluation.
- [Create transcript](https://elevenlabs.io/docs/api-reference/speech-to-text/convert) documents
  `diarize`, word timestamps and optional speaker-library matching. Request diarization and word
  timestamps; leave speaker-library matching and optional paid enrichment off. Validate the chosen
  response schema and defaults against a pinned adapter contract before activation.
- [Zero retention](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode) is an
  Enterprise option. Do not claim the owner's existing plan has it, or assume `enable_logging=false`
  grants it. Establish actual retention, training-use controls, processing region, deletion behavior
  and terms for both STT and TTS before sending real information. If incompatible with the governing
  policy, keep real-audio processing disabled; do not buy an upgrade or relax policy automatically.

The owner reported privately saving the project key. This is not proof of endpoint authorization,
deployment, successful STT/TTS, long-term credit coverage or an installed runtime secret. Do not
inspect or reproduce the key. Credential installation remains a separately authorized operator step.

For Li speech, synthesize only the actual final Li response through a server-side adapter. Stream
audio of that finalized text if supported; do not stream speculative reasoning or introduce new
spoken claims. Bound the text sent to TTS, preserve EN/SV and cancellation, and leave text usable on
failure. A voice ID needs an owner listening choice; do not clone anyone or choose a paid voice
without verified coverage. TTS alone does not implement OM-003's continuous conversation controller.

## Proposed data and API boundaries

Names below describe contracts, not existing tables or deployed endpoints. Resolve final schema
against existing task/commitment and artifact contracts before writing a new immutable migration.

| Record | Minimum responsibility |
| --- | --- |
| Work note/task | Owner/workspace scope, classification, text, version, optional due time/timezone, status and source link. Reuse a compatible governed task contract rather than maintain duplicate tasks. |
| Meeting | Opaque ID, owner/workspace, title/timezone, recording authority record, classification, processing and retention states. |
| Recording artifact | Private object reference, bounded size/duration/media type, integrity metadata, deletion deadline and confirmed retention choice. Never a public object URL. |
| Transcription job | Meeting/artifact revision, operation ID, provider/model contract, dispatch/reconciliation state and reserved/observed usage metadata. No raw provider response in logs. |
| Transcript segment | Stable ID, start/end time, text, speaker ID, revision and source provenance. Treat all provider text as untrusted content. |
| Speaker annotation | Meeting-scoped speaker ID, display name, suggested/owner-confirmed status and source/correction metadata. |
| Summary/task proposal | Exact transcript revision and segment references, uncertainty, review status and governed applied-record ID where applicable. |

Browser requests go through the authenticated BFF to the private backend. No master key in JavaScript,
URLs, analytics or local storage. Backend verifies owner, Work scope and artifact binding on every
operation. Neither browser/BFF nor transcription adapter receives database write authority beyond
its approved capability. Reuse isolated storage/retention patterns, not shared credentials.

Proposed capabilities: bounded list/detail; create/edit note or task; create meeting; upload/finalize
recording; explicitly dispatch transcription; inspect job status; edit segment/speaker annotation;
request summary; review task proposals; retain/delete audio. Writes require stable operation IDs,
expected revisions and existing action confirmations where applicable. Pagination and minimal summary
fields avoid sending every transcript to Home. No arbitrary external audio URL fetching or automatic
provider dispatch on merely opening a meeting. No new scheduler is assumed.

## Privacy, storage and deletion

Work-confidential records stay in a separately scoped Work namespace, default private to Li. Li may
retrieve relevant approved Work context for a requested follow-up, not bulk inject all meetings into
every turn. Specialists receive only authorized minimum context through Li; derived summaries,
tasks, history and captures inherit classification and provenance. Explicit memory capture follows
Theo's existing proposal/confirmation rules and never silently turns transcript claims into facts.

Use private encrypted storage for audio and durable scoped storage for text/metadata. Do not put
recordings/transcripts in Git, public URLs, application logs, browser caches or general analytics.
Apply bounded media sniffing, duration/size checks, safe decoding and malformed-response rejection.
Reject executable/unsupported input; display transcript text without interpreting HTML or commands.

Recording retention is separate from transcript retention. Proposed UI asks **Delete recording** or
**Keep recording** once the transcript is durably stored, even if summarization later fails. Show
the exact consequence: deleting audio does not delete transcript, summary or reviewed tasks.
An unanswered prompt must not create indefinite retention. Before audio implementation, approve a
finite temporary retention deadline and Keep duration, disclosed before capture; expiration must be
explicitly covered by that choice. No implicit permanent retention and no guessed deadline here.

Deletion is an idempotent governed operation: hide playback immediately after acceptance, reconcile
private object deletion, then report actual outcome. Track provider copy/deletion separately from Li
storage. Never say "deleted everywhere" without proof; backup expiry follows storage policy. Do not
keep hidden audio versions in backups or derivative stores under a contrary retention claim. Review
existing lifecycle and backup coverage before creating any audio resources.

## Failure, replay and cost controls

Job states: prepared -> dispatched -> completed, failed-known, or outcome-uncertain. Persist dispatch
intent before the network call. Timeout, lost response or crash after dispatch may have consumed
credit; they must not trigger an automatic paid retry. Exact replay returns the saved state with no
second provider request. A restart cannot invent a new operation ID to evade the uncertain state.
Reconcile using approved bounded provider metadata if available; otherwise require an explicit
operator decision and new budget before any replacement attempt. Durable valid transcript publication
is atomic; a partial response is not a completed transcript.

Reserve a conservative maximum cost before dispatch, using verified endpoint pricing, duration/text
limits and current remaining allowance. Include STT, summary-model usage, storage, processing and TTS
separately; an ElevenLabs allowance does not cover Li's reasoning provider or cloud storage. Bound
concurrency to one meeting transcription initially; reserve across simultaneous devices and Li TTS.
An expiring key or stale balance disables dispatch safely. No auto top-up or bill-later fallback.

Before a metered test, record exact maximum duration/bytes, calls, output/text limits, concurrency,
cost ceiling and coverage freshness. These are activation prerequisites, not unbounded defaults.
One API-key credit cap is only defense in depth, not a substitute for shared-account and infrastructure
coverage. No live test is authorized by this proposal. Local fixtures must use fake providers.

Log fixed stage/category/status and bounded usage only. Exclude audio, transcripts, summaries, names,
prompts, raw error bodies, signed URLs and credentials. On logout stop capture/playback and fence late
callbacks. A lost client must not cause indefinite recording or hidden automatic submission.

## Delivery and acceptance

| Phase | Smallest deliverable | Required evidence |
| --- | --- | --- |
| W1 | Typed Work notes/tasks and meeting metadata, without audio/network provider activation | Reviewed scope/permissions and reuse decision; local synthetic persistence, EN/SV, keyboard/200% layout, owner isolation, stale-edit and replay tests. Separate migration/deployment approvals if needed. |
| W2 | Local transcript domain and fake STT adapter | Synthetic EN/SV multi-speaker segments; rename-all and single-segment correction; overlap/unknown states; prompt injection, provenance, private-to-Li and task-review boundaries; no live selector or key required. |
| W3 | Recording/import and retention controls | Approved retention deadlines, capture/consent UX, bounded storage and deletion reconciliation; local interruption/replay/logout tests. No real audio until provider handling and cost gates pass. |
| W4 | Bounded provider evaluation | Exact owner authorization and fresh coverage; permitted synthetic recordings, declared ground truth, source-attribution/error measurements in EN/SV, uncertain-effect and no-retry controls. |
| W5 | Authorized deployment and physical acceptance | Immutable candidate validation, migration compatibility and rollback/disable plan; actual phone/tablet/Windows capture behavior, owner transcript/summary review and stability evidence. |
| V | Enhanced Li voice under OM-003 | Existing entry gate, data/cost review, selected voice audition, final-response-only synthesis, interruption/authority tests, authorized deployment and measured owner/device acceptance. |

Quality review must separate transcription mistakes, diarization mistakes, name suggestions and
summary/task attribution mistakes. Test quiet two-speaker, noisy/crosstalk, mixed EN/SV, unfamiliar
names, unknown speakers and partial uploads. Evaluate who-said-what against known synthetic ground
truth; a successful HTTP response is not accuracy acceptance. Safety and privacy cases must all pass;
owner quality thresholds and a bounded sample set must be agreed before live evaluation, not chosen
after seeing results. Never claim physical acceptance from fake-provider tests.

Rollback disables new dispatch/capture while keeping authorized saved text readable where compatible.
Schema changes must be additive/rehearsed and separately approved; application rollback must not
erase recordings, recreate deleted audio, replay jobs or downgrade access controls. No migration,
cloud configuration, provider activation or runtime permission change is part of this design batch.

## Open decisions before affected implementation

1. Approve finite temporary audio expiry and retained-audio duration, including unanswered prompts.
2. Verify provider retention/training/region/deletion suitability for the intended Work classification.
3. Pin bounded capture/job sizes, cost reservation and reconciliation contract after local prototypes.
4. Choose Li's voice by a separately authorized, covered EN/SV audition once OM-003 is eligible.

These do not block local W1/W2 contracts and synthetic tests. Track completion in the existing
[personal-use checklist](../docs/PERSONAL_V1_ACCEPTANCE.md) and
[milestones](../docs/OPEN_MILESTONES.md), not a duplicate roadmap. All phases remain unimplemented
by this document; KR-011, OM-003 and owner/device/stability evidence remain open.
