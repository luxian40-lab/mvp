# PM — Semana 1 Loop Nat (HITL → Studio → RAG)

**Estado:** GO Ops (sin Dev grande)  
**PM:** encargada de que cada rol cumpla la meta  
**Meta observable (7 días):** ≥5 candidatas **revisadas** en 1 cliente piloto · anotar % aprobadas · ≥3 publicadas en RAG (smoke) · 0 PII obvia  
**URL:** https://admin.eki.technology/admin/knowledge-studio/  
**Fuera de scope:** fine-tune · auto-aprender sin humano · tipificar salud · Cloud API Meta · dummies módulo (otro track)

---

## Ritual (15 min / semana, idealmente 3×5 min)

1. Abrir Knowledge Studio → cola **pendientes** del cliente piloto.  
2. Por cada candidata: leer preview → **Aprobar** / **Rechazar** / (si aplica) **Publicar**.  
3. Checklist Legal al aprobar (abajo).  
4. Anotar en la tabla de métricas (abajo).  
5. Si el Studio **bloquea** (no carga, no aprueba, no indexa) → escalar PM → Dev/UX.

---

## Checklist Legal / Sec (al aprobar)

Rechazar o editar si el texto tiene:

- [ ] Cédula / documento  
- [ ] Teléfono  
- [ ] Nombre completo de persona real (salvo marca/producto)  
- [ ] Dirección exacta de finca / vereda sensible  
- [ ] Datos de salud

Preview corto OK. Si duda → **Rechazar** (no aprobar “por si acaso”).

---

## Checklist Nat del cliente piloto (antes del día 1)

Dueño: **Growth + Nat**

- [ ] Cliente piloto elegido (nombre + id)  
- [ ] `numero_whatsapp_nat` / canal OK  
- [ ] Biblioteca **de esa org** (no solo general)  
- [ ] Catálogo (± Plan B)  
- [ ] Smoke: saludo → plaga o rutina → respuesta usable  
- [ ] Al menos 1 conversación real que genere candidata (o forzar flujo HITL si existe)

---

## Métricas (llenar cada revisión)

| Fecha | Cliente | Revisadas (acum.) | Aprobadas | Rechazadas | Publicadas RAG | % aprobadas | Notas / PII |
|-------|---------|-------------------|-----------|------------|----------------|-------------|-------------|
| | | | | | | | |
| | | | | | | | |
| **Cierre día 7** | | ≥5 | | | ≥3 | | 0 PII |

**Proxy “¿se reutilizó?” (semana 2+):** tras publicar, smoke pregunta tipada → ¿la respuesta cita/usa el conocimiento nuevo? Sí/No.

---

## Matriz de agentes (PM revisa cumplimiento)

| Agente | Debe hacer esta semana | Entregable a PM | No hacer |
|--------|------------------------|-----------------|----------|
| **PM** | Dueña de meta; ritual; escalar gaps; go/no-go Dev | Tablero métricas al día 7 | Código |
| **Growth** | Dueño operativo del ritual 15 min; elige piloto | Filas en tabla + % | Features nuevas |
| **Ops / CS** | Apoya si el piloto es cliente con CS activo | Confirmación “piloto vivo” | Spamear WA |
| **Nat** | Checklist org; criterio “buena candidata” (técnica, reutilizable) | Lista de 3 temas prioritarios a capturar | Vendedora vacía |
| **Content** | Si aprueban FAQ/ficha: tono eki corto | OK de copy en ≥1 publicada | Reescribir Studio |
| **Legal** | Checklist PII; veto si hace falta | “PASS Legal” o lista rechazos | Ignorar salud/PII |
| **Sec** | Revisión ligera PII en docs aprobados (muestra) | PASS/FAIL PII | Fine-tune |
| **Data** | Definir conteo honesto: revisada = estado ≠ pendiente | Fórmula % = aprobadas/revisadas | Inventar KPI Learning |
| **QA** | Día 7: smoke Nat + 1 consulta tipada post-publicación | QA_PASS / FAIL | Deploy solo |
| **UX** | Solo si Growth reporta “Studio duele” | Lista de fricción (≤5 bullets) | Rediseño total |
| **Dev** | Solo gaps bloqueantes aprobados por PM | Fix mínimo + test si toca código | Auto-aprender |
| **SRE** | Solo si index RAG/Chroma cae | Salud index | Microservicios |
| **Diseñador** | No aplica semana 1 | — | — |
| **CTO** | Go/no-go si piden auto-learn o nuevo canal | Bloqueo si salen del scope | — |

---

## Escalamiento (cuándo abre cada rol)

| Señal | Quién entra |
|-------|-------------|
| No hay candidatas en 48 h | Nat + Growth (generar chats / revisar auto-HITL) |
| Studio 500 / no aprueba / no publica | **Dev** (gap) + QA |
| Cola confusa / no se entiende aprobar | **UX** (1 pase) |
| PII en aprobadas | **Legal + Sec**; revertir/desindexar |
| Meta día 7 incumplida | PM: extender 3 días **o** abrir Dev en cuello medido |

---

## Definición de “semana 1 cumplida” (PM cierra)

- [ ] ≥5 candidatas revisadas (mismo cliente piloto)  
- [ ] % aprobadas anotado  
- [ ] ≥3 en RAG + smoke tipado QA  
- [ ] 0 PII obvia (Sec/Legal)  
- [ ] Runbook usado (este doc o Notion link)  
- [ ] Decisión explícita: **seguir Ops** / **abrir Dev-UX gaps** / **cambiar piloto**

---

## Decisión vigente

**Dev = NO** hasta que Ops/Growth use Studio ≥1 sesión real **o** reporte bloqueo.  
**Módulo dummies** = track aparte (no mezcla esta semana).
