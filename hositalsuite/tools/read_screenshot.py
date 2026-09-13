#!/usr/bin/env python
"""Read the text out of a screenshot (OCR).

The owner's preferred way to show exactly where a problem is, is a
screenshot. This tool turns any image into the text that is on it — error
messages, URLs, button labels, table values — in reading order.

Usage:
    python tools/read_screenshot.py path/to/shot.png [another.png ...]

One-time setup (the sandbox venv does not survive between sessions —
reinstall when needed, it takes about a minute):

    pip install rapidocr-onnxruntime Pillow opencv-python-headless

Each line is printed with its confidence. Lines below 0.50 are marked
"low-confidence" — treat them as a guess, not a reading.
"""
from __future__ import annotations

import sys


def read(path: str) -> None:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:  # pragma: no cover - environment hint
        sys.exit(f"OCR engine not installed ({exc}).\n"
                 "Run:  pip install rapidocr-onnxruntime Pillow "
                 "opencv-python-headless")

    from PIL import Image
    try:
        with Image.open(path) as im:
            print(f"\n=== {path} — {im.size[0]}x{im.size[1]} {im.mode} ===")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"could not open {path}: {exc}")

    result, _ = RapidOCR()(path)
    if not result:
        print("  (no text found)")
        return
    # reading order: top-to-bottom, then left-to-right
    rows = []
    for box, text, conf in result:
        top = min(pt[1] for pt in box)
        left = min(pt[0] for pt in box)
        rows.append((top, left, text, float(conf)))
    for top, left, text, conf in sorted(rows):
        mark = "" if conf >= 0.50 else "  [low-confidence]"
        print(f"  [{conf:.2f}] {text}{mark}")


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        read(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
