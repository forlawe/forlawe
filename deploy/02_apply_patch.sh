#!/usr/bin/env bash
# ============================================================================
# 02 — PUT THE NEW CODE IN PLACE
#
# Replaces the 8 changed files in your hospital suite with the ones built in
# this workspace. It refuses to touch anything else, and it checks the patch
# BEFORE writing a single byte.
#
# Usage:
#   bash deploy/02_apply_patch.sh /path/to/your/hositalsuite
#
# The 8 files it touches (nothing else):
#   app/static/css/app.css
#   app/templates/_auth_footer.html      (new)
#   app/templates/landing_sales.html
#   app/templates/login.html
#   app/templates/request_access.html
#   app/templates/signup_pick.html
#   app/templates/forgot_password.html
#   app/templates/reset_password.html
#
# No Python changed => no migration, no restart of the database, no .env edit.
# ============================================================================
set -euo pipefail

APP_DIR="${1:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PATCH="$HERE/landing_auth_mobile.patch"

if [ -z "$APP_DIR" ] || [ ! -d "$APP_DIR" ]; then
  echo "Usage: bash deploy/02_apply_patch.sh /path/to/your/hositalsuite"
  exit 1
fi
[ -f "$PATCH" ] || { echo "Patch not found: $PATCH"; exit 1; }

cd "$APP_DIR"

echo "==> 1/3 Dry run (nothing written yet)"
if ! git apply --check --verbose "$PATCH"; then
  echo
  echo "❌ The patch does not fit your files. That means your copy has already"
  echo "   drifted from the version this patch was cut against. Stop here and"
  echo "   tell me — I will re-cut the patch against your current files."
  echo
  echo "   To see the difference yourself:"
  echo "     diff -u app/templates/landing_sales.html <this workspace>/hositalsuite/app/templates/landing_sales.html"
  exit 1
fi
echo "    dry run OK — the patch fits"

echo "==> 2/3 Applying"
git apply --stat "$PATCH"
git apply "$PATCH"

echo "==> 3/3 Confirming the files now match this workspace"
FAIL=0
for f in app/static/css/app.css app/templates/_auth_footer.html \
         app/templates/landing_sales.html app/templates/login.html \
         app/templates/request_access.html app/templates/signup_pick.html \
         app/templates/forgot_password.html app/templates/reset_password.html; do
  if diff -q "$APP_DIR/$f" "$HERE/../hositalsuite/$f" >/dev/null 2>&1; then
    echo "    ok   $f"
  else
    echo "    DIFF $f"
    FAIL=1
  fi
done

if [ "$FAIL" -eq 1 ]; then
  echo
  echo "⚠️  At least one file does not match. Compare them before you restart."
  exit 1
fi

echo
echo "✅ Code replaced. Next: bash deploy/03_verify.sh <base-url>"
echo "   (on a VPS, restart the service first:  sudo systemctl restart hospital-suite"
echo "    or  gunicorn/graceful reload — templates are read per request, so a"
echo "    restart is only strictly needed for app.css cache-busting)"
