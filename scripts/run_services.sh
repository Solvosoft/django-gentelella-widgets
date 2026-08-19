#!/bin/bash
# Levanta servicios de soporte para el demo. Por defecto solo MailHog; --sign
# suma el servidor de firma digital.
#
#   - MailHog:   captura el correo que manda djgentelella.async_notification
#                (newsletters, notificaciones) sin un SMTP real.
#                SMTP :1025, UI web http://localhost:8025
#   - Firmador:  servidor de firma digital (extra [firmador], settings
#                FIRMADOR_*). Imagen "firmadorlibreserver" -- hay que
#                buildearla antes, ver docs/source/firmador-setup.rst (este
#                script no la genera). Puerto host 9001 -> contenedor 9999
#                (FIRMADOR_DOMAIN default).
#
# Uso:
#   ./scripts/run_services.sh          # solo MailHog
#   ./scripts/run_services.sh --sign   # MailHog + Firmador
#
# Foreground: Ctrl+C detiene y borra los contenedores levantados.
set -euo pipefail

SIGN=0
for arg in "$@"; do
  case "$arg" in
    --sign) SIGN=1 ;;
    *) echo "uso: $0 [--sign]" >&2; exit 1 ;;
  esac
done

MAILHOG=djgentelella_mailhog
FIRMADOR=firmadorserver
CONTAINERS=("$MAILHOG")

cleanup() { docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1; }
trap cleanup EXIT

docker run -d --rm --name "$MAILHOG" -p 8025:8025 -p 1025:1025 mailhog/mailhog
echo "MailHog:  UI http://localhost:8025  ·  SMTP localhost:1025"

if [ "$SIGN" = 1 ]; then
  CONTAINERS+=("$FIRMADOR")
  docker run -d --rm --name "$FIRMADOR" -p 9001:9999 firmadorlibreserver
  echo "Firmador: http://localhost:9001"
fi

echo "Ctrl+C para detener"

for c in "${CONTAINERS[@]}"; do
  docker logs -f "$c" &
done
wait
