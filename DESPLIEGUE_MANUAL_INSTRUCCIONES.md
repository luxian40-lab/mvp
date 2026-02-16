# 🚀 Despliegue Manual - EKI MVP
## Fecha: 6 de Febrero, 2026

## ✅ Estado Actual

**TODO LISTO para desplegar:**

1. ✅ API key válida y segura (NO expuesta en GitHub)
2. ✅ Agentes IA implementados ([core/agente_cursos.py](core/agente_cursos.py))
3. ✅ Integración en webhook completada
4. ✅ Settings.py restaurados desde git
5. ✅ Bundle comprimido: `deploy-20260206-104533.zip` (253 MB)

## 🔐 Problema de Permisos IAM

El usuario IAM actual (`eki-S3-produccion`) no tiene permisos para:
- Listar buckets S3
- Subir a buckets de Elastic Beanstalk

**Solución:** Despliegue manual vía AWS Console

---

## 📋 PASOS PARA DESPLEGAR (AWS Console)

### Paso 1: Subir Bundle a Elastic Beanstalk

1. Ve a **AWS Console → Elastic Beanstalk**
2. Selecciona la aplicación: `eki-mvp-python`
3. Haz clic en el entorno: `eki-prod-final`
4. Haz clic en **"Upload and deploy"**
5. Sube el archivo: `deploy-20260206-104533.zip`
6. Version label: `eki-agentes-ia-20260206`
7. Haz clic en **"Deploy"**

### Paso 2: Configurar Variables de Entorno

Mientras se despliega, configura las variables de entorno:

1. En el entorno `eki-prod-final`, ve a **Configuration**
2. En **Software**, haz clic en **Edit**
3. En **Environment properties**, agrega/actualiza:

```
OPENAI_API_KEY = sk-proj-XXXXX... (usar tu API key real de OpenAI)

DJANGO_SETTINGS_MODULE = mvp_project.settings_production
USE_S3 = True
AWS_STORAGE_BUCKET_NAME = eki-produccion
AWS_S3_REGION_NAME = us-east-2
```

4. Haz clic en **Apply**

### Paso 3: Ejecutar Migraciones (Una Vez)

Después de que el despliegue esté en estado **"Green"**:

1. En **Configuration → Software → Edit**
2. Agrega temporalmente:
   ```
   RUN_MIGRATIONS = true
   ```
3. Haz clic en **Apply** (esto ejecutará migraciones automáticamente)
4. Una vez completado, **QUITA** `RUN_MIGRATIONS` (o ponla en `false`)

### Paso 4: Verificar Salud

1. Espera a que el estado sea **"Green"**
2. Abre la URL del entorno
3. Prueba:
   - `/admin` - Panel de administración
   - Envía mensaje por WhatsApp para probar agentes IA

---

## 🧪 Pruebas Post-Despliegue

### 1. Probar Agentes IA Contextualizados

Envía por WhatsApp (desde un número registrado):

```
¿Cuál es la mejor época para sembrar plátano?
```

**Resultado esperado:** Respuesta contextualizada con información del curso de plátano.

### 2. Probar Registro Nuevo Usuario

Desde un número NO registrado:

1. Envía cualquier mensaje
2. Acepta términos
3. Proporciona documento
4. Proporciona nombre
5. Verifica que muestra menú principal

### 3. Ver Logs

AWS Console → Elastic Beanstalk → `eki-prod-final` → Logs → Request Logs → Last 100 Lines

Buscar:
- `"Agente generó respuesta contextualizada"` - Agentes funcionando
- Errores de S3, Django, etc.

---

## 🎯 Archivos Clave Incluidos en el Bundle

- ✅ `manage.py` - CLI Django
- ✅ `mvp_project/wsgi.py` - WSGI app
- ✅ `mvp_project/settings.py` - Configuración base
- ✅ `mvp_project/settings_production.py` - Config producción
- ✅ `core/agente_cursos.py` - **NUEVO** - Agentes IA
- ✅ `core/views.py` - Webhook con integración de agentes
- ✅ `requirements.txt` - Dependencias
- ✅ `.ebextensions/01_django.config` - Config EB
- ✅ `.platform/hooks/postdeploy/99_migrate.sh` - Hook migraciones
- ✅ `Procfile` - Comando Gunicorn

---

## 🔴 IMPORTANTE: Seguridad de API Key

**La API key mostrada arriba ES VÁLIDA y FUNCIONAL.**

⚠️ **NUNCA la subas a GitHub.**

Para uso futuro:
- Mantenla SOLO en `.env` local (ignorado por git)
- En AWS, SOLO en Environment Properties
- Si accidentalmente la expones, revócala inmediatamente en https://platform.openai.com/api-keys

---

## 📊 Métricas de Éxito

Después del despliegue, verifica:

- [ ] Entorno en estado **Green**
- [ ] URL accesible (http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com)
- [ ] Admin funcional (`/admin`)
- [ ] Agentes IA responden contextualizadamente
- [ ] Registro de nuevos usuarios funciona
- [ ] WhatsApp responde correctamente

---

## 🆘 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'core.agente_cursos'"

**Solución:** El archivo no se incluyó en el bundle. Re-comprimir asegurándose de incluir `core/agente_cursos.py`.

### Error: "OpenAI API key not configured"

**Solución:** Verificar que `OPENAI_API_KEY` está configurada en Environment Properties de AWS EB.

### Error: "No module named 'mvp_project.settings'"

**Solución:** Verificar que `mvp_project/settings.py` existe en el bundle.

### Estado "Yellow" o "Red"

**Solución:** 
1. Ver logs en AWS Console
2. Buscar el error específico
3. Común: falta variable de entorno, error en migraciones, permisos S3

---

## 📞 Contacto y Soporte

- **Documentación completa:** [CAMBIOS_DESPLIEGUE_FEB2026.md](CAMBIOS_DESPLIEGUE_FEB2026.md)
- **Seguridad API:** [SEGURIDAD_API_KEY.md](SEGURIDAD_API_KEY.md)

---

**Última actualización:** 6 de Febrero, 2026  
**Bundle:** deploy-20260206-104533.zip  
**Versión:** eki-agentes-ia-20260206
