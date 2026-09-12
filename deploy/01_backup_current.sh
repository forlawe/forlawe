#!/usr/bin/env bash
# ============================================================================
# 01 — BACK UP WHAT IS RUNNING NOW  (run this FIRST, every time)
#
# Two things get backed up:
#   1. the code folder  (so you can put the old files straight back)
#   2. the database     (so a failed deploy can never cost you patient data)
#
# Usage:
#   bash deploy/01_backup_current.sh /path/to/your/hositalsuite
#
# If you deploy on Render (no shell), you do not run this — Render keeps the
# previous deploy for one-click rollback, and the database lives on Supabase.
# For that path use: Supabase dashboard -> Database -> Backups -> download.
# ============================================================================
set -euo pipefail

APP_DIR="${1:-}"
if [ -z "$APP_DIR" ] || [ ! -d "$APP_DIR" ]; then
  echo "Usage: bash deploy/01_backup_current.sh /path/to/your/hositalsuite"
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/hospital-suite-backups}"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"

echo "==> Backing up code from $APP_DIR"
# -a keeps permissions/timestamps. Runtime data is EXCLUDED on purpose: it is
# backed up separately below, and data/app.db is often open by the server.
tar --exclude='./data' --exclude='./.venv' --exclude='./venv' \
    --exclude='__pycache__' --exclude='./.git' \
    -czf "$DEST/code.tar.gz" -C "$APP_DIR" .
echo "    code   -> $DEST/code.tar.gz ($(du -h "$DEST/code.tar.gz" | cut -f1))"

# Secrets are tiny and irreplaceable — keep a copy, but never in the repo.
for f in .env .secret_key vapid_keys.json; do
  [ -f "$APP_DIR/$f" ] && cp "$APP_DIR/$f" "$DEST/$f" && echo "    secret -> $DEST/$f"
done

echo "==> Backing up the database"
DB_URL="$(grep -E '^DATABASE_URL=' "$APP_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [ -n "${DB_URL:-}" ] && [ -f "$APP_DIR/${DB_URL#sqlite:///}" ]; then
  SQLITE_FILE="$APP_DIR/${DB_URL#sqlite:///}"
  # `.backup` (not cp) is safe on a live database — it takes a consistent copy.
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$SQLITE_FILE" ".backup '$DEST/app.db'"
  else
    cp "$SQLITE_FILE" "$DEST/app.db"
    echo "    (sqlite3 CLI not found — used a plain copy; stop the app first next time)"
  fi
  echo "    sqlite -> $DEST/app.db"
elif command -v pg_dump >/dev/null 2>&1 && [ -n "${DB_URL:-}" ]; then
  pg_dump "$DB_URL" -Fc -f "$DEST/app.dump"
  echo "    postgres -> $DEST/app.dump"
else
  echo "    !! Could not find a local SQLite file and pg_dump is not installed."
  echo "    !! Take the backup by hand BEFORE you continue (Supabase -> Backups)."
fi

echo
echo "✅ Backup finished: $DEST"
ls -lh "$DEST"
echo
echo "Rollback of the code, if you ever need it:"
echo "  tar -xzf $DEST/code.tar.gz -C $APP_DIR"
