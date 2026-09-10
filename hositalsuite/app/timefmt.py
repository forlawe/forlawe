"""How long something took — one clock for every screen and every voice.

Patients and staff were seeing a pile of minutes (256m). That is hard to
read. We always show hours:minutes, so 154 minutes is 2:34m and 1,465
minutes is 24:25m.

Spoken lines stay in words: "2 hours 34 minutes".

Privacy helpers: mask phone, first name only — NDPA compliance, no leak.
"""
from __future__ import annotations


def mask_phone(phone: str | None) -> str:
    """Privacy: 08012345678 → 080****5678, +2348012345678 → +234****5678.

    Shows first 3 and last 4, masks middle. If too short, masks all but last 2.
    Empty → —. Used in staff lists so junior staff don't see full numbers.
    Admins can still see full via direct view if needed, but template uses
    this filter by default for privacy.
    """
    if not phone:
        return "—"
    p = str(phone).strip()
    if len(p) <= 4:
        return "****"
    if len(p) <= 7:
        return p[:2] + "****" + p[-2:]
    return p[:3] + "****" + p[-4:]


def first_name_only(full_name: str | None) -> str:
    """Privacy: 'Folake Abatan' → 'Folake', 'Mr Tunde Ojo' → 'Tunde'.

    Strips titles, returns first meaningful name. For TV and public screens.
    """
    if not full_name:
        return "Patient"
    s = str(full_name).strip()
    for title in ("Mr ", "Mrs ", "Ms ", "Miss ", "Dr ", "Chief ", "Alhaji ", "Alhaja ", "Pastor "):
        if s.lower().startswith(title.lower()):
            s = s[len(title):].strip()
    parts = s.split()
    if not parts:
        return "Patient"
    return parts[0]


def privacy_initials(full_name: str | None) -> str:
    """Privacy: 'Folake Abatan' → 'F.A.' for very public lists."""
    if not full_name:
        return "P."
    parts = [p for p in str(full_name).strip().split() if p]
    if not parts:
        return "P."
    if len(parts) == 1:
        return parts[0][0].upper() + "."
    return f"{parts[0][0].upper()}.{parts[-1][0].upper()}."


def _minutes(value) -> int | None:
    if value is None or value == "":
        return None
    # Jinja Undefined (when a key is missing) must not crash the page — show —
    try:
        if isinstance(value, str) and value.strip() in ("", "—", "-"):
            return None
        n = int(round(float(value)))
    except Exception:
        return None
    return max(0, n)


def fmt_hm(value) -> str:
    """Compact clock: 154 → '2:34m', 45 → '0:45m', unknown → '—'."""
    n = _minutes(value)
    if n is None:
        return "—"
    hours, mins = divmod(n, 60)
    return f"{hours}:{mins:02d}m"


def say_hm(value) -> str:
    """Spoken / prose clock: 154 → '2 hours 34 minutes'."""
    n = _minutes(value)
    if n is None:
        return "—"
    if n == 0:
        return "0 minutes"
    hours, mins = divmod(n, 60)
    parts: list[str] = []
    if hours:
        parts.append("1 hour" if hours == 1 else f"{hours} hours")
    if mins:
        parts.append("1 minute" if mins == 1 else f"{mins} minutes")
    return " ".join(parts)
