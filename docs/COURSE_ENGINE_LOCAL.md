# Course Engine — manual ops + costos (prod)

**Estado (2026-08-29):** pipeline validado en prod (admin curso, voces, Runway, MP4 S3). Rama `feat/course-engine` desplegada en `eki-prod-final`.

**Curso mixto (10 módulos, video + infografía + podcast + RAG):** ver [`COURSE_ENGINE_CURSO_MIXTO.md`](COURSE_ENGINE_CURSO_MIXTO.md).

## Microcontenidos — qué dejar en el manual

En eki hay **dos sentidos** de microcontenido:

| Tipo | Qué es | Dónde vive |
|------|--------|------------|
| **PasoModulo (WA)** | Texto + media que el estudiante recibe con *listo* | Admin → Módulo → Estructura / Module Builder |
| **Video Course Engine** | MP4 corto (~20–50 s) generado por IA (lección → storyboard → assets) | S3 `media/course_engine/videos/<run_id>.mp4` |

**Flujo manual recomendado (hoy):**

1. **Curso** → pestaña *Course Engine (video IA)* → tier + voz default.
2. **Módulo** → override tier/voz si hace falta (vacío = hereda curso).
3. **QA voz** → *Escuchar muestra (~5 s)* — solo al configurar; cada clic consume ElevenLabs.
4. **Generar video** (CLI hoy; botón admin + Celery en slice futuro):
   ```powershell
   python manage.py course_engine_generate_video ^
     --cliente-id 1 --curso-id 22 --modulo-id 45 ^
     --tier premium
   ```
   Con `--modulo-id` el brief sale del título/descripción del módulo y hereda tier/voz.
5. **Publicar como microcontenido WA:** copiar URL S3 del MP4 al **PasoModulo** correspondiente (campo media / URL) o subir el archivo en la pestaña Clase. Mismo criterio que cualquier video de módulo: HTTPS público, ≤16 MB para WhatsApp.
6. **Checklist antes de publicar módulo:** contenido OK, media accesible, drip, voz coherente con marca del cliente.

**Regla ops:** no generar video en lote sin QA humano del MP4. Un run = un microcontenido candidato.

### Tiers (curso y módulo)

| Tier | Duración aprox. | Runway | Tope costo est. (código) | Cuándo usar |
|------|-----------------|--------|--------------------------|-------------|
| **economico** | 20–30 s | No | ~$2 | Contenido masivo, sin clip animado |
| **estandar** | 25–35 s | 1 clip (~4 s) | ~$5 | Balance costo / impacto visual |
| **premium** | 35–50 s | hasta 3 clips | ~$15 | Demos, clientes B2B, piezas estrella |

### Voces (catálogo eki)

Maria, Sofia, Carlos, Andrés — dropdown en admin. Default global: `ELEVENLABS_VOICE_ID` en EB. Clon cliente: pegar Voice ID de ElevenLabs en curso/módulo.

---

## Costos — qué cobra y qué no

### Gratis (sin llamada API)

- Abrir/guardar curso o módulo en admin.
- Elegir tier, voz, tier por módulo.
- Variables EB configuradas (keys sin uso).

### Cobra al usar

| Acción | Proveedor | Orden de magnitud |
|--------|-----------|-------------------|
| Escuchar muestra (~5 s) | ElevenLabs | Centavos por clic |
| Links «Probar catálogo» (×4 voces) | ElevenLabs | 1 llamada por voz y clic |
| Storyboard + lección | OpenAI (gpt-4o-mini) | ~$0.02 por video |
| Imagen por escena | OpenAI (gpt-image-1) | ~$0.04 × N escenas |
| Narración por escena | ElevenLabs | ~$0.15 / 1 000 caracteres de guion |
| Clip Runway (4 s, gen4_turbo) | Runway | ~$0.20 por clip (estimado interno) |

**Estimados por corrida completa (referencia real aug-2026):**

| Run | Tema | Tier | Costo est. | Notas |
|-----|------|------|------------|-------|
| `005f1a665318` | Aguacate Hass | premium | ~$0.56 | 1 Runway |
| `6681ef74059c` | Cacao fino | premium | ~$0.47 | 1 Runway, contexto mejorado |

Los topes en `budget.py` evitan desbordes; Runway solo en tier estándar/premium.

### A futuro — control de costos a escala

Cuando haya **muchas generaciones / mes**, revisar:

1. **Dashboard** — modelos `CourseGenerationRun` (slice pendiente): run_id, tier, costo_est, costo_real, cliente, curso, módulo.
2. **Presupuesto por cliente** — tope mensual USD en contrato B2B antes de habilitar tier premium.
3. **Caché TTS** — misma voz + mismo texto = no repetir ElevenLabs (muestras QA).
4. **Batch nocturno** — Celery con cola y límite de concurrencia Runway (evita picos de créditos).
5. **Alertas** — si costo_real > tope tier o fallos Runway > N %, aviso Ops.

Hasta entonces: registrar manualmente run_id + URL S3 en hoja de control del curso o ticket interno.

---

## Contexto Runway e imágenes (fix 2026-08-29)

Problemas resueltos en prod:

- Prompts con **lección + brief + guion** (`prompt_context.py`) — Runway ya no “inventa” agricultura genérica.
- Escenas **texto/resumen**: fondo sin letras + overlay ffmpeg con el guion real.
- Keyframe **local** a Runway (más fiel que URL S3).
- Clip Runway en **loop** hasta cubrir narración.
- Si Runway falla → fallback ken-burns sobre la imagen del storyboard.

---

## Flujo técnico

```
RAG EMPRESA (DocumentoRAG + Chroma)
        ↓
     OpenAI → LECCIÓN
        ↓
    ANALIZADOR pedagógico
        ↓
  STORYBOARD AUTOMÁTICO
        ↓
┌─────────────────────────────┐
│ Tipos de escena             │
│ imagen | imagen_zoom        │
│ diagrama | video_ia         │
│ texto | narracion           │
│ transicion | resumen        │
└──────────────┬──────────────┘
               ↓
     GENERACIÓN DE ASSETS
   (ElevenLabs narración + stubs visuales)
               ↓
         COMPOSICIÓN (ffmpeg — MVP)
               ↓
            S3 (cuando exista MP4)
```

## Variables de entorno (local)

```env
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
# Voz: en elevenlabs.io → Voices → copiar Voice ID
ELEVENLABS_VOICE_ID=xxxxxxxxxxxxxxxxxxxx
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
COURSE_ENGINE_TTS_PROVIDER=elevenlabs
COURSE_ENGINE_TTS_FALLBACK_OPENAI=true
COURSE_ENGINE_ENABLED=true
```

### ElevenLabs — elegir voz

1. [ElevenLabs Voice Library](https://elevenlabs.io/voice-library) → filtrar español.
2. Probar voces con acento neutro/latino (no `nova` de OpenAI).
3. Opcional: **Voice Cloning** con muestra de voz eki (30s–1min).
4. Copiar **Voice ID** → `ELEVENLABS_VOICE_ID` (global) o **Curso / Modulo → ElevenLabs Voice ID** (por cliente / voz clonada).

### Voz clonada del cliente

1. Cliente graba muestras en [ElevenLabs Voice Lab](https://elevenlabs.io/app/voice-lab) (Instant / Professional clone).
2. Copiar **Voice ID** de esa voz (mismo formato que biblioteca: `Wb1wmVQjMx9g2QSIOTPI`).
3. Pegar en **Curso → Course Engine → Voice ID** (todo el curso) o **Modulo → Course Engine** (solo ese modulo).
4. Etiqueta visible: «Agronomo Cenipalma» para que ops sepa cual es.

## QA — muestra de voz

```powershell
# Por curso (Voice ID del curso o .env)
python manage.py course_engine_voice_preview --curso-id 22

# Por modulo
python manage.py course_engine_voice_preview --modulo-id 45

# Voice ID directo (voz clonada cliente)
python manage.py course_engine_voice_preview --voice-id Ux2YbCNfurnKHnzlBHGX --label "Agronomo cliente"
```

Admin: **Curso / Modulo → Course Engine → Escuchar muestra (~5 s)** (pestaña colapsada en curso).

Veredicto esperado: `QA_PASS muestra voz` + URL MP3 `audio/mpeg` ≤16 MB.

Modelo recomendado: `eleven_multilingual_v2` (español rural/claro).

## Comandos local / ops

```powershell
# Paquete mixto (respeta course_engine_format del curso)
python manage.py course_engine_generate_bundle ^
  --cliente-id 1 --curso-id 22 --modulo-id 45

# Override formato / dry-run costo
python manage.py course_engine_generate_bundle ^
  --cliente-id 1 --curso-id 22 --modulo-id 45 ^
  --formato mixto_completo --tier estandar --dry-run

# Solo video MP4 (legacy)
python manage.py course_engine_generate_video ^
  --cliente-id 1 --curso-id 22 --modulo-id 45 --tier estandar
```

Salida: `tmp/course_engine/runs/<run_id>/run.json` + `compose/video_final.mp4` + URL S3 si `USE_S3=True`.

## Módulos (código)

| Archivo | Rol |
|---------|-----|
| `video_generator.py` | Orquestador MP4 completo |
| `prompt_context.py` | Prompts con contexto lección (Runway + imágenes) |
| `runway_service.py` | Runway image→video / text→video |
| `budget.py` | Topes por tier + estimados USD |
| `clip_builder.py` | ffmpeg clips + overlay texto |
| `voice_config.py` | Catálogo 4 voces + herencia curso→módulo |
| `rag_source.py` | Contexto DocumentoRAG vía `rag_manager` |
| `lesson.py` | OpenAI → borrador lección |
| `storyboard.py` | Escenas automáticas |
| `tts.py` | ElevenLabs (+ fallback OpenAI) |
| `image_service.py` | gpt-image-1 por escena |

## Pendiente (siguientes slices)

- [x] Imágenes: `gpt-image-1` por escena
- [x] ffmpeg concat (audio + slides + zoom + Runway loop)
- [x] `CourseVideoGenerator` → MP4 local + S3
- [x] **Runway** — tier `estandar`/`premium`, escenas `video_ia`
- [x] Admin voces + preview QA + EB env vars
- [x] Prompts contextuales + overlay texto
- [ ] Modelos DB `CourseGenerationRun` / historial costos
- [ ] Admin botón «Generar video» + Celery async
- [ ] Publicar MP4 → PasoModulo en un clic

## Runway — video IA (4–10 s)

1. Cuenta en [dev.runwayml.com](https://dev.runwayml.com) → API Keys
2. En `.env`:
   ```
   RUNWAY_API_KEY=key_...
   RUNWAY_IMAGE_TO_VIDEO_MODEL=gen4_turbo   # mas barato con keyframe
   RUNWAY_DURATION_SEC=4
   ```
3. Smoke (sin pipeline completo):
   ```powershell
   python manage.py course_engine_runway_smoke --use-last-run --duration 4
   python manage.py course_engine_runway_smoke --texto "Campo de cafe al amanecer" --duration 4
   ```
4. Video completo con 1 escena `video_ia` → tier `estandar`:
   ```powershell
   python manage.py course_engine_generate_video --cliente-id 1 --curso-id 22 --brief "Broca del cafe" --tier estandar
   ```

| Modelo Runway | Modo | Costo aprox | Cuándo |
|---------------|------|-------------|--------|
| `gen4_turbo` | image→video | ~5 cr/s | **Default eki** — keyframe + movimiento |
| `gen4.5` | text→video | ~12 cr/s | Smoke sin imagen |
| `veo3.1_fast` | text/image | ~10–15 cr/s | Mayor calidad, mas caro |

Alternativas futuras: Replicate (SVD), Fal.ai — evaluar si Runway supera presupuesto.

## Rama git

- Trabajo: `feat/course-engine`
- **No** auto-merge a `main`
- TTS anterior: `feat/course-engine-tts` (OpenAI only) — superseded por ElevenLabs aquí
