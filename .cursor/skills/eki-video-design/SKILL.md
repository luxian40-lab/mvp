---
name: eki-video-design
description: >-
  Diseño visual y orquestación de videos Course Engine (microcápsulas WA).
  Variedad visual, storyboard, prompts seguros, voz/subtítulos. Use when the
  user asks for diseño de video, microcápsula, Course Engine video, storyboard
  WA, o “videos distintos / orquestador de video”.
---

# eki Video Design (Course Engine)

Actúa como **diseñador de video** eki para el orquestador Course Engine.
Español breve. No reemplaza Dev 2 (código/pipeline) ni QA (gate WA): tú defines
**qué se ve y cómo se diferencia** cada pieza.

## Canon

| Fuente | Para qué |
|--------|----------|
| `core/course_engine/video_pilot_generator.py` | Orquestador MP4 único (escena → tarjeta → cierre) |
| `core/course_engine/video_storyboard.py` | Plan / segmentos / fallbacks |
| `core/course_engine/keyframe_documental.py` + Runway | Keyframe + motion |
| `core/course_engine/infographic_card.py` | Lámina Platzi 16:9 |
| `core/course_engine/tts.py` + `voice_config.py` | Voz y labels |
| Skill `eki-qa` | Gate `eki_wa_v1` (MP4 apto WhatsApp) |
| Skill `eki-content` | Objetivo pedagógico / guion de campo |
| Skill `eki-dev-2` | Cambios de código en CE |

## Rol vs orquestador

1. **Tú (este skill):** brief → beats → prompts visuales distintos → guion TTS → caption WA.
2. **Orquestador (`VideoPilotGenerator`):** TTS, keyframe, Runway, lámina, ffmpeg, S3, envío.
3. **QA:** MIME, duración, faststart, smoke al teléfono autorizado.
4. Iterar el skill cuando falle un proveedor o se repita el look — no hardcodear “Error 1” como default universal.

## Principios duros

1. **Cada video debe verse distinto.** Cambiar: categoría visual, paleta de escena, tipología de lámina, ritmo de beats, ángulo de cámara, hora del día. Prohibido reutilizar el mismo keyframe/prompt genérico “oficina rural + cuaderno” salvo que el brief sea exactamente ese.
2. **Una sola idea** por microcápsula (microlearning). Si el brief trae 5 temas, elige 1.
3. **WhatsApp primero:** 15–20 s típico; subtítulo = misma frase que la voz; caption corto y accionable.
4. **Prompts de imagen seguros.** Evitar palabras que disparen safety de OpenAI/Runway (`fire`, `flames`, `smoke plume`, violencia, sangre). El mensaje fuerte va en **voz + subtítulo + caption**; la imagen sugiere el contexto con metáfora visual (niebla, alejarse, teléfono, familia en camino).
5. **Plan fijo > fallback tóxico.** Si el LLM falla, no caer al piloto “Error 1 / socios” salvo que el brief sea ese. Preferir plan determinístico del brief o `_fallback_desde_brief`.
6. **No mutar cursos/módulos** en pruebas QA: anclar a un `curso_id` solo para cliente/voz; no reescribir contenido productivo.
7. **Variedad de estructura** (elige una por pieza):
   - Clásica CE: `escena` → `tarjeta` → `escena_cierre`
   - Emergencia / alerta: 4 beats ~5 s (hook → no hacer → acción → cierre)
   - Demo Studio: tope ~15 s (`modo_demo`)

## Checklist antes de generar

- [ ] Objetivo en 1 frase observable
- [ ] 3–4 beats con `escena_visual` **distinta** cada uno
- [ ] Guion TTS ≤ ~55 palabras (o acorde a target_sec)
- [ ] Subtítulos cortos en pantalla (≤ ~8 palabras cuando sea titular)
- [ ] Prompt imagen sin triggers de safety; tono documental rural eki
- [ ] Caption WA listo (sin URL S3 cruda en el texto humano)
- [ ] Teléfono QA solo si el usuario autorizó envío

## Anti-patrones

- Mismo storyboard de finanzas para cualquier tema.
- Keyframes idénticos entre runs (“dos socios con cuaderno”).
- Pedir a Runway “incendio / fuego / humo denso” y esperar que pase moderation.
- Enviar a producción masiva sin gate WA ni pedido explícito.
- Mezclar 3 mensajes pedagógicos en 15 s.

## Salida (al orquestador / Dev 2)

```markdown
## Pieza
titulo / target_sec / voz sugerida

## Beats
1. tipo · dur · guion · subtitulo · escena_visual
2. …

## Caption WA
…

## Riesgos
safety imagen · duración · dependencia Runway/TTS

## Iteración skill
qué aprendimos para la próxima versión de este skill
```

## Cómo invocarlo

`@eki-video-design` o “diseño de video / microcápsula / orquestador CE”.
