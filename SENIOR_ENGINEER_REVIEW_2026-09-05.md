# Senior Engineering Review — 2026-09-05

Scope: release-readiness of PR #5 (`arena/01a06e4b-hositalsuite` → `main`),
which consolidates all outstanding work from the pre-review branch
`arena/01a06682-hositalsuite` (former PR #4) onto the rewritten `main`.

Author: supervising engineer (automated review).
Status: **GO — safe to merge**, with owner-only follow-ups listed at the end.

---

## 1. What happened (the chain this review closes)

1. A VAPID **private key** was committed in prose (`HOSPITAL_ASSISTANT_WORLD_CLASS_REPORT.md`).
2. A remediation commit (`a292a17`, "redact: remove leaked key fragment
   completely") became the *only* commit on a rewritten `main` (squashed root).
3. The outstanding work sat on `arena/01a06682-hositalsuite` (PR #4) whose
   history predates the rewrite — so GitHub marked it **CONFLICTING**, and its
   tree still contained the burned key hardcoded in
   `tests/test_secrets_hygiene.py` (split across two string literals so its own
   scanner did not flag its source).
4. This review rebuilt the work as a clean branch on `main` (PR #5), scrubbed
   the secret, and then **caught and fixed three silent regressions** the
   rebuild would otherwise have shipped (section 2).

## 2. Regressions caught before merge (the important part)

PR #5 was first assembled from the pre-review tree, which would have reverted
fixes already on `main`. The following were detected and re-applied:

| # | Area | Regression that was about to ship | Fix applied |
|---|------|-----------------------------------|-------------|
| 1 | `migrations/versions/{i23,k25,k26}` | Reverted to bare `except: pass`; the inspector-based idempotency guard (the Supabase `InFailedSqlTransaction` / 424 GB egress root cause) was lost | Restored `main`'s reviewed versions (`76f6b66`) |
| 2 | `app/queue_estimator.py` | `get_live_counts` cache dropped from 60s back to 30s (egress guard) | Re-applied 60s on top of the newer F-012/F-013/F-014 estimation logic (`5a824b1`) |
| 3 | `app/hims.py` | Fuzzy surname search fallback was org-wide, not branch-scoped (could surface another branch's patient) | Re-applied `apply_branch_filter` while keeping newer `other_names` scoring (`3d1dbd7`) |

Verified **not** regressed (the pre-review tree already carried these, often
more completely): chatbot leet/compact/proximity hardening, `migrate.py`
inspector + loud logging, scheduler advisory-lock leader election,
migration-safety DFS, columns-only fuzzy candidate fetch, VAPID auto-generate
fallback, `serve.py` privacy refusal before teaching.

## 3. Verification performed on the final head

- **Secret scan**: `git grep` for the burned key pair and PEM private-key
  blocks across the full tree — **clean**.
  `tests/test_secrets_hygiene.py` rewritten to detect the burned keys by
  SHA-256 fingerprint only (no raw key material committed anywhere).
- **Tests (SQLite)**: full suite **1044 passed / 8 skipped** at the first
  assembly; targeted re-runs after the three fixes (secrets hygiene, migration
  safety, secret-key enforcement, HIMS, queue estimator, fast-track guard)
  all green. A full-suite re-run on the final head is logged with this review.
- **Boot smoke test**: `run.py` boots with alembic stamp + KB sync; `/` → 302
  `/start` (200), `/login` 200, `/chat` 200, `/privacy` 200; `run.py dbcheck`
  reports "Database reachable and schema ready"; **no 500s**.
- **PR state**: `MERGEABLE` / `CLEAN`, 122 files (+6,444 / −1,172).

## 4. Findings that need the owner (the automation cannot do these)

1. **CI is not actually running.** The workflow file lives at
   `ci/github-actions-tests.yml`, but GitHub only executes workflows from
   `.github/workflows/`. A push attempt from this environment is rejected:
   *"refusing to allow a GitHub App to create or update workflow
   `.github/workflows/tests.yml` without `workflows` permission."*
   → Owner: follow `ci/README.md` Option A (paste into
   `.github/workflows/tests.yml` via the web UI), or re-grant the
   `workflows` scope. Until then, PRs show **no checks** — including PR #5.
2. **Branch protection** on `main` is not enabled (requires repo admin; the
   API returns 403 for integration tokens). Recommended rule: require PR,
   require status checks `tests (SQLite)`, `tests (PostgreSQL)`,
   `dependency audit`. Only enable the required-checks half *after* CI is
   actually running, or all merges block.
3. **Rotate VAPID keys in Render** (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
   `VAPID_SUBJECT`). This is the definitive remediation: the old key is
   burned and still exists in git history reachable via merged PRs. Rotation
   makes it worthless; no history purge can un-leak a live key. Old push
   subscriptions must re-enable.
4. **`docs/DO_THIS_NOW.md`** exposes the real Supabase project reference
   (`zhhdhfllypkzvmukilwt`) in a connection-string example. The password is a
   placeholder, but verify the real database password is not the literal
   `OLDPASSWORD` shown, and consider masking the project ref.
5. **(Optional) Full history purge** — force-push scrubbed history and delete
   the merged PR refs that still reach the leaked key. Riskier than rotation
   and unnecessary once keys are rotated; only with explicit owner sign-off.

## 5. Recommendation

**GO — merge PR #5.** The tree is clean of secrets, regressions are fixed,
the suite is green, and the app boots. Merge deploys to production (Render
tracks `main`), so complete the Render-side VAPID rotation (item 4.3) at the
same time. CI activation (4.1) and branch protection (4.2) are follow-ups,
not blockers.
