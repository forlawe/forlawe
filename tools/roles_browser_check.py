"""Prove Role Management works in a REAL browser, not just in the test client.

A Flask test client is not a browser. It does not run JavaScript, it does not
apply CSS, and it will happily "pass" a page that renders as a wall of broken
markup on the founder's Android phone. This drives an actual Chromium at a
real running server, at phone width, and asserts on what is on the screen.

Usage:
    python3 tools/roles_browser_check.py http://127.0.0.1:5055
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055"
PHONE = {"width": 390, "height": 844}

failures: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    (notes if ok else failures).append(f"{'PASS' if ok else 'FAIL'}  {label}"
                                       + (f" — {detail}" if detail else ""))


def sign_in(page, username: str, password: str = "Passw0rd!x") -> bool:
    # /logout is POST-only (a GET logout is a CSRF hole), so clear the session
    # by wiping cookies instead of navigating to it.
    page.context.clear_cookies()
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    if page.query_selector('input[name="username"]') is None:
        return False
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"], .btn')
    page.wait_for_load_state("domcontentloaded")
    return "/login" not in page.url


def run() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=PHONE)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ---------------------------------------------------------- admin
        check("administrator can sign in", sign_in(page, "admin"))

        page.goto(f"{BASE}/admin/roles", wait_until="domcontentloaded")
        body = page.content()
        check("Role Management page loads", "Roles" in page.title() or
              "what each may do" in body)
        for role in ("Super Administrator", "HOD", "Staff"):
            check(f"built-in role '{role}' is listed", role in body)

        # The tick-list must actually render as tick boxes on a phone.
        page.goto(f"{BASE}/admin/roles", wait_until="domcontentloaded")
        link = page.query_selector('a[href^="/admin/roles/"]')
        if link:
            link.click()
            page.wait_for_load_state("domcontentloaded")
            boxes = page.query_selector_all('input[type="checkbox"][name="perm"]')
            check("permission tick boxes render", len(boxes) >= 10,
                  f"{len(boxes)} boxes")
            if boxes:
                box = boxes[0].bounding_box()
                check("tick boxes are big enough for a thumb",
                      bool(box) and box["width"] >= 20 and box["height"] >= 20,
                      f"{box}")
        else:
            check("a role can be opened for editing", False)

        # Nothing may overflow the phone screen sideways.
        for path in ("/admin/roles", "/my-department"):
            page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            over = page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth")
            check(f"{path} fits a 390px phone", over <= 2, f"{over}px too wide")

        # ---------------------------------------------------------- an HOD
        if sign_in(page, "browserhod"):
            page.goto(f"{BASE}/", wait_until="domcontentloaded")
            nav = page.inner_html("#mainnav")
            check("HOD does NOT see the admin link", 'href="/admin"' not in nav)
            check("HOD DOES see My Department", "/my-department" in nav)

            page.goto(f"{BASE}/my-department", wait_until="domcontentloaded")
            desk = page.content()
            check("the department desk loads for an HOD",
                  "Who is working on what" in desk)
            check("the desk says what it is showing and hiding",
                  "your own department" in desk or "only" in desk)

            # Teamwork: putting your name on something must actually work.
            if page.query_selector('select[name="kind"]'):
                page.select_option('select[name="kind"]', "TRIAGE")
                page.click('form[action="/my-department/claim"] button')
                page.wait_for_load_state("domcontentloaded")
                check("claiming a task works", "You are on" in page.content())
            else:
                check("the claim form is on the page", False)

            # The admin screens must be refused, not just hidden.
            page.goto(f"{BASE}/admin/roles", wait_until="domcontentloaded")
            check("HOD is REFUSED the role screen, not just denied the link",
                  "403" in page.content() or "not allowed" in page.content().lower()
                  or "Forbidden" in page.content())
        else:
            check("the test HOD account exists", False,
                  "create 'browserhod' before running this")

        check("no JavaScript errors on any page", not errors, "; ".join(errors[:3]))
        browser.close()

    for line in notes:
        print(line)
    for line in failures:
        print(line)
    print(f"\n{len(notes)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
