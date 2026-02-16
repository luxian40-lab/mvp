#!/bin/bash
# Limpiar archivos corruptos antes del deploy

echo "=== LIMPIANDO ARCHIVOS CORRUPTOS ==="

# Eliminar response_templates.py corrupto si existe
if [ -f "/var/app/current/core/response_templates.py" ]; then
    echo "Eliminando response_templates.py corrupto..."
    rm -f /var/app/current/core/response_templates.py
fi

# Eliminar caché de Python
echo "Limpiando caché de Python..."
find /var/app/current -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /var/app/current -name "*.pyc" -delete 2>/null || true

echo "=== LIMPIEZA COMPLETADA ==="
