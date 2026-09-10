import os
os.environ.setdefault("DATABASE_URL", "sqlite:///tv_demo.db")
os.environ.setdefault("SECRET_KEY", "demo-secret")
os.environ["DISABLE_SCHEDULER"] = "1"

from app import create_app
from app.models import Organization, User, Department, db
from app.tv import ensure_default_screens
from app.servicepoints import ensure_defaults

app = create_app(scheduler=False)

with app.app_context():
    db.create_all()
    # Seed org if none
    org = db.session.query(Organization).first()
    if not org:
        org = Organization(code="IJD", name="Ijede General Hospital", slug="ijede")
        db.session.add(org)
        db.session.flush()
        print(f"Created org {org.id}")

        # Admin user
        admin = User(org_id=org.id, username="admin", name="Super Admin", role="SUPER_ADMIN", phone="08012345678")
        admin.set_password("Admin123!")
        admin.approved = True
        admin.must_change_password = False
        db.session.add(admin)

        # Dept
        dept = Department(org_id=org.id, name="Dental", active=True)
        db.session.add(dept)
        db.session.commit()
        print("Seeded admin / admin / Admin123!")

    ensure_defaults(org.id)
    ensure_default_screens(org.id)
    db.session.commit()
    print("TV screens + clinics seeded")

if __name__ == "__main__":
    # Allow preview host
    app.run(host="0.0.0.0", port=5000, debug=False)
