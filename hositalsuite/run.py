#!/usr/bin/env python3
"""Hospital Admin Manager Suite — entry point & CLI.

Usage:
  python run.py                  # start the web server (with scheduler)
  python run.py seed             # first-time setup: hospital, users, structure, roster
  python run.py demo             # seed + sample inspection/complaint history for evaluation
  python run.py tick             # run one scheduler pass (reminders, SLA, WhatsApp queue)
  python run.py backup           # create a database backup now
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

os.environ.setdefault("DISABLE_SCHEDULER", "0")


def seed(demo: bool = False):
    os.environ.setdefault("DISABLE_SCHEDULER", "1")
    from app import create_app
    from app.seeddata import seed_data
    app = create_app(scheduler=False)
    org = seed_data(app, demo=demo)
    if org is None:
        print("Already seeded. Use the running application to manage configuration.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        seed(demo=False)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        seed(demo=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "tick":
        os.environ["DISABLE_SCHEDULER"] = "1"
        from app import create_app
        from app.scheduler import tick
        app = create_app(scheduler=False)
        tick(app)
        print("Scheduler pass complete.")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "dbcheck":
        # First command to run on any new host: verifies DATABASE_URL and creates tables.
        os.environ["DISABLE_SCHEDULER"] = "1"
        from app import create_app
        from app.models import db
        app = create_app(scheduler=False)
        with app.app_context():
            uri = str(db.engine.url)
            print("Connecting to:", uri.split("@")[-1] if "@" in uri else uri)
            db.session.execute(db.text("SELECT 1"))
            db.create_all()
            print("✅ Database reachable and schema ready.")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "backup":
        from app import create_app
        from app.scheduler import job_nightly_backup
        app = create_app(scheduler=False)
        with app.app_context():
            job_nightly_backup(app)
        print("Backup complete.")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "tick-loop":
        # For Render Background Worker: run scheduler loop forever, no web server
        # Use with DISABLE_SCHEDULER=0 (default) on this worker, and DISABLE_SCHEDULER=1 on web workers
        import time
        from app import create_app
        from app.scheduler import _loop
        os.environ["DISABLE_SCHEDULER"] = "0"
        app = create_app(scheduler=False)
        print("Starting scheduler loop (background worker)...")
        _loop(app, interval=30)
        return

    from app import create_app
    app = create_app()
    port = int(os.environ.get("PORT", "8077"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
