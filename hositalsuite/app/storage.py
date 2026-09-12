"""Durable file storage.

WHY THIS EXISTS
---------------
Render (and most cheap PaaS hosts) give you an **ephemeral filesystem**: every
deploy, restart or idle-spin-down wipes the container disk. The app used to write
complaint evidence photos, inspection photos, the hospital logo and every generated
PDF to `data/` inside the container — so all of it silently disappeared. The live
symptom was `/branding/logo` returning 404 for an already-uploaded logo.

This module puts every binary the app owns behind ONE interface with a pluggable
backend, so the storage decision is a config switch, not a code change:

    STORAGE_BACKEND=db     -> bytes live in the database (default; survives restarts)
    STORAGE_BACKEND=disk   -> local filesystem (dev / when a real volume is mounted)
    STORAGE_BACKEND=s3     -> S3-compatible object storage (Supabase Storage, R2, S3) — recommended for >1000 files

Keys look like ``"complaints/1737052800-a1b2c3d4e5f6.jpg"``. Legacy rows that hold a
bare filesystem path still resolve: `get()` falls back to reading the old location,
and `migrate_disk_to_db()` sweeps anything left on disk into the database at boot.

FIX 2026-08-27 (expert review): DB backend bloats DB at scale. S3 backend added.
Render Postgres does NOT ship pooler — see RENDER_DB_MIGRATION.md
"""
from __future__ import annotations

import hashlib
import io
import os
import secrets
import time

from flask import current_app, send_file

from .models import StoredFile, db

# ------------------------------------------------------------------ helpers
CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".pdf": "application/pdf", ".csv": "text/csv",
    ".db": "application/octet-stream",
}


def content_type_for(key: str) -> str:
    return CONTENT_TYPES.get(os.path.splitext(key or "")[1].lower(), "application/octet-stream")


def backend() -> str:
    try:
        return (current_app.config.get("STORAGE_BACKEND") or "db").lower()
    except RuntimeError:          # outside app context (CLI, tests)
        return os.environ.get("STORAGE_BACKEND", "db").lower()


def new_key(folder: str, ext: str) -> str:
    """Collision-resistant, non-guessable key. Never uses the client filename."""
    return f"{folder}/{int(time.time())}-{secrets.token_hex(6)}{ext}"


def _disk_path(key: str) -> str | None:
    """Resolve a key to a path under UPLOAD_DIR, refusing traversal."""
    from .config import Config
    if not key:
        return None
    root = os.path.normpath(Config.UPLOAD_DIR)
    full = os.path.normpath(os.path.join(root, key))
    # os.path.commonpath is traversal-proof; str.startswith is not ("/updata" bug)
    try:
        if os.path.commonpath([full, root]) != root:
            return None
    except ValueError:
        return None
    return full


# ------------------------------------------------------------------ S3 helpers
def _s3_client():
    """Return boto3 client if S3 backend configured, else None."""
    try:
        import boto3  # type: ignore
        from botocore.config import Config as BotoConfig  # type: ignore
        cfg = current_app.config
        bucket = cfg.get("S3_BUCKET") or os.environ.get("S3_BUCKET")
        if not bucket:
            return None, None
        # Support R2 / Supabase S3-compatible endpoints
        endpoint = cfg.get("S3_ENDPOINT") or os.environ.get("S3_ENDPOINT")
        region = cfg.get("S3_REGION") or os.environ.get("S3_REGION") or "auto"
        access = cfg.get("S3_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY")
        secret = cfg.get("S3_SECRET_KEY") or os.environ.get("S3_SECRET_KEY")
        client_kwargs = {}
        if endpoint:
            client_kwargs["endpoint_url"] = endpoint
        if region and region != "auto":
            client_kwargs["region_name"] = region
        if access and secret:
            client_kwargs["aws_access_key_id"] = access
            client_kwargs["aws_secret_access_key"] = secret
        client = boto3.client("s3", config=BotoConfig(signature_version="s3v4"), **client_kwargs)
        return client, bucket
    except Exception:
        return None, None


# ------------------------------------------------------------------ write
def put(key: str, data: bytes, *, org_id: int | None = None,
        filename: str | None = None, content_type: str | None = None) -> str:
    """Store bytes under `key`. Idempotent: re-putting the same key overwrites."""
    ct = content_type or content_type_for(key)
    b = backend()
    if b == "disk":
        full = _disk_path(key)
        if not full:
            raise ValueError(f"unsafe storage key: {key!r}")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)
        return key
    if b == "s3":
        client, bucket = _s3_client()
        if client and bucket:
            try:
                client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=ct)
                # Also keep metadata in DB without blob to keep total_bytes accurate and for listing
                row = db.session.query(StoredFile).filter_by(key=key).first()
                digest = hashlib.sha256(data).hexdigest()
                if row is None:
                    # Store empty data for S3 backend to avoid bloat, but keep metadata
                    row = StoredFile(key=key, org_id=org_id, folder=key.split("/")[0] if "/" in key else "",
                                     filename=filename or os.path.basename(key), content_type=ct,
                                     size=len(data), sha256=digest, data=b"")
                    db.session.add(row)
                else:
                    row.size, row.sha256, row.content_type = len(data), digest, ct
                    row.data = b""  # don't store blob in DB when S3 active
                    if org_id is not None:
                        row.org_id = org_id
                db.session.flush()
                return key
            except Exception as exc:
                try:
                    current_app.logger.warning("s3 put failed for %s: %s — falling back to db", key, exc)
                except Exception:
                    pass
        # Fall through to db if S3 not configured or failed

    row = db.session.query(StoredFile).filter_by(key=key).first()
    digest = hashlib.sha256(data).hexdigest()
    if row is None:
        row = StoredFile(key=key, org_id=org_id, folder=key.split("/")[0] if "/" in key else "",
                         filename=filename or os.path.basename(key), content_type=ct,
                         size=len(data), sha256=digest, data=data)
        db.session.add(row)
    else:
        row.data, row.size, row.sha256, row.content_type = data, len(data), digest, ct
        if org_id is not None:
            row.org_id = org_id
    db.session.flush()
    return key


def put_file(local_path: str, key: str, *, org_id: int | None = None) -> str:
    with open(local_path, "rb") as fh:
        return put(key, fh.read(), org_id=org_id, filename=os.path.basename(local_path))


# ------------------------------------------------------------------ read
def get(key: str) -> bytes | None:
    """Return the bytes for `key`, or None. Falls back to legacy disk locations."""
    if not key:
        return None
    b = backend()
    if b == "s3":
        client, bucket = _s3_client()
        if client and bucket:
            try:
                resp = client.get_object(Bucket=bucket, Key=key)
                return resp["Body"].read()
            except Exception:
                pass
        # Fall through to DB if S3 miss

    if b != "disk":
        row = db.session.query(StoredFile).filter_by(key=key).first()
        if row is not None:
            # If S3 backend but row has empty data (migrated), try S3 again, else return blob
            if row.data:
                return row.data
            # Empty data means S3 backend expected — try S3 one more time, else None
            if b == "s3":
                client, bucket = _s3_client()
                if client and bucket:
                    try:
                        resp = client.get_object(Bucket=bucket, Key=key)
                        return resp["Body"].read()
                    except Exception:
                        pass
            else:
                # For db backend, empty data shouldn't happen, but return None to trigger disk fallback
                if row.size == 0:
                    pass
                else:
                    return row.data

    # legacy / disk backend: try the key as a relative path, then as an absolute path
    full = _disk_path(key)
    for candidate in (full, key if os.path.isabs(key) else None):
        if candidate and os.path.isfile(candidate):
            with open(candidate, "rb") as fh:
                return fh.read()
    return None


def exists(key: str) -> bool:
    return get(key) is not None


def send(key: str, *, as_attachment: bool = False, download_name: str | None = None,
         max_age: int = 0, mimetype: str | None = None):
    """Flask response for a stored object. Raises FileNotFoundError if missing."""
    data = get(key)
    if data is None:
        raise FileNotFoundError(key)
    return send_file(io.BytesIO(data),
                     mimetype=mimetype or content_type_for(key),
                     as_attachment=as_attachment,
                     download_name=download_name or os.path.basename(key),
                     max_age=max_age)


def delete(key: str) -> None:
    if not key:
        return
    db.session.query(StoredFile).filter_by(key=key).delete()
    full = _disk_path(key)
    if full and os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


def total_bytes(org_id: int | None = None) -> int:
    q = db.session.query(db.func.coalesce(db.func.sum(StoredFile.size), 0))
    if org_id is not None:
        q = q.filter(StoredFile.org_id == org_id)
    return int(q.scalar() or 0)


# ------------------------------------------------------------------ boot-time rescue
def migrate_disk_to_db(app) -> int:
    """Sweep anything still sitting on the ephemeral disk into durable storage.

    Runs once at boot. Best-effort and idempotent: files already in the DB are
    skipped, and any failure is logged rather than blocking startup.
    """
    if backend() == "disk":
        return 0
    from .config import Config

    # If the database is unhealthy, ABORT the whole sweep immediately. Retrying
    # per-file multiplies the connection timeout by the number of files (37
    # files x 10s = 6 minutes), which outlasts the host's health check and puts
    # the container in a restart loop that serves nothing at all.
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as exc:                             # noqa: BLE001
        db.session.rollback()
        app.logger.warning("storage: skipping disk rescue, database not ready (%s)", exc)
        return 0

    moved = 0
    failures = 0
    for root_dir in (Config.UPLOAD_DIR, Config.REPORT_DIR):
        if not os.path.isdir(root_dir):
            continue
        base = os.path.normpath(root_dir)
        prefix = "" if base == os.path.normpath(Config.UPLOAD_DIR) else "reports"
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                local = os.path.join(dirpath, name)
                rel = os.path.relpath(local, base).replace(os.sep, "/")
                key = f"{prefix}/{rel}" if prefix else rel
                try:
                    if db.session.query(StoredFile.id).filter_by(key=key).first():
                        continue
                    if os.path.getsize(local) > 25 * 1024 * 1024:
                        continue
                    put_file(local, key)
                    moved += 1
                except Exception as exc:            # noqa: BLE001 - never block boot
                    db.session.rollback()
                    failures += 1
                    app.logger.warning("storage: could not migrate %s: %s", local, exc)
                    if failures >= 3:
                        app.logger.warning("storage: aborting disk rescue after %d failures; "
                                           "will retry on the next start", failures)
                        return moved
    if moved:
        db.session.commit()
        app.logger.info("storage: rescued %d file(s) from the ephemeral disk", moved)
    return moved


# ------------------------------------------------------------------ PDF helper
def build_pdf(builder, key: str, *args, org_id: int | None = None,
              dest_pos: int = -1, **kwargs) -> str:
    """Run a reportlab builder into a temp file, then persist the bytes durably.

    The pdfgen functions write to a filesystem path, and reportlab needs a real
    seekable file. We give it a temp file that is always cleaned up, then hand
    the bytes to durable storage so the PDF survives the next restart.

    `dest_pos` is where the builder expects its dest_path argument (-1 = last),
    because the pdfgen signatures are not consistent about it.
    """
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        call_args = list(args)
        if dest_pos < 0:
            call_args.append(tmp)
        else:
            call_args.insert(dest_pos, tmp)
        builder(*call_args, **kwargs)
        with open(tmp, "rb") as fh:
            put(key, fh.read(), org_id=org_id, content_type="application/pdf")
        return key
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def build_summary(org, title, subtitle, header, rows, key, *,
                  notes=None, verify_code=None) -> str:
    """Durable wrapper around pdfgen.build_summary_pdf (same argument order)."""
    from . import pdfgen
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        pdfgen.build_summary_pdf(org, title, subtitle, header, rows, tmp,
                                 notes=notes, verify_code=verify_code)
        with open(tmp, "rb") as fh:
            put(key, fh.read(), org_id=getattr(org, "id", None),
                content_type="application/pdf")
        return key
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
