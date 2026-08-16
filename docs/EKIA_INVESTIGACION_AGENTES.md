# EkiA — investigación profunda: agentes, soberanía y futuro de eki

**Clasificación:** investigación estratégica interna · producto + arquitectura + riesgo  
**Estado:** documento de trabajo (complementa la visión; no la reemplaza)  
**Fecha:** 16 agosto 2026 · **v2 (profunda)**  
**Pregunta central:** ¿cómo evolucionar Nat → **EkiA** sin romper la tesis de eki (evolución sin reescritura, WhatsApp/3G primero, soberanía progresiva)?  

**Canon de referencia (obligatorio):**

| Documento | Uso en esta investigación |
|-----------|---------------------------|
| `docs/VISION_TECNOLOGICA_EKI_2026_2035.md` | Norte 2035, arcos A–D, plano experiencia/inteligencia, capas de IA 0–4, mínimo privilegio, riesgos |
| `docs/NAT_GUIA_COMPLETA.md` | Contrato actual de Nat (agrónoma de bolsillo, solo-Nat vs LMS) |
| `docs/DOMAIN_ARCHITECTURE.md` | Bounded contexts: `agents_edu` vs `agents_commercial` |
| `docs/SEGURIDAD.md` · `docs/RUNBOOK_REDIS_CHROMA.md` · `docs/UMBRAL_ELASTICACHE.md` | Operación y umbrales |
| Skill `.cursor/skills/eki-nat/` | Checklist operativo Nat |

> **Regla de partida (visión cap. 4 + 13):** eki ya es **multi-agente de forma explícita**. La tentación del “gran agente único” choca con una decisión de producto ya acertada. EkiA debe **elevar la cara comercial/rural**, no fusionar tutores, PQRS, GEI y retención en un solo prompt.

---

## 0. Resumen ejecutivo (qué decidir)

1. **EkiA** = evolución de marca y robustez de **Nat** (agente técnico/comercial rural), no un reemplazo de toda la IA de eki.  
2. Arquitectura correcta: **una cara (EkiA) + orquesta de agentes/tools internos + HITL**, alineada a la visión (“asistiva y explícitamente multi-agente”).  
3. EkiA alimenta el **Arco A→B** de inteligencia territorial (señales `ContextoAgroSession` → eventos tipados → alertas agregadas), pero **no es** el Event Engine ni el IQ Rural.  
4. **IA propia** pertenece a capas 3–4 de la visión (2029–2035), condicionada a contratos, datasets documentados y evaluación. Construirla antes de Capa 0 (gobernanza) es el error más caro.  
5. **Una vía de marca · varias vías internas · varios contratos de producto · un gobierno de datos.**

---

## 1. Dónde encaja EkiA en la visión 2026–2035

La visión fija tres constantes: **continuidad tecnológica**, **evolución controlada**, **inteligencia territorial rural con soberanía progresiva**. EkiA es una pieza del **plano de experiencia** (conversación WhatsApp comercial) que produce señales para el **plano de inteligencia**.

```text
PLANO DE EXPERIENCIA (latencia / confiabilidad)
  WhatsApp educativo (*listo*, drip, tutor, PQRS, GEI)
  WhatsApp comercial  →  EkiA (hoy Nat)
  Portal / Aprende / Studio / Certificados / Admin

        │ emite eventos (contrato)
        ▼

PLANO DE INTELIGENCIA (completitud / trazabilidad)
  Event Engine → Lake → Features → Modelos → Alertas / IQ Rural / Gemelo
```

### 1.1 Preguntas que eki debe responder (visión cap. 3) y rol de EkiA

| Horizonte | Pregunta de eki | Rol de EkiA |
|-----------|-----------------|-------------|
| **2026** | ¿Cómo formamos en WhatsApp/3G y demostramos que ocurrió? | Secundario: no compite con LMS; sirve orgs solo-comercial |
| **2030** | ¿Qué ocurre en este municipio esta semana? | Primario como **productor de señales** (cultivo, zona, problema, plaga) tipificadas |
| **2035** | ¿Cómo se comporta el gemelo bajo escenarios? | Fuente histórica de demanda agronómica y práctica; no el simulador |

### 1.2 Mapeo a arcos (visión cap. 5)

| Arco | Qué construye eki | Qué debe hacer EkiA |
|------|-------------------|---------------------|
| **A · 2026–2027** Endurecer monolito + nervio de eventos | Firma Twilio, handlers, Redis/ElastiCache, outbox, taxonomía territorial v0 | Rename + orquestación explícita + `EventoIA` completo + tenancy duro + Chroma durable |
| **B · 2027–2029** Datos + inteligencia aplicada | Event Engine, lake, predicción, alertas v1, IQ Rural v1 | Clasificadores de consulta comercial → eventos `reporte.*` / `agro.*`; demanda por territorio |
| **C · 2029–2032** Gemelo + APIs | Simulación, APIs inteligencia, modelos especializados | Fine-tune lenguaje rural; RAG sigue mandando en hechos (precios/protocolos) |
| **D · 2032–2035** Soberanía LATAM | Modelos propios en dominios críticos | Inferencias críticas de campo bajo control eki; LLM externo = fallback no sensible |

**Degradación (regla de admisión de arcos):** si el LLM cae, EkiA responde con **reglas + catálogo + biblioteca**, no se calla. La inteligencia es aditiva; el canal es existencial.

---

## 2. Estado actual: eki ya eligió multi-agente

La visión (cap. 13) enumera agentes vivos con contratos distintos. Confundirlos es error de producto:

| Agente | Canal / superficie | Contrato | No debe hacer |
|--------|--------------------|----------|---------------|
| Tutor educativo (Darío/Claudia / RAG edu) | WA educativo / módulo | Pedagogía, avance, evaluación | Vender insumos |
| **Nat → EkiA** | WA comercial (`numero_whatsapp_nat`) | Agrónoma de bolsillo + catálogo + precio ref. | Avanzar *listo* / cobrar |
| PQRS | WA educativo (turno soporte) | Queja/solicitud | Secuestrar turno pedagógico |
| Formulario GEI | WA, sesión secuencial | Recolección estructurada (sin RAG abierto) | Conversación libre |
| Consultor retención | Portal Centro de Éxito | Explicar riesgo al coordinador | Hablar con el productor de campo |

**Bounded contexts** (`DOMAIN_ARCHITECTURE.md`): `agents_edu` ≠ `agents_commercial`. EkiA vive en comercial; no se fusiona con pedagógico.

Activos ya sembrados (visión cap. 2) que EkiA debe industrializar, no reinventar:

- `ContextoAgroSession` (municipio, vereda, lat/lon, cultivo, etapa, problema)
- Biblioteca / RAG comercial + Knowledge Studio (HITL)
- `ProductoCatalogo` / `ProductoComercial`
- `EventoIA` + replay AI Ops
- Open-Meteo por municipio
- Separación de línea Twilio destino

---

## 3. Investigación profunda: “gran agente”

### 3.1 Definición rigurosa

En marketing, “gran agente” = un solo chatbot que lo hace todo.  
En ingeniería seria, un sistema monolítico de agentes suele ser:

1. Router / classifier  
2. Tools con permisos  
3. Políticas y kill switches  
4. Memoria acotada  
5. Evaluación continua  

Si alguien vende “un solo system prompt para LMS + ventas + salud + legal”, no está vendiendo un gran agente: está vendiendo **deuda de gobernanza**.

### 3.2 Por qué seduce en eki

- Una marca (EkiA) más fuerte que “Nat/Nati”.  
- Menos explicación al productor (“habla con eki”).  
- Narrativa de plataforma única.  
- Menos pantallas en portal.

### 3.3 Por qué choca con la visión

| Principio visión | Conflicto con gran-agente monolítico |
|------------------|--------------------------------------|
| Multi-agente explícito (cap. 13) | Fusionar tutores + Nat destruye contratos |
| Mínimo privilegio (cap. 4.11 / 18) | Un cerebro “con acceso a todo” es la arquitectura **prohibida** |
| WhatsApp/3G primero | Contexto enorme = latencia y costo |
| Inteligencia aditiva | Un fallo de prompt tumba varios productos |
| Separación identidad/conocimiento | Un prompt “rico” arrastra PII al vendor |

### 3.4 Veredicto

**Gran agente como UX/branding: sí.**  
**Gran agente como un único cerebro con acceso amplio a datos: no, y está prohibido por visión.**

---

## 4. Investigación profunda: agentes individuales

### 4.1 Lo que eki ya demostró

Separar agentes por contrato reduce errores de producto (Nat no avanza cursos; GEI no improvisa con RAG; retención no habla al estudiante). Eso debe **preservarse**.

### 4.2 Especialistas internos bajo la cara EkiA

Dentro de la línea comercial, EkiA no es un solo prompt: es un **orquestador** con especialistas:

| Especialista interno | Input permitido (matriz visión) | Output | Kill / límite |
|----------------------|----------------------------------|--------|---------------|
| **Diagnóstico de campo** | cultivo, zona, síntoma, foto, historial agro seudonimizado | Hipótesis + preguntas | No certeza falsa; no dosis letales sin etiqueta |
| **RAG org** | biblioteca `cliente=` + general eki etiquetada | Pasajes con `fuente_id` | Sin fuente → no afirma |
| **Catálogo / precios** | `ProductoCatalogo` / lista oficial | 1–3 opciones + precio ref. | No inventa stock/marcas |
| **Clima** | Open-Meteo por municipio | Bloque verificado inyectado | No “predicción mágica” |
| **Riesgo / compliance** | flags habeas, opt-out, toxicidad, agroquímico | Bloqueo / escalamiento | Prioridad sobre el LLM |
| **HITL / humano** | cola Knowledge Studio | Corrección publicable | SLA semanal |
| **Señal territorial** | tags → evento anonimizado | `EventoIA` / futura familia `reporte` | Sin PII en agregados |

### 4.3 Fortalezas vs debilidades (a escala década)

**Fortalezas:** blast radius bajo; eval por dominio; PI separable (contenido cliente vs eki); encaje multi-tenant; alineado a usuarios DB `eki_agro` vs `eki_tutor`.

**Debilidades:** orquestación; handoffs; ops debe entender colas; riesgo de ping-pong si el router es flojo.

### 4.4 Veredicto

Los agentes individuales son la **base correcta**. La cara única EkiA es la capa de experiencia que el usuario ve.

---

## 5. Decisión arquitectónica recomendada (híbrido canónico)

```text
Productor (WhatsApp comercial)
        │
        ▼
┌───────────────────┐
│  EkiA (cara UX)   │  copy, tono, agrónoma de bolsillo
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Orquestador       │  intención + urgencia + política
│ (servicio eki)    │  NUNCA: SQL libre al LLM
└─────────┬─────────┘
          │
          ├─► tools de dominio (catálogo, RAG, clima, foto)
          ├─► agente riesgo (veto)
          └─► HITL si hace falta
          ▼
   EventoIA / telemetría / (Arco B) eventos territoriales
```

### 5.1 Principios operativos (derivados de visión)

1. **El modelo recibe texto preparado, no credenciales** (cap. 18.3).  
2. **Catálogo y documentos mandan sobre el LLM** en hechos (precios, protocolos).  
3. **Sin fuente → Plan B tipado** (manejo cultural / principio activo genérico), nunca marca inventada.  
4. **Solo-Nat ≠ LMS** (`portal_productos`).  
5. **Capa 0 antes que modelo nuevo** (trazas, prompts versionados, costos, regresión).  
6. **Rename gradual:** UI EkiA; código `nat_*` con alias meses.  
7. **Degradación:** LLM down → reglas + catálogo.

### 5.2 Relación con “una vía o varias”

| Dimensión | Decisión |
|-----------|----------|
| Marca / cara | **Una** (EkiA) |
| Agentes de producto eki | **Varias** (tutor, EkiA, PQRS, GEI, retención) |
| Tools bajo EkiA | **Varias** |
| Contratos B2B | **Varias** (`cursos`, `nat`/`ekia`, `gei`, `empleabilidad`) |
| Gobierno de datos / eventos | **Uno** |
| Proveedores LLM | **Varios con interfaz estable** → soberanía progresiva |

---

## 6. Ruta a futuro alineada a capas de IA (visión cap. 13)

### Capa 0 — Gobernanza (2026, inmediata)

Antes de “EkiA robusto” o IA propia:

- [ ] Trazas `EventoIA` + replay en toda interacción comercial  
- [ ] Prompts versionados en repo (no literales dispersos)  
- [ ] Suite adversaria (alucinación, tenancy, inyección de prompt)  
- [ ] Costo por agente  
- [ ] Matriz de tools: qué puede leer / escribir / enviar  
- [ ] Kill switch (dejar de llamar LLM sin redeploy)  
- [ ] Separación identidad: prompts sin nombre/teléfono/cédula  

### Capa 1 — Clasificación (2026–2027) — donde EkiA más aporta al territorio

Convertir chat libre de campo en **eventos tipados** (cultivo, plaga, escasez, barrera…), con confianza.  
Salida = eventos, no prosa. Esto habilita el patrón:  
**señal → correlación → alerta → acción** (cap. 3 / 14).

### Capa 2 — Predicción (2027–2029)

- Demanda comercial por territorio/temporada  
- Probabilidad de escalamiento HITL  
- (Con Event Engine) aporte a clusters agropecuarios  

### Capa 3 — Especialización (2029–2032)

Fine-tune / adaptadores sobre español rural y agronomía LATAM.  
**RAG no se abandona** para hechos. Visión: modelo para comprender; recuperación para afirmar.

### Capa 4 — Modelos propios (2032–2035)

Solo en dominios que eki vende como propios (clasificación territorial, lenguaje de campo crítico).  
Objetivo ≠ fundacional gigante; objetivo = **control datos → modelo → decisión**.

---

## 7. Nube, ciberseguridad y agente rural (profundización)

### 7.1 Nube — costuras baratas ahora (visión cap. 17)

Estado real hoy (también visto en QA ago-2026): Redis local, Chroma bajo path de app, webhook async apagado, 1 instancia EB. Eso **soporta carga actual** pero no es suelo firme para EkiA a escala.

Orden de dolor medido (no moda):

1. Observabilidad + backups restaurados  
2. ElastiCache (obligatorio al 2ª instancia; antes si colas importan)  
3. Vector store durable (EFS o servicio; nunca solo `/var/app/current`)  
4. Separar worker/beat de latencia web  
5. Webhook Celery bajo picos  
6. Lake/outbox cuando taxonomía territorial exista  

### 7.2 Ciberseguridad — EkiA en la matriz de permisos

Usuario conceptual `eki_agro` (visión 18.5):

| Puede | No puede |
|-------|----------|
| Cultivo, clima, plagas, catálogo org, contexto agro, biblioteca org | Nómina, otros clientes, identidad completa, facturación, conversaciones educativas ajenas |

Reglas específicas EkiA:

- Tenancy: org A no lee biblioteca/catálogo B (tests CI).  
- Webhook comercial: HMAC + `compare_digest`.  
- Foto de cultivo: retención y minimización.  
- Tool write/send: rate limit + auditoría + kill switch (cap. 13).  
- Prompt injection desde docs RAG y desde el usuario.

### 7.3 Agente rural — restricciones de diseño producto

- Respuestas cortas; una pantalla.  
- Foto mala → preguntas, no certeza.  
- Agroquímico → etiqueta + técnico de zona.  
- Red 3G → no depender de media pesada para el valor.  
- Confianza territorial > elocuencia del modelo.

---

## 8. Riesgos de negocio y riesgos a futuro

### 8.1 Riesgos de negocio (corto plazo)

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Alucinación agronómica | Reputación / daño de cultivo | RAG + veto + HITL |
| Mezclar LMS y comercial | Confusión contractual | `portal_productos` + líneas WA |
| Overclaim “todo lo sabe” | Churn | Copy honesto + escalamiento |
| Costo tokens | Margen | RAG corto, límites, caché |
| Rename brusco | Romper ops/webhooks | Alias `nat` |
| Señales territoriales sin ética | Pérdida de licencia social | Agregación, k-anonimato, opt-in |

### 8.2 IA propia — cuándo sí / cuándo no

**NO** mientras falte Capa 0, contratos de entrenamiento, o aislamiento de PII.  
**SÍ** cuando existan datasets con ficha de procedencia (visión cap. 11), exclusión contractual de orgs que no autorizan, eval reproducible y serving bajo control eki.

### 8.3 Propiedad intelectual — capas a separar ya

1. Contenido del cliente (manuales, precios) — cliente dueño; eki custodio  
2. Contenido general eki (`cliente_id=0`) — PI eki  
3. Código, prompts, orquestación — PI eki  
4. Salidas del modelo — definir en contrato  
5. Fuentes externas (Agrosavia, ICA) — términos; no re-publicar como propio  
6. Pesos/fine-tunes — activo a proteger (visión 18.6)

### 8.4 Custodia de datos — mínimo serio

Inventario: chats comerciales, fotos, geo, embeddings, logs Twilio, candidatas HITL.  
Retención por clase + borrado fin de contrato.  
Export/portabilidad + destrucción certificable.  
Prod ≠ eval.  
Auditoría de acceso staff.

### 8.5 Riesgos técnicos de visión (cap. 26) aplicados a EkiA

- Dependencia total de LLM externos en dominio crítico  
- Chroma/Redis no durables → pérdida de conocimiento  
- God objects (`views`, prompts mezclados con reglas) → EkiA debe extraer servicios  
- API/herramientas sin auth → no repetir el anti-patrón LXP  

---

## 9. Escenarios de decisión (para comité)

### Escenario A — “Un solo superbot EkiA para todo eki”

**Rechazar.** Viola multi-agente, mínimo privilegio y contratos de producto.

### Escenario B — “Solo rebrand Nat → EkiA sin orquestación”

**Insuficiente.** Mejora marca; no reduce alucinación ni prepara territorio.

### Escenario C — “Híbrido cara EkiA + tools + HITL + eventos” (recomendado)

**Aprobar** como ruta Arco A→B. Encaja visión.

### Escenario D — “Entrenar modelo propio en 2026 con todos los chats”

**Rechazar** hasta Capa 0 + contratos + seudonimización + datasets documentados.

---

## 10. Criterios go / no-go

### GO para invertir en EkiA robusto (Arco A)

- [ ] Tenancy RAG/catálogo en tests  
- [ ] Smoke: saludo → rutina/foto → precio → Plan B en 1 org piloto  
- [ ] `EventoIA` + fuente_usada en respuestas  
- [ ] Política PI/retención de 1–2 páginas firmable  
- [ ] HITL semanal con dueño  
- [ ] Plan escrito ElastiCache + vector durable  
- [ ] Kill switch LLM  

### NO-GO

- [ ] “Que conteste de todo” sin fuentes  
- [ ] Entrenar con chats sin cláusula  
- [ ] Fusionar tutor educativo y EkiA en un cerebro  
- [ ] LLM con acceso directo a PostgreSQL  
- [ ] Alertas territoriales con PII en paneles  

---

## 11. Plan de trabajo sugerido (18–24 meses, sin comprometer deploy)

### 0–3 meses

- Aprobar nombre EkiA + matriz rename (UI → docs → código lento)  
- Capa 0: eval adversaria + costos + prompts versionados  
- Endurecer tenancy y degradación catálogo  

### 3–9 meses (Arco A)

- Orquestador + tools formales  
- Persistencia vectorial + Redis durable según umbral  
- Emisión sistemática de señales tipificadas (precursor familia comercial/territorial)  

### 9–24 meses (entrada Arco B)

- Clasificadores consulta → eventos  
- Primeros agregados territoriales agro (sin PII)  
- Score demanda / HITL en sombra  

### Post-24 meses

Seguir capas 2–4 de visión; no adelantar soberanía de modelo sin lake y contratos.

---

## 12. Conclusiones

1. La visión ya resolvió el falso dilema: **multi-agente es acierto**; el “gran agente” solo vale como **cara**.  
2. **EkiA** es el nombre y el endurecimiento de Nat dentro de `agents_commercial`, productor de señales para inteligencia territorial — no el sustituto del LMS ni del Event Engine.  
3. El futuro de eki (IQ Rural, alertas, gemelo) **necesita** conversaciones de campo tipificadas; EkiA es una de las mejores fuentes si se gobierna.  
4. **IA propia** es soberanía progresiva (capas 3–4), no el siguiente sprint.  
5. Construir sin Capa 0, sin PI/custodia y sin mínimo privilegio no es ambición: es riesgo reputacional en territorio.

---

## 13. Decisiones cerradas (16 ago 2026)

Estas respuestas quedan como **acuerdo de trabajo** hasta que Legal/dirección las enmienden por escrito.

### D1 — Alcance de marca EkiA

**Decisión:** EkiA = evolución de **Nat / Nati** (agente comercial-rural). **No** es paraguas de tutor, PQRS, GEI ni retención en 2026–2027.

| Incluye | Excluye (por ahora) |
|---------|---------------------|
| Línea WhatsApp comercial, portal solo-Nat/EkiA, biblioteca/catálogo, diagnóstico de campo | Tutor educativo, *listo*/LMS, formulario GEI, Centro de Éxito |

Revisar ampliación de marca solo tras Capa 0 estable y 1 piloto comercial exitoso.

### D2 — Orgs piloto para señales agregadas (Arco B precursor)

**Decisión:** arrancar con **clientes `portal_productos` que incluyen `nat`** (solo-Nat o combo con nat), priorizando 1–2 orgs con:

- biblioteca propia cargada,
- catálogo o Plan B acordado,
- consentimiento contractual de **agregados** (no chats crudos).

Hasta firmar anexo: **solo métricas internas eki** (conteos seudonimizados en admin), sin tablero municipal al cliente.

*Acción pendiente comercial:* nombrar las 1–2 orgs concretas en la próxima reunión Growth/Ops.

### D3 — Cláusula de entrenamiento / IA propia

**Decisión por defecto: prohibido entrenar con datos del cliente** salvo **opt-in escrito** (anexo).

| Uso | Default |
|-----|---------|
| Operar EkiA (RAG, respuesta, logs operativos) | Permitido bajo contrato de servicio |
| Agregados territoriales k-anónimos internos | Permitido si el contrato de programa lo contempla |
| Entrenar / fine-tune con chats, fotos o embeddings del cliente | **Prohibido** hasta opt-in |
| Dataset eki general (`cliente_id=0`) | PI eki; no mezclar contenido de cliente opt-out |

### D4 — Dueño HITL Knowledge Studio

**Decisión:**

| Rol | Responsabilidad |
|-----|-----------------|
| **Content (dueño primario)** | Calidad de fichas, aprobación/rechazo de candidatas, tono agrónomo |
| **Ops / CS** | Cola semanal, SLA, escalamiento a humano en campo |
| **Growth** | Prioriza orgs/piloto comercial; no aprueba conocimiento técnico solo |
| **Sec / Legal** | Vetos de PII / PI / fuentes |

Ritmo mínimo: **revisión semanal** con acta corta (qué se publicó / qué se rechazó).

### D5 — Presupuesto de tokens por org

**Decisión v0 (operativa, ajustable):**

| Señal | Umbral | Acción |
|-------|--------|--------|
| Soft | ~80% del cupo mensual estimado de la org | Aviso interno Ops + log |
| Hard | 100% del cupo | Degradar a reglas + catálogo + Plan B (sin LLM) hasta reset de ciclo |
| Pico anómalo (1 h) | >3× media horaria de la org | Rate limit + revisión inyección/abuso |

Cupo inicial sugerido: definir en contrato comercial (ej. bandas S/M/L). Hasta tener facturación por org: **límite global de alerta en admin** + hard limit por org en código cuando exista campo de cuota.

---

## 14. Cierre del día (16 ago 2026) — vínculo QA

Ver sección operativa del chat / informe QA del mismo día: pruebas clave verdes, migraciones generadas, Apiarios y media_wa_apto quedan para siguiente jornada.

---

*Documento de investigación v2.1. Complementa `VISION_TECNOLOGICA_EKI_2026_2035.md`; no autoriza deploy, rename en producción ni entrenamiento de modelos por sí solo.*
