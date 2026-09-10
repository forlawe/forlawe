"""F-070 — every route requiring authorization is reachable in normal navigation.

Phase 6 of the rebuild spec: "an automated check (crawl the route table, crawl
the templates, flag any authorized-but-unlinked route) runs in CI, not as a
one-off manual audit."

This test IS that check:
  1. crawl the route table (app.url_map),
  2. crawl every template / view / static script for references — both
     url_for('endpoint') calls and literal URL paths (with Jinja/JS/format
     placeholders normalized),
  3. flag any route whose view function carries an authorization decorator
     (require_login / require_role / require_admin_manager_on_duty) and is
     never referenced.

Endpoints on the allowlist are deliberate, reviewed exceptions — each carries
a written reason (legacy address kept alive, printed-QR alias, external
webhook/API consumer, PWA/offline shell reached from JavaScript registration
rather than a link). Adding a NEW route without linking it AND without a
reasoned allowlist entry fails this test.
"""
import ast
import os
import re

from app import create_app

AUTH_DECORATORS = ("require_login", "require_role", "require_admin_manager_on_duty")

# --------------------------------------------------------------------------
# reviewed exceptions — endpoint: why it is allowed to stay unlinked
# --------------------------------------------------------------------------
ALLOWLIST = {
    "triage.consulting_room_legacy":
        "Legacy '/consulting-room/legacy' path kept alive for old bookmarks/"
        "links; renders the same room screen as consulting.room (linked).",
    "inspections.department_children":
        "fetched from static JS with a concatenated id — "
        "fetch('/inspections/departments/' + id + '/children') in app.js, "
        "which no static literal-path crawl can resolve.",
}


def _auth_protected_endpoints():
    """Return endpoints whose view has an auth decorator, by reading the AST
    of each view module. Deterministic: a route either carries the decorator
    or it does not — no runtime trickery."""
    protected = set()
    for fname in os.listdir("app/views"):
        if not fname.endswith(".py"):
            continue
        src = open(os.path.join("app/views", fname), encoding="utf-8").read()
        m = re.search(r"Blueprint\(\s*['\"]([A-Za-z0-9_]+)['\"]", src)
        bp = m.group(1) if m else fname[:-3]
        tree = ast.parse(src)

        def dname(dec):
            d = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(d, ast.Name):
                return d.id
            if isinstance(d, ast.Attribute):
                return d.attr
            return ""

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = [dname(d) for d in node.decorator_list]
            if any(n in AUTH_DECORATORS for n in names):
                if any(n in ("get", "post", "route") for n in names):
                    protected.add(f"{bp}.{node.name}")
    return protected


def _reference_crawl():
    """All endpoint references anywhere reachable: url_for endpoint names plus
    literal URL paths resolved against the real route table."""
    app = create_app(scheduler=False)
    rules = []
    for r in app.url_map.iter_rules():
        if r.rule.startswith("/static"):
            continue
        methods = (set(r.methods) or set()) - {"HEAD", "OPTIONS"}
        if not methods:
            methods = {"GET"}
        rules.append((r.endpoint, r.rule, methods))

    def rule_re(rule):
        # escape the static text first, THEN insert a wildcard per converter —
        # escaping the whole rule would also escape the wildcard fragments
        out = "^"
        for chunk in re.split(r"(<[^>]*>)", rule):
            if chunk.startswith("<") and chunk.endswith(">"):
                ctype = chunk[1:-1].partition(":")[0]
                out += ".*" if ctype == "path" else "[^/]+"
            else:
                out += re.escape(chunk)
        return out + "$"

    refs = set()          # url_for endpoint names
    paths = []            # literal path snippets
    url_for_re = re.compile(r"""url_for\(\s*['"]([A-Za-z0-9_.]+)['"]""")
    quoted_re = re.compile(r"""(?P<q>['"`])(?P<p>/[^'"`\n]*)(?P=q)""")

    for base in ("app/templates", "app/static"):
        for root, _, files in os.walk(base):
            for f in files:
                if not f.endswith((".html", ".js")):
                    continue
                t = open(os.path.join(root, f), encoding="utf-8").read()
                refs.update(url_for_re.findall(t))
                for m in quoted_re.finditer(t):
                    paths.append(m.group("p"))
    for fname in os.listdir("app/views"):
        if not fname.endswith(".py"):
            continue
        t = open(os.path.join("app/views", fname), encoding="utf-8").read()
        refs.update(url_for_re.findall(t))
        for m in quoted_re.finditer(t):
            p = m.group("p")
            if p.startswith("/") and re.search(r"(redirect|action_url|url\s*=|href\s*=)", t[max(0, m.start() - 60):m.start()]):
                paths.append(p)

    def norm(p):
        p = re.split(r"[?#]", p, maxsplit=1)[0]
        p = re.sub(r"\{\{[^}]*\}\}", "\u0001", p)
        p = re.sub(r"\$\{[^}]*\}", "\u0001", p)
        p = re.sub(r"\{[^}]*\}", "\u0001", p)  # format-style {id}
        return p

    resolved = set()
    for e in refs:
        if "." in e and any(e == ep for ep, _, _ in rules):
            resolved.add(e)
        elif "." not in e:
            resolved.update(ep for ep, _, _ in rules
                            if ep.split(".")[0] == e or ep.endswith("." + e))
    for raw in paths:
        p = norm(raw)
        if not p.startswith("/"):
            continue
        for ep, rule, methods in rules:
            if re.match(rule_re(rule), p):
                resolved.add(ep)

    # A <form> with no action attribute posts to the page's OWN url — so a
    # POST-only endpoint whose rule path matches a reachable GET endpoint on
    # the same path is reachable by normal navigation (e.g. the /hims/import
    # form renders at GET and submits to the same /hims/import as POST).
    same_path_get = {}
    for ep, rule, methods in rules:
        for m in methods:
            if m == "GET":
                same_path_get.setdefault(rule, set()).add(ep)
    for ep, rule, methods in rules:
        if "POST" in methods and ep not in resolved:
            for g in same_path_get.get(rule, set()):
                if g in resolved:
                    resolved.add(ep)
                    break

    return app, set(ep for ep, _, _ in rules), resolved


def test_every_authorized_route_is_reachable_or_reasoned():
    app, all_endpoints, reachable = _reference_crawl()
    protected = _auth_protected_endpoints() & all_endpoints
    unknown = set(ALLOWLIST) - all_endpoints
    assert not unknown, f"allowlist names unregistered endpoints: {sorted(unknown)}"
    orphaned = sorted(ep for ep in protected - reachable if ep not in ALLOWLIST)
    assert not orphaned, (
        "F-070: authorized route(s) exist but nothing links to them — link "
        f"them from the right role's template or add a REASONED allowlist "
        f"entry: {orphaned}"
    )


def test_allowlist_routes_stay_registered():
    """Guard against allowlist rot: every listed exception must still exist."""
    app, all_endpoints, _ = _reference_crawl()
    missing = sorted(set(ALLOWLIST) - all_endpoints)
    assert not missing, f"allowlist entries no longer registered: {missing}"
