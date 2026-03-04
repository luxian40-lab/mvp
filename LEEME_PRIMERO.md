# LO QUE HICE PARA TI - DEPLOYMENT AWS

## TU PREGUNTA:
"Elastic Beanstalk o App Runner? Quiero que todo funcione bien y que las variables de entorno se transfieran correctamente. Habia problemas con BOM tambien."

## MI RESPUESTA:

### USA ELASTIC BEANSTALK

Por que?
- Ya tienes 70% configurado
- Mas control
- Costos similares (~$50/mes)
- Facil escalar despues

## LO QUE HICE:

### 1. Limpie BOM
- [x] Creado script: `scripts/verification/verificar_bom.py`
- [x] Removido BOM de 2 archivos
- [x] Ahora se verifica automaticamente en cada deploy

### 2. Configure Elastic Beanstalk
- [x] `.ebextensions/01_django.config` - Limpio
- [x] `.ebextensions/02_migrate.config` - Migraciones auto
- [x] `.ebextensions/03_instance.config` - Instancia t3.small
- [x] Todo sin emojis ni basura

### 3. Scripts de Deploy
- [x] `deploy_eb.sh` - Deploy completo automatizado
- [x] `configure_eb_env.sh` - Configura variables en AWS
- [x] `scripts/verification/verificar_aws_ready.py` - Verifica que todo este listo

### 4. Documentacion
- [x] `AWS_DEPLOYMENT_DECISION.md` - Por que EB
- [x] `GUIA_DEPLOYMENT_EB.md` - Guia completa paso a paso
- [x] `RESUMEN_EJECUTIVO_AWS.md` - Resumen ejecutivo

## COMO FUNCIONAN LAS VARIABLES DE ENTORNO:

### NO VAN EN GIT:
- `.env.production` esta en tu maquina (gitignored)
- NUNCA subes credenciales a git

### VAN A AWS:
```bash
# Tu ejecutas:
bash configure_eb_env.sh

# Script lee .env.production y ejecuta:
eb setenv SECRET_KEY=xxx DATABASE_URL=xxx TWILIO_SID=xxx ...

# Variables quedan en AWS
# En el deploy, EB las inyecta al container
# Django las lee via os.environ
```

### SEGURO Y FACIL:
1. Completas `.env.production` en tu maquina
2. Ejecutas `configure_eb_env.sh`
3. Variables quedan en AWS
4. Deploy y listo!

## LO QUE TIENES QUE HACER:

### 1. Instalar EB CLI
```bash
pip install awsebcli
```

### 2. Completar .env.production
Ya tienes el template, solo llena los XXX con tus valores reales

### 3. Inicializar EB (si no lo has hecho)
```bash
eb init
# Selecciona: us-east-2, Docker platform
```

### 4. Configurar Variables
```bash
bash configure_eb_env.sh
```

### 5. Deploy!
```bash
bash deploy_eb.sh
```

## RESUMEN DE ARCHIVOS CREADOS:

### Scripts:
- `deploy_eb.sh` - Deploy automatizado
- `configure_eb_env.sh` - Config variables
- `scripts/verification/verificar_bom.py` - Verifica BOM
- `scripts/verification/verificar_aws_ready.py` - Verifica pre-deploy

### Configs:
- `.ebextensions/01_django.config` - Settings Django
- `.ebextensions/02_migrate.config` - Migraciones
- `.ebextensions/03_instance.config` - Instancia config

### Docs:
- `AWS_DEPLOYMENT_DECISION.md` - Decision EB vs App Runner
- `GUIA_DEPLOYMENT_EB.md` - Guia completa
- `RESUMEN_EJECUTIVO_AWS.md` - Resumen ejecutivo
- `ESTE_ARCHIVO.md` - Resumen simple

## STATUS ACTUAL:

### Completado:
- [x] BOM limpiado
- [x] Scripts de deploy creados
- [x] Configs EB actualizadas
- [x] Documentacion completa
- [x] AWS credentials configuradas (verificado)

### Pendiente (tu trabajo):
- [ ] Instalar EB CLI (`pip install awsebcli`)
- [ ] Iniciar Docker Desktop
- [ ] Completar .env.production
- [ ] Ejecutar `eb init`
- [ ] Ejecutar `bash configure_eb_env.sh`
- [ ] Ejecutar `bash deploy_eb.sh`

## COMANDOS RAPIDOS:

```bash
# Instalar EB CLI
pip install awsebcli

# Inicializar EB
eb init

# Configurar variables
bash configure_eb_env.sh

# Deploy
bash deploy_eb.sh

# Ver logs
eb logs -f

# Abrir app
eb open
```

## SI TIENES PROBLEMAS:

1. Lee: `GUIA_DEPLOYMENT_EB.md`
2. Ejecuta: `python scripts/verification/verificar_aws_ready.py`
3. Ve logs: `eb logs -f`

## CONCLUSION:

**TODO ESTA LISTO.**

Solo necesitas:
1. Instalar EB CLI
2. Completar .env.production
3. Ejecutar 3 comandos

**Las variables de entorno se transfieren automaticamente y de forma segura a AWS.**
**Los problemas de BOM estan resueltos.**
**Todo el deployment esta automatizado.**

**Un solo comando y tu app esta en produccion!**

---

## CAMBIOS RECIENTES (Sesion Marzo 4, 2026)

### 1. Plantillas Twilio Actualizadas
- **Habeas Data**: SID actualizado a `HX579c4e36ab20209afa55742f6e3c0c55`
- **Verificacion datos**: SID actualizado a `HX180afd8c7cf5266799921abf523c80f6`
  - Ahora envía 5 variables: Nombre, Cédula, Organización, Edad, Municipio
  - Función `enviar_confirmacion_datos()` actualizada con params `edad` y `municipio`

### 2. Selección de Cursos
- Estudiantes ahora escriben "tomar 1" (o "tomar 2", etc.) para seleccionar curso
- También acepta solo el número como antes
- Regex: `r'^tomar\s*(\d+)$'`

### 3. Certificados con Marcadores RGB (PNG)
- **Plantilla**: `certificadoeki.png` en S3 (PNG lossless, no JPEG)
- **5 marcadores de color** en la plantilla:
  - Magenta (255,0,255) → Nombre del estudiante
  - Rojo (255,0,0) → Cédula
  - Azul (0,0,255) → Código QR
  - Verde (0,255,0) → Nombre de la empresa
  - Naranja (255,128,0) → Logo/texto Eki
- **Tolerancia 0** (solo coincidencia exacta de color)
- **BytesIO**: Certificados se generan en memoria, nunca tocan disco
- **S3**: Se suben directamente a `s3://eki-produccion/certificados/{org}/{cedula}_{curso_id}.png`
- **URL en S3**: `https://eki-produccion.s3.us-east-2.amazonaws.com/pruebas/certificadoeki.png`

### 4. PostgreSQL RDS
- **settings.py**: Parsea `DATABASE_URL` como fallback cuando `DB_*` vars no existen
- **settings_production.py**: Mismo fallback de `DATABASE_URL`
- **Fallback local**: Si RDS no accesible (timeout 3s), usa SQLite automáticamente
- **En EB**: Variables `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` ya configuradas
- **psycopg**: Requiere `psycopg2-binary` en EB (Python 3.11). Local con Python 3.14 usa `psycopg[binary]` v3

### 5. Celery Sincrónico
- `CELERY_TASK_ALWAYS_EAGER=True` configurado en EB
- Tareas se ejecutan síncronamente sin necesidad de Redis
- Cuando se agregue Redis, cambiar a `False` para procesamiento async real

### 6. Optimizacion select_related (N+1 eliminado)
- **Dashboard estudiantes**: Pre-carga progresos y gamificación con `prefetch` (antes: ~1000 queries por 200 estudiantes, ahora: ~4 queries)
- **Conversaciones**: Usa `annotate(Count, Max)` para conteos y fechas (antes: ~4N queries, ahora: 1 query principal + 2N para últimos mensajes)
- **Webhook**: `Estudiante.objects.select_related('cliente')` ya estaba implementado

### 7. Fix Encoding Windows
- Emojis en `settings.py` reemplazados por ASCII (`[OK]`/`[WARN]`) para evitar `UnicodeEncodeError: 'charmap'` en Windows cp1252

### 8. Twilio Auth Token
- Actualizado a `7f09068820cfd46eed5c7355aece8e40` en `.env` y `.env.production`
- **NUNCA** va en git (`.gitignore` protege `.env*`)

### 9. Deploy Exitoso
- Branch: `fresh-push-3` pusheado y desplegado a `eki-prod-final`
- Health: `Ok` (Green), 0 errores
- Variables EB actualizadas: `CELERY_TASK_ALWAYS_EAGER=True`, `ELASTIC_BEANSTALK=true`

---

## CAMBIOS ANTERIORES

### 1. Campo Edad en Estudiantes
- Se agrego campo `edad` (numerico) al modelo Estudiante
- `rango_edad` se calcula automaticamente desde la edad (18-30, 31-50, 50+)
- Visible en admin (listado y formulario de edicion)
- Incluido en plantilla de importacion Excel (columna G)
- El flujo de onboarding por WhatsApp ahora muestra edad y genero en la confirmacion
- Los estudiantes pueden corregir campo por campo (nombre, municipio, departamento, documento, edad, genero) escribiendo `campo: valor`

### 2. PQRS y Soporte Unificados
- Las solicitudes de soporte ahora incluyen tipos PQRS (Peticion, Queja, Reclamo, Sugerencia, Felicitacion)
- Una sola vista en admin: "Solicitudes de Soporte y PQRS"
- Panel de estadisticas unificado con conteos por tipo
- PQRS antiguo oculto del sidebar (datos preservados)

### 3. Celery + Redis (Procesamiento Asincrono)
- **Instalado**: celery 5.4.0, redis 5.2.1
- **Archivo de configuracion**: `mvp_project/celery.py`
- **Tareas definidas** en `core/tasks.py`:
  - `procesar_respuesta_estudiante` - Procesa mensajes de WhatsApp async
  - `generar_certificado_async` - Genera certificados PDF en background
  - `actualizar_gamificacion_async` - Actualiza puntos/niveles
  - `enviar_notificacion_async` - Envia mensajes WhatsApp
  - `enviar_archivo_modulo_async` - Envia archivos multimedia
  - `enviar_campanas_programadas` - Cada 5 min busca campanas pendientes
  - `ejecutar_campana_async` - Ejecuta una campana individual
  - `generar_reporte_actividad` - Reporte cada hora
  - `limpiar_logs_antiguos` - Limpia mensajes > 90 dias (2 AM)
  - `enviar_email_org_admin_async` - Emails a admins de organizacion
- **Procfile**: Incluye lineas para `worker` y `beat`
- **Fallback**: Si Redis no esta disponible, todo funciona sincronamente
- **Variables de entorno requeridas**:
  - `CELERY_BROKER_URL` (default: redis://localhost:6379/0)
  - `CELERY_RESULT_BACKEND` (default: redis://localhost:6379/0)
  - `CELERY_TASK_ALWAYS_EAGER=True` para ejecutar sync sin Redis

### Como ejecutar Celery en local:
```bash
# Terminal 1: Redis (o usar Docker)
docker run -p 6379:6379 redis

# Terminal 2: Worker
celery -A mvp_project worker --loglevel=info

# Terminal 3: Beat (tareas programadas)
celery -A mvp_project beat --loglevel=info

# Terminal 4: Django
python manage.py runserver
```

### Sin Redis (desarrollo rapido):
Agregar a `.env`:
```
CELERY_TASK_ALWAYS_EAGER=True
```
Las tareas se ejecutaran sincronamente sin necesidad de Redis.

### 4. RAG Multi-Tenant — Base de Conocimiento para Agentes IA

**ARQUITECTURA:**
```
Compañia 1 (Eki)                    Compañia 2 (Cooperativa)
├─ Curso: Tomates                   ├─ Curso: Maiz
│  ├─ manual_tomates.pdf   ← AISLADO│  ├─ manual_maiz.pdf     ← AISLADO
│  └─ ChromaDB propio              │  └─ ChromaDB propio
└─ Curso: Café                     └─ Curso: Ganadería
   ├─ manual_cafe.pdf      ← AISLADO   ├─ manual_ganaderia.pdf ← AISLADO
   └─ ChromaDB propio                  └─ ChromaDB propio
```

**REGLA DE ORO:** Compañia A NO puede ver documentos de Compañia B. Curso 1 NO puede ver documentos de Curso 2. Aislamiento total.

**Archivos creados:**
- `core/rag_eki_multitenant.py` — Motor RAG con ChromaDB (procesamiento, busqueda, respuestas)
- `core/rag_manager.py` — Singleton manager con cache de instancias RAG
- Modelo `DocumentoRAG` en `core/models.py` — Trackea documentos subidos (curso, tipo, estado, chunks)
- Admin integrado en `CursoAdmin` como inline + `DocumentoRAGAdmin` standalone

**Como funciona:**
1. Admin sube PDF/DOCX/TXT en el admin de Curso (inline "Documentos RAG")
2. El sistema extrae texto, lo divide en chunks y lo indexa en ChromaDB
3. Cuando un estudiante pregunta algo, los agentes (Geronimo, Maria, IA Assistant):
   - Detectan el cliente_id y curso_id del estudiante
   - Buscan documentos relevantes SOLO en ese cliente+curso
   - Inyectan el contexto en el prompt de OpenAI
   - Responden con información del material del curso

**Acciones admin disponibles:**
- "Indexar documentos RAG" — Indexa documentos pendientes
- "Indexar contenido de modulos en RAG" — Indexa el texto de los modulos como documentos
- "Re-indexar" — Fuerza re-procesamiento
- "Eliminar del RAG" — Quita del indice sin borrar archivo

**Integracion con agentes IA:**
- `ai_assistant.py` (responder_con_ia) — Inyecta contexto RAG automaticamente
- `tutor_ia_modulo.py` (generar_enseñanza_modulo) — Geronimo usa docs del curso
- `tutor_ia_modulo.py` (evaluar_respuesta_modulo) — Evaluacion con contexto RAG

**Estructura de archivos ChromaDB:**
```
chroma_db/
├── cliente_1/
│   ├── curso_1/chroma.sqlite3   ← Aislado
│   └── curso_2/chroma.sqlite3   ← Aislado
├── cliente_2/
│   └── curso_1/chroma.sqlite3   ← Aislado
└── (auto-creado al subir docs)
```

**Requisitos produccion:**
- `chromadb>=1.0.0` en requirements.txt (ya incluido)
- Python 3.11+ (EB usa 3.11, compatible)
- Sin dependencias externas adicionales (ChromaDB usa SQLite internamente)
