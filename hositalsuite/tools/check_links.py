"""Find template links/forms that point at URLs the app does not serve.

This is the class of bug that produced the "Create user does nothing" and the
department-page 404: a hand-written URL in a template drifting from the route.
Run it any time templates change:  python tools/check_links.py
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/linkcheck.db")
os.environ.setdefault("SECRET_KEY", "linkcheck")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import create_app  # noqa: E402


def build_matchers(app):
    out = []
    for r in app.url_map.iter_rules():
        pattern = re.sub(r"<[^>]+>", "[^/]+", str(r))
        out.append((re.compile("^" + pattern + "$"), set(r.methods), str(r)))
    return out


def main() -> int:
    app = create_app(scheduler=False)
    rules = build_matchers(app)

    JINJA = re.compile(r"\{\{.*?\}\}")

    def serves(path: str, method: str) -> bool:
        # A URL like /admin/section/{{ s.id }}/delete must still be checked:
        # replace each Jinja expression with a stand-in path segment. This is
        # precisely where the department-page 404 was hiding.
        # A trailing {{ q }} is an optional query string, not a path segment.
        cleaned = re.sub(r"\{\{\s*q\s*\}\}$", "", path)
        concrete = JINJA.sub("1", cleaned).replace(" ", "")
        concrete = concrete.split("?")[0] or "/"
        if "{%" in concrete:
            return True          # control flow inside a URL: too dynamic to verify
        return any(rx.match(concrete) and method in methods for rx, methods, _ in rules)

    bad = set()
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app", "templates")
    for f in glob.glob(os.path.join(root, "**", "*.html"), recursive=True):
        html = open(f, encoding="utf-8").read()
        rel = os.path.relpath(f, root)
        # form actions -> check against the form's OWN method (default GET per HTML spec)
        for m in re.finditer(r'<form\b([^>]*)>', html, re.I):
            attrs = m.group(1)
            am = re.search(r'action="(/[^"]*)"', attrs)
            if not am:
                continue
            mm = re.search(r'method="(\w+)"', attrs, re.I)
            method = (mm.group(1).upper() if mm else "GET")
            if not serves(am.group(1), method):
                bad.add((rel, method, am.group(1)))
        # plain hrefs -> must accept GET (skip static, anchors, templated URLs)
        for m in re.finditer(r'href="(/[^"#?]*)"', html):
            p = m.group(1)
            if p.startswith("/static") or p in ("/",):
                continue
            if not serves(p, "GET"):
                bad.add((rel, "GET", p))

    if not bad:
        print("✅ every template link and form points at a real route")
        return 0
    print(f"❌ {len(bad)} broken link(s)/form(s):")
    for rel, meth, p in sorted(bad):
        print(f"   {meth:5} {p:50} in {rel}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
