# Patient pages — the master UX plan (NOT built yet — plan only)

Written 2026-09-14 in plain English a child can understand, as the owner
asked. Nothing here is code yet. When the owner says "go", we build it in
the order at the bottom, one small safe step at a time.

The idea in one sentence: **make every patient page feel like one calm,
friendly hospital that always answers, never shouts, and works on the
cheapest phone with the worst internet.**

---

## Step 1 — Walk in the patient's shoes first (watch, don't guess)

Before changing anything, we watch real patients use the pages (or read
their real complaints and the server logs). We write down every place they
pause, tap the wrong thing, or ask "what now?". That list becomes our
to-fix list.

*Why:* a designer who guesses is a decorator. A designer who watches is a
doctor — we treat real pains, not imagined ones.
*How we know it worked:* every later step points at something we actually
saw a real person struggle with.

## Step 2 — One page, one job (the room rule)

A house works because each room does one thing: kitchen cooks, bedroom
sleeps. Same for pages:

| Page | Its ONE job (say it in 3 words) |
|---|---|
| Welcome | choose your door |
| Join-a-queue | get my number |
| Booking | pick day, time |
| Emergency | go to A&E |
| Complaint | tell what went wrong |
| Feedback | rate my visit |
| Tracker | where am I now |

If a page ever starts doing two jobs, we split it into two pages.
*How we know it worked:* a child can name each page's job in three words.

## Step 3 — One box of LEGO for every page (finish the design system)

We already started this (the shared `.pp-*` blocks). Now we finish the box
so EVERY page is built from the same pieces: buttons, cards, chips,
banners — plus four new pieces pages still improvise today:

- **waiting picture** (a gentle grey outline that shimmers while data loads),
- **nothing-here-yet picture** (a friendly empty state),
- **oops picture** (a kind error state that says how to fix it),
- **all-done picture** (a warm success state that says what happens next).

*Why:* same blocks = same feel = the hospital feels like ONE place, and a
fix made once fixes every page.
*How we know it worked:* no page has its own private colours or one-off
boxes left in the code.

## Step 4 — Thumb-first layout (the one-hand rule)

Most patients hold the phone in ONE hand while carrying a bag, a child, or
a file folder. So everything important lives where the thumb already rests:
big buttons at the bottom, one column top to bottom, letters big enough to
read in bright sunlight, nothing sideways-scrolling.
*How we know it worked:* every page can be finished with one thumb, no
stretching, no pinching, no sideways scroll.

## Step 5 — The page always answers back (the nod rule)

When a person taps, the page must nod: the button moves or changes colour
in a blink. When the page is fetching something, it shows the gentle
shimmer outline (never a spinning wheel of nothing). When it finishes, it
shows a big friendly tick and the next step.
*Why:* silence feels broken. A nod feels like a person listening.
*How we know it worked:* no tap ever feels ignored; no page ever looks
frozen, even on a slow day.

## Step 6 — Forms that hold your hand

One question at a time where we can. An example inside every box
("e.g. 08012345678"). We check while you type — phone too short? we say so
right there, kindly, before you press the big button. If anything goes
wrong we KEEP everything you typed and point at the one box to fix, in
plain words, never a code.
*How we know it worked:* nobody ever re-types their name after an error.

## Step 7 — Every page can talk and listen

A small speaker button beside every instruction reads it aloud in the
patient's own language (English, Yorùbá, Hausa, Igbo). The words stay short,
like a friend talking, not a form shouting.
*Why:* some patients cannot read well, or cannot read at all. Listening is
care too.
*How we know it worked:* a person who cannot read can still join the queue
or book a visit by listening only.

## Step 8 — A human is always one tap away

The help card with the real phone numbers stays at the bottom of every
page, and every page carries one line: "Prefer a human? Call us." The red
emergency button is always there but never shouts over the page.
*How we know it worked:* from any page, help is one tap — never a hunt.

## Step 9 — Kind to slow internet and old phones

Pages stay feather-light: tiny pictures, no heavy libraries, words first.
If the connection is bad we SAY so kindly ("Slow connection — your page is
coming") instead of looking broken. Checking a booking or a queue number
works even with no internet at all.
*How we know it worked:* pages open in about 3 seconds on a cheap phone on
a bad network, and offline checks still work.

## Step 10 — Remember me kindly

The site remembers your language. A returning patient is welcomed back by
seeing THEIR thing first — last booking, live queue number — with no
password, ever, for patients.
*How we know it worked:* a returning patient reaches their thing in one tap.

## Step 11 — Calm, honest, trustworthy

Soft colours on calm days; red only for true emergencies. Privacy is said
in one short line exactly where we ask for a name or phone — not buried.
Errors never blame: "That number looks a little short — shall we check it
together?"
*How we know it worked:* reading any page aloud to a worried parent sounds
kind, not clinical.

## Step 12 — The grandma test, then small safe steps

The final exam: a grandma, an old cheap phone, bright sunlight, alone. She
books a visit and checks her number. If she smiles, we ship.
And we ship in SMALL steps — one page at a time, each guarded by the
automatic tests, old look stays until the new one proves better. We watch
four numbers forever: time-to-book, taps-to-book, how many people give up
halfway, how many call the help desk confused.

---

## The order we will build (when the owner says go)

1. Welcome hub (the front door) — steps 4, 5, 10 first, it sets the tone.
2. Join-a-queue + live tracker — steps 5, 6, 7 (the busiest door).
3. Booking (both doors) — steps 5, 6, 11.
4. Emergency — steps 4, 7, 8 (calm under panic).
5. Complaint + feedback — steps 3, 6, 11 (where trust is won or lost).
6. Status / thank-you pages — steps 3, 5, 10 (the goodbye that brings
   people back).

Each page: look at it together → build → tests → show the owner → next.

## What I need from the owner

Just two words when ready: **"go"** — and optionally which page to start
with (or trust the order above). Nothing is built until then.
