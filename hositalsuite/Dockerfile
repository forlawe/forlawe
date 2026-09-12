# Portable production deployment (fallback target per failure-matrix §40)
FROM python:3.13-slim

WORKDIR /srv/hospitalsuite
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8077

COPY requirements.txt alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py start.sh ./
RUN chmod +x start.sh

# F-003: migrations/ + alembic.ini must ship in the image. The app runs
# `alembic upgrade head` at boot (run_alembic_upgrade); without these files
# the documented Docker fallback path silently skipped every migration and
# fell back to ensure_schema() — the exact drift the migration chain exists
# to prevent.
RUN chmod +x start.sh

# data directories (mount a volume in production to persist DB/uploads/backups
# when using SQLite; with PostgreSQL only uploads/backups need persistence)
RUN mkdir -p data/uploads data/reports data/backups

EXPOSE 8077

# gunicorn: production WSGI server.
# WEB_CONCURRENCY defaults to 1 because the in-process scheduler must run exactly
# once; multiple workers would double-send reminders/escalations. When you scale
# horizontally, run one scheduler process and set DISABLE_SCHEDULER=1 on web workers.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8077} --workers ${WEB_CONCURRENCY:-1} --threads ${WEB_THREADS:-4} --timeout 120 'app:create_app()'"]
