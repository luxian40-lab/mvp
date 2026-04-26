# Route Map by Domain

## Admin and dashboards
- `admin/dashboard/`
- `admin/dashboard/resumen-data/`
- `admin/dashboard-antiguo/`
- `admin/dashboard-metrics/`
- `admin/dashboard-analytics/`
- `admin/analytics/*`
- `admin/reportes-avanzados/*`
- `admin/crear-curso-ia/`
- `admin/vista-previa-curso-ia/`
- `admin/dashboard-gerencial/`
- `admin/calendario/`
- `admin/conversaciones/`
- `admin/importar-estudiantes/`
- `admin/importar-prospectos/`
- `admin/bot-comercial/`
- `admin/test-email/`

## Webhooks
- `webhook/whatsapp/`
- `webhook/ia-bot-comercial/`

## Public APIs
- `api/estudiante/<telefono>/`
- `api/estudiante/<telefono>/progreso/`
- `api/estudiante/<telefono>/siguiente-tarea/`
- `api/empleabilidad/*`
- `api/integracion/*`

## Certificados
- `verificar-certificado/<codigo_verificacion>/`
- `descargar-certificado/<codigo_verificacion>/`
- `api/certificados/verificar/`

## Media
- `media/modulo/<modulo_id>/archivos/`
- `media/stream/`
- `media/descargar-archivo/<archivo_id>/`
- `media-proxy/<filename>`

## Health and root
- `health/`
- `/` (redirect a admin)
