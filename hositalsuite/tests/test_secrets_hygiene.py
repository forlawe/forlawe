"""Secrets hygiene — the test that exists because a private key WAS committed.

On 2026-09-03 an independent code review found the production VAPID PRIVATE
key written in plaintext inside HOSPITAL_ASSISTANT_WORLD_CLASS_REPORT.md —
in the same patchset that added *.pem / vapid_keys.json to .gitignore. A
.gitignore rule protects runtime files; it does nothing for a secret typed
into a status report.

These tests scan every file git actually tracks (so .gitignore rules are
honoured by construction) and fail when secret-shaped material appears:

  1. the specific keypair that leaked must never come back — even quoted,
     even in an "example" — it is compromised and rotation is one-way;
  2. no PEM private key blocks anywhere in the repo (there are none today,
     so any appearance is an incident);
  3. no VAPID-shaped private key literal in any markdown/report file.

Placeholders like `your_auth_token_here` or `TWILIO_AUTH_TOKEN=...` do NOT
match and must keep working in docs — the tests are written to allow them.

Important: the burned key *values* are deliberately NOT stored here. Storing
them — even split across two string literals so the scanner below would not
flag its own source — re-commits the secret. Instead we keep only the
SHA-256 digests, which identify the exact burned key without re-leaking it.
"""
import hashlib
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SHA-256 digests of the VAPID keypair compromised on 2026-09-03. The raw
# values are never written to the repository again; the digests are one-way
# and cannot be reversed to recover the keys, but let this test recognise
# the exact burned keypair if it ever reappears in any tracked file.
BURNED_PRIVATE_SHA256 = "d3d9445370d4546dbb42161ca5dc1ff18bbfe8e928e0b51c6a2f7997f3ce3314"
BURNED_PUBLIC_SHA256 = "c42effce97c6499e18310b49be6cc049879ad90417e7c8851fba9a914450339a"

# A VAPID private key is exactly 43 base64url chars; the public key is 87.
# Bounded by non-base64url lookarounds so a key embedded in prose (between
# backticks, quotes, spaces, punctuation) still matches as one token.
_PRIVATE_TOKEN = re.compile(r"(?<![A-Za-z0-9_\-])([A-Za-z0-9_\-]{43})(?![A-Za-z0-9_\-])")
_PUBLIC_TOKEN = re.compile(r"(?<![A-Za-z0-9_\-])([A-Za-z0-9_\-]{87})(?![A-Za-z0-9_\-])")

# PEM private keys (RSA/EC/OPENSSH/ENCRYPTED/PGP ...).
PEM_PRIVATE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")

# A VAPID private key is exactly 43 base64url chars. Only flag it in prose
# files (.md/.txt) next to the word PRIVATE — code files legitimately hold
# regexes/constants describing key *shapes*, not key *values*.
VAPID_IN_PROSE = re.compile(
    r"PRIVATE[^`\"]{0,40}[`\"']([A-Za-z0-9_\-]{40,60})[`\"']")

# Text files worth scanning. Skip .git (not tracked), node_modules-style dirs,
# and anything git itself doesn't track.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache",
             ".ruff_cache", ".mypy_cache", "htmlcov"}


def _sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _tracked_files():
    """Every file git tracks, falling back to a directory walk when git is
    unavailable (e.g. exporting a tarball)."""
    files = []
    try:
        import subprocess
        out = subprocess.run(["git", "ls-files"], cwd=REPO, timeout=30,
                             capture_output=True, text=True, check=True)
        files = [f for f in out.stdout.splitlines() if f]
        if files:
            return files
    except Exception:                                   # noqa: BLE001
        pass
    for root, dirs, names in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            path = os.path.relpath(os.path.join(root, n), REPO)
            if not path.startswith(".git"):
                files.append(path)
    return files


def _read(path):
    """File contents as text, or '' for binary files."""
    full = os.path.join(REPO, path)
    try:
        with open(full, "rb") as fh:
            data = fh.read()
    except OSError:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def test_the_leaked_vapid_keypair_never_returns():
    """The compromised key is burned. Even a 'documentation' quote is a leak.

    Files are scanned for 43/87-char base64url tokens and compared against
    the digest of the burned keypair, so the test never stores the key itself
    but still catches the exact value if it is pasted back in (even inline).
    """
    hits = []
    for path in _tracked_files():
        body = _read(path)
        for m in _PRIVATE_TOKEN.finditer(body):
            if _sha256(m.group(1)) == BURNED_PRIVATE_SHA256:
                hits.append(f"{path}: burned VAPID PRIVATE key present")
                break
        for m in _PUBLIC_TOKEN.finditer(body):
            if _sha256(m.group(1)) == BURNED_PUBLIC_SHA256:
                hits.append(f"{path}: burned VAPID public key present")
                break
    assert not hits, (
        "The VAPID keypair compromised on 2026-09-03 reappeared in the repo:\n"
        + "\n".join(hits)
        + "\nIt must stay out of every file — rotate instead of restoring."
        + "\nSee docs/SECURITY_INCIDENT_2026-09-03_VAPID_KEY_ROTATION.md")


def test_no_pem_private_keys_anywhere():
    """A PEM private key in the repo is an incident, full stop."""
    hits = []
    for path in _tracked_files():
        if PEM_PRIVATE.search(_read(path)):
            hits.append(path)
    assert not hits, (
        "Private key material committed in: " + ", ".join(hits)
        + "\nSecrets belong in the platform env (Render), never in git.")


def test_no_vapid_shaped_private_keys_in_prose_files():
    """Catch the general mistake, not just this one key: a 43-char base64url
    literal labelled PRIVATE inside a report/guide markdown file."""
    hits = []
    for path in _tracked_files():
        if not path.lower().endswith((".md", ".txt", ".rst")):
            continue
        for match in VAPID_IN_PROSE.finditer(_read(path)):
            literal = match.group(1)
            # Real VAPID private keys are exactly 43 base64url characters and
            # placeholders ('...', 'xxxxx', 'your_key_here') are shorter or
            # contain non-base64url characters — both pass through.
            if re.fullmatch(r"[A-Za-z0-9_\-]{43}", literal) and literal not in (
                    "x" * 43,):
                hits.append(f"{path}: {literal[:8]}…")
    assert not hits, (
        "Possible VAPID private key written in a document:\n" + "\n".join(hits)
        + "\nDocuments must reference env var NAMES (VAPID_PRIVATE_KEY), "
        "never values.")
