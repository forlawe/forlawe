"""Accessibility pass (report §15 item 5) — pin the fixes and the verdicts.

Patient-facing surfaces first: a hospital portal is used on cheap phones, on
hospital Wi-Fi, by people who are unwell, older, or holding a child. The pass
checked every shared template and every public page for: language of the
document, landmark structure, a skip link, programmatic labels on form fields
(a visible <label> with no for= helps nobody who cannot see the screen),
alt text on images, and keyboard-hostile click handlers.

Already-true verdicts (checked, left alone):
  * every <img> across all 81+34 templates carries alt text
  * <html lang> is set from the real page language (F-022)
  * base.html has nav/main landmarks; flash messages are text, not colour-only
  * login, chat and change_password forms were already fully labeled
Fixed by this pass:
  * skip link + <main id> in base.html; aria-current="page" on the active nav link
  * booking/complaint/feedback portals + both status pages: label-for wiring
  * TV night-mode toggle was an onclick <div> (unclickable by keyboard) — now a button
"""
from __future__ import annotations

import re

import pytest

NON_INTERACTIVE_ONCLICK = re.compile(
    r"<(div|span|td|tr|li|p|h[1-6])[^>]*\bonclick=", re.I)


def _visible_fields(html: str):
    """(tag, attrs) for every non-hidden, non-submit form field."""
    out = []
    for m in re.finditer(r"<(input|select|textarea)\b([^>]*)>", html):
        attrs = m.group(2)
        if 'type="hidden"' in attrs or 'type="submit"' in attrs:
            continue
        out.append((m.group(1), attrs, m.start()))
    return out


def _field_is_labeled(html: str, tag: str, attrs: str, pos: int) -> bool:
    if "aria-label" in attrs or "aria-labelledby" in attrs:
        return True
    m = re.search(r'\bid="([^"]+)"', attrs)
    if m and re.search(r'<label[^>]*for="%s"' % re.escape(m.group(1)), html):
        return True
    # label wrapping the field
    before = html[max(0, pos - 300):pos]
    if "<label" in before and "</label>" not in before.split("<label")[-1]:
        return True
    return False


def test_every_base_page_has_a_skip_link_and_main_target(client):
    # /login is deliberately exempt: a single sign-in card is the first and
    # only content — there is nothing to skip past.
    for path in ("/book", "/complaint", "/feedback", "/chat",
                 "/book/status", "/complaint/status"):
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.get_data(as_text=True)
        assert 'class="skip-link"' in html, f"{path}: no skip link"
        assert 'id="main-content"' in html, f"{path}: main has no skip target"


def test_active_nav_link_carries_aria_current(app, seeded):
    from tests.conftest import login
    client = app.test_client()
    assert login(client, "admin")
    html = client.get("/").get_data(as_text=True)
    active = re.findall(r'<a href="[^"]*" class="active"[^>]*>', html)
    assert active, "expected at least one active nav link on the dashboard"
    assert any('aria-current="page"' in a for a in active)


@pytest.mark.parametrize("path", ["/book", "/complaint", "/feedback",
                                  "/book/status", "/complaint/status"])
def test_public_forms_label_every_field(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    html = r.get_data(as_text=True)
    fields = _visible_fields(html)
    assert fields, f"{path}: expected a form"
    unlabeled = [(t, a) for (t, a, p) in fields
                 if not _field_is_labeled(html, t, a, p)]
    assert not unlabeled, f"{path}: unlabeled fields {unlabeled}"


def test_tv_templates_have_no_click_only_divs():
    """The night-mode toggle used to be an onclick <div>: invisible to Tab
    and to screen readers. It must stay a real button."""
    for f in ("app/templates/tv/clinic.html", "app/templates/tv/main.html"):
        s = open(f, encoding="utf-8").read()
        assert not NON_INTERACTIVE_ONCLICK.search(s), \
            f"{f}: onclick on a non-interactive element"
        assert "tv-night-toggle" in s and "aria-pressed" in s


def test_brightness_slider_is_labelled_for_screen_readers():
    for f in ("app/templates/tv/clinic.html", "app/templates/tv/main.html"):
        s = open(f, encoding="utf-8").read()
        assert 'aria-label="Screen brightness"' in s


def test_every_image_in_every_template_has_alt_text():
    """Verdict pin: this was already true everywhere — keep it true."""
    import glob
    for f in glob.glob("app/templates/**/*.html", recursive=True):
        s = open(f, encoding="utf-8").read()
        for m in re.finditer(r"<img\b([^>]*)>", s):
            assert "alt=" in m.group(1), f"{f}: <img> without alt"
