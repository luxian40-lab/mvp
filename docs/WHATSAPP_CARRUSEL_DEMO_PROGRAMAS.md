# Carrusel demo WhatsApp — vitrina de programas (mismo número vs número futuro)

**Estado:** carrusel **v2 copy orgánico** · `HX95fc0a1493b5def0937d1b068afb93f6`  
**Fecha:** 21 agosto 2026  
**Demo activa:** *Tome las riendas de su dinero*. Resto = página web (Ver más).

Complementa el flujo LMS. **No** sustituye `listo` ni onboarding de organizaciones.

---

## 1. Decisión de producto (ahora)

| Card | Rol |
|------|-----|
| Agrosavia | Solo vitrina |
| Fedepalma | Solo vitrina |
| **eki · Tome las riendas de su dinero** | **Demo** (CTA lead) |
| Profamilia | Solo vitrina |

**Quién lo ve:** teléfonos que **no** existen como `Estudiante` (`ProspectoB2B`).  
**Canal ahora:** mismo número educativo.  
**Entrada al carrusel:** en el menú de ventas, opción **4️⃣ Ver programas (demo)** (también vale escribir `4` o `programas`).

### Flujo completo (sin ficha)

```text
1. Usuario escribe al número eki (hola, lo que sea)
2. eki responde MENÚ:
     1 empresa · 2 web · 3 soy estudiante · 4 ver programas (demo)
3. Si escribe 4 → CARRUSEL (plantilla HX o lista texto)
4. En cada card: **Ver más** (web) | **Solo info** o **Quiero demo** (chat)
5. Riendas + Quiero demo → mensaje de cómo hacer la demo (*1* + correo)
```

---

## 2. ¿Por qué a futuro lo ideal es **otro número**?

Hoy el mismo número funciona **si** el código separa bien:

```text
¿Hay Estudiante con ese teléfono?
  SÍ → LMS (listo, módulos, reto, PQRS…)
  NO → prospecto / vitrina / ventas  ← carrusel demo
```

A escala, un segundo número es mejor: menos riesgo de mezclar leads con alumnos, keywords claras, reputación Meta/opt-out por propósito, métricas Growth vs Learning, y el mismo patrón que Nat/eki.ia (línea aparte).

**Norte:** Número A aprendizaje · Número B vitrina/captación · (opc.) C Nat.

Mientras tanto: mismo número + gate “solo si no hay Estudiante” es aceptable.

---

## 3. Plantilla `twilio/carousel` — **2 botones** + body llamativo

### 3.0 Guía práctica: qué poner en cada cosa (Twilio / Meta)

Piensa la plantilla como **un mensaje de arriba + 4 tarjetas deslizables**.

| Dónde en Twilio | Qué es | Qué debes colocar (demo eki) |
|-----------------|--------|------------------------------|
| **Friendly name** | Nombre interno (solo tú lo ves) | `eki_demo_carrusel_programas_v2` |
| **Language** | Idioma | `Spanish (es)` |
| **Content type** | Tipo de plantilla | `twilio/carousel` (Carrusel) |
| **Body** (texto arriba) | Lo primero que lee el usuario **antes** de deslizar | El texto A de la §3.3 (llamativo) |
| **Card 1…4 → Media** | Foto de la tarjeta | URL HTTPS pública de la imagen (jpg/png). Las 4 del mismo tamaño |
| **Card → Title** | Título en negrita de la card | Ej. `eki · Riendas` (corto) |
| **Card → Body** | Subtexto bajo el título | 1 línea de beneficio (title+body ≤ 160 caracteres juntos) |
| **Card → Button 1** | Primer botón | Tipo **Quick reply**. Title: `Ver descripción`. **ID** = `desc_agrosavia` / `desc_fedepalma` / `desc_riendas` / `desc_profamilia` |
| **Card → Button 2** | Segundo botón | Tipo **Quick reply**. Vitrina: title `Solo info`, id `info_…`. Riendas: title `Quiero demo`, id `in_riendas` |

**El ID del botón es lo que hace funcionar eki:** cuando el usuario toca, Twilio manda ese `id` al webhook (`ButtonPayload`). El código ya espera exactamente:

- `desc_agrosavia`, `desc_fedepalma`, `desc_riendas`, `desc_profamilia`
- `info_agrosavia`, `info_fedepalma`, `info_profamilia`
- `in_riendas`

Si pones otro id (ej. `boton1`), eki no sabrá qué responder.

**Después de crear la plantilla:**

1. Enviar a **aprobación WhatsApp** (categoría MARKETING).  
2. Cuando quede *Approved*, copias el **Content SID** (`HX…`).  
3. Lo pegas en el servidor: variable de entorno `EKI_DEMO_CAROUSEL_CONTENT_SID=HXxxxxx`.  
4. Sin ese HX, la opción 4 igual funciona pero manda **lista en texto** (fallback), no el carrusel con fotos.

**Orden en pantalla del usuario:** Body → desliza cards → toca botón → eki responde con otro mensaje (descripción o CTA). Eso no se configura en la plantilla: lo hace el código.

### 3.1 Reglas

- Body arriba del carrusel: obligatorio.  
- Por card: title+body ≤ **160** chars; media HTTPS; **1–2 botones**.  
- Mismo **tipo** de botón en el mismo orden en todas (2× `QUICK_REPLY`).  
- Title botón ≤ 25 chars.

### 3.2 Flujo (dos tiempos)

```text
Carrusel
  ├─ «Ver descripción» → texto largo
  │         └─ En Riendas: luego *quiero demo* o *no gracias*
  └─ «Quiero demo» (Riendas) / «Solo info» (vitrina)
```

### 3.3 Body llamativo (recomendado)

**A (usar este):**  
`Así se ve un curso eki: corto, por WhatsApp, a su ritmo. Tome las riendas es la que sí se puede probar hoy.`

**B:**  
`Capacitación real por WhatsApp. Deslice los programas: mire ejemplos o entre a la demo de finanzas eki.`

**C:**  
`¿Quiere ver cómo se siente un curso eki? Deslice. Solo Tome las riendas abre la demo; el resto es muestra.`

### 3.4 Cards

| # | title | body corto | Botón 1 | Botón 2 |
|---|--------|------------|---------|---------|
| 1 | Agrosavia · campo | Técnicas de finca por chat. Ejemplo eki. | `desc_agrosavia` Ver descripción | `info_agrosavia` Solo info |
| 2 | Fedepalma · palma | Buenas prácticas en formato WhatsApp. | `desc_fedepalma` | `info_fedepalma` |
| 3 | eki · Riendas | Tome las riendas de su dinero. Demo real. | `desc_riendas` | `in_riendas` **Quiero demo** |
| 4 | Profamilia · bienestar | Bienestar paso a paso por WhatsApp. | `desc_profamilia` | `info_profamilia` |

Si Meta rechaza titles distintos en el botón 2, unificar a `Siguiente` y distinguir solo por `id`.

### 3.5 JSON Content API (v2)

```json
{
  "friendly_name": "eki_demo_carrusel_programas_v2",
  "language": "es",
  "variables": {},
  "types": {
    "twilio/carousel": {
      "body": "Deslice y descubra cómo se aprende con eki por WhatsApp. Toque una tarjeta: lea la descripción o, en finanzas, pida la demo.",
      "cards": [
        {
          "title": "Agrosavia · campo",
          "body": "Técnicas de finca por chat. Ejemplo eki.",
          "media": "https://REEMPLAZAR/media/demo/carrusel_agrosavia.jpg",
          "actions": [
            {"type": "QUICK_REPLY", "title": "Ver descripción", "id": "desc_agrosavia"},
            {"type": "QUICK_REPLY", "title": "Solo info", "id": "info_agrosavia"}
          ]
        },
        {
          "title": "Fedepalma · palma",
          "body": "Buenas prácticas en formato WhatsApp.",
          "media": "https://REEMPLAZAR/media/demo/carrusel_fedepalma.jpg",
          "actions": [
            {"type": "QUICK_REPLY", "title": "Ver descripción", "id": "desc_fedepalma"},
            {"type": "QUICK_REPLY", "title": "Solo info", "id": "info_fedepalma"}
          ]
        },
        {
          "title": "eki · Riendas",
          "body": "Tome las riendas de su dinero. Demo real.",
          "media": "https://REEMPLAZAR/media/demo/carrusel_riendas.jpg",
          "actions": [
            {"type": "QUICK_REPLY", "title": "Ver descripción", "id": "desc_riendas"},
            {"type": "QUICK_REPLY", "title": "Quiero demo", "id": "in_riendas"}
          ]
        },
        {
          "title": "Profamilia · bienestar",
          "body": "Bienestar paso a paso por WhatsApp.",
          "media": "https://REEMPLAZAR/media/demo/carrusel_profamilia.jpg",
          "actions": [
            {"type": "QUICK_REPLY", "title": "Ver descripción", "id": "desc_profamilia"},
            {"type": "QUICK_REPLY", "title": "Solo info", "id": "info_profamilia"}
          ]
        }
      ]
    }
  }
}
```

Tras crear: `HX…` → `EKI_DEMO_CAROUSEL_CONTENT_SID`.

### 3.5.1 Assets generados (21 ago 2026)

| Card | URL pública |
|------|-------------|
| Agrosavia (abejas) | `https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo/carrusel_agrosavia.jpg` |
| Fedepalma (panela) | `https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo/carrusel_fedepalma.jpg` |
| eki Riendas (dinero) | `https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo/carrusel_riendas.jpg` |
| Profamilia (bienestar*) | `https://eki-produccion.s3.us-east-2.amazonaws.com/media/demo/carrusel_profamilia.jpg` |

\*Visual de bienestar (no logo oficial Profamilia). Content SID creado: **`HX9de0ba3d3e333e9476f0859713270ba5`** (`eki_demo_carrusel_programas_v2`).

Tras crear: `HX…` → `EKI_DEMO_CAROUSEL_CONTENT_SID`.

### 3.6 Respuestas eki al tap

| id | Efecto |
|----|--------|
| `desc_*` | Descripción larga |
| `desc_riendas` | Descripción + *quiero demo* / *no gracias* |
| `in_riendas` | CTA: *1* + correo |
| `info_*` | Aviso solo muestra |

**Nunca** crear `Estudiante` ni progreso desde estos taps.

Código: `core/catalogo_demo_carousel.py`.

---

## 4. Seguridad del mismo número

- [ ] Solo si `Estudiante.DoesNotExist`  
- [ ] Estudiante activo → no carrusel  
- [ ] Sin HX → fallback texto  
- [ ] No atar a `listo`

---

## 5. Migración futura a otro número

1. Segundo sender Twilio/WhatsApp.  
2. Mover o clonar HX al número B.  
3. Webhook B → solo vitrina/prospectos.  
4. Número A → solo LMS.

---

## 6. Referencias

- https://www.twilio.com/docs/content/carousel  
- https://www.twilio.com/docs/content/using-variables-with-content-api  

---

*No autoriza envío masivo hasta HX aprobado y smoke en 1–2 números.*
