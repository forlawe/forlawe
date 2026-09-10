/* Native Voice Bank — phrase, not clone, dynamic time/name/place/count
 * Plays recorded human audio, stitched, with TTS fallback.
 * Dynamic: time greeting via hour, names via any new name, places via any new place.
 */
(function(){
  window.NativeVoice = {
    // Compose via API and play
    speak: async function(kind, opts){
      opts = opts || {};
      const params = new URLSearchParams({
        kind: kind,
        name: opts.name || '',
        count: opts.count || 0,
        place: opts.place || '',
        patient: opts.patient || '',
        room: opts.room || '',
        detail: opts.detail || '',
        lang: opts.lang || 'en',
        org: opts.org || ''
      });
      try {
        const r = await fetch('/api/v1/voice/compose?' + params.toString());
        const j = await r.json();
        console.log('NativeVoice compose', j);
        if (j.use_native && j.audio_sequence && j.audio_sequence.length){
          await this.playSequence(j.audio_sequence);
        } else if (j.fallback_text || j.text){
          this.speakTTS(j.fallback_text || j.text);
        }
        return j;
      } catch(e){
        console.warn('NativeVoice failed, TTS fallback', e);
        if (opts.fallbackText) this.speakTTS(opts.fallbackText);
      }
    },
    playSequence: async function(seq){
      for (let i=0;i<seq.length;i++){
        await this.playOne(seq[i].audio_url);
      }
    },
    playOne: function(url){
      return new Promise((resolve, reject)=>{
        const a = new Audio(url);
        a.onended = resolve;
        a.onerror = ()=>{ console.warn('audio failed', url); resolve(); };
        a.play().catch(()=>resolve());
      });
    },
    speakTTS: function(text){
      if (!('speechSynthesis' in window)) return;
      try {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.volume = 1.0;
        // Prefer en-NG voice if available
        const voices = window.speechSynthesis.getVoices();
        let ng = voices.find(v=>v.lang && v.lang.toLowerCase().includes('en-ng'));
        if (ng) u.voice = ng;
        window.speechSynthesis.speak(u);
      } catch(e){}
    },
    // For TV: poll /api/v1/voice/next and play
    pollAndPlay: async function(screenCode, lang){
      try {
        const r = await fetch(`/api/v1/voice/next?screen=${encodeURIComponent(screenCode||'MAIN')}&lang=${encodeURIComponent(lang||'en')}`);
        const j = await r.json();
        if (j.announcements && j.announcements.length){
          for (let ann of j.announcements){
            if (ann.voice && ann.voice.audio_sequence && ann.voice.audio_sequence.length){
              await this.playSequence(ann.voice.audio_sequence);
            }
          }
        }
      } catch(e){ console.warn('pollAndPlay failed', e); }
    }
  };

  // Auto-enhance existing app.js voice: if NativeVoice enabled, override speak
  document.addEventListener('DOMContentLoaded', function(){
    // Check if native voice setting enabled via meta tag or global
    const nativeEnabled = document.body.getAttribute('data-native-voice') === '1';
    if (nativeEnabled && window.HMS && window.HMS.speak){
      const origSpeak = window.HMS.speak;
      window.HMS.speak = function(text, urgency){
        // Try native first for known kinds? For now keep TTS, but log
        // Real integration: map text to kind via heuristics
        origSpeak(text, urgency);
      };
    }
  });
})();
