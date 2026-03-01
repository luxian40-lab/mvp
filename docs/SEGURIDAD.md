# Política de Seguridad — Eki

## 1. Autenticación y Autorización

### Onboarding WhatsApp (3 barreras)
1. **Habeas Data**: El estudiante debe aceptar el tratamiento de datos personales (Ley 1581 de 2012) mediante botón interactivo de Twilio.
2. **Verificación 2FA (Cédula)**: El estudiante debe ingresar su número de cédula exacto, que se compara contra el registro en BD.
3. **Confirmación de Datos**: El estudiante verifica que sus datos (nombre, cédula, organización) son correctos.

Solo después de las 3 barreras el `estado_chat` pasa a `ACTIVO`.

### Admin Django
- Autenticación del admin vía Django Auth (usuario/contraseña).
- Superusuarios y staff con permisos granulares por modelo.
- Gestión de sesiones con la configuración estándar de Django.

## 2. Protección de Datos Personales

### Datos Recopilados

| Dato | Campo | Sensibilidad |
|---|---|---|
| Cédula | `cedula` (unique) | Alta |
| Nombre | `nombre` | Media |
| Teléfono | `telefono` (unique) | Alta |
| Municipio | `municipio` | Baja |
| Departamento | `departamento` | Baja |
| Género | `genero` (M/F/O/NR) | Media |

### Medidas

- **Transmisión**: HTTPS (TLS) para todo el tráfico web y webhook.
- **Almacenamiento**: PostgreSQL RDS con cifrado en reposo habilitado.
- **Archivos**: S3 con acceso controlado por IAM policies.
- **Habeas Data**: Registro de fecha/hora de aceptación (`fecha_aceptacion_terminos`).
- **Eliminación**: Cascada controlada en `delete_model` — relaciones eliminadas en orden.

## 3. Seguridad de la Infraestructura

### AWS

| Servicio | Configuración de Seguridad |
|---|---|
| **Elastic Beanstalk** | Security groups, HTTPS listener |
| **RDS PostgreSQL** | Cifrado AES-256, backups automáticos |
| **S3** | Bucket policy restrictiva, no público por defecto |
| **IAM** | Principio de menor privilegio |

### Variables de Entorno Sensibles

Almacenadas como variables de entorno de EB (nunca en código):

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL` (PostgreSQL connection string)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `DJANGO_SECRET_KEY`

## 4. Seguridad en WhatsApp

### Twilio Content Templates
- Todos los mensajes masivos usan **Content Templates aprobados** por Twilio/Meta.
- No se envían mensajes de sesión no solicitados.
- Validación en el admin: campañas requieren Content SID válido antes de ejecutar.

### Rate Limiting
- El webhook procesa mensajes secuencialmente por número.
- Status callbacks (queued, sent, delivered) se ignoran para no re-procesar.
- Filtros: mensajes sin Body/Media se descartan.

### Audio
- Las notas de voz se transcriben con Whisper localmente.
- No se almacena el audio después de la transcripción.

## 5. Registro y Auditoría

- **WhatsappLog**: Registro de todo mensaje entrante (INCOMING) y enviado (SENT).
- **AuditLog**: Registro de acciones administrativas.
- **EnvioLog**: Registro por campaña/estudiante de cada envío y su estado.

## 6. Manejo de Errores

- Los errores de envío de Twilio se capturan y registran sin exponer al usuario.
- Los errores de webhook retornan HTTP 500 pero se logean completamente con traceback.
- Los templates de Twilio tienen fallback a texto plano si el template falla.

## 7. Cumplimiento

- **Ley 1581 de 2012** (Colombia): Protección de datos personales — consentimiento obligatorio.
- **Política de WhatsApp Business**: Templates aprobados para mensajes proactivos.
- **GDPR-ready**: Estructura preparada para derecho al olvido (eliminación controlada).

## 8. Acciones Recomendadas

- [ ] Implementar rotación periódica de credenciales Twilio/AWS.
- [ ] Habilitar MFA para acceso al admin Django.
- [ ] Configurar alertas de CloudWatch para patrones anómalos en el webhook.
- [ ] Implementar backups automatizados con retención de 30 días.
- [ ] Auditar permisos IAM trimestralmente.
