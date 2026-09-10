"""Nigerian language scaffolding: switcher, translated portals, voice tags."""


def test_default_language_english(client, seeded):
    r = client.get("/complaint")
    assert b"SUBMIT COMPLAINT" in r.data
    assert b'data-lang="en-NG"' in r.data


def test_switch_to_yoruba_translates_portals_and_voice(client, seeded):
    r = client.get("/lang/yo?next=/complaint")
    assert r.status_code == 302
    r = client.get("/complaint")
    assert "FI Ẹ̀DÙN SÍLẸ̀".encode() in r.data
    assert "Nọ́mbà fóònù".encode() in r.data
    assert b'data-lang="yo-NG"' in r.data          # voice-to-text follows language
    assert b'<html lang="yo">' in r.data
    # language persists across other portals
    r = client.get("/book")
    assert "FIPAMỌ́ ÌBẸ̀WÒ MI".encode() in r.data
    r = client.get("/feedback")
    assert "FI ÈSÌ RÁNṢẸ́".encode() in r.data
    r = client.get("/queue/join")
    assert "GBA NỌ́MBÀ ÌLÀ MI".encode() in r.data


def test_hausa_and_igbo(client, seeded):
    client.get("/lang/ha?next=/complaint")
    r = client.get("/complaint")
    assert "AIKA ƘORAFI".encode() in r.data and b'data-lang="ha-NG"' in r.data
    client.get("/lang/ig?next=/complaint")
    r = client.get("/complaint")
    assert "ZIPU MKPESA".encode() in r.data and b'data-lang="ig-NG"' in r.data


def test_invalid_language_ignored(client, seeded):
    client.get("/lang/xx?next=/complaint")
    r = client.get("/complaint")
    assert b"SUBMIT COMPLAINT" in r.data


def test_lang_switch_rejects_open_redirect(client, seeded):
    r = client.get("/lang/yo?next=https://evil.example.com")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/")


def test_thanks_pages_localized(client, seeded):
    client.get("/lang/yo?next=/complaint")
    r = client.get("/complaint/thanks?ref=HOSP-CMP-2026-000001")
    assert "A gbà ẹ̀dùn rẹ.".encode() in r.data
