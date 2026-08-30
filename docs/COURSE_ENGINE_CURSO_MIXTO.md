# Course Engine — curso mixto (10 módulos)

**Objetivo:** un curso no es “solo 10 videos”. Cada módulo es un **paquete de microcontenidos** mezclados para WhatsApp / Aprende, alimentado por **RAG** (manuales del cliente) y voz **ElevenLabs**.

Canon técnico complementario: [`COURSE_ENGINE_LOCAL.md`](COURSE_ENGINE_LOCAL.md).

---

## 1. Qué es un módulo mixto (eki)

Un **módulo** = varios **pasos** (*listo* en WA). Cada paso entrega **un** microcontenido. El Course Engine genera el **material**; ops lo publica en PasoModulo / Module Builder.

### Receta estándar por módulo (recomendada)

| Orden WA | Tipo | Formato | Duración | Rol pedagógico |
|----------|------|---------|----------|----------------|
| 1 | **Hook video** | MP4 | 20–35 s | Gancho visual + idea clave |
| 2 | **Infografía** | PNG/JPG | — | Resumen visual (1 pantalla) |
| 3 | **Podcast** | MP3 | 2–4 min | Profundizar con voz (manos libres / audio) |
| 4 | **Texto + evaluación** | WA | — | Repaso + pregunta (manual o existente) |

Variantes:

- **Ligero (economico):** video + texto (sin podcast; infografía dentro del video como escena `diagrama`).
- **Estándar B2B:** video (1 Runway) + infografía suelta + podcast corto (~2 min).
- **Premium showcase:** video premium + infografía HD + podcast ~4 min + mismo RAG.

---

## 2. Segmentación en el curso (admin)

En **Curso → Course Engine → Formato (segmentación)** eliges cómo se arma **cada módulo** al generar:

| Formato | Pasos WA | Contenido generado |
|---------|----------|-------------------|
| **Solo video** | 1 | MP4 |
| **Video + infografía** *(default)* | 2 | MP4 + PNG diagrama |
| **Mixto completo** | 3 | MP4 + PNG + podcast MP3 |
| **Mixto ligero** | 1 | MP4 económico (sin PNG suelta ni podcast) |

Complementos en el mismo fieldset:

- **Tier** — calidad del video (Runway en estándar/premium).
- **Podcast (min)** — 2 / 3 / 4 min (solo mixto completo).
- **Voz** — ElevenLabs (video + podcast misma voz).

Un **mismo RAG + lección** alimenta video, infografía y podcast en un solo `run_id`.

---

## 3. RAG — cómo alimenta todo el paquete

```
DocumentoRAG (PDF/manual cliente)
        ↓ indexar (Chroma, 1× por doc)
        ↓
Por módulo: consulta = título + objetivos del módulo
        ↓
    ┌───┴───┬───────────┐
    ↓       ↓           ↓
 Lección  Guion      Infografía
 (GPT)    podcast     (prompt diagrama)
    ↓       ↓           ↓
 Storyboard → Video MP4 + assets S3
```

- **Sin RAG:** GPT solo usa brief → más genérico (riesgo “agricultura 101”).
- **Con RAG:** lección, guiones y prompts visuales citan el manual del cliente.
- **Costo RAG por módulo:** ~$0.01–0.03 GPT extra (embeddings del doc son **una vez** al indexar).

**Checklist cliente:** subir PDFs al curso → indexar → verificar `DocumentoRAG` estado `indexado` antes de generar lote.

---

## 4. Modelos recomendados (2026)

### OpenAI (texto + imagen)

| Uso | Modelo | Por qué |
|-----|--------|---------|
| Lección + storyboard + análisis | `gpt-4o-mini` | Barato, JSON estable, suficiente para microlearning |
| Imágenes + infografías | `gpt-image-1` quality `medium` | Escenas e infografías; diagramas con prompt “sin texto ilegible” |
| Upgrade futuro (cliente exigente) | `gpt-4o` solo storyboard | Mejor coherencia pedagógica; +costo |

### ElevenLabs — **dos modelos** (mejora clave)

| Uso | Variable EB | Modelo recomendado | Notas |
|-----|-------------|-------------------|--------|
| **Video** (frases cortas por escena) | `ELEVENLABS_MODEL_ID_VIDEO` | `eleven_multilingual_v2` | Español rural claro; frases 5–15 s |
| **Podcast** (2–4 min monólogo) | `ELEVENLABS_MODEL_ID_PODCAST` | `eleven_multilingual_v2` | Prosodia estable en pasajes largos |
| Podcast expressivo (piloto) | idem | `eleven_v3` | Más expresivo; probar 1 episodio antes de lote |
| **No usar** para podcast | — | `eleven_flash_v2_5` / `eleven_turbo_v2_5` | Latencia baja, voz plana en largo |

**Ajustes voz podcast** (vs video): stability ~0.55, similarity ~0.80, style ~0.12 — más natural en 2–4 min.

**Plan ElevenLabs:** Creator (~100k chars/mes) alcanza ~1 curso de 10 módulos mixto; Pro si hay varios cursos/mes o podcasts largos.

### Runway (solo dentro del video)

| Tier curso | Clips Runway / módulo |
|------------|------------------------|
| economico | 0 |
| estandar | 1 × ~4 s |
| premium | 1–3 × ~4 s |

---

## 5. Costos — curso 10 módulos (estimado APIs)

Supuestos: RAG indexado, 1 voz, 1 regeneración QA cada 10 piezas (+10% contingencia).

### Por módulo — paquete mixto estándar

| Pieza | Detalle | USD |
|-------|---------|-----|
| Video | tier **estandar** (5 escenas, 1 Runway) | ~0.50 |
| Infografía | 1 PNG diagrama (prompt RAG) | ~0.04 |
| Podcast | ~2 min (~1.200 caracteres), Multilingual v2 | ~0.18 |
| GPT extra | guion podcast + lección (RAG) | ~0.03 |
| **Subtotal / módulo** | | **~0.75** |

### Totales curso (10 módulos)

| Escenario | Contenido / módulo | USD curso (10 mód.) | ElevenLabs chars ≈ |
|-----------|-------------------|---------------------|---------------------|
| **A — Ligero** | video economico + infografía en video | **$3 – 4** | ~8k |
| **B — Estándar eki** | video estandar + infografía + podcast 2 min | **$7 – 8** | ~25k |
| **C — Premium** | video premium + infografía + podcast 3–4 min | **$9 – 12** | ~35k |
| **D — Solo video** (10× estandar) | MP4 únicamente | **$5 – 6** | ~10k |

**No incluye:** horas diseño instruccional, revisión agronómica, clon de voz cliente, plan ElevenLabs/Runway mensual.

### Indexación RAG (una vez por curso)

| Docs | Costo embeddings (orden magnitud) |
|------|-----------------------------------|
| 5–10 PDFs (~200 pág total) | ~$0.10 – 0.50 |
| Re-indexar tras cambio manual | solo docs nuevos |

---

## 6. Flujo ops — curso mixto de punta a punta

### Fase 0 — Setup (1× por curso)

1. Cliente entrega manuales → **DocumentoRAG** en el curso.
2. Indexar RAG (prod con Chroma).
3. Curso → **Course Engine**: tier default + voz (Maria/Sofia/… o clon).
4. QA voz: **una** muestra (~5 s), no spamear catálogo.

### Fase 1 — Por cada módulo (×10)

1. **Generar paquete** (respeta formato del curso en admin):
   ```powershell
   python manage.py course_engine_generate_bundle ^
     --cliente-id 1 --curso-id 22 --modulo-id 45
   ```
   Salida: `bundle_manifest.json` con URLs por paso WA (video → infografía → podcast).

2. **QA humano** — video, infografía legible, podcast escucha completa.

3. **Publicar en WA** — Module Builder: pegar URLs del manifest en orden (`paso_orden`).

4. Anotar `run_id` + costos en control interno (hasta dashboard DB).

### Fase 2 — Publicación curso

- Checklist módulo verde → publicar módulos WA.
- Drip entre módulos según curso/cliente.

---

## 7. Roadmap técnico (mezcla automática)

| Prioridad | Entrega | Estado |
|-----------|---------|--------|
| P0 | Video MP4 + RAG + Runway + voces | ✅ Prod |
| P0 | `course_engine_generate_bundle` — 1 comando → video + PNG + MP3 | ✅ CLI |
| P0 | Campo curso `course_engine_format` + podcast min en admin | ✅ |
| P1 | Auto-crear PasoModulo desde `bundle_manifest.json` | 🔲 |
| P2 | `CourseGenerationRun` + costo real por módulo | 🔲 |
| P3 | Infografía vector/PDF (opcional) | 🔲 |

### Diseño `generate_bundle` (target)

```
RAG + módulo
    → lección (1× GPT)
    → storyboard video
    → guion podcast (GPT, 300–600 palabras desde misma lección)
    → prompt infografía (1 diagrama desde puntos_clave)
    → paralelo: video | imagen PNG | TTS podcast
    → S3: videos/, images/, tts/podcasts/
    → manifest.json (URLs para Module Builder)
```

**Principio:** una sola fuente de verdad (lección + RAG) alimenta **video, infografía y podcast** — no tres briefs distintos.

---

## 8. Calculadora rápida (referencia)

```text
costo_modulo ≈ costo_video(tier) + 0.04·N_infografías + 0.15·(chars_podcast/1000) + 0.03

costo_video economico  ≈ 0.35
costo_video estandar   ≈ 0.50
costo_video premium    ≈ 0.55

curso_10 = costo_modulo × 10 × 1.10   # +10% QA/reintentos
```

Ejemplo **estándar mixto:** `(0.50 + 0.04 + 0.18 + 0.03) × 10 × 1.10` ≈ **USD 8.50**.

---

## 9. Decisiones eki (resumen)

| Pregunta | Respuesta |
|----------|-----------|
| ¿Podcast e infografía van aparte del video? | **Sí**, como pasos WA distintos; **no**, en generación — salen del **mismo RAG/lección**. |
| ¿Mejor modelo podcast? | **Multilingual v2** (prod); pilotar **eleven_v3** para expresividad. |
| ¿Mejor modelo video? | **Multilingual v2** (misma voz); opcional Turbo en frases ultra cortas para ahorrar. |
| ¿Cuánto un curso 10 módulos mixto? | **~USD 7–12** APIs (estándar–premium). |
| ¿RAG vale la pena? | **Sí** para fidelidad; costo marginal bajo. |

---

*Última actualización: 2026-08-30 — corridas referencia: cacao `6681ef74059c`, aguacate `005f1a665318`.*
