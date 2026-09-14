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


def _contrast_on_white(hex_colour: str) -> float:
    return 1.05 / (_relative_luminance(hex_colour) + 0.05)


def test_wcag_foreground_tokens_have_not_regressed():
    """The three previously regressed tokens must remain AA on white."""
    css = CSS.read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--(amber|orange|faint):\s*(#[0-9a-fA-F]{6})", css))

    assert set(tokens) == {"amber", "orange", "faint"}
    assert tokens["amber"] != "#9a7400"
    assert tokens["orange"] != "#c2660a"
    assert tokens["faint"] != "#8595a6"
    for name, colour in tokens.items():
        assert _contrast_on_white(colour) >= 4.5, (
            f"--{name} {colour} no longer meets WCAG AA on white"
        )
