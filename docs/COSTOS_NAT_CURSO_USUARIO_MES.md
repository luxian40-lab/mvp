# Costos aproximados — 1 usuario / mes (curso 5 módulos + 40 consultas Nat)

**Fecha:** 2026-09-14  
**Alcance:** costo variable de **canal + IA** por un estudiante/usuario activo.  
**No incluye:** sueldos, EB/RDS fijos, S3 storage, margen comercial, IVA.  
**Moneda:** USD y COP (TRM referencial **4 000 COP/USD** — ajustar al día).

> “Exacto” en ops = **fórmula + supuestos explícitos**. Las tarifas Meta/Twilio/OpenAI cambian; esto es el modelo contable eki, no una factura.

---

## 1. Escenario pedido

| Pieza | Cantidad |
|-------|----------|
| Curso | **5 módulos** en el mes |
| Consultas Nat | **40** preguntas del usuario (cuota diaria típica eki ~40/día; aquí = **40/mes**) |
| Motor Nat (defaults código) | Router `gpt-5-nano` + respuesta `gpt-5-mini` (+ a veces `gpt-5` técnico / visión) |

Hipótesis de mensajes WhatsApp (alineado a `ESTIMACION_CONVERSACIONES_USUARIO_MES.md`):

| Flujo | Mensajes aproximados / mes |
|-------|----------------------------|
| Curso (contenido + *listo* ida/vuelta) | **~58** (usable 5 mód., L≈2) |
| Nat (40 preg. × 2 bubbles) | **80** |
| **Total bubbles WA** | **~138** |

De esos ~138:

- ~40 **inbound** (gratis Meta; Twilio suele cobrar handling)
- ~98 **outbound** (Twilio + Meta según categoría/ventana)

---

## 2. Tarifas usadas (Colombia, destinatario +57)

### WhatsApp (Twilio + Meta pass-through)

| Concepto | USD / mensaje | Notas |
|----------|---------------|--------|
| Twilio handling | **0,005** | Inbound y outbound |
| Meta marketing (plantilla) | **0,0125** | CO |
| Meta utility / servicio | **~0,0008** | CO; desde **1 oct 2026** Meta cobra también servicio en ventana 24h (antes a menudo $0 Meta en ventana) |

Referencias: [Twilio WhatsApp pricing](https://www.twilio.com/en-us/whatsapp/pricing), rate cards Meta CO 2026.

### OpenAI (API oficial, sep 2026)

| Modelo (uso Nat) | USD / 1M input | USD / 1M output |
|------------------|----------------|-----------------|
| `gpt-5-nano` (router) | **0,05** | **0,40** |
| `gpt-5-mini` (respuesta) | **0,25** | **2,00** |
| `gpt-5` (técnico) | **1,25** | **10,00** |

Fuente: docs OpenAI / rate cards públicas 2026.

**Tokens por consulta Nat (caso base):**

- Router: 800 in / 50 out  
- Respuesta mini: 3 500 in / 700 out  
- **10 %** de consultas usan `gpt-5` técnico en vez de mini

---

## 3. Cálculo WhatsApp — 1 usuario / mes

### 3.1 Twilio handling (siempre)

\[
138 \times 0{,}005 = \mathbf{0{,}69\ USD}
\]

### 3.2 Meta (dos mundos)

**A) Hoy / pre–1 oct 2026 (ventana servicio Meta ~$0 en free-form)**  

Asumimos: 5 plantillas utility/marketing de reenganche + resto free-form en ventana tras *listo*/Nat.

| Ítem | Cant. | Meta USD | Subtotal |
|------|-------|----------|----------|
| Plantillas marketing (ej. aviso) | 2 | 0,0125 | 0,025 |
| Plantillas utility | 3 | 0,0008 | 0,0024 |
| Free-form en ventana | 93 | 0 | 0 |
| **Meta** | | | **≈ 0,03 USD** |

**B) Desde 1 oct 2026 (servicio ≈ utility CO)**  

Casi todo outbound paga ~0,0008 Meta + plantillas marketing más caras:

| Ítem | Cant. | Meta USD | Subtotal |
|------|-------|----------|----------|
| Marketing | 2 | 0,0125 | 0,025 |
| Utility/servicio outbound | 96 | 0,0008 | 0,0768 |
| **Meta** | | | **≈ 0,10 USD** |

### 3.3 Total canal WA / usuario·mes

| Escenario | Twilio | Meta | **Total WA** | **COP (~4 000)** |
|-----------|--------|------|--------------|------------------|
| Pre-oct 2026 | 0,69 | 0,03 | **0,72 USD** | **~$2 900** |
| Post-oct 2026 | 0,69 | 0,10 | **0,79 USD** | **~$3 200** |

---

## 4. Cálculo IA Nat — 40 consultas / mes

### 4.1 Caso base (90 % mini + 10 % gpt-5)

**1 consulta mini** (router + mini):

\[
\begin{align*}
\text{nano} &= 800\times0{,}05/10^6 + 50\times0{,}40/10^6 = 0{,}00006\\
\text{mini} &= 3500\times0{,}25/10^6 + 700\times2{,}00/10^6 = 0{,}002275\\
\text{total} &= \mathbf{0{,}00234\ USD}
\end{align*}
\]

**1 consulta técnica** (router + gpt-5):

\[
0{,}00006 + 3500\times1{,}25/10^6 + 700\times10/10^6 = \mathbf{0{,}01144\ USD}
\]

**40 consultas:**

\[
36\times0{,}00234 + 4\times0{,}01144 = 0{,}084 + 0{,}046 = \mathbf{0{,}13\ USD}
\]

Rango (todo mini ↔ mucho técnico/visión): **0,09 – 0,50 USD** / usuario·mes solo Nat LLM.

### 4.2 Tutor curso (4 interacciones IA pedagógicas)

Modelo barato / mini: **≈ 0,01 USD**.  
Si reutilizan stack Nat: **≈ 0,01 – 0,05 USD**.

---

## 5. Total por usuario / mes (número pedido)

| Bloque | USD | COP (~4 000) |
|--------|-----|--------------|
| WhatsApp (post-oct 2026) | **0,79** | ~3 160 |
| Nat LLM (40 consultas) | **0,13** | ~520 |
| Tutor curso (4) | **0,01** | ~40 |
| **TOTAL variable** | **≈ 0,93 USD** | **≈ $3 700 COP** |

Redondeo operativo: **~1 USD / usuario·mes** (±20 % según marketing templates, reintentos media y % de `gpt-5`).

---

## 6. Escalado rápido

| Usuarios activos / mes | Costo variable ≈ |
|------------------------|------------------|
| 25 (cohorte tipo Zoraida) | **~25 USD** (~100 000 COP) |
| 100 | **~100 USD** |
| 500 | **~500 USD** |
| 1 000 | **~1 000 USD** |

Fórmula:

\[
C_{\text{mes}} \approx N \times \bigl(0{,}005 \times M_{\text{bubbles}} + Meta_{\text{out}} + LLM_{\text{Nat40}} + LLM_{\text{tutor}}\bigr)
\]

Con \(M_{\text{bubbles}} \approx 138\), \(LLM_{\text{Nat40}} \approx 0{,}13\).

---

## 7. Qué NO está en el 1 USD

- Generación Course Engine (video/voz ElevenLabs / imágenes)  
- Indexación Chroma / storage S3  
- Campañas masivas marketing adicionales  
- HITL humano (Knowledge Studio)  
- Infra EB/RDS/Redis  

---

## 8. Cómo volverlo “factura real” el mes que viene

1. Export Twilio usage (WhatsApp) del mes.  
2. Export OpenAI usage filtrado por proyecto Nat.  
3. Contar en `WhatsappLog`: OUTGOING/INCOMING + `agente_usado=BOT_COMERCIAL`.  
4. Sustituir precios de la §2 por los de la factura.

---

**Dueño de mantenimiento:** Data + Growth · revisar tarifas cada vez que Meta/OpenAI publiquen cambio.
