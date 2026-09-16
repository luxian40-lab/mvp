# Estimación: conversaciones mínimas por usuario / mes (curso + Nat)

**Alcance:** orden de magnitud para planificación (Twilio / ops / producto).  
**No es** telemetría real de prod; son **mínimos razonables** con un curso activo.  
**Canal:** WhatsApp (curso pedagógico + Nat).  
**Fecha:** 2026-09-11

---

## 1. Definiciones (para no mezclar peras con manzanas)

| Concepto | Qué contamos aquí |
|----------|-------------------|
| **Mensaje** | Un bubble WhatsApp (entrada **o** salida). |
| **Turno / interacción** | Un mensaje del usuario que dispara respuesta del sistema. |
| **Conversación (día útil)** | Día en que el usuario escribe ≥1 mensaje relevante (curso o Nat). |
| **Conversación (hilo mensual)** | Conjunto de turnos del mismo usuario en el mes (curso + Nat). |

En eki el curso avanza con ***listo*** (y a veces A–D / envíos). Nat es otro hilo (preguntas agro/comercial).

---

## 2. Hipótesis del escenario (las que pediste)

| Variable | Valor usado |
|----------|-------------|
| Módulos del curso | **5** (piso) a **10** (techo del ejemplo) |
| Mensajes de contenido de curso (sistema → usuario) | **~30** en el mes (orden de magnitud del ejemplo) |
| Interacciones con IA del curso (tutor / eval / ayuda) | **4** (mínimo del ejemplo) |
| Conversación adicional con **Nat** | Sí — se suma aparte (mínimo + escenario “más Nat”) |

Supuestos operativos eki:

- ~**1 *listo* (o avance) por bloque/sección** relevante; no reenvíos masivos.
- Curso **no** se completa entero en 1 día: ritmo mensual realista.
- Nat **no** usa el tope técnico (hoy cuota ~40 preguntas/día); aquí usamos uso **mínimo / bajo**.

---

## 3. Cuentas — solo curso (sin Nat)

### 3.1 Reparto orientativo de los ~30 mensajes de salida (contenido)

Si el mes entrega ~30 mensajes de material:

| Curso | Módulos | Mensajes salida / módulo (aprox.) |
|-------|---------|-----------------------------------|
| Corto | 5 | 30 ÷ 5 = **6** |
| Medio-largo | 10 | 30 ÷ 10 = **3** |

Eso es **contenido outbound**. Falta lo que escribe el usuario.

### 3.2 Entradas mínimas del usuario en curso

| Concepto | Fórmula piso | 5 módulos | 10 módulos |
|----------|--------------|-----------|------------|
| Avances (*listo* / ok) | ≥ 1 por módulo (muy piso) | **5** | **10** |
| Más realista (varias secciones/módulo) | ~2–3 *listo*/módulo | **10–15** | **20–30** |
| Interacciones IA curso (ejemplo dado) | fijas | **4** | **4** |

**Piso estricto (usuario escribe poco):**

\[
\text{entradas curso mín} \approx \text{módulos} + \text{IA curso}
\]

- 5 módulos: \(5 + 4 = \mathbf{9}\) turnos de usuario  
- 10 módulos: \(10 + 4 = \mathbf{14}\) turnos de usuario  

**Con secciones (mínimo “usable” en WA eki):**

\[
\text{entradas curso} \approx 2\times\text{módulos} + \text{IA curso}
\]

- 5 módulos: \(10 + 4 = \mathbf{14}\)  
- 10 módulos: \(20 + 4 = \mathbf{24}\)  

### 3.3 Mensajes totales del hilo curso (ida + vuelta)

Aprox.: cada entrada de usuario genera ≥1 respuesta del bot (a menudo más, por multi-msg de material).

| Escenario | Entradas usuario | Salidas (contenido + acuses) | **Total mensajes curso / mes** |
|-----------|------------------|------------------------------|--------------------------------|
| Piso 5 mód. | 9 | ~30 contenido + ~9 acuses ≈ 39 | **~48** |
| Piso 10 mód. | 14 | ~30 + ~14 ≈ 44 | **~58** |
| Usable 5 mód. | 14 | ~30 + ~14 ≈ 44 | **~58** |
| Usable 10 mód. | 24 | ~30 + ~24 ≈ 54 | **~78** |

> Si el “30” del ejemplo ya incluye **todo** lo outbound (contenido + CTAs), baja el total ~10–20%. El orden de magnitud se mantiene: **~50–80 mensajes/mes** solo curso en un mes activo.

### 3.4 “Conversaciones” de curso / mes (días útiles)

Si el usuario estudia **2–4 días** en el mes (mínimo realista):

| Ritmo | Días con actividad curso | ≈ conversaciones-día curso |
|-------|--------------------------|----------------------------|
| Muy bajo | 2 | **2** |
| Bajo | 4 | **4** |
| Moderado (5–10 mód. repartidos) | 6–10 | **6–10** |

---

## 4. Cuentas — Nat (adicional)

Nat es **otro** flujo (preguntas del usuario → respuesta Nat). No avanza el curso.

### 4.1 Mínimo Nat en el mes

| Escenario Nat | Preguntas usuario / mes | Respuestas Nat / mes | **Mensajes Nat / mes** | Conversaciones-día Nat |
|---------------|-------------------------|----------------------|------------------------|-------------------------|
| Casi nada | 2 | 2 | **4** | 1–2 |
| Bajo (recomendado como “mínimo con uso”) | 8 | 8 | **16** | 2–4 |
| “Más conversación con Nat” | 20 | 20 | **40** | 5–10 |
| Activo (aún bajo el techo diario) | 40 | 40 | **80** | 8–15 |

Tope técnico de referencia en plataforma: orden **~40 preguntas Nat / 24 h** por teléfono (cuota). Un mes “activo diario” podría llegar a cientos; **no** es el mínimo.

### 4.2 Mezcla curso + Nat (lo que pediste)

**Caso A — mínimo del ejemplo + Nat bajo**

- Curso usable 5 módulos: ~58 mensajes  
- Nat bajo: ~16 mensajes  
- **Total ≈ 74 mensajes / mes**  
- Conversaciones-día: ~4 curso + ~3 Nat ≈ **~5–7 días** con tráfico (pueden solaparse → **~4–7 días únicos**)

**Caso B — 10 módulos + más Nat**

- Curso usable 10 módulos: ~78 mensajes  
- Nat “más conversación”: ~40 mensajes  
- **Total ≈ 118 mensajes / mes**  
- Conversaciones-día: ~8 curso + ~6 Nat → **~8–12 días únicos**

**Caso C — piso absoluto (casi no habla)**

- Curso piso 5 mód. + 4 IA: ~48 mensajes  
- Nat casi nada: ~4 mensajes  
- **Total ≈ 52 mensajes / mes**  
- **~2–3 días** de conversación en el mes  

---

## 5. Tabla resumen (mínimos)

| Perfil | Módulos | IA curso | Nat (preg./mes) | Mensajes totales / mes | Días con conversación / mes |
|--------|---------|----------|-----------------|------------------------|-----------------------------|
| Piso absoluto | 5 | 4 | 2 | **~50** | **2–3** |
| Ejemplo base + Nat bajo | 5 | 4 | 8 | **~70–80** | **4–7** |
| Curso largo + más Nat | 10 | 4 | 20 | **~110–120** | **8–12** |
| Curso largo + Nat activo | 10 | 4 | 40 | **~150–160** | **10–15** |

---

## 6. Fórmulas listas para reutilizar

Sea:

- \(M\) = número de módulos tocados en el mes  
- \(L\) = *listo*/avances por módulo (usar **1** piso, **2** usable)  
- \(I\) = interacciones IA curso en el mes (ej. **4**)  
- \(N\) = preguntas Nat en el mes  
- \(C\) = mensajes de contenido outbound del curso (ej. **30**)

Entonces:

\[
E_{\text{curso}} = L\cdot M + I
\]

\[
\text{Mensajes}_{\text{curso}} \approx C + E_{\text{curso}} + E_{\text{curso}}
= C + 2(L\cdot M + I)
\]

(el segundo \(E\) aproxima ≥1 respuesta por turno de usuario)

\[
\text{Mensajes}_{\text{Nat}} \approx 2N
\]

\[
\text{Mensajes}_{\text{mes}} \approx C + 2(L\cdot M + I) + 2N
\]

**Ejemplo numérico (5 mód., L=2, I=4, C=30, N=8):**

\[
30 + 2(2\cdot5 + 4) + 2\cdot8 = 30 + 28 + 16 = \mathbf{74}
\]

**Ejemplo (10 mód., L=2, I=4, C=30, N=20):**

\[
30 + 2(2\cdot10 + 4) + 2\cdot20 = 30 + 48 + 40 = \mathbf{118}
\]

---

## 7. Cómo leer esto en negocio / Twilio

1. **Mínimo serio con curso vivo:** ~**50–80 mensajes/usuario/mes** (curso) + Nat bajo.  
2. **Con “más Nat”:** súbele **~40 mensajes** (20 preguntas ida/vuelta).  
3. **Conversaciones/mes** (días útiles): **mínimo 2–3**; con ritmo normal de 5–10 módulos + Nat **~5–12**.  
4. No confundir con el **techo** Nat (~40/día): eso es límite de abuso, no el piso de producto.

---

## 8. Fuera de este cálculo

- Campañas / push / habeas / onboarding puntual  
- Certificados, PQRS, GEI, empleabilidad  
- Reintentos de media (63019) y *reenvía video*  
- Multi-curso (menú) o sandbox menú Nat|Cursos  

Si hace falta, el siguiente paso es bajar esto a **números reales** desde `WhatsappLog` (curso vs `BOT_COMERCIAL`) por cohorte.
