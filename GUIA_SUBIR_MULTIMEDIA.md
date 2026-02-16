# 🎬 GUÍA: Cómo Subir Videos e Imágenes para WhatsApp

## ❌ Problema Actual
Los registros de ArchivoModulo existen en la base de datos:
- "video bienvenida" (Módulo 0.00)
- "pruebas" (Módulo 0.10)

**PERO NO TIENEN ARCHIVOS SUBIDOS** → Por eso aparecen líneas negras en WhatsApp.

## ✅ Solución: Subir Archivos via Admin

### Paso 1: Acceder al Admin
```
URL: https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/admin
Usuario: Tu usuario admin
```

### Paso 2: Ir a Archivos Multimedia
```
Admin → Core → 📁 Archivos Multimedia
```

### Paso 3: Editar "video bienvenida"
1. Click en **"video bienvenida"**
2. Busca la sección **"Archivo"** (primera sección)
3. Verás: `Actualmente: (ninguno)`
4. Click en **"Elegir archivo"**
5. Selecciona tu video desde el PC (ej: `bienvenida.mp4`)
6. Click **"Guardar"**

### Paso 4: Editar "pruebas"
1. Click en **"pruebas"**
2. Busca la sección **"Archivo"**
3. Click **"Elegir archivo"**
4. Selecciona tu imagen desde el PC (ej: `pruebas.jpg`)
5. Click **"Guardar"**

## 🚀 ¿Qué Pasa Automáticamente?

### Cuando Guardas:
```
1. Django sube archivo → S3 bucket: eki-produccion
2. Ruta en S3: media/modulos/2026/02/bienvenida.mp4
3. URL generada: https://eki-produccion.s3.amazonaws.com/media/modulos/2026/02/bienvenida.mp4
4. Archivo es PÚBLICO (gracias a AWS_DEFAULT_ACL = 'public-read')
```

### Cuando Usuario Pide "continuar":
```python
# views.py hace esto automáticamente:
if archivo.archivo:  # ✅ Ahora tiene archivo
    url = archivo.archivo.url  # Django genera URL de S3
    # Envía a WhatsApp con la URL
```

## 🎯 NO Necesitas:
- ❌ Subir archivos manualmente a S3
- ❌ Configurar URLs públicas tú mismo
- ❌ Copiar URLs de S3
- ❌ Usar campo "url_externa"

## ✅ Solo Necesitas:
- ✅ Admin Django → Archivos Multimedia → Elegir archivo → Guardar
- ✅ Django hace TODO automáticamente

## 🧪 Probar:
Después de subir archivos:
1. WhatsApp → Escribe "continuar"
2. Deberías ver:
   - Módulo 0.00: VIDEO de bienvenida (reproducible)
   - Módulo 0.10: IMAGEN de pruebas (visible)

## ⚠️ Si Sigue Sin Verse:
Verifica en Admin que el archivo dice:
```
Actualmente: modulos/2026/02/bienvenida.mp4
```

Si dice "Actualmente: (ninguno)" → Archivo NO está subido.
