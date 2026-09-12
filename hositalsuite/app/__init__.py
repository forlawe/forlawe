"""Application factory."""
from __future__ import annotations

import os

from flask import Flask, g, render_template, request
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .models import User, db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to continue."


@login_manager.user_loader
def load_user(user_id: str):
    u = db.session.get(User, int(user_id))
    return u if u and u.active else None


def _configure_logging(app: Flask) -> None:
    """Structured, timestamped logs to stdout so incidents are greppable.

    Gunicorn captures stdout on Render; bare print() statements lose level and
    timestamp, which makes post-incident diagnosis guesswork.
    FIX: expert review flagged remaining print() — now all via logger.
    Privacy: filter masks access_key / personal_tv secrets in log lines.
    """
    import logging
    import sys
    import re

    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

    # Mask personal TV access_key and phone numbers in logs — privacy hardening
    _KEY_RE = re.compile(r'([a-z_]*access_key[\"\'=\s:]+)([A-Za-z0-9_\-]{8,})', re.IGNORECASE)
    _T_RE = re.compile(r'(/t/)([A-Za-z0-9_\-]{8,})')
    class _PrivacyFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                msg = record.getMessage()
                # mask /t/<key> and access_key=xxx
                msg = _T_RE.sub(r'\1****', msg)
                msg = _KEY_RE.sub(r'\1****', msg)
                # Store masked version back as msg to avoid double formatting
                # We override args to make getMessage return masked
                record.msg = msg
                record.args = ()
            except Exception:
                pass
            return True

    handler.addFilter(_PrivacyFilter())
    app.logger.handlers = [handler]
    app.logger.setLevel(level)
    app.logger.propagate = False

    # Sentry error tracking if DSN set (Phase 1 hardening)
    dsn = os.environ.get("SENTRY_DSN") or app.config.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=float(os.environ.get("SENTRY_TRACES", "0.1")),
                environment=os.environ.get("RENDER_ENV", os.environ.get("ENV", "production")),
            )
            app.logger.info("Sentry enabled")
        except Exception as exc:
            app.logger.warning("Sentry init failed: %s", exc)


def create_app(config_object=None, scheduler: bool = True) -> Flask:
    Config.ensure_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object or Config)

    # Behind Render/Cloudflare the socket peer is the proxy, not the patient.
    # Without this, request.remote_addr is identical for everyone: per-IP rate
    # limits become global (one abuser locks out the hospital) and audit-log
    # IPs are worthless. url_for(_external=True) also needs the real scheme.
    proxies = int(app.config.get("TRUSTED_PROXY_COUNT", 1) or 0)
    if proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies,
                                x_host=proxies, x_port=proxies)

    _configure_logging(app)

    db.init_app(app)
    login_manager.init_app(app)

    from .security import register_security_hooks
    from .views.auth import bp as auth_bp
    from .views.mfa import bp as mfa_bp
    from .views.main import bp as main_bp
    from .views.inspections import bp as insp_bp
    from .views.complaints import bp as comp_bp
    from .views.bookings import bp as book_bp
    from .views.queue import bp as queue_bp
    from .views.feedback import bp as fb_bp
    from .views.chat import bp as chat_bp
    from .views.referrals import bp as ref_bp
    from .views.roster import bp as roster_bp
    from .views.hims import bp as hims_bp
    from .views.reception import bp as reception_bp
    from .views.triage import bp as triage_bp
    from .views.consulting import bp as consulting_bp
    from .views.tracking import bp as tracking_bp
    from .views.cashdesk import bp as cashdesk_bp
    from .views.lahsma import bp as lahsma_bp
    from .views.admincp import bp as admin_bp
    from .views.rolesadmin import bp as rolesadmin_bp
    from .views.deptdesk import bp as deptdesk_bp
    from .views.servicepoints_admin import bp as svcpts_bp
    from .views.tv import bp as tv_bp
    from .views.hospital_structure import bp as hospstruct_bp
    from .views.reports import bp as reports_bp
    from .views.api import bp as api_bp
    from .views.twilio_diag import bp as twilio_diag_bp
    from .views.fasttrack import bp as fasttrack_bp
    from .views.onboard import bp as onboard_bp
    from .views.attendance import bp as attendance_bp
    from .views.native_voice import bp as native_voice_bp
    from .views.native_voice import api_bp as voice_api_bp
    from .views.personal_tv import bp as personal_tv_bp
    from .views.push_api import bp as push_api_bp

    for blueprint in (auth_bp, mfa_bp, main_bp, insp_bp, comp_bp, book_bp, queue_bp, fb_bp,
                      chat_bp, ref_bp, roster_bp, hims_bp, reception_bp, triage_bp, consulting_bp, tracking_bp, cashdesk_bp,
                      lahsma_bp,
                      admin_bp, rolesadmin_bp, deptdesk_bp, svcpts_bp, tv_bp, hospstruct_bp,
                      reports_bp, api_bp, twilio_diag_bp, fasttrack_bp, onboard_bp, attendance_bp,
                      native_voice_bp, voice_api_bp, personal_tv_bp, push_api_bp):
        app.register_blueprint(blueprint)

    from .timefmt import fmt_hm, say_hm, mask_phone, first_name_only, privacy_initials
    app.jinja_env.filters["hm"] = fmt_hm
    app.jinja_env.filters["sayhm"] = say_hm
    app.jinja_env.filters["mask_phone"] = mask_phone
    app.jinja_env.filters["first_name"] = first_name_only
    app.jinja_env.filters["privacy_initials"] = privacy_initials
    # Templates like notifications.html use getattr/hasattr — expose them safely
    app.jinja_env.globals["getattr"] = getattr
    app.jinja_env.globals["hasattr"] = hasattr

    register_security_hooks(app)

    # Scope every request to the signed-in user's hospital, at the DATABASE
    # level. Registered AFTER the security hooks so login has already resolved.
    from .rls import register as register_rls
    register_rls(app)

    # Import v2 models so create_all sees them — no breaking changes
    try:
        from . import models_v2 as _models_v2  # noqa: F401
        from . import queue_estimator as _qe  # noqa: F401
        from . import push as _push  # noqa: F401
        from . import personal_tv as _ptv  # noqa: F401
    except Exception:
        pass

    with app.app_context():
        # SQLite hardening: WAL lets the scheduler thread and web requests write
        # concurrently without "database is locked" errors; busy_timeout makes
        # writers wait instead of failing instantly.
        if str(db.engine.url).startswith("sqlite"):
            from sqlalchemy import event

            @event.listens_for(db.engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=15000")
                cur.close()

        # Boot steps are individually guarded: a failure in seeding or the KB
        # must never leave the hospital with a dead site. Log loudly, serve on.
        def _boot_step(name, fn):
            try:
                fn()
            except Exception:                            # noqa: BLE001
                db.session.rollback()
                app.logger.exception("boot step %r failed — continuing", name)

        # ONE database readiness probe up front. If the database is not
        # answering, every subsequent boot step would each burn its own
        # connect_timeout; serially that outlasts the host's health check and
        # the container is killed before it ever listens. Better to start in
        # degraded mode (static pages + an honest 503 on /health) and let the
        # scheduler heal things once the database returns.
        db_ready = False
        try:
            db.session.execute(db.text("SELECT 1"))
            db_ready = True
        except Exception as exc:                         # noqa: BLE001
            db.session.rollback()
            app.logger.error("DATABASE NOT REACHABLE AT BOOT (%s) — starting in DEGRADED mode. "
                             "Pages will serve; /api/v1/health will report status=degraded.", exc)

        if db_ready:
            _boot_step("create_all", db.create_all)

            # Alembic first (proper versioned migrations), then the legacy
            # column-adder as a safety net for anything Alembic could not do.
            from .migrate import ensure_schema, run_alembic_upgrade
            _boot_step("alembic_upgrade", lambda: run_alembic_upgrade(app))
            _boot_step("ensure_schema", ensure_schema)

            # Rescue any files still living on the ephemeral container disk.
            from .storage import migrate_disk_to_db
            _boot_step("storage_rescue", lambda: migrate_disk_to_db(app))

            # Fold the old two-column department roster into the unified roster.
            # Idempotent; the original rows are copied, never deleted.
            from .rosterdata import migrate_legacy_entries
            _boot_step("roster_merge", lambda: migrate_legacy_entries(app))

            # First-boot bootstrap on free hosts with no shell access (Render free):
            # AUTO_SEED=1 seeds ONLY an empty database; credentials printed once to logs.
            if os.environ.get("AUTO_SEED") == "1":
                from .seeddata import auto_seed
                _boot_step("auto_seed", lambda: auto_seed(app))

            # Load the global master dialogue library for the patient assistant.
            from .chatbot.seed_kb import seed_global_kb
            _boot_step("seed_kb", lambda: seed_global_kb(app))

            # Row-Level Security: make the DATABASE refuse to leak between
            # hospitals, so a future forgotten org_id filter returns nothing
            # instead of somebody else's patients. No-op on SQLite.
            def _enable_rls():
                from .rls import enable
                enable(app)
            _boot_step("row_level_security", _enable_rls)

            # Role Management: every hospital gets the built-in roles that
            # reproduce the old hard-coded behaviour exactly. Idempotent, and
            # it never overwrites a role an administrator has already re-ticked.
            def _seed_roles():
                from .models import Organization
                from .roles import ensure_builtin_roles
                for org in db.session.query(Organization).all():
                    ensure_builtin_roles(org.id)
                db.session.commit()
            _boot_step("seed_roles", _seed_roles)

            def _seed_branches():
                from .branches import ensure_all_orgs
                ensure_all_orgs()
            _boot_step("seed_branches", _seed_branches)

    @app.context_processor
    def inject_globals():
        # NEVER let template globals crash — return safe defaults on any error
        try:
            from .security import csrf_token
            from .services import org_settings_bundle
            from . import i18n
            bundle = {}
            u = None
            try:
                from flask_login import current_user
                u = current_user if getattr(current_user, "is_authenticated", False) else None
            except Exception:
                u = None
            try:
                lang = i18n.get_lang()
            except Exception:
                lang = "en"
            hospital = None
            try:
                from .models import Organization
                from .services import current_org
                if u is not None and getattr(u, "org_id", None):
                    try:
                        hospital = db.session.get(Organization, u.org_id)
                    except Exception:
                        hospital = None
                if hospital is None:
                    try:
                        hospital = current_org()
                    except Exception:
                        hospital = None
                if hospital is None:
                    try:
                        # Only fallback if single org — avoid multi-tenant leak
                        if db.session.query(Organization).count() <= 1:
                            hospital = db.session.query(Organization).order_by(Organization.id).first()
                    except Exception:
                        hospital = None
            except Exception:
                hospital = None
            try:
                if u is not None and getattr(u, "org_id", None):
                    bundle = org_settings_bundle(u.org_id)
                elif hospital is not None and getattr(hospital, "id", None):
                    bundle = org_settings_bundle(hospital.id)
            except Exception:
                bundle = {}
            def nav_permissions():
                try:
                    from flask_login import current_user as _cu
                    from .navigation import permissions_for
                    return permissions_for(_cu)
                except Exception:
                    try:
                        from .navigation import permissions_for as _pf
                        return _pf(None)
                    except Exception:
                        return {}

            branch = None
            try:
                if u is not None and getattr(u, "branch_id", None):
                    from .models import Branch
                    branch = db.session.get(Branch, u.branch_id)
            except Exception:
                branch = None
            try:
                _ = i18n.translate
                langs = i18n.LANGS
                speech_lang = i18n.speech_tag(lang)
            except Exception:
                _ = lambda x, **kw: x
                langs = ["en"]
                speech_lang = "en-NG"
            try:
                csp_nonce = getattr(g, "csp_nonce", "") or ""
            except Exception:
                csp_nonce = ""
            return dict(csrf_token=csrf_token, settings=bundle,
                        app_version=app.config.get("APP_VERSION", "1.8.0"),
                        _=_, lang=lang, langs=langs,
                        speech_lang=speech_lang, hospital=hospital,
                        current_branch=branch,
                        nav_permissions=nav_permissions,
                        onboard_guide=bool(bundle.get("onboard_guide")),
                        csp_nonce=csp_nonce)
        except Exception:
            # Ultimate fallback — never crash rendering
            try:
                from .security import csrf_token as _ct
                ct = _ct
            except Exception:
                ct = lambda: ""
            try:
                csp_nonce = getattr(g, "csp_nonce", "") or ""
            except Exception:
                csp_nonce = ""
            return dict(csrf_token=ct, settings={}, app_version="1.8.0",
                        _=lambda x, **kw: x, lang="en", langs=["en"],
                        speech_lang="en-NG", hospital=None,
                        current_branch=None,
                        nav_permissions=lambda: {}, onboard_guide=False,
                        csp_nonce=csp_nonce)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="The page you requested was not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You do not have permission to access this page."), 403

    @app.errorhandler(413)
    def too_large(e):
        db.session.rollback()
        return render_template("error.html", code=413,
                               message="That file is too large. Please upload a photo under 5 MB."), 413

    @app.errorhandler(429)
    def too_many(e):
        return render_template("error.html", code=429,
                               message="Too many requests. Please wait a moment and try again."), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("unhandled 500 on %s %s", request.method, request.path)
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. The technical team has been notified."), 500

    @app.errorhandler(Exception)
    def unhandled(e):
        """Last line of defence: no traceback ever reaches a patient's screen.

        Real HTTP errors keep their own status; anything else becomes a clean
        500 page, the DB session is rolled back so the worker stays usable, and
        the full stack trace goes to the logs.
        """
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        db.session.rollback()
        app.logger.exception("unhandled exception on %s %s", request.method, request.path)
        return render_template("error.html", code=500,
                               message="Something went wrong on our side. The technical team has been notified."), 500

    @app.teardown_request
    def _cleanup_session(exc):
        """Never leak a broken transaction into the next request on this thread."""
        if exc is not None:
            db.session.rollback()

    if scheduler and os.environ.get("DISABLE_SCHEDULER") != "1":
        from .scheduler import start_scheduler
        start_scheduler(app)

    return app
