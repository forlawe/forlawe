"""Row-Level Security verification against a real PostgreSQL server.

Companion to tests/test_rls.py, for the milestone the consultant flagged:

    "PostgreSQL/RLS paths still need to be exercised against real Postgres
     (not just SQLite) before this is trusted for production traffic."

The unit tests prove the policies inside a test run; this script proves them
the way an operator or attacker would meet them — with raw SQL connections,
no ORM, no app in between. It creates its OWN throwaway database, boots the
app into it exactly like production (alembic chain → ensure_schema → RLS
enable), then attacks:

  A. the connection role is not one that bypasses every policy
     (superuser / BYPASSRLS — the failure mode where RLS reports "active"
     and protects nothing);
  B. every protected table has ENABLE + FORCE ROW LEVEL SECURITY and the
     org_isolation policy in the catalogue;
  C. the policies actually bite:
       1. a query with NO org filter returns only your hospital's rows
       2. an unset tenant sees nothing (fail closed)
       3. the background-job sentinel (-1) sees everything
       4. you cannot INSERT a row into another hospital
       5. you cannot UPDATE your row into another hospital
       6. you cannot DELETE another hospital's row (it is invisible)
       7. the tenant setting is transaction-local: after COMMIT the same
          connection sees nothing (no bleed into the next request)
       8. two connections do not bleed into each other
       9. garbage in the tenant variable fails closed, never open

Usage:
    python tools/verify_postgres_rls.py postgresql://user:pw@127.0.0.1:5432/postgres

The database named in the URL is only used to say "CREATE DATABASE"; nothing
in it is touched. Exits non-zero if any check fails.
"""
from __future__ import annotations

import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)                       # make `app` importable

import psycopg2                                # noqa: E402
import psycopg2.extras                         # noqa: E402


RESULTS: list[tuple[str, str]] = []            # (name, "PASS"/"FAIL …")


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, "PASS" if ok else f"FAIL {detail}".strip()))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


def set_tenant(conn, value: str, local: bool = True) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_org', %s, %s)", (value, local))


def scalar(conn, sql: str, params=()) -> object:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def fresh_conn(url: str):
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].startswith(("postgres://", "postgresql://")):
        print(__doc__)
        return 2
    admin_url = sys.argv[1].replace("postgresql+psycopg2://", "postgresql://", 1)
    dbname = "rls_verify_" + uuid.uuid4().hex[:8]

    print(f"=== creating throwaway database {dbname} ===")
    admin = fresh_conn(admin_url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{dbname}"')
    admin.close()
    db_url = admin_url.rsplit("/", 1)[0] + "/" + dbname

    try:
        # ---- boot the app exactly like production: alembic → schema → RLS --
        # (this also exercises the boot migration path, including the
        #  env.py transaction fix, against real PostgreSQL)
        os.environ["DATABASE_URL"] = db_url
        os.environ.setdefault("SECRET_KEY", "rls-verification-script")
        os.environ["DISABLE_SCHEDULER"] = "1"
        from app import create_app, rls
        app = create_app(scheduler=False)

        with app.app_context():
            from app.models import db
            db.session.remove()
            db.engine.dispose()

            # ---------------- A. the connection role itself -----------------
            print("\n=== A. the connection role ===")
            conn = fresh_conn(db_url)
            with conn.cursor() as cur:
                cur.execute("SELECT rolname, rolsuper, rolbypassrls "
                            "FROM pg_roles WHERE rolname = current_user")
                rolname, rolsuper, rolbypassrls = cur.fetchone()
            print(f"  connected as: {rolname}  superuser={rolsuper}  bypassrls={rolbypassrls}")
            check("connection role is not superuser and holds no BYPASSRLS",
                  not (rolsuper or rolbypassrls),
                  "PostgreSQL exempts this role from EVERY policy — RLS is inert")
            conn.rollback()

            # ---------------- B. the catalogue ------------------------------
            print("\n=== B. catalogue: ENABLE + FORCE + policy per table ===")
            conn = fresh_conn(db_url)
            present, absent = [], []
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'")
                have = {r[0] for r in cur.fetchall()}
                for t in rls.PROTECTED_TABLES:
                    (present if t in have else absent).append(t)
                cur.execute(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                    "COUNT(p.polname) AS policies "
                    "FROM pg_class c "
                    "LEFT JOIN pg_policy p ON p.polrelid = c.oid "
                    "WHERE c.relname = ANY(%s) AND c.relkind = 'r' "
                    "GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity",
                    (present,))
                rows = cur.fetchall()
            ok = True
            for r in rows:
                if not (r["relrowsecurity"] and r["relforcerowsecurity"] and r["policies"] >= 1):
                    ok = False
                    print(f"    !! {r['relname']}: rls={r['relrowsecurity']} "
                          f"force={r['relforcerowsecurity']} policies={r['policies']}")
            check(f"all {len(rows)} protected tables present in the schema have "
                  f"ENABLE + FORCE ROW LEVEL SECURITY and the org_isolation policy",
                  ok and len(rows) == len(present))
            if absent:
                print(f"  note: not in the migration-built schema (created later "
                      f"by the boot fallback, then protected): {absent}")
            conn.rollback()

            # ---------------- C. the attacks --------------------------------
            print("\n=== C. the attacks (raw SQL, no ORM, no app) ===")
            a = fresh_conn(db_url)
            b = fresh_conn(db_url)

            # seed: two hospitals, one patient each, as a cross-org job
            set_tenant(a, "-1", local=False)
            with a.cursor() as cur:
                cur.execute("INSERT INTO organization (code, name) "
                            "VALUES ('RLSV1', 'Verify Hospital A'), "
                            "       ('RLSV2', 'Verify Hospital B') RETURNING id")
                org_a, org_b = cur.fetchone()[0], None
                cur.execute("SELECT id FROM organization WHERE code = 'RLSV2'")
                org_b = cur.fetchone()[0]
                for org, num, sur in ((org_a, "V/1", "VERIFYA"), (org_b, "V/2", "VERIFYB")):
                    cur.execute(
                        "INSERT INTO patient (org_id, hospital_number, surname, "
                        "first_name, sex, payer_type, category, active) "
                        "VALUES (%s, %s, %s, 'Test', 'F', 'SELF', 'GENERAL', TRUE)",
                        (org, num, sur))
            a.commit()
            # the sentinel above was set SESSION-level; clear it so every
            # check below starts from "no tenant", like a pooled connection
            set_tenant(a, "", local=False)
            a.commit()

            # C1 — THE seatbelt: a query with NO org filter
            set_tenant(a, str(org_a))
            with a.cursor() as cur:
                cur.execute("SELECT surname FROM patient")
                names = [r[0] for r in cur.fetchall()]
            check("a query with NO org filter returns only this hospital's patients",
                  names == ["VERIFYA"], f"got {names}")

            # C2 — unset tenant sees nothing
            set_tenant(a, "")
            n = scalar(a, "SELECT count(*) FROM patient")
            check("an unset tenant sees NOTHING (fail closed)", n == 0, f"count={n}")

            # C3 — the background-job sentinel
            set_tenant(a, "-1")
            n = scalar(a, "SELECT count(*) FROM patient")
            check("the background-job sentinel (-1) sees all hospitals", n == 2, f"count={n}")
            a.rollback()

            # C4 — cannot INSERT into another hospital
            set_tenant(a, str(org_a))
            try:
                with a.cursor() as cur:
                    cur.execute(
                        "INSERT INTO patient (org_id, hospital_number, surname, "
                        "first_name, sex, payer_type, category, active) "
                        "VALUES (%s, 'X/1', 'PLANTED', 'Bad', 'M', 'SELF', 'GENERAL', TRUE)",
                        (org_b,))
                a.commit()
                check("INSERT into another hospital is refused", False, "it was accepted!")
            except psycopg2.Error:
                a.rollback()
                check("INSERT into another hospital is refused", True)

            # C5 — cannot UPDATE your row into another hospital
            set_tenant(a, str(org_a))            # (re-set: C4's rollback cleared it)
            try:
                with a.cursor() as cur:
                    cur.execute("UPDATE patient SET org_id = %s", (org_b,))
                    rowcount = cur.rowcount
                a.commit()
                check("UPDATE re-homing a row into another hospital is refused",
                      False, f"it was accepted (rowcount={rowcount})!")
            except psycopg2.Error:
                a.rollback()
                check("UPDATE re-homing a row into another hospital is refused", True)

            # C6 — DELETE against another hospital's rows
            with a.cursor() as cur:
                cur.execute("DELETE FROM patient WHERE surname = 'VERIFYB'")
                deleted = cur.rowcount
            a.commit()
            check("DELETE aimed at another hospital's rows deletes nothing",
                  deleted == 0, f"rowcount={deleted}")

            # C7 — tenant setting is transaction-local
            set_tenant(a, str(org_a))            # inside this transaction…
            n_in = scalar(a, "SELECT count(*) FROM patient")
            a.commit()                           # …gone after COMMIT
            n_out = scalar(a, "SELECT count(*) FROM patient")
            check("the tenant setting dies with its transaction (pooled-connection safety)",
                  n_in == 1 and n_out == 0, f"during={n_in} after commit={n_out}")

            # C8 — two connections do not bleed
            set_tenant(a, str(org_a))            # a is now scoped, transaction open
            n_b = scalar(b, "SELECT count(*) FROM patient")
            check("a scoped connection does not leak its tenant onto other connections",
                  n_b == 0, f"other connection saw {n_b} rows")
            a.rollback(); b.rollback()

            # C9 — garbage fails closed
            set_tenant(a, "garbage")
            try:
                n = scalar(a, "SELECT count(*) FROM patient")
                ok9 = (n == 0)
                detail9 = f"returned {n} rows"
            except psycopg2.Error:
                a.rollback()
                ok9, detail9 = True, "raised (also fail-closed)"
            check("a garbage tenant value never opens the door", ok9, detail9)

            set_tenant(a, "")                    # leave it clean
            a.commit()
            for c in (a, b):
                c.close()

        # ---- verdict --------------------------------------------------------
        failed = [r for r in RESULTS if not r[1].startswith("PASS")]
        print("\n================ VERDICT ================")
        for name, verdict in RESULTS:
            print(f"  {verdict:9s} {name}")
        if failed:
            print(f"\n{len(failed)} check(s) FAILED")
            return 1
        print(f"\nALL {len(RESULTS)} CHECKS PASSED — row-level security is real "
              f"on this server, for this role")
        return 0
    finally:
        try:
            cleanup = fresh_conn(admin_url)
            cleanup.autocommit = True
            with cleanup.cursor() as cur:
                # WITH (FORCE): the app's pooled engine may still hold a
                # connection; PG13+ can drop around it.
                cur.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
            cleanup.close()
            print(f"(throwaway database {dbname} dropped)")
        except Exception as exc:                 # noqa: BLE001
            print(f"note: could not drop {dbname}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
