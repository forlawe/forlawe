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
# Both patches, in order. Each is independent; both are verified to apply to a
# fresh clone of Hcarepro2026/hositalsuite@main.
PATCHES=("landing_auth_mobile.patch" "fasttrack_two_doors.patch")

if [ -z "$APP_DIR" ] || [ ! -d "$APP_DIR" ]; then
  echo "Usage: bash deploy/02_apply_patch.sh /path/to/your/hositalsuite"
  exit 1
fi
for f in "${PATCHES[@]}"; do
  [ -f "$HERE/$f" ] || { echo "Patch not found: $HERE/$f"; exit 1; }
done

cd "$APP_DIR"

echo "==> 1/3 Dry run (nothing written yet)"
for f in "${PATCHES[@]}"; do
  echo "    checking $f"
  git apply --check "$HERE/$f" || {
    echo
    echo "❌ $f does not fit your files. Your copy has drifted from the version"
    echo "   the patch was cut against. Stop here and tell me — I will re-cut it."
    exit 1
  }
done
PATCH="$HERE/${PATCHES[0]}"
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
for f in "${PATCHES[@]}"; do
  echo "    $f"
  git apply --stat "$HERE/$f"
  git apply "$HERE/$f"
done

echo "==> 3/3 Confirming the files now match this workspace"
FAIL=0
for f in app/static/css/app.css app/templates/_auth_footer.html \
         app/templates/landing_sales.html app/templates/login.html \
         app/templates/request_access.html app/templates/signup_pick.html \
         app/templates/forgot_password.html app/templates/reset_password.html \
         app/views/bookings.py app/views/queue.py \
         app/templates/booking_portal.html app/templates/queue_join.html \
         app/templates/patient_hub.html tests/test_fasttrack_doors.py \
         tests/test_f039_consent_partial.py; do
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
