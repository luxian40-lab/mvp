# 🚨 PLAN DE EMERGENCIA: CREDENCIALES TWILIO COMPROMETIDAS

**Fecha:** Febrero 4, 2026  
**Severidad:** CRÍTICA  
**Estado:** EN INVESTIGACIÓN

---

## ⚠️ SITUACIÓN ACTUAL

**Reporte:** Usuario indica posible exposición de credenciales Twilio  
**Vector:** Notificación por correo electrónico  
**Repositorio:** https://github.com/luxian40-lab/mvp  
**Revisión inicial:** ✅ NO HAY CREDENCIALES REALES en GitHub

---

## ✅ VERIFICACIONES COMPLETADAS

### 1. Revisión de Git History
```bash
git log --all --full-history -- .env .env.local .env.production
# Resultado: VACÍO (nunca se subieron archivos .env)
```

### 2. Revisión de Archivos Públicos
- `.env.example`: ✅ Solo placeholders
- `verificar_numero_twilio.py`: ✅ Solo placeholders  
- Ningún archivo con `ACa[32 chars]` reales

### 3. Variables en EB
```bash
eb printenv | grep TWILIO
# Resultado: Credenciales están SOLO en EB (no en código)
```

---

## 🔒 PLAN DE ROTACIÓN INMEDIATA

### PASO 1: Rotar Credenciales Twilio (URGENTE)

**1.1 Crear nuevas credenciales:**
```
1. Ir a: https://console.twilio.com/
2. Account → API keys & tokens
3. Crear nuevo Auth Token
4. COPIAR INMEDIATAMENTE (solo se muestra una vez)
```

**1.2 Revocar credenciales antiguas:**
```
1. Console → Account → Auth Tokens
2. Encontrar token actual
3. Click "Revoke" / "Delete"
4. Confirmar revocación
```

**1.3 Actualizar en Elastic Beanstalk:**
```bash
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp

eb setenv TWILIO_AUTH_TOKEN="nuevo_token_aqui"

eb restart
```

**1.4 Verificar funcionamiento:**
```bash
# Enviar mensaje de prueba desde WhatsApp
# Verificar logs
eb logs --stream
```

### PASO 2: Rotar AWS Credentials (PREVENTIVO)

**2.1 AWS Console:**
```
1. IAM → Users → tu-usuario
2. Security credentials
3. Access keys → Create access key
4. COPIAR access_key_id y secret_access_key
5. Delete old key
```

**2.2 Actualizar en EB:**
```bash
eb setenv \
  AWS_ACCESS_KEY_ID="nuevo_key_id" \
  AWS_SECRET_ACCESS_KEY="nuevo_secret_key"

eb restart
```

### PASO 3: Rotar SECRET_KEY Django (PREVENTIVO)

**3.1 Generar nueva:**
```bash
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp
python scripts/utils/generar_secret_key.py
```

**3.2 Actualizar en EB:**
```bash
eb setenv SECRET_KEY="nueva_secret_key_django"
eb restart
```

### PASO 4: Cambiar Contraseñas PostgreSQL (PREVENTIVO)

**4.1 AWS RDS Console:**
```
1. RDS → Databases → eki-database
2. Modify
3. Master password → Set new password
4. Apply immediately
```

**4.2 Actualizar DATABASE_URL:**
```bash
# Nueva URL con nueva contraseña
NEW_DB_URL="postgresql://ekiadmin:NUEVA_PASSWORD@eki-database.c5awuis82zet.us-east-2.rds.amazonaws.com:5432/ekidb"

eb setenv DATABASE_URL="$NEW_DB_URL"
eb restart
```

---

## 🔍 MONITOREO POST-ROTACIÓN

### Logs a revisar:
```bash
# 1. Verificar conexión Twilio
eb logs | grep -i "twilio\|whatsapp\|mensaje"

# 2. Verificar conexión S3
eb logs | grep -i "s3\|aws\|media"

# 3. Verificar conexión DB
eb logs | grep -i "database\|postgres\|connection"

# 4. Verificar Django funcionando
eb logs | grep -i "error\|warning\|critical"
```

### Test funcional:
1. ✅ Enviar "menu" desde WhatsApp → Debe responder
2. ✅ Enviar "continuar" → Debe mostrar módulo con multimedia
3. ✅ Ver admin: https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/admin
4. ✅ Verificar certificados generados

---

## 📋 CHECKLIST DE SEGURIDAD

### Inmediato (0-1 hora):
- [ ] Identificar correo exacto recibido
- [ ] Determinar si es falsa alarma o real
- [ ] Si real: Rotar Twilio Auth Token
- [ ] Si real: Verificar Twilio usage logs (llamadas no autorizadas)
- [ ] Reiniciar aplicación en EB

### Corto plazo (1-24 horas):
- [ ] Rotar AWS Access Keys (preventivo)
- [ ] Rotar Django SECRET_KEY (preventivo)
- [ ] Revisar logs de acceso no autorizado
- [ ] Implementar 2FA en todas las cuentas

### Mediano plazo (1-7 días):
- [ ] Implementar secrets management (AWS Secrets Manager)
- [ ] Configurar alertas de seguridad en Twilio
- [ ] Configurar alertas de billing (uso anormal)
- [ ] Documentar procedimiento de rotación
- [ ] Capacitar equipo en mejores prácticas

---

## 🛡️ PREVENCIÓN FUTURA

### 1. Usar AWS Secrets Manager
```python
# mvp_project/settings.py
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-2')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise e

# En lugar de:
# TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

# Usar:
# TWILIO_AUTH_TOKEN = get_secret('eki/twilio/auth_token')
```

### 2. Configurar IP Whitelisting en Twilio
```
Console → Account → Security → IP Access Control Lists
Agregar IPs de EB solamente
```

### 3. Alertas de Uso Anormal
```
Console → Monitor → Alerts
- Configurar alerta si > 1000 mensajes/día
- Configurar alerta si > $50/día
```

### 4. Rotación Automática
```bash
# Cron job mensual
0 0 1 * * /usr/local/bin/rotate_credentials.sh
```

---

## 📞 CONTACTOS DE EMERGENCIA

- **Twilio Support:** https://support.twilio.com
- **AWS Support:** https://console.aws.amazon.com/support
- **GitHub Security:** security@github.com

---

## 📝 NOTAS

**Última actualización:** Febrero 4, 2026  
**Responsable:** Equipo Eki MVP  
**Próxima revisión:** Después de confirmación del correo
