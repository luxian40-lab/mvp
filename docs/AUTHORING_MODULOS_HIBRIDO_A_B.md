# Authoring de módulos eki — híbrido A / B / CE

**Estado:** implementado (slice A/B routing + UI modo clase) — CE (paso C) pendiente  
**Fecha:** 2026-09-14 · actualizado implementación  
**Dueña de decisión:** PM + fundadora  
**Canon relacionado:** Module Builder, Course Engine, pestaña Clase, WhatsApp *listo*

---

## 1. Problema

No es “falta un botón Clase”. Hay **dos productos de authoring mezclados** (subir archivo vs armar experiencia WhatsApp) y el admin obliga a verlos a la vez.

Síntoma actual (crear módulo):

- Banda **IR A**: Clase / Estructura / Materiales / Media / Examen
- Aterrizaje en **Estructura vacía** (“Agregar Bloque”)
- Copy de culpa: *“Camino recomendado: Module Builder…”*
- Carga cognitiva alta para staff nuevo; cliente jamás debería ver esto

---

## 2. Por qué el “solo Clase” no convence del todo

En eki una “clase” WhatsApp **casi nunca es un PDF suelto**: es secuencia + media + a veces eval A–D.

| Enfoque | Qué resuelve | Qué no resuelve |
|---------|--------------|-----------------|
| Solo Clase (dummies plano) | ~80% de confusión / fricción | El producto estrella (micros, *listo*, CE) |
| Solo Builder | Potencia para Content | Staff nuevo se pierde |
| **Híbrido A vs B** | Fácil **y** potente, con intención explícita | — |

El deseo de producto es: **fácil y potente**, no solo “esconder pestañas”.

---

## 3. Qué dice el mercado (LMS + WhatsApp learning)

| Fuente / patrón | Aprendizaje |
|-----------------|-------------|
| **Moodle UX research** | Mayor dolor = content management: carga cognitiva, curva alta, tiempo. Piden **menos pasos, más contextual**, no más settings. |
| **Canvas** | Flujo claro: **Modules = secuencia**; contenido en Pages/Files; no 5 destinos “IR A” compitiendo. |
| **Industry (LMS built-in vs authoring)** | SME / staff no diseñador → UI mínima (subir + publicar). ID / Content → builder rico. **Híbrido**, no un solo camino. |
| **WhatsApp microlearning** (Leap10x, canapés, SAQL) | Patrón ganador: **Upload → IA/estructura → Review cards → Publish** (3–4 pasos). El builder drag existe **después** del upload. |

Referencias útiles:

- Moodle Course Creation journeys (UX research)
- Canvas Modules / Pages (organización secuencial)
- eLearning Industry / Sprout Labs: cuándo usar authoring built-in vs externo
- Leap10x, canapés.ai, SAQL: upload → microcápsulas WA

---

## 4. Mesa de agentes (veredicto)

| Rol | Veredicto |
|-----|-----------|
| **PM** | Happy path sí, pero mal vendido: no es “esconder todo”, es **elegir modo al crear**. Meta = 2 modos explícitos. |
| **UX** | Banda IR A + Estructura vacía + “ve al Builder” = anti-patrón. Primero **intención**, luego UI. |
| **Content** | Necesitan Builder/CE; dummies puro les queda corto. Quieren **borrador IA → editar cards**. |
| **Diseñador** | Menos chrome; un hero de creación, no 5 destinos iguales. |
| **QA** | Riesgo dummies extremo: media no apta WA. **Checklist de publicación** no negociable. |
| **Dev** | No reescribir modelos; fix = **routing + progressive disclosure**. |
| **CTO** | Visión: WA-first + Course Engine. Norte = upload → microcápsulas, no tabs Jazzmin. |
| **Growth / Ops** | Staff nuevo se pierde → no escala. Cliente no ve Estructura. |
| **Legal / Sec** | Layout irrelevante; sí **quién puede publicar**. |

---

## 5. Propuesta de producto (híbrido)

Al **Crear módulo**, una pregunta (o inferencia):

```
¿Qué vas a hacer?
(A) Subir una clase rápido  → título + archivo + Activar + checklist WA
(B) Armar por partes (WA)   → Builder / CE (cards, listo, eval)
```

### Reglas

1. **Nunca** aterrizar en Estructura vacía ni en copy “ve al Builder”.
2. **Modo A** no muestra IR A completo.
3. **Modo B** es el camino interactivo (pestañas/canvas **dentro del Builder**, no en el changeform clásico).
4. **Course Engine** (“sube PDF → genera micros”) = **paso C natural** (como Leap10x/canapés); **no** reemplaza A/B el día 1.

### Flujos

| Modo | Quién | Pantalla | Éxito |
|------|-------|----------|-------|
| **A — Rápido** | Staff nuevo, carga simple | Título + media/texto + Activar + checklist WA | Publicado apto WA en ≤10 min |
| **B — Por partes** | Content / ID | Module Builder (y/o CE studio) | 1 módulo WA con micros/*listo* sin preguntar “¿dónde está el Builder?” |
| **C — CE (después)** | Content + Dev 2 | Upload doc → borrador cards → review → publish | Competitivo vs WA microlearning del mercado |

---

## 6. Decisión PM

| Hacer | No hacer (aún) |
|-------|----------------|
| Diseñar modal / primer paso **A vs B** + aterrizaje correcto | Solo “ocultar pestañas” sin elegir modo |
| Checklist publicación WA en modo A (obligatorio) | Reescribir modelos Curso/Módulo |
| Luego CE: upload → borrador micros | Meter cliente portal en Estructura/Builder |
| Métricas de tiempo (abajo) | Fine-tune / auto-learn mezclado en este track |

### Métricas de aceptación (cuando se implemente)

- [ ] Persona nueva publica en **≤10 min** en modo A  
- [ ] Content arma 1 módulo WA en modo B **sin** preguntar “¿dónde está el Builder?”  
- [ ] 0 aterrizajes en Estructura vacía post-crear  
- [ ] 0 copy de culpa “recomendado: Module Builder” en el camino feliz  
- [ ] QA: media del caso A pasa gates WA (sin 63019/63021 en feliz)

---

## 7. Orden de trabajo sugerido

| Fase | Qué | Roles | Estado |
|------|-----|-------|--------|
| **0 — Doc** | Alineación | PM | Hecho |
| **1 — UX/Dev slice** | A vs B + aterrizajes | Dev (+ UX) | **Hecho en código** |
| **2 — QA** | Cronómetro + smoke media WA | QA | Pendiente post-deploy |
| **3 — CE** | Upload → micros | Dev 2 / Content | Pendiente |

### Implementado (2026-09-14)

- `core/modulo_authoring_mode.py` — sesión `clase` / `builder`
- Alta módulo: radio **¿Qué vas a hacer?**
- Default → **Clase** (`?modo=clase`), sin IR A / sin Estructura
- Opción B → Module Builder (si está habilitado)
- Sin copy “ve al Builder”; enlace explícito “Armar por partes”
- Checklist WA sigue en ficha Clase
- Tests: `core.tests_modulo_alta_micro` + redirects builder UI

---

## 8. Anti-patrones a no repetir

- Dejar al usuario en tabla de bloques vacía  
- Cinco destinos IR A con la misma jerarquía visual  
- Mensaje “el camino bueno es otro sitio”  
- Un solo happy path que mate el Builder  
- Publicar sin checklist de media WhatsApp  

---

## 9. Próximo paso

Cuando la fundadora diga **go**:

1. UX dibuja pantalla A vs B (1 página).  
2. PM aprueba copy de botones.  
3. Dev implementa routing mínimo.  
4. QA cronómetro + media.
