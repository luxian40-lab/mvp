#!/bin/bash
# Si EKI_EB_ROLE=ai_workers → usa Procfile.ai (inst. 2 Celery IA).
set -e
ROLE="${EKI_EB_ROLE:-web}"
if [ "$ROLE" = "ai_workers" ] && [ -f Procfile.ai ]; then
  cp Procfile.ai Procfile
  echo "eki: Procfile.ai activo (EKI_EB_ROLE=ai_workers)"
fi
