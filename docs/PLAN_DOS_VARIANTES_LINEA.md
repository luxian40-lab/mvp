# Plan: dos variantes de línea (Twilio-like vs Meta)

Un cambio por commit. No mezclar pasadas.

## Modelo

| | Línea 2 | Línea principal |
|---|---|---|
| Nombre de producto | Modo Twilio (tal cual) | Versión Meta |
| Menú | No. Sin carrusel. Sin Formación/Asesoría. | Carrusel / lista de cursos + agentes |
| Agentes | Solo Formador y Compañero dentro del curso | Lista de agentes (nat, coach, …) |
| Entrada | Campaña, inscripción o curso ya abierto | Menú sandbox Meta |
| Avance | listo / continuar (mismo flujo de siempre) | Continuar en Meta + mismo avance de curso |
| Campañas | Salen por su `phone_number_id` | Salen por el de la principal |

Twilio el canal HTTP solo queda para el **aula**. La línea 2 es Meta Cloud API con **comportamiento** del curso viejo.

## Pasada 1 — Línea 2 = flujo curso lineal (esta)

1. Quien escribe a la línea 2 no entra al menú carrusel.
2. Tras habeas / cédula / confirmación, el mensaje va al camino de curso (`ruta=cursos`).
3. Asesoría y agentes separados se cortan.
4. El admin «Línea 2» deja de hablar de carrusel; deja claro: curso por campaña o inscripción.
5. Tests: hola en L2 no manda carrusel; asesoria no abre agentes.

## Pasada 2 — Principal = versión Meta (sin romper)

1. Carrusel / lista, casillas de cursos y agentes en Cliente.
2. Primer continuar de curso nuevo = saludo Formador/Compañero + módulo 1.
3. No tocar el cuerpo Twilio de aula.

## Pasada 3 — Campañas por la línea 2

1. En la ficha de campaña se elige «Línea 2 · modo Twilio».
2. El envío usa `CampanaMeta.phone_number_id`.
3. Solo plantillas de la WABA de esa línea. Si es de la principal, el formulario y el envío cortan.
4. Tras el toque, la respuesta sigue en L2 → Pasada 1 (curso lineal).
5. Smoke real cuando el 6193 esté CONNECTED. `WHATSAPP_BUSINESS_ACCOUNT_ID_2` en el entorno, vacío por defecto.

## Fuera de alcance hasta autorizar deploy

- Desplegar.
- Apagar HSM Twilio viejo.
- Mezclar catálogo del Cliente en la línea 2.
