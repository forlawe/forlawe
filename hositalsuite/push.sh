#!/usr/bin/env bash
# One-command push for the founder.
#
#   bash push.sh <YOUR_NEW_TOKEN>
#
# Get a token at https://github.com/settings/tokens
#   -> "Generate new token (classic)" -> tick BOTH  repo  and  workflow
#
# The token is used once and never written to a file, so it cannot leak from
# the repo. It WILL appear in your shell history — clear it afterwards with:
#   history -c
set -euo pipefail

TOKEN="${1:-}"
if [ -z "$TOKEN" ]; then
  echo "Usage: bash push.sh <YOUR_NEW_TOKEN>"
  echo
  echo "You have these commits waiting to go live:"
  git --no-pager log --oneline origin/main..HEAD 2>/dev/null \
    || git --no-pager log --oneline -8
  exit 1
fi

echo "Pushing to github.com/Hcarepro2026/hositalsuite (branch main)…"
git push "https://Hcarepro2026:${TOKEN}@github.com/Hcarepro2026/hositalsuite.git" main

echo
echo "✅ Pushed. Render auto-deploys in about 2–3 minutes."
echo
echo "Then check, in this order:"
echo "  1. https://hospital-suite.onrender.com/api/v1/ready   -> should say ready:true"
echo "  2. Sign in, open Reception, take in a test patient"
echo "  3. Walk them: Billing -> Paying Point -> HIMS folder -> Triage"
echo "  4. Tap the screen ONCE so the phone is allowed to speak, then listen"
echo
echo "⚠  Now revoke this token if it was temporary, and run:  history -c"
