"""Live page addresses for the patient assistant.

The hospital's web address can change (new host, new domain). We never
hard-code a site. We build the link from THIS request when we have one,
otherwise from the hospital's own public address setting.
"""
from __future__ import annotations

# endpoint, path, short label a patient can tap
PAGES = {
    "book": ("bookings.portal", "/book", "Book a visit"),
    "fasttrack": ("bookings.portal", "/book", "Book Fast Track"),
    "queue": ("queue.join_page", "/queue/join", "Get a number"),
    "complaint": ("complaints.portal", "/complaint", "Make a complaint"),
    "feedback": ("feedback.portal", "/feedback", "Rate your visit"),
    "book_status": ("bookings.portal_status", "/book/status", "Check a booking"),
    "complaint_status": ("complaints.portal_status", "/complaint/status",
                         "Check a complaint"),
    "welcome": ("main.patient_hub", "/welcome", "Hospital home"),
}

# What pages a recognised intent may honestly point at.
ACTION_PAGES = {
    "book": ("book", "fasttrack", "queue"),
    "fasttrack": ("fasttrack", "queue"),
    "queue": ("queue", "fasttrack"),
    "complaint": ("complaint",),
    "feedback": ("feedback",),
    "book_status": ("book_status",),
    "complaint_status": ("complaint_status",),
    "clinical": ("book",),
    "handoff": ("welcome",),
    "emergency": (),
    "welcome": ("welcome",),
}


def site_root() -> str:
    """The live site, no trailing slash. Changes with host and domain."""
    try:
        from flask import has_request_context, request
        if has_request_context() and request:
            root = (request.url_root or "").rstrip("/")
            if root:
                return root
    except Exception:                                    # noqa: BLE001
        pass
    try:
        from flask import current_app
        return (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    except Exception:                                    # noqa: BLE001
        return ""


def page_url(key: str) -> str:
    spec = PAGES.get(key)
    if not spec:
        return ""
    endpoint, path, _label = spec
    try:
        from flask import has_request_context, url_for
        if has_request_context():
            return url_for(endpoint, _external=True)
    except Exception:                                    # noqa: BLE001
        pass
    root = site_root()
    return f"{root}{path}" if root else path


def links_for(action: str | None) -> list[dict]:
    """[{href, label, key}] for an action we can actually serve."""
    keys = ACTION_PAGES.get(action or "", ())
    out = []
    seen = set()
    for key in keys:
        href = page_url(key)
        if not href or href in seen:
            continue
        seen.add(href)
        out.append({"href": href, "label": PAGES[key][2], "key": key})
    return out


def action_for_intent(intent: str | None) -> str | None:
    i = (intent or "").strip()
    if not i:
        return None
    if i in ("fast_track", "fasttrack") or i.endswith("_fast_track"):
        return "fasttrack"
    if i in ("book_appointment", "followup_book", "anc_book",
             "hours_clinic", "first_visit_steps", "first_visit_bring"):
        return "book"
    if i.endswith("_book"):
        return "book"
    if i in ("cancel_appointment", "check_appointment", "reschedule"):
        return "book_status"
    if i in ("complaint_start", "bill_dispute") or i.endswith("_complaint") \
            or i.endswith("_report_fraud"):
        return "complaint"
    if i == "complaint_status":
        return "complaint_status"
    if i in ("feedback", "feedback_start"):
        return "feedback"
    if i in ("queue_join", "queue"):
        return "queue"
    if i in ("emergency_general", "emergency_chest", "anc_danger",
             "labour_signs", "newborn_jaundice"):
        return "emergency"
    if i == "human_handoff":
        return "handoff"
    if i == "directions":
        return "welcome"
    return None
