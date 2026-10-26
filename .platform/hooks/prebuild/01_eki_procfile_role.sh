#!/bin/bash
# Si EKI_EB_ROLE=ai_workers → usa Procfile.ai (inst. 2 Celery IA).
set -e
# Elastic Beanstalk no exporta las propiedades del entorno a los hooks de prebuild.
GET_CONFIG="${EKI_GET_CONFIG:-/opt/elasticbeanstalk/bin/get-config}"
ROLE="${EKI_EB_ROLE:-}"
if [ -z "$ROLE" ] && [ -x "$GET_CONFIG" ]; then
  ROLE="$("$GET_CONFIG" environment -k EKI_EB_ROLE 2>/dev/null || true)"
fi
ROLE="${ROLE:-web}"
if [ "$ROLE" = "ai_workers" ] && [ -f Procfile.ai ]; then
  grep -v '^[[:space:]]*#' Procfile.ai | sed '/^[[:space:]]*$/d' > Procfile
  echo "eki: Procfile.ai activo (EKI_EB_ROLE=ai_workers)"
fi
