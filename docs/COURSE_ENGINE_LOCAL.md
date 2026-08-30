# Course Engine — pipeline local (rama `feat/course-engine`)

**No mergear a `main` hasta QA local completo.**

## Flujo

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

## Comandos local

```powershell
git checkout feat/course-engine

# Solo narración (probar voz)
python manage.py generate_tts_smoke --texto "Bienvenido al módulo de riego eficiente."

# Pipeline completo hasta assets (sin prod)
python manage.py course_engine_local_run ^
  --cliente-id 1 ^
  --curso-id 22 ^
  --brief "Lección introductoria sobre riego en café" ^
  --hasta assets

# Solo storyboard (sin gastar ElevenLabs)
python manage.py course_engine_local_run --cliente-id 1 --curso-id 22 --brief "..." --hasta storyboard --sin-audio
```

Salida: `tmp/course_engine/runs/<run_id>/run.json` + `assets/` + `compose/manifest.json`

## Módulos

| Archivo | Rol |
|---------|-----|
| `rag_source.py` | Contexto DocumentoRAG vía `rag_manager` |
| `lesson.py` | OpenAI → borrador lección |
| `analyzer.py` | Análisis pedagógico |
| `storyboard.py` | Escenas automáticas |
| `tts.py` | **ElevenLabs** (+ fallback OpenAI) |
| `assets.py` | Narración S3 + stubs visuales |
| `compose.py` | Manifest ffmpeg (video final pendiente) |
| `pipeline.py` | Orquestador |

## Pendiente (siguientes slices)

- [x] Imágenes: `gpt-image-1` por escena
- [x] ffmpeg concat (audio + slides + zoom)
- [x] `CourseVideoGenerator` → MP4 local + S3
- [x] **Runway** (`runway_service.py`) — tier `estandar`/`premium`, escenas `video_ia`
- [ ] Modelos DB `CourseGenerationRun` / `MediaAsset`
- [ ] Admin UI Module Builder
- [ ] Celery async
- [ ] Deploy prod solo con `COURSE_ENGINE_ENABLED=true` + QA_PASS

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
