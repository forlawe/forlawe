"""Speech-to-text: run the browser tests as part of the normal suite.

WHY THIS WRAPPER EXISTS
-----------------------
The dictation bug the founder reported ("perfect on my laptop but repeating
words on my phone") lives entirely in the browser, in how Chrome on Android
ends and restarts a recognition session. No Flask test could ever see it — the
test client does not run JavaScript at all.

tests/js/speech_test.js drives the REAL app/static/js/app.js with a fake
SpeechRecognition that behaves the way Android does. This file makes `pytest`
run it, so nobody can break dictation again without the normal suite failing.

If Node is not installed the test SKIPS rather than fails: a missing developer
tool must not block a deploy of the hospital's software.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "js", "speech_test.js")
APP_JS = os.path.join(os.path.dirname(HERE), "app", "static", "js", "app.js")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="Node.js is not installed; browser tests skipped")
def test_dictation_behaves_on_a_phone_not_just_a_laptop():
    result = subprocess.run(["node", SCRIPT], capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, (
        "The browser dictation tests failed. This is the code that runs on the "
        "founder's Android phone:\n\n" + result.stdout + result.stderr)


# ------------------------------------------------------------------ guards
# These are cheap, run everywhere (no Node needed), and stop the specific
# mistakes that caused the reported fault from creeping back in.

def test_finals_are_never_stored_by_result_index_alone():
    """THE regression guard for the reported bug.

    Storing finals in a map keyed by the browser's `resultIndex` is safe on a
    laptop (one long session, indices only grow) and WRONG on a phone (Android
    restarts on silence and the indices reset to 0, overwriting earlier
    phrases). The fix locks each session's text before the restart.
    """
    source = open(APP_JS, encoding="utf-8").read()
    assert "lockSession" in source, \
        "the per-session lock is gone — Android will scramble dictation again"
    assert "rec.onend = function () {\n        lockSession();" in source, \
        ("onend no longer locks the session before restarting. The next "
         "session's indices start at 0 and will overwrite what was already "
         "said — this is exactly the bug the founder reported.")


def test_spoken_punctuation_is_supported():
    """Android never inserts punctuation; the user must be able to say it."""
    source = open(APP_JS, encoding="utf-8").read()
    assert "_punctuate" in source, "spoken punctuation support was removed"
    for spoken in ("full stop", "comma", "question mark", "new line"):
        assert spoken in source, f"the spoken mark '{spoken}' is no longer handled"


def test_longer_punctuation_phrases_are_matched_first():
    """'full stop' must beat 'stop', or half the phrase is eaten.

    Reads the real order in the table rather than trusting a comment.
    """
    source = open(APP_JS, encoding="utf-8").read()
    table = source[source.index("PUNCTUATION: ["):source.index("/* Turn spoken marks")]
    assert table.index("full stop") < table.index("comma"), \
        "'full stop' must be matched before shorter marks"
    assert "\\bstop\\b" not in table, \
        ("a bare 'stop' pattern would turn 'tell them to stop' into "
         "'tell them to.' — always match the full phrase")


def test_a_genuine_repetition_is_not_silently_swallowed():
    """A person really may say 'no no'. Over-eager de-duplication is a bug too."""
    source = open(APP_JS, encoding="utf-8").read()
    assert "_isEcho" in source
    body = source[source.index("_isEcho: function"):]
    body = body[:body.index("start: function")]
    assert "a === b || a.slice(-b.length) === b" in body, \
        ("the echo check is no longer an exact tail match. Anything fuzzier "
         "will swallow real speech like 'no no' or 'yes yes'.")
