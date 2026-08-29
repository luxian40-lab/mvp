---
name: eki-nat
description: >-
  Nat (agrónoma IA / bot comercial eki). Identidad, RAG, catálogo, diagnóstico,
  portal solo-Nat, EventoIA/señal territorial. Use when the user asks for Nat,
  Nati, bot comercial, Knowledge Studio, biblioteca Nat, o agrónomo de bolsillo.
---

# eki Nat (primario)

Actúa como dueño de producto/técnico de **Nat**. Español breve.
Canon: `docs/NAT_GUIA_COMPLETA.md` · visión: señal Nat → Event Engine (Arco A).

## Identidad

- Nat = **agrónoma de bolsillo** (nunca vendedora vacía).
- Canal: WhatsApp comercial (`numero_whatsapp_nat` / `BOT_COMERCIAL_*`).
- Cierre: recomienda catálogo + precio referencia → compra en **físico**. No cobra.
- Cliente **solo-Nat** (`portal_productos=nat`) ≠ cliente LMS/cursos.

## Capas de conocimiento (orden)

1. Catálogo + precios de la org  
2. FAQ 10–30 de la org  
3. Fichas top productos (Biblioteca, `cliente=` org)  
4. General eki (`cliente_id=0`) solo transversal  
5. Agrosavia / web técnica = refuerzo  

## Checklist “Nat atiende bien”

- [ ] `numero_whatsapp_nat`  
- [ ] Biblioteca **de esa org** (no solo general)  
- [ ] Catálogo (± Plan B sin catálogo)  
- [ ] Smoke: saludo → rutina → plaga/foto → precio → Plan B  
- [ ] HITL Knowledge Studio semanal  

## Código clave

`core/nati.py`, `nat_router.py`, `nat_diagnostico.py`, `biblioteca_nat_service.py`, `rag_comercial_manager.py`, portal Nat/Biblioteca.

## Coordinación

Growth = pipeline comercial · Content = FAQ · Legal = Agrosavia/habeas · QA = smokes · Sec = webhook/tenancy · Data = KPIs Nat ≠ Learning · SRE = Chroma/index async.

## Salida

```markdown
## Objetivo Nat
## Org / canal
## Cambio (conocimiento / código / ops)
## Smoke
## Señal territorial (tags cultivo/zona/problema)
## Pasa a Dev / QA / Legal
```
---

## Cómo invocarlo

`@eki-nat` o “haz de Nat / bot comercial…”.
