/* Speech-to-text tests, run against the REAL app/static/js/app.js.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The founder reported dictation "working perfectly on my laptop but repeating
 * words when I used my phone", and not honouring "comma, full-stop etc".
 *
 * Neither fault could be caught by the Python suite: the bug lives entirely in
 * the browser, in how Chrome on Android ends and restarts a recognition
 * session. A Flask test client never executes this code at all.
 *
 * So this harness loads the actual shipped app.js into a fake DOM, drives it
 * with a fake SpeechRecognition that behaves the way ANDROID does (ends on
 * silence, resets result indices to 0 on resume, replays the last final), and
 * asserts on what ends up in the textbox.
 *
 * Run:  node tests/js/speech_test.js
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const APP_JS = path.join(__dirname, "..", "..", "app", "static", "js", "app.js");

let passed = 0;
const failures = [];

function check(label, ok, detail) {
  if (ok) { passed++; console.log("PASS  " + label); }
  else { failures.push(label); console.log("FAIL  " + label + (detail ? " — " + detail : "")); }
}

function eq(label, actual, expected) {
  check(label, actual === expected,
        "got " + JSON.stringify(actual) + ", expected " + JSON.stringify(expected));
}

/* ------------------------------------------------------------------ fake DOM */
function makeElement(tag) {
  return {
    tagName: tag, value: "", innerHTML: "", className: "", children: [],
    _attrs: {}, parentNode: null,
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); },
      toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); }
    },
    getAttribute(k) { return k in this._attrs ? this._attrs[k] : null; },
    setAttribute(k, v) { this._attrs[k] = v; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); },
    remove() {},
    dispatchEvent() { return true; },
    addEventListener() {},
    closest() { return null; },
    querySelectorAll() { return []; },
    querySelector() { return null; }
  };
}

/* ------------------------------------------------------------------ fake Android */
/* Chrome on Android: ends the session after a silence, and on resume the new
   session's result indices START AGAIN AT ZERO. Some builds also replay the
   final phrase of the previous session. This models exactly that. */
class AndroidRecognition {
  constructor() {
    this.lang = ""; this.continuous = false;
    this.interimResults = false; this.maxAlternatives = 1;
    this.onresult = null; this.onend = null; this.onerror = null;
    AndroidRecognition.live = this;
  }
  start() { this.running = true; this._index = 0; }
  stop() { this.running = false; if (this.onend) this.onend(); }
  abort() { this.stop(); }

  /* Emit final phrases in the CURRENT session, indices from 0 upward. */
  say(...phrases) {
    const results = [];
    const startAt = this._index;
    phrases.forEach(p => {
      results.push({ 0: { transcript: p }, isFinal: true, length: 1 });
    });
    this._index += phrases.length;
    const all = [];
    for (let i = 0; i < startAt; i++) all.push({ 0: { transcript: "" }, isFinal: true });
    results.forEach(r => all.push(r));
    all.length = startAt + results.length;
    if (this.onresult) this.onresult({ resultIndex: startAt, results: all });
  }

  /* The user pauses; Android gives up and fires onend. app.js restarts it. */
  silence() { if (this.onend) this.onend(); }
}

/* ------------------------------------------------------------------ load app.js */
function loadApp() {
  const target = makeElement("textarea");
  const btn = makeElement("button");
  btn.parentNode = makeElement("div");

  const documentStub = {
    getElementById(id) { return id === "note" ? target : null; },
    createElement: makeElement,
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return null; },
    body: makeElement("body"),
    documentElement: makeElement("html")
  };

  const sandbox = {
    console,
    document: documentStub,
    addEventListener() {}, removeEventListener() {},
    navigator: { onLine: true },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    setTimeout, clearTimeout, setInterval, clearInterval,
    Event: function (t) { this.type = t; },
    SpeechRecognition: AndroidRecognition,
    SpeechSynthesisUtterance: function () {},
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;

  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(APP_JS, "utf8"), sandbox,
                  { filename: "app.js" });

  if (!sandbox.hmsVoice) throw new Error("hmsVoice was not defined by app.js");
  return { voice: sandbox.hmsVoice, target, btn };
}

/* ================================================================ THE BUG */
console.log("\n--- the reported bug: laptop fine, phone repeats words ---");
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;

  /* A laptop keeps ONE session: this always worked. */
  rec.say("the patient", "is waiting", "at the pharmacy", "please attend");
  eq("laptop (one unbroken session) transcribes correctly",
     target.value, "The patient is waiting at the pharmacy please attend");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;

  /* A PHONE breaks the same sentence across silences. This is what failed. */
  rec.say("the patient", "is waiting");
  rec.silence();
  rec.say("at the pharmacy");
  rec.silence();
  rec.say("please attend");
  eq("phone (broken by silences) transcribes the SAME text",
     target.value, "The patient is waiting at the pharmacy please attend");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;

  /* Android replaying the previous final on resume must not double it. */
  rec.say("the generator has failed");
  rec.silence();
  rec.say("the generator has failed", "and there is no budget");
  eq("a phrase replayed by Android on resume is not duplicated",
     target.value, "The generator has failed and there is no budget");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;

  /* But a REAL repetition by a human must survive. Swallowing it would be a
     worse bug than the one being fixed. */
  rec.say("no");
  rec.silence();
  rec.say("no I did not agree");
  eq("a genuine human repetition is NOT swallowed",
     target.value, "No no I did not agree");
}

/* ================================================================ PUNCTUATION */
console.log("\n--- the reported gap: comma, full-stop etc ---");
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("i waited three hours comma nobody told me why full stop");
  eq("spoken 'comma' and 'full stop' become real punctuation",
     target.value, "I waited three hours, nobody told me why.");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("why was i not attended to question mark");
  eq("spoken 'question mark' becomes ?",
     target.value, "Why was I not attended to?");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("the ward is dirty full stop please send someone full stop");
  eq("a new sentence is capitalised after a full stop",
     target.value, "The ward is dirty. Please send someone.");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("first point new line second point");
  eq("spoken 'new line' breaks the line",
     target.value, "First point\nSecond point");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  /* "full stop" must beat "stop", "question mark" must beat "mark". */
  rec.say("tell them to stop full stop");
  eq("the word 'stop' inside a sentence is left alone",
     target.value, "Tell them to stop.");
}
{
  const { voice, target, btn } = loadApp();
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("punctuation survives a phone pause comma");
  rec.silence();
  rec.say("and still works afterwards full stop");
  eq("punctuation still works across an Android restart",
     target.value, "Punctuation survives a phone pause, and still works afterwards.");
}

/* ================================================================ SAFETY */
console.log("\n--- it must not damage what is already in the box ---");
{
  const { voice, target, btn } = loadApp();
  target.value = "Typed by hand.";
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("then dictated");
  rec.silence();
  rec.say("across a pause");
  eq("text already typed is kept and appended to",
     target.value, "Typed by hand. Then dictated across a pause");
}
{
  const { voice, target, btn } = loadApp();
  target.setAttribute("maxlength", "20");
  voice.start(btn, "note");
  const rec = AndroidRecognition.live;
  rec.say("this sentence is far longer than the limit allows");
  check("a maxlength is still respected", target.value.length <= 20,
        "length " + target.value.length);
}

/* ================================================================ */
console.log("\n" + passed + " passed, " + failures.length + " failed");
process.exit(failures.length ? 1 : 0);
