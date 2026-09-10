"""Regression tests for bugs found by load testing (4,000/min campaign)."""
from app import services
from app.models import Complaint, db

from conftest import csrf


def test_reference_collision_retries_to_unique(client, seeded):
    """Two submissions computing the SAME reference must not 500 —
    the second must retry and receive a unique reference."""
    real = services.next_complaint_ref
    calls = {"n": 0}

    def rigged(org, when):
        calls["n"] += 1
        if calls["n"] == 2:
            first = db.session.query(Complaint).first()
            return first.ref          # force a collision with complaint #1
        return real(org, when)

    services.next_complaint_ref = rigged
    try:
        for i in (1, 2):
            tok = csrf(client, "/complaint")
            r = client.post("/complaint/submit", data={"consent": "1", 
                "_csrf": tok, "department_id": seeded["dept"],
                "category": "Long waiting time",
                "description": f"Collision regression complaint number {i}.",
                "phone": "08012345678", "idem": f"coll-{i}"}, follow_redirects=True)
            assert b"has been received" in r.data, f"submission {i} failed"
        refs = [c.ref for c in db.session.query(Complaint).all()]
        assert len(refs) == 2 and len(set(refs)) == 2, refs
    finally:
        services.next_complaint_ref = real


def test_concurrent_submissions_never_duplicate_refs(app, seeded):
    """Hammer the ref allocator from threads; every persisted ref stays unique."""
    import threading
    with app.app_context():
        from app.models import Organization
        org = db.session.get(Organization, seeded["org"])
        from datetime import datetime
        errors = []

        def worker(i):
            try:
                with app.app_context():
                    from app.models import Complaint as C
                    c, _ = services.insert_with_unique_ref(lambda: C(
                        org_id=org.id, ref=services.next_complaint_ref(org, datetime.now()),
                        department_id=seeded["dept"], category="Other",
                        description=f"thread {i}", phone="08011112222", status="NEW",
                        sla_hours=24, sla_deadline_at=datetime.now()))
                    db.session.commit()
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        refs = [r for (r,) in db.session.query(Complaint.ref).all()]
        assert len(refs) == len(set(refs)) == 12, refs
