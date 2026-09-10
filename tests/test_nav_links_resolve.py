"""F-024 regression: internal links must resolve, and the nav/hub must use url_for().

Why this exists: navigation was written with raw href strings ("/my-department").
It works only while the strings happen to match the current URL prefixes; a
blueprint prefix change would stale every one of them with NO error anywhere —
just a 404 the next time a user clicks. url_for() code fails loudly instead
(F-007 was exactly such a failure, and it was the only catchable one).

Two invariants pinned here:
  1. base.html nav + patient_hub.html tiles contain ZERO hardcoded internal
     hrefs — they use url_for() (the F-024 refactor itself cannot regress);
  2. every hardcoded internal href ANYWHERE in the templates resolves to a
     real route (exact or dynamic-prefix), so the remaining legacy links can
     no longer rot silently.
"""
import os
import re

from app import create_app

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "app", "templates")

# href="/..." — cut the captured path at the first {{ (Jinja expression), ?
# (query string) or closing quote. Anchors (#), protocol-relative (//), tel:,
# mailto: and url_for() calls don't match this pattern at all.
HREF_RE = re.compile(r'href="(/[^"]*)"')
PATH_RE = re.compile(r"^(/[^\"{#?]*)")


def _iter_templates():
    for root, _dirs, names in os.walk(TEMPLATE_DIR):
        for n in names:
            if n.endswith(".html"):
                yield os.path.join(root, n)


def _static_prefix(href: str) -> str | None:
    """The static leading path of an href that may embed Jinja expressions,
    e.g. '/hims/folder/{{ p.id }}/visit' -> '/hims/folder/'. Pure-static
    hrefs return the whole path."""
    m = PATH_RE.match(href)
    return m.group(1) if m else None


def test_nav_and_hub_templates_use_url_for_exclusively():
    """The two templates the audit called out must never regress to raw hrefs."""
    must_be_clean = ["base.html", "patient_hub.html"]
    bad = []
    for name in must_be_clean:
        body = open(os.path.join(TEMPLATE_DIR, name)).read()
        for m in HREF_RE.finditer(body):
            bad.append(f"{name}: {m.group(1)}")
    assert not bad, (
        "Hardcoded internal hrefs back in the nav/hub templates — use url_for() "
        "(F-024). Offenders:\n" + "\n".join(bad))


def test_every_hardcoded_template_href_resolves_to_a_real_route():
    """Any remaining raw href anywhere must match a registered route — exactly
    or as the static prefix of one (dynamic links like /hims/folder/{{ id }}).
    This is the net that catches 'silent 404 six months from now' TODAY."""
    app = create_app(scheduler=False)
    paths = sorted({str(r) for r in app.url_map.iter_rules()})
    # static head of each rule (everything before its first <converter>) —
    # a request like /tv/MAIN is served by /tv/<code>, so the literal
    # string /tv/MAIN must count as resolvable.
    heads = sorted({p.split("<", 1)[0] for p in paths if "<" in p})

    def resolves(prefix: str) -> bool:
        prefix = prefix.rstrip("/")
        if not prefix:
            return True
        for p in paths:
            if p == prefix or p.rstrip("/") == prefix:
                return True
            if p.startswith(prefix + "/") or p == prefix + "/":
                return True
        for h in heads:
            if h.rstrip("/") and prefix.startswith(h.rstrip("/")):
                return True
        return False

    unresolved = []
    for full in _iter_templates():
        rel = os.path.relpath(full, TEMPLATE_DIR)
        body = open(full, encoding="utf-8", errors="replace").read()
        for m in HREF_RE.finditer(body):
            href = m.group(1)
            if href == "/":
                continue                      # site root always exists
            prefix = _static_prefix(href) or href
            prefix = prefix.rstrip("*")
            if not prefix or prefix == "/":
                continue
            if not resolves(prefix):
                unresolved.append(f"{rel}: {href}")
    assert not unresolved, (
        "Template hrefs pointing at NO registered route (these 404 when "
        "clicked):\n" + "\n".join(sorted(unresolved)))
