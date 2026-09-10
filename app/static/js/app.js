/* Hospital Admin Manager Suite — client helpers: voice-to-text, offline capture, GPS */
(function () {
  "use strict";

  /* ------------------------------------------------ connectivity banner */
  var banner = document.getElementById("offline-banner");
  var okBanner = document.getElementById("online-banner");
  function paintConn() {
    var on = navigator.onLine;
    var chip = document.getElementById("conn-chip");
    if (chip) { chip.textContent = on ? "ONLINE" : "OFFLINE"; chip.className = "conn" + (on ? "" : " off"); }
    if (banner) banner.classList.toggle("show", !on);
    if (okBanner) okBanner.classList.toggle("show", on && window.__wasOffline === true);
    if (!on) window.__wasOffline = true;
    if (on) setTimeout(function () { if (okBanner) okBanner.classList.remove("show"); }, 4000);
  }
  window.addEventListener("online", function () { paintConn(); trySyncQueue(); });
  window.addEventListener("offline", paintConn);
  paintConn();

  /* ------------------------------------------------ phone menu (hamburger) */
  (function () {
    var btn = document.getElementById("nav-toggle");
    var wrap = document.getElementById("navwrap");
    if (!btn || !wrap) return;
    btn.addEventListener("click", function () {
      var open = wrap.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.textContent = open ? "✕ Close" : "☰ Menu";
    });
  })();

  /* ------------------------------------------------ nav dropdown */
  window.hmsToggleMenu = function (btn) {
    var dd = btn.closest(".dd");
    var wasOpen = dd.classList.contains("open");
    document.querySelectorAll(".dd.open").forEach(function (o) { o.classList.remove("open"); });
    if (!wasOpen) dd.classList.add("open");
  };
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".dd")) document.querySelectorAll(".dd.open").forEach(function (o) { o.classList.remove("open"); });
  });

  /* ------------------------------------------------ voice-to-text (Web Speech API) */
  window.hmsVoice = {
    supported: !!(window.SpeechRecognition || window.webkitSpeechRecognition),

    /* ------------------------------------------------------------------
       Dictation.

       Problems this rewrite fixes (all reported from real phones):

       1. REPEATED AND SCRAMBLED WORDS ON ANDROID (reported 20 Aug 2026:
          "working perfectly on my laptop but repeating words on my phone").

          THE CAUSE. Finals used to be stored in a map keyed by the browser's
          `resultIndex`. On a LAPTOP that is safe: desktop Chrome keeps one
          recognition session open, so the index only ever grows. On a PHONE
          Android ends the session after ~5s of silence and we restart it —
          and the new session's indices RESET TO ZERO. Every phrase after the
          first pause therefore OVERWROTE an earlier one, and Android's habit
          of replaying the previous final on resume duplicated others.

          Dictating "the patient / is waiting / at the pharmacy / please
          attend" with pauses produced "please attend is waiting" — words lost
          AND repeated, exactly as reported. That is why the same code behaved
          on a laptop and misbehaved on a phone.

          THE FIX. Finals are appended to a plain string the moment they
          arrive, and each session's committed text is frozen when that session
          ends. An index from a new session can no longer reach back and
          corrupt a phrase that is already safely written down. A replayed
          phrase is also detected and dropped (see _isEcho).

       2. THE MIC STOPPED ON ITS OWN. Android ends recognition after ~5s of
          silence. The old code treated that as "user finished". Now onend
          RESTARTS it automatically while the user still wants to dictate, so
          the mic keeps listening until THEY stop it.

       3. NO AUTO-STOP WHEN FULL. If the target has a maxlength we stop once it
          is reached, and there is a hard 3-minute safety cap so a forgotten
          mic cannot record forever or drain the battery.

       4. NO FEEDBACK. The button now shows a live "listening" state and the
          interim words appear as you speak.

       5. NO PUNCTUATION (reported 20 Aug 2026: "it's not applying or sensitive
          to comma, full-stop etc").

          Android's speech engine does NOT insert punctuation — it only ever
          returns bare words, so a long complaint arrives as one unbroken run
          of text that is hard to read and impossible to skim. Desktop Chrome
          sometimes adds it, which is why the laptop again looked fine.

          Rather than guess where sentences end (guessing would put full stops
          in the wrong places and be worse than none), the user SAYS the mark:
          "full stop", "comma", "question mark", "new line". Those spoken words
          are converted to real punctuation, and the next letter is capitalised.
          This is how professional dictation has always worked, and it means
          the person speaking stays in control of their own sentences.
       ------------------------------------------------------------------ */
    MAX_MS: 180000,          /* 3-minute hard cap */

    /* ------------------------------------------------------------------
       SPOKEN PUNCTUATION.

       Longest phrases first: "question mark" must be matched before "mark",
       and "full stop" before "stop", or the shorter word wins and eats half
       the phrase. Nigerian English usage is included alongside the American
       forms ("full stop" AND "period"), because staff here say both.
       ------------------------------------------------------------------ */
    PUNCTUATION: [
      [/\b(full stop|fullstop|period)\b/gi, "."],
      [/\b(question mark|questionmark)\b/gi, "?"],
      [/\b(exclamation mark|exclamation point)\b/gi, "!"],
      [/\b(open bracket|open parenthesis)\b/gi, "("],
      [/\b(close bracket|close parenthesis)\b/gi, ")"],
      [/\b(semi colon|semicolon)\b/gi, ";"],
      [/\bcolon\b/gi, ":"],
      [/\bcomma\b/gi, ","],
      [/\b(dash|hyphen)\b/gi, "-"],
      [/\b(new line|newline|next line)\b/gi, "\n"],
      [/\b(new paragraph|next paragraph)\b/gi, "\n\n"]
    ],

    /* Turn spoken marks into real ones, then tidy the spacing around them. */
    _punctuate: function (text) {
      if (!text) return "";
      var out = text;
      for (var i = 0; i < this.PUNCTUATION.length; i++) {
        out = out.replace(this.PUNCTUATION[i][0], this.PUNCTUATION[i][1]);
      }
      /* No space BEFORE a mark, exactly one after it. */
      out = out.replace(/\s+([,.;:!?)])/g, "$1")
               .replace(/([(])\s+/g, "$1")
               .replace(/([,;:])(?=[^\s])/g, "$1 ")
               .replace(/([.!?])(?=[A-Za-z0-9])/g, "$1 ")
               .replace(/[ \t]{2,}/g, " ")
               .replace(/[ \t]*\n[ \t]*/g, "\n");
      /* Capitalise the first letter, and the first letter of each sentence.
         Someone dictating a complaint should not have to fix case by hand. */
      out = out.replace(/(^\s*|[.!?]\s+|\n\s*)([a-z])/g, function (m, lead, ch) {
        return lead + ch.toUpperCase();
      });
      /* The standalone pronoun "I". Android returns it lower-case, and "i
         waited three hours" looks careless on a complaint a manager will read. */
      out = out.replace(/\bi\b/g, "I");
      return out;
    },

    /* ------------------------------------------------------------------
       Is this final just Android replaying something we already wrote down?

       On resume Android often re-sends the tail of the previous session. We
       compare against the end of what we already hold. Deliberately exact
       (after normalising case and spacing) rather than fuzzy: a person really
       may say "yes yes" or "no no", and swallowing a genuine repetition would
       be a worse bug than the one being fixed.
       ------------------------------------------------------------------ */
    _isEcho: function (existing, phrase) {
      if (!existing || !phrase) return false;
      var norm = function (s) {
        return s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ")
                .replace(/\s+/g, " ").trim();
      };
      var a = norm(existing), b = norm(phrase);
      if (!b) return false;
      return a === b || a.slice(-b.length) === b;
    },

    start: function (btn, targetId) {
      var target = document.getElementById(targetId);
      if (!target) return;
      if (!this.supported) {
        this._toast(btn, "Voice typing is not available in this browser. Please type instead.");
        return;
      }
      /* second tap = the USER stopping it */
      if (btn._rec) { this.stop(btn); return; }

      var Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
      var rec = new Rec();
      rec.lang = btn.getAttribute("data-lang") || "en-NG";
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;

      var self = this;
      var base = (target.value || "").replace(/\s+$/, "");
      /* Text safely written down and beyond the reach of a session restart. */
      var locked = "";
      /* Finals from the CURRENT session only, keyed by this session's index.
         Keying is still right WITHIN a session (Chrome re-sends a final it is
         still refining), but it is frozen into `locked` the moment the session
         ends — which is what stops Android's index reset corrupting it. */
      var session = {};
      var wantStop = false;
      var limit = parseInt(target.getAttribute("maxlength") || "0", 10);

      btn._rec = rec;
      btn._stopFn = function () { wantStop = true; try { rec.stop(); } catch (e) {} };
      this._setRecording(btn, true);
      /* Nobody guesses that you can SAY punctuation, so tell them, once, at
         the moment it is useful. Shown next to the button rather than in a
         manual nobody reads. */
      this._showHint(btn);

      /* Append this session's finals to `text`, dropping any that Android is
         merely replaying from before the pause.
         Used BOTH for live rendering and for locking, so what the user watches
         being typed is exactly what gets kept. Doing the echo check only at
         lock time showed the duplicate on screen first, which is precisely the
         thing being complained about. */
      function withSession(text) {
        Object.keys(session).sort(function (a, b) { return a - b; })
          .forEach(function (k) {
            var phrase = session[k];
            if (!phrase) return;
            if (self._isEcho(text, phrase)) return;     /* Android replay */
            text += (text ? " " : "") + phrase;
          });
        return text;
      }

      /* Fold this session's finals into the permanent text. Called on every
         session end, so a phrase can never be overwritten by a later index. */
      function lockSession() {
        locked = withSession(locked);
        session = {};
      }

      function render(interim) {
        var spoken = withSession(locked);
        if (interim && !self._isEcho(spoken, interim)) {
          spoken += (spoken ? " " : "") + interim;
        }

        var merged = (base ? base + " " : "") + spoken;
        merged = self._punctuate(merged);
        if (limit > 0 && merged.length >= limit) {
          merged = merged.slice(0, limit);
          self._toast(btn, "That is the maximum length — microphone stopped.");
          btn._stopFn();
        }
        target.value = merged;
        target.dispatchEvent(new Event("input", { bubbles: true }));
      }

      rec.onresult = function (e) {
        var interim = "";
        for (var i = e.resultIndex; i < e.results.length; i++) {
          var r = e.results[i];
          var txt = (r[0] && r[0].transcript ? r[0].transcript : "").trim();
          if (!txt) continue;
          if (r.isFinal) {
            session[i] = txt;
          } else {
            interim += (interim ? " " : "") + txt;
          }
        }
        render(interim);
      };

      rec.onerror = function (e) {
        var err = e && e.error;
        if (err === "no-speech" || err === "aborted") return;   /* onend will restart */
        if (err === "language-not-supported" && rec.lang !== "en-NG") {
          rec.lang = "en-NG";                                   /* fall back and continue */
          return;
        }
        wantStop = true;
        self.stop(btn);
        if (err === "not-allowed" || err === "service-not-allowed") {
          self._toast(btn, "Microphone blocked. Allow microphone access in your browser settings, or type instead.");
        } else if (err === "network") {
          self._toast(btn, "Voice typing needs internet. Please type instead.");
        } else if (err === "language-not-supported") {
          self._toast(btn, "Voice typing is not available in this language on this phone.");
        }
      };

      /* Android ends recognition on silence. Restart unless the USER asked to
         stop (or the safety cap fired).

         LOCKING BEFORE THE RESTART IS THE WHOLE FIX. The next session's result
         indices begin again at 0, so anything still held per-index would be
         overwritten by the next phrase. Freezing it into `locked` first puts it
         permanently out of reach. */
      rec.onend = function () {
        lockSession();
        render("");
        if (wantStop) { self._cleanup(btn); return; }
        try { rec.start(); } catch (e) { self._cleanup(btn); }
      };

      btn._timer = setTimeout(function () {
        self._toast(btn, "Microphone stopped after 3 minutes. Tap it again to continue.");
        btn._stopFn();
      }, this.MAX_MS);

      try { rec.start(); } catch (e) { this._cleanup(btn); }
    },

    stop: function (btn) {
      if (btn && btn._stopFn) btn._stopFn();
      else this._cleanup(btn);
    },

    _setRecording: function (btn, on) {
      btn.classList.toggle("recording", !!on);
      if (on) {
        if (!btn._label) btn._label = btn.innerHTML;
        btn.innerHTML = "⏹ Listening… tap to stop";
        btn.setAttribute("aria-label", "Stop dictation");
      } else {
        btn.innerHTML = btn._label || "🎤 Speak";
        btn.setAttribute("aria-label", "Start dictation");
      }
    },

    _cleanup: function (btn) {
      if (!btn) return;
      if (btn._timer) { clearTimeout(btn._timer); btn._timer = null; }
      btn._rec = null;
      btn._stopFn = null;
      this._hideHint(btn);
      this._setRecording(btn, false);
    },

    /* Tell the user they can speak their punctuation. Shown while the mic is
       live, removed when it stops. Deliberately not a pop-up: a dialog in the
       middle of dictation would interrupt the very thing it is explaining. */
    _showHint: function (btn) {
      try {
        if (btn._hint) return;
        var host = (btn && btn.parentNode) || document.body;
        var h = document.createElement("div");
        h.className = "voice-hint";
        h.textContent = "Tip: say \u201ccomma\u201d, \u201cfull stop\u201d, \u201cquestion mark\u201d "
                      + "or \u201cnew line\u201d and they will be typed for you.";
        host.appendChild(h);
        btn._hint = h;
      } catch (e) { /* a missing tip must never stop dictation */ }
    },

    _hideHint: function (btn) {
      try {
        if (btn && btn._hint && btn._hint.parentNode) {
          btn._hint.parentNode.removeChild(btn._hint);
        }
        if (btn) btn._hint = null;
      } catch (e) {}
    },

    /* Small inline message — never a blocking alert() mid-dictation. */
    _toast: function (btn, msg) {
      try {
        var host = (btn && btn.parentNode) || document.body;
        var t = document.createElement("div");
        t.className = "voice-toast";
        t.textContent = msg;
        host.appendChild(t);
        setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 5000);
      } catch (e) { /* never block the user */ }
    },

    /* Louder, clearer spoken alerts (§19): full volume, best English voice,
       layered bell at higher gain. Voice remains an enhancement, never a dependency. */
    /* ------------------------------------------------------------------
       AUDIO UNLOCK.

       Every modern browser blocks speech and sound until the user has
       interacted with the page. Before this, the very first announcement was
       silently swallowed and staff concluded "voice reminders don't work" —
       which is exactly what was reported. We now:
         * detect that audio is still locked,
         * show a one-tap "Enable voice alerts" banner,
         * unlock on the first tap anywhere and speak a short confirmation,
         * remember the choice for next time.
       ------------------------------------------------------------------ */
    audioReady: false,

    unlockAudio: function (announce) {
      // Mark audio unlocked FIRST. Each step below is independently guarded so
      // one unsupported API (common on older Android browsers) cannot leave
      // the whole feature switched off — which is how this failed silently.
      this.audioReady = true;
      try { localStorage.setItem("hms-audio-ok", "1"); } catch (e) {}

      try {
        if ('speechSynthesis' in window) {
          var u = new SpeechSynthesisUtterance(announce ? "Voice alerts are on." : " ");
          u.volume = announce ? 1.0 : 0.01;
          window.speechSynthesis.speak(u);
        }
      } catch (e) { /* speech unavailable: chime and text still work */ }

      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (Ctx) {
          if (!this._actx) this._actx = new Ctx();
          if (this._actx.state === "suspended") this._actx.resume();
        }
      } catch (e) { /* no Web Audio: speech still works */ }

      try {
        var banner = document.getElementById("voice-unlock");
        if (banner) banner.remove();
      } catch (e) {}
    },

    /* Shown until the user taps once. Without it the failure is invisible. */
    showUnlockBanner: function () {
      if (document.getElementById("voice-unlock")) return;
      var self = this;
      var bar = document.createElement("div");
      bar.id = "voice-unlock";
      bar.className = "voice-unlock";
      var msg = document.createElement("span");
      msg.textContent = "🔔 Tap to turn on spoken alerts";
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "btn small"; btn.textContent = "Enable";
      btn.onclick = function (e) { e.stopPropagation(); self.unlockAudio(true); };
      bar.appendChild(msg); bar.appendChild(btn);
      document.body.appendChild(bar);
    },

    speak: function (text, urgency) {
      var P = (window.hmsAlerts && window.hmsAlerts.prefs) ||
              { voice_enabled: true, voice_min_level: "standard" };
      if (!P.voice_enabled) return;
      var LV = { standard: 0, urgent: 1, emergency: 2 };
      if ((LV[urgency] || 0) < (LV[P.voice_min_level] || 0)) return;
      // inQuietHours lives on hmsAlerts, not here. Calling this.inQuietHours()
      // threw a TypeError and killed EVERY spoken alert before it started —
      // a second, independent reason voice reminders appeared not to work.
      var alerts = window.hmsAlerts;
      if (alerts && typeof alerts.inQuietHours === "function" && alerts.inQuietHours()) return;
      try {
        if (!('speechSynthesis' in window)) return;
        if (!this.audioReady) {                 // browser has not unlocked audio yet
          this.showUnlockBanner();              // make the problem VISIBLE
          return;
        }
        window.speechSynthesis.cancel();        // clear queue → no overlapping repeats
        var u = new SpeechSynthesisUtterance(text);
        u.lang = this.alertLang || "en-NG";      // speak in the user's chosen language
        u.volume = 1.0;                          // maximum
        u.rate = urgency === "emergency" ? 1.0 : 0.92;   // slightly slower = clearer
        u.pitch = 1.0;
        var pick = function () {
          var vs = window.speechSynthesis.getVoices();
          var v = vs.filter(function (x) { return /^en/i.test(x.lang); })
                    .sort(function (a, b) { return (b.lang === "en-NG") - (a.lang === "en-NG") ||
                                                   (b.localService - a.localService); })[0];
          if (v) u.voice = v;
          window.speechSynthesis.speak(u);
        };
        // Voice list loads asynchronously. If it is empty we wait for
        // onvoiceschanged — but on many Android builds that event NEVER fires,
        // which left the announcement queued forever and silent. Always speak
        // after a short grace period regardless; the default system voice is
        // perfectly acceptable.
        if (window.speechSynthesis.getVoices().length) {
          pick();
        } else {
          var said = false;
          var once = function () { if (!said) { said = true; pick(); } };
          try { window.speechSynthesis.onvoiceschanged = once; } catch (e) {}
          setTimeout(once, 250);
        }
      } catch (e) { /* fall back silently to text */ }
    },

    bell: function (urgency) {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        if (!this._actx) this._actx = new Ctx();
        var ctx = this._actx;
        if (ctx.state === "suspended") ctx.resume();
        var GAIN = 0.9;   // much louder than before (was 0.25)
        var notes = urgency === "emergency" ? [[880, 0], [660, .22], [880, .44], [660, .66], [880, .88]]
                  : urgency === "urgent" ? [[740, 0], [740, .25], [740, .5]]
                  : [[660, 0], [880, .28]];
        notes.forEach(function (n) {
          // two detuned oscillators per note = fuller, clearer chime
          [0, 3].forEach(function (det) {
            var o = ctx.createOscillator(), g = ctx.createGain();
            o.type = det ? "triangle" : "sine";
            o.frequency.value = n[0] + det;
            g.gain.setValueAtTime(0.0001, ctx.currentTime + n[1]);
            g.gain.exponentialRampToValueAtTime(GAIN, ctx.currentTime + n[1] + .02);
            g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + n[1] + .24);
            o.connect(g); g.connect(ctx.destination);
            o.start(ctx.currentTime + n[1]); o.stop(ctx.currentTime + n[1] + .28);
          });
        });
      } catch (e) { /* sound is an enhancement */ }
    }
  };

  /* ------------------------------------------------ inspection: dynamic sections/units */
  window.hmsDeptCascade = function (deptSelect, sectionSelect, unitSelect, csrf) {
    if (!deptSelect) return;
    deptSelect.addEventListener("change", function () {
      sectionSelect.innerHTML = '<option value="">— Whole department —</option>';
      unitSelect.innerHTML = '<option value="">—</option>';
      unitSelect.disabled = true;
      var id = deptSelect.value;
      if (!id) { sectionSelect.disabled = true; return; }
      fetch("/inspections/departments/" + id + "/children", {
        method: "POST", headers: { "X-CSRF-Token": csrf }
      }).then(function (r) { return r.json(); }).then(function (data) {
        sectionSelect.disabled = false;
        (data.sections || []).forEach(function (s) {
          var o = document.createElement("option"); o.value = s.id; o.textContent = s.name;
          o.setAttribute("data-units", JSON.stringify(s.units || []));
          sectionSelect.appendChild(o);
        });
      }).catch(function () {});
    });
    if (sectionSelect) sectionSelect.addEventListener("change", function () {
      unitSelect.innerHTML = '<option value="">— Whole section —</option>';
      var opt = sectionSelect.options[sectionSelect.selectedIndex];
      var units = opt ? JSON.parse(opt.getAttribute("data-units") || "[]") : [];
      units.forEach(function (u) {
        var o = document.createElement("option"); o.value = u.id; o.textContent = u.name;
        unitSelect.appendChild(o);
      });
      unitSelect.disabled = units.length === 0;
    });
  };

  /* ------------------------------------------------ inspection GPS */
  window.hmsGps = function (mode, latInput, lngInput, statusEl) {
    if (mode === "disabled" || !latInput) return;
    if (!navigator.geolocation) { if (statusEl) statusEl.textContent = "GPS not available on this device."; return; }
    if (statusEl) statusEl.textContent = "Getting GPS location…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      latInput.value = pos.coords.latitude.toFixed(6);
      lngInput.value = pos.coords.longitude.toFixed(6);
      if (statusEl) statusEl.textContent = "✅ GPS location captured.";
    }, function (err) {
      if (statusEl) statusEl.textContent = mode === "mandatory"
        ? "❌ GPS unavailable — submission requires location." : "GPS not captured (optional).";
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 120000 });
  };

  /* ------------------------------------------------ score -> explanation enforcement */
  window.hmsScoreEnforce = function (form) {
    if (!form) return;
    form.querySelectorAll("input[name^='score_']").forEach(function (input) {
      input.addEventListener("change", function () {
        var no = input.name.split("_")[1];
        var box = document.getElementById("expl-box-" + no);
        if (!box) return;
        var low = parseInt(input.value, 10) <= 2;
        box.style.display = low ? "block" : "none";
        var card = box.closest(".crit-card");
        if (card) card.classList.toggle("flagged", low);
      });
    });
    form.addEventListener("submit", function (e) {
      var missing = [];
      [1, 2, 3, 4, 5].forEach(function (no) {
        var sel = form.querySelector("input[name='score_" + no + "']:checked");
        var expl = document.getElementById("explanation_" + no);
        if (sel && parseInt(sel.value, 10) <= 2 && expl && !expl.value.trim()) {
          missing.push(no);
        }
      });
      if (missing.length) {
        e.preventDefault();
        alert("Explanation required for criterion " + missing.join(", ") +
              " (score 1 or 2). Use text or the 🎤 voice button.");
        var box = document.getElementById("expl-box-" + missing[0]);
        if (box) box.scrollIntoView({ behavior: "smooth", block: "center" });
        return false;
      }
      /* stash a copy locally until the server confirms (offline safety) */
      try {
        var data = {};
        new FormData(form).forEach(function (v, k) { if (typeof v === "string") data[k] = v; });
        localStorage.setItem("hms-last-inspection", JSON.stringify({ at: Date.now(), data: data }));
      } catch (err) {}
    });
  };

  /* ------------------------------------------------ offline submission queue */
  function trySyncQueue() {
    var raw = null;
    try { raw = localStorage.getItem("hms-sync-queue"); } catch (e) {}
    if (!raw) return;
    var queue = JSON.parse(raw || "[]");
    if (!queue.length) return;
    var item = queue[0];
    fetch(item.url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": item.csrf },
      body: JSON.stringify(item.data)
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        queue.shift();
        localStorage.setItem("hms-sync-queue", JSON.stringify(queue));
        if (res.j && res.j.ok) {
          alert("Inspection " + res.j.ref + " synced successfully.");
          if (res.j.detail_url) window.location = res.j.detail_url;
        } else if (res.j && res.j.error === "duplicate") {
          alert("This inspection was already submitted (" + res.j.ref + ").");
        } else {
          alert("Sync failed: " + ((res.j && res.j.error) || "please retry"));
        }
      }).catch(function () { /* still offline */ });
  }
  window.hmsQueueSubmit = function (url, data, csrf) {
    var q = [];
    try { q = JSON.parse(localStorage.getItem("hms-sync-queue") || "[]"); } catch (e) {}
    q.push({ url: url, data: data, csrf: csrf });
    localStorage.setItem("hms-sync-queue", JSON.stringify(q));
    alert("You are offline. Your inspection has been SAVED LOCALLY and will sync automatically when connectivity returns.");
  };

  /* ------------------------------------------------ live alert engine (§19): bell + voice + browser notifications */
  window.hmsAlerts = {
    lastId: parseInt(localStorage.getItem("hms-alert-last") || "0", 10),
    prefs: { voice_enabled: true, voice_min_level: "standard", quiet_start: "",
             quiet_end: "", push_enabled: false },
    LEVELS: { standard: 0, urgent: 1, emergency: 2 },

    inQuietHours: function () {
      try {
        // Empty start/end means quiet hours are OFF. Anything else would
        // silence night-shift staff, who need announcements most.
        if (!this.prefs.quiet_start || !this.prefs.quiet_end) return false;
        if (this.prefs.quiet_start === this.prefs.quiet_end) return false;
        var now = new Date();
        var cur = now.getHours() * 60 + now.getMinutes();
        var p = function (s) { var x = (s || "0:0").split(":"); return parseInt(x[0], 10) * 60 + parseInt(x[1] || 0, 10); };
        var a = p(this.prefs.quiet_start), b = p(this.prefs.quiet_end);
        return a <= b ? (cur >= a && cur < b) : (cur >= a || cur < b);
      } catch (e) { return false; }
    },

    bell: function (urgency) {
      if (window.hmsVoice && window.hmsVoice.bell) { window.hmsVoice.bell(urgency); return; }
      /* unreachable fallback kept for safety */
      window.hmsVoice.bell(urgency);
    },

    speak: function (text, urgency) {
      if (window.hmsVoice && window.hmsVoice.speak) { window.hmsVoice.speak(text, urgency); return; }
    },

    toast: function (a) {
      var zone = document.getElementById("toast-zone");
      if (!zone) return;
      var el = document.createElement("div");
      el.className = "toast " + a.urgency;
      // textContent, never innerHTML: alert text can contain a patient name
      // typed by a member of the public.
      var t = document.createElement("div"); t.className = "t-title";
      t.textContent = a.subject || "Alert";
      var b = document.createElement("div"); b.className = "t-body";
      b.textContent = a.body || "";
      el.appendChild(t); el.appendChild(b);
      zone.appendChild(el);
      setTimeout(function () { el.style.opacity = "0"; el.style.transition = "opacity .6s";
        setTimeout(function () { el.remove(); }, 650); }, 9000);
    },

    notify: function (a) {
      if (!this.prefs.push_enabled) return;
      if (!('Notification' in window) || Notification.permission !== "granted") return;
      try { new Notification(a.subject, { body: a.body, tag: "hms-" + a.id }); } catch (e) {}
    },

    poll: function () {
      var self = this;
      fetch("/api/v1/alerts/poll?after=" + self.lastId).then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.prefs) self.prefs = data.prefs;
          (data.alerts || []).forEach(function (a) {
            self.toast(a);
            self.notify(a);
            if (!self.inQuietHours()) self.bell(a.urgency);
            var line = a.speech || a.body;
            self.speak(a.urgency === "emergency" ? "Attention. " + line
                     : a.urgency === "urgent" ? "Alert. " + line : line, a.urgency);
          });
          if (data.last_id && data.last_id > self.lastId) {
            self.lastId = data.last_id;
            localStorage.setItem("hms-alert-last", String(self.lastId));
          }
        }).catch(function () { /* offline — next pass */ });
    },

    start: function () {
      var self = this;

      // Unlock audio on the FIRST interaction of any kind. Staff tap something
      // within seconds of signing in, so in practice voice is ready before the
      // first announcement arrives.
      ["pointerdown", "keydown", "touchstart"].forEach(function (evt) {
        document.addEventListener(evt, function once() {
          if (window.hmsVoice) window.hmsVoice.unlockAudio(false);
          ["pointerdown", "keydown", "touchstart"].forEach(function (e2) {
            document.removeEventListener(e2, once);
          });
        }, { once: true, passive: true });
      });

      // If they enabled it before on this device, assume it is still allowed.
      try {
        if (localStorage.getItem("hms-audio-ok") === "1" && window.hmsVoice) {
          window.hmsVoice.audioReady = true;
        }
      } catch (e) {}

      self.poll();
      setInterval(function () { self.poll(); }, 30000);
    },

    /* Lets a nurse prove voice works on THEIR device, without waiting for a
       real patient event. Wired to the button on /alert-settings. */
    testVoice: function () {
      if (window.hmsVoice) window.hmsVoice.unlockAudio(false);
      this.bell("urgent");
      var who = (window.hmsUserName || "Colleague");
      this.speak(who + ", this is a test announcement. "
                 + "3 patients are waiting for your attention.", "urgent");
    }
  };

  /* ------------------------------------------------ feature phone / future phone detection */
  window.hmsFeaturePhoneCheck = function(){
    try{
      var ua = (navigator.userAgent||'').toLowerCase();
      var isFeature = /kaios|nokia|opera mini|opera mobi|ucbrowser|uc browser|j2me|midp|alcatel|micromax|itel|tecno/.test(ua);
      var noFetch = typeof fetch === 'undefined';
      var noPromise = typeof Promise === 'undefined';
      var smallScreen = window.screen && window.screen.width < 320;
      if(isFeature || noFetch || noPromise){
        var banner = document.getElementById('feature-phone-banner');
        if(banner) banner.style.display='block';
      }
      // Also detect if push not supported — show provision note
      if(window.hmsPush && !window.hmsPush.isSupported()){
        var banner2 = document.getElementById('feature-phone-banner');
        if(banner2) banner2.style.display='block';
      }
    }catch(e){}
  };
  // Auto-run on load for all browsers
  try{ window.hmsFeaturePhoneCheck(); }catch(e){}

  /* ------------------------------------------------ draft autosave for inspection form */
  window.hmsDraft = function (form, key) {
    if (!form) return;
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(key) || "null"); } catch (e) {}
    if (saved && saved.at && Date.now() - saved.at < 86400000) {
      Object.keys(saved.data || {}).forEach(function (k) {
        var el = form.elements[k];
        if (!el) return;
        if (el.type === "radio") {
          if (el.value === saved.data[k]) el.checked = true;
        } else if (el.tagName !== "SELECT" || saved.data[k]) { el.value = saved.data[k]; }
      });
      var n = document.getElementById("draft-note");
      if (n) n.style.display = "block";
    }
    var t = null;
    form.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () {
        var data = {};
        new FormData(form).forEach(function (v, k) { if (typeof v === "string") data[k] = v; });
        try { localStorage.setItem(key, JSON.stringify({ at: Date.now(), data: data })); } catch (e) {}
      }, 400);
    });
  };
})();
