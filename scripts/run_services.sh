#!/bin/bash
# Levanta servicios de soporte para el demo. Por defecto solo MailHog; --sign
# suma el servidor de firma digital; --celery suma Redis (broker) para
# probar el dispatch en cola de async_notification.
#
#   - MailHog:   captura el correo que manda djgentelella.async_notification
#                (newsletters, notificaciones) sin un SMTP real.
#                SMTP :1025, UI web http://localhost:8025
#   - Firmador:  servidor de firma digital (extra [firmador], settings
#                FIRMADOR_*). Imagen "firmadorlibreserver" -- hay que
#                buildearla antes, ver docs/source/firmador-setup.rst (este
#                script no la genera). Puerto host 9001 -> contenedor 9999
#                (FIRMADOR_DOMAIN default).
#   - Redis:     broker de Celery (extra [celery], setting CELERY_BROKER_URL).
#                Sin esto (o sin CELERY_BROKER_URL seteado) async_notification
#                cae solo a SyncBackend -- Redis es solo para probar la cola
#                de verdad. Puerto host 6379.
#
# Uso:
#   ./scripts/run_services.sh            # solo MailHog
#   ./scripts/run_services.sh --sign     # MailHog + Firmador
#   ./scripts/run_services.sh --celery   # MailHog + Redis
#
# Foreground: Ctrl+C detiene y borra los contenedores levantados.
set -euo pipefail

SIGN=0
CELERY=0
for arg in "$@"; do
  case "$arg" in
    --sign) SIGN=1 ;;
    --celery) CELERY=1 ;;
    *) echo "uso: $0 [--sign] [--celery]" >&2; exit 1 ;;
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
echo "          demo server default is the console backend (prints, doesn't send) --"
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

echo "Ctrl+C para detener"

for c in "${CONTAINERS[@]}"; do
  docker logs -f "$c" &
done
wait
