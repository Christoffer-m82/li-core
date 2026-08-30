from pathlib import Path


STATIC = Path(__file__).parents[1] / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
APP = (STATIC / "assets" / "app.js").read_text(encoding="utf-8")
VOICE = (STATIC / "assets" / "voice.js").read_text(encoding="utf-8")


def test_supported_browser_transcript_uses_normal_chat_once():
    assert "BrowserVoiceTranscriptionProvider" in VOICE
    assert "sendMessage(transcript)" in APP
    assert APP.count("sendMessage(transcript)") == 1
    assert "fetch('/api/chat'" in APP
    assert "audio" not in APP[APP.index("fetch('/api/chat'"):APP.index("fetch('/api/chat'") + 500]


def test_unsupported_browser_falls_back_to_text():
    assert "Voice input is unsupported; use text chat" in APP
    assert "microphone-button" in HTML
    assert 'id="message-input"' in HTML


def test_permission_silence_timeout_and_network_failures_are_visible():
    for code in ("not-allowed", "no-speech", "timeout", "network", "audio-capture"):
        assert code in APP
    assert 'role="status"' in HTML


def test_cancel_before_send_invalidates_session_and_timer():
    assert "function cancelVoiceInput()" in APP
    assert "state.voiceSession += 1" in APP
    assert "clearTimeout(state.voiceSendTimer)" in APP
    assert 'id="voice-cancel"' in HTML


def test_stop_speaking_is_immediate_and_accessible():
    assert "this.synthesis?.cancel()" in VOICE
    assert "function stopSpeaking()" in APP
    assert 'aria-label="Stop Li speaking"' in HTML


def test_swedish_and_english_language_selection():
    assert "return swedishSignals.test(normalized) ? 'sv-SE'" in VOICE
    assert ": 'en-US'" in VOICE
    assert "selectVoice" in VOICE


def test_raw_audio_is_never_uploaded_or_persisted():
    assert "MediaRecorder" not in VOICE
    assert "getUserMedia" not in VOICE
    assert "rawAudioRetention: 'none'" in VOICE
    assert "Audio is ephemeral and never stored by Li" in HTML


def test_voice_uses_normal_history_and_cannot_call_approval_endpoint():
    assert "state.history.push({ role: 'user', text: message })" in APP
    voice_flow = APP[APP.index("async function startVoiceInput"):APP.index("function initializeVoice")]
    assert "action-intents" not in voice_flow
    assert "decision" not in voice_flow
    assert "renderActionIntent" in APP


def test_duplicate_recognition_callbacks_and_sends_are_fenced():
    assert "if (this.settled) return" in VOICE
    assert "if (session !== state.voiceSession || state.sending) return" in APP
    assert "if (state.sending) return" in APP


def test_gmail_send_remains_absent():
    assert "Sending remains unavailable by design" in HTML
    assert "email.send" not in VOICE

