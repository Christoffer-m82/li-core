# Voice Interaction Foundation

Li Web voice is an additive input/output adapter around the existing authenticated chat experience. It does not create a second orchestration path.

## Web milestone

- `BrowserVoiceTranscriptionProvider` wraps `SpeechRecognition` / `webkitSpeechRecognition` when the browser exposes it. It starts only after a microphone-button action, produces a visible transcript, and fails closed when there is no trustworthy final result.
- The web response policy permits microphone access only to Li's own origin. Browser permission is
  still required, and framing remains denied, so third-party origins cannot inherit microphone use.
- `BrowserVoiceSynthesisProvider` wraps `speechSynthesis`. It speaks the actual final Li response, selects Swedish or English browser voices where available, and supports immediate cancellation.
- The final transcript is sent through the existing BFF `POST /api/chat` to backend `POST /li/chat`. Memory, identity, specialist routing, ActionIntent creation, conversation history, and privacy behavior are therefore identical to typed chat.
- Voice code has no audio-upload, audio-storage, logging, analytics, artifact, or memory API. Raw audio retention is none. Browser speech services and their availability or processing behavior are browser/vendor-dependent.
- Approval cards remain tactile. Voice code cannot call the ActionIntent decision endpoint, so a phrase such as “yes, approve it” is only a normal chat turn and cannot resolve a pending action.

## Planned real-time conversation milestone

The owner requested natural, human-sounding phone/tablet conversation on 2026-09-06 and asked to
record the plan only. See the [real-time voice plan](docs/REALTIME_VOICE_PLAN.md) for provider
evaluation, architecture options, interruption and timing requirements, delivery stages, and
acceptance gates. This is future scope under OM-003, not implemented behavior or a provider decision.
The existing final-response, orchestration and approval boundaries above remain in force; any
speech-to-speech design that changes them must resolve that contract before implementation.
Its project placement is late in Package 6 after the blueprint's
[core stability entry gate](docs/LI_OS_IMPROVEMENT_BLUEPRINT.md#om-003-dependency-placement), before
enhanced-voice device/owner acceptance and final sign-off; blocked voice work does not stop unrelated
eligible acceptance work.

## Typed provider boundary

The browser adapters define the reusable contract shape for later providers:

- transcription: support detection, `start({onInterim, onState}) -> Promise<string>`, and `cancel()`;
  cancellation aborts the active recognition and settles its pending start without a transcript;
- synthesis: support detection, `speak(finalText, language, callbacks)`, `selectVoice(language)`, and `stop()`.

A future server STT provider can implement the transcription contract behind an authenticated, ephemeral transport. It must not alter `/li/chat` semantics or retain raw audio by default. No server provider or credential is configured in this milestone.

## Native iOS, Android, and tablet mapping

Native clients may use platform microphone and speech frameworks to produce a final transcript, then submit that text through the same authenticated `/li/chat` contract. They render the returned response and ActionIntents normally, and may synthesize only the returned final response using platform TTS. Native audio transport, if later required, remains a replaceable adapter; Li orchestration, memory, privacy, identity, and approval semantics stay server-owned and unchanged.
