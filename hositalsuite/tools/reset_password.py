#!/usr/bin/env python
"""Reset a staff password from the service shell — the founder's way back in.

When the first-boot random password is lost (Render logs scroll away on the
free tier), run this from the service's shell (Render dashboard → your
service → "Shell"):

    python tools/reset_password.py admin
    python tools/reset_password.py admin 'MyNewPassw0rd!'

With no password argument a strong random one is generated and printed.
The app's own strength rules are enforced, and on PostgreSQL the lookup
runs under the cross-hospital RLS scope (rls.background_all_orgs) — the
same declaration the scheduler uses — because this CLI runs outside any
request.
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    username = sys.argv[1].strip()
    new_pw = sys.argv[2] if len(sys.argv) > 2 else secrets.token_urlsafe(10) + "A1!"

    from app import create_app
    from app.accounts import password_strength_errors
    from app.models import User, db

    errors = password_strength_errors(new_pw, username=username)
    if errors:
        print("That password is not strong enough:")
        for e in errors:
            print(f"  - {e}")
        return 2

    app = create_app(scheduler=False)
    with app.app_context():
        from app.rls import background_all_orgs
        with background_all_orgs():
            users = db.session.query(User).filter_by(username=username).all()
            if not users:
                print(f"No user named {username!r} exists.")
                return 1
            for u in users:
                u.set_password(new_pw)
            # clear the brute-force lockout row(s) for this username, if any
            from app.models import LoginAttempt
            db.session.query(LoginAttempt).filter(
                LoginAttempt.username == username).delete()
            db.session.commit()
            names = ", ".join(f"{u.username}@org{u.org_id}" for u in users)
            print(f"Password reset for: {names}")
            print(f"New password: {new_pw}")
            if len(users) == 1 and users[0].must_change_password:
                print("(You will be asked to set your own password at first login.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
