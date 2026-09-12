"""F-036: the /privacy notice discloses third-party AI processing.

Patient-typed chat messages and recent conversation history are sent verbatim
to Groq/Gemini/OpenRouter when the knowledge base can't answer. The privacy
notice must say so plainly (NDPA transparency), and the sub-processor list
must carry the vendors.
"""
from __future__ import annotations


def test_privacy_notice_discloses_ai_providers(client, seeded):
    html = client.get("/privacy").get_data(as_text=True).lower()
    assert "assistant chat" in html
    for provider in ("groq", "gemini", "openrouter"):
        assert provider in html, provider
    assert "recent messages" in html or "conversation" in html


def test_subprocessor_registry_lists_ai_vendors():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[1] / "docs" / "SUB_PROCESSORS.md").read_text()
    for vendor in ("Groq", "Gemini", "OpenRouter"):
        assert vendor in doc, vendor
