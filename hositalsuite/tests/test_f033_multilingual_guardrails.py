"""F-033: the AI clinical guardrails must protect all five supported languages.

The pre-model gate (engine.CLINICAL_SEEK) and the post-model leak check
(ai._CLINICAL_LEAK) were English-only, while the system prompt invites
patients to write in English, Nigerian Pidgin, Yoruba, Hausa or Igbo. A
clinical question in any of the four other languages used to sail to the
model unguarded. These tests pin the fix: both gates recognise the dangerous
patterns in every supported language, matched with or without diacritics,
and still leave harmless conversation alone.
"""
from __future__ import annotations

import pytest

from app.chatbot.ai import _looks_clinical
from app.chatbot.engine import is_clinical_seek


@pytest.mark.parametrize(
    "text",
    [
        # English regressions
        "what is wrong with me",
        "prescribe something for me",
        # Nigerian Pidgin
        "Wetin dey wrong with me?",
        "I get malaria?",
        "Which tablet i go take?",
        "Abeg which medicine wey i go drink",
        # Yoruba — with and without diacritics
        "Kí ni oògùn fún ìbà?",
        "oogun fun iba",
        "Ṣe mo ní ìbà?",
        "Kí ló ń ṣe mi?",
        # Hausa — including hooked letters that have no ASCII decomposition
        "Wane magani na ciwon kai?",
        "Ko ina da zazzabin malaria?",
        "Rubuta magani mini",
        "Yawan kwaya nawã?",            # dosage — schwa/hooked orthography
        # Igbo
        "O nwere m ọria?",
        "Gini mere m? Kedu ogwu m ga-eji?",
        "Dee ogwu nye m",
    ],
)
def test_clinical_seek_caught_in_every_language(text):
    assert is_clinical_seek(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Where is the cafeteria?",
        "What time does the lab open?",
        "Ẹ kú àṣálẹ̀",                       # Yoruba greeting
        "Ina kwana lafiya?",                # Hausa greeting
        "Biko kedụ ebe ụlọ mposi dị?",      # Igbo: where is the toilet
        "I wan book appointment tomorrow",  # Pidgin booking
        "Book me a follow-up at the clinic next Tuesday",
    ],
)
def test_benign_messages_still_pass(text):
    assert not is_clinical_seek(text), text


@pytest.mark.parametrize(
    "text",
    [
        # English regressions
        "you may have typhoid",
        "take paracetamol 500mg twice daily",
        # Localized leaks
        "You get malaria o",                       # Pidgin
        "O ní ìbà — mu oògùn meji lọ́sọ̀sẹ̀",          # Yoruba diagnosis + dosage
        "Kana da zazzabin malaria, sha kwayoyi",   # Hausa
        "Ị nwere ọria sicklẹ",                     # Igbo
    ],
)
def test_model_leak_caught_in_every_language(text):
    assert _looks_clinical(text), text


@pytest.mark.parametrize(
    "text",
    [
        "The lab is on the right, ẹ jọ̀wọ́",        # localized safe directions
        "Our A&E dey open 24/7",                   # Pidgin safe redirect
        "Reception will direct you to Room 3",
    ],
)
def test_safe_replies_are_not_flagged_as_leaks(text):
    assert not _looks_clinical(text), text
