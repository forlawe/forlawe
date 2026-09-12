"""F-004 regression: a missing SECRET_KEY must stop the boot, not weaken it.

The old fallback hardcoded "dev-insecure-key-change-me" — every session it
signed was forgeable by anyone who read the public repo. Config is imported
once per process, so these probes run real subprocesses with a controlled
environment (importing again in-process would not re-execute the class body).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _probe(extra_env: dict, code: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("SECRET_KEY", "FLASK_ENV")}
    env.update(extra_env)
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, cwd=ROOT, timeout=120)


def test_missing_secret_key_refuses_to_start():
    r = _probe({}, "from app.config import Config")
    assert r.returncode != 0, "app booted without SECRET_KEY — the insecure fallback is back"
    assert "SECRET_KEY is not set" in r.stderr


def test_development_mode_generates_an_ephemeral_key_and_warns():
    r = _probe({"FLASK_ENV": "development"},
               "from app.config import Config; print(Config.SECRET_KEY)")
    assert r.returncode == 0
    key = r.stdout.strip()
    assert len(key) >= 64 and key != "dev-insecure-key-change-me"
    assert "EPHEMERAL" in r.stderr, "dev mode must warn loudly about the ephemeral key"


def test_explicit_secret_key_is_used_verbatim():
    r = _probe({"SECRET_KEY": "regression-probe-key"},
               "from app.config import Config; print(Config.SECRET_KEY)")
    assert r.returncode == 0 and r.stdout.strip() == "regression-probe-key"
