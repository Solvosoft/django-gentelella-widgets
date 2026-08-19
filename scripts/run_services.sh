#!/bin/bash
# Runs support services for the demo. MailHog only by default; --sign adds
# the digital-signature server; --celery adds Redis (broker) to exercise
# async_notification's queued dispatch.
#
#   - MailHog:   captures the mail djgentelella.async_notification sends
#                (newsletters, notifications) without a real SMTP server.
#                SMTP :1025, web UI http://localhost:8025
#   - Firmador:  digital-signature server (extra [firmador], FIRMADOR_*
#                settings). Image "firmadorlibreserver" -- build it first,
#                see docs/source/firmador-setup.rst (this script doesn't
#                build it). Host port 9001 -> container 9999 (matches
#                FIRMADOR_DOMAIN's default).
#   - Redis:     Celery broker (extra [celery], CELERY_BROKER_URL setting).
#                Without this (or without CELERY_BROKER_URL set)
#                async_notification just falls back to SyncBackend -- Redis
#                is only for exercising the real queue. Host port 6379.
#
# Usage:
#   ./scripts/run_services.sh            # MailHog only
#   ./scripts/run_services.sh --sign     # MailHog + Firmador
#   ./scripts/run_services.sh --celery   # MailHog + Redis
#
# Foreground: Ctrl+C stops and removes the containers.
set -euo pipefail

SIGN=0
CELERY=0
for arg in "$@"; do
  case "$arg" in
    --sign) SIGN=1 ;;
    --celery) CELERY=1 ;;
    *) echo "usage: $0 [--sign] [--celery]" >&2; exit 1 ;;
  esac
done

MAILHOG=djgentelella_mailhog
FIRMADOR=firmadorserver
REDIS=djgentelella_redis
CONTAINERS=("$MAILHOG")

cleanup() { docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1; }
trap cleanup EXIT

docker run -d --rm --name "$MAILHOG" -p 8025:8025 -p 1025:1025 mailhog/mailhog
echo "MailHog:  UI http://localhost:8025  ·  SMTP localhost:1025"
echo "          the demo server defaults to the console backend (prints, doesn't send) --"
echo "          run it with 'make run-mailhog' (or EMAIL_BACKEND=smtp EMAIL_HOST=localhost"
echo "          EMAIL_PORT=1025) so email actually lands here"

if [ "$SIGN" = 1 ]; then
  CONTAINERS+=("$FIRMADOR")
  docker run -d --rm --name "$FIRMADOR" -p 9001:9999 firmadorlibreserver
  echo "Firmador: http://localhost:9001"
fi

if [ "$CELERY" = 1 ]; then
  CONTAINERS+=("$REDIS")
  docker run -d --rm --name "$REDIS" -p 6379:6379 redis:7
  echo "Redis:    localhost:6379 -- set CELERY_BROKER_URL=redis://localhost:6379/0"
  echo "          and run: cd demo && celery -A demo worker -l info"
fi

echo "Ctrl+C to stop"

for c in "${CONTAINERS[@]}"; do
  docker logs -f "$c" &
done
wait
