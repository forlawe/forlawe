#!/usr/bin/env bash
# Load-test runner: boots dedicated gunicorn instances and runs locust scenarios.
# Usage: bash loadtest/run.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p loadtest/results data

export RATE_LIMIT_SCALE=100000   # capacity measurement only — see locustfile header
export SECRET_KEY="loadtest-key"
export DISABLE_SCHEDULER=1

PORT=8090
stop_server() { pkill -f "gunicorn.*hms-load-instance" 2>/dev/null || true; sleep 1; }

start_server() {  # $1=workers $2=threads $3=database_url
  DATABASE_URL="$3" gunicorn --bind 127.0.0.1:$PORT --workers "$1" --threads "$2" \
    --timeout 120 --name hms-load-instance --daemon --pid /tmp/hms-load.pid \
    --access-logfile /tmp/hms-load-access.log --error-logfile /tmp/hms-load-error.log \
    "app:create_app()"
  for i in $(seq 1 30); do
    curl -s -o /dev/null http://127.0.0.1:$PORT/api/v1/health && return 0
    sleep 0.5
  done
  echo "server failed to start"; tail /tmp/hms-load-error.log; return 1
}

run_locust() {  # $1=name $2=users $3=duration
  echo "=== $1: $2 users for $3 ==="
  locust -f loadtest/locustfile.py --headless --host http://127.0.0.1:$PORT \
    -u "$2" -r 25 -t "$3" --csv loadtest/results/"$1" --only-summary 2>&1 | tail -30
}

echo "--- Scenario set starting ---"
