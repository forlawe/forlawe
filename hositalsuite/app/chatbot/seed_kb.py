"""Seed / sync the GLOBAL master dialogue library (org_id NULL).

Idempotent per-intent: on every boot it ADDS any global intent that is missing,
without touching existing rows (so tenant edits, thumbs and hit-counts survive,
and new dialogues ship to existing deployments automatically).
"""
from __future__ import annotations

ALL_MODULES = None


# ---------------------------------------------------------------------------
# F-041: one trigger phrase, one owner.
#
# The shipped library contained exact duplicate triggers claimed by different
# intents ("audit log" by reports AND security headers; "data protection" by
# NDPA rights AND the privacy policy; the bare department name re-listed in
# every sub-intent of that department). The scorer breaks such exact ties by
# list order, so the winner was an accident of file layout — ambiguous and
# silently resolved, exactly what learning.py's coin-flip detector exists to
# catch. Instead of hand-editing ~1,200 duplicates across 9 modules, the
# aggregation point below enforces single ownership on every seed/refresh:
#
#   * a trigger listed in _TRIGGER_WINNER goes to the intent whose ANSWER
#     actually serves that question (deliberate, reviewed decisions); and
#   * every other duplicate goes to the FIRST intent that declares it in
#     file order — for department words that is always the department's
#     overview intent ("_what"), which is the right general answer.
#
# Sub-intents keep their SPECIFIC triggers ("laboratory fasting", "hims
# file number") — only the ambiguous shared words are de-duplicated.
_TRIGGER_WINNER = {
    "where is lab": "lab_how",
    "where is pharmacy": "pharmacy_how",
    "where is billing": "billing_how",
    "vapid": "vapid_setup",
    "audit log": "reports_archive",
    "how long will i wait": "queue_wait_time",
    "estimated wait": "queue_wait_time",
    "opera mini": "feature_phone",
    "how to triage": "how_to_triage",
    "call room queue": "how_to_call_patient",
    "how to assign role": "how_to_manage_users",
    "slow internet": "slow_internet",
    "data protection": "ndpa_rights",
    "baby not moving": "obstetrics_gynaecology_baby_movement",
    "lab": "laboratory_what",
    "laboratory": "laboratory_what",
    "wheelchair": "special_needs",
    "hims": "health_information_managemen_what",
    "hospital number": "health_information_managemen_file_number",
    "billing": "finance_accounts_what",
    "hmo": "finance_accounts_nhis",
    "annual leave": "leave_types",
    "security": "security_what",
    "visiting hours": "visiting",
    "journalist": "public_affairs_media",
    "dirty bed sheet": "laundry_dirty_linen",
    "when will i be discharged": "admission_discharge",
    "infection control": "nursing_services_ipc",
}


def _norm_trigger(kw: str) -> str:
    return " ".join((kw or "").lower().split())


def dedupe_triggers(entries: list[dict]) -> list[dict]:
    """Return the entries with every trigger phrase owned by ONE intent."""
    first_owner: dict[str, str] = {}
    for e in entries:
        for kw in e.get("kw", []):
            first_owner.setdefault(_norm_trigger(kw), e["intent"])
    for e in entries:
        kept: list[str] = []
        seen_here: set[str] = set()
        for kw in e.get("kw", []):
            key = _norm_trigger(kw)
            if key in seen_here:
                continue
            winner = _TRIGGER_WINNER.get(key) or first_owner[key]
            if winner == e["intent"]:
                seen_here.add(key)
                kept.append(kw)
        if len(kept) != len(e.get("kw", [])):
            e["kw"] = kept
    return entries


def _all_kb():
    from . import (kb_core, kb_departments_full, kb_depts, kb_extra, kb_extended,
                   kb_part5, kb_part6, kb_part7, kb_app_master)
    from . import kb_mental_health_draft
    entries = (
        list(kb_core.KB) + list(kb_depts.KB) + list(kb_extra.KB) + list(kb_extended.KB)
        + list(kb_part5.KB) + list(kb_part6.KB) + list(kb_part7.KB)
        + list(kb_departments_full.KB) + list(kb_app_master.KB)
    )
    # F-043: Mental Health dialogue ships only after clinical tone review —
    # see kb_mental_health_draft's docstring before flipping _REVIEWED.
    if getattr(kb_mental_health_draft, "_REVIEWED", False):
        entries = entries + list(kb_mental_health_draft.KB)
    return dedupe_triggers(entries)


def seed_global_kb(app, quiet: bool = False) -> int:
    from ..models import KnowledgeArticle, db
    with app.app_context():
        existing = {a.intent: a for a in db.session.query(KnowledgeArticle)
                    .filter_by(org_id=None).all()}
        added = updated = 0
        for entry in _all_kb():
            row = existing.get(entry["intent"])
            if row is None:
                db.session.add(KnowledgeArticle(
                    org_id=None, scope="global", status="approved",
                    category=entry["cat"], intent=entry["intent"],
                    keywords="\n".join(entry["kw"]),
                    en=entry["en"], pidgin=entry.get("pcm"), yo=entry.get("yo"),
                    ha=entry.get("ha"), ig=entry.get("ig"), cta=entry.get("cta")))
                added += 1
                continue
            # REFRESH existing global rows when the shipped library changes.
            # Previously we skipped them entirely, so improved wording and NEW
            # TRIGGERS never reached a deployed hospital — a fix could be
            # written, tested, deployed, and still not work in production.
            # Tenant-authored rows (org_id set) are never touched.
            new_kw = "\n".join(entry["kw"])
            changed = (row.keywords != new_kw or row.en != entry["en"]
                       or row.cta != entry.get("cta")
                       or row.pidgin != entry.get("pcm"))
            if changed:
                row.keywords = new_kw
                row.en = entry["en"]
                row.pidgin = entry.get("pcm")
                row.yo = entry.get("yo") or row.yo
                row.ha = entry.get("ha") or row.ha
                row.ig = entry.get("ig") or row.ig
                row.cta = entry.get("cta")
                row.category = entry["cat"]
                updated += 1
        if added or updated:
            db.session.commit()
        if not quiet and (added or updated):
            kws = sum(len(e["kw"]) for e in _all_kb())
            print(f"[KB] synced +{added} new / {updated} updated global intents "
                  f"(library now {len(_all_kb())} intents / {kws} triggers)")
        return added + updated


def library_stats(app) -> dict:
    from ..models import KnowledgeArticle, db
    with app.app_context():
        rows = db.session.query(KnowledgeArticle).filter_by(org_id=None).all()
        return {"intents": len(rows),
                "triggers": sum(len(a.keywords.splitlines()) for a in rows)}
