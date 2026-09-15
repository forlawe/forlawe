"""Regression pins for the fixes reported in GitHub issue #8.

These are intentionally small, direct tests.  Both defects had already been
fixed once, then came back through a later merge; a source-level pin and a
real rendered login check make that kind of silent regression visible.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.views import auth

from conftest import csrf


CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "app.css"


def test_unknown_login_still_pays_the_password_hash_cost(client, seeded, monkeypatch):
    """A nonexistent username must verify against the fixed dummy hash."""
    calls = []
    real_check_password_hash = auth.check_password_hash

    def recording_check(password_hash, password):
        calls.append(password_hash)
        return real_check_password_hash(password_hash, password)

    monkeypatch.setattr(auth, "check_password_hash", recording_check)
    response = client.post(
        "/login",
        data={
            "_csrf": csrf(client, "/login"),
            "username": "definitely-not-a-real-user",
            "password": "WrongPassword1!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert auth._DUMMY_PASSWORD_HASH in calls


def _relative_luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]

    def linearise(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = (linearise(channel) for channel in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(foreground: str, background: str) -> float:
    foreground_luminance = _relative_luminance(foreground)
    background_luminance = _relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def test_wcag_foreground_tokens_pass_on_their_real_usage_backgrounds():
    """Test the foreground/background pairs patients actually see.

    The previous check compared every token with white. That masked the
    orange status-pill regression because --orange is rendered on --orange-bg.
    """
    css = CSS.read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--(amber|orange|faint):\s*(#[0-9a-fA-F]{6})", css))
    backgrounds = dict(re.findall(
        r"--(amber-bg|orange-bg):\s*(#[0-9a-fA-F]{6})", css
    ))

    assert set(tokens) == {"amber", "orange", "faint"}
    assert set(backgrounds) == {"amber-bg", "orange-bg"}
    assert tokens["amber"] != "#9a7400"
    assert tokens["orange"] != "#c2660a"
    assert tokens["faint"] != "#8595a6"
    assert "background:var(--amber-bg);color:var(--amber)" in css
    assert "background:var(--orange-bg);color:var(--orange)" in css

    assert _contrast(tokens["amber"], backgrounds["amber-bg"]) >= 4.5
    assert _contrast(tokens["orange"], backgrounds["orange-bg"]) >= 4.5
    assert _contrast(tokens["faint"], "#ffffff") >= 4.5
