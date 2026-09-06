# Li real-time voice conversation plan

**Status:** Planned milestone only; no implementation, provider selection, activation or deployment.
**Requested:** 2026-09-06 by Christoffer.
**Milestone:** OM-003 in [Open milestones](OPEN_MILESTONES.md).
**Scope owner:** Christoffer; technical choices remain provisional until evaluation.

## Intended experience

Li should offer a human-sounding, expressive voice and natural back-and-forth conversation on
the owner's phone and tablet. Start with the existing Android phone/tablet installable web app,
with Windows as a regression target. Native Android/iOS integration is a later delivery stage,
tracked separately; this plan does not claim a native app already exists as a finished product.

The desired interaction is an explicit **Talk with Li** session: tap to begin, talk without pressing
a button for each turn, interrupt or correct Li while she speaks, and end the session explicitly.
Li should respect thinking pauses, distinguish brief acknowledgements from requests to stop, and
continue coherently after an interruption. Her delivery should feel warm and natural in both
Swedish and English, including language changes during a conversation.

Natural expression does not mean claiming human identity, feelings, background activity, or
knowledge of the owner's emotions. Preserve the [Constitution](../CONSTITUTION.md) and existing
[English and Swedish conversation guidance](LI_CONVERSATION_EVALUATION.md).

## Verified baseline and scope difference

The [Voice Interaction Foundation](../VOICE_ARCHITECTURE.md) remains the description of implemented
behavior. Its browser adapters provide single-turn recognition and read the completed Li response
through platform speech synthesis. Final transcripts enter the normal authenticated chat path.
The browser code does not configure a server audio provider or implement a continuous real-time
conversation session. Repository inspection establishes this baseline, not live device readiness.

This milestone adds two distinct requirements: a better speaking voice and a conversation controller
for timing, streaming, interruption and recovery. Replacing text-to-speech alone does not satisfy it.

## Placement in package 6

OM-003 is a late dependency-gated stream in **Package 6 — Personal-use completion**, not the next task
merely because it was requested or documented. The authoritative execution placement and entry gate
are in the [improvement blueprint](LI_OS_IMPROVEMENT_BLUEPRINT.md#om-003-dependency-placement), while
the [personal-use checklist](PERSONAL_V1_ACCEPTANCE.md#package-6-dependency-sequence) records current
completion evidence.

The repository already has merged and locally verified response-safety, context/privacy, bilingual
intent, tactile approval and recoverable-turn foundations. Migrations 037–039 and the earlier
application release also have separate staging evidence. These facts satisfy foundation work already
proved at those layers; they do not establish current live or device stability for the complete entry
gate.

Before voice implementation becomes eligible, the relevant current-release chat/history,
memory/privacy, bilingual response/routing, action-approval and recoverable-turn paths must pass their
applicable automated and staged checks with rollback available and no blocking security or data-
integrity finding. Outstanding evidence is tracked in the personal-use checklist, including the
latest applicable staging rollout and smoke checks, migration 040 and its memory journey where
included, device checks, and stable-use observation.

Once eligible, retain this order: **provider/voice evaluation and cost-coverage verification →
architecture decision → implementation → authorized staged deployment → Android phone/tablet and
owner acceptance, with Windows regression coverage**. Final release sign-off that includes enhanced
voice follows that acceptance. Optional visual improvements, profile photos, activation of every
proactive rhythm, and standalone native-app completion are not prerequisites for installable-web
voice. If a voice-specific gate is blocked, continue unrelated eligible package 6 work.

## User-facing requirements

| Area | Planned behavior |
| --- | --- |
| Voice character | Audition a consistent Li voice in Swedish and English; tune pace, emphasis and warmth without excessive theatrical effects or repetitive acknowledgements. |
| Turn timing | Use speech and meaning cues to wait through unfinished thoughts; respond promptly when the owner finishes. |
| Interruption | Keep listening during playback; a deliberate correction stops audible output and cancels queued speech. A small acknowledgement should not always end Li's turn. |
| Continuity | Track what was played, not just what was generated. Keep unheard speech distinct from heard conversation after cancellation. |
| Spoken responses | Prefer manageable conversational turns. Consult Li's existing capabilities when needed and describe delays truthfully. |
| Controls | Visible listening/speaking/thinking states, microphone mute, stop-speaking and end-session controls; preserve text and existing approval cards. |
| Audio environment | Test built-in microphones, speakerphone, wired/Bluetooth headsets, background speech and echo. |
| Recovery | Handle permission denial, disconnect, session expiry and provider failure without silently resubmitting actions or continuing microphone capture after ending. |
| Device continuity | Reuse the authorized conversation/history across devices; no automatic transfer of a live microphone session. |
| Background behavior | Define and test screen-lock and app-switch behavior per platform. If unsupported, show a clear paused/ended state; do not promise always-on listening. |

## Architecture options and provisional recommendation

| Option | Fit for Li | Tradeoff to evaluate |
| --- | --- | --- |
| Streaming recognition → existing Li reasoning → streaming speech generation | Keeps the current orchestration path and strong control of response text. A conversation framework can coordinate timing and interruption. | Each stage adds potential delay; transcripts alone lose some vocal expression. The present final-response contract would need an explicit streaming design. |
| Native speech-to-speech interface → bounded Li backend capabilities | Candidate for the most fluid exchange; immediate spoken interaction can coexist with slower memory/specialist work. | The interface itself reasons. Define precisely which replies it can originate and how it stays consistent with Li's identity, history and backend results. |

Provisional recommendation: compare an OpenAI Realtime conversation prototype with an ElevenLabs
Conversational prototype, using Gemini Live as the multilingual comparison. Cartesia is an alternate
speech generator for the pipeline option; Hume is an optional expression-focused comparison if its
language support meets the target. This is an evaluation order, not a purchase or final vendor decision.

A possible transport is WebRTC for browser/mobile audio, with LiveKit as an optional session and
turn-handling framework. Assess the additional hosting, dependency and cost requirements before
adopting a framework. It does not replace Li's reasoning or authorization rules.

The selected design must resolve an existing constraint: the current foundation speaks only the
final response returned by Li and creates no second orchestration path. A speech-to-speech interface
that originates responses changes that contract. Record and review that decision in the authoritative
voice architecture before implementing it; this plan does not silently supersede the constraint.

## Provider research snapshot

The following first-party material was reviewed on 2026-09-06. Claims describe documented capabilities,
not an independent listening benchmark. Recheck models, availability, language support, API contracts,
data handling and pricing before implementation; avoid treating a model name as a permanent default.

| Candidate | Reason to evaluate | Limitation or verification needed |
| --- | --- | --- |
| [OpenAI Realtime](https://developers.openai.com/api/docs/guides/realtime) | Integrated live audio, reasoning and tools; browser/mobile transport support. | Evaluate actual end-to-end delay and controlled integration with Li's existing reasoning and history. |
| [ElevenLabs expressive mode](https://elevenlabs.io/docs/eleven-agents/customization/voice/expressive-mode) | Eleven v3 Conversational offers context-sensitive delivery and a turn-taking system. | Audition the live conversational model in both languages. Documentation warns that Professional Voice Clone characteristics are not reliably preserved by this model. |
| [Gemini Live](https://ai.google.dev/gemini-api/docs/live-api/capabilities) | Native audio, interruption and multilingual conversation including Swedish. | Features differ by version: documented affective-dialogue and proactive-audio settings are not supported in Gemini 3.1 Flash Live. Do not combine all versions' features into one claim. |
| [Cartesia Sonic](https://www.cartesia.ai/sonic) | Streaming speech generation with expressive delivery. | Requires a separate listening/reasoning/turn-handling design for the full experience. |
| [Hume EVI](https://dev.hume.ai/docs/speech-to-speech-evi/overview) | Expression-aware voice interaction, interruption and configurable model integration. | Swedish is absent from the currently documented EVI 3/EVI 4-mini language lists; not a default bilingual choice. Vocal expression is an uncertain signal, not proof of an emotional state. |
| [LiveKit turn handling](https://docs.livekit.io/agents/logic/turns/) | Meaning-aware turn detection, interruption handling and playback/history coordination. | Framework behavior and language coverage require device testing; this is not a voice or reasoning model. |

## Li integration, privacy and cost boundaries

Follow [Security boundaries](SECURITY_BOUNDARIES.md), the
[Memory Storage Policy](../memory/storage-policy.md), and the
[no-spending requirement](../AGENTS.md#no-spending-requirement).

- Li remains the authority for canonical memory, specialist orchestration and governed actions.
  A voice provider receives only the bounded context needed for the authorized session; it gains
  no direct database, Theo, owner-confirmation, artifact-storage or specialist-provider credentials.
- Backend and provider master credentials remain server-side. Any proposed short-lived client
  media credential needs an explicitly reviewed scope, expiry and revocation design. Bind sessions
  to verified owner identity and conversation, and review transport/CSP changes without wildcard access.
- Spoken "yes" remains an ordinary utterance under the current foundation. Approval cards remain
  tactile; voice alone must not resolve an ActionIntent or expand action permissions.
- Microphone capture begins only through an explicit session start and permission grant. Stop media
  tracks, queued audio and provider sessions on end/logout; fence late events and reconnect callbacks.
- Keep raw audio ephemeral in Li by default. Separately establish provider recording, logging,
  retention, training-use and regional processing terms before sending audio; no claim of universal
  zero retention follows from Li not storing recordings. Do not save inferred emotional labels as memory.
- Preserve existing conversation retention and memory-confirmation semantics. Design transcripts,
  heard-versus-generated output and idempotent turn IDs before integration; an interruption must not
  make an unheard claim look heard or a pending action look completed.
- API usage, streaming infrastructure and hosting can be metered. An existing chat subscription or
  API key is not evidence of included API usage. Verify existing prepaid/included coverage and absence
  of automatic overages before live tests; otherwise record the blocker and continue offline work.
- Define bounded session duration, concurrency, idle timeout and usage limits before activation.
  Keep configuration disabled until provider/data-handling prerequisites and exact deployment
  authorization are established. The owner's present instruction authorizes this plan only.

## Delivery stages

| Stage | Deliverable | Exit evidence |
| --- | --- | --- |
| V1 — plan | This plan and links from the existing milestone and architecture. | Documentation review and valid links; no runtime change. |
| V2 — provider and design evaluation | Bounded comparison with the same synthetic Li persona, scenario content and target devices; choose voice, provider, architecture and initial limits. | Verified cost coverage before live calls, recorded model/settings and owner listening preference, reviewed authority/retention design. Implementation/evaluation remains future work. |
| V3 — local implementation | Session controls, selected replaceable adapter, streaming, interruption/history handling and failure states connected to existing Li boundaries. | Automated synthetic session, recovery, authorization and regression checks; complete reviewed diff. |
| V4 — authorized staged trial | Configure the selected provider and deploy the reviewed implementation under the existing release process. | Exact external-action authorization, bounded cost coverage, staged privacy/denial checks and a tested disable/rollback path. |
| V5 — device acceptance | Android phone/tablet conversations in Swedish and English, plus Windows regressions. Native app work remains separately tracked. | Owner preference, measured timing and all applicable device/authority checks; dated acceptance evidence. |

No future stage is marked implemented or authorized for execution by this document. Preserve the
current browser voice path as a fallback candidate; confirm rollback compatibility when designing
any transcript/history change. Disabling the new session must stop capture and provider work while
leaving normal typed conversation available.

## Evaluation and completion criteria

Extend the existing [conversation evaluation](LI_CONVERSATION_EVALUATION.md); do not duplicate its
personality scenarios. Add audio-specific cases below using synthetic data. Begin with a small,
bounded comparison and expand only after verifying available coverage and assessing results.

| Test | Required observation |
| --- | --- |
| English and Swedish ordinary conversation | Fluent, appropriate delivery and correct names; language switches preserve context and the recognizable Li voice. |
| Unfinished sentence and thinking pause | Li waits through a hesitation without repeatedly cutting in. |
| "Mm-hmm" versus "Wait, I meant tomorrow" during speech | Acknowledgement and deliberate interruption behave differently; correction affects the subsequent answer. |
| Interrupted or cancelled output | Playback stops, queued output is cancelled, and unheard material is not treated as delivered. |
| Slow specialist or memory lookup | Li accurately indicates work in progress and returns the actual result, without fabricated memory or tool completion. |
| Spoken approval and provider/tool injection | Neither speech nor provider output bypasses existing confirmation or authority controls. |
| Permission denial, mute, end, logout and expired session | Clear state, no lingering capture/playback, usable text fallback and ignored stale events. |
| Wi-Fi/mobile transition and reconnect | No duplicate turn/action, no stale playback and an honest recovery state. |
| Speakerphone, headset, background speech, screen lock and app switching | Record actual device behavior; unsupported operation is visible rather than described as supported. |

Measure end-of-turn to first audible response, interruption to audible stop, false interruptions,
premature replies, recognition corrections and provider failures. Report median and slow-tail timing
with sample counts, network/device conditions and model settings. Provider time-to-first-byte is not
the same as the owner's end-to-end experience. Record simple-chat and tool-assisted turns separately.

Proposed initial goals for simple exchanges: median first audible response within 1 second after a
completed turn, deliberate interruption stopping playback within 300 ms at the 95th percentile, and
owner scores of at least 4/5 for naturalness, timing and voice preference in each language. These are
design targets to validate, not measured results or guarantees; investigate failures and document any
agreed revision. Authorization, duplicate-action and microphone-stop checks must all pass.

Use [device acceptance](PERSONAL_V1_DEVICE_ACCEPTANCE.md) to record deployed evidence without claiming
that synthetic tests establish physical-device performance. OM-003 stays open until the selected
implementation, authorized rollout and applicable device/owner acceptance are evidenced. No listening
trial, cost entitlement, human-likeness score or live deployment is established by this planning update.
