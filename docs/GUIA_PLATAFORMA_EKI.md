# Guía completa de la plataforma eki

Documento de referencia para el equipo: **qué hace el producto**, **cómo se conectan las piezas** y **cómo operar** admin, portal, aula y WhatsApp.

Última actualización: junio 2026 · producción en `eki-prod-final` (Elastic Beanstalk).

---

## 1. Qué es eki

eki es una **plataforma de formación** orientada a programas B2B (organizaciones, cooperativas, proyectos de empleabilidad). El canal principal es **WhatsApp**: el estudiante recibe lecciones, evaluaciones y multimedia en conversación, avanza con la palabra **listo** y puede obtener certificados.

Sobre el mismo núcleo de datos existen tres superficies web:

| Superficie | URL | Quién entra | Para qué |
|------------|-----|-------------|----------|
| **Admin operaciones** | [admin.eki.technology](https://admin.eki.technology) | Staff eki (Django) | Cursos, módulos, drip, campañas, estudiantes, certificados |
| **Portal B2B** | [app.eki.technology](https://app.eki.technology) | Coordinadores del cliente | Métricas, campañas, empleabilidad, branding |
| **Aula virtual** | [aprende.eki.technology](https://aprende.eki.technology) | Estudiantes y docentes | Consultar material, tareas, perfil y biblioteca |

Todo vive en un **monolito Django** desplegado en AWS (EB + RDS PostgreSQL + S3 + Redis/Celery).

---

## 2. Modelo mental: un solo contenido, varios canales

```
Admin configura Curso → Módulos → Secciones → Microcontenidos (pasos)
                              ↘ Archivos multimedia (ArchivoModulo)
                                    ↓
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
         WhatsApp              Aula virtual          Portal (métricas)
    (entrega progresiva)    (consulta en línea)    (reportes agregados)
```

- **Curso** (`core.Curso`): programa formativo; pertenece a un `Cliente` (organización) o es general.
- **Módulo** (`core.Modulo`): unidad didáctica numerada (0 = bienvenida, 1, 2, 3…).
- **Sección** (`core.SeccionModulo`): bloque dentro del módulo; en WhatsApp cada sección se libera con un **listo**.
- **Paso / microcontenido** (`core.PasoModulo`): texto + URL o archivo multimedia; puede ser contenido, evaluación, reto o entrega.
- **Archivo multimedia** (`core.ArchivoModulo`): video, PDF, imagen o audio adjunto al módulo (además de los pasos).

El estudiante **no ve en el aula más de lo que el drip y su avance permiten** (misma lógica que WhatsApp).

---

## 3. Flujo del estudiante por WhatsApp

### 3.1 Onboarding B2B

1. Mensaje inicial → aceptación de datos (Habeas Data).
2. Validación por **cédula + teléfono** (2FA ligero).
3. Confirmación o corrección de datos personales.
4. Asignación a organización (`Cliente`) y curso según **campaña** o selección.

Estados en `Estudiante.estado_chat` (máquina de estados en `core/models.py`).

### 3.2 Avance en el curso

- El estudiante escribe **listo** para recibir el siguiente bloque de contenido.
- Si el módulo tiene **microcontenidos**, cada *listo* entrega una **sección** (varios pasos seguidos hasta una evaluación).
- Si no hay microcontenidos, se envía el **contenido completo** del módulo + multimedia de `ArchivoModulo`.
- Las **evaluaciones** (opciones A–D, abiertas, retos) se responden en chat; la gamificación registra puntos o notas según el modo del cliente.

Lógica principal: `core/module_steps.py`, `core/response_templates.py`, `core/views.py` (webhook Twilio).

### 3.3 Drip (liberación en el tiempo)

El **drip** controla **cuándo** se puede avanzar:

| Mecanismo | Dónde se configura | Efecto |
|-----------|-------------------|--------|
| Días entre módulos | Curso / `ConfiguracionDripCliente` | Tras completar M1, espera N días antes de M2 |
| Fecha `habilitado_desde` | Módulo o `HabilitacionModuloDripCliente` | El módulo no abre hasta esa fecha |
| Lista blanca por estudiante | `HabilitacionModuloEstudiante` | Solo estudiantes listados ven ciertos módulos |

Código: `core/drip_schedule.py`.  
En el **aula**, `aprende/acceso_modulos.py` aplica las mismas reglas: solo aparecen módulos liberados.

### 3.4 Campañas B2B (sin menú 1-2-3)

En campañas corporativas el estudiante **no elige curso con menú numérico**. El orden lo define `Campana.curso_destino` y el avance es lineal con **listo**.

Código: `core/flujo_whatsapp_b2b.py` integrado en `core/views.py` y plantillas de respuesta.

---

## 4. Aula virtual (`/aprende/`)

### 4.1 Acceso

| Rol | Login | Credenciales |
|-----|-------|--------------|
| Estudiante | `/aprende/estudiante/login/` | Cédula + teléfono WhatsApp (mismos del programa) |
| Docente | `/aprende/profesor/login/` | Usuario del portal con rol `profesor` o `admin` |

Sesión estudiante: cookie de sesión Django (`APRENDE_EST_SESSION_KEY`).

### 4.2 Qué ve el estudiante

1. **Mis cursos** — progreso e inscripción en catálogo (`visible_en_aula=True`).
2. **Módulo** — contenido didáctico:
   - Texto introductorio del módulo (si existe).
   - **Secciones y pasos** configurados en admin (microcontenidos).
   - Video del módulo, PDF y **archivos multimedia** (`ArchivoModulo`).
   - **Solo consulta en línea**: reproductores embebidos (video, audio, imagen, PDF en iframe). Sin enlaces de descarga del material del curso.
3. **Tareas** — entregas calificadas por el docente (1–5).
4. **Biblioteca** — todo el multimedia de módulos ya liberados, agrupado por curso (también solo visualización).
5. **Mi perfil** — datos personales, foto, puntos/nivel (gamificación), subida de documentos propios.

### 4.3 Drip en el aula

`modulos_visibles_aula()` filtra:

- Calendario / lista blanca (`modulo_disponible_por_calendario`).
- Avance lineal (no muestra módulos futuros).
- Bloqueo entre módulos si el anterior está completo y aún corre el drip (`drip_bloquea_siguiente_modulo`).

### 4.4 Qué sube el docente hoy

- Desde **admin Django** (`core/admin/cursos.py`): módulos, secciones, pasos, archivos multimedia (origen principal del contenido que llega por WhatsApp).
- Desde **aula profesor** (`aprende/lesson_service.py`): lecciones simplificadas y archivos para pruebas rápidas.

### 4.5 Archivos relevantes del aula

| Archivo | Función |
|---------|---------|
| `aprende/views.py` | Rutas estudiante/docente |
| `aprende/acceso_modulos.py` | Drip y visibilidad de módulos |
| `aprende/contenido_modulo_service.py` | Arma secciones/pasos para la plantilla |
| `aprende/media_aula.py` | Tipo de media (video, PDF, YouTube…) |
| `aprende/partials/media_viewer.html` | Visor embebido sin descarga |
| `aprende/perfil_service.py` | Perfil y gamificación |
| `aprende/documento_service.py` | Documentos que sube el estudiante |

---

## 5. Portal B2B (`portal/`)

Los coordinadores de cada `Cliente` entran con usuario/contraseña del portal.

**Capacidades** (según producto contratado en `Cliente.portal_productos`):

- Dashboard y métricas de avance.
- Campañas y segmentos.
- Empleabilidad (códigos geo, métricas).
- Branding (logo, subtítulo).
- Exportaciones y reportes.

Código: `portal/views.py`, `portal/capabilities.py`, `portal/branding.py`.

---

## 6. Admin operaciones (`core/admin/`)

El admin Django (Jazzmin) fue reorganizado en paquete `core/admin/`:

| Módulo admin | Gestiona |
|--------------|----------|
| `clientes.py` | Organizaciones B2B, drip, gamificación |
| `cursos.py` | Cursos, módulos, secciones, pasos, archivos |
| `estudiantes.py` | Estudiantes, progreso, envíos |
| `campanas.py` | Campañas WhatsApp |
| `certificados.py` | Plantillas y envío |
| `grupos.py` | Grupos de estudiantes, archivos módulo |
| `gamificacion.py` | Puntos, badges, ranking |

**Hub aula:** `/admin/aula-web/` — vista operativa para publicar cursos en el catálogo del aula.

**Atajo grupos:** enlace directo a `GrupoEstudiantes` desde el índice admin.

---

## 7. Gamificación

Modos por organización (`Cliente.modo_gamificacion`):

- **Puntos** — ranking por `PerfilGamificacion.puntos_totales`.
- **Calificación 1–5** — promedio ponderado de evaluaciones.
- **Desactivada**.

El estudiante consulta su estado en **Mi perfil** del aula. La lógica vive en `core/gamificacion.py` y `core/gamificacion_modo.py`.

---

## 8. Certificados y formularios externos

- Generación PDF: `core/certificado_service.py`, `core/certificado_presencial_service.py`.
- Envío masivo: vistas admin de certificados + Twilio.
- Enlaces a formularios externos (empleabilidad, validación): `core/form_externo_service.py`, modelo `EnlaceFormularioExterno`.

---

## 9. Infraestructura y deploy

| Componente | Detalle |
|------------|---------|
| Hosting | AWS Elastic Beanstalk `eki-prod-final` |
| Base de datos | PostgreSQL RDS (`DATABASE_URL`) |
| Archivos | S3 `eki-produccion` (media estudiantes, videos, PDFs) |
| Cola | Celery + Redis en EB (mensajes programados, certificados, drip) |
| DNS | Cloudflare → `admin`, `app`, `aprende` |

**Deploy:**

```powershell
.\scripts\eb_precheck_main.ps1
.\scripts\eb_deploy_main.ps1
```

Las migraciones corren en `.platform/hooks/predeploy/02_migrate.sh`.

**Smoke tests:**

```text
https://admin.eki.technology/health/     → 200
https://aprende.eki.technology/aprende/  → 200
https://app.eki.technology/portal/login/ → 200
```

Checklist detallado: `docs/CHECKLIST_PRE_DEPLOY.md`.  
Auditoría técnica profunda: `docs/AUDITORIA_ARQUITECTURA_EKI.md`.

---

## 10. Cómo configurar contenido para que se vea en el aula

### Paso a paso (recomendado)

1. En **Admin → Cursos → Módulo**, pestaña **Secciones**: crear sección 1, 2, 3…
2. En **Microcontenidos** (inline): por cada paso, completar **Contenido** y opcionalmente **Media URL** o subir archivo (`media_file_upload` → guarda en S3 y llena `media_url`).
3. En **Archivos multimedia** del módulo: agregar PDFs, videos o imágenes adicionales.
4. Opcional: video principal del módulo en campos `video_url` / `video_archivo`.
5. Marcar curso **Visible en aula** si debe aparecer en catálogo.
6. Verificar **drip** (fechas y días entre módulos) para que el estudiante de prueba tenga el módulo liberado.

### Comportamiento en el aula

- Se listan **secciones** con sus **pasos** en orden.
- Cada multimedia se muestra en **visor embebido** (no botón “Descargar”).
- Los documentos que **sube el estudiante** (entregas propias) sí pueden descargarse desde su lista de entregas; es material del estudiante, no del curso.

### Limitación conocida

Las URLs directas de S3 pueden copiarse manualmente por un usuario avanzado. Para protección fuerte haría falta un **proxy de streaming** con URLs firmadas de corta duración (mejora futura P2).

---

## 11. Pruebas locales

```bash
python manage.py check
python manage.py test aprende.tests core.tests_flujo_whatsapp_b2b -v 1
```

Número de prueba equipo: **3026480629** (WA: `573026480629`).

---

## 12. Mapa rápido de cambios recientes (junio 2026)

| Tema | Estado |
|------|--------|
| Aula diseño académico (tipografía, morado institucional) | Producción |
| Drip en listado de módulos del aula | Producción |
| Perfil estudiante (foto, puntos, datos) | Producción + migración `0114` |
| Documentos del estudiante en aula | Producción + `DocumentoEstudianteAula` |
| Biblioteca multimedia por drip | Producción |
| Secciones/microcontenidos visibles solo consulta | Este documento / despliegue pendiente |
| WhatsApp B2B sin menú 1-2-3 | Producción |
| Admin dividido en `core/admin/` | Producción |

---

## 13. Contacto operativo

- **Rollback EB:** `eb deploy eki-prod-final --version <versión_anterior>`
- **Logs:** consola EB o `eb logs eki-prod-final`
- **Health:** `/health/` en cualquier dominio del entorno

---

*Documento mantenido por el equipo de producto eki. Para detalle de deuda técnica y seguridad, ver `docs/AUDITORIA_ARQUITECTURA_EKI.md`.*
