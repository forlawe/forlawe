"""Polish round (F-022, F-023, F-025, F-026) — each finding, pinned.

F-022: the html lang attribute reflects the real UI language, instead of
       hardcoded English while the product speaks five languages.
F-023: every <img> carries alt text (alert_settings.html was the one miss).
F-025: Fast Track is a normal nav item — the gold gradient is gone; visual
       weight in the staff nav tracks clinical importance, not revenue.
F-026: every icon-only nav link has a title tooltip.
"""
from __future__ import annotations

import re

import pytest


def test_html_lang_is_dynamic(client, seeded):
    html = client.get("/").get_data(as_text=True)
    m = re.search(r'<html lang="([^"]*)"', html)
    assert m, "no html lang attribute"
    assert "{{" not in m.group(1)              # template rendered, not raw


def test_every_template_html_tag_uses_the_dynamic_lang():
    import os
    tpl = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
    bad = []
    for root, _dirs, files in os.walk(tpl):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            src = open(path, encoding="utf-8").read()
            for m in re.finditer(r'<html[^>]*>', src):
                if 'lang="{{' not in m.group(0):
                    bad.append(os.path.relpath(path, tpl))
    assert not bad, bad


def test_all_imgs_have_alt(client, seeded):
    html = client.get("/alert-settings").get_data(as_text=True)
    for tag in re.finditer(r"<img\b[^>]*>", html):
        assert re.search(r'\balt="', tag.group(0)), tag.group(0)


def test_fast_track_nav_is_no_longer_gold(client, seeded):
    from tests.conftest import login
    login(client, "admin")
    html = client.get("/dashboard").get_data(as_text=True)
    m = re.search(r"<a\b[^>]*>⭐ Fast Track</a>", html)
    assert m, "Fast Track nav item missing"
    assert "linear-gradient" not in m.group(0)         # no more gold/black shout
    assert "font-weight:900" not in m.group(0)         # no more heaviest weight


def test_icon_only_nav_links_have_tooltips(client, seeded):
    from tests.conftest import login
    login(client, "admin")
    html = client.get("/dashboard").get_data(as_text=True)
    nav = html.split("</nav>")[0]
    for icon in ("🔔", "🗣", "🔐"):
        for tag in re.finditer(r"<a\b[^>]*>" + icon, nav):
            assert "title=" in tag.group(0), tag.group(0)
