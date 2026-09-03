# Auditoría multimedia Module Builder + S3 (eki)

**Rol:** Cloud Architect / Multimedia Pipeline  
**Fecha:** 2026-09-01  
**Canon:** `docs/MODULE_BUILDER_WA.md` · `core/twilio_media.py` · Impulso prod (curso 22)

---

## 1. Resumen ejecutivo

| Área | Estado | Veredicto |
|------|--------|-----------|
| Videos WA en Impulso (prod) | 25/25 video OK, 0 fail Twilio 14d | **PASS** |
| Upload Module Builder (MP4) | Gate H.264 Main + `wa_safe/` | **PASS** |
| Course Engine → S3 | Sin gate WA al subir | **GAP P1** |
| Infografías (PNG) | Upload directo, sin límite peso explícito | **WARN** |
| Podcasts (MP3) | Upload aceptado; `media_wa_apto` vacío | **WARN** |
| Ancho de banda rural | 720p / ≤16 MB / faststart | **PASS** en pipeline WA |

**Estándar obligatorio de aquí en adelante:** perfil **`eki_wa_v1`** (ver §4).

---

## 2. Arquitectura S3 actual

```
Upload admin / Module Builder
        │
        ├─ MP4/MOV/M4V ──► validar cabecera ──► ffmpeg H.264 Main + AAC
        │                      │                    │
        │                      │                    └─► modulos/pasos/wa_safe/..._h264_main_faststart.mp4
        │                      └─► async Celery (videos grandes) ──► mismo encode
        │
        ├─ PNG/JPG/PDF ──► modulos/pasos/{YYYY}/{MM}/modulo_{id}_...
        │
        └─ MP3/audio ──► mismo path; sin transcode a audio/mpeg forzado

Course Engine (generador)
        │
        └─ compose/video_final.mp4 ──► media/course_engine/videos/{run_id}.mp4
            (sin optimizar_mp4_bytes_whatsapp hoy)
```

**Bucket:** `eki-produccion` · región `us-east-2`  
**URLs Twilio:** públicas regionales (`eki-produccion.s3.us-east-2.amazonaws.com/...`), sin presigned en envío WA.

**Modelo de datos:** `PasoModulo.media_url` + `PasoModulo.media_wa_apto` (bool|null).  
No hay tabla separada de assets; un paso = un microcontenido WA.

---

## 3. Evaluación de calidad y ancho de banda

### 3.1 Perfil `eki_wa_v1` (referencia Impulso reparado)

| Parámetro | Valor |
|-----------|--------|
| Video | H.264 **Main**, yuv420p, ancho máx **720 px** |
| Audio | AAC mono, ~96 kbps (baja a 64/48 si >16 MB) |
| Contenedor | MP4 **faststart** |
| Tamaño máx | **16 MB** (límite práctico Meta/Twilio) |
| Códigos evitados | 63019 (URL/MIME), 63021 (codec) |

Implementación: `core/twilio_media.py` → `optimizar_mp4_bytes_whatsapp`, `evaluar_mp4_listo_whatsapp`.  
Upload admin: `core/admin/_common.py` → `_procesar_mp4_bytes_whatsapp`.

### 3.2 Streaming

WhatsApp **no** hace streaming adaptativo: entrega el archivo completo. La “optimización rural” es **peso + codec**, no HLS/DASH.

### 3.3 Course Engine (gap)

- Compone a **1280×720** (`clip_builder.py`).
- Sube sin pasar gate WA (`compose.subir_video_s3`).
- **Riesgo:** videos generados “bonitos” en preview pero **63021** o >16 MB en campo.

**Acción recomendada (Dev):** tras `concatenar_clips`, ejecutar el mismo `_procesar_mp4_bytes_whatsapp` antes de S3 y marcar `media_wa_apto=True` al publicar en paso.

---

## 4. Infografías y podcasts

### 4.1 Modelo actual (suficiente para MVP)

| Tipo | Campo | Paso WA | MIME Twilio |
|------|-------|---------|-------------|
| Infografía | `media_url` PNG/JPG | 1 paso, imagen | `image/png` o `image/jpeg` |
| Podcast | `media_url` MP3 | 1 paso, audio | **`audio/mpeg`** (no `audio/mp3`) |
| Video | `media_url` MP4 | 1 paso, video | `video/mp4` |

Course Engine **mixto** (`format_config.py`): video + infografía + podcast = **3 pasos** en el mismo módulo, mismo `run_id` en manifest.

### 4.2 Gaps

1. **MP3:** no se fuerza `Content-Type: audio/mpeg` ni `media_wa_apto=True` al subir (warn en audit M10–M11 Impulso).
2. **PNG HD:** sin compresión automática; límite WA ~5 MB imagen — validar en upload.
3. **Endpoints:** no hace falta API nueva; flujo es POST `add_micro` / `replace_media` en `/admin/module-builder/<id>/`. Manifest CE → pegar URLs en Builder.

### 4.3 Endpoints / acciones (contrato)

| Acción | Método | Uso |
|--------|--------|-----|
| `save_modulo` | POST ajax | Texto, drip, flags |
| `add_micro` | POST multipart | Nuevo paso + archivo |
| `replace_media` | POST multipart | Reemplazar archivo paso |
| `audit_media_wa` | management command | QA lectura sin Twilio |

---

## 5. Saldo APIs generación (prod 2026-09-01)

| API | Restante | Notas |
|-----|----------|-------|
| Runway | ~825 créditos (~USD 8.25) | ~10 módulos estándar (1 clip/módulo) |
| ElevenLabs | ~24k caracteres / 26k | 1 curso mixto corto |
| OpenAI | dashboard | bajo costo por módulo vs Runway |

Priorizar **tier económico** + gate WA; Runway solo en clips clave.

---

## 6. Checklist operativo (antes de publicar módulo)

- [ ] `python manage.py audit_media_wa --curso-id N --solo-riesgo` → 0 fail
- [ ] Videos: `media_wa_apto=true` y path `wa_safe` o `h264_main_faststart`
- [ ] Impulso / piloto: smoke 1 video por módulo nuevo (tel QA autorizado)
- [ ] CE: no publicar URL `course_engine/videos/*.mp4` sin pasar `eki_wa_v1`

---

## 7. Roadmap técnico (prioridad)

| P | Item | Dueño |
|---|------|-------|
| P1 | Course Engine → `eki_wa_v1` antes de S3 | Dev |
| P1 | MP3 upload → `audio/mpeg` + `media_wa_apto` | Dev |
| P2 | PNG >5 MB → compresión o reject con mensaje | Dev |
| P2 | Semáforo WA en listado pasos (pre-publicar) | UX + Dev |
| P3 | Manifest CE → “Publicar en Builder” 1 clic | Dev |
