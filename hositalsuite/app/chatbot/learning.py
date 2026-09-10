"""Learning from real conversations — proposing, never silently changing.

THE ONE DECISION THAT SHAPES THIS WHOLE FILE
--------------------------------------------
A hospital assistant must NEVER teach itself what to say to patients.

It is tempting: mine the chats, spot the gaps, write new answers automatically,
watch the accuracy climb. But an answer nobody approved is an answer nobody is
accountable for, and this app talks to sick people about where to go and what
to pay. One auto-generated sentence about a fee or a department could send a
patient to the wrong place with confidence.

So the system LEARNS CONTINUOUSLY and PROPOSES. A human approves with one tap.
The learning is real; the accountability stays human. And because approval is
one tap rather than a form, it actually happens.

WHAT IT LEARNS, IN ORDER OF VALUE
---------------------------------
1. MISSING WORDS (the biggest win, and the safest)
   Five patients ask "abeg where I go chop" and get nothing, but the hospital
   already HAS a cafeteria answer. Nothing needs writing — the answer exists,
   it simply cannot be found. Proposing those words as new triggers improves
   accuracy without changing a single word a patient reads.

2. MISSING ANSWERS
   Questions asked repeatedly that match nothing at all. The system cannot
   write the answer — it does not know what the hospital's policy is — but it
   can say "eleven people asked about parking this month" and let a human
   write two sentences once.

3. ANSWERS THAT ARE FAILING
   Articles collecting thumbs-down. The words are wrong, or the answer is
   right but reads badly. A human must read and rewrite; the system only
   points.

4. COIN-FLIP MATCHES
   Two articles scored almost the same, so the winner was luck. These are the
   silent failures — the patient gets a confident answer to a different
   question. Worth a human eye before somebody complains.

5. CORRECTIONS FROM STAFF
   Notes typed straight into the chat ("that is wrong, always say X").

NOT AN EMR, AND NOT A SURVEILLANCE TOOL
---------------------------------------
This reads what patients typed to a chatbot in order to answer them better.
It never stores who they are, and the review screen shows the QUESTION, never
a name or a phone number.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import timedelta

from ..models import (ChatFeedback, ChatMessage, ChatSession, KnowledgeArticle,
                      db, now_naive)

# How many times a thing must happen before it is worth a human's attention.
# Three is deliberate: one is an accident, two is a coincidence, three is a
# pattern. Set higher and real gaps sit unnoticed for weeks.
MIN_OCCURRENCES = 3

# A match this close to the runner-up was luck, not understanding.
COIN_FLIP_RATIO = 1.15

# Words that carry no meaning on their own — never proposed as triggers.
_STOPWORDS = {
    "a", "about", "am", "an", "and", "any", "are", "as", "at", "be", "been",
    "but", "by", "can", "could", "did", "do", "does", "for", "from", "get",
    "give", "go", "going", "good", "got", "had", "has", "have", "he", "her",
    "here", "him", "his", "how", "i", "if", "in", "is", "it", "its", "just",
    "know", "like", "me", "more", "my", "need", "no", "not", "now", "of",
    "on", "one", "or", "our", "out", "please", "pls", "she", "should", "so",
    "some", "tell", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "to", "up", "us", "want", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with", "would",
    "you", "your", "abeg", "sir", "ma", "madam", "hello", "hi", "thanks",
}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower())
            if len(w) > 2 and w not in _STOPWORDS]


def _stem(word: str) -> str:
    """Crudely reduce a word to its root so related questions group together.

    "park", "parking" and "parked" are the same question to a patient, but
    three different strings to a computer — so four people asking about
    parking looked like four unrelated one-offs and were never reported.

    Deliberately simple. A real stemmer would be more accurate and would also
    be a dependency, a download and something else to break on a free-tier
    server. This handles English plurals and -ing endings, which is what
    actually shows up in these questions.
    """
    w = (word or "").lower()
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            base = w[:-len(suffix)]
            if suffix == "ies":
                base += "y"
            return base
    return w


def _phrase(text: str) -> str:
    """A short, readable version of what the patient typed."""
    return " ".join((text or "").split())[:160]


def _since(days: int):
    return now_naive() - timedelta(days=days)


# Words a patient is likely to use, mapped to the vocabulary the answers are
# written in. Deliberately small and hand-checked: this decides which existing
# answer a failed question gets attached to, so a wrong entry here would
# propose a wrong (though still human-approved) improvement.
_MEANING_HINTS = {
    "chop": ("cafeteria", "food", "eat", "meal"),
    "belle": ("pregnan", "antenatal", "anc"),
    "sick": ("unwell", "clinic", "doctor"),
    "money": ("bill", "pay", "cost", "fee"),
    "kudi": ("bill", "pay", "cost"),
    "waka": ("direction", "find", "locate"),
    "shayo": ("water", "drink"),
    "wahala": ("complain", "problem", "issue"),
    "abeg": (),
}


def _closest_by_meaning(articles, text: str):
    """Find an article whose ANSWER TEXT is about what the patient asked.

    Used only when no article shares a trigger word. Matching against the
    answer body catches the case where a patient and an answer use different
    vocabularies for the same thing — which is most of Pidgin.
    """
    words = set(_words(text))
    if not words:
        return None
    expanded = set(words)
    for w in words:
        expanded.update(_MEANING_HINTS.get(w, ()))

    best, best_hits = None, 0
    for a in articles:
        body = ((a.en or "") + " " + (a.pidgin or "")).lower()
        if not body:
            continue
        hits = sum(1 for w in expanded if len(w) > 3 and w in body)
        if hits > best_hits:
            best, best_hits = a, hits
    # Two independent hits, so one common word cannot drag a question to a
    # completely unrelated answer.
    return best if best_hits >= 2 else None


# ------------------------------------------------------------------ 1. words
def missing_words(org_id, days: int = 30, limit: int = 20) -> list[dict]:
    """Questions that failed, whose words point at an answer we already have.

    THE HIGHEST-VALUE, LOWEST-RISK LEARNING IN THE SYSTEM. The answer already
    exists and is already approved — it simply could not be found. Approving
    one of these changes nothing a patient reads; it only makes an existing
    answer reachable.
    """
    from .engine import _articles_for, _score, _norm

    rows = (db.session.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.org_id == org_id,
                    ChatMessage.role == "user",
                    ChatMessage.unanswered.is_(True),
                    ChatMessage.at >= _since(days))
            .limit(2000).all())
    if not rows:
        return []

    articles = _articles_for(org_id)
    if not articles:
        return []

    # For each failed question, find the article that came CLOSEST. If a real
    # subject word from the question is missing from that article's triggers,
    # that word is the reason the patient got nothing.
    proposals: dict[tuple, dict] = {}
    for msg in rows:
        if msg.intent == "teaching_note":
            continue
        text = _norm(msg.text)
        best, best_score = None, 0
        for a in articles:
            sc = _score(a, text)
            if sc > best_score:
                best, best_score = a, sc
        if best is None or best_score < 1:
            # No article shares a WORD with this question. That is usually a
            # genuinely missing answer — but not always: a patient writing in
            # Pidgin ("abeg where I go chop") shares no English word with the
            # cafeteria answer, even though the answer is exactly right.
            #
            # So before giving up, look for an article whose EXISTING TEXT
            # already talks about this. The words a patient uses and the words
            # an answer is written in are different vocabularies; the answer
            # body is the bridge between them.
            best = _closest_by_meaning(articles, msg.text)
            if best is None:
                continue                    # genuinely a missing ANSWER
            best_score = 1

        existing = {w for kw in (best.keywords or "").splitlines()
                    for w in _words(kw)}
        for word in _words(msg.text):
            if word in existing:
                continue
            key = (best.id, word)
            entry = proposals.setdefault(key, {
                "article_id": best.id, "intent": best.intent,
                "category": best.category, "word": word,
                "count": 0, "examples": []})
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append(_phrase(msg.text))

    out = [p for p in proposals.values() if p["count"] >= MIN_OCCURRENCES]
    out.sort(key=lambda p: -p["count"])
    return out[:limit]


# ------------------------------------------------------------------ 2. answers
def missing_answers(org_id, days: int = 30, limit: int = 20,
                    exclude_words: set | None = None) -> list[dict]:
    """Things patients keep asking that we have no answer for at all.

    The system cannot write these — it does not know the hospital's policy on
    parking or visiting hours. It can only say how many people asked, so two
    sentences written once serve everybody who asks next month.
    """
    rows = (db.session.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.org_id == org_id,
                    ChatMessage.role == "user",
                    ChatMessage.unanswered.is_(True),
                    ChatMessage.at >= _since(days))
            .limit(2000).all())

    # Group by the meaningful words they share, so "where can I park",
    # "is there parking" and "car park space?" become one item, not three.
    groups: dict[frozenset, dict] = {}
    for msg in rows:
        if msg.intent == "teaching_note":
            continue
        raw = _words(msg.text)
        words = frozenset(_stem(w) for w in raw)
        if not words:
            continue
        match = None
        for key in groups:
            overlap = len(key & words)
            if overlap and overlap >= min(len(key), len(words)) * 0.5:
                match = key
                break
        if match is None:
            groups[words] = {"topic": " / ".join(sorted(words)[:3]),
                             "count": 1, "examples": [_phrase(msg.text)],
                             "words": set(words)}
        else:
            g = groups[match]
            g["count"] += 1
            g["words"] |= words
            if len(g["examples"]) < 4:
                g["examples"].append(_phrase(msg.text))

    out = [g for g in groups.values() if g["count"] >= MIN_OCCURRENCES]
    # Anything already proposed as a missing WORD is not a missing ANSWER —
    # the answer exists. Showing it in both lists would have the founder write
    # a duplicate answer for something one tap already fixes.
    if exclude_words:
        out = [g for g in out
               if not (g["words"] & exclude_words)]
    for g in out:
        g["suggested_keywords"] = sorted(g["words"])[:12]
        g.pop("words", None)
    out.sort(key=lambda g: -g["count"])
    return out[:limit]


# ------------------------------------------------------------------ 3. failing
def failing_answers(org_id, days: int = 60, limit: int = 15) -> list[dict]:
    """Answers collecting thumbs-down. A human must read and rewrite these."""
    rows = (db.session.query(ChatFeedback)
            .filter(ChatFeedback.at >= _since(days),
                    ChatFeedback.article_id.isnot(None))
            .limit(4000).all())
    tally: dict[int, dict] = defaultdict(lambda: {"up": 0, "down": 0})
    for f in rows:
        tally[f.article_id][f.rating] = tally[f.article_id].get(f.rating, 0) + 1

    out = []
    for aid, counts in tally.items():
        down, up = counts.get("down", 0), counts.get("up", 0)
        if down < MIN_OCCURRENCES or down <= up:
            continue
        art = db.session.get(KnowledgeArticle, aid)
        if art is None:
            continue
        out.append({"article_id": aid, "intent": art.intent,
                    "category": art.category,
                    "preview": _phrase(art.en), "down": down, "up": up})
    out.sort(key=lambda r: -r["down"])
    return out[:limit]


# ------------------------------------------------------------------ 4. coin flips
def coin_flip_matches(org_id, days: int = 30, limit: int = 15) -> list[dict]:
    """Answers that only just beat a rival — the winner was luck.

    These are the SILENT failures. The patient gets a confident answer to a
    slightly different question and never presses thumbs-down, because it
    looks like an answer. This is how "can I bring a cooking pot" became the
    weapons policy.
    """
    from .engine import _articles_for, _score, _norm

    rows = (db.session.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.org_id == org_id,
                    ChatMessage.role == "user",
                    ChatMessage.unanswered.is_(False),
                    ChatMessage.article_id.isnot(None),
                    ChatMessage.at >= _since(days))
            .limit(1500).all())
    articles = _articles_for(org_id)
    if not articles:
        return []

    seen: dict[tuple, dict] = {}
    for msg in rows:
        text = _norm(msg.text)
        scored = sorted(((_score(a, text), a) for a in articles),
                        key=lambda p: -p[0])[:2]
        if len(scored) < 2 or scored[1][0] <= 0:
            continue
        top, runner = scored[0], scored[1]
        if top[0] <= runner[0] * COIN_FLIP_RATIO:
            key = (top[1].id, runner[1].id)
            entry = seen.setdefault(key, {
                "winner": top[1].intent, "runner_up": runner[1].intent,
                "count": 0, "examples": []})
            entry["count"] += 1
            if len(entry["examples"]) < 3:
                entry["examples"].append(_phrase(msg.text))

    out = [v for v in seen.values() if v["count"] >= 2]
    out.sort(key=lambda v: -v["count"])
    return out[:limit]


# ------------------------------------------------------------------ 5. staff notes
def corrections(org_id, days: int = 60, limit: int = 20) -> list[dict]:
    """Corrections typed straight into the chat by staff or the founder."""
    rows = (db.session.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.org_id == org_id,
                    ChatMessage.intent == "teaching_note",
                    ChatMessage.at >= _since(days))
            .order_by(ChatMessage.at.desc()).limit(limit).all())
    return [{"id": m.id, "text": _phrase(m.text), "at": m.at} for m in rows]


# ------------------------------------------------------------------ applying
def add_keyword(org_id, article_id: int, word: str, user_id=None) -> tuple[bool, str]:
    """Teach an EXISTING approved answer one new trigger word.

    The answer text is untouched — only its findability changes. This is the
    only kind of learning applied to a live answer, and even this needs a tap.
    """
    word = (word or "").strip().lower()
    if not word or len(word) < 3:
        return False, "That word is too short to be a useful trigger."
    art = db.session.get(KnowledgeArticle, article_id)
    if art is None:
        return False, "That answer no longer exists."
    if art.org_id not in (None, org_id):
        return False, "That answer belongs to another hospital."

    existing = [k.strip() for k in (art.keywords or "").splitlines() if k.strip()]
    if word in {e.lower() for e in existing}:
        return False, "That word is already a trigger for this answer."

    # A tenant must not edit the shared global library in place. Adding to the
    # global copy would change every hospital's assistant at once.
    if art.org_id is None:
        clone = KnowledgeArticle(
            org_id=org_id, category=art.category, intent=art.intent,
            keywords="\n".join(existing + [word]),
            en=art.en, pidgin=art.pidgin, yo=art.yo, ha=art.ha, ig=art.ig,
            cta=art.cta, clinical_safe=art.clinical_safe, scope="tenant",
            status="approved", submitted_by=user_id)
        db.session.add(clone)
        return True, (f"Learned. This hospital's copy of \u201c{art.intent}\u201d "
                      f"now also answers to \u201c{word}\u201d.")

    art.keywords = "\n".join(existing + [word])
    return True, f"Learned. \u201c{art.intent}\u201d now also answers to \u201c{word}\u201d."


def summary(org_id, days: int = 30) -> dict:
    """The headline for the review screen."""
    words = missing_words(org_id, days)
    return {
        "missing_words": len(words),
        "missing_answers": len(missing_answers(
            org_id, days, exclude_words={w["word"] for w in words})),
        "failing": len(failing_answers(org_id)),
        "coin_flips": len(coin_flip_matches(org_id, days)),
        "corrections": len(corrections(org_id)),
    }


def accuracy(org_id, days: int = 30) -> dict:
    """How well the assistant is actually doing — the number to watch."""
    rows = (db.session.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.org_id == org_id,
                    ChatMessage.role == "user",
                    ChatMessage.at >= _since(days))
            .limit(5000).all())
    total = len(rows)
    if not total:
        return {"asked": 0, "answered": 0, "percent": 0, "reliable": False}
    answered = sum(1 for m in rows if not m.unanswered)
    return {
        "asked": total,
        "answered": answered,
        "percent": round(answered / total * 100),
        # Under 20 questions a percentage is noise, not a measurement.
        "reliable": total >= 20,
    }
