"""End-to-end check of the two booking doors, run against a LIVE server.

This is the manual test issue #1 asked for: "verify by manually testing both
/book and /book/fast-track end to end, not just reading the code".

It does what a real patient's browser does — GET the page, keep only the fields
that page actually rendered, POST them back — and then reads the rows out of
the database to see what was really stored. It also tries to sneak a premium
department through the free door.

Usage:
    # 1. seed a database and start the app
    SECRET_KEY=x DATABASE_URL=sqlite:///data/e2e.db python -c \
        "from app import create_app; from app.seeddata import seed_data; \
         seed_data(create_app(), announce=False)"
    SECRET_KEY=x DATABASE_URL=sqlite:///data/e2e.db PORT=8078 \
        gunicorn --bind 0.0.0.0:8078 --workers 1 --threads 4 "app:create_app()"

    # 2. run this against it
    python tools/e2e_booking_doors.py http://127.0.0.1:8078 data/e2e.db

Exits non-zero if any expectation fails.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import date, timedelta

import requests
from html import unescape

SESSION = requests.Session()   # keeps the CSRF cookie between GET and POST
EXPECTED = {
    "/book": {"is_fast_track": False},
    "/book/fast-track": {"is_fast_track": True},
}


def rendered_fields(html: str) -> set[str]:
    """Names of the form controls the page rendered (not the <meta name=> tags)."""
    names = set()
    for tag in re.findall(r"<(?:input|select|textarea)\b[^>]*>", html):
        m = re.search(r'name="([^"]+)"', tag)
        if m:
            names.add(m.group(1))
    return names


def hidden_inputs(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", html):
        if 'type="hidden"' not in tag:
            continue
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[name.group(1)] = value.group(1) if value else ""
    return out


def options(html: str, field: str) -> list[tuple[str, str]]:
    """(value, label) pairs of a <select>, in page order."""
    m = re.search(rf'<select[^>]*name="{field}"[^>]*>(.*?)</select>', html, re.S)
    if not m:
        return []
    return [(v, " ".join(unescape(lab).split()))
            for v, lab in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)', m.group(1))]


def book(base: str, door: str, *, label: str, drop: tuple[str, ...] = (),
         force: dict[str, str] | None = None) -> dict:
    """GET a door, fill in only what it rendered, POST it, report the outcome."""
    html = SESSION.get(base + door).text
    data = hidden_inputs(html)
    data.update(force or {})

    depts = [o for o in options(html, "department_id") if o[0]]
    if "department_id" not in data and depts:
        data["department_id"] = depts[0][0]
    times = [o for o in options(html, "appointment_time") if o[0]]
    data["appointment_date"] = (date.today() + timedelta(days=1)).isoformat()
    data["appointment_time"] = times[0][0] if times else "09:00"
    data["patient_name"] = label
    data["phone"] = "08033334444"
    data["consent"] = "1"
    if "fast_track_consent" in rendered_fields(html):
        data["fast_track_consent"] = "1"   # a real patient ticks the box they can see
    for key in drop:
        data.pop(key, None)

    r = SESSION.post(base + "/book/submit", data=data, allow_redirects=True)
    refused = re.search(r"(Fast Track[^<]{0,80}premium[^<]{0,40}|premium service[^<]{0,60})",
                        r.text)
    print(f"\n=== {door}  ({label}) ===")
    print(f"  fields the page rendered: "
          f"{', '.join(sorted(rendered_fields(html)))}")
    print(f"  HTTP {r.status_code} | final URL: {r.url[len(base):]}")
    if r.status_code >= 400:
        print(f"  refused by the server: {refused.group(1) if refused else '(no message matched)'}")
    return {"door": door, "status": r.status_code,
            "final": r.url[len(base):],
            "refused": bool(refused),
            "fields": rendered_fields(html),
            "depts": [lab for _, lab in depts]}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = (args[0] if args else "http://127.0.0.1:8077").rstrip("/")
    db_path = args[1] if len(args) > 1 else "data/e2e.db"
    failures: list[str] = []

    if "--clear" in sys.argv:
        con = sqlite3.connect(db_path)
        con.execute("DELETE FROM appointment")
        con.commit(); con.close()
        print("cleared previous appointments from " + db_path)

    print("=== what each door offers ===")
    runs = [
        book(base, "/book", label="Normal Door"),
        book(base, "/book/fast-track", label="Fast Track Door"),
        book(base, "/book/fast-track", label="Fast Track, NO consent",
             drop=("fast_track_consent",)),
        book(base, "/book", label="Sneaky premium dept via free door",
             drop=("fast_track_consent",), force={"department_id": "1"}),
    ]

    for run in runs:
        lounge = any("Fast Track" in lab for lab in run["depts"])
        print(f"  {run['door']:20} {len(run['depts'])} departments; "
              f"'Fast Track' lounge listed: {lounge}")
        want_field = EXPECTED[run["door"]]["is_fast_track"]
        got_field = "is_fast_track" in run["fields"]
        if got_field != want_field:
            failures.append(f"{run['door']} rendered is_fast_track={got_field}, "
                            f"expected {want_field}")
        if lounge != want_field:
            failures.append(f"{run['door']} lounge listed={lounge}, expected {want_field}")

    # the two bookings that were allowed through, and the two that were not
    if runs[0]["status"] != 200:
        failures.append(f"/book should have booked, got HTTP {runs[0]['status']}")
    if runs[1]["status"] != 200:
        failures.append(f"/book/fast-track should have booked, got HTTP {runs[1]['status']}")
    if runs[2]["status"] != 422 or not runs[2]["refused"]:
        failures.append("fast track WITHOUT consent must be refused with 422, "
                        f"got HTTP {runs[2]['status']}")
    if runs[3]["status"] != 422 or not runs[3]["refused"]:
        failures.append("a premium department posted through the free door must be "
                        f"refused with 422, got HTTP {runs[3]['status']}")

    print("\n=== what actually landed in the database ===")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT ref, patient_name, is_fast_track, fast_track_reason, "
                       "status FROM appointment ORDER BY id DESC LIMIT 4").fetchall()
    stored = {r["patient_name"]: r for r in rows}
    for r in rows:
        print(f"  {r['ref']}  {r['patient_name']:34} "
              f"is_fast_track={bool(r['is_fast_track'])!s:5} "
              f"reason={r['fast_track_reason']} status={r['status']}")

    for name, want in (("Normal Door", False), ("Fast Track Door", True)):
        row = stored.get(name)
        if row is None:
            failures.append(f"no appointment stored for {name}")
        elif bool(row["is_fast_track"]) is not want:
            failures.append(f"{name} stored is_fast_track={bool(row['is_fast_track'])}, "
                            f"expected {want}")
    for name in ("Fast Track, NO consent", "Sneaky premium dept via free door"):
        if name in stored:
            failures.append(f"{name} must NOT have created an appointment")

    print("\n" + ("ALL CHECKS PASSED" if not failures
                  else "FAILURES:\n  - " + "\n  - ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
