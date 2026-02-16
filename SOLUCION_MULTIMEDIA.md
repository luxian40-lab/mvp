# 🚨 SOLUCIÓN URGENTE: MULTIMEDIA NO FUNCIONA

## PROBLEMA IDENTIFICADO

✅ **S3 está funcionando correctamente** (test exitoso)  
✅ **El código está listo** para enviar multimedia  
❌ **NO hay archivos reales subidos** en S3

### Estado actual de S3:
```
s3://eki-produccion/media/
├── test-manual.txt (16 Bytes)
└── test/imagen-prueba.jpg (2.5 KB)

❌ media/modulos/ → VACÍO (0 archivos)
```

### Registros en base de datos:
- **ArchivoModulo** tiene registros con `activo=True`
- Campo `archivo` = **NULL** (no hay archivo subido)
- El admin muestra: "Actualmente: modulos/2026/02/VIDEO_MODULO_0.mp4"
- Pero el archivo NO existe en S3

---

## 3 SOLUCIONES INMEDIATAS

### 🎯 OPCIÓN 1: SUBIR ARCHIVOS VÍA ADMIN (Recomendado)

**Pasos:**
1. Ir a: https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/admin
2. Login con tu usuario admin
3. Ir a: **Core → Archivos Módulo**
4. Editar cada archivo (ej: "video bienvenida")
5. En el campo **"Subir Archivo desde PC"** → Seleccionar el video/imagen
6. Guardar

**✅ Django automáticamente subirá a S3** (ya configurado)

---

### 🎯 OPCIÓN 2: USAR URLs EXTERNAS (Más rápido)

Si tienes los archivos en YouTube, Google Drive, Dropbox:

1. Admin → Core → Archivos Módulo
2. Editar archivo
3. En campo **"URL Externa"** → Pegar link público
4. Guardar

**Ejemplos de URLs válidas:**
- YouTube: `https://www.youtube.com/watch?v=VIDEO_ID`
- Drive: `https://drive.google.com/file/d/FILE_ID/view?usp=sharing`
- S3 directo: `https://eki-produccion.s3.amazonaws.com/media/video.mp4`

---

### 🎯 OPCIÓN 3: SUBIR DIRECTO A S3 (Técnico)

Si tienes archivos grandes localmente:

```powershell
# Subir un video
aws s3 cp C:\ruta\al\video.mp4 s3://eki-produccion/media/modulos/2026/02/VIDEO_MODULO_0.mp4 --region us-east-2

# Verificar
aws s3 ls s3://eki-produccion/media/modulos/ --recursive --human-readable
```

Luego en admin:
1. Editar ArchivoModulo
2. Escribir manualmente en campo `archivo`: `modulos/2026/02/VIDEO_MODULO_0.mp4`
3. Guardar

---

## 📋 VERIFICACIÓN POST-SUBIDA

Después de subir archivos, verificar:

```powershell
# Ver archivos en S3
aws s3 ls s3://eki-produccion/media/modulos/ --recursive --human-readable

# Debería mostrar:
# 2026-02-04 15:30:00    5.2 MiB media/modulos/2026/02/VIDEO_MODULO_0.mp4
# 2026-02-04 15:31:00  120.5 KiB media/modulos/2026/02/imagen_cafe.jpg
```

---

## 🔧 CONFIGURAR NOMBRE "EKI SOLUCIONES"

Para que aparezca "EKI Soluciones" en lugar del número:

### En Twilio Console:

1. Ir a: https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders
2. Click en tu número: **+573202948806**
3. En **"Sender Display Name"** → Escribir: **EKI Soluciones**
4. Guardar

**⚠️ Nota:** Esto requiere que tu número esté **aprobado** (no Sandbox). Si aún estás en Sandbox, necesitas:
- Enviar solicitud de aprobación a Twilio
- Proveer documentos de negocio
- Esperar aprobación (1-3 días)

---

## 📊 CAPACIDAD DEL SERVIDOR

### Configuración actual:

**Gunicorn:**
```
Workers: 3
Threads per worker: 4
Total capacidad: 12 conexiones simultáneas
```

**Servidor EC2:**
- Tipo: t3.small (2 vCPU, 2 GB RAM)
- Django: 1 worker process
- PostgreSQL: RDS db.t3.micro

### Usuarios simultáneos estimados:

| Escenario | Usuarios | Estado |
|-----------|----------|--------|
| Bajo uso | 5-10 | ✅ Estable |
| Medio uso | 20-30 | ⚠️ Puede ralentizar |
| Alto uso | 50+ | 🔴 Riesgo de timeout |

### Recomendaciones:

**Inmediato:**
- ✅ Ya configurado: timeout 120s, max-requests 1000
- ✅ Workers: 3 (óptimo para 2 vCPU)

**Si creces a >30 usuarios:**
1. Upgrade a EC2 t3.medium (2 vCPU, 4 GB RAM)
2. Aumentar workers: 5-6
3. Considerar auto-scaling

**Si creces a >100 usuarios:**
1. EC2 t3.large + Auto Scaling Group
2. Load Balancer
3. Cache con Redis
4. CDN para videos (CloudFront)

---

## ✅ CHECKLIST FINAL

Antes de ir a producción con usuarios:

- [ ] Subir TODOS los videos/imágenes necesarios
- [ ] Verificar cada archivo en S3: `aws s3 ls`
- [ ] Probar en WhatsApp: enviar "hola" y navegar hasta módulo con video
- [ ] Confirmar que video se reproduce
- [ ] Configurar nombre "EKI Soluciones" en Twilio (si aprobado)
- [ ] Documentar cuántos usuarios esperados
- [ ] Monitorear logs: `aws logs tail /aws/elasticbeanstalk/eki-prod-final/var/log/web.stdout.log`

---

## 🆘 SOPORTE RÁPIDO

**Si un usuario reporta "video no se ve":**

1. Verificar archivo existe en S3:
   ```powershell
   aws s3 ls s3://eki-produccion/media/modulos/ --recursive
   ```

2. Probar URL directa:
   ```
   https://eki-produccion.s3.amazonaws.com/media/modulos/2026/02/archivo.mp4
   ```

3. Revisar logs:
   ```powershell
   aws logs tail /aws/elasticbeanstalk/eki-prod-final/var/log/web.stdout.log --follow
   ```

**Si todo falla:** Usar URL externa (YouTube/Drive) como backup temporal.
