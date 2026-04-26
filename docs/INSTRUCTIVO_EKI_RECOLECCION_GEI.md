# Instructivo EKI: recolección de datos (Ficha GEI) y formularios en WhatsApp

Fecha: abril 2026

## Qué es

Algunos cursos configuran un **formulario secuencial** (sin RAG) que toma **preguntas de texto en WhatsApp** y guarda las respuestas en el modelo **Ficha GEI** (variables para cálculo de emisiones / módulo 5). El agente de formulario tiene **prioridad** sobre el bot educativo mientras haya una **sesión activa**.

## Manual para el equipo (admin web)

- Tras iniciar sesión en el **Admin de Django** abra el **Manual de Instrucciones eki**:
  - Ruta: `/admin/instrucciones/`
  - Sección dedicada: **Ficha GEI: recolección de datos por WhatsApp** (índice y detalle, versión 1.4+).

## Dónde se configura

- **Django admin → Formulario → Tipos de formulario**: asociar curso y módulo disparador, activo.
- **Pasos del flujo** (inline): orden, campo destino en `FichaGEI`, texto de pregunta, validaciones, opcional, reintento, etc.
- **Fichas GEI y sesiones** en sus respectivos menús; exportación a Excel de fichas en el admin de `FichaGEI`.

## Despliegue (EB)

1. Código con migraciones de `formulario` y, si aplica, `core` (ver runbook de deploy).
2. Tras publicar, ejecutar en el entorno: **`python manage.py migrate`** (incluido en el flujo de Beanstalk si el `.ebextensions` o Procfile lo definen; si no, migrar manualmente contra RDS).

Migraciones añadidas en este módulo (referencia; el número final puede variar según rama):

- `formulario.0001_initial` — tablas `FichaGEI`, `TipoFormulario`, `FlujoPregunta`, `SesionFormulario`
- Cualquier migración de `core` requerida por el grafo (p. ej. ajuste de `Curso` si se generó en `makemigrations` conjunto)

## Métricas disponibles

### Dashboard interno (staff)

- **Métricas** (`/admin/dashboard-metrics/`): sección *Recolección de datos (Ficha GEI — WhatsApp)* con:
  - fichas totales, fichas nuevas (30 días)
  - formularios en curso, formularios cerrados (30 días)
  - completitud promedio (7 campos, últimas 300 fichas con el filtro de empresa activo)
- Mismo cálculo respeta el filtro de **Empresa** del formulario.

### API JSON (staff, sesión de admin)

- Ruta: `GET /admin/analytics/api/?tipo=formulario_gei`
- Parámetros opcionales: `cliente_id=<id>` para acotar por organización.
- Respuesta: totales, recuentos 30 días, sesiones activas, completitud promedio, etc. (`schema: formulario_gei_v1`).

Para reportes con **todas las variables por fila**, usar la acción **exportar a Excel** en el admin de Fichas GEI.

## Documentos relacionados

- `docs/RUNBOOK_EB_MAIN.md` — despliegue y migraciones
- `docs/ROUTE_MAP_BY_DOMAIN.md` — rutas por dominio (si aplica al proxy)
