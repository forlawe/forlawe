"""Load/capacity test for Hospital Admin Manager Suite (locust).

Traffic mix mirrors a real hospital surge: most load hits the patient-facing
public endpoints (QR scans), a small share is staff dashboard traffic, and a
slice exercises the WRITE path (complaint/feedback submissions).

Run (example, 4,000 requests/min ≈ 67 rps):
  RATE_LIMIT_SCALE=100000 locust -f loadtest/locustfile.py --headless \
      --host http://127.0.0.1:8090 -u 67 -r 20 -t 120s \
      --csv loadtest/results/run1

RATE_LIMIT_SCALE must match the SERVER's setting (relaxed only for capacity
measurement; production runs with the real limits).
"""
import re
import uuid

from locust import HttpUser, constant_pacing, task

CSRF_RE = re.compile(r'name="_csrf" value="([^"]+)"')
DEPT_RE = re.compile(r'<option value="(\d+)"')


def csrf_of(html: str) -> str:
    m = CSRF_RE.search(html)
    return m.group(1) if m else ""


class PatientUser(HttpUser):
    """Anonymous patient/visitor arriving via QR code or link."""
    weight = 8
    wait_time = constant_pacing(1.0)   # 1 request/sec/user → rps == user count

    @task(10)
    def complaint_portal(self):
        self.client.get("/complaint", name="/complaint (portal)")

    @task(7)
    def booking_portal(self):
        self.client.get("/book", name="/book (portal)")

    @task(2)
    def referral_book_entry(self):
        self.client.get("/book?r=LOADTEST", name="/book?r= (referral entry)")

    @task(6)
    def feedback_portal(self):
        self.client.get("/feedback", name="/feedback (portal)")

    @task(5)
    def queue_join(self):
        self.client.get("/queue/join", name="/queue/join")

    @task(4)
    def queue_screen(self):
        self.client.get("/queue/screen", name="/queue/screen (display)")

    @task(3)
    def health(self):
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(3)
    def submit_complaint(self):
        """WRITE path: full realistic submission (CSRF + idempotency key)."""
        r = self.client.get("/complaint", name="/complaint (pre-submit)")
        token = csrf_of(r.text)
        m = DEPT_RE.search(r.text)
        dept = m.group(1) if m else "1"
        self.client.post("/complaint/submit", data={
            "_csrf": token, "department_id": dept,
            "category": "Long waiting time",
            "description": "Load test submission — measuring write capacity.",
            "phone": "08012345678", "idem": f"load-{uuid.uuid4().hex}",
        }, name="POST /complaint/submit (write)")

    @task(2)
    def submit_feedback(self):
        r = self.client.get("/feedback", name="/feedback (pre-submit)")
        token = csrf_of(r.text)
        self.client.post("/feedback/submit", data={
            "_csrf": token, "rating": "4",
            "comment": "Load test feedback.",
        }, name="POST /feedback/submit (write)")


class StaffUser(HttpUser):
    """Logged-in staff member working the dashboards."""
    weight = 1
    wait_time = constant_pacing(1.5)

    def on_start(self):
        r = self.client.get("/login")
        token = csrf_of(r.text)
        self.client.post("/login", data={
            "_csrf": token, "username": "loadstaff", "password": "LoadStaff#2026x",
        }, name="POST /login")

    @task(5)
    def dashboard(self):
        self.client.get("/", name="/ (staff dashboard)")

    @task(3)
    def complaints(self):
        self.client.get("/complaints?status=OPEN", name="/complaints (staff)")

    @task(2)
    def queue_control(self):
        self.client.get("/queue", name="/queue (staff)")

    @task(2)
    def bookings(self):
        self.client.get("/bookings", name="/bookings (staff)")

    @task(1)
    def feedbacks(self):
        self.client.get("/feedbacks", name="/feedbacks (staff)")

    @task(1)
    def referrals(self):
        self.client.get("/referrals", name="/referrals (staff)")
