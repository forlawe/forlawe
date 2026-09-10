"""F-080 — every text-capable colour token passes WCAG AA contrast (>=4.5:1).

The audit found app.css shipping colour values that failed contrast for the
text they carry. This test reads the ACTUAL token hex values from app.css and
computes the WCAG ratio for each documented pairing (text colour on its real
background, including white text on coloured fills). If anyone lightens a
token back below the threshold, the build fails — contrast is verified by
computation, not by eyeball (Phase 7).
"""
import re
from pathlib import Path

CSS = Path("app/static/css/app.css").read_text(encoding="utf-8")


def _hex(name):
    m = re.search(rf"{name}:#([0-9a-fA-F]{{6}})", CSS)
    assert m, f"token {name} not found in app.css"
    return "#" + m.group(1).lower()


def _lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _require(fg, bg, minimum=4.5, label=""):
    r = _ratio(fg, bg)
    assert r >= minimum, \
        f"contrast {r:.2f}:1 < {minimum}:1 for {label} ({fg} on {bg})"


def test_dark_text_on_white_cards():
    white = "#ffffff"
    for token in ("ink", "ink-2", "muted", "faint"):
        _require(_hex(token), white, 4.5, f"text {token} on white")
    for token in ("green", "amber", "orange", "red", "primary", "green-soft"):
        _require(_hex(token), white, 4.5, f"text {token} on white")


def test_status_text_on_its_own_tint():
    # pill classes render e.g. .pill.amber{color:amber; background:amber-bg}
    for token, tint in (("amber", "amber-bg"), ("orange", "orange-bg"),
                        ("green", "green-bg"), ("red", "red-bg")):
        _require(_hex(token), _hex(tint), 4.5, f"{token} on {tint}")


def test_white_text_on_coloured_fills():
    white = "#ffffff"
    for token in ("green", "green-soft", "amber", "orange", "red", "primary",
                  "primary-600", "primary-700", "primary-800"):
        _require(white, _hex(token), 4.5, f"white text on {token}")


def test_gold_badge_on_black():
    # Fast Track badge: gold text on black (large/900-weight display use)
    _require("#ffd700", "#000000", 4.5, "gold Fast Track badge on black")


def test_faint_is_the_lightest_allowed_neutral():
    # keep design intent: faint < muted < ink-2 < ink in darkness
    pairs = [("faint", "muted"), ("muted", "ink-2"), ("ink-2", "ink")]
    for light, dark in pairs:
        assert _lum(_hex(light)) > _lum(_hex(dark)), \
            f"token {light} should be lighter than {dark}"


def test_visual_theme_still_uses_teal_blue_and_navy():
    """Phase 7 keeps the suite's calm teal/navy personality: at least one of
    the green status family and one primary token must stay cool-toned."""
    green = _hex("green")
    primary = _hex("primary")
    g_r = int(green[1:3], 16)
    g_b = int(green[5:7], 16)
    assert g_b <= g_r + 30, "green lost its cool teal cast"
    p_r = int(primary[1:3], 16)
    assert p_r < 40 and int(primary[3:5], 16) < 110, "primary is no longer navy"
