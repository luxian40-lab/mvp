# 🚨 DEBUG: Fallos de Deployment en Elastic Beanstalk

**Fecha:** 4 de Febrero 2026  
**Ambiente:** eki-prod-final (e-sapgrd4n6r)  
**Región:** us-east-2

---

## 📋 PROBLEMA PRINCIPAL

Todos los deployments fallan con el mismo error:
```
ERROR: Engine execution has encountered an error.
Command failed on instance. Return code: 1
Instance deployment: Your source bundle has issues that caused the deployment to fail.
```

**Resultado:** Siempre revierte a la versión anterior `app-s3-autodetect-final`

---

## 🔍 INVESTIGACIÓN REALIZADA

### 1️⃣ **PRIMER DESCUBRIMIENTO: Scripts Duplicados**

**Fecha:** 4 Feb 2026 - Primera sesión de debugging

**Hallazgo:**
- Encontramos que `collectstatic` se ejecutaba **3 VECES**:
  1. `.ebextensions/01_django.config` (container_commands)
  2. `.platform/hooks/postdeploy/01_migrate.sh`
  3. `.platform/hooks/postdeploy/99_migrate.sh` (DUPLICADO)

- `migrate` se ejecutaba **2 VECES**:
  1. `.platform/hooks/postdeploy/01_migrate.sh`
  2. `.platform/hooks/postdeploy/99_migrate.sh`

**Problemas detectados:**
- Sin manejo de errores en `01_migrate.sh` (faltaba `set -e`)
- Scripts ejecutándose simultáneamente causando conflictos
- Sin `ignoreErrors: false` en `.ebextensions` para propagar errores

---

### 2️⃣ **SOLUCIONES APLICADAS**

**Commit:** "Fix CRITICO: Eliminar scripts duplicados y collectstatic x3"

#### Cambios realizados:

**A) Eliminado `.platform/hooks/postdeploy/99_migrate.sh`**
```bash
# Archivo completamente eliminado (39 líneas)
# Era un duplicado con lógica condicional que causaba conflictos
```

**B) Modificado `.platform/hooks/postdeploy/01_migrate.sh`**
```bash
#!/bin/bash
set -e  # ✅ AÑADIDO: Para en errores

echo "=== POST-DEPLOY: Migraciones y Static Files ==="

source /var/app/venv/*/bin/activate
cd /var/app/current

echo "Ejecutando migraciones..."
python manage.py migrate --noinput || {
    echo "ERROR: Migraciones fallaron"
    exit 1  # ✅ AÑADIDO: Manejo explícito de errores
}

# ✅ ELIMINADO: python manage.py collectstatic --noinput
# (Se ejecuta solo en container_commands)

echo "Post-deploy completado (collectstatic se ejecuta en container_commands)"
```

**C) Modificado `.ebextensions/01_django.config`**
```yaml
container_commands:
  01_collectstatic:
    command: "source /var/app/venv/*/bin/activate && python manage.py collectstatic --noinput"
    leader_only: true
    ignoreErrors: false  # ✅ AÑADIDO: Propagar errores explícitamente
```

---

### 3️⃣ **PRIMER INTENTO DE DEPLOYMENT**

**Versión:** `app-fix-deployment-v2`  
**Fecha:** 4 Feb 2026 - 02:53 UTC

**Método utilizado:**
```powershell
# Creamos ZIP con Compress-Archive
Compress-Archive -Path * -DestinationPath app-fix-deployment-v2.zip -Force

# Subimos a S3
aws s3 cp app-fix-deployment-v2.zip s3://elasticbeanstalk-us-east-2-178773630934/eki-mvp/

# Creamos versión y deployamos
aws elasticbeanstalk create-application-version --application-name eki-mvp-python --version-label app-fix-deployment-v2 --source-bundle S3Bucket=...,S3Key=...
aws elasticbeanstalk update-environment --environment-name eki-prod-final --version-label app-fix-deployment-v2
```

**Resultado:** ❌ **FALLIDO**
```
Status: Ready
Health: Red
VersionLabel: app-s3-autodetect-final  # Revirtió a versión anterior
DateUpdated: 2026-02-05T02:54:18Z
```

**Error en eventos:**
```
ERROR: Engine execution has encountered an error.
ERROR: Instance deployment: Your source bundle has issues
ERROR: Command failed on instance. Return code: 1
```

---

### 4️⃣ **SEGUNDO DESCUBRIMIENTO: ZIP Incompleto**

**Análisis del ZIP creado:**
```powershell
# Verificamos contenido del ZIP app-fix-deployment-v2.zip
Add-Type -Assembly System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead("app-fix-deployment-v2.zip")
```

**Hallazgo CRÍTICO:**
```
❌ .platform/hooks/postdeploy/01_migrate.sh (NO EXISTE)
❌ .platform/hooks/postdeploy/99_migrate.sh (NO EXISTE)
❌ .ebextensions/01_django.config (NO EXISTE)
✅ requirements.txt (897 bytes)
✅ manage.py (689 bytes)
```

**Causa raíz:** `Compress-Archive` de PowerShell **NO incluye carpetas que empiezan con punto** (`.platform`, `.ebextensions`)

---

### 5️⃣ **SEGUNDO INTENTO: Git Archive**

**Método corregido:**
```powershell
# Usamos git archive que SÍ incluye carpetas ocultas
git archive --format=zip --output=app-fix-deployment-v3.zip HEAD
```

**Resultado del ZIP:**
```
✅ Tamaño: 1.5 GB (1,523,156,065 bytes)
✅ .platform/hooks/postdeploy/01_migrate.sh (489 bytes)
✅ .ebextensions/01_django.config (955 bytes)
✅ requirements.txt (897 bytes)
✅ manage.py (689 bytes)
✅ mvp_project/settings.py (17,982 bytes)
```

**Problema nuevo:** ⚠️ ZIP demasiado grande (1.5GB) por incluir archivos multimedia del proyecto

**Intentamos subir a S3:**
```powershell
aws s3 cp app-fix-deployment-v3.zip s3://elasticbeanstalk-us-east-2-178773630934/eki-mvp/
```

**Resultado:** ❌ Interrupciones manuales (Ctrl+C) - Muy lento / Timeout

---

## 🎯 ESTADO ACTUAL

### Archivos corregidos ✅
- ✅ `99_migrate.sh` eliminado
- ✅ `01_migrate.sh` con manejo de errores
- ✅ `.ebextensions/01_django.config` con `ignoreErrors: false`
- ✅ Commits aplicados en Git

### Problema actual ⚠️
- ❌ No hemos podido crear un ZIP válido que:
  1. Incluya `.platform` y `.ebextensions`
  2. Sea lo suficientemente pequeño para subir a S3
  3. Respete `.ebignore` para excluir archivos innecesarios

### Archivos a excluir (según .ebignore)
```
# Ya tenemos .ebignore configurado correctamente:
*.pyc, __pycache__/, db.sqlite3
venv/, .venv/, media/
*.mp4, *.mov, *.avi, *.pdf, *.jpg, *.png
backups/, logs/
*.bat, *.ps1, *.md (excepto README)
```

---

## 🔧 PRÓXIMOS PASOS

### Opción 1: Usar `eb deploy` (RECOMENDADO)
```bash
# eb deploy respeta automáticamente .ebignore
eb deploy eki-prod-final
```

**Ventajas:**
- ✅ Respeta `.ebignore` automáticamente
- ✅ Crea ZIP optimizado
- ✅ Maneja upload a S3
- ✅ Crea versión y despliega en un solo comando

### Opción 2: ZIP manual con exclusiones
```powershell
# Crear ZIP excluyendo directorios grandes
$exclude = @('media', 'staticfiles', 'venv', '.venv', 'backups', 'logs', '__pycache__')
# Necesitaríamos script custom para crear ZIP con exclusiones
```

### Opción 3: Limpiar archivos multimedia temporalmente
```powershell
# Mover media a backup temporal
Move-Item media media_backup
# Crear deployment
git archive --format=zip --output=app-fix-deployment-v4.zip HEAD
# Restaurar
Move-Item media_backup media
```

---

## 📊 HISTORIAL DE DEPLOYMENTS

| Versión | Fecha | Método | Resultado | Motivo Fallo |
|---------|-------|--------|-----------|--------------|
| app-diag-s3-v2 | ~ 4 Feb | Manual ZIP | ❌ Fallido | Scripts duplicados |
| app-diag-s3-v3 | ~ 4 Feb | Manual ZIP | ❌ Fallido | Scripts duplicados |
| app-produccion-final-v1 | ~ 4 Feb | Manual ZIP | ❌ Fallido | Scripts duplicados |
| app-fix-deployment-v2 | 4 Feb 02:53 | Compress-Archive | ❌ Fallido | ZIP sin .platform/.ebextensions |
| app-fix-deployment-v3 | 4 Feb 02:5x | git archive | ⏸️ No subido | ZIP 1.5GB muy grande |
| **app-s3-autodetect-final** | **Actual** | **Anterior** | ✅ **Funcionando** | **(Degraded pero estable)** |

---

## 🔑 LECCIONES APRENDIDAS

1. **Compress-Archive NO sirve** para Elastic Beanstalk (ignora carpetas con punto)
2. **git archive** incluye todo pero no respeta `.ebignore` (incluye archivos grandes)
3. **eb deploy** es la herramienta correcta para deployments (respeta .ebignore)
4. Los scripts de deployment **deben tener manejo de errores** (`set -e`, `|| { exit 1 }`)
5. `collectstatic` debe ejecutarse **solo una vez** (en container_commands)
6. La instancia actual está **Degraded** pero funcional con `app-s3-autodetect-final`

---

## 📝 COMANDOS ÚTILES PARA DEBUGGING

```powershell
# Ver estado actual
aws elasticbeanstalk describe-environments --environment-names eki-prod-final --region us-east-2

# Ver eventos recientes
aws elasticbeanstalk describe-events --environment-name eki-prod-final --region us-east-2 --max-items 10

# Solicitar logs completos
aws elasticbeanstalk request-environment-info --environment-name eki-prod-final --info-type tail --region us-east-2

# Descargar logs (esperar 15 seg después del request)
aws elasticbeanstalk retrieve-environment-info --environment-name eki-prod-final --info-type tail --region us-east-2

# Ver versiones disponibles
aws elasticbeanstalk describe-application-versions --application-name eki-mvp-python --region us-east-2

# Verificar contenido de ZIP
Add-Type -Assembly System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead("archivo.zip")
$zip.Entries | Select-Object FullName, Length
```

---

## 🎬 PRÓXIMA ACCIÓN RECOMENDADA

**Usar `eb deploy` para crear deployment correcto:**

```bash
# 1. Asegurarnos que .ebignore está correcto (YA LO ESTÁ ✅)
cat .ebignore

# 2. Verificar que estamos en la rama correcta
git status

# 3. Desplegar usando eb CLI
eb deploy eki-prod-final

# 4. Monitorear
eb status eki-prod-final
eb logs eki-prod-final
```

**Alternativa si `eb` no funciona:**
Crear ZIP manualmente excluyendo carpetas grandes y subirlo con AWS CLI.

---

## ✅ SOLUCIÓN FINAL (5 Feb 2026)

### Deployment Exitoso

**Comando usado:**
```powershell
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe deploy eki-prod-final
```

**Resultado:**
```
✅ Uploading: [##################################################] 100%
✅ 2026-02-05 16:10:10    INFO    Environment update completed successfully
✅ Status: Ready
✅ Health: Green
✅ Version: app-be21-260205_110537057227
```

**Estado Final:**
- 🟢 **Health: Green**
- ✅ **Status: Ready**
- 🎥 **Multimedia funcionando** en producción
- 📦 **ZIP respetó .ebignore** correctamente

**URL Producción:** `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com`

---

**Generado:** 4 de Febrero 2026  
**Por:** GitHub Copilot (Claude Sonnet 4.5)  
**Propósito:** Documentar fallos de deployment para referencia futura
