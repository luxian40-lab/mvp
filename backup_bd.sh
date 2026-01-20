#!/bin/bash
# ========================================
# SCRIPT DE BACKUP ANTES DEL DEPLOYMENT
# ========================================
# Este script crea un backup completo de tu base de datos SQLite
# Ejecútalo ANTES de hacer el deploy a AWS

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backups"
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sqlite3"

echo "🔄 Creando backup de la base de datos..."

# Crear directorio de backups si no existe
mkdir -p $BACKUP_DIR

# Copiar base de datos
if [ -f "db.sqlite3" ]; then
    cp db.sqlite3 $BACKUP_FILE
    echo "✅ Backup creado: $BACKUP_FILE"
    
    # Listar backups existentes
    echo ""
    echo "📦 Backups disponibles:"
    ls -lh $BACKUP_DIR/
    
    echo ""
    echo "✅ Backup completado exitosamente"
    echo "⚠️  Guarda este archivo en un lugar seguro antes del deployment"
else
    echo "❌ ERROR: No se encontró db.sqlite3"
    exit 1
fi
