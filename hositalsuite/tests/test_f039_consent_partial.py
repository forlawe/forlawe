"""F-039: one Fast Track consent statement, shared — never re-typed.

The paid-service consent used to exist hand-typed in two patient templates
with three drifted wordings of the same legally load-bearing sentence. The
fix is a single partial; these tests make the drift impossible to reintroduce
silently (a second copy anywhere in templates fails the suite) and prove both
patient forms still render the statement.
"""
from __future__ import annotations

CONSENT_MARK = "I choose Fast Track. I understand it is a premium service"


def test_consent_statement_exists_in_exactly_one_template():
    """Anti-drift guard: the consent sentence lives only in the partial."""
    import os

    tpl_dir = os.path.join(os.path.dirname(__file__), "..", "app", "templates")
    hits = []
    for root, _dirs, files in os.walk(tpl_dir):
        for f in files:
            if f.endswith((".html", ".jinja", ".txt")):
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fh:
                    if CONSENT_MARK in fh.read():
                        hits.append(os.path.basename(path))
    assert hits == ["_fasttrack_consent.html"], hits


def test_both_patient_forms_render_the_consent(client, seeded):
    for url in ("/book", "/queue/join"):
        r = client.get(url)
        assert r.status_code == 200, (url, r.status_code)
        assert CONSENT_MARK in r.get_data(as_text=True), url


def test_consent_wording_is_single_version(client, seeded):
    """The three historical wordings are gone — every rendered form shows the
    same 'quiet, private lounge' promise."""
    for url in ("/book", "/queue/join"):
        html = client.get(url).get_data(as_text=True)
        assert "quiet, private lounge" in html, url
        assert "quiet, comfortable lounge" not in html
