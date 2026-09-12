import os
from zoneinfo import ZoneInfo

# Load private .env file if present (never committed to git)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _data_uri(default_rel: str) -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return "sqlite:///" + os.path.join(DATA_DIR, default_rel)
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        # relative path with a folder part (e.g. data/app.db) resolves from project root
        base = BASE_DIR if os.path.dirname(rel) else DATA_DIR
        return "sqlite:///" + os.path.join(base, rel)
    return url


def _connect_args() -> dict:
    """Driver-level connection timeouts (PostgreSQL only; SQLite has no socket).

    connect_timeout caps the TCP handshake; the keepalive settings make the
    kernel detect a silently dropped connection in ~30s instead of hanging on
    a dead socket for many minutes.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        return {}
    return {
        "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "application_name": "hospital-suite",
    }


class Config:
    APP_VERSION = "1.8.1"
    # F-004: a hardcoded fallback key is worse than no key — every session it
    # signs is forgeable by anyone who has read this file (it is public on
    # GitHub). Missing SECRET_KEY must therefore FAIL LOUDLY at boot, not
    # silently weaken the app. Render sets it via generateValue: true in
    # render.yaml; tests set their own in conftest. Local development opts in
    # explicitly with FLASK_ENV=development, which generates an ephemeral key
    # and says so loudly (sessions do not survive a restart — by design).
    if not (os.environ.get("SECRET_KEY") or "").strip():
        if os.environ.get("FLASK_ENV") == "development":
            import secrets as _secrets
            import sys as _sys
            print("=" * 72, file=_sys.stderr)
            print("WARNING: SECRET_KEY is not set — using an EPHEMERAL random key.",
                  file=_sys.stderr)
            print("Everyone is logged out on every restart. For anything beyond a",
                  file=_sys.stderr)
            print("laptop demo: export SECRET_KEY=$(python -c \"import secrets;"
                  "print(secrets.token_hex(32))\")",
                  file=_sys.stderr)
            print("=" * 72, file=_sys.stderr)
            SECRET_KEY = _secrets.token_hex(32)
        else:
            raise RuntimeError(
                "SECRET_KEY is not set — refusing to start with a guessable "
                "session key. Fix: on Render it is generated automatically "
                "(render.yaml generateValue); anywhere else run "
                "`export SECRET_KEY=$(python -c \"import secrets; "
                "print(secrets.token_hex(32))\")` and redeploy/restart.")
    else:
        SECRET_KEY = os.environ["SECRET_KEY"].strip()
    SQLALCHEMY_DATABASE_URI = _data_uri("app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Resilient connections: validate before use (pool_pre_ping) and recycle
    # before the Supabase pooler drops idle connections — prevents
    # "SSL SYSCALL error: EOF detected" after idle periods.
    # FIX: explicit pool sizing (expert review S5, Render DB pooler gap)
    # Default 5+10 is fine for 1 worker. For >1 worker, set via env and add PgBouncer.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        # Bound every connection attempt. Without connect_timeout a database
        # that accepts TCP but never answers (Supabase pooler wobble, an IPv6
        # black-hole, a network partition) blocks the worker for the OS default
        # of ~130s. At boot that outlasts the host's health check, so the
        # container is killed and restarted forever and the site serves NOTHING
        # — not even static files. Fail fast instead and start in degraded mode.
        "connect_args": _connect_args(),
    }

    # --- Phase 1 hardening: Redis, Sentry, Object Storage ---
    REDIS_URL = os.environ.get("REDIS_URL", os.environ.get("REDIS_TLS_URL", ""))
    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
    # Object storage: db (default pilot), disk (dev/volume), s3 (Supabase Storage / R2 / S3)
    # For s3, set S3_BUCKET, S3_REGION, S3_ACCESS_KEY, S3_SECRET_KEY, S3_ENDPOINT
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    S3_REGION = os.environ.get("S3_REGION", "")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")  # for R2 / Supabase

    # --- NDPA / Compliance ---
    DPO_NAME = os.environ.get("DPO_NAME", "Hospital Admin")
    DPO_EMAIL = os.environ.get("DPO_EMAIL", "")
    DATA_RESIDENCY = os.environ.get("DATA_RESIDENCY", "Frankfurt, EU (Render) / AWS EU-West (Supabase) — configure per deployment")
    RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "2190"))  # 6 years default, floor 30 enforced in job
    TIMEZONE = ZoneInfo(os.environ.get("TIMEZONE", "Africa/Lagos"))

    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    REPORT_DIR = os.path.join(DATA_DIR, "reports")
    BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(DATA_DIR, "backups")
    BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "7"))
    # Hard floor between backups, in hours. A backup reads EVERY table — on a
    # metered-egress database a runaway backup loop is the most expensive
    # thing this app can do. The Setting-based per-day guard is primary; this
    # in-memory floor survives the case where settings are unreadable.
    MIN_BACKUP_INTERVAL_HOURS = float(os.environ.get("MIN_BACKUP_INTERVAL_HOURS", "20"))
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB evidence photos/files

    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8077")

    # WhatsApp Business Cloud API
    WHATSAPP_MODE = os.environ.get("WHATSAPP_MODE", "sandbox")
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
    WHATSAPP_REPORT_TEMPLATE = os.environ.get("WHATSAPP_REPORT_TEMPLATE", "")
    WHATSAPP_SIMULATE_FAILURE = os.environ.get("WHATSAPP_SIMULATE_FAILURE", "0") == "1"

    # Mail. Prefer a web API (Resend / Brevo / SendGrid): Render blocks SMTP.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", os.environ.get("SMTP_FROM", ""))
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", os.environ.get("MAIL_FROM", "no-reply@localhost"))
    SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"

    USSD_SHARED_SECRET = os.environ.get("USSD_SHARED_SECRET", "")

    # Load/capacity testing only: scales rate-limit thresholds (default 1 = production).
    # Set high (e.g. 100000) during load tests to measure raw serving capacity.
    RATE_LIMIT_SCALE = int(os.environ.get("RATE_LIMIT_SCALE", "1") or 1)

    # Push — Web Push VAPID for alarm-like notifications when closed (free, cost saver)
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@hospital.local")

    # Smart queue estimator — free AI-like logic
    QUEUE_ESTIMATOR_ENABLED = os.environ.get("QUEUE_ESTIMATOR_ENABLED", "1") == "1"

    # Cost saving: No SMS for patients inside hospital except emergency/complaints
    PATIENT_SMS_INSIDE_HOSPITAL = os.environ.get("PATIENT_SMS_INSIDE_HOSPITAL", "0") == "1"  # default OFF

    # SMS provider interface (§38): sandbox | termii | twilio | disabled
    SMS_MODE = os.environ.get("SMS_MODE", "sandbox")
    TERMII_API_KEY = os.environ.get("TERMII_API_KEY", "")
    TERMII_SENDER_ID = os.environ.get("TERMII_SENDER_ID", "")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
    # Twilio's WhatsApp sender is a DIFFERENT number from the SMS one, so it
    # gets its own setting. Falls back to TWILIO_FROM if only one is set.
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    WHATSAPP_TIMEOUT = float(os.environ.get("WHATSAPP_TIMEOUT", "15"))

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure cookies by default; set COOKIE_SECURE=0 only for plain-HTTP local dev.
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 10  # 10 hours

    # Durable storage backend: "db" (survives restarts on ephemeral hosts) | "disk"
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "db").lower()

    # Number of trusted reverse proxies in front of the app (Render/Cloudflare = 1).
    # Drives ProxyFix so rate limiting and audit logs see the real client IP.
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1") or 1)

    # Brute-force lockout (per username, complements the per-IP rate limiter)
    LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "10") or 10)
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15") or 15)

    # Hard ceiling on request body size — refuses oversized uploads before they
    # are buffered into memory (prevents a trivial memory-exhaustion crash).
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(8 * 1024 * 1024)))

    @classmethod
    def ensure_dirs(cls):
        for d in (DATA_DIR, cls.UPLOAD_DIR, cls.REPORT_DIR, cls.BACKUP_DIR,
                  os.path.join(cls.UPLOAD_DIR, "complaints"),
                  os.path.join(cls.UPLOAD_DIR, "inspections"),
                  os.path.join(cls.UPLOAD_DIR, "logos"),
                  os.path.join(cls.UPLOAD_DIR, "ca")):
            os.makedirs(d, exist_ok=True)
