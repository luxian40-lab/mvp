# L3 — ventana 24 h y retoma (sin tocar clientes todavía)

Fecha: 25 de noviembre de 2026. Solo Meta. Twilio no entra al curso.

## No hacer ahora

- No Wave a los 9 ni a los 15 de AgriCapital.
- No mezclar este arreglo con un deploy de portal.
- No parche en vivo sin este contrato y sin la prueba del 0629.
- No cambiar L1 ni L2 en este commit.

## Fase 1 — Contrato

1. Ventana abierta = entrante real en esa línea en las últimas `WA_VENTANA_HORAS` (hoy 23). Un botón de plantilla no cuenta como ventana para media.
2. Si la ventana está cerrada y la persona escribe *Continuar* / *listo* en L3: **no** se llama `continuar_leccion` (eso subía el paso aunque Meta no entregara).
3. En ese caso se manda como mucho **una** plantilla UTILITY cada 20 h: `eki_avance_curso_img` + imagen `recordatorio_curso.jpg`. Variables: nombre, curso, módulo.
4. Si la plantilla está vacía en settings: se omite el envío de sesión y tampoco se avanza el paso.
5. Si la ventana está abierta: sigue el camino de hoy (clase de sesión por Meta).
6. L1 y L2 no pasan por `registro_cursos._avanzar`. Este slice no los cambia.
7. Un fallo `131047` que llega después (webhook de estado) no se reintenta con media libre. El reenganche es la plantilla, no otro dump de sesión.
8. Certificados y portal no se tocan aquí.

## Fase 2 — Checklist solo 0629 (no otros números)

1. El 0629 está como Julian, AgriCapital, Maquinaria módulo 2.
2. Escribir a mano *Continuar* en el chat de la línea 3 (no solo el botón de la plantilla).
3. Debe llegar el texto y la media del módulo, estado `delivered` o `read`, sin `131047`.
4. El paso del progreso no debe subir si la media no salió.
5. Recién con eso en verde se habla de deploy. Nadie más recibe mensaje en esta fase.

## Fase 3 — Código (este branch)

- `core/lineas/registro_cursos.py`: ventana cerrada → retoma, sin `continuar_leccion`. Si la ventana está abierta y el envío de la lección falla (`success` falso, p. ej. 131047), se restauran paso y módulo de antes de ese turno.
- `mvp_project/settings.py`: `EKI_REGISTRO_REENGANCHE_PLANTILLA` y `EKI_REGISTRO_REENGANCHE_IMAGEN` con default en código (el bloque de variables de EB ya está al tope; no hace falta `setenv`).
- Tests: `test_listo_ventana_cerrada_no_avanza_ni_vuelca_leccion`, `test_listo_ventana_cerrada_sin_plantilla_no_envia`.

Deploy: solo cuando se pida, label `main-wa-registro-retoma-*`. Rollback = versión EB anterior.

## Fase 4 — Ops (lista, no ejecutar)

Cuando la fase 2 pase y haya deploy:

- Plantilla `eki_avance_curso_img` (UTILITY), imagen `recordatorio_curso.jpg`.
- Línea `1477762615411333` (L3).
- Orden interno: 0629 otra vez, después los 9, después los 6. No marketing `eki_retoma_curso_img`.
- **Esta fase no se corre en esta sesión.**

## Fase 5 — L1 y L2, otro commit

El mismo `131047` puede salir en `sandbox_meta` si se manda media de sesión fuera de 24 h. En 7 días el volumen real estuvo en L3 (`registro_cursos`). L1/L2 quedan para un commit aparte, con el mismo contrato, cuando Agri esté estable. No se mezclan en este diff.
