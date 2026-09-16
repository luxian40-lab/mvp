# Referencia — Course Engine video (eki)

Notas operativas para ir mejorando el skill `eki-video-design` y el orquestador.

## Pipeline actual (piloto WA)

1. Brief (+ foco opcional) → `planificar_video_leccion` o **plan fijo**
2. TTS por segmento (`generar_narracion_archivo`)
3. Keyframe documental + Runway (apertura / cierre)
4. Lámina infográfica animada (`tarjeta`)
5. Compose ffmpeg → gate WA → S3 `media/course_engine/videos/wa_safe/`
6. Envío opcional Twilio (solo QA autorizado)

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `video_pilot_generator.py` | Orquesta un MP4 |
| `video_storyboard.py` | JSON plan + fallbacks |
| `portal_api.py` | Demo Studio enqueue |
| `scripts/eb_ce_microcapsula_incendio.*` | Ejemplo QA plan fijo + visuals seguros |
| `scripts/eb_ce_studio_demo_15s.*` | Demo Studio 15s |

## Lecciones (actualizar aquí)

| Fecha | Caso | Aprendizaje |
|-------|------|-------------|
| 2026-09-03 | Incendio Tolima | Fallback LLM → Error1 finanzas. Mitigar con plan fijo. |
| 2026-09-03 | Incendio Tolima | OpenAI/Runway rechazan fuego/humo. Mensaje en voz; imagen = niebla/alejarse/teléfono. |
| 2026-09-03 | Variedad | Sin brief distinto + prompts distintos, los videos “se parecen”. Skill debe forzar contraste visual. |

## Mejora futura (backlog skill)

- [ ] Catálogo de “looks” (agro / emergencia / finanzas / salud) con prompts base rotativos
- [ ] Seed de variedad por `run_id` (hora del día, ángulo, paleta)
- [ ] Param `plan_override` estable en `VideoPilotGenerator.generar`
- [ ] Tests: fallback nunca Error1 si el brief no es Error1
