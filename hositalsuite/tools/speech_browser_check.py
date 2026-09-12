"""Prove the dictation fix works in a REAL browser, on the REAL page.

The Node harness tests the logic in isolation. This loads an actual hospital
page in Chromium at phone size, replaces only the SpeechRecognition engine with
one that behaves like Android (ends on silence, resets indices, replays the
last final), and checks what really lands in the textarea on screen.

Usage: python3 tools/speech_browser_check.py http://127.0.0.1:5055
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055"
PHONE = {"width": 390, "height": 844}

failures: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (notes if ok else failures).append(
        f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))


# A fake engine that reproduces Android's actual misbehaviour.
FAKE_ANDROID = """
window.__android = null;
class FakeRec {
  constructor(){ this.onresult=null; this.onend=null; this.onerror=null;
                 this._i=0; window.__android=this; }
  start(){ this._i = 0; }
  stop(){ if(this.onend) this.onend(); }
  abort(){ this.stop(); }
  say(){ const phrases=[...arguments]; const startAt=this._i;
    const all=[]; for(let i=0;i<startAt;i++) all.push({0:{transcript:""},isFinal:true});
    phrases.forEach(p=>all.push({0:{transcript:p},isFinal:true}));
    this._i += phrases.length;
    if(this.onresult) this.onresult({resultIndex:startAt, results:all}); }
  silence(){ if(this.onend) this.onend(); }
}
window.SpeechRecognition = FakeRec;
window.webkitSpeechRecognition = FakeRec;
"""


def run() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=PHONE)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # The public complaint page: no login, has a mic and a textarea.
        page.add_init_script(FAKE_ANDROID)
        page.goto(f"{BASE}/complaint", wait_until="domcontentloaded")

        has_mic = page.query_selector(".mic-btn") is not None
        check("the complaint page has a microphone button", has_mic)
        if not has_mic:
            browser.close()
            print("\n".join(notes + failures))
            return 1

        def dictate(script: str) -> str:
            page.evaluate("document.getElementById('cmp-desc').value = ''")
            page.click(".mic-btn")
            page.evaluate(script)
            return page.eval_on_selector("#cmp-desc", "el => el.value")

        # 1. THE REPORTED BUG, on a real page.
        got = dictate("""
            const r = window.__android;
            r.say('the patient', 'is waiting');
            r.silence();
            r.say('at the pharmacy');
            r.silence();
            r.say('please attend');
        """)
        check("phone pauses do not scramble or repeat words",
              got == "The patient is waiting at the pharmacy please attend", repr(got))
        page.click(".mic-btn")

        # 2. Android replaying its last final must not duplicate it.
        got = dictate("""
            const r = window.__android;
            r.say('the generator has failed');
            r.silence();
            r.say('the generator has failed', 'and there is no budget');
        """)
        check("a phrase replayed on resume is not duplicated",
              got == "The generator has failed and there is no budget", repr(got))
        page.click(".mic-btn")

        # 3. Spoken punctuation.
        got = dictate("""
            window.__android.say('i waited three hours comma nobody told me why full stop');
        """)
        check("spoken comma and full stop become real punctuation",
              got == "I waited three hours, nobody told me why.", repr(got))
        page.click(".mic-btn")

        got = dictate("""
            window.__android.say('why was i not attended to question mark');
        """)
        check("spoken question mark becomes ?",
              got == "Why was I not attended to?", repr(got))

        # 4. The tip must actually appear on screen while the mic is live.
        # NOTE: dictate() already STARTED the mic, so it is live right now.
        # An extra click here would stop it — which is what made this check
        # fail the first time round. The mic is a toggle; track its state.
        hint = page.query_selector(".voice-hint")
        check("the spoken-punctuation tip is shown while dictating",
              hint is not None and "full stop" in (hint.inner_text() if hint else ""))
        if hint:
            box = hint.bounding_box()
            check("the tip fits the phone screen",
                  bool(box) and box["width"] <= 390, str(box))
        page.click(".mic-btn")   # stop
        check("the tip disappears when the microphone stops",
              page.query_selector(".voice-hint") is None)

        # 5. Nothing overflows sideways on a phone.
        over = page.evaluate(
            "() => document.documentElement.scrollWidth - window.innerWidth")
        check("the page still fits a 390px phone", over <= 2, f"{over}px too wide")

        check("no JavaScript errors", not errors, "; ".join(errors[:3]))
        browser.close()

    for line in notes:
        print(line)
    for line in failures:
        print(line)
    print(f"\n{len(notes)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
