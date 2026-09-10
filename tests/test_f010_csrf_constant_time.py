"""F-010: the CSRF token check is constant-time.

`token != session` compares byte-by-byte with early exit — a timing
side-channel. Low real-world risk, free to remove; this pins that the check
goes through secrets.compare_digest and still rejects bad tokens.
"""
from __future__ import annotations

import inspect


def test_csrf_check_uses_constant_time_compare():
    from app import security
    src = inspect.getsource(security.csrf_protect)
    assert "compare_digest" in src
    code = src.split("#")[0] + src.split("if not token")[1]   # strip comments
    assert "!= session" not in code


def test_wrong_csrf_token_still_rejected(client, seeded):
    page = client.get("/queue/join").get_data(as_text=True)
    token = page.split('name="_csrf" value="')[1].split('"')[0]
    r = client.post("/queue/join", data={"_csrf": token + "x",
                                         "department_id": "1",
                                         "patient_name": "CSRF Probe"},
                    follow_redirects=False)
    assert r.status_code == 403
