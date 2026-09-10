#!/usr/bin/env bash
# ============================================================================
# 03 — PROVE IT WORKED  (safe to run on production: every request is a GET)
#
# Usage:
#   bash deploy/03_verify.sh                          # local  (http://127.0.0.1:8077)
#   bash deploy/03_verify.sh https://hospital-suite.onrender.com
#
# Exit code 0 = every check passed. Anything else = read the FAIL lines.
# ============================================================================
set -uo pipefail

BASE="${1:-http://127.0.0.1:8077}"
BASE="${BASE%/}"
PASS=0; FAIL=0

# check <label> <url> <substring that must appear>
check() {
  local label="$1" url="$2" want="${3:-}"
  local body code
  body="$(curl -sS -m 25 -w $'\n%{http_code}' "$BASE$url" 2>/dev/null)" || {
    echo "  FAIL  $label  (could not reach $BASE$url)"; FAIL=$((FAIL+1)); return; }
  code="${body##*$'\n'}"; body="${body%$'\n'*}"
  if [ "$code" != "200" ]; then
    echo "  FAIL  $label  (HTTP $code on $url)"; FAIL=$((FAIL+1)); return
  fi
  if [ -n "$want" ] && ! grep -qF -- "$want" <<<"$body"; then
    echo "  FAIL  $label  (page loads but '$want' is missing — old file still served)"; FAIL=$((FAIL+1)); return
  fi
  echo "  ok    $label  (HTTP $code)"; PASS=$((PASS+1))
}

echo "Verifying $BASE"
echo
echo "-- app is alive --"
check "health endpoint"        /api/v1/health
check "ready endpoint"         /api/v1/ready
check "patient hub"            /welcome

echo
echo "-- landing page is wired to the auth pages --"
check "landing loads"          /sales        'class="nav"'
check "landing -> staff login" /sales        'href="/login"'
check "landing -> staff signup" /sales       'href="/signup"'
check "landing -> set up"      /sales        'href="/start"'

echo
echo "-- landing page is built for phones --"
check "hamburger button"       /sales        'class="nav-toggle"'
check "mobile drawer"          /sales        'id="nav-drawer"'
check "aria-expanded (a11y)"   /sales        'aria-expanded'
check "safe-area padding"      /sales        'env(safe-area-inset-top'

echo
echo "-- auth pages link back to the landing page --"
check "login page"             /login        'class="auth-footer"'
check "login -> /sales"        /login        'href="/sales"'
check "signup page"            /signup       'class="auth-footer"'
check "forgot password"        /forgot-password 'class="auth-footer"'

echo
echo "-- the new CSS is actually being served --"
CSS_BODY="$(curl -sS -m 25 "$BASE/static/css/app.css" 2>/dev/null)"
if grep -qF '.auth-footer' <<<"$CSS_BODY"; then
  echo "  ok    app.css contains .auth-footer"; PASS=$((PASS+1))
else
  echo "  FAIL  app.css has no .auth-footer (browser/CDN cache or old file)"; FAIL=$((FAIL+1))
fi
if grep -qF 'flex-direction:column' <<<"$CSS_BODY"; then
  echo "  ok    app.css stacks the auth card + footer"; PASS=$((PASS+1))
else
  echo "  FAIL  app.css is missing the auth column rule"; FAIL=$((FAIL+1))
fi

echo
echo "=================================================="
echo "  passed: $PASS    failed: $FAIL"
echo "=================================================="
if [ "$FAIL" -ne 0 ]; then
  echo
  echo "If a page still shows the OLD markup, it is almost always a cached file:"
  echo "  1. hard-refresh on your phone (or open a private window)"
  echo "  2. confirm the file on the server really changed:"
  echo "       grep -c nav-toggle app/templates/landing_sales.html   # should be > 0"
  echo "  3. restart the app service, then run this script again"
  exit 1
fi
echo "✅ All checks green. Open $BASE/sales on your PHONE and tap ☰ Menu."
