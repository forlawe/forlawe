"""QR code generation for the public complaint portal + personal TV."""
from __future__ import annotations

import base64
import io

import qrcode


def make_qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=10, border=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def make_qr_data_uri(data: str, box_size: int = 6) -> str:
    """Data URI for inline QR — premium, no extra request, works offline, slow internet optimized."""
    img = qrcode.make(data, box_size=box_size, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
