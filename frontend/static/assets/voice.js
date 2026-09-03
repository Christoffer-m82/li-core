/* Browser voice adapters. They never receive Li credentials or persist audio. */
(function exposeVoiceFoundation(global) {
  const SpeechRecognition = global.SpeechRecognition || global.webkitSpeechRecognition;

  /** @typedef {'idle'|'listening'|'transcribing'|'thinking'|'speaking'|'error'} VoiceState */
  /**
   * @typedef {Object} VoiceTranscriptionProvider
   * @property {(handlers: {onInterim?: function(string): void, onState?: function(VoiceState): void}) => Promise<string>} start
   * @property {() => void} cancel
   */
  /**
   * @typedef {Object} VoiceSynthesisProvider
   * @property {(text: string, language: string, handlers?: Object) => boolean} speak
   * @property {() => void} stop
   */

  class BrowserVoiceTranscriptionProvider {
    constructor({ language = global.navigator?.language || 'en-US', timeoutMs = 15000 } = {}) {
      this.language = language;
      this.timeoutMs = timeoutMs;
      this.recognition = null;
      this.timer = null;
      this.settled = false;
      this.rejectPending = null;
    }

    static isSupported() { return Boolean(SpeechRecognition); }

    start({ onInterim, onState } = {}) {
      if (!SpeechRecognition) return Promise.reject(new Error('unsupported'));
      this.cancel();
      this.settled = false;
      return new Promise((resolve, reject) => {
        this.rejectPending = reject;
        const recognition = new SpeechRecognition();
        this.recognition = recognition;
        recognition.lang = this.language;
        recognition.interimResults = true;
        recognition.continuous = false;
        recognition.maxAlternatives = 1;
        const finish = (callback, value) => {
          if (this.settled || this.recognition !== recognition) return;
          this.settled = true;
          global.clearTimeout(this.timer);
          this.recognition = null;
          this.rejectPending = null;
          callback(value);
        };
        recognition.onstart = () => onState?.('listening');
        recognition.onresult = (event) => {
          let interim = '';
          let finalTranscript = '';
          let finalConfidence = null;
          for (let index = event.resultIndex; index < event.results.length; index += 1) {
            const result = event.results[index];
            const alternative = result?.[0];
            if (!alternative || !String(alternative.transcript || '').trim()) continue;
            if (result.isFinal) { finalTranscript += alternative.transcript; finalConfidence = alternative.confidence; }
            else interim += alternative.transcript;
          }
          onInterim?.((finalTranscript || interim).trim());
          if (finalTranscript.trim() && Number.isFinite(finalConfidence)) finish(resolve, finalTranscript.trim());
        };
        recognition.onerror = (event) => finish(reject, new Error(event.error || 'recognition-failed'));
        recognition.onend = () => {
          if (!this.settled) finish(reject, new Error('no-speech'));
        };
        this.timer = global.setTimeout(() => {
          finish(reject, new Error('timeout'));
          recognition.abort();
        }, this.timeoutMs);
        try { recognition.start(); } catch (error) { finish(reject, error); }
      });
    }

    cancel() {
      const rejectPending = this.rejectPending;
      global.clearTimeout(this.timer);
      this.settled = true;
      this.rejectPending = null;
      if (this.recognition) {
        this.recognition.onstart = null;
        this.recognition.onresult = null;
        this.recognition.onerror = null;
        this.recognition.onend = null;
        this.recognition.abort();
        this.recognition = null;
      }
      rejectPending?.(new Error('cancelled'));
    }
  }

  class BrowserVoiceSynthesisProvider {
    constructor() { this.synthesis = global.speechSynthesis; }
    static isSupported() { return Boolean(global.speechSynthesis && global.SpeechSynthesisUtterance); }
    selectVoice(language) {
      const wanted = String(language || 'en').toLowerCase();
      const base = wanted.split('-')[0];
      return (this.synthesis?.getVoices() || []).find((voice) => voice.lang.toLowerCase() === wanted)
        || (this.synthesis?.getVoices() || []).find((voice) => voice.lang.toLowerCase().startsWith(`${base}-`))
        || null;
    }
    speak(text, language, { onStart, onEnd, onError } = {}) {
      if (!BrowserVoiceSynthesisProvider.isSupported() || !String(text || '').trim()) return false;
      this.stop();
      const utterance = new global.SpeechSynthesisUtterance(text);
      utterance.lang = language || global.navigator?.language || 'en-US';
      utterance.voice = this.selectVoice(utterance.lang);
      utterance.onstart = onStart || null;
      utterance.onend = onEnd || null;
      utterance.onerror = onError || null;
      this.synthesis.speak(utterance);
      return true;
    }
    stop() { this.synthesis?.cancel(); }
  }

  function detectLanguage(text, fallback = global.navigator?.language || 'en-US') {
    const normalized = ` ${String(text || '').toLowerCase()} `;
    const swedishSignals = /[åäö]|\b(och|att|det|jag|du|inte|som|för|med|tack)\b/;
    return swedishSignals.test(normalized) ? 'sv-SE' : (String(fallback).toLowerCase().startsWith('sv') ? 'sv-SE' : 'en-US');
  }

  global.LiVoice = Object.freeze({
    BrowserVoiceTranscriptionProvider,
    BrowserVoiceSynthesisProvider,
    detectLanguage,
    capability: Object.freeze({
      sttMode: 'browser-native',
      ttsMode: 'browser-native',
      serverProviderConfigured: false,
      rawAudioRetention: 'none',
    }),
  });
}(window));
