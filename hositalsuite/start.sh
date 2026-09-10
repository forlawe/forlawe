#!/bin/bash
# Workspace launcher — uses local SQLite because this sandbox cannot open direct
# TCP connections to Supabase (web-only egress). Production deployments use .env
# (DATABASE_URL → Supabase) unchanged.
cd "$(dirname "$0")"
export SECRET_KEY="$(cat .secret_key 2>/dev/null || echo workspace-dev-key)"
export PORT=8077
export DATABASE_URL="sqlite:///data/app.db"
exec python -u run.py
