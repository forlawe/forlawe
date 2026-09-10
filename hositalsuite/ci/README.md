# Continuous Integration — one activation step remains (owner-only)

**Status 2026-09-04:** The workflow is written, YAML-validated, and kept in
this folder (`ci/github-actions-tests.yml`) because BOTH the Arena app token
and Personal Access Tokens without the `workflow` scope are refused when
pushing files under `.github/workflows/`. GitHub only ever RUNS workflows
from `.github/workflows/`, so one human step activates it:

## Activate (pick either, ~2 minutes)

**Option A — GitHub website (no tools needed)**
1. Open the repo → **Add file → Create new file**
2. Filename: `.github/workflows/tests.yml`
3. Paste the entire contents of `ci/github-actions-tests.yml`
4. Commit (to `main`, or to a branch and PR it)

**Option B — from any clone with a token that has the `workflow` scope**
```bash
mkdir -p .github/workflows && cp ci/github-actions-tests.yml .github/workflows/tests.yml
git add .github/workflows/tests.yml && git commit -m "Activate CI (F-001)" && git push
```

> Alternative: in Arena, reconnect GitHub with the `workflow` scope and ask
> the agent to push it — the file is ready and validated.

## What runs once activated

| Job | What it proves |
|---|---|
| `tests (SQLite)` | Full suite on the developer-laptop engine |
| `tests (PostgreSQL)` | Full suite on the production engine + `alembic upgrade head` applies cleanly to an EMPTY database |
| `dependency audit` | `pip-audit` reports known CVEs in pinned dependencies (advisory — informs, never blocks a hotfix) |

Triggers: every push to `main`, every pull request, and manual runs
(Actions tab → tests → Run workflow).

Green tick = every test passed and migrations apply; safe to deploy.
Red X = do NOT deploy until fixed.

## Branch protection (the other half of F-001)

Settings → Branches → Add rule for `main`:
- **Require a pull request before merging**
- **Require status checks**: `tests (SQLite)`, `tests (PostgreSQL)`, `dependency audit`
- **Require branches to be up to date before merging**

Enabling these needs repo **admin** — the automated attempt returned 403
(integration tokens cannot change repo settings), so it is a 2-minute job in
the GitHub web UI by the repo owner. Until CI is actually running (step
above), do NOT turn on the required-status-checks half — a required check
that never reports blocks all merges.
