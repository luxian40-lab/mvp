# Política de Backup y Recuperación — Eki

## 1. Componentes a Respaldar

| Componente | Ubicación | Frecuencia | Retención |
|---|---|---|---|
| **Base de datos (PostgreSQL)** | AWS RDS | Diario (automático) | 7 días |
| **Archivos de media** | AWS S3 `eki-produccion` | Versionado S3 | 30 días |
| **Código fuente** | GitHub `fresh-push-3` | Cada deploy | Indefinido |
| **Variables de entorno** | EB Configuration | Manual | Documentado |
| **Logs de WhatsApp** | DB (WhatsappLog) | Con DB backup | Con DB |
| **SQLite local (desarrollo)** | `db.sqlite3` | Manual | Local |

## 2. Backup de Base de Datos (RDS)

### Respaldos Automáticos (AWS RDS)

AWS RDS realiza snapshots automáticos diariamente:

- **Ventana de backup**: Configurable en la consola RDS (recomendado: 03:00-04:00 UTC)
- **Retención**: 7 días (configurable hasta 35 días)
- **Tipo**: Snapshot completo + logs de transacciones

### Snapshot Manual (Antes de deploys)

```bash
# Crear snapshot manual antes de un deploy importante
aws rds create-db-snapshot \
    --db-instance-identifier eki-prod-db \
    --db-snapshot-identifier eki-pre-deploy-$(date +%Y%m%d)
```

### Script Local (desarrollo)

Usar el script `backup_bd.ps1` incluido en el proyecto:

```powershell
.\backup_bd.ps1
```

Este copia `db.sqlite3` a una carpeta de backups con timestamp.

## 3. Backup de Archivos (S3)

### Versionado de S3

Habilitar versionado en el bucket para mantener historial de cambios:

```bash
aws s3api put-bucket-versioning \
    --bucket eki-produccion \
    --versioning-configuration Status=Enabled
```

### Lifecycle Rules (Retención)

Configurar regla de ciclo de vida para versiones antiguas:

```json
{
    "Rules": [
        {
            "ID": "cleanup-old-versions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 30
            }
        }
    ]
}
```

### Contenido del Bucket

```
eki-produccion/
├── media/
│   ├── certificados/          # Certificados generados (PDF/imagen)
│   ├── plantillas/            # Plantillas de certificados
│   ├── excels/                # Archivos Excel importados
│   ├── archivos_modulo/       # Material multimedia de cursos
│   └── profile/               # Logos e imágenes
```

## 4. Backup de Código

### Git (GitHub)

- **Rama principal**: `fresh-push-3`
- **Cada deploy** incluye commit con descripción de cambios
- Las migraciones están versionadas en git

### Pre-deploy Checklist

1. `git status` — verificar que no hay cambios sin commitear
2. `git add -A && git commit -m "..."` — commitear todo
3. `git push origin fresh-push-3` — subir a GitHub
4. Crear snapshot de RDS si el deploy incluye migraciones
5. `eb deploy` — desplegar

## 5. Recuperación

### Restaurar Base de Datos (RDS)

```bash
# Listar snapshots disponibles
aws rds describe-db-snapshots \
    --db-instance-identifier eki-prod-db \
    --query "DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime]" \
    --output table

# Restaurar desde snapshot
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier eki-prod-db-restored \
    --db-snapshot-identifier eki-pre-deploy-20260201
```

### Restaurar Archivos S3

```bash
# Listar versiones de un archivo
aws s3api list-object-versions \
    --bucket eki-produccion \
    --prefix media/certificados/cert_123.png

# Restaurar versión anterior
aws s3api get-object \
    --bucket eki-produccion \
    --key media/certificados/cert_123.png \
    --version-id XXXXX \
    restored_cert_123.png
```

### Rollback de Código

```bash
# Ver deploys anteriores
eb list-environments

# Rollback a versión anterior de EB
eb deploy --version <version-label>

# O rollback de git
git revert HEAD
git push origin fresh-push-3
eb deploy
```

## 6. Plan de Contingencia

### Falla Total de BD

1. Restaurar desde último snapshot de RDS (< 24h de pérdida)
2. Verificar migraciones: `python manage.py showmigrations`
3. Aplicar migraciones pendientes: `python manage.py migrate`
4. Verificar integridad: `python manage.py check`

### Falla de S3

1. S3 tiene 99.999999999% de durabilidad — falla es extremadamente rara
2. Restaurar desde versiones anteriores si se sobrescribió un archivo
3. Re-generar certificados desde la base de datos si es necesario

### Falla de Twilio

1. El webhook retorna errores que se logean
2. Los mensajes tienen fallback a texto plano
3. Monitorear en Twilio Console: https://console.twilio.com/

### Falla de EB

1. `eb health` — verificar estado
2. `eb logs` — revisar logs
3. `eb deploy` — re-desplegar última versión
4. Si persiste: `eb restore <environment-id>` o recrear environment

## 7. Monitoreo

### Metrics Recomendadas

- **RDS**: CPU, conexiones activas, espacio libre
- **EB**: Health status, request count, latency
- **S3**: Requests count, storage size
- **Twilio**: Message delivery rate, error rate

### Alertas (CloudWatch)

```bash
# Alerta de salud de EB
aws cloudwatch put-metric-alarm \
    --alarm-name eki-eb-health \
    --metric-name HealthyHostCount \
    --namespace AWS/ElasticBeanstalk \
    --statistic Minimum \
    --period 300 \
    --threshold 1 \
    --comparison-operator LessThanThreshold
```

## 8. Frecuencia de Pruebas

| Prueba | Frecuencia |
|---|---|
| Verificar snapshots RDS | Semanal |
| Test de restauración | Mensual |
| Verificar versionado S3 | Mensual |
| Auditar variables de entorno | Trimestral |
| Simulacro de recuperación completa | Semestral |
