"""Phase 7 accessibility batch — the checks that can be done by computation.

Covers the rebuild spec Phase 7 acceptance criteria that are machine-
checkable at the source level, complementing:
  - WCAG AA contrast on token pairs  -> tests/test_f080_contrast_tokens.py
  - html lang / alt text / nav polish -> tests/test_f022_f026_polish.py
  - screen-reader + keyboard manual run-through (cannot be automated) is
    documented in docs/ACCESSIBILITY_PASS.md, updated by this batch.

Checks here:
  1. every icon-only interactive control has a real aria-label
     (a title alone is not an accessible name on touch devices);
  2. prefers-reduced-motion and :focus-visible are present in app.css and
     can never be deleted without failing this test;
  3. core controls (.btn, .backlink, primary nav) keep >= 44px touch targets
     in app.css;
  4. no template introduces a raw hex colour outside the design system
     (app.css palette) or the REVIEWED, count-pinned exception list in
     a11y_hex_baseline.py — and the pinned exceptions may not grow.
"""
import os
import re

from a11y_hex_baseline import REVIEWED_EXCEPTIONS

TEMPLATE_DIR = "app/templates"
CSS_FILE = "app/static/css/app.css"

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
TOKEN_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# total inline hex occurrences at the 2026-09-09 baseline (see a11y_hex_baseline)
TOTAL_INLINE_HEX_BASELINE = 926


def _norm_hex(h: str) -> str:
    h = h.lower()
    if len(h) == 4:  # #abc shorthand -> #aabbcc
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def _all_templates():
    for root, _, files in os.walk(TEMPLATE_DIR):
        for f in files:
            if f.endswith(".html"):
                yield os.path.join(root, f)


def _design_system_colours():
    css = open(CSS_FILE, encoding="utf-8").read()
    return {_norm_hex(h) for h in TOKEN_HEX_RE.findall(css)}


def _template_hex_inventory():
    counts = {}
    for path in _all_templates():
        t = open(path, encoding="utf-8").read()
        for h in HEX_RE.findall(t):
            n = _norm_hex(h)
            counts[n] = counts.get(n, 0) + 1
    return counts


# ------------------------------------------------------------------ 1. names
def test_every_icon_only_control_has_an_accessible_name():
    """An icon-only button/link must carry aria-label; title alone is not
    enough (invisible on touch, read inconsistently by assistive tech)."""
    pat = re.compile(r"<(button|a)\b([^>]*)>(.*?)</\1>", re.S)
    offenders = []
    for path in _all_templates():
        t = open(path, encoding="utf-8").read()
        for m in pat.finditer(t):
            tag, attrs, inner = m.group(1), m.group(2), m.group(3)
            inner_text = re.sub(r"<[^>]+>", "", inner)
            inner_text = re.sub(r"\s+", "", inner_text)
            if re.search(r"[A-Za-z0-9À-ž]", inner_text):
                continue  # has visible text
            if "aria-label" in attrs:
                continue
            if tag == "a" and re.search(r"aria-label|<img[^>]*alt=\"[^\"]+\"", attrs):
                continue
            offenders.append((path.replace(TEMPLATE_DIR + "/", ""), tag, attrs[:90]))
    assert not offenders, (
        "icon-only controls need aria-label (title alone is not enough): "
        f"{offenders}"
    )


# ------------------------------------------------------------------ 2. motion
def test_reduced_motion_and_focus_visible_are_guarded_in_css():
    css = open(CSS_FILE, encoding="utf-8").read()
    assert "prefers-reduced-motion" in css, "prefers-reduced-motion rule missing"
    assert ":focus-visible" in css, ":focus-visible rule missing"
    # Never remove the focus outline without an alternative visible indicator.
    # Where outline:none IS used (form fields), the same rule must supply a
    # border/box-shadow change as the indicator (WCAG 2.4.7 with 2.4.11).
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, block = m.group(1).strip(), m.group(2)
        if re.search(r"outline\s*:\s*(?:0|none)", block):
            assert re.search(r"border|box-shadow|background", block), (
                f"rule {selector!r} removes outline with no visible "
                f"alternative indicator: {block.strip()[:80]}"
            )


# ------------------------------------------------------------------ 3. targets
def test_core_touch_targets_are_at_least_44px():
    css = re.sub(r"/\*.*?\*/", "", open(CSS_FILE, encoding="utf-8").read(), flags=re.S)

    def min_height_of(exact_selector):
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            if m.group(1).strip() == exact_selector:
                hm = re.search(r"min-height\s*:\s*([0-9.]+)px", m.group(2))
                if hm:
                    return float(hm.group(1))
        raise AssertionError(f"{exact_selector} rule with min-height not found")

    assert min_height_of(".btn") >= 44, ".btn must keep a >=44px touch target"
    assert min_height_of(".backlink") >= 44, ".backlink must keep a 44px target"
    nav_ok = any(
        re.search(r"min-height\s*:\s*(4[4-9]|[5-9][0-9])px", m.group(2))
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
        if ".nav" in m.group(1).strip().split()[0]
    )
    assert nav_ok, "primary nav links need a >=44px touch target in app.css"


# ------------------------------------------------------------------ 4. hex
def test_no_raw_hex_outside_design_system_or_reviewed_list():
    palette = _design_system_colours()
    inventory = _template_hex_inventory()
    bad = sorted(c for c in inventory if c not in palette and c not in REVIEWED_EXCEPTIONS)
    assert not bad, (
        "raw hex colours outside the design system with no reviewed exception: "
        f"{bad}"
    )
    grown = sorted(c for c, n in inventory.items()
                   if c in REVIEWED_EXCEPTIONS and n > REVIEWED_EXCEPTIONS[c])
    assert not grown, (
        "reviewed exception colours grew past their pinned baseline: "
        f"{[(c, REVIEWED_EXCEPTIONS[c], inventory[c]) for c in grown]}"
    )
    total = sum(inventory.values())
    assert total <= TOTAL_INLINE_HEX_BASELINE, (
        f"inline hex grew: {total} > baseline {TOTAL_INLINE_HEX_BASELINE}"
    )
