# forlawe / forlawe — workspace branch `arena/01a097c6-forlawe`

> The verified deliverable is merged to `main` via pull request from the
> session branch. The branch name above is where the work happened, not the
> source of truth — `main` is.

**The deployable application is in [`hositalsuite/`](hositalsuite/). That folder is
the deploy root.** Its contents map 1:1 onto the root of the production repo
`Hcarepro2026/hositalsuite`.

Everything a build needs sits together inside `hositalsuite/`:

| file | present |
| --- | --- |
| `requirements.txt` | yes |
| `run.py` | yes |
| `runtime.txt` | yes (`python-3.12.7`) |
| `render.yaml` | yes |
| `Dockerfile` | yes |
| `start.sh` | yes |
| `alembic.ini` + `migrations/` | yes |
| `app/` | yes |
| `tests/` | yes (1060 passed, 8 skipped) |

So point Render at `hositalsuite/` as the root directory. `render.yaml`'s
`buildCommand: pip install --upgrade pip && pip install -r requirements.txt`
then resolves to `hositalsuite/requirements.txt`, and its `startCommand`
(`gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
"app:create_app()"`) resolves to `hositalsuite/app/`.

The `requirements.txt` and `runtime.txt` at **this** level are shims only, so
that `pip install -r requirements.txt` typed from the repo root also works.
They are not a second copy of the app.

## Where the detail is

* [`DEPLOY_READY.md`](DEPLOY_READY.md) — Render + Supabase runbook, the
  end-to-end booking-door test results, the `alembic` CLI blocker that was
  found and fixed, and an explicit "not verified here" section.
* [`POSTGRES_VERIFICATION.md`](POSTGRES_VERIFICATION.md) — the consultant's
  "next milestone", done: everything exercised against a real PostgreSQL 16
  server. Eight bugs found and fixed (migrations that never committed,
  patient doors that 500ed, a scheduler that never ticked, an unprotected
  WhatsApp table…), RLS proven with raw-SQL attacks, and the re-run recipes.
* [`CONSULTANT_REPORT_RESPONSE.md`](CONSULTANT_REPORT_RESPONSE.md) — line-by-line
  adjudication of the Patient Journey Recommendation Report.
* [`ISSUE_1_REPLY.md`](ISSUE_1_REPLY.md) — the reply to issue #1.
