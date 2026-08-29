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
4. Copiar **Voice ID** → `ELEVENLABS_VOICE_ID`.

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

- [ ] Imágenes: DALL-E / Stable Diffusion por escena
- [ ] `video_ia`: integración proveedor (Runway/Pika — evaluar costo)
- [ ] ffmpeg concat real (audio + slides)
- [ ] Modelos DB `CourseGenerationRun` / `MediaAsset`
- [ ] Admin UI Module Builder
- [ ] Deploy prod solo con `COURSE_ENGINE_ENABLED=true` + QA_PASS

## Rama git

- Trabajo: `feat/course-engine`
- **No** auto-merge a `main`
- TTS anterior: `feat/course-engine-tts` (OpenAI only) — superseded por ElevenLabs aquí
