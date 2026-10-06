#!/bin/sh
# API and background worker in one container, for hosts where a separate worker costs money
# (e.g. Render's free tier). Docker Compose runs them as separate services instead.
set -e

alembic upgrade head

# Keep the worker running: restart it if it ever exits.
(
  while true; do
    python -m app.workers.main || true
    echo "worker exited; restarting in 5s" >&2
    sleep 5
  done
) &

# No --proxy-headers: X-Forwarded-For can be forged through the proxies in front, which would let
# a client dodge the login rate limit. Behind them all requests share one limit bucket instead.
exec uvicorn app.asgi:app --host 0.0.0.0 --port "${PORT:-8000}"
