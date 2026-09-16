#!/bin/bash
# Permisos de CHROMA_DB_DIR. Vive aqui y no en .ebextensions porque en AL2023
# la seccion commands solo corre al crear la instancia, no en cada deploy.
set -u

ENVF=/opt/elasticbeanstalk/deployment/env
if [ -f "$ENVF" ]; then
  set -a; . "$ENVF" 2>/dev/null || true; set +a
fi
CHROMA_DIR="${CHROMA_DB_DIR:-/var/app/chroma_data}"

mkdir -p "$CHROMA_DIR"
chown -R webapp:webapp "$CHROMA_DIR" || true
# setgid: lo que cree webapp o ec2-user queda escribible por el grupo
find "$CHROMA_DIR" -type d -exec chmod 2775 {} + || true
find "$CHROMA_DIR" -type f -exec chmod 664 {} + || true
# ec2-user corre los scripts de ops por SSH y necesita escribir el sqlite de chroma
usermod -aG webapp ec2-user || true

echo "[chroma] $CHROMA_DIR listo ($(stat -c '%U:%G %a' "$CHROMA_DIR"))"
