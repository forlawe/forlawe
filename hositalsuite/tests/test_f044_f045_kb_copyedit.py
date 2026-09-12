"""F-044/F-045: KB copyedit standards, kept honest by tests.

F-044 — no capitalised word after a mid-sentence em-dash in patient-facing
answers (the old "Absolutely — You can book" quirk). Proper nouns, "I", and
ALL-CAPS labels are exempt.

F-045 — the intensifiers "genuinely / absolutely / honestly" appear rarely
enough that repeat patients won't notice a tic (was ~1 in 13 department
entries; now a handful across the whole library, with varied wording).
"""
from __future__ import annotations

import re

EXEMPT = {"I", "Accident", "Records", "Reception", "Self", "Lab", "Apple",
          "Your", "Hims", "A", "The"}


def test_no_mid_sentence_capital_after_emdash():
    from app.chatbot.seed_kb import _all_kb
    quirks = []
    for e in _all_kb():
        for txt in (e["en"], e.get("pcm") or ""):
            for m in re.finditer(r"[a-z] — ([A-Z][a-z]+)", txt):
                word = m.group(1)
                if word not in EXEMPT and not word.isupper():
                    quirks.append((e["intent"], m.group(0)))
    assert not quirks, quirks


def test_intensifier_density_is_low_and_varied():
    from app.chatbot.seed_kb import _all_kb
    counts = {"genuinely": 0, "absolutely": 0, "honestly": 0}
    for e in _all_kb():
        blob = (e["en"] + " " + (e.get("pcm") or "")).lower()
        for w in counts:
            counts[w] += len(re.findall(rf"\b{w}\b", blob))
    total = sum(counts.values())
    assert total <= 12, counts                       # was 34 across the library
    assert counts["genuinely"] <= 3, counts          # the dominant tic, broken up
