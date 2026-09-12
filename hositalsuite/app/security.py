"""Security primitives: CSRF, rate limiting, password policy, safe uploads, RBAC."""
from __future__ import annotations

import functools
import os
import re
import secrets
import time
from collections import defaultdict, deque

from flask import abort, redirect, render_template, request, session, url_for
from flask_login import current_user

from .config import Config

# ------------------------------------------------------------------ CSRF
def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


CSRF_EXEMPT: set[str] = set()  # endpoint names exempt (webhooks / USSD API)


def csrf_exempt(view_name: str):
    """Usage: @csrf_exempt('api.whatsapp_webhook') above the route decorator."""
    CSRF_EXEMPT.add(view_name)

    def deco(fn):
        return fn
    return deco


def csrf_protect():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if request.endpoint in CSRF_EXEMPT:
        return None
    token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    # F-010: constant-time compare — a plain equality check would leak the
    # token byte-by-byte through timing; negligible risk, free to remove.
    if not token or not secrets.compare_digest(
            token.encode(), (session.get("_csrf") or "").encode()):
        abort(403, description="Invalid or missing CSRF token. Refresh the page and try again.")
    return None


# ------------------------------------------------------------------ RBAC
def require_login(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def is_admin_manager_on_duty(user) -> bool:
    """v1.7.18: Only Admin Manager rostered for TODAY has full ADMIN_MANAGER privileges."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "role", "") != "ADMIN_MANAGER":
        return True  # not AM role, not relevant
    try:
        from .services import on_duty
        from .models import now_naive
        today = now_naive().date()
        duty = on_duty(user.org_id, today)
        return bool(duty and duty.id == user.id)
    except Exception:
        return False


def require_role(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                abort(403)
            # v1.7.18: ADMIN_MANAGER day-on-duty enforcement
            if current_user.role == "ADMIN_MANAGER" and "ADMIN_MANAGER" in roles:
                # SUPER_ADMIN can always, but if ADMIN_MANAGER role required, check on-duty
                # Unless also SUPER_ADMIN in roles (then super can pass), check duty for AM
                if not is_admin_manager_on_duty(current_user):
                    # Allow if user also has SUPER_ADMIN via extra role? Check via roles_of
                    try:
                        from .roles import roles_of
                        extra_roles = [r.code for r in roles_of(current_user)]
                        if "SUPER_ADMIN" in extra_roles:
                            pass  # super admin extra hat allows
                        else:
                            # Check if on-duty AM, else 403 with helpful message
                            # But still allow viewing roster (view) — handled in navigation, here we block full AM actions
                            # For routes that include ADMIN_MANAGER, off-duty AM gets 403
                            abort(403, description="Admin Manager access is limited to the Admin Manager on duty TODAY (Roster & Day-On-Duty).")
                    except Exception:
                        abort(403, description="Admin Manager access is limited to the Admin Manager on duty TODAY.")
            return fn(*a, **kw)
        return wrapper
    return deco


def require_admin_manager_on_duty(fn):
    """Decorator: only on-duty Admin Manager (or SUPER_ADMIN) can access."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if getattr(current_user, "is_super", False):
            return fn(*a, **kw)
        if getattr(current_user, "role", "") == "ADMIN_MANAGER":
            if is_admin_manager_on_duty(current_user):
                return fn(*a, **kw)
            abort(403, description="Only the Admin Manager on duty TODAY can perform this action.")
        # Also allow SUPER_ADMIN via extra role
        try:
            from .roles import roles_of
            if any(r.code == "SUPER_ADMIN" for r in roles_of(current_user)):
                return fn(*a, **kw)
        except Exception:
            pass
        abort(403)
    return wrapper


def same_org_or_super(entity_org_id: int):
    """Ensure the current user belongs to the entity's tenant (super admin of same org)."""
    if current_user.org_id != entity_org_id:
        abort(403)


# ------------------------------------------------------------------ rate limiting
# FIX S5 (expert review): in-memory per-process breaks with >1 worker/instance.
# Now supports Redis if REDIS_URL is set, fallback to in-memory for single-worker pilot.
class RateLimiter:
    def __init__(self):
        self.hits = defaultdict(deque)
        self._redis = None
        self._redis_checked = False

    def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        url = os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL", "")
        if not url:
            try:
                from flask import current_app
                url = current_app.config.get("REDIS_URL", "") if current_app else ""
            except Exception:
                url = ""
        if url:
            try:
                import redis  # type: ignore
                self._redis = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
                self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def allow(self, key: str, limit: int, window: float) -> bool:
        r = self._get_redis()
        if r:
            try:
                # Redis sliding window via INCR + EXPIRE
                pipe = r.pipeline()
                pipe.incr(key)
                pipe.ttl(key)
                count, ttl = pipe.execute()
                if ttl == -1:
                    r.expire(key, int(window))
                return int(count) <= limit
            except Exception:
                # Fall back to memory if Redis fails
                pass

        now = time.monotonic()
        # bound memory: drop stale keys occasionally
        if len(self.hits) > 10000:
            for k in [k for k, dq in self.hits.items() if not dq or now - dq[-1] > 600]:
                del self.hits[k]
        dq = self.hits[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


_limiter = RateLimiter()


def client_ip() -> str:
    """Real client IP behind Render/Cloudflare.

    ProxyFix already rewrites remote_addr from X-Forwarded-For, but Cloudflare's
    CF-Connecting-IP is authoritative when present. Without this every visitor
    shares the proxy's IP, which makes per-IP rate limits effectively global
    (one bad actor locks out the whole hospital) and makes audit-log IPs useless.
    """
    cf = request.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()[:64]
    return (request.remote_addr or "unknown")[:64]


def rate_limit(limit: int = 10, window: float = 60.0, key_extra: str = ""):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            from flask import current_app
            # RATE_LIMIT_SCALE relaxes limits for capacity/load testing only.
            # Default 1 = production limits. NEVER set high in real deployments.
            scale = int(current_app.config.get("RATE_LIMIT_SCALE", 1) or 1)
            effective = limit * scale
            key = f"{request.endpoint}|{client_ip()}|{key_extra}"
            if not _limiter.allow(key, effective, window):
                return render_template("error.html", code=429,
                                       message="Too many requests. Please wait a moment and try again."), 429
            return fn(*a, **kw)
        return wrapper
    return deco


# ------------------------------------------------------------------ safe redirects
def safe_next(target: str | None, fallback: str = "/") -> str:
    """Return `target` only if it is a path on THIS site, else `fallback`.

    A bare startswith("/") test is NOT enough: "//evil.com" starts with "/" but
    browsers treat it as a protocol-relative URL and navigate off-site. That is
    an open redirect — a phishing link that looks like it belongs to the
    hospital. Also rejects backslash tricks and any absolute URL.
    """
    if not target:
        return fallback
    t = target.strip()
    if not t.startswith("/"):
        return fallback
    if t.startswith("//") or t.startswith("/" + chr(92)):
        return fallback
    if "://" in t:
        return fallback
    return t


# ------------------------------------------------------------------ phone numbers
# Nigerian mobile numbers, local (08012345678) or international (+2348012345678).
PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def clean_phone(raw: str) -> str:
    """Normalise a typed phone number: strip spaces, dashes and brackets."""
    return (raw or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def valid_phone(raw: str) -> bool:
    return bool(PHONE_RE.match(clean_phone(raw)))


# ------------------------------------------------------------------ password policy
# Hard-to-guess rule lives in app.accounts so login, reset and admin share it.
from .accounts import PASSWORD_MIN_LEN, password_strength_errors  # noqa: E402,F401


# ------------------------------------------------------------------ file uploads
ALLOWED_UPLOAD_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".pdf": "application/pdf",
}
UPLOAD_MAGIC = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG", ".png"),
    (b"RIFF", ".webp"),
    (b"%PDF", ".pdf"),
]


def validate_upload(file_storage) -> tuple[str | None, str | None]:
    """Return (safe_filename, error). Validates extension, size and magic bytes."""
    if file_storage is None or not file_storage.filename:
        return None, "No file was provided."
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        return None, "Only JPG, PNG, WEBP or PDF files are allowed."
    data = file_storage.read(Config.MAX_UPLOAD_BYTES + 1)
    if len(data) > Config.MAX_UPLOAD_BYTES:
        return None, "File is too large (maximum 5 MB)."
    if not any(data.startswith(m) for m, _ in UPLOAD_MAGIC):
        return None, "The file content does not match a valid image or PDF."
    safe = f"{int(time.time())}-{secrets.token_hex(6)}{ext}"
    return safe, None


def save_upload(file_storage, subfolder: str, *, org_id: int | None = None) -> tuple[str | None, str | None]:
    """Validate + persist an upload to DURABLE storage. Returns (key, error).

    Writes through app.storage, so uploads survive restarts on hosts with an
    ephemeral filesystem (Render free) instead of vanishing on the next deploy.
    """
    from . import storage
    safe, err = validate_upload(file_storage)
    if err:
        return None, err
    file_storage.seek(0)
    data = file_storage.read(Config.MAX_UPLOAD_BYTES + 1)
    if len(data) > Config.MAX_UPLOAD_BYTES:
        return None, "File is too large (maximum 5 MB)."
    key = f"{subfolder}/{safe}"
    try:
        storage.put(key, data, org_id=org_id, filename=file_storage.filename)
    except Exception:                                    # noqa: BLE001
        from flask import current_app
        current_app.logger.exception("upload failed for key %s", key)
        return None, "The file could not be saved. Please try again."
    return key, None


def resolve_upload_path(rel_path: str) -> str | None:
    """Legacy on-disk resolver, kept traversal-proof for pre-storage rows."""
    if not rel_path:
        return None
    root = os.path.normpath(Config.UPLOAD_DIR)
    full = os.path.normpath(os.path.join(root, rel_path))
    # commonpath is the correct containment test; startswith is fooled by
    # sibling directories that share a prefix (e.g. "/data/uploads-evil").
    try:
        if os.path.commonpath([full, root]) != root:
            return None
    except ValueError:
        return None
    return full if os.path.isfile(full) else None


# ------------------------------------------------------------------ hooks
def _generate_csp_nonce() -> str:
    # 16 bytes urlsafe is 22 chars, enough entropy for CSP nonce per request
    return secrets.token_urlsafe(16)

def _csp_before():
    # Generate per-request nonce for inline scripts. Stored in g and
    # made available to templates via context processor in __init__.py.
    from flask import g
    g.csp_nonce = _generate_csp_nonce()

def register_security_hooks(app):
    app.before_request(_csp_before)
    app.before_request(csrf_protect)

    from .views.auth import enforce_pending_password_change
    from .views.mfa import enforce_mfa
    app.before_request(enforce_pending_password_change)
    app.before_request(enforce_mfa)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)")
        # HSTS: only meaningful over TLS, and must never be sent on plain-HTTP dev.
        if request.is_secure:
            resp.headers.setdefault("Strict-Transport-Security",
                                    "max-age=31536000; includeSubDomains")
        # CSP: script-src now uses per-request nonce instead of 'unsafe-inline'.
        # style-src still allows 'unsafe-inline' because the app has many
        # style=\"\" attributes which would otherwise require 'unsafe-hashes' or a
        # full CSS refactor. Inline <style> tags use the nonce where present.
        # This removes the main XSS vector (inline scripts) while keeping the
        # mobile-first UI working. Next step: extract style attributes to classes
        # and switch style-src to nonce-only.
        from flask import g as _g
        nonce = getattr(_g, "csp_nonce", "") or ""
        # Build CSP: if nonce present, include it for script and style
        script_part = f"'self' 'nonce-{nonce}'" if nonce else "'self'"
        style_part = f"'self' 'unsafe-inline' 'nonce-{nonce}'" if nonce else "'self' 'unsafe-inline'"
        csp_value = (
            "default-src 'self'; "
            "img-src 'self' data: https://tile.openstreetmap.org https://*.tile.openstreetmap.org; "
            f"style-src {style_part}; "
            f"script-src {script_part}; worker-src 'self'; connect-src 'self'; font-src 'self' data:; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        resp.headers.setdefault("Content-Security-Policy", csp_value)
        # Expose nonce in header for debugging / future strict-dynamic?
        if nonce:
            resp.headers.setdefault("X-CSP-Nonce", nonce)
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        resp.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if request.path.startswith("/static/"):
            resp.headers.setdefault("Cache-Control", "public, max-age=3600")
        else:
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp
